import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

from app.services.dto.outreach_viewmodels import BulkTargetPreviewItemDTO
from app.services.dto.outreach_enums import ConversationOpState, NextActionType
from app.ui.views.bulk_outreach_dialog import BulkOutreachDialog, AddCustomTargetDialog

app = QApplication.instance() or QApplication([])

class TestBulkOutreachDialogEnhancements(unittest.TestCase):

    def setUp(self):
        self.mock_outreach = MagicMock()
        self.mock_resume = MagicMock()
        self.mock_resume.list_resumes.return_value = []

        self.sample_targets = [
            BulkTargetPreviewItemDTO(
                application_id=101,
                company_name="Google",
                job_title="Software Engineer",
                recruiter_name="Larry",
                recruiter_email="larry@google.com",
                resume_id=1,
                resume_name="Resume A",
                is_valid=True,
                validation_error=None,
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.NEEDS_ACTION,
                next_action_type=NextActionType.NONE,
                is_selected=True,
            ),
            BulkTargetPreviewItemDTO(
                application_id=102,
                company_name="Meta",
                job_title="RPA Developer",
                recruiter_name="Mark",
                recruiter_email="mark@meta.com",
                resume_id=1,
                resume_name="Resume A",
                is_valid=True,
                validation_error=None,
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.NEEDS_ACTION,
                next_action_type=NextActionType.NONE,
                is_selected=True,
            ),
            BulkTargetPreviewItemDTO(
                application_id=103,
                company_name="InvalidCorp",
                job_title="Intern",
                recruiter_name="Bob",
                recruiter_email="invalid-email",
                resume_id=None,
                resume_name="",
                is_valid=False,
                validation_error="Invalid email format",
                is_duplicate=False,
                duplicate_tier=None,
                current_state=ConversationOpState.CLOSED,
                next_action_type=NextActionType.NONE,
                is_selected=True,
            ),
        ]

    def test_search_and_filter(self):
        dlg = BulkOutreachDialog(
            outreach_service=self.mock_outreach,
            resume_service=self.mock_resume,
            initial_targets=self.sample_targets,
        )
        self.assertEqual(dlg.table_targets.rowCount(), 3)

        # Filter by "google" -> only Google row visible
        dlg._apply_table_filters("google")
        self.assertFalse(dlg.table_targets.isRowHidden(0))
        self.assertTrue(dlg.table_targets.isRowHidden(1))
        self.assertTrue(dlg.table_targets.isRowHidden(2))

        # Clear filter -> all rows visible
        dlg._apply_table_filters("")
        self.assertFalse(dlg.table_targets.isRowHidden(0))
        self.assertFalse(dlg.table_targets.isRowHidden(1))
        self.assertFalse(dlg.table_targets.isRowHidden(2))

    def test_checkbox_selection(self):
        dlg = BulkOutreachDialog(
            outreach_service=self.mock_outreach,
            resume_service=self.mock_resume,
            initial_targets=self.sample_targets,
        )
        # Deselect all
        dlg._deselect_all_targets()
        for t in dlg._targets:
            self.assertFalse(t.is_selected)

        # Select all
        dlg._select_all_targets()
        for t in dlg._targets:
            self.assertTrue(t.is_selected)

    def test_throttling_intervals(self):
        dlg = BulkOutreachDialog(
            outreach_service=self.mock_outreach,
            resume_service=self.mock_resume,
            initial_targets=self.sample_targets,
        )
        values = [dlg.cmb_interval.itemData(i) for i in range(dlg.cmb_interval.count())]
        self.assertIn(60.0, values)
        self.assertIn(30.0, values)
        self.assertIn(90.0, values)
        self.assertIn(120.0, values)

    def test_editable_preview(self):
        dlg = BulkOutreachDialog(
            outreach_service=self.mock_outreach,
            resume_service=self.mock_resume,
            initial_targets=self.sample_targets,
        )
        self.assertFalse(dlg.txt_preview_subject.isReadOnly())
        self.assertFalse(dlg.txt_preview_body.isReadOnly())

        dlg.txt_preview_subject.setText("Custom Subject Here")
        dlg.txt_preview_body.setPlainText("Custom Body Text")
        self.assertEqual(dlg.txt_preview_subject.text(), "Custom Subject Here")
        self.assertEqual(dlg.txt_preview_body.toPlainText(), "Custom Body Text")

    def test_add_custom_target_modal(self):
        modal = AddCustomTargetDialog()
        modal.txt_company.setText("Amazon")
        modal.txt_title.setText("Cloud Engineer")
        modal.txt_recruiter.setText("Jeff")
        modal.txt_email.setText("jeff@amazon.com")

        target = modal.get_target_dto()
        self.assertIsNone(target.application_id)
        self.assertEqual(target.company_name, "Amazon")
        self.assertEqual(target.job_title, "Cloud Engineer")
        self.assertEqual(target.recruiter_name, "Jeff")
        self.assertEqual(target.recruiter_email, "jeff@amazon.com")
        self.assertTrue(target.is_valid)
        self.assertTrue(target.is_selected)

if __name__ == "__main__":
    unittest.main()
