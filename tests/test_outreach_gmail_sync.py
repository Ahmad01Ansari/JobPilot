"""Unit tests for two-way Gmail label synchronization, sent email ingestion, and subject/greeting parsing."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Communication, Company, Contact, Job, Resume, User
from app.services.dto.outreach_dto import ExpandedInboundEmailDTO, OutreachCreateDTO
from app.services.dto.outreach_enums import FollowUpStatus, MessageStatus
from app.services.email.mock_provider import MockEmailProvider
from app.services.inbound_sync_service import (
    InboundSyncService,
    extract_company_from_recipient_email,
    extract_recruiter_name_from_body,
    parse_application_subject,
)
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.outreach_service import OutreachService
from app.services.secrets_service import SecretsService


class TestOutreachGmailSync(unittest.TestCase):
    """Verifies parsing of sent applications, two-way sync, and Gmail label integration."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "gmail_sync_test.db")
        self.attach_dir = Path(self.temp_dir) / "attachments"
        self.attach_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = os.path.join(self.temp_dir, "test.key")

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        with self.Session() as s:
            u = User(id=1, name="Test Candidate", email="test_candidate@example.com", is_active=True)
            s.add(u)
            r = Resume(
                id=1,
                user_id=1,
                name="Test_Candidate_Resume",
                file_path="/mock/path/Test_Candidate_Resume.pdf",
                file_hash="mock_hash_1234",
                is_default=True,
            )
            s.add(r)
            s.commit()

        self.secrets_svc = SecretsService(key_path=self.key_path, session_factory=self.Session)
        self.secrets_svc.set_email_credentials(
            user="test_candidate@example.com",
            password="mockpassword1234",
            sync_label="RPA-Developer-Application",
        )

        self.mock_provider = MockEmailProvider(account_email="test_candidate@example.com")
        self.dispatcher = OutreachDispatcher(
            session_factory=self.Session,
            attachments_dir=self.attach_dir,
            default_provider=self.mock_provider,
        )
        self.outreach_svc = OutreachService(
            session_factory=self.Session,
            dispatcher=self.dispatcher,
            email_provider=self.mock_provider,
        )
        self.sync_svc = InboundSyncService(
            session_factory=self.Session,
            outreach_service=self.outreach_svc,
            provider=self.mock_provider,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_subject_parsing_heuristics(self):
        """Tests parsing of various real-world email subjects from the user's Gmail label."""
        # 1. Simple position
        title, comp = parse_application_subject("Application for Junior Workflow Automation Developer")
        self.assertEqual(title, "Junior Workflow Automation Developer")
        self.assertIsNone(comp)

        # 2. Case variations and trailing 'Position'
        title, comp = parse_application_subject("Application For Automation Engineer")
        self.assertEqual(title, "Automation Engineer")

        # 3. Duplicate repeated text (common clipboard glitch)
        title, comp = parse_application_subject("Application for RPA Developer PositionApplication for RPA Developer Position")
        self.assertEqual(title, "RPA Developer")

        # 4. Position with company and candidate name
        title, comp = parse_application_subject("Resume for RPA Developer Position at Infosys - Ahmad Raza")
        self.assertEqual(title, "RPA Developer")
        self.assertEqual(comp, "Infosys")

        # 5. Practitioner role
        title, comp = parse_application_subject("Application for Junior RPA Practitioner Position")
        self.assertEqual(title, "Junior RPA Practitioner")

    def test_greeting_and_domain_extraction(self):
        """Tests extracting recruiter names from greetings and company from corporate emails."""
        body1 = "Dear Dharsan,\n\nI'm writing to express my interest in the Junior Workflow Automation Developer position."
        self.assertEqual(extract_recruiter_name_from_body(body1), "Dharsan")

        body2 = "Hi Akhila, I am writing to express my interest in the RPA Developer position at your organization."
        self.assertEqual(extract_recruiter_name_from_body(body2), "Akhila")

        body3 = "Hi Rameshwar Sir, As per our recent conversation on LinkedIn..."
        self.assertEqual(extract_recruiter_name_from_body(body3), "Rameshwar")

        body_generic = "Dear Hiring Manager,\n\nPlease find attached my resume."
        self.assertIsNone(extract_recruiter_name_from_body(body_generic))

        # Domain extraction
        self.assertEqual(extract_company_from_recipient_email("kiersten@accelirate.com"), "Accelirate")
        self.assertEqual(extract_company_from_recipient_email("recruiter@infosys.com"), "Infosys")
        self.assertIsNone(extract_company_from_recipient_email("user@gmail.com"))

    def test_ingest_sent_application_from_gmail_label(self):
        """Ingests an email sent from Gmail under the RPA-Developer-Application label."""
        msg_id = f"gmail-sent-{uuid.uuid4().hex[:8]}@gmail.com"
        sent_email = ExpandedInboundEmailDTO(
            message_id=msg_id,
            from_address="test_candidate@example.com",
            to_addresses=["kiersten@accelirate.com"],
            subject="Application for Junior RPA Practitioner Position",
            body_text="Hi Kiersten, I hope you are doing well. I am writing to express my interest in the Junior RPA Practitioner position at Accelirate.",
            received_at=datetime(2026, 9, 7, 10, 30, tzinfo=timezone.utc),
            attachments_metadata=[{"filename": "Mohd_Ahmad_Resume.pdf", "size_bytes": 102400}],
        )

        # Enqueue in custom folder queue
        self.mock_provider.enqueue_inbound(sent_email, folder="RPA-Developer-Application")

        # Run sync
        res = self.sync_svc.sync_mailbox(sync_label="RPA-Developer-Application")
        self.assertTrue(res["success"])
        self.assertEqual(res["ingested_applications"], 1)

        # Verify DB records created
        with self.Session() as s:
            app = s.execute(
                select(Application)
                .join(Application.contact)
                .where(Contact.email == "kiersten@accelirate.com")
            ).scalars().first()
            self.assertIsNotNone(app)
            self.assertEqual(app.status, "SUBMITTED")
            self.assertEqual(app.job.platform, "EMAIL")
            self.assertEqual(app.application_type, "EMAIL")
            self.assertEqual(app.job.title, "Junior RPA Practitioner")
            self.assertEqual(app.job.company.name, "Accelirate")
            self.assertEqual(app.contact.name, "Kiersten")
            self.assertIsNotNone(app.resume_id)

            # Check communication record
            comm = s.execute(
                select(Communication).where(Communication.provider_message_id == msg_id)
            ).scalar_one_or_none()
            self.assertIsNotNone(comm)
            self.assertEqual(comm.direction, "OUTBOUND")
            self.assertEqual(comm.recipient_email, "kiersten@accelirate.com")
            self.assertIn("RPA-Developer-Application", comm.source)

    def test_recruiter_reply_to_ingested_application(self):
        """Verifies an incoming recruiter reply correctly matches the ingested sent application."""
        # 1. Ingest sent email
        sent_msg_id = f"sent-{uuid.uuid4().hex[:6]}@gmail.com"
        sent_email = ExpandedInboundEmailDTO(
            message_id=sent_msg_id,
            from_address="test_candidate@example.com",
            to_addresses=["akhila@acmeautomation.com"],
            subject="Application For Automation Engineer",
            body_text="Hi Akhila, I am writing to express my interest in the RPA Developer position.",
            received_at=datetime(2026, 9, 7, 11, 0, tzinfo=timezone.utc),
        )
        self.mock_provider.enqueue_inbound(sent_email, folder="RPA-Developer-Application")
        self.sync_svc.sync_mailbox(sync_label="RPA-Developer-Application")

        # 2. Recruiter replies under the label or in INBOX
        reply_msg_id = f"reply-{uuid.uuid4().hex[:6]}@acmeautomation.com"
        reply_email = ExpandedInboundEmailDTO(
            message_id=reply_msg_id,
            from_address="akhila@acmeautomation.com",
            to_addresses=["test_candidate@example.com"],
            subject="Re: Application For Automation Engineer",
            body_text="Hi Ahmad, thank you for applying! When are you available for a screening call?",
            received_at=datetime(2026, 9, 8, 14, 0, tzinfo=timezone.utc),
            in_reply_to=sent_msg_id,
        )
        self.mock_provider.enqueue_inbound(reply_email, folder="INBOX")

        res = self.sync_svc.sync_mailbox(sync_label="RPA-Developer-Application")
        self.assertEqual(res["matched_count"], 1)

        # Check application status updated to RECRUITER_CONTACTED
        with self.Session() as s:
            app = s.execute(
                select(Application)
                .join(Application.contact)
                .where(Contact.email == "akhila@acmeautomation.com")
            ).scalars().first()
            self.assertEqual(app.status, "RECRUITER_CONTACTED")

            # Verify communication timeline has 2 records
            comms = s.execute(
                select(Communication).where(Communication.application_id == app.id).order_by(Communication.occurred_at)
            ).scalars().all()
            self.assertEqual(len(comms), 2)
            self.assertEqual(comms[0].direction, "OUTBOUND")
            self.assertEqual(comms[1].direction, "INBOUND")

    def test_outbound_send_appends_to_gmail_label(self):
        """Verifies that sending an outreach from JobPilot automatically appends it to the Gmail sync label."""
        dto = OutreachCreateDTO(
            manual_company_name="RoboCorp",
            manual_job_title="Senior RPA Architect",
            contact_name="Sarah",
            contact_email="sarah@robocorp.test",
            subject="Job Application: Senior RPA Architect",
            body_text="Hi Sarah, please review my credentials.",
        )

        send_res = self.outreach_svc.send_outreach(dto)
        self.assertTrue(send_res["success"])

        # Check mock provider recorded label append
        self.assertEqual(len(self.mock_provider.appended_labels), 1)
        appended_msg, label = self.mock_provider.appended_labels[0]
        self.assertEqual(label, "RPA-Developer-Application")
        self.assertEqual(appended_msg.to_address, "sarah@robocorp.test")

    def test_send_reply_threading_with_autosaved_draft(self):
        """Verifies that follow-up reply ignores autosaved DRAFT, maintains exact root subject, and sets In-Reply-To."""
        orig_msg_id = "<CAO+++ew70MVg8NToAH56jAx5qFuK+tgA-SqO5tr73P2NtAr-5g@mail.gmail.com>"
        orig_subject = "Application for Junior Workflow Automation Developer"

        # 1. Ingest original application from Gmail label
        sent_email = ExpandedInboundEmailDTO(
            message_id=orig_msg_id,
            from_address="test_candidate@example.com",
            to_addresses=["dharsan@psrtek.com"],
            subject=orig_subject,
            body_text="Dear Dharsan, I am applying for the Junior Workflow Automation Developer role.",
            received_at=datetime(2026, 9, 11, 6, 30, tzinfo=timezone.utc),
        )
        self.mock_provider.enqueue_inbound(sent_email, folder="RPA-Developer-Application")
        sync_res = self.sync_svc.sync_mailbox(sync_label="RPA-Developer-Application")
        self.assertEqual(sync_res["ingested_applications"], 1)

        with self.Session() as s:
            app = s.execute(
                select(Application)
                .join(Application.contact)
                .where(Contact.email == "dharsan@psrtek.com")
            ).scalars().first()
            self.assertIsNotNone(app)
            app_id = app.id

        # 2. Simulate user typing a follow-up which debounced autosaves as a DRAFT in DB
        draft_id = self.outreach_svc.save_draft(
            application_id=app_id,
            body_text="Hi Dharsan,\n\nI hope you are having a productive week. Following up on my application.",
        )
        self.assertIsNotNone(draft_id)

        # 3. User clicks Send Reply (without specifying subject)
        reply_res = self.outreach_svc.send_reply(
            application_id=app_id,
            body_text="Hi Dharsan,\n\nI hope you are having a productive week. Following up on my application.",
        )
        self.assertTrue(reply_res["success"])

        # 4. Verify dispatched message properties
        sent_msgs = [m for m in self.mock_provider.sent_messages if m.to_address == "dharsan@psrtek.com"]
        self.assertTrue(len(sent_msgs) >= 1)
        latest_sent = sent_msgs[-1]

        # Critical assertions for Gmail conversation threading:
        # A. Subject MUST strictly match "Re: " + root subject character-for-character
        self.assertEqual(latest_sent.subject, f"Re: {orig_subject}")
        # B. In-Reply-To MUST point to the original message ID
        self.assertEqual(latest_sent.in_reply_to, orig_msg_id)
        # C. References MUST include the original message ID
        self.assertIn(orig_msg_id, latest_sent.references)

    def test_mime_builder_rfc_brackets(self):
        """Verifies that GenericSmtpImapProvider ensures In-Reply-To and References have RFC 2822 angle brackets."""
        from app.services.email.smtp_imap_provider import GenericSmtpImapProvider
        from app.services.dto.outreach_dto import EmailMessageDTO

        provider = GenericSmtpImapProvider(
            smtp_host="smtp.example.com",
            smtp_user="test@jobpilot.mock",
            smtp_password="secret",
        )
        msg_dto = EmailMessageDTO(
            account_id="default",
            send_token="tok_123",
            from_address="test@jobpilot.mock",
            from_name="Test User",
            to_address="recruiter@example.com",
            subject="Re: Test Position",
            body_text="Testing threading headers",
            in_reply_to="unbracketed-id-123@example.com",
            references="unbracketed-id-123@example.com unbracketed-id-456@example.com",
        )
        mime = provider.build_mime_message(msg_dto)
        self.assertEqual(mime["In-Reply-To"], "<unbracketed-id-123@example.com>")
        self.assertEqual(mime["References"], "<unbracketed-id-123@example.com> <unbracketed-id-456@example.com>")


if __name__ == "__main__":
    unittest.main()
