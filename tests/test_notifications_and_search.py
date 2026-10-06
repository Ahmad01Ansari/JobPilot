"""Unit and integration tests for Phase 15: Global Search and Desktop Notifications."""

from datetime import datetime, timedelta, timezone
import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.models import (
    Application,
    Company,
    Contact,
    FollowUp,
    Interview,
    Job,
    User,
    generate_job_fingerprint,
)
from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationRunResult,
    AutomationState,
    InterventionType,
)
from app.services.notification_service import NotificationService
from app.services.search_service import GlobalSearchResult, SearchResultItem, SearchService
from app.ui.main_window import MainWindow
from app.ui.top_bar import TopBar
from app.ui.widgets.search_dialog import GlobalSearchDialog


class TestSearchService(unittest.TestCase):
    """Test suite for unified multi-entity SearchService."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.service = SearchService(session_factory=self.SessionFactory)
        self._seed_data()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def _seed_data(self):
        with self.SessionFactory() as session:
            # 1. Companies
            google = Company(
                name="Google LLC",
                normalized_name="google",
                industry="Technology",
                location="Mountain View, CA",
                website="https://google.com",
                notes="Search and cloud giant",
            )
            openai = Company(
                name="OpenAI Corp",
                normalized_name="openai",
                industry="Artificial Intelligence",
                location="San Francisco, CA",
                website="https://openai.com",
                notes="Frontier AI laboratory",
            )
            session.add_all([google, openai])
            session.flush()

            # 2. Jobs
            job1 = Job(
                company_id=google.id,
                platform="linkedin",
                title="Staff Machine Learning Engineer",
                company_raw="Google LLC",
                location="Mountain View, CA",
                source_url="https://linkedin.com/jobs/view/101",
                description="Lead PyTorch machine learning infrastructure and LLM optimization.",
                job_fingerprint=generate_job_fingerprint(
                    "linkedin", "Google LLC", "Staff Machine Learning Engineer", "Mountain View, CA"
                ),
            )
            job2 = Job(
                company_id=openai.id,
                platform="naukri",
                title="Senior Python Backend Architect",
                company_raw="OpenAI Corp",
                location="San Francisco, CA",
                source_url="https://naukri.com/job-listings-202",
                description="Design high-throughput FastAPI and Kubernetes inference infrastructure.",
                job_fingerprint=generate_job_fingerprint(
                    "naukri", "OpenAI Corp", "Senior Python Backend Architect", "San Francisco, CA"
                ),
            )
            session.add_all([job1, job2])
            session.flush()

            # 3. Applications
            app1 = Application(
                job_id=job1.id,
                status="SUBMITTED",
                notes="Applied via Easy Apply on LinkedIn",
                applied_at=utc_now(),
            )
            app2 = Application(
                job_id=job2.id,
                status="INTERVIEW",
                notes="Invited for technical loop",
                applied_at=utc_now() - timedelta(days=2),
            )
            session.add_all([app1, app2])
            session.flush()

            # 4. Contacts
            contact1 = Contact(
                company_id=google.id,
                name="Sarah Connor",
                designation="Lead AI Recruiter",
                email="sarah.connor@google.com",
                phone="+1-555-0199",
                notes="Contacted regarding ML infra roles",
            )
            contact2 = Contact(
                company_id=openai.id,
                name="Marcus Brody",
                designation="Engineering Director",
                email="marcus@openai.com",
                notes="Technical hiring manager",
            )
            session.add_all([contact1, contact2])
            session.flush()

            # 5. Interviews
            int1 = Interview(
                application_id=app1.id,
                round_number=1,
                round_name="Technical Coding",
                scheduled_at=utc_now() + timedelta(hours=3),
                interviewer="Dr. Emily Watson",
                mode="VIRTUAL",
                meeting_link="https://meet.google.com/xyz-abc",
                status="SCHEDULED",
                notes="Focus on algorithm complexity and graphs",
            )
            int2 = Interview(
                application_id=app2.id,
                round_number=2,
                round_name="System Architecture",
                scheduled_at=utc_now() + timedelta(days=1),
                interviewer="David Hilbert",
                mode="VIRTUAL",
                meeting_link="https://zoom.us/j/123456",
                status="SCHEDULED",
                notes="Distributed cache and queue design",
            )
            session.add_all([int1, int2])
            session.commit()

    def test_search_all_entities_match(self):
        """Querying 'Google' should return matches across company, job, application, and contact."""
        res = self.service.search("Google")
        self.assertGreaterEqual(res.total_count, 4)
        entity_types = {item.entity_type for item in res.items}
        self.assertIn("company", entity_types)
        self.assertIn("job", entity_types)
        self.assertIn("application", entity_types)
        self.assertIn("contact", entity_types)

    def test_search_by_skill_token(self):
        """Querying 'PyTorch' should match the ML engineer job."""
        res = self.service.search("PyTorch")
        self.assertGreaterEqual(res.total_count, 1)
        job_titles = [item.title for item in res.items if item.entity_type == "job"]
        self.assertIn("Staff Machine Learning Engineer", job_titles)

    def test_search_category_filter_job_only(self):
        """Specifying category='job' returns only job entities."""
        res = self.service.search("Google", category="job")
        for item in res.items:
            self.assertEqual(item.entity_type, "job")
            self.assertEqual(item.target_page, "jobs")

    def test_search_category_filter_company_only(self):
        """Specifying category='company' returns only companies."""
        res = self.service.search("OpenAI", category="company")
        self.assertEqual(res.total_count, 1)
        self.assertEqual(res.items[0].entity_type, "company")
        self.assertEqual(res.items[0].title, "OpenAI Corp")

    def test_search_category_filter_contact_only(self):
        """Specifying category='contact' returns only recruiter contacts."""
        res = self.service.search("Sarah", category="contact")
        self.assertEqual(res.total_count, 1)
        self.assertEqual(res.items[0].entity_type, "contact")
        self.assertIn("sarah.connor@google.com", res.items[0].subtitle)

    def test_search_category_filter_interview_only(self):
        """Specifying category='interview' returns interview rounds."""
        res = self.service.search("Architecture", category="interview")
        self.assertEqual(res.total_count, 1)
        self.assertEqual(res.items[0].entity_type, "interview")
        self.assertIn("System Architecture", res.items[0].title)

    def test_search_empty_and_whitespace_query(self):
        """Blank or whitespace query safely returns empty result."""
        res1 = self.service.search("")
        self.assertEqual(res1.total_count, 0)
        self.assertEqual(len(res1.items), 0)

        res2 = self.service.search("   \t  ")
        self.assertEqual(res2.total_count, 0)

    def test_search_no_match(self):
        """Query yielding no results returns total_count 0."""
        res = self.service.search("NonexistentCompany9999")
        self.assertEqual(res.total_count, 0)
        self.assertEqual(len(res.items), 0)


class TestNotificationService(unittest.TestCase):
    """Test suite for NotificationService, scheduled reminders, and automation alert hooks."""

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.notif_service = NotificationService(
            session_factory=self.SessionFactory,
            enable_tray=False,  # Headless test mode
        )
        self.captured_notifications = []
        self.notif_service.notification_triggered.connect(
            lambda lvl, title, msg: self.captured_notifications.append((lvl, title, msg))
        )

    def tearDown(self):
        self.notif_service.stop_reminder_timer()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_upcoming_interview_reminder_detection_and_deduplication(self):
        """Detects upcoming interviews within 24 hours and prevents duplicate alerts."""
        now = utc_now()
        with self.SessionFactory() as session:
            job = Job(
                platform="linkedin",
                title="Cloud Reliability Engineer",
                company_raw="Netflix",
                source_url="https://linkedin.com/jobs/view/netflix1",
                job_fingerprint="fp_netflix_1",
            )
            session.add(job)
            session.flush()

            app = Application(job_id=job.id, status="INTERVIEW")
            session.add(app)
            session.flush()

            # Interview within 4 hours (should notify)
            int_soon = Interview(
                application_id=app.id,
                round_name="Technical Round 1",
                scheduled_at=now + timedelta(hours=4),
                status="SCHEDULED",
            )
            # Interview in 48 hours (outside 24h window, should NOT notify)
            int_far = Interview(
                application_id=app.id,
                round_name="Executive Final",
                scheduled_at=now + timedelta(hours=48),
                status="SCHEDULED",
            )
            session.add_all([int_soon, int_far])
            session.commit()

        # 1. First Scan
        res1 = self.notif_service.check_reminders()
        self.assertEqual(res1["interviews_notified"], 1)
        self.assertEqual(len(self.captured_notifications), 1)
        self.assertIn("Netflix", self.captured_notifications[0][2])
        self.assertIn("Technical Round 1", self.captured_notifications[0][2])

        # 2. Second Scan (Deduplication should prevent re-alerting)
        res2 = self.notif_service.check_reminders()
        self.assertEqual(res2["interviews_notified"], 0)
        self.assertEqual(len(self.captured_notifications), 1)

        # 3. Clear cache and re-check -> should notify again
        self.notif_service.clear_reminder_cache()
        res3 = self.notif_service.check_reminders()
        self.assertEqual(res3["interviews_notified"], 1)
        self.assertEqual(len(self.captured_notifications), 2)

    def test_follow_up_due_and_overdue_reminders(self):
        """Detects due and overdue follow-ups with appropriate severity levels."""
        now = utc_now()
        with self.SessionFactory() as session:
            job = Job(
                platform="naukri",
                title="Robotics Engineer",
                company_raw="Boston Dynamics",
                source_url="https://naukri.com/job-listings-bd1",
                job_fingerprint="fp_bd_1",
            )
            session.add(job)
            session.flush()

            app = Application(job_id=job.id, status="APPLIED")
            session.add(app)
            session.flush()

            # Due in 2 hours (Today / soon)
            fu_due = FollowUp(
                application_id=app.id,
                due_at=now + timedelta(hours=2),
                status="PENDING",
                notes="Check in on interview feedback",
            )
            # Overdue by 1 day
            fu_overdue = FollowUp(
                application_id=app.id,
                due_at=now - timedelta(days=1),
                status="PENDING",
                notes="Send resume update to HR",
            )
            # Completed follow-up (should be ignored)
            fu_done = FollowUp(
                application_id=app.id,
                due_at=now - timedelta(hours=5),
                status="COMPLETED",
                notes="Already answered",
            )
            session.add_all([fu_due, fu_overdue, fu_done])
            session.commit()

        res = self.notif_service.check_reminders()
        self.assertEqual(res["followups_notified"], 2)

        titles = [n[1] for n in self.captured_notifications]
        levels = [n[0] for n in self.captured_notifications]

        self.assertIn("Follow-up Due Today", titles)
        self.assertIn("Overdue Follow-up Reminder", titles)
        self.assertIn("warning", levels)

    def test_automation_intervention_alert_dispatch(self):
        """Intervention event immediately emits high-priority warning notification."""
        event = AutomationInterventionEvent(
            run_id="run_123",
            platform="naukri",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Cloudflare Turnstile challenge detected in browser window.",
        )
        self.notif_service._on_intervention_required(event)

        self.assertEqual(len(self.captured_notifications), 1)
        level, title, message = self.captured_notifications[0]
        self.assertEqual(level, "warning")
        self.assertIn("Action Required", title)
        self.assertIn("Captcha Detected", message)

    def test_automation_run_completion_dispatch(self):
        """Run finished events emit completion or failure summary notifications."""
        # Completed run
        success_result = AutomationRunResult(
            run_id="run_abc",
            platform="linkedin",
            status=AutomationState.COMPLETED,
            started_at=utc_now(),
            finished_at=utc_now(),
            applications_submitted=5,
            jobs_qualified=8,
            jobs_skipped=12,
        )
        self.notif_service._on_run_finished(success_result)

        self.assertEqual(len(self.captured_notifications), 1)
        level, title, message = self.captured_notifications[0]
        self.assertEqual(level, "success")
        self.assertIn("Automation Completed", title)
        self.assertIn("Applied: 5", message)

        # Failed run
        failed_result = AutomationRunResult(
            run_id="run_err",
            platform="naukri",
            status=AutomationState.FAILED,
            started_at=utc_now(),
            finished_at=utc_now(),
            stop_reason="Browser crashed unexpectedly",
        )
        self.notif_service._on_run_finished(failed_result)

        self.assertEqual(len(self.captured_notifications), 2)
        level, title, message = self.captured_notifications[1]
        self.assertEqual(level, "error")
        self.assertIn("Automation Terminated", title)
        self.assertIn("Browser crashed unexpectedly", message)

    def test_notification_settings_suppression(self):
        """Disabling notification types in settings suppresses corresponding alerts."""
        self.notif_service.notify_automation_interventions = False
        self.notif_service.notify_automation_completion = False

        event = AutomationInterventionEvent(
            run_id="run_xyz",
            platform="linkedin",
            intervention_type=InterventionType.LOGIN_REQUIRED,
            message="Login required",
        )
        self.notif_service._on_intervention_required(event)
        self.assertEqual(len(self.captured_notifications), 0)


class TestUIIntegration(unittest.TestCase):
    """UI integration tests for TopBar search button, GlobalSearchDialog, and MainWindow."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.SessionFactory = sessionmaker(bind=self.engine)
        self.search_service = SearchService(session_factory=self.SessionFactory)

        # Seed sample job
        with self.SessionFactory() as session:
            job = Job(
                platform="linkedin",
                title="Fullstack Python Engineer",
                company_raw="Canonical",
                location="Remote",
                source_url="https://linkedin.com/jobs/view/canonical1",
                job_fingerprint="fp_canonical_1",
            )
            session.add(job)
            session.commit()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_global_search_dialog_rendering_and_querying(self):
        """Dialog executes live search and populates result widgets."""
        dialog = GlobalSearchDialog(search_service=self.search_service)
        self.assertEqual(dialog.results_list.count(), 0)

        # Set search text and perform search directly
        dialog.txt_search.setText("Canonical")
        dialog._perform_search()

        self.assertGreaterEqual(dialog.results_list.count(), 1)
        self.assertIn("Canonical", dialog.lbl_status.text())

    def test_global_search_dialog_selection_signal(self):
        """Selecting a result emits target_page and entity_id."""
        dialog = GlobalSearchDialog(search_service=self.search_service)
        dialog.txt_search.setText("Fullstack")
        dialog._perform_search()

        captured = []
        dialog.result_selected.connect(lambda page, eid: captured.append((page, eid)))

        first_item = dialog.results_list.item(0)
        self.assertIsNotNone(first_item)
        dialog._on_item_activated(first_item)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][0], "jobs")

    def test_top_bar_search_button(self):
        """TopBar contains search button that emits search_requested signal."""
        top_bar = TopBar()
        self.assertTrue(hasattr(top_bar, "btn_search"))
        self.assertTrue(hasattr(top_bar, "search_requested"))

        emitted = []
        top_bar.search_requested.connect(lambda: emitted.append(True))
        top_bar.btn_search.click()
        self.assertEqual(len(emitted), 1)

    def test_main_window_search_navigation_and_shortcut(self):
        """MainWindow binds Ctrl+K, opens search dialog, and navigates upon selection."""
        window = MainWindow()
        self.assertTrue(hasattr(window, "shortcut_search"))
        self.assertEqual(window.shortcut_search.key().toString(), "Ctrl+K")

        # Test selecting search result
        window._on_search_result_selected("jobs", 1)
        self.assertEqual(window.state.current_page_id, "jobs")

        window._on_search_result_selected("applications", 2)
        self.assertEqual(window.state.current_page_id, "applications")

        window._on_search_result_selected("interviews", 3)
        self.assertEqual(window.state.current_page_id, "interviews")

        # Close main window timers
        window.notification_service.stop_reminder_timer()
        window.close()


if __name__ == "__main__":
    unittest.main()
