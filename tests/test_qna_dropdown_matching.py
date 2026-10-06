"""Unit tests for intelligent dropdown option matching and referral source question resolution."""

import unittest
from modules.qna_engine import QnAEngine


class TestQnADropdownMatching(unittest.TestCase):
    """Verifies that dropdown and combobox matching selects the correct option even when written answers differ."""

    def setUp(self):
        self.engine = QnAEngine()

    def test_written_sentence_matches_single_option(self):
        """When bot generates a sentence containing 'LinkedIn', it must match 'LinkedIn' in dropdown."""
        target = "I saw the job posting on LinkedIn."
        options = ["Select an option", "Company Website", "LinkedIn", "Employee Referral", "Other"]
        matched = self.engine._match_option(target, options)
        self.assertEqual(matched, "LinkedIn")

    def test_written_answer_matches_composite_job_board_option(self):
        """Matches composite options like 'Job Board (LinkedIn, Indeed)' when target mentions LinkedIn."""
        target = "I saw the job posting on LinkedIn."
        options = ["Select an option", "Company Career Website", "Job Board (LinkedIn, Indeed)", "Recruiter", "Other"]
        matched = self.engine._match_option(target, options)
        self.assertEqual(matched, "Job Board (LinkedIn, Indeed)")

    def test_learn_about_position_question_resolution(self):
        """Tests that 'How did you learn about this position? *' resolves to LinkedIn when LinkedIn is available."""
        question = "How did you learn about this position? *"
        options = ["Select an option", "Company Website", "LinkedIn", "Social Media", "Other"]
        answer = self.engine.answer_question(
            question=question,
            options=options,
            field_type="select"
        )
        self.assertEqual(answer.value, "LinkedIn")

    def test_placeholder_options_are_never_chosen(self):
        """Validates that 'Select an option' is filtered out and never returned as matched option."""
        target = "Unknown random answer"
        options = ["Select an option", "Option Alpha", "Option Beta"]
        matched = self.engine._match_option(target, options)
        self.assertNotEqual(matched, "Select an option")
        self.assertIn(matched, ["Option Alpha", "Option Beta"])

    def test_referral_synonym_mapping(self):
        """Tests that referral answers match options like 'Employee Referral'."""
        target = "Referred by a friend / colleague"
        options = ["Select an option", "Career Site", "Job Fair", "Employee Referral", "Agency"]
        matched = self.engine._match_option(target, options)
        self.assertEqual(matched, "Employee Referral")


if __name__ == "__main__":
    unittest.main()
