"""Comprehensive automated test suite for the redesigned System Settings & Security command center."""

import os
import shutil
import tempfile
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.services.backup_service import BackupService
from app.services.secrets_service import SecretsService
from app.services.settings_service import SettingsService
from app.ui.views.settings.presentation_model import SettingsPresentationModel
from app.ui.views.settings.settings_registry import search_settings
from app.ui.views.settings.settings_view import SettingsView

app = QApplication.instance() or QApplication([])


class TestSettingsRedesign(unittest.TestCase):
    """Test suite covering navigation, production defaults, dirty state, and search."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "redesign_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )

        self.key_path = os.path.join(self.temp_dir, ".test_key")
        self.secrets_service = SecretsService(key_path=self.key_path, session_factory=self.Session)
        self.settings_service = SettingsService(session_factory=self.Session)
        self.backup_service = BackupService(
            db_path=self.db_path,
            session_factory=self.Session,
        )

        self.view = SettingsView(
            service=self.settings_service,
            secrets_service=self.secrets_service,
            backup_service=self.backup_service,
        )
        self.view.show()

    def tearDown(self):
        self.view.close()
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. NAVIGATION & LAYOUT TESTS
    # =========================================================================
    def test_sidebar_and_sections_count(self):
        """Verifies 6 sections are registered in the stacked widget and sidebar."""
        self.assertEqual(self.view.stacked_widget.count(), 6)
        self.assertEqual(self.view.tabs.count(), 6)

        tab_names = [self.view.tabs.tabText(i) for i in range(6)]
        self.assertEqual(tab_names[0], "General")
        self.assertEqual(tab_names[1], "Browser")
        self.assertEqual(tab_names[2], "Automation")
        self.assertEqual(tab_names[3], "AI & Screening")
        self.assertEqual(tab_names[4], "Credentials & Security")
        self.assertEqual(tab_names[5], "Backup & Restore")

    def test_section_navigation(self):
        """Verifies clicking health bar chips or sidebar items navigates correctly."""
        # Switch to Browser
        self.view._switch_section_safe("browser")
        self.assertEqual(self.view.stacked_widget.currentIndex(), 1)

        # Switch to Automation
        self.view._switch_section_safe("automation")
        self.assertEqual(self.view.stacked_widget.currentIndex(), 2)

        # Switch to AI
        self.view._switch_section_safe("ai")
        self.assertEqual(self.view.stacked_widget.currentIndex(), 3)

        # Switch to Credentials
        self.view._switch_section_safe("credentials")
        self.assertEqual(self.view.stacked_widget.currentIndex(), 4)

        # Switch to Backup
        self.view._switch_section_safe("backup")
        self.assertEqual(self.view.stacked_widget.currentIndex(), 5)

    # =========================================================================
    # 2. EXACT PRODUCTION DEFAULTS TESTS
    # =========================================================================
    def test_exact_production_defaults(self):
        """Verifies all settings load with the exact production defaults specified in Phase 0."""
        # General defaults
        gen = self.view.general_section.get_values()
        self.assertEqual(gen["click_gap"], 1)
        self.assertFalse(gen["smooth_scroll"])
        self.assertFalse(gen["run_non_stop"])
        self.assertTrue(gen["alternate_sortby"])
        self.assertTrue(gen["cycle_date_posted"])

        # Browser defaults
        br = self.view.browser_section.get_values()
        self.assertFalse(br["run_in_background"])
        self.assertTrue(br["stealth_mode"])
        self.assertTrue(br["safe_mode"])
        self.assertFalse(br["disable_extensions"])
        self.assertTrue(br["keep_screen_awake"])

        # Automation defaults
        auto = self.view.automation_section.get_values()
        self.assertFalse(auto["pause_before_submit"])
        self.assertTrue(auto["pause_at_failed_question"])
        self.assertFalse(auto["follow_companies"])
        self.assertFalse(auto["close_tabs"])

        # AI defaults
        ai = self.view.ai_section.get_values()
        self.assertEqual(ai["provider"], "ollama")
        self.assertEqual(ai["model"], "llama3.1:8b")
        self.assertEqual(ai["api_url"], "http://localhost:11434/v1")

    # =========================================================================
    # 3. DIRTY STATE & SAVE WORKFLOW
    # =========================================================================
    def test_dirty_state_and_persistence(self):
        """Verifies modification activates dirty state, enables Save Changes, and updates DB."""
        self.assertFalse(self.view.presentation_model.is_any_dirty())
        self.assertFalse(self.view.btn_save.isEnabled())

        # Modify click gap
        self.view.spn_click_gap.setValue(5)
        self.assertTrue(self.view.presentation_model.is_category_dirty("general"))
        self.assertTrue(self.view.presentation_model.is_any_dirty())
        self.assertTrue(self.view.btn_save.isEnabled())
        self.assertIn("Unsaved", self.view.header.lbl_dirty.text())

        # Save Changes
        self.view.btn_save.click()
        self.assertFalse(self.view.presentation_model.is_any_dirty())
        self.assertFalse(self.view.btn_save.isEnabled())
        self.assertIn("saved successfully", self.view.notification_bar.message_label.text())

        # Verify persisted in database
        val = self.settings_service.get_setting("click_gap")
        self.assertEqual(val, 5)

    def test_section_reset(self):
        """Verifies Reset Section resets only the active category without altering other categories."""
        # Set non-default values in General and Browser
        self.view.spn_click_gap.setValue(7)
        self.view.browser_section.chk_headless.setChecked(True)
        self.view.btn_save.click()

        # Reset General section
        self.view.btn_reset.click()
        self.assertEqual(self.view.spn_click_gap.value(), 1)  # Default restored
        self.assertIn("Reset", self.view.notification_bar.message_label.text())

        # Browser remains untouched
        self.assertTrue(self.view.browser_section.chk_headless.isChecked())

    # =========================================================================
    # 4. CREDENTIAL ISOLATION & PASSWORDS
    # =========================================================================
    def test_credentials_isolation_and_echo_modes(self):
        """Verifies password inputs retain Password echo mode and secrets are encrypted."""
        self.assertEqual(self.view.txt_li_pwd.echoMode(), self.view.txt_li_pwd.EchoMode.Password)
        self.assertEqual(self.view.txt_nk_pwd.echoMode(), self.view.txt_nk_pwd.EchoMode.Password)
        self.assertEqual(self.view.txt_ai_key.echoMode(), self.view.txt_ai_key.EchoMode.Password)

        # Set secret through service
        self.secrets_service.set_secret("linkedin_username", "user@test.com")
        self.secrets_service.set_secret("linkedin_password", "SecretPass123!")
        self.view.load_credentials_display()

        # Verify card shows configured without exposing raw password and email is masked
        self.assertEqual(self.view.credentials_section.card_linkedin.lbl_status.text(), "● Configured")
        self.assertIn("us***@test.com", self.view.credentials_section.card_linkedin.lbl_account.text())
        self.assertEqual(self.view.credentials_section.card_linkedin.lbl_pwd_status.text(), "Password: ✓ Stored securely")

    # =========================================================================
    # 5. PREDICTABLE SEARCH NAVIGATION
    # =========================================================================
    def test_settings_search(self):
        """Verifies searching keywords maps to correct sections."""
        res_smtp = search_settings("smtp")
        self.assertTrue(len(res_smtp) > 0)
        self.assertEqual(res_smtp[0]["section"], "credentials")

        res_headless = search_settings("headless")
        self.assertTrue(len(res_headless) > 0)
        self.assertEqual(res_headless[0]["section"], "browser")

        res_delay = search_settings("timing")
        self.assertTrue(len(res_delay) > 0)
        self.assertEqual(res_delay[0]["section"], "general")

        res_ai = search_settings("ollama")
        self.assertTrue(len(res_ai) > 0)
        self.assertEqual(res_ai[0]["section"], "ai")

        res_backup = search_settings("restore")
        self.assertTrue(len(res_backup) > 0)
        self.assertEqual(res_backup[0]["section"], "backup")


if __name__ == "__main__":
    unittest.main()
