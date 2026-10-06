"""
Tests for Setup Wizard UI glitch fixes, Q&A fact synchronization, editing, and tour launch.
"""

import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
import sys

from app.ui.widgets.onboarding_steps.step_preferences import StepPreferencesWidget
from app.ui.widgets.onboarding_steps.step_readiness_summary import StepReadinessSummaryWidget
from app.ui.widgets.onboarding_steps.step_qna_knowledge import StepQnAKnowledgeWidget, QnAEditDialog
from app.services.setup.setup_service import SetupService

app = QApplication.instance() or QApplication(sys.argv + ["-platform", "offscreen"])


class TestSetupUIEnhancements(unittest.TestCase):
    def test_preferences_prefill_from_ai_extraction(self):
        widget = StepPreferencesWidget()
        extracted = {
            "current_title": {"value": "AI Automation Architect"},
            "current_city": {"value": "Bengaluru"},
        }
        # When user has no existing preferences, suggest from AI extraction
        widget.load_preferences({}, extracted_data=extracted)

        self.assertIn("AI Automation Architect", widget.txt_titles.text())
        self.assertIn("Bengaluru", widget.txt_locations.text())

    def test_readiness_buttons_equal_and_prominent(self):
        widget = StepReadinessSummaryWidget()
        self.assertEqual(widget.btn_tour.text(), "🧭 Take 60-Second Product Tour")
        self.assertEqual(widget.btn_finish.text(), "⚡ Finish and Open JobPilot ►")
        self.assertGreaterEqual(widget.btn_tour.minimumHeight(), 46)
        self.assertGreaterEqual(widget.btn_finish.minimumHeight(), 46)

    def test_qna_edit_dialog_saves_answer(self):
        mock_qna_service = MagicMock()
        mock_qna_service.update_entry.return_value = (MagicMock(), None)

        dialog = QnAEditDialog(
            entry_id=42,
            question="What is your notice period?",
            answer="30 days",
            category="notice_period",
            qna_service=mock_qna_service
        )
        dialog.txt_a.setPlainText("15 days")
        dialog._on_save()

        mock_qna_service.update_entry.assert_called_once_with(
            entry_id=42,
            question="What is your notice period?",
            answer="15 days",
            category="notice_period",
            validation_status="VERIFIED"
        )

    def test_sync_profile_facts_to_qna_bank(self):
        service = SetupService()
        profile_data = {
            "professional": {
                "years_of_experience": 5,
                "notice_period_days": 15,
                "current_title": "Lead Automation Engineer",
            }
        }
        # Test synchronization logic against real database
        updated = service.sync_profile_facts_to_qna_bank(profile_data)
        self.assertGreater(updated, 0)


if __name__ == "__main__":
    unittest.main()
