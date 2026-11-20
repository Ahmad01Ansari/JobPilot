import unittest
from modules.qna_engine import QnAEngine

class TestLinkedInFormValidation(unittest.TestCase):
    def setUp(self):
        self.engine = QnAEngine()
        self.engine.personal["current_city"] = "Delhi"
        self.engine.prof.update({
            "skills": ["Automation Anywhere 360", "Python 3.11", "SAP GUI Scripting", "SQL"],
        })
        self.engine.standard_answers.update({
            "certifications": "Automation Anywhere Advanced Automation, Agentic Process Automation Developer Masterclass",
            "reason_for_change": "Seeking new challenges in enterprise RPA and agentic AI automation.",
        })

    def test_tools_and_platforms_not_intercepted_by_github_key(self):
        q = "Which tools, platforms, or technologies are you proficient in? (e.g., Jira, GitHub, MS Project, AI tools, etc.)*"
        ans = self.engine.answer_text_question(q)
        self.assertNotIn(ans, ["2", "Yes", "No"])
        self.assertIn("Automation Anywhere", ans)
        self.assertIn("Python", ans)

    def test_primary_technologies_list(self):
        q = "Please list the primary technologies you've worked with and mention any advanced or latest versions used (e.g., .NET 6, Angular 15, Python 3.11, etc.)*"
        ans = self.engine.answer_text_question(q)
        self.assertNotIn(ans, ["2", "Yes", "No"])
        self.assertIn("Python", ans)
        self.assertIn("Automation Anywhere", ans)

    def test_certifications_list(self):
        q = "Have you completed any relevant certifications or training programs? Please list them.*"
        ans = self.engine.answer_text_question(q)
        self.assertNotIn(ans, ["Yes", "No", "2"])
        self.assertIn("Advanced Automation", ans)

    def test_reason_for_seeking_opportunity_concise(self):
        q = "What is your primary reason for seeking a new opportunity?*"
        ans = self.engine.answer_text_question(q)
        self.assertLess(len(ans), 100, "Single line answer must be concise to avoid truncation mid-word")
        self.assertTrue(ans.endswith("."), "Should be a complete sentence")
        self.assertIn("RPA", ans)

    def test_why_join_company(self):
        q = "Why Do You Want to Join Our Company?*"
        ans = self.engine.answer_text_question(q)
        self.assertGreater(len(ans), 20)
        self.assertIn("engineering", ans.lower())

    def test_rating_scale_1_to_5(self):
        q = "How would you rate your communication and stakeholder engagement skills? (Scale of 1-5)*"
        ans = self.engine.answer_text_question(q)
        self.assertIn(ans, ["4", "5"])


    def test_location_city_not_numeric(self):
        q = "Location (city) *"
        ans = self.engine.answer_text_question(q)
        self.assertNotIn(ans, ["2", "2.0", "0", "Yes", "No"])
        self.assertIn("Delhi", ans)

    def test_currency_choice_resolution(self):
        """Verify currency dropdown questions resolve to INR and match valid options."""
        q = "Select currency type *"
        opts1 = ["Select an option", "INR", "USD", "EUR"]
        target1, matched1 = self.engine.answer_select_or_radio(q, opts1)
        self.assertEqual(matched1, "INR")

        opts2 = ["Choose an option", "Indian Rupee (INR)", "US Dollar (USD)", "Euro (EUR)"]
        target2, matched2 = self.engine.answer_select_or_radio(q, opts2)
        self.assertEqual(matched2, "Indian Rupee (INR)")

        opts3 = ["Select an option", "Fiji Dollar (FJD)", "Rupees", "US Dollar"]
        target3, matched3 = self.engine.answer_select_or_radio("Select desired salary currency", opts3)
        self.assertEqual(matched3, "Rupees")

    def test_currency_text_resolution(self):
        """Verify currency text question returns candidate currency (INR)."""
        ans1 = self.engine.answer_text_question("Select currency type *")
        self.assertEqual(ans1, "INR")

        ans2 = self.engine.answer_text_question("Currency")
        self.assertEqual(ans2, "INR")

    def test_linkedin_applier_native_select_dropdown_execution(self):
        """Verify LinkedInApplier dispatches synthetic events and selects currency on native select."""
        from unittest.mock import MagicMock
        from platforms.linkedin.applier import LinkedInApplier

        applier = LinkedInApplier.__new__(LinkedInApplier)
        applier.qna_engine = self.engine

        mock_driver = MagicMock()
        mock_modal = MagicMock()

        # Mock select element
        mock_select = MagicMock()
        mock_select.is_displayed.return_value = True
        mock_select.get_attribute.side_effect = lambda attr: "urn:li:fsd_formElement:currency" if attr == "id" else ""

        # Mock label
        mock_label = MagicMock()
        mock_label.text = "Select currency type *"
        mock_modal.find_element.return_value = mock_label

        mock_modal.find_elements.side_effect = lambda by, val: (
            [] if val == "radio" or "type='radio'" in val
            else [mock_select] if val == "select"
            else []
        )

        # Mock driver.execute_script:
        # First call: return selected text (empty/placeholder)
        # Second call: return options raw
        mock_driver.execute_script.side_effect = [
            "Select an option",  # selected text
            [
                {"index": 0, "value": "", "text": "Select an option"},
                {"index": 1, "value": "INR", "text": "INR"},
                {"index": 2, "value": "USD", "text": "USD"},
            ],  # options raw
            None,  # event dispatch
        ]

        applier._answer_step_questions(mock_driver, mock_modal)

        # Verify execute_script was called to dispatch synthetic events
        self.assertTrue(mock_driver.execute_script.called)
        dispatch_script_call = mock_driver.execute_script.call_args_list[-1]
        script_text = dispatch_script_call[0][0]
        self.assertIn("dispatchEvent(new Event('change', { bubbles: true }))", script_text)
        self.assertIn("dispatchEvent(new Event('input', { bubbles: true }))", script_text)
        # Verify target index 1 (INR) was passed to the script
        self.assertEqual(dispatch_script_call[0][2], 1)
        self.assertEqual(dispatch_script_call[0][3], "INR")


if __name__ == "__main__":
    unittest.main()
