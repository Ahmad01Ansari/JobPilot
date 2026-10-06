'''
Unit Tests for GlassdoorBrowser (Phase C)
Validates profile directory isolation, lock cleanup, stealth settings, and overlay dismissal.
'''

import os
import unittest
from unittest.mock import MagicMock, patch

from platforms.glassdoor.browser import (
    GlassdoorBrowser,
    get_default_glassdoor_profile_dir,
    DEFAULT_GLASSDOOR_PROFILE_DIR,
)


class TestGlassdoorBrowser(unittest.TestCase):
    def test_default_profile_dir(self):
        expected = os.path.expanduser("~/.jobpilot-glassdoor-profile")
        self.assertEqual(get_default_glassdoor_profile_dir(), expected)
        self.assertEqual(DEFAULT_GLASSDOOR_PROFILE_DIR, expected)

    @patch("modules.browser_lock.cleanup_stale_profile_locks")
    @patch("platforms.glassdoor.browser.uc.Chrome")
    @patch("platforms.glassdoor.browser.apply_stealth_to_driver")
    def test_browser_start_and_close(self, mock_stealth, mock_uc, mock_cleanup):
        mock_driver = MagicMock()
        mock_uc.return_value = mock_driver

        browser = GlassdoorBrowser(headless=True, stealth=True)
        drv = browser.start()

        self.assertIsNotNone(drv)
        mock_cleanup.assert_called()
        mock_stealth.assert_called_once_with(mock_driver)

        browser.close()
        mock_driver.quit.assert_called_once()
        self.assertIsNone(browser.driver)

    def test_is_logged_in_detected(self):
        mock_driver = MagicMock()
        mock_elem = MagicMock()
        mock_elem.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_elem]

        browser = GlassdoorBrowser()
        browser.driver = mock_driver

        self.assertTrue(browser.is_logged_in())

    def test_is_logged_in_not_detected(self):
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []

        browser = GlassdoorBrowser()
        browser.driver = mock_driver

        self.assertFalse(browser.is_logged_in())

    def test_dismiss_overlays(self):
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True

        # First selector matches 1 displayed button, rest return empty
        mock_driver.find_elements.side_effect = [[mock_btn]] + [[] for _ in range(50)]

        browser = GlassdoorBrowser()
        browser.driver = mock_driver

        count = browser.dismiss_overlays()
        self.assertEqual(count, 1)
        mock_btn.click.assert_called_once()


if __name__ == "__main__":
    unittest.main()
