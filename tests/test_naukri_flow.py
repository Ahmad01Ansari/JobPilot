import unittest
from unittest.mock import MagicMock
from platforms.naukri.applier import NaukriFlowDetector
from platforms.naukri.selectors import (
    QUESTIONNAIRE_MODAL_SELECTORS,
    DIRECT_APPLY_SUCCESS_SELECTORS,
    PROFILE_INCOMPLETE_SELECTORS,
    CAPTCHA_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    MODAL_CLOSE_BUTTONS,
)


class TestNaukriFlowDetector(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.detector = NaukriFlowDetector(self.mock_browser)

    def test_detect_apply_button_type_direct(self):
        btn = MagicMock()
        btn.text = "Apply"
        btn.get_attribute.return_value = ""
        flow = self.detector.detect_apply_button_type(btn)
        self.assertEqual(flow, "DIRECT")

    def test_detect_apply_button_type_external(self):
        btn = MagicMock()
        btn.text = "Apply on Company Site"
        btn.get_attribute.return_value = "Apply on employer website"
        flow = self.detector.detect_apply_button_type(btn)
        self.assertEqual(flow, "EXTERNAL")

    def test_detect_flow_external_new_tab(self):
        self.mock_driver.window_handles = ["win_main", "win_external"]
        self.mock_driver.current_url = "https://careers.company.com/jobs/apply"

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "EXTERNAL")
        self.assertIn("careers.company.com", reason)

    def test_detect_flow_captcha(self):
        self.mock_driver.window_handles = ["win_main"]
        captcha_elem = MagicMock()
        captcha_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS:
                return [captcha_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "CAPTCHA")
        self.assertIn("CAPTCHA", reason)

    def test_detect_flow_questionnaire(self):
        self.mock_driver.window_handles = ["win_main"]
        qna_elem = MagicMock()
        qna_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS or selector in LOGIN_REQUIRED_SELECTORS or selector in PROFILE_INCOMPLETE_SELECTORS:
                return []
            if selector in QUESTIONNAIRE_MODAL_SELECTORS:
                return [qna_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "QUESTIONNAIRE")
        self.assertIn("questionnaire", reason.lower())

    def test_detect_flow_direct_success(self):
        self.mock_driver.window_handles = ["win_main"]
        success_elem = MagicMock()
        success_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if (selector in CAPTCHA_SELECTORS or
                selector in LOGIN_REQUIRED_SELECTORS or
                selector in PROFILE_INCOMPLETE_SELECTORS or
                selector in QUESTIONNAIRE_MODAL_SELECTORS):
                return []
            if selector in DIRECT_APPLY_SUCCESS_SELECTORS:
                return [success_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "DIRECT")

    def test_detect_flow_profile_incomplete(self):
        self.mock_driver.window_handles = ["win_main"]
        incomplete_elem = MagicMock()
        incomplete_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in CAPTCHA_SELECTORS or selector in LOGIN_REQUIRED_SELECTORS:
                return []
            if selector in PROFILE_INCOMPLETE_SELECTORS:
                return [incomplete_elem]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        flow, reason = self.detector.detect_flow_after_click(initial_windows=["win_main"])
        self.assertEqual(flow, "PROFILE_INCOMPLETE")

    def test_close_modal_if_open(self):
        close_btn = MagicMock()
        close_btn.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in MODAL_CLOSE_BUTTONS:
                return [close_btn]
            return []

        self.mock_driver.find_elements.side_effect = find_elements

        res = self.detector.close_modal_if_open()
        self.assertTrue(res)
        close_btn.click.assert_called_once()


class TestNaukriExternalUrlExtraction(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        from platforms.naukri.applier import NaukriApplier
        self.applier = NaukriApplier(
            browser=self.mock_browser,
            form=MagicMock(),
            safety_gate=MagicMock(),
            submitter=MagicMock(),
            tracker=MagicMock(),
        )

    def test_extract_url_from_href(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda attr: "https://careers.google.com/jobs/123" if attr == "href" else None
        btn.find_elements.return_value = []
        url = self.applier._extract_external_apply_url(btn)
        self.assertEqual(url, "https://careers.google.com/jobs/123")

    def test_extract_url_unwraps_tracking_redirect(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda attr: (
            "https://www.naukri.com/external-redirect?url=https%3A%2F%2Fjobs.lever.co%2Facme%2F456"
            if attr == "href" else None
        )
        btn.find_elements.return_value = []
        url = self.applier._extract_external_apply_url(btn)
        self.assertEqual(url, "https://jobs.lever.co/acme/456")

    def test_extract_url_from_onclick(self):
        btn = MagicMock()
        btn.get_attribute.side_effect = lambda attr: (
            "window.open('https://boards.greenhouse.io/corp/jobs/789', '_blank')"
            if attr == "onclick" else None
        )
        btn.find_elements.return_value = []
        url = self.applier._extract_external_apply_url(btn)
        self.assertEqual(url, "https://boards.greenhouse.io/corp/jobs/789")

    def test_extract_url_dynamic_new_tab(self):
        btn = MagicMock()
        btn.get_attribute.return_value = None
        btn.find_elements.return_value = []

        handles_state = [["tab_main"]]
        def get_handles():
            return handles_state[0]

        type(self.mock_driver).window_handles = unittest.mock.PropertyMock(side_effect=get_handles)
        self.mock_driver.current_window_handle = "tab_main"

        def on_click():
            handles_state[0] = ["tab_main", "tab_portal"]
        btn.click.side_effect = on_click

        self.mock_driver.current_url = "https://careers.amazon.jobs/en/jobs/101"

        url = self.applier._extract_external_apply_url(btn, job_url="https://www.naukri.com/job-listings-test")
        self.assertEqual(url, "https://careers.amazon.jobs/en/jobs/101")
        # Ensure external tab was closed and focus switched back
        self.mock_driver.close.assert_called_once()
        self.mock_driver.switch_to.window.assert_called()

    def test_apply_to_job_external_sets_company_portal(self):
        from modules.models import job_from_naukri
        job = job_from_naukri(
            job_id="nk_ext_999",
            title="Senior Automation Engineer",
            company="Alpha Tech",
            location="Bengaluru",
            source_url="https://www.naukri.com/job-listings-alpha-999",
        )

        apply_btn = MagicMock()
        apply_btn.text = "Apply on company site"
        apply_btn.get_attribute.side_effect = lambda attr: "https://careers.alphatech.com/apply" if attr == "href" else None
        apply_btn.find_elements.return_value = []

        self.applier.flow_detector.find_apply_button = MagicMock(return_value=apply_btn)
        self.applier.flow_detector.detect_apply_button_type = MagicMock(return_value="EXTERNAL")

        res = self.applier.apply_to_job(job)
        self.assertEqual(res.get("status"), "EXTERNAL")
        self.assertEqual(job.application_method, "COMPANY_PORTAL")
        self.assertEqual(job.application_url, "https://careers.alphatech.com/apply")
        self.assertNotEqual(job.application_url, job.source_url)


if __name__ == "__main__":
    unittest.main()
