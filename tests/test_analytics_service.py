"""Exhaustive unit test suite verifying recruitment analytics semantics, cohorts, and boundary conditions."""

from datetime import datetime, timedelta, timezone
import os
import shutil
import tempfile
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.models import Application, Communication, Interview, Job, JobEvaluation, Offer
from app.db.session import configure_sqlite_pragmas
from app.services.analytics_service import (
    ACTIVE_AGING_STATUSES,
    AnalyticsFilter,
    AnalyticsService,
    PROGRESSED_STATUSES,
    SUBMITTED_STATUSES,
    get_local_date_bounds,
)
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.recruitment_service import RecruitmentService


class TestAnalyticsServiceSemantics(unittest.TestCase):
    """Rigorous semantic and mathematical validation of AnalyticsService."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "analytics_semantic_test.db")
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
        self.analytics_service = AnalyticsService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_pre_submission_and_error_states_strictly_excluded(self):
        """Verifies FAILED, UNKNOWN, MANUAL_REQUIRED, EXTERNAL, SKIPPED, and APPLYING are NOT counted as submitted."""
        job, _ = self.job_service.create_manual_job(title="Cloud Architect", company="Amazon")
        
        # Create applications in pre-submission and error states
        error_states = ["APPLYING", "FAILED", "UNKNOWN", "MANUAL_REQUIRED", "EXTERNAL"]
        for st in error_states:
            j, _ = self.job_service.create_manual_job(title=f"Role {st}", company="Amazon")
            self.app_service.create_application(job_id=j.id, status=st)

        f = AnalyticsFilter(date_preset="ALL")
        summary = self.analytics_service.get_summary_metrics(f)
        self.assertEqual(summary["submitted_applications"].value, 0)
        self.assertEqual(summary["response_rate"], 0.0)

    def test_genuine_submitted_statuses_counted(self):
        """Verifies applications in SUBMITTED_STATUSES with applied_at timestamps are counted."""
        statuses_to_test = ["SUBMITTED", "UNDER_REVIEW", "SHORTLISTED", "INTERVIEW", "OFFER", "REJECTED", "WITHDRAWN"]
        for st in statuses_to_test:
            j, _ = self.job_service.create_manual_job(title=f"Role {st}", company="Google")
            app, _ = self.app_service.create_application(job_id=j.id, status="SUBMITTED")
            if st != "SUBMITTED":
                self.app_service.transition_status(app.id, st)

        f = AnalyticsFilter(date_preset="ALL")
        summary = self.analytics_service.get_summary_metrics(f)
        self.assertEqual(summary["submitted_applications"].value, len(statuses_to_test))

    def test_direct_recruiter_response_vs_pipeline_progression(self):
        """Verifies direct recruiter responses require inbound Communication, distinct from stage progression."""
        j1, _ = self.job_service.create_manual_job(title="Backend Dev", company="Meta")
        j2, _ = self.job_service.create_manual_job(title="Frontend Dev", company="Apple")

        app1, _ = self.app_service.create_application(job_id=j1.id, status="SUBMITTED")
        app2, _ = self.app_service.create_application(job_id=j2.id, status="SUBMITTED")

        # app1 receives an actual inbound communication from recruiter
        with self.Session() as session:
            comm = Communication(
                application_id=app1.id,
                type="EMAIL",
                direction="INBOUND",
                occurred_at=utc_now(),
                subject="Interview invitation",
            )
            session.add(comm)
            session.commit()

        # app2 only advanced to UNDER_REVIEW (stage progression proxy, NO inbound communication)
        self.app_service.transition_status(app2.id, "UNDER_REVIEW")

        f = AnalyticsFilter(date_preset="ALL")
        summary = self.analytics_service.get_summary_metrics(f)
        
        self.assertEqual(summary["submitted_applications"].value, 2)
        # Direct Recruiter Response: only app1
        self.assertEqual(summary["direct_responses"], 1)
        self.assertEqual(summary["response_rate"], 50.0)
        # Pipeline Progression: app2 advanced to UNDER_REVIEW
        self.assertEqual(summary["progressed_applications"], 1)
        self.assertEqual(summary["progression_rate"], 50.0)

    def test_distinct_interview_and_offer_counting(self):
        """Verifies multiple interview rounds and multiple offers on one application count as exactly 1."""
        j, _ = self.job_service.create_manual_job(title="AI Engineer", company="OpenAI")
        app, _ = self.app_service.create_application(job_id=j.id, status="SUBMITTED")

        # 3 interview rounds
        dt = utc_now() + timedelta(days=2)
        self.recruitment_service.schedule_interview(app.id, round_name="Round 1", scheduled_at=dt)
        self.recruitment_service.schedule_interview(app.id, round_name="Round 2", scheduled_at=dt)
        self.recruitment_service.schedule_interview(app.id, round_name="Round 3", scheduled_at=dt)

        # 2 offer updates
        self.recruitment_service.record_offer(app.id, offered_ctc=2500000)
        self.recruitment_service.record_offer(app.id, offered_ctc=2800000)

        f = AnalyticsFilter(date_preset="ALL")
        summary = self.analytics_service.get_summary_metrics(f)
        self.assertEqual(summary["submitted_applications"].value, 1)
        self.assertEqual(summary["interviewed_applications"], 1)
        self.assertEqual(summary["offer_applications"], 1)
        self.assertEqual(summary["interview_rate"], 100.0)
        self.assertEqual(summary["offer_rate"], 100.0)

    def test_decoupled_discovery_vs_application_cohorts(self):
        """Verifies jobs discovered in an earlier period do not falsely inflate current application cohorts."""
        now = utc_now()
        # Job discovered 40 days ago
        j, _ = self.job_service.create_manual_job(title="Legacy Lead", company="Oracle")
        with self.Session() as session:
            db_j = session.get(Job, j.id)
            db_j.created_at = now - timedelta(days=40)
            session.commit()

        # Application submitted 5 days ago (within 7D window)
        app, _ = self.app_service.create_application(job_id=j.id, status="SUBMITTED")
        with self.Session() as session:
            db_app = session.get(Application, app.id)
            db_app.applied_at = now - timedelta(days=5)
            session.commit()

        # Filter: Last 7 days
        start_7d = now - timedelta(days=7)
        f_7d = AnalyticsFilter(start_date=start_7d, end_date=now)
        funnel = self.analytics_service.get_funnel_flow(f_7d)

        # Job is NOT in discovery cohort (discovered 40 days ago)
        self.assertEqual(funnel["discovery_cohort_count"], 0)
        # Application IS in application cohort (applied 5 days ago)
        self.assertEqual(funnel["application_cohort_count"], 1)

    def test_period_comparison_unavailable_when_no_prior_data(self):
        """Verifies comparison_available is False and reason is clear when prior period has zero data."""
        now = utc_now()
        j, _ = self.job_service.create_manual_job(title="Senior Dev", company="Uber")
        app, _ = self.app_service.create_application(job_id=j.id, status="SUBMITTED")

        # Bounded 7-day period (allow 1 minute buffer for fresh creation)
        start_date = now - timedelta(days=7)
        end_date = utc_now() + timedelta(minutes=1)
        f = AnalyticsFilter(start_date=start_date, end_date=end_date)
        summary = self.analytics_service.get_summary_metrics(f)

        comp = summary["submitted_applications"]
        self.assertEqual(comp.value, 1)
        self.assertFalse(comp.comparison_available)
        self.assertEqual(comp.reason, "No previous-period data")
        self.assertIsNone(comp.pct_change)

    def test_response_time_stats_source_tagging_and_insufficient_data(self):
        """Verifies response latency returns INSUFFICIENT_DATA when sample < 3, and tags COMMUNICATION when >= 3."""
        now = utc_now()
        # 1. Zero to 2 samples -> INSUFFICIENT_DATA
        j1, _ = self.job_service.create_manual_job(title="Role 1", company="C1")
        app1, _ = self.app_service.create_application(job_id=j1.id, status="SUBMITTED")
        with self.Session() as session:
            comm = Communication(
                application_id=app1.id,
                type="EMAIL",
                direction="INBOUND",
                occurred_at=now + timedelta(days=2),
            )
            session.add(comm)
            session.commit()

        f = AnalyticsFilter(date_preset="ALL")
        stats = self.analytics_service.get_response_time_stats(f)
        self.assertFalse(stats.has_sufficient_data)
        self.assertEqual(stats.source_type, "INSUFFICIENT_DATA")

        # 2. Add 2 more samples with inbound communications -> COMMUNICATION
        for i in [2, 3]:
            j, _ = self.job_service.create_manual_job(title=f"Role {i}", company=f"C{i}")
            app, _ = self.app_service.create_application(job_id=j.id, status="SUBMITTED")
            with self.Session() as session:
                comm = Communication(
                    application_id=app.id,
                    type="EMAIL",
                    direction="INBOUND",
                    occurred_at=now + timedelta(days=i),
                )
                session.add(comm)
                session.commit()

        stats3 = self.analytics_service.get_response_time_stats(f)
        self.assertTrue(stats3.has_sufficient_data)
        self.assertEqual(stats3.source_type, "COMMUNICATION")
        self.assertEqual(stats3.sample_count, 3)
        self.assertIsNotNone(stats3.avg_days)

    def test_application_aging_buckets_and_terminal_exclusion(self):
        """Verifies elapsed days bucket assignment and exclusion of closed/terminal applications."""
        now = utc_now()
        # Active application applied 5 days ago -> 3–7 days
        j1, _ = self.job_service.create_manual_job(title="Active Dev", company="C1")
        app1, _ = self.app_service.create_application(job_id=j1.id, status="SUBMITTED")
        with self.Session() as session:
            db_app1 = session.get(Application, app1.id)
            db_app1.applied_at = now - timedelta(days=5)
            session.commit()

        # Terminal application applied 40 days ago, but REJECTED -> must NOT be in active aging
        j2, _ = self.job_service.create_manual_job(title="Closed Dev", company="C2")
        app2, _ = self.app_service.create_application(job_id=j2.id, status="SUBMITTED")
        self.app_service.transition_status(app2.id, "REJECTED")
        with self.Session() as session:
            db_app2 = session.get(Application, app2.id)
            db_app2.applied_at = now - timedelta(days=40)
            session.commit()

        f = AnalyticsFilter(date_preset="ALL")
        aging = self.analytics_service.get_aging_distribution(f)
        self.assertEqual(aging["3–7 days"], 1)
        self.assertEqual(aging["30–60 days"], 0)
        self.assertEqual(aging["60+ days"], 0)

    def test_application_centric_role_and_company_breakdown(self):
        """Verifies role and company analytics query submitted applications, not unapplied jobs."""
        # Unapplied job (Discovered only)
        self.job_service.create_manual_job(title="Unapplied Role", company="Phantom Corp")

        # Applied job
        j_applied, _ = self.job_service.create_manual_job(title="Senior Python Architect", company="Target Corp")
        self.app_service.create_application(job_id=j_applied.id, status="SUBMITTED")

        f = AnalyticsFilter(date_preset="ALL")
        breakdown = self.analytics_service.get_role_company_breakdown(f)

        roles = [r["title"] for r in breakdown["roles"]]
        comps = [c["company"] for c in breakdown["companies"]]

        self.assertIn("Senior Python Architect", roles)
        self.assertNotIn("Unapplied Role", roles)
        self.assertIn("Target Corp", comps)
        self.assertNotIn("Phantom Corp", comps)

    def test_method_distribution_and_csv_export(self):
        """Verifies application method breakdown and CSV export formatting."""
        j, _ = self.job_service.create_manual_job(title="Easy Apply Engineer", company="Tesla")
        self.app_service.create_application(job_id=j.id, status="SUBMITTED", application_type="EASY_APPLY")

        f = AnalyticsFilter(date_preset="ALL")
        methods = self.analytics_service.get_method_distribution(f)
        easy_method = next(m for m in methods if m["method_key"] == "EASY_APPLY")
        self.assertEqual(easy_method["applications"], 1)

        csv_text = self.analytics_service.export_to_csv(f)
        self.assertIn("# JobPilot Recruitment Analytics Export", csv_text)
        self.assertIn("Easy Apply Engineer", csv_text)
        self.assertIn("Tesla", csv_text)


if __name__ == "__main__":
    unittest.main()
