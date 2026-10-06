"""
Unit tests for SetupReadinessService and Platform Preflight checks.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.services.setup.setup_readiness import SetupReadinessService
from app.services.setup.setup_requirements import RequirementStatus


class TestSetupReadinessService(unittest.TestCase):
    def setUp(self):
        self.mock_profile_service = MagicMock()
        self.mock_resume_service = MagicMock()
        self.mock_settings_service = MagicMock()
        self.mock_secrets_service = MagicMock()
        self.mock_qna_service = MagicMock()
        self.mock_platform_service = MagicMock()

        self.service = SetupReadinessService(
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            settings_service=self.mock_settings_service,
            secrets_service=self.mock_secrets_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
        )

    def test_empty_database_not_ready(self):
        # Empty profile
        self.mock_profile_service.get_primary_user_profile.return_value = {}
        # Empty resumes
        self.mock_resume_service.list_resumes.return_value = []
        # Empty preferences
        self.mock_settings_service.get.side_effect = lambda k, d=None: {}
        self.mock_secrets_service.get_secret.return_value = None
        self.mock_qna_service.get_stats.return_value = {"total_entries": 0}
        self.mock_platform_service.list_platforms.return_value = []

        report = self.service.evaluate()
        self.assertFalse(report.is_core_ready)
        self.assertFalse(report.is_automation_ready)
        self.assertGreaterEqual(len(report.blockers), 2)
        self.assertEqual(report.requirements["candidate_profile"].status, RequirementStatus.NOT_STARTED)
        self.assertEqual(report.requirements["primary_resume"].status, RequirementStatus.NOT_STARTED)

    def test_core_ready_without_ai(self):
        # Configured profile
        self.mock_profile_service.get_primary_user_profile.return_value = {
            "personal_info": {"name": "Test User", "email": "test@example.com", "phone": "1234567890"},
            "skills": ["Python", "Qt", "FastAPI"],
        }
        # Configured resume
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(b"%PDF-1.4 dummy resume content")
            tmp.flush()
            mock_res = MagicMock()
            mock_res.file_path = tmp.name
            mock_res.original_filename = "resume.pdf"
            self.mock_resume_service.list_resumes.return_value = [mock_res]
            self.mock_resume_service.get_default_resume.return_value = mock_res

            # Configured preferences
            self.mock_settings_service.get.side_effect = lambda k, d=None: {
                "search_preferences": {"titles": ["Backend Engineer"], "locations": ["Remote"]}
            }.get(k, d or {})

            # AI and Q&A are unconfigured
            self.mock_secrets_service.get_secret.return_value = None
            self.mock_qna_service.get_stats.return_value = {"total_entries": 0}
            self.mock_platform_service.list_platforms.return_value = []

            report = self.service.evaluate()
            self.assertTrue(report.is_core_ready)
            self.assertFalse(report.is_automation_ready)
            self.assertEqual(report.core_completed_count, 3)

    def test_platform_preflight_blocks_incomplete(self):
        # Empty profile
        self.mock_profile_service.get_primary_user_profile.return_value = {}
        self.mock_resume_service.list_resumes.return_value = []
        self.mock_settings_service.get.return_value = {}

        preflight = self.service.evaluate_for_platform("linkedin")
        self.assertFalse(preflight.can_run_automation)
        self.assertGreater(len(preflight.blockers), 0)


if __name__ == "__main__":
    unittest.main()
