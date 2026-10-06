"""Unit and UI contract tests for Outreach Redesign: OutreachComposerDialog & Workspace.

Tests:
  - OutreachComposerDialog layout, initialization, and validation
  - Job selection auto-population of company and position
  - Template selection token interpolation
  - Cadence radio button options mapping to day lists
  - Dispatch worker execution with OutreachCreateDTO
  - OutreachWorkspace 3-zone layout and subcomponents assembly
"""

import os
from pathlib import Path
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Company, Job, Resume, User
from app.repositories.dto import JobCreateDTO
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_viewmodels import (
    NextActionRecommendation,
    OutreachConversationViewModel,
    PresentationConversationState,
)
from app.services.email.mock_provider import MockEmailProvider
from app.services.job_service import JobService
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService
from app.services.resume_service import ResumeService
from app.ui.views.outreach import (
    CommandHeader,
    ContextPanel,
    ConversationInbox,
    InlineReplyComposer,
    OutreachComposerDialog,
    OutreachWorkspace,
    ThreadView,
)
from app.ui.views.outreach.conversation_inbox import ConversationCard
from app.ui.views.outreach.job_picker_modal import JobPickerModal


class TestOutreachComposerUI(unittest.TestCase):
    """Headless UI and functional tests for the modern New Outreach composer."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(self.temp_dir, "composer_ui_test.db")
        attach_dir = Path(self.temp_dir) / "attachments"
        attach_dir.mkdir(parents=True, exist_ok=True)

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.Session() as s:
            u = User(id=1, name="Ahmad Raza", email="ahmad@test.com", is_active=True)
            s.add(u)
            c = Company(id=1, name="Stripe", normalized_name="stripe")
            s.add(c)
            j = Job(
                id=1,
                company_id=1,
                company_raw="Stripe",
                title="Staff Automation Engineer",
                platform="linkedin",
                source_url="https://linkedin.com/jobs/view/999",
                job_fingerprint="fp_stripe_staff_auto",
                is_active=True,
            )
            s.add(j)
            r = Resume(
                id=1,
                user_id=1,
                name="Automation Resume",
                role_target="Automation Engineer",
                version="2.0",
                file_path="/fake/resume.pdf",
                file_hash="fakehashsha256resume",
                is_default=True,
            )
            s.add(r)
            s.commit()

        self.mock_provider = MockEmailProvider(account_email="ahmad@test.com")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=attach_dir,
            default_provider=self.mock_provider,
        )
        self.outreach_service = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
        )
        self.resume_service = ResumeService(session_factory=self.Session)
        self.job_service = JobService(session_factory=self.Session)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_composer_dialog_initialization(self):
        """Dialog loads with pre-populated resumes and jobs."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        # Should have loaded the job and resume into combo boxes
        self.assertGreaterEqual(dialog.cmb_jobs.count(), 2)  # placeholder + 1 job
        self.assertGreaterEqual(dialog.cmb_resume.count(), 2)  # placeholder + 1 resume

        # Default resume is auto-selected
        self.assertEqual(dialog.cmb_resume.currentData(), 1)
        dialog.close()

    def test_job_selection_populates_fields(self):
        """Selecting a saved job auto-fills Company, Title, and Job URL."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        # Select the first real job (index 1)
        dialog.cmb_jobs.setCurrentIndex(1)
        QApplication.processEvents()

        self.assertEqual(dialog.txt_company.text(), "Stripe")
        self.assertEqual(dialog.txt_job_title.text(), "Staff Automation Engineer")
        self.assertEqual(dialog.txt_job_url.text(), "https://linkedin.com/jobs/view/999")
        self.assertIn("Staff Automation Engineer at Stripe", dialog.txt_subject.text())
        dialog.close()

    def test_template_selection_interpolates_variables(self):
        """Template selection replaces placeholder tokens with form values."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        dialog.txt_company.setText("Databricks")
        dialog.txt_job_title.setText("Solutions Architect")
        dialog.txt_contact_name.setText("Elena Rostova")

        # Mock templates cache with token placeholders
        dialog._templates_cache = [
            {
                "id": 42,
                "name": "Recruiter Intro",
                "category": "Initial",
                "subject_template": "Application — {{job_title}} at {{company_name}}",
                "body_template": "Hi {{recruiter_name}},\nI am writing regarding the {{job_title}} role at {{company_name}}.",
            }
        ]
        dialog.cmb_template.addItem("Test Template", 42)
        dialog.cmb_template.setCurrentIndex(dialog.cmb_template.count() - 1)
        QApplication.processEvents()

        self.assertEqual(dialog.txt_subject.text(), "Application — Solutions Architect at Databricks")
        self.assertIn("Hi Elena Rostova", dialog.txt_body.toPlainText())
        self.assertIn("Solutions Architect role at Databricks", dialog.txt_body.toPlainText())
        dialog.close()

    def test_validation_prevents_empty_dispatch(self):
        """Validation fails if required fields are missing."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        # All empty
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_company.setText("Acme")
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_job_title.setText("Dev")
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_contact_email.setText("invalid-email")
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_contact_email.setText("recruiter@acme.com")
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_subject.setText("Application")
        self.assertFalse(dialog._validate_inputs())

        dialog.txt_body.setPlainText("Hello, please consider my application.")
        self.assertTrue(dialog._validate_inputs())
        dialog.close()

    def test_cadence_options(self):
        """Cadence radio options correctly map to delivery day offsets."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )

        with patch.object(dialog, "_validate_inputs", return_value=True):
            with patch("app.ui.views.outreach.composer_dialog._OutreachSendWorker") as MockWorker:
                worker_inst = MagicMock()
                MockWorker.return_value = worker_inst

                dialog.rb_cadence_std.setChecked(True)
                dialog._on_send_outreach()
                dto1: OutreachCreateDTO = MockWorker.call_args[0][1]
                self.assertEqual(dto1.followup_cadence_days, [4, 10, 17])

                dialog.rb_cadence_fast.setChecked(True)
                dialog._on_send_outreach()
                dto2: OutreachCreateDTO = MockWorker.call_args[0][1]
                self.assertEqual(dto2.followup_cadence_days, [3, 7])

                dialog.rb_cadence_none.setChecked(True)
                dialog._on_send_outreach()
                dto3: OutreachCreateDTO = MockWorker.call_args[0][1]
                self.assertEqual(dto3.followup_cadence_days, [])
        dialog.close()


    def test_composer_ai_prompt_and_refine(self):
        """Composer supports custom AI prompt instructions and body text refinement."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        self.assertTrue(hasattr(dialog, "txt_ai_instructions"))
        self.assertTrue(hasattr(dialog, "btn_refine_body"))

        dialog.txt_company.setText("Acme")
        dialog.txt_job_title.setText("Engineer")
        dialog.txt_ai_instructions.setText("Emphasize Python and immediate availability")

        with patch("app.ui.views.outreach.composer_dialog._AIPitchWorker") as MockAIWorker:
            mock_inst = MagicMock()
            MockAIWorker.return_value = mock_inst
            dialog._on_generate_ai_pitch()
            self.assertEqual(MockAIWorker.call_args[1]["custom_instructions"], "Emphasize Python and immediate availability")

        dialog.txt_body.setPlainText("Hello, I am interested in Acme.")
        with patch("app.ui.views.outreach.composer_dialog._AIRefineWorker") as MockRefineWorker:
            mock_refine_inst = MagicMock()
            MockRefineWorker.return_value = mock_refine_inst
            dialog._on_refine_body()
            self.assertEqual(MockRefineWorker.call_args[1]["current_body"], "Hello, I am interested in Acme.")
            self.assertEqual(MockRefineWorker.call_args[1]["instructions"], "Emphasize Python and immediate availability")

        dialog.close()

    def test_composer_styles_no_yellow_border(self):
        """Dialog stylesheet uses 6-digit hex and does not contain 8-digit alpha hex #ffffff0d."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        style = dialog.styleSheet()
        self.assertNotIn("#ffffff0d", style, "8-digit hex causes Qt QSS to render neon yellow border")
        self.assertIn("#262C36", style)
        self.assertIn("#161B22", style)
        dialog.close()

    def test_job_picker_modal_pagination_and_search(self):
        """JobPickerModal paginates 10 jobs per page and allows search and new job creation."""
        # Seed 25 additional jobs
        for i in range(1, 26):
            dto = JobCreateDTO(
                platform="email",
                company_raw=f"Company {i}",
                title=f"Backend Engineer {i}",
                source_url=f"https://linkedin.com/jobs/view/{1000 + i}",
                application_method="EMAIL",
            )
            self.job_service.upsert_job(dto)

        modal = JobPickerModal(job_service=self.job_service)
        modal.show()
        QApplication.processEvents()

        # Total jobs should be 26 (1 from setUp + 25 newly added)
        # Page 1 should show exactly 10 jobs
        self.assertEqual(modal.table.rowCount(), 10)
        self.assertIn("Page 1 of 3", modal.lbl_page_info.text())
        self.assertTrue(modal.btn_prev.isEnabled() is False)
        self.assertTrue(modal.btn_next.isEnabled() is True)

        # Navigate to Page 2
        modal._on_next_page()
        QApplication.processEvents()
        self.assertEqual(modal.table.rowCount(), 10)
        self.assertIn("Page 2 of 3", modal.lbl_page_info.text())
        self.assertTrue(modal.btn_prev.isEnabled() is True)

        # Search test
        modal.txt_search.setText("Engineer 12")
        modal._do_search()
        QApplication.processEvents()
        self.assertEqual(modal.table.rowCount(), 1)
        self.assertIn("Page 1 of 1", modal.lbl_page_info.text())

        # Test creating a new job from modal
        modal.txt_new_company.setText("Anthropic")
        modal.txt_new_title.setText("AI Researcher")
        modal.txt_new_url.setText("https://anthropic.com/careers/1")

        emitted_job = []
        modal.job_selected.connect(lambda job: emitted_job.append(job))
        modal._on_save_new_job()
        QApplication.processEvents()

        self.assertEqual(len(emitted_job), 1)
        self.assertEqual(emitted_job[0]["company_name"], "Anthropic")
        self.assertEqual(emitted_job[0]["title"], "AI Researcher")
        modal.close()

    def test_composer_dialog_fixed_horizontal_dimensions(self):
        """Dialog is strictly clamped to 780px and scroll content to 740px to prevent X scrolling."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        self.assertEqual(dialog.width(), 780)
        self.assertEqual(dialog.maximumWidth(), 780)
        self.assertEqual(dialog.scroll_content.maximumWidth(), 740)
        dialog.close()

    def test_composer_dialog_auto_creates_manual_job_if_unlinked(self):
        """If user enters custom company and position without picking an existing job, a Job is saved in JobRepository."""
        dialog = OutreachComposerDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            job_service=self.job_service,
        )
        dialog.txt_company.setText("OpenAI")
        dialog.txt_job_title.setText("Prompt Architect")
        dialog.txt_contact_name.setText("Sam Altman")
        dialog.txt_contact_email.setText("sam@openai.com")
        dialog.txt_subject.setText("Application: Prompt Architect")
        dialog.txt_body.setPlainText("Hello Sam, I am a great fit.")

        with patch.object(self.outreach_service, "send_outreach") as mock_send:
            mock_send.return_value = {"success": True, "application_id": 42}
            dialog._on_send_outreach()

            # Verify that JobService created the job
            saved_jobs = self.job_service.list_jobs()
            openai_job = next((j for j in saved_jobs if j.company_raw == "OpenAI"), None)
            self.assertIsNotNone(openai_job)
            self.assertEqual(openai_job.title, "Prompt Architect")
            self.assertEqual(openai_job.application_method, "EMAIL")

        dialog.close()


class TestOutreachWorkspaceLayout(unittest.TestCase):
    """Tests the 3-zone layout and integration of OutreachWorkspace."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def test_workspace_component_assembly(self):
        """Workspace properly instantiates and connects all 5 core zones."""
        ws = OutreachWorkspace()
        self.assertIsInstance(ws._header, CommandHeader)
        self.assertIsInstance(ws._inbox, ConversationInbox)
        self.assertIsInstance(ws._thread_view, ThreadView)
        self.assertIsInstance(ws._composer, InlineReplyComposer)
        self.assertIsInstance(ws._context, ContextPanel)

        # Check splitter has 3 zones: Inbox (left), Center (thread+composer), Context (right)
        self.assertEqual(ws._splitter.count(), 3)

        # Verify refresh lifecycle hook
        self.assertTrue(hasattr(ws, "refresh"))
        ws.refresh()

        ws.close()

    def test_command_header_kpi_card_styling(self):
        """CommandHeader metric cards have height 36px, min-width 115px, and top accent border."""
        header = CommandHeader()
        for pill in header._pills.values():
            self.assertEqual(pill.height(), 36)
            self.assertEqual(pill.minimumWidth(), 115)
            self.assertIn("border-top: 3px solid", pill.styleSheet())
        header.close()

    def test_inline_reply_composer_rag_prompt(self):
        """Composer has RAG prompt input and can set generated reply text."""
        composer = InlineReplyComposer()
        composer.show()
        self.assertTrue(hasattr(composer, "_ai_prompt_bar"))
        self.assertTrue(composer._ai_prompt_bar.isHidden())

        # Clicking AI Copilot toggles prompt bar
        composer._app_id = 99
        composer._toggle_ai_copilot_prompt()
        self.assertFalse(composer._ai_prompt_bar.isHidden())

        # Setting reply text populates editor and closes prompt bar
        composer.set_reply_text("Dear Recruiter, I have 2 years of experience.")
        self.assertIn("2 years of experience", composer._editor.toPlainText())
        self.assertTrue(composer._ai_prompt_bar.isHidden())
        composer.close()

    def test_inline_reply_composer_minimize_and_template_menu(self):
        """Composer can be minimized/expanded and interpolates chosen templates."""
        composer = InlineReplyComposer()
        composer.show()
        self.assertFalse(composer._is_minimized)
        self.assertTrue(composer._compact_bar.isHidden())

        # Minimize
        composer._toggle_minimize()
        self.assertTrue(composer._is_minimized)
        self.assertTrue(composer._editor.isHidden())
        self.assertFalse(composer._compact_bar.isHidden())

        # Expand again
        composer._toggle_minimize()
        self.assertFalse(composer._is_minimized)
        self.assertFalse(composer._editor.isHidden())
        self.assertTrue(composer._compact_bar.isHidden())

        # Template interpolation
        composer.load_for_conversation(app_id=5, recipient_name="Jordan Bell")
        composer._apply_template_text("Hi {{recruiter_name}},\nFollowing up on my previous email.")
        self.assertIn("Hi Jordan Bell,", composer._editor.toPlainText())
        self.assertIn("Following up on my previous email.", composer._editor.toPlainText())
        composer.close()

    def test_conversation_card_priority_and_read(self):
        """ConversationCard displays unread dot, priority star, and emits priority_toggled."""
        action = NextActionRecommendation(
            action_type="WAIT",
            headline="Awaiting reply",
            rationale="No immediate action required",
            cta_label="View Thread",
        )
        vm = OutreachConversationViewModel(
            application_id=10,
            company_name="Figma",
            job_title="Product Designer",
            recruiter_name="Sarah",
            recruiter_email="sarah@figma.com",
            recruitment_status="APPLIED",
            state=PresentationConversationState.WAITING,
            next_action=action,
            is_priority=True,
            unread_count=2,
            last_activity_at=datetime.now(timezone.utc),
            last_snippet="Let us know your availability.",
        )
        card = ConversationCard(vm=vm, is_selected=False)
        self.assertEqual(card._star_btn.text(), "★")
        self.assertGreater(card._vm.unread_count, 0)
        self.assertIsNotNone(card._unread_dot)

        emitted = []
        card.priority_toggled.connect(lambda app_id: emitted.append(app_id))
        card._on_star_clicked()
        self.assertEqual(emitted, [10])
        card.close()

    def test_conversation_inbox_filter_pills(self):
        """Inbox quick filter pills (All, Unread, Starred) filter cards accordingly."""
        inbox = ConversationInbox()
        now = datetime.now(timezone.utc)
        action = NextActionRecommendation(
            action_type="WAIT",
            headline="Awaiting reply",
            rationale="No immediate action required",
            cta_label="View Thread",
        )
        vm1 = OutreachConversationViewModel(
            application_id=1,
            company_name="Google",
            job_title="SWE",
            recruiter_name="Recruiter 1",
            recruiter_email="r1@google.com",
            recruitment_status="APPLIED",
            state=PresentationConversationState.WAITING,
            next_action=action,
            is_priority=False,
            unread_count=0,
            last_activity_at=now,
            last_snippet="Snippet 1",
        )
        vm2 = OutreachConversationViewModel(
            application_id=2,
            company_name="Meta",
            job_title="SWE",
            recruiter_name="Recruiter 2",
            recruiter_email="r2@meta.com",
            recruitment_status="APPLIED",
            state=PresentationConversationState.WAITING,
            next_action=action,
            is_priority=True,
            unread_count=0,
            last_activity_at=now,
            last_snippet="Snippet 2",
        )
        vm3 = OutreachConversationViewModel(
            application_id=3,
            company_name="Apple",
            job_title="SWE",
            recruiter_name="Recruiter 3",
            recruiter_email="r3@apple.com",
            recruitment_status="APPLIED",
            state=PresentationConversationState.WAITING,
            next_action=action,
            is_priority=False,
            unread_count=1,
            last_activity_at=now,
            last_snippet="Snippet 3",
        )
        inbox.set_conversations([vm1, vm2, vm3])

        # Default ALL: 3 cards
        cards_count = sum(1 for i in range(inbox._cards_layout.count()) if isinstance(inbox._cards_layout.itemAt(i).widget(), ConversationCard))
        self.assertEqual(cards_count, 3)

        # UNREAD filter: 1 card
        inbox._set_filter_tag("UNREAD")
        cards_count = sum(1 for i in range(inbox._cards_layout.count()) if isinstance(inbox._cards_layout.itemAt(i).widget(), ConversationCard))
        self.assertEqual(cards_count, 1)

        # STARRED filter: 1 card
        inbox._set_filter_tag("STARRED")
        cards_count = sum(1 for i in range(inbox._cards_layout.count()) if isinstance(inbox._cards_layout.itemAt(i).widget(), ConversationCard))
        self.assertEqual(cards_count, 1)

        # Back to ALL: 3 cards
        inbox._set_filter_tag("ALL")
        cards_count = sum(1 for i in range(inbox._cards_layout.count()) if isinstance(inbox._cards_layout.itemAt(i).widget(), ConversationCard))
        self.assertEqual(cards_count, 3)
        inbox.close()

    def test_workspace_cta_wait_action(self):
        """WAIT action scrolls to bottom of thread and focuses composer."""
        ws = OutreachWorkspace()
        with patch.object(ws._thread_view, "scroll_to_bottom") as mock_scroll:
            with patch.object(ws._composer, "focus_editor") as mock_focus:
                ws._on_cta_clicked("WAIT")
                mock_scroll.assert_called_once()
                mock_focus.assert_called_once()
        ws.close()
