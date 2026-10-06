"""Job evaluation model for tracking automated search filtering and qualification decisions."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntIdMixin, JsonType, TimestampMixin, UTCDateTime, utc_now


class JobEvaluation(Base, IntIdMixin, TimestampMixin):
    """Stores automated job qualification and evaluation outcomes."""

    __tablename__ = "job_evaluations"

    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Core legacy status preserved for backwards compatibility with analytics queries
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True, default="QUALIFIED"
    )  # QUALIFIED, NOT_QUALIFIED, SKIPPED, DISCOVERED

    # Evolved Qualification Engine Fields
    score: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, index=True
    )  # 0 to 100
    decision: Mapped[str] = mapped_column(
        String(50), nullable=False, default="REVIEW_REQUIRED", index=True
    )  # STRONG_MATCH, GOOD_MATCH, POSSIBLE_MATCH, WEAK_MATCH, REJECTED, REVIEW_REQUIRED
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Evidence completeness (0.0 to 1.0), nullable if uncomputed

    evaluation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="SUCCESS", index=True
    )  # SUCCESS, INSUFFICIENT_DATA, FAILED
    ai_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="NOT_REQUESTED"
    )  # NOT_REQUESTED, APPLIED, UNAVAILABLE, FAILED, SKIPPED

    # Structured Components & Breakdown
    matched_skills: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    missing_skills: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    hard_filter_failures: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JsonType, nullable=True)
    positive_reasons: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    negative_reasons: Mapped[Optional[List[str]]] = mapped_column(JsonType, nullable=True)
    component_scores: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Legacy & Operational fields
    decision_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    candidate_experience: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rules_matched: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)

    # Engine Lineage & Audit
    engine_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    ai_model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False, index=True)

    # Composite Index for fast O(1) retrieval of latest evaluation per job
    __table_args__ = (
        Index("ix_job_eval_job_evaluated", "job_id", "evaluated_at"),
    )

    # Relationship
    job: Mapped["Job"] = relationship("Job", back_populates="evaluations")

    def __repr__(self) -> str:
        return f"<JobEvaluation(id={self.id}, job_id={self.job_id}, score={self.score}, decision='{self.decision}', status='{self.status}')>"


# Domain alias
JobQualification = JobEvaluation
