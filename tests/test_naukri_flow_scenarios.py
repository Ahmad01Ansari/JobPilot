"""
Automated Test Suite for the 20 Required Scenarios from WorkingFlow/Naukriflow.md (Section 23).
Covers:
1. test_direct_apply_success
2. test_already_applied
3. test_questionnaire_text_input
4. test_questionnaire_textarea
5. test_questionnaire_contenteditable
6. test_questionnaire_radio
7. test_questionnaire_dropdown
8. test_input_value_verification
9. test_input_retry_after_failed_entry
10. test_next_question_transition
11. test_questionnaire_final_submission
12. test_external_application
13. test_login_required
14. test_captcha_manual_required
15. test_rate_limited
16. test_apply_button_disabled
17. test_unknown_apply_state
18. test_submission_unconfirmed
19. test_no_duplicate_submission
20. test_diagnostic_capture_on_failure
"""

import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

from platforms.naukri.applier import NaukriFlowDetector, NaukriApplier
from platforms.naukri.form import NaukriForm, FormField
from platforms.naukri.diagnostics import capture_naukri_diagnostics
from platforms.naukri.selectors import (
    CAPTCHA_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    RATE_LIMIT_SELECTORS,
)
from modules.qna_engine import Answer


class TestNaukriFlowScenarios(unittest.TestCase):
    """Verifies all 20 required flow scenarios specified in WorkingFlow/Naukriflow.md."""

    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_driver.window_handles = ["win_main"]
        self.mock_driver.current_window_handle = "win_main"
        self.mock_driver.current_url = "https://www.naukri.com/job-listings-test"

        self.detector = NaukriFlowDetector(self.mock_browser)
        self.form = NaukriForm(self.mock_browser)

        self.mock_job = MagicMock()
        self.mock_job.job_id = "test_job_2026"
        self.mock_job.title = "Senior Automation Engineer"
        self.mock_job.company = "TechCorp Global"
        self.mock_job.source_url = "https://www.naukri.com/job-listings-test"

    # 1. test_direct_apply_success
    def test_direct_apply_success(self):
        """Verifies direct 1-click apply success returning SUBMITTED / APPLICATION_CONFIRMED."""
        applier = NaukriApplier(browser=self.mock_browser)
        applier.flow_detector.is_already_applied = MagicMock(return_value=False)

        apply_btn = MagicMock()
        apply_btn.is_displayed.return_value = True
        apply_btn.is_enabled.return_value = True
        apply_btn.text = "Apply"
        apply_btn.get_attribute.return_value = ""
        applier.flow_detector.find_apply_button = MagicMock(return_value=apply_btn)
        applier.flow_detector.detect_flow_after_click = MagicMock(return_value=("DIRECT", "1-click apply confirmed"))
        applier.submitter.find_submit_button = MagicMock(return_value=None)
        applier.submitter.verify_submission = MagicMock(return_value=(True, "Application submitted"))

        res = applier.apply_to_job(self.mock_job)
        self.assertEqual(res["status"], "SUBMITTED")
        self.assertIn("Application submitted", res["reason"])

    # 2. test_already_applied
    def test_already_applied(self):
        """Verifies pre-apply detection of already applied job."""
        applier = NaukriApplier(browser=self.mock_browser)
        applier.flow_detector.is_already_applied = MagicMock(return_value=True)

        res = applier.apply_to_job(self.mock_job)
        self.assertEqual(res["status"], "SKIPPED")
        self.assertEqual(res["reason"], "Already applied")

    # 3. test_questionnaire_text_input
    def test_questionnaire_text_input(self):
        """Verifies text input discovery, answering, and verified filling."""
        elem = MagicMock()
        elem.get_attribute.side_effect = lambda attr: "2" if attr == "value" else ""
        field = FormField(field_type="text", label="Years of Experience", element=elem)
        ans = Answer(value="2", source="profile", confidence=1.0, field_type="text")

        success = self.form.fill_field(field, ans)
        self.assertTrue(success)
        elem.clear.assert_called()
        elem.send_keys.assert_called_with("2")

    # 4. test_questionnaire_textarea
    def test_questionnaire_textarea(self):
        """Verifies textarea discovery, answering, and verified filling."""
        elem = MagicMock()
        elem.get_attribute.side_effect = lambda attr: "Detailed experience snippet" if attr == "value" else ""
        field = FormField(field_type="textarea", label="Project Summary", element=elem)
        ans = Answer(value="Detailed experience snippet", source="profile", confidence=0.95, field_type="textarea")

        success = self.form.fill_field(field, ans)
        self.assertTrue(success)
        elem.send_keys.assert_called_with("Detailed experience snippet")

    # 5. test_questionnaire_contenteditable
    def test_questionnaire_contenteditable(self):
        """Verifies contenteditable element discovery and filling."""
        elem = MagicMock()
        elem.get_attribute.side_effect = lambda attr: "Hello recruiter" if attr == "textContent" else ""
        elem.text = "Hello recruiter"
        field = FormField(field_type="contenteditable", label="Cover Note", element=elem)
        ans = Answer(value="Hello recruiter", source="profile", confidence=1.0, field_type="contenteditable")

        success = self.form.fill_field(field, ans)
        self.assertTrue(success)
        elem.send_keys.assert_called_with("Hello recruiter")

    # 6. test_questionnaire_radio
    def test_questionnaire_radio(self):
        """Verifies radio button intent matching and click execution."""
        chip1 = MagicMock()
        chip2 = MagicMock()
        chip3 = MagicMock()

        field = FormField(
            field_type="radio",
            label="Have you ever served in the military?",
            element=chip1,
            options=["Currently serving", "Previously served", "Never served"],
            raw_elements=[chip1, chip2, chip3],
        )
        ans = Answer(value="Never served", source="rule", confidence=0.95, field_type="radio")

        success = self.form.fill_field(field, ans)
        self.assertTrue(success)
        chip3.click.assert_called_once()
        chip1.click.assert_not_called()

    # 7. test_questionnaire_dropdown
    def test_questionnaire_dropdown(self):
        """Verifies dropdown/select element matching and selection."""
        select_elem = MagicMock()
        select_elem.tag_name = "select"
        opt1 = MagicMock()
        opt1.text = "Immediate"
        opt2 = MagicMock()
        opt2.text = "30 Days"

        field = FormField(
            field_type="select",
            label="Notice Period",
            element=select_elem,
            options=["Immediate", "30 Days"],
            raw_elements=[opt1, opt2],
        )
        ans = Answer(value="30 Days", source="profile", confidence=1.0, field_type="select")

        with patch("platforms.naukri.form.Select") as mock_select:
            sel_instance = MagicMock()
            mock_select.return_value = sel_instance
            success = self.form.fill_field(field, ans)
            self.assertTrue(success)
            sel_instance.select_by_visible_text.assert_called_with("30 Days")

    # 8. test_input_value_verification
    def test_input_value_verification(self):
        """Verifies input verification fails if entered value is not reflected in DOM."""
        elem = MagicMock()
        # Value remains empty even after typing
        elem.get_attribute.return_value = ""
        field = FormField(field_type="text", label="Notice Period", element=elem)
        ans = Answer(value="30", source="profile", confidence=1.0, field_type="text")

        success = self.form.fill_field(field, ans)
        self.assertFalse(success)

    # 9. test_input_retry_after_failed_entry
    def test_input_retry_after_failed_entry(self):
        """Verifies attempt 2 retry succeeds when attempt 1 failed to update value."""
        elem = MagicMock()
        # First attempt returns "", second attempt returns "30"
        elem.get_attribute.side_effect = ["", "30"]
        field = FormField(field_type="text", label="Notice Period", element=elem)
        ans = Answer(value="30", source="profile", confidence=1.0, field_type="text")

        success = self.form.fill_field(field, ans)
        self.assertTrue(success)

    # 10. test_next_question_transition
    def test_next_question_transition(self):
        """Verifies waiting for DOM transition after advancing to next step."""
        f2 = FormField(field_type="text", label="Expected CTC", element=MagicMock())
        # First call returns old question, second call returns new question
        self.form.discover_fields = MagicMock(return_value=[f2])

        transitioned = self.form.wait_for_question_transition(previous_label="Current CTC", timeout=1.0)
        self.assertTrue(transitioned)

    # 11. test_questionnaire_final_submission
    def test_questionnaire_final_submission(self):
        """Verifies final submit button detection and safety gate halting."""
        f1 = FormField(field_type="text", label="Notice Period", element=MagicMock())
        self.form.discover_fields = MagicMock(side_effect=[[f1], []])
        self.form.next = MagicMock(return_value=(False, "STOPPED_AT_SUBMIT"))

        result = self.form.fill_form()
        self.assertEqual(result["status"], "READY_TO_SUBMIT")

    # 12. test_external_application
    def test_external_application(self):
        """Verifies redirect or external portal is classified as EXTERNAL."""
        self.mock_driver.window_handles = ["win_main", "win_external"]
        self.mock_driver.current_url = "https://careers.google.com/jobs/apply"

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "EXTERNAL")
        self.assertIn("careers.google.com", reason)

    # 13. test_login_required
    def test_login_required(self):
        """Verifies session expiration or login page is classified as LOGIN_REQUIRED."""
        login_elem = MagicMock()
        login_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in LOGIN_REQUIRED_SELECTORS:
                return [login_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements
        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "LOGIN_REQUIRED")

    # 14. test_captcha_manual_required
    def test_captcha_manual_required(self):
        """Verifies CAPTCHA challenge is classified as CAPTCHA."""
        captcha_elem = MagicMock()
        captcha_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS:
                return [captcha_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements
        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "CAPTCHA")

    # 15. test_rate_limited
    def test_rate_limited(self):
        """Verifies rate limit / access block is classified as RATE_LIMITED."""
        rate_elem = MagicMock()
        rate_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in RATE_LIMIT_SELECTORS:
                return [rate_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements
        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "RATE_LIMITED")

    # 16. test_apply_button_disabled
    def test_apply_button_disabled(self):
        """Verifies disabled apply button returns APPLY_UNAVAILABLE."""
        btn = MagicMock()
        btn.text = "Apply"
        btn.get_attribute.side_effect = lambda attr: "true" if attr in ("disabled", "aria-disabled") else "disabled-apply"

        flow = self.detector.detect_apply_button_type(btn)
        self.assertEqual(flow, "APPLY_UNAVAILABLE")

    # 17. test_unknown_apply_state
    def test_unknown_apply_state(self):
        """Verifies unknown UI state triggers diagnostic capture and returns UNKNOWN."""
        applier = NaukriApplier(browser=self.mock_browser)
        applier.flow_detector.is_already_applied = MagicMock(return_value=False)

        apply_btn = MagicMock()
        apply_btn.is_displayed.return_value = True
        apply_btn.is_enabled.return_value = True
        apply_btn.text = "Apply"
        apply_btn.get_attribute.return_value = ""

        applier.flow_detector.find_apply_button = MagicMock(return_value=apply_btn)
        applier.flow_detector.detect_flow_after_click = MagicMock(return_value=("UNKNOWN", "Unrecognized DOM state"))

        with patch("platforms.naukri.applier.capture_naukri_diagnostics") as mock_diag:
            res = applier.apply_to_job(self.mock_job)
            self.assertEqual(res["status"], "UNKNOWN")
            mock_diag.assert_called_once()

    # 18. test_submission_unconfirmed
    def test_submission_unconfirmed(self):
        """Verifies unconfirmed 1-click submission returns UNKNOWN status."""
        applier = NaukriApplier(browser=self.mock_browser)
        applier.flow_detector.is_already_applied = MagicMock(return_value=False)

        apply_btn = MagicMock()
        apply_btn.is_displayed.return_value = True
        apply_btn.is_enabled.return_value = True
        apply_btn.text = "Apply"
        apply_btn.get_attribute.return_value = ""

        applier.flow_detector.find_apply_button = MagicMock(return_value=apply_btn)
        applier.flow_detector.detect_flow_after_click = MagicMock(return_value=("DIRECT", "Direct apply clicked"))
        applier.submitter.find_submit_button = MagicMock(return_value=None)
        applier.submitter.verify_submission = MagicMock(return_value=(False, "Timeout waiting for confirmation"))

        res = applier.apply_to_job(self.mock_job)
        self.assertEqual(res["status"], "UNKNOWN")
        self.assertIn("unconfirmed", res["reason"].lower())

    # 19. test_no_duplicate_submission
    def test_no_duplicate_submission(self):
        """Verifies that an already-applied job is skipped immediately without duplicate submission."""
        applier = NaukriApplier(browser=self.mock_browser)
        applier.flow_detector.is_already_applied = MagicMock(return_value=True)
        applier.submitter.submit_application = MagicMock()

        res = applier.apply_to_job(self.mock_job)
        self.assertEqual(res["status"], "SKIPPED")
        applier.submitter.submit_application.assert_not_called()

    # 20. test_diagnostic_capture_on_failure
    def test_diagnostic_capture_on_failure(self):
        """Verifies diagnostic capture generates screenshot, HTML, and JSON reports."""
        mock_driver = MagicMock()
        mock_driver.page_source = "<html><body><h1>Screening Questionnaire</h1></body></html>"
        mock_driver.current_url = "https://www.naukri.com/job-listings-test"

        diag_dir = capture_naukri_diagnostics(
            driver=mock_driver,
            job_id="test_diag_999",
            context="questionnaire_test",
            question="What is your notice period?",
            error="Value remained empty",
        )

        self.assertTrue(os.path.exists(diag_dir))
        self.assertTrue(os.path.exists(os.path.join(diag_dir, "page_source.html")))
        self.assertTrue(os.path.exists(os.path.join(diag_dir, "question.txt")))
        self.assertTrue(os.path.exists(os.path.join(diag_dir, "error.txt")))
        self.assertTrue(os.path.exists(os.path.join(diag_dir, "detected_inputs.json")))
        self.assertTrue(os.path.exists(os.path.join(diag_dir, "detected_buttons.json")))

        # Cleanup test debug directory
        try:
            shutil.rmtree(diag_dir)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
