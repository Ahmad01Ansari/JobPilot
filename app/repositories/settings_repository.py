"""Repository for Application Settings configuration key-value storage."""

from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppSetting
from app.repositories.base import BaseRepository


class SettingsRepository(BaseRepository):
    """Data access operations for application configuration parameters."""

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value by key, returning default if not found."""
        setting = self.session.execute(
            select(AppSetting).where(AppSetting.key == key.strip())
        ).scalar_one_or_none()
        if setting is None:
            return default
        return setting.value_json

    def set(
        self,
        key: str,
        value: Any,
        category: str = "general",
        description: Optional[str] = None,
    ) -> AppSetting:
        """Sets a configuration setting value."""
        setting = self.session.execute(
            select(AppSetting).where(AppSetting.key == key.strip())
        ).scalar_one_or_none()

        if setting:
            setting.value_json = value
            setting.category = category.strip().lower()
            if description:
                setting.description = description
        else:
            setting = AppSetting(
                key=key.strip(),
                value_json=value,
                category=category.strip().lower(),
                description=description,
            )
            self.session.add(setting)

        self.session.flush()
        return setting

    def get_category(self, category: str) -> Dict[str, Any]:
        """Returns all configuration key-value pairs belonging to a category."""
        stmt = select(AppSetting).where(AppSetting.category == category.strip().lower())
        records = list(self.session.execute(stmt).scalars().all())
        return {r.key: r.value_json for r in records}

    def delete(self, key: str) -> bool:
        """Deletes a configuration setting."""
        setting = self.session.execute(
            select(AppSetting).where(AppSetting.key == key.strip())
        ).scalar_one_or_none()
        if not setting:
            return False
        self.session.delete(setting)
        self.session.flush()
        return True
