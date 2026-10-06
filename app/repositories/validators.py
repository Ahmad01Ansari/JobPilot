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


# Application status state machine definitions
ALLOWED_TRANSITIONS = {
    None: {
        "APPLYING",
        "SUBMITTED",
        "UNDER_REVIEW",
        "SHORTLISTED",
        "DISCOVERED",
        "QUALIFIED",
        "SKIPPED",
        "JUNK",
    },
    "DISCOVERED": {"QUALIFIED", "SKIPPED", "JUNK"},
    "QUALIFIED": {"APPLYING", "SKIPPED", "JUNK"},
    "SKIPPED": {"QUALIFIED", "APPLYING", "JUNK"},  # Allow manual re-qualification or junking
    "JUNK": {"DISCOVERED", "QUALIFIED", "APPLYING", "SUBMITTED", "SKIPPED", "NOT_APPLIED"},
    "APPLYING": {
        "SUBMITTED",
        "FAILED",
        "UNKNOWN",
        "MANUAL_REQUIRED",
        "EXTERNAL",
        "JUNK",
    },
    "FAILED": {"APPLYING", "JUNK"},  # Manual retry or junking
    "UNKNOWN": {"SUBMITTED", "FAILED", "APPLYING", "JUNK"},  # Manual confirmation or junking
    "MANUAL_REQUIRED": {"APPLYING", "SUBMITTED", "SKIPPED", "JUNK"},
    "EXTERNAL": {"SUBMITTED", "APPLYING", "WITHDRAWN", "JUNK"},
    "SUBMITTED": {
        "UNDER_REVIEW",
        "SHORTLISTED",
        "JUNK",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "REJECTED",
        "WITHDRAWN",
    },
    "UNDER_REVIEW": {
        "SHORTLISTED",
        "RECRUITER_CONTACTED",
        "ASSESSMENT",
        "INTERVIEW",
        "OFFER",
        "REJECTED",
        "WITHDRAWN",
    },
    "SHORTLISTED": {
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
        "REJECTED",
        "WITHDRAWN",
    },
    "ASSESSMENT": {
        "INTERVIEW",
        "OFFER",
        "UNDER_REVIEW",
        "REJECTED",
        "WITHDRAWN",
    },
    "INTERVIEW": {
        "INTERVIEW",  # Multiple rounds
        "OFFER",
        "ASSESSMENT",
        "UNDER_REVIEW",
        "REJECTED",
        "WITHDRAWN",
    },
    "OFFER": {
        "OFFER",
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
