"""Platform configuration and account settings models.

SECURITY INVARIANT:
No passwords, session cookies, OTPs, or auth tokens are stored in the database.
Credentials and sessions remain in local environment/secrets and persistent browser profiles.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, IntIdMixin, JsonType, UTCDateTime


class Platform(Base, IntIdMixin, TimestampMixin):
    """Job search platform registry (e.g., LinkedIn, Naukri)."""

    __tablename__ = "platforms"

    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    accounts: Mapped[List["PlatformAccount"]] = relationship(
        "PlatformAccount", back_populates="platform", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Platform(id={self.id}, name='{self.name}', enabled={self.is_enabled})>"


class PlatformAccount(Base, IntIdMixin, TimestampMixin):
    """Platform search configuration and runtime parameters."""

    __tablename__ = "platform_accounts"

    platform_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("platforms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    auth_mode: Mapped[str] = mapped_column(String(50), default="persistent_profile")  # persistent_profile, manual
    status: Mapped[str] = mapped_column(String(50), default="READY")  # READY, LOGGED_OUT, CHALLENGE_REQUIRED, ERROR
    last_run_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, nullable=True)

    # Explicit configuration columns
    default_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    experience_years: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_applications: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    daily_application_goal: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    apply_mode: Mapped[str] = mapped_column(String(50), default="EASY_APPLY_ONLY")
    pause_before_submit: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    stealth_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    safe_mode: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Extension JSON for platform-specific extras only
    extra_settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JsonType, nullable=True)

    # Relationship
    platform: Mapped["Platform"] = relationship("Platform", back_populates="accounts")

    def __repr__(self) -> str:
        return f"<PlatformAccount(id={self.id}, account='{self.account_name}', status='{self.status}')>"
