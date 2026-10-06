'''
Unit Tests for Indeed Applier
Tests details extraction (description, salary, experience, work style) and cooperative pause/stop handling.
'''

import unittest
from unittest.mock import MagicMock
from selenium.webdriver.common.by import By

from platforms.indeed.applier import IndeedApplier
from platforms.indeed.search import IndeedJobItem


class TestIndeedApplier(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_tracker = MagicMock()
        self.mock_bridge = MagicMock()
        self.applier = IndeedApplier(
            browser=self.mock_browser,
            tracker=self.mock_tracker,
            automation_bridge=self.mock_bridge,
        )

    def test_extract_job_details_populates_all_fields(self):
        job = IndeedJobItem(
            job_id="63b4cb6c23855705",
            title="RPA - Ui Path Developer",
            company="Step One Step Ahead LLP",
            location="Mumbai, Maharashtra",
        )

        mock_desc_el = MagicMock()
        mock_desc_el.text = (
            "Job Title: RPA Developer (UiPath)\n"
            "Location: Andheri, Chinchpokli, Thane (On-site – Work from Office Mandatory)\n"
            "Experience: 1–4 Years\n"
            "Job Type: Full-Time\n"
            "Job Description :\n"
            "We are seeking a skilled RPA Developer (UiPath) with hands-on experience in designing, developing, and implementing automation solutions."
        )

        mock_details_el = MagicMock()
        mock_details_el.text = "Pay\n₹4,00,000 - ₹8,00,000 a year\nJob type\nFull-time"

        mock_sal_el = MagicMock()
        mock_sal_el.text = "₹4,00,000 - ₹8,00,000 a year"

        def mock_find_elements(by, sel):
            if by == By.CSS_SELECTOR:
                if "#jobDescriptionText" in sel or "JobDescription" in sel:
                    return [mock_desc_el]
                elif "#jobDetailsSection" in sel or "#salaryInfoAndJobType" in sel:
                    return [mock_details_el]
                elif "Pay" in sel or "salary" in sel.lower() or "css-19j1a75" in sel:
                    return [mock_sal_el]
            return []

        self.mock_driver.find_elements.side_effect = mock_find_elements

        extracted = self.applier.extract_job_details(job)

        # Assert JD extracted
        self.assertIn("We are seeking a skilled RPA Developer", job.description)
        self.assertEqual(extracted.get("description"), job.description)

        # Assert Salary extracted & parsed
        self.assertEqual(job.salary, "₹4,00,000 - ₹8,00,000 a year")
        self.assertEqual(job.salary_min, 400000)
        self.assertEqual(job.salary_max, 800000)
        self.assertEqual(extracted.get("salary_min"), 400000)
        self.assertEqual(extracted.get("salary_max"), 800000)

        # Assert Experience extracted
        self.assertEqual(job.experience_text, "1-4 Years")
        self.assertEqual(job.required_experience_min, 1)
        self.assertEqual(job.required_experience_max, 4)
        self.assertEqual(extracted.get("experience_text"), "1-4 Years")

        # Assert Work Style extracted
        self.assertEqual(job.work_style, "On-site")

        # Assert tracker was notified
        self.mock_tracker.record_state.assert_called()

        # Assert automation bridge was notified
        self.mock_bridge.handle_job_discovered.assert_called_once()
        evt = self.mock_bridge.handle_job_discovered.call_args[0][0]
        self.assertEqual(evt.salary_text, "₹4,00,000 - ₹8,00,000 a year")
        self.assertEqual(evt.experience_text, "1-4 Years")
        self.assertEqual(evt.salary_min, 400000)
        self.assertEqual(evt.salary_max, 800000)
        self.assertEqual(evt.required_experience_min, 1)
        self.assertEqual(evt.required_experience_max, 4)
        self.assertEqual(evt.work_style, "On-site")

    def test_apply_to_job_respects_stop_and_pause_check(self):
        job = IndeedJobItem(
            job_id="63b4cb6c23855705",
            title="RPA Developer",
            company="Test Corp",
            location="India",
        )
        success, reason = self.applier.apply_to_job(
            job=job,
            main_window="main_handle",
            stop_check=lambda: True,
        )
        self.assertFalse(success)
        self.assertIn("paused or stopped", reason.lower())

    def test_external_flow_extracts_portal_url(self):
        from platforms.indeed.applier import extract_external_portal_url

        # Direct external link on apply button
        mock_apply_el = MagicMock()
        mock_apply_el.get_attribute.side_effect = lambda a: "https://flex.wd1.myworkdayjobs.com/careers/job123" if a == "href" else None
        url = extract_external_portal_url(self.mock_driver, mock_apply_el, "d47945a0c03d6ea5")
        self.assertEqual(url, "https://flex.wd1.myworkdayjobs.com/careers/job123")

        # Fallback to applystart redirect
        url_fallback = extract_external_portal_url(self.mock_driver, None, "d47945a0c03d6ea5")
        self.assertEqual(url_fallback, "https://in.indeed.com/applystart?jk=d47945a0c03d6ea5")

    def test_extract_job_details_via_full_job_description_heading(self):
        job = IndeedJobItem(
            job_id="e12927c8a1c321b6",
            title="Jr. RPA Developer",
            company="RPASoft",
            location="Bengaluru, Karnataka",
        )

        # Mock JS execution returning text under "Full job description"
        expected_jd = (
            "We have 2 Positions open for 1-2 Years experience as Jr. RPA Developer in Bengaluru. "
            "The candidate must know UiPath and Blue Prism process automation frameworks. "
            "Key responsibilities include workflow design, test bot deployment, log monitoring, and collaborating with cross-functional software teams to automate repetitive tasks."
        )
        self.mock_driver.execute_script.return_value = expected_jd

        extracted = self.applier.extract_job_details(job)
        self.assertEqual(job.description, expected_jd)
        self.assertEqual(extracted.get("description"), expected_jd)

    def test_multilevel_jd_extraction_escalates_to_level2(self):
        from platforms.indeed.applier import is_valid_job_description

        self.assertFalse(is_valid_job_description(""))
        self.assertFalse(is_valid_job_description("Short stub under 250 characters."))
        self.assertFalse(is_valid_job_description("Please enable cookies to view job description"))
        self.assertTrue(is_valid_job_description(
            "We are seeking an experienced Senior RPA Developer skilled in UiPath, Python, and SQL for our enterprise automation team. "
            "Primary responsibilities include bot architecture, process modeling, orchestration, error handling, and cross-system API integration. "
            "Candidates should have strong analytical problem-solving skills and experience with scalable cloud deployments."
        ))

        job = IndeedJobItem(
            job_id="test_escalate_123",
            title="Senior RPA Developer",
            company="Global Tech",
            location="Bengaluru",
        )

        # Mock Level 1 to return empty, and Level 2 to return rich JD
        self.applier._extract_jd_level1_inpage = MagicMock(return_value="")
        level2_desc = (
            "Detailed Job Description:\n"
            "Key Responsibilities:\n"
            "- Design and implement robust UiPath robotic process automations for critical workflows.\n"
            "- Monitor automated pipelines and diagnose orchestrator logs across enterprise environments.\n"
            "Requirements:\n"
            "- 3+ years in RPA development with advanced Python scripting proficiency and API integration skills."
        )
        self.applier._extract_jd_level2_viewjob_tab = MagicMock(return_value=(level2_desc, {"salary": "₹12,00,000 - ₹18,00,000 a year"}))

        extracted = self.applier.extract_job_details(job)

        self.applier._extract_jd_level1_inpage.assert_called_once()
        self.applier._extract_jd_level2_viewjob_tab.assert_called_once_with("test_escalate_123")
        self.assertEqual(job.description, level2_desc)
        self.assertEqual(extracted.get("description"), level2_desc)
        self.assertEqual(job.salary, "₹12,00,000 - ₹18,00,000 a year")

    def test_applier_skips_blacklisted_description_bad_words(self):
        self.applier.bad_words = ["US Citizen Only", "Security Clearance"]
        job = IndeedJobItem(
            job_id="test_bad_word_job",
            title="Senior Automation Developer",
            company="Defense Corp",
            location="Remote",
        )

        rich_desc_with_bad_word = (
            "Job Title: Senior Automation Developer at Defense Corp.\n"
            "We are developing enterprise automation workflows using Python and Selenium.\n"
            "Requirements:\n"
            "- Must be US Citizen Only with active polygraph verification.\n"
            "- 5+ years experience in automation testing and scripting frameworks across Unix environments."
        )

        self.applier.extract_job_details = MagicMock(return_value={"description": rich_desc_with_bad_word})
        job.description = rich_desc_with_bad_word

        success, message = self.applier.apply_to_job(job, main_window="main_win")
        self.assertFalse(success)
        self.assertIn("blacklisted phrase", message)
        self.assertIn("US Citizen Only", message)


if __name__ == "__main__":
    unittest.main()
