"""Factory and registry for Outreach Email Providers."""

from typing import Dict, Optional

from app.services.email.mock_provider import MockEmailProvider
from app.services.email.provider import EmailProvider
from app.services.email.smtp_imap_provider import GenericSmtpImapProvider
from app.services.secrets_service import SecretsService

_PROVIDER_REGISTRY: Dict[str, EmailProvider] = {}


def register_email_provider(account_id: str, provider: EmailProvider) -> None:
    """Manually registers an EmailProvider instance for testing or custom dependency injection."""
    _PROVIDER_REGISTRY[account_id] = provider


def unregister_email_provider(account_id: str) -> None:
    """Removes a registered provider from the cache."""
    _PROVIDER_REGISTRY.pop(account_id, None)


def get_email_provider(
    account_id: str = "default",
    secrets_service: Optional[SecretsService] = None,
) -> EmailProvider:
    """Retrieves or builds the appropriate EmailProvider for the requested account."""
    if account_id in _PROVIDER_REGISTRY:
        return _PROVIDER_REGISTRY[account_id]

    # In explicit mock or test mode, return a MockEmailProvider
    if account_id == "mock":
        provider = MockEmailProvider(account_email="candidate@jobpilot.mock")
        _PROVIDER_REGISTRY[account_id] = provider
        return provider

    # Load configuration from SecretsService, config/secrets.py, or environment
    sec_service = secrets_service or SecretsService()
    creds = sec_service.get_email_credentials(account_id=account_id)

    provider = GenericSmtpImapProvider(
        smtp_host=creds["smtp_host"],
        smtp_port=creds["smtp_port"],
        smtp_user=creds["user"],
        smtp_password=creds["password"],
        smtp_use_ssl=creds["smtp_use_ssl"],
        smtp_use_tls=creds["smtp_use_tls"],
        imap_host=creds["imap_host"],
        imap_port=creds["imap_port"],
        imap_user=creds["user"],
        imap_password=creds["password"],
        imap_use_ssl=creds["imap_use_ssl"],
    )
    _PROVIDER_REGISTRY[account_id] = provider
    return provider
