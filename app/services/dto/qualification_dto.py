"""Data Transfer Objects for the Job Qualification Engine."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.services.dto.qualification_enums import (
    AIStatus,
    EvaluationStatus,
    ExperienceStrength,
    QualificationDecision,
)


@dataclass(frozen=True)
class CandidateQualificationContext:
    """Canonical immutable snapshot of verified candidate facts for pure qualification evaluation."""
    candidate_id: int
    target_titles: Tuple[str, ...]
    current_title: str
    years_of_experience: float
    primary_skills: Tuple[str, ...]
    secondary_skills: Tuple[str, ...]
    all_skills: Tuple[str, ...]
    preferred_locations: Tuple[str, ...]
    current_city: str
    willing_to_relocate: bool
    expected_ctc: Optional[int] = None
    current_ctc: Optional[int] = None
    notice_period_days: int = 30
    blacklisted_companies: Tuple[str, ...] = field(default_factory=tuple)
    negative_title_keywords: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class JobQualificationInput:
    """Normalized immutable job facts passed to the qualification engine."""
    job_id: int
    title: str
    company_name: str
    location: Optional[str] = None
    work_style: Optional[str] = None
    experience_text: Optional[str] = None
    required_experience_min: Optional[int] = None
    required_experience_max: Optional[int] = None
    salary_text: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_period: str = "YEAR"
    salary_currency: str = "INR"
    description: Optional[str] = None


@dataclass
class ScoringWeights:
    """Configurable weights for qualification scoring. Baseline hypothesis subject to real-job calibration."""
    role_weight: float = 0.35
    skill_weight: float = 0.35
    experience_weight: float = 0.20
    location_weight: float = 0.10
    notes: str = "Initial baseline hypothesis. Calibrated in Phase 10."


@dataclass
class SkillMatchResult:
    """Outcome of skill matching against a job description."""
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 to 100.0


@dataclass
class ExperienceEvaluationResult:
    """Outcome of experience evaluation incorporating requirement strength."""
    score: float  # 0.0 to 100.0 or normalized
    requirement_strength: ExperienceStrength
    parsed_min_years: Optional[int]
    parsed_max_years: Optional[int]
    is_unknown: bool = False
    reason: str = ""


@dataclass
class QualificationResultDTO:
    """Structured qualification outcome for presentation and persistence."""
    job_id: int
    score: int  # 0 to 100
    decision: QualificationDecision
    confidence: Optional[float] = None  # Nullable evidence completeness (0.0 to 1.0)
    evaluation_status: EvaluationStatus = EvaluationStatus.SUCCESS
    ai_status: AIStatus = AIStatus.NOT_REQUESTED
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    hard_filter_failures: List[Dict[str, Any]] = field(default_factory=list)
    positive_reasons: List[str] = field(default_factory=list)
    negative_reasons: List[str] = field(default_factory=list)
    recommendation: str = ""
    component_scores: Dict[str, Any] = field(default_factory=dict)
    engine_version: str = "1.0.0"
    ai_model_version: Optional[str] = None
    evaluated_at: Optional[datetime] = None
