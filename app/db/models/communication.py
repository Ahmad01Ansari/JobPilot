"""Communication log model for tracking emails, calls, and recruiter messages."""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime, utc_now


class Communication(Base, IntIdMixin, TimestampMixin):
    """Tracks inbound and outbound interactions with recruiters and employers."""

    __tablename__ = "communications"

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

    type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="EMAIL"
    )  # EMAIL, PHONE_CALL, LINKEDIN_MESSAGE, WHATSAPP, RECRUITER_MESSAGE, OTHER
    direction: Mapped[str] = mapped_column(
        String(20), nullable=False, default="INBOUND"
    )  # INBOUND, OUTBOUND
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="SENT"
    )  # DRAFT, SCHEDULED, SENDING, SENT, FAILED, DELIVERY_CONFIRMED
    account_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    send_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sender_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    recipient_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    template_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_version: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    attachment_snapshot_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    body_snippet: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual")

    # Relationships
    application: Mapped[Optional["Application"]] = relationship("Application", back_populates="communications")
    contact: Mapped[Optional["Contact"]] = relationship("Contact", back_populates="communications")
    template: Mapped[Optional["EmailTemplate"]] = relationship("EmailTemplate")

    def __repr__(self) -> str:
        return f"<Communication(id={self.id}, type='{self.type}', direction='{self.direction}', status='{self.status}')>"
