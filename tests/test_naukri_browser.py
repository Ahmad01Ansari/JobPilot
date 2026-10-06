import unittest
from unittest.mock import MagicMock, patch
import os

from platforms.naukri.browser import NaukriBrowser, DEFAULT_NAUKRI_PROFILE_DIR
from platforms.naukri.selectors import (
    LOGIN_URL,
    HOME_URL,
    CAPTCHA_SELECTORS,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
)


class TestNaukriBrowser(unittest.TestCase):
    def test_profile_directory_isolation(self):
        # Must use dedicated ~/.jobpilot-naukri-profile (with legacy fallback), isolated from LinkedIn
        expected_profile = os.path.expanduser("~/.jobpilot-naukri-profile")
        legacy_profile = os.path.expanduser("~/.apply-and-pray-naukri-profile")
        expected = legacy_profile if os.path.exists(legacy_profile) and not os.path.exists(expected_profile) else expected_profile
        self.assertEqual(DEFAULT_NAUKRI_PROFILE_DIR, expected)

        browser = NaukriBrowser()
        self.assertEqual(browser.profile_dir, expected)

        custom_browser = NaukriBrowser(profile_dir="/tmp/test-profile")
        self.assertEqual(custom_browser.profile_dir, "/tmp/test-profile")

    def test_session_state_not_started(self):
        browser = NaukriBrowser()
        self.assertEqual(browser.check_session_state(), "UNKNOWN")

    def test_session_state_captcha_detected(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector == CAPTCHA_SELECTORS[0]:
                return [mock_elem]
            return []

        mock_driver.find_elements.side_effect = find_elements
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "CAPTCHA")

    def test_session_state_logged_in_detected(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS:
                return []
            if selector in LOGGED_IN_SELECTORS:
                return [mock_elem]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_driver.current_url = "https://www.naukri.com/mnjuser/homepage"
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGGED_IN")

    def test_session_state_login_required_detected(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS or selector in LOGGED_IN_SELECTORS:
                return []
            if selector in LOGIN_REQUIRED_SELECTORS:
                return [mock_elem]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_driver.current_url = LOGIN_URL
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGIN_REQUIRED")

    def test_session_state_unauthenticated_header_login_button_detected(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            # When looking for login button in header via XPath or selector
            if "login_Layer" in selector or "Login" in selector:
                return [mock_elem]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_driver.current_url = "https://www.naukri.com/rpa-developer-jobs-in-india"
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGIN_REQUIRED")
        self.assertFalse(browser.is_logged_in())

    def test_session_state_mnjuser_url_returns_logged_in(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []
        # URL has mnjuser — this path is only accessible when authenticated
        mock_driver.current_url = "https://www.naukri.com/mnjuser/homepage"
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGGED_IN")
        self.assertTrue(browser.is_logged_in())

    def test_login_detects_error_message(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        mock_user = MagicMock()
        mock_pwd = MagicMock()
        mock_sub = MagicMock()
        mock_err = MagicMock()
        mock_err.is_displayed.return_value = True
        mock_err.text = "Invalid details"

        def find_elements(by, selector):
            if "username" in selector.lower():
                return [mock_user]
            if "password" in selector.lower():
                return [mock_pwd]
            if "submit" in selector.lower() or "button" in selector.lower():
                return [mock_sub]
            if "server-err" in selector or "err" in selector:
                return [mock_err]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_driver.current_url = LOGIN_URL
        browser.driver = mock_driver

        success, msg = browser.login("test@example.com", "wrongpwd", timeout=2)
        self.assertFalse(success)
        self.assertIn("Invalid details", msg)

    def test_close_cleans_up_state(self):
        browser = NaukriBrowser()
        mock_driver = MagicMock()
        browser.driver = mock_driver
        browser.wait = MagicMock()
        browser.actions = MagicMock()

        browser.close()
        mock_driver.quit.assert_called_once()
        self.assertIsNone(browser.driver)
        self.assertIsNone(browser.wait)
        self.assertIsNone(browser.actions)


if __name__ == "__main__":
    unittest.main()
