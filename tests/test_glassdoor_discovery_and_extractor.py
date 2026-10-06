"""
Comprehensive Unit Tests for Glassdoor UI Discovery, Page Classifier, and Semantic Extractor
Tests all layers with offline HTML fixtures and mock DOM snapshots without requiring live network access.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import shutil

from platforms.glassdoor.page_classifier import GlassdoorPageClassifier, GlassdoorPageType
from platforms.glassdoor.extractor import (
    GlassdoorJobDescriptionExtractor,
    GlassdoorJobExtractor,
    JDValidationStatus,
    validate_title,
    validate_company,
)
from platforms.glassdoor.discovery import (
    GlassdoorDiscoveryRunner,
    redact_sensitive_text,
    JobCardCandidate,
)
from platforms.glassdoor.popup_manager import GlassdoorPopupManager, PopupCategory
from modules.tracker import ApplicationTracker, ApplicationRecord


class TestGlassdoorPageClassifier(unittest.TestCase):
    """Verifies multi-signal page classification without relying solely on URL."""

    def test_classify_search_results(self):
        result = GlassdoorPageClassifier.classify_dom_snapshot(
            url="https://www.glassdoor.com/Job/jobs.htm?sc.keyword=RPA",
            title="RPA Jobs | Glassdoor",
            html='<ul data-test="job-listing-list"><li>Job 1</li></ul><input id="searchBar-jobTitle"/>',
            visible_text="Showing 25 jobs for RPA in India",
            button_texts=["Easy Apply only", "Date Posted"],
            input_names=["searchBar-jobTitle", "searchBar-location"],
        )
        self.assertEqual(result.page_type, GlassdoorPageType.SEARCH_RESULTS)
        self.assertTrue(result.is_search_results)
        self.assertGreaterEqual(result.confidence, 0.7)

    def test_classify_standalone_job_detail(self):
        result = GlassdoorPageClassifier.classify_dom_snapshot(
            url="https://www.glassdoor.com/job-listing/rpa-developer-jl=1009999",
            title="RPA Developer at TechCorp | Glassdoor",
            html='<div id="jobDescriptionText">Build bot flows using UiPath.</div><button data-test="easyApply">Easy Apply</button>',
            visible_text="RPA Developer TechCorp 3+ years experience required",
            button_texts=["Easy Apply", "Save"],
        )
        self.assertEqual(result.page_type, GlassdoorPageType.JOB_DETAIL)
        self.assertTrue(result.is_job_detail)

    def test_classify_captcha_challenge(self):
        result = GlassdoorPageClassifier.classify_dom_snapshot(
            url="https://www.glassdoor.com/Job/jobs.htm",
            title="Just a moment...",
            html='<div id="challenge-stage"><iframe src="https://challenges.cloudflare.com/turnstile"></iframe></div>',
            visible_text="Verify you are human before accessing Glassdoor",
            button_texts=["Verify"],
        )
        self.assertEqual(result.page_type, GlassdoorPageType.CAPTCHA)
        self.assertTrue(result.requires_intervention)

    def test_classify_login_wall(self):
        result = GlassdoorPageClassifier.classify_dom_snapshot(
            url="https://www.glassdoor.com/profile/login_input.htm",
            title="Sign In | Glassdoor",
            html='<form><input id="inlineUserEmail"/><input type="password"/><button type="submit">Sign In</button></form>',
            visible_text="Sign in to your Glassdoor account",
            button_texts=["Sign In", "Continue with Google"],
            input_names=["inlineUserEmail", "password"],
        )
        self.assertEqual(result.page_type, GlassdoorPageType.LOGIN)
        self.assertTrue(result.requires_intervention)

    def test_classify_smartapply_indeed_step(self):
        result = GlassdoorPageClassifier.classify_dom_snapshot(
            url="https://smartapply.indeed.com/beta/indeedapply/form/review-module",
            title="Review your application | Indeed",
            html='<button data-testid="submit-application-button">Submit your application</button>',
            visible_text="Review your application before submitting",
            button_texts=["Submit your application", "Exit"],
        )
        self.assertEqual(result.page_type, GlassdoorPageType.APPLICATION_STEP)
        self.assertEqual(result.details.get("provider"), "indeed_smart_apply")


class TestGlassdoorJobDescriptionExtractor(unittest.TestCase):
    """Verifies layered JD extraction, validation categorization, and placeholder rejection."""

    def test_validate_jd_content_valid(self):
        full_jd = "We are seeking an experienced RPA Developer proficient in UiPath, Automation Anywhere, and Python scripting. You will design, develop, and deploy end-to-end automation workflows across enterprise systems."
        status, reason = GlassdoorJobDescriptionExtractor.validate_jd_content(full_jd)
        self.assertEqual(status, JDValidationStatus.VALID_DESCRIPTION)
        self.assertIsNone(reason)

    def test_validate_jd_content_partial(self):
        short_jd = "Hiring RPA Dev. Immediate joiners."
        status, reason = GlassdoorJobDescriptionExtractor.validate_jd_content(short_jd)
        self.assertEqual(status, JDValidationStatus.PARTIAL_DESCRIPTION)

    def test_validate_jd_content_empty_or_missing(self):
        status, reason = GlassdoorJobDescriptionExtractor.validate_jd_content("")
        self.assertEqual(status, JDValidationStatus.MISSING_DESCRIPTION)

    def test_validate_jd_content_invalid_login_stub(self):
        login_stub = "Please log in to continue reading this job description."
        status, reason = GlassdoorJobDescriptionExtractor.validate_jd_content(login_stub)
        self.assertEqual(status, JDValidationStatus.INVALID_CONTENT)

    def test_extract_from_dom_level_1(self):
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = {
            "text": "Detailed responsibilities: 1. Develop UiPath automation pipelines. 2. Integrate REST APIs with enterprise ERP systems. Requirements: 3+ years experience.",
            "selector": "#jobDescriptionText",
            "method": "VISIBLE_DETAIL_DOM",
        }
        res = GlassdoorJobDescriptionExtractor.extract_from_dom(mock_driver)
        self.assertTrue(res.is_usable)
        self.assertEqual(res.status, JDValidationStatus.VALID_DESCRIPTION)
        self.assertIn("UiPath", res.description)
        self.assertGreater(res.character_count, 100)


class TestGlassdoorJobExtractor(unittest.TestCase):
    """Verifies semantic job card extraction, title validation, and normalization contract."""

    def test_title_and_company_validation(self):
        self.assertTrue(validate_title("Senior RPA Developer"))
        self.assertFalse(validate_title("Apply"))
        self.assertFalse(validate_title("Search"))
        self.assertFalse(validate_title("Jobs"))

        self.assertTrue(validate_company("Acme Automation Corp"))
        self.assertFalse(validate_company("Save"))
        self.assertFalse(validate_company("Reviews"))

    def test_extract_valid_job_card(self):
        card = {
            "title": "Automation Anywhere Developer",
            "company": "Tech Solutions Pvt Ltd",
            "location": "Bengaluru, Karnataka (Remote)",
            "link": "https://www.glassdoor.com/job-listing/dev-jl=10109999",
            "jobId": "10109999",
            "isEasyApply": True,
            "salary": "₹8,00,000 - ₹12,00,000 a year",
        }
        job = GlassdoorJobExtractor.extract_from_card_dom(card, search_keyword="RPA Developer")
        self.assertIsNotNone(job)
        self.assertEqual(job.title, "Automation Anywhere Developer")
        self.assertEqual(job.company, "Tech Solutions Pvt Ltd")
        self.assertEqual(job.job_id, "10109999")
        self.assertEqual(job.apply_type, "DIRECT")
        self.assertEqual(job.work_style, "REMOTE")
        self.assertEqual(job.raw_metadata.get("salary_text"), "₹8,00,000 - ₹12,00,000 a year")
        self.assertEqual(job.description, "")  # Never fake placeholder string

    def test_extract_invalid_title_rejected(self):
        card = {
            "title": "Apply",
            "company": "Tech Corp",
            "location": "India",
        }
        job = GlassdoorJobExtractor.extract_from_card_dom(card)
        self.assertIsNone(job)


class TestGlassdoorDiscoveryRunner(unittest.TestCase):
    """Verifies discovery runner artifact persistence and secret redaction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_redact_sensitive_text(self):
        sample = 'login: password="supersecret123" and session_id="abc999" and Bearer eyJhbGciOi'
        cleaned = redact_sensitive_text(sample)
        self.assertNotIn("supersecret123", cleaned)
        self.assertIn("[REDACTED_SECRET]", cleaned)

    def test_discovery_runner_creates_artifacts(self):
        mock_driver = MagicMock()
        mock_driver.current_url = "https://www.glassdoor.com/Job/jobs.htm?sc.keyword=RPA"
        mock_driver.title = "RPA Developer Jobs | Glassdoor"
        mock_driver.page_source = "<html><body><h1>Jobs</h1><ul data-test='job-listing-list'><li>RPA Dev</li></ul></body></html>"
        dom_payload = {
            "headings": [{"tag": "H1", "text": "RPA Jobs"}],
            "buttons": [{"tag": "BUTTON", "text": "Easy Apply only", "visible": True}],
            "inputs": [{"name": "searchBar-jobTitle", "placeholder": "Job Title", "visible": True}],
            "links": [{"text": "Job 1", "href": "https://www.glassdoor.com/job/1"}],
            "iframes": [],
            "visibleText": "RPA Developer TechCorp Bangalore",
            "jobCards": [{
                "candidateIndex": 0,
                "title": "RPA Developer",
                "company": "TechCorp",
                "location": "Bangalore",
                "link": "https://www.glassdoor.com/job/1",
                "jobId": "1001",
                "isEasyApply": True,
            }],
            "jobDetail": {
                "title": "RPA Developer",
                "company": "TechCorp",
                "location": "Bangalore",
                "descriptionLength": 500,
                "descriptionPreview": "UiPath bot design",
                "applyCtaText": "Easy Apply",
                "applicationMethod": "DIRECT_EASY_APPLY",
            },
        }
        mock_driver.execute_script.side_effect = [
            {"width": 1280, "height": 800},
            dom_payload,
        ]

        runner = GlassdoorDiscoveryRunner(browser=mock_driver, base_debug_dir=self.temp_dir)
        report = runner.run_discovery(custom_name="test_run")

        self.assertTrue(os.path.exists(os.path.join(report.artifacts_dir, "page.html")))
        self.assertTrue(os.path.exists(os.path.join(report.artifacts_dir, "discovery.json")))
        self.assertTrue(os.path.exists(os.path.join(report.artifacts_dir, "discovery_report.txt")))
        self.assertEqual(len(report.job_cards), 1)
        self.assertEqual(report.job_cards[0].title, "RPA Developer")


class TestStaleJobRecovery(unittest.TestCase):
    """Verifies that ApplicationTracker safely resets crashed APPLYING jobs on startup."""

    def test_reset_stale_in_flight(self):
        tracker = ApplicationTracker(enable_db=False)
        rec1 = ApplicationRecord(platform="glassdoor", job_id="9991", title="RPA Dev", company="A", location="B", source_url="", status="APPLYING")
        rec2 = ApplicationRecord(platform="glassdoor", job_id="9992", title="RPA Dev", company="A", location="B", source_url="", status="SUBMITTED")
        tracker._records[("glassdoor", "9991")] = rec1
        tracker._records[("glassdoor", "9992")] = rec2

        recovered = tracker.reset_stale_in_flight(platform="glassdoor")
        self.assertEqual(recovered, 1)
        self.assertEqual(rec1.status, "DISCOVERED")
        self.assertEqual(rec2.status, "SUBMITTED")


class TestGlassdoorApplicationDetectorAndForm(unittest.TestCase):
    """Verifies application flow classification and form analyzer."""

    def test_application_detector_easy_apply(self):
        from platforms.glassdoor.application_detector import GlassdoorApplicationDetector, ApplicationMethod
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True
        mock_btn.is_enabled.return_value = True
        mock_btn.text = "Easy Apply"

        def mock_fe(by, sel):
            if "easy" in sel.lower():
                return [mock_btn]
            return []

        mock_driver.find_elements.side_effect = mock_fe

        ctx = GlassdoorApplicationDetector.detect_flow(mock_driver)
        self.assertEqual(ctx.method, ApplicationMethod.DIRECT_PLATFORM_APPLY)
        self.assertTrue(ctx.is_easy_apply)

    def test_form_analyzer_step_classification(self):
        from platforms.glassdoor.form_analyzer import GlassdoorFormAnalyzer, FormStepCategory
        mock_driver = MagicMock()
        mock_driver.execute_script.return_value = {
            "title": "Review your application",
            "errors": [],
            "fields": [
                {"name": "firstName", "label": "First name", "type": "text", "required": True, "value": "Ahmad"},
                {"name": "resumeFile", "label": "Resume", "type": "file", "required": True, "value": ""},
            ],
            "buttons": ["Submit your application"],
            "isReview": True,
            "url": "https://smartapply.indeed.com/review-module",
        }

        res = GlassdoorFormAnalyzer.analyze_step(mock_driver)
        self.assertEqual(res.step_category, FormStepCategory.REVIEW)
        self.assertTrue(res.is_review_step)
        self.assertTrue(res.can_submit)
        self.assertEqual(len(res.fields), 2)
        self.assertEqual(res.fields[0].semantic_name, "first_name")


if __name__ == "__main__":
    unittest.main()

