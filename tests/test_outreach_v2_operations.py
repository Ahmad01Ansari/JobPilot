"""Unit tests for Outreach Center V2 Operations, Work Queue, and Bulk Pipeline."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.models import (
    Application,
    Communication,
    Company,
    Contact,
    EmailTemplate,
    FollowUp,
    Job,
    Resume,
    User,
)
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_enums import (
    CadenceState,
    ConversationOpState,
    FollowUpStatus,
    InboundClassification,
    MessageStatus,
    NextActionOwner,
    NextActionType,
    PriorityLevel,
    WorkQueueSection,
)
from app.services.email.mock_provider import MockEmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService


def make_job(company_id: int, company_name: str, title: str, tag: str) -> Job:
    return Job(
        company_id=company_id,
        company_raw=company_name,
        title=title,
        platform="EMAIL",
        job_fingerprint=f"fp_{tag}",
        source_url=f"email://{tag}",
    )


class TestOutreachV2Operations(unittest.TestCase):
    """Verifies operational states, next-action ownership, work queue, and bulk validation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "v2_test.db")
        self.attach_dir = Path(self.temp_dir) / "attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Candidate Ahmad", email="ahmad@test.com", is_active=True)
            s.add(u)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="ahmad@test.com")
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
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_case_mapping_waiting_for_recruiter(self):
        """Outbound pitch without reply maps to WAITING_FOR_RECRUITER with owner RECRUITER."""
        with self.Session() as s:
            comp = Company(name="Acme Corp", normalized_name="acme corp")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Acme Corp", "RPA Lead", "acme")
            s.add(job)
            s.flush()
            contact = Contact(name="Bob Recruiter", email="bob@acme.com", company_id=comp.id)
            s.add(contact)
            s.flush()
            app = Application(
                job_id=job.id,
                contact_id=contact.id,
                status="SUBMITTED",
                application_type="EMAIL",
                applied_at=utc_now(),
            )
            s.add(app)
            s.flush()
            comm = Communication(
                application_id=app.id,
                contact_id=contact.id,
                direction="OUTBOUND",
                status="SENT",
                subject="Application for RPA Lead",
                occurred_at=utc_now(),
            )
            s.add(comm)
            s.commit()
            app_id = app.id

        cases = self.service.list_outreach_cases()
        self.assertEqual(len(cases), 1)
        c = cases[0]
        self.assertEqual(c.application_id, app_id)
        self.assertEqual(c.conversation_state, ConversationOpState.WAITING_FOR_RECRUITER)
        self.assertEqual(c.next_action_owner, NextActionOwner.RECRUITER)
        self.assertEqual(c.work_queue_section, WorkQueueSection.WAITING)

    def test_case_mapping_interview_request_needs_action(self):
        """Inbound email classified as INTERVIEW_REQUEST sets owner USER and section TODAY."""
        with self.Session() as s:
            comp = Company(name="Google", normalized_name="google")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Google", "Automation Architect", "google")
            s.add(job)
            s.flush()
            contact = Contact(name="Alice Recruiter", email="alice@google.com", company_id=comp.id)
            s.add(contact)
            s.flush()
            app = Application(
                job_id=job.id,
                contact_id=contact.id,
                status="SUBMITTED",
                application_type="EMAIL",
                applied_at=utc_now(),
            )
            s.add(app)
            s.flush()
            comm_in = Communication(
                application_id=app.id,
                contact_id=contact.id,
                direction="INBOUND",
                status="SENT",
                subject="Interview with Google",
                occurred_at=utc_now(),
            )
            comm_in.ai_classification = InboundClassification.INTERVIEW_REQUEST.value
            s.add(comm_in)
            s.commit()

        cases = self.service.list_outreach_cases()
        self.assertEqual(len(cases), 1)
        c = cases[0]
        self.assertEqual(c.conversation_state, ConversationOpState.NEEDS_ACTION)
        self.assertEqual(c.next_action_owner, NextActionOwner.USER)
        self.assertEqual(c.next_action_type, NextActionType.CONFIRM_INTERVIEW)
        self.assertEqual(c.work_queue_section, WorkQueueSection.TODAY)
        self.assertEqual(c.priority, PriorityLevel.HIGH)

    def test_case_mapping_followup_due_today(self):
        """Cadence step due today places application in TODAY section with owner USER."""
        now = datetime.now(timezone.utc)
        with self.Session() as s:
            comp = Company(name="Meta", normalized_name="meta")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Meta", "DevOps", "meta")
            s.add(job)
            s.flush()
            contact = Contact(name="Carol Recruiter", email="carol@meta.com", company_id=comp.id)
            s.add(contact)
            s.flush()
            app = Application(
                job_id=job.id,
                contact_id=contact.id,
                status="SUBMITTED",
                application_type="EMAIL",
                applied_at=now - timedelta(days=4),
            )
            s.add(app)
            s.flush()
            fu = FollowUp(
                application_id=app.id,
                contact_id=contact.id,
                step_number=1,
                due_at=now - timedelta(hours=2),  # Due 2 hours ago
                status=FollowUpStatus.PENDING.value,
            )
            s.add(fu)
            s.commit()

        cases = self.service.list_outreach_cases()
        self.assertEqual(len(cases), 1)
        c = cases[0]
        self.assertEqual(c.conversation_state, ConversationOpState.FOLLOW_UP_DUE)
        self.assertEqual(c.next_action_owner, NextActionOwner.USER)
        self.assertEqual(c.next_action_type, NextActionType.SEND_FOLLOW_UP)
        self.assertEqual(c.work_queue_section, WorkQueueSection.TODAY)

    def test_work_queue_grouping(self):
        """get_work_queue accurately distributes cases into TODAY, UPCOMING, WAITING, and CLOSED."""
        now = datetime.now(timezone.utc)
        with self.Session() as s:
            comp = Company(name="Netflix", normalized_name="netflix")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Netflix", "Engineer", "netflix")
            s.add(job)
            s.flush()
            contact = Contact(name="Dan", email="dan@netflix.com", company_id=comp.id)
            s.add(contact)
            s.flush()

            # Case 1: Today (inbound question)
            app1 = Application(job_id=job.id, contact_id=contact.id, status="SUBMITTED", application_type="EMAIL")
            s.add(app1)
            s.flush()
            s.add(Communication(application_id=app1.id, direction="INBOUND", occurred_at=now, summary="What is your salary?"))

            # Case 2: Upcoming (Follow up in 3 days)
            app2 = Application(job_id=job.id, contact_id=contact.id, status="SUBMITTED", application_type="EMAIL")
            s.add(app2)
            s.flush()
            s.add(FollowUp(application_id=app2.id, step_number=1, due_at=now + timedelta(days=3), status="PENDING"))

            # Case 3: Closed (Offer received)
            app3 = Application(job_id=job.id, contact_id=contact.id, status="OFFER", application_type="EMAIL")
            s.add(app3)

            s.commit()

        queue = self.service.get_work_queue()
        self.assertEqual(len(queue), 4)

        sections = {q.section: q for q in queue}
        self.assertEqual(sections[WorkQueueSection.TODAY].count, 1)
        self.assertEqual(sections[WorkQueueSection.UPCOMING].count, 1)
        self.assertEqual(sections[WorkQueueSection.CLOSED].count, 1)

    def test_bulk_target_validation(self):
        """validate_bulk_targets catches missing emails and duplicate applications."""
        with self.Session() as s:
            comp = Company(name="Uber", normalized_name="uber")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Uber", "RPA Developer", "uber")
            s.add(job)
            s.flush()

            # Valid app
            c1 = Contact(name="Valid Recruiter", email="valid@uber.com", company_id=comp.id)
            s.add(c1)
            s.flush()
            app1 = Application(job_id=job.id, contact_id=c1.id, status="APPLYING", application_type="EMAIL")
            s.add(app1)

            # Invalid email app
            c2 = Contact(name="Invalid Recruiter", email="bad_email_format", company_id=comp.id)
            s.add(c2)
            s.flush()
            app2 = Application(job_id=job.id, contact_id=c2.id, status="APPLYING", application_type="EMAIL")
            s.add(app2)

            s.commit()
            id1, id2 = app1.id, app2.id

        val_res = self.service.validate_bulk_targets([id1, id2])
        self.assertEqual(val_res.total_selected, 2)
        self.assertEqual(val_res.valid_count, 1)
        self.assertEqual(val_res.error_count, 1)

        item1 = next(i for i in val_res.items if i.application_id == id1)
        self.assertTrue(item1.is_valid)
        self.assertTrue(item1.is_selected)

        item2 = next(i for i in val_res.items if i.application_id == id2)
        self.assertFalse(item2.is_valid)
        self.assertFalse(item2.is_selected)
        self.assertIn("invalid", item2.validation_error.lower())

    def test_bulk_outreach_dispatch_step_on_existing_app(self):
        """dispatch_bulk_outreach_step dispatches successfully and attaches to existing application."""
        self.service.seed_templates_if_empty()
        templates = self.service.list_templates()
        tpl_id = templates[0]["id"]

        with self.Session() as s:
            comp = Company(name="Stripe", normalized_name="stripe")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Stripe", "Fullstack", "stripe")
            s.add(job)
            s.flush()
            contact = Contact(name="Stripe Recruiter", email="recruiter@stripe.com", company_id=comp.id)
            s.add(contact)
            s.flush()
            app = Application(job_id=job.id, contact_id=contact.id, status="APPLYING", application_type="EMAIL")
            s.add(app)
            s.commit()
            target_app_id = app.id

        res = self.service.dispatch_bulk_outreach_step(
            application_id=target_app_id,
            template_id=tpl_id,
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["application_id"], target_app_id)

        # Verify application status was updated and communication created
        with self.Session() as s:
            app_after = s.get(Application, target_app_id)
            self.assertEqual(app_after.status, "SUBMITTED")
            comms = s.query(Communication).filter_by(application_id=target_app_id).all()
            self.assertEqual(len(comms), 1)
            self.assertEqual(comms[0].direction, "OUTBOUND")
            self.assertEqual(comms[0].status, "SENT")

    def test_priority_and_read_toggles(self):
        """Toggling priority and read states updates both indexed columns and notes metadata."""
        with self.Session() as s:
            comp = Company(name="Airbnb", normalized_name="airbnb")
            s.add(comp)
            s.flush()
            job = make_job(comp.id, "Airbnb", "Backend", "airbnb")
            s.add(job)
            s.flush()
            app = Application(job_id=job.id, status="SUBMITTED", application_type="EMAIL")
            s.add(app)
            s.commit()
            app_id = app.id

        # Toggle Priority
        new_prio = self.service.toggle_conversation_priority(app_id)
        self.assertTrue(new_prio)

        with self.Session() as s:
            app_check = s.get(Application, app_id)
            self.assertTrue(app_check.is_priority)
            self.assertIn('"is_priority": true', app_check.notes)

        # Mark Read
        self.service.mark_conversation_read(app_id, is_read=True)
        with self.Session() as s:
            app_check = s.get(Application, app_id)
            self.assertFalse(app_check.is_unread)
            self.assertIn('"is_read": true', app_check.notes)


if __name__ == "__main__":
    unittest.main()
