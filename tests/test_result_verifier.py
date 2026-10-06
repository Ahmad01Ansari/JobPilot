"""Unit tests for ResultVerifier and SnapshotRecorder."""

import os
from pathlib import Path
import tempfile
import unittest

from app.services.automation.universal_agent import (
    AgentExecutionState,
    AgentRunTimeline,
    InterventionReason,
    ResultVerifier,
    SnapshotRecorder,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestResultVerifierAndSnapshotRecorder(unittest.IsolatedAsyncioTestCase):
    """Verifies confirmation parsing, validation error handling, visual proof, and audit snapshots."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)

        self.timeline = AgentRunTimeline()
        self.sm = UniversalApplicationStateMachine(timeline=self.timeline)
        self.verifier = ResultVerifier()
        self.recorder = SnapshotRecorder(base_snapshot_dir=self.temp_dir.name)

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_successful_confirmation_verification(self) -> None:
        """Verifies success certification, reference code extraction, and state machine completion."""
        # 1. Navigate to confirmation page
        await self.agent.navigate(f"{self.base_url}/thank-you?status=success&ref=APP-JP-98765")

        # 2. Verify submission signals
        result = await self.verifier.verify_submission(self.agent)

        self.assertTrue(result.is_success)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.reference_number, "APP-JP-98765")
        self.assertIn("Thank you", result.confirmation_header or "")
        self.assertGreater(len(result.matched_signals), 0)

        # 3. Update state machine
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        self.sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        self.sm.transition_to(AgentExecutionState.SUBMITTING)
        self.sm.transition_to(AgentExecutionState.VERIFYING_SUBMISSION)

        self.verifier.verify_and_update_state(self.sm, result)

        self.assertEqual(self.sm.current_state, AgentExecutionState.COMPLETED)
        self.assertEqual(self.sm.terminal_result, TerminalResult.SUCCESS_SUBMITTED)

    async def test_validation_error_verification_and_state_pause(self) -> None:
        """Verifies error banner detection and transition to PAUSED_FOR_INTERVENTION."""
        # 1. Trigger submission failure on standard job by submitting empty form
        await self.agent.navigate(f"{self.base_url}/standard-job")
        # Submit empty form directly via script click
        await self.agent.evaluate("document.querySelector('#application-form').submit()")
        # Wait for page reload with error banner
        await self.agent.wait_for_selector("#form-errors", timeout_ms=3000)

        # 2. Run verifier
        result = await self.verifier.verify_submission(self.agent)

        self.assertFalse(result.is_success)
        self.assertEqual(result.status, "VALIDATION_ERROR")
        self.assertGreater(len(result.error_messages), 0)
        error_text = " ".join(result.error_messages)
        self.assertIn("Please provide all required fields", error_text)

        # 3. Update state machine
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        self.sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        self.sm.transition_to(AgentExecutionState.SUBMITTING)
        self.sm.transition_to(AgentExecutionState.VERIFYING_SUBMISSION)

        self.verifier.verify_and_update_state(self.sm, result)

        self.assertEqual(self.sm.current_state, AgentExecutionState.PAUSED_FOR_INTERVENTION)
        self.assertEqual(self.sm.intervention_reason, InterventionReason.POST_SUBMIT_VALIDATION_ERROR)

    async def test_security_challenge_post_submit_detection(self) -> None:
        """Verifies that an unexpected CAPTCHA post-submit is recognized."""
        await self.agent.navigate(f"{self.base_url}/challenge/captcha")
        result = await self.verifier.verify_submission(self.agent)

        self.assertFalse(result.is_success)
        self.assertEqual(result.status, "CHALLENGE_DETECTED")

    async def test_snapshot_recorder_visual_and_cryptographic_proof(self) -> None:
        """Verifies PNG screenshot capture, DOM outerHTML storage, and SHA-256 audit hash generation."""
        await self.agent.navigate(f"{self.base_url}/thank-you?status=success&ref=APP-JP-98765")
        verification = await self.verifier.verify_submission(self.agent)

        snap_output_dir = Path(self.temp_dir.name) / "test_snapshot_run"
        snapshot = await self.recorder.capture_snapshot(
            agent=self.agent,
            verification=verification,
            terminal_result=TerminalResult.SUCCESS_SUBMITTED,
            output_dir=str(snap_output_dir),
            filled_fields={"first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.com"},
            job_title="Senior Full Stack Engineer",
            company="Acme Corp",
        )

        # 1. Metadata attributes
        self.assertEqual(snapshot.status, "SUCCESS")
        self.assertEqual(snapshot.terminal_result, "SUCCESS_SUBMITTED")
        self.assertEqual(snapshot.reference_number, "APP-JP-98765")
        self.assertEqual(snapshot.job_title, "Senior Full Stack Engineer")
        self.assertEqual(snapshot.company, "Acme Corp")
        self.assertEqual(snapshot.filled_fields_summary["email"], "jane.doe@example.com")

        # 2. Visual screenshot artifact
        self.assertIsNotNone(snapshot.screenshot_path)
        self.assertTrue(os.path.exists(snapshot.screenshot_path))
        self.assertGreater(os.path.getsize(snapshot.screenshot_path), 100)

        # 3. DOM HTML artifact
        self.assertIsNotNone(snapshot.dom_html_path)
        self.assertTrue(os.path.exists(snapshot.dom_html_path))
        dom_text = Path(snapshot.dom_html_path).read_text(encoding="utf-8")
        self.assertIn("Thank you for your application!", dom_text)

        # 4. JSON metadata file
        self.assertIsNotNone(snapshot.metadata_path)
        self.assertTrue(os.path.exists(snapshot.metadata_path))

        # 5. Cryptographic hash
        self.assertEqual(len(snapshot.audit_hash), 64)  # Valid hex SHA-256 string
