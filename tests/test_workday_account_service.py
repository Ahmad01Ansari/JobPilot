"""Unit tests for WorkdayAccountService."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.workday_account_service import WorkdayAccountService


class TestWorkdayAccountService(unittest.TestCase):
    """Verifies tenant extraction, Workday detection, and company account CRUD."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.service = WorkdayAccountService(session_factory=self.session_factory)

    def tearDown(self):
        self.engine.dispose()

    def test_is_workday_portal(self):
        # Workday URLs
        self.assertTrue(self.service.is_workday_portal("https://tranetechnologies.wd12.myworkdayjobs.com/en-US/job/123"))
        self.assertTrue(self.service.is_workday_portal("https://walmart.wd5.myworkdayjobs.com/Careers"))
        self.assertTrue(self.service.is_workday_portal("https://company.myworkday.com/login"))
        
        # Other ATS URLs (Must NOT be flagged as Workday)
        self.assertFalse(self.service.is_workday_portal("https://boards.greenhouse.io/airbnb/jobs/123"))
        self.assertFalse(self.service.is_workday_portal("https://jobs.lever.co/stripe/abc-xyz"))
        self.assertFalse(self.service.is_workday_portal("https://careers.smartrecruiters.com/AcmeCorp"))
        self.assertFalse(self.service.is_workday_portal("https://indeed.com/viewjob?jk=123"))

    def test_extract_tenant(self):
        url = "https://tranetechnologies.wd12.myworkdayjobs.com/en-US/Trane_Technologies_Careers/job/JR-11455"
        self.assertEqual(self.service.extract_tenant(url), "tranetechnologies")

        url2 = "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced"
        self.assertEqual(self.service.extract_tenant(url2), "adobe")

    def test_account_crud_lifecycle(self):
        url = "https://tranetechnologies.wd12.myworkdayjobs.com/en-US/Trane_Technologies_Careers/job/JR-11455"
        
        # 1. Initially no account
        self.assertFalse(self.service.has_account(url))
        self.assertIsNone(self.service.get_account(url))

        # 2. Record account
        rec = self.service.record_account(url, company_name="Trane Technologies", username="candidate@example.com")
        self.assertEqual(rec["tenant"], "tranetechnologies")
        self.assertEqual(rec["company_name"], "Trane Technologies")

        # 3. Verify lookup
        self.assertTrue(self.service.has_account(url))
        self.assertTrue(self.service.has_account("https://tranetechnologies.wd12.myworkdayjobs.com/another-job"))
        self.assertTrue(self.service.has_account("", company_name="Trane Technologies"))
        
        # Different company is still False
        self.assertFalse(self.service.has_account("https://walmart.wd5.myworkdayjobs.com/job/456"))

        # 4. List accounts
        all_accts = self.service.list_accounts()
        self.assertEqual(len(all_accts), 1)
        self.assertEqual(all_accts[0]["username"], "candidate@example.com")

        # 5. Delete account
        deleted = self.service.delete_account("tranetechnologies")
        self.assertTrue(deleted)
        self.assertFalse(self.service.has_account(url))
        self.assertEqual(len(self.service.list_accounts()), 0)


if __name__ == "__main__":
    unittest.main()
