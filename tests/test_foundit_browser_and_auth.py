'''
Unit Tests for Foundit Browser & Authentication Flow
'''

import unittest
from unittest.mock import MagicMock, patch
from platforms.foundit.browser import FounditBrowser
from platforms.foundit.auth import FounditAuth
from selenium.webdriver.common.by import By


class TestFounditBrowserAndAuth(unittest.TestCase):

    def test_default_profile_directory(self):
        browser = FounditBrowser()
        self.assertIn(".jobpilot-foundit-profile", browser.profile_dir)

    def test_check_session_state_logged_in(self):
        browser = FounditBrowser()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.foundit.in/seeker/dashboard"
        mock_driver.find_elements.return_value = []
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGGED_IN")
        self.assertTrue(browser.is_logged_in())

    def test_check_session_state_with_cookies(self):
        browser = FounditBrowser()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.foundit.in/"
        mock_driver.get_cookies.return_value = [
            {"name": "IS_LOGGED_IN", "value": "true"},
            {"name": "MSSOAT", "value": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid_session_token"},
        ]
        mock_driver.find_elements.return_value = []
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGGED_IN")
        self.assertTrue(browser.is_logged_in())

    def test_check_session_state_login_required(self):
        browser = FounditBrowser()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.foundit.in/"

        login_btn = MagicMock()
        login_btn.is_displayed.return_value = True

        def mock_find_elements(by, value):
            if "Login" in value:
                return [login_btn]
            return []

        mock_driver.find_elements.side_effect = mock_find_elements
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "LOGIN_REQUIRED")
        self.assertFalse(browser.is_logged_in())

    def test_check_session_state_captcha(self):
        browser = FounditBrowser()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.foundit.in/"

        cf_elem = MagicMock()
        cf_elem.is_displayed.return_value = True

        def mock_find_elements(by, value):
            if "challenges.cloudflare.com" in value:
                return [cf_elem]
            return []

        mock_driver.find_elements.side_effect = mock_find_elements
        browser.driver = mock_driver

        state = browser.check_session_state()
        self.assertEqual(state, "CAPTCHA")

    def test_auth_already_logged_in(self):
        browser = MagicMock()
        browser.check_session_state.return_value = "LOGGED_IN"
        browser.driver = MagicMock()

        auth = FounditAuth(browser)
        success, msg = auth.login("test@example.com", "secret")
        self.assertTrue(success)
        self.assertIn("Already logged in", msg)

    def test_auth_handles_challenge(self):
        browser = MagicMock()
        browser.check_session_state.return_value = "CAPTCHA"
        browser.driver = MagicMock()

        auth = FounditAuth(browser)
        success, msg = auth.login("test@example.com", "secret")
        self.assertFalse(success)
        self.assertIn("Manual intervention required", msg)


if __name__ == "__main__":
    unittest.main()
