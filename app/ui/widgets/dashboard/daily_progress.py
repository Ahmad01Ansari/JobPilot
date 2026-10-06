"""Daily progress widget displaying verified today's metrics as a compact summary strip."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from app.services.dto.dashboard_dto import DailyProgressDTO
from app.ui.theme import COLORS


class ProgressMetricItem(QWidget):
    """Compact text item displaying a single verified daily metric."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title = title

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.lbl_value = QLabel("0")
        self.lbl_value.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 800;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.lbl_value)

        lbl_title = QLabel(self.title)
        lbl_title.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 500;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(lbl_title)

    def set_value(self, val: int) -> None:
        self.lbl_value.setText(str(val))


class DailyProgressWidget(QFrame):
    """Compact horizontal summary strip displaying verified today's progress achievements."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            DailyProgressWidget {
                background-color: transparent;
                border: none;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(12)

        lbl_tag = QLabel("TODAY")
        lbl_tag.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
            padding-right: 4px;
        """)
        layout.addWidget(lbl_tag)

        self.item_discovered = ProgressMetricItem("found")
        self.item_qualified = ProgressMetricItem("qualified")
        self.item_applications = ProgressMetricItem("applied")
        self.item_outreach = ProgressMetricItem("outreach")
        self.item_followups = ProgressMetricItem("follow-ups")

        def _dot():
            d = QLabel("•")
            d.setStyleSheet(f"color: {COLORS['border_subtle']}; font-size: 10px; background: transparent; border: none;")
            return d

        layout.addWidget(self.item_discovered)
        layout.addWidget(_dot())
        layout.addWidget(self.item_qualified)
        layout.addWidget(_dot())
        layout.addWidget(self.item_applications)
        layout.addWidget(_dot())
        layout.addWidget(self.item_outreach)
        layout.addWidget(_dot())
        layout.addWidget(self.item_followups)
        layout.addStretch(1)

    def set_progress(self, progress: DailyProgressDTO) -> None:
        """Updates progress items with authoritative values."""
        self.item_discovered.set_value(progress.discovered_today)
        self.item_qualified.set_value(progress.qualified_today)
        self.item_applications.set_value(progress.applications_submitted_today)
        self.item_outreach.set_value(progress.outreach_sent_today)
        self.item_followups.set_value(progress.followups_completed_today)
