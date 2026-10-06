"""Unit tests for inbound recruiter synchronization, 3-tier thread matching, and auto-pause invariant."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, FollowUp, User
from app.services.dto.outreach_dto import ExpandedInboundEmailDTO, OutreachCreateDTO
from app.services.dto.outreach_enums import FollowUpStatus, MessageStatus
from app.services.email.mock_provider import MockEmailProvider
from app.services.inbound_sync_service import InboundSyncService
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService


class TestOutreachInboundSync(unittest.TestCase):
    """Verifies recruiter reply matching and the critical follow-up auto-pause invariant."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "sync_test.db")
        self.attach_dir = Path(self.temp_dir) / "attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Candidate User", email="candidate@test.com", is_active=True)
            s.add(u)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="candidate@test.com")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=self.attach_dir,
            default_provider=self.mock_provider,
        )
        self.outreach_svc = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
            email_provider=self.mock_provider,
        )
        self.sync_svc = InboundSyncService(
            session_factory=self.Session,
            outreach_service=self.outreach_svc,
            provider=self.mock_provider,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tier1_header_matching_and_auto_pause(self):
        """Tier 1: Recruiter reply with In-Reply-To header matches and auto-pauses all follow-ups."""
        uid = uuid.uuid4().hex[:6]
        dto = OutreachCreateDTO(
            manual_company_name=f"Acme Cyber {uid}",
            manual_job_title="Security Lead",
            contact_name="Dan Recruiter",
            contact_email=f"dan_{uid}@acmecyber.test",
            subject="Job Application: Security Lead",
            body_text="Hi Dan, please consider my application.",
            followup_cadence_days=[4, 10, 18],
        )
        send_res = self.outreach_svc.send_outreach(dto)
        self.assertTrue(send_res["success"])
        app_id = send_res["application_id"]
        comm_id = send_res["communication_id"]
        outbound_msg_id = send_res["provider_message_id"]

        # Verify follow-ups are initially PENDING
        timeline_before = self.outreach_svc.get_conversation_timeline(app_id)
        self.assertEqual(len(timeline_before["follow_ups"]), 3)
        for fu in timeline_before["follow_ups"]:
            self.assertEqual(fu["status"], FollowUpStatus.PENDING.value)

        # Simulate recruiter reply with In-Reply-To header
        reply_dto = ExpandedInboundEmailDTO(
            message_id=f"recruiter-msg-{uid}@acmecyber.test",
            from_address=f"dan_{uid}@acmecyber.test",
            to_addresses=["candidate@test.com"],
            subject="Re: Job Application: Security Lead",
            body_text="Thanks for reaching out! We'd love to set up an interview.",
            received_at=datetime.now(timezone.utc),
            in_reply_to=outbound_msg_id,
        )
        self.mock_provider.enqueue_inbound(reply_dto)

        # Run sync
        sync_result = self.sync_svc.sync_mailbox()
        self.assertTrue(sync_result["success"])
        self.assertEqual(sync_result["matched_count"], 1)

        # Verify critical invariant: follow-ups are now PAUSED
        timeline_after = self.outreach_svc.get_conversation_timeline(app_id)
        self.assertEqual(timeline_after["conversation_state"], "REPLIED")
        self.assertEqual(timeline_after["status"], "RECRUITER_CONTACTED")
        self.assertEqual(len(timeline_after["communications"]), 2)  # 1 outbound + 1 inbound

        for fu in timeline_after["follow_ups"]:
            self.assertEqual(fu["status"], FollowUpStatus.PAUSED.value)
            self.assertIn("Recruiter reply received", fu["paused_reason"])

    def test_tier2_recruiter_email_matching(self):
        """Tier 2: Inbound matches when from_address matches recruiter email even without thread headers."""
        uid = uuid.uuid4().hex[:6]
        dto = OutreachCreateDTO(
            manual_company_name=f"Vanguard AI {uid}",
            manual_job_title="ML Ops Lead",
            contact_name="Elena",
            contact_email=f"elena_{uid}@vanguard.test",
            subject="Application: ML Ops Lead",
            body_text="Hi Elena",
            followup_cadence_days=[5, 12],
        )
        send_res = self.outreach_svc.send_outreach(dto)
        app_id = send_res["application_id"]

        # Recruiter replies from new thread (no In-Reply-To)
        new_thread_reply = ExpandedInboundEmailDTO(
            message_id=f"fresh-thread-{uid}@vanguard.test",
            from_address=f"elena_{uid}@vanguard.test",
            to_addresses=["candidate@test.com"],
            subject="Regarding your application at Vanguard AI",
            body_text="Hi Candidate, we liked your profile. When are you free for a call?",
            received_at=datetime.now(timezone.utc),
        )
        self.mock_provider.enqueue_inbound(new_thread_reply)

        sync_result = self.sync_svc.sync_mailbox()
        self.assertEqual(sync_result["matched_count"], 1)

        timeline = self.outreach_svc.get_conversation_timeline(app_id)
        self.assertEqual(timeline["conversation_state"], "REPLIED")
        for fu in timeline["follow_ups"]:
            self.assertEqual(fu["status"], FollowUpStatus.PAUSED.value)

    def test_tier3_subject_token_matching(self):
        """Tier 3: Inbound matches based on company name in subject if sender email differs."""
        uid = uuid.uuid4().hex[:6]
        company_name = f"Solaris Energy {uid}"
        dto = OutreachCreateDTO(
            manual_company_name=company_name,
            manual_job_title="Cloud Engineer",
            contact_name="Solaris HR",
            contact_email=f"hr_{uid}@solaris.test",
            subject="Job Application: Cloud Engineer",
            body_text="Hi Solaris team",
            followup_cadence_days=[3],
        )
        send_res = self.outreach_svc.send_outreach(dto)
        app_id = send_res["application_id"]

        # Reply from a different recruiter / coordinator email
        coord_reply = ExpandedInboundEmailDTO(
            message_id=f"coord-{uid}@solaris.test",
            from_address=f"coordinator_{uid}@solaris-talent.com",
            to_addresses=["candidate@test.com"],
            subject=f"Re: Cloud Engineer position at {company_name}",
            body_text="Hi Candidate, moving you to interview round.",
            received_at=datetime.now(timezone.utc),
        )
        self.mock_provider.enqueue_inbound(coord_reply)

        sync_result = self.sync_svc.sync_mailbox()
        self.assertEqual(sync_result["matched_count"], 1)

        timeline = self.outreach_svc.get_conversation_timeline(app_id)
        self.assertEqual(timeline["conversation_state"], "REPLIED")

    def test_inbound_deduplication(self):
        """Syncing the same inbound email multiple times is idempotent."""
        uid = uuid.uuid4().hex[:6]
        dto = OutreachCreateDTO(
            manual_company_name=f"Dedup Corp {uid}",
            manual_job_title="Tester",
            contact_email=f"tester_{uid}@dedup.test",
            subject="Application",
            body_text="Hello",
        )
        send_res = self.outreach_svc.send_outreach(dto)
        app_id = send_res["application_id"]

        reply = ExpandedInboundEmailDTO(
            message_id=f"dedup-msg-{uid}@dedup.test",
            from_address=f"tester_{uid}@dedup.test",
            to_addresses=["candidate@test.com"],
            subject="Re: Application",
            body_text="Reply content",
            received_at=datetime.now(timezone.utc),
        )
        self.mock_provider.enqueue_inbound(reply)

        # First sync
        res1 = self.sync_svc.sync_mailbox()
        self.assertEqual(res1["matched_count"], 1)

        # Second sync
        res2 = self.sync_svc.sync_mailbox()
        self.assertEqual(res2["matched_count"], 0)

        timeline = self.outreach_svc.get_conversation_timeline(app_id)
        # Should remain exactly 2 communications (1 outbound + 1 inbound)
        self.assertEqual(len(timeline["communications"]), 2)


if __name__ == "__main__":
    unittest.main()
