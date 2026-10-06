"""Unit tests for lifecycle-aware 4-tier duplicate detection in Outreach Center."""

import os
import shutil
import tempfile
import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Company, Contact, Job, User
from app.repositories.application_repository import ApplicationRepository
from app.repositories.dto import ApplicationCreateDTO


class TestOutreachDuplicates(unittest.TestCase):
    """Verifies 4-tier hierarchical duplicate application detection."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "dup_test.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Test Candidate", email="candidate@test.com", is_active=True)
            comp = Company(id=1, name="ABC Technologies Inc.", normalized_name="abc technologies")
            contact = Contact(id=1, name="Jane Recruiter", email="jane@abctech.com", company_id=1)
            job1 = Job(
                id=1,
                company_id=1,
                title="Senior RPA Developer",
                company_raw="ABC Technologies Inc.",
                platform="LINKEDIN",
                source_url="https://jobs.example.com/rpa/123",
                job_fingerprint="fp_job_1",
            )
            job2 = Job(
                id=2,
                company_id=1,
                title="Python Backend Engineer",
                company_raw="ABC Technologies Inc.",
                platform="MANUAL",
                source_url="https://jobs.example.com/python/456",
                job_fingerprint="fp_job_2",
            )
            s.add_all([u, comp, contact, job1, job2])
            s.commit()

            # Create an active application on job1
            repo = ApplicationRepository(s)
            dto = ApplicationCreateDTO(
                job_id=1,
                user_id=1,
                contact_id=1,
                status="UNDER_REVIEW",
                application_type="EMAIL",
            )
            repo.create_application(dto)
            s.commit()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_tier1_exact_job_id_match(self):
        """Tier 1: Exact job_id match triggers duplicate detection across active statuses."""
        with self.Session() as s:
            repo = ApplicationRepository(s)
            res = repo.check_duplicate_outreach_application(job_id=1)
            self.assertTrue(res.is_duplicate)
            self.assertEqual(res.match_tier, "EXACT_JOB_ID")
            self.assertEqual(res.existing_status, "UNDER_REVIEW")
            self.assertTrue(res.can_override)

    def test_tier2_normalized_company_and_title(self):
        """Tier 2: Same normalized company and title without job_id triggers duplicate."""
        with self.Session() as s:
            repo = ApplicationRepository(s)
            # "ABC Technologies" matches "ABC Technologies Inc." through normalization
            res = repo.check_duplicate_outreach_application(
                company_name="ABC Technologies",
                job_title="Senior RPA Developer",
            )
            self.assertTrue(res.is_duplicate)
            self.assertEqual(res.match_tier, "NORMALIZED_COMPANY_TITLE")

    def test_tier3_contact_email_and_title(self):
        """Tier 3: Same recruiter email and job title triggers duplicate."""
        with self.Session() as s:
            repo = ApplicationRepository(s)
            res = repo.check_duplicate_outreach_application(
                contact_email="jane@abctech.com",
                job_title="Senior RPA Developer",
            )
            self.assertTrue(res.is_duplicate)
            self.assertEqual(res.match_tier, "CONTACT_TITLE")

    def test_tier4_source_url_match(self):
        """Tier 4: Matching application source URL triggers duplicate."""
        with self.Session() as s:
            repo = ApplicationRepository(s)
            res = repo.check_duplicate_outreach_application(
                source_url="https://jobs.example.com/rpa/123",
            )
            self.assertTrue(res.is_duplicate)
            self.assertEqual(res.match_tier, "SOURCE_URL")

    def test_lifecycle_aware_inactive_states_do_not_block(self):
        """Inactive terminal states like WITHDRAWN do not trigger duplicate blocking."""
        with self.Session() as s:
            # Change application to WITHDRAWN
            app = s.get(Application, 1)
            app.status = "WITHDRAWN"
            s.commit()

            repo = ApplicationRepository(s)
            res = repo.check_duplicate_outreach_application(job_id=1)
            self.assertFalse(res.is_duplicate)

    def test_non_matching_criteria_returns_false(self):
        """Different company and title returns no duplicate."""
        with self.Session() as s:
            repo = ApplicationRepository(s)
            res = repo.check_duplicate_outreach_application(
                company_name="Acme Corp",
                job_title="DevOps Lead",
                contact_email="recruiter@acme.org",
            )
            self.assertFalse(res.is_duplicate)


if __name__ == "__main__":
    unittest.main()
