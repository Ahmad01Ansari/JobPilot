"""Unit tests for PageAnalyzer against FakeATSServer."""

import tempfile
import unittest

from app.services.automation.universal_agent import PageAnalyzer
from app.services.automation.universal_agent.browser_agent import StagehandBrowserAgent, UniversalSessionManager
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestPageAnalyzer(unittest.IsolatedAsyncioTestCase):
    """Verifies generic DOM parsing, field identification, file inputs, and security challenge detection."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)
        await self.agent.initialize(headless=True)
        self.analyzer = PageAnalyzer()

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_standard_job_form_analysis(self) -> None:
        await self.agent.navigate(f"{self.base_url}/standard-job")
        result = await self.analyzer.analyze(self.agent)

        self.assertIn("Acme Corp", result.title)
        self.assertIsNone(result.challenge_detected)
        self.assertFalse(result.is_multi_step)

        # 1. Total logical fields must equal 12
        self.assertEqual(len(result.fields), 12)

        # 2. Required fields must equal 8
        required_fields = result.get_required_fields()
        self.assertEqual(len(required_fields), 8)

        # 3. File upload field
        self.assertEqual(len(result.file_upload_fields), 1)
        file_field = result.file_upload_fields[0]
        self.assertEqual(file_field.field_id, "resume_upload")
        self.assertEqual(file_field.input_type, "file")
        self.assertTrue(file_field.required)

        # 4. Check specific fields and labels
        first_name = result.get_field_by_id_or_name("first_name")
        self.assertIsNotNone(first_name)
        self.assertEqual(first_name.input_type, "text")
        self.assertIn("First Name", first_name.label)
        self.assertTrue(first_name.required)

        email = result.get_field_by_id_or_name("email")
        self.assertIsNotNone(email)
        self.assertEqual(email.input_type, "email")
        self.assertTrue(email.required)

        phone = result.get_field_by_id_or_name("phone")
        self.assertIsNotNone(phone)
        self.assertEqual(phone.input_type, "tel")

        # Radio group for work authorization
        work_auth = result.get_field_by_id_or_name("work_auth")
        self.assertIsNotNone(work_auth)
        self.assertEqual(work_auth.input_type, "radio_group")
        self.assertEqual(len(work_auth.options), 2)
        opt_values = {o["value"] for o in work_auth.options}
        self.assertIn("yes", opt_values)
        self.assertIn("no", opt_values)

        # Dropdown for experience
        years_exp = result.get_field_by_id_or_name("years_experience")
        self.assertIsNotNone(years_exp)
        self.assertEqual(years_exp.input_type, "select")
        self.assertTrue(len(years_exp.options) >= 4)

        # Submit button
        self.assertTrue(len(result.submit_buttons) >= 1)
        self.assertIn("submit", result.submit_buttons[0]["selector"].lower())

    async def test_multi_step_wizard_analysis(self) -> None:
        await self.agent.navigate(f"{self.base_url}/wizard/step1")
        result = await self.analyzer.analyze(self.agent)

        self.assertTrue(result.is_multi_step)
        self.assertIsNotNone(result.step_indicator)
        self.assertIn("step 1 of 3", result.step_indicator.lower())
        self.assertTrue(len(result.next_buttons) >= 1)

    async def test_captcha_challenge_detection(self) -> None:
        await self.agent.navigate(f"{self.base_url}/challenge/captcha")
        result = await self.analyzer.analyze(self.agent)

        self.assertEqual(result.challenge_detected, "CAPTCHA_CHALLENGE")

    async def test_login_gate_detection(self) -> None:
        await self.agent.navigate(f"{self.base_url}/challenge/login")
        result = await self.analyzer.analyze(self.agent)

        self.assertEqual(result.challenge_detected, "LOGIN_REQUIRED")


if __name__ == "__main__":
    unittest.main()
