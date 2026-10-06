'''
Comprehensive Test Suite for Humanoid Behavior, Stealth, and Multi-Platform CAPTCHA Detection
Validates:
- modules.human_behavior (delays, typing cadence, human clicks, review dwell)
- modules.stealth (CDP script injection and fallback safety)
- modules.captcha_detector (detection, token solved checks, cooperative HITL loops across Naukri, Foundit, LinkedIn, Indeed)
'''

import unittest
from unittest.mock import MagicMock, patch, call

from modules.human_behavior import (
    human_delay,
    human_type,
    human_click,
    human_review_dwell,
)
from modules.stealth import apply_stealth_to_driver, STEALTH_CDP_SCRIPT
from modules.captcha_detector import CaptchaDetector
from app.services.automation_events import InterventionType, AutomationInterventionEvent


class TestHumanBehavior(unittest.TestCase):
    """Unit tests for humanoid interaction timing and typing cadence."""

    def test_human_delay_testing_override(self):
        delay = human_delay(min_s=1.0, max_s=2.0, testing_override=0.002)
        self.assertAlmostEqual(delay, 0.002)

    def test_human_delay_actions(self):
        with patch("modules.human_behavior._is_testing", return_value=False):
            with patch("time.sleep"):
                d_key = human_delay(action="keystroke")
                self.assertGreaterEqual(d_key, 0.035)
                self.assertLessEqual(d_key, 0.110)

                d_click = human_delay(action="click")
                self.assertGreaterEqual(d_click, 0.50)
                self.assertLessEqual(d_click, 1.25)

                d_rev = human_delay(action="review")
                self.assertGreaterEqual(d_rev, 1.50)
                self.assertLessEqual(d_rev, 3.20)

    def test_human_type_testing_mode(self):
        mock_elem = MagicMock()
        mock_driver = MagicMock()
        success = human_type(mock_elem, "Senior Developer", clear_first=True, driver=mock_driver)
        self.assertTrue(success)
        mock_elem.clear.assert_called()
        mock_elem.send_keys.assert_called_with("Senior Developer")
        mock_driver.execute_script.assert_called()

    def test_human_type_cadence(self):
        mock_elem = MagicMock()
        mock_driver = MagicMock()
        with patch("modules.human_behavior._is_testing", return_value=False):
            with patch("time.sleep") as mock_sleep:
                success = human_type(mock_elem, "Hi!", clear_first=True, driver=mock_driver)
                self.assertTrue(success)
                # Verify send_keys was called for 'H', 'i', '!'
                calls = [c[0][0] for c in mock_elem.send_keys.call_args_list if c[0] and len(c[0][0]) == 1]
                self.assertIn("H", calls)
                self.assertIn("i", calls)
                self.assertIn("!", calls)
                self.assertGreater(mock_sleep.call_count, 2)

    def test_human_click_smooth_scroll(self):
        mock_elem = MagicMock()
        mock_driver = MagicMock()
        success = human_click(mock_driver, mock_elem, smooth_scroll=True, dwell_before=False)
        self.assertTrue(success)
        mock_driver.execute_script.assert_called()
        mock_elem.click.assert_called_once()

    def test_human_click_fallback_to_js(self):
        mock_elem = MagicMock()
        mock_elem.click.side_effect = Exception("ElementClickIntercepted")
        mock_driver = MagicMock()
        success = human_click(mock_driver, mock_elem, smooth_scroll=False, dwell_before=False)
        self.assertTrue(success)
        # Verify fallback JS click executed
        js_calls = [c[0][0] for c in mock_driver.execute_script.call_args_list]
        self.assertTrue(any("arguments[0].click()" in s for s in js_calls))

    def test_human_review_dwell(self):
        mock_driver = MagicMock()
        with patch("modules.human_behavior._is_testing", return_value=False):
            with patch("time.sleep"):
                human_review_dwell(mock_driver, min_s=0.1, max_s=0.2)
                # Verify micro-scrolling up and down
                js_calls = [c[0][0] for c in mock_driver.execute_script.call_args_list]
                self.assertTrue(any("scrollBy" in s for s in js_calls))

    def test_cycle_sleep_testing_mode(self):
        from modules.human_behavior import cycle_sleep
        # Should return True instantly in test environment
        res = cycle_sleep(duration_minutes=10, platform_name="linkedin")
        self.assertTrue(res)

    def test_cycle_sleep_zero_duration(self):
        from modules.human_behavior import cycle_sleep
        with patch("modules.human_behavior._is_testing", return_value=False):
            res = cycle_sleep(duration_minutes=0, platform_name="naukri")
            self.assertTrue(res)

    def test_cycle_sleep_interruptible_by_stop_check(self):
        from modules.human_behavior import cycle_sleep
        with patch("modules.human_behavior._is_testing", return_value=False):
            with patch("time.sleep"):
                # Simulate stop requested immediately
                res = cycle_sleep(duration_minutes=5, platform_name="foundit", stop_check=lambda: True)
                self.assertFalse(res)

    def test_cycle_sleep_countdown_completion(self):
        from modules.human_behavior import cycle_sleep
        logged = []
        with patch("modules.human_behavior._is_testing", return_value=False):
            with patch("time.sleep"):
                res = cycle_sleep(
                    duration_minutes=0.05,
                    platform_name="indeed",
                    stop_check=lambda: False,
                    log_callback=lambda m: logged.append(m),
                    step_s=1.0,
                )
                self.assertTrue(res)
                self.assertTrue(any("Entering Sleeping Mode" in m for m in logged))
                self.assertTrue(any("completed" in m.lower() for m in logged))

    def test_platform_sleep_duration_configs(self):
        from modules.config_loader import get_platform
        for plat in ["linkedin", "naukri", "indeed", "foundit"]:
            cfg = get_platform(plat)
            self.assertIn("sleep_duration_minutes", cfg)
            self.assertGreaterEqual(cfg["sleep_duration_minutes"], 0)


class TestStealthInjection(unittest.TestCase):
    """Unit tests for Chrome DevTools Protocol anti-bot masking."""

    def test_apply_stealth_with_cdp(self):
        mock_driver = MagicMock()
        mock_driver.execute_cdp_cmd.return_value = {"identifier": "1"}
        applied = apply_stealth_to_driver(mock_driver)
        self.assertTrue(applied)
        mock_driver.execute_cdp_cmd.assert_called_once_with(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": STEALTH_CDP_SCRIPT}
        )

    def test_apply_stealth_fallback_to_execute_script(self):
        mock_driver = MagicMock(spec=["execute_script"])
        applied = apply_stealth_to_driver(mock_driver)
        self.assertTrue(applied)
        mock_driver.execute_script.assert_called_once()

    def test_apply_stealth_none_driver(self):
        self.assertFalse(apply_stealth_to_driver(None))


class TestCaptchaDetector(unittest.TestCase):
    """Unit tests for cross-platform CAPTCHA and checkpoint detection."""

    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_bridge = MagicMock()
        self.detector = CaptchaDetector(platform="generic", automation_bridge=self.mock_bridge)

    def test_is_captcha_present_js_positive(self):
        self.mock_driver.execute_script.return_value = {"present": True, "type": "Cloudflare Turnstile"}
        present, desc = self.detector.is_captcha_present(self.mock_driver)
        self.assertTrue(present)
        self.assertEqual(desc, "Cloudflare Turnstile")

    def test_is_captcha_present_linkedin_checkpoint_url(self):
        self.mock_driver.execute_script.return_value = {"present": False}
        self.mock_driver.current_url = "https://www.linkedin.com/checkpoint/challenge/12345"
        present, desc = self.detector.is_captcha_present(self.mock_driver, platform="linkedin")
        self.assertTrue(present)
        self.assertIn("LinkedIn", desc)

    def test_is_captcha_present_naukri_dom_fallback(self):
        self.mock_driver.execute_script.return_value = {"present": False}
        self.mock_driver.current_url = "https://www.naukri.com/apply"
        mock_captcha_div = MagicMock()
        mock_captcha_div.is_displayed.return_value = True
        mock_captcha_div.size = {"width": 300, "height": 80}
        self.mock_driver.find_elements.return_value = [mock_captcha_div]

        present, desc = self.detector.is_captcha_present(self.mock_driver, platform="naukri")
        self.assertTrue(present)
        self.assertIn("captcha", desc.lower())

    def test_is_captcha_present_foundit_dom_fallback(self):
        self.mock_driver.execute_script.return_value = {"present": False}
        self.mock_driver.current_url = "https://www.foundit.in/job/123"
        mock_cf = MagicMock()
        mock_cf.is_displayed.return_value = True
        mock_cf.size = {"width": 150, "height": 60}
        self.mock_driver.find_elements.return_value = [mock_cf]

        present, desc = self.detector.is_captcha_present(self.mock_driver, platform="foundit")
        self.assertTrue(present)

    def test_is_captcha_solved_when_challenge_gone(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(False, "")):
            self.assertTrue(self.detector.is_captcha_solved(self.mock_driver))

    def test_is_captcha_solved_via_token(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "reCAPTCHA")):
            self.mock_driver.execute_script.return_value = True
            self.assertTrue(self.detector.is_captcha_solved(self.mock_driver))

    def test_is_captcha_solved_linkedin_redirect(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "LinkedIn Challenge")):
            self.mock_driver.current_url = "https://www.linkedin.com/jobs/search/"
            self.mock_driver.execute_script.return_value = False
            self.assertTrue(self.detector.is_captcha_solved(self.mock_driver, platform="linkedin"))

    def test_handle_captcha_returns_true_if_not_present(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(False, "")):
            res = self.detector.handle_captcha(self.mock_driver, platform="naukri")
            self.assertTrue(res)

    def test_handle_captcha_emits_intervention_event(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "Cloudflare Challenge")):
            with patch.object(self.detector, "is_captcha_solved", side_effect=[False, True]):
                with patch("time.sleep"):
                    res = self.detector.handle_captcha(
                        self.mock_driver,
                        platform="foundit",
                        job_title="Full Stack Engineer",
                        company="Tech Solutions",
                        timeout=5,
                        automation_bridge=self.mock_bridge,
                    )
                    self.assertTrue(res)
                    self.mock_bridge.handle_intervention.assert_called_once()
                    event = self.mock_bridge.handle_intervention.call_args[0][0]
                    self.assertEqual(event.intervention_type, InterventionType.CAPTCHA_DETECTED)
                    self.assertEqual(event.platform, "foundit")

    def test_handle_captcha_emits_2fa_for_linkedin(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "LinkedIn Security Checkpoint / 2FA")):
            with patch.object(self.detector, "is_captcha_solved", side_effect=[False, True]):
                with patch("time.sleep"):
                    res = self.detector.handle_captcha(
                        self.mock_driver,
                        platform="linkedin",
                        job_title="Data Scientist",
                        company="LinkedIn Corp",
                        timeout=5,
                        automation_bridge=self.mock_bridge,
                    )
                    self.assertTrue(res)
                    event = self.mock_bridge.handle_intervention.call_args[0][0]
                    self.assertEqual(event.intervention_type, InterventionType.TWO_FACTOR_AUTH)

    def test_handle_captcha_stops_on_stop_check(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "reCAPTCHA")):
            with patch.object(self.detector, "is_captcha_solved", return_value=False):
                stop_check = MagicMock(return_value=True)
                res = self.detector.handle_captcha(
                    self.mock_driver,
                    platform="naukri",
                    timeout=10,
                    stop_check=stop_check,
                )
                self.assertFalse(res)

    def test_handle_captcha_times_out(self):
        with patch.object(self.detector, "is_captcha_present", return_value=(True, "reCAPTCHA")):
            with patch.object(self.detector, "is_captcha_solved", return_value=False):
                with patch("time.sleep"):
                    res = self.detector.handle_captcha(
                        self.mock_driver,
                        platform="naukri",
                        timeout=0,
                    )
                    self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
