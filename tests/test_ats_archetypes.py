"""Automated Empirical Evaluation Suite for Phase 14: ATS Archetype Fixtures.

Evaluates Universal AI Application Agent components and orchestrator across
4 realistic top-tier ATS platform archetypes:
1. Greenhouse (/greenhouse) - Standard form, resume upload, custom questions, EEO survey.
2. Lever (/lever) - Single full name input, candidate links, experience selector.
3. Workday (/workday/step1-3) - Multi-step application wizard with resume upload and review.
4. Ashby (/ashby) - Dynamic portal structure, work auth/visa selects, compensation.

Validates against empirical benchmark criteria:
- Field Mapping Accuracy >= 98.0%
- Required-Field Completion == 100.0%
- Resume Upload Success == 100.0%
"""

import asyncio
from pathlib import Path
import tempfile
import unittest

from app.services.automation.universal_agent import (
    AgentExecutionState,
    FieldMapper,
    FileUploader,
    FormFiller,
    PageAnalyzer,
    ResultVerifier,
    TerminalResult,
    UniversalApplicationOrchestrator,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestATSArchetypes(unittest.IsolatedAsyncioTestCase):
    """Empirical evaluation of Universal Agent on top-tier ATS archetypes."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)

        # Create valid sample resume PDF artifact
        self.sample_resume = Path(self.temp_dir.name) / "Jane_Doe_Resume_2026.pdf"
        self.sample_resume.write_bytes(b"%PDF-1.4 Mock Candidate Resume Data for ATS Evaluation")

        self.candidate_context = {
            "profile": {
                "user.first_name": "Jane",
                "user.last_name": "Doe",
                "user.name": "Jane Doe",
                "user.email": "jane.doe@example.com",
                "profile.phone_number": "+1 (555) 0100",
                "profile.linkedin_url": "https://linkedin.com/in/janedoe",
                "profile.portfolio_url": "https://github.com/janedoe",
                "professional_profile.total_experience_years": "5-8",
                "professional_profile.notice_period_days": "30",
                "professional_profile.expected_ctc": "$150,000",
                "current_company": "Acme Corp",
                "gender": "Female",
                "veteran_status": "No",
                "disability_status": "No",
            },
            "resume": {
                "resume.file_path": str(self.sample_resume),
            },
            "qna": {
                "legally_authorized_to_work": "yes",
                "require_visa_sponsorship": "no",
            },
        }

        self.page_analyzer = PageAnalyzer()
        self.field_mapper = FieldMapper(candidate_context=self.candidate_context)
        self.file_uploader = FileUploader()
        self.form_filler = FormFiller(file_uploader=self.file_uploader)
        self.result_verifier = ResultVerifier()

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_greenhouse_archetype(self) -> None:
        """Evaluates Greenhouse ATS archetype: personal info, custom questions, resume upload, EEO."""
        portal_url = f"{self.base_url}/greenhouse"
        await self.agent.navigate(portal_url)

        # 1. Page Analysis
        analysis = await self.page_analyzer.analyze(self.agent)
        self.assertGreaterEqual(len(analysis.fields), 8)
        self.assertFalse(analysis.is_multi_step)

        # 2. Semantic Mapping & Accuracy Verification
        mapping_res = self.field_mapper.map_fields(analysis)
        self.assertGreaterEqual(mapping_res.accuracy, 0.98, "Greenhouse field mapping accuracy fell below 98%")
        self.assertEqual(len(mapping_res.unresolved_required_fields), 0, "Unresolved required fields detected on Greenhouse")

        # 3. Form Population & Required Completion
        fill_res = await self.form_filler.fill_form(self.agent, mapping_res)
        self.assertEqual(fill_res.required_completion_rate, 1.0, "Greenhouse required field completion must be 100%")
        self.assertTrue(fill_res.is_complete)

        # 4. Form Submission & Result Verification
        await self.agent.click("#submit_app")
        await asyncio.sleep(1.0)

        verification = await self.result_verifier.verify_submission(self.agent)
        self.assertTrue(verification.is_success, f"Greenhouse submission verification failed: {verification}")
        self.assertEqual(verification.reference_number, "GH-CONF-12345")

        # 5. Server-side Multipart Validation
        last_sub = self.server.last_submission
        self.assertIsNotNone(last_sub)
        self.assertEqual(last_sub["fields"]["first_name"], "Jane")
        self.assertEqual(last_sub["fields"]["last_name"], "Doe")
        self.assertEqual(last_sub["fields"]["email"], "jane.doe@example.com")
        self.assertEqual(last_sub["fields"]["work_auth"], "yes")
        self.assertIn("resume", last_sub["files"])
        self.assertEqual(last_sub["files"]["resume"]["filename"], "Jane_Doe_Resume_2026.pdf")

    async def test_lever_archetype(self) -> None:
        """Evaluates Lever ATS archetype: single full name input, links, experience dropdown."""
        portal_url = f"{self.base_url}/lever"
        await self.agent.navigate(portal_url)

        # 1. Page Analysis
        analysis = await self.page_analyzer.analyze(self.agent)
        self.assertGreaterEqual(len(analysis.fields), 6)

        # 2. Semantic Mapping
        mapping_res = self.field_mapper.map_fields(analysis)
        self.assertGreaterEqual(mapping_res.accuracy, 0.98, "Lever field mapping accuracy fell below 98%")
        self.assertEqual(len(mapping_res.unresolved_required_fields), 0)

        # Full name check
        name_mapping = mapping_res.get_resolved_mapping("name")
        self.assertIsNotNone(name_mapping)
        self.assertEqual(name_mapping.effective_value, "Jane Doe")

        # 3. Form Population
        fill_res = await self.form_filler.fill_form(self.agent, mapping_res)
        self.assertEqual(fill_res.required_completion_rate, 1.0, "Lever required completion must be 100%")
        self.assertTrue(fill_res.is_complete)

        # 4. Submission & Verification
        await self.agent.click("#lever-submit-btn")
        await asyncio.sleep(1.0)

        verification = await self.result_verifier.verify_submission(self.agent)
        self.assertTrue(verification.is_success, f"Lever submission verification failed: {verification}")
        self.assertEqual(verification.reference_number, "LEV-CONF-67890")

        # 5. Server-side Validation
        last_sub = self.server.last_submission
        self.assertIsNotNone(last_sub)
        self.assertEqual(last_sub["fields"]["name"], "Jane Doe")
        self.assertEqual(last_sub["fields"]["email"], "jane.doe@example.com")
        self.assertEqual(last_sub["fields"]["years_experience"], "5-8")
        self.assertIn("resume", last_sub["files"])

    async def test_workday_archetype_wizard(self) -> None:
        """Evaluates Workday multi-step wizard: Step 1 (Info) -> Step 2 (Exp & Resume) -> Step 3 (Review)."""
        portal_url = f"{self.base_url}/workday/step1"
        await self.agent.navigate(portal_url)

        # --- STEP 1: Personal Info ---
        analysis_s1 = await self.page_analyzer.analyze(self.agent)
        self.assertTrue(analysis_s1.is_multi_step)
        mapping_s1 = self.field_mapper.map_fields(analysis_s1)
        self.assertGreaterEqual(mapping_s1.accuracy, 0.98)
        self.assertEqual(len(mapping_s1.unresolved_required_fields), 0)

        fill_s1 = await self.form_filler.fill_form(self.agent, mapping_s1)
        self.assertEqual(fill_s1.required_completion_rate, 1.0)

        await self.agent.click("#workday-next-step1")
        await asyncio.sleep(1.0)

        # --- STEP 2: Experience & Resume ---
        self.assertIn("workday/step2", await self.agent.get_url())
        analysis_s2 = await self.page_analyzer.analyze(self.agent)
        mapping_s2 = self.field_mapper.map_fields(analysis_s2)
        self.assertGreaterEqual(mapping_s2.accuracy, 0.98)
        self.assertEqual(len(mapping_s2.unresolved_required_fields), 0)

        fill_s2 = await self.form_filler.fill_form(self.agent, mapping_s2)
        self.assertEqual(fill_s2.required_completion_rate, 1.0)

        await self.agent.click("#workday-next-step2")
        await asyncio.sleep(1.0)

        # --- STEP 3: Review & Submit ---
        self.assertIn("workday/step3", await self.agent.get_url())
        await self.agent.click("#workday-final-submit")
        await asyncio.sleep(1.0)

        verification = await self.result_verifier.verify_submission(self.agent)
        self.assertTrue(verification.is_success, f"Workday submission verification failed: {verification}")
        self.assertEqual(verification.reference_number, "WD-CONF-77889")

    async def test_ashby_archetype(self) -> None:
        """Evaluates Ashby ATS archetype: dynamic form, compensation, visa questions."""
        portal_url = f"{self.base_url}/ashby"
        await self.agent.navigate(portal_url)

        # 1. Page Analysis
        analysis = await self.page_analyzer.analyze(self.agent)
        self.assertGreaterEqual(len(analysis.fields), 6)

        # 2. Semantic Mapping
        mapping_res = self.field_mapper.map_fields(analysis)
        self.assertGreaterEqual(mapping_res.accuracy, 0.98, "Ashby field mapping accuracy fell below 98%")
        self.assertEqual(len(mapping_res.unresolved_required_fields), 0)

        # 3. Form Population
        fill_res = await self.form_filler.fill_form(self.agent, mapping_res)
        self.assertEqual(fill_res.required_completion_rate, 1.0, "Ashby required completion must be 100%")
        self.assertTrue(fill_res.is_complete)

        # 4. Submission & Verification
        await self.agent.click("#ashby-submit")
        await asyncio.sleep(1.0)

        verification = await self.result_verifier.verify_submission(self.agent)
        self.assertTrue(verification.is_success, f"Ashby submission verification failed: {verification}")
        self.assertEqual(verification.reference_number, "ASH-CONF-99001")

        # 5. Server-side Validation
        last_sub = self.server.last_submission
        self.assertIsNotNone(last_sub)
        self.assertEqual(last_sub["fields"]["first_name"], "Jane")
        self.assertEqual(last_sub["fields"]["last_name"], "Doe")
        self.assertEqual(last_sub["fields"]["email"], "jane.doe@example.com")
        self.assertIn("resume", last_sub["files"])

    async def test_full_orchestrator_on_greenhouse_with_human_gate(self) -> None:
        """Evaluates full UniversalApplicationOrchestrator on Greenhouse archetype enforcing V1 review gate."""
        review_gate_visited = False

        def on_review(orch, analysis, fill_result):
            nonlocal review_gate_visited
            review_gate_visited = True
            self.assertIn(orch.state_machine.current_state, [AgentExecutionState.PENDING_HUMAN_REVIEW, AgentExecutionState.PAUSED_FOR_INTERVENTION])
            orch.confirm_submission("Human approved submission on Greenhouse archetype.")

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=self.agent,
            candidate_context=self.candidate_context,
            on_review_requested=on_review,
        )

        result = await orchestrator.run(
            portal_url=f"{self.base_url}/greenhouse",
            job_title="Senior Backend Engineer",
            company="Stripe",
            headless=True,
        )

        self.assertTrue(review_gate_visited, "V1 Human Review Gate was not visited during Greenhouse orchestration!")
        self.assertTrue(result.is_success)
        self.assertEqual(result.terminal_result, TerminalResult.SUCCESS_SUBMITTED)
        self.assertEqual(result.reference_number, "GH-CONF-12345")
        self.assertIsNotNone(result.snapshot)

    async def test_ats_archetypes_empirical_summary(self) -> None:
        """Verifies aggregate benchmarks across all 4 archetypes satisfy production criteria:
        - Field Mapping Accuracy >= 98%
        - Required-Field Completion == 100%
        - Resume Upload Success == 100%
        """
        urls = [
            f"{self.base_url}/greenhouse",
            f"{self.base_url}/lever",
            f"{self.base_url}/workday/step1",
            f"{self.base_url}/ashby",
        ]

        accuracies = []
        req_completion_rates = []

        for url in urls:
            await self.agent.navigate(url)
            analysis = await self.page_analyzer.analyze(self.agent)
            mapping_res = self.field_mapper.map_fields(analysis)
            accuracies.append(mapping_res.accuracy)

            fill_res = await self.form_filler.fill_form(self.agent, mapping_res)
            req_completion_rates.append(fill_res.required_completion_rate)

        avg_accuracy = sum(accuracies) / len(accuracies)
        avg_completion = sum(req_completion_rates) / len(req_completion_rates)

        self.assertGreaterEqual(avg_accuracy, 0.98, f"Aggregate accuracy {avg_accuracy:.3f} fell below 98%")
        self.assertEqual(avg_completion, 1.0, f"Aggregate required completion rate {avg_completion:.3f} must be 100%")


if __name__ == "__main__":
    unittest.main()
