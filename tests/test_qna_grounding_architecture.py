"""Unit tests for Grounded QnA Engine Skill Verification Architecture.

Verifies that:
1. Questions asking for experience in specific skills (e.g. Siemens PLC, HMI, Modbus)
   ground strictly against candidate profile facts and return 0 if unmentioned.
2. Questions asking for candidate core skills (Python, Automation Anywhere) return candidate experience.
3. Questions asking for total/overall experience return candidate overall experience.
4. Generic rule keys (e.g. 'years', 'experience') do not falsely match skill-specific questions.
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.qna_engine import QnAEngine, Answer


class TestQnAGroundingArchitecture(unittest.TestCase):
    def setUp(self):
        self.qna = QnAEngine()
        # Seed test candidate profile
        self.qna.prof = {
            "years_of_experience": 2,
            "skills": ["Python", "Automation Anywhere", "Process Automation"],
            "primary_skills": ["Python", "Automation Anywhere"],
            "secondary_skills": ["SQL", "REST APIs"],
            "title": "RPA Developer",
            "headline": "RPA Developer & Automation Engineer",
            "summary": "Experienced in building Python automations and Automation Anywhere bots.",
            "work_experiences": [
                {
                    "title": "RPA Developer",
                    "description": "Developed automations using Python and Automation Anywhere.",
                }
            ],
        }
        self.qna.ai_context = " mohd ahmad raza ansari rpa developer python automation anywhere "
        self.qna.resume_text = " mohd ahmad raza ansari python automation anywhere sql "
        # Mock out external AI call to isolate grounded fallback logic
        self.qna._query_ai = MagicMock(return_value=None)
        # Seed custom rule bank including generic keys
        self.qna.custom_qa = {
            "years": "2",
            "experience": "2",
            "years of experience": "2",
            "python": "2",
        }

    def test_unmentioned_hardware_skill_answers_zero(self):
        """Unverified/unmentioned skills must strictly return 0."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in Siemens PLC?")
        self.assertEqual(ans.value, "0")

    def test_unmentioned_hmi_skill_answers_zero(self):
        """HMI Programming must return 0 because it does not exist in candidate profile."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in HMI Programming?")
        self.assertEqual(ans.value, "0")

    def test_unmentioned_modbus_skill_answers_zero(self):
        """Modbus must return 0 because it does not exist in candidate profile."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in Modbus?")
        self.assertEqual(ans.value, "0")

    def test_verified_candidate_skill_answers_candidate_experience(self):
        """Skills listed in candidate facts must return candidate tenure."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in Python?")
        self.assertEqual(ans.value, "2")

    def test_verified_automation_anywhere_skill(self):
        """Multi-word skill in candidate facts must return candidate tenure."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in Automation Anywhere?")
        self.assertEqual(ans.value, "2")

    def test_generic_overall_experience_answers_total(self):
        """Total/overall experience questions return candidate overall experience."""
        ans = self.qna.resolve_text_answer("Total years of experience")
        self.assertEqual(ans.value, "2")
        self.assertEqual(ans.source, "profile")

    def test_generic_rule_key_does_not_match_skill_question(self):
        """Rule key 'years' -> '2' must not match questions asking about a specific skill."""
        ans = self.qna.resolve_text_answer("How many years of experience do you have in Solidworks API?")
        self.assertEqual(ans.value, "0")


if __name__ == "__main__":
    unittest.main()

