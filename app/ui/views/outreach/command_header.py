"""Command Header — Top bar for the Outreach Center workspace.

Displays recruitment pipeline metrics (Outreached, Waiting, Replied, Actions, Due),
a Sync button, and a New Outreach CTA. All metrics are clickable to set inbox filters.

Design: Subtle surface elevation, no heavy borders. Uses theme tokens exclusively.
"""

import logging
from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.Outreach.CommandHeader")


class MetricPill(QFrame):
    """Compact clickable metric pill: count + label, used as filter toggle."""
    clicked = Signal(str)  # emits the filter value

    def __init__(
        self,
        label: str,
        count: int = 0,
        filter_value: str = "",
        accent_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._filter_value = filter_value
        self._accent = accent_color or COLORS["text_muted"]
        self._is_active = False

        self.setFixedHeight(36)
        self.setMinimumWidth(115)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        self._count_label = QLabel(str(count))
        self._count_label.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 800;
            color: {self._accent};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self._count_label)

        self._text_label = QLabel(label)
        self._text_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLORS['text_muted']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)
        layout.addWidget(self._text_label)

        self._update_style()

    def set_count(self, count: int):
        self._count_label.setText(str(count))

    def set_active(self, active: bool):
        self._is_active = active
        self._update_style()

    def _update_style(self):
        if self._is_active:
            self.setStyleSheet(f"""
                MetricPill {{
                    background: {COLORS['surface_hover']};
                    border: 1px solid {self._accent};
                    border-top: 3px solid {self._accent};
                    border-radius: 6px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                MetricPill {{
                    background: {COLORS['surface']};
                    border: 1px solid {COLORS['border']};
                    border-top: 3px solid {self._accent};
                    border-radius: 6px;
                }}
                MetricPill:hover {{
                    background: {COLORS['surface_hover']};
                    border-color: {self._accent};
                }}
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self._filter_value)


class CommandHeader(QWidget):
    """Top bar: "Outreach" title · metric pills · [Sync] · [+ New Outreach]."""

    sync_requested = Signal()
    bulk_outreach_requested = Signal()
    new_outreach_requested = Signal()
    filter_changed = Signal(str)  # emits filter state value or "" for all

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._active_filter = ""
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(12)

        # Title
        title = QLabel("Outreach")
        title.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {COLORS['text']};
            letter-spacing: -0.3px;
        """)
        layout.addWidget(title)

        layout.addSpacing(8)

        # Metric pills
        self._pills: Dict[str, MetricPill] = {}
        pill_configs = [
            ("Outreached", "", COLORS["text"]),
            ("Waiting", "WAITING", COLORS["warning"]),
            ("Replied", "REPLIED", COLORS["info"]),
            ("Actions", "NEEDS_ACTION", COLORS["danger"]),
            ("Due", "FOLLOW_UP_DUE", COLORS["accent"]),
        ]
        for label, filter_val, color in pill_configs:
            pill = MetricPill(label, 0, filter_val, accent_color=color)
            pill.clicked.connect(self._on_pill_clicked)
            self._pills[filter_val] = pill
            layout.addWidget(pill)

        layout.addStretch(1)

        # Sync button
        self._sync_btn = QPushButton("⟳  Sync")
        self._sync_btn.setFixedHeight(36)
        self._sync_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._sync_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border-color: {COLORS['border_light']};
            }}
        """)
        self._sync_btn.clicked.connect(self.sync_requested.emit)
        layout.addWidget(self._sync_btn)

        # Bulk Outreach button
        self._bulk_btn = QPushButton("⚡  Bulk Outreach")
        self._bulk_btn.setFixedHeight(36)
        self._bulk_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bulk_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['surface']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
                padding: 0 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
                border-color: {COLORS.get('accent_hover', COLORS['accent'])};
            }}
        """)
        self._bulk_btn.clicked.connect(self.bulk_outreach_requested.emit)
        layout.addWidget(self._bulk_btn)

        # New Outreach button
        self._new_btn = QPushButton("+ New Outreach")
        self._new_btn.setFixedHeight(36)
        self._new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._new_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_hover']};
            }}
        """)
        self._new_btn.clicked.connect(self.new_outreach_requested.emit)
        layout.addWidget(self._new_btn)

        # Container styling
        self.setStyleSheet(f"""
            CommandHeader {{
                background: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

    def update_stats(self, stats: Dict[str, int]):
        """Updates metric pill counts from OutreachService.get_outreach_stats()."""
        mapping = {
            "": stats.get("total_outreached", 0),
            "WAITING": stats.get("awaiting_reply", 0),
            "REPLIED": stats.get("recruiter_replied", 0),
            "NEEDS_ACTION": 0,  # Will be computed from conversations
            "FOLLOW_UP_DUE": stats.get("followups_due", 0),
        }
        for filter_val, count in mapping.items():
            if filter_val in self._pills:
                self._pills[filter_val].set_count(count)

    def set_action_count(self, count: int):
        """Updates the 'Actions' pill count separately (computed from conversation list)."""
        if "NEEDS_ACTION" in self._pills:
            self._pills["NEEDS_ACTION"].set_count(count)

    def _on_pill_clicked(self, filter_val: str):
        # Toggle: clicking same pill deactivates
        if self._active_filter == filter_val:
            self._active_filter = ""
        else:
            self._active_filter = filter_val

        for fv, pill in self._pills.items():
            pill.set_active(fv == self._active_filter)

        self.filter_changed.emit(self._active_filter)

    def set_syncing(self, is_syncing: bool):
        """Visual feedback during mailbox sync."""
        if is_syncing:
            self._sync_btn.setText("⟳  Syncing...")
            self._sync_btn.setEnabled(False)
        else:
            self._sync_btn.setText("⟳  Sync")
            self._sync_btn.setEnabled(True)
