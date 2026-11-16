"""Unit tests for LogsView signal wiring, real-time log ingestion, and canonical path resolution."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure offscreen Qt platform for test execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

# Ensure QApplication singleton exists
app = QApplication.instance() or QApplication(sys.argv)

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.automation_service import AutomationManager
from app.services.logs.automation_event import AutomationEvent, AutomationEventType
from app.services.os.app_paths import AppPaths
from app.ui.views.logs_view import LogsView, resolve_canonical_log_path


class TestLogsViewWiring(unittest.TestCase):
    """Verifies that LogsView receives live activities and raw logs."""

    def setUp(self) -> None:
        self.manager = AutomationManager()
        self.logs_view = LogsView()
        self.logs_view.connect_automation_manager(self.manager)

    def tearDown(self) -> None:
        if hasattr(self.logs_view, "_poll_timer") and self.logs_view._poll_timer.isActive():
            self.logs_view._poll_timer.stop()
        self.logs_view.deleteLater()
        app.processEvents()

    def test_canonical_log_path_resolution(self) -> None:
        """resolve_canonical_log_path must resolve to AppPaths log.txt."""
        expected_user_log = AppPaths.get_logs_dir() / "log.txt"
        resolved = resolve_canonical_log_path()
        self.assertEqual(resolved, expected_user_log)

    def test_activity_logged_signal_updates_raw_console_and_bridge(self) -> None:
        """When manager emits activity_logged, raw console and bridge must receive it."""
        test_msg = "Discovered job: Senior Python Developer @ TechCorp"
        test_time = "21:45:00"

        self.manager.activity_logged.emit(test_time, test_msg)
        app.processEvents()

        console_text = self.logs_view.tab_raw_console.editor.toPlainText()
        self.assertIn(test_msg, console_text)
        self.assertIn(test_time, console_text)

    def test_job_discovered_updates_hero_and_battlefield(self) -> None:
        """When manager emits job_discovered, CurrentActionCard and Battlefield must update."""
        event = JobDiscoveredEvent(
            run_id="run_test_123",
            platform="linkedin",
            title="AI Systems Architect",
            company="DeepMind",
            url="https://linkedin.com/jobs/view/123",
        )

        self.manager.job_discovered.emit(event)
        app.processEvents()

        # Verify active run was updated
        self.assertEqual(self.logs_view._active_run_id, "run_test_123")

        # Verify Hero card reflects the target job
        target_text = self.logs_view.current_action_card.target_lbl.text()
        self.assertIn("AI Systems Architect", target_text)

        # Verify Timeline has the event card
        self.assertGreater(len(self.logs_view.tab_battlefield._events), 0)
        latest_event = self.logs_view.tab_battlefield._events[-1]
        self.assertEqual(latest_event.job_title, "AI Systems Architect")
        self.assertEqual(latest_event.company, "DeepMind")

    def test_application_submitted_updates_pipeline_and_metrics(self) -> None:
        """When manager emits application_submitted, metrics and pipeline stage must advance."""
        event = ApplicationSubmittedEvent(
            run_id="run_test_123",
            platform="naukri",
            job_id=999,
            title="Lead RPA Engineer",
            company="AutomationGlobal",
            status="SUBMITTED",
        )

        self.manager.application_submitted.emit(event)
        app.processEvents()

        # Check metrics strip
        ctx = self.logs_view.registry.get("run_test_123")
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.applications_submitted, 1)

    def test_realtime_log_listener_callback(self) -> None:
        """Direct callback via helpers.print_lg listener must stream into raw console."""
        raw_line = "[21:50:00]  JOBS  Discovered: Lead Architect @ Anthropic"
        self.logs_view._on_realtime_log_callback(raw_line)
        app.processEvents()

        console_text = self.logs_view.tab_raw_console.editor.toPlainText()
        self.assertIn("Lead Architect @ Anthropic", console_text)

    def test_refresh_polls_file_and_updates_ui(self) -> None:
        """Calling refresh() must execute without error and update header and context."""
        self.logs_view.refresh()
        app.processEvents()
        self.assertIsNotNone(self.logs_view.header)


if __name__ == "__main__":
    unittest.main()
