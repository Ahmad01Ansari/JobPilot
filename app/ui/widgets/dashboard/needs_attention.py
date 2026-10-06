"""Needs Attention widget displaying recruiter replies, overdue tasks, and manual reviews."""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.dashboard_dto import TodaysHuntItemDTO
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class NeedsAttentionRow(QFrame):
    """Row item in the Needs Attention queue."""

    def __init__(self, item: TodaysHuntItemDTO, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            NeedsAttentionRow {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            NeedsAttentionRow:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Urgency / Type Pill
        style_map = {
            "URGENT": "danger",
            "HIGH": "warning",
            "NORMAL": "primary",
            "INFORMATIONAL": "neutral",
        }
        b_style = style_map.get(self.item.urgency, "warning")
        self.badge = StatusBadge(self.item.item_type.replace("_", " ").title(), status_type=b_style, height=20)
        layout.addWidget(self.badge, alignment=Qt.AlignVCenter)

        # Context
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)

        lbl_t = QLabel(f"{self.item.company} — {self.item.title}")
        lbl_t.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        col.addWidget(lbl_t)

        lbl_reason = QLabel(self.item.reason or self.item.subtitle)
        lbl_reason.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        col.addWidget(lbl_reason)

        layout.addLayout(col, 1)

        # Action Button
        btn_text = self._action_text(self.item.recommended_action)
        self.btn_act = QPushButton(btn_text)
        self.btn_act.setCursor(Qt.PointingHandCursor)
        self.btn_act.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_elevated']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['border']};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        layout.addWidget(self.btn_act, alignment=Qt.AlignVCenter)

    def _action_text(self, action: str) -> str:
        mapping = {
            "OPEN_CONVERSATION": "Reply →",
            "COMPOSE_FOLLOWUP": "Follow Up →",
            "REVIEW_APPLICATION": "Review →",
            "PREPARE_INTERVIEW": "Prepare →",
            "REVIEW_JOB": "Review →",
        }
        return mapping.get(action, "View →")


class NeedsAttentionWidget(QFrame):
    """Container displaying tasks requiring immediate recruiter communication or intervention."""

    action_triggered = Signal(str, dict)  # (action_type, payload)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[TodaysHuntItemDTO] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            NeedsAttentionWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_icon = QLabel("⚠️")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        header_row.addWidget(lbl_icon)

        lbl_title = QLabel("NEEDS ATTENTION")
        lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        header_row.addWidget(lbl_title)

        self.badge_count = QLabel("0")
        self.badge_count.setStyleSheet(f"""
            background-color: {COLORS['surface_alt']};
            color: {COLORS['text_muted']};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 9px;
            border: 1px solid {COLORS['border']};
        """)
        header_row.addWidget(self.badge_count)
        header_row.addStretch(1)

        layout.addLayout(header_row)

        # Items container
        self.items_container = QVBoxLayout()
        self.items_container.setContentsMargins(0, 0, 0, 0)
        self.items_container.setSpacing(8)
        layout.addLayout(self.items_container)

    def set_items(self, items: List[TodaysHuntItemDTO]) -> None:
        """Filters for urgent/attention tasks and renders them."""
        # Keep items that are not top opportunities or informational upcoming interviews
        attention_items = [
            it for it in items
            if it.item_type in ("INTERVIEW_TODAY", "OVERDUE_FOLLOWUP", "RECRUITER_REPLY", "FOLLOWUP_DUE_TODAY", "MANUAL_REVIEW")
        ]
        self._items = attention_items

        while self.items_container.count():
            child = self.items_container.takeAt(0)
            w = child.widget()
            if w:
                w.deleteLater()

        if not attention_items:
            self.badge_count.setText("0")
            lbl_empty = QLabel("🎉 All caught up. No messages or applications require attention.")
            lbl_empty.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; padding: 12px 0;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.items_container.addWidget(lbl_empty)
            lbl_empty.show()
            return

        self.badge_count.setText(str(len(attention_items)))
        self.badge_count.setStyleSheet(f"""
            background-color: {COLORS['primary_subtle']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 7px;
            border-radius: 9px;
            border: 1px solid {COLORS['primary']}40;
        """)

        for item in attention_items[:4]:
            row = NeedsAttentionRow(item)
            action_type = self._map_action_type(item.recommended_action)
            payload = dict(item.action_payload)
            row.btn_act.clicked.connect(
                lambda _, at=action_type, p=payload: self.action_triggered.emit(at, p)
            )
            row.mousePressEvent = (
                lambda _, at=action_type, p=payload: self.action_triggered.emit(at, p)
            )
            self.items_container.addWidget(row)
            row.show()

    def _map_action_type(self, raw_action: str) -> str:
        mapping = {
            "PREPARE_INTERVIEW": "NAVIGATE_INTERVIEW",
            "COMPOSE_FOLLOWUP": "NAVIGATE_FOLLOWUP",
            "OPEN_CONVERSATION": "NAVIGATE_OUTREACH",
            "REVIEW_APPLICATION": "NAVIGATE_APPLICATION",
            "REVIEW_JOB": "NAVIGATE_JOB",
        }
        return mapping.get(raw_action, "NAVIGATE_JOB")
