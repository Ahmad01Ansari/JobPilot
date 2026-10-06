"""Data Transfer Objects for Outreach Center operations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from app.services.dto.outreach_enums import InboundClassification, MessageStatus


@dataclass
class OutreachCreateDTO:
    """Payload for creating a new outbound outreach message and associated application."""
    account_id: str = "default"
    # Target Job (either existing ID or manual specification)
    job_id: Optional[int] = None
    manual_job_title: Optional[str] = None
    manual_company_name: Optional[str] = None
    manual_job_url: Optional[str] = None

    # Existing application binding (for bulk outreach to existing applications)
    existing_application_id: Optional[int] = None

    # Recruiter Contact
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_designation: Optional[str] = None

    # Resume & Template
    resume_id: Optional[int] = None
    template_id: Optional[int] = None

    # Message Content
    subject: str = ""
    body_text: str = ""
    body_html: Optional[str] = None

    # Schedule & Automation
    schedule_time: Optional[datetime] = None
    followup_cadence_days: List[int] = field(default_factory=lambda: [4, 10, 17])
    override_duplicate: bool = False


@dataclass
class EmailMessageDTO:
    """Standardized message payload sent to an EmailProvider adapter."""
    account_id: str
    send_token: str
    from_address: str
    from_name: str
    to_address: str
    subject: str
    body_text: str
    cc_addresses: List[str] = field(default_factory=list)
    body_html: Optional[str] = None
    attachment_snapshot_path: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    provider_thread_id: Optional[str] = None


@dataclass
class SendResultDTO:
    """Normalized response from an EmailProvider adapter dispatch attempt."""
    success: bool
    send_token: str
    status: MessageStatus
    provider_message_id: Optional[str] = None
    provider_thread_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class ExpandedInboundEmailDTO:
    """Rich metadata for an incoming email received from an email provider."""
    message_id: str
    from_address: str
    to_addresses: List[str]
    subject: str
    body_text: str
    received_at: datetime
    thread_id: Optional[str] = None
    in_reply_to: Optional[str] = None
    references: Optional[str] = None
    cc_addresses: List[str] = field(default_factory=list)
    body_html: Optional[str] = None
    attachments_metadata: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SyncCheckpointDTO:
    """Cursor state for periodic mailbox synchronization."""
    account_id: str
    last_sync_at: Optional[datetime] = None
    last_history_id: Optional[str] = None
    cursor_token: Optional[str] = None


@dataclass
class DuplicateMatchResultDTO:
    """Diagnostics and evaluation details for lifecycle-aware duplicate detection."""
    is_duplicate: bool
    match_tier: Optional[str] = None  # EXACT_JOB_ID, NORMALIZED_COMPANY_TITLE, CONTACT_TITLE, SOURCE_URL
    existing_application_id: Optional[int] = None
    existing_status: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    applied_at: Optional[datetime] = None
    can_override: bool = True


@dataclass
class ConnectionStatusDTO:
    """Status result from testing connection to an email provider."""
    success: bool
    provider_name: str
    message: str = ""
    account_email: Optional[str] = None
    tested_at: Optional[datetime] = None
