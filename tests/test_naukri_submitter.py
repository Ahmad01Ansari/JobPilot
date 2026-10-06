'''
Unit Tests for NaukriSubmitter & Submission Confirmation (Phase 12)
Validates submit button finding, post-click verification across all 3 indicator layers,
idempotency enforcement on unconfirmed clicks (setting UNKNOWN and blocking retry),
and NaukriApplier end-to-end approval-to-submission execution.
'''

import unittest
from unittest.mock import MagicMock, patch

from modules.models import Job
from modules.tracker import ApplicationTracker
from platforms.naukri.submitter import NaukriSubmitter
from platforms.naukri.applier import NaukriApplier
from platforms.naukri.safety_gate import SafetyGateResult
from platforms.naukri.selectors import (
    SUBMISSION_SUCCESS_SELECTORS,
    APPLIED_BUTTON_SELECTORS,
)


class TestNaukriSubmitter(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_tracker = MagicMock()

        self.submitter = NaukriSubmitter(
            browser=self.mock_browser,
            tracker=self.mock_tracker,
        )

        self.sample_job = Job(
            platform="naukri",
            job_id="naukri_submit_999",
            title="Automation Anywhere Developer",
            company="Global RPA Tech",
            location="Bangalore, India",
            source_url="https://www.naukri.com/job-listings-999",
        )

    def test_find_submit_button(self):
        btn_next = MagicMock()
        btn_next.text = "Save and Next"
        btn_next.is_displayed.return_value = True
        btn_next.is_enabled.return_value = True

        btn_submit = MagicMock()
        btn_submit.text = "Submit Application"
        btn_submit.is_displayed.return_value = True
        btn_submit.is_enabled.return_value = True

        self.mock_driver.find_elements.return_value = [btn_next, btn_submit]

        found = self.submitter.find_submit_button()
        self.assertEqual(found, btn_submit)

    def test_verify_submission_via_success_banner(self):
        banner = MagicMock()
        banner.is_displayed.return_value = True
        banner.text = "Application sent successfully!"

        def find_elements(by, selector):
            if selector in SUBMISSION_SUCCESS_SELECTORS:
                return [banner]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        confirmed, reason = self.submitter.verify_submission(timeout=1.0)
        self.assertTrue(confirmed)
        self.assertIn("Success indicator found", reason)

    def test_verify_submission_via_applied_button(self):
        btn_applied = MagicMock()
        btn_applied.is_displayed.return_value = True
        btn_applied.text = "Applied"

        def find_elements(by, selector):
            if selector in APPLIED_BUTTON_SELECTORS:
                return [btn_applied]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        confirmed, reason = self.submitter.verify_submission(timeout=1.0)
        self.assertTrue(confirmed)
        self.assertIn("Applied button detected", reason)

    def test_verify_submission_via_body_text(self):
        self.mock_driver.find_elements.return_value = []
        body_mock = MagicMock()
        body_mock.text = "Thank you. You have applied for this position."
        self.mock_driver.find_element.return_value = body_mock

        confirmed, reason = self.submitter.verify_submission(timeout=1.0)
        self.assertTrue(confirmed)
        self.assertIn("Confirmation text matched", reason)

    def test_verify_submission_timeout_returns_false(self):
        self.mock_driver.find_elements.return_value = []
        body_mock = MagicMock()
        body_mock.text = "Still on form page with questions"
        self.mock_driver.find_element.return_value = body_mock

        confirmed, reason = self.submitter.verify_submission(timeout=0.2, check_interval=0.05)
        self.assertFalse(confirmed)
        self.assertIn("timed out", reason.lower())

    def test_submit_application_success(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.is_enabled.return_value = True
        btn.text = "Submit"

        self.submitter.find_submit_button = MagicMock(return_value=btn)
        self.submitter.verify_submission = MagicMock(return_value=(True, "Success banner detected"))

        success, reason = self.submitter.submit_application(self.sample_job)
        self.assertTrue(success)
        self.assertEqual(reason, "CONFIRMED_SUBMITTED")
        btn.click.assert_called_once()
        self.mock_tracker.record_state.assert_called_once_with(self.sample_job, "SUBMITTED")

    def test_submit_application_click_with_timeout_records_unknown(self):
        # Critical test: click dispatched, but verification timed out
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.is_enabled.return_value = True
        btn.text = "Submit"

        self.submitter.find_submit_button = MagicMock(return_value=btn)
        self.submitter.verify_submission = MagicMock(return_value=(False, "Timed out after 8s"))

        success, reason = self.submitter.submit_application(self.sample_job)
        self.assertFalse(success)
        self.assertIn("TIMEOUT_UNKNOWN", reason)

        # Enforce that tracker recorded UNKNOWN to block dangerous automated retry
        self.mock_tracker.record_state.assert_called_once()
        call_args = self.mock_tracker.record_state.call_args[0]
        self.assertEqual(call_args[0], self.sample_job)
        self.assertEqual(call_args[1], "UNKNOWN")

    def test_submit_application_missing_button_records_failed(self):
        self.submitter.find_submit_button = MagicMock(return_value=None)

        success, reason = self.submitter.submit_application(self.sample_job)
        self.assertFalse(success)
        self.assertEqual(reason, "SUBMIT_BUTTON_NOT_FOUND")
        self.mock_tracker.record_state.assert_called_once_with(
            self.sample_job, "FAILED", reason="Submit button not found"
        )

    def test_naukri_applier_pipeline_to_submission(self):
        # Full integration through NaukriApplier
        mock_flow = MagicMock()
        mock_flow.find_apply_button.return_value = MagicMock()
        mock_flow.detect_apply_button_type.return_value = "DIRECT"
        mock_flow.detect_flow_after_click.return_value = ("QUESTIONNAIRE", "Screening modal")

        mock_form = MagicMock()
        mock_form.fill_form.return_value = {
            "status": "READY_TO_SUBMIT",
            "filled_fields": [{"field": "Years of experience", "value": "2"}],
        }

        mock_gate = MagicMock()
        mock_gate.review.return_value = SafetyGateResult(
            decision="APPROVE",
            summary=MagicMock(),
            approved=True,
        )

        mock_submitter = MagicMock()
        mock_submitter.submit_application.return_value = (True, "CONFIRMED_SUBMITTED")

        applier = NaukriApplier(
            browser=self.mock_browser,
            form=mock_form,
            safety_gate=mock_gate,
            submitter=mock_submitter,
            flow_detector=mock_flow,
            tracker=self.mock_tracker,
        )

        res = applier.apply_to_job(self.sample_job)
        self.assertEqual(res["status"], "SUBMITTED")
        mock_gate.review.assert_called_once()
        mock_submitter.submit_application.assert_called_once_with(self.sample_job)


if __name__ == "__main__":
    unittest.main()
