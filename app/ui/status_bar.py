"""
Application status bar component.
Displays high-level engine, database, and automation statuses without exposing internal file paths.
"""

from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from app.ui.theme import COLORS


class StatusBar(QStatusBar):
    """Bottom status bar with decoupled system indicators."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizeGripEnabled(False)

        # Engine Status
        self.engine_label = QLabel("Engine: Ready")
        self.engine_label.setStyleSheet(f"color: {COLORS['success']}; font-weight: 600; padding: 0 8px;")

        # Database Status
        self.db_label = QLabel("Database: Not Connected (Phase 2)")
        self.db_label.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 0 8px;")

        # Automation Status
        self.automation_label = QLabel("Automation: Idle")
        self.automation_label.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 0 8px;")

        self.addPermanentWidget(self.engine_label)
        self.addPermanentWidget(self.db_label)
        self.addPermanentWidget(self.automation_label)

    def set_engine_status(self, text: str, is_ready: bool = True):
        color = COLORS['success'] if is_ready else COLORS['danger']
        self.engine_label.setText(f"Engine: {text}")
        self.engine_label.setStyleSheet(f"color: {color}; font-weight: 600; padding: 0 8px;")

    def set_database_status(self, text: str):
        self.db_label.setText(f"Database: {text}")

    def set_automation_status(self, text: str):
        self.automation_label.setText(f"Automation: {text}")
