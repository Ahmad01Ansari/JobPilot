"""Automated test suite for Phase 13: Automation Engine Integration."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, AutomationRun, Job
from app.db.session import configure_sqlite_pragmas
from app.repositories.automation_run_repository import AutomationRunRepository
from app.services.automation_bridge import AutomationBridge
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
from app.services.automation_service import AutomationManager, AutomationWorker
from app.services.log_service import LogService
from app.ui.views.automation_view import AutomationView
from app.ui.views.logs_view import LogsView
from tests.fake_automation_engine import FakeAutomationEngine

app = QApplication.instance() or QApplication([])


class TestAutomationIntegration(unittest.TestCase):
    """Integration and behavioral test suite for automation manager, worker, bridge, and UI."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase13_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )

        self.log_file = os.path.join(self.temp_dir, "test_log.txt")
        self.log_service = LogService(log_path=self.log_file)
        self.log_service.ensure_log_file()

        self.manager = AutomationManager(session_factory=self.Session)

    def tearDown(self):
        if self.manager.is_running() and self.manager._current_worker:
            self.manager.request_stop()
            self.manager._current_worker.wait(2000)

        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_automation_manager_start_and_status(self):
        """Verifies starting automation, state progression, and preventing concurrent runs."""
        fake_engine = FakeAutomationEngine(jobs_to_discover=2, jobs_to_apply=1, delay_seconds=0.01)

        success, err = self.manager.start_automation(
            platform="linkedin",
            custom_runner=fake_engine.run,
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        # Attempt concurrent run
        second_success, second_err = self.manager.start_automation(platform="naukri")
        self.assertFalse(second_success)
        self.assertIn("already running", second_err.lower())

        # Wait for worker to finish
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)

        # Process any pending Qt events
        QTest.qWait(100)
        self.assertEqual(self.manager.get_state(), AutomationState.COMPLETED)
        self.assertFalse(self.manager.is_running())

    def test_automation_manager_stop_lifecycle(self):
        """Verifies stopping an active run transitions through STOP_REQUESTED and terminates."""
        fake_engine = FakeAutomationEngine(jobs_to_discover=10, jobs_to_apply=5, delay_seconds=0.1)

        success, _ = self.manager.start_automation(
            platform="linkedin",
            custom_runner=fake_engine.run,
        )
        self.assertTrue(success)

        # Request stop while running
        QTest.qWait(50)
        stop_success, stop_err = self.manager.request_stop()
        self.assertTrue(stop_success)
        self.assertIsNone(stop_err)

        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)

        QTest.qWait(100)
        self.assertFalse(self.manager.is_running())

    def test_automation_run_persisted_in_db(self):
        """Verifies an AutomationRun entity is created, tracked, and finalized in SQLite."""
        fake_engine = FakeAutomationEngine(jobs_to_discover=3, jobs_to_apply=2, delay_seconds=0.01)

        received_results = []
        self.manager.run_finished.connect(received_results.append)

        self.manager.start_automation(platform="linkedin", custom_runner=fake_engine.run)
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(len(received_results), 1)
        run_result: AutomationRunResult = received_results[0]
        self.assertEqual(run_result.status, AutomationState.COMPLETED)
        self.assertEqual(run_result.jobs_discovered, 3)
        self.assertEqual(run_result.applications_submitted, 2)

        # Verify in DB via repository
        session = self.Session()
        try:
            repo = AutomationRunRepository(session)
            db_run = repo.get_by_run_id(run_result.run_id)
            self.assertIsNotNone(db_run)
            self.assertEqual(db_run.platform, "linkedin")
            self.assertEqual(db_run.status, AutomationState.COMPLETED.value)
            self.assertEqual(db_run.jobs_discovered, 3)
            self.assertEqual(db_run.applications_submitted, 2)
            self.assertIsNotNone(db_run.finished_at)
        finally:
            session.close()

    def test_worker_signals_emitted(self):
        """Verifies worker emits discrete Qt domain signals for discovery and submission."""
        discovered_events = []
        submitted_events = []
        progress_events = []

        fake_engine = FakeAutomationEngine(jobs_to_discover=2, jobs_to_apply=1, delay_seconds=0.01)

        self.manager.job_discovered.connect(discovered_events.append)
        self.manager.application_submitted.connect(submitted_events.append)
        self.manager.progress_updated.connect(progress_events.append)

        self.manager.start_automation(platform="naukri", custom_runner=fake_engine.run)
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(len(discovered_events), 2)
        self.assertEqual(len(submitted_events), 1)
        self.assertTrue(len(progress_events) >= 2)
        self.assertEqual(discovered_events[0].platform, "naukri")

    def test_bridge_job_upsert_idempotent(self):
        """Verifies bridge updates existing job record upon duplicate discovery without error."""
        bridge = AutomationBridge(session_factory=self.Session)

        event1 = JobDiscoveredEvent(
            run_id="run-1",
            platform="linkedin",
            title="Data Engineer",
            company="Acme Corp",
            external_job_id="ext-101",
            location="Remote",
            url="https://linkedin.com/jobs/101",
        )
        job_id_1 = bridge.handle_job_discovered(event1)
        self.assertIsNotNone(job_id_1)

        # Re-emitting same job
        event2 = JobDiscoveredEvent(
            run_id="run-2",
            platform="linkedin",
            title="Data Engineer",
            company="Acme Corp",
            external_job_id="ext-101",
            location="Remote - India",
            url="https://linkedin.com/jobs/101",
        )
        job_id_2 = bridge.handle_job_discovered(event2)
        self.assertEqual(job_id_1, job_id_2)

        # Verify only 1 job row exists in DB
        session = self.Session()
        try:
            count = session.query(Job).count()
            self.assertEqual(count, 1)
        finally:
            session.close()

    def test_bridge_application_idempotent(self):
        """Verifies duplicate application event does not create duplicate application records."""
        bridge = AutomationBridge(session_factory=self.Session)

        disc = JobDiscoveredEvent(
            run_id="run-1",
            platform="linkedin",
            title="DevOps Engineer",
            company="Cloud Inc",
            external_job_id="ext-202",
        )
        job_id = bridge.handle_job_discovered(disc)

        app_event_1 = ApplicationSubmittedEvent(
            run_id="run-1",
            platform="linkedin",
            job_id=job_id,
            external_job_id="ext-202",
            title="DevOps Engineer",
            company="Cloud Inc",
        )
        app_id_1 = bridge.handle_application_submitted(app_event_1)
        self.assertIsNotNone(app_id_1)

        # Re-emitting same application
        app_event_2 = ApplicationSubmittedEvent(
            run_id="run-2",
            platform="linkedin",
            job_id=job_id,
            external_job_id="ext-202",
            title="DevOps Engineer",
            company="Cloud Inc",
        )
        app_id_2 = bridge.handle_application_submitted(app_event_2)
        self.assertEqual(app_id_1, app_id_2)

        session = self.Session()
        try:
            app_count = session.query(Application).count()
            self.assertEqual(app_count, 1)
        finally:
            session.close()

    def test_bridge_handles_db_errors_gracefully(self):
        """Verifies bridge catches database persistence failures and does not raise exceptions."""
        broken_sessionmaker = sessionmaker(bind=create_engine("sqlite:////nonexistent/dir/db.sqlite"))
        bridge = AutomationBridge(session_factory=broken_sessionmaker)

        event = JobDiscoveredEvent(
            run_id="run-err",
            platform="linkedin",
            title="Security Specialist",
            company="SecureCorp",
        )
        # Must not raise
        result = bridge.handle_job_discovered(event)
        self.assertIsNone(result)

    def test_manual_intervention_signals(self):
        """Verifies that login / captcha interventions emit proper signals."""
        interventions = []
        self.manager.intervention_required.connect(interventions.append)

        fake_engine = FakeAutomationEngine(
            jobs_to_discover=1,
            jobs_to_apply=0,
            simulate_intervention=InterventionType.CAPTCHA_DETECTED,
            delay_seconds=0.01,
        )

        self.manager.start_automation(platform="naukri", custom_runner=fake_engine.run)
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(len(interventions), 1)
        self.assertEqual(interventions[0].intervention_type, InterventionType.CAPTCHA_DETECTED)
        self.assertIn("Simulated intervention", interventions[0].message)

    def test_worker_error_recovery(self):
        """Verifies worker captures unhandled engine exceptions and marks run as FAILED."""
        fake_engine = FakeAutomationEngine(
            jobs_to_discover=1,
            jobs_to_apply=0,
            simulate_error="Simulated browser crash!",
            delay_seconds=0.01,
        )

        self.manager.start_automation(platform="linkedin", custom_runner=fake_engine.run)
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(self.manager.get_state(), AutomationState.FAILED)

    def test_log_service_tail_filter_and_clear(self):
        """Tests LogService reading, filtering, and safe truncation."""
        sample_logs = (
            "2026-09-21 10:00:00 | INFO | Initializing engine\n"
            "2026-09-21 10:00:05 | WARN | Rate limit threshold reached\n"
            "2026-09-21 10:00:10 | ERROR | Connection timeout exception\n"
            "2026-09-21 10:00:15 | INFO | Session completed successfully\n"
        )
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write(sample_logs)

        lines = self.log_service.tail(n_lines=10)
        self.assertEqual(len(lines), 4)

        # Filter by level
        error_lines = self.log_service.filter_logs(lines, level="ERROR")
        self.assertEqual(len(error_lines), 1)
        self.assertIn("timeout exception", error_lines[0])

        # Filter by search
        search_lines = self.log_service.filter_logs(lines, search="rate limit")
        self.assertEqual(len(search_lines), 1)
        self.assertIn("Rate limit threshold", search_lines[0])

        # Safe clear without confirmation
        self.assertFalse(self.log_service.safe_clear(confirm=False))
        self.assertEqual(len(self.log_service.tail()), 4)

        # Safe clear with confirmation
        self.assertTrue(self.log_service.safe_clear(confirm=True))
        self.assertEqual(len(self.log_service.tail()), 0)

    def test_automation_view_ui_state(self):
        """Verifies AutomationView reflects manager state transitions and user controls."""
        view = AutomationView(automation_manager=self.manager)
        self.assertEqual(view.badge_status.text(), "IDLE")
        self.assertTrue(view.btn_start.isEnabled())
        self.assertFalse(view.btn_stop.isEnabled())

        # Start simulated run via view
        fake_engine = FakeAutomationEngine(jobs_to_discover=2, jobs_to_apply=1, delay_seconds=0.02)
        self.manager.start_automation(platform="linkedin", custom_runner=fake_engine.run)

        QTest.qWait(50)
        # Should reflect running state
        self.assertIn(view.badge_status.text(), ("STARTING", "RUNNING", "COMPLETED"))

        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(view.badge_status.text(), "COMPLETED")
        self.assertTrue(view.btn_start.isEnabled())
        self.assertFalse(view.btn_stop.isEnabled())
        self.assertEqual(view.val_discovered.text(), "2")
        self.assertEqual(view.val_applied.text(), "1")

    def test_logs_view_ui_state(self):
        """Verifies LogsView renders lines, handles search filter, and interacts with LogService."""
        with open(self.log_file, "w", encoding="utf-8") as f:
            f.write("Line 1: INFO Starting system\nLine 2: ERROR Selector failed\n")

        logs_view = LogsView(log_service=self.log_service)
        self.assertIn("Selector failed", logs_view.console.toPlainText())

        # Search filter
        logs_view.txt_search.setText("Selector")
        self.assertIn("Selector failed", logs_view.console.toPlainText())
        self.assertNotIn("Starting system", logs_view.console.toPlainText())

    def test_all_platforms_sequential_execution(self):
        """Verifies simulated all-platforms run executes sequential stages."""
        execution_stages = []

        def sequential_runner(worker):
            # Stage 1: LinkedIn
            execution_stages.append("linkedin_started")
            worker.record_job_discovered(
                JobDiscoveredEvent(
                    run_id=worker.run_id,
                    platform="linkedin",
                    title="Backend Dev",
                    company="Stripe",
                    external_job_id="seq-li-1",
                )
            )
            execution_stages.append("linkedin_finished")

            # Stage 2: Naukri
            execution_stages.append("naukri_started")
            worker.record_job_discovered(
                JobDiscoveredEvent(
                    run_id=worker.run_id,
                    platform="naukri",
                    title="Full Stack Dev",
                    company="Flipkart",
                    external_job_id="seq-nk-1",
                )
            )
            execution_stages.append("naukri_finished")

        self.manager.start_automation(platform="all", custom_runner=sequential_runner)
        worker = self.manager._current_worker
        if worker:
            worker.wait(5000)
        QTest.qWait(100)

        self.assertEqual(
            execution_stages,
            ["linkedin_started", "linkedin_finished", "naukri_started", "naukri_finished"],
        )
        self.assertEqual(self.manager.get_state(), AutomationState.COMPLETED)



if __name__ == "__main__":
    unittest.main()

