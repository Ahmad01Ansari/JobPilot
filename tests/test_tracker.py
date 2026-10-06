import os
import tempfile
import unittest
from modules.models import Job
from modules.tracker import ApplicationTracker, ApplicationRecord


class TestApplicationTracker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_csv = os.path.join(self.temp_dir.name, "test_tracker.csv")
        self.tracker = ApplicationTracker(file_path=self.test_csv)

        self.sample_job = Job(
            platform="naukri",
            job_id="naukri_001",
            title="RPA Developer",
            company="AventIQ AI",
            location="Noida",
            source_url="https://www.naukri.com/job-001",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_state_recording_and_retrieval(self):
        # 1. Record DISCOVERED
        self.tracker.record_state(self.sample_job, "DISCOVERED")
        self.assertEqual(self.tracker.get_state("naukri_001", "naukri"), "DISCOVERED")

        # 2. Transition to QUALIFIED
        self.tracker.record_state(self.sample_job, "QUALIFIED")
        self.assertEqual(self.tracker.get_state("naukri_001", "naukri"), "QUALIFIED")

        # 3. Transition to SUBMITTED
        self.tracker.record_state(self.sample_job, "SUBMITTED")
        self.assertEqual(self.tracker.get_state("naukri_001", "naukri"), "SUBMITTED")

    def test_submitted_job_is_not_retryable(self):
        self.tracker.record_state(self.sample_job, "SUBMITTED")
        should_skip, reason = self.tracker.is_already_handled("naukri_001", "naukri")
        self.assertTrue(should_skip)
        self.assertIn("Already successfully submitted", reason)
        self.assertFalse(self.tracker.is_retryable("naukri_001", "naukri"))

    def test_unknown_state_strict_non_retry_rule(self):
        # Critical safety test: UNKNOWN state (e.g. timeout during submit) must NEVER be auto-retried
        self.tracker.record_state(
            self.sample_job,
            "UNKNOWN",
            reason="Browser timeout after clicking apply button",
        )
        self.assertEqual(self.tracker.get_state("naukri_001", "naukri"), "UNKNOWN")

        should_skip, reason = self.tracker.is_already_handled("naukri_001", "naukri")
        self.assertTrue(should_skip)
        self.assertIn("cannot automatically retry without manual confirmation", reason)
        self.assertFalse(self.tracker.is_retryable("naukri_001", "naukri"))

    def test_manual_required_blocks_retry(self):
        self.tracker.record_state(
            self.sample_job,
            "MANUAL_REQUIRED",
            reason="CAPTCHA challenge presented on apply",
        )
        should_skip, reason = self.tracker.is_already_handled("naukri_001", "naukri")
        self.assertTrue(should_skip)
        self.assertIn("MANUAL_REQUIRED", reason)
        self.assertFalse(self.tracker.is_retryable("naukri_001", "naukri"))

    def test_csv_persistence_across_instances(self):
        job2 = Job(
            platform="naukri",
            job_id="naukri_002",
            title="Python Automation Engineer",
            company="Tech Corp",
            location="Delhi",
            source_url="https://www.naukri.com/job-002",
        )
        self.tracker.record_state(self.sample_job, "SUBMITTED")
        self.tracker.record_state(job2, "SKIPPED", reason="Required experience is high")

        # Create new instance loading the same CSV file
        new_tracker = ApplicationTracker(file_path=self.test_csv)
        self.assertEqual(new_tracker.get_state("naukri_001", "naukri"), "SUBMITTED")
        self.assertEqual(new_tracker.get_state("naukri_002", "naukri"), "SKIPPED")

        stats = new_tracker.get_stats("naukri")
        self.assertEqual(stats["SUBMITTED"], 1)
        self.assertEqual(stats["SKIPPED"], 1)
        self.assertEqual(stats["FAILED"], 0)


    def test_record_application_compatibility(self):
        # 1. Record SUBMITTED via record_application
        rec = self.tracker.record_application(
            platform="glassdoor",
            job_id="gd_001",
            title="Software Engineer",
            company="Google",
            location="Bengaluru",
            url="https://glassdoor.com/job/gd_001",
            status="SUBMITTED",
        )
        self.assertEqual(rec.status, "SUBMITTED")
        self.assertEqual(self.tracker.get_state("gd_001", "glassdoor"), "SUBMITTED")

        # 2. Record SKIPPED via record_application
        rec_skip = self.tracker.record_application(
            platform="glassdoor",
            job_id="gd_002",
            title="Senior Lead",
            company="Meta",
            location="Remote",
            url="https://glassdoor.com/job/gd_002",
            status="SKIPPED",
            reason="Title blacklisted",
        )
        self.assertEqual(rec_skip.status, "SKIPPED")
        self.assertEqual(rec_skip.skip_reason, "Title blacklisted")

        # 3. Record ALREADY_APPLIED maps to SKIPPED with reason
        rec_already = self.tracker.record_application(
            platform="glassdoor",
            job_id="gd_003",
            title="DevOps Engineer",
            company="Amazon",
            location="Hyderabad",
            url="https://glassdoor.com/job/gd_003",
            status="ALREADY_APPLIED",
        )
        self.assertEqual(rec_already.status, "SKIPPED")
        self.assertEqual(rec_already.skip_reason, "Already applied")

        # 4. Record EXTERNAL
        rec_ext = self.tracker.record_application(
            platform="glassdoor",
            job_id="gd_004",
            title="Product Manager",
            company="Apple",
            location="Bengaluru",
            url="https://glassdoor.com/job/gd_004",
            status="EXTERNAL",
        )
        self.assertEqual(rec_ext.status, "EXTERNAL")


if __name__ == "__main__":
    unittest.main()
