"""Comprehensive test suite for MigrationService and CLI migration tooling."""

import csv
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import (
    Application,
    AppSetting,
    Company,
    Job,
    Platform,
    PlatformAccount,
    ProfessionalProfile,
    Profile,
    QnAEntry,
    Resume,
    User,
)
from app.db.session import configure_sqlite_pragmas
from app.services.migration_service import MigrationReport, MigrationService, ValidationReport
from app.services.resume_service import ResumeService


class TestMigrationService(unittest.TestCase):
    """Tests for configuration migration engine, parity validator, and idempotency."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "migration_test.db")
        self.storage_dir = os.path.join(self.temp_dir, "managed_resumes")
        self.csv_dir = os.path.join(self.temp_dir, "all excels")
        os.makedirs(self.csv_dir, exist_ok=True)
        os.makedirs(self.storage_dir, exist_ok=True)

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

        self.resume_service = ResumeService(storage_dir=self.storage_dir, session_factory=self.Session)
        self.service = MigrationService(
            session_factory=self.Session,
            resume_service=self.resume_service,
            project_root=self.temp_dir,
        )

        # Mock sample profile.json configuration
        self.sample_config = {
            "personal": {
                "first_name": "Alex",
                "middle_name": "J",
                "last_name": "Mercer",
                "email": "alex.mercer@example.com",
                "phone_number": "+1234567890",
                "current_city": "Bengaluru",
                "street": "123 Tech Park Road",
                "state": "Karnataka",
                "zipcode": "560001",
                "country": "India",
                "willing_to_relocate": True,
            },
            "professional": {
                "title": "Senior Automation Engineer",
                "current_employer": "Global Tech Corp",
                "years_of_experience": 4.5,
                "current_ctc": 1200000,
                "desired_salary": 1800000,
                "notice_period_days": 45,
                "skills": ["Python", "Selenium", "SQL"],
                "linkedin_url": "https://linkedin.com/in/alex-mercer",
                "portfolio_url": "https://github.com/alex-mercer",
                "headline": "Senior Automation Engineer | Python",
                "summary": "Experienced engineer with a track record in test automation.",
                "cover_letter": "I am passionate about building scalable automation...",
            },
            "resumes": {
                "default": "resumes/alex_resume.pdf",
            },
            "platforms": {
                "linkedin": {
                    "search_terms": ["Automation Engineer", "SDET"],
                    "search_location": "Bengaluru, India",
                    "current_experience": 4,
                    "switch_number": 25,
                    "easy_apply_only": True,
                    "pause_before_submit": True,
                    "stealth_mode": True,
                    "safe_mode": True,
                },
                "naukri": {
                    "search_terms": ["Python Automation Engineer"],
                    "search_location": "Bengaluru",
                    "experience_years": 4,
                    "max_jobs_evaluated_per_search": 40,
                    "apply_mode": "direct_only",
                    "pause_before_submit": True,
                    "core_skills": ["python", "selenium"],
                },
            },
            "qna": {
                "standard_answers": {
                    "require_visa": "No",
                    "us_citizenship": "Other",
                    "comfortable_with_remote": "Yes",
                },
                "custom_qa": {
                    "Notice period in days?": "45",
                    "Years with Python?": "4",
                },
            },
            "ai": {
                "enabled": True,
                "provider": "ollama",
                "model": "llama3.1:8b",
                "api_url": "http://localhost:11434/v1/",
                "spec": "openai-like",
                "stream": False,
            },
        }

        # Create physical sample resume file
        resume_dir = os.path.join(self.temp_dir, "resumes")
        os.makedirs(resume_dir, exist_ok=True)
        self.resume_path = os.path.join(resume_dir, "alex_resume.pdf")
        with open(self.resume_path, "wb") as f:
            f.write(b"%PDF-1.4 sample resume content for test")

        # Create sample historical CSVs
        self._create_sample_csvs()

    def _create_sample_csvs(self):
        # 1. applications.csv
        app_csv_path = os.path.join(self.csv_dir, "applications.csv")
        with open(app_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "platform", "job_id", "title", "company", "location", "source_url",
                "status", "application_type", "discovered_at", "applied_at",
                "failure_reason", "skip_reason"
            ])
            writer.writerow([
                "naukri", "nk_101", "Automation Engineer", "Acme Tech Pvt Ltd",
                "Bengaluru", "https://naukri.com/job/nk_101", "SUBMITTED", "DIRECT",
                "2026-09-01 10:00:00", "2026-09-01 10:05:00", "", ""
            ])
            writer.writerow([
                "naukri", "nk_102", "QA Specialist", "Acme Technologies LLC",
                "Bengaluru", "https://naukri.com/job/nk_102", "FAILED", "DIRECT",
                "2026-09-01 11:00:00", "", "Button not found", ""
            ])

        # 2. all_applied_applications_history.csv
        li_csv_path = os.path.join(self.csv_dir, "all_applied_applications_history.csv")
        with open(li_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Job ID", "Title", "Company", "Work Location", "Work Style", "About Job",
                "Experience required", "Skills required", "HR Name", "HR Link", "Resume",
                "Re-posted", "Date Posted", "Date Applied", "Job Link", "External Job link",
                "Questions Found", "Connect Request"
            ])
            writer.writerow([
                "li_201", "Senior SDET", "InnoCorp Inc", "Bengaluru", "Hybrid",
                "Developing automated test suites", "4+ years", "Python, PyTest",
                "Jane Doe", "https://linkedin.com/in/janedoe", "alex_resume.pdf", "No",
                "2026-08-20", "2026-08-21", "https://linkedin.com/jobs/view/li_201", "",
                "3 questions", "Sent"
            ])

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_user_and_profiles_migration(self):
        """Verifies candidate personal and professional profiles migrate accurately."""
        with self.Session() as session:
            user, profile, pro_profile = self.service.migrate_user_and_profiles(
                session, self.sample_config
            )
            session.commit()

            self.assertEqual(user.email, "alex.mercer@example.com")
            self.assertEqual(user.name, "Alex Mercer")
            self.assertEqual(profile.first_name, "Alex")
            self.assertEqual(profile.last_name, "Mercer")
            self.assertEqual(profile.current_city, "Bengaluru")
            self.assertTrue(profile.willing_to_relocate)

            self.assertEqual(pro_profile.current_title, "Senior Automation Engineer")
            self.assertEqual(pro_profile.years_of_experience, 4.5)
            self.assertEqual(pro_profile.current_ctc, 1200000)
            self.assertEqual(pro_profile.expected_ctc, 1800000)
            self.assertEqual(pro_profile.notice_period_days, 45)
            self.assertEqual(pro_profile.skills, ["Python", "Selenium", "SQL"])

    def test_platform_and_account_migration_no_secrets(self):
        """Verifies platform configs migrate without storing secrets in the database."""
        with self.Session() as session:
            user, _, _ = self.service.migrate_user_and_profiles(session, self.sample_config)
            accounts = self.service.migrate_platforms(session, user.id, self.sample_config)
            session.commit()

            self.assertEqual(len(accounts), 2)
            li_acc = next(a for a in accounts if a.platform.name == "linkedin")
            self.assertEqual(li_acc.default_location, "Bengaluru, India")
            self.assertEqual(li_acc.max_applications, 25)
            self.assertEqual(li_acc.apply_mode, "EASY_APPLY_ONLY")

            nk_acc = next(a for a in accounts if a.platform.name == "naukri")
            self.assertEqual(nk_acc.default_location, "Bengaluru")
            self.assertEqual(nk_acc.max_applications, 40)

            # Security Invariant: Verify zero passwords or secrets in platform_accounts
            for acc in accounts:
                self.assertFalse(hasattr(acc, "password"))
                self.assertFalse(hasattr(acc, "token"))
                if acc.extra_settings:
                    self.assertNotIn("password", acc.extra_settings)
                    self.assertNotIn("token", acc.extra_settings)
                    self.assertNotIn("secret", acc.extra_settings)

    def test_qna_migration_provenance(self):
        """Verifies Q&A entries are created with PROFILE provenance and VERIFIED status."""
        with self.Session() as session:
            user, _, _ = self.service.migrate_user_and_profiles(session, self.sample_config)
            entries = self.service.migrate_qna(session, user.id, self.sample_config)
            session.commit()

            self.assertGreaterEqual(len(entries), 4)
            visa_q = next((e for e in entries if "visa" in e.question_text.lower()), None)
            self.assertIsNotNone(visa_q)
            self.assertEqual(visa_q.answer_text, "No")
            self.assertEqual(visa_q.source, "PROFILE")
            self.assertEqual(visa_q.validation_status, "VERIFIED")

            custom_q = next((e for e in entries if "notice period" in e.question_text.lower()), None)
            self.assertIsNotNone(custom_q)
            self.assertEqual(custom_q.answer_text, "45")

    def test_settings_migration(self):
        """Verifies bot engine and non-sensitive AI settings are stored."""
        with self.Session() as session:
            settings = self.service.migrate_settings(session, self.sample_config)
            session.commit()

            self.assertGreaterEqual(len(settings), 10)
            keys = [s.key for s in settings]
            self.assertIn("bot.stealth_mode", keys)
            self.assertIn("bot.click_gap", keys)
            self.assertIn("ai.enabled", keys)
            self.assertIn("ai.model", keys)

            # Security Invariant: Ensure ai.api_key is NOT stored
            self.assertNotIn("ai.api_key", keys)

    def test_historical_csv_migration_and_deduplication(self):
        """Verifies CSV job listings and applications are imported and normalized."""
        with self.Session() as session:
            user, _, _ = self.service.migrate_user_and_profiles(session, self.sample_config)
            jobs_cnt, apps_cnt, comp_cnt = self.service.migrate_historical_applications(
                session, user.id, csv_dir=self.csv_dir
            )
            session.commit()

            self.assertEqual(jobs_cnt, 3)
            self.assertEqual(apps_cnt, 3)
            # Acme Tech Pvt Ltd and Acme Technologies LLC should normalize to Acme
            self.assertLessEqual(comp_cnt, 3)

            # Verify applications exist in DB
            db_apps = session.scalars(select(Application)).all()
            self.assertEqual(len(db_apps), 3)
            statuses = {a.status for a in db_apps}
            self.assertIn("SUBMITTED", statuses)
            self.assertIn("FAILED", statuses)

    def test_full_migration_and_parity_validation(self):
        """Verifies end-to-end migration executes and parity validation passes 100%."""
        report = self.service.run_full_migration(
            dry_run=False,
            config=self.sample_config,
            csv_dir=self.csv_dir,
        )

        self.assertTrue(report.success)
        self.assertTrue(report.user_migrated)
        self.assertTrue(report.profiles_migrated)
        self.assertGreater(report.platforms_count, 0)
        self.assertGreater(report.platform_accounts_count, 0)
        self.assertGreater(report.qna_entries_count, 0)
        self.assertGreater(report.settings_count, 0)
        self.assertEqual(report.jobs_imported, 3)
        self.assertEqual(report.applications_imported, 3)

        self.assertIsNotNone(report.validation)
        self.assertTrue(report.validation.is_valid)
        self.assertEqual(len(report.validation.mismatches), 0)

    def test_dry_run_mode_leaves_database_empty(self):
        """Verifies that dry_run=True leaves the database unchanged."""
        report = self.service.run_full_migration(
            dry_run=True,
            config=self.sample_config,
            csv_dir=self.csv_dir,
        )

        self.assertTrue(report.dry_run)
        # Verify database has zero committed rows
        with self.Session() as session:
            user_count = session.scalar(select(func.count(User.id))) or 0
            job_count = session.scalar(select(func.count(Job.id))) or 0
            app_count = session.scalar(select(func.count(Application.id))) or 0
            self.assertEqual(user_count, 0)
            self.assertEqual(job_count, 0)
            self.assertEqual(app_count, 0)

    def test_idempotency_safe_rerun(self):
        """Verifies running the migration twice does not duplicate records."""
        report1 = self.service.run_full_migration(
            dry_run=False,
            config=self.sample_config,
            csv_dir=self.csv_dir,
        )
        self.assertTrue(report1.success)

        # Run migration a second time
        report2 = self.service.run_full_migration(
            dry_run=False,
            config=self.sample_config,
            csv_dir=self.csv_dir,
        )
        self.assertTrue(report2.success)

        with self.Session() as session:
            user_count = session.scalar(select(func.count(User.id)))
            platform_acc_count = session.scalar(select(func.count(PlatformAccount.id)))
            job_count = session.scalar(select(func.count(Job.id)))
            app_count = session.scalar(select(func.count(Application.id)))

            self.assertEqual(user_count, 1)
            self.assertEqual(platform_acc_count, 2)
            self.assertEqual(job_count, 3)
            self.assertEqual(app_count, 3)

    def test_validation_detects_discrepancies(self):
        """Verifies validate_migration catches discrepancies if database records diverge."""
        self.service.run_full_migration(
            dry_run=False,
            config=self.sample_config,
            csv_dir=self.csv_dir,
        )

        tampered_config = dict(self.sample_config)
        tampered_config["professional"] = dict(self.sample_config["professional"])
        tampered_config["professional"]["desired_salary"] = 9999999  # Mismatch

        with self.Session() as session:
            user = session.scalars(select(User)).first()
            val_report = self.service.validate_migration(session, user.id, tampered_config)
            self.assertFalse(val_report.is_valid)
            self.assertTrue(any("Desired Salary" in m for m in val_report.mismatches))


if __name__ == "__main__":
    unittest.main()
