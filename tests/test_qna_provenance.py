import unittest
from modules.qna_engine import QnAEngine, Answer, validate_answer


class TestQnAProvenanceAndValidation(unittest.TestCase):
    def setUp(self):
        self.engine = QnAEngine(ai_client=None)

    def test_provenance_calculation(self):
        # 1. CTC in Lakhs -> calculation
        ans_lacs = self.engine.resolve_text_answer("What is your expected CTC in Lakhs?")
        self.assertEqual(ans_lacs.source, "calculation")
        self.assertTrue(ans_lacs.validated)
        self.assertGreaterEqual(ans_lacs.confidence, 0.9)
        self.assertIn("5.5", str(ans_lacs.value))

        # 1b. Naukri specific: What is your current CTC in Lacs per annum?
        ans_cur_lacs = self.engine.resolve_text_answer("What is your current CTC in Lacs per annum?")
        self.assertEqual(ans_cur_lacs.source, "calculation")
        self.assertTrue(ans_cur_lacs.validated)
        self.assertEqual(str(ans_cur_lacs.value), "3.50")

        # 2. Notice period in months -> calculation
        ans_np = self.engine.resolve_text_answer("Notice period in months")
        self.assertEqual(ans_np.source, "calculation")
        self.assertTrue(ans_np.validated)

    def test_provenance_profile(self):
        # Experience -> profile
        ans_exp = self.engine.resolve_text_answer("Total years of experience")
        self.assertEqual(ans_exp.source, "profile")
        self.assertEqual(str(ans_exp.value), "2")
        self.assertTrue(ans_exp.validated)

        # Name -> profile
        ans_name = self.engine.resolve_text_answer("Full legal name")
        self.assertEqual(ans_name.source, "profile")
        self.assertTrue(ans_name.validated)

    def test_provenance_rule(self):
        # Custom QA match -> rule
        ans_why = self.engine.resolve_text_answer("Why should we hire you?")
        self.assertEqual(ans_why.source, "rule")
        self.assertTrue(ans_why.validated)
        self.assertIn("proven hands-on experience", str(ans_why.value).lower())

    def test_validation_bounds_notice_period(self):
        # Valid notice period passes
        valid_ans = Answer(value="30 days", source="profile", confidence=1.0)
        res_ok = validate_answer(valid_ans, "Notice period required")
        self.assertTrue(res_ok.validated)

        # Out-of-bounds notice period (e.g. 500 days) fails
        bad_ans = Answer(value="500 days", source="llm", confidence=0.5)
        res_bad = validate_answer(bad_ans, "Notice period required")
        self.assertFalse(res_bad.validated)
        self.assertIn("outside reasonable bounds", res_bad.validation_error)

    def test_validation_bounds_salary(self):
        # Valid salary in Lacs passes
        valid_ans = Answer(value="5.5", source="calculation", confidence=0.98)
        res_ok = validate_answer(valid_ans, "Expected CTC in LPA")
        self.assertTrue(res_ok.validated)

        # Out-of-bounds salary in Lacs (e.g. 500 LPA) fails
        bad_ans = Answer(value="500", source="llm", confidence=0.5)
        res_bad = validate_answer(bad_ans, "Expected CTC in LPA")
        self.assertFalse(res_bad.validated)
        self.assertIn("outside realistic bounds", res_bad.validation_error)

    def test_validation_boolean_choice(self):
        # Yes / No question
        valid_ans = Answer(value="Yes", source="profile", confidence=1.0)
        res_ok = validate_answer(valid_ans, "Are you willing to relocate?", available_options=["Yes", "No"])
        self.assertTrue(res_ok.validated)

        # Invalid choice fails
        invalid_ans = Answer(value="Maybe later", source="llm", confidence=0.4)
        res_bad = validate_answer(invalid_ans, "Are you willing to relocate?", available_options=["Yes", "No"])
        self.assertFalse(res_bad.validated)
        self.assertIn("requires 'Yes' or 'No'", res_bad.validation_error)

    def test_backward_compatibility_strings(self):
        # Existing callers expecting plain strings must not break
        text_ans = self.engine.answer_text_question("Total years of experience")
        self.assertIsInstance(text_ans, str)
        self.assertEqual(text_ans, "2")

        target, matched = self.engine.answer_select_or_radio(
            "Are you willing to relocate?",
            ["Yes", "No"]
        )
        self.assertIsInstance(target, str)
        self.assertEqual(target, "Yes")
        self.assertEqual(matched, "Yes")


if __name__ == "__main__":
    unittest.main()
