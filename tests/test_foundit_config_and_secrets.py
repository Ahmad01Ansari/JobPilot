'''
Unit Tests for Foundit Configuration, Secrets, and Profile Loading
'''

import unittest
from unittest.mock import patch, MagicMock

from modules.config_loader import get_platform, validate_foundit_config
from app.services.secrets_service import SecretsService
from modules.models import job_from_foundit, Job
from platforms.base_platform import SUPPORTED_PLATFORMS, list_supported_platforms


class TestFounditConfigAndSecrets(unittest.TestCase):

    def test_foundit_in_supported_platforms(self):
        self.assertIn("foundit", SUPPORTED_PLATFORMS)
        self.assertIn("foundit", list_supported_platforms())

    def test_foundit_config_loading_and_validation(self):
        cfg = get_platform("foundit")
        self.assertIsInstance(cfg, dict)
        self.assertTrue(cfg.get("enabled"))
        self.assertIn("RPA Developer", cfg.get("search_terms", []))
        self.assertEqual(cfg.get("search_location"), "India")
        # Validation routine should pass
        self.assertTrue(validate_foundit_config())

    def test_foundit_secrets_retrieval(self):
        service = SecretsService()
        with patch.object(service, "get_secret") as mock_get:
            mock_get.side_effect = lambda k, default=None: {
                "secret.foundit_username": "test_user@example.com",
                "secret.foundit_password": "MockPassword123!",
                "foundit_username": "test_user@example.com",
                "foundit_password": "MockPassword123!",
            }.get(k, default)
            u, p = service.get_platform_credentials("foundit")
            self.assertEqual(u, "test_user@example.com")
            self.assertEqual(p, "MockPassword123!")

    def test_job_from_foundit_model(self):
        job = job_from_foundit(
            job_id="68631630",
            title="Mulesoft RPA Developer",
            company="plumlogix",
            location="Pune, India",
            required_experience_min=4,
            required_experience_max=6,
            salary_min=500000,
            salary_max=800000,
            source_url="https://www.foundit.in/job/68631630",
        )
        self.assertIsInstance(job, Job)
        self.assertEqual(job.platform, "foundit")
        self.assertEqual(job.job_id, "68631630")
        self.assertEqual(job.title, "Mulesoft RPA Developer")
        self.assertEqual(job.company, "plumlogix")
        self.assertEqual(job.location, "Pune, India")
        self.assertEqual(job.required_experience_min, 4)
        self.assertEqual(job.required_experience_max, 6)
        self.assertEqual(job.experience_range_str(), "4-6 years")


if __name__ == "__main__":
    unittest.main()
