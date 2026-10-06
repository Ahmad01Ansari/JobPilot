"""Application settings management service.

Provides typed access, categorization, validation, batch updating,
and defaults management for system-wide configuration parameters.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import sessionmaker

from app.db.models import AppSetting
from app.db.session import SessionLocal, get_db_session
from app.repositories.settings_repository import SettingsRepository


DEFAULT_SETTINGS: Dict[str, Dict[str, Any]] = {
    # General execution preferences
    "click_gap": {"value": 1, "category": "general", "description": "Seconds to wait between UI actions/clicks"},
    "smooth_scroll": {"value": False, "category": "general", "description": "Enable smooth page scrolling"},
    "run_non_stop": {"value": False, "category": "general", "description": "Run continuously until manually stopped"},
    "alternate_sortby": {"value": True, "category": "general", "description": "Alternate between recent and relevant sort orders"},
    "cycle_date_posted": {"value": True, "category": "general", "description": "Cycle through posted date filters"},

    # Browser & stealth controls
    "run_in_background": {"value": False, "category": "browser", "description": "Run Chrome in headless mode without visible window"},
    "disable_extensions": {"value": False, "category": "browser", "description": "Disable Chrome extensions for performance"},
    "safe_mode": {"value": True, "category": "browser", "description": "Open Chrome with isolated guest/safe profile"},
    "stealth_mode": {"value": True, "category": "browser", "description": "Run in undetected mode to bypass anti-bot challenges"},
    "keep_screen_awake": {"value": True, "category": "browser", "description": "Prevent system display from sleeping during run"},

    # Automation safeguards
    "enable_universal_agent": {"value": True, "category": "automation", "description": "Enable Stagehand-based Universal AI Application Agent for external ATS portals"},
    "pause_before_submit": {"value": False, "category": "automation", "description": "Pause before clicking final submit button for human review"},
    "pause_at_failed_question": {"value": True, "category": "automation", "description": "Pause if a screening question cannot be answered"},
    "follow_companies": {"value": False, "category": "automation", "description": "Follow companies automatically on apply"},
    "close_tabs": {"value": False, "category": "automation", "description": "Close external application tabs after processing"},

    # Logging & diagnostics
    "logs_folder_path": {"value": "logs/", "category": "logging", "description": "Relative directory for execution log files"},
    "show_ai_error_alerts": {"value": False, "category": "logging", "description": "Show popups on AI provider connection failures"},
}


class SettingsService:
    """Service layer for managing system settings and operational parameters."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def seed_defaults_if_empty(self) -> None:
        """Seeds default configuration key-values into database if not present."""
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            for key, meta in DEFAULT_SETTINGS.items():
                if repo.get(key) is None:
                    repo.set(
                        key=key,
                        value=meta["value"],
                        category=meta["category"],
                        description=meta["description"],
                    )
            session.commit()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a single setting value, returning default or fallback."""
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            val = repo.get(key)
            if val is not None:
                return val
            if default is not None:
                return default
            return DEFAULT_SETTINGS.get(key, {}).get("value")

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience alias for get_setting."""
        return self.get_setting(key, default=default)

    def set(self, key: str, value: Any, category: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """Convenience alias for save_setting."""
        return self.save_setting(key, value, category=category)

    def save(self) -> None:
        """No-op sync method for interface consistency with file-based settings."""
        pass

    def is_universal_agent_enabled(self) -> bool:
        """Returns True if the universal AI application agent is enabled."""
        val = self.get_setting("enable_universal_agent", True)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes")
        return bool(val)

    def get_category_settings(self, category: str) -> Dict[str, Any]:
        """Returns all key-value settings belonging to a category, populated with defaults."""
        self.seed_defaults_if_empty()
        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            db_vals = repo.get_category(category)

            # Overlay over defaults
            result = {}
            for k, meta in DEFAULT_SETTINGS.items():
                if meta["category"] == category.strip().lower():
                    result[k] = db_vals.get(k, meta["value"])
            return result

    def get_all_settings_grouped(self) -> Dict[str, Dict[str, Any]]:
        """Returns all system settings grouped by their category."""
        self.seed_defaults_if_empty()
        categories = ["general", "browser", "automation", "logging"]
        grouped: Dict[str, Dict[str, Any]] = {}
        for cat in categories:
            grouped[cat] = self.get_category_settings(cat)
        return grouped

    def save_setting(
        self,
        key: str,
        value: Any,
        category: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Saves or updates a single setting in the database."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = SettingsRepository(session)
                cat = category or DEFAULT_SETTINGS.get(key, {}).get("category", "general")
                desc = description or DEFAULT_SETTINGS.get(key, {}).get("description")
                repo.set(key=key, value=value, category=cat, description=desc)
                session.commit()
                return True, None
        except Exception as e:
            return False, f"Failed to save setting '{key}': {e}"

    def save_batch(self, settings_map: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Saves multiple settings atomically in a single transaction."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = SettingsRepository(session)
                for key, val in settings_map.items():
                    cat = DEFAULT_SETTINGS.get(key, {}).get("category", "general")
                    desc = DEFAULT_SETTINGS.get(key, {}).get("description")
                    repo.set(key=key, value=val, category=cat, description=desc)
                session.commit()
                return True, None
        except Exception as e:
            return False, f"Failed to batch save settings: {e}"

    def reset_category_to_defaults(self, category: str) -> Tuple[bool, Optional[str]]:
        """Resets all settings in a category back to their factory default values."""
        try:
            cat_clean = category.strip().lower()
            with get_db_session(self._session_factory) as session:
                repo = SettingsRepository(session)
                for key, meta in DEFAULT_SETTINGS.items():
                    if meta["category"] == cat_clean:
                        repo.set(
                            key=key,
                            value=meta["value"],
                            category=cat_clean,
                            description=meta["description"],
                        )
                session.commit()
                return True, None
        except Exception as e:
            return False, f"Failed to reset category '{category}': {e}"

    def get_section(self, section: str) -> Dict[str, Any]:
        """Retrieves all settings within a section/category."""
        return self.get_category_settings(section)

    def update_section(self, section: str, values: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Updates multiple settings within a specific section."""
        return self.save_batch(values)

    def reset_section(self, section: str) -> Tuple[bool, Optional[str]]:
        """Resets only the specified section to its factory defaults."""
        return self.reset_category_to_defaults(section)

