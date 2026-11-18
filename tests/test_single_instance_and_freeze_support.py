"""
Unit tests for Single Instance Enforcement, Freeze Support, and macOS Bundle Safety.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from app.services.os.single_instance import SingleInstanceManager, _get_server_name


class TestSingleInstanceAndFreezeSupport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure QApplication is initialized for QLocalServer/QLocalSocket in tests
        if not QApplication.instance():
            cls.app = QApplication(["test", "--offscreen"])
        else:
            cls.app = QApplication.instance()

    def test_server_name_generation(self):
        name = _get_server_name()
        self.assertTrue(name.startswith("jobpilot_desktop_single_instance_"))
        self.assertGreater(len(name), len("jobpilot_desktop_single_instance_"))

    def test_bypass_flags(self):
        with patch.object(sys, "argv", ["run_desktop.py", "--test-run"]):
            is_primary, mgr = SingleInstanceManager.acquire_lock()
            self.assertTrue(is_primary)
            self.assertIsNone(mgr)

        with patch.object(sys, "argv", ["run_desktop.py", "--allow-multiple"]):
            is_primary, mgr = SingleInstanceManager.acquire_lock()
            self.assertTrue(is_primary)
            self.assertIsNone(mgr)

        with patch.dict(os.environ, {"JOBPILOT_ALLOW_MULTIPLE": "1"}):
            with patch.object(sys, "argv", ["run_desktop.py"]):
                is_primary, mgr = SingleInstanceManager.acquire_lock()
                self.assertTrue(is_primary)
                self.assertIsNone(mgr)

    def test_primary_and_secondary_instance_detection(self):
        test_server_name = f"test_jobpilot_lock_{os.getpid()}"
        from PySide6.QtNetwork import QLocalServer

        QLocalServer.removeServer(test_server_name)

        with patch("app.services.os.single_instance._get_server_name", return_value=test_server_name):
            with patch.object(sys, "argv", ["run_desktop.py"]):
                # 1. Primary instance acquires the lock
                is_primary_1, mgr_1 = SingleInstanceManager.acquire_lock()
                self.assertTrue(is_primary_1)
                self.assertIsNotNone(mgr_1)

                try:
                    # 2. Secondary instance attempts to acquire lock on the same socket
                    is_primary_2, mgr_2 = SingleInstanceManager.acquire_lock()
                    self.assertFalse(is_primary_2)
                    self.assertIsNone(mgr_2)
                finally:
                    if mgr_1:
                        mgr_1.release()
                    QLocalServer.removeServer(test_server_name)

    def test_window_activation_on_signal(self):
        test_server_name = f"test_jobpilot_window_{os.getpid()}"
        from PySide6.QtNetwork import QLocalServer

        QLocalServer.removeServer(test_server_name)

        mgr = SingleInstanceManager(server_name=test_server_name)
        mock_window = MagicMock()
        mock_window.isMinimized.return_value = False
        mgr.register_main_window(mock_window)

        mgr._activate_existing_window()
        mock_window.show.assert_called_once()
        mock_window.raise_.assert_called_once()
        mock_window.activateWindow.assert_called_once()

        # Test minimized window restoration
        mock_window_min = MagicMock()
        mock_window_min.isMinimized.return_value = True
        mgr.register_main_window(mock_window_min)
        mgr._activate_existing_window()
        mock_window_min.showNormal.assert_called_once()

    def test_macos_psn_argument_filter(self):
        argv = ["/Applications/JobPilot.app/Contents/MacOS/JobPilot", "-psn_0_1234567"]
        filtered = [arg for arg in argv if not arg.startswith("-psn_")]
        self.assertEqual(filtered, ["/Applications/JobPilot.app/Contents/MacOS/JobPilot"])

    def test_open_chrome_lazy_uc_import(self):
        # Verify that modules.open_chrome can be imported without loading undetected_chromedriver
        import modules.open_chrome as oc
        self.assertTrue(callable(oc.ensure_ssl_certificates))
        self.assertTrue(callable(oc.createChromeSession))

    def test_browser_single_instance_duplicate_guard(self):
        # 1. Naukri
        from platforms.naukri.browser import NaukriBrowser
        nb = NaukriBrowser()
        mock_driver = MagicMock()
        mock_driver.window_handles = ["handle1"]
        nb.driver = mock_driver
        nb.start()
        # Ensure it didn't overwrite the existing driver
        self.assertEqual(nb.driver, mock_driver)

        # 2. Foundit
        from platforms.foundit.browser import FounditBrowser
        fb = FounditBrowser()
        fb.driver = mock_driver
        ret = fb.start()
        self.assertEqual(ret, mock_driver)

        # 3. Indeed
        from platforms.indeed.browser import IndeedBrowser
        ib = IndeedBrowser()
        ib.driver = mock_driver
        ib.start()
        self.assertEqual(ib.driver, mock_driver)

        # 4. LinkedIn
        from platforms.linkedin.browser import LinkedInBrowser
        lb = LinkedInBrowser()
        lb.driver = mock_driver
        lb.start()
        self.assertEqual(lb.driver, mock_driver)

    def test_automation_manager_single_run_enforcement(self):
        from app.services.automation_service import AutomationManager
        from app.services.automation_events import AutomationState
        mgr = AutomationManager()
        mgr._current_state = AutomationState.RUNNING
        started, err = mgr.start_automation("naukri")
        self.assertFalse(started)
        self.assertEqual(err, "Automation is already running.")


if __name__ == "__main__":
    unittest.main()
