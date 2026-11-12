"""Validation utilities for domain state machines and entity normalization."""

import re
from typing import Optional, Set, Tuple


LEGAL_SUFFIXES_REGEX = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s+limited|ltd\.?|inc\.?|incorporated|corp\.?|corporation|llc|llp|gmbh)\b",
    re.IGNORECASE,
)


def normalize_company_name(name: str) -> str:
    """Deterministically normalizes a company name for deduplication.

    - Lowercases and collapses multiple spaces.
    - Strips isolated legal registration suffixes (Pvt Ltd, LLC, Inc, etc.)
    - Preserves distinctive business terms (Technologies, Solutions, Media, etc.)
    """
    if not name:
        return ""

    cleaned = name.strip().lower()
    # Replace commas, dots, dashes with spaces
    cleaned = re.sub(r"[,.\-_/]", " ", cleaned)
    # Remove legal suffixes
    cleaned = LEGAL_SUFFIXES_REGEX.sub("", cleaned)
    # Collapse multiple spaces and strip
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


# Canonical lifecycle classification sets (Single Source of Truth)
UNAPPLIED_ALIAS_STATUSES = {"NOT_APPLIED", "DISCOVERED", "QUALIFIED", "EXTERNAL"}

PRE_APPLICATION_STATUSES = {
    "NOT_APPLIED",
    "APPLYING",
    "MANUAL_REQUIRED",
    "FAILED",
    "SKIPPED",
    "UNKNOWN",
    "JUNK",
}

PIPELINE_STATUSES = (
    "SUBMITTED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "RECRUITER_CONTACTED",
    "ASSESSMENT",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
)

TERMINAL_OUTCOME_STATUSES = {"OFFER", "REJECTED", "WITHDRAWN", "JUNK"}

CANONICAL_STAGE_LABELS = {
    "NOT_APPLIED": "Not Applied",
    "APPLYING": "Applying",
    "MANUAL_REQUIRED": "Manual Check",
    "FAILED": "Failed",
    "SKIPPED": "Skipped",
    "UNKNOWN": "Unknown",
    "SUBMITTED": "Submitted",
    "UNDER_REVIEW": "Under Review",
    "SHORTLISTED": "Shortlisted",
    "RECRUITER_CONTACTED": "Recruiter Call",
    "ASSESSMENT": "Assessment",
    "INTERVIEW": "Interview",
    "OFFER": "Offer",
    "REJECTED": "Rejected",
    "WITHDRAWN": "Withdrawn",
    "JUNK": "Junk",
}


def normalize_display_status(status: Optional[str]) -> str:
    """Normalizes legacy discovery/external/internal tracker statuses to canonical UI stages.

    Jobs discovered from any source (including Company Portal / External) share the single
    canonical 'NOT_APPLIED' stage until an application or explicit skip/failure occurs.
    """
    st = (status or "").strip().upper()
    if not st or st in UNAPPLIED_ALIAS_STATUSES:
        return "NOT_APPLIED"
    if st == "ALREADY_APPLIED":
        return "SKIPPED"
    return st


# Application status state machine definitions
ALLOWED_TRANSITIONS = {
    None: {
        "NOT_APPLIED",
        "APPLYING",
        "SUBMITTED",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
        "MANUAL_REQUIRED",
        "FAILED",
        "DISCOVERED",
        "QUALIFIED",
        "SKIPPED",
        "JUNK",
    },
    "NOT_APPLIED": {
        "APPLYING",
        "SUBMITTED",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
        "MANUAL_REQUIRED",
        "FAILED",
        "SKIPPED",
        "JUNK",
    },
    "DISCOVERED": {"NOT_APPLIED", "QUALIFIED", "APPLYING", "SUBMITTED", "SKIPPED", "JUNK"},
    "QUALIFIED": {"NOT_APPLIED", "APPLYING", "SUBMITTED", "SKIPPED", "JUNK"},
    "SKIPPED": {"NOT_APPLIED", "QUALIFIED", "APPLYING", "SUBMITTED", "JUNK"},
    "JUNK": {"NOT_APPLIED", "DISCOVERED", "QUALIFIED", "APPLYING", "SUBMITTED", "SKIPPED"},
    "APPLYING": {
        "NOT_APPLIED",
        "SUBMITTED",
        "FAILED",
        "UNKNOWN",
        "MANUAL_REQUIRED",
        "EXTERNAL",
        "SKIPPED",
        "JUNK",
    },
    "FAILED": {"NOT_APPLIED", "APPLYING", "SUBMITTED", "MANUAL_REQUIRED", "SKIPPED", "JUNK"},
    "UNKNOWN": {"NOT_APPLIED", "SUBMITTED", "FAILED", "APPLYING", "MANUAL_REQUIRED", "JUNK"},
    "MANUAL_REQUIRED": {"NOT_APPLIED", "APPLYING", "SUBMITTED", "SKIPPED", "FAILED", "JUNK"},
    "EXTERNAL": {"NOT_APPLIED", "SUBMITTED", "APPLYING", "SKIPPED", "WITHDRAWN", "JUNK"},
    "SUBMITTED": {
        "NOT_APPLIED",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "REJECTED",
        "WITHDRAWN",
        "JUNK",
    },
    "UNDER_REVIEW": {
        "SUBMITTED",
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
    },
    "SHORTLISTED": {
        "UNDER_REVIEW",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
    },
    "RECRUITER_CONTACTED": {
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "REJECTED",
        "WITHDRAWN",
    },
    "ASSESSMENT": {
        "INTERVIEW",
        "OFFER",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "REJECTED",
        "WITHDRAWN",
    },
    "INTERVIEW": {
        "INTERVIEW",
        "OFFER",
        "ASSESSMENT",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "SUBMITTED",
        "REJECTED",
        "WITHDRAWN",
    },
    "OFFER": {
        "OFFER",
        "INTERVIEW",
        "REJECTED",
        "WITHDRAWN",
    },
    "REJECTED": set(),
    "WITHDRAWN": set(),
}


def validate_status_transition(
    current_status: Optional[str],
    new_status: str,
    allow_override: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validates an application status transition against the state machine.

    Args:
        current_status: The existing status of the application (or None if creating)
        new_status: The proposed target status
        allow_override: If True, permits manual administrative override of terminal states

    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    if allow_override:
        return True, None

    if current_status == new_status:
        return True, None

    if new_status.upper() == "JUNK" or (current_status and current_status.upper() == "JUNK"):
        return True, None

    allowed: Set[str] = ALLOWED_TRANSITIONS.get(current_status, set())
    if new_status in allowed:
        return True, None

    return False, (
        f"Invalid status transition from '{current_status}' to '{new_status}'. "
        f"Allowed target states: {sorted(list(allowed)) if allowed else 'None (Terminal state)'}."
    )
