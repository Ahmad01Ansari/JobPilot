"""Automated test suite for Phase 12: Universal Agent QThread & AutomationService Lifecycle Integration."""

import asyncio
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QObject
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AutomationRun
from app.db.session import configure_sqlite_pragmas
from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationRunResult,
    AutomationState,
    InterventionType,
)
from app.services.automation_service import AutomationManager, AutomationWorker
from app.services.automation.universal_agent.orchestrator import (
    OrchestrationResult,
    UniversalApplicationOrchestrator,
)
from app.services.automation.universal_agent.snapshot_recorder import ApplicationSubmissionSnapshot
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.timeline import AgentRunTimeline
from platforms.router import PlatformRouter, UniversalPlatform

app = QApplication.instance() or QApplication([])


class MockUniversalOrchestrator(UniversalApplicationOrchestrator):
    """Controllable UniversalApplicationOrchestrator for async lifecycle verification."""

    def __init__(self, mode: str = "review_then_submit") -> None:
        self.mode = mode
        self.timeline = AgentRunTimeline()
        self.state_machine = UniversalApplicationStateMachine(timeline=self.timeline)
        self.intervention_manager = MagicMock()
        self._listeners = []

        # Setup real or mock intervention handling
        self._resolution_event = asyncio.Event()
        self._active_request = None

        def add_int_listener(cb):
            self._listeners.append(cb)
        self.intervention_manager.add_listener = add_int_listener

        def trigger_int(reason, message, details=None):
            req = MagicMock()
            req.reason = reason
            req.message = message
            req.details = details or {}
            self._active_request = req
            for l in self._listeners:
                l(req)
            return req
        self.intervention_manager.trigger_intervention = trigger_int

        self.browser_agent = MagicMock()
        async def mock_close():
            pass
        self.browser_agent.close = mock_close

    def _set_event_safely(self) -> None:
        if not hasattr(self, "_resolution_event") or not self._resolution_event:
            return
        if hasattr(self, "_loop") and self._loop and self._loop.is_running():
            try:
                running = asyncio.get_running_loop()
                if running == self._loop:
                    self._resolution_event.set()
                else:
                    self._loop.call_soon_threadsafe(self._resolution_event.set)
            except RuntimeError:
                self._loop.call_soon_threadsafe(self._resolution_event.set)
        else:
            self._resolution_event.set()

    def confirm_submission(self, notes: Optional[str] = None, data: Optional[Dict[str, Any]] = None, **kwargs) -> None:
        self.confirmed = True
        self._set_event_safely()

    def takeover_manually(self, notes: Optional[str] = None) -> None:
        self.taken_over = True
        self._set_event_safely()

    def cancel(self, reason: str = "Cancelled") -> None:
        self.cancelled = True
        self._set_event_safely()

    async def run(
        self,
        portal_url: str,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        headless: bool = False,
        max_wizard_steps: int = 10,
    ) -> OrchestrationResult:
        self._loop = asyncio.get_running_loop()
        self._resolution_event = asyncio.Event()
        if self.mode == "review_then_submit":
            # 1. Step through states to PENDING_HUMAN_REVIEW
            self.state_machine.transition_to(AgentExecutionState.INITIALIZING, message="Initializing session")
            self.state_machine.transition_to(AgentExecutionState.NAVIGATING, message=f"Navigating to {portal_url}")
            self.state_machine.transition_to(AgentExecutionState.ANALYZING_PAGE, message="Scanning form")
            self.state_machine.transition_to(AgentExecutionState.MAPPING_FIELDS, message="Mapping fields")
            self.state_machine.transition_to(AgentExecutionState.FILLING_FORM, message="Populating fields")
            await asyncio.sleep(0.02)

            # 2. Trigger Pre-Submission Review
            self.state_machine.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW, message="Review needed")
            req = MagicMock()
            req.reason = InterventionReason.PRE_SUBMISSION_REVIEW
            req.message = "Please review before submitting."
            req.details = {"fields": {"name": "Test User"}}
            for l in self._listeners:
                l(req)

            # Wait for confirm or cancel
            await self._resolution_event.wait()

            if getattr(self, "cancelled", False):
                self.state_machine.complete(TerminalResult.FAILED_UNRECOVERABLE, message="Cancelled by user")
                return OrchestrationResult(
                    terminal_result=TerminalResult.FAILED_UNRECOVERABLE,
                    is_success=False,
                    state=AgentExecutionState.COMPLETED,
                    current_url=portal_url,
                    job_title=job_title,
                    company=company,
                    error_message="User cancelled application.",
                )

            if getattr(self, "taken_over", False):
                self.state_machine.complete(TerminalResult.MANUAL_COMPLETED, message="Manual takeover")
                return OrchestrationResult(
                    terminal_result=TerminalResult.MANUAL_COMPLETED,
                    is_success=False,
                    state=AgentExecutionState.COMPLETED,
                    current_url=portal_url,
                    job_title=job_title,
                    company=company,
                )

            # Confirmed -> Submit -> Verify -> Complete
            self.state_machine.transition_to(AgentExecutionState.SUBMITTING, message="Submitting form")
            await asyncio.sleep(0.02)
            self.state_machine.transition_to(AgentExecutionState.VERIFYING_SUBMISSION, message="Verifying submission")
            self.state_machine.complete(TerminalResult.SUCCESS_SUBMITTED, message="Submission confirmed")

            snap = ApplicationSubmissionSnapshot(
                portal_url=portal_url,
                submission_timestamp="2026-09-29T12:00:00Z",
                status="SUBMITTED",
                terminal_result=TerminalResult.SUCCESS_SUBMITTED.value,
                reference_number="CONF-9999",
                job_title=job_title or "Job",
                company=company or "Company",
                filled_fields_summary={"name": "Test User"},
                audit_hash="abc123sha",
            )
            return OrchestrationResult(
                terminal_result=TerminalResult.SUCCESS_SUBMITTED,
                is_success=True,
                state=AgentExecutionState.COMPLETED,
                current_url=portal_url,
                job_title=job_title,
                company=company,
                reference_number="CONF-9999",
                snapshot=snap,
            )

        elif self.mode == "error":
            return OrchestrationResult(
                terminal_result=TerminalResult.FAILED_UNRECOVERABLE,
                is_success=False,
                state=AgentExecutionState.COMPLETED,
                current_url=portal_url,
                error_message="Simulated navigation error",
            )


class TestUniversalWorkerLifecycle(unittest.TestCase):
    """Integration test suite for AutomationWorker and AutomationManager universal execution."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase12_test.db")
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

        self.manager = AutomationManager(session_factory=self.Session)

    def tearDown(self):
        if self.manager.is_running() and self.manager._current_worker:
            self.manager.request_stop()
            self.manager._current_worker.wait(2000)

        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_worker_initialization_with_universal_parameters(self):
        """Verifies worker accepts universal configuration attributes cleanly."""
        worker = AutomationWorker(
            run_id="run-u1",
            platform="universal",
            session_factory=self.Session,
            target_url="https://jobs.example.com/apply/123",
            job_title="Software Architect",
            company="Globex Corporation",
            candidate_context={"name": "Alice Developer"},
            headless=True,
        )
        self.assertEqual(worker.platform, "universal")
        self.assertEqual(worker.target_url, "https://jobs.example.com/apply/123")
        self.assertEqual(worker.job_title, "Software Architect")
        self.assertEqual(worker.company, "Globex Corporation")
        self.assertEqual(worker.candidate_context["name"], "Alice Developer")
        self.assertTrue(worker.headless)

    def test_universal_platform_router_routing(self):
        """Verifies PlatformRouter dispatches to UniversalPlatform correctly."""
        router = PlatformRouter()
        self.assertIn("universal", router.universal_platform.platform_name)

        # Route without URL returns failed stats dict
        result = router.route("universal")
        self.assertEqual(result["platform"], "universal")
        self.assertEqual(result["status"], "failed")

        # Test pause, resume, close methods
        router.pause()
        self.assertTrue(router.universal_platform._is_paused)
        router.resume()
        self.assertFalse(router.universal_platform._is_paused)
        router.close()

    def test_universal_worker_review_and_submission_lifecycle(self):
        """Verifies QThread boot, asyncio event loop execution, intervention signal, and submission."""
        mock_orch = MockUniversalOrchestrator(mode="review_then_submit")

        worker = AutomationWorker(
            run_id="run-u2",
            platform="universal",
            session_factory=self.Session,
            target_url="https://career.acme.org/job/42",
            job_title="Lead AI Engineer",
            company="Acme AI",
            headless=True,
            orchestrator=mock_orch,
        )

        interventions = []
        submissions = []
        states = []
        results = []

        worker.intervention_required.connect(lambda ev: interventions.append(ev))
        worker.application_submitted.connect(lambda ev: submissions.append(ev))
        worker.state_changed.connect(lambda rid, st: states.append(st))
        worker.finished_result.connect(lambda res: results.append(res))

        worker.start()

        # Wait until pre-submission review intervention is emitted
        timeout_loops = 50
        while not interventions and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1

        self.assertGreater(len(interventions), 0, "Expected intervention_required signal")
        first_int = interventions[0]
        self.assertEqual(first_int.intervention_type, InterventionType.PRE_SUBMISSION_REVIEW)
        self.assertEqual(first_int.platform, "universal")

        # Confirm review via worker method
        worker.confirm_review(notes="Confirmed in test")

        timeout_loops = 50
        while (worker.isRunning() or not results) and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1
        worker.wait(1000)

        self.assertFalse(worker.isRunning(), "Worker thread should terminate cleanly")
        self.assertEqual(len(submissions), 1, "Expected 1 ApplicationSubmittedEvent")
        self.assertEqual(submissions[0].company, "Acme AI")
        self.assertEqual(submissions[0].title, "Lead AI Engineer")
        self.assertEqual(submissions[0].source_url, "https://career.acme.org/job/42")

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0].status, AutomationState.COMPLETED)
        self.assertEqual(results[0].applications_submitted, 1)

    def test_universal_worker_manual_takeover_lifecycle(self):
        """Verifies candidate can switch to manual takeover via worker."""
        mock_orch = MockUniversalOrchestrator(mode="review_then_submit")

        worker = AutomationWorker(
            run_id="run-u3",
            platform="universal",
            session_factory=self.Session,
            target_url="https://portal.example.com/apply",
            job_title="DevOps Specialist",
            company="CloudCo",
            orchestrator=mock_orch,
        )

        interventions = []
        worker.intervention_required.connect(lambda ev: interventions.append(ev))
        worker.start()

        timeout_loops = 50
        while not interventions and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1

        self.assertTrue(len(interventions) > 0)

        # Trigger manual takeover
        worker.takeover_manually(notes="Candidate opted to finish manually")
        timeout_loops = 50
        while worker.isRunning() and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1
        worker.wait(1000)

        self.assertFalse(worker.isRunning())
        self.assertTrue(getattr(mock_orch, "taken_over", False))

    def test_automation_manager_universal_orchestration(self):
        """Verifies AutomationManager starts universal run, passes kwargs, and coordinates confirmation."""
        mock_orch = MockUniversalOrchestrator(mode="review_then_submit")

        interventions = []
        runs_finished = []
        self.manager.intervention_required.connect(lambda ev: interventions.append(ev))
        self.manager.run_finished.connect(lambda res: runs_finished.append(res))

        started, err = self.manager.start_automation(
            platform="universal",
            target_url="https://startup.io/careers/1",
            job_title="Full Stack Developer",
            company="Startup Inc",
            orchestrator=mock_orch,
        )
        self.assertTrue(started, f"Failed to start automation: {err}")
        self.assertTrue(self.manager.is_running())

        # Wait for intervention
        timeout_loops = 50
        while not interventions and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1

        self.assertGreater(len(interventions), 0)

        # Confirm review via manager
        ok = self.manager.confirm_current_review(notes="Manager confirmed")
        self.assertTrue(ok)

        timeout_loops = 50
        while not runs_finished and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1

        self.assertGreater(len(runs_finished), 0)
        self.assertEqual(runs_finished[0].status, AutomationState.COMPLETED)
        self.assertFalse(self.manager.is_running())

        # Verify DB record
        with self.Session() as session:
            record = session.query(AutomationRun).filter_by(platform="universal").first()
            self.assertIsNotNone(record)
            self.assertEqual(record.status, AutomationState.COMPLETED.value)
            self.assertEqual(record.applications_submitted, 1)

    def test_universal_worker_stop_cancellation(self):
        """Verifies worker aborts cleanly when request_stop is invoked during pending intervention."""
        mock_orch = MockUniversalOrchestrator(mode="review_then_submit")

        worker = AutomationWorker(
            run_id="run-u4",
            platform="universal",
            session_factory=self.Session,
            target_url="https://portal.test/cancel",
            job_title="QA Engineer",
            company="TestLab",
            orchestrator=mock_orch,
        )

        interventions = []
        worker.intervention_required.connect(lambda ev: interventions.append(ev))
        worker.start()

        timeout_loops = 50
        while not interventions and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1

        self.assertTrue(len(interventions) > 0)

        # Stop requested
        worker.request_stop()
        timeout_loops = 50
        while worker.isRunning() and timeout_loops > 0:
            QTest.qWait(50)
            timeout_loops -= 1
        worker.wait(1000)

        self.assertFalse(worker.isRunning())
        self.assertTrue(getattr(mock_orch, "cancelled", False))


if __name__ == "__main__":
    unittest.main()
