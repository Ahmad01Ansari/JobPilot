"""Generic SMTP / IMAP Email Provider implementation."""

from datetime import datetime, timezone
import email
from email.header import decode_header
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid, parseaddr, parsedate_to_datetime
import imaplib
import os
import re
import smtplib
import socket
import ssl
from typing import Any, Dict, List, Optional, Tuple

from app.services.dto.outreach_dto import (
    ConnectionStatusDTO,
    EmailMessageDTO,
    ExpandedInboundEmailDTO,
    SendResultDTO,
    SyncCheckpointDTO,
)
from app.services.dto.outreach_enums import MessageStatus
from app.services.email.provider import EmailProvider
from app.services.sanitizer_service import LogSanitizer


def _decode_header_str(header_value: Optional[str]) -> str:
    """Decodes an encoded email header string (e.g., =?utf-8?b?...?=)."""
    if not header_value:
        return ""
    decoded_fragments = decode_header(header_value)
    result = []
    for fragment, charset in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)


def _extract_body_parts(msg: email.message.Message) -> Tuple[str, str, List[Dict[str, Any]]]:
    """Extracts plain text, HTML body, and attachment metadata from a MIME message."""
    text_content = ""
    html_content = ""
    attachments: List[Dict[str, Any]] = []

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Handle attachments
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = _decode_header_str(filename)
                attachments.append({
                    "filename": filename or "attachment",
                    "content_type": content_type,
                    "size_bytes": len(part.get_payload(decode=True) or b""),
                })
                continue

            # Handle text and html body
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                try:
                    decoded_text = payload.decode(charset, errors="replace")
                except (LookupError, UnicodeDecodeError):
                    decoded_text = payload.decode("utf-8", errors="replace")
                if content_type == "text/plain" and not text_content:
                    text_content = decoded_text
                elif content_type == "text/html" and not html_content:
                    html_content = decoded_text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                decoded_text = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                decoded_text = payload.decode("utf-8", errors="replace")
            if msg.get_content_type() == "text/html":
                html_content = decoded_text
            else:
                text_content = decoded_text

    return text_content, html_content, attachments


import logging
import time

logger = logging.getLogger("JobPilot.Email.SmtpImapProvider")


class GenericSmtpImapProvider(EmailProvider):
    """Production provider adapter communicating over standard SMTP and IMAP protocols."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_ssl: bool = False,
        smtp_use_tls: bool = True,
        imap_host: Optional[str] = None,
        imap_port: int = 993,
        imap_user: Optional[str] = None,
        imap_password: Optional[str] = None,
        imap_use_ssl: bool = True,
        timeout: float = 25.0,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_use_ssl = smtp_use_ssl
        self.smtp_use_tls = smtp_use_tls

        self.imap_host = imap_host or smtp_host
        self.imap_port = imap_port
        self.imap_user = imap_user or smtp_user
        self.imap_password = imap_password or smtp_password
        self.imap_use_ssl = imap_use_ssl
        self.timeout = timeout
        self._sent_tokens: Dict[str, SendResultDTO] = {}


    def get_provider_name(self) -> str:
        return "smtp_imap"

    @staticmethod
    def _sanitize_header(value: Optional[str]) -> str:
        """Strips CRLF characters to prevent SMTP header injection."""
        if not value:
            return ""
        return re.sub(r"[\r\n]+", " ", str(value)).strip()

    def test_connection(self) -> ConnectionStatusDTO:
        """Tests SMTP and optionally IMAP connectivity."""
        now = datetime.now(timezone.utc)
        # Test SMTP
        try:
            if self.smtp_use_ssl:
                ssl_ctx = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout, context=ssl_ctx)
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
                if self.smtp_use_tls:
                    ssl_ctx = ssl.create_default_context()
                    server.starttls(context=ssl_ctx)

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.quit()
        except Exception as e:
            return ConnectionStatusDTO(
                success=False,
                provider_name="smtp_imap",
                message=f"SMTP connection failed: {LogSanitizer.sanitize_text(str(e))}",
                account_email=self.smtp_user,
                tested_at=now,
            )

        # Test IMAP if configured
        if self.imap_host and self.imap_user and self.imap_password:
            try:
                if self.imap_use_ssl:
                    client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
                else:
                    client = imaplib.IMAP4(self.imap_host, self.imap_port)
                client.login(self.imap_user, self.imap_password)
                client.logout()
            except Exception as e:
                return ConnectionStatusDTO(
                    success=False,
                    provider_name="smtp_imap",
                    message=f"IMAP connection failed: {str(e)}",
                    account_email=self.imap_user,
                    tested_at=now,
                )

        return ConnectionStatusDTO(
            success=True,
            provider_name="smtp_imap",
            message="SMTP and IMAP connections established successfully",
            account_email=self.smtp_user,
            tested_at=now,
        )

    def build_mime_message(self, message: EmailMessageDTO) -> MIMEMultipart:
        """Constructs an RFC 2822 compliant MIME message object from EmailMessageDTO."""
        msg = MIMEMultipart("mixed")
        actual_sender = self.smtp_user if (self.smtp_user and "@" in self.smtp_user) else message.from_address
        sender_display = f"{message.from_name} <{actual_sender}>" if message.from_name else actual_sender
        msg["From"] = self._sanitize_header(sender_display)
        msg["To"] = self._sanitize_header(message.to_address)
        if message.cc_addresses:
            msg["Cc"] = ", ".join(self._sanitize_header(c) for c in message.cc_addresses if c)
        msg["Subject"] = self._sanitize_header(message.subject)
        msg["Date"] = formatdate(localtime=True)

        domain = actual_sender.split("@")[-1] if "@" in actual_sender else self.smtp_host
        msg["Message-ID"] = make_msgid(idstring=message.send_token, domain=domain)

        if message.in_reply_to:
            irt = message.in_reply_to.strip()
            if not irt.startswith("<"):
                irt = f"<{irt}"
            if not irt.endswith(">"):
                irt = f"{irt}>"
            msg["In-Reply-To"] = irt

        if message.references:
            refs = message.references.strip()
            parts = refs.split()
            cleaned_parts = []
            for p in parts:
                p = p.strip()
                if p:
                    if not p.startswith("<"):
                        p = f"<{p}"
                    if not p.endswith(">"):
                        p = f"{p}>"
                    cleaned_parts.append(p)
            if cleaned_parts:
                msg["References"] = " ".join(cleaned_parts)

        # Body parts: Plain text and Optional HTML
        body_part = MIMEMultipart("alternative")
        body_part.attach(MIMEText(message.body_text or "", "plain", "utf-8"))
        if message.body_html:
            body_part.attach(MIMEText(message.body_html, "html", "utf-8"))
        msg.attach(body_part)

        # Attachment if staged snapshot exists
        if message.attachment_snapshot_path and os.path.exists(message.attachment_snapshot_path):
            with open(message.attachment_snapshot_path, "rb") as f:
                content = f.read()
            filename = os.path.basename(message.attachment_snapshot_path)
            # Remove send token prefix from displayed attachment filename if present
            if "_" in filename:
                clean_name = filename.split("_", 1)[1]
            else:
                clean_name = filename

            att = MIMEApplication(content, _subtype="pdf")
            att.add_header("Content-Disposition", "attachment", filename=clean_name)
            msg.attach(att)

        return msg

    def send_email(self, message: EmailMessageDTO) -> SendResultDTO:
        now = datetime.now(timezone.utc)
        try:
            mime_msg = self.build_mime_message(message)
            recipients = [message.to_address] + (message.cc_addresses or [])
            actual_sender = self.smtp_user if (self.smtp_user and "@" in self.smtp_user) else message.from_address

            max_attempts = 3
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    if self.smtp_use_ssl:
                        ssl_ctx = ssl.create_default_context()
                        server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=self.timeout, context=ssl_ctx)
                    else:
                        server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout)
                        if self.smtp_use_tls:
                            ssl_ctx = ssl.create_default_context()
                            server.starttls(context=ssl_ctx)

                    if self.smtp_user and self.smtp_password:
                        server.login(self.smtp_user, self.smtp_password)

                    server.send_message(mime_msg, from_addr=actual_sender, to_addrs=recipients)
                    try:
                        server.quit()
                    except Exception:
                        pass

                    provider_msg_id = mime_msg["Message-ID"]
                    result = SendResultDTO(
                        success=True,
                        send_token=message.send_token,
                        status=MessageStatus.SENT,
                        provider_message_id=provider_msg_id,
                        provider_thread_id=message.provider_thread_id or provider_msg_id,
                        timestamp=now,
                    )
                    self._sent_tokens[message.send_token] = result
                    return result
                except (socket.gaierror, socket.timeout, ConnectionError, OSError, smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
                    last_exception = e
                    logger.warning("SMTP send attempt %d/%d to %s failed with %s: %s. Retrying...", attempt, max_attempts, self.smtp_host, type(e).__name__, e)
                    if attempt < max_attempts:
                        time.sleep(1.0 * attempt)
                except Exception as e:
                    last_exception = e
                    logger.error("Non-retryable SMTP error: %s", e)
                    break

            return SendResultDTO(
                success=False,
                send_token=message.send_token,
                status=MessageStatus.FAILED,
                error_message=f"{type(last_exception).__name__}: {str(last_exception)}" if last_exception else "Failed to send email via SMTP",
                timestamp=now,
            )
        except Exception as e:
            return SendResultDTO(
                success=False,
                send_token=message.send_token,
                status=MessageStatus.FAILED,
                error_message=f"{type(e).__name__}: {str(e)}",
                timestamp=now,
            )

    def fetch_inbound(
        self,
        checkpoint: SyncCheckpointDTO,
        folder: Optional[str] = None,
    ) -> List[ExpandedInboundEmailDTO]:
        if not (self.imap_host and self.imap_user and self.imap_password):
            return []

        results: List[ExpandedInboundEmailDTO] = []
        client = None
        try:
            if self.imap_use_ssl:
                client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=self.timeout)
            else:
                client = imaplib.IMAP4(self.imap_host, self.imap_port, timeout=self.timeout)

            client.login(self.imap_user, self.imap_password)

            target_folder = folder or "INBOX"
            typ, data = client.select(f'"{target_folder}"', readonly=True)
            if typ != "OK":
                typ, data = client.select(target_folder, readonly=True)
            if typ != "OK":
                # Folder listing fallback to find matching label name in Gmail
                try:
                    res, mailboxes = client.list()
                    if res == "OK" and mailboxes:
                        for mb in mailboxes:
                            decoded_mb = mb.decode("utf-8", errors="replace")
                            if target_folder.lower() in decoded_mb.lower():
                                parts = decoded_mb.split(' "/" ')
                                if len(parts) > 1:
                                    candidate_name = parts[-1].strip().strip('"')
                                    typ, data = client.select(f'"{candidate_name}"', readonly=True)
                                    if typ == "OK":
                                        break
                except Exception as list_err:
                    logger.debug("IMAP folder list fallback error: %s", list_err)

            if typ != "OK":
                logger.warning("Could not select IMAP folder '%s' (status: %s)", target_folder, typ)
                return []

            if checkpoint.last_sync_at:
                since_date = checkpoint.last_sync_at.strftime("%d-%b-%Y")
                typ, data = client.search(None, f'(SINCE "{since_date}")')
            else:
                typ, data = client.search(None, "ALL")

            if typ != "OK" or not data or not data[0]:
                return []

            msg_ids = data[0].split()
            # Retrieve latest messages (limit to 200 for responsive execution while covering historical batches)
            for mid in msg_ids[-200:]:
                typ_m, msg_data = client.fetch(mid, "(RFC822)")
                if typ_m != "OK" or not msg_data or not msg_data[0]:
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Message headers
                message_id = msg.get("Message-ID", f"imap-{mid.decode('utf-8')}")
                from_addr = parseaddr(msg.get("From", ""))[1]
                to_addr = parseaddr(msg.get("To", ""))[1]
                subject = _decode_header_str(msg.get("Subject", ""))
                in_reply_to = msg.get("In-Reply-To")
                references = msg.get("References")

                # Date parsing
                date_hdr = msg.get("Date")
                received_at = datetime.now(timezone.utc)
                if date_hdr:
                    try:
                        received_at = parsedate_to_datetime(date_hdr)
                        if received_at.tzinfo is None:
                            received_at = received_at.replace(tzinfo=timezone.utc)
                    except Exception:
                        pass

                body_text, body_html, attachments = _extract_body_parts(msg)

                results.append(
                    ExpandedInboundEmailDTO(
                        message_id=message_id,
                        from_address=from_addr,
                        to_addresses=[to_addr] if to_addr else [],
                        subject=subject,
                        body_text=body_text,
                        body_html=body_html if body_html else None,
                        received_at=received_at,
                        in_reply_to=in_reply_to,
                        references=references,
                        attachments_metadata=attachments,
                    )
                )

            return results
        except Exception as e:
            logger.error("Error fetching IMAP messages from folder '%s': %s", folder, e)
            return []
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass
                try:
                    client.logout()
                except Exception:
                    pass

    def append_to_label(self, message: EmailMessageDTO, label_name: str) -> bool:
        """Appends the message to the specified IMAP label/mailbox (e.g. RPA-Developer-Application)."""
        if not (self.imap_host and self.imap_user and self.imap_password and label_name):
            return False
        client = None
        try:
            mime_msg = self.build_mime_message(message)
            msg_bytes = mime_msg.as_bytes()
            if self.imap_use_ssl:
                client = imaplib.IMAP4_SSL(self.imap_host, self.imap_port, timeout=self.timeout)
            else:
                client = imaplib.IMAP4(self.imap_host, self.imap_port, timeout=self.timeout)
            client.login(self.imap_user, self.imap_password)
            date_time = imaplib.Time2Internaldate(time.time())
            clean_label = label_name.strip().strip('"')
            typ, _ = client.append(f'"{clean_label}"', r'(\Seen)', date_time, msg_bytes)
            if typ != "OK":
                # Create the label mailbox if it doesn't exist yet
                client.create(f'"{clean_label}"')
                typ, _ = client.append(f'"{clean_label}"', r'(\Seen)', date_time, msg_bytes)
            return typ == "OK"
        except Exception as e:
            logger.warning("Failed to append message to IMAP label '%s': %s", label_name, e)
            return False
        finally:
            if client:
                try:
                    client.logout()
                except Exception:
                    pass

    def check_send_status(self, send_token: str) -> Optional[SendResultDTO]:
        """Returns the send result for the given token if already dispatched."""
        return self._sent_tokens.get(send_token)


# Backward-compatible / ergonomic alias
SmtpImapProvider = GenericSmtpImapProvider

