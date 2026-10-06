"""Application status history and transition audit trail model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime, utc_now


class ApplicationStatusHistory(Base, IntIdMixin, TimestampMixin):
    """Audit trail recording each state transition of an application."""

    __tablename__ = "application_status_history"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="automation"
    )  # automation, manual, email, recruiter
    notes: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Relationship
    application: Mapped["Application"] = relationship("Application", back_populates="status_history")

    def __repr__(self) -> str:
        return f"<ApplicationStatusHistory(app_id={self.application_id}, {self.old_status} -> {self.new_status})>"
