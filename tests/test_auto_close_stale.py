"""Unit tests for Automatic Closing of Stale Applications."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Job, ApplicationStatusHistory
from app.repositories.application_repository import ApplicationRepository
from app.repositories.job_repository import JobRepository
from app.services.application_service import ApplicationService
from app.services.settings_service import SettingsService


class TestAutoCloseStaleApplications(unittest.TestCase):
    """Test suite covering the 60-day auto-close lifecycle for stale applications."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_auto_close.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

        self.app_service = ApplicationService(session_factory=self.Session)
        self.settings_service = SettingsService(session_factory=self.Session)

        # Seed default settings
        self.settings_service.seed_defaults_if_empty()

        # Create test jobs and applications
        now = datetime.now(timezone.utc)
        self.old_date = now - timedelta(days=70)      # > 60 days (stale)
        self.recent_date = now - timedelta(days=10)   # < 60 days (active)

        with self.Session() as session:
            # 1. Stale submitted job (should be auto-closed)
            job1 = Job(
                title="Frontend Developer",
                company_raw="Acme Corp",
                platform="linkedin",
                job_fingerprint="fp_job1",
                source_url="https://linkedin.com/job/1",
                is_active=True,
                created_at=self.old_date,
            )
            session.add(job1)
            session.flush()

            app1 = Application(
                job_id=job1.id,
                status="SUBMITTED",
                created_at=self.old_date,
                updated_at=self.old_date,
                applied_at=self.old_date,
            )
            session.add(app1)

            # 2. Recent submitted job (should NOT be auto-closed)
            job2 = Job(
                title="Backend Developer",
                company_raw="Beta LLC",
                platform="naukri",
                job_fingerprint="fp_job2",
                source_url="https://naukri.com/job/2",
                is_active=True,
                created_at=self.recent_date,
            )
            session.add(job2)
            session.flush()

            app2 = Application(
                job_id=job2.id,
                status="SUBMITTED",
                created_at=self.recent_date,
                updated_at=self.recent_date,
                applied_at=self.recent_date,
            )
            session.add(app2)

            # 3. Stale interview application (Protected! should NOT be auto-closed)
            job3 = Job(
                title="Staff AI Engineer",
                company_raw="Gamma Labs",
                platform="linkedin",
                job_fingerprint="fp_job3",
                source_url="https://linkedin.com/job/3",
                is_active=True,
                created_at=self.old_date,
            )
            session.add(job3)
            session.flush()

            app3 = Application(
                job_id=job3.id,
                status="INTERVIEW",
                created_at=self.old_date,
                updated_at=self.old_date,
                applied_at=self.old_date,
            )
            session.add(app3)

            # 4. Stale offer application (Protected! should NOT be auto-closed)
            job4 = Job(
                title="Principal Architect",
                company_raw="Delta Inc",
                platform="indeed",
                job_fingerprint="fp_job4",
                source_url="https://indeed.com/job/4",
                is_active=True,
                created_at=self.old_date,
            )
            session.add(job4)
            session.flush()

            app4 = Application(
                job_id=job4.id,
                status="OFFER",
                created_at=self.old_date,
                updated_at=self.old_date,
            )
            session.add(app4)

            # 5. Stale under-review application (should be auto-closed)
            job5 = Job(
                title="ML Specialist",
                company_raw="Epsilon AI",
                platform="universal",
                job_fingerprint="fp_job5",
                source_url="https://epsilon.ai/careers/5",
                is_active=True,
                created_at=self.old_date,
            )
            session.add(job5)
            session.flush()

            app5 = Application(
                job_id=job5.id,
                status="UNDER_REVIEW",
                created_at=self.old_date,
                updated_at=self.old_date,
            )
            session.add(app5)

            session.commit()
            self.job1_id = job1.id
            self.job2_id = job2.id
            self.job3_id = job3.id
            self.job5_id = job5.id
            self.app1_id = app1.id
            self.app2_id = app2.id
            self.app3_id = app3.id
            self.app5_id = app5.id

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_stale_applications(self):
        """Verifies find_stale_applications identifies only stale non-terminal applications."""
        with self.Session() as session:
            repo = ApplicationRepository(session)
            stale = repo.find_stale_applications(inactivity_days=60)
            stale_ids = [a.id for a in stale]

            # app1 (SUBMITTED, 70d) and app5 (UNDER_REVIEW, 70d) should be found
            self.assertIn(self.app1_id, stale_ids)
            self.assertIn(self.app5_id, stale_ids)

            # app2 (recent, 10d) must NOT be found
            self.assertNotIn(self.app2_id, stale_ids)

            # app3 (INTERVIEW, 70d) is protected and must NOT be found
            self.assertNotIn(self.app3_id, stale_ids)

    def test_auto_close_stale_applications_execution(self):
        """Verifies execution transitions stale applications to CLOSED and sets jobs inactive."""
        res = self.app_service.auto_close_stale_applications(inactivity_days=60)
        self.assertTrue(res["enabled"])
        self.assertEqual(res["closed_count"], 2)
        self.assertIn(self.app1_id, res["closed_ids"])
        self.assertIn(self.app5_id, res["closed_ids"])

        # Check DB states
        with self.Session() as session:
            a1 = session.get(Application, self.app1_id)
            self.assertEqual(a1.status, "CLOSED")

            j1 = session.get(Job, self.job1_id)
            self.assertFalse(j1.is_active)
            self.assertIsNotNone(j1.closed_at)

            # Check audit history
            history = session.query(ApplicationStatusHistory).filter_by(application_id=self.app1_id).all()
            self.assertTrue(len(history) >= 1)
            self.assertEqual(history[-1].new_status, "CLOSED")
            self.assertEqual(history[-1].source, "SYSTEM")
            self.assertIn("Auto-closed", history[-1].notes)

            # Verify protected and recent applications are untouched
            a2 = session.get(Application, self.app2_id)
            self.assertEqual(a2.status, "SUBMITTED")

            a3 = session.get(Application, self.app3_id)
            self.assertEqual(a3.status, "INTERVIEW")

    def test_auto_close_disabled_in_settings(self):
        """Verifies auto_close does nothing when disabled in settings."""
        self.settings_service.set("auto_close_stale_applications", False)

        res = self.app_service.auto_close_stale_applications(inactivity_days=60)
        self.assertFalse(res["enabled"])
        self.assertEqual(res["closed_count"], 0)

        with self.Session() as session:
            a1 = session.get(Application, self.app1_id)
            self.assertEqual(a1.status, "SUBMITTED")

    def test_kpi_counts_after_auto_close(self):
        """Verifies canonical KPI card counts reflect auto-closed items."""
        with self.Session() as session:
            repo = ApplicationRepository(session)
            kpi_before = repo.get_canonical_kpi_counts()
            self.assertEqual(kpi_before["submitted"], 2)  # app1 and app2
            self.assertEqual(kpi_before["under_review"], 1)  # app5
            self.assertEqual(kpi_before["closed"], 0)

        # Run auto-close
        self.app_service.auto_close_stale_applications(inactivity_days=60)

        with self.Session() as session:
            repo = ApplicationRepository(session)
            kpi_after = repo.get_canonical_kpi_counts()
            self.assertEqual(kpi_after["submitted"], 1)  # only app2 remains
            self.assertEqual(kpi_after["under_review"], 0)  # app5 was closed
            self.assertEqual(kpi_after["closed"], 2)  # app1 and app5 closed
            self.assertEqual(kpi_after["interviews"], 1)  # app3 untouched


if __name__ == "__main__":
    unittest.main()
