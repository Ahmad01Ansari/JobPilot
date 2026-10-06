"""Test verifying that Universal Application Agent navigates from Job Overview pages to Form pages."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from app.services.automation.universal_agent.page_analyzer import FormAnalysisResult, FormFieldInfo, PageAnalyzer
from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator
from app.services.automation.universal_agent.state_machine import AgentExecutionState, TerminalResult
from app.services.automation.universal_agent.result_verifier import VerificationResult


class TestOverviewPageNavigation(unittest.IsolatedAsyncioTestCase):
    async def test_page_analyzer_distinguishes_apply_now_from_submit(self):
        analyzer = PageAnalyzer()
        mock_agent = MagicMock()
        mock_agent.get_url = AsyncMock(return_value="https://tangentia.catsone.com/careers/9463/jobs/16855744")
        mock_agent.get_title = AsyncMock(return_value="RPA Developer")
        mock_agent.get_content = AsyncMock(return_value="<html>...</html>")

        # Mock page.evaluate returning 0 fields and an Apply Now link
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={
            "challenge_detected": None,
            "is_multi_step": False,
            "step_indicator": None,
            "fields": [],
            "submit_buttons": [],
            "next_buttons": [],
            "apply_now_buttons": [{"selector": 'a[href*="/apply"]', "text": "Apply Now"}],
        })
        mock_agent.page = mock_page

        result = await analyzer.analyze(mock_agent)
        self.assertEqual(len(result.fields), 0)
        self.assertEqual(len(result.submit_buttons), 0)
        self.assertEqual(len(result.apply_now_buttons), 1)
        self.assertEqual(result.apply_now_buttons[0]["text"], "Apply Now")

    async def test_orchestrator_clicks_apply_now_when_on_overview_page(self):
        # Setup mocks
        mock_agent = MagicMock()
        mock_agent.is_initialized = True
        mock_agent.initialize = AsyncMock()
        mock_agent.navigate = AsyncMock(return_value=True)
        mock_agent.get_url = AsyncMock(side_effect=[
            "https://portal.com/jobs/123",        # Step 1: overview
            "https://portal.com/jobs/123",        # Inside step 1
            "https://portal.com/jobs/123/apply",  # Step 2: form page
            "https://portal.com/jobs/123/apply",  # Inside step 2
            "https://portal.com/jobs/123/apply",  # Post-submit
        ])
        mock_agent.get_title = AsyncMock(return_value="Job Portal")
        mock_agent.click = AsyncMock()
        mock_agent.screenshot = AsyncMock(return_value=b"fake_png")
        mock_agent.get_content = AsyncMock(return_value="<html>Success</html>")

        # Mock analyzer: Step 1 returns 0 fields + Apply Now; Step 2 returns form fields + Submit Application
        mock_analyzer = MagicMock()
        overview_result = FormAnalysisResult(
            url="https://portal.com/jobs/123",
            title="Overview",
            fields=[],
            submit_buttons=[],
            apply_now_buttons=[{"selector": "a.btn-apply", "text": "Apply Now"}],
        )
        form_result = FormAnalysisResult(
            url="https://portal.com/jobs/123/apply",
            title="Application Form",
            fields=[
                FormFieldInfo("first_name", "first_name", "#first_name", "text", "First Name", required=True),
                FormFieldInfo("email", "email", "#email", "email", "Email", required=True),
            ],
            submit_buttons=[{"selector": "#submit-btn", "text": "Submit Application"}],
            apply_now_buttons=[],
        )
        mock_analyzer.analyze = AsyncMock(side_effect=[overview_result, form_result])

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=mock_agent,
            page_analyzer=mock_analyzer,
        )

        # Mock verification to certify success
        orchestrator.result_verifier.verify_submission = AsyncMock(return_value=VerificationResult(
            status="SUCCESS",
            is_success=True,
            confirmation_header="Thank you for applying",
        ))

        # Auto-confirm review when requested
        def on_review(orch, analysis, fill_res):
            orch.confirm_submission()

        orchestrator.on_review_requested = on_review

        res = await orchestrator.run(
            portal_url="https://portal.com/jobs/123",
            job_title="Software Engineer",
            company="Tangentia",
        )

        # Assertions
        # 1. Agent clicked the 'Apply Now' button on step 1 to reach form
        mock_agent.click.assert_any_call("a.btn-apply")

        # 2. Agent clicked the '#submit-btn' on step 2 to submit
        mock_agent.click.assert_any_call("#submit-btn")

        # 3. Application completed successfully
        self.assertTrue(res.is_success)
        self.assertEqual(orchestrator.state_machine.terminal_result, TerminalResult.SUCCESS_SUBMITTED)

    async def test_orchestrator_handles_submit_as_entry_button_and_form_submit(self):
        """Verifies that 'Submit Application' on a 0-field landing page acts as an entry button,
        and 'SUBMIT' on a form page acts as the final submission button."""
        mock_agent = MagicMock()
        mock_agent.is_initialized = True
        mock_agent.initialize = AsyncMock()
        mock_agent.navigate = AsyncMock(return_value=True)
        mock_agent.get_url = AsyncMock(side_effect=[
            "https://naukri.com/job-123",
            "https://naukri.com/job-123",
            "https://facileconsulting.com/jobs/rpa-developer",
            "https://facileconsulting.com/jobs/rpa-developer",
            "https://facileconsulting.com/jobs/rpa-developer",
        ])
        mock_agent.get_title = AsyncMock(return_value="RPA Developer")
        mock_agent.click = AsyncMock()
        mock_agent.screenshot = AsyncMock(return_value=b"fake_png")
        mock_agent.get_content = AsyncMock(return_value="<html>Success</html>")

        # Step 1: Landing page with 0 fields, entry button saying "Submit Application" / "Apply on company site"
        overview_result = FormAnalysisResult(
            url="https://naukri.com/job-123",
            title="Naukri Job",
            fields=[],
            submit_buttons=[],
            apply_now_buttons=[{"selector": "button#company-site-button", "text": "Apply on company website"}],
        )

        # Step 2: Form page with 4 fields and "SUBMIT" button
        form_result = FormAnalysisResult(
            url="https://facileconsulting.com/jobs/rpa-developer",
            title="Apply for this position",
            fields=[
                FormFieldInfo("name", "name", "#name", "text", "Full Name", required=True),
                FormFieldInfo("email", "email", "#email", "email", "Email", required=True),
            ],
            submit_buttons=[{"selector": "button.btn-submit", "text": "SUBMIT"}],
            next_buttons=[],
            apply_now_buttons=[],
        )

        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(side_effect=[overview_result, form_result])

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=mock_agent,
            page_analyzer=mock_analyzer,
        )

        orchestrator.result_verifier.verify_submission = AsyncMock(return_value=VerificationResult(
            status="SUCCESS",
            is_success=True,
            confirmation_header="Application Received",
        ))

        orchestrator.on_review_requested = lambda orch, analysis, fill_res: orch.confirm_submission()

        res = await orchestrator.run(
            portal_url="https://naukri.com/job-123",
            job_title="RPA Developer",
            company="Facile Consulting",
        )

        # Assertions:
        # 1. Clicked entry button on Step 1
        mock_agent.click.assert_any_call("button#company-site-button")
        # 2. Clicked SUBMIT button on Step 2
        mock_agent.click.assert_any_call("button.btn-submit")
        # 3. Application succeeded
        self.assertTrue(res.is_success)
        self.assertEqual(orchestrator.state_machine.terminal_result, TerminalResult.SUCCESS_SUBMITTED)


if __name__ == "__main__":
    unittest.main()
