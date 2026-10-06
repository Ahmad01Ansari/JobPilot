"""Email provider abstractions and implementations."""

from app.services.email.factory import (
    get_email_provider,
    register_email_provider,
    unregister_email_provider,
)
from app.services.email.mock_provider import MockEmailProvider
from app.services.email.provider import EmailProvider
from app.services.email.smtp_imap_provider import GenericSmtpImapProvider

__all__ = [
    "EmailProvider",
    "MockEmailProvider",
    "GenericSmtpImapProvider",
    "get_email_provider",
    "register_email_provider",
    "unregister_email_provider",
]
