import unittest
from unittest.mock import MagicMock, patch

from platforms.indeed.captcha_handler import IndeedCaptchaHandler
from platforms.indeed.submitter import IndeedSubmitter
from platforms.indeed.form import IndeedForm
from app.services.automation_events import InterventionType, AutomationInterventionEvent


class TestIndeedCaptchaHandler(unittest.TestCase):
    """Unit tests for Indeed CAPTCHA detection and cooperative resolution handling."""

    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_browser = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_bridge = MagicMock()
        self.handler = IndeedCaptchaHandler(self.mock_browser, self.mock_bridge)

    def test_is_captcha_present_via_js(self):
        self.mock_driver.execute_script.return_value = True
        self.assertTrue(self.handler.is_captcha_present())

    def test_is_captcha_present_false(self):
        self.mock_driver.execute_script.return_value = False
        self.mock_driver.find_elements.return_value = []
        self.assertFalse(self.handler.is_captcha_present())

    def test_is_captcha_present_via_dom_fallback(self):
        self.mock_driver.execute_script.return_value = False
        mock_el = MagicMock()
        mock_el.is_displayed.return_value = True
        mock_el.size = {"width": 100, "height": 80}
        self.mock_driver.find_elements.return_value = [mock_el]
        self.assertTrue(self.handler.is_captcha_present())

    def test_is_captcha_present_ignores_hidden_elements(self):
        self.mock_driver.execute_script.return_value = False
        mock_hidden = MagicMock()
        mock_hidden.is_displayed.return_value = False
        mock_hidden.size = {"width": 0, "height": 0}
        self.mock_driver.find_elements.return_value = [mock_hidden]
        self.assertFalse(self.handler.is_captcha_present())

    def test_is_captcha_solved_via_js(self):
        self.mock_driver.execute_script.return_value = True
        self.assertTrue(self.handler.is_captcha_solved())

    def test_is_captcha_solved_when_not_present(self):
        # When JS returns False for solved, but captcha is not present at all
        self.mock_driver.execute_script.side_effect = [False, False]  # solved check, present check
        self.mock_driver.find_elements.return_value = []
        self.assertTrue(self.handler.is_captcha_solved())

    def test_is_captcha_solved_via_response_textarea(self):
        # JS returns False
        self.mock_driver.execute_script.return_value = False
        mock_textarea = MagicMock()
        mock_textarea.get_attribute.return_value = "03AFcWeA6789012345678901234567890"  # length > 20
        self.mock_driver.find_elements.return_value = [mock_textarea]
        self.assertTrue(self.handler.is_captcha_solved())

    def test_handle_captcha_returns_true_if_not_present(self):
        with patch.object(self.handler, "is_captcha_present", return_value=False):
            res = self.handler.handle_captcha(self.mock_driver, job_title="Dev", company="TestCo")
            self.assertTrue(res)

    def test_handle_captcha_returns_true_if_already_solved(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", return_value=True):
                res = self.handler.handle_captcha(self.mock_driver, job_title="Dev", company="TestCo")
                self.assertTrue(res)

    def test_handle_captcha_solves_in_countdown(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", side_effect=[False, False, True]):
                with patch("time.sleep"):
                    res = self.handler.handle_captcha(self.mock_driver, timeout=10)
                    self.assertTrue(res)

    def test_handle_captcha_timeout_returns_false(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", return_value=False):
                with patch("time.sleep"):
                    # Test timeout = 0 so loop exits immediately
                    res = self.handler.handle_captcha(self.mock_driver, timeout=0)
                    self.assertFalse(res)

    def test_handle_captcha_stops_on_stop_check(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", return_value=False):
                stop_check = MagicMock(return_value=True)
                res = self.handler.handle_captcha(self.mock_driver, timeout=10, stop_check=stop_check)
                self.assertFalse(res)

    def test_handle_captcha_emits_intervention_event(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", side_effect=[False, True]):
                with patch("time.sleep"):
                    self.handler.handle_captcha(
                        self.mock_driver,
                        job_title="Frontend Engineer",
                        company="Fintech Corp",
                        timeout=5,
                        automation_bridge=self.mock_bridge,
                    )
                    self.mock_bridge.handle_intervention.assert_called_once()
                    args, _ = self.mock_bridge.handle_intervention.call_args
                    event = args[0]
                    self.assertEqual(event.intervention_type, InterventionType.CAPTCHA_DETECTED)
                    self.assertIn("Frontend Engineer", event.message)
                    self.assertIn("Fintech Corp", event.message)

    def test_handle_captcha_resumes_when_user_marks_resolved_via_bridge(self):
        with patch.object(self.handler, "is_captcha_present", return_value=True):
            with patch.object(self.handler, "is_captcha_solved", return_value=False):
                self.mock_bridge.is_captcha_resolved_by_user.side_effect = [False, True]
                with patch("time.sleep"):
                    res = self.handler.handle_captcha(
                        self.mock_driver,
                        job_title="Dev",
                        company="Co",
                        timeout=10,
                        automation_bridge=self.mock_bridge,
                    )
                    self.assertTrue(res)
                    self.assertEqual(self.mock_bridge.reset_captcha_status.call_count, 2)

    def test_automation_bridge_captcha_state_lifecycle(self):
        from app.services.automation_bridge import AutomationBridge
        bridge = AutomationBridge()
        self.assertFalse(bridge.is_captcha_resolved_by_user())
        bridge.mark_captcha_resolved()
        self.assertTrue(bridge.is_captcha_resolved_by_user())
        bridge.reset_captcha_status()
        self.assertFalse(bridge.is_captcha_resolved_by_user())

    def test_consecutive_applications_captcha_isolation(self):
        """Ensures that user solving CAPTCHA on App 1 does NOT prevent detection on App 2."""
        from app.services.automation_bridge import AutomationBridge
        bridge = AutomationBridge()
        handler = IndeedCaptchaHandler(self.mock_browser, bridge)

        # Application 1: Captcha is present, user solves via dialog during wait loop
        def simulate_user_resolving(_):
            bridge.mark_captcha_resolved()

        with patch.object(handler, "is_captcha_present", return_value=True):
            with patch.object(handler, "is_captcha_solved", return_value=False):
                with patch("time.sleep", side_effect=simulate_user_resolving):
                    res1 = handler.handle_captcha(
                        self.mock_driver,
                        job_title="Job 1",
                        company="Company A",
                        timeout=5,
                        automation_bridge=bridge,
                    )
                    self.assertTrue(res1)
                    # Crucial: Bridge must be clean after handle_captcha finishes
                    self.assertFalse(bridge.is_captcha_resolved_by_user())

        # Application 2: Another CAPTCHA appears. It must NOT be considered solved!
        with patch.object(handler, "is_captcha_present", return_value=True):
            self.mock_driver.execute_script.return_value = False
            self.mock_driver.find_elements.return_value = []
            # is_captcha_solved must be FALSE on App 2
            self.assertFalse(handler.is_captcha_solved())


class TestIndeedSubmitterCaptchaIntegration(unittest.TestCase):
    """Tests that IndeedSubmitter properly integrates with CAPTCHA handling."""

    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_driver.current_window_handle = "app_win"
        self.mock_driver.window_handles = ["app_win", "main_win"]
        self.mock_browser = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_bridge = MagicMock()
        self.mock_captcha_handler = MagicMock()
        self.submitter = IndeedSubmitter(
            browser=self.mock_browser,
            tracker=MagicMock(),
            automation_bridge=self.mock_bridge,
            captcha_handler=self.mock_captcha_handler,
        )

    def test_submitter_waits_for_captcha_before_click(self):
        # 1. Captcha is present and not solved initially
        self.mock_captcha_handler.is_captcha_present.return_value = True
        self.mock_captcha_handler.is_captcha_solved.side_effect = [False, True, True, True]
        self.mock_captcha_handler.handle_captcha.return_value = True

        mock_btn = MagicMock()
        mock_btn.text = "Submit your application"
        mock_btn.is_displayed.return_value = True
        mock_btn.is_enabled.return_value = True

        with patch.object(self.submitter, "find_submit_button", return_value=mock_btn):
            with patch.object(self.submitter, "verify_confirmation", return_value=(True, "Application submitted")):
                with patch("time.sleep"):
                    success, msg = self.submitter.submit_application(
                        app_window="app_win",
                        main_window="main_win",
                        job_title="Software Engineer",
                        company="Global Tech",
                    )
                    self.assertTrue(success)
                    self.mock_captcha_handler.handle_captcha.assert_called()

    def test_submitter_halts_if_captcha_unresolved(self):
        self.mock_captcha_handler.is_captcha_present.return_value = True
        self.mock_captcha_handler.is_captcha_solved.return_value = False
        self.mock_captcha_handler.handle_captcha.return_value = False

        with patch("time.sleep"):
            success, msg = self.submitter.submit_application(
                app_window="app_win",
                main_window="main_win",
                job_title="Backend Developer",
                company="Startup Inc",
            )
            self.assertFalse(success)
            self.assertIn("CAPTCHA", msg)


class TestIndeedFormCaptchaIntegration(unittest.TestCase):
    """Tests that IndeedForm detects CAPTCHA as a form step."""

    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_driver.current_url = "https://smartapply.indeed.com/beta/indoorglobal"
        self.mock_driver.find_elements.return_value = []
        self.mock_browser = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_captcha_handler = MagicMock()
        self.form = IndeedForm(
            browser=self.mock_browser,
            captcha_handler=self.mock_captcha_handler,
        )

    def test_form_detects_captcha_step(self):
        with patch.object(self.form, "wait_for_spinner"):
            self.mock_driver.find_elements.return_value = []
            self.mock_captcha_handler.is_captcha_present.return_value = True
            self.mock_captcha_handler.is_captcha_solved.return_value = False
            step = self.form.detect_step_type()
            self.assertEqual(step, "CAPTCHA")

    def test_form_detects_contact_info_with_visible_inputs(self):
        with patch.object(self.form, "wait_for_spinner"):
            mock_input = MagicMock()
            mock_input.is_displayed.return_value = True
            def fe_side_effect(by, selector):
                if any(k in selector for k in ["firstName", "first-name", "phone"]):
                    return [mock_input]
                return []
            self.mock_driver.find_elements.side_effect = fe_side_effect
            step = self.form.detect_step_type()
            self.assertEqual(step, "CONTACT_INFO")

    def test_form_does_not_detect_captcha_when_app_inputs_exist(self):
        with patch.object(self.form, "wait_for_spinner"):
            # Mock find_elements to return an input when checking app inputs
            mock_input = MagicMock()
            mock_input.is_displayed.return_value = False  # Not displayed as contact input
            # First few calls return empty, but CSS selector check returns input
            def fe_side_effect(by, selector):
                if "input:not([type='hidden'])" in selector:
                    return [mock_input]
                return []
            self.mock_driver.find_elements.side_effect = fe_side_effect
            self.mock_captcha_handler.is_captcha_present.return_value = True
            self.mock_captcha_handler.is_captcha_solved.return_value = False
            step = self.form.detect_step_type()
            self.assertEqual(step, "QUESTIONS")


if __name__ == "__main__":
    unittest.main()
