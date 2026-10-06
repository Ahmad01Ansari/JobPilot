"""Unit, integration, and UI test suite for RecruitmentService, InterviewsView, and FollowupsView."""

from datetime import datetime, timedelta, timezone
import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base, utc_now
from app.db.session import configure_sqlite_pragmas
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.recruitment_service import RecruitmentService


class TestRecruitmentService(unittest.TestCase):
    """Unit and lifecycle tests for interviews, communications, follow-ups, and contacts."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase11_test.db")
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

        # Seed sample job and application
        self.job, _ = self.job_service.create_manual_job(title="Senior SDET", company="Atlassian")
        self.app, _ = self.app_service.create_application(job_id=self.job.id, status="SUBMITTED")

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_schedule_interview_valid(self):
        """Verifies scheduling an interview round with valid parameters."""
        dt = utc_now() + timedelta(days=2)
        interview, err = self.recruitment_service.schedule_interview(
            application_id=self.app.id,
            round_name="Technical Screening",
            scheduled_at=dt,
            round_number=1,
            round_type="TECHNICAL",
            interviewer_name="Alice Recruiter",
            mode="VIRTUAL",
            meeting_link="https://meet.google.com/abc-def-ghi",
            notes="Focus on Selenium & pytest",
        )
        self.assertIsNotNone(interview)
        self.assertIsNone(err)
        self.assertEqual(interview.round_name, "Technical Screening")
        self.assertEqual(interview.status, "SCHEDULED")

    def test_virtual_interview_validates_url(self):
        """Verifies meeting link must be valid http/https for virtual interviews."""
        dt = utc_now() + timedelta(days=1)
        interview, err = self.recruitment_service.schedule_interview(
            application_id=self.app.id,
            round_name="Coding Round",
            scheduled_at=dt,
            mode="VIRTUAL",
            meeting_link="not-a-valid-url",
        )
        self.assertIsNone(interview)
        self.assertIn("must be a valid http", err)

    def test_reschedule_interview_preserves_history(self):
        """Verifies rescheduling updates time and appends notes without using RESCHEDULED terminal status."""
        dt1 = utc_now() + timedelta(days=1)
        interview, _ = self.recruitment_service.schedule_interview(
            application_id=self.app.id,
            round_name="System Design",
            scheduled_at=dt1,
        )

        # Reschedule to 3 days later
        dt2 = utc_now() + timedelta(days=3)
        rescheduled, err = self.recruitment_service.reschedule_interview(
            interview_id=interview.id,
            new_scheduled_at=dt2,
            reason="Interviewer on leave",
        )
        self.assertIsNotNone(rescheduled)
        self.assertIsNone(err)
        self.assertEqual(rescheduled.status, "SCHEDULED")  # Active status preserved
        self.assertEqual(rescheduled.scheduled_at, dt2)
        self.assertIn("Rescheduled from", rescheduled.notes)

    def test_complete_interview_with_and_without_feedback(self):
        """Verifies completing an interview round updates completed_at with optional feedback."""
        dt = utc_now() + timedelta(days=1)
        interview, _ = self.recruitment_service.schedule_interview(
            application_id=self.app.id,
            round_name="Managerial Round",
            scheduled_at=dt,
        )

        # Complete with feedback
        updated, err = self.recruitment_service.update_interview_status(
            interview_id=interview.id,
            status="COMPLETED",
            feedback="Strong cultural fit and leadership skills.",
        )
        self.assertIsNotNone(updated)
        self.assertIsNone(err)
        self.assertEqual(updated.status, "COMPLETED")
        self.assertIsNotNone(updated.completed_at)
        self.assertEqual(updated.feedback, "Strong cultural fit and leadership skills.")

    def test_invalid_interview_status_rejected(self):
        """Verifies state rejects arbitrary interview statuses."""
        dt = utc_now() + timedelta(days=1)
        interview, _ = self.recruitment_service.schedule_interview(
            application_id=self.app.id,
            round_name="Round 1",
            scheduled_at=dt,
        )
        res, err = self.recruitment_service.update_interview_status(
            interview_id=interview.id,
            status="SOMETHING_INVALID",
        )
        self.assertIsNone(res)
        self.assertIn("Invalid interview status", err)

    def test_get_or_create_contact_deduplication(self):
        """Verifies contacts are deduplicated by email or normalized name."""
        c1 = self.recruitment_service.get_or_create_contact(
            name="Bob Smith",
            email="bob.smith@atlassian.com",
            designation="Talent Acquisition",
        )
        self.assertIsNotNone(c1)

        # Lookup by same email with different casing
        c2 = self.recruitment_service.get_or_create_contact(
            name="Bob S.",
            email="BOB.SMITH@ATLASSIAN.COM",
        )
        self.assertEqual(c1.id, c2.id)

    def test_log_communication_valid_types_and_directions(self):
        """Verifies logging communication events with valid types and directions."""
        comm, err = self.recruitment_service.log_communication(
            type_="EMAIL",
            direction="INBOUND",
            application_id=self.app.id,
            subject="Interview Invitation",
            summary="Recruiter sent Google Meet invite",
        )
        self.assertIsNotNone(comm)
        self.assertIsNone(err)
        self.assertEqual(comm.type, "EMAIL")
        self.assertEqual(comm.direction, "INBOUND")

    def test_invalid_communication_type_rejected(self):
        """Verifies illegal communication types are rejected."""
        comm, err = self.recruitment_service.log_communication(
            type_="CARRIER_PIGEON",
            direction="INBOUND",
        )
        self.assertIsNone(comm)
        self.assertIn("Invalid communication type", err)

    def test_create_and_complete_follow_up_sets_completed_at(self):
        """Verifies creating follow-up and marking as COMPLETED sets timestamp."""
        due = utc_now() + timedelta(days=4)
        fu, err = self.recruitment_service.create_follow_up(
            due_at=due,
            application_id=self.app.id,
            notes="Ask about next steps",
        )
        self.assertIsNotNone(fu)
        self.assertIsNone(err)
        self.assertEqual(fu.status, "PENDING")
        self.assertIsNone(fu.completed_at)

        completed, err_c = self.recruitment_service.complete_follow_up(fu.id, status="COMPLETED")
        self.assertIsNotNone(completed)
        self.assertIsNone(err_c)
        self.assertEqual(completed.status, "COMPLETED")
        self.assertIsNotNone(completed.completed_at)

    def test_cancel_follow_up_preserves_record(self):
        """Verifies cancelling a follow-up sets CANCELLED rather than deleting."""
        due = utc_now() + timedelta(days=2)
        fu, _ = self.recruitment_service.create_follow_up(due_at=due, application_id=self.app.id)

        cancelled, _ = self.recruitment_service.complete_follow_up(fu.id, status="CANCELLED")
        self.assertEqual(cancelled.status, "CANCELLED")

        # Record still present in database
        all_fu = self.recruitment_service.list_follow_ups(status="CANCELLED")
        self.assertEqual(len(all_fu), 1)

    def test_overdue_followup_dynamic_detection(self):
        """Verifies derived overdue count detects pending follow-ups with past due dates."""
        # 1. Past due date (overdue)
        past_due = utc_now() - timedelta(days=2)
        self.recruitment_service.create_follow_up(due_at=past_due, application_id=self.app.id)

        # 2. Future due date (not overdue)
        future_due = utc_now() + timedelta(days=2)
        self.recruitment_service.create_follow_up(due_at=future_due, application_id=self.app.id)

        metrics = self.recruitment_service.get_metrics()
        self.assertEqual(metrics["pending_follow_ups"], 2)
        self.assertEqual(metrics["overdue_follow_ups"], 1)

    def test_record_offer_and_status_validation(self):
        """Verifies recording offer and validating offer status."""
        join_date = utc_now() + timedelta(days=30)
        offer, err = self.recruitment_service.record_offer(
            application_id=self.app.id,
            offered_ctc=2500000,
            currency="INR",
            joining_date=join_date,
            status="RECEIVED",
            notes="Base CTC 22L + 3L joining bonus",
        )
        self.assertIsNotNone(offer)
        self.assertIsNone(err)
        self.assertEqual(offer.offered_ctc, 2500000)
        self.assertEqual(offer.status, "RECEIVED")

        metrics = self.recruitment_service.get_metrics()
        self.assertEqual(metrics["offers_received"], 1)


class TestPhase11Views(unittest.TestCase):
    """Headless PySide6 UI tests for InterviewsView and FollowupsView."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase11_view_test.db")
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

        self.job, _ = self.job_service.create_manual_job(title="Lead Architect", company="Cisco")
        self.application, _ = self.app_service.create_application(job_id=self.job.id, status="SUBMITTED")

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_interviews_view_rendering_and_table(self):
        """Verifies InterviewsView renders scheduled interview rounds."""
        from app.ui.views.interviews_view import InterviewsView

        dt = utc_now() + timedelta(days=2)
        self.recruitment_service.schedule_interview(
            application_id=self.application.id,
            round_name="Coding Assessment",
            scheduled_at=dt,
            interviewer_name="Dave Engineer",
        )

        view = InterviewsView(service=self.recruitment_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 1)
        self.assertIn("1 rounds", view.lbl_stats.text())

    def test_followups_view_rendering_and_completion(self):
        """Verifies FollowupsView renders metric cards, table, and completes reminder."""
        from app.ui.views.followups_view import FollowupsView

        due = utc_now() + timedelta(days=1)
        fu, _ = self.recruitment_service.create_follow_up(
            due_at=due,
            application_id=self.application.id,
            notes="Send portfolio link",
        )

        view = FollowupsView(service=self.recruitment_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 1)

        # Trigger completion action
        view._on_complete_clicked(fu.id)
        self.assertTrue(view.notification_bar.isVisible())
        self.assertIn("completed", view.notification_bar.message_label.text())


if __name__ == "__main__":
    unittest.main()
