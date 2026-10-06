"""
Unit tests for SetupService orchestrator and conflict resolution.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.services.setup.setup_service import SetupService
from app.services.setup.setup_readiness import SetupReadinessService


class TestSetupService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_state.json"

        self.mock_profile_service = MagicMock()
        self.mock_resume_service = MagicMock()
        self.mock_resume_parser = MagicMock()
        self.mock_ai_service = MagicMock()
        self.mock_settings_service = MagicMock()
        self.mock_secrets_service = MagicMock()
        self.mock_qna_service = MagicMock()
        self.mock_platform_service = MagicMock()

        self.readiness = SetupReadinessService(
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            settings_service=self.mock_settings_service,
            secrets_service=self.mock_secrets_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
        )

        self.service = SetupService(
            state_path=self.state_file,
            readiness_service=self.readiness,
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            resume_parser=self.mock_resume_parser,
            ai_service=self.mock_ai_service,
            settings_service=self.mock_settings_service,
            secrets_service=self.mock_secrets_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_start_setup(self):
        state = self.service.start_setup(mode="QUICK")
        self.assertEqual(state.setup_mode, "QUICK")
        self.assertIsNotNone(state.started_at)

    def test_conflict_detection(self):
        self.mock_profile_service.get_primary_user_profile.return_value = {
            "personal_info": {"name": "Ahmad Raza"},
            "years_of_experience": "3",
        }
        # Discrepancy in experience years
        new_profile = {
            "name": {"value": "Ahmad Raza", "source": "RESUME"},
            "experience_years": {"value": 5, "source": "RESUME"},
        }
        conflicts = self.service.detect_conflicts(new_profile)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["field"], "experience_years")
        self.assertEqual(conflicts[0]["existing_value"], "3")
        self.assertEqual(conflicts[0]["new_value"], "5")

    def test_ai_provider_step_stores_secret_properly(self):
        self.mock_ai_service.test_connection.return_value = {"success": True}
        ok, err, caps = self.service.save_ai_provider_step(
            provider="groq",
            api_key="gsk_secret_123456",
            endpoint=None,
            model="llama-3.3-70b-versatile",
        )
        self.assertTrue(ok)
        # Verify secret stored in SecretsService
        self.mock_secrets_service.set_secret.assert_called_with("ai_api_key_groq", "gsk_secret_123456")
        # Verify key is NOT in setup state or file
        state_content = self.state_file.read_text(encoding="utf-8")
        self.assertNotIn("gsk_secret_123456", state_content)

    def test_complete_setup(self):
        success, changes = self.service.complete_setup()
        self.assertTrue(success)
        self.mock_settings_service.set.assert_any_call("general.onboarding_completed", True)
        self.assertTrue(self.service.state.is_completed)

    def test_resume_upload(self):
        sample_file = Path(self.temp_dir.name) / "test_resume.pdf"
        sample_file.write_text("dummy resume content")
        mock_record = MagicMock()
        mock_record.id = 12
        self.mock_resume_service.add_resume.return_value = (mock_record, True, None)

        ok, err, record = self.service.save_resume_upload(str(sample_file))
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(record.id, 12)
        self.assertEqual(self.service.state.active_resume_id, "12")
        self.assertIn("resume_ingest", self.service.state.completed_steps)


if __name__ == "__main__":
    unittest.main()
