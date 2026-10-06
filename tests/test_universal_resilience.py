"""
Unit and integration test suite for Universal Application Agent Real-World Resilience.
Verifies failure recovery, popup management, page health classification, iframe inspection,
validation error detection, checkpoint recovery, and duplicate application prevention.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.automation.universal_agent.checkpoint_manager import CheckpointManager, ExecutionCheckpoint
from app.services.automation.universal_agent.frame_resolver import FrameResolver, FrameInfo
from app.services.automation.universal_agent.page_classifier import PageClassifier, PageHealthChecker, PageClass, PageHealthStatus
from app.services.automation.universal_agent.popup_manager import PopupManager, PopupClassification
from app.services.automation.universal_agent.recovery_manager import RecoveryManager, FailureCategory
from app.services.automation.universal_agent.validation_resolver import ValidationResolver, FormFieldError
from app.services.automation.universal_agent.result_verifier import ResultVerifier, VerificationResult
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator


class TestUniversalAgentResilience(unittest.IsolatedAsyncioTestCase):
    """Failure-injection and resilience verification suite."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.recovery_mgr = RecoveryManager(run_id="test_run", artifacts_dir=self.temp_dir)
        self.checkpoint_mgr = CheckpointManager(storage_dir=self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_recovery_manager_exception_classification(self) -> None:
        """Verifies taxonomy classification of diverse browser and network exceptions."""
        # 1. CAPTCHA / Cloudflare
        exc = Exception("Cloudflare Turnstile verification required")
        cat = self.recovery_mgr.classify_exception(exc)
        self.assertEqual(cat, FailureCategory.CAPTCHA_REQUIRED)

        # 2. Authentication / Session expiration
        exc = Exception("401 Unauthorized: Session expired. Please log in.")
        cat = self.recovery_mgr.classify_exception(exc)
        self.assertEqual(cat, FailureCategory.AUTH_REQUIRED)

        # 3. Element obscuration by modal
        exc = Exception("Element is not clickable at point (100, 200) because another element obscures it")
        cat = self.recovery_mgr.classify_exception(exc)
        self.assertEqual(cat, FailureCategory.ELEMENT_NOT_INTERACTABLE)

        # 4. Element not found
        exc = Exception("waiting for selector '#submit-btn' failed: timeout 5000ms")
        cat = self.recovery_mgr.classify_exception(exc)
        self.assertEqual(cat, FailureCategory.ELEMENT_NOT_FOUND)

        # 5. Browser disconnect / Target closed
        exc = Exception("Target page, context or browser has been closed")
        cat = self.recovery_mgr.classify_exception(exc)
        self.assertEqual(cat, FailureCategory.BROWSER_ERROR)

    def test_recovery_manager_retry_budgets_and_exhaustion(self) -> None:
        """Verifies retry budgets prevent infinite loops and enforce non-retryable categories."""
        op_key = "click_next"
        # Transient errors allow 3 retries
        self.assertTrue(self.recovery_mgr.can_retry(op_key, FailureCategory.TRANSIENT))
        self.recovery_mgr.record_attempt(op_key, FailureCategory.TRANSIENT)
        self.assertTrue(self.recovery_mgr.can_retry(op_key, FailureCategory.TRANSIENT))
        self.recovery_mgr.record_attempt(op_key, FailureCategory.TRANSIENT)
        self.assertTrue(self.recovery_mgr.can_retry(op_key, FailureCategory.TRANSIENT))
        self.recovery_mgr.record_attempt(op_key, FailureCategory.TRANSIENT)
        # 4th attempt exceeds max budget of 3
        self.assertFalse(self.recovery_mgr.can_retry(op_key, FailureCategory.TRANSIENT))

        # CAPTCHA allows 0 automatic retries
        self.assertFalse(self.recovery_mgr.can_retry("solve_captcha", FailureCategory.CAPTCHA_REQUIRED))

        # Resetting budget restores retryability
        self.recovery_mgr.reset_budget(op_key)
        self.assertTrue(self.recovery_mgr.can_retry(op_key, FailureCategory.TRANSIENT))

    def test_page_classifier_heuristics(self) -> None:
        """Verifies multi-signal page classification across diverse portal states."""
        # 1. 404 / 500 Error
        cls = PageClassifier.classify("https://ats.example.com/job/404", "404 Not Found - Company", "The requested page was not found")
        self.assertEqual(cls, PageClass.ERROR)

        # 2. Maintenance page
        cls = PageClassifier.classify("https://ats.example.com/apply", "Scheduled Site Maintenance", "Our portal is under maintenance")
        self.assertEqual(cls, PageClass.MAINTENANCE)

        # 3. Security Check
        cls = PageClassifier.classify("https://jobs.example.com/verify", "Security Check", "Please verify you are human to proceed")
        self.assertEqual(cls, PageClass.CAPTCHA)

        # 4. Success confirmation
        cls = PageClassifier.classify("https://jobs.example.com/thank-you", "Confirmation", "Thank you for applying! Your application has been received.")
        self.assertEqual(cls, PageClass.APPLICATION_SUCCESS)

        # 5. Form page
        cls = PageClassifier.classify("https://jobs.example.com/apply/123", "Application Form", "Enter your personal details", input_count=8)
        self.assertEqual(cls, PageClass.APPLICATION_FORM)

    async def test_popup_manager_benign_dismissal(self) -> None:
        """Verifies benign cookie banners and newsletter modals are safely identified and dismissed."""
        # Mock agent evaluating cookie overlay
        mock_agent = MagicMock()
        mock_agent.evaluate = AsyncMock(return_value={
            "text": "We use cookies to enhance your experience. Please accept our cookie policy.",
            "buttons": [{"idx": 0, "text": "Accept All", "tag": "button"}],
            "tagName": "div",
            "id": "onetrust-banner-sdk",
        })

        dismissed, detected = await PopupManager.scan_and_dismiss_popups(mock_agent)
        self.assertTrue(dismissed)
        self.assertIsNotNone(detected)
        self.assertEqual(detected.classification, PopupClassification.BENIGN)

    async def test_popup_manager_destructive_protection(self) -> None:
        """Verifies destructive popups (e.g. discard application) are NEVER automatically clicked."""
        mock_agent = MagicMock()
        mock_agent.evaluate = AsyncMock(return_value={
            "text": "Are you sure you want to discard your application? All entered data will be deleted.",
            "buttons": [{"idx": 0, "text": "Discard Application", "tag": "button"}],
            "tagName": "div",
            "id": "discard-modal",
        })

        dismissed, detected = await PopupManager.scan_and_dismiss_popups(mock_agent)
        self.assertFalse(dismissed)
        self.assertIsNotNone(detected)
        self.assertEqual(detected.classification, PopupClassification.DESTRUCTIVE)

    async def test_validation_resolver_error_detection(self) -> None:
        """Verifies active form validation errors are extracted with field selectors and error text."""
        mock_agent = MagicMock()
        mock_agent.evaluate = AsyncMock(return_value={
            "field_errors": [
                {
                    "field_identifier": "phone",
                    "error_text": "Please enter a valid 10-digit phone number.",
                    "selector": "#phone",
                    "input_type": "tel",
                }
            ],
            "summary_banners": ["Please correct the highlighted errors before submitting."],
        })

        report = await ValidationResolver.inspect_validation_errors(mock_agent)
        self.assertTrue(report.has_errors)
        self.assertEqual(len(report.field_errors), 1)
        self.assertEqual(report.field_errors[0].field_identifier, "phone")
        self.assertEqual(report.field_errors[0].error_text, "Please enter a valid 10-digit phone number.")
        self.assertEqual(len(report.summary_banners), 1)

    async def test_frame_resolver_application_frame_discovery(self) -> None:
        """Verifies detection of application forms inside nested iframes."""
        mock_agent = MagicMock()
        mock_agent.evaluate = AsyncMock(return_value=[
            {
                "frame_index": 0,
                "name": "google_tag_manager",
                "frame_id": "gtm_frame",
                "src": "https://googletagmanager.com/ns.html",
                "input_count": 0,
                "has_form": False,
                "is_accessible": True,
                "selector": "#gtm_frame",
            },
            {
                "frame_index": 1,
                "name": "greenhouse_application_frame",
                "frame_id": "grnhse_iframe",
                "src": "https://boards.greenhouse.io/embed/job_app",
                "input_count": 6,
                "has_form": True,
                "is_accessible": True,
                "selector": "#grnhse_iframe",
            },
        ])

        app_frame = await FrameResolver.find_application_frame(mock_agent)
        self.assertIsNotNone(app_frame)
        self.assertEqual(app_frame.frame_id, "grnhse_iframe")
        self.assertEqual(app_frame.input_count, 6)

    def test_checkpoint_manager_persistence_and_restore(self) -> None:
        """Verifies saving, loading, and cleaning execution checkpoints."""
        cp = ExecutionCheckpoint(
            application_id=42,
            job_id="job_9981",
            current_url="https://ats.example.com/apply/step2",
            page_role="APPLICATION_STEP",
            execution_state="FILLING_FORM",
            current_step=2,
            completed_steps=["step_1"],
            facts_used={"user.email": "test@example.com"},
        )

        saved_path = self.checkpoint_mgr.save_checkpoint(cp)
        self.assertTrue(os.path.exists(saved_path))

        loaded = self.checkpoint_mgr.load_checkpoint("job_9981")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.job_id, "job_9981")
        self.assertEqual(loaded.current_step, 2)
        self.assertEqual(loaded.facts_used["user.email"], "test@example.com")

        self.checkpoint_mgr.clear_checkpoint("job_9981")
        self.assertIsNone(self.checkpoint_mgr.load_checkpoint("job_9981"))

    def test_submission_status_unknown_transitions(self) -> None:
        """Verifies ambiguous post-submit states yield SUBMISSION_STATUS_UNKNOWN without auto-retry."""
        sm = UniversalApplicationStateMachine()
        verifier = ResultVerifier()

        ambiguous_res = VerificationResult(
            status="UNKNOWN",
            is_success=False,
            details={"url": "https://ats.example.com/status", "title": "Portal Status"},
        )

        verifier.verify_and_update_state(sm, ambiguous_res)
        self.assertEqual(sm.terminal_result, TerminalResult.SUBMISSION_STATUS_UNKNOWN)
        self.assertFalse(sm.is_success)

    async def test_duplicate_application_prevention(self) -> None:
        """Verifies orchestrator halts immediately if an application record has already been submitted."""
        mock_agent = MagicMock()
        mock_agent.is_initialized = True

        mock_app = MagicMock()
        mock_app.status = "SUBMITTED"

        with patch("app.services.application_service.ApplicationService.get_by_job_id", return_value=mock_app):
            orch = UniversalApplicationOrchestrator(
                browser_agent=mock_agent,
                checkpoint_manager=self.checkpoint_mgr,
            )
            result = await orch.run(
                portal_url="https://example.com/job/123",
                job_title="Software Engineer",
                company="Acme Corp",
                job_id=123,
            )

            self.assertEqual(result.terminal_result, TerminalResult.SKIPPED_DISQUALIFIED)
            self.assertFalse(result.is_success)
            self.assertIn("Duplicate prevented", orch.state_machine.terminal_message)


if __name__ == "__main__":
    unittest.main()
