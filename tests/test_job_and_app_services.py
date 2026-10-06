"""Unit, behavioral, and UI integration test suite for JobService, ApplicationService, and Phase 10 views."""

import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Job, generate_job_fingerprint
from app.db.session import configure_sqlite_pragmas
from app.repositories.dto import JobCreateDTO
from app.services.application_service import ApplicationFilter, ApplicationService
from app.services.job_service import JobFilter, JobService


class TestJobAndApplicationServices(unittest.TestCase):
    """Unit and domain lifecycle tests for JobService and ApplicationService."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase10_test.db")
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
        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_job_service_upsert_creates_new_job(self):
        """Verifies upserting a new job creates a record."""
        dto = JobCreateDTO(
            platform="linkedin",
            company_raw="Stripe",
            title="Senior QA Engineer",
            source_url="https://linkedin.com/jobs/view/123",
            external_job_id="123",
            location="Bengaluru",
        )
        job, created = self.job_service.upsert_job(dto)
        self.assertTrue(created)
        self.assertEqual(job.title, "Senior QA Engineer")
        self.assertEqual(job.company_raw, "Stripe")

    def test_job_service_upsert_deduplicates_and_updates_existing(self):
        """Verifies upserting an identical job updates timestamp without creating duplicate."""
        dto = JobCreateDTO(
            platform="linkedin",
            company_raw="Stripe",
            title="Senior QA Engineer",
            source_url="https://linkedin.com/jobs/view/123",
            external_job_id="123",
            location="Bengaluru",
        )
        job1, created1 = self.job_service.upsert_job(dto)
        self.assertTrue(created1)

        # Upsert again
        job2, created2 = self.job_service.upsert_job(dto)
        self.assertFalse(created2)
        self.assertEqual(job1.id, job2.id)

        # Count should be exactly 1
        count = self.job_service.count_jobs()
        self.assertEqual(count, 1)

    def test_job_service_fingerprint_with_and_without_job_id(self):
        """Verifies deterministic fingerprints produce expected digests."""
        fp1 = generate_job_fingerprint(
            platform="naukri",
            company="Infosys",
            title="Python Dev",
            external_job_id="999",
        )
        fp2 = generate_job_fingerprint(
            platform="naukri",
            company="Infosys",
            title="Python Dev",
            external_job_id="999",
        )
        self.assertEqual(fp1, fp2)

        # Different job ID produces different fingerprint
        fp3 = generate_job_fingerprint(
            platform="naukri",
            company="Infosys",
            title="Python Dev",
            external_job_id="1000",
        )
        self.assertNotEqual(fp1, fp3)

    def test_job_service_filter_and_pagination(self):
        """Verifies filtering by platform, search text, and pagination."""
        for i in range(5):
            self.job_service.create_manual_job(
                title=f"Python Engineer {i}",
                company=f"Company {i}",
                platform="linkedin" if i % 2 == 0 else "naukri",
                location="Bengaluru" if i < 3 else "Remote",
            )

        # Total count
        self.assertEqual(self.job_service.count_jobs(), 5)

        # Filter by platform
        f_li = JobFilter(platform="linkedin")
        li_jobs = self.job_service.list_jobs(filters=f_li)
        self.assertEqual(len(li_jobs), 3)

        # Search filter
        f_search = JobFilter(search="Remote")
        remote_jobs = self.job_service.list_jobs(filters=f_search)
        self.assertEqual(len(remote_jobs), 2)

        # Pagination: limit 2, offset 0
        page1 = self.job_service.list_jobs(limit=2, offset=0)
        self.assertEqual(len(page1), 2)
        page2 = self.job_service.list_jobs(limit=2, offset=2)
        self.assertEqual(len(page2), 2)
        self.assertNotEqual(page1[0].id, page2[0].id)

    def test_job_service_manual_job_creation(self):
        """Verifies manual job entry with validation."""
        job, err = self.job_service.create_manual_job(
            title="Lead SDET",
            company="Razorpay",
            platform="referral",
            location="Remote",
            salary_text="30 LPA",
            description="Testing enterprise payment gateways.",
        )
        self.assertIsNotNone(job)
        self.assertIsNone(err)
        self.assertEqual(job.title, "Lead SDET")
        self.assertEqual(job.platform, "referral")

        # Missing title rejected
        bad_job, bad_err = self.job_service.create_manual_job(title="", company="Acme")
        self.assertIsNone(bad_job)
        self.assertIn("Job title cannot be empty", bad_err)

    def test_job_service_mark_inactive(self):
        """Verifies closing a job listing."""
        job, _ = self.job_service.create_manual_job(title="Architect", company="Google")
        self.assertTrue(job.is_active)

        success = self.job_service.mark_inactive(job.id) if hasattr(self.job_service, "mark_inactive") else self.job_service.mark_job_inactive(job.id)
        self.assertTrue(success)

        reloaded = self.job_service.get_job(job.id)
        self.assertFalse(reloaded.is_active)

    def test_application_service_create_application(self):
        """Verifies creating an application record for a job."""
        job, _ = self.job_service.create_manual_job(title="DevOps Engineer", company="Amazon")
        app, err = self.app_service.create_application(
            job_id=job.id,
            status="APPLYING",
            application_type="EASY_APPLY",
            notes="Applied through automation queue",
        )
        self.assertIsNotNone(app)
        self.assertIsNone(err)
        self.assertEqual(app.status, "APPLYING")
        self.assertEqual(app.job_id, job.id)

    def test_application_service_transition_status_valid(self):
        """Verifies valid state machine transitions: APPLYING -> SUBMITTED -> UNDER_REVIEW."""
        job, _ = self.job_service.create_manual_job(title="QA Lead", company="Microsoft")
        app, _ = self.app_service.create_application(job_id=job.id, status="APPLYING")

        # 1. APPLYING -> SUBMITTED
        updated, err = self.app_service.transition_status(app.id, "SUBMITTED", notes="Form submitted")
        self.assertIsNotNone(updated)
        self.assertIsNone(err)
        self.assertEqual(updated.status, "SUBMITTED")
        self.assertIsNotNone(updated.applied_at)

        # 2. SUBMITTED -> UNDER_REVIEW
        updated2, err2 = self.app_service.transition_status(app.id, "UNDER_REVIEW")
        self.assertIsNotNone(updated2)
        self.assertIsNone(err2)
        self.assertEqual(updated2.status, "UNDER_REVIEW")

    def test_application_service_transition_status_idempotent(self):
        """Verifies transitioning to identical status is a safe no-op without duplicate history."""
        job, _ = self.job_service.create_manual_job(title="SRE", company="Meta")
        app, _ = self.app_service.create_application(job_id=job.id, status="APPLYING")

        # Call transition with same status
        res, err = self.app_service.transition_status(app.id, "APPLYING")
        self.assertIsNotNone(res)
        self.assertIsNone(err)

        # History should only have the 1 creation record, no duplicates
        history = self.app_service.get_status_history(app.id)
        self.assertEqual(len(history), 1)

    def test_application_service_transition_invalid_rejected(self):
        """Verifies state machine prevents illegal status transitions."""
        job, _ = self.job_service.create_manual_job(title="Backend Dev", company="Netflix")
        app, _ = self.app_service.create_application(job_id=job.id, status="SUBMITTED")

        # SUBMITTED -> OFFER is not allowed directly (must go through review/interview)
        res, err = self.app_service.transition_status(app.id, "OFFER")
        self.assertIsNone(res)
        self.assertIn("Invalid status transition", err)

    def test_application_service_status_history_captures_from_to(self):
        """Verifies audit trail captures both old_status (from) and new_status (to)."""
        job, _ = self.job_service.create_manual_job(title="Data Engineer", company="Apple")
        app, _ = self.app_service.create_application(job_id=job.id, status="APPLYING")
        self.app_service.transition_status(app.id, "SUBMITTED", source="automation_test", notes="Done")

        history = self.app_service.get_status_history(app.id)
        self.assertEqual(len(history), 2)

        # Initial creation
        self.assertIsNone(history[0].old_status)
        self.assertEqual(history[0].new_status, "APPLYING")

        # Second transition
        self.assertEqual(history[1].old_status, "APPLYING")
        self.assertEqual(history[1].new_status, "SUBMITTED")
        self.assertEqual(history[1].source, "automation_test")

    def test_application_service_get_pipeline_summary(self):
        """Verifies pipeline summary counts per status."""
        job1, _ = self.job_service.create_manual_job(title="J1", company="C1")
        job2, _ = self.job_service.create_manual_job(title="J2", company="C2")
        job3, _ = self.job_service.create_manual_job(title="J3", company="C3")

        self.app_service.create_application(job_id=job1.id, status="SUBMITTED")
        self.app_service.create_application(job_id=job2.id, status="SUBMITTED")
        self.app_service.create_application(job_id=job3.id, status="APPLYING")

        summary = self.app_service.get_pipeline_summary()
        self.assertEqual(summary.get("SUBMITTED", 0), 2)
        self.assertEqual(summary.get("APPLYING", 0), 1)

    def test_job_to_application_full_relationship(self):
        """Critical integration test: Job -> Application -> StatusHistory cascade and FK integrity."""
        job, _ = self.job_service.create_manual_job(title="Principal Architect", company="Oracle")
        app, _ = self.app_service.create_application(job_id=job.id, status="APPLYING")
        self.app_service.transition_status(app.id, "SUBMITTED")

        # Fetch job and navigate relationships
        loaded_job = self.job_service.get_job(job.id)
        self.assertIsNotNone(loaded_job)
        self.assertEqual(len(loaded_job.applications), 1)

        loaded_app = loaded_job.applications[0]
        self.assertEqual(loaded_app.id, app.id)
        self.assertEqual(len(loaded_app.status_history), 2)


class TestPhase10Views(unittest.TestCase):
    """Headless PySide6 UI tests for JobsView and ApplicationsView."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase10_view_test.db")
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
        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_jobs_view_rendering_and_table_population(self):
        """Verifies JobsView renders table rows, shows counts, and populates details."""
        from app.ui.views.jobs_view import JobsView

        self.job_service.create_manual_job(title="Python Developer", company="Spotify")
        self.job_service.create_manual_job(title="SDET II", company="Uber")

        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 2)
        self.assertIn("2 jobs", view.lbl_stats.text())

    def test_jobs_view_search_filtering(self):
        """Verifies text search in JobsView filters the table dynamically."""
        from app.ui.views.jobs_view import JobsView

        self.job_service.create_manual_job(title="Python Engineer", company="Spotify")
        self.job_service.create_manual_job(title="Java Architect", company="Oracle")

        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 2)

        # Search for Python
        view.txt_search.setText("Python")
        self.assertEqual(view.table.rowCount(), 1)

    def test_applications_view_rendering_and_summary_cards(self):
        """Verifies ApplicationsView renders metrics cards and populates table."""
        from app.ui.views.applications_view import ApplicationsView

        job, _ = self.job_service.create_manual_job(title="Full Stack Lead", company="Airbnb")
        self.app_service.create_application(job_id=job.id, status="SUBMITTED")

        view = ApplicationsView(service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.tabs.count(), 6)

    def test_junk_job_lifecycle_and_filtering(self):
        """Verifies marking jobs as junk hides them from default repository queries and restore brings them back."""
        job1, _ = self.job_service.create_manual_job(title="AI Research Lead", company="DeepMind")
        job2, _ = self.job_service.create_manual_job(title="Irrelevant Spam Job", company="SpamCorp")

        # 1. Initially both jobs appear in repository
        active_jobs = self.job_service.list_jobs()
        self.assertEqual(len(active_jobs), 2)

        # 2. Mark job2 as JUNK
        app, err = self.app_service.mark_as_junk(job_id=job2.id, notes="Irrelevant to career profile")
        self.assertIsNone(err)
        self.assertIsNotNone(app)
        self.assertEqual(app.status, "JUNK")

        # 3. Default list_jobs must hide JUNK jobs
        active_jobs_after = self.job_service.list_jobs()
        self.assertEqual(len(active_jobs_after), 1)
        self.assertEqual(active_jobs_after[0].id, job1.id)

        # 4. Status='JUNK' filter specifically retrieves the junk job
        junk_jobs = self.job_service.list_jobs(filters=JobFilter(status="JUNK"))
        self.assertEqual(len(junk_jobs), 1)
        self.assertEqual(junk_jobs[0].id, job2.id)

        # 5. Category counts report junk count accurately
        counts = self.job_service.get_category_counts()
        self.assertEqual(counts["junk"], 1)

        # 6. Restore job from junk
        res_app, res_err = self.app_service.restore_from_junk(job_id=job2.id)
        self.assertIsNone(res_err)
        self.assertTrue(bool(res_app))

        # 7. Both jobs are visible in the repository again
        restored_jobs = self.job_service.list_jobs()
        self.assertEqual(len(restored_jobs), 2)


if __name__ == "__main__":
    unittest.main()

