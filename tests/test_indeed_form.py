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

    def test_answer_screening_questions_numeric_experience_sanitized_to_integer(self):
        # Mock standalone input for numeric experience question
        mock_input = MagicMock()
        mock_input.is_displayed.return_value = True
        mock_input.tag_name = "input"
        mock_input.get_attribute.side_effect = lambda a: "exp_inp" if a == "id" else ("text" if a == "type" else None)

        mock_label = MagicMock()
        mock_label.text = "How many years of RPA Developer experience do you have? *"

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "fieldset":
                return []
            elif by == By.XPATH and "input" in val:
                return [mock_input]
            elif by == By.CSS_SELECTOR and "label[for='exp_inp']" in val:
                return [mock_label]
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        answered = self.form.answer_screening_questions(job_title="RPA Developer", company_name="Gupta Traders")
        self.assertEqual(len(answered), 1)
        # Must be pure integer string without text like '1-4 YEARS' or decimals
        ans_val = answered[0]["answer"]
        self.assertTrue(ans_val.isdigit(), f"Answer '{ans_val}' should be pure digits")
        self.assertEqual(ans_val, "2")
        mock_input.send_keys.assert_called_with("2")

    def test_work_authorization_without_sponsorship_answers_yes(self):
        ans, opt = self.mock_qna.resolve_choice_answer(
            "Are you authorised to work in India without visa sponsorship?",
            available_options=["Yes", "No"]
        )
        self.assertEqual(ans.value, "Yes")
        self.assertEqual(opt, "Yes")

    def test_answer_screening_questions_currency_select_dropdown(self):
        """Verify IndeedForm identifies 'Select currency type *' and dispatches React synthetic events."""
        mock_select = MagicMock()
        mock_select.tag_name = "select"
        mock_select.is_displayed.return_value = True
        mock_select.get_attribute.side_effect = lambda a: "currency_select" if a == "id" else ("select" if a == "type" else None)

        mock_opt0 = MagicMock()
        mock_opt0.text = "Select an option"
        mock_opt1 = MagicMock()
        mock_opt1.text = "INR"
        mock_opt2 = MagicMock()
        mock_opt2.text = "USD"

        # Mock find_elements
        mock_label = MagicMock()
        mock_label.text = "Select currency type *"

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "fieldset":
                return []
            elif by == By.XPATH and ("input" in val or "select" in val):
                return [mock_select]
            elif by == By.CSS_SELECTOR and "label[for='currency_select']" in val:
                return [mock_label]
            elif by == By.TAG_NAME and val == "select":
                return [mock_select]
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        # Mock execute_script for options extraction & selection
        def mock_execute_script(script, *args):
            if "sel.options" in script and "targetText" in script:
                # _select_native_option script
                return "INR"
            elif "sel.options" in script:
                return [
                    {"index": 0, "value": "", "text": "Select an option"},
                    {"index": 1, "value": "INR", "text": "INR"},
                    {"index": 2, "value": "USD", "text": "USD"},
                ]
            elif "selectedIndex <= 0" in script:
                return False
            return None

        self.mock_driver.execute_script.side_effect = mock_execute_script

        with patch("platforms.indeed.form.Select") as mock_select_cls:
            mock_sel_instance = MagicMock()
            mock_sel_instance.options = [mock_opt0, mock_opt1, mock_opt2]
            mock_select_cls.return_value = mock_sel_instance

            answered = self.form.answer_screening_questions(job_title="RPA Developer", company_name="Enterprise Corp")
            self.assertEqual(len(answered), 1)
            self.assertEqual(answered[0]["answer"], "INR")
            self.assertEqual(answered[0]["question"], "Select currency type *")

    def test_select_native_option_dispatches_react_events(self):
        """Verify _select_native_option dispatches input, change, and blur events with React descriptor."""
        mock_select = MagicMock()
        self.mock_driver.execute_script.return_value = "INR"

        res = self.form._select_native_option(mock_select, "INR")
        self.assertEqual(res, "INR")

        self.mock_driver.execute_script.assert_called()
        script = self.mock_driver.execute_script.call_args[0][0]
        self.assertIn("HTMLSelectElement.prototype, 'value'", script)
        self.assertIn("dispatchEvent(new Event('change', { bubbles: true }))", script)
        self.assertIn("dispatchEvent(new Event('input', { bubbles: true }))", script)

    def test_resolve_safe_option_currency_matching(self):
        """Verify _resolve_safe_option matches currency options even with varied labels."""
        options = ["Select an option", "INR", "USD", "EUR"]
        res = self.form._resolve_safe_option("Select currency type *", options, "INR", "INR")
        self.assertEqual(res, "INR")

        # Even with generic label, detect currency from options pool
        res2 = self.form._resolve_safe_option("Choose", options, "", None)
        self.assertEqual(res2, "INR")

    def test_resolve_safe_option_hearing_source(self):
        """Verify _resolve_safe_option picks valid hearing source from options."""
        options = ["Select an option", "Internet Search", "Company Website", "Career Fair", "Other"]
        res = self.form._resolve_safe_option("How did you hear about Smart Data Solutions? *", options, "", None)
        self.assertIn(res, ["Internet Search", "Company Website", "Other"])
        self.assertNotEqual(res, "Select an option")

    def test_auto_heal_invalid_step_fields_repairs_unselected_dropdown(self):
        """Verify _auto_heal_invalid_step_fields scans DOM and repairs unselected dropdowns."""
        mock_sel = MagicMock()

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "select":
                return [mock_sel]
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        # Mock execute_script return values for self-healing passes
        def mock_execute_script(script, *args):
            if "selects.map" in script:
                return [{
                    "index": 0,
                    "isUnselected": True,
                    "name": "hearing_source",
                    "id": "hearing_source",
                    "ariaLabel": "How did you hear about Smart Data Solutions? *",
                    "options": ["Internet Search", "Company Website", "Other"]
                }]
            elif "sel.options" in script and "targetText" in script:
                return "Internet Search"
            elif "radios.map" in script or "input[type=\"radio\"]" in script:
                return []
            return None

        self.mock_driver.execute_script.side_effect = mock_execute_script

        healed = self.form._auto_heal_invalid_step_fields()
        self.assertGreaterEqual(healed, 1)

    def test_custom_combobox_currency_selection(self):
        """Verify _select_custom_combobox_option matches INR currency and handles pointer events."""
        mock_btn = MagicMock()
        mock_btn.tag_name = "button"
        mock_btn.get_attribute.side_effect = lambda a: "combobox" if a == "role" else None

        def mock_exec(script, *args):
            if "targetText" in script and "qContext" in script:
                return "India Rupee (INR)"
            elif "innerText" in script:
                return "India Rupee (INR)"
            return None

        self.mock_driver.execute_script.side_effect = mock_exec

        chosen = self.form._select_custom_combobox_option(mock_btn, "INR", question_context="Select currency type *")
        self.assertEqual(chosen, "India Rupee (INR)")

    def test_auto_heal_skips_already_filled_inputs(self):
        """Verify self-healer preserves existing user text and does not overwrite filled fields."""
        mock_inp_filled = MagicMock()
        mock_inp_filled.get_attribute.side_effect = lambda a: "550000" if a == "value" else None

        mock_inp_empty = MagicMock()
        mock_inp_empty.get_attribute.side_effect = lambda a: "" if a == "value" else None

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "select":
                return []
            elif by == By.XPATH and val.startswith("//input"):
                return [mock_inp_filled, mock_inp_empty]
            elif by == By.XPATH and "button" in val:
                return []
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        def mock_exec(script, *args):
            if "selects.map" in script or "input[type=\"radio\"]" in script:
                return []
            elif "closest('div, fieldset')" in script:
                return "Salary Expectation"
            return None

        self.mock_driver.execute_script.side_effect = mock_exec

        healed = self.form._auto_heal_invalid_step_fields()
        self.assertEqual(healed, 1)
        # Empty input received fill, filled input was preserved
        mock_inp_empty.send_keys.assert_called()
        mock_inp_filled.send_keys.assert_not_called()

    def test_custom_combobox_referral_selection(self):
        """Verify _select_custom_combobox_option matches Indeed referral source."""
        mock_btn = MagicMock()
        mock_btn.tag_name = "button"
        mock_btn.get_attribute.side_effect = lambda a: "combobox" if a == "role" else None

        def mock_exec(script, *args):
            if "targetText" in script and "qContext" in script:
                return "Indeed"
            elif "innerText" in script:
                return "Indeed"
            return None

        self.mock_driver.execute_script.side_effect = mock_exec

        chosen = self.form._select_custom_combobox_option(
            mock_btn, "Indeed", question_context="How did you hear about Smart Data Solutions? *"
        )
        self.assertEqual(chosen, "Indeed")

    def test_auto_heal_error_flagged_dropdown(self):
        """Verify self-healer Pass 0 locates 'Choose an option to continue' container and heals dropdown."""
        mock_container = MagicMock()
        mock_select = MagicMock()
        mock_select.tag_name = "select"

        def mock_driver_find_elements(by, val):
            if by == By.TAG_NAME and val == "select":
                return [mock_select]
            return []

        self.mock_driver.find_elements.side_effect = mock_driver_find_elements

        def mock_exec(script, *args):
            if "choose an option to continue" in script:
                return [mock_container]
            elif "querySelector('select')" in script:
                return mock_select
            elif "sel.options" in script:
                return ["INR", "USD"]
            elif "aria-labelledby" in script or "closest('div, fieldset')" in script:
                return "Select currency type *"
            elif "selects.map" in script or "input[type=\"radio\"]" in script:
                return []
            return None

        self.mock_driver.execute_script.side_effect = mock_exec

        with patch.object(self.form, "_select_native_option", return_value="INR") as mock_sel_native:
            healed = self.form._auto_heal_invalid_step_fields()
            self.assertGreaterEqual(healed, 1)
            mock_sel_native.assert_called()

    def test_auto_heal_error_flagged_combobox_referral(self):
        """Verify Pass 0 auto-heals 'How did you hear about Smart Data Solutions' dropdown button."""
        mock_combo_btn = MagicMock()
        mock_combo_btn.tag_name = "button"

        def mock_exec(script, *args):
            if "choose an option to continue" in script:
                return [mock_combo_btn]
            elif "matches('button" in script or "querySelector('button" in script:
                return mock_combo_btn
            elif "aria-labelledby" in script or "closest('div, fieldset')" in script:
                return "How did you hear about Smart Data Solutions? *"
            elif "selects.map" in script or "input[type=\"radio\"]" in script:
                return []
            return None

        self.mock_driver.execute_script.side_effect = mock_exec

        with patch.object(self.form, "_select_custom_combobox_option", return_value="Indeed") as mock_sel_combo:
            healed = self.form._auto_heal_invalid_step_fields()
            self.assertGreaterEqual(healed, 1)
            mock_sel_combo.assert_called_once()
            args, kwargs = mock_sel_combo.call_args
            self.assertEqual(args[0], mock_combo_btn)
            self.assertEqual(args[1], "Indeed")
            self.assertIn("Smart Data Solutions", kwargs.get("question_context", ""))


if __name__ == "__main__":
    unittest.main()
