"""Follow-up reminder and task tracking model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime


class FollowUp(Base, IntIdMixin, TimestampMixin):
    """Tracks follow-up tasks, reminders, and outreach cadences."""

    __tablename__ = "follow_ups"

    application_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    contact_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sequence_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    step_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING"
    )  # PENDING, DUE, COMPLETED, PAUSED, SKIPPED, CANCELLED
    paused_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    application: Mapped[Optional["Application"]] = relationship("Application", back_populates="follow_ups")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="follow_ups")

    def __repr__(self) -> str:
        return f"<FollowUp(id={self.id}, due='{self.due_at}', status='{self.status}')>"
