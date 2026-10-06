"""Canonical enumerations and state definitions for Outreach Center."""

from enum import Enum


class MessageStatus(str, Enum):
    """Lifecycle states of an individual email transmission."""
    DRAFT = "DRAFT"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"


class ConversationState(str, Enum):
    """Aggregate state of communication/interaction for a candidate outreach."""
    DRAFTING = "DRAFTING"
    WAITING = "WAITING"
    REPLIED = "REPLIED"
    NEEDS_ACTION = "NEEDS_ACTION"
    COMPLETED = "COMPLETED"


class FollowUpStatus(str, Enum):
    """Lifecycle states of a scheduled follow-up reminder."""
    PENDING = "PENDING"
    DUE = "DUE"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class InboundClassification(str, Enum):
    """AI and rule-based classification categories for incoming recruiter responses."""
    ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
    RECRUITER_RESPONSE = "RECRUITER_RESPONSE"
    INTERVIEW_REQUEST = "INTERVIEW_REQUEST"
    INFORMATION_REQUEST = "INFORMATION_REQUEST"
    ASSESSMENT_REQUEST = "ASSESSMENT_REQUEST"
    REJECTION = "REJECTION"
    OFFER = "OFFER"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


# Canonical single constants to prevent string variation bugs (e.g. 'email', 'Email', 'EMAIL')
CANONICAL_APPLICATION_METHOD_EMAIL = "EMAIL"
CANONICAL_PLATFORM_EMAIL = "EMAIL"
CANONICAL_SOURCE_DIRECT_EMAIL = "DIRECT_EMAIL"


class NextActionOwner(str, Enum):
    """The party responsible for executing the next required action."""
    USER = "USER"
    RECRUITER = "RECRUITER"
    SYSTEM = "SYSTEM"
    NONE = "NONE"


class NextActionType(str, Enum):
    """Specific operational next action to be taken on an outreach case."""
    REPLY_TO_RECRUITER = "REPLY_TO_RECRUITER"
    SEND_FOLLOW_UP = "SEND_FOLLOW_UP"
    REVIEW_RECRUITER_REPLY = "REVIEW_RECRUITER_REPLY"
    REVIEW_ATTACHMENT = "REVIEW_ATTACHMENT"
    CONFIRM_INTERVIEW = "CONFIRM_INTERVIEW"
    SCHEDULE_INTERVIEW = "SCHEDULE_INTERVIEW"
    UPDATE_APPLICATION = "UPDATE_APPLICATION"
    WAIT_FOR_RECRUITER = "WAIT_FOR_RECRUITER"
    PAUSE_CADENCE = "PAUSE_CADENCE"
    RESUME_CADENCE = "RESUME_CADENCE"
    NONE = "NONE"


class ConversationOpState(str, Enum):
    """Standardized operational conversation state separating outbox from relationship lifecycle."""
    NEEDS_ACTION = "NEEDS_ACTION"
    WAITING_FOR_RECRUITER = "WAITING_FOR_RECRUITER"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    REPLIED = "REPLIED"
    SCHEDULED = "SCHEDULED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CLOSED = "CLOSED"
    UNKNOWN = "UNKNOWN"


class CadenceState(str, Enum):
    """Overall status of the automated follow-up cadence."""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    NONE = "NONE"


class PriorityLevel(str, Enum):
    """Operational urgency level of an outreach case."""
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"


class WorkQueueSection(str, Enum):
    """Categorization buckets for the Outreach Operations Work Queue."""
    TODAY = "TODAY"
    UPCOMING = "UPCOMING"
    WAITING = "WAITING"
    CLOSED = "CLOSED"

