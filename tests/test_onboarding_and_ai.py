"""Tests for Universal AI Service, Resume Parser, Onboarding Wizard, and Profile Sync."""

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestUniversalAIService(unittest.TestCase):
    """Tests for UniversalAIService configuration, connection testing, and text generation."""

    def setUp(self):
        from app.services.ai_service import UniversalAIService
        self.service = UniversalAIService()
        self.orig_config = self.service.get_config()

    def tearDown(self):
        if hasattr(self, "orig_config") and self.orig_config:
            self.service.save_config(
                enabled=self.orig_config.get("enabled", True),
                provider=self.orig_config.get("provider", "ollama"),
                model=self.orig_config.get("model", "llama3.1:8b"),
                api_url=self.orig_config.get("api_url", "http://localhost:11434/v1"),
                api_key=self.orig_config.get("api_key", ""),
            )

    def test_get_config_returns_dict(self):
        cfg = self.service.get_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("enabled", cfg)
        self.assertIn("provider", cfg)
        self.assertIn("model", cfg)
        self.assertIn("api_url", cfg)
        self.assertIn("api_key", cfg)

    def test_test_connection_returns_tuple(self):
        ok, msg, latency = self.service.test_connection(provider="ollama", api_url="http://127.0.0.1:99999")
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(msg, str)
        self.assertIsInstance(latency, float)

    def test_unsupported_provider_returns_false(self):
        ok, msg, latency = self.service.test_connection(provider="nonexistent_provider")
        self.assertFalse(ok)
        self.assertIn("Unsupported", msg)

    def test_openai_requires_api_key(self):
        ok, msg, _ = self.service.test_connection(provider="openai", api_key="")
        self.assertFalse(ok)
        self.assertIn("API key", msg)

    def test_gemini_requires_api_key(self):
        ok, msg, _ = self.service.test_connection(provider="gemini", api_key="")
        self.assertFalse(ok)
        self.assertIn("API key", msg)

    def test_deepseek_requires_api_key(self):
        ok, msg, _ = self.service.test_connection(provider="deepseek", api_key="")
        self.assertFalse(ok)
        self.assertIn("API key", msg)

    def test_save_config_persists(self):
        """Verifies that save_config does not raise and reads back."""
        self.service.save_config(enabled=True, provider="ollama", model="test-model", api_url="http://localhost:11434/v1")
        cfg = self.service.get_config()
        self.assertEqual(cfg["provider"], "ollama")
        self.assertEqual(cfg["model"], "test-model")

    def test_get_active_client_returns_none_when_disabled(self):
        self.service.save_config(enabled=False, provider="ollama")
        client = self.service.get_active_client()
        self.assertIsNone(client)

    def test_get_active_client_returns_none_for_gemini(self):
        self.service.save_config(enabled=True, provider="gemini", api_key="test-key")
        client = self.service.get_active_client()
        self.assertIsNone(client)  # Gemini has no OpenAI-compatible endpoint

    def test_get_active_client_returns_openai_for_ollama(self):
        self.service.save_config(enabled=True, provider="ollama", api_url="http://localhost:11434/v1")
        client = self.service.get_active_client()
        # Returns OpenAI client object (even if Ollama isn't running)
        if client is not None:
            self.assertTrue(hasattr(client, "chat"))


class TestQnAEngineUniversalAI(unittest.TestCase):
    """Tests for QnAEngine integration with UniversalAIService."""

    def setUp(self):
        from app.services.ai_service import UniversalAIService
        self.ai_svc = UniversalAIService()
        self.orig_config = self.ai_svc.get_config()

    def tearDown(self):
        if hasattr(self, "orig_config") and self.orig_config:
            self.ai_svc.save_config(
                enabled=self.orig_config.get("enabled", True),
                provider=self.orig_config.get("provider", "ollama"),
                model=self.orig_config.get("model", "llama3.1:8b"),
                api_url=self.orig_config.get("api_url", "http://localhost:11434/v1"),
                api_key=self.orig_config.get("api_key", ""),
            )

    def test_set_universal_ai_service_updates_model(self):
        from modules.qna_engine import QnAEngine
        engine = QnAEngine(ai_client=None)
        self.ai_svc.save_config(enabled=True, provider="ollama", model="test-universal-model")
        # set_universal_ai_service should update the engine's model config
        engine.set_universal_ai_service(self.ai_svc)
        self.assertEqual(engine.ai_cfg.get("model"), "test-universal-model")


class TestResumeParserService(unittest.TestCase):
    """Tests for ResumeParserService text extraction and rule-based fallback."""

    def setUp(self):
        from app.services.resume_parser import ResumeParserService
        self.parser = ResumeParserService(ai_service=None)

    def test_extract_text_from_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.parser.extract_raw_text("/nonexistent/path/resume.pdf")

    def test_extract_text_from_txt_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("John Doe\njohn@example.com\nPython Developer with 3 years of experience")
            f.flush()
            text = self.parser.extract_raw_text(f.name)
        os.unlink(f.name)
        self.assertIn("john@example.com", text)
        self.assertIn("John Doe", text)

    def test_heuristic_extraction_finds_email(self):
        text = "Jane Smith\njane.smith@company.com\n+919876543210\nSenior Software Engineer with 5 years of experience\nPython, Java, Docker"
        data = self.parser._extract_with_rules(text)
        self.assertEqual(data["personal"]["email"], "jane.smith@company.com")
        self.assertTrue(data["personal"]["first_name"].lower().startswith("jane"))

    def test_heuristic_extraction_finds_phone(self):
        text = "Ahmad Raza\nraza@test.org\n+916388623967\nRPA Developer"
        data = self.parser._extract_with_rules(text)
        self.assertIn("6388623967", data["personal"]["phone"])

    def test_heuristic_extraction_finds_skills(self):
        text = "Software Engineer\ntest@x.com\nPython JavaScript Docker SQL Machine Learning"
        data = self.parser._extract_with_rules(text)
        skill_names = [s["name"] for s in data["skills"]]
        self.assertIn("Python", skill_names)
        self.assertIn("Docker", skill_names)
        self.assertIn("SQL", skill_names)

    def test_heuristic_extraction_finds_experience_years(self):
        text = "Dev\ndev@x.com\n3.5 years of experience in backend development"
        data = self.parser._extract_with_rules(text)
        self.assertEqual(data["professional"]["years_of_experience"], 3.5)

    def test_heuristic_extraction_finds_linkedin(self):
        text = "Name\nname@x.com\nhttps://linkedin.com/in/johndoe"
        data = self.parser._extract_with_rules(text)
        self.assertIn("linkedin.com/in/johndoe", data["personal"]["linkedin_url"])

    def test_heuristic_extraction_finds_github(self):
        text = "Name\nname@x.com\nhttps://github.com/johndoe"
        data = self.parser._extract_with_rules(text)
        self.assertIn("github.com/johndoe", data["personal"]["github_url"])

    def test_parse_resume_from_txt_returns_heuristic(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Ahmad Raza\nahmad@test.com\nPython Developer\n2 years of experience\nPython Docker SQL")
            f.flush()
            data, raw, method = self.parser.parse_resume(f.name)
        os.unlink(f.name)
        self.assertEqual(method, "heuristic")
        self.assertIn("personal", data)
        self.assertIn("professional", data)
        self.assertIn("skills", data)

    def test_validate_extracted_payload(self):
        valid = {"personal": {"first_name": "A"}, "professional": {"current_title": "Dev"}}
        self.assertTrue(self.parser._validate_extracted_payload(valid))
        self.assertFalse(self.parser._validate_extracted_payload({"bad": True}))
        self.assertFalse(self.parser._validate_extracted_payload("string"))


class TestOnboardingWizardUI(unittest.TestCase):
    """Tests for OnboardingWizardDialog instantiation and step navigation in offscreen mode."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        if not QApplication.instance():
            cls._app = QApplication([])
        else:
            cls._app = QApplication.instance()

    def test_wizard_instantiation(self):
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog()
        self.assertIsNotNone(wizard)
        self.assertEqual(wizard.stack.currentIndex(), 0)

    def test_wizard_step_navigation(self):
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog()
        wizard._go_to_page(1)
        self.assertEqual(wizard.stack.currentIndex(), 1)
        wizard._go_to_page(2)
        self.assertEqual(wizard.stack.currentIndex(), 2)
        wizard._go_to_page(4)
        self.assertEqual(wizard.stack.currentIndex(), 4)

    def test_wizard_ai_provider_change(self):
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog()
        wizard.combo_ai_provider.setCurrentIndex(1)  # OpenAI
        self.assertEqual(wizard.combo_ai_provider.currentData(), "openai")

    def test_wizard_populate_review_fields(self):
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog()
        test_data = {
            "personal": {
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
                "phone": "+911234567890",
                "current_city": "Mumbai",
                "country": "India",
                "linkedin_url": "https://linkedin.com/in/testuser",
                "github_url": "https://github.com/testuser",
            },
            "professional": {
                "current_title": "ML Engineer",
                "years_of_experience": 4.5,
                "notice_period_days": 60,
                "current_ctc": 800000,
                "expected_ctc": 1200000,
                "summary": "Experienced ML engineer.",
            },
            "skills": [{"name": "Python", "years": "4"}, {"name": "TensorFlow", "years": "3"}],
            "qna": {
                "authorized_in_india": "Yes",
                "authorized_in_us": "No",
                "require_sponsorship": "No",
                "open_to_relocation": "Yes",
                "comfortable_with_remote": "Yes",
            },
        }
        wizard._populate_review_fields(test_data)
        self.assertEqual(wizard.txt_rev_fname.text(), "Test")
        self.assertEqual(wizard.txt_rev_lname.text(), "User")
        self.assertEqual(wizard.txt_rev_email.text(), "test@example.com")
        self.assertEqual(wizard.txt_rev_title.text(), "ML Engineer")
        self.assertEqual(wizard.txt_rev_exp.text(), "4.5")
        self.assertIn("Python", wizard.skill_chips)
        self.assertIn("TensorFlow", wizard.skill_chips)

    def test_wizard_add_remove_skill_chip(self):
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog()
        wizard.skill_chips = ["Python", "Docker"]
        wizard.txt_new_skill.setText("React")
        wizard._add_skill_chip()
        self.assertIn("React", wizard.skill_chips)
        wizard._remove_skill_chip("Docker")
        self.assertNotIn("Docker", wizard.skill_chips)
        self.assertIn("Python", wizard.skill_chips)


class TestProfileOnboardingSync(unittest.TestCase):
    """Tests for ProfileService.apply_onboarding_data integration."""

    def setUp(self):
        from app.services.profile_service import ProfileService

        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "onboard_test.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)
        self.svc = ProfileService(session_factory=self.Session)
        self.svc.is_test = True

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_apply_onboarding_data_succeeds(self):
        user, profile, prof_profile = self.svc.get_primary_user_profile()

        test_data = {
            "personal": {
                "first_name": "TestUser",
                "last_name": "Onboard",
                "email": "testuser@jobpilot.test",
                "phone": "+919999999999",
                "current_city": "Bangalore",
                "state": "Karnataka",
                "country": "India",
                "linkedin_url": "",
                "github_url": "",
            },
            "professional": {
                "current_title": "QA Automation Engineer",
                "years_of_experience": 1.5,
                "notice_period_days": 15,
                "current_ctc": 400000,
                "expected_ctc": 600000,
                "summary": "Testing onboarding sync.",
            },
            "skills": [{"name": "Selenium", "years": "1"}, {"name": "Python", "years": "2"}],
            "qna": {
                "authorized_in_india": "Yes",
                "open_to_relocation": "No",
                "comfortable_with_remote": "Yes",
            },
        }
        ok, err = self.svc.apply_onboarding_data(user_id=user.id, data=test_data)
        self.assertTrue(ok, f"apply_onboarding_data failed: {err}")

        # Verify applied
        updated_user, updated_profile, updated_pro = self.svc.get_profile_by_user_id(user.id)
        self.assertEqual(updated_user.name, "TestUser Onboard")
        self.assertEqual(updated_pro.current_title, "QA Automation Engineer")
        self.assertEqual(updated_pro.years_of_experience, 1.5)


if __name__ == "__main__":
    unittest.main()
