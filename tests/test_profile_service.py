"""Unit and UI test suite for ProfileService and ProfileView."""

import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import ProfessionalProfile, Profile, User
from app.db.session import configure_sqlite_pragmas
from app.services.profile_service import ProfileService


class TestProfileService(unittest.TestCase):
    """Unit tests for ProfileService business logic and validation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "profile_test.db")
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
        self.service = ProfileService(session_factory=self.Session)

        # Snapshot config/profile.json
        self.profile_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "profile.json")
        self.profile_backup = None
        if os.path.exists(self.profile_json_path):
            with open(self.profile_json_path, "r", encoding="utf-8") as f:
                self.profile_backup = f.read()

    def tearDown(self):
        if self.profile_backup and os.path.exists(self.profile_json_path):
            with open(self.profile_json_path, "w", encoding="utf-8") as f:
                f.write(self.profile_backup)
            try:
                import modules.config_loader as cfg_ldr
                cfg_ldr._PROFILE_CACHE = None
            except Exception:
                pass
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_or_create_primary_profile(self):
        """Verifies creating default primary candidate user and profile when empty."""
        user, profile, pro = self.service.get_primary_user_profile()
        self.assertIsNotNone(user)
        self.assertIn("@", user.email)

    def test_save_profile_success(self):
        """Verifies valid profile updates are saved to database."""
        user, _, _ = self.service.get_primary_user_profile()

        personal = {
            "first_name": "Jordan",
            "last_name": "Lee",
            "email": "jordan.lee@example.com",
            "phone_number": "+91 9988776655",
            "current_city": "Gurugram",
            "state": "Haryana",
            "country": "India",
            "zipcode": "122001",
            "address": "DLF Cyber City",
            "willing_to_relocate": True,
        }

        professional = {
            "title": "Lead SDET",
            "current_employer": "FinTech Innovations",
            "years_of_experience": 5.5,
            "current_ctc": 1500000,
            "expected_ctc": 2200000,
            "notice_period_days": 60,
            "skills": "Python, Selenium, PyTest, Docker",
            "headline": "Lead SDET | Automation Architect",
            "summary": "Building automated quality gates for enterprise services.",
            "linkedin_url": "https://linkedin.com/in/jordanlee",
            "github_url": "https://github.com/jordanlee",
        }

        success, err = self.service.save_profile(user.id, personal, professional)
        self.assertTrue(success)
        self.assertIsNone(err)

        # Inspect persisted records
        saved_user, saved_profile, saved_pro = self.service.get_profile_by_user_id(user.id)
        self.assertEqual(saved_user.name, "Jordan Lee")
        self.assertEqual(saved_user.email, "jordan.lee@example.com")
        self.assertEqual(saved_profile.current_city, "Gurugram")
        self.assertTrue(saved_profile.willing_to_relocate)

        self.assertEqual(saved_pro.current_title, "Lead SDET")
        self.assertEqual(saved_pro.years_of_experience, 5.5)
        self.assertEqual(saved_pro.current_ctc, 1500000)
        self.assertEqual(saved_pro.expected_ctc, 2200000)
        self.assertEqual(saved_pro.notice_period_days, 60)
        self.assertIn("Selenium", saved_pro.skills)

    def test_save_profile_invalid_email_rejected(self):
        """Verifies malformed emails are rejected."""
        user, _, _ = self.service.get_primary_user_profile()
        personal = {"first_name": "A", "last_name": "B", "email": "invalid-email"}
        professional = {"title": "Engineer"}

        success, err = self.service.save_profile(user.id, personal, professional)
        self.assertFalse(success)
        self.assertIn("valid candidate email", err)

    def test_save_profile_negative_experience_rejected(self):
        """Verifies negative experience is rejected."""
        user, _, _ = self.service.get_primary_user_profile()
        personal = {"first_name": "A", "last_name": "B", "email": "a@b.com"}
        professional = {"title": "Engineer", "years_of_experience": -2.0}

        success, err = self.service.save_profile(user.id, personal, professional)
        self.assertFalse(success)
        self.assertIn("cannot be negative", err)

    def test_save_profile_negative_ctc_rejected(self):
        """Verifies negative CTC values are rejected."""
        user, _, _ = self.service.get_primary_user_profile()
        personal = {"first_name": "A", "last_name": "B", "email": "a@b.com"}
        professional = {"title": "Engineer", "current_ctc": -500000}

        success, err = self.service.save_profile(user.id, personal, professional)
        self.assertFalse(success)
        self.assertIn("cannot be negative", err)

    def test_validate_completeness_scoring(self):
        """Verifies completeness scoring and readiness determination."""
        user, _, _ = self.service.get_primary_user_profile()

        # Incomplete profile initially
        eval_before = self.service.validate_completeness(user.id)
        self.assertFalse(eval_before["is_ready"])
        self.assertGreater(len(eval_before["missing_critical"]), 0)

        # Populate complete candidate
        personal = {
            "first_name": "Sam",
            "last_name": "Taylor",
            "email": "sam@example.com",
            "phone_number": "+1234567890",
            "current_city": "Mumbai",
        }
        professional = {
            "title": "Software Engineer",
            "years_of_experience": 3.0,
            "current_ctc": 800000,
            "expected_ctc": 1400000,
            "notice_period_days": 30,
            "skills": "Python, SQL",
            "linkedin_url": "https://linkedin.com/in/samtaylor",
            "summary": "Experienced software developer.",
        }
        self.service.save_profile(user.id, personal, professional)

        eval_after = self.service.validate_completeness(user.id)
        self.assertTrue(eval_after["is_ready"])
        self.assertEqual(len(eval_after["missing_critical"]), 0)
        self.assertGreaterEqual(eval_after["score"], 90)


class TestProfileView(unittest.TestCase):
    """Headless UI tests for PySide6 ProfileView component."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "view_test.db")
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
        self.service = ProfileService(session_factory=self.Session)

        # Snapshot config/profile.json
        self.profile_json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "profile.json")
        self.profile_backup = None
        if os.path.exists(self.profile_json_path):
            with open(self.profile_json_path, "r", encoding="utf-8") as f:
                self.profile_backup = f.read()

    def tearDown(self):
        if self.profile_backup and os.path.exists(self.profile_json_path):
            with open(self.profile_json_path, "w", encoding="utf-8") as f:
                f.write(self.profile_backup)
            try:
                import modules.config_loader as cfg_ldr
                cfg_ldr._PROFILE_CACHE = None
            except Exception:
                pass
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_profile_view_rendering_and_interaction(self):
        """Verifies ProfileView populates from DB, responds to save, reset, and readiness clicks."""
        from app.ui.views.profile_view import ProfileView

        view = ProfileView(service=self.service)
        view.show()
        self.assertIsNotNone(view.current_user_id)

        # Check default loaded values
        self.assertIn("@", view.txt_email.text())

        # Edit fields
        view.txt_first_name.setText("Morgan")
        view.txt_last_name.setText("Freeman")
        view.txt_email.setText("morgan.freeman@example.com")
        view.txt_title.setText("Principal Automation Engineer")
        view.txt_city.setText("Bengaluru")
        view.txt_current_ctc.setText("1800000")
        view.txt_expected_ctc.setText("2500000")
        view.spn_notice.setValue(45)

        # Trigger Save
        view.btn_save.click()
        self.assertIn("saved to database", view.notification_bar.message_label.text())

        # Verify persisted in database
        saved_user, _, saved_pro = self.service.get_profile_by_user_id(view.current_user_id)
        self.assertEqual(saved_user.email, "morgan.freeman@example.com")
        self.assertEqual(saved_user.name, "Morgan Freeman")
        self.assertEqual(saved_pro.current_title, "Principal Automation Engineer")
        self.assertEqual(saved_pro.current_ctc, 1800000)

        # Edit field without saving and trigger Reset
        view.txt_city.setText("Unsaved City")
        view.btn_reset.click()
        self.assertEqual(view.txt_city.text(), "Bengaluru")

        # Trigger Check Readiness
        view.btn_validate.click()
        self.assertTrue(view.notification_bar.isVisible())
        self.assertIn("Readiness", view.notification_bar.message_label.text())


if __name__ == "__main__":
    unittest.main()
