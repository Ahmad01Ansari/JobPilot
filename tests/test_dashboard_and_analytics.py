"""Unit, integration, and UI test suite for DashboardService, AnalyticsService, and Phase 12 views."""

from datetime import datetime, timedelta
import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.session import configure_sqlite_pragmas
from app.services.analytics_service import AnalyticsService
from app.services.application_service import ApplicationService
from app.services.dashboard_service import ActivityEvent, DashboardService
from app.services.job_service import JobService
from app.services.recruitment_service import RecruitmentService


class TestDashboardAndAnalyticsServices(unittest.TestCase):
    """Unit tests for dashboard aggregation and conversion analytics."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase12_test.db")
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
        self.dashboard_service = DashboardService(session_factory=self.Session)
        self.analytics_service = AnalyticsService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_funnel_zero_submissions_and_jobs(self):
        """Verifies safe 0.0% handling when no applications or jobs exist."""
        funnel = self.analytics_service.get_funnel_metrics()
        self.assertEqual(funnel["total_jobs"], 0)
        self.assertEqual(funnel["submitted_applications"], 0)
        self.assertEqual(funnel["application_rate"], 0.0)
        self.assertEqual(funnel["response_rate"], 0.0)
        self.assertEqual(funnel["interview_rate"], 0.0)
        self.assertEqual(funnel["offer_rate"], 0.0)

    def test_distinct_application_interviews_conversion(self):
        """Verifies multiple interview rounds on 1 application count as 1 interviewed application."""
        # 1. Job and Application
        job, _ = self.job_service.create_manual_job(title="QA Engineer", company="Stripe")
        app, _ = self.app_service.create_application(job_id=job.id, status="SUBMITTED")

        # 2. Schedule 3 interview rounds on the SAME application
        dt = utc_now() + timedelta(days=1)
        self.recruitment_service.schedule_interview(application_id=app.id, round_name="HR", scheduled_at=dt)
        self.recruitment_service.schedule_interview(application_id=app.id, round_name="Tech", scheduled_at=dt)
        self.recruitment_service.schedule_interview(application_id=app.id, round_name="Manager", scheduled_at=dt)

        # 3. Analytics verification
        funnel = self.analytics_service.get_funnel_metrics()
        self.assertEqual(funnel["submitted_applications"], 1)
        self.assertEqual(funnel["interviewed_applications"], 1)  # Distinct application count
        self.assertEqual(funnel["interview_rate"], 100.0)

    def test_distinct_application_offers_conversion(self):
        """Verifies multiple offer updates on 1 application count as 1 offer application."""
        job, _ = self.job_service.create_manual_job(title="DevOps", company="Netflix")
        app, _ = self.app_service.create_application(job_id=job.id, status="SUBMITTED")

        self.recruitment_service.record_offer(application_id=app.id, offered_ctc=2000000)
        self.recruitment_service.record_offer(application_id=app.id, offered_ctc=2200000)

        funnel = self.analytics_service.get_funnel_metrics()
        self.assertEqual(funnel["offer_applications"], 1)
        self.assertEqual(funnel["offer_rate"], 100.0)

    def test_response_rate_distinct_applications(self):
        """Verifies response rate counts distinct applications advancing beyond SUBMITTED."""
        job1, _ = self.job_service.create_manual_job(title="J1", company="C1")
        job2, _ = self.job_service.create_manual_job(title="J2", company="C2")

        app1, _ = self.app_service.create_application(job_id=job1.id, status="SUBMITTED")
        app2, _ = self.app_service.create_application(job_id=job2.id, status="SUBMITTED")

        # Advance app1 to UNDER_REVIEW
        self.app_service.transition_status(app1.id, "UNDER_REVIEW")

        funnel = self.analytics_service.get_funnel_metrics()
        self.assertEqual(funnel["submitted_applications"], 2)
        self.assertEqual(funnel["responded_applications"], 1)
        self.assertEqual(funnel["response_rate"], 50.0)

    def test_stage_distribution_sums_correctly(self):
        """Verifies stage breakdown matches total application records."""
        job1, _ = self.job_service.create_manual_job(title="J1", company="C1")
        job2, _ = self.job_service.create_manual_job(title="J2", company="C2")

        self.app_service.create_application(job_id=job1.id, status="SUBMITTED")
        self.app_service.create_application(job_id=job2.id, status="APPLYING")

        stages = self.analytics_service.get_stage_distribution()
        total_in_stages = sum(stages.values())
        self.assertEqual(total_in_stages, 2)
        self.assertEqual(stages["SUBMITTED"], 1)
        self.assertEqual(stages["APPLYING"], 1)

    def test_recent_activity_sorted_descending(self):
        """Verifies activity events are ordered strictly by timestamp descending."""
        self.job_service.create_manual_job(title="Older Job", company="Acme")
        job_new, _ = self.job_service.create_manual_job(title="Newer Job", company="Beta")

        app, _ = self.app_service.create_application(job_id=job_new.id, status="SUBMITTED")

        events = self.dashboard_service.get_recent_activity(limit=10)
        self.assertGreaterEqual(len(events), 2)

        # Check descending order
        for i in range(len(events) - 1):
            self.assertGreaterEqual(events[i].timestamp, events[i + 1].timestamp)

    def test_date_range_filtering(self):
        """Verifies start_date and end_date filter boundaries."""
        self.job_service.create_manual_job(title="Test Job", company="Acme")

        past_start = utc_now() - timedelta(days=1)
        past_end = utc_now() + timedelta(days=1)
        metrics = self.dashboard_service.get_summary_metrics(start_date=past_start, end_date=past_end)
        self.assertEqual(metrics["total_jobs"], 1)

        # Future filter returns 0
        future_start = utc_now() + timedelta(days=5)
        future_metrics = self.dashboard_service.get_summary_metrics(start_date=future_start)
        self.assertEqual(future_metrics["total_jobs"], 0)


class TestPhase12Views(unittest.TestCase):
    """Headless PySide6 UI tests for DashboardView and AnalyticsView."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase12_view_test.db")
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
        self.dashboard_service = DashboardService(session_factory=self.Session)
        self.analytics_service = AnalyticsService(session_factory=self.Session)

        # Seed initial job and application
        job, _ = self.job_service.create_manual_job(title="Software Engineer", company="Microsoft")
        self.app_service.create_application(job_id=job.id, status="SUBMITTED")

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dashboard_view_rendering(self):
        """Verifies DashboardView renders metric cards, platform breakdown, and activity stream."""
        from app.ui.views.dashboard_view import DashboardView

        view = DashboardView(service=self.dashboard_service)
        view.show()

        self.assertEqual(view.plat_container.count(), 4)  # 4 platforms
        self.assertIn("Dashboard Overview", view.header.title_label.text())

    def test_analytics_view_rendering(self):
        """Verifies AnalyticsView renders conversion cards and platform table."""
        from app.ui.views.analytics_view import AnalyticsView

        view = AnalyticsView(service=self.analytics_service)
        view.show()

        self.assertGreaterEqual(view.table.rowCount(), 4)  # platform rows including foundit
        self.assertIn("Application Analytics", view.header.title_label.text())


if __name__ == "__main__":
    unittest.main()
