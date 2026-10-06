"""Presentation model managing category-scoped dirty-state tracking for non-sensitive configuration."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal


class SettingsPresentationModel(QObject):
    """Tracks non-sensitive configuration changes per category to provide clean dirty-state detection.

    CRITICAL SECURITY INVARIANT:
    Plaintext secrets and credentials NEVER enter this model. Credential changes are handled
    exclusively via SecretsService in focused modal dialogs.
    """

    dirty_state_changed = Signal(bool)  # Emits True if any category has unsaved changes
    category_dirty_changed = Signal(str, bool)  # (category, is_dirty)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._initial_values: Dict[str, Dict[str, Any]] = {}
        self._current_values: Dict[str, Dict[str, Any]] = {}

    def set_initial_category(self, category: str, values: Dict[str, Any]) -> None:
        """Stores a clean baseline copy for a category (e.g. general, browser, automation)."""
        cat = category.strip().lower()
        self._initial_values[cat] = dict(values)
        self._current_values[cat] = dict(values)
        self.category_dirty_changed.emit(cat, False)
        self.dirty_state_changed.emit(self.is_any_dirty())

    def update_current_value(self, category: str, key: str, value: Any) -> None:
        """Updates the working value for a specific setting key in a category."""
        cat = category.strip().lower()
        if cat not in self._current_values:
            self._current_values[cat] = {}
            self._initial_values[cat] = {}

        self._current_values[cat][key] = value
        is_dirty = self.is_category_dirty(cat)
        self.category_dirty_changed.emit(cat, is_dirty)
        self.dirty_state_changed.emit(self.is_any_dirty())

    def is_category_dirty(self, category: str) -> bool:
        """Checks if a category has any differences between initial baseline and current values."""
        cat = category.strip().lower()
        init = self._initial_values.get(cat, {})
        curr = self._current_values.get(cat, {})
        for k, v in curr.items():
            if init.get(k) != v:
                return True
        return False

    def is_any_dirty(self) -> bool:
        """Returns True if any tracked category has unsaved changes."""
        for cat in self._current_values:
            if self.is_category_dirty(cat):
                return True
        return False

    def get_dirty_categories(self) -> List[str]:
        """Returns list of all categories with unsaved changes."""
        return [cat for cat in self._current_values if self.is_category_dirty(cat)]

    def get_category_delta(self, category: str) -> Dict[str, Any]:
        """Returns key-value pairs of changed settings in the given category."""
        cat = category.strip().lower()
        init = self._initial_values.get(cat, {})
        curr = self._current_values.get(cat, {})
        return {k: v for k, v in curr.items() if init.get(k) != v}

    def get_category_values(self, category: str) -> Dict[str, Any]:
        """Returns current working values for the given category."""
        cat = category.strip().lower()
        return dict(self._current_values.get(cat, {}))

    def mark_category_clean(self, category: str) -> None:
        """Resets baseline to current values upon successful save."""
        cat = category.strip().lower()
        if cat in self._current_values:
            self._initial_values[cat] = dict(self._current_values[cat])
            self.category_dirty_changed.emit(cat, False)
            self.dirty_state_changed.emit(self.is_any_dirty())
