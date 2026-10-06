"""Interview round and scheduling model."""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime


class Interview(Base, IntIdMixin, TimestampMixin):
    """Tracks interview rounds, schedules, modes, and feedback."""

    __tablename__ = "interviews"

    application_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    round_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # HR, Technical, Coding, Managerial, Client, Final
    scheduled_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    interviewer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(50), default="VIRTUAL")  # VIRTUAL, PHONE, IN_PERSON
    meeting_link: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="SCHEDULED"
    )  # SCHEDULED, COMPLETED, CANCELLED, RESCHEDULED, NO_SHOW
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    application: Mapped["Application"] = relationship("Application", back_populates="interviews")

    def __repr__(self) -> str:
        return f"<Interview(id={self.id}, round='{self.round_name}', status='{self.status}')>"
