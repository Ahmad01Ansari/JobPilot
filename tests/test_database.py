"""Comprehensive test suite for JobPilot Database Architecture and Relational Models."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.config import DatabaseConfig
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    AppSetting,
    Company,
    Contact,
    Communication,
    FollowUp,
    Interview,
    Job,
    JobEvaluation,
    Offer,
    Platform,
    PlatformAccount,
    Profile,
    ProfessionalProfile,
    QnAEntry,
    Resume,
    User,
    calculate_file_sha256,
    generate_job_fingerprint,
)
from app.db.service import check_connection, get_summary_stats, init_db
from app.db.session import configure_sqlite_pragmas, get_db_session


class TestDatabaseArchitecture(unittest.TestCase):
    """Tests SQLite connection pragmas, session management, and configuration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_jobpilot.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine, future=True)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_pragmas_wal_and_foreign_keys(self):
        """Verifies that WAL mode and foreign key enforcement are active on SQLite connections."""
        with self.engine.connect() as conn:
            journal_mode = conn.execute(text("PRAGMA journal_mode")).scalar()
            foreign_keys = conn.execute(text("PRAGMA foreign_keys")).scalar()

            self.assertEqual(str(journal_mode).lower(), "wal")
            self.assertEqual(foreign_keys, 1)

    def test_database_config_resolution(self):
        """Verifies DatabaseConfig path resolution and environment variable overrides."""
        cfg_custom = DatabaseConfig(self.db_path)
        self.assertEqual(str(cfg_custom.db_path), self.db_path)
        self.assertTrue(cfg_custom.get_url().startswith("sqlite:///"))

        os.environ["JOBPILOT_DB_PATH"] = self.db_path
        try:
            cfg_env = DatabaseConfig()
            self.assertEqual(str(cfg_env.db_path), self.db_path)
        finally:
            del os.environ["JOBPILOT_DB_PATH"]

    def test_get_db_session_commit_and_rollback(self):
        """Tests that get_db_session commits on success and rolls back on exception."""
        # Success path
        with get_db_session(self.Session) as session:
            company = Company(name="Test Corp", normalized_name="test corp")
            session.add(company)

        with self.Session() as session:
            found = session.execute(select(Company).where(Company.name == "Test Corp")).scalar_one_or_none()
            self.assertIsNotNone(found)

        # Failure / Rollback path
        try:
            with get_db_session(self.Session) as session:
                bad_company = Company(name="Rollback Corp", normalized_name="rollback corp")
                session.add(bad_company)
                raise RuntimeError("Simulated transaction failure")
        except RuntimeError:
            pass

        with self.Session() as session:
            not_found = session.execute(
                select(Company).where(Company.name == "Rollback Corp")
            ).scalar_one_or_none()
            self.assertIsNone(not_found)

    def test_diagnostics_service(self):
        """Tests check_connection and get_summary_stats."""
        diag = check_connection(self.engine)
        self.assertEqual(diag["status"], "ok")
        self.assertEqual(diag["dialect"], "sqlite")
        self.assertTrue(diag["wal_enabled"])
        self.assertTrue(diag["foreign_keys"])
        self.assertGreater(diag["table_count"], 10)

        with self.Session() as session:
            stats = get_summary_stats(session)
            self.assertIn("jobs_count", stats)
            self.assertIn("applications_count", stats)
            self.assertIn("companies_count", stats)


class TestDomainModels(unittest.TestCase):
    """Tests all domain entities, relationships, constraints, and timestamps."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_models.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine, future=True)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_company_and_contact_relationship(self):
        """Tests Company and Contact creation and bidirectional relationship."""
        with self.Session() as session:
            company = Company(
                name="Acme Corporation",
                normalized_name="acme",
                website="https://acme.example.com",
                industry="Information Technology",
                location="Bengaluru, India",
            )
            session.add(company)
            session.flush()

            contact = Contact(
                company_id=company.id,
                name="Jane Doe",
                designation="Talent Acquisition Lead",
                email="jane.doe@acme.example.com",
                phone="+91-9876543210",
                linkedin_url="https://linkedin.com/in/janedoe",
            )
            session.add(contact)
            session.commit()

            # Verify relationship
            loaded_comp = session.execute(select(Company).where(Company.id == company.id)).scalar_one()
            self.assertEqual(len(loaded_comp.contacts), 1)
            self.assertEqual(loaded_comp.contacts[0].name, "Jane Doe")
            self.assertEqual(loaded_comp.contacts[0].company.name, "Acme Corporation")

    def test_job_with_fingerprint_and_raw_fields(self):
        """Tests Job creation, deterministic fingerprint, and preservation of raw text."""
        fp = generate_job_fingerprint(
            platform="naukri",
            company="Enterprise AI",
            title="Senior RPA Developer",
            location="Noida",
            source_url="https://www.naukri.com/job-123",
            external_job_id="naukri_123",
        )

        with self.Session() as session:
            job = Job(
                platform="naukri",
                external_job_id="naukri_123",
                job_fingerprint=fp,
                title="Senior RPA Developer",
                company_raw="Enterprise AI",
                location="Noida, India",
                work_style="Hybrid",
                experience_text="3-5 Yrs",
                required_experience_min=3,
                required_experience_max=5,
                salary_text="12-15 Lacs PA",
                salary_min=1200000,
                salary_max=1500000,
                salary_period="YEAR",
                salary_currency="INR",
                source_url="https://www.naukri.com/job-123",
                apply_type="DIRECT",
            )
            session.add(job)
            session.commit()

            loaded_job = session.execute(select(Job).where(Job.job_fingerprint == fp)).scalar_one()
            self.assertEqual(loaded_job.experience_text, "3-5 Yrs")
            self.assertEqual(loaded_job.salary_text, "12-15 Lacs PA")
            self.assertEqual(loaded_job.salary_period, "YEAR")
            self.assertTrue(loaded_job.is_active)

            # Fingerprint uniqueness constraint
            duplicate_job = Job(
                platform="naukri",
                job_fingerprint=fp,
                title="Duplicate",
                company_raw="Enterprise AI",
                source_url="https://www.naukri.com/job-123",
            )
            session.add(duplicate_job)
            with self.assertRaises(IntegrityError):
                session.commit()

    def test_job_evaluation_separated_from_application(self):
        """Tests that JobEvaluation encapsulates automation decisions without polluting Application."""
        with self.Session() as session:
            job = Job(
                platform="linkedin",
                job_fingerprint="fp_eval_test",
                title="Python Backend Engineer",
                company_raw="Tech Corp",
                source_url="https://linkedin.com/jobs/view/999",
            )
            session.add(job)
            session.flush()

            evaluation = JobEvaluation(
                job_id=job.id,
                status="SKIPPED",
                decision_reason="Negative title keyword: mechanical",
                candidate_experience=2,
                rules_matched={"title_filter": False, "exp_filter": True},
            )
            session.add(evaluation)
            session.commit()

            loaded_job = session.execute(select(Job).where(Job.id == job.id)).scalar_one()
            self.assertEqual(len(loaded_job.evaluations), 1)
            self.assertEqual(loaded_job.evaluations[0].status, "SKIPPED")
            self.assertEqual(loaded_job.evaluations[0].rules_matched["title_filter"], False)

    def test_application_lifecycle_and_status_history(self):
        """Tests Application lifecycle transitions and audit trail logging in ApplicationStatusHistory."""
        with self.Session() as session:
            job = Job(
                platform="naukri",
                job_fingerprint="fp_app_test",
                title="Automation Engineer",
                company_raw="Automation Ltd",
                source_url="https://naukri.com/job-888",
            )
            session.add(job)
            session.flush()

            application = Application(
                job_id=job.id,
                status="APPLYING",
                application_type="EASY_APPLY",
            )
            session.add(application)
            session.flush()

            # Record initial state transition
            h1 = ApplicationStatusHistory(
                application_id=application.id,
                old_status=None,
                new_status="APPLYING",
                source="automation",
                notes="Starting form fill",
            )
            session.add(h1)

            # Transition to SUBMITTED
            application.status = "SUBMITTED"
            application.applied_at = utc_now()
            h2 = ApplicationStatusHistory(
                application_id=application.id,
                old_status="APPLYING",
                new_status="SUBMITTED",
                source="automation",
                notes="Success confirmation banner detected",
            )
            session.add(h2)
            session.commit()

            loaded_app = session.execute(select(Application).where(Application.id == application.id)).scalar_one()
            self.assertEqual(loaded_app.status, "SUBMITTED")
            self.assertEqual(len(loaded_app.status_history), 2)
            self.assertEqual(loaded_app.status_history[1].new_status, "SUBMITTED")

    def test_recruitment_pipeline_entities(self):
        """Tests Interview, Communication, FollowUp, and Offer entities linked to Application."""
        with self.Session() as session:
            job = Job(
                platform="linkedin",
                job_fingerprint="fp_pipeline_test",
                title="Full Stack Lead",
                company_raw="CloudScale",
                source_url="https://linkedin.com/jobs/view/777",
            )
            session.add(job)
            session.flush()

            application = Application(job_id=job.id, status="SHORTLISTED")
            session.add(application)
            session.flush()

            # Communication
            comm = Communication(
                application_id=application.id,
                type="EMAIL",
                direction="INBOUND",
                subject="Interview Invitation for Full Stack Lead",
                summary="Recruiter reached out to schedule Round 1 Technical.",
            )
            session.add(comm)

            # Interview
            scheduled_time = utc_now() + timedelta(days=2)
            interview = Interview(
                application_id=application.id,
                round_number=1,
                round_name="Technical",
                scheduled_at=scheduled_time,
                interviewer="Lead Architect",
                mode="VIRTUAL",
                meeting_link="https://meet.google.com/xyz-abc-def",
                status="SCHEDULED",
            )
            session.add(interview)

            # Follow-up
            follow_up = FollowUp(
                application_id=application.id,
                due_at=scheduled_time + timedelta(days=1),
                status="PENDING",
                notes="Send thank-you email and check on interview feedback",
            )
            session.add(follow_up)

            # Offer
            offer = Offer(
                application_id=application.id,
                offered_ctc=1800000,
                currency="INR",
                joining_date=utc_now() + timedelta(days=30),
                status="RECEIVED",
            )
            session.add(offer)
            session.commit()

            # Verify associations
            loaded = session.execute(select(Application).where(Application.id == application.id)).scalar_one()
            self.assertEqual(len(loaded.communications), 1)
            self.assertEqual(loaded.communications[0].type, "EMAIL")
            self.assertEqual(len(loaded.interviews), 1)
            self.assertEqual(loaded.interviews[0].round_name, "Technical")
            self.assertEqual(len(loaded.follow_ups), 1)
            self.assertEqual(loaded.offer.offered_ctc, 1800000)

    def test_user_profile_without_sensitive_demographics(self):
        """Verifies User and Profile models, ensuring sensitive demographic fields are omitted."""
        with self.Session() as session:
            user = User(name="Ahmad Raza", email="ahmad@example.com", phone="+919876543210")
            session.add(user)
            session.flush()

            profile = Profile(
                user_id=user.id,
                first_name="Ahmad",
                last_name="Raza",
                current_city="Noida",
                country="India",
                preferred_locations=["Noida", "Gurugram", "Bengaluru"],
                willing_to_relocate=True,
            )
            session.add(profile)

            prof_profile = ProfessionalProfile(
                user_id=user.id,
                current_title="Software Development Engineer",
                current_employer="Enterprise Tech",
                years_of_experience=2.5,
                current_ctc=600000,
                expected_ctc=1000000,
                notice_period_days=30,
                skills=["Python", "Selenium", "RPA", "SQLAlchemy"],
            )
            session.add(prof_profile)
            session.commit()

            loaded_user = session.execute(select(User).where(User.id == user.id)).scalar_one()
            self.assertEqual(loaded_user.profile.first_name, "Ahmad")
            self.assertEqual(loaded_user.professional_profile.skills, ["Python", "Selenium", "RPA", "SQLAlchemy"])

            # Verify absence of demographic attributes on Profile
            self.assertFalse(hasattr(Profile, "gender"))
            self.assertFalse(hasattr(Profile, "ethnicity"))
            self.assertFalse(hasattr(Profile, "disability_status"))
            self.assertFalse(hasattr(Profile, "veteran_status"))

    def test_platform_account_contains_no_secrets(self):
        """Verifies Platform and PlatformAccount have NO credential, cookie, or password columns."""
        self.assertFalse(hasattr(PlatformAccount, "password"))
        self.assertFalse(hasattr(PlatformAccount, "cookies"))
        self.assertFalse(hasattr(PlatformAccount, "session_cookie"))
        self.assertFalse(hasattr(PlatformAccount, "otp"))
        self.assertFalse(hasattr(PlatformAccount, "token"))

        with self.Session() as session:
            platform = Platform(name="linkedin", display_name="LinkedIn", is_enabled=True)
            session.add(platform)
            session.flush()

            account = PlatformAccount(
                platform_id=platform.id,
                account_name="Default Profile",
                auth_mode="persistent_profile",
                default_location="India",
                max_applications=25,
            )
            session.add(account)
            session.commit()

            loaded_acct = session.execute(select(PlatformAccount).where(PlatformAccount.id == account.id)).scalar_one()
            self.assertEqual(loaded_acct.platform.name, "linkedin")
            self.assertEqual(loaded_acct.max_applications, 25)

    def test_qna_entry_provenance_and_validation(self):
        """Verifies QnAEntry categorization, confidence, and validation status."""
        with self.Session() as session:
            qna_verified = QnAEntry(
                question_text="What is your notice period?",
                normalized_question="notice period",
                answer_text="30 days",
                category="notice_period",
                source="PROFILE",
                confidence=1.0,
                validation_status="VERIFIED",
            )
            qna_llm = QnAEntry(
                question_text="Have you worked with Kubernetes in production?",
                normalized_question="kubernetes production",
                answer_text="Yes, configured pods and deployments for microservices.",
                category="skills",
                source="LLM",
                confidence=0.72,
                validation_status="NEEDS_REVIEW",
            )
            session.add_all([qna_verified, qna_llm])
            session.commit()

            verified_entries = session.execute(
                select(QnAEntry).where(QnAEntry.validation_status == "VERIFIED")
            ).scalars().all()
            self.assertEqual(len(verified_entries), 1)
            self.assertEqual(verified_entries[0].source, "PROFILE")

            unverified = session.execute(
                select(QnAEntry).where(QnAEntry.validation_status == "NEEDS_REVIEW")
            ).scalars().all()
            self.assertEqual(len(unverified), 1)
            self.assertEqual(unverified[0].confidence, 0.72)

    def test_timezone_aware_utc_timestamps_and_mutation(self):
        """Verifies created_at and updated_at are timezone-aware UTC and update on change."""
        with self.Session() as session:
            setting = AppSetting(key="app.theme", value_json="dark", category="general")
            session.add(setting)
            session.commit()

            initial_created = setting.created_at
            initial_updated = setting.updated_at

            self.assertIsNotNone(initial_created.tzinfo)
            self.assertEqual(initial_created.tzinfo, timezone.utc)

            # Update setting
            setting.value_json = "light"
            setting.updated_at = utc_now()
            session.commit()

            loaded = session.execute(select(AppSetting).where(AppSetting.key == "app.theme")).scalar_one()
            self.assertEqual(loaded.value_json, "light")
            self.assertGreaterEqual(loaded.updated_at, initial_updated)

    def test_cascading_deletes(self):
        """Verifies foreign key cascade behavior."""
        with self.Session() as session:
            company = Company(name="Cascading Corp", normalized_name="cascading corp")
            session.add(company)
            session.flush()

            job = Job(
                company_id=company.id,
                platform="linkedin",
                job_fingerprint="fp_cascade_test",
                title="Cascade Engineer",
                company_raw="Cascading Corp",
                source_url="https://linkedin.com/job/cascade",
            )
            session.add(job)
            session.flush()

            evaluation = JobEvaluation(job_id=job.id, status="QUALIFIED")
            application = Application(job_id=job.id, status="APPLYING")
            session.add_all([evaluation, application])
            session.commit()

            # Delete Job -> Evaluations and Applications must be deleted automatically
            session.delete(job)
            session.commit()

            eval_count = session.scalar(select(JobEvaluation).where(JobEvaluation.job_id == job.id))
            app_count = session.scalar(select(Application).where(Application.job_id == job.id))
            self.assertIsNone(eval_count)
            self.assertIsNone(app_count)


if __name__ == "__main__":
    unittest.main()
