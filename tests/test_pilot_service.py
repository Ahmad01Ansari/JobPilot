"""Unit tests for the JobPilot AI Pilot Subsystem."""

from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock

from app.services.pilot.intent_router import IntentRouter
from app.services.pilot.pilot_models import (
    InterventionKind,
    InterventionStatus,
    PilotActionType,
    PilotAuthor,
    PilotMessage,
    PilotRuleChange,
    PilotStep,
)
from app.services.pilot.pilot_service import PilotService


class TestIntentRouter(unittest.TestCase):
    """Verifies intent parsing and parameter extraction."""

    def setUp(self):
        self.router = IntentRouter(ai_gateway=None)

    def test_parse_empty_string(self):
        action, params, _ = self.router.parse_intent("")
        self.assertEqual(action, PilotActionType.CHAT)

    def test_parse_run_linkedin_automation(self):
        action, params, _ = self.router.parse_intent("run the LinkedIn automation")
        self.assertEqual(action, PilotActionType.START_AUTOMATION)
        self.assertEqual(params.get("platform"), "linkedin")

    def test_parse_run_indeed(self):
        action, params, _ = self.router.parse_intent("run indeed")
        self.assertEqual(action, PilotActionType.START_AUTOMATION)
        self.assertEqual(params.get("platform"), "indeed")

    def test_parse_start_naukri_bot(self):
        action, params, _ = self.router.parse_intent("start naukri bot")
        self.assertEqual(action, PilotActionType.START_AUTOMATION)
        self.assertEqual(params.get("platform"), "naukri")

    def test_parse_today_apply_report(self):
        action, params, _ = self.router.parse_intent("today apply report")
        self.assertEqual(action, PilotActionType.GET_APPLICATIONS_REPORT)
        self.assertEqual(params.get("timeframe"), "today")

    def test_parse_what_did_we_apply_to_today(self):
        action, params, _ = self.router.parse_intent("what did we apply to today?")
        self.assertEqual(action, PilotActionType.GET_APPLICATIONS_REPORT)

    def test_parse_top_jobs(self):
        action, params, _ = self.router.parse_intent("show eligible jobs")
        self.assertEqual(action, PilotActionType.GET_TOP_JOBS)

    def test_parse_check_platforms(self):
        action, params, _ = self.router.parse_intent("check platforms")
        self.assertEqual(action, PilotActionType.CHECK_PLATFORMS)

    def test_parse_search_intent(self):
        action, params, _ = self.router.parse_intent("Find remote python developer jobs on linkedin")
        self.assertEqual(action, PilotActionType.SEARCH_JOBS)
        self.assertEqual(params.get("platform"), "linkedin")
        self.assertTrue(params.get("remote"))

    def test_parse_apply_intent(self):
        action, params, _ = self.router.parse_intent("apply to 10 jobs on indeed")
        self.assertEqual(action, PilotActionType.APPLY_JOBS)
        self.assertEqual(params.get("count"), 10)
        self.assertEqual(params.get("platform"), "indeed")

    def test_parse_direct_url(self):
        url = "https://www.linkedin.com/jobs/view/123456789"
        action, params, _ = self.router.parse_intent(url)
        self.assertEqual(action, PilotActionType.APPLY_JOBS)
        self.assertEqual(params.get("url"), url)

    def test_parse_deal_breaker_rule(self):
        action, params, _ = self.router.parse_intent("Skip jobs requiring a security clearance")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("type"), "add_deal_breaker")
        self.assertIn("security clearance", params.get("deal_breaker", ""))

    def test_parse_min_score_rule(self):
        action, params, _ = self.router.parse_intent("Set minimum match score to 85%")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("type"), "set_min_score")
        self.assertEqual(params.get("min_score"), 85)

    def test_parse_pause_resume_stop(self):
        self.assertEqual(self.router.parse_intent("pause automation")[0], PilotActionType.PAUSE_AUTOMATION)
        self.assertEqual(self.router.parse_intent("resume")[0], PilotActionType.RESUME_AUTOMATION)
        self.assertEqual(self.router.parse_intent("stop bot")[0], PilotActionType.STOP_AUTOMATION)

    def test_parse_2fa_code(self):
        action, params, _ = self.router.parse_intent("Here is the verification code: 829103")
        self.assertEqual(action, PilotActionType.ANSWER_INTERVENTION)
        self.assertEqual(params.get("answer"), "829103")


class TestPilotService(unittest.TestCase):
    """Verifies PilotService execution of real commands."""

    def setUp(self):
        self.mock_session_factory = MagicMock()
        self.automation_mock = MagicMock()
        self.automation_mock.is_running.return_value = False
        self.automation_mock.start_automation.return_value = (True, None)
        self.resume_mock = MagicMock()
        self.job_mock = MagicMock()

        self.service = PilotService(
            session_factory=self.mock_session_factory,
            ai_gateway=None,
            automation_service=self.automation_mock,
            resume_service=self.resume_mock,
            job_service=self.job_mock,
        )

    def test_execute_run_linkedin_calls_automation_manager(self):
        reply = self.service.process_user_prompt("run the LinkedIn automation")
        self.assertEqual(reply.action_type, PilotActionType.START_AUTOMATION)
        self.automation_mock.start_automation.assert_called_once_with(
            platform="linkedin",
            target_url=None,
            headless=None,
        )

    def test_execute_run_indeed_calls_automation_manager(self):
        reply = self.service.process_user_prompt("run indeed")
        self.assertEqual(reply.action_type, PilotActionType.START_AUTOMATION)
        self.automation_mock.start_automation.assert_called_once_with(
            platform="indeed",
            target_url=None,
            headless=None,
        )

    def test_execute_all_tag_actions(self):
        router = self.service.intent_router
        # 1. Run all platforms
        for plat in ["linkedin", "indeed", "naukri", "foundit", "glassdoor"]:
            action, params, _ = router.parse_intent(f"run {plat}")
            self.assertEqual(action, PilotActionType.START_AUTOMATION)
            self.assertEqual(params.get("platform"), plat)

        # 2. Controls
        self.assertEqual(router.parse_intent("pause automation")[0], PilotActionType.PAUSE_AUTOMATION)
        self.assertEqual(router.parse_intent("resume automation")[0], PilotActionType.RESUME_AUTOMATION)
        self.assertEqual(router.parse_intent("stop automation")[0], PilotActionType.STOP_AUTOMATION)

        # 3. Reports
        self.assertEqual(router.parse_intent("today apply report")[0], PilotActionType.GET_APPLICATIONS_REPORT)
        self.assertEqual(router.parse_intent("show eligible jobs")[0], PilotActionType.GET_TOP_JOBS)
        self.assertEqual(router.parse_intent("check platforms")[0], PilotActionType.CHECK_PLATFORMS)

        # 4. Rules
        action, params, _ = router.parse_intent("skip contract roles")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("type"), "add_deal_breaker")

        # 5. Resumes and QnA
        self.assertEqual(router.parse_intent("extract resume")[0], PilotActionType.EXTRACT_RESUME)
        self.assertEqual(router.parse_intent("list resumes")[0], PilotActionType.LIST_RESUMES)
        self.assertEqual(router.parse_intent("list qna")[0], PilotActionType.LIST_QNA)

    def test_execute_stop_automation(self):
        self.automation_mock.is_running.return_value = True
        reply = self.service.process_user_prompt("stop automation")
        self.assertEqual(reply.action_type, PilotActionType.STOP_AUTOMATION)
        self.automation_mock.request_stop.assert_called_once()

    def test_execute_pause_and_resume(self):
        self.automation_mock.is_running.return_value = True
        self.automation_mock.is_paused.return_value = True

        reply_pause = self.service.process_user_prompt("pause")
        self.assertEqual(reply_pause.action_type, PilotActionType.PAUSE_AUTOMATION)
        self.automation_mock.pause.assert_called_once()

        reply_resume = self.service.process_user_prompt("resume")
        self.assertEqual(reply_resume.action_type, PilotActionType.RESUME_AUTOMATION)
        self.automation_mock.resume.assert_called_once()

    def test_initial_timeline_has_greeting(self):
        timeline = self.service.get_timeline()
        self.assertGreaterEqual(len(timeline), 1)
        self.assertEqual(timeline[0].author, PilotAuthor.PILOT)

    def test_intervention_resolution(self):
        inv = self.service.create_intervention(
            prompt="Enter LinkedIn 2FA",
            kind=InterventionKind.TWO_FACTOR,
            platform="LinkedIn",
        )
        self.assertEqual(inv.status, InterventionStatus.OPEN)

        # Candidate types the 2FA code in chat
        reply = self.service.process_user_prompt("482910")
        self.assertEqual(inv.status, InterventionStatus.ANSWERED)
        self.assertEqual(inv.answer, "482910")
        self.automation_mock.confirm_review.assert_called_once()

    def test_list_resumes_returns_candidate_library(self):
        class DummyResume:
            def __init__(self, id, file_path, is_default, version, role_target):
                self.id = id
                self.file_path = file_path
                self.is_default = is_default
                self.version = version
                self.role_target = role_target

        self.resume_mock.list_resumes.return_value = [
            DummyResume(1, "/path/to/My_Resume_2026.pdf", True, "1.0", "AI Engineer"),
            DummyResume(2, "/path/to/RPA_Lead_Resume.pdf", False, "1.2", "RPA Developer"),
        ]
        msg = self.service.process_user_prompt("list resumes")
        self.assertIn("My_Resume_2026.pdf", msg.body)
        self.assertIn("RPA_Lead_Resume.pdf", msg.body)
        self.assertIn("[ACTIVE DEFAULT]", msg.body)

    def test_top_10_jobs_query_intent_and_execution(self):
        from app.services.dto.dashboard_dto import TopOpportunityDTO
        self.job_mock.get_top_opportunities.return_value = [
            TopOpportunityDTO(
                job_id=757,
                title="Senior Hyper Automation Developer",
                company="Robert Bosch",
                platform="foundit",
                score=88,
                location="Remote",
                application_method="DIRECT",
                decision="STRONG_MATCH",
                evaluation_status="QUALIFIED",
                confidence=0.9,
            )
        ]
        msg = self.service.process_user_prompt("find out the top 10 job for me today for apply")
        self.assertIn("#757: Senior Hyper Automation Developer", msg.body)
        self.assertIn("Robert Bosch", msg.body)
        self.assertIn("88%", msg.body)
        self.assertIn("apply to #757", msg.body)

    def test_apply_specific_job_id_extraction(self):
        action, params, _ = self.service.intent_router.parse_intent("apply to #608")
        self.assertEqual(action, PilotActionType.APPLY_JOBS)
        self.assertEqual(params.get("job_id"), 608)

    def test_smart_search_remote_python(self):
        action, params, _ = self.service.intent_router.parse_intent("find remote Python developer jobs")
        self.assertEqual(action, PilotActionType.SEARCH_JOBS)
        self.assertTrue(params.get("remote"))

    def test_check_platforms_reads_secrets_service(self):
        msg = self.service.process_user_prompt("check platforms")
        self.assertIn("Linkedin", msg.body)
        self.assertIn("Naukri", msg.body)
        self.assertIn("[READY]", msg.body)
        self.assertIn("rjaahmad60@gmail.com", msg.body)

    def test_dynamic_step_simulation_transitions(self):
        msg = self.service.process_user_prompt("start naukri bot")
        running_steps = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running_steps), 1)

        # Incoming bot log
        self.service._on_bot_activity("23:00:00", "[NaukriPlatform] Scanning search results page 1...")
        running_steps = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running_steps), 1)
        self.assertIn("Scanning search results page 1...", running_steps[0].title)

        # Run finished
        class FakeResult:
            applications_submitted = 2
            jobs_discovered = 10
            jobs_evaluated = 8
        self.service._on_bot_run_finished(FakeResult())
        running_steps = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running_steps), 0)

    def test_get_resume_skills_intent_and_execution(self):
        class DummyResume:
            def __init__(self, id, file_path, is_default, version, role_target, parsed_metadata=None):
                self.id = id
                self.name = "Mohd Ahmad Raza Ansari Resume 11 09 2026.pdf"
                self.file_path = file_path
                self.is_default = is_default
                self.version = version
                self.role_target = role_target
                self.parsed_metadata = parsed_metadata or {
                    "detected_skills": [
                        {"canonical": "Python", "category": "Languages"},
                        {"canonical": "Automation Anywhere", "category": "RPA"},
                        {"canonical": "Docker", "category": "DevOps & Cloud"},
                    ]
                }

        self.resume_mock.list_resumes.return_value = [
            DummyResume(1, "/tmp/dummy.pdf", True, "1.0", "AI Engineer")
        ]

        action, _, _ = self.service.intent_router.parse_intent("what are the key skills from my resume")
        self.assertEqual(action, PilotActionType.GET_RESUME_SKILLS)

        msg = self.service.process_user_prompt("what are the key skills from my resume")
        self.assertIn("Verified Technical Skills", msg.body)
        self.assertIn("Python", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

    def test_design_resume_intent_and_execution(self):
        action, params, _ = self.service.intent_router.parse_intent("design a resume for Tech Lead")
        self.assertEqual(action, PilotActionType.TAILOR_RESUME)
        self.assertEqual(params.get("target"), "tech lead")

        msg = self.service.process_user_prompt("design a resume for Tech Lead")
        self.assertIn("TECH LEAD", msg.body)
        self.assertIn("Executive Summary", msg.body)
        self.assertIn("Core Competencies", msg.body)
        self.assertIn("Tailored Key Achievements", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

    def test_parse_offers_intent_and_execution(self):
        action, params, _ = self.service.intent_router.parse_intent("what is compnay and about the offer i have??")
        self.assertEqual(action, PilotActionType.GET_OFFERS)

        msg = self.service.process_user_prompt("what is compnay and about the offer i have??")
        self.assertEqual(msg.action_type, PilotActionType.GET_OFFERS)
        self.assertIn("Offer", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

    def test_tailor_resume_cleans_filler_phrases(self):
        action, params, _ = self.service.intent_router.parse_intent("design resume for full stack for me")
        self.assertEqual(action, PilotActionType.TAILOR_RESUME)
        self.assertEqual(params.get("target"), "Full Stack Engineer")

        msg = self.service.process_user_prompt("design resume for full stack for me")
        self.assertIn("FULL STACK ENGINEER", msg.body)
        self.assertNotIn("FOR ME", msg.body)

    def test_update_application_status_intent_and_fuzzy_execution(self):
        # Test intent parsing with user syntax and typo "insfosys"
        action, params, _ = self.service.intent_router.parse_intent("for insfosys is mark as rejected")
        self.assertEqual(action, PilotActionType.UPDATE_APPLICATION_STATUS)
        self.assertEqual(params.get("company"), "insfosys")
        self.assertEqual(params.get("status"), "REJECTED")

        # Test execution
        msg = self.service.process_user_prompt("for insfosys is mark as rejected")
        self.assertEqual(msg.action_type, PilotActionType.UPDATE_APPLICATION_STATUS)
        self.assertIn("Application Status Updated", msg.body)
        self.assertIn("REJECTED", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

    def test_query_application_status_intent_and_execution(self):
        action, params, _ = self.service.intent_router.parse_intent("status of infosys")
        self.assertEqual(action, PilotActionType.QUERY_APPLICATION_STATUS)
        self.assertEqual(params.get("company"), "infosys")

        mock_app = MagicMock()
        mock_app.id = 1653
        mock_app.status = "UNDER_REVIEW"
        mock_app.job.title = "RPA Consultant"
        mock_app.job.company.name = "Infosys"
        mock_app.job.company_raw = "Infosys"
        mock_app.job.platform = "naukri"
        mock_app.applied_at = None
        self.mock_session_factory().query.return_value.join.return_value.outerjoin.return_value.filter.return_value.all.return_value = [mock_app]

        msg = self.service.process_user_prompt("status of infosys")
        self.assertEqual(msg.action_type, PilotActionType.QUERY_APPLICATION_STATUS)
        self.assertIn("Application Status", msg.body)
        self.assertIn("RPA Consultant", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

        # Verify 'did i apply' inquiries route to QUERY_APPLICATION_STATUS and do not launch automation
        action, params, _ = self.service.intent_router.parse_intent("did i apply rpa engineer with pyt robocorp at fugentex solution")
        self.assertEqual(action, PilotActionType.QUERY_APPLICATION_STATUS)
        self.assertEqual(params.get("company"), "fugentex solution")
        self.assertEqual(params.get("role"), "rpa engineer with pyt robocorp")

    def test_token_efficient_offer_summary(self):
        msg = self.service.process_user_prompt("what is the offer i have")
        self.assertEqual(msg.action_type, PilotActionType.GET_OFFERS)
        # Verify no unsolicited email template or lengthy 5-part treatise
        self.assertNotIn("Sample Negotiation Email Template", msg.body)
        self.assertNotIn("Subject: Re: Offer of Employment", msg.body)
        self.assertIn("Offer", msg.body)
        running = [s for s in msg.steps if s.status == "running"]
        self.assertEqual(len(running), 0)

    def test_pilot_message_serialization_roundtrip(self):
        original = PilotMessage(
            author=PilotAuthor.USER,
            body="test message",
            action_type=PilotActionType.CHAT,
            payload={"key": "val"},
            steps=[PilotStep(title="step 1", status="done")],
        )
        data = original.to_dict()
        restored = PilotMessage.from_dict(data)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.author, original.author)
        self.assertEqual(restored.body, original.body)
        self.assertEqual(restored.action_type, original.action_type)
        self.assertEqual(len(restored.steps), 1)
        self.assertEqual(restored.steps[0].title, "step 1")


    def test_get_skip_keywords_intent_and_execution(self):
        action1, _, _ = self.service.intent_router.parse_intent("what are skip keyword?")
        self.assertEqual(action1, PilotActionType.GET_RULES)

        action2, _, _ = self.service.intent_router.parse_intent("give me list of skip keyword?")
        self.assertEqual(action2, PilotActionType.GET_RULES)

        msg = self.service.process_user_prompt("what are skip keyword?")
        self.assertEqual(msg.action_type, PilotActionType.GET_RULES)
        self.assertIn("Active Skip Keywords & Exclusion Rules", msg.body)
        self.assertIn("Negative Title Keywords", msg.body)
        self.assertIn("electrical", msg.body)
        self.assertEqual(len([s for s in msg.steps if s.status == "running"]), 0)

    def test_add_deal_breaker_imperative_only(self):
        action, params, _ = self.service.intent_router.parse_intent("skip jobs with rust")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("deal_breaker"), "rust")

        # Test user phrasing variants
        action, params, _ = self.service.intent_router.parse_intent("add unity as skip keyword in list")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("type"), "add_deal_breaker")
        self.assertEqual(params.get("deal_breaker"), "unity")

        action, params, _ = self.service.intent_router.parse_intent("add unity in skip keyword list")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("deal_breaker"), "unity")

        action, params, _ = self.service.intent_router.parse_intent("remove unity from skip keyword list")
        self.assertEqual(action, PilotActionType.UPDATE_RULES)
        self.assertEqual(params.get("type"), "remove_deal_breaker")
        self.assertEqual(params.get("deal_breaker"), "unity")


if __name__ == "__main__":
    unittest.main()
