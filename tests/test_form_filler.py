"""Unit tests for Hybrid FormFiller and Native FileUploader."""

import os
from pathlib import Path
import tempfile
import unittest

from app.services.automation.universal_agent import (
    FileUploader,
    FormFiller,
    PageAnalyzer,
    SemanticFieldMapper,
)
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestFormFillerAndFileUploader(unittest.IsolatedAsyncioTestCase):
    """Verifies deterministic Playwright filling, option selection, file attachment, and required-field gating."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)

        self.analyzer = PageAnalyzer()
        self.file_uploader = FileUploader()
        self.form_filler = FormFiller(file_uploader=self.file_uploader)

        # Create dummy sample resume file
        self.sample_resume = Path(self.temp_dir.name) / "sample_resume.pdf"
        self.sample_resume.write_bytes(b"%PDF-1.4 mock resume content for automated test suite")

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_file_uploader_validation_and_attachment(self) -> None:
        """Verifies file validation rules and successful DOM attachment."""
        # 1. Validation checks
        valid, err = self.file_uploader.validate_file("")
        self.assertFalse(valid)
        self.assertIn("empty", err.lower())

        valid, err = self.file_uploader.validate_file("non_existent_file.pdf")
        self.assertFalse(valid)
        self.assertIn("does not exist", err.lower())

        invalid_ext = Path(self.temp_dir.name) / "malicious.exe"
        invalid_ext.write_bytes(b"bad")
        valid, err = self.file_uploader.validate_file(str(invalid_ext))
        self.assertFalse(valid)
        self.assertIn("unsupported file extension", err.lower())

        valid, err = self.file_uploader.validate_file(str(self.sample_resume))
        self.assertTrue(valid)
        self.assertIsNone(err)

        # 2. Upload file to /standard-job
        await self.agent.navigate(f"{self.base_url}/standard-job")
        success, err = await self.file_uploader.upload_file(
            agent=self.agent,
            selector="#resume_upload",
            file_path=str(self.sample_resume),
        )
        self.assertTrue(success, f"Upload should succeed: {err}")
        self.assertIsNone(err)

        # 3. Verify DOM has file attached
        is_attached = await self.file_uploader.verify_upload(self.agent, "#resume_upload")
        self.assertTrue(is_attached)

    async def test_end_to_end_standard_job_form_fill(self) -> None:
        """Verifies 100% required-field completion and accurate population on standard job application."""
        # 1. Navigate and analyze
        await self.agent.navigate(f"{self.base_url}/standard-job")
        analysis = await self.analyzer.analyze(self.agent)
        self.assertEqual(len(analysis.fields), 12)

        # 2. Map fields using candidate facts
        candidate_context = {
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

        mapper = SemanticFieldMapper(candidate_context=candidate_context)
        mapping_result = mapper.map_fields(analysis)
        self.assertEqual(mapping_result.resolved_count, 12)

        # 3. Fill form
        fill_result = await self.form_filler.fill_form(self.agent, mapping_result)

        # 4. Assert 100% Required Field Completion
        self.assertTrue(fill_result.is_complete)
        self.assertEqual(fill_result.required_completion_rate, 1.0)
        self.assertEqual(fill_result.required_fields_filled, 8)
        self.assertEqual(fill_result.filled_fields, 12)
        self.assertEqual(len(fill_result.failed_fields), 0)

        # 5. Verify filled values in browser DOM directly
        first_name_val = await self.agent.evaluate("document.querySelector('#first_name').value")
        self.assertEqual(first_name_val, "Jane")

        last_name_val = await self.agent.evaluate("document.querySelector('#last_name').value")
        self.assertEqual(last_name_val, "Doe")

        email_val = await self.agent.evaluate("document.querySelector('#email').value")
        self.assertEqual(email_val, "jane.doe@example.com")

        phone_val = await self.agent.evaluate("document.querySelector('#phone').value")
        self.assertEqual(phone_val, "+1 (555) 000-0000")

        work_auth_checked = await self.agent.evaluate("document.querySelector(\"input[name='work_auth'][value='yes']\").checked")
        self.assertTrue(work_auth_checked)

        visa_checked = await self.agent.evaluate("document.querySelector(\"input[name='visa_sponsorship'][value='no']\").checked")
        self.assertTrue(visa_checked)

        exp_val = await self.agent.evaluate("document.querySelector('#years_experience').value")
        self.assertEqual(exp_val, "5-8")

        has_resume = await self.file_uploader.verify_upload(self.agent, "#resume_upload")
        self.assertTrue(has_resume)

    async def test_incomplete_required_fields_gating(self) -> None:
        """Verifies that missing required fields result in is_complete=False and completion rate < 1.0."""
        await self.agent.navigate(f"{self.base_url}/standard-job")
        analysis = await self.analyzer.analyze(self.agent)

        # Provide candidate context missing email and visa sponsorship
        partial_context = {
            "profile": {
                "user.first_name": "Jane",
                "user.last_name": "Doe",
            }
        }

        mapper = SemanticFieldMapper(candidate_context=partial_context)
        mapping_result = mapper.map_fields(analysis)

        fill_result = await self.form_filler.fill_form(self.agent, mapping_result)

        self.assertFalse(fill_result.is_complete)
        self.assertLess(fill_result.required_completion_rate, 1.0)
        self.assertIn("phone", fill_result.failed_fields)
