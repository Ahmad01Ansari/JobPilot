"""Unit tests for Outreach lifecycle state management, closing conversations, and auto-stale logic."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, FollowUp, Job, User
from app.db.models.status_history import ApplicationStatusHistory
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    ConversationOpState,
    FollowUpStatus,
    MessageStatus,
    WorkQueueSection,
)
from app.services.dto.outreach_viewmodels import PresentationConversationState
from app.services.email.mock_provider import MockEmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService


class TestOutreachLifecycleManagement(unittest.TestCase):
    """Verifies manual status transitions, conversation closing, and ghosting auto-stale policies."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "lifecycle_test.db")
        self.attach_dir = Path(self.temp_dir) / "attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Jane Candidate", email="jane@candidate.test", is_active=True)
            s.add(u)
            comp = Company(id=1, name="Acme Corp", normalized_name="acme corp")
            s.add(comp)
            job = Job(id=1, title="Software Engineer", company_id=1, company_raw="Acme Corp", platform="EMAIL", job_fingerprint="fp_test_123", source_url="email://alice@acme.test")
            s.add(job)
            contact = Contact(id=1, name="Alice Recruiter", email="alice@acme.test", company_id=1)
            s.add(contact)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="jane@candidate.test")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=self.attach_dir,
            default_provider=self.mock_provider,
        )
        self.service = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
            email_provider=self.mock_provider,
        )

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_close_conversation_cancels_followups_and_records_audit(self):
        """Calling close_conversation cancels all active follow-ups and records status history."""
        now = datetime.now(timezone.utc)
        with self.Session() as s:
            app = Application(
                id=1,
                job_id=1,
                contact_id=1,
                user_id=1,
                status="SUBMITTED",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                applied_at=now,
                created_at=now,
            )
            s.add(app)
            fu1 = FollowUp(id=1, application_id=1, step_number=1, due_at=now + timedelta(days=3), status=FollowUpStatus.PENDING.value)
            fu2 = FollowUp(id=2, application_id=1, step_number=2, due_at=now + timedelta(days=7), status=FollowUpStatus.DUE.value)
            s.add_all([fu1, fu2])
            s.commit()

        success = self.service.close_conversation(1, reason="Candidate took another offer")
        self.assertTrue(success)

        with self.Session() as s:
            app = s.get(Application, 1)
            self.assertEqual(app.status, "CLOSED")

            followups = s.execute(select(FollowUp).where(FollowUp.application_id == 1)).scalars().all()
            for fu in followups:
                self.assertEqual(fu.status, FollowUpStatus.CANCELLED.value)

            history = s.execute(
                select(ApplicationStatusHistory).where(ApplicationStatusHistory.application_id == 1)
            ).scalars().all()
            self.assertGreaterEqual(len(history), 1)
            self.assertEqual(history[-1].new_status, "CLOSED")
            self.assertEqual(history[-1].notes, "Candidate took another offer")

    def test_update_application_status_to_terminal_cancels_cadence(self):
        """Transitioning application status to REJECTED or OFFER automatically halts follow-ups."""
        now = datetime.now(timezone.utc)
        with self.Session() as s:
            app = Application(
                id=2,
                job_id=1,
                contact_id=1,
                user_id=1,
                status="UNDER_REVIEW",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                applied_at=now,
                created_at=now,
            )
            s.add(app)
            fu = FollowUp(id=3, application_id=2, step_number=1, due_at=now + timedelta(days=3), status=FollowUpStatus.PENDING.value)
            s.add(fu)
            s.commit()

        # Update to INTERVIEW -> followups remain active
        self.service.update_application_status(2, "INTERVIEW")
        with self.Session() as s:
            fu = s.get(FollowUp, 3)
            self.assertEqual(fu.status, FollowUpStatus.PENDING.value)

        # Update to REJECTED -> followups cancelled
        self.service.update_application_status(2, "REJECTED")
        with self.Session() as s:
            app = s.get(Application, 2)
            self.assertEqual(app.status, "REJECTED")
            fu = s.get(FollowUp, 3)
            self.assertEqual(fu.status, FollowUpStatus.CANCELLED.value)

    def test_auto_stale_ghosting_detection(self):
        """An application with no response for >= 30 days after cadence completed is classified as CLOSED."""
        stale_time = datetime.now(timezone.utc) - timedelta(days=45)
        with self.Session() as s:
            app = Application(
                id=3,
                job_id=1,
                contact_id=1,
                user_id=1,
                status="SUBMITTED",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                applied_at=stale_time,
                created_at=stale_time,
            )
            s.add(app)
            comm = Communication(
                id=1,
                application_id=3,
                direction="OUTBOUND",
                status=MessageStatus.SENT.value,
                occurred_at=stale_time,
                subject="Initial Pitch",
            )
            s.add(comm)
            # Follow-up completed 40 days ago
            fu = FollowUp(id=4, application_id=3, step_number=1, due_at=stale_time + timedelta(days=3), status=FollowUpStatus.COMPLETED.value)
            s.add(fu)
            s.commit()

        # list_conversations_vm presentation state
        vms = self.service.list_conversations_vm()
        self.assertEqual(len(vms), 1)
        self.assertEqual(vms[0].state, PresentationConversationState.COMPLETED)

        # list_outreach_cases operational case
        cases = self.service.list_outreach_cases()
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0].conversation_state, ConversationOpState.CLOSED)
        self.assertEqual(cases[0].work_queue_section, WorkQueueSection.CLOSED)
        self.assertIn("Closed (Ghosted / Stale)", cases[0].next_action_headline)

    def test_get_outreach_stats_includes_closed(self):
        """get_outreach_stats returns accurate closed metric counts matching list view."""
        now = datetime.now(timezone.utc)
        stale_time = now - timedelta(days=40)
        with self.Session() as s:
            app1 = Application(id=4, job_id=1, user_id=1, status="CLOSED", application_type=CANONICAL_APPLICATION_METHOD_EMAIL, created_at=now)
            app2 = Application(id=5, job_id=1, user_id=1, status="SUBMITTED", application_type=CANONICAL_APPLICATION_METHOD_EMAIL, created_at=now)
            # app3 is stale (> 30 days)
            app3 = Application(id=6, job_id=1, user_id=1, status="SUBMITTED", application_type=CANONICAL_APPLICATION_METHOD_EMAIL, created_at=stale_time)
            s.add_all([app1, app2, app3])
            s.commit()

        stats = self.service.get_outreach_stats()
        closed_list = self.service.list_conversations_vm(state_filter="CLOSED")
        self.assertEqual(stats["closed"], 2)  # app1 (CLOSED) + app3 (stale)
        self.assertEqual(stats["total_closed"], 2)
        self.assertEqual(stats["total_outreached"], 3)
        self.assertEqual(stats["closed"], len(closed_list))

    def test_transition_status_to_closed_cancels_scheduled_interview_and_followups(self):
        """Transitioning an application to CLOSED cancels any scheduled interviews and follow-ups."""
        from app.db.models.interview import Interview
        from app.repositories.application_repository import ApplicationRepository
        now = datetime.now(timezone.utc)
        with self.Session() as s:
            app = Application(
                id=7,
                job_id=1,
                user_id=1,
                status="INTERVIEW",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                created_at=now,
            )
            s.add(app)
            iv = Interview(
                id=101,
                application_id=7,
                round_number=1,
                round_name="Technical Screen",
                scheduled_at=now + timedelta(days=2),
                status="SCHEDULED",
            )
            fu = FollowUp(
                id=101,
                application_id=7,
                step_number=1,
                due_at=now + timedelta(days=3),
                status=FollowUpStatus.PENDING.value,
            )
            s.add_all([iv, fu])
            s.commit()

        with self.Session() as s:
            repo = ApplicationRepository(s)
            repo.transition_status(application_id=7, new_status="CLOSED", source="test", allow_override=True)
            s.commit()

        with self.Session() as s:
            app = s.get(Application, 7)
            self.assertEqual(app.status, "CLOSED")
            iv = s.get(Interview, 101)
            self.assertEqual(iv.status, "CANCELLED")
            fu = s.get(FollowUp, 101)
            self.assertEqual(fu.status, FollowUpStatus.CANCELLED.value)


if __name__ == "__main__":
    unittest.main()
