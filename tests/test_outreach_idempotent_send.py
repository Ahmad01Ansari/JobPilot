"""Unit tests for OutreachDispatcher 2-phase idempotent outbox dispatch."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, FollowUp, Job, Resume, User
from app.services.dto.outreach_dto import OutreachCreateDTO, SendResultDTO
from app.services.dto.outreach_enums import FollowUpStatus, MessageStatus
from app.services.email.mock_provider import MockEmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher


class TestOutreachIdempotentSend(unittest.TestCase):
    """Verifies 2-phase outbox database transactions, fault isolation, and reconciliation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "outbox_test.db")
        self.attach_dir = Path(self.temp_dir) / "staged_attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Seed candidate user and a sample resume file
        self.dummy_resume_file = os.path.join(self.temp_dir, "My_Resume.pdf")
        with open(self.dummy_resume_file, "wb") as f:
            f.write(b"%PDF-1.4 sample resume content for testing")

        with self.Session() as s:
            u = User(id=1, name="Candidate User", email="candidate@test.com", is_active=True)
            res = Resume(
                id=1,
                user_id=1,
                name="Primary Resume",
                file_path=self.dummy_resume_file,
                file_hash="hash_resume_123456",
                version="1.0",
            )
            s.add_all([u, res])
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="candidate@test.com")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=self.attach_dir,
            default_provider=self.mock_provider,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_successful_two_phase_dispatch(self):
        """Phase 1 + 2 executes cleanly: Application, Communication, and FollowUps are created."""
        dto = OutreachCreateDTO(
            manual_company_name="Apex Global Inc.",
            manual_job_title="Senior Automation Engineer",
            manual_job_url="https://apex.com/jobs/42",
            contact_name="Sarah Miller",
            contact_email="smiller@apex.com",
            contact_designation="Director of Engineering",
            resume_id=1,
            subject="Job Application: Senior Automation Engineer",
            body_text="Hello Sarah, please find my application attached.",
            followup_cadence_days=[4, 10, 17],
        )

        send_res, app, comm, dup = self.dispatcher.dispatch_outreach(
            dto=dto,
            sender_name="Candidate User",
            sender_email="candidate@test.com",
            provider=self.mock_provider,
        )

        self.assertIsNone(dup)
        self.assertTrue(send_res.success)
        self.assertEqual(send_res.status, MessageStatus.SENT)
        self.assertIsNotNone(app)
        self.assertIsNotNone(comm)
        self.assertEqual(comm.status, MessageStatus.SENT.value)
        self.assertTrue(comm.provider_message_id.startswith("mock-"))
        self.assertIsNotNone(comm.attachment_snapshot_path)
        self.assertTrue(os.path.exists(comm.attachment_snapshot_path))

        # Check database records
        with self.Session() as s:
            saved_comm = s.get(Communication, comm.id)
            self.assertEqual(saved_comm.status, MessageStatus.SENT.value)

            # Check 3 follow-ups scheduled
            fus = s.execute(
                select(FollowUp).where(FollowUp.application_id == app.id).order_by(FollowUp.step_number)
            ).scalars().all()
            self.assertEqual(len(fus), 3)
            self.assertEqual(fus[0].step_number, 1)
            self.assertEqual(fus[0].status, FollowUpStatus.PENDING.value)
            self.assertEqual(fus[1].step_number, 2)
            self.assertEqual(fus[2].step_number, 3)

    def test_provider_failure_isolates_error(self):
        """When provider fails, Communication is marked FAILED and no FollowUps are created."""
        self.mock_provider.fail_next_send = True
        self.mock_provider.error_message_to_fail = "554 Mailbox quota exceeded"

        dto = OutreachCreateDTO(
            manual_company_name="Beta Systems",
            manual_job_title="DevOps Lead",
            contact_email="hr@betasystems.org",
            subject="Application",
            body_text="Hello HR",
            followup_cadence_days=[3, 7],
        )

        send_res, app, comm, dup = self.dispatcher.dispatch_outreach(
            dto=dto,
            sender_name="Candidate User",
            sender_email="candidate@test.com",
            provider=self.mock_provider,
        )

        self.assertFalse(send_res.success)
        self.assertEqual(send_res.status, MessageStatus.FAILED)
        self.assertIn("554 Mailbox quota exceeded", send_res.error_message)

        with self.Session() as s:
            saved_comm = s.get(Communication, comm.id)
            self.assertEqual(saved_comm.status, MessageStatus.FAILED.value)
            self.assertIn("554", saved_comm.error_message)

            # Confirm NO followups were scheduled
            fus = s.execute(select(FollowUp).where(FollowUp.application_id == app.id)).scalars().all()
            self.assertEqual(len(fus), 0)

    def test_duplicate_pre_commit_blocking(self):
        """Dispatcher refuses pre-commit if duplicate detected and override_duplicate is False."""
        # 1. Send first application
        dto1 = OutreachCreateDTO(
            manual_company_name="Gamma Labs",
            manual_job_title="ML Engineer",
            contact_email="recruiter@gammalabs.ai",
            subject="Application 1",
            body_text="First outreach",
        )
        res1, app1, comm1, _ = self.dispatcher.dispatch_outreach(
            dto=dto1,
            sender_name="Candidate User",
            sender_email="candidate@test.com",
            provider=self.mock_provider,
        )
        self.assertTrue(res1.success)

        # 2. Attempt duplicate send
        dto2 = OutreachCreateDTO(
            manual_company_name="Gamma Labs",
            manual_job_title="ML Engineer",
            contact_email="recruiter@gammalabs.ai",
            subject="Application 2",
            body_text="Duplicate outreach",
            override_duplicate=False,
        )
        res2, app2, comm2, dup2 = self.dispatcher.dispatch_outreach(
            dto=dto2,
            sender_name="Candidate User",
            sender_email="candidate@test.com",
            provider=self.mock_provider,
        )
        self.assertFalse(res2.success)
        self.assertIsNotNone(dup2)
        self.assertTrue(dup2.is_duplicate)
        self.assertIsNone(app2)
        self.assertIsNone(comm2)

    def test_duplicate_override_allowed(self):
        """Setting override_duplicate=True bypasses the duplicate check."""
        dto1 = OutreachCreateDTO(
            manual_company_name="Delta Tech",
            manual_job_title="Data Scientist",
            contact_email="recruiting@deltatech.com",
            subject="Outreach 1",
            body_text="First",
        )
        self.dispatcher.dispatch_outreach(dto1, "Candidate", "candidate@test.com", self.mock_provider)

        dto2 = OutreachCreateDTO(
            manual_company_name="Delta Tech",
            manual_job_title="Data Scientist",
            contact_email="recruiting@deltatech.com",
            subject="Outreach 2",
            body_text="Follow-up on different role",
            override_duplicate=True,
        )
        res2, app2, comm2, dup2 = self.dispatcher.dispatch_outreach(
            dto2, "Candidate", "candidate@test.com", self.mock_provider
        )
        self.assertTrue(res2.success)
        self.assertIsNotNone(app2)
        self.assertIsNotNone(comm2)

    def test_reconciliation_of_stuck_sending_communications(self):
        """Dispatcher reconciles communications stuck in SENDING status."""
        stuck_token = "stk_stuck_999"
        old_time = datetime.now(timezone.utc) - timedelta(minutes=15)

        with self.Session() as s:
            comp = Company(name="Orphan Co", normalized_name="orphan co")
            s.add(comp)
            s.flush()
            job = Job(
                company_id=comp.id,
                platform="EMAIL",
                title="Ghost Role",
                company_raw="Orphan Co",
                source_url="email://orphan",
                job_fingerprint="fp_ghost_999",
            )
            s.add(job)
            s.flush()
            app = Application(job_id=job.id, user_id=1, status="SUBMITTED")
            s.add(app)
            s.flush()

            # Add stuck communication
            stuck_comm = Communication(
                application_id=app.id,
                type="EMAIL",
                direction="OUTBOUND",
                status=MessageStatus.SENDING.value,
                send_token=stuck_token,
                sender_email="candidate@test.com",
                recipient_email="ghost@orphan.com",
                created_at=old_time,
                occurred_at=old_time,
            )
            s.add(stuck_comm)
            s.commit()
            comm_id = stuck_comm.id

        # Run reconciliation without provider confirmation -> should mark FAILED
        count = self.dispatcher.reconcile_in_flight_communications(self.mock_provider, max_age_seconds=60)
        self.assertEqual(count, 1)

        with self.Session() as s:
            reconciled = s.get(Communication, comm_id)
            self.assertEqual(reconciled.status, MessageStatus.FAILED.value)
            self.assertIn("timed out", reconciled.error_message)


if __name__ == "__main__":
    unittest.main()
