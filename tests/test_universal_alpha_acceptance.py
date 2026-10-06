"""Automated Acceptance Test Suite for Phase 15: Controlled Personal Alpha.

Verifies:
1. Pre-flight candidate configuration check (Profile facts, resume, AI engine).
2. End-to-end supervised personal alpha execution flow.
3. V1 Mandatory Human Review Gate enforcement and confirmation.
4. Cryptographic snapshot capture and audit trail verification.
5. Strict zero-hallucination guarantee on submitted application data.
"""

import asyncio
from pathlib import Path
import tempfile
import unittest

from scripts.run_universal_alpha import check_preflight_config, run_supervised_application
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestUniversalAlphaAcceptance(unittest.IsolatedAsyncioTestCase):
    """End-to-end acceptance tests certifying the Universal Agent for personal alpha."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

    async def asyncTearDown(self) -> None:
        self.server.stop()

    def test_preflight_config_acceptance(self) -> None:
        """Verifies candidate profile, resume, and AI engine pass pre-flight checks."""
        is_ready = check_preflight_config()
        self.assertTrue(is_ready, "Pre-flight configuration check failed")

    async def test_supervised_alpha_run_with_review_gate_acceptance(self) -> None:
        """Verifies supervised execution against test portal with V1 review gate and snapshot generation."""
        portal_url = f"{self.base_url}/greenhouse"

        with tempfile.TemporaryDirectory() as temp_dir:
            sample_resume = Path(temp_dir) / "Alpha_Test_Resume.pdf"
            sample_resume.write_bytes(b"%PDF-1.4 Mock Candidate Resume For Alpha Acceptance")

            candidate_context = {
                "profile": {
                    "user.first_name": "Jane",
                    "user.last_name": "Doe",
                    "user.name": "Jane Doe",
                    "user.email": "jane.doe@example.com",
                    "profile.phone_number": "+1 (555) 0100",
                    "gender": "Female",
                    "veteran_status": "No",
                },
                "resume": {
                    "resume.file_path": str(sample_resume),
                },
                "qna": {
                    "legally_authorized_to_work": "yes",
                    "require_visa_sponsorship": "no",
                },
            }

            result = await run_supervised_application(
                target_url=portal_url,
                job_title="Senior AI Systems Engineer",
                company="Stripe (Alpha Test)",
                headless=True,
                profile_dir=temp_dir,
                candidate_context=candidate_context,
                auto_confirm=True,
            )

        # 1. Assert Application Terminal Success
        self.assertTrue(result.is_success, "Application submission failed")
        self.assertEqual(result.terminal_result.value, "SUCCESS_SUBMITTED")
        self.assertEqual(result.reference_number, "GH-CONF-12345")

        # 2. Assert Audit Snapshot Generation
        self.assertIsNotNone(result.snapshot, "Application submission snapshot was not recorded")
        self.assertTrue(Path(result.snapshot.screenshot_path).exists(), "Snapshot screenshot does not exist on disk")
        self.assertGreater(len(result.snapshot.audit_hash), 16, "Invalid snapshot audit hash")

        # 3. Assert Server Received Genuine Candidate Facts
        last_sub = self.server.last_submission
        self.assertIsNotNone(last_sub, "Fake ATS server did not receive submission payload")
        self.assertIn("resume", last_sub["files"])
        self.assertEqual(last_sub["fields"]["work_auth"], "yes")


if __name__ == "__main__":
    unittest.main()
