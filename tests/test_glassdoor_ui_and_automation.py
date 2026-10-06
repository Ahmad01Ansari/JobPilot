"""Tests for Glassdoor Desktop UI, Service, and Automation integration."""

import unittest
from unittest.mock import MagicMock, patch

from app.db.models import Platform
from app.services.platform_service import PlatformService
from app.services.secrets_service import SecretsService
from app.ui.widgets.jobs.job_details_dialog import format_platform_name as format_details_platform
from app.ui.widgets.jobs.jobs_detail_panel import format_platform_name as format_panel_platform
from app.ui.widgets.platform_chart_card import PLATFORM_COLORS, PLATFORM_ICONS


class TestGlassdoorUIServiceIntegration(unittest.TestCase):
    """Verifies that Glassdoor is registered across UI components, services, and color maps."""

    def test_platform_service_seeding_includes_glassdoor(self):
        """Ensures default platform seeds include enabled Glassdoor."""
        mock_session = MagicMock()
        mock_repo = MagicMock()
        mock_repo.get_platform_by_name.return_value = None

        with patch("app.services.platform_service.PlatformRepository", return_value=mock_repo):
            with patch("app.services.platform_service.get_db_session") as mock_ctx:
                mock_ctx.return_value.__enter__.return_value = mock_session
                service = PlatformService(session_factory=MagicMock())
                service.seed_default_platforms()

                seeded_names = [call[1]["name"] for call in mock_repo.get_or_create_platform.call_args_list]
                self.assertIn("glassdoor", seeded_names)

                for call in mock_repo.save_account.call_args_list:
                    kwargs = call[1]
                    if kwargs.get("platform_name") == "glassdoor":
                        self.assertEqual(kwargs.get("display_name"), "Glassdoor")
                        self.assertIn("Python Engineer", kwargs.get("extra_settings", {}).get("search_terms", []))

    def test_secrets_service_handles_glassdoor(self):
        """Ensures SecretsService resolves Glassdoor credentials correctly."""
        service = SecretsService(session_factory=MagicMock())
        with patch.object(service, "get_secret") as mock_secret:
            mock_secret.side_effect = lambda k, default=None: {
                "glassdoor_username": "user@example.com",
                "glassdoor_password": "supersecretpassword",
            }.get(k, default)

            user, pwd = service.get_platform_credentials("glassdoor")
            self.assertEqual(user, "user@example.com")
            self.assertEqual(pwd, "supersecretpassword")

    def test_format_platform_name(self):
        """Ensures format_platform_name formats Glassdoor properly."""
        self.assertEqual(format_details_platform("glassdoor"), "Glassdoor")
        self.assertEqual(format_panel_platform("glassdoor"), "Glassdoor")

    def test_platform_chart_card_has_glassdoor(self):
        """Ensures chart color and icon maps include Glassdoor."""
        self.assertIn("glassdoor", PLATFORM_COLORS)
        self.assertEqual(PLATFORM_COLORS["glassdoor"], "#0CAA41")
        self.assertIn("glassdoor", PLATFORM_ICONS)
        self.assertEqual(PLATFORM_ICONS["glassdoor"], "🏢")

    @patch("platforms.router.GlassdoorPlatform")
    def test_automation_service_run_glassdoor_engine(self, mock_gd_platform_cls):
        """Ensures AutomationWorkerThread executes Glassdoor platform lifecycle."""
        from app.services.automation_service import AutomationWorker

        mock_platform_inst = MagicMock()
        mock_gd_platform_cls.return_value = mock_platform_inst
        mock_platform_inst.login.return_value = True
        mock_platform_inst.search_and_apply.return_value = {"jobs_applied": 3}

        worker = AutomationWorker(run_id="test_gd_run", platform="glassdoor")
        worker.emit_activity = MagicMock()

        worker._run_glassdoor_engine()

        mock_platform_inst.initialize.assert_called_once()
        mock_platform_inst.login.assert_called_once()
        mock_platform_inst.search_and_apply.assert_called_once()
        mock_platform_inst.close.assert_called_once()
        worker.emit_activity.assert_any_call("Glassdoor session completed. Applied: 3")


if __name__ == "__main__":
    unittest.main()
