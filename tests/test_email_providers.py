"""Unit tests for Outreach Email Providers (Mock and SMTP/IMAP)."""

from datetime import datetime, timezone
import email
from email.message import EmailMessage
import os
import shutil
import tempfile
import unittest

from app.services.dto.outreach_dto import (
    EmailMessageDTO,
    ExpandedInboundEmailDTO,
    SyncCheckpointDTO,
)
from app.services.dto.outreach_enums import MessageStatus
from app.services.email.factory import (
    get_email_provider,
    register_email_provider,
    unregister_email_provider,
)
from app.services.email.mock_provider import MockEmailProvider
from app.services.email.smtp_imap_provider import (
    GenericSmtpImapProvider,
    _decode_header_str,
    _extract_body_parts,
)


class TestEmailProviders(unittest.TestCase):
    """Tests MockEmailProvider and GenericSmtpImapProvider MIME handling and contracts."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_provider = MockEmailProvider(account_email="tester@jobpilot.mock")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        unregister_email_provider("test_account")

    def test_mock_provider_test_connection(self):
        """Mock provider reports connectivity and respects failure configuration."""
        res = self.mock_provider.test_connection()
        self.assertTrue(res.success)
        self.assertEqual(res.provider_name, "mock")

        self.mock_provider.connection_should_succeed = False
        res_fail = self.mock_provider.test_connection()
        self.assertFalse(res_fail.success)

    def test_mock_provider_send_and_idempotency(self):
        """Mock provider dispatches email and caches results by send_token."""
        msg = EmailMessageDTO(
            account_id="mock",
            send_token="token_abc_123",
            from_address="candidate@test.com",
            from_name="Test Candidate",
            to_address="recruiter@company.com",
            subject="Application for Senior Engineer",
            body_text="Dear Recruiter, please find my application attached.",
        )

        # First dispatch
        res1 = self.mock_provider.send_email(msg)
        self.assertTrue(res1.success)
        self.assertEqual(res1.status, MessageStatus.SENT)
        self.assertIsNotNone(res1.provider_message_id)
        self.assertEqual(len(self.mock_provider.sent_messages), 1)

        # Second dispatch with identical send_token (idempotency check)
        res2 = self.mock_provider.send_email(msg)
        self.assertTrue(res2.success)
        self.assertEqual(res1.provider_message_id, res2.provider_message_id)
        # Should not append a second message
        self.assertEqual(len(self.mock_provider.sent_messages), 1)

    def test_mock_provider_fault_injection(self):
        """Mock provider simulates dispatch failures when configured."""
        self.mock_provider.fail_next_send = True
        self.mock_provider.error_message_to_fail = "550 Recipient address rejected"

        msg = EmailMessageDTO(
            account_id="mock",
            send_token="token_fail_456",
            from_address="candidate@test.com",
            from_name="Test Candidate",
            to_address="invalid@company.com",
            subject="Application",
            body_text="Hello",
        )
        res = self.mock_provider.send_email(msg)
        self.assertFalse(res.success)
        self.assertEqual(res.status, MessageStatus.FAILED)
        self.assertIn("550", res.error_message)

    def test_mock_provider_inbound_fetch(self):
        """Mock provider filters queued inbound emails by checkpoint cursor."""
        t1 = datetime(2026, 9, 28, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 9, 28, 12, 0, 0, tzinfo=timezone.utc)

        inbound1 = ExpandedInboundEmailDTO(
            message_id="msg-1",
            from_address="recruiter@company.com",
            to_addresses=["candidate@test.com"],
            subject="Re: Application",
            body_text="Let's schedule a call.",
            received_at=t1,
        )
        inbound2 = ExpandedInboundEmailDTO(
            message_id="msg-2",
            from_address="hr@another.com",
            to_addresses=["candidate@test.com"],
            subject="Offer Details",
            body_text="Congratulations!",
            received_at=t2,
        )
        self.mock_provider.enqueue_inbound(inbound1)
        self.mock_provider.enqueue_inbound(inbound2)

        # Checkpoint before both
        ckpt1 = SyncCheckpointDTO(account_id="mock", last_sync_at=datetime(2026, 9, 28, 9, 0, 0, tzinfo=timezone.utc))
        msgs1 = self.mock_provider.fetch_inbound(ckpt1)
        self.assertEqual(len(msgs1), 2)

        # Checkpoint between t1 and t2
        ckpt2 = SyncCheckpointDTO(account_id="mock", last_sync_at=datetime(2026, 9, 28, 11, 0, 0, tzinfo=timezone.utc))
        msgs2 = self.mock_provider.fetch_inbound(ckpt2)
        self.assertEqual(len(msgs2), 1)
        self.assertEqual(msgs2[0].message_id, "msg-2")

    def test_smtp_mime_message_construction(self):
        """GenericSmtpImapProvider builds RFC 2822 compliant MIME messages with attachments and thread headers."""
        # Create a mock staged attachment file
        dummy_attachment_path = os.path.join(self.temp_dir, "tok123_resume.pdf")
        with open(dummy_attachment_path, "wb") as f:
            f.write(b"%PDF-1.4 dummy pdf binary content")

        provider = GenericSmtpImapProvider(
            smtp_host="mail.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="password",
        )

        msg_dto = EmailMessageDTO(
            account_id="work",
            send_token="tok123",
            from_address="user@example.com",
            from_name="Jane Developer",
            to_address="hiring@techcorp.com",
            cc_addresses=["lead@techcorp.com"],
            subject="Job Application: Senior Backend Engineer",
            body_text="Please find my resume attached.",
            body_html="<p>Please find my <b>resume</b> attached.</p>",
            attachment_snapshot_path=dummy_attachment_path,
            in_reply_to="<parent-msg-id@techcorp.com>",
            references="<root-msg-id@techcorp.com> <parent-msg-id@techcorp.com>",
        )

        mime = provider.build_mime_message(msg_dto)
        self.assertIn("Jane Developer", mime["From"])
        self.assertIn("user@example.com", mime["From"])
        self.assertEqual(mime["To"], "hiring@techcorp.com")
        self.assertEqual(mime["Cc"], "lead@techcorp.com")
        self.assertEqual(mime["Subject"], "Job Application: Senior Backend Engineer")
        self.assertEqual(mime["In-Reply-To"], "<parent-msg-id@techcorp.com>")
        self.assertEqual(mime["References"], "<root-msg-id@techcorp.com> <parent-msg-id@techcorp.com>")
        self.assertTrue(mime["Message-ID"].startswith("<"))

        # Verify body parts and attachment extraction
        text, html, attachments = _extract_body_parts(mime)
        self.assertEqual(text, "Please find my resume attached.")
        self.assertEqual(html, "<p>Please find my <b>resume</b> attached.</p>")
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "resume.pdf")

    def test_factory_and_registry(self):
        """Factory retrieves mock provider by default and supports custom registration."""
        mock_p = get_email_provider("mock")
        self.assertIsInstance(mock_p, MockEmailProvider)

        custom = MockEmailProvider(account_email="custom@provider.test")
        register_email_provider("test_account", custom)
        self.assertIs(get_email_provider("test_account"), custom)


if __name__ == "__main__":
    unittest.main()
