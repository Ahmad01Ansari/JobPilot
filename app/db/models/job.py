"""Normalized Job entity model with fingerprinting and raw text preservation."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, JsonType, UTCDateTime, utc_now


def generate_job_fingerprint(
    platform: str,
    company: str,
    title: str,
    location: Optional[str] = None,
    source_url: Optional[str] = None,
    external_job_id: Optional[str] = None,
) -> str:
    """Computes a deterministic SHA-256 fingerprint for a job listing to prevent duplicates."""
    components = [
        str(platform or "").strip().lower(),
        str(external_job_id or "").strip().lower() if external_job_id else "",
        str(company or "").strip().lower(),
        str(title or "").strip().lower(),
        str(location or "").strip().lower() if location else "",
        str(source_url or "").strip().lower() if source_url else "",
    ]
    raw_key = "|".join(c for c in components if c)
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


class Job(Base, IntIdMixin, TimestampMixin):
    """Normalized job posting entity."""

    __tablename__ = "jobs"

    company_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    external_job_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    job_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    work_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Remote, Hybrid, On-site

    # Preserved raw text alongside parsed bounds
    experience_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    required_experience_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_experience_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    salary_text: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    salary_min: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    salary_max: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    salary_period: Mapped[str] = mapped_column(String(20), default="YEAR")  # YEAR, MONTH, HOUR, UNKNOWN
    salary_currency: Mapped[str] = mapped_column(String(10), default="INR")

    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    apply_type: Mapped[str] = mapped_column(String(50), default="DIRECT")  # DIRECT, QUESTIONNAIRE, EXTERNAL (Deprecated in favor of application_method)
    application_method: Mapped[str] = mapped_column(String(50), default="EASY_APPLY")  # EASY_APPLY, COMPANY_PORTAL, MANUAL, UNKNOWN
    application_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)

    # Lifecycle & activity tracking
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    # Canonical Opportunity link
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("job_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    canonical_url_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Relationships
    company: Mapped[Optional["Company"]] = relationship("Company", back_populates="jobs")
    opportunity: Mapped[Optional["JobOpportunity"]] = relationship(
        "JobOpportunity", back_populates="listings", foreign_keys=[opportunity_id]
    )
    evaluations: Mapped[List["JobEvaluation"]] = relationship(
        "JobEvaluation", back_populates="job", cascade="all, delete-orphan"
    )
    applications: Mapped[List["Application"]] = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, platform='{self.platform}', title='{self.title}', company='{self.company_raw}')>"
