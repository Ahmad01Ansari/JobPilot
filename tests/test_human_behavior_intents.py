import unittest
from unittest.mock import MagicMock, patch

from app.db.session import SessionLocal
from app.services.pilot.intent_router import IntentRouter
from app.services.pilot.pilot_models import PilotActionType
from app.services.pilot.pilot_service import PilotService


class TestHumanBehaviorIntents(unittest.TestCase):
    """Exhaustive test suite verifying human behavioral phrasing and edge cases."""

    def setUp(self):
        self.router = IntentRouter(ai_gateway=None)
        self.session_factory = SessionLocal

    def test_past_application_inquiries(self):
        """Humans asking if they applied, checking application status, or referencing jobs."""
        inquiries = [
            ("did i apply rpa engineer with pyt robocorp at fugentex solution", "fugentex solution", "rpa engineer with pyt robocorp"),
            ("did i apply to fugentex solution", "fugentex solution", None),
            ("have i applied to infosys", "infosys", None),
            ("did we apply to ncare md", "ncare md", None),
            ("check if i applied to google", "google", None),
            ("is there an application for amazon", "amazon", None),
            ("status of my application at gamma labs", "gamma labs", None),
            ("status of infosys", "infosys", None),
            ("did i apply for python developer at microsoft", "microsoft", "python developer"),
        ]
        for query, expected_comp, expected_role in inquiries:
            with self.subTest(query=query):
                act, params, _ = self.router.parse_intent(query)
                self.assertEqual(act, PilotActionType.QUERY_APPLICATION_STATUS)
                if expected_comp:
                    self.assertIn(expected_comp, params.get("company", "").lower())
                if expected_role:
                    self.assertIn(expected_role, params.get("role", "").lower())

    def test_skip_keyword_and_rule_modifications(self):
        """Humans adding, removing, and viewing skip keywords with various connectors."""
        rule_cases = [
            ("add unity as skip keyword in list", PilotActionType.UPDATE_RULES, "add_deal_breaker", "unity"),
            ("add unity in skip keyword list", PilotActionType.UPDATE_RULES, "add_deal_breaker", "unity"),
            ("add unity to skip keywords", PilotActionType.UPDATE_RULES, "add_deal_breaker", "unity"),
            ("add unity as a skip keyword", PilotActionType.UPDATE_RULES, "add_deal_breaker", "unity"),
            ("add skip keyword unity", PilotActionType.UPDATE_RULES, "add_deal_breaker", "unity"),
            ("skip jobs with rust", PilotActionType.UPDATE_RULES, "add_deal_breaker", "rust"),
            ("avoid civil engineering", PilotActionType.UPDATE_RULES, "add_deal_breaker", "civil engineering"),
            ("remove unity from skip keyword list", PilotActionType.UPDATE_RULES, "remove_deal_breaker", "unity"),
            ("remove skip keyword unity", PilotActionType.UPDATE_RULES, "remove_deal_breaker", "unity"),
            ("unskip unity", PilotActionType.UPDATE_RULES, "remove_deal_breaker", "unity"),
            ("what are skip keyword?", PilotActionType.GET_RULES, None, None),
            ("what are the skip keywords", PilotActionType.GET_RULES, None, None),
            ("list skip keywords", PilotActionType.GET_RULES, None, None),
            ("show rules", PilotActionType.GET_RULES, None, None),
        ]
        for query, expected_act, expected_type, expected_breaker in rule_cases:
            with self.subTest(query=query):
                act, params, _ = self.router.parse_intent(query)
                self.assertEqual(act, expected_act)
                if expected_type:
                    self.assertEqual(params.get("type"), expected_type)
                if expected_breaker:
                    self.assertEqual(params.get("deal_breaker"), expected_breaker)

    def test_inquiry_never_triggers_dangerous_automation(self):
        """Questions containing the word 'apply' must NEVER launch live browser automation."""
        non_actions = [
            "how to apply on linkedin",
            "how do i apply for jobs",
            "why did you apply to infosys",
            "where did i apply today",
            "can i apply later",
            "should i apply to contract roles",
            "did i apply to #704",
        ]
        for query in non_actions:
            with self.subTest(query=query):
                act, _, _ = self.router.parse_intent(query)
                self.assertNotEqual(act, PilotActionType.APPLY_JOBS)
                self.assertNotEqual(act, PilotActionType.START_AUTOMATION)

    def test_direct_imperative_controls(self):
        """Strict direct commands must trigger their respective actions instantly."""
        commands = [
            ("stop", PilotActionType.STOP_AUTOMATION),
            ("stop bot", PilotActionType.STOP_AUTOMATION),
            ("pause", PilotActionType.PAUSE_AUTOMATION),
            ("resume", PilotActionType.RESUME_AUTOMATION),
            ("apply to #704", PilotActionType.APPLY_JOBS),
            ("apply to 5 jobs on linkedin", PilotActionType.APPLY_JOBS),
            ("start applying", PilotActionType.APPLY_JOBS),
            ("run linkedin bot", PilotActionType.START_AUTOMATION),
            ("launch indeed", PilotActionType.START_AUTOMATION),
        ]
        for query, expected_act in commands:
            with self.subTest(query=query):
                act, _, _ = self.router.parse_intent(query)
                self.assertEqual(act, expected_act)

    def test_candidate_profile_and_resume_inquiries(self):
        """Candidate asking about resume skills, library, tailoring, or offers."""
        queries = [
            ("what are the key skills from my resume", PilotActionType.GET_RESUME_SKILLS),
            ("list resumes", PilotActionType.LIST_RESUMES),
            ("design a resume for tech lead", PilotActionType.TAILOR_RESUME),
            ("what is the offer i have", PilotActionType.GET_OFFERS),
            ("find remote python developer jobs", PilotActionType.SEARCH_JOBS),
            ("today apply report", PilotActionType.GET_APPLICATIONS_REPORT),
        ]
        for query, expected_act in queries:
            with self.subTest(query=query):
                act, _, _ = self.router.parse_intent(query)
                self.assertEqual(act, expected_act)

    def test_application_lifecycle_updates(self):
        """Candidate instructing to mark applications or update stages."""
        updates = [
            ("mark all gamma labs as rejected", PilotActionType.UPDATE_APPLICATION_STATUS),
            ("update infosys to under review", PilotActionType.UPDATE_APPLICATION_STATUS),
        ]
        for query, expected_act in updates:
            with self.subTest(query=query):
                act, params, _ = self.router.parse_intent(query)
                self.assertEqual(act, expected_act)

    def test_grounded_platform_navigation_and_features(self):
        """Verifies grounded answers for UI navigation and zero hallucination."""
        pilot = PilotService(session_factory=self.session_factory)
        
        # 1. Daily Apply Limit query
        msg_limit = pilot.process_user_prompt("How to change my daily apply limit?")
        self.assertIn("Platforms", msg_limit.body)
        self.assertIn("Configure", msg_limit.body)
        self.assertIn("Daily Application Goal", msg_limit.body)
        self.assertNotIn("Open Settings", msg_limit.body)
        # Verify exactly 3 non-duplicate steps
        self.assertEqual(len(msg_limit.steps), 3)
        self.assertTrue(all(s.status == "done" for s in msg_limit.steps))

        # 2. Email Outreach query
        msg_outreach = pilot.process_user_prompt("What is the email outreach feature?")
        self.assertIn("Email Outreach Workspace", msg_outreach.body)
        self.assertIn("Ctrl+6", msg_outreach.body)
        self.assertIn("Recruiter Contact Directory", msg_outreach.body)
        self.assertEqual(len(msg_outreach.steps), 3)

        # 3. Universal ATS Agent query
        msg_ats = pilot.process_user_prompt("what is universal ats agent?")
        self.assertIn("Universal ATS Agent", msg_ats.body)
        self.assertIn("Greenhouse", msg_ats.body)


if __name__ == "__main__":
    unittest.main()

