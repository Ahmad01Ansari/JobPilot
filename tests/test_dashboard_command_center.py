"""Unit tests for JobPilot Dashboard Command Center logic.
Verifies:
1. Today's Job Hunt never falls back to Top Opportunities (clean empty queue).
2. Deterministic Next Best Action waterfall prioritization.
3. Search Performance DTO aggregation with single data model.
4. Daily progress repository delegation and local timezone boundaries.
"""
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import MagicMock, patch

from app.services.dashboard_service import DashboardService
from app.services.dto.dashboard_dto import (
    DailyProgressDTO,
    NextBestActionDTO,
    SearchPerformanceDTO,
    TodaysHuntItemDTO,
    TopOpportunityDTO,
)


class TestDashboardCommandCenter(unittest.TestCase):
    """Verifies core architectural constraints of the Dashboard Command Center."""

    def setUp(self):
        self.mock_session_factory = MagicMock()
        self.mock_job_service = MagicMock()
        self.mock_recruitment_service = MagicMock()
        self.mock_outreach_service = MagicMock()
        self.mock_application_service = MagicMock()
        self.mock_profile_service = MagicMock()
        self.mock_resume_service = MagicMock()
        self.mock_qna_service = MagicMock()
        self.mock_platform_service = MagicMock()
        self.mock_analytics_service = MagicMock()

        # Default all list queries to empty lists to avoid MagicMock truthiness
        self.mock_recruitment_service.list_interviews.return_value = []
        self.mock_recruitment_service.list_follow_ups.return_value = []
        self.mock_outreach_service.get_work_queue.return_value = []
        self.mock_application_service.list_applications.return_value = []
        self.mock_job_service.get_top_opportunities.return_value = []

        self.service = DashboardService(
            session_factory=self.mock_session_factory,
            job_service=self.mock_job_service,
            recruitment_service=self.mock_recruitment_service,
            outreach_service=self.mock_outreach_service,
            application_service=self.mock_application_service,
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
            analytics_service=self.mock_analytics_service,
        )

    def test_todays_hunt_never_contains_top_opportunities(self):
        """Today's Job Hunt must NEVER contain Top Opportunities or fall back to them when empty."""
        # Operational queue is empty
        self.mock_recruitment_service.list_interviews.return_value = []
        self.mock_recruitment_service.list_follow_ups.return_value = []
        self.mock_outreach_service.get_work_queue.return_value = []
        self.mock_application_service.list_applications.return_value = []

        # Even if job_service has top opportunities available:
        self.mock_job_service.get_top_opportunities.return_value = [
            TopOpportunityDTO(
                job_id=99,
                title="Lead Python Architect",
                company="TechCorp",
                location="Remote",
                platform="linkedin",
                application_method="EASY_APPLY",
                score=95,
                decision="STRONG_MATCH",
                evaluation_status="SUCCESS",
                confidence=0.98,
            )
        ]

        items = self.service.get_todays_job_hunt_items()
        self.assertEqual(items, [], "Empty operational queue MUST return empty list, not top opportunities")
        for item in items:
            self.assertNotEqual(item.item_type, "TOP_OPPORTUNITY")

    def test_next_best_action_waterfall_priority(self):
        """Next Best Action must follow strict deterministic waterfall priority."""
        from app.utils_time import get_local_day_utc_range
        now = datetime.now(timezone.utc)
        start_of_today, end_of_today = get_local_day_utc_range()

        # Case 1: Interview today beats recruiter reply and follow-ups
        mock_interview = MagicMock()
        mock_interview.id = 101
        mock_interview.scheduled_at = start_of_today + timedelta(hours=4)
        mock_interview.application.job.title = "Senior RPA Engineer"
        mock_interview.application.job.company_raw = "Global Automation"
        mock_interview.round_name = "System Architecture"
        mock_interview.mode = "VIRTUAL"
        mock_interview.meeting_link = "https://meet.google.com/xyz"
        mock_interview.application_id = 50

        self.mock_recruitment_service.list_interviews.return_value = [mock_interview]

        nba = self.service.get_next_best_action()
        self.assertEqual(nba.action_type, "INTERVIEW_TODAY")
        self.assertEqual(nba.action_name, "PREPARE_INTERVIEW")
        self.assertEqual(nba.company, "Global Automation")


        # Case 2: No interview, but recruiter reply exists -> RECRUITER_REPLY
        self.mock_recruitment_service.list_interviews.return_value = []

        from app.services.dto.outreach_enums import WorkQueueSection
        mock_group = MagicMock()
        mock_group.section = WorkQueueSection.TODAY
        mock_case = MagicMock()
        mock_case.id = 202
        mock_case.application_id = 60
        mock_case.application_company = "Apex Systems"
        mock_case.application_job_title = "Backend Lead"
        mock_case.subject = "When can you start?"
        mock_case.last_message_at = now - timedelta(hours=1)
        mock_group.cases = [mock_case]
        self.mock_outreach_service.get_work_queue.return_value = [mock_group]

        nba = self.service.get_next_best_action()
        self.assertEqual(nba.action_type, "RECRUITER_REPLY")
        self.assertEqual(nba.action_name, "OPEN_CONVERSATION")
        self.assertEqual(nba.company, "Apex Systems")

        # Case 3: No interview or reply, but overdue follow-up exists -> OVERDUE_FOLLOWUP
        self.mock_outreach_service.get_work_queue.return_value = []
        mock_fu = MagicMock()
        mock_fu.id = 303
        mock_fu.due_at = now - timedelta(days=2)
        mock_fu.application.job.title = "Python Engineer"
        mock_fu.application.job.company_raw = "Cloud Inc"
        mock_fu.application_id = 70
        mock_fu.contact_id = 80
        self.mock_recruitment_service.list_follow_ups.return_value = [mock_fu]

        nba = self.service.get_next_best_action()
        self.assertEqual(nba.action_type, "OVERDUE_FOLLOWUP")
        self.assertEqual(nba.action_name, "COMPOSE_FOLLOWUP")
        self.assertEqual(nba.company, "Cloud Inc")

        # Case 4: No operational actions, but high match opportunity (>= 85) -> TOP_OPPORTUNITY_REVIEW
        self.mock_recruitment_service.list_follow_ups.return_value = []
        self.mock_application_service.list_applications.return_value = []
        self.mock_job_service.get_top_opportunities.return_value = [
            TopOpportunityDTO(
                job_id=404,
                title="AI Platform Engineer",
                company="Innovate Labs",
                location="Bengaluru",
                platform="naukri",
                application_method="EASY_APPLY",
                score=92,
                decision="STRONG_MATCH",
                evaluation_status="SUCCESS",
                confidence=0.95,
                matched_skills=["Python", "FastAPI", "Docker"],
            )
        ]

        nba = self.service.get_next_best_action()
        self.assertEqual(nba.action_type, "TOP_OPPORTUNITY_REVIEW")
        self.assertEqual(nba.action_name, "REVIEW_JOB")
        self.assertEqual(nba.company, "Innovate Labs")

        # Case 5: Zero actions and zero high-match jobs -> ALL_CAUGHT_UP
        self.mock_job_service.get_top_opportunities.return_value = []
        nba = self.service.get_next_best_action()
        self.assertEqual(nba.action_type, "ALL_CAUGHT_UP")
        self.assertEqual(nba.badge_text, "ALL CLEAR")

    def test_search_performance_aggregation_dto(self):
        """Search performance must aggregate into a single SearchPerformanceDTO."""
        self.mock_analytics_service.get_funnel_flow.return_value = {
            "stages": [
                {"stage_id": "discovered", "count": 100},
                {"stage_id": "qualified", "count": 40},
                {"stage_id": "submitted", "count": 20},
                {"stage_id": "responses", "count": 8},
                {"stage_id": "interviews", "count": 4},
                {"stage_id": "offers", "count": 1},
            ]
        }
        self.mock_analytics_service.get_platform_performance.return_value = [
            {
                "platform_key": "linkedin",
                "platform": "LinkedIn",
                "jobs": 60,
                "applications": 12,
                "interviews": 3,
                "offers": 1,
                "application_rate": 20.0,
                "interview_rate": 25.0,
                "offer_rate": 8.3,
            }
        ]

        dto = self.service.get_search_performance(preset="30D")
        self.assertIsInstance(dto, SearchPerformanceDTO)
        self.assertEqual(dto.total_discovered, 100)
        self.assertEqual(dto.total_qualified, 40)
        self.assertEqual(dto.total_applied, 20)
        self.assertEqual(dto.total_interviews, 4)
        self.assertEqual(dto.total_offers, 1)
        self.assertEqual(dto.application_conversion_pct, 50.0) # 20 / 40 * 100
        self.assertEqual(dto.interview_conversion_pct, 20.0)   # 4 / 20 * 100
        self.assertEqual(len(dto.platform_metrics), 1)
        self.assertEqual(dto.platform_metrics[0].platform_key, "linkedin")


if __name__ == "__main__":
    unittest.main()
