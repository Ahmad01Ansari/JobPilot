import unittest
from unittest.mock import MagicMock, patch
from selenium.webdriver.common.by import By

from platforms.indeed.form import IndeedForm
from modules.qna_engine import QnAEngine, Answer


class TestIndeedForm(unittest.TestCase):
    def setUp(self):
        self.mock_driver = MagicMock()
        self.mock_browser = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.mock_qna = QnAEngine()
        self.form = IndeedForm(self.mock_browser, qna_engine=self.mock_qna)

    def test_answer_screening_questions_handles_relatives_and_worked_before_radios(self):
        # Create a mock fieldset for "Are you related to anyone who currently works for MoneyGram?"
        mock_fs = MagicMock()
        mock_fs.is_displayed.return_value = True

        mock_legend = MagicMock()
        mock_legend.text = "Are you related to anyone who currently works for MoneyGram? If yes, who and how are you related? *"

        mock_radio_yes = MagicMock()
        mock_radio_yes.get_attribute.side_effect = lambda a: "opt_yes" if a == "id" else ("Yes" if a == "value" else None)
        mock_radio_no = MagicMock()
        mock_radio_no.get_attribute.side_effect = lambda a: "opt_no" if a == "id" else ("No" if a == "value" else None)

        def mock_fs_find_elements(by, val):
            if by == By.XPATH and ".//legend" in val:
                return [mock_legend]
            elif by == By.XPATH and "type='radio'" in val:
                return [mock_radio_yes, mock_radio_no]
            return []

        mock_fs.find_elements.side_effect = mock_fs_find_elements

        # Mock driver find_elements
        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "fieldset":
                return [mock_fs]
            elif by == By.CSS_SELECTOR and "label[for='opt_yes']" in val:
                lbl = MagicMock()
                lbl.text = "Yes"
                return [lbl]
            elif by == By.CSS_SELECTOR and "label[for='opt_no']" in val:
                lbl = MagicMock()
                lbl.text = "No"
                return [lbl]
            elif by == By.XPATH and "input" in val:
                return []
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        answered = self.form.answer_screening_questions(job_title="RPA Developer", company_name="MoneyGram")
        self.assertEqual(len(answered), 1)
        self.assertEqual(answered[0]["answer"], "No")
        # Ensure driver execute_script was called to click the "No" radio
        self.mock_driver.execute_script.assert_called()

    def test_answer_screening_questions_handles_salary_expectation_input(self):
        # Mock standalone text input for salary expectations
        mock_input = MagicMock()
        mock_input.is_displayed.return_value = True
        mock_input.tag_name = "input"
        mock_input.get_attribute.side_effect = lambda a: "salary_inp" if a == "id" else ("text" if a == "type" else None)

        mock_label = MagicMock()
        mock_label.text = "What are your annual salary expectations in local currency for this position? *"

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "fieldset":
                return []
            elif by == By.XPATH and "input" in val:
                return [mock_input]
            elif by == By.CSS_SELECTOR and "label[for='salary_inp']" in val:
                return [mock_label]
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        answered = self.form.answer_screening_questions(job_title="RPA Developer", company_name="MoneyGram")
        self.assertEqual(len(answered), 1)
        # Should populate numeric annual compensation from candidate profile (default 550000)
        self.assertEqual(answered[0]["answer"], "550000")
        mock_input.send_keys.assert_called_with("550000")


if __name__ == "__main__":
    unittest.main()
