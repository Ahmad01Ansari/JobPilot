"""Unit tests for Outreach Redesign Phase 1: ViewModels and Draft Persistence.

Tests the new presentation-layer ViewModels, Next Action computation,
draft save/get/delete lifecycle, and server-side paginated listing.
"""

import os
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Application, Communication, Company, Contact, FollowUp, Job, Resume, User,
)
from app.services.dto.outreach_enums import FollowUpStatus, MessageStatus
from app.services.dto.outreach_viewmodels import (
    ConversationDetailViewModel,
    NextActionRecommendation,
    OutreachConversationViewModel,
    PresentationConversationState,
)
from app.services.email.mock_provider import MockEmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService


class TestViewModelsAndDrafts(unittest.TestCase):
    """Phase 1 Outreach Redesign: presentation models, draft persistence, ViewModel factories."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(self.temp_dir, "vm_test.db")
        attach_dir = Path(self.temp_dir) / "attachments"
        attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        # Seed user
        with self.Session() as s:
            u = User(id=1, name="Ahmad Raza", email="ahmad@test.com", is_active=True)
            s.add(u)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="ahmad@test.com")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=attach_dir,
            default_provider=self.mock_provider,
        )
        self.service = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
            email_provider=self.mock_provider,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_application(self, company_name="Acme Corp", job_title="Dev", status="APPLIED"):
        """Helper: seeds a complete Application + Job + Company + Contact chain."""
        import uuid
        with self.Session() as s:
            co = Company(name=company_name, normalized_name=company_name.lower().strip())
            s.add(co)
            s.flush()
            job = Job(
                title=job_title,
                company_id=co.id,
                company_raw=company_name,
                platform="EMAIL",
                job_fingerprint=uuid.uuid4().hex,
                source_url="https://example.com/job",
            )
            s.add(job)
            s.flush()
            contact = Contact(name="Sarah R", email="sarah@acme.com", designation="HR Manager")
            s.add(contact)
            s.flush()
            app = Application(
                job_id=job.id,
                contact_id=contact.id,
                status=status,
                application_type="EMAIL",
                applied_at=datetime.now(timezone.utc),
            )
            s.add(app)
            s.commit()
            return app.id

    def _add_communication(self, app_id, direction="OUTBOUND", status="SENT", body="Hello", **kw):
        with self.Session() as s:
            comm = Communication(
                application_id=app_id,
                type="EMAIL",
                direction=direction,
                status=status,
                subject=kw.get("subject", "Test Subject"),
                body_snippet=body[:160],
                summary=body,
                sender_email=kw.get("sender_email", "ahmad@test.com"),
                recipient_email=kw.get("recipient_email", "sarah@acme.com"),
                occurred_at=kw.get("occurred_at", datetime.now(timezone.utc)),
            )
            if "ai_classification" in kw:
                comm.ai_classification = kw["ai_classification"]
            s.add(comm)
            s.commit()
            return comm.id

    # ---------------------------------------------------------------
    # Draft Persistence Tests
    # ---------------------------------------------------------------

    def test_save_draft_creates_new(self):
        app_id = self._create_application()
        draft_id = self.service.save_draft(app_id, "Dear Sarah, I am writing...")
        self.assertIsNotNone(draft_id)
        self.assertIsInstance(draft_id, int)

    def test_save_draft_upserts(self):
        app_id = self._create_application()
        id1 = self.service.save_draft(app_id, "First version")
        id2 = self.service.save_draft(app_id, "Updated version")
        self.assertEqual(id1, id2, "Upsert should reuse the same draft row")

    def test_get_draft_returns_content(self):
        app_id = self._create_application()
        self.service.save_draft(app_id, "Draft body here", subject="Follow-Up")
        draft = self.service.get_draft(app_id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["body_text"], "Draft body here")
        self.assertEqual(draft["subject"], "Follow-Up")

    def test_get_draft_returns_none_when_empty(self):
        app_id = self._create_application()
        self.assertIsNone(self.service.get_draft(app_id))

    def test_delete_draft(self):
        app_id = self._create_application()
        self.service.save_draft(app_id, "Temporary draft")
        self.assertTrue(self.service.delete_draft(app_id))
        self.assertIsNone(self.service.get_draft(app_id))

    def test_delete_draft_returns_false_when_missing(self):
        app_id = self._create_application()
        self.assertFalse(self.service.delete_draft(app_id))

    def test_draft_survives_service_reinstantiation(self):
        """Simulates app restart: draft persists in DB across service instances."""
        app_id = self._create_application()
        self.service.save_draft(app_id, "Persistent draft", subject="Re: Interview")

        # New service instance (simulates restart)
        svc2 = OutreachService(session_factory=self.Session)
        draft = svc2.get_draft(app_id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["body_text"], "Persistent draft")
        self.assertEqual(draft["subject"], "Re: Interview")

    # ---------------------------------------------------------------
    # Next Action Computation Tests
    # ---------------------------------------------------------------

    def test_next_action_waiting(self):
        action = OutreachService._compute_next_action(
            app_status="APPLIED",
            conv_state=PresentationConversationState.WAITING,
            has_inbound=False,
        )
        self.assertEqual(action.action_type, "WAIT")
        self.assertIn("Awaiting", action.headline)

    def test_next_action_needs_action_reply(self):
        action = OutreachService._compute_next_action(
            app_status="RECRUITER_CONTACTED",
            conv_state=PresentationConversationState.NEEDS_ACTION,
            has_inbound=True,
            latest_inbound_classification="INFORMATION_REQUEST",
        )
        self.assertEqual(action.action_type, "REPLY")
        self.assertEqual(action.cta_label, "Draft Reply")

    def test_next_action_interview_request(self):
        action = OutreachService._compute_next_action(
            app_status="RECRUITER_CONTACTED",
            conv_state=PresentationConversationState.NEEDS_ACTION,
            has_inbound=True,
            latest_inbound_classification="INTERVIEW_REQUEST",
        )
        self.assertEqual(action.action_type, "SCHEDULE_INTERVIEW")
        self.assertEqual(action.suggested_status, "INTERVIEWING")

    def test_next_action_completed(self):
        action = OutreachService._compute_next_action(
            app_status="REJECTED",
            conv_state=PresentationConversationState.COMPLETED,
            has_inbound=False,
        )
        self.assertEqual(action.action_type, "WAIT")
        self.assertIn("Completed", action.headline)

    def test_next_action_followup_due(self):
        due = datetime.now(timezone.utc) - timedelta(hours=2)
        action = OutreachService._compute_next_action(
            app_status="APPLIED",
            conv_state=PresentationConversationState.FOLLOW_UP_DUE,
            has_inbound=False,
            next_followup_due=due,
        )
        self.assertEqual(action.action_type, "EXECUTE_FOLLOWUP")

    # ---------------------------------------------------------------
    # list_conversations_vm Tests
    # ---------------------------------------------------------------

    def test_list_conversations_vm_returns_viewmodels(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Hello recruiter")

        results = self.service.list_conversations_vm()
        self.assertEqual(len(results), 1)
        vm = results[0]
        self.assertIsInstance(vm, OutreachConversationViewModel)
        self.assertEqual(vm.application_id, app_id)
        self.assertEqual(vm.company_name, "Acme Corp")
        self.assertEqual(vm.job_title, "Dev")
        self.assertEqual(vm.recruiter_name, "Sarah R")
        self.assertIsInstance(vm.next_action, NextActionRecommendation)

    def test_list_conversations_vm_state_filter(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Hi")

        # Waiting state — no inbound
        waiting = self.service.list_conversations_vm(state_filter="WAITING")
        self.assertEqual(len(waiting), 1)

        # Replied filter should be empty
        replied = self.service.list_conversations_vm(state_filter="REPLIED")
        self.assertEqual(len(replied), 0)

    def test_list_conversations_vm_pagination(self):
        for i in range(5):
            self._create_application(company_name=f"Corp{i}", job_title=f"Dev{i}")

        page1 = self.service.list_conversations_vm(limit=2, offset=0)
        page2 = self.service.list_conversations_vm(limit=2, offset=2)
        self.assertEqual(len(page1), 2)
        self.assertEqual(len(page2), 2)

    def test_list_conversations_vm_search(self):
        self._create_application(company_name="Google", job_title="SRE")
        self._create_application(company_name="Microsoft", job_title="SDE")

        results = self.service.list_conversations_vm(search_query="Google")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].company_name, "Google")

    def test_list_conversations_vm_draft_preview(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Initial outreach")
        self.service.save_draft(app_id, "My draft reply to Sarah")

        results = self.service.list_conversations_vm()
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0].active_draft_preview)

    # ---------------------------------------------------------------
    # get_conversation_detail_vm Tests
    # ---------------------------------------------------------------

    def test_get_conversation_detail_vm_basic(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Hello recruiter, ...")

        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertIsNotNone(vm)
        self.assertIsInstance(vm, ConversationDetailViewModel)
        self.assertEqual(vm.company_name, "Acme Corp")
        self.assertEqual(vm.job_title, "Dev")
        self.assertEqual(len(vm.messages), 1)
        self.assertEqual(vm.messages[0].direction, "OUTBOUND")

    def test_get_conversation_detail_vm_with_inbound(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Initial pitch")
        self._add_communication(
            app_id, direction="INBOUND", body="Thanks! Please share your availability",
            sender_email="sarah@acme.com",
            occurred_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )

        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertEqual(len(vm.messages), 2)
        self.assertEqual(vm.state, PresentationConversationState.REPLIED)

    def test_get_conversation_detail_vm_returns_none_for_invalid(self):
        self.assertIsNone(self.service.get_conversation_detail_vm(99999))

    def test_get_conversation_detail_vm_draft_excluded_from_thread(self):
        app_id = self._create_application()
        self._add_communication(app_id, direction="OUTBOUND", body="Sent message")
        self.service.save_draft(app_id, "Work in progress draft")

        vm = self.service.get_conversation_detail_vm(app_id)
        # Draft should not appear in messages but should be in active_draft fields
        self.assertEqual(len(vm.messages), 1)
        self.assertIsNotNone(vm.active_draft_body)
        self.assertEqual(vm.active_draft_body, "Work in progress draft")

    def test_get_conversation_detail_vm_contact(self):
        app_id = self._create_application()
        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertIsNotNone(vm.contact)
        self.assertEqual(vm.contact.name, "Sarah R")
        self.assertEqual(vm.contact.email, "sarah@acme.com")

    def test_get_conversation_detail_vm_followups(self):
        app_id = self._create_application()
        # Add a follow-up
        with self.Session() as s:
            fu = FollowUp(
                application_id=app_id,
                step_number=1,
                due_at=datetime.now(timezone.utc) + timedelta(days=4),
                status=FollowUpStatus.PENDING.value,
            )
            s.add(fu)
            s.commit()

        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertEqual(len(vm.follow_ups), 1)
        self.assertEqual(vm.follow_ups[0].step_number, 1)
        self.assertEqual(vm.follow_ups[0].status, FollowUpStatus.PENDING.value)

    # ---------------------------------------------------------------
    # Presentation State Resolution Tests
    # ---------------------------------------------------------------

    def test_completed_state(self):
        app_id = self._create_application(status="REJECTED")
        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertEqual(vm.state, PresentationConversationState.COMPLETED)

    def test_paused_state(self):
        app_id = self._create_application()
        with self.Session() as s:
            fu = FollowUp(
                application_id=app_id,
                step_number=1,
                due_at=datetime.now(timezone.utc) + timedelta(days=4),
                status=FollowUpStatus.PAUSED.value,
                paused_reason="Recruiter replied",
            )
            s.add(fu)
            s.commit()

        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertEqual(vm.state, PresentationConversationState.PAUSED)

    def test_followup_due_state(self):
        app_id = self._create_application()
        with self.Session() as s:
            fu = FollowUp(
                application_id=app_id,
                step_number=1,
                due_at=datetime.now(timezone.utc) - timedelta(hours=2),
                status=FollowUpStatus.PENDING.value,
            )
            s.add(fu)
            s.commit()

        vm = self.service.get_conversation_detail_vm(app_id)
        self.assertEqual(vm.state, PresentationConversationState.FOLLOW_UP_DUE)


if __name__ == "__main__":
    unittest.main()
