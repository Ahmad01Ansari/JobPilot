"""Targeted verification tests for beta testing feedback fixes across platforms."""

import unittest
from unittest.mock import MagicMock, patch

from modules.qna_engine import QnAEngine, Answer
from platforms.indeed.form import IndeedForm
from platforms.linkedin.applier import LinkedInApplier
from platforms.foundit.rotator import FounditRotator
from platforms.foundit.search import FounditSearch


class TestBetaFeedbackFixes(unittest.TestCase):
    def setUp(self):
        self.qna_engine = QnAEngine(ai_client=None)
        self.qna_engine.prof["years_of_experience"] = 2.0
        self.qna_engine.full_name = "Mohd Ahmad Raza Ansari"

    def test_naukri_mention_name_and_exp_database(self):
        """Verify 'Mention name & exp. in Database' does NOT return the candidate's personal name."""
        q = "Mention name & exp. in Database & Integration (SQL Server; MySQL; REST APIs; Web Services)"
        ans = self.qna_engine.resolve_text_answer(q)
        self.assertNotEqual(str(ans.value), "Mohd Ahmad Raza Ansari")
        self.assertIn("SQL", str(ans.value))
        self.assertIn("REST APIs", str(ans.value))

    def test_naukri_mention_name_and_exp_programming(self):
        """Verify programming languages question returns Python and JavaScript, not a beginner stub."""
        q = "Mention name & exp. in Programming Languages (Python, C#, Java , Javascript)"
        ans = self.qna_engine.resolve_text_answer(q)
        self.assertIn("Python", str(ans.value))
        self.assertIn("JavaScript", str(ans.value))

    def test_naukri_mention_name_and_exp_rpa(self):
        """Verify RPA question returns Automation Anywhere."""
        q = "Mention name & exp. in the RPA tools (UiPath, Microsoft Power Automate, Automation Anywhere)"
        ans = self.qna_engine.resolve_text_answer(q)
        self.assertIn("Automation Anywhere", str(ans.value))

    def test_naukri_mention_name_and_exp_aiml(self):
        """Verify AI/Machine tools question returns Generative AI and LLMs."""
        q = "Mention name and exp. AI & Machine tools(AI/ML; Generative AI; OpenAI/LLMs; NLP; OCR)"
        ans = self.qna_engine.resolve_text_answer(q)
        self.assertIn("Generative AI", str(ans.value))
        self.assertIn("OpenAI", str(ans.value))

    def test_candidate_name_only_for_real_identity_queries(self):
        """Verify candidate full name is only returned for genuine identity prompts."""
        real_name_q = "Full legal name"
        ans = self.qna_engine.resolve_text_answer(real_name_q)
        self.assertEqual(str(ans.value), "Mohd Ahmad Raza Ansari")

        signature_q = "Applicant signature"
        ans_sig = self.qna_engine.resolve_text_answer(signature_q)
        self.assertEqual(str(ans_sig.value), "Mohd Ahmad Raza Ansari")

    def test_linkedin_sponsorship_radio_negative(self):
        """Verify visa sponsorship question returns No."""
        q = "Will you in the future require employer sponsorship to work where this job is located?"
        target, matched = self.qna_engine.answer_select_or_radio(q, ["Yes", "No"])
        self.assertEqual(target, "No")

    def test_linkedin_prior_employment_radio_negative(self):
        """Verify prior employment question returns No."""
        q = "Are you currently employed, or ever been employed by J.S. Held or its subsidiaries before?"
        target, matched = self.qna_engine.answer_select_or_radio(q, ["Yes", "No"])
        self.assertEqual(target, "No")

    def test_indeed_referral_question_negative(self):
        """Verify employee referral question returns No."""
        q = "Were you referred by a current Smart Data Solutions employee?"
        target, matched = self.qna_engine.answer_select_or_radio(q, ["Yes", "No"])
        self.assertEqual(target, "No")

    def test_indeed_safe_option_currency_resolver(self):
        """Verify currency dropdown defaults to INR/USD and never Fiji Dollar."""
        options = ["Fiji Dollar (FJD)", "Indian Rupee (INR)", "US Dollar (USD)"]
        resolved = IndeedForm._resolve_safe_option("Select desired salary currency", options, "", None)
        self.assertEqual(resolved, "Indian Rupee (INR)")

    def test_indeed_safe_option_country_resolver(self):
        """Verify country dropdown defaults to India (+91) and never Afghanistan or British Indian Ocean Territory."""
        options = ["Afghanistan (+93)", "Albania (+355)", "British Indian Ocean Territory (+246)", "India (+91)", "United States (+1)"]
        resolved = IndeedForm._resolve_safe_option("Phone Country Code", options, "", None)
        self.assertEqual(resolved, "India (+91)")

    def test_indeed_safe_option_dial_codes_on_unaligned_label(self):
        """Verify that when options contain dial codes, India (+91) is chosen even with checkbox label."""
        options = ["Afghanistan (+93)", "Albania (+355)", "British Indian Ocean Territory (+246)", "India (+91)"]
        q_text = "(Optional) I would like to receive text messages to this number about my job application."
        resolved = IndeedForm._resolve_safe_option(q_text, options, "", None)
        self.assertEqual(resolved, "India (+91)")

    def test_indeed_clean_phone_number(self):
        """Verify phone number is cleaned to pure digits without + or decimals."""
        self.assertEqual(IndeedForm._clean_phone_number("+916388623967"), "6388623967")
        self.assertEqual(IndeedForm._clean_phone_number("+91 63886 23967"), "6388623967")
        self.assertEqual(IndeedForm._clean_phone_number("6388623967"), "6388623967")
        self.assertEqual(IndeedForm._clean_phone_number("+1 (555) 123-4567"), "5551234567")
        self.assertEqual(IndeedForm._clean_phone_number("06388623967"), "6388623967")

    def test_unverified_answers_not_persisted_to_custom_qa(self):
        """Verify bot guesses or fallbacks do not poison custom_qa."""
        initial_count = len(self.qna_engine.custom_qa)
        q = "Random new question that is not in profile 998877"
        self.qna_engine.answer_question(q, options=["Yes", "No"], field_type="radio")
        self.assertEqual(len(self.qna_engine.custom_qa), initial_count)


if __name__ == "__main__":
    unittest.main()

