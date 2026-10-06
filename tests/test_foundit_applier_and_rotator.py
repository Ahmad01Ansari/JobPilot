"""
tests/test_foundit_applier_and_rotator.py

Unit tests for Foundit application flow detection, submitter verification,
and search rotation behavior.
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.models import Job, job_from_foundit
from platforms.foundit.applier import FounditFlowDetector, FounditApplier
from platforms.foundit.submitter import FounditSubmitter
from platforms.foundit.rotator import (
    FounditRotationConfig,
    FounditSearchRotator,
    TermStats,
    RotationStats,
)


class TestFounditFlowDetector(unittest.TestCase):
    """Tests for classifying application flow types on Foundit."""

    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.detector = FounditFlowDetector(browser=self.mock_browser)

    def test_detect_captcha(self):
        captcha_elem = MagicMock()
        captcha_elem.is_displayed.return_value = True
        self.mock_driver.find_elements.side_effect = lambda by, sel: [captcha_elem] if "cloudflare" in sel else []

        flow = self.detector.detect_flow()
        self.assertEqual(flow, "CAPTCHA")

    def test_detect_already_applied(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Applied"
        btn.get_attribute.side_effect = lambda attr: ""
        self.mock_driver.find_elements.return_value = []

        flow = self.detector.detect_flow(button_elem=btn)
        self.assertEqual(flow, "ALREADY_APPLIED")

    def test_detect_external(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply on Company Site"
        btn.get_attribute.side_effect = lambda attr: "_blank" if attr == "target" else ""
        self.mock_driver.find_elements.return_value = []

        flow = self.detector.detect_flow(button_elem=btn)
        self.assertEqual(flow, "EXTERNAL")

    def test_detect_direct(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Quick Apply"
        btn.get_attribute.side_effect = lambda attr: ""
        self.mock_driver.find_elements.return_value = []

        flow = self.detector.detect_flow(button_elem=btn)
        self.assertEqual(flow, "DIRECT")

    def test_detect_apply_now_external(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply Now"
        btn.get_attribute.side_effect = lambda attr: ""
        self.mock_driver.find_elements.return_value = []

        flow = self.detector.detect_flow(button_elem=btn)
        self.assertEqual(flow, "EXTERNAL")

    def test_detect_unknown_when_no_button(self):
        self.mock_driver.find_elements.return_value = []
        flow = self.detector.detect_flow(button_elem=None)
        self.assertEqual(flow, "UNKNOWN")


class TestFounditSubmitter(unittest.TestCase):
    """Tests for submitter execution and verification."""

    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.submitter = FounditSubmitter(browser=self.mock_browser)
        self.job = job_from_foundit(
            job_id="999888",
            title="Senior QA Engineer",
            company="Global Tech",
            location="Bengaluru",
        )

    def test_submit_manual_pause(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply Now"
        btn.get_attribute.return_value = ""
        self.submitter.find_apply_button = MagicMock(return_value=btn)

        success, status = self.submitter.submit(self.job, pause_before_submit=True)
        self.assertFalse(success)
        self.assertEqual(status, "MANUAL_REQUIRED")

    def test_submit_success_verified(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply Now"
        btn.get_attribute.return_value = ""
        self.submitter.find_apply_button = MagicMock(return_value=btn)
        self.submitter.verify_submission = MagicMock(return_value=True)

        success, status = self.submitter.submit(self.job, pause_before_submit=False)
        self.assertTrue(success)
        self.assertEqual(status, "SUBMITTED")

    def test_submit_unconfirmed_recorded_as_unknown(self):
        """Idempotency test: unconfirmed submissions after a click MUST be UNKNOWN."""
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply Now"
        btn.get_attribute.return_value = ""
        self.submitter.find_apply_button = MagicMock(return_value=btn)
        self.submitter.verify_submission = MagicMock(return_value=False)

        success, status = self.submitter.submit(self.job, pause_before_submit=False)
        self.assertFalse(success)
        self.assertEqual(status, "UNKNOWN")


class TestFounditApplier(unittest.TestCase):
    """Tests for Applier coordination and deduplication."""

    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_tracker = MagicMock()
        self.applier = FounditApplier(browser=self.mock_browser, tracker=self.mock_tracker)
        self.job = job_from_foundit(
            job_id="12345",
            title="Python Architect",
            company="Innovatech",
            location="Hyderabad",
        )

    def test_skips_when_tracker_indicates_applied(self):
        self.mock_tracker.is_applied.return_value = True
        result = self.applier.apply(self.job)
        self.assertEqual(result["status"], "ALREADY_APPLIED")

    def test_multi_tab_external_site(self):
        self.mock_tracker.is_applied.return_value = False
        self.mock_driver.current_window_handle = "main_win"
        self.mock_driver.window_handles = ["main_win"]
        self.mock_driver.current_url = "https://linkedin.com/jobs/view/9999"

        card = MagicMock()
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Apply Now"
        btn.get_attribute.return_value = ""
        card.find_elements.return_value = [btn]

        def open_tab(*args, **kwargs):
            self.mock_driver.window_handles = ["main_win", "ext_win"]
        self.mock_driver.execute_script.side_effect = open_tab
        btn.click.side_effect = open_tab

        result = self.applier.apply(self.job, card_elem=card)
        self.assertEqual(result["status"], "EXTERNAL")
        self.assertEqual(result["external_url"], "https://linkedin.com/jobs/view/9999")
        self.mock_tracker.record_external.assert_called_once()
        self.mock_driver.switch_to.window.assert_called_with("main_win")

    def test_multi_tab_qualification_failure(self):
        self.mock_tracker.is_applied.return_value = False
        self.mock_driver.current_window_handle = "main_win"
        self.mock_driver.window_handles = ["main_win"]
        self.mock_driver.current_url = "https://www.foundit.in/job/12345"

        mock_qual_engine = MagicMock()
        mock_qual_res = MagicMock()
        mock_qual_res.__bool__.return_value = False
        mock_qual_res.reason = "Excluded keyword: intern"
        mock_qual_engine.qualify_job_post_click.return_value = mock_qual_res

        card = MagicMock()
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Quick Apply"
        btn.get_attribute.return_value = ""
        card.find_elements.return_value = [btn]

        def open_tab(*args, **kwargs):
            self.mock_driver.window_handles = ["main_win", "tab_win"]
        self.mock_driver.execute_script.side_effect = open_tab
        btn.click.side_effect = open_tab

        result = self.applier.apply(self.job, card_elem=card, qualification_engine=mock_qual_engine)
        self.assertEqual(result["status"], "SKIPPED")
        self.assertEqual(result["reason"], "Excluded keyword: intern")
        self.mock_tracker.record_skipped.assert_called_once()
        self.mock_driver.switch_to.window.assert_called_with("main_win")

    def test_multi_tab_native_success(self):
        self.mock_tracker.is_applied.return_value = False
        self.mock_driver.current_window_handle = "main_win"
        self.mock_driver.window_handles = ["main_win"]
        self.mock_driver.current_url = "https://www.foundit.in/job/12345"

        self.applier.submitter.submit = MagicMock(return_value=(True, "SUBMITTED"))

        card = MagicMock()
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Quick Apply"
        btn.get_attribute.return_value = ""
        card.find_elements.return_value = [btn]

        def open_tab(*args, **kwargs):
            self.mock_driver.window_handles = ["main_win", "tab_win"]
        self.mock_driver.execute_script.side_effect = open_tab
        btn.click.side_effect = open_tab

        result = self.applier.apply(self.job, card_elem=card)
        self.assertEqual(result["status"], "SUBMITTED")
        self.mock_tracker.record_submitted.assert_called_once()
        self.mock_driver.switch_to.window.assert_called_with("main_win")

    def test_apply_on_job_page_already_applied(self):
        """Tests apply_on_job_page when job page shows Already Applied (Screenshot 2)."""
        self.mock_tracker.is_applied.return_value = False
        applied_elem = MagicMock()
        applied_elem.is_displayed.return_value = True
        applied_elem.text = "Applied 35 minutes ago"
        self.mock_driver.find_elements.side_effect = lambda by, sel: [applied_elem] if "applied" in sel.lower() or "application status" in sel.lower() else []

        res = self.applier.apply_on_job_page(self.job)
        self.assertEqual(res["status"], "ALREADY_APPLIED")
        self.mock_tracker.record_skipped.assert_called_with(self.job, reason="ALREADY_APPLIED_ON_PORTAL")

    def test_apply_on_job_page_with_questionnaire_success(self):
        """Tests apply_on_job_page opening Screen Questionnaire drawer, answering, and submitting (Screenshot 1 & 3)."""
        self.mock_tracker.is_applied.return_value = False

        apply_btn = MagicMock()
        apply_btn.is_displayed.return_value = True
        apply_btn.text = "⚡ Quick Apply"
        apply_btn.get_attribute.return_value = ""

        # Questionnaire drawer is open after click
        self.applier.form_handler.is_questionnaire_open = MagicMock(return_value=True)
        self.applier.form_handler.fill_all_visible_fields = MagicMock(return_value=(4, 0))
        self.applier.form_handler.submit_questionnaire = MagicMock(return_value=True)
        self.applier.submitter.verify_submission = MagicMock(return_value=True)

        self.mock_driver.find_elements.side_effect = lambda by, sel: (
            [] if "applied" in sel.lower() or "application status" in sel.lower()
            else [apply_btn] if "quick apply" in sel.lower() or "apply" in sel.lower()
            else []
        )

        res = self.applier.apply_on_job_page(self.job)
        self.assertEqual(res["status"], "SUBMITTED")
        self.applier.form_handler.fill_all_visible_fields.assert_called_once()
        self.applier.form_handler.submit_questionnaire.assert_called_once()
        self.mock_tracker.record_submitted.assert_called_once_with(self.job)

    def test_apply_on_job_page_external_apply_now(self):
        """Tests apply_on_job_page with '↗ Apply Now' external employer button (Screenshot 2)."""
        self.mock_tracker.is_applied.return_value = False
        apply_btn = MagicMock()
        apply_btn.is_displayed.return_value = True
        apply_btn.text = "Apply Now"
        apply_btn.get_attribute.side_effect = lambda attr: (
            "https://careers.hollister.com/job/rpa-developer-ii-999" if attr == "href"
            else "_blank" if attr == "target"
            else "<button><span>Apply Now</span><svg></svg></button>" if attr == "outerHTML"
            else ""
        )

        self.mock_driver.find_elements.side_effect = lambda by, sel: (
            [] if "applied" in sel.lower() or "application status" in sel.lower()
            else [apply_btn] if "apply now" in sel.lower() or "apply" in sel.lower()
            else []
        )

        res = self.applier.apply_on_job_page(self.job)
        self.assertEqual(res["status"], "EXTERNAL")
        self.assertEqual(res["external_url"], "https://careers.hollister.com/job/rpa-developer-ii-999")
        self.assertEqual(self.job.application_method, "COMPANY_PORTAL")
        self.assertEqual(self.job.apply_type, "EXTERNAL")
        self.assertEqual(self.job.application_url, "https://careers.hollister.com/job/rpa-developer-ii-999")
        self.mock_tracker.record_external.assert_called_once_with(self.job, external_url="https://careers.hollister.com/job/rpa-developer-ii-999")


class TestFounditFormQuestionnaire(unittest.TestCase):
    """Tests for the Foundit side-drawer Screen Questionnaire (Screenshot 1)."""

    def setUp(self):
        from platforms.foundit.form import FounditForm
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.form = FounditForm(browser=self.mock_browser)

    def test_is_questionnaire_open(self):
        drawer = MagicMock()
        drawer.is_displayed.return_value = True
        self.mock_driver.find_elements.side_effect = lambda by, sel: [drawer] if "screen questionnaire" in sel.lower() else []
        self.assertTrue(self.form.is_questionnaire_open())

    def test_fill_questionnaire_binary_radios(self):
        """Tests answering questions like 'How many years of experience do you have in Java Selenium?' with Yes/No radios."""
        # Questions from Screenshot 1
        q1 = MagicMock()
        q1.text = "Ques 1 How many years of experience do you have in Java Selenium?"
        q2 = MagicMock()
        q2.text = "Ques 2 How many years of experience do you have in API Automation?"

        # Radio options
        r_yes = MagicMock()
        r_yes.get_attribute.return_value = "Yes"
        r_no = MagicMock()
        r_no.get_attribute.return_value = "No"

        block1 = MagicMock()
        block1.find_elements.side_effect = lambda by, sel: [r_yes, r_no] if "@type='radio'" in sel else []
        block1.text = "Ques 1 How many years of experience do you have in Java Selenium?\nYes\nNo"

        block2 = MagicMock()
        block2.find_elements.side_effect = lambda by, sel: [r_yes, r_no] if "@type='radio'" in sel else []
        block2.text = "Ques 2 How many years of experience do you have in API Automation?\nYes\nNo"

        q1.find_element.return_value = block1
        q2.find_element.return_value = block2

        drawer = MagicMock()
        drawer.find_elements.side_effect = lambda by, sel: (
            [q1, q2] if "ques " in sel.lower()
            else []
        )
        self.mock_driver.find_elements.side_effect = lambda by, sel: [drawer] if "screen questionnaire" in sel.lower() else []

        answered, failed = self.form.fill_all_visible_fields()
        self.assertEqual(answered, 2)
        self.assertEqual(failed, 0)

    def test_submit_questionnaire(self):
        btn = MagicMock()
        btn.is_displayed.return_value = True
        btn.text = "Submit"
        self.mock_driver.find_elements.side_effect = lambda by, sel: [btn] if "submit" in sel.lower() else []

        success = self.form.submit_questionnaire()
        self.assertTrue(success)


class TestFounditSearchRotator(unittest.TestCase):
    """Tests for search rotation settings and stop behavior."""

    def test_rotation_config_defaults(self):
        cfg = FounditRotationConfig(
            search_terms=["Python Developer", "Django"],
            max_pages_per_search=2,
            consecutive_skips_limit=15,
        )
        self.assertEqual(len(cfg.search_terms), 2)
        self.assertEqual(cfg.max_pages_per_search, 2)
        self.assertEqual(cfg.consecutive_skips_limit, 15)
        self.assertTrue(cfg.easy_apply_only)

    def test_rotation_config_hybrid_mode(self):
        cfg = FounditRotationConfig(
            apply_mode="ALL",
            easy_apply_only=False,
        )
        self.assertEqual(cfg.apply_mode, "ALL")
        self.assertFalse(cfg.easy_apply_only)

    def test_rotator_stop_check_immediate(self):
        mock_browser = MagicMock()
        mock_browser.driver = MagicMock()
        cfg = FounditRotationConfig(search_terms=["Python"])
        rotator = FounditSearchRotator(
            browser=mock_browser,
            config=cfg,
        )

        result = rotator.run(stop_check=lambda: True)
        self.assertEqual(result["terms_searched"], 0)
        self.assertEqual(result["jobs_applied"], 0)


if __name__ == "__main__":
    unittest.main()
