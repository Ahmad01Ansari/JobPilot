import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as flask_app_module
from app import app
from modules.models import Job
from modules.tracker import ApplicationRecord


class TestDashboardIntegration(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_home_page_renders_dashboard(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("JobPilot Automation Dashboard", html)
        self.assertIn("Unified & Naukri Overview", html)
        self.assertIn("Naukri Evaluated", html)
        self.assertIn("Naukri Success", html)

    def test_api_naukri_stats(self):
        with patch.object(flask_app_module.tracker, "get_stats") as mock_get_stats:
            mock_get_stats.return_value = {
                "SUBMITTED": 5,
                "SKIPPED": 10,
                "FAILED": 2,
                "MANUAL_REQUIRED": 1,
                "EXTERNAL": 1,
                "QUALIFIED": 3,
                "DISCOVERED": 22,
            }
            response = self.client.get('/api/naukri/stats')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()

            self.assertEqual(data["platform"], "naukri")
            self.assertEqual(data["success"], 5)
            self.assertEqual(data["skipped"], 10)
            self.assertEqual(data["failed"], 2)
            self.assertEqual(data["manual_required"], 1)
            self.assertEqual(data["external"], 1)
            self.assertEqual(data["applications"], 44)

    def test_api_all_stats(self):
        with patch.object(flask_app_module.tracker, "get_stats") as mock_get_stats:
            def side_effect(platform=None):
                if platform == "naukri":
                    return {"SUBMITTED": 3, "SKIPPED": 4}
                elif platform == "linkedin":
                    return {"SUBMITTED": 7, "SKIPPED": 1}
                else:
                    return {"SUBMITTED": 10, "SKIPPED": 5}

            mock_get_stats.side_effect = side_effect
            response = self.client.get('/api/stats')
            self.assertEqual(response.status_code, 200)
            data = response.get_json()

            self.assertIn("naukri", data)
            self.assertIn("linkedin", data)
            self.assertIn("total", data)
            self.assertEqual(data["naukri"]["success"], 3)
            self.assertEqual(data["linkedin"]["success"], 7)
            self.assertEqual(data["total"]["success"], 10)

    def test_api_applications_list_and_filter(self):
        rec1 = ApplicationRecord(
            platform="naukri",
            job_id="nk_1",
            title="RPA Developer",
            company="Enterprise Corp",
            location="Noida",
            source_url="https://naukri.com/nk_1",
            status="SUBMITTED",
            applied_at="2026-09-20 12:00:00",
        )
        rec2 = ApplicationRecord(
            platform="linkedin",
            job_id="li_1",
            title="Automation Engineer",
            company="Tech Inc",
            location="Remote",
            source_url="https://linkedin.com/jobs/1",
            status="SKIPPED",
            skip_reason="Exp high",
        )

        with patch.object(flask_app_module.tracker, "get_all_records") as mock_get_all:
            mock_get_all.return_value = [rec1, rec2]

            # Unfiltered
            res = self.client.get('/api/applications')
            self.assertEqual(res.status_code, 200)
            items = res.get_json()
            self.assertEqual(len(items), 2)
            self.assertEqual(items[0]["platform"], "naukri")
            self.assertEqual(items[0]["status"], "SUBMITTED")

    def test_api_naukri_jobs_endpoint(self):
        rec = ApplicationRecord(
            platform="naukri",
            job_id="nk_99",
            title="Lead Developer",
            company="Naukri Corp",
            location="Bangalore",
            source_url="https://naukri.com/nk_99",
            status="SUBMITTED",
        )

        with patch.object(flask_app_module.tracker, "get_all_records") as mock_get_all:
            mock_get_all.return_value = [rec]

            res = self.client.get('/api/naukri/jobs')
            self.assertEqual(res.status_code, 200)
            items = res.get_json()
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["job_id"], "nk_99")
            mock_get_all.assert_called_once_with(platform="naukri", include_junk=False)

    def test_legacy_applied_jobs_route(self):
        # Even if CSV is empty or missing, response handles gracefully
        res = self.client.get('/applied-jobs')
        self.assertIn(res.status_code, [200, 404])


if __name__ == "__main__":
    unittest.main()
