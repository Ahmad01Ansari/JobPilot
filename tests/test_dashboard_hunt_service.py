"""Unit tests for DashboardService and Today's Job Hunt prioritization and aggregation."""

from datetime import datetime, timedelta, timezone
import os
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.session import configure_sqlite_pragmas
from app.services.application_service import ApplicationService
from app.services.dashboard_service import DashboardService
from app.services.dto.dashboard_dto import (
    DailyProgressDTO,
    DashboardSnapshotDTO,
    ReadinessSummaryDTO,
    TodaysHuntItemDTO,
    TopOpportunityDTO,
)
from app.services.dto.qualification_dto import QualificationResultDTO
from app.services.dto.qualification_enums import EvaluationStatus, QualificationDecision
from app.services.job_qualification_service import JobQualificationService
from app.services.job_service import JobService
from app.services.recruitment_service import RecruitmentService


class TestDashboardHuntService(unittest.TestCase):
    """Verifies Today's Job Hunt prioritization, deduplication, and progress aggregation."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_hunt.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)
        self.recruitment_service = RecruitmentService(session_factory=self.Session)
        self.qual_service = JobQualificationService(session_factory=self.Session)
        self.dashboard_service = DashboardService(
            session_factory=self.Session,
            job_service=self.job_service,
            recruitment_service=self.recruitment_service,
            application_service=self.app_service,
        )

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_empty_database_snapshot(self):
        """Verifies clean, non-crashing empty snapshot on a fresh database."""
        snapshot = self.dashboard_service.get_dashboard_snapshot()
        self.assertIsInstance(snapshot, DashboardSnapshotDTO)
        self.assertEqual(len(snapshot.hunt_items), 0)
        self.assertEqual(len(snapshot.top_opportunities), 0)
        self.assertEqual(snapshot.daily_progress.discovered_today, 0)
        self.assertEqual(snapshot.daily_progress.qualified_today, 0)
        self.assertFalse(snapshot.readiness.profile_complete)

    def test_top_opportunities_selection(self):
        """Verifies unapplied jobs with STRONG_MATCH and GOOD_MATCH are surfaced in score order."""
        # 1. Create 3 jobs
        j1, _ = self.job_service.create_manual_job(title="AI Lead", company="Alpha Tech")
        j2, _ = self.job_service.create_manual_job(title="Python Engineer", company="Beta Corp")
        j3, _ = self.job_service.create_manual_job(title="Junior QA", company="Gamma Ltd")

        # 2. Record qualification evaluations
        from app.repositories.job_evaluation_repo import JobEvaluationRepository
        with self.Session() as s:
            repo = JobEvaluationRepository(s)
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=j1.id,
                    score=92,
                    decision=QualificationDecision.STRONG_MATCH,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    matched_skills=["Python", "PyTorch"],
                )
            )
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=j2.id,
                    score=84,
                    decision=QualificationDecision.GOOD_MATCH,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    matched_skills=["Django"],
                )
            )
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=j3.id,
                    score=35,
                    decision=QualificationDecision.REJECTED,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    matched_skills=[],
                )
            )
            s.commit()

        # 3. Query top opportunities
        opps = self.job_service.get_top_opportunities(limit=5)
        self.assertEqual(len(opps), 2)  # j1 and j2; j3 is REJECTED
        self.assertEqual(opps[0].job_id, j1.id)
        self.assertEqual(opps[0].score, 92)
        self.assertEqual(opps[0].decision, "STRONG_MATCH")
        self.assertEqual(opps[0].recommended_action, "REVIEW_JOB")

        self.assertEqual(opps[1].job_id, j2.id)
        self.assertEqual(opps[1].score, 84)

        # 4. If j1 is applied to, it must disappear from top opportunities
        self.app_service.create_application(job_id=j1.id, status="SUBMITTED")
        opps_after_apply = self.job_service.get_top_opportunities(limit=5)
        self.assertEqual(len(opps_after_apply), 1)
        self.assertEqual(opps_after_apply[0].job_id, j2.id)

    def test_daily_progress_verified_metrics(self):
        """Verifies daily progress metrics count only authoritative timestamps today."""
        now = utc_now()

        # Discovered today
        j1, _ = self.job_service.create_manual_job(title="Dev 1", company="Company 1")
        j2, _ = self.job_service.create_manual_job(title="Dev 2", company="Company 2")

        # Qualified today
        from app.repositories.job_evaluation_repo import JobEvaluationRepository
        with self.Session() as s:
            repo = JobEvaluationRepository(s)
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=j1.id,
                    score=85,
                    decision=QualificationDecision.GOOD_MATCH,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    evaluated_at=now,
                )
            )
            s.commit()

        # Applications submitted today
        app1, _ = self.app_service.create_application(job_id=j1.id, status="SUBMITTED")

        # Outreach sent today
        self.recruitment_service.log_communication(
            type_="EMAIL",
            direction="OUTBOUND",
            application_id=app1.id,
            subject="Application Follow-up",
            occurred_at=now,
        )

        # Follow-up completed today
        fu, _ = self.recruitment_service.create_follow_up(
            due_at=now,
            application_id=app1.id,
            notes="Call recruiter",
        )
        self.recruitment_service.complete_follow_up(fu.id, status="COMPLETED")

        # Verify progress
        prog = self.dashboard_service.get_todays_progress()
        self.assertEqual(prog.discovered_today, 2)
        self.assertEqual(prog.qualified_today, 1)
        self.assertEqual(prog.applications_submitted_today, 1)
        self.assertEqual(prog.outreach_sent_today, 1)
        self.assertEqual(prog.followups_completed_today, 1)

    def test_discovered_and_qualified_today_not_equal_totals(self):
        """Strictly verifies that today's metrics NEVER equal lifetime totals when past data exists."""
        from app.db.models import Job
        now = utc_now()
        past_date = now - timedelta(days=5)

        # 1. Historical job from 5 days ago
        past_job, _ = self.job_service.create_manual_job(title="Legacy Dev", company="Old Corp")
        with self.Session() as s:
            j = s.get(Job, past_job.id)
            j.created_at = past_date
            s.commit()
            past_job_id = past_job.id

        # 2. Modern job discovered today
        today_job, _ = self.job_service.create_manual_job(title="Modern Dev", company="New Corp")

        # 3. Two evaluations run today: one qualified GOOD_MATCH, one REJECTED
        from app.repositories.job_evaluation_repo import JobEvaluationRepository
        with self.Session() as s:
            repo = JobEvaluationRepository(s)
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=today_job.id,
                    score=85,
                    decision=QualificationDecision.GOOD_MATCH,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    evaluated_at=now,
                )
            )
            repo.record_qualification(
                QualificationResultDTO(
                    job_id=past_job_id,
                    score=20,
                    decision=QualificationDecision.REJECTED,
                    evaluation_status=EvaluationStatus.SUCCESS,
                    evaluated_at=now,
                )
            )
            s.commit()

        # 4. Check metrics
        prog = self.dashboard_service.get_todays_progress()
        funnel = self.dashboard_service.get_pipeline_funnel()

        # Total jobs in database is 2, but only 1 discovered today!
        self.assertEqual(prog.discovered_today, 1)
        self.assertEqual(funnel["total_jobs"], 2)
        self.assertNotEqual(prog.discovered_today, funnel["total_jobs"])

        # 2 evaluations occurred today, but only 1 actually QUALIFIED!
        self.assertEqual(prog.qualified_today, 1)

    def test_todays_hunt_prioritization_and_deduplication(self):
        """Verifies deterministic prioritization and deduplication by application_id."""
        now = utc_now()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)

        # Create two jobs and applications
        j1, _ = self.job_service.create_manual_job(title="Backend Dev", company="Uber")
        app1, _ = self.app_service.create_application(job_id=j1.id, status="UNDER_REVIEW")

        j2, _ = self.job_service.create_manual_job(title="Frontend Dev", company="Meta")
        app2, _ = self.app_service.create_application(job_id=j2.id, status="UNDER_REVIEW")

        # On app1: Schedule an interview for today (Priority 1) AND an overdue follow-up (Priority 2)
        self.recruitment_service.schedule_interview(
            application_id=app1.id,
            round_name="Technical",
            scheduled_at=now,
            mode="VIRTUAL",
        )
        self.recruitment_service.create_follow_up(
            due_at=yesterday,
            application_id=app1.id,
            notes="Overdue note",
        )

        # On app2: Schedule an overdue follow-up (Priority 2)
        self.recruitment_service.create_follow_up(
            due_at=yesterday,
            application_id=app2.id,
            notes="Overdue follow-up for Meta",
        )

        items = self.dashboard_service.get_todays_job_hunt_items(limit=10)

        # Because app1 has both Interview Today (Priority 1) and Overdue Follow-up (Priority 2),
        # deduplication must ensure app1 produces only ONE item: the Interview Today (Priority 1).
        # And secondary actions are recorded in the subtitle ("+1 more action").
        self.assertGreaterEqual(len(items), 2)

        # First item should be Interview Today for app1
        self.assertEqual(items[0].priority, 1)
        self.assertEqual(items[0].item_type, "INTERVIEW_TODAY")
        self.assertEqual(items[0].company, "Uber")
        self.assertIn("+1 more action", items[0].subtitle)
        self.assertEqual(items[0].recommended_action, "PREPARE_INTERVIEW")

        # Second item should be Overdue Follow-up for app2
        self.assertEqual(items[1].priority, 2)
        self.assertEqual(items[1].item_type, "OVERDUE_FOLLOWUP")
        self.assertEqual(items[1].company, "Meta")
        self.assertEqual(items[1].recommended_action, "COMPOSE_FOLLOWUP")

    def test_main_window_action_routing(self):
        """Verifies MainWindow._on_dashboard_action_requested navigates and triggers inspections."""
        from unittest.mock import MagicMock
        from app.ui.main_window import MainWindow

        # Create a mock MainWindow with required attributes
        mw = MagicMock()
        mw.view_instances = {
            "jobs": MagicMock(),
            "outreach": MagicMock(),
            "interviews": MagicMock(),
            "followups": MagicMock(),
            "applications": MagicMock(),
        }
        # Bind the unbound method to mw
        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_JOB", {"job_id": 42})
        mw.navigate_to.assert_called_with("jobs")
        mw.view_instances["jobs"].inspect_job_by_id.assert_called_with(42)

        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_OUTREACH", {"application_id": 10})
        mw.navigate_to.assert_called_with("outreach")
        mw.view_instances["outreach"].select_conversation.assert_called_with(10)

        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_INTERVIEW", {"interview_id": 7})
        mw.navigate_to.assert_called_with("interviews")
        mw.view_instances["interviews"].inspect_interview_by_id.assert_called_with(7)

        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_FOLLOWUP", {"followup_id": 99})
        mw.navigate_to.assert_called_with("followups")
        mw.view_instances["followups"].highlight_follow_up.assert_called_with(99)

        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_APPLICATION", {"application_id": 88})
        mw.navigate_to.assert_called_with("applications")
        mw.view_instances["applications"].inspect_application_by_id.assert_called_with(88)

        MainWindow._on_dashboard_action_requested(mw, "NAVIGATE_AUTOMATION", {})
        mw.navigate_to.assert_called_with("automation")
