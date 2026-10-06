'''
Unit Tests for NaukriSafetyGate & Human Review Engine (Phase 11)
Validates review summary generation, formatted table output, decision routing (APPROVE, DISCARD, MANUAL_REQUIRED),
safe fallback on non-interactive inputs, and NaukriApplier pipeline orchestration.
'''

import unittest
from unittest.mock import MagicMock, patch

from modules.models import Job
from platforms.naukri.safety_gate import (
    NaukriSafetyGate,
    ApplicationReviewSummary,
    SafetyGateResult,
)
from platforms.naukri.applier import NaukriApplier


class TestNaukriSafetyGate(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver

        self.sample_job = Job(
            platform="naukri",
            job_id="naukri_test_123",
            title="Senior RPA Developer",
            company="Enterprise Automation Corp",
            location="Noida, India",
            source_url="https://www.naukri.com/job-listings-123",
        )

        self.sample_fields = [
            {
                "field": "What is your current CTC in Lacs?",
                "type": "text",
                "value": "3.50",
                "source": "calculation",
                "confidence": 0.98,
                "success": True,
            },
            {
                "field": "Expected CTC in Lacs",
                "type": "text",
                "value": "5.50",
                "source": "calculation",
                "confidence": 0.98,
                "success": True,
            },
            {
                "field": "Notice period in days",
                "type": "text",
                "value": "30",
                "source": "profile",
                "confidence": 1.0,
                "success": True,
            },
            {
                "field": "Experience in Automation Anywhere",
                "type": "text",
                "value": "2",
                "source": "rule",
                "confidence": 0.95,
                "success": True,
            },
        ]

    def test_build_summary_parameters(self):
        gate = NaukriSafetyGate(browser=self.mock_browser, pause_before_submit=True)
        summary = gate.build_summary(
            job=self.sample_job,
            filled_fields=self.sample_fields,
            resume_path="/dummy/path/resume.pdf",
        )

        self.assertEqual(summary.job_id, "naukri_test_123")
        self.assertEqual(summary.job_title, "Senior RPA Developer")
        self.assertEqual(summary.company, "Enterprise Automation Corp")
        self.assertIn("3.50", summary.current_ctc)
        self.assertIn("5.50", summary.expected_ctc)
        self.assertIn("30", summary.notice_period)
        self.assertEqual(len(summary.filled_fields), 4)

    def test_build_summary_warnings_on_low_confidence(self):
        gate = NaukriSafetyGate(browser=self.mock_browser, pause_before_submit=True)
        low_conf_field = [
            {
                "field": "Describe your niche bot architecture",
                "type": "textarea",
                "value": "Complex pipelines",
                "source": "llm",
                "confidence": 0.60,  # Low confidence
                "success": True,
            }
        ]
        summary = gate.build_summary(
            job=self.sample_job,
            filled_fields=low_conf_field,
            resume_path="/nonexistent/resume_missing.pdf",
        )
        self.assertTrue(any("Low confidence LLM" in w for w in summary.warnings))
        self.assertTrue(any("not found on disk" in w for w in summary.warnings))

    def test_format_table_renders_all_sections(self):
        gate = NaukriSafetyGate(browser=self.mock_browser, pause_before_submit=True)
        summary = gate.build_summary(
            job=self.sample_job,
            filled_fields=self.sample_fields,
            resume_path="/dummy/resume.pdf",
        )
        output = summary.format_table()

        self.assertIn("APPLICATION SAFETY GATE REVIEW", output)
        self.assertIn("Senior RPA Developer", output)
        self.assertIn("Enterprise Automation Corp", output)
        self.assertIn("Current CTC", output)
        self.assertIn("Expected CTC", output)
        self.assertIn("Notice Period", output)
        self.assertIn("FILLED QUESTIONS & ANSWERS", output)
        self.assertIn("What is your current CTC in Lacs?", output)

    def test_review_approval_flow(self):
        # Handler returns APPROVE
        gate = NaukriSafetyGate(
            browser=self.mock_browser,
            pause_before_submit=True,
            review_handler=lambda summary: "APPROVE",
        )
        res = gate.review(job=self.sample_job, filled_fields=self.sample_fields)
        self.assertEqual(res.decision, "APPROVE")
        self.assertTrue(res.approved)

    def test_review_discard_flow(self):
        # Handler returns DISCARD
        gate = NaukriSafetyGate(
            browser=self.mock_browser,
            pause_before_submit=True,
            review_handler=lambda summary: "DISCARD",
        )
        res = gate.review(job=self.sample_job, filled_fields=self.sample_fields)
        self.assertEqual(res.decision, "DISCARD")
        self.assertFalse(res.approved)

    def test_review_manual_flow(self):
        # Handler returns MANUAL_REQUIRED
        gate = NaukriSafetyGate(
            browser=self.mock_browser,
            pause_before_submit=True,
            review_handler=lambda summary: "MANUAL_REQUIRED",
        )
        res = gate.review(job=self.sample_job, filled_fields=self.sample_fields)
        self.assertEqual(res.decision, "MANUAL_REQUIRED")
        self.assertFalse(res.approved)

    def test_review_safe_fallback_on_eof_input(self):
        # When no handler and stdin raises EOFError (non-interactive)
        gate = NaukriSafetyGate(browser=self.mock_browser, pause_before_submit=True)
        with patch("builtins.input", side_effect=EOFError):
            res = gate.review(job=self.sample_job, filled_fields=self.sample_fields)
            # Safe default must NOT auto-submit; route to MANUAL_REQUIRED
            self.assertEqual(res.decision, "MANUAL_REQUIRED")
            self.assertFalse(res.approved)

    def test_naukri_applier_questionnaire_review_flow(self):
        mock_flow = MagicMock()
        mock_flow.find_apply_button.return_value = MagicMock()
        mock_flow.detect_apply_button_type.return_value = "DIRECT"
        mock_flow.detect_flow_after_click.return_value = ("QUESTIONNAIRE", "Screening modal")

        mock_form = MagicMock()
        mock_form.fill_form.return_value = {
            "status": "READY_TO_SUBMIT",
            "filled_fields": self.sample_fields,
        }

        mock_gate = MagicMock()
        mock_gate.review.return_value = SafetyGateResult(
            decision="APPROVE",
            summary=MagicMock(),
            approved=True,
        )

        mock_submitter = MagicMock()
        mock_submitter.submit_application.return_value = (True, "CONFIRMED_SUBMITTED")
        mock_tracker = MagicMock()

        applier = NaukriApplier(

            browser=self.mock_browser,
            form=mock_form,
            safety_gate=mock_gate,
            submitter=mock_submitter,
            flow_detector=mock_flow,
            tracker=mock_tracker,
        )

        result = applier.apply_to_job(self.sample_job)
        self.assertEqual(result["status"], "SUBMITTED")
        mock_gate.review.assert_called_once()
        mock_submitter.submit_application.assert_called_once_with(self.sample_job)
        mock_tracker.record_state.assert_any_call(self.sample_job, "APPLYING")


    def test_naukri_applier_discard_during_review(self):
        mock_flow = MagicMock()
        mock_flow.find_apply_button.return_value = MagicMock()
        mock_flow.detect_apply_button_type.return_value = "DIRECT"
        mock_flow.detect_flow_after_click.return_value = ("QUESTIONNAIRE", "Screening modal")

        mock_form = MagicMock()
        mock_form.fill_form.return_value = {
            "status": "READY_TO_SUBMIT",
            "filled_fields": self.sample_fields,
        }

        mock_gate = MagicMock()
        mock_gate.review.return_value = SafetyGateResult(
            decision="DISCARD",
            summary=MagicMock(),
            approved=False,
        )

        mock_tracker = MagicMock()

        applier = NaukriApplier(
            browser=self.mock_browser,
            form=mock_form,
            safety_gate=mock_gate,
            flow_detector=mock_flow,
            tracker=mock_tracker,
        )

        result = applier.apply_to_job(self.sample_job)
        self.assertEqual(result["status"], "SKIPPED")
        mock_flow.close_modal_if_open.assert_called_once()
        mock_tracker.record_state.assert_any_call(self.sample_job, "SKIPPED", reason="Discarded during human review")


if __name__ == "__main__":
    unittest.main()
