"""Data transfer objects for Dashboard and Today's Job Hunt presentation layer."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class TodaysHuntItemDTO:
    """Represents a prioritized, actionable task in the Today's Job Hunt work queue."""

    id: str                            # Synthetic unique key, e.g. "INTERVIEW:14" or "FOLLOWUP:8"
    item_type: str                     # INTERVIEW_TODAY, OVERDUE_FOLLOWUP, RECRUITER_REPLY, FOLLOWUP_DUE_TODAY, MANUAL_REVIEW, TOP_OPPORTUNITY, UPCOMING_INTERVIEW
    priority: int                      # 1 (Highest) to 7 (Lowest)
    urgency: str                       # 'URGENT', 'HIGH', 'NORMAL', 'INFORMATIONAL'
    title: str                         # e.g., "Senior Python Engineer" or "Recruiter Reply Received"
    company: str                       # e.g., "Acme Corp"
    subtitle: str                      # e.g., "Technical Round — 11:00 AM" or "Application submitted 5 days ago"
    reason: str                        # Explanation of why this requires attention
    source_entity_type: str            # 'interview', 'followup', 'conversation', 'application', 'job'
    source_entity_id: int              # Primary key of the target entity
    recommended_action: str            # 'PREPARE_INTERVIEW', 'COMPOSE_FOLLOWUP', 'OPEN_CONVERSATION', 'REVIEW_APPLICATION', 'REVIEW_JOB'
    action_payload: Dict[str, Any]     # Serialized routing metadata (e.g., {'job_id': 10, 'application_id': 20})
    due_at: Optional[datetime] = None  # Deadline or scheduled timestamp
    sort_key: str = ""                 # Composite string for tie-breaking


@dataclass
class NextBestActionDTO:
    """Represents the single highest-priority operational action right now."""

    action_id: str                          # e.g., "NBA_INTERVIEW:14", "NBA_REPLY:5", "NBA_TOP_OPP:42"
    action_type: str                        # 'INTERVIEW_TODAY', 'RECRUITER_REPLY', 'OVERDUE_FOLLOWUP', 'FOLLOWUP_DUE_TODAY', 'MANUAL_REVIEW', 'TOP_OPPORTUNITY_REVIEW', 'ALL_CAUGHT_UP'
    title: str                              # e.g., "Interview Today: Senior RPA Developer"
    company: str                            # e.g., "Enterprise Automation Corp"
    subtitle: str                           # e.g., "Technical Round at 03:00 PM (Google Meet)"
    reason: str                             # e.g., "Immediate preparation recommended before your interview starts."
    button_label: str                       # e.g., "Prepare Interview", "Reply to Recruiter", "Compose Follow-up"
    action_name: str                        # e.g., "PREPARE_INTERVIEW", "OPEN_CONVERSATION", "COMPOSE_FOLLOWUP", "REVIEW_JOB"
    action_payload: Dict[str, Any] = field(default_factory=dict)
    badge_text: str = "HIGH PRIORITY"
    badge_variant: str = "danger"           # 'danger', 'warning', 'success', 'purple', 'primary', 'neutral'
    timestamp: Optional[datetime] = None


@dataclass
class TopOpportunityDTO:
    """Represents a high-quality qualified unapplied job opportunity with explainability."""

    job_id: int
    title: str
    company: str
    location: Optional[str]
    platform: str
    application_method: str                 # 'EASY_APPLY', 'COMPANY_PORTAL'
    score: int                              # 0 to 100
    decision: str                           # 'STRONG_MATCH', 'GOOD_MATCH'
    evaluation_status: str                  # 'SUCCESS'
    confidence: Optional[float]
    rank: int = 1                           # 1 to 5
    freshness_status: str = "QUALIFIED"     # 'QUALIFIED', 'PENDING', 'FAILED', 'STALE'
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    application_url: Optional[str] = None
    discovered_at: Optional[datetime] = None
    recommended_action: str = "REVIEW_JOB"  # Contextual action (no blind automation)


@dataclass
class PlatformMetricDTO:
    """Breakdown metrics for a specific source platform."""

    platform_key: str                       # 'linkedin', 'naukri', 'indeed', 'glassdoor', 'foundit'
    platform_name: str                      # 'LinkedIn', 'Naukri', 'Indeed', 'Glassdoor', 'Foundit'
    discovered_count: int = 0
    applied_count: int = 0
    interview_count: int = 0
    offer_count: int = 0
    application_rate: float = 0.0           # applied / discovered * 100
    interview_rate: float = 0.0             # interview / applied * 100
    offer_rate: float = 0.0                 # offer / applied * 100


@dataclass
class SearchPerformanceDTO:
    """Unified single authoritative data model powering Search Performance & ATS Funnel."""

    preset: str = "30D"                     # 'TODAY', '7D', '30D', '90D', 'ALL'
    total_discovered: int = 0
    total_qualified: int = 0
    total_applied: int = 0
    total_responses: int = 0
    total_interviews: int = 0
    total_offers: int = 0
    application_conversion_pct: float = 0.0 # applied / qualified * 100
    interview_conversion_pct: float = 0.0   # interviews / applied * 100
    offer_conversion_pct: float = 0.0       # offers / applied * 100
    funnel_stages: List[Dict[str, Any]] = field(default_factory=list)
    platform_metrics: List[PlatformMetricDTO] = field(default_factory=list)


@dataclass
class DailyProgressDTO:
    """Tracks verified progress metrics achieved today."""

    discovered_today: int = 0               # Jobs scraped/created today
    qualified_today: int = 0                # Jobs evaluated today
    applications_submitted_today: int = 0   # Applications submitted today
    outreach_sent_today: int = 0            # Outbound communications sent today
    followups_completed_today: int = 0      # Follow-up tasks completed today


@dataclass
class ReadinessSummaryDTO:
    """Component-level readiness state for candidate profile, resume, QnA, and platforms."""

    profile_complete: bool = False          # Verified profile facts exist
    resume_configured: bool = False         # Default active resume is set
    qna_answered_ratio: float = 0.0         # e.g., 0.82 (82%)
    qna_answered_count: int = 0
    qna_total_count: int = 0
    platforms: Dict[str, str] = field(default_factory=dict)  # e.g., {'linkedin': 'READY', 'naukri': 'READY'}


@dataclass
class DashboardSnapshotDTO:
    """Unified snapshot of all dashboard sections loaded asynchronously."""

    next_best_action: Optional[NextBestActionDTO] = None
    hunt_items: List[TodaysHuntItemDTO] = field(default_factory=list)
    top_opportunities: List[TopOpportunityDTO] = field(default_factory=list)
    daily_progress: DailyProgressDTO = field(default_factory=DailyProgressDTO)
    search_performance: Optional[SearchPerformanceDTO] = None
    readiness: ReadinessSummaryDTO = field(default_factory=ReadinessSummaryDTO)
    pipeline_summary: Dict[str, int] = field(default_factory=dict)
    recent_activities: List[Any] = field(default_factory=list)

