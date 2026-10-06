'''
Unit Tests for NaukriForm (Phase 10: Form Interaction Engine)
Validates field discovery, question identification, answer resolution with provenance,
input filling with JS fallbacks, radio/dropdown matching, and hard stop before final submit.
'''

import unittest
from unittest.mock import MagicMock, patch
from selenium.webdriver.common.by import By

from platforms.naukri.form import NaukriForm, FormField
from modules.qna_engine import QnAEngine, Answer


class TestNaukriForm(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_browser.driver = self.mock_driver
        self.qna_engine = QnAEngine()
        self.form = NaukriForm(
            browser=self.mock_browser,
            qna_engine=self.qna_engine,
            resume_path="/dummy/resume.pdf",
        )

    # 1. Question Identification Tests
    def test_identify_question_via_label_for(self):
        elem = MagicMock()
        elem.get_attribute.side_effect = lambda attr: "test_input_id" if attr == "id" else None

        label_elem = MagicMock()
        label_elem.text = "  * Total Years of Experience: "

        self.mock_driver.find_elements.side_effect = lambda by, sel: (
            [label_elem] if "test_input_id" in sel else []
        )

        label = self.form.identify_question(elem)
        self.assertEqual(label, "Total Years of Experience")

    def test_identify_question_via_aria_label_or_placeholder(self):
        elem = MagicMock()
        elem.get_attribute.side_effect = lambda attr: {
            "id": None,
            "aria-label": "Enter your Current CTC (in Lacs)",
            "placeholder": "e.g. 5.5",
        }.get(attr)
        elem.find_element.side_effect = Exception("No parent")

        label = self.form.identify_question(elem)
        self.assertEqual(label, "Enter your Current CTC (in Lacs)")

    def test_identify_question_via_parent_block(self):
        elem = MagicMock()
        elem.get_attribute.return_value = None

        parent_block = MagicMock()
        prompt_elem = MagicMock()
        prompt_elem.text = "What is your notice period in days?*"
        parent_block.find_elements.return_value = [prompt_elem]

        label = self.form.identify_question(elem, parent_block=parent_block)
        self.assertEqual(label, "What is your notice period in days")

    # 2. Field Discovery Tests
    def test_discover_fields_all_types(self):
        # Setup mock container with various field types
        container = MagicMock()

        # Text input
        inp_text = MagicMock()
        inp_text.is_displayed.return_value = True
        inp_text.get_attribute.side_effect = lambda attr: "text" if attr == "type" else "Current City" if attr == "name" else None

        # Number input
        inp_num = MagicMock()
        inp_num.is_displayed.return_value = True
        inp_num.get_attribute.side_effect = lambda attr: "number" if attr == "type" else "Notice Period" if attr == "name" else None

        # Textarea
        txt_area = MagicMock()
        txt_area.is_displayed.return_value = True
        txt_area.get_attribute.side_effect = lambda attr: "Cover Letter" if attr == "name" else None

        # Radio buttons
        r1 = MagicMock()
        r1.is_displayed.return_value = True
        r1.get_attribute.side_effect = lambda attr: "radio_gender" if attr == "name" else "Yes" if attr == "value" else None
        r1.text = "Yes"

        r2 = MagicMock()
        r2.is_displayed.return_value = True
        r2.get_attribute.side_effect = lambda attr: "radio_gender" if attr == "name" else "No" if attr == "value" else None
        r2.text = "No"

        # Checkbox
        cb = MagicMock()
        cb.is_displayed.return_value = True
        cb.get_attribute.side_effect = lambda attr: "checkbox" if attr == "type" else "terms" if attr == "name" else None
        cb.text = "I agree to terms"

        # Select
        sel_elem = MagicMock()
        sel_elem.is_displayed.return_value = True
        sel_elem.tag_name = "select"
        sel_elem.get_attribute.side_effect = lambda attr: "relocate" if attr == "name" else None
        opt1 = MagicMock()
        opt1.text = "Yes"
        opt2 = MagicMock()
        opt2.text = "No"
        sel_elem.find_elements.return_value = [opt1, opt2]

        # File upload
        file_elem = MagicMock()
        file_elem.get_attribute.side_effect = lambda attr: "file" if attr == "type" else None

        def find_elements(by, selector):
            if "file" in selector:
                return [file_elem]
            elif "textarea" in selector:
                return [txt_area]
            elif "radio" in selector or "chip" in selector:
                return [r1, r2]
            elif "checkbox" in selector:
                return [cb]
            elif "select" in selector:
                return [sel_elem]
            elif "text" in selector or "number" in selector:
                return [inp_text, inp_num]
            return []

        container.find_elements.side_effect = find_elements

        fields = self.form.discover_fields(container=container)
        types = [f.field_type for f in fields]

        self.assertIn("file", types)
        self.assertIn("textarea", types)
        self.assertIn("radio", types)
        self.assertIn("checkbox", types)
        self.assertIn("select", types)
        self.assertIn("text", types)
        self.assertIn("number", types)

    # 3. Answering & Provenance Tests
    def test_answer_resolution_provenance(self):
        # Text field: notice period
        f_notice = FormField(
            field_type="text",
            label="What is your notice period?",
            element=MagicMock(),
        )
        ans_notice = self.form.answer(f_notice)
        self.assertTrue(ans_notice.validated)
        self.assertIn(ans_notice.source, ["profile", "calculation", "rule"])
        self.assertIn("30", str(ans_notice.value))

        # Radio field: relocation
        f_reloc = FormField(
            field_type="radio",
            label="Are you willing to relocate?",
            element=MagicMock(),
            options=["Yes", "No"],
            raw_elements=[MagicMock(), MagicMock()],
        )
        ans_reloc = self.form.answer(f_reloc)
        self.assertTrue(ans_reloc.validated)
        self.assertEqual(ans_reloc.value, "Yes")

        # File field
        f_file = FormField(
            field_type="file",
            label="Resume Upload",
            element=MagicMock(),
        )
        ans_file = self.form.answer(f_file)
        self.assertEqual(ans_file.value, "/dummy/resume.pdf")
        self.assertEqual(ans_file.source, "profile")

    # 4. Fill Field Tests
    def test_fill_text_field(self):
        elem = MagicMock()
        f = FormField(field_type="text", label="City", element=elem)
        ans = Answer(value="New Delhi", source="profile", confidence=1.0)

        success = self.form.fill_field(f, ans)
        self.assertTrue(success)
        elem.clear.assert_called()
        elem.send_keys.assert_called_with("New Delhi")

    def test_fill_text_field_js_fallback(self):
        elem = MagicMock()
        elem.send_keys.side_effect = Exception("ElementNotInteractable")
        f = FormField(field_type="text", label="City", element=elem)
        ans = Answer(value="New Delhi", source="profile", confidence=1.0)

        success = self.form.fill_field(f, ans)
        self.assertTrue(success)
        self.mock_driver.execute_script.assert_called()

    def test_fill_radio_field(self):
        r_yes = MagicMock()
        r_no = MagicMock()
        f = FormField(
            field_type="radio",
            label="Do you have work authorization?",
            element=r_yes,
            options=["Yes", "No"],
            raw_elements=[r_yes, r_no],
        )
        ans = Answer(value="Yes", source="rule", confidence=0.95)

        success = self.form.fill_field(f, ans)
        self.assertTrue(success)
        r_yes.click.assert_called_once()
        r_no.click.assert_not_called()

    def test_fill_checkbox_field(self):
        cb = MagicMock()
        cb.is_selected.return_value = False
        f = FormField(
            field_type="checkbox",
            label="I agree to terms and conditions",
            element=cb,
            options=["I agree to terms and conditions"],
            raw_elements=[cb],
        )
        ans = Answer(value="Yes", source="rule", confidence=1.0)

        success = self.form.fill_field(f, ans)
        self.assertTrue(success)
        cb.click.assert_called_once()

    # 5. Button Classification Tests
    def test_is_final_submit_classification(self):
        btn_next = MagicMock()
        btn_next.text = "Next"
        btn_next.get_attribute.return_value = ""
        self.assertFalse(self.form.is_final_submit(btn_next))

        btn_continue = MagicMock()
        btn_continue.text = "Save and Continue"
        btn_continue.get_attribute.return_value = ""
        self.assertFalse(self.form.is_final_submit(btn_continue))

        btn_submit = MagicMock()
        btn_submit.text = "Submit Application"
        btn_submit.get_attribute.return_value = "submit"
        self.assertTrue(self.form.is_final_submit(btn_submit))

        btn_apply = MagicMock()
        btn_apply.text = "Apply"
        btn_apply.get_attribute.return_value = ""
        self.assertTrue(self.form.is_final_submit(btn_apply))

    # 6. Safety Gate: Hard Stop at Final Submit
    def test_next_stops_at_final_submit_without_clicking(self):
        submit_btn = MagicMock()
        submit_btn.text = "Submit"
        submit_btn.is_displayed.return_value = True
        submit_btn.is_enabled.return_value = True
        submit_btn.get_attribute.return_value = "submit"

        self.form.find_action_button = MagicMock(return_value=(submit_btn, True))

        advanced, reason = self.form.next()
        self.assertFalse(advanced)
        self.assertEqual(reason, "STOPPED_AT_SUBMIT")
        # Ensure submit button was NEVER clicked!
        submit_btn.click.assert_not_called()
        self.mock_driver.execute_script.assert_not_called()

    def test_next_advances_on_intermediate_button(self):
        next_btn = MagicMock()
        next_btn.text = "Next"
        next_btn.is_displayed.return_value = True
        next_btn.is_enabled.return_value = True
        next_btn.get_attribute.return_value = ""

        self.form.find_action_button = MagicMock(return_value=(next_btn, False))

        advanced, reason = self.form.next()
        self.assertTrue(advanced)
        self.assertEqual(reason, "NAVIGATED_NEXT")
        next_btn.click.assert_called_once()

    # 7. Full Form Filling Flow Test
    def test_fill_form_halts_at_submit(self):
        f1 = FormField(field_type="text", label="Years of Experience", element=MagicMock())
        self.form.discover_fields = MagicMock(side_effect=[[f1], []])
        self.form.next = MagicMock(return_value=(False, "STOPPED_AT_SUBMIT"))

        result = self.form.fill_form()
        self.assertEqual(result["status"], "READY_TO_SUBMIT")
        self.assertEqual(len(result["filled_fields"]), 1)
        self.assertEqual(result["filled_fields"][0]["field"], "Years of Experience")


if __name__ == "__main__":
    unittest.main()
