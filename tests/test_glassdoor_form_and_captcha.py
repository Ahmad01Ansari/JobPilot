'''
Unit Tests for Glassdoor Form, Submitter, and CAPTCHA Handler (Phases H, I, J)
Validates multi-step form progression, resume upload, submission confirmation verification,
and anti-bot CAPTCHA handling.
'''

import unittest
from unittest.mock import MagicMock, patch

from platforms.glassdoor.form import GlassdoorForm
from platforms.glassdoor.submitter import GlassdoorSubmitter
from platforms.glassdoor.captcha_handler import GlassdoorCaptchaHandler


class TestGlassdoorFormAndCaptcha(unittest.TestCase):
    def test_form_is_open(self):
        mock_driver = MagicMock()
        mock_modal = MagicMock()
        mock_modal.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_modal]

        browser = MagicMock()
        browser.driver = mock_driver

        form = GlassdoorForm(browser=browser)
        self.assertTrue(form.is_form_open())

    @patch("platforms.glassdoor.form.get_personal")
    def test_form_fill_personal_info(self, mock_get_personal):
        mock_get_personal.return_value = {
            "first_name": "Ahmad",
            "last_name": "Ansari",
            "email": "ahmad@example.com",
            "phone_number": "+919876543210",
            "current_city": "Delhi",
        }

        mock_driver = MagicMock()
        mock_input = MagicMock()
        mock_input.is_displayed.return_value = True
        mock_input.get_attribute.return_value = ""  # empty
        mock_driver.find_element.return_value = mock_input

        browser = MagicMock()
        browser.driver = mock_driver

        form = GlassdoorForm(browser=browser)
        form.fill_personal_info()

        # Should find input and type
        self.assertTrue(mock_driver.find_element.called)

    @patch("platforms.glassdoor.form.get_resume")
    def test_upload_resume_if_needed(self, mock_get_resume):
        mock_get_resume.return_value = "/tmp/fake_resume.pdf"

        mock_driver = MagicMock()
        mock_file_input = MagicMock()
        mock_driver.find_elements.return_value = [mock_file_input]

        browser = MagicMock()
        browser.driver = mock_driver

        form = GlassdoorForm(browser=browser)
        uploaded = form.upload_resume_if_needed()

        self.assertTrue(uploaded)
        mock_file_input.send_keys.assert_called_once_with("/tmp/fake_resume.pdf")

    def test_submitter_pause_before_submit(self):
        browser = MagicMock()
        submitter = GlassdoorSubmitter(browser=browser, pause_before_submit=True)
        # Should return False and pause without clicking
        result = submitter.submit_application()
        self.assertFalse(result)

    def test_submitter_successful_confirmation(self):
        mock_driver = MagicMock()
        mock_submit_btn = MagicMock()
        mock_submit_btn.is_displayed.return_value = True
        mock_submit_btn.is_enabled.return_value = True

        mock_success_banner = MagicMock()
        mock_success_banner.is_displayed.return_value = True

        # First find submit button, then find success banner
        def find_elements_side_effect(by, sel):
            if "submit" in sel.lower() or "Submit" in sel:
                return [mock_submit_btn]
            if "success" in sel or "submitted" in sel.lower():
                return [mock_success_banner]
            return []

        mock_driver.find_elements.side_effect = find_elements_side_effect

        browser = MagicMock()
        browser.driver = mock_driver

        submitter = GlassdoorSubmitter(browser=browser, pause_before_submit=False)
        result = submitter.submit_application()

        self.assertTrue(result)
        mock_submit_btn.click.assert_called_once()

    def test_captcha_handler_visible_challenge_detected(self):
        mock_driver = MagicMock()
        mock_iframe = MagicMock()
        mock_iframe.is_displayed.return_value = True
        mock_iframe.rect = {"width": 300, "height": 300}
        mock_driver.find_elements.return_value = [mock_iframe]

        browser = MagicMock()
        browser.driver = mock_driver

        handler = GlassdoorCaptchaHandler(browser=browser)
        self.assertTrue(handler.is_captcha_present(mock_driver))

    def test_captcha_handler_no_challenge(self):
        mock_driver = MagicMock()
        mock_driver.find_elements.return_value = []

        browser = MagicMock()
        browser.driver = mock_driver

        handler = GlassdoorCaptchaHandler(browser=browser)
        self.assertFalse(handler.is_captcha_present(mock_driver))


if __name__ == "__main__":
    unittest.main()
