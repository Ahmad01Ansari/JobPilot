"""
Integration tests for Setup Wizard data transfer to user profile, Settings, and Secrets.
Verifies that AI provider configs, platform credentials, and search preferences
properly persist across SettingsService, SecretsService, and config/profile.json.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.setup.setup_service import SetupService
from app.services.setup.setup_readiness import SetupReadinessService
from app.services.secrets_service import SecretsService
from app.services.settings_service import SettingsService
from app.ui.widgets.onboarding_steps.step_platforms import StepPlatformsWidget
from app.ui.widgets.onboarding_steps.step_ai_provider import StepAIProviderWidget
from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
from PySide6.QtWidgets import QApplication
import sys

_app = QApplication.instance() or QApplication(sys.argv + ["-platform", "offscreen"])


class TestSetupDataTransfer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "setup_state.json"
        self.profile_json_file = Path(self.temp_dir.name) / "profile.json"

        # Create dummy initial profile.json
        initial_profile = {
            "personal": {"first_name": "Test", "email": "test@example.com"},
            "professional": {"title": "Engineer"},
            "platforms": {
                "naukri": {"enabled": False, "search_terms": [], "search_location": "Delhi"},
                "linkedin": {"enabled": False, "search_terms": [], "search_location": "Bangalore"},
            },
            "ai": {
                "enabled": False,
                "provider": "ollama",
                "api_url": "http://localhost:11434",
                "model": "llama3",
            }
        }
        with open(self.profile_json_file, "w", encoding="utf-8") as f:
            json.dump(initial_profile, f, indent=2)

        # Isolated temporary SQLite database and SecretsService
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.key_path = str(Path(self.temp_dir.name) / "secret.key")
        self.secrets_service = SecretsService(key_path=self.key_path, session_factory=self.session_factory)

        self.mock_settings_store = {}
        self.settings_service = MagicMock(spec=SettingsService)
        self.settings_service.get.side_effect = lambda k, default=None: self.mock_settings_store.get(k, default)
        self.settings_service.set.side_effect = lambda k, v: self.mock_settings_store.__setitem__(k, v)
        self.settings_service.save.return_value = True

        self.mock_ai_service = MagicMock()
        self.mock_ai_service.test_connection.return_value = {"success": True}

        self.mock_platform_service = MagicMock()
        m_naukri = MagicMock()
        m_naukri.name = "naukri"
        m_naukri.display_name = "Naukri"
        m_naukri.is_enabled = False
        m_naukri.default_location = "Delhi"
        m_naukri.description = ""

        m_linkedin = MagicMock()
        m_linkedin.name = "linkedin"
        m_linkedin.display_name = "LinkedIn"
        m_linkedin.is_enabled = False
        m_linkedin.default_location = "Bangalore"
        m_linkedin.description = ""

        self.platform_db = {
            "naukri": m_naukri,
            "linkedin": m_linkedin,
        }
        self.mock_platform_service.list_platforms.return_value = list(self.platform_db.values())
        def mock_save_plat(platform_name, is_enabled=None, default_location=None, **kwargs):
            if platform_name in self.platform_db:
                if is_enabled is not None:
                    self.platform_db[platform_name].is_enabled = is_enabled
                if default_location is not None:
                    self.platform_db[platform_name].default_location = default_location
            return True, None
        self.mock_platform_service.save_platform_config.side_effect = mock_save_plat

        self.readiness = SetupReadinessService(
            settings_service=self.settings_service,
            secrets_service=self.secrets_service,
            platform_service=self.mock_platform_service,
        )

        self.service = SetupService(
            state_path=self.state_file,
            readiness_service=self.readiness,
            ai_service=self.mock_ai_service,
            settings_service=self.settings_service,
            secrets_service=self.secrets_service,
            platform_service=self.mock_platform_service,
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    @patch("app.services.setup.setup_service.Path")
    def test_ai_provider_transfer_full_pipeline(self, mock_path_cls):
        # Point Path("config/profile.json") to self.profile_json_file
        def mock_path_call(p):
            if str(p) == "config/profile.json":
                return self.profile_json_file
            return Path(p)
        mock_path_cls.side_effect = mock_path_call

        ok, err, caps = self.service.save_ai_provider_step(
            provider="groq",
            api_key="gsk_live_test_api_key_12345",
            endpoint="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            skip=False
        )

        self.assertTrue(ok)
        self.assertIsNone(err)

        # 1. Verify SettingsService persistence
        self.assertEqual(self.mock_settings_store.get("ai.provider"), "groq")
        self.assertEqual(self.mock_settings_store.get("ai.provider_id"), "groq")
        self.assertEqual(self.mock_settings_store.get("ai.model"), "llama-3.3-70b-versatile")
        self.assertEqual(self.mock_settings_store.get("ai.api_url"), "https://api.groq.com/openai/v1")
        self.assertTrue(self.mock_settings_store.get("ai.use_AI"))

        # 2. Verify SecretsService persistence (canonical & legacy keys)
        self.assertEqual(self.secrets_service.get_ai_secret("groq"), "gsk_live_test_api_key_12345")
        self.assertEqual(self.secrets_service.get_secret("ai_api_key_groq"), "gsk_live_test_api_key_12345")

        # 3. Verify config/profile.json synchronization
        with open(self.profile_json_file, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        self.assertEqual(profile_data["ai"]["provider"], "groq")
        self.assertEqual(profile_data["ai"]["model"], "llama-3.3-70b-versatile")
        self.assertEqual(profile_data["ai"]["api_url"], "https://api.groq.com/openai/v1")
        self.assertTrue(profile_data["ai"]["enabled"])

        # 4. Verify SetupReadinessService evaluates AI as READY
        ai_req = self.readiness._evaluate_ai_provider()
        self.assertEqual(ai_req.status.value, "READY")

    @patch("app.services.setup.setup_service.Path")
    def test_platform_credentials_transfer_full_pipeline(self, mock_path_cls):
        def mock_path_call(p):
            if str(p) == "config/profile.json":
                return self.profile_json_file
            return Path(p)
        mock_path_cls.side_effect = mock_path_call

        payload = {
            "naukri": {
                "username": "candidate@naukri.com",
                "password": "NaukriSecretPassword123!",
                "location": "Noida, India",
            },
            "linkedin": {
                "username": "candidate@linkedin.com",
                "password": "LinkedInSecretPassword456!",
                "location": "Remote",
            }
        }

        ok, err = self.service.save_platforms_step(payload)
        self.assertTrue(ok)
        self.assertIsNone(err)

        # 1. Verify SecretsService persistence (canonical & legacy)
        n_user, n_pass = self.secrets_service.get_platform_credentials("naukri")
        self.assertEqual(n_user, "candidate@naukri.com")
        self.assertEqual(n_pass, "NaukriSecretPassword123!")

        li_user, li_pass = self.secrets_service.get_platform_credentials("linkedin")
        self.assertEqual(li_user, "candidate@linkedin.com")
        self.assertEqual(li_pass, "LinkedInSecretPassword456!")

        self.assertEqual(self.secrets_service.get_secret("platform_username_naukri"), "candidate@naukri.com")
        self.assertEqual(self.secrets_service.get_secret("platform_password_naukri"), "NaukriSecretPassword123!")

        # 2. Verify PlatformService enablement
        self.assertTrue(self.platform_db["naukri"].is_enabled)
        self.assertEqual(self.platform_db["naukri"].default_location, "Noida, India")
        self.assertTrue(self.platform_db["linkedin"].is_enabled)
        self.assertEqual(self.platform_db["linkedin"].default_location, "Remote")

        # 3. Verify config/profile.json platform synchronization
        with open(self.profile_json_file, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        self.assertTrue(profile_data["platforms"]["naukri"]["enabled"])
        self.assertEqual(profile_data["platforms"]["naukri"]["search_location"], "Noida, India")
        self.assertTrue(profile_data["platforms"]["linkedin"]["enabled"])
        self.assertEqual(profile_data["platforms"]["linkedin"]["search_location"], "Remote")

        # 4. Verify get_platform_statuses returns credentialed and configured details
        statuses = self.service.get_platform_statuses()
        status_map = {s["id"]: s for s in statuses}
        self.assertTrue(status_map["naukri"]["has_credentials"])
        self.assertEqual(status_map["naukri"]["username"], "candidate@naukri.com")
        self.assertEqual(status_map["naukri"]["location"], "Noida, India")
        self.assertEqual(status_map["naukri"]["status_label"], "Configured ✓")

    @patch("app.services.setup.setup_service.Path")
    def test_preferences_transfer_full_pipeline(self, mock_path_cls):
        def mock_path_call(p):
            if str(p) == "config/profile.json":
                return self.profile_json_file
            return Path(p)
        mock_path_cls.side_effect = mock_path_call

        prefs = {
            "titles": ["AI Engineer", "Python Developer"],
            "locations": ["Bangalore, India"],
            "negative_keywords": ["Senior Manager", "PHP"],
        }

        ok, err = self.service.save_preferences_step(prefs)
        self.assertTrue(ok)

        # 1. Verify SettingsService persistence
        saved_prefs = self.mock_settings_store.get("search_preferences")
        self.assertEqual(saved_prefs["titles"], ["AI Engineer", "Python Developer"])

        # 2. Verify config/profile.json synchronization
        with open(self.profile_json_file, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        for p_name in ["naukri", "linkedin"]:
            self.assertEqual(profile_data["platforms"][p_name]["search_terms"], ["AI Engineer", "Python Developer"])
            self.assertEqual(profile_data["platforms"][p_name]["search_location"], "Bangalore, India")
            self.assertEqual(profile_data["platforms"][p_name]["negative_title_words"], ["Senior Manager", "PHP"])


class TestSetupUIPreFillAndAutoSave(unittest.TestCase):
    def setUp(self):
        self.mock_setup_service = MagicMock(spec=SetupService)
        self.mock_settings_service = MagicMock()
        self.mock_secrets_service = MagicMock()
        self.mock_readiness_service = MagicMock()

        self.mock_setup_service._get_settings_service.return_value = self.mock_settings_service
        self.mock_setup_service._get_secrets_service.return_value = self.mock_secrets_service
        self.mock_setup_service.readiness_service = self.mock_readiness_service
        self.mock_setup_service.state = MagicMock()
        self.mock_setup_service.state.completed_steps = []
        self.mock_setup_service.state.skipped_steps = []

    def test_platforms_widget_prefills_configured_data(self):
        self.mock_setup_service.get_platform_statuses.return_value = [
            {
                "id": "naukri",
                "name": "Naukri",
                "description": "",
                "is_enabled": True,
                "status_label": "Configured ✓",
                "has_credentials": True,
                "username": "user@naukri.com",
                "location": "Noida, India",
            },
            {
                "id": "indeed",
                "name": "Indeed",
                "description": "",
                "is_enabled": True,
                "status_label": "Supported ✓",
                "has_credentials": False,
                "username": "user@indeed.com",
                "location": "Remote",
            }
        ]

        widget = StepPlatformsWidget(self.mock_setup_service)
        naukri_card = widget.cards["naukri"]
        self.assertEqual(naukri_card.txt_username.text(), "user@naukri.com")
        self.assertIn("Password Saved in Keyring", naukri_card.txt_password.placeholderText())

        indeed_card = widget.cards["indeed"]
        self.assertEqual(indeed_card.txt_username.text(), "user@indeed.com")
        self.assertEqual(indeed_card.txt_search_location.text(), "Remote")

    def test_ai_provider_widget_prefills_configured_data(self):
        self.mock_settings_service.get.side_effect = lambda k, default=None: {
            "ai.provider": "groq",
            "ai.groq.endpoint": "https://api.groq.com/openai/v1",
            "ai.groq.model": "llama-3.3-70b-versatile",
        }.get(k, default)
        self.mock_secrets_service.get_ai_secret.return_value = "gsk_saved_key_123"

        widget = StepAIProviderWidget(self.mock_setup_service)
        self.assertEqual(widget.cmb_provider.currentData(), "groq")
        self.assertEqual(widget.txt_endpoint.text(), "https://api.groq.com/openai/v1")
        self.assertEqual(widget.txt_model.text(), "llama-3.3-70b-versatile")
        self.assertEqual(widget.txt_api_key.text(), "gsk_saved_key_123")

    def test_wizard_rail_click_triggers_autosave(self):
        wizard = OnboardingWizardDialog(self.mock_setup_service)
        wizard.current_step_idx = 1  # AI step
        wizard.step_ai.txt_api_key.setText("gsk_new_entered_key")
        wizard.step_ai.cmb_provider.setCurrentIndex(0)  # Groq

        # User clicks step 7 (Platforms) on the rail without clicking Continue
        wizard._on_rail_item_clicked(7)

        # Verify save_ai_provider_step was called automatically
        self.mock_setup_service.save_ai_provider_step.assert_called()


if __name__ == "__main__":
    unittest.main()
