"""AutomationRun entity model for tracking bot execution sessions and metrics."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IntIdMixin, JsonType, TimestampMixin, UTCDateTime, utc_now


class AutomationRun(Base, IntIdMixin, TimestampMixin):
    """Tracks discrete automation runs across platforms with metrics and outcome status."""

    __tablename__ = "automation_runs"

    run_id: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="STARTING", index=True)

    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    current_keyword: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    jobs_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    jobs_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applications_submitted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    stop_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    meta_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)
