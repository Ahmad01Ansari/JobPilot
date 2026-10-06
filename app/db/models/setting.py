"""Application settings model."""

from typing import Any, Optional
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, IntIdMixin, JsonType


class AppSetting(Base, IntIdMixin, TimestampMixin):
    """Configuration parameter store for application settings."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value_json: Mapped[Any] = mapped_column(JsonType, nullable=False)
    category: Mapped[str] = mapped_column(
        String(50), default="general", index=True
    )  # general, database, bot, ai, security
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<AppSetting(key='{self.key}', category='{self.category}')>"
