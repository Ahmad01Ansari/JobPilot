"""Canonical JobOpportunity entity and deduplication audit evidence models."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IntIdMixin, JsonType, TimestampMixin, UTCDateTime, utc_now


class OpportunityStatus(str, enum.Enum):
    """Canonical lifecycle state of a hiring requisition across all platforms."""
    DISCOVERED = "DISCOVERED"
    QUALIFIED = "QUALIFIED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    SKIPPED = "SKIPPED"
    CLOSED = "CLOSED"


class ConfidenceLevel(str, enum.Enum):
    """Calibrated confidence tier for cross-platform identity matching."""
    EXACT = "EXACT"        # Same ATS provider & ATS ID, or identical normalized application URL
    HIGH = "HIGH"          # Company match + Title similarity >= 0.85 + compatible location/remote
    POSSIBLE = "POSSIBLE"  # Company match + Title similarity >= 0.60, ambiguous location or missing URL
    UNIQUE = "UNIQUE"      # Distinct new opportunity


class DedupDecision(str, enum.Enum):
    """Deduplication resolution outcome."""
    LINKED_EXISTING = "LINKED_EXISTING"
    CREATED_NEW = "CREATED_NEW"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED_APPLICATION = "BLOCKED_APPLICATION"


class JobOpportunity(Base, IntIdMixin, TimestampMixin):
    """Canonical hiring requisition entity grouping multi-platform job listings."""

    __tablename__ = "job_opportunities"

    canonical_company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    canonical_company_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    canonical_application_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True, index=True)
    canonical_url_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    ats_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    ats_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    primary_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    work_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default=OpportunityStatus.DISCOVERED.value, index=True)
    applied_job_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    applied_platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    # Relationships
    listings: Mapped[List["Job"]] = relationship(
        "Job",
        back_populates="opportunity",
        foreign_keys="Job.opportunity_id",
    )
    applications: Mapped[List["Application"]] = relationship(
        "Application",
        back_populates="opportunity",
        foreign_keys="Application.opportunity_id",
    )
    evidence: Mapped[List["JobDeduplicationEvidence"]] = relationship(
        "JobDeduplicationEvidence",
        back_populates="opportunity",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<JobOpportunity(id={self.id}, title='{self.canonical_title}', company='{self.canonical_company_name}', status='{self.status}')>"


class JobDeduplicationEvidence(Base, IntIdMixin, TimestampMixin):
    """Immutable audit trail for cross-platform deduplication and linking decisions."""

    __tablename__ = "job_deduplication_evidence"

    incoming_job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matched_opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("job_opportunities.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    matched_job_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    confidence_level: Mapped[str] = mapped_column(String(20), nullable=False)
    decision: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_json: Mapped[Dict[str, Any]] = mapped_column(JsonType, nullable=False)
    decision_reason: Mapped[str] = mapped_column(String(512), nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)

    # Relationships
    opportunity: Mapped[Optional["JobOpportunity"]] = relationship("JobOpportunity", back_populates="evidence")
    incoming_job: Mapped["Job"] = relationship("Job", foreign_keys=[incoming_job_id])

    def __repr__(self) -> str:
        return f"<JobDeduplicationEvidence(incoming={self.incoming_job_id}, opp={self.matched_opportunity_id}, conf='{self.confidence_level}', decision='{self.decision}')>"
