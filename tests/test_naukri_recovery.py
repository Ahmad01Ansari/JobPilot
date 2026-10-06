'''
Unit Tests for Naukri Error Recovery Engine (Phase 13)
Deliberately tests browser errors, authentication challenges, and application failures:
- Browser: timeout, stale element, network delay, unexpected popup, webdriver exception
- Authentication: session expired, login required, OTP, CAPTCHA, incomplete profile
- Application: missing field, unexpected form, external redirect, post-click submission timeout (UNKNOWN)
Verifies that all failures transition cleanly to controlled states (FAILED, MANUAL_REQUIRED, UNKNOWN, EXTERNAL)
and never crash the automation run.
'''

import unittest
from unittest.mock import MagicMock, patch
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException,
    WebDriverException,
)

from modules.models import Job
from platforms.naukri.recovery import (
    classify_error,
    dismiss_unexpected_popups,
    retry_on_transient_error,
    safe_apply_job,
)
from platforms.naukri.selectors import POPUP_DISMISS_SELECTORS


class TestNaukriRecovery(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_browser = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_tracker = MagicMock()

        self.sample_job = Job(
            platform="naukri",
            job_id="naukri_err_555",
            title="AI Automation Engineer",
            company="Robotics Inc",
            location="Gurgaon, India",
            source_url="https://www.naukri.com/job-listings-555",
        )

    # 1. Browser Error Classification Tests
    def test_classify_browser_timeout_before_submit(self):
        exc = TimeoutException("Timed out waiting for element presence")
        state, reason = classify_error(exc, context="page_load")
        self.assertEqual(state, "FAILED")
        self.assertIn("timeout", reason.lower())

    def test_classify_browser_timeout_post_submit(self):
        # Strict idempotency: timeout during submission -> UNKNOWN
        exc = TimeoutException("Confirmation not detected")
        state, reason = classify_error(exc, context="submit")
        self.assertEqual(state, "UNKNOWN")
        self.assertIn("prevent duplicate", reason.lower())

    def test_classify_stale_element(self):
        exc = StaleElementReferenceException("Element is no longer attached to DOM")
        state, reason = classify_error(exc, context="form_fill")
        self.assertEqual(state, "FAILED")
        self.assertIn("stale", reason.lower())

    def test_classify_click_intercepted(self):
        exc = ElementClickInterceptedException("Element <button> is not clickable at point, overlay obscures it")
        state, reason = classify_error(exc, context="button_click")
        self.assertEqual(state, "FAILED")
        self.assertIn("intercepted", reason.lower())

    def test_classify_webdriver_exception(self):
        exc = WebDriverException("Chrome process crashed or disconnected")
        state, reason = classify_error(exc, context="navigation")
        self.assertEqual(state, "FAILED")
        self.assertIn("webdriver", reason.lower())

    # 2. Authentication Challenge Classification Tests
    def test_classify_captcha_challenge(self):
        exc = Exception("Encountered CAPTCHA verification iframe")
        state, reason = classify_error(exc, context="apply_modal")
        self.assertEqual(state, "MANUAL_REQUIRED")
        self.assertIn("captcha", reason.lower())

    def test_classify_otp_challenge(self):
        exc = Exception("Two-factor OTP required to continue")
        state, reason = classify_error(exc, context="login")
        self.assertEqual(state, "MANUAL_REQUIRED")
        self.assertIn("otp", reason.lower())

    def test_classify_session_expired(self):
        exc = Exception("Session expired; please login again")
        state, reason = classify_error(exc, context="apply_click")
        self.assertEqual(state, "MANUAL_REQUIRED")
        self.assertIn("session expired", reason.lower())

    def test_classify_incomplete_profile(self):
        exc = Exception("Incomplete profile: please update profile before applying")
        state, reason = classify_error(exc, context="apply_click")
        self.assertEqual(state, "MANUAL_REQUIRED")
        self.assertIn("profile", reason.lower())

    # 3. Application Flow Classification Tests
    def test_classify_external_redirect(self):
        exc = Exception("Redirected to external portal: https://careers.company.com")
        state, reason = classify_error(exc, context="apply_flow")
        self.assertEqual(state, "EXTERNAL")
        self.assertIn("external", reason.lower())

    def test_classify_missing_field_or_element(self):
        exc = NoSuchElementException("Unable to locate element: div.question-item")
        state, reason = classify_error(exc, context="form_fill")
        self.assertEqual(state, "FAILED")
        self.assertIn("missing", reason.lower())

    # 4. Popup Sweeper Tests
    def test_dismiss_unexpected_popups(self):
        btn1 = MagicMock()
        btn1.is_displayed.return_value = True

        btn2 = MagicMock()
        btn2.is_displayed.return_value = False

        def find_elements(by, sel):
            if sel in POPUP_DISMISS_SELECTORS:
                return [btn1, btn2]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        dismissed = dismiss_unexpected_popups(self.mock_driver)
        self.assertGreaterEqual(dismissed, 1)
        btn1.click.assert_called()

    # 5. Retry on Transient Errors Tests
    def test_retry_on_stale_element_success(self):
        mock_action = MagicMock()
        # Fails with StaleElement on attempt 1, succeeds on attempt 2
        mock_action.side_effect = [
            StaleElementReferenceException("Stale"),
            "SUCCESS",
        ]

        result = retry_on_transient_error(mock_action, retries=3, delay=0.01)
        self.assertEqual(result, "SUCCESS")
        self.assertEqual(mock_action.call_count, 2)

    def test_retry_on_click_intercepted_sweeps_popups(self):
        mock_action = MagicMock()
        mock_action.side_effect = [
            ElementClickInterceptedException("Intercepted"),
            "CLICKED",
        ]

        # Driver has popup
        close_btn = MagicMock()
        close_btn.is_displayed.return_value = True
        self.mock_driver.find_elements.return_value = [close_btn]

        result = retry_on_transient_error(
            mock_action, retries=3, delay=0.01, driver=self.mock_driver
        )
        self.assertEqual(result, "CLICKED")
        self.assertEqual(mock_action.call_count, 2)
        close_btn.click.assert_called()

    # 6. Safe Job Application Runner Tests
    def test_safe_apply_job_catches_unhandled_crash(self):
        mock_applier = MagicMock()
        mock_applier.driver = self.mock_driver
        mock_applier.tracker = self.mock_tracker
        mock_applier.flow_detector = MagicMock()
        self.mock_driver.window_handles = ["win_main"]

        # Simulate severe unhandled crash inside apply_to_job
        mock_applier.apply_to_job.side_effect = WebDriverException("Unexpected browser crash!")

        # Safe apply must NOT raise an exception
        result = safe_apply_job(mock_applier, self.sample_job)

        self.assertTrue(result["recovered"])
        self.assertEqual(result["status"], "FAILED")
        self.assertIn("WebDriver", result["reason"])

        # Tracker recorded controlled state
        self.mock_tracker.record_state.assert_called_once_with(
            self.sample_job, "FAILED", reason=result["reason"]
        )
        mock_applier.flow_detector.close_modal_if_open.assert_called_once()

    def test_safe_apply_job_restores_window_handles_on_crash(self):
        mock_applier = MagicMock()
        mock_applier.driver = self.mock_driver
        mock_applier.tracker = self.mock_tracker
        mock_applier.flow_detector = MagicMock()

        # Started with 1 window
        self.mock_driver.window_handles = ["win_main"]

        def crash_with_new_tab(*args, **kwargs):
            self.mock_driver.window_handles = ["win_main", "win_rogue_popup"]
            raise Exception("Page crashed with open rogue tab")

        mock_applier.apply_to_job.side_effect = crash_with_new_tab

        result = safe_apply_job(mock_applier, self.sample_job)
        self.assertTrue(result["recovered"])
        self.mock_driver.close.assert_called_once()
        self.mock_driver.switch_to.window.assert_any_call("win_main")



if __name__ == "__main__":
    unittest.main()
