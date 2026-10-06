"""Comprehensive test suite for Phase 14: Settings, Security, Backup & Sanitization."""

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import AppSetting
from app.db.session import configure_sqlite_pragmas
from app.services.backup_service import BackupService
from app.services.sanitizer_service import LogSanitizer, SanitizingLogFilter
from app.services.secrets_service import SecretsService
from app.services.settings_service import SettingsService
from app.ui.views.settings_view import SettingsView

app = QApplication.instance() or QApplication([])


class MockAutomationManager:
    """Mock coordinator for testing concurrency guards."""

    def __init__(self, running: bool = False):
        self._running = running

    def is_running(self) -> bool:
        return self._running


class TestSettingsSecurityBackup(unittest.TestCase):
    """Test suite covering encryption, pre-log sanitization, atomic backups, and settings UI."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase14_test.db")
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

        # Setup mock profile.json
        self.profile_path = os.path.join(self.temp_dir, "test_profile.json")
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump({
                "personal": {"first_name": "Test", "email": "test@example.com"},
                "professional": {"title": "Software Engineer"},
            }, f)

        # Setup mock resumes dir
        self.resumes_dir = os.path.join(self.temp_dir, "resumes")
        os.makedirs(self.resumes_dir, exist_ok=True)
        with open(os.path.join(self.resumes_dir, "sample_resume.pdf"), "w") as f:
            f.write("%PDF-1.4 Mock PDF Content")

        self.settings_service = SettingsService(session_factory=self.Session)
        self.backup_service = BackupService(
            db_path=self.db_path,
            profile_path=self.profile_path,
            resumes_dir=self.resumes_dir,
            session_factory=self.Session,
        )

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. SECRETS & ENCRYPTION TESTS
    # =========================================================================
    def test_secrets_encryption_and_decryption(self):
        """Verifies plaintext secrets are encrypted at rest with Fernet and decrypted on demand."""
        self.secrets_service.set_secret("linkedin_password", "MyP@ssw0rd123!")

        # Verify plaintext does NOT exist in raw database row
        with self.Session() as session:
            record = session.query(AppSetting).filter(AppSetting.key == "secret.linkedin_password").first()
            self.assertIsNotNone(record)
            raw_stored = record.value_json.get("encrypted", "")
            self.assertNotIn("MyP@ssw0rd123!", raw_stored)
            self.assertTrue(len(raw_stored) > 20)

        # Verify decryption works cleanly
        decrypted = self.secrets_service.get_secret("linkedin_password")
        self.assertEqual(decrypted, "MyP@ssw0rd123!")

    def test_partial_secret_update(self):
        """Verifies updating one secret does not modify or leak other existing secrets."""
        self.secrets_service.set_secret("user_a", "SecretA")
        self.secrets_service.set_secret("user_b", "SecretB")

        # Update only user_a
        self.secrets_service.set_secret("user_a", "SecretA_Updated")

        self.assertEqual(self.secrets_service.get_secret("user_a"), "SecretA_Updated")
        self.assertEqual(self.secrets_service.get_secret("user_b"), "SecretB")

    def test_platform_credentials_scoped_retrieval(self):
        """Verifies get_platform_credentials decrypts only the target platform credentials."""
        self.secrets_service.set_secret("linkedin_username", "user@linkedin.com")
        self.secrets_service.set_secret("linkedin_password", "Lipwd999")
        self.secrets_service.set_secret("naukri_username", "user@naukri.com")
        self.secrets_service.set_secret("naukri_password", "Nkpwd999")

        user, pwd = self.secrets_service.get_platform_credentials("linkedin")
        self.assertEqual(user, "user@linkedin.com")
        self.assertEqual(pwd, "Lipwd999")

    def test_secrets_masking(self):
        """Verifies secret masking produces safe strings for UI rendering."""
        masked_short = self.secrets_service.mask_secret("1234")
        self.assertEqual(masked_short, "••••••••")

        masked_long = self.secrets_service.mask_secret("sk-1234567890abcdef1234")
        self.assertEqual(masked_long, "sk-••••••••1234")

    def test_ollama_connection_without_api_key(self):
        """Verifies Ollama provider connection check works without requiring an API key."""
        ok, msg = self.secrets_service.test_ai_connection(
            provider="ollama",
            api_key=None,
            api_url="http://127.0.0.1:99999/v1/",  # Non-existent endpoint
        )
        self.assertFalse(ok)
        self.assertNotIn("API key is required", msg)

    # =========================================================================
    # 2. LOG SANITIZATION TESTS
    # =========================================================================
    def test_sanitizer_redacts_api_keys(self):
        """Verifies OpenAI and Gemini API keys are scrubbed."""
        raw = "Using OpenAI key sk-abcdef123456789012345678 and Gemini key AIzaSyD9876543210123456789012345678901"
        sanitized = LogSanitizer.sanitize_text(raw)
        self.assertNotIn("sk-abcdef", sanitized)
        self.assertNotIn("AIzaSyD987", sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)

    def test_sanitizer_redacts_bearer_and_cookies(self):
        """Verifies Bearer authorization tokens and session cookies are scrubbed."""
        raw = "Header Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 with cookie li_at=AQEDATk8332145"
        sanitized = LogSanitizer.sanitize_text(raw)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", sanitized)
        self.assertNotIn("AQEDATk8332145", sanitized)
        self.assertIn("[REDACTED_TOKEN]", sanitized)
        self.assertIn("[REDACTED_COOKIE]", sanitized)

    def test_sanitizer_redacts_passwords_and_exceptions(self):
        """Verifies passwords in logs and exception tracebacks are redacted before write."""
        raw = "Exception: password='SuperSecretPassword123' failed authentication"
        sanitized = LogSanitizer.sanitize_text(raw)
        self.assertNotIn("SuperSecretPassword123", sanitized)
        self.assertIn("password=[REDACTED]", sanitized)

        # Test logging filter
        logger = logging.getLogger("test_sanitizer_logger")
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=10,
            msg="User login with password='PlainTextSecret'",
            args=(),
            exc_info=None,
        )
        filter_obj = SanitizingLogFilter()
        filter_obj.filter(record)
        self.assertNotIn("PlainTextSecret", record.msg)
        self.assertIn("password=[REDACTED]", record.msg)

    # =========================================================================
    # 3. BACKUP & RESTORE INTEGRITY TESTS
    # =========================================================================
    def test_backup_creation_and_manifest(self):
        """Verifies backup archive contains database, profile, resumes, and valid SHA-256 manifest."""
        ok, archive_path, manifest = self.backup_service.create_backup(target_dir=self.temp_dir)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(archive_path))
        self.assertEqual(manifest["backup_format_version"], 1)

        # Check archive contents
        with zipfile.ZipFile(archive_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("database/jobpilot.db", namelist)
            self.assertIn("config/profile.json", namelist)
            self.assertIn("manifest.json", namelist)

            # Ensure machine encryption key is NEVER included in backups
            self.assertNotIn(".key", namelist)
            self.assertNotIn("test_key", namelist)

    def test_backup_blocked_while_automation_running(self):
        """Verifies backup creation is rejected when automation is active."""
        running_manager = MockAutomationManager(running=True)
        backup_svc = BackupService(
            db_path=self.db_path,
            automation_manager=running_manager,
        )
        ok, msg, _ = backup_svc.create_backup(target_dir=self.temp_dir)
        self.assertFalse(ok)
        self.assertIn("Cannot perform backup or restore while automation is running", msg)

    def test_restore_blocked_while_automation_running(self):
        """Verifies restore is rejected when automation is active."""
        running_manager = MockAutomationManager(running=True)
        backup_svc = BackupService(
            db_path=self.db_path,
            automation_manager=running_manager,
        )
        ok, msg = backup_svc.restore_backup("dummy_path.zip")
        self.assertFalse(ok)
        self.assertIn("Cannot perform backup or restore while automation is running", msg)

    def test_restore_corrupt_zip_fails_and_preserves_db(self):
        """Verifies corrupt archive fails in staging without touching active database."""
        # Record pre-restore state in DB
        with self.Session() as session:
            session.add(AppSetting(key="sentinel_key", value_json="active_db_value", category="general"))
            session.commit()

        # Create corrupt zip
        corrupt_zip = os.path.join(self.temp_dir, "corrupt.zip")
        with open(corrupt_zip, "w") as f:
            f.write("Not a real zip archive")

        ok, msg = self.backup_service.restore_backup(corrupt_zip)
        self.assertFalse(ok)

        # Verify active database remains completely intact
        with self.Session() as session:
            record = session.query(AppSetting).filter(AppSetting.key == "sentinel_key").first()
            self.assertIsNotNone(record)
            self.assertEqual(record.value_json, "active_db_value")

    def test_restore_hash_mismatch_fails_and_preserves_db(self):
        """Verifies tampered file in archive fails SHA-256 verification and leaves active DB untouched."""
        ok, archive_path, _ = self.backup_service.create_backup(target_dir=self.temp_dir)
        self.assertTrue(ok)

        # Tamper with the archive by inserting altered file without updating manifest
        tampered_zip = os.path.join(self.temp_dir, "tampered.zip")
        with zipfile.ZipFile(archive_path, "r") as zf_in:
            with zipfile.ZipFile(tampered_zip, "w") as zf_out:
                for item in zf_in.infolist():
                    data = zf_in.read(item.filename)
                    if item.filename == "config/profile.json":
                        data = b'{"tampered": true}'
                    zf_out.writestr(item, data)

        # Attempt restore
        restore_ok, restore_msg = self.backup_service.restore_backup(tampered_zip)
        self.assertFalse(restore_ok)
        self.assertIn("SHA-256 checksum mismatch", restore_msg)

    def test_restore_valid_archive_succeeds(self):
        """Verifies valid archive is staged, validated, and restored atomically."""
        # 1. Populate initial data & backup
        with self.Session() as session:
            session.add(AppSetting(key="backup_marker", value_json="saved_in_backup", category="general"))
            session.commit()

        ok, archive_path, _ = self.backup_service.create_backup(target_dir=self.temp_dir)
        self.assertTrue(ok)

        # 2. Alter current database
        with self.Session() as session:
            session.query(AppSetting).filter(AppSetting.key == "backup_marker").delete()
            session.add(AppSetting(key="new_marker", value_json="created_after_backup", category="general"))
            session.commit()

        # 3. Restore from archive
        restore_ok, restore_msg = self.backup_service.restore_backup(archive_path)
        self.assertTrue(restore_ok)
        self.assertIn("successfully", restore_msg.lower())

        # 4. Verify restored state
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT key, value_json FROM app_settings WHERE key = 'backup_marker'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertIn("saved_in_backup", row[1])

    # =========================================================================
    # 4. SETTINGS SERVICE & UI TESTS
    # =========================================================================
    def test_settings_section_reset(self):
        """Verifies resetting one section leaves other sections and secrets untouched."""
        self.settings_service.save_setting("click_gap", 8, category="general")
        self.settings_service.save_setting("run_in_background", True, category="browser")

        # Reset only general
        self.settings_service.reset_section("general")

        self.assertEqual(self.settings_service.get_setting("click_gap"), 1)  # Default
        self.assertEqual(self.settings_service.get_setting("run_in_background"), True)  # Untouched

    def test_settings_view_tabs_and_controls(self):
        """Verifies SettingsView builds all 6 tabs and initializes controls."""
        view = SettingsView(
            service=self.settings_service,
            secrets_service=self.secrets_service,
            backup_service=self.backup_service,
        )
        self.assertEqual(view.tabs.count(), 6)
        tab_titles = [view.tabs.tabText(i).replace("&&", "&") for i in range(view.tabs.count())]
        self.assertIn("General", tab_titles)
        self.assertIn("Browser", tab_titles)
        self.assertIn("Automation", tab_titles)
        self.assertIn("AI & Screening", tab_titles)
        self.assertIn("Credentials & Security", tab_titles)
        self.assertIn("Backup & Restore", tab_titles)

        # Password echo modes
        self.assertEqual(view.txt_li_pwd.echoMode(), view.txt_li_pwd.EchoMode.Password)
        self.assertEqual(view.txt_nk_pwd.echoMode(), view.txt_nk_pwd.EchoMode.Password)
        self.assertEqual(view.txt_ai_key.echoMode(), view.txt_ai_key.EchoMode.Password)

    def test_backup_archive_verification(self):
        """Verifies BackupService archive verification validates manifest, hashes, and SQLite integrity."""
        # 1. Create a valid backup
        ok, archive_path, manifest = self.backup_service.create_backup(target_dir=self.temp_dir)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(archive_path))

        # 2. Verify archive
        ok, msg, ver_manifest = self.backup_service.verify_backup(archive_path)
        self.assertTrue(ok)
        self.assertIn("Integrity verified", msg)
        self.assertIsNotNone(ver_manifest)

        # 3. Test non-existent archive
        bad_ok, bad_msg, _ = self.backup_service.verify_backup("/tmp/nonexistent_backup.zip")
        self.assertFalse(bad_ok)
        self.assertIn("missing backup archive", bad_msg)

    def test_universal_agent_setting(self):
        """Verifies Universal Agent toggle is configurable and persists through SettingsService."""
        # Check default value
        self.assertTrue(self.settings_service.is_universal_agent_enabled())

        # Toggle to false
        self.settings_service.save_setting("enable_universal_agent", False, category="automation")
        self.assertFalse(self.settings_service.is_universal_agent_enabled())

        # Toggle back to true
        self.settings_service.save_setting("enable_universal_agent", True, category="automation")
        self.assertTrue(self.settings_service.is_universal_agent_enabled())


if __name__ == "__main__":
    unittest.main()

