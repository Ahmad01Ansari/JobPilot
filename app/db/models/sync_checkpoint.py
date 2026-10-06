"""Model tracking mailbox synchronization cursor and timestamps."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntIdMixin, TimestampMixin, UTCDateTime


class EmailSyncCheckpoint(Base):
    """Stores the latest synchronization checkpoint per email account."""

    __tablename__ = "email_sync_checkpoints"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)
    last_history_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cursor_token: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    def __repr__(self) -> str:
        return f"<EmailSyncCheckpoint(account_id='{self.account_id}', last_sync_at='{self.last_sync_at}')>"
