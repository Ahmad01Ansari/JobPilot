"""Unit & contract tests for the redesigned Automation Control Center UI."""

import os
import sys
import time
import unittest
from datetime import datetime, timezone

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QTextEdit, QComboBox, QFrame

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationRunResult,
    AutomationState,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.automation_service import AutomationManager
from app.ui.theme import ThemeManager
from app.ui.views.automation_view import AutomationView
from app.ui.widgets.automation.state import AutomationUIState


class TestAutomationUIContracts(unittest.TestCase):
    """Tests contract preservation, state management, and theme switching for AutomationView."""

    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv + ["-platform", "offscreen"])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.manager = AutomationManager()
        self.view = AutomationView(automation_manager=self.manager)
        self.view.show()

    def tearDown(self):
        self.view.close()

    def test_legacy_public_attributes_preserved(self):
        """Verifies every legacy public attribute required by callers and tests exists with expected types."""
        # Badges and buttons
        self.assertIsInstance(self.view.badge_status, QLabel)
        self.assertIsInstance(self.view.btn_start, QPushButton)
        self.assertIsInstance(self.view.btn_stop, QPushButton)
        self.assertIsInstance(self.view.btn_pause, QPushButton)
        self.assertIsInstance(self.view.combo_platform, QComboBox)

        # Metrics labels
        self.assertIsInstance(self.view.val_discovered, QLabel)
        self.assertIsInstance(self.view.val_evaluated, QLabel)
        self.assertIsInstance(self.view.val_qualified, QLabel)
        self.assertIsInstance(self.view.val_applied, QLabel)
        self.assertIsInstance(self.view.val_skipped, QLabel)
        self.assertIsInstance(self.view.val_errors, QLabel)

        # Activity stream & intervention banner
        self.assertIsInstance(self.view.activity_stream, QTextEdit)
        self.assertIsInstance(self.view.btn_clear_stream, QPushButton)
        self.assertIsInstance(self.view.intervention_card, QFrame)
        self.assertIsInstance(self.view.lbl_intervention, QLabel)
        self.assertIsInstance(self.view.btn_dismiss_intervention, QPushButton)

    def test_idle_state_contains_no_fake_metrics(self):
        """Guarantees that when idle, counters strictly display real zeros and no fake numbers."""
        self.assertEqual(self.view.val_discovered.text(), "0")
        self.assertEqual(self.view.val_evaluated.text(), "0")
        self.assertEqual(self.view.val_qualified.text(), "0")
        self.assertEqual(self.view.val_applied.text(), "0")
        self.assertEqual(self.view.val_skipped.text(), "0")
        self.assertEqual(self.view.val_errors.text(), "0")

        self.assertEqual(self.view.badge_status.text(), "IDLE")
        self.assertTrue(self.view.btn_start.isEnabled())
        self.assertFalse(self.view.btn_stop.isEnabled())
        self.assertFalse(self.view.intervention_banner.isVisible())
        self.assertEqual(self.view.current_job_card.lbl_title.text(), "No active job")

    def test_dark_and_light_theme_tokens(self):
        """Verifies theme notification cleanly switches both dark and light palettes without exception."""
        # Switch to light
        ThemeManager.notify_listeners("light")
        QTest.qWait(20)
        self.assertEqual(self.view.badge_status.text(), "IDLE")

        # Switch to dark
        ThemeManager.notify_listeners("dark")
        QTest.qWait(20)
        self.assertEqual(self.view.badge_status.text(), "IDLE")

    def test_monotonic_stopwatch(self):
        """Verifies elapsed runtime calculation uses monotonic clock (drift-free)."""
        state = AutomationUIState()
        state.start_monotonic = time.monotonic() - 65.0  # 1 min 5 sec ago
        self.assertGreaterEqual(state.elapsed_seconds(), 64.9)
        self.assertEqual(state.formatted_elapsed_time(), "01:05")

        # Stopped state
        state.finish_monotonic = state.start_monotonic + 122.0
        self.assertEqual(state.formatted_elapsed_time(), "02:02")

    def test_current_job_handles_missing_optional_fields(self):
        """Verifies current job card safely renders when url/location are missing."""
        disc_event = JobDiscoveredEvent(
            run_id="test-run-1",
            platform="linkedin",
            title="Senior Automation Engineer",
            company="Tech Corp",
            location=None,
            url=None,
        )
        self.view._on_job_discovered(disc_event)
        self.assertEqual(self.view.current_job_card.lbl_title.text(), "Senior Automation Engineer")
        self.assertEqual(self.view.current_job_card.lbl_company.text(), "Tech Corp")
        self.assertFalse(self.view.current_job_card.lbl_location.isVisible())
        self.assertFalse(self.view.current_job_card.btn_open_job.isEnabled())

        # Now update with location and URL
        disc_event_full = JobDiscoveredEvent(
            run_id="test-run-1",
            platform="linkedin",
            title="Senior Automation Engineer",
            company="Tech Corp",
            location="Bangalore, India",
            url="https://www.linkedin.com/jobs/view/12345",
        )
        self.view._on_job_discovered(disc_event_full)
        self.assertTrue(self.view.current_job_card.lbl_location.isVisible())
        self.assertEqual(self.view.current_job_card.lbl_location.text(), "Location: Bangalore, India")
        self.assertTrue(self.view.current_job_card.btn_open_job.isEnabled())

    def test_state_transitions(self):
        """Verifies complete lifecycle state transitions reflect correctly in UI."""
        # STARTING
        self.view._on_state_changed("run-1", "STARTING")
        self.assertEqual(self.view.badge_status.text(), "STARTING")
        self.assertFalse(self.view.btn_start.isEnabled())
        self.assertTrue(self.view.btn_stop.isEnabled())

        # RUNNING
        self.view._on_state_changed("run-1", "RUNNING")
        self.assertEqual(self.view.badge_status.text(), "RUNNING")
        self.assertFalse(self.view.btn_start.isEnabled())
        self.assertTrue(self.view.btn_stop.isEnabled())

        # Progress update
        progress = AutomationProgressEvent(
            run_id="run-1",
            platform="linkedin",
            current_term="RPA Developer",
            current_job="RPA Engineer @ GlobalTech",
            jobs_discovered=10,
            jobs_evaluated=8,
            jobs_qualified=5,
            jobs_skipped=3,
            applications_submitted=4,
            errors_count=0,
        )
        self.view._on_progress_updated(progress)
        self.assertEqual(self.view.val_discovered.text(), "10")
        self.assertEqual(self.view.val_evaluated.text(), "8")
        self.assertEqual(self.view.val_qualified.text(), "5")
        self.assertEqual(self.view.val_applied.text(), "4")
        self.assertEqual(self.view.val_skipped.text(), "3")
        self.assertEqual(self.view.val_errors.text(), "0")

        # COMPLETED
        now = datetime.now(timezone.utc)
        result = AutomationRunResult(
            run_id="run-1",
            platform="linkedin",
            status=AutomationState.COMPLETED,
            started_at=now,
            finished_at=now,
            jobs_discovered=10,
            jobs_evaluated=8,
            jobs_qualified=5,
            jobs_skipped=3,
            applications_submitted=4,
            errors_count=0,
        )
        self.view._on_run_finished(result)
        self.view._on_state_changed("run-1", "COMPLETED")
        self.assertEqual(self.view.badge_status.text(), "COMPLETED")
        self.assertTrue(self.view.btn_start.isEnabled())
        self.assertFalse(self.view.btn_stop.isEnabled())

    def test_intervention_banner_display_and_dismiss(self):
        """Verifies manual intervention banner appears with message and hides upon dismiss."""
        int_event = AutomationInterventionEvent(
            run_id="run-1",
            platform="linkedin",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="CAPTCHA challenge detected. Please solve in browser.",
        )
        self.view._on_intervention_required(int_event)
        self.assertTrue(self.view.intervention_banner.isVisible())
        self.assertIn("CAPTCHA_DETECTED", self.view.lbl_intervention.text())

        # Dismiss notice
        self.view.btn_dismiss_intervention.click()
        self.assertFalse(self.view.intervention_banner.isVisible())

    def test_pause_resume_button_state_transitions(self):
        """Verifies btn_pause enables and switches text between '⏸ Pause' and '▶ Resume'."""
        # When IDLE, pause button is disabled
        self.view._update_state_ui("IDLE")
        self.assertFalse(self.view.btn_pause.isEnabled())
        self.assertIn("Pause", self.view.btn_pause.text())

        # When RUNNING, pause button is enabled with 'Pause'
        self.view._update_state_ui("RUNNING")
        self.assertTrue(self.view.btn_pause.isEnabled())
        self.assertIn("Pause", self.view.btn_pause.text())

        # When PAUSED, pause button is enabled with 'Resume'
        self.view._update_state_ui("PAUSED")
        self.assertTrue(self.view.btn_pause.isEnabled())
        self.assertIn("Resume", self.view.btn_pause.text())

        # When COMPLETED, pause button is disabled
        self.view._update_state_ui("COMPLETED")
        self.assertFalse(self.view.btn_pause.isEnabled())

    def test_platform_selector_switching(self):
        """Verifies selecting each platform in segmented control updates canonical state and combo."""
        platforms = ["linkedin", "naukri", "indeed", "foundit", "all"]
        for p in platforms:
            self.view.platform_selector.select_platform(p)
            self.assertEqual(self.view.platform_selector.current_platform(), p)
            self.assertEqual(self.view.combo_platform.currentData(), p)

        # External change via combo_platform updates segmented control
        self.view.combo_platform.setCurrentIndex(1)  # naukri
        self.assertEqual(self.view.platform_selector.current_platform(), "naukri")

    def test_dual_mode_activity_stream(self):
        """Verifies activity feed captures events, filters categories, and toggles to raw logs."""
        stream = self.view.live_activity_stream
        stream.clear()

        # Log different event types
        stream.log_activity("10:00:01", "Job Discovered: Python Engineer @ Corp")
        stream.log_activity("10:00:02", "Qualified: Python Engineer @ Corp")
        stream.log_activity("10:00:03", "Application Submitted: Python Engineer @ Corp")
        stream.log_activity("10:00:04", "Error: Connection timeout")

        # In Activity Feed mode
        self.assertIn("JOBS", stream.toPlainText())
        self.assertIn("SUBMISSIONS", stream.toPlainText())

        # Category filter: Jobs
        stream._set_category_filter("Jobs")
        self.assertIn("Job Discovered", stream.toPlainText())
        self.assertNotIn("Application Submitted", stream.toPlainText())

        # Switch to Raw Logs
        stream._set_active_view("raw")
        self.assertIn("[10:00:01]", stream.toPlainText())
        self.assertIn("[10:00:04]", stream.toPlainText())

        # Reset filter
        stream._set_active_view("activity")
        stream._set_category_filter("All")

    def test_run_details_drawer_inspection(self):
        """Verifies clicking a historical run row opens the read-only RunDetailsDrawer."""
        from app.db.models.automation_run import AutomationRun
        now = datetime.now(timezone.utc)
        mock_run = AutomationRun(
            run_id="test-drawer-run-1234",
            platform="foundit",
            status="COMPLETED",
            started_at=now,
            finished_at=now,
            jobs_discovered=15,
            jobs_evaluated=12,
            jobs_qualified=8,
            jobs_skipped=4,
            applications_submitted=5,
            errors_count=0,
            stop_reason="Clean exit",
        )

        drawer = self.view.run_details_drawer
        self.assertFalse(drawer.isVisible())

        # Trigger run selection
        self.view._on_run_selected(mock_run)
        self.assertTrue(drawer.isVisible())
        self.assertEqual(drawer.lbl_platform.text(), "Foundit")
        self.assertEqual(drawer.cnt_discovered.text(), "15")
        self.assertEqual(drawer.cnt_submitted.text(), "5")

        # Close drawer
        drawer.btn_close.click()
        self.assertFalse(drawer.isVisible())


if __name__ == "__main__":
    unittest.main()
