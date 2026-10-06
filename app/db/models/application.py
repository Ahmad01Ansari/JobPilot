"""Application entity model managing application lifecycle and recruitment pipeline states."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime


class Application(Base, IntIdMixin, TimestampMixin):
    """Represents an application made to a specific job listing."""

    __tablename__ = "applications"

    job_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resume_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("resumes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Lifecycle & Pipeline status:
    # Recruitment Pipeline: SUBMITTED, UNDER_REVIEW, SHORTLISTED, RECRUITER_CONTACTED, ASSESSMENT, INTERVIEW, OFFER, REJECTED, WITHDRAWN
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="APPLYING", index=True)
    # Automation Lifecycle (Option A): NOT_STARTED, RUNNING, SUCCESS, FAILED, MANUAL_REQUIRED, UNKNOWN
    automation_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="NOT_STARTED", index=True)
    application_type: Mapped[str] = mapped_column(String(50), default="EASY_APPLY")
    applied_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    skip_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    external_job_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Outreach Operations V2: indexed triage flags
    is_unread: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, index=True)
    is_priority: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True, index=True)

    # Canonical Opportunity link
    opportunity_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("job_opportunities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="applications")
    opportunity: Mapped[Optional["JobOpportunity"]] = relationship(
        "JobOpportunity", back_populates="applications", foreign_keys=[opportunity_id]
    )
    user: Mapped[Optional["User"]] = relationship("User", back_populates="applications")
    resume: Mapped[Optional["Resume"]] = relationship("Resume", back_populates="applications")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="applications")

    status_history: Mapped[List["ApplicationStatusHistory"]] = relationship(
        "ApplicationStatusHistory", back_populates="application", cascade="all, delete-orphan"
    )
    communications: Mapped[List["Communication"]] = relationship(
        "Communication", back_populates="application", cascade="all, delete-orphan"
    )
    interviews: Mapped[List["Interview"]] = relationship(
        "Interview", back_populates="application", cascade="all, delete-orphan"
    )
    follow_ups: Mapped[List["FollowUp"]] = relationship(
        "FollowUp", back_populates="application", cascade="all, delete-orphan"
    )
    offer: Mapped[Optional["Offer"]] = relationship(
        "Offer", back_populates="application", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Application(id={self.id}, job_id={self.job_id}, status='{self.status}')>"
