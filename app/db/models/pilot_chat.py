"""Database model for persisting AI Pilot conversation history with retention management."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntIdMixin, TimestampMixin, UTCDateTime, utc_now


class PilotChatMessage(Base, IntIdMixin, TimestampMixin):
    """Stores chat messages between candidate and AI Pilot with 14-day retention."""

    __tablename__ = "pilot_chat_messages"

    uuid: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    author: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, default="chat", index=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    steps_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rule_change_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    intervention_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<PilotChatMessage(id={self.id}, uuid='{self.uuid}', author='{self.author}')>"

