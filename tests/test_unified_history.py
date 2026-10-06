'''
Unit Tests for Unified Application History (Phase 15)
Validates the canonical 12-column applications.csv schema,
ApplicationRecord aliases for backwards compatibility,
multi-platform deduplication, query methods, and legacy LinkedIn CSV synchronization.
'''

import os
import csv
import tempfile
import unittest
from unittest.mock import MagicMock

from modules.models import Job
from modules.tracker import (
    ApplicationTracker,
    ApplicationRecord,
    CSV_FIELDNAMES,
    DEFAULT_TRACKER_PATH,
)


class TestUnifiedApplicationHistory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "applications.csv")
        self.tracker = ApplicationTracker(file_path=self.csv_path)

        self.sample_naukri_job = Job(
            platform="naukri",
            job_id="naukri_101",
            title="Senior RPA Developer",
            company="Tech Corp",
            location="Noida, India",
            source_url="https://www.naukri.com/job-listings-101",
        )

        self.sample_linkedin_job = Job(
            platform="linkedin",
            job_id="li_202",
            title="Python Automation Engineer",
            company="Global Solutions",
            location="Remote",
            source_url="https://www.linkedin.com/jobs/view/202",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_canonical_12_column_csv_header(self):
        self.tracker.record_state(self.sample_naukri_job, "DISCOVERED")

        self.assertTrue(os.path.exists(self.csv_path))
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)

        expected_columns = [
            "platform",
            "job_id",
            "title",
            "company",
            "location",
            "source_url",
            "status",
            "application_type",
            "discovered_at",
            "applied_at",
            "failure_reason",
            "skip_reason",
        ]
        self.assertEqual(header, expected_columns)
        self.assertEqual(header, CSV_FIELDNAMES)

    def test_record_state_submitted_populates_applied_at(self):
        rec = self.tracker.record_state(self.sample_naukri_job, "SUBMITTED")
        self.assertEqual(rec.status, "SUBMITTED")
        self.assertEqual(rec.state, "SUBMITTED")  # Backwards-compat property
        self.assertIsNotNone(rec.applied_at)
        self.assertEqual(rec.updated_at, rec.applied_at)  # Backwards-compat property

        # Verify CSV contents
        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["platform"], "naukri")
            self.assertEqual(row["job_id"], "naukri_101")
            self.assertEqual(row["status"], "SUBMITTED")
            self.assertEqual(row["applied_at"], rec.applied_at)
            self.assertEqual(row["failure_reason"], "")
            self.assertEqual(row["skip_reason"], "")

    def test_record_state_skipped_populates_skip_reason(self):
        rec = self.tracker.record_state(
            self.sample_naukri_job,
            "SKIPPED",
            reason="Experience exceeds candidate criteria",
        )
        self.assertEqual(rec.status, "SKIPPED")
        self.assertEqual(rec.skip_reason, "Experience exceeds candidate criteria")
        self.assertIsNone(rec.failure_reason)
        self.assertEqual(rec.reason, "Experience exceeds candidate criteria")  # Property alias
        self.assertIsNone(rec.applied_at)

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["skip_reason"], "Experience exceeds candidate criteria")
            self.assertEqual(rows[0]["failure_reason"], "")

    def test_record_state_failed_populates_failure_reason(self):
        rec = self.tracker.record_state(
            self.sample_naukri_job,
            "FAILED",
            reason="Modal close button timed out",
        )
        self.assertEqual(rec.status, "FAILED")
        self.assertEqual(rec.failure_reason, "Modal close button timed out")
        self.assertIsNone(rec.skip_reason)
        self.assertEqual(rec.reason, "Modal close button timed out")  # Property alias

        with open(self.csv_path, mode="r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["failure_reason"], "Modal close button timed out")
            self.assertEqual(rows[0]["skip_reason"], "")

    def test_record_evaluation_helper(self):
        rec = self.tracker.record_evaluation(
            self.sample_naukri_job,
            "SKIPPED",
            skip_reason="Negative title word: mechanical",
        )
        self.assertEqual(rec.status, "SKIPPED")
        self.assertEqual(rec.skip_reason, "Negative title word: mechanical")

    def test_query_methods(self):
        self.tracker.record_state(self.sample_naukri_job, "SUBMITTED")
        self.tracker.record_state(self.sample_linkedin_job, "SKIPPED", reason="Blacklisted company")

        # get_record
        rec_nk = self.tracker.get_record("naukri_101", "naukri")
        self.assertIsNotNone(rec_nk)
        self.assertEqual(rec_nk.title, "Senior RPA Developer")

        # get_status and get_state
        self.assertEqual(self.tracker.get_status("naukri_101", "naukri"), "SUBMITTED")
        self.assertEqual(self.tracker.get_state("naukri_101", "naukri"), "SUBMITTED")
        self.assertEqual(self.tracker.get_status("li_202", "linkedin"), "SKIPPED")

        # get_all_records
        all_recs = self.tracker.get_all_records()
        self.assertEqual(len(all_recs), 2)

        nk_recs = self.tracker.get_all_records(platform="naukri")
        self.assertEqual(len(nk_recs), 1)
        self.assertEqual(nk_recs[0].platform, "naukri")

        submitted_recs = self.tracker.get_all_records(status="SUBMITTED")
        self.assertEqual(len(submitted_recs), 1)
        self.assertEqual(submitted_recs[0].job_id, "naukri_101")

    def test_multi_platform_stats(self):
        self.tracker.record_state(self.sample_naukri_job, "SUBMITTED")
        self.tracker.record_state(self.sample_linkedin_job, "QUALIFIED")

        nk_stats = self.tracker.get_stats("naukri")
        self.assertEqual(nk_stats["SUBMITTED"], 1)
        self.assertEqual(nk_stats["QUALIFIED"], 0)

        li_stats = self.tracker.get_stats("linkedin")
        self.assertEqual(li_stats["SUBMITTED"], 0)
        self.assertEqual(li_stats["QUALIFIED"], 1)

        total_stats = self.tracker.get_stats()
        self.assertEqual(total_stats["SUBMITTED"], 1)
        self.assertEqual(total_stats["QUALIFIED"], 1)

    def test_sync_legacy_linkedin_files(self):
        # Create mock legacy LinkedIn applied CSV
        legacy_applied = os.path.join(self.temp_dir.name, "legacy_applied.csv")
        with open(legacy_applied, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Job ID", "Title", "Company", "Work Location", "Date Applied", "Job Link"],
            )
            writer.writeheader()
            writer.writerow({
                "Job ID": "998877",
                "Title": "RPA Consultant",
                "Company": "Old Corp",
                "Work Location": "Bengaluru",
                "Date Applied": "2026-09-10 12:00:00",
                "Job Link": "https://www.linkedin.com/jobs/view/998877",
            })

        # Create mock legacy LinkedIn failed CSV
        legacy_failed = os.path.join(self.temp_dir.name, "legacy_failed.csv")
        with open(legacy_failed, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Job ID", "Job Link", "Date Tried", "Assumed Reason"],
            )
            writer.writeheader()
            writer.writerow({
                "Job ID": "112233",
                "Job Link": "https://www.linkedin.com/jobs/view/112233",
                "Date Tried": "2026-09-11 14:00:00",
                "Assumed Reason": "Found a Bad Word in About Job",
            })
            writer.writerow({
                "Job ID": "445566",
                "Job Link": "https://www.linkedin.com/jobs/view/445566",
                "Date Tried": "2026-09-11 15:00:00",
                "Assumed Reason": "Timeout clicking Easy Apply",
            })

        new_count = self.tracker.sync_legacy_linkedin_files(
            applied_csv=legacy_applied,
            failed_csv=legacy_failed,
        )

        self.assertEqual(new_count, 3)

        # Verify applied job ingestion
        rec_app = self.tracker.get_record("998877", "linkedin")
        self.assertIsNotNone(rec_app)
        self.assertEqual(rec_app.status, "SUBMITTED")
        self.assertEqual(rec_app.title, "RPA Consultant")
        self.assertEqual(rec_app.application_type, "EASY_APPLY")
        self.assertEqual(rec_app.applied_at, "2026-09-10 12:00:00")

        # Verify skipped job ingestion (from bad word)
        rec_skip = self.tracker.get_record("112233", "linkedin")
        self.assertIsNotNone(rec_skip)
        self.assertEqual(rec_skip.status, "SKIPPED")
        self.assertEqual(rec_skip.skip_reason, "Found a Bad Word in About Job")

        # Verify failed job ingestion
        rec_fail = self.tracker.get_record("445566", "linkedin")
        self.assertIsNotNone(rec_fail)
        self.assertEqual(rec_fail.status, "FAILED")
        self.assertEqual(rec_fail.failure_reason, "Timeout clicking Easy Apply")

    def test_legacy_format_loading(self):
        # Write a legacy CSV with old columns ('state', 'updated_at', 'reason')
        legacy_csv = os.path.join(self.temp_dir.name, "legacy_tracking.csv")
        with open(legacy_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["platform", "job_id", "title", "company", "location", "source_url", "state", "discovered_at", "updated_at", "reason", "application_type"],
            )
            writer.writeheader()
            writer.writerow({
                "platform": "naukri",
                "job_id": "leg_1",
                "title": "Legacy Job",
                "company": "Legacy Corp",
                "location": "India",
                "source_url": "https://naukri.com/leg-1",
                "state": "SUBMITTED",
                "discovered_at": "2026-09-01 10:00:00",
                "updated_at": "2026-09-01 10:05:00",
                "reason": "",
                "application_type": "DIRECT",
            })
            writer.writerow({
                "platform": "naukri",
                "job_id": "leg_2",
                "title": "Legacy Job 2",
                "company": "Legacy Corp 2",
                "location": "India",
                "source_url": "https://naukri.com/leg-2",
                "state": "SKIPPED",
                "discovered_at": "2026-09-01 11:00:00",
                "updated_at": "2026-09-01 11:01:00",
                "reason": "Exp high",
                "application_type": "DIRECT",
            })

        tracker = ApplicationTracker(file_path=legacy_csv)
        rec1 = tracker.get_record("leg_1", "naukri")
        self.assertEqual(rec1.status, "SUBMITTED")
        self.assertEqual(rec1.applied_at, "2026-09-01 10:05:00")

        rec2 = tracker.get_record("leg_2", "naukri")
        self.assertEqual(rec2.status, "SKIPPED")
        self.assertEqual(rec2.skip_reason, "Exp high")


if __name__ == "__main__":
    unittest.main()
