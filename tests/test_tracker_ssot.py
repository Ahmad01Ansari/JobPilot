import os
import tempfile
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.db.models import Job, Application, User
from modules.tracker import ApplicationTracker, ApplicationRecord


class TestTrackerSSOT(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_jobpilot.db")
        self.test_csv = os.path.join(self.temp_dir.name, "test_applications.csv")

        self.engine = create_engine(f"sqlite:///{self.db_path}")
        from sqlalchemy import event
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Seed test user
        with self.SessionLocal() as session:
            user = User(id=1, email="test@jobpilot.local", name="Test User")
            session.add(user)
            session.commit()

        # Monkeypatch get_db_session in tracker tests
        import app.db.session
        self.orig_session_local = app.db.session.SessionLocal
        app.db.session.SessionLocal = self.SessionLocal

    def tearDown(self):
        import app.db.session
        app.db.session.SessionLocal = self.orig_session_local
        self.temp_dir.cleanup()

    def test_ssot_sync_to_db(self):
        tracker = ApplicationTracker(file_path=self.test_csv, enable_db=True)
        job_data = {
            "platform": "naukri",
            "job_id": "test_ssot_101",
            "title": "Python Developer",
            "company": "Tech Corp",
            "location": "Bangalore",
            "source_url": "https://naukri.com/job/test_ssot_101",
        }

        # 1. Record state
        tracker.record_state(job_data, "SUBMITTED")

        # 2. Verify in SQLite database
        with self.SessionLocal() as session:
            from app.repositories.job_repository import JobRepository
            from app.repositories.application_repository import ApplicationRepository

            j_repo = JobRepository(session)
            job = j_repo.get_by_external_id("naukri", "test_ssot_101")
            self.assertIsNotNone(job)
            self.assertEqual(job.title, "Python Developer")

            a_repo = ApplicationRepository(session)
            app = a_repo.get_by_job_id(job.id)
            self.assertIsNotNone(app)
            self.assertEqual(app.status, "SUBMITTED")

        # 3. New tracker instance loads from DB (SSOT)
        new_tracker = ApplicationTracker(file_path=os.path.join(self.temp_dir.name, "empty.csv"), enable_db=True)
        should_skip, reason = new_tracker.is_already_handled("test_ssot_101", "naukri")
        self.assertTrue(should_skip)
        self.assertIn("Already successfully submitted", reason)

    def test_dynamic_db_lookup_if_not_in_cache(self):
        # Directly insert a job into DB without notifying tracker
        with self.SessionLocal() as session:
            from app.repositories.job_repository import JobRepository
            from app.repositories.application_repository import ApplicationRepository
            from app.repositories.dto import JobCreateDTO, ApplicationCreateDTO

            j_repo = JobRepository(session)
            job, _ = j_repo.upsert_job(JobCreateDTO(
                platform="linkedin",
                company_raw="Enterprise AI",
                title="AI Engineer",
                external_job_id="li_ssot_202",
                source_url="https://linkedin.com/jobs/view/li_ssot_202",
                application_method="COMPANY_PORTAL",
            ))

            a_repo = ApplicationRepository(session)
            a_repo.create_application(ApplicationCreateDTO(
                job_id=job.id,
                user_id=1,
                status="SUBMITTED",
            ))
            session.commit()

        # Tracker with empty memory cache should find it in DB
        tracker = ApplicationTracker(file_path=os.path.join(self.temp_dir.name, "empty2.csv"), enable_db=True)
        # Clear tracker's in-memory cache to simulate fresh un-cached query
        tracker._records.clear()

        should_skip, reason = tracker.is_already_handled("li_ssot_202", "linkedin")
        self.assertTrue(should_skip)
        self.assertIn("Already successfully submitted", reason)


if __name__ == "__main__":
    unittest.main()
