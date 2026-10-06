"""End-to-end tests for UniversalApplicationOrchestrator."""

import asyncio
from pathlib import Path
import tempfile
import unittest

from app.services.automation.universal_agent import (
    AgentExecutionState,
    AgentRunTimeline,
    InterventionReason,
    OrchestrationResult,
    TerminalResult,
    UniversalApplicationOrchestrator,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestUniversalApplicationOrchestrator(unittest.IsolatedAsyncioTestCase):
    """Verifies end-to-end multi-step orchestration, V1 review gate enforcement, and manual takeover."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)

        # Create sample dummy resume
        self.sample_resume = Path(self.temp_dir.name) / "sample_resume.pdf"
        self.sample_resume.write_bytes(b"%PDF-1.4 test resume artifact for orchestrator")

        self.candidate_context = {
            "profile": {
                "user.first_name": "Jane",
                "user.last_name": "Doe",
                "user.email": "jane.doe@example.com",
                "profile.phone_number": "+1 (555) 000-0000",
                "profile.linkedin_url": "https://linkedin.com/in/janedoe",
                "profile.portfolio_url": "https://github.com/janedoe",
                "professional_profile.total_experience_years": "5-8",
                "professional_profile.notice_period_days": "30",
                "professional_profile.expected_ctc": "$140,000",
            },
            "resume": {
                "resume.file_path": str(self.sample_resume),
            },
            "qna": {
                "legally_authorized_to_work": "yes",
                "require_visa_sponsorship": "no",
            },
        }

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_end_to_end_single_page_application_success(self) -> None:
        """Verifies full single-page application run, V1 review gate pause, and successful certified submission."""
        review_gated = asyncio.Event()

        def on_review(orch, analysis, fill_result):
            # Assert state was in PENDING_HUMAN_REVIEW / PAUSED_FOR_INTERVENTION before submission
            self.assertIn(orch.state_machine.current_state, [AgentExecutionState.PENDING_HUMAN_REVIEW, AgentExecutionState.PAUSED_FOR_INTERVENTION])
            review_gated.set()
            # Human confirms review
            orch.confirm_submission("Reviewed and confirmed by candidate.")

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=self.agent,
            candidate_context=self.candidate_context,
            on_review_requested=on_review,
        )

        result = await orchestrator.run(
            portal_url=f"{self.base_url}/standard-job",
            job_title="Senior Full Stack Engineer",
            company="Acme Corp",
            headless=True,
        )

        # 1. Assert review gate was strictly visited
        self.assertTrue(review_gated.is_set())

        # 2. Assert submission outcome
        self.assertTrue(result.is_success)
        self.assertEqual(result.terminal_result, TerminalResult.SUCCESS_SUBMITTED)
        self.assertEqual(result.reference_number, "APP-JP-98765")
        self.assertIn("thank-you", result.current_url)

        # 3. Assert snapshot visual & cryptographic artifacts
        self.assertIsNotNone(result.snapshot)
        self.assertIsNotNone(result.snapshot.screenshot_path)
        self.assertTrue(Path(result.snapshot.screenshot_path).exists())
        self.assertGreater(len(result.snapshot.audit_hash), 0)

        # 4. Assert timeline audit trail shows legal sequence through review gate
        timeline_states = [e.state for e in result.timeline.events if e.event_type == "STATE_CHANGE"]
        self.assertIn(AgentExecutionState.PENDING_HUMAN_REVIEW.value, timeline_states)
        self.assertIn(AgentExecutionState.SUBMITTING.value, timeline_states)
        review_idx = timeline_states.index(AgentExecutionState.PENDING_HUMAN_REVIEW.value)
        submit_idx = timeline_states.index(AgentExecutionState.SUBMITTING.value)
        self.assertLess(review_idx, submit_idx, "PENDING_HUMAN_REVIEW must strictly precede SUBMITTING")

    async def test_v1_human_review_cancellation(self) -> None:
        """Verifies that user can decline submission at review gate, preventing submission."""
        def on_review(orch, analysis, fill_result):
            orch.cancel("Candidate declined to proceed.")

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=self.agent,
            candidate_context=self.candidate_context,
            on_review_requested=on_review,
        )

        result = await orchestrator.run(
            portal_url=f"{self.base_url}/standard-job",
            job_title="Senior Full Stack Engineer",
            company="Acme Corp",
            headless=True,
        )

        self.assertFalse(result.is_success)
        self.assertEqual(result.terminal_result, TerminalResult.USER_CANCELLED)
        # Form was not submitted, server last_submission should be None
        self.assertIsNone(self.server.last_submission)

    async def test_manual_takeover_during_orchestration(self) -> None:
        """Verifies that manual takeover halts automation and leaves browser session open."""
        def on_review(orch, analysis, fill_result):
            orch.takeover_manually("Candidate taking over.")

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=self.agent,
            candidate_context=self.candidate_context,
            on_review_requested=on_review,
        )

        result = await orchestrator.run(
            portal_url=f"{self.base_url}/standard-job",
            headless=True,
        )

        self.assertFalse(result.is_success)
        self.assertEqual(result.terminal_result, TerminalResult.MANUAL_REQUIRED)
        self.assertTrue(orchestrator.browser_agent.is_initialized)

    async def test_multi_step_wizard_end_to_end(self) -> None:
        """Verifies multi-page application wizard progression (Step 1 -> Step 2 -> Step 3 -> Confirmation)."""
        review_reached = asyncio.Event()

        def on_review(orch, analysis, fill_result):
            review_reached.set()
            orch.confirm_submission("Wizard completed, approving final submit.")

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=self.agent,
            candidate_context=self.candidate_context,
            on_review_requested=on_review,
        )

        result = await orchestrator.run(
            portal_url=f"{self.base_url}/wizard/step1",
            job_title="Full Stack Engineer",
            company="Apex Dynamics",
            headless=True,
        )

        self.assertTrue(review_reached.is_set())
        self.assertTrue(result.is_success)
        self.assertEqual(result.terminal_result, TerminalResult.SUCCESS_SUBMITTED)
        self.assertEqual(result.reference_number, "APP-WIZARD-1122")
        self.assertIn("thank-you", result.current_url)

    async def test_mandatory_privacy_and_consent_sweep(self) -> None:
        """Verifies that ensure_mandatory_consent_accepted detects and checks privacy and required checkboxes."""
        from app.services.automation.universal_agent.form_filler import FormFiller

        await self.agent.navigate(f"{self.base_url}/standard-job")
        
        js_inject = """
            document.body.innerHTML = `
                <form id="app-form">
                    <div class="pretty p-icon">
                        <input id="chk_privacy" type="checkbox" required="required" name="agree_privacy">
                        <label for="chk_privacy">(Required) Allow us to process your personal data *</label>
                    </div>
                    <div class="custom-control">
                        <input id="chk_terms" type="checkbox" name="terms_consent">
                        <label for="chk_terms">I agree to terms of service and privacy policy</label>
                    </div>
                    <div>
                        <input id="chk_marketing" type="checkbox" name="marketing_opt_in">
                        <label for="chk_marketing">Send me marketing newsletters</label>
                    </div>
                </form>
            `;
        """
        await self.agent.evaluate(js_inject)

        filler = UniversalFormFiller() if 'UniversalFormFiller' in globals() else FormFiller()
        accepted_count = await filler.ensure_mandatory_consent_accepted(self.agent)

        self.assertEqual(accepted_count, 2)
        chk_privacy_checked = await self.agent.evaluate("document.querySelector('#chk_privacy').checked")
        chk_terms_checked = await self.agent.evaluate("document.querySelector('#chk_terms').checked")
        chk_marketing_checked = await self.agent.evaluate("document.querySelector('#chk_marketing').checked")

        self.assertTrue(chk_privacy_checked)
        self.assertTrue(chk_terms_checked)
        self.assertFalse(chk_marketing_checked)


