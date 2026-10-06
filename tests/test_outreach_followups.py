"""Comprehensive unit tests for Outreach Center follow-up cadences, scheduler, and pause/resume logic."""

from datetime import datetime, timedelta, timezone
import json
import unittest

from sqlalchemy import select

from app import app
from app.db.base import utc_now
from app.db.models import Application, Communication, Company, Contact, FollowUp, Job, User
from app.db.session import SessionLocal, get_db_session
from app.services.dto.outreach_dto import ExpandedInboundEmailDTO, OutreachCreateDTO
from app.services.dto.outreach_enums import (
    FollowUpStatus,
    MessageStatus,
)
from app.services.email.factory import register_email_provider, unregister_email_provider
from app.services.email.mock_provider import MockEmailProvider
from app.services.followup_scheduler import FollowUpScheduler
from app.services.inbound_sync_service import InboundSyncService
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService


class TestOutreachFollowups(unittest.TestCase):
    """Verifies sequence creation, step progression, execution, and cadence pausing."""

    def setUp(self):
        self.client = app.test_client()
        self.mock_provider = MockEmailProvider(account_email="tester@jobpilot.local")
        register_email_provider("default", self.mock_provider)
        self.dispatcher = OutreachDispatcher(session_factory=SessionLocal)
        self.scheduler = FollowUpScheduler(session_factory=SessionLocal, dispatcher=self.dispatcher)
        self.service = OutreachService(session_factory=SessionLocal)

        # Seed candidate user
        with get_db_session(SessionLocal) as s:
            user = s.get(User, 1)
            if not user:
                s.add(User(id=1, name="Alex Mercer", email="alex@jobpilot.local", is_active=True))
                s.commit()

    def tearDown(self):
        unregister_email_provider("default")
        with get_db_session(SessionLocal) as s:
            test_contacts = select(Contact.id).where(Contact.email.like("%@corp.test"))
            test_apps = s.query(Application).filter(
                Application.application_type == "EMAIL",
                Application.contact_id.in_(test_contacts),
            ).all()
            for app in test_apps:
                s.query(FollowUp).filter(FollowUp.application_id == app.id).delete(synchronize_session=False)
                s.query(Communication).filter(Communication.application_id == app.id).delete(synchronize_session=False)
                s.delete(app)
            s.query(Contact).filter(Contact.email.like("%@corp.test")).delete(synchronize_session=False)
            s.query(Company).filter(Company.name.like("Cadence Corp%")).delete(synchronize_session=False)
            s.query(User).filter(User.email.in_(["tester@jobpilot.local", "alex@jobpilot.local"])).delete(synchronize_session=False)
            s.commit()

    def _create_test_application(self, recruiter_email="recruiter_fu@corp.test", cadence_days=None):
        """Helper to create a fresh application with outreach communication and cadences."""
        if cadence_days is None:
            cadence_days = [4, 10, 17]

        dto = OutreachCreateDTO(
            manual_company_name="Cadence Corp",
            manual_job_title="Lead RPA Architect",
            contact_name="Sarah Connor",
            contact_email=recruiter_email,
            subject="Application: Lead RPA Architect",
            body_text="Hello Sarah, I am excited to apply.",
            followup_cadence_days=cadence_days,
            override_duplicate=True,
        )

        res = self.service.send_outreach(
            dto=dto,
            sender_name="Alex Mercer",
            sender_email="alex@jobpilot.local",
        )
        app_id = res["application_id"]

        with get_db_session(SessionLocal) as s:
            followups = s.query(FollowUp).filter(FollowUp.application_id == app_id).all()

        return app_id, res, followups

    def test_cadence_creation(self):
        """Dispatched outreach generates sequential FollowUp records."""
        app_id, send_res, followups = self._create_test_application(
            recruiter_email="sarah_cadence@corp.test",
            cadence_days=[3, 7, 14],
        )
        self.assertTrue(send_res["success"])
        self.assertEqual(len(followups), 3)

        with get_db_session(SessionLocal) as s:
            fus = s.query(FollowUp).filter(FollowUp.application_id == app_id).order_by(FollowUp.step_number.asc()).all()
            self.assertEqual(len(fus), 3)
            self.assertEqual(fus[0].step_number, 1)
            self.assertEqual(fus[0].status, FollowUpStatus.PENDING.value)
            self.assertEqual(fus[1].step_number, 2)
            self.assertEqual(fus[2].step_number, 3)

            # Check that due_at is ordered progressively
            self.assertLess(fus[0].due_at, fus[1].due_at)
            self.assertLess(fus[1].due_at, fus[2].due_at)

    def test_refresh_due_statuses(self):
        """Pending follow-ups transition to DUE when due_at arrives."""
        app_id, _, _ = self._create_test_application(recruiter_email="overdue@corp.test", cadence_days=[5])

        with get_db_session(SessionLocal) as s:
            fu = s.query(FollowUp).filter(FollowUp.application_id == app_id).first()
            # Artificially set due_at in the past
            fu.due_at = datetime.now(timezone.utc) - timedelta(hours=2)
            s.commit()

        # Run scheduler refresh
        due_count = self.scheduler.refresh_due_statuses()
        self.assertGreaterEqual(due_count, 1)

        with get_db_session(SessionLocal) as s:
            fu = s.query(FollowUp).filter(FollowUp.application_id == app_id).first()
            self.assertEqual(fu.status, FollowUpStatus.DUE.value)

    def test_prepare_followup_draft(self):
        """FollowUpScheduler prepares pre-rendered step templates with context."""
        app_id, _, _ = self._create_test_application(recruiter_email="draft_check@corp.test", cadence_days=[4, 10])

        with get_db_session(SessionLocal) as s:
            fu = s.query(FollowUp).filter(FollowUp.application_id == app_id, FollowUp.step_number == 1).first()
            fu_id = fu.id

        draft = self.scheduler.prepare_followup_draft(fu_id)
        self.assertEqual(draft["followup_id"], fu_id)
        self.assertEqual(draft["step_number"], 1)
        self.assertIn("Lead RPA Architect", draft["subject"])
        self.assertTrue(len(draft["body_text"]) > 20)

    def test_execute_followup(self):
        """Executing a follow-up sends the email and marks the record COMPLETED."""
        app_id, _, _ = self._create_test_application(recruiter_email="exec_fu@corp.test", cadence_days=[4])

        with get_db_session(SessionLocal) as s:
            fu = s.query(FollowUp).filter(FollowUp.application_id == app_id).first()
            fu_id = fu.id

        res = self.scheduler.execute_followup(fu_id, custom_subject="Polite follow-up", custom_body="Just following up!")
        self.assertTrue(res["success"])
        self.assertEqual(res["status"], "COMPLETED")

        with get_db_session(SessionLocal) as s:
            fu_updated = s.get(FollowUp, fu_id)
            self.assertEqual(fu_updated.status, FollowUpStatus.COMPLETED.value)
            self.assertIsNotNone(fu_updated.completed_at)

    def test_manual_pause_and_resume_service(self):
        """Service can pause and resume follow-up cadence, blocking execution while paused."""
        app_id, _, _ = self._create_test_application(recruiter_email="pause_fu@corp.test", cadence_days=[4, 10])

        # Pause
        paused = self.service.pause_followups(app_id, reason="Recruiter scheduled call")
        self.assertEqual(paused, 2)

        with get_db_session(SessionLocal) as s:
            fus = s.query(FollowUp).filter(FollowUp.application_id == app_id).all()
            for f in fus:
                self.assertEqual(f.status, FollowUpStatus.PAUSED.value)
                self.assertEqual(f.paused_reason, "Recruiter scheduled call")

        # Attempt to execute while paused -> must fail gracefully
        exec_attempt = self.scheduler.execute_followup(fus[0].id)
        self.assertFalse(exec_attempt["success"])
        self.assertIn("paused", exec_attempt["error"].lower())

        # Resume
        resumed = self.service.resume_followups(app_id)
        self.assertEqual(resumed, 2)

        with get_db_session(SessionLocal) as s:
            fus_resumed = s.query(FollowUp).filter(FollowUp.application_id == app_id).all()
            for f in fus_resumed:
                self.assertEqual(f.status, FollowUpStatus.PENDING.value)
                self.assertIsNone(f.paused_reason)

    def test_pause_and_resume_rest_api(self):
        """REST endpoints POST /conversations/<id>/pause and /resume work as expected."""
        app_id, _, _ = self._create_test_application(recruiter_email="api_pause@corp.test", cadence_days=[4])

        # Pause via API
        res = self.client.post(
            f"/api/outreach/conversations/{app_id}/pause",
            data=json.dumps({"reason": "Manual dashboard test"}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["paused_count"], 1)

        # Resume via API
        res2 = self.client.post(f"/api/outreach/conversations/{app_id}/resume")
        self.assertEqual(res2.status_code, 200)
        data2 = res2.get_json()
        self.assertEqual(data2["resumed_count"], 1)

    def test_auto_pause_on_inbound_recruiter_reply(self):
        """When an inbound reply arrives, pending follow-ups are auto-paused."""
        app_id, send_res, _ = self._create_test_application(recruiter_email="sarah_reply@corp.test", cadence_days=[4, 10])
        outbound_msg_id = send_res["provider_message_id"]

        # Enqueue reply into mock provider
        reply_dto = ExpandedInboundEmailDTO(
            message_id=f"recruiter-reply-{app_id}@corp.test",
            from_address="sarah_reply@corp.test",
            to_addresses=["alex@jobpilot.local"],
            subject="Re: Application: Lead RPA Architect",
            body_text="Hi Alex, thanks for applying. Let's talk tomorrow at 2 PM.",
            received_at=datetime.now(timezone.utc),
            in_reply_to=outbound_msg_id,
        )
        self.mock_provider.enqueue_inbound(reply_dto)

        inbound_service = InboundSyncService(
            session_factory=SessionLocal,
            outreach_service=self.service,
            provider=self.mock_provider,
        )
        sync_result = inbound_service.sync_mailbox()
        self.assertTrue(sync_result["success"])
        self.assertEqual(sync_result["matched_count"], 1)

        # Verify all pending follow-ups for this application are now PAUSED
        with get_db_session(SessionLocal) as s:
            fus = s.query(FollowUp).filter(FollowUp.application_id == app_id).all()
            self.assertEqual(len(fus), 2)
            for f in fus:
                self.assertEqual(f.status, FollowUpStatus.PAUSED.value)
                self.assertIn("recruiter reply", f.paused_reason.lower())


if __name__ == "__main__":
    unittest.main()
