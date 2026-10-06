import unittest
from modules.qna_engine import QnAEngine

class TestLinkedInFormValidation(unittest.TestCase):
    def setUp(self):
        self.engine = QnAEngine()

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

if __name__ == "__main__":
    unittest.main()
