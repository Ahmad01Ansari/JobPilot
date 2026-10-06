"""PySide6 offscreen test suite verifying LogsView (Automation Mission Control)."""

import os
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"
_app = QApplication.instance() or QApplication([])

from app.services.logs.automation_event import AutomationEvent, AutomationEventType, EventSource
from app.ui.state import AppState
from app.ui.views.logs_view import LogsView


class TestLogsMissionControlUI(unittest.TestCase):
    """Verifies that LogsView instantiates, renders tabs, and updates upon events."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from pathlib import Path
        self.dummy_log = Path("/tmp/test_mission_control_empty.txt")
        if self.dummy_log.exists():
            self.dummy_log.unlink()
        self.view = LogsView(log_file_path=self.dummy_log)
        self.state = AppState()
        self.view.set_app_state(self.state)
        self.view.show()

    def tearDown(self):
        if hasattr(self, "dummy_log") and self.dummy_log.exists():
            self.dummy_log.unlink()
        self.view.hide()
        self.view.deleteLater()

    def test_initial_state(self):
        # Verify 5 tabs exist
        self.assertEqual(self.view.tabs.count(), 5)
        self.assertEqual(self.view.tabs.tabText(0), "Live Battlefield")
        self.assertEqual(self.view.tabs.tabText(1), "Run History & Funnel")
        self.assertEqual(self.view.tabs.tabText(2), "Error & Incident Center")
        self.assertEqual(self.view.tabs.tabText(3), "Raw Console")
        self.assertEqual(self.view.tabs.tabText(4), "System Diagnostics")

        # Initial metrics should be 0
        self.assertEqual(self.view.status_strip.card_discovered._value, 0)
        self.assertEqual(self.view.status_strip.card_applied._value, 0)

    def test_live_event_updates_ui(self):
        # 1. Job Discovered
        e1 = AutomationEvent(
            run_id="run-test-ui",
            platform="naukri",
            event_type=AutomationEventType.JOB_DISCOVERED,
            stage="DISCOVER",
            action="Found 12 matching listings",
            metadata={"count": 12},
        )
        self.view.bridge.event_emitted.emit(e1)

        # Assert metrics updated
        self.assertEqual(self.view.status_strip.card_discovered._value, 12)
        self.assertEqual(self.view.current_action_card.platform_lbl.text(), "Naukri")
        self.assertEqual(self.view.current_action_card.action_lbl.text(), "Found 12 matching listings")

        # 2. Application Submitted
        e2 = AutomationEvent(
            run_id="run-test-ui",
            platform="naukri",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            stage="SUBMISSION",
            job_title="Lead Python Engineer",
            company="Tech Corp",
            action="Submitted Easy Apply form successfully",
        )
        self.view.bridge.event_emitted.emit(e2)

        self.assertEqual(self.view.status_strip.card_applied._value, 1)
        self.assertIn("Lead Python Engineer", self.view.current_action_card.target_lbl.text())

    def test_intervention_event_updates_error_tab(self):
        e_captcha = AutomationEvent(
            run_id="run-test-ui",
            platform="naukri",
            event_type=AutomationEventType.CAPTCHA_DETECTED,
            stage="APPLICATION",
            message="Please solve the slide challenge",
        )
        self.view.bridge.event_emitted.emit(e_captcha)

        # Tab text should reflect active intervention
        self.assertIn("Error Center (1)", self.view.tabs.tabText(2))
        self.assertTrue(self.view.tab_errors.idle_card.isHidden())

        # Resolve intervention
        self.view._on_intervention_resolved(e_captcha.event_id)
        self.assertFalse(self.view.tab_errors.idle_card.isHidden())
        self.assertEqual(self.view.tabs.tabText(2), "Error & Incident Center")

    def test_deep_link_navigation(self):
        # Test deep link signal triggers AppState navigation
        self.view._on_open_job(42)
        self.assertEqual(self.state.current_page_id, "jobs")

        self.view._on_open_application(108)
        self.assertEqual(self.state.current_page_id, "applications")


if __name__ == "__main__":
    unittest.main()
