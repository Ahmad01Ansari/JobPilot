"""Unit and UI Component Test Suite for Phase 13: Universal UI Dialogs and Timeline.

Tests:
1. UniversalReviewDialog (Table population, callbacks, signals, confirm/takeover/cancel).
2. UniversalInterventionDialog (CAPTCHA/Login/Unknown field variations, inputs, signals).
3. UniversalTimelineWidget (Step state progression, badges, reset, theme).
4. AutomationView Universal UI integration (event routing and dialog lifecycle).
"""

import os
import unittest
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationState,
    InterventionType,
)
from app.ui.views.automation.universal_intervention_dialog import UniversalInterventionDialog
from app.ui.views.automation.universal_review_dialog import UniversalReviewDialog
from app.ui.widgets.automation.universal_timeline_widget import UniversalTimelineWidget
from app.ui.views.automation_view import AutomationView

app = QApplication.instance() or QApplication([])


class TestUniversalReviewDialog(unittest.TestCase):
    """Tests for the V1 Human Review Gate Pre-Submission Dialog."""

    def setUp(self):
        self.sample_fields = {
            "Full Name": {"value": "Jane Doe", "provenance": "PROFILE_FACT", "is_required": True},
            "Email": {"value": "jane@example.com", "provenance": "PROFILE_FACT", "is_required": True},
            "Years of Python": {"value": "5", "provenance": "LLM_SYNTHESIS", "is_required": False},
        }

    def test_review_dialog_initialization_and_table(self):
        dialog = UniversalReviewDialog(
            job_title="Senior AI Engineer",
            company="Anthropic",
            target_url="https://jobs.lever.co/anthropic/123",
            resume_name="Jane_Doe_Resume_2026.pdf",
            field_details=self.sample_fields,
        )

        self.assertIn("Senior AI Engineer", dialog.windowTitle())
        self.assertIn("Anthropic", dialog.windowTitle())
        self.assertEqual(dialog.table.rowCount(), 3)
        self.assertEqual(dialog.table.columnCount(), 3)

        # Check row 0 contents
        item_0_label = dialog.table.item(0, 0)
        self.assertIsNotNone(item_0_label)
        self.assertIn("Full Name *", item_0_label.text())

        item_0_val = dialog.table.item(0, 1)
        self.assertEqual(item_0_val.text(), "Jane Doe")

        item_0_prov = dialog.table.item(0, 2)
        self.assertEqual(item_0_prov.text(), "PROFILE_FACT")

        # Row 2 (optional, LLM)
        item_2_label = dialog.table.item(2, 0)
        self.assertEqual(item_2_label.text(), "Years of Python")
        item_2_prov = dialog.table.item(2, 2)
        self.assertEqual(item_2_prov.text(), "LLM_SYNTHESIS")

    def test_review_dialog_confirm(self):
        confirmed_cb = MagicMock()
        signal_data = []

        dialog = UniversalReviewDialog(
            field_details=self.sample_fields,
            on_confirmed=confirmed_cb,
        )
        dialog.confirmed.connect(lambda notes: signal_data.append(notes))

        dialog.notes_input.setText("Approved for submission")
        QTest.mouseClick(dialog.btn_confirm, Qt.LeftButton)

        confirmed_cb.assert_called_once_with("Approved for submission")
        self.assertEqual(signal_data, ["Approved for submission"])
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_review_dialog_takeover(self):
        takeover_cb = MagicMock()
        signal_data = []

        dialog = UniversalReviewDialog(
            field_details=self.sample_fields,
            on_takeover=takeover_cb,
        )
        dialog.takeover_requested.connect(lambda notes: signal_data.append(notes))

        dialog.notes_input.setText("Need to edit custom question")
        QTest.mouseClick(dialog.btn_takeover, Qt.LeftButton)

        takeover_cb.assert_called_once_with("Need to edit custom question")
        self.assertEqual(signal_data, ["Need to edit custom question"])
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_review_dialog_cancel(self):
        rejected_cb = MagicMock()
        signal_data = []

        dialog = UniversalReviewDialog(
            field_details=self.sample_fields,
            on_rejected=rejected_cb,
        )
        dialog.rejected.connect(lambda reason: signal_data.append(reason))

        dialog.notes_input.setText("Wrong compensation mapped")
        QTest.mouseClick(dialog.btn_cancel, Qt.LeftButton)

        rejected_cb.assert_called_once_with("Wrong compensation mapped")
        self.assertEqual(signal_data, ["Wrong compensation mapped"])
        self.assertEqual(dialog.result(), QDialog.Rejected)


class TestUniversalInterventionDialog(unittest.TestCase):
    """Tests for interactive intervention dialogs (CAPTCHA, Login, Fields)."""

    def test_intervention_dialog_captcha(self):
        resumed_cb = MagicMock()
        signal_data = []

        dialog = UniversalInterventionDialog(
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Cloudflare Turnstile detected in browser.",
            on_resumed=resumed_cb,
        )
        dialog.resumed.connect(lambda data: signal_data.append(data))

        labels = [lbl.text() for lbl in dialog.findChildren(QLabel)]
        self.assertTrue(any("Security Verification Detected" in t for t in labels))
        self.assertEqual(dialog.windowTitle(), "Action Required — Automation Paused")
        self.assertIsNone(dialog.field_input)

        QTest.mouseClick(dialog.btn_resume, Qt.LeftButton)
        resumed_cb.assert_called_once_with({"action": "RESUME"})
        self.assertEqual(signal_data, [{"action": "RESUME"}])
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_intervention_dialog_unknown_field_input(self):
        resumed_cb = MagicMock()
        signal_data = []

        dialog = UniversalInterventionDialog(
            intervention_type=InterventionType.UNKNOWN_REQUIRED_FIELD,
            message="Please provide your Github profile URL.",
            details={"field_name": "GitHub URL"},
            on_resumed=resumed_cb,
        )
        dialog.resumed.connect(lambda data: signal_data.append(data))

        self.assertIsNotNone(dialog.field_input)
        dialog.field_input.setText("https://github.com/developer")

        QTest.mouseClick(dialog.btn_resume, Qt.LeftButton)
        expected = {"action": "RESUME", "value": "https://github.com/developer"}
        resumed_cb.assert_called_once_with(expected)
        self.assertEqual(signal_data, [expected])
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_intervention_dialog_two_factor_auth_otp(self):
        resumed_cb = MagicMock()
        signal_data = []

        dialog = UniversalInterventionDialog(
            intervention_type=InterventionType.TWO_FACTOR_AUTH,
            message="One-time verification code (OTP) required. Please enter the verification code.",
            on_resumed=resumed_cb,
        )
        dialog.resumed.connect(lambda data: signal_data.append(data))

        self.assertIsNotNone(dialog.field_input)
        self.assertEqual(dialog.btn_resume.text(), "Verify & Continue")
        labels = [lbl.text() for lbl in dialog.findChildren(QLabel)]
        self.assertTrue(any("Verification Code (OTP) Required" in t for t in labels))

        dialog.field_input.setText("654321")
        QTest.mouseClick(dialog.btn_resume, Qt.LeftButton)

        expected = {"action": "RESUME", "code": "654321", "value": "654321"}
        resumed_cb.assert_called_once_with(expected)
        self.assertEqual(signal_data, [expected])
        self.assertEqual(dialog.result(), QDialog.Accepted)

    def test_intervention_dialog_takeover_and_cancel(self):
        takeover_cb = MagicMock()
        dialog = UniversalInterventionDialog(
            intervention_type=InterventionType.LOGIN_REQUIRED,
            message="Please log in to Workday.",
            on_takeover=takeover_cb,
        )
        QTest.mouseClick(dialog.btn_takeover, Qt.LeftButton)
        takeover_cb.assert_called_once_with(None)
        self.assertEqual(dialog.result(), QDialog.Accepted)

        cancelled_cb = MagicMock()
        dialog_cancel = UniversalInterventionDialog(
            intervention_type=InterventionType.LOGIN_REQUIRED,
            message="Please log in to Workday.",
            on_cancelled=cancelled_cb,
        )
        QTest.mouseClick(dialog_cancel.btn_cancel, Qt.LeftButton)
        cancelled_cb.assert_called_once()
        self.assertEqual(dialog_cancel.result(), QDialog.Rejected)

    def test_intervention_dialog_multi_unresolved_fields(self):
        resumed_cb = MagicMock()
        signal_data = []

        dialog = UniversalInterventionDialog(
            intervention_type=InterventionType.UNKNOWN_REQUIRED_FIELD,
            message="Missing required candidate facts for: Full Legal Name, Current CTC",
            details={
                "unresolved_fields": ["Full Legal Name", "Current CTC"],
                "field_name": "Full Legal Name",
            },
            on_resumed=resumed_cb,
        )
        dialog.resumed.connect(lambda data: signal_data.append(data))

        self.assertEqual(len(dialog.field_inputs), 2)
        self.assertIn("Full Legal Name", dialog.field_inputs)
        self.assertIn("Current CTC", dialog.field_inputs)

        dialog.field_inputs["Full Legal Name"].setText("Ahmad Raza")
        dialog.field_inputs["Current CTC"].setText("12 LPA")

        QTest.mouseClick(dialog.btn_resume, Qt.LeftButton)
        expected = {
            "action": "RESUME",
            "Full Legal Name": "Ahmad Raza",
            "Current CTC": "12 LPA",
            "value": "Ahmad Raza",
        }
        resumed_cb.assert_called_once_with(expected)
        self.assertEqual(signal_data, [expected])
        self.assertEqual(dialog.result(), QDialog.Accepted)


class TestUniversalTimelineWidget(unittest.TestCase):
    """Tests for the step-by-step universal agent timeline."""

    def test_timeline_lifecycle_progression(self):
        timeline = UniversalTimelineWidget()
        self.assertEqual(timeline.current_step, "IDLE")
        self.assertEqual(timeline.lbl_status_msg.text(), "Idle")

        # Initializing
        timeline.update_state("INITIALIZING")
        self.assertEqual(timeline.current_step, "INITIALIZING")
        self.assertEqual(timeline.step_widgets["INITIALIZING"]["badge"].text(), "●")
        self.assertEqual(timeline.step_widgets["NAVIGATING"]["badge"].text(), "○")

        # Progress to FILLING_FORM
        timeline.update_state("FILLING_FORM", message="Populating fields...")
        self.assertEqual(timeline.current_step, "FILLING_FORM")
        self.assertEqual(timeline.lbl_status_msg.text(), "Populating fields...")
        # Previous steps should be checkmarked
        self.assertEqual(timeline.step_widgets["INITIALIZING"]["badge"].text(), "✓")
        self.assertEqual(timeline.step_widgets["NAVIGATING"]["badge"].text(), "✓")
        self.assertEqual(timeline.step_widgets["ANALYZING_PAGE"]["badge"].text(), "✓")
        self.assertEqual(timeline.step_widgets["MAPPING_FIELDS"]["badge"].text(), "✓")
        self.assertEqual(timeline.step_widgets["FILLING_FORM"]["badge"].text(), "●")
        self.assertEqual(timeline.step_widgets["PENDING_HUMAN_REVIEW"]["badge"].text(), "○")

        # Human Review Gate
        timeline.update_state("PENDING_HUMAN_REVIEW")
        self.assertEqual(timeline.step_widgets["PENDING_HUMAN_REVIEW"]["badge"].text(), "⚠")

        # Completed
        timeline.update_state("COMPLETED")
        for step_key, _ in UniversalTimelineWidget.STEPS[:-1]:
            self.assertEqual(timeline.step_widgets[step_key]["badge"].text(), "✓")
        self.assertEqual(timeline.step_widgets["COMPLETED"]["badge"].text(), "●")

        # Reset
        timeline.reset()
        self.assertEqual(timeline.current_step, "IDLE")
        self.assertEqual(timeline.step_widgets["INITIALIZING"]["badge"].text(), "○")


class TestAutomationViewUniversalIntegration(unittest.TestCase):
    """Tests for AutomationView integration with universal review and interventions."""

    def setUp(self):
        self.mock_manager = MagicMock()
        self.mock_manager.get_state.return_value = AutomationState.IDLE
        self.view = AutomationView(automation_manager=self.mock_manager)

    def tearDown(self):
        if hasattr(self.view, "_active_review_dialog") and self.view._active_review_dialog:
            self.view._active_review_dialog.close()
        if hasattr(self.view, "_active_int_dialog") and self.view._active_int_dialog:
            self.view._active_int_dialog.close()

    def test_timeline_updates_on_state_change(self):
        self.view._on_state_changed("run-test", "INITIALIZING")
        self.assertEqual(self.view.universal_timeline.current_step, "INITIALIZING")

    def test_routes_pre_submission_review_to_review_dialog(self):
        event = AutomationInterventionEvent(
            run_id="run-test",
            platform="universal",
            intervention_type=InterventionType.PRE_SUBMISSION_REVIEW,
            message="Please review all mapped fields before submitting.",
            details={"fill_result": {"Name": "Test User"}},
        )
        self.view._on_intervention_required(event)

        self.assertIsNotNone(self.view._active_review_dialog)
        self.assertTrue(isinstance(self.view._active_review_dialog, UniversalReviewDialog))
        self.assertEqual(self.view._active_review_dialog.table.rowCount(), 1)

    def test_routes_unknown_field_to_universal_intervention_dialog(self):
        event = AutomationInterventionEvent(
            run_id="run-test",
            platform="universal",
            intervention_type=InterventionType.UNKNOWN_REQUIRED_FIELD,
            message="Unknown field detected.",
            details={"field_name": "Sponsorship required?"},
        )
        self.view._on_intervention_required(event)

        self.assertIsNotNone(self.view._active_int_dialog)
        self.assertTrue(isinstance(self.view._active_int_dialog, UniversalInterventionDialog))

    def test_dismisses_dialogs_on_submission_event(self):
        review_dialog = MagicMock()
        int_dialog = MagicMock()
        self.view._active_review_dialog = review_dialog
        self.view._active_int_dialog = int_dialog

        sub_event = ApplicationSubmittedEvent(
            run_id="run-test",
            platform="universal",
            title="Software Engineer",
            company="Acme Corp",
            status="SUCCESS",
        )
        self.view._on_application_submitted(sub_event)

        review_dialog.accept.assert_called_once()
        int_dialog.accept.assert_called_once()
        self.assertIsNone(self.view._active_review_dialog)
        self.assertIsNone(self.view._active_int_dialog)


if __name__ == "__main__":
    unittest.main()
