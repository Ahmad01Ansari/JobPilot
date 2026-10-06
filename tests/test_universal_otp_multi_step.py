"""
Unit tests for Universal AI Application Agent Multi-Page, OTP/2FA, and Custom Pill Radiogroups.
Verifies:
1. Detection and classification of OTP/verification code pages as TWO_FACTOR_AUTH.
2. Progression through multi-step workflows (Apply Now -> Email -> OTP -> Application Form).
3. Extraction and population of custom pill-style radio groups (e.g. Oracle JET / Workday).
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.services.automation.universal_agent.page_classifier import PageClass, PageClassifier
from app.services.automation.universal_agent.page_analyzer import (
    FormAnalysisResult,
    FormFieldInfo,
)
from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
)
from app.services.automation.universal_agent.result_verifier import VerificationResult


class TestUniversalOtpMultiStepFlow(unittest.IsolatedAsyncioTestCase):

    def test_page_classifier_detects_otp_challenge(self):
        """PageClassifier identifies verification code / OTP pages as TWO_FACTOR_AUTH."""
        cls = PageClassifier.classify(
            url="https://portal.com/apply/verification",
            title="Verification Code",
            text_content="We have sent a verification code to your email. Enter the 6-digit code below.",
            input_count=1,
            has_file_input=False,
        )
        self.assertEqual(cls, PageClass.TWO_FACTOR_AUTH)

    async def test_orchestrator_pauses_for_otp_and_resumes_to_form(self):
        """
        Simulates:
        Step 1: Email entry page (with 1 email field and Continue button).
        Step 2: OTP verification page -> pauses for TWO_FACTOR_AUTH. User resumes.
        Step 3: Main application form with custom Yes/No radio groups -> submits.
        """
        mock_agent = MagicMock()
        mock_agent.is_initialized = True
        mock_agent.initialize = AsyncMock()
        mock_agent.navigate = AsyncMock(return_value=True)
        mock_agent.get_url = AsyncMock(side_effect=[
            "https://portal.com/apply/email",       # Step 1
            "https://portal.com/apply/otp",         # Step 2: OTP screen
            "https://portal.com/apply/form",        # Step 3: Main application form
            "https://portal.com/apply/form",
            "https://portal.com/apply/confirmation",
        ])
        mock_agent.get_title = AsyncMock(return_value="Photon Career Portal")
        mock_agent.click = AsyncMock()
        mock_agent.evaluate = AsyncMock(side_effect=lambda script, *args, **kwargs: (
            {"has_errors": False, "field_errors": [], "summary_banners": []}
            if ("error" in script.lower() or "validation" in script.lower())
            else True
        ))
        mock_agent.screenshot = AsyncMock(return_value=b"fake_png")
        mock_agent.get_content = AsyncMock(return_value="<html>Application Submitted</html>")

        # Step 1: Email page
        step1_analysis = FormAnalysisResult(
            url="https://portal.com/apply/email",
            title="Candidate Email",
            fields=[
                FormFieldInfo("email", "email", "#primary-email-0", "email", "Email Address", required=True),
            ],
            submit_buttons=[],
            next_buttons=[{"selector": "button.btn-continue", "text": "Continue"}],
            is_multi_step=True,
        )

        # Step 2: OTP challenge page
        step2_analysis = FormAnalysisResult(
            url="https://portal.com/apply/otp",
            title="Verification Code",
            fields=[
                FormFieldInfo("otp", "otp", "#verification-code-0", "text", "Enter Verification Code", required=True),
            ],
            submit_buttons=[],
            next_buttons=[{"selector": "button.btn-verify", "text": "Verify"}],
            challenge_detected="TWO_FACTOR_AUTH",
            is_multi_step=True,
        )

        # Step 3: Application form with custom pill radio group
        step3_analysis = FormAnalysisResult(
            url="https://portal.com/apply/form",
            title="Application Details",
            fields=[
                FormFieldInfo("first_name", "firstName", "#firstName-15", "text", "First Name", required=True),
                FormFieldInfo("last_name", "lastName", "#lastName-14", "text", "Last Name", required=True),
                FormFieldInfo(
                    "relocate",
                    "relocate",
                    "#relocate-group",
                    "radio_group",
                    "Willing to Relocate",
                    required=True,
                    options=[{"value": "No", "label": "No"}, {"value": "Yes", "label": "Yes"}],
                ),
            ],
            submit_buttons=[{"selector": "button.btn-submit", "text": "SUBMIT"}],
            next_buttons=[],
            is_multi_step=False,
        )

        mock_analyzer = MagicMock()
        mock_analyzer.analyze = AsyncMock(side_effect=[
            step1_analysis,
            step1_analysis,  # re-scan step 1
            step2_analysis,  # step 2 (OTP)
            step2_analysis,  # post-resume
            step3_analysis,  # step 3 (Form)
            step3_analysis,  # re-scan step 3
        ])

        orchestrator = UniversalApplicationOrchestrator(
            browser_agent=mock_agent,
            page_analyzer=mock_analyzer,
        )

        # Verify submission mock
        orchestrator.result_verifier.verify_submission = AsyncMock(return_value=VerificationResult(
            status="SUCCESS",
            is_success=True,
            confirmation_header="Thank you for applying",
        ))

        # Auto-resolve OTP when intervention is triggered
        def on_intervention(req):
            if req.reason == InterventionReason.TWO_FACTOR_AUTH:
                orchestrator.intervention_manager.resolve_resume()

        orchestrator.intervention_manager.add_listener(on_intervention)

        # Auto-confirm pre-submission review
        def on_review(orch, analysis, fill_res):
            orch.confirm_submission()

        orchestrator.on_review_requested = on_review

        # Run
        result = await orchestrator.run(
            portal_url="https://portal.com/apply/email",
            job_title="RPA Developer",
            company="Photon",
        )

        # Assertions
        # 1. Clicked continue on step 1
        self.assertTrue(any(call.args and call.args[0] == "button.btn-continue" for call in mock_agent.click.mock_calls))
        # 2. Clicked submit on final form
        mock_agent.click.assert_any_call("button.btn-submit")
        # 3. Successful submission
        self.assertTrue(result.is_success)
        self.assertEqual(orchestrator.state_machine.terminal_result, TerminalResult.SUCCESS_SUBMITTED)


if __name__ == "__main__":
    unittest.main()
