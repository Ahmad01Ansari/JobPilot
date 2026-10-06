import os
import time
import tempfile
import unittest
from unittest.mock import MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.db.models import User, Profile, ProfessionalProfile
from app.services.profile_service import ProfileService
from app.services.task_runner import JobRunnerPool
from modules.config_loader import (
    get_personal,
    get_professional,
    get_candidate_experience,
    get_salary_preferences,
    get_notice_period,
)


class TestProductionPhase2(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_phase2.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}")

        from sqlalchemy import event
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

        # Seed primary user & secondary user
        with self.SessionLocal() as session:
            u1 = User(id=1, email="primary@jobpilot.local", name="Primary Candidate", phone="+919999999999")
            session.add(u1)
            session.flush()

            p1 = Profile(
                user_id=u1.id,
                first_name="Primary",
                last_name="Candidate",
                current_city="Noida",
                state="Uttar Pradesh",
                country="India",
                zipcode="201301",
            )
            session.add(p1)

            pp1 = ProfessionalProfile(
                user_id=u1.id,
                current_title="Senior Automation Engineer",
                current_employer="Enterprise Corp",
                years_of_experience=6,
                current_ctc=1200000,
                expected_ctc=1800000,
                notice_period_days=45,
            )
            session.add(pp1)

            # User 2 (multi-tenant)
            u2 = User(id=2, email="user2@jobpilot.local", name="Second Candidate", phone="+918888888888")
            session.add(u2)
            session.flush()

            pp2 = ProfessionalProfile(
                user_id=u2.id,
                current_title="Junior Python Dev",
                current_employer="Startup AI",
                years_of_experience=1,
                current_ctc=400000,
                expected_ctc=700000,
                notice_period_days=15,
            )
            session.add(pp2)

            session.commit()

        # Wire DB session into app.db.session for testing
        import app.db.session
        self.orig_session_local = app.db.session.SessionLocal
        app.db.session.SessionLocal = self.SessionLocal

        self.profile_service = ProfileService(session_factory=self.SessionLocal)

    def tearDown(self):
        import app.db.session
        app.db.session.SessionLocal = self.orig_session_local
        self.temp_dir.cleanup()

    def test_db_first_config_loader_primary_user(self):
        personal = get_personal(user_id=1)
        self.assertEqual(personal["first_name"], "Primary")
        self.assertEqual(personal["last_name"], "Candidate")
        self.assertEqual(personal["current_city"], "Noida")

        prof = get_professional(user_id=1)
        self.assertEqual(prof["title"], "Senior Automation Engineer")
        self.assertEqual(prof["years_of_experience"], 6)

        sal = get_salary_preferences(user_id=1)
        self.assertEqual(sal["current_ctc"], 1200000)
        self.assertEqual(sal["desired_salary"], 1800000)

        self.assertEqual(get_notice_period(user_id=1), 45)
        self.assertEqual(get_candidate_experience(user_id=1), 6)

    def test_db_first_config_loader_multi_user(self):
        prof2 = get_professional(user_id=2)
        self.assertEqual(prof2["title"], "Junior Python Dev")
        self.assertEqual(prof2["years_of_experience"], 1)

        sal2 = get_salary_preferences(user_id=2)
        self.assertEqual(sal2["current_ctc"], 400000)
        self.assertEqual(sal2["desired_salary"], 700000)

        self.assertEqual(get_notice_period(user_id=2), 15)
        self.assertEqual(get_candidate_experience(user_id=2), 1)

    def test_export_profile_to_dict(self):
        data = self.profile_service.export_profile_to_dict(user_id=1)
        self.assertIn("personal", data)
        self.assertIn("professional", data)
        self.assertIn("platforms", data)

        self.assertEqual(data["personal"]["first_name"], "Primary")
        self.assertEqual(data["professional"]["title"], "Senior Automation Engineer")
        self.assertEqual(data["professional"]["years_of_experience"], 6)
        self.assertEqual(data["professional"]["current_ctc"], 1200000)

    def test_import_profile_from_dict(self):
        new_profile_payload = {
            "personal": {
                "first_name": "Imported",
                "last_name": "Engineer",
                "email": "imported@jobpilot.local",
                "phone_number": "+917777777777",
                "current_city": "Bengaluru",
                "state": "Karnataka",
                "country": "India",
            },
            "professional": {
                "title": "Lead Architect",
                "current_employer": "Global Tech",
                "years_of_experience": 10,
                "current_ctc": 3000000,
                "desired_salary": 4500000,
                "notice_period_days": 60,
            }
        }

        ok, err = self.profile_service.import_profile_from_dict(user_id=3, data=new_profile_payload)
        self.assertTrue(ok, err)

        # Verify DB-first loader immediately sees the imported values
        prof3 = get_professional(user_id=3)
        self.assertEqual(prof3["title"], "Lead Architect")
        self.assertEqual(prof3["years_of_experience"], 10)
        self.assertEqual(prof3["current_ctc"], 3000000)
        self.assertEqual(prof3["desired_salary"], 4500000)
        self.assertEqual(get_notice_period(user_id=3), 60)

    def test_lightweight_task_runner_pool(self):
        pool = JobRunnerPool(max_workers=2)

        executed = []

        def mock_runner(stop_check):
            for i in range(5):
                if stop_check():
                    return {"stopped_at": i}
                time.sleep(0.02)
            executed.append(True)
            return {"applied": 5}

        # 1. Submit task
        task_id = pool.submit_job_run(platform="naukri", user_id=1, runner_override=mock_runner)
        self.assertTrue(task_id.startswith("task_"))

        # 2. Wait for completion
        time.sleep(0.2)
        task_info = pool.get_task(task_id)
        self.assertIsNotNone(task_info)
        self.assertEqual(task_info["status"], "COMPLETED")
        self.assertEqual(task_info["result"]["applied"], 5)
        self.assertTrue(executed[0])

        pool.shutdown(wait=False)

    def test_task_runner_cancellation(self):
        pool = JobRunnerPool(max_workers=2)

        def slow_runner(stop_check):
            for i in range(100):
                if stop_check():
                    return {"stopped_at": i}
                time.sleep(0.01)
            return {"status": "finished"}

        task_id = pool.submit_job_run(platform="linkedin", user_id=1, runner_override=slow_runner)
        time.sleep(0.03)

        # Signal stop
        stopped = pool.stop_task(task_id)
        self.assertTrue(stopped)

        time.sleep(0.05)
        task_info = pool.get_task(task_id)
        self.assertEqual(task_info["status"], "STOPPED")

        pool.shutdown(wait=False)


if __name__ == "__main__":
    unittest.main()
