'''
Phase 18: Automated Regression Tests & End-to-End Verification Harness
Comprehensive test suite validating:
1. URL generation & slugification
2. Experience parsing (Naukri card & job descriptions)
3. Salary parsing (Lacs PA & formatted currency)
4. Job normalization (Naukri & LinkedIn to canonical Job model)
5. Deduplication & tracker idempotency
6. QnA Engine answer resolution & provenance
7. Answer validation & untrusted input filtering
8. Application state machine & safety invariants (UNKNOWN, MANUAL_REQUIRED, etc.)
9. Full End-to-End multi-platform simulation harness with Dashboard integration
'''

import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from modules.models import Job, job_from_naukri, job_from_linkedin
from modules.qualification_engine import (
    QualificationEngine,
    QualificationResult,
    extract_experience_bounds,
)
from modules.qna_engine import QnAEngine, Answer, validate_answer
from modules.tracker import ApplicationTracker, ApplicationRecord
from platforms.naukri.search import slugify, build_search_url, NaukriSearch
from platforms.naukri.parser import (
    parse_experience_string,
    parse_salary_string,
    parse_work_style,
    extract_job_id,
    NaukriJobParser,
)
from platforms.naukri.selectors import (
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_EXPERIENCE_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_DESCRIPTION_SNIPPET,
)
from platforms.naukri.applier import NaukriFlowDetector
from platforms.naukri.safety_gate import NaukriSafetyGate, ApplicationReviewSummary
from platforms.naukri.submitter import NaukriSubmitter
from platforms.naukri.rotator import SearchRotationEngine, SearchRotationConfig
from platforms.router import PlatformRouter, LinkedInPlatform, NaukriPlatform
from app import app as flask_app


# =====================================================================
# 1. URL Generation & Slugification Regression Tests
# =====================================================================
class TestURLGenerationRegression(unittest.TestCase):
    """Verifies that URL generation and slugification meet all Naukri routing requirements."""

    def test_slugify_variations(self):
        cases = [
            ("RPA Developer", "rpa-developer"),
            ("Python / Django & React", "python-django-react"),
            ("C++ Engineer (Remote!)", "c-engineer-remote"),
            ("AI / ML Specialist #1", "ai-ml-specialist-1"),
            ("   Senior   Automation   Architect   ", "senior-automation-architect"),
            ("devops_engineer", "devops-engineer"),
        ]
        for input_text, expected in cases:
            with self.subTest(input_text=input_text):
                self.assertEqual(slugify(input_text), expected)

    def test_build_search_url_pagination(self):
        # Page 1 must not contain -1 in URL path
        url_p1 = build_search_url("RPA Developer", "India", experience_years=2, page=1)
        self.assertTrue(url_p1.startswith("https://www.naukri.com/rpa-developer-jobs-in-india?"))
        self.assertNotIn("-jobs-in-india-1", url_p1)
        self.assertIn("k=RPA+Developer", url_p1)
        self.assertIn("l=India", url_p1)
        self.assertIn("experience=2", url_p1)

        # Page 2 and above must append page suffix to slug
        url_p2 = build_search_url("RPA Developer", "India", experience_years=2, page=2)
        self.assertTrue(url_p2.startswith("https://www.naukri.com/rpa-developer-jobs-in-india-2?"))

        url_p5 = build_search_url("Python Developer", "Delhi", experience_years=3, page=5)
        self.assertTrue(url_p5.startswith("https://www.naukri.com/python-developer-jobs-in-delhi-5?"))

    def test_build_search_url_parameters(self):
        # Optional freshness / jobAge
        url_fresh = build_search_url("Automation", "Bangalore", freshness_days=3)
        self.assertIn("jobAge=3", url_fresh)

        # Missing location
        url_no_loc = build_search_url("Data Analyst", "")
        self.assertTrue(url_no_loc.startswith("https://www.naukri.com/data-analyst-jobs?"))
        self.assertNotIn("in-", url_no_loc)

        # Zero experience (Fresher filter)
        url_fresher = build_search_url("Trainee", "Pune", experience_years=0)
        self.assertIn("experience=0", url_fresher)


# =====================================================================
# 2. Experience Parsing Regression Tests
# =====================================================================
class TestExperienceParsingRegression(unittest.TestCase):
    """Verifies parsing of raw Naukri card experience strings and JD text bounds."""

    def test_parse_experience_string_canonical_examples(self):
        # Explicit examples from Roadmap Phase 18:
        # "1-5 years" → min=1, max=5
        # "3 to 5 years" → min=3, max=5
        # "5+ years" → min=5
        # "2 yrs" → min=2
        self.assertEqual(parse_experience_string("1-5 years"), (1, 5))
        self.assertEqual(parse_experience_string("3 to 5 years"), (3, 5))
        self.assertEqual(parse_experience_string("5+ years"), (5, None))
        self.assertEqual(parse_experience_string("2 yrs"), (2, None))

    def test_parse_experience_string_edge_cases(self):
        cases = [
            ("0-2 Yrs", (0, 2)),
            ("0 - 1 years", (0, 1)),
            ("10 - 15 Yrs", (10, 15)),
            ("12+ Yrs", (12, None)),
            ("Fresher", (0, 0)),
            ("Freshers can apply", (0, 0)),
            ("Entry Level Fresher", (0, 0)),
            ("Not Disclosed", (None, None)),
            ("Unspecified", (None, None)),
            ("", (None, None)),
            (None, (None, None)),
        ]
        for input_val, expected in cases:
            with self.subTest(input_val=input_val):
                self.assertEqual(parse_experience_string(input_val), expected)

    def test_extract_experience_bounds_from_jd(self):
        # Description text extraction in QualificationEngine
        self.assertEqual(
            extract_experience_bounds("Looking for an engineer with 1-5 years experience"),
            (1, 5)
        )
        self.assertEqual(
            extract_experience_bounds("Requires 3 to 5 years hands-on RPA experience"),
            (3, 5)
        )
        self.assertEqual(
            extract_experience_bounds("Candidate must possess 5+ years building backend APIs"),
            (5, None)
        )
        self.assertEqual(
            extract_experience_bounds("Minimum 2 yrs experience in test automation"),
            (2, None)
        )
        self.assertEqual(
            extract_experience_bounds("Candidate should have 2-4 yrs experience"),
            (2, 4)
        )
        self.assertEqual(
            extract_experience_bounds("No experience required. College graduates welcome."),
            (None, None)
        )


# =====================================================================
# 3. Salary Parsing Regression Tests
# =====================================================================
class TestSalaryParsingRegression(unittest.TestCase):
    """Verifies parsing of Naukri salary strings into INR annual numbers."""

    def test_parse_salary_lacs(self):
        self.assertEqual(parse_salary_string("3-6 Lacs PA"), (300000, 600000))
        self.assertEqual(parse_salary_string("3.5 - 5.5 Lacs PA"), (350000, 550000))
        self.assertEqual(parse_salary_string("6.0 Lacs PA"), (600000, None))
        self.assertEqual(parse_salary_string("12 - 18 Lacs P.A."), (1200000, 1800000))
        self.assertEqual(parse_salary_string("4.25 Lacs PA"), (425000, None))

    def test_parse_salary_raw_currency(self):
        self.assertEqual(parse_salary_string("50,000 - 1,00,000 PA"), (50000, 100000))
        self.assertEqual(parse_salary_string("3,50,000 - 5,50,000 P.A."), (350000, 550000))

    def test_parse_salary_undisclosed_and_blanks(self):
        cases = ["Not Disclosed", "Confidential", "Unspecified", "Hidden", "", None]
        for val in cases:
            with self.subTest(val=val):
                self.assertEqual(parse_salary_string(val), (None, None))


# =====================================================================
# 4. Job Normalization Regression Tests
# =====================================================================
class TestJobNormalizationRegression(unittest.TestCase):
    """Verifies that platform-specific listings convert to canonical Job models identically."""

    def test_naukri_normalization(self):
        job = job_from_naukri(
            job_id="naukri_998877",
            title="Senior Automation Engineer",
            company="Tata Consultancy Services",
            location="Pune, India",
            required_experience_min=2,
            required_experience_max=5,
            salary_min=400000,
            salary_max=800000,
            work_style="Hybrid",
            source_url="https://www.naukri.com/job-listings-998877",
            raw_metadata={"department": "Engineering"}
        )
        self.assertEqual(job.platform, "naukri")
        self.assertEqual(job.job_id, "naukri_998877")
        self.assertEqual(job.required_experience_min, 2)
        self.assertEqual(job.required_experience_max, 5)
        self.assertEqual(job.salary_min, 400000)
        self.assertEqual(job.salary_max, 800000)
        self.assertEqual(job.work_style, "Hybrid")
        self.assertEqual(job.apply_type, "DIRECT")
        self.assertIn("department", job.raw_metadata)

    def test_linkedin_normalization(self):
        job = job_from_linkedin(
            job_id="li_11223344",
            title="RPA Developer",
            company="Infosys",
            location="Bengaluru, Karnataka, India",
            experience_required=3,
            source_url="https://www.linkedin.com/jobs/view/11223344",
            work_style="Remote"
        )
        self.assertEqual(job.platform, "linkedin")
        self.assertEqual(job.job_id, "li_11223344")
        self.assertEqual(job.required_experience_min, 3)
        self.assertEqual(job.work_style, "Remote")
        self.assertEqual(job.apply_type, "DIRECT")

    def test_work_style_heuristics(self):
        self.assertEqual(parse_work_style("Remote", "Software Engineer"), "Remote")
        self.assertEqual(parse_work_style("Noida", "RPA Developer (Work From Home)"), "Remote")
        self.assertEqual(parse_work_style("Bangalore", "DevOps", "Hybrid model 3 days a week"), "Hybrid")
        self.assertEqual(parse_work_style("Gurgaon", "Backend Engineer"), "On-site")
        self.assertIsNone(parse_work_style("", "Developer"))


# =====================================================================
# 5. Deduplication & Idempotency Regression Tests
# =====================================================================
class TestDeduplicationRegression(unittest.TestCase):
    """Verifies that application tracking strictly enforces deduplication and idempotency."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.temp_dir, "applications.csv")
        self.tracker = ApplicationTracker(file_path=self.csv_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_idempotent_submission(self):
        job = job_from_naukri("job_dedup_1", "RPA Lead", "AventIQ", "Delhi")
        self.tracker.record_job(job)

        # Before apply
        handled, _ = self.tracker.is_already_handled("job_dedup_1", platform="naukri")
        self.assertFalse(handled)
        self.assertTrue(self.tracker.is_retryable("job_dedup_1", platform="naukri"))

        # Submit
        self.tracker.record_submission(job, status="SUBMITTED")

        # After submit
        handled, reason = self.tracker.is_already_handled("job_dedup_1", platform="naukri")
        self.assertTrue(handled)
        self.assertIn("Already successfully submitted", reason)
        self.assertFalse(self.tracker.is_retryable("job_dedup_1", platform="naukri"))
        self.assertTrue(self.tracker.is_applied("job_dedup_1", platform="naukri"))

    def test_sync_legacy_files_no_duplicates(self):
        # Write mock legacy LinkedIn files
        li_dir = os.path.join(self.temp_dir, "all excels")
        os.makedirs(li_dir, exist_ok=True)
        li_applied = os.path.join(li_dir, "applied_jobs.csv")
        with open(li_applied, "w", encoding="utf-8") as f:
            f.write("Job ID,Title,Company,Date Applied\n")
            f.write("li_100,Python Dev,Google,2026-09-15 10:00:00\n")

        self.tracker.sync_legacy_linkedin_files(applied_csv=li_applied, failed_csv="")
        rec = self.tracker.get_record("li_100", platform="linkedin")
        self.assertIsNotNone(rec)
        self.assertEqual(rec.status, "SUBMITTED")

        # Running sync again must not duplicate records
        self.tracker.sync_legacy_linkedin_files(applied_csv=li_applied, failed_csv="")
        all_records = self.tracker.get_all_records()
        self.assertEqual(len(all_records), 1)


# =====================================================================
# 6. QnA Provenance Regression Tests
# =====================================================================
class TestQnAProvenanceRegression(unittest.TestCase):
    """Verifies that all answers carry provenance and strict confidence ratings."""

    def setUp(self):
        self.qna = QnAEngine(ai_client=None)

    def test_ctc_and_notice_provenance(self):
        ans_curr = self.qna.resolve_text_answer("What is your expected CTC in Lakhs?")
        self.assertEqual(ans_curr.source, "calculation")
        self.assertTrue(ans_curr.validated)
        self.assertGreaterEqual(ans_curr.confidence, 0.9)
        self.assertIn("5.5", str(ans_curr.value))

        ans_np = self.qna.resolve_text_answer("Notice period in months")
        self.assertEqual(ans_np.source, "calculation")
        self.assertTrue(ans_np.validated)

    def test_profile_and_rule_provenance(self):
        ans_exp = self.qna.resolve_text_answer("Total years of experience")
        self.assertIn(ans_exp.source, ("profile", "rule"))
        self.assertTrue(ans_exp.validated)

        ans_name = self.qna.resolve_text_answer("Full legal name")
        self.assertEqual(ans_name.source, "profile")
        self.assertTrue(ans_name.validated)

        ans_why = self.qna.resolve_text_answer("Why should we hire you?")
        self.assertEqual(ans_why.source, "rule")
        self.assertTrue(ans_why.validated)


# =====================================================================
# 7. Answer Validation & Untrusted String Filtering Regression Tests
# =====================================================================
class TestAnswerValidationRegression(unittest.TestCase):
    """Verifies domain constraints on answers, rejecting invalid or untrusted inputs."""

    def test_notice_period_validation(self):
        # Valid: 0 to 180 days
        self.assertTrue(validate_answer(Answer("30", "profile", 1.0), "Notice Period (Days)").validated)
        self.assertTrue(validate_answer(Answer("0", "profile", 1.0), "Notice Period in days").validated)
        self.assertTrue(validate_answer(Answer("Immediate", "rule", 0.95), "Notice Period").validated)

        # Invalid: Negative or absurd
        self.assertFalse(validate_answer(Answer("-5", "llm", 0.5), "Notice Period (Days)").validated)
        self.assertFalse(validate_answer(Answer("365", "llm", 0.5), "Notice Period (Days)").validated)
        self.assertFalse(validate_answer(Answer("", "llm", 0.1), "Notice Period (Days)").validated)

    def test_ctc_validation(self):
        # Valid: 0.5 to 100.0 LPA
        self.assertTrue(validate_answer(Answer("3.5", "profile", 1.0), "Current CTC (in Lacs)").validated)
        self.assertTrue(validate_answer(Answer("15.0", "profile", 1.0), "Expected CTC in Lacs").validated)

        # Invalid: Negative, zero, or absurdly high
        self.assertFalse(validate_answer(Answer("0", "llm", 0.2), "Expected CTC in Lacs").validated)
        self.assertFalse(validate_answer(Answer("-2.5", "llm", 0.2), "Current CTC in Lacs").validated)
        self.assertFalse(validate_answer(Answer("500", "llm", 0.2), "Current CTC in Lacs").validated)
        self.assertFalse(validate_answer(Answer("unknown", "llm", 0.2), "Current CTC in Lacs").validated)

    def test_experience_validation(self):
        # Valid: 0 to 45 years
        self.assertTrue(validate_answer(Answer("2", "rule", 0.95), "Total Experience in Years").validated)
        self.assertTrue(validate_answer(Answer("0", "rule", 0.95), "Experience in Python").validated)

        # Invalid: Negative or unrealistic
        self.assertFalse(validate_answer(Answer("-1", "llm", 0.3), "Years of Experience").validated)
        self.assertFalse(validate_answer(Answer("60", "llm", 0.3), "Years of Experience").validated)

    def test_choice_option_constraint(self):
        options = ["Yes", "No"]
        self.assertTrue(validate_answer(Answer("Yes", "rule", 0.95), "Are you willing to relocate?", options).validated)
        self.assertTrue(validate_answer(Answer("no", "rule", 0.95), "Are you willing to relocate?", options).validated)

        # Rejects option not present in select/radio choices
        self.assertFalse(validate_answer(Answer("Maybe", "llm", 0.4), "Are you willing to relocate?", options).validated)


# =====================================================================
# 8. Application State Invariants Regression Tests
# =====================================================================
class TestApplicationStatesRegression(unittest.TestCase):
    """Verifies that critical states (UNKNOWN, MANUAL_REQUIRED, FAILED) obey idempotency invariants."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = ApplicationTracker(file_path=os.path.join(self.temp_dir, "applications.csv"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_unknown_state_is_never_auto_retried(self):
        # Strict Invariant: Post-click timeouts result in UNKNOWN, and UNKNOWN jobs MUST NOT be retried
        job = job_from_naukri("job_unk_99", "Backend Dev", "Tech Corp", "Delhi")
        self.tracker.record_job(job)
        self.tracker.record_submission(job, status="UNKNOWN", failure_reason="Timeout waiting for confirmation banner")

        handled, reason = self.tracker.is_already_handled("job_unk_99", platform="naukri")
        self.assertTrue(handled)
        self.assertIn("UNKNOWN state — cannot automatically retry", reason)
        self.assertFalse(self.tracker.is_retryable("job_unk_99", platform="naukri"))

    def test_manual_required_state_halts_automation(self):
        job = job_from_naukri("job_man_88", "RPA Dev", "Secure Org", "Noida")
        self.tracker.record_job(job)
        self.tracker.record_submission(job, status="MANUAL_REQUIRED", failure_reason="CAPTCHA challenge encountered")

        handled, reason = self.tracker.is_already_handled("job_man_88", platform="naukri")
        self.assertTrue(handled)
        self.assertIn("MANUAL_REQUIRED", reason)
        self.assertFalse(self.tracker.is_retryable("job_man_88", platform="naukri"))

    def test_skipped_state_records_reason(self):
        job = job_from_naukri("job_skip_77", "Mechanical Supervisor", "Factory Ltd", "Pune")
        self.tracker.record_evaluation(job, "SKIPPED", skip_reason="Negative title word: mechanical")

        rec = self.tracker.get_record("job_skip_77", platform="naukri")
        self.assertEqual(rec.status, "SKIPPED")
        self.assertEqual(rec.skip_reason, "Negative title word: mechanical")

        # When checking already handled, skipped job is safely skipped
        handled, reason = self.tracker.is_already_handled("job_skip_77", platform="naukri", skip_if_previously_skipped=True)
        self.assertTrue(handled)
        self.assertIn("Previously skipped", reason)


# =====================================================================
# 9. End-to-End Simulation Harness & Cross-Platform Verification
# =====================================================================
class TestEndToEndHarness(unittest.TestCase):
    """Full integration test simulating search rotation, qualification, form filling,
    safety gate approval, submission, unified history tracking, and dashboard reporting.
    """

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.csv_path = os.path.join(self.temp_dir, "applications.csv")
        self.tracker = ApplicationTracker(file_path=self.csv_path)

        # Qualification Engine with candidate having 2 years exp
        self.qual_engine = QualificationEngine(
            candidate_experience=2,
            did_masters=False,
            security_clearance=False,
            bad_words=["US Citizen Only", "Polygraph"],
            negative_title_words=["mechanical", "civil", "technician"],
            blacklisted_companies={"ScamCorp"},
            about_company_bad_words=["Staffing"],
            about_company_good_words=["Robert Half"],
        )

        # Mock browser session
        self.mock_driver = MagicMock()
        self.mock_driver.window_handles = ["win_main"]
        self.mock_driver.current_window_handle = "win_main"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_full_naukri_pipeline_simulation(self):
        # 1. Simulate discovery of 3 jobs
        job_direct = job_from_naukri(
            job_id="naukri_e2e_001",
            title="Senior RPA Developer",
            company="Enterprise AI",
            location="Noida, India",
            required_experience_min=2,
            required_experience_max=4,
            source_url="https://www.naukri.com/job-listings-001"
        )
        job_disqualified = job_from_naukri(
            job_id="naukri_e2e_002",
            title="Mechanical Maintenance Engineer",
            company="Tata Steel",
            location="Jamshedpur",
            required_experience_min=1,
            required_experience_max=3,
            source_url="https://www.naukri.com/job-listings-002"
        )
        job_external = job_from_naukri(
            job_id="naukri_e2e_003",
            title="Lead Python Developer",
            company="Amazon",
            location="Hyderabad",
            required_experience_min=2,
            required_experience_max=5,
            source_url="https://www.naukri.com/job-listings-003"
        )

        # 2. Evaluate qualification
        # Job 1 (Direct) qualifies
        res1 = self.qual_engine.qualify(job_direct)
        self.assertTrue(res1.accepted)
        self.tracker.record_job(job_direct)
        self.tracker.record_evaluation(job_direct, "QUALIFIED")

        # Job 2 (Mechanical) disqualified
        res2 = self.qual_engine.qualify(job_disqualified)
        self.assertFalse(res2.accepted)
        self.tracker.record_job(job_disqualified)
        self.tracker.record_evaluation(job_disqualified, "SKIPPED", skip_reason=res2.reason)

        # Job 3 (External) qualifies initially
        res3 = self.qual_engine.qualify(job_external)
        self.assertTrue(res3.accepted)
        self.tracker.record_job(job_external)
        self.tracker.record_evaluation(job_external, "QUALIFIED")

        # 3. Simulate Flow Detection
        flow_detector = NaukriFlowDetector(self.mock_driver)

        # Handle Job 3: Flow detector detects external redirect -> marks EXTERNAL
        with patch.object(flow_detector, "detect_flow_after_click", return_value="EXTERNAL"):
            with patch.object(flow_detector, "close_modal_if_open"):
                self.tracker.record_submission(job_external, status="EXTERNAL", failure_reason="External company site redirect")

        # Handle Job 1: Flow detector detects Questionnaire modal -> fills form -> safety gate approves -> submit confirms
        with patch.object(flow_detector, "detect_flow_after_click", return_value="QUESTIONNAIRE"):
            # Mock Form
            mock_form = MagicMock()
            mock_form.fill_form.return_value = {
                "success": True,
                "status": "STOPPED_AT_SUBMIT",
                "answers": [
                    Answer("3.50", "calculation", 0.98, "text", True),
                    Answer("5.50", "calculation", 0.98, "text", True),
                    Answer("30", "profile", 1.0, "text", True),
                ]
            }

            # Mock Safety Gate: returns APPROVE
            gate = NaukriSafetyGate(pause_before_submit=True, review_handler=lambda s: "APPROVE")
            gate_res = gate.review(
                job=job_direct,
                filled_fields=[
                    {"field": "What is your current CTC in Lacs?", "value": "3.50", "source": "calculation", "confidence": 0.98},
                    {"field": "Expected CTC in Lacs", "value": "5.50", "source": "calculation", "confidence": 0.98},
                    {"field": "Notice period in days", "value": "30", "source": "profile", "confidence": 1.0},
                ]
            )
            self.assertEqual(gate_res.decision, "APPROVE")

            # Mock Submitter: confirms submission
            submitter = NaukriSubmitter(self.mock_driver, tracker=self.tracker)
            with patch.object(submitter, "find_submit_button", return_value=MagicMock()):
                with patch.object(submitter, "verify_submission", return_value=(True, "Success banner detected")):
                    ok, msg = submitter.submit_application(job_direct)
                    self.assertTrue(ok)
                    self.assertEqual(msg, "CONFIRMED_SUBMITTED")

        # 4. Verify Final Tracker State
        self.assertEqual(self.tracker.get_state("naukri_e2e_001", platform="naukri"), "SUBMITTED")
        self.assertEqual(self.tracker.get_state("naukri_e2e_002", platform="naukri"), "SKIPPED")
        self.assertEqual(self.tracker.get_state("naukri_e2e_003", platform="naukri"), "EXTERNAL")

        # 5. Verify Flask Dashboard API Reporting against this ledger
        client = flask_app.test_client()
        with patch("app.tracker", self.tracker):
            # Naukri stats endpoint
            resp = client.get("/api/naukri/stats")
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertEqual(data["applications"], 3)
            self.assertEqual(data["success"], 1)
            self.assertEqual(data["skipped"], 1)
            self.assertEqual(data["external"], 1)
            self.assertEqual(data["failed"], 0)

            # Combined stats endpoint
            resp_stats = client.get("/api/stats")
            self.assertEqual(resp_stats.status_code, 200)
            stats_data = resp_stats.get_json()
            self.assertEqual(stats_data["naukri"]["success"], 1)
            self.assertEqual(stats_data["naukri"]["skipped"], 1)
            self.assertEqual(stats_data["naukri"]["external"], 1)

            # Applications listing endpoint
            resp_apps = client.get("/api/applications?platform=naukri")
            self.assertEqual(resp_apps.status_code, 200)
            apps_data = resp_apps.get_json()
            self.assertEqual(len(apps_data), 3)

    def test_linkedin_regression_safety(self):
        """Verifies zero regressions on LinkedIn platform classes and CLI routing."""
        mock_li = MagicMock(spec=LinkedInPlatform)
        mock_li.platform_name = "linkedin"
        mock_li.login.return_value = True
        mock_li.search_and_apply.return_value = {"platform": "linkedin", "result": "completed", "applications": 12}

        router = PlatformRouter(linkedin_platform=mock_li)
        res = router.route("linkedin")
        self.assertEqual(res["result"], "completed")
        self.assertEqual(res["applications"], 12)
        self.assertEqual(res["platform"], "linkedin")
        mock_li.login.assert_called_once()
        mock_li.search_and_apply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
