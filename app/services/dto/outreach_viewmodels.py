"""Presentation-layer ViewModels for the Outreach Center redesign.

These dataclasses provide structured, presentation-ready data to UI components,
preventing direct multi-table queries from widgets.  UI code consumes these
ViewModels exclusively — never raw ORM models.

Ref: outreach_redesign_plan.md §3 — Data & Presentation Models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


# ---------------------------------------------------------------------------
# 3.1  Conversation State & Next Action Enums
# ---------------------------------------------------------------------------

class PresentationConversationState(str, Enum):
    """Aggregate UI-visible state for a recruitment conversation."""
    NEEDS_ACTION = "NEEDS_ACTION"       # Recruiter asked question or interview request
    WAITING = "WAITING"                 # Awaiting recruiter reply
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"    # Cadence step is overdue
    REPLIED = "REPLIED"                 # Recruiter replied, no immediate action
    SCHEDULED = "SCHEDULED"             # Outbound email scheduled for future
    PAUSED = "PAUSED"                   # Follow-up sequence manually/auto-paused
    COMPLETED = "COMPLETED"             # Offer, Rejected, or Withdrawn
    NEEDS_REVIEW = "NEEDS_REVIEW"       # Unmatched inbound requiring manual link


# ---------------------------------------------------------------------------
# 3.1  Next Action Recommendation
# ---------------------------------------------------------------------------

@dataclass
class NextActionRecommendation:
    """AI/rule-derived suggestion for the candidate's next step on a conversation."""
    action_type: str            # REPLY, SCHEDULE_INTERVIEW, EXECUTE_FOLLOWUP, REVIEW_ATTACHMENT, WAIT
    headline: str               # e.g. "Reply with Availability"
    rationale: str              # e.g. "Recruiter requested interview availability"
    cta_label: str              # e.g. "Draft Reply"
    suggested_status: Optional[str] = None   # e.g. "INTERVIEWING"
    due_date: Optional[datetime] = None


# ---------------------------------------------------------------------------
# 3.2  Aggregated Conversation ViewModel (Inbox card level)
# ---------------------------------------------------------------------------

@dataclass
class OutreachConversationViewModel:
    """Single-row ViewModel powering an inbox conversation card."""
    application_id: Optional[int]
    company_name: str
    job_title: str
    recruiter_name: str
    recruiter_email: str
    recruitment_status: str           # APPLIED, UNDER_REVIEW, INTERVIEWING, OFFER, REJECTED
    state: PresentationConversationState
    next_action: NextActionRecommendation
    last_activity_at: Optional[datetime]
    last_snippet: str
    has_unmatched_inbound: bool = False
    active_draft_preview: Optional[str] = None
    resume_version_tag: Optional[str] = None
    unread_count: int = 0
    is_priority: bool = False


# ---------------------------------------------------------------------------
# 3.3  Follow-Up Step ViewModel
# ---------------------------------------------------------------------------

@dataclass
class FollowUpStepViewModel:
    """Presentation model for a single follow-up cadence step."""
    id: int
    step_number: int
    due_at: Optional[datetime]
    status: str               # PENDING, DUE, COMPLETED, PAUSED, SKIPPED, CANCELLED
    paused_reason: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# 3.4  Conversation Timeline ViewModel (detail view)
# ---------------------------------------------------------------------------

@dataclass
class TimelineMessageViewModel:
    """A single email in the conversation thread."""
    id: int
    direction: str             # INBOUND or OUTBOUND
    status: str                # SENT, DRAFT, FAILED, etc.
    occurred_at: Optional[datetime]
    subject: Optional[str]
    snippet: str               # First ~160 chars
    body_text: str             # Full message body
    sender_email: Optional[str]
    recipient_email: Optional[str]
    attachment_path: Optional[str] = None
    attachment_name: Optional[str] = None
    resume_version_tag: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ContactViewModel:
    """Recruiter contact information for the context panel."""
    id: int
    name: str
    email: str
    designation: Optional[str] = None


@dataclass
class ResumeSnapshotViewModel:
    """Historical resume snapshot attached to the conversation."""
    id: int
    name: str
    role_target: str
    version_tag: str           # e.g. "v2.1"
    file_path: Optional[str] = None
    file_exists: bool = True


@dataclass
class ConversationDetailViewModel:
    """Full detail ViewModel for the recruitment workspace center panel."""
    application_id: int
    company_name: str
    job_title: str
    recruitment_status: str
    applied_at: Optional[datetime]
    state: PresentationConversationState
    next_action: NextActionRecommendation
    contact: Optional[ContactViewModel]
    resume: Optional[ResumeSnapshotViewModel]
    messages: List[TimelineMessageViewModel] = field(default_factory=list)
    follow_ups: List[FollowUpStepViewModel] = field(default_factory=list)
    active_draft_body: Optional[str] = None
    active_draft_subject: Optional[str] = None


# ---------------------------------------------------------------------------
# 3.5  Outreach Operations V2 Models (Work Queue & Bulk Pipeline)
# ---------------------------------------------------------------------------

from app.services.dto.outreach_enums import (
    CadenceState,
    ConversationOpState,
    NextActionOwner,
    NextActionType,
    PriorityLevel,
    WorkQueueSection,
)


@dataclass
class OutreachCaseOperationViewModel:
    """Consolidated operational projection of an Outreach Case for high-volume workflows."""
    application_id: int
    company_name: str
    job_title: str
    recruitment_status: str
    contact_id: Optional[int]
    contact_name: str
    contact_email: str
    contact_designation: Optional[str]
    conversation_state: ConversationOpState
    next_action_type: NextActionType
    next_action_owner: NextActionOwner
    next_action_due_at: Optional[datetime]
    next_action_headline: str
    next_action_rationale: str
    next_action_cta: str
    priority: PriorityLevel
    cadence_state: CadenceState
    cadence_active_step: int
    cadence_total_steps: int
    last_contact_at: Optional[datetime]
    last_inbound_at: Optional[datetime]
    last_outbound_at: Optional[datetime]
    last_snippet: str
    unread_attention: bool
    is_priority: bool
    resume_version_tag: Optional[str]
    has_draft: bool
    work_queue_section: WorkQueueSection


@dataclass
class WorkQueueGroupViewModel:
    """A prioritized section of the Outreach Operations Work Queue."""
    section: WorkQueueSection
    headline: str
    count: int
    cases: List[OutreachCaseOperationViewModel] = field(default_factory=list)


@dataclass
class BulkTargetPreviewItemDTO:
    """Individual recipient preview row in the Bulk Outreach Composer."""
    application_id: Optional[int]
    company_name: str
    job_title: str
    recruiter_name: str
    recruiter_email: str
    resume_id: Optional[int]
    resume_name: str
    is_valid: bool
    validation_error: Optional[str]
    is_duplicate: bool
    duplicate_tier: Optional[str]
    current_state: ConversationOpState
    next_action_type: NextActionType
    is_selected: bool = True


@dataclass
class BulkTargetValidationResultDTO:
    """Aggregated validation payload presented to the user before bulk email queueing."""
    total_selected: int
    valid_count: int
    duplicate_count: int
    error_count: int
    items: List[BulkTargetPreviewItemDTO] = field(default_factory=list)

