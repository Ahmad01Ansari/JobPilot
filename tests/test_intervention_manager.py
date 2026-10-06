"""Unit tests for Human-in-the-Loop InterventionManager and ManualTakeoverWorkflow."""

import asyncio
import tempfile
import unittest

from app.services.automation.universal_agent import (
    AgentExecutionState,
    AgentRunTimeline,
    InterventionManager,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestInterventionManager(unittest.IsolatedAsyncioTestCase):
    """Verifies pause/resume synchronization, manual takeover, cancellation, and timeout safety."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)

        self.timeline = AgentRunTimeline()
        self.sm = UniversalApplicationStateMachine(timeline=self.timeline)
        self.manager = InterventionManager()

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_captcha_challenge_pause_and_resume_flow(self) -> None:
        """Verifies state machine pauses on CAPTCHA and resumes cleanly when user resolves."""
        # 1. Advance state machine to ANALYZING_PAGE
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)

        # 2. Trigger CAPTCHA intervention
        received_events = []
        self.manager.add_listener(lambda req: received_events.append(req))

        req = self.manager.trigger_intervention(
            self.sm,
            reason=InterventionReason.CAPTCHA_CHALLENGE,
            message="Cloudflare Turnstile challenge encountered in browser.",
            details={"type": "turnstile", "sitekey": "mock-key-123"},
        )

        self.assertEqual(self.sm.current_state, AgentExecutionState.PAUSED_FOR_INTERVENTION)
        self.assertEqual(self.sm.intervention_reason, InterventionReason.CAPTCHA_CHALLENGE)
        self.assertTrue(self.manager.is_paused)
        self.assertEqual(len(received_events), 1)

        # 3. Simulate background wait and async human resolution
        async def mock_human_solver():
            await asyncio.sleep(0.05)
            self.manager.resolve_resume({"challenge_cleared": True})

        solve_task = asyncio.create_task(mock_human_solver())
        resolved_req = await self.manager.wait_for_resolution()
        await solve_task

        self.assertTrue(resolved_req.is_resolved)
        self.assertEqual(resolved_req.resolution_action, "RESUME")
        self.assertTrue(resolved_req.resolution_data.get("challenge_cleared"))

        # 4. Resume automation: state machine returns to ANALYZING_PAGE
        self.sm.transition_to(
            AgentExecutionState.ANALYZING_PAGE,
            details={"resume_source": "human_challenge_resolution"},
        )
        self.assertEqual(self.sm.current_state, AgentExecutionState.ANALYZING_PAGE)

    async def test_unknown_required_field_data_supply_flow(self) -> None:
        """Verifies pausing on unknown mandatory field and resuming when candidate provides answer."""
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)

        # Trigger unknown required field intervention
        req = self.manager.trigger_intervention(
            self.sm,
            reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
            message="Form requires 'Security Clearance' which is absent from profile.",
            details={"unresolved_field": "security_clearance"},
        )

        self.assertEqual(self.sm.current_state, AgentExecutionState.PAUSED_FOR_INTERVENTION)

        # User provides answer in dialog
        self.manager.resolve_resume({"security_clearance": "Secret"})

        self.assertTrue(req.is_resolved)
        self.assertEqual(req.resolution_data["security_clearance"], "Secret")

        # Resume into form filling
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        self.assertEqual(self.sm.current_state, AgentExecutionState.FILLING_FORM)

    async def test_manual_takeover_preserves_live_browser_session(self) -> None:
        """Verifies that manual takeover transitions cleanly without closing or crashing the browser."""
        await self.agent.navigate(f"{self.base_url}/standard-job")
        title_before = await self.agent.get_title()

        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)

        # User decides to take over manually
        result = self.manager.resolve_manual_takeover(
            state_machine=self.sm,
            agent=self.agent,
            notes="Candidate wants to verify and submit directly.",
        )

        # 1. State machine completed with MANUAL_REQUIRED
        self.assertEqual(self.sm.current_state, AgentExecutionState.COMPLETED)
        self.assertEqual(self.sm.terminal_result, TerminalResult.MANUAL_REQUIRED)

        # 2. Browser session is strictly preserved
        self.assertTrue(result.success)
        self.assertTrue(result.browser_kept_open)
        self.assertTrue(self.agent.is_initialized)

        # Page is still active and accessible
        title_after = await self.agent.get_title()
        self.assertEqual(title_before, title_after)

    async def test_user_cancellation_workflow(self) -> None:
        """Verifies clean cancellation when user chooses to abort."""
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)

        self.manager.trigger_intervention(
            self.sm,
            reason=InterventionReason.PRE_SUBMISSION_REVIEW,
            message="Waiting for candidate pre-submission confirmation.",
        )

        self.manager.resolve_cancel(self.sm, reason="Candidate decided not to apply.")

        self.assertEqual(self.sm.current_state, AgentExecutionState.COMPLETED)
        self.assertEqual(self.sm.terminal_result, TerminalResult.USER_CANCELLED)

    async def test_timeout_handling_safety(self) -> None:
        """Verifies that waiting on intervention with timeout does not hang or deadlock."""
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)

        self.manager.trigger_intervention(
            self.sm,
            reason=InterventionReason.CAPTCHA_CHALLENGE,
            message="Test timeout",
        )

        # Wait with 0.1 second timeout
        res = await self.manager.wait_for_resolution(timeout_seconds=0.1)

        self.assertTrue(res.is_resolved)
        self.assertEqual(res.resolution_action, "TIMEOUT")
