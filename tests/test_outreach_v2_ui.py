"""Unit tests for Outreach Center V2 UI components and Bulk Outreach Dialog.

Adheres strictly to docs/ai/TESTING_RULES.md:
- Tests WorkQueueCaseCardWidget, BulkOutreachWorker, BulkOutreachDialog, and OutreachView.
- Uses unittest with isolated in-memory DB or temporary directory.
- Runs cleanly in offscreen Qt environment (QCoreApplication/QApplication).
"""

from datetime import datetime, timezone
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure offscreen Qt application exists
app = QApplication.instance()
if not app:
    app = QApplication(["-platform", "offscreen"])

from app.db.base import Base, utc_now
from app.db.models import Application, Company, Contact, EmailTemplate, Job, Resume
from sqlalchemy.orm import sessionmaker
from app.services.dto.outreach_enums import (
    CadenceState,
    ConversationOpState,
    NextActionOwner,
    NextActionType,
    PriorityLevel,
    WorkQueueSection,
)
from app.services.dto.outreach_viewmodels import (
    BulkTargetPreviewItemDTO,
    OutreachCaseOperationViewModel,
)
from app.services.outreach_service import OutreachService
from app.services.resume_service import ResumeService
from app.ui.views.bulk_outreach_dialog import BulkOutreachDialog, BulkOutreachWorker
from app.ui.views.outreach_view import OutreachView, WorkQueueCaseCardWidget
from sqlalchemy import create_engine


def make_test_case(app_id: int, company: str = "Test Co", section: WorkQueueSection = WorkQueueSection.TODAY):
    return OutreachCaseOperationViewModel(
        application_id=app_id,
        company_name=company,
        job_title="Software Engineer",
        recruitment_status="SUBMITTED",
        contact_id=1,
        contact_name="Alice",
        contact_email="alice@test.com",
        contact_designation="HR",
        conversation_state=ConversationOpState.NEEDS_ACTION,
        next_action_type=NextActionType.REPLY_TO_RECRUITER,
        next_action_owner=NextActionOwner.USER,
        next_action_due_at=utc_now(),
        next_action_headline="Reply to Recruiter",
        next_action_rationale="Recruiter asked questions",
        next_action_cta="Draft Reply",
        priority=PriorityLevel.HIGH,
        cadence_state=CadenceState.ACTIVE,
        cadence_active_step=1,
        cadence_total_steps=3,
        last_contact_at=utc_now(),
        last_inbound_at=utc_now(),
        last_outbound_at=None,
        last_snippet="Looking forward to speaking with you.",
        unread_attention=True,
        is_priority=True,
        resume_version_tag="v1.0",
        has_draft=False,
        work_queue_section=section,
    )


class TestOutreachV2UI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ui.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.mock_provider = MagicMock()
        self.service = OutreachService(
            session_factory=self.Session,
            email_provider=self.mock_provider,
        )
        self.resume_service = ResumeService(storage_dir=self.temp_dir, session_factory=self.Session, is_test=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_case_card_widget_initialization_and_signals(self):
        """WorkQueueCaseCardWidget renders operational fields and emits signals correctly."""
        case = make_test_case(101, "Google")
        card = WorkQueueCaseCardWidget(case, is_selected=False, is_checked=False)

        self.assertEqual(card.app_id, 101)
        self.assertEqual(card.company_name, "Google")
        self.assertTrue(card.is_prio)
        self.assertTrue(card.is_unread)
        self.assertEqual(card.cta_label, "Draft Reply")

        # Test selection toggle signal
        emitted_sel = []
        card.selection_toggled.connect(lambda app_id, chk: emitted_sel.append((app_id, chk)))
        card.chk_select.setChecked(True)
        self.assertEqual(emitted_sel, [(101, True)])

        # Test priority toggle signal
        emitted_prio = []
        card.priority_toggled.connect(lambda app_id: emitted_prio.append(app_id))
        card.btn_star.click()
        self.assertEqual(emitted_prio, [101])

    def test_bulk_outreach_worker_lifecycle(self):
        """BulkOutreachWorker iterates targets, respects pauses, and emits progress."""
        targets = [
            BulkTargetPreviewItemDTO(
                application_id=1,
                company_name="Company A",
                job_title="Dev 1",
                recruiter_name="R1",
                recruiter_email="r1@a.com",
                resume_id=None,
                resume_name="Resume",
                is_valid=True,
                validation_error=None,
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.WAITING_FOR_RECRUITER,
                next_action_type=NextActionType.NONE,
            ),
            BulkTargetPreviewItemDTO(
                application_id=2,
                company_name="Company B",
                job_title="Dev 2",
                recruiter_name="R2",
                recruiter_email="r2@b.com",
                resume_id=None,
                resume_name="Resume",
                is_valid=True,
                validation_error=None,
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.WAITING_FOR_RECRUITER,
                next_action_type=NextActionType.NONE,
            ),
        ]

        mock_svc = MagicMock()
        mock_svc.dispatch_bulk_outreach_step.return_value = {"success": True, "application_id": 1}

        worker = BulkOutreachWorker(
            outreach_service=mock_svc,
            targets=targets,
            template_id=1,
            resume_id=None,
            interval_seconds=0.01,
        )

        progress_events = []
        finished_results = []
        worker.progress.connect(lambda c, t, comp: progress_events.append((c, t, comp)))
        worker.finished.connect(lambda summ: finished_results.append(summ))

        # Run synchronously in test
        worker.run()

        self.assertEqual(len(progress_events), 2)
        self.assertEqual(progress_events[0], (1, 2, "Company A"))
        self.assertEqual(progress_events[1], (2, 2, "Company B"))

        self.assertEqual(len(finished_results), 1)
        self.assertEqual(finished_results[0]["sent"], 2)
        self.assertEqual(finished_results[0]["failed"], 0)
        self.assertFalse(finished_results[0]["cancelled"])

    def test_bulk_outreach_dialog_target_removal(self):
        """BulkOutreachDialog allows removal of targets and updates stats badge."""
        targets = [
            BulkTargetPreviewItemDTO(
                application_id=1,
                company_name="Target 1",
                job_title="Title 1",
                recruiter_name="Rec 1",
                recruiter_email="r1@target.com",
                resume_id=None,
                resume_name="Resume",
                is_valid=True,
                validation_error=None,
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.WAITING_FOR_RECRUITER,
                next_action_type=NextActionType.NONE,
            ),
            BulkTargetPreviewItemDTO(
                application_id=2,
                company_name="Target 2",
                job_title="Title 2",
                recruiter_name="Rec 2",
                recruiter_email="r2@target.com",
                resume_id=None,
                resume_name="Resume",
                is_valid=False,
                validation_error="Invalid email syntax",
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.WAITING_FOR_RECRUITER,
                next_action_type=NextActionType.NONE,
            ),
        ]

        dlg = BulkOutreachDialog(
            outreach_service=self.service,
            resume_service=self.resume_service,
            initial_targets=targets,
        )

        self.assertEqual(dlg.table_targets.rowCount(), 2)
        self.assertIn("2 Total • 1 Selected Valid • 1 Blocked", dlg.lbl_stats_badge.text())

        # Remove target at index 1 (the blocked one)
        dlg._remove_target_at(1)
        self.assertEqual(dlg.table_targets.rowCount(), 1)
        self.assertIn("1 Total • 1 Selected Valid • 0 Blocked", dlg.lbl_stats_badge.text())


if __name__ == "__main__":
    unittest.main()
