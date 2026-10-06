"""Screening question and answer knowledge base model with provenance and validation status."""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, IntIdMixin, UTCDateTime


class QnAEntry(Base, IntIdMixin, TimestampMixin):
    """Screening Q&A repository for automated and assisted application filling."""

    __tablename__ = "qna_entries"

    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_question: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(50), default="text")  # text, numeric, boolean, choice
    category: Mapped[str] = mapped_column(
        String(50), default="general", index=True
    )  # notice_period, salary, experience, location, relocation, skills, authorization, general
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # PROFILE, RULE, LLM, MANUAL
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    validation_status: Mapped[str] = mapped_column(
        String(50), default="VERIFIED", index=True
    )  # VERIFIED, NEEDS_REVIEW, REJECTED
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<QnAEntry(id={self.id}, category='{self.category}', source='{self.source}', status='{self.validation_status}')>"
