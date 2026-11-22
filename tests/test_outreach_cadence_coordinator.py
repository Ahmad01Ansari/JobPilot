"""Tests for OutreachCadenceCoordinator, FollowUpScheduler HITL workflow, and AI Copilot integration."""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, FollowUp, Job, User
from app.services.dto.outreach_enums import FollowUpStatus
from app.services.followup_scheduler import FollowUpScheduler
from app.services.outreach_coordinator import OutreachCadenceCoordinator
from app.services.pilot.intent_router import IntentRouter
from app.services.pilot.pilot_models import PilotActionType
from app.services.pilot.pilot_service import PilotService


class TestOutreachCadenceCoordinator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        with self.session_factory() as s:
            user = User(id=1, email="candidate@test.com", name="Ahmad Candidate")
            s.add(user)
            company = Company(id=1, name="Acme Robotics", normalized_name="acme robotics", website="https://acme.ai")
            s.add(company)
            job = Job(
                id=1,
                company_id=1,
                title="Senior RPA Engineer",
                company_raw="Acme Robotics",
                location="Remote",
                platform="email",
                job_fingerprint="acme_rpa_eng_1",
                source_url="https://acme.ai/jobs/1",
            )
            s.add(job)
            contact = Contact(id=1, name="Alice Recruiter", email="alice@acme.ai")
            s.add(contact)
            app = Application(
                id=1,
                user_id=1,
                job_id=1,
                contact_id=1,
                status="APPLIED",
                applied_at=datetime.now(timezone.utc) - timedelta(days=4),
            )
            s.add(app)
            comm = Communication(
                id=1,
                application_id=1,
                type="EMAIL",
                direction="OUTBOUND",
                status="SENT",
                subject="Inquiry: Senior RPA Engineer - Ahmad",
                body_snippet="Excited to submit my application for the RPA role.",
                summary="Full body text of application.",
                occurred_at=datetime.now(timezone.utc) - timedelta(days=4),
            )
            s.add(comm)
            fu = FollowUp(
                id=1,
                application_id=1,
                contact_id=1,
                step_number=1,
                due_at=datetime.now(timezone.utc) - timedelta(hours=2),
                status=FollowUpStatus.PENDING.value,
            )
            s.add(fu)
            s.commit()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_get_due_followups_for_user_returns_rich_metadata(self):
        scheduler = FollowUpScheduler(session_factory=self.session_factory)
        due = scheduler.get_due_followups_for_user(user_id=1)
        self.assertEqual(len(due), 1)
        item = due[0]
        self.assertEqual(item["company_name"], "Acme Robotics")
        self.assertEqual(item["job_title"], "Senior RPA Engineer")
        self.assertEqual(item["contact_name"], "Alice Recruiter")
        self.assertEqual(item["contact_email"], "alice@acme.ai")
        self.assertEqual(item["step_number"], 1)
        self.assertEqual(item["status"], FollowUpStatus.DUE.value)
        self.assertIn("last_email_sent_at", item)
        self.assertEqual(item["last_email_subject"], "Inquiry: Senior RPA Engineer - Ahmad")
        self.assertIn("Excited to submit", item["last_email_snippet"])
        self.assertIn("Senior RPA Engineer", item["proposed_subject"])
        self.assertTrue(len(item["proposed_body"]) > 20)

    def test_snooze_followup_updates_due_date_and_resets_status(self):
        scheduler = FollowUpScheduler(session_factory=self.session_factory)
        success = scheduler.snooze_followup(followup_id=1, days=3)
        self.assertTrue(success)

        with self.session_factory() as s:
            fu = s.get(FollowUp, 1)
            self.assertEqual(fu.status, FollowUpStatus.PENDING.value)
            self.assertGreater(fu.due_at, datetime.now(timezone.utc) + timedelta(days=2))

    def test_cancel_followup_cancels_all_cadences_for_application(self):
        scheduler = FollowUpScheduler(session_factory=self.session_factory)
        success = scheduler.cancel_followup(followup_id=1, reason="User cancelled via test")
        self.assertTrue(success)

        with self.session_factory() as s:
            fu = s.get(FollowUp, 1)
            self.assertEqual(fu.status, FollowUpStatus.CANCELLED.value)

    def test_coordinator_lifecycle_and_emission(self):
        coordinator = OutreachCadenceCoordinator()
        coordinator._scheduler = FollowUpScheduler(session_factory=self.session_factory)
        coordinator._inbound_sync = MagicMock()
        coordinator._inbound_sync.sync_mailbox.return_value = {"new_messages": 0}

        emitted_due = []
        loop = QEventLoop()
        coordinator.due_followups_detected.connect(lambda lst: (emitted_due.extend(lst), loop.quit()))

        coordinator.run_cadence_cycle()
        loop.exec()

        self.assertEqual(len(emitted_due), 1)
        self.assertEqual(emitted_due[0]["company_name"], "Acme Robotics")

        coordinator.stop()

    def test_intent_router_followup_heuristics(self):
        router = IntentRouter()

        action, params, _ = router.parse_intent("Check my follow-ups please")
        self.assertEqual(action, PilotActionType.GET_FOLLOWUPS)

        action, params, _ = router.parse_intent("Do I have any followups due?")
        self.assertEqual(action, PilotActionType.GET_FOLLOWUPS)

        action, params, _ = router.parse_intent("Send follow-up to Acme Robotics now")
        self.assertEqual(action, PilotActionType.EXECUTE_FOLLOWUP)

        action, params, _ = router.parse_intent("Snooze follow-up for 5 days")
        self.assertEqual(action, PilotActionType.SNOOZE_FOLLOWUP)
        self.assertEqual(params.get("days"), 5)

        action, params, _ = router.parse_intent("Cancel follow-up cadence")
        self.assertEqual(action, PilotActionType.CANCEL_FOLLOWUP)

    def test_pilot_service_get_followups_overview(self):
        pilot = PilotService(session_factory=self.session_factory)
        msg = pilot.process_user_prompt("Check my follow-ups please")
        self.assertIn("Outreach Follow-Up Requiring Confirmation", msg.body)
        self.assertIn("Acme Robotics", msg.body)
        self.assertIn("Alice Recruiter", msg.body)
        self.assertIn("Proposed Follow-Up Draft", msg.body)
        self.assertIsNotNone(msg.intervention)
        self.assertEqual(msg.intervention.options, ["Send Now", "Snooze 3 Days", "Cancel Cadence"])

    def test_followup_review_dialog_ui_and_signals(self):
        from app.ui.views.outreach.followup_review_dialog import FollowUpReviewDialog

        fu_data = {
            "id": 1,
            "followup_id": 1,
            "company_name": "Acme Robotics",
            "job_title": "Senior RPA Engineer",
            "contact_name": "Alice Recruiter",
            "contact_email": "alice@acme.ai",
            "step_number": 1,
            "last_email_sent_at": "Nov 17, 2026",
            "last_email_subject": "Inquiry: Senior RPA Engineer - Ahmad",
            "last_email_snippet": "Excited to submit my application.",
            "proposed_subject": "Following up on my Senior RPA Engineer note",
            "proposed_body": "Hi Alice, following up on my application.",
        }

        dialog = FollowUpReviewDialog(fu_data)
        self.assertEqual(dialog.txt_subject.text(), "Following up on my Senior RPA Engineer note")
        self.assertEqual(dialog.txt_body.toPlainText(), "Hi Alice, following up on my application.")

        approved_events = []
        dialog.approved_send.connect(lambda fid, subj, body: approved_events.append((fid, subj, body)))

        dialog.txt_subject.setText("Custom Follow-up Subject")
        dialog.txt_body.setPlainText("Custom body for Alice")
        dialog._on_send_clicked()

        self.assertEqual(len(approved_events), 1)
        self.assertEqual(approved_events[0][0], 1)
        self.assertEqual(approved_events[0][1], "Custom Follow-up Subject")
        self.assertEqual(approved_events[0][2], "Custom body for Alice")


if __name__ == "__main__":
    unittest.main()
