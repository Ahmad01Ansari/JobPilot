"""
Application-wide UI state and signal bus for JobPilot.
Decouples UI components without premature global singletons.
"""

from PySide6.QtCore import QObject, Signal


class AppState(QObject):
    """
    Lightweight UI state event bus.
    Enables components to emit and observe navigation, notification, and status events.
    """

    # Emitted when active navigation page changes (passes page_id: str)
    page_changed = Signal(str)

    # Emitted to display a temporary notification banner (passes level: str, message: str)
    notification_emitted = Signal(str, str)

    # Emitted when system or engine status changes (passes component: str, status_text: str)
    status_changed = Signal(str, str)

    # Emitted when domain entities are updated across any page (passes entity: str, e.g. 'applications', 'jobs', 'profile')
    data_updated = Signal(str)

    def __init__(self, parent: QObject = None):
        super().__init__(parent)
        self.current_page_id: str = "dashboard"
        self.engine_status: str = "Ready"
        self.database_status: str = "Not Connected (Phase 2)"
        self.automation_status: str = "Idle"

    @property
    def current_page(self) -> str:
        """Alias for current_page_id."""
        return self.current_page_id

    def set_current_page(self, page_id: str) -> None:
        if self.current_page_id != page_id:
            self.current_page_id = page_id
            self.page_changed.emit(page_id)

    def notify(self, level: str, message: str) -> None:
        self.notification_emitted.emit(level, message)

    def emit_data_updated(self, entity: str = "general") -> None:
        """Broadcasts real-time entity updates to all listening views."""
        self.data_updated.emit(entity)

    def update_status(self, component: str, status_text: str) -> None:
        if component == "engine":
            self.engine_status = status_text
        elif component == "database":
            self.database_status = status_text
        elif component == "automation":
            self.automation_status = status_text
        self.status_changed.emit(component, status_text)

