"""Structured domain events and state definitions for automation workflows."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AutomationState(str, Enum):
    """Lifecycle states for automation execution."""

    IDLE = "IDLE"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOP_REQUESTED = "STOP_REQUESTED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class InterventionType(str, Enum):
    """Specific manual or external interventions encountered during automation."""

    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    MANUAL_ACTION_REQUIRED = "MANUAL_ACTION_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    PRE_SUBMISSION_REVIEW = "PRE_SUBMISSION_REVIEW"
    UNKNOWN_REQUIRED_FIELD = "UNKNOWN_REQUIRED_FIELD"
    TWO_FACTOR_AUTH = "TWO_FACTOR_AUTH"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class JobDiscoveredEvent:
    """Dispatched when a job card or posting is encountered."""

    run_id: str = "default"
    platform: str = "unknown"
    title: str = "Unknown Job"
    company: str = "Unknown Company"
    external_job_id: Optional[str] = None
    location: Optional[str] = None
    url: Optional[str] = None
    application_method: str = "EASY_APPLY"
    application_url: Optional[str] = None
    description: Optional[str] = None
    experience_text: Optional[str] = None
    salary_text: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    required_experience_min: Optional[int] = None
    required_experience_max: Optional[int] = None
    work_style: Optional[str] = None
    timestamp: datetime = field(default_factory=_now_utc)



@dataclass
class JobEvaluatedEvent:
    """Dispatched when qualification logic filters a discovered job."""

    run_id: str
    platform: str
    title: str
    company: str
    is_qualified: bool
    external_job_id: Optional[str] = None
    reason: Optional[str] = None
    timestamp: datetime = field(default_factory=_now_utc)


@dataclass
class ApplicationSubmittedEvent:
    """Dispatched when an application is successfully submitted by an engine."""

    run_id: str
    platform: str
    title: str
    company: str
    job_id: Optional[int] = None
    external_job_id: Optional[str] = None
    status: str = "SUBMITTED"
    submitted_at: datetime = field(default_factory=_now_utc)
    source_url: Optional[str] = None


@dataclass
class AutomationProgressEvent:
    """Dispatched periodically with execution counters and current activity."""

    run_id: str
    platform: str
    current_term: Optional[str] = None
    current_job: Optional[str] = None
    jobs_discovered: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    applications_submitted: int = 0
    errors_count: int = 0
    timestamp: datetime = field(default_factory=_now_utc)


@dataclass
class AutomationInterventionEvent:
    """Dispatched when human interaction is required (CAPTCHA, login, OTP, review)."""

    run_id: str
    platform: str
    intervention_type: InterventionType
    message: str
    action_url: Optional[str] = None
    details: Optional[dict] = None
    timestamp: datetime = field(default_factory=_now_utc)


@dataclass
class AutomationRunResult:
    """Final outcome summary for a completed or terminated automation session."""

    run_id: str
    platform: str
    status: AutomationState
    started_at: datetime
    finished_at: datetime
    jobs_discovered: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    applications_submitted: int = 0
    errors_count: int = 0
    stop_reason: Optional[str] = None
