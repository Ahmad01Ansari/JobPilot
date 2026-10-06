"""Comprehensive test suite for JobPilot Repository and Data Access Layer."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.session import configure_sqlite_pragmas
from app.repositories import (
    ApplicationCreateDTO,
    ApplicationRepository,
    CompanyRepository,
    ContactRepository,
    JobCreateDTO,
    JobEvaluationRepository,
    JobRepository,
    PlatformRepository,
    ProfessionalProfileUpdateDTO,
    ProfileUpdateDTO,
    QnACreateDTO,
    QnARepository,
    RecruitmentRepository,
    ResumeRepository,
    SettingsRepository,
    UserRepository,
    normalize_company_name,
    validate_status_transition,
)


class TestValidationAndNormalization(unittest.TestCase):
    """Tests company name normalization and the application status transition state machine."""

    def test_company_normalization(self):
        """Verifies legal suffix stripping, whitespace normalization, and case insensitivity."""
        cases = [
            ("ABC Technologies Pvt. Ltd.", "abc technologies"),
            ("abc technologies", "abc technologies"),
            ("ABC Technologies", "abc technologies"),
            ("Acme Corp.", "acme"),
            ("Acme Corporation", "acme"),
            ("Google India Private Limited", "google india"),
            ("Tech Solutions LLC", "tech solutions"),
            ("Global Services LLP", "global services"),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_company_name(raw), expected)

    def test_valid_status_transitions(self):
        """Verifies legitimate application lifecycle progressions succeed."""
        valid_sequences = [
            ("APPLYING", "SUBMITTED"),
            ("SUBMITTED", "UNDER_REVIEW"),
            ("UNDER_REVIEW", "SHORTLISTED"),
            ("SHORTLISTED", "INTERVIEW"),
            ("INTERVIEW", "INTERVIEW"),  # Multiple rounds
            ("INTERVIEW", "OFFER"),
            ("OFFER", "OFFER"),
            ("APPLYING", "FAILED"),
            ("FAILED", "APPLYING"),  # Retry
            ("APPLYING", "UNKNOWN"),
            ("UNKNOWN", "SUBMITTED"),  # Confirmation
        ]
        for current, target in valid_sequences:
            with self.subTest(transition=f"{current} -> {target}"):
                is_valid, err = validate_status_transition(current, target)
                self.assertTrue(is_valid, msg=f"Failed on {current} -> {target}: {err}")
                self.assertIsNone(err)

    def test_invalid_status_transitions_rejected(self):
        """Verifies illegitimate or backwards transitions are rejected unless overridden."""
        invalid_sequences = [
            ("REJECTED", "SUBMITTED"),
            ("OFFER", "DISCOVERED"),
            ("SUBMITTED", "APPLYING"),
            ("WITHDRAWN", "SHORTLISTED"),
            ("OFFER", "APPLYING"),
        ]
        for current, target in invalid_sequences:
            with self.subTest(transition=f"{current} -> {target}"):
                is_valid, err = validate_status_transition(current, target)
                self.assertFalse(is_valid)
                self.assertIsNotNone(err)

                # Overriding allows the transition
                override_valid, override_err = validate_status_transition(
                    current, target, allow_override=True
                )
                self.assertTrue(override_valid)
                self.assertIsNone(override_err)


class BaseRepositoryTestCase(unittest.TestCase):
    """Base test case initializing an isolated in-memory or temporary SQLite database."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_repos.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine, future=True)
        self.session = self.Session()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)


class TestDomainRepositories(BaseRepositoryTestCase):
    """Tests all individual repository classes and multi-repository transactions."""

    def test_user_and_profile_repository(self):
        """Tests user creation, profile saving, and professional profile persistence using DTOs."""
        repo = UserRepository(self.session)
        user = repo.get_or_create_primary_user(
            name="Ahmad Raza",
            email="ahmad@example.com",
            phone="+91-9876543210",
        )
        self.session.commit()

        # Update Personal Profile
        p_dto = ProfileUpdateDTO(
            first_name="Ahmad",
            last_name="Raza",
            current_city="Noida",
            preferred_locations=["Noida", "Gurugram"],
            willing_to_relocate=True,
        )
        profile = repo.save_profile(user.id, p_dto)

        # Update Professional Profile
        prof_dto = ProfessionalProfileUpdateDTO(
            current_title="Software Engineer",
            current_employer="Enterprise Corp",
            years_of_experience=2.5,
            current_ctc=600000,
            expected_ctc=1000000,
            skills=["Python", "SQLAlchemy", "PySide6"],
        )
        prof_profile = repo.save_professional_profile(user.id, prof_dto)
        self.session.commit()

        # Fetch and verify
        primary_user = repo.get_primary_user()
        self.assertIsNotNone(primary_user)
        self.assertEqual(primary_user.profile.current_city, "Noida")
        self.assertEqual(primary_user.professional_profile.skills, ["Python", "SQLAlchemy", "PySide6"])

    def test_resume_repository_default_invariant(self):
        """Verifies that setting a new default resume unsets the previous default atomically."""
        u_repo = UserRepository(self.session)
        user = u_repo.get_or_create_primary_user("Resume User", "resume@example.com")
        self.session.commit()

        r_repo = ResumeRepository(self.session)
        r1 = r_repo.add_resume(
            user_id=user.id,
            name="Resume_v1.pdf",
            file_path="/path/to/v1.pdf",
            is_default=True,
        )
        r2 = r_repo.add_resume(
            user_id=user.id,
            name="Resume_v2.pdf",
            file_path="/path/to/v2.pdf",
            is_default=False,
        )
        self.session.commit()

        default_res = r_repo.get_default_resume(user.id)
        self.assertEqual(default_res.id, r1.id)

        # Switch default to r2
        r_repo.set_default_resume(r2.id, user.id)
        self.session.commit()

        # Check invariant: r2 is now default, r1 is no longer default
        self.assertTrue(r2.is_default)
        self.assertFalse(r1.is_default)
        self.assertEqual(r_repo.get_default_resume(user.id).id, r2.id)

    def test_company_and_contact_repository(self):
        """Tests company deduplication by normalized name and contact linking."""
        c_repo = CompanyRepository(self.session)
        # Create company
        comp1 = c_repo.get_or_create_by_name("ABC Technologies Pvt. Ltd.", location="Noida")
        self.session.commit()

        # Request company again with slightly different casing/suffix
        comp2 = c_repo.get_or_create_by_name("abc technologies", website="https://abc.example.com")
        self.session.commit()

        # Must be the exact same company row
        self.assertEqual(comp1.id, comp2.id)
        self.assertEqual(comp2.website, "https://abc.example.com")

        # Create contact
        ct_repo = ContactRepository(self.session)
        contact = ct_repo.create_contact(
            name="John Doe",
            company_id=comp1.id,
            designation="HR Specialist",
            email="john@abc.example.com",
        )
        self.session.commit()

        contacts = ct_repo.list_by_company(comp1.id)
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0].email, "john@abc.example.com")

    def test_job_repository_upsert_and_filtering(self):
        """Tests JobRepository deduplication via fingerprint, last_seen_at updates, and pagination."""
        j_repo = JobRepository(self.session)
        dto = JobCreateDTO(
            platform="naukri",
            external_job_id="nk_12345",
            company_raw="Enterprise Tech",
            title="Senior Python Engineer",
            location="Bengaluru",
            source_url="https://naukri.com/job/12345",
            experience_text="3-5 Yrs",
            required_experience_min=3,
            required_experience_max=5,
            salary_text="15-20 Lacs PA",
            salary_min=1500000,
            salary_max=2000000,
        )

        job1, created1 = j_repo.upsert_job(dto)
        self.session.commit()
        self.assertTrue(created1)
        initial_seen = job1.last_seen_at

        # Upsert again -> must not duplicate row, should update last_seen_at
        job2, created2 = j_repo.upsert_job(dto)
        self.session.commit()
        self.assertFalse(created2)
        self.assertEqual(job1.id, job2.id)
        self.assertGreaterEqual(job2.last_seen_at, initial_seen)

        # Count and listing
        total_jobs = j_repo.count_jobs(platform="naukri")
        self.assertEqual(total_jobs, 1)

        jobs = j_repo.list_jobs(platform="naukri", search="Python")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "Senior Python Engineer")

    def test_job_evaluation_repository(self):
        """Tests recording and retrieving automated job qualification decisions."""
        j_repo = JobRepository(self.session)
        job, _ = j_repo.upsert_job(
            JobCreateDTO(
                platform="linkedin",
                company_raw="AI Labs",
                title="RPA Developer",
                source_url="https://linkedin.com/job/rpa",
            )
        )
        self.session.commit()

        eval_repo = JobEvaluationRepository(self.session)
        evaluation = eval_repo.record_evaluation(
            job_id=job.id,
            status="QUALIFIED",
            decision_reason="Matching skill and experience profile",
            candidate_experience=2,
            rules_matched={"experience": True, "skills": True},
        )
        self.session.commit()

        latest = eval_repo.get_latest_evaluation(job.id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, "QUALIFIED")
        self.assertEqual(latest.rules_matched["skills"], True)

    def test_application_repository_transitions_and_history(self):
        """Tests application lifecycle transitions, blocking check, and atomic status history generation."""
        j_repo = JobRepository(self.session)
        job, _ = j_repo.upsert_job(
            JobCreateDTO(
                platform="linkedin",
                company_raw="Automation Co",
                title="Backend Developer",
                source_url="https://linkedin.com/job/backend",
            )
        )
        self.session.commit()

        app_repo = ApplicationRepository(self.session)
        # Verify not blocking initially
        self.assertFalse(app_repo.is_job_blocking(job.id))

        app = app_repo.create_application(
            ApplicationCreateDTO(
                job_id=job.id,
                status="APPLYING",
            )
        )
        self.session.commit()

        # APPLYING is a blocking state
        self.assertTrue(app_repo.is_job_blocking(job.id))
        self.assertEqual(len(app.status_history), 1)
        self.assertEqual(app.status_history[0].new_status, "APPLYING")

        # Transition to SUBMITTED
        app_repo.transition_status(
            application_id=app.id,
            new_status="SUBMITTED",
            source="automation",
            notes="Form successfully filled and verified",
        )
        self.session.commit()

        self.assertEqual(app.status, "SUBMITTED")
        self.assertIsNotNone(app.applied_at)
        self.assertEqual(len(app.status_history), 2)
        self.assertEqual(app.status_history[1].new_status, "SUBMITTED")

        # Attempt invalid backwards transition: SUBMITTED -> APPLYING must raise ValueError
        with self.assertRaises(ValueError):
            app_repo.transition_status(
                application_id=app.id,
                new_status="APPLYING",
            )

    def test_recruitment_repository_pipeline(self):
        """Tests Interview, Communication, FollowUp, and Offer scheduling."""
        j_repo = JobRepository(self.session)
        job, _ = j_repo.upsert_job(
            JobCreateDTO(
                platform="linkedin",
                company_raw="Enterprise Corp",
                title="Lead Architect",
                source_url="https://linkedin.com/job/lead",
            )
        )
        app_repo = ApplicationRepository(self.session)
        app = app_repo.create_application(ApplicationCreateDTO(job_id=job.id, status="SHORTLISTED"))
        self.session.commit()

        r_repo = RecruitmentRepository(self.session)

        # Schedule Interview
        interview = r_repo.schedule_interview(
            application_id=app.id,
            round_name="Technical",
            scheduled_at=utc_now() + timedelta(days=2),
            meeting_link="https://meet.google.com/test",
            interviewer="VP Engineering",
        )

        # Log Communication
        comm = r_repo.log_communication(
            type_="EMAIL",
            direction="INBOUND",
            application_id=app.id,
            subject="Interview Confirmation",
            summary="Confirmed technical round time.",
        )

        # Create Follow-up
        fu = r_repo.create_follow_up(
            due_at=utc_now() + timedelta(days=3),
            application_id=app.id,
            notes="Send post-interview thank you email",
        )

        # Record Offer
        offer = r_repo.record_offer(
            application_id=app.id,
            offered_ctc=2200000,
            currency="INR",
            status="RECEIVED",
        )
        self.session.commit()

        # Assertions
        interviews = r_repo.list_interviews_by_application(app.id)
        self.assertEqual(len(interviews), 1)
        self.assertEqual(interviews[0].round_name, "Technical")

        pending_fu = r_repo.list_pending_follow_ups()
        self.assertEqual(len(pending_fu), 1)

        saved_offer = r_repo.get_offer_by_application(app.id)
        self.assertIsNotNone(saved_offer)
        self.assertEqual(saved_offer.offered_ctc, 2200000)

    def test_qna_repository_provenance_and_atomic_increment(self):
        """Tests QnARepository trust provenance rule for LLM vs Profile, and atomic usage count increment."""
        q_repo = QnARepository(self.session)

        # Profile answer -> VERIFIED
        profile_qna = q_repo.upsert_answer(
            QnACreateDTO(
                question_text="What is your notice period in days?",
                answer_text="30",
                source="PROFILE",
                confidence=1.0,
            )
        )

        # LLM answer -> NEEDS_REVIEW
        llm_qna = q_repo.upsert_answer(
            QnACreateDTO(
                question_text="Describe your experience with Apache Airflow.",
                answer_text="Built DAGs for scheduling batch ETL pipelines.",
                source="LLM",
                confidence=0.75,
            )
        )
        self.session.commit()

        self.assertEqual(profile_qna.validation_status, "VERIFIED")
        self.assertEqual(llm_qna.validation_status, "NEEDS_REVIEW")

        # Unreviewed list
        unreviewed = q_repo.list_unreviewed()
        self.assertEqual(len(unreviewed), 1)
        self.assertEqual(unreviewed[0].id, llm_qna.id)

        # Atomic usage count increment
        initial_usage = profile_qna.usage_count
        q_repo.increment_usage(profile_qna.id)
        self.session.commit()

        # Refresh from session
        self.session.refresh(profile_qna)
        self.assertEqual(profile_qna.usage_count, initial_usage + 1)
        self.assertIsNotNone(profile_qna.last_used_at)

    def test_settings_repository(self):
        """Tests get/set for configuration parameters by key and category."""
        s_repo = SettingsRepository(self.session)
        s_repo.set("bot.max_retries", 3, category="bot")
        s_repo.set("bot.stealth_mode", True, category="bot")
        s_repo.set("general.theme", "dark", category="general")
        self.session.commit()

        retries = s_repo.get("bot.max_retries")
        self.assertEqual(retries, 3)

        default_val = s_repo.get("nonexistent.key", default="fallback")
        self.assertEqual(default_val, "fallback")

        bot_settings = s_repo.get_category("bot")
        self.assertEqual(bot_settings["bot.max_retries"], 3)
        self.assertTrue(bot_settings["bot.stealth_mode"])


if __name__ == "__main__":
    unittest.main()
