"""Enums for the Job Qualification Engine."""

from enum import Enum


class QualificationDecision(str, Enum):
    """Explicit qualification outcome decision indicating alignment strength."""
    STRONG_MATCH = "STRONG_MATCH"
    GOOD_MATCH = "GOOD_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    WEAK_MATCH = "WEAK_MATCH"
    REJECTED = "REJECTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class EvaluationStatus(str, Enum):
    """Operational status of the deterministic evaluation pipeline."""
    SUCCESS = "SUCCESS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    FAILED = "FAILED"


class AIStatus(str, Enum):
    """Operational status of the optional AI semantic enhancement layer."""
    NOT_REQUESTED = "NOT_REQUESTED"
    APPLIED = "APPLIED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExperienceStrength(str, Enum):
    """Qualitative strength of experience requirement specified in a job posting."""
    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"
    FLEXIBLE = "FLEXIBLE"
    UNKNOWN = "UNKNOWN"
