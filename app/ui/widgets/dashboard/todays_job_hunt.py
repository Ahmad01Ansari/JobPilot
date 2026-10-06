"""Hero Work Queue widget for Today's Job Hunt."""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.dashboard_dto import TodaysHuntItemDTO
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class ActionCard(QFrame):
    """Individual actionable task card within the Today's Job Hunt queue."""

    action_triggered = Signal(str, dict)  # (action_type, payload)

    def __init__(self, item: TodaysHuntItemDTO, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.item = item
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            ActionCard {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            ActionCard:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(10)

        # 1. Type / Urgency Pill
        badge_type = "neutral"
        if self.item.urgency == "URGENT":
            badge_type = "danger"
        elif self.item.urgency == "HIGH":
            badge_type = "warning"
        elif self.item.item_type == "TOP_OPPORTUNITY":
            badge_type = "success"
        elif self.item.item_type in ("INTERVIEW_TODAY", "UPCOMING_INTERVIEW"):
            badge_type = "purple"

        pill_text = self.item.item_type.replace("_", " ").title()
        self.badge = StatusBadge(pill_text, status_type=badge_type, width=115, height=20)
        layout.addWidget(self.badge, alignment=Qt.AlignVCenter)

        # 2. Contextual Content Column
        content_col = QVBoxLayout()
        content_col.setContentsMargins(0, 0, 0, 0)
        content_col.setSpacing(1)

        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        lbl_title = QLabel(self.item.title)
        lbl_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        title_row.addWidget(lbl_title)

        if self.item.company and self.item.company.strip().lower() not in self.item.title.lower():
            lbl_company = QLabel(f"@ {self.item.company}")
            lbl_company.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent; border: none;")
            title_row.addWidget(lbl_company)
        title_row.addStretch(1)
        content_col.addLayout(title_row)

        lbl_sub = QLabel(self.item.subtitle)
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        content_col.addWidget(lbl_sub)

        if self.item.reason:
            raw_r = self.item.reason or ""
            for token in ("Stacktrace:", "stack trace:", "Traceback (most recent"):
                if token in raw_r:
                    raw_r = raw_r.split(token)[0]
            raw_r = raw_r.strip()
            if raw_r.startswith("Message:"):
                raw_r = raw_r[8:].strip()
            clean_r = " ".join([line.strip() for line in raw_r.splitlines() if line.strip() and not line.strip().startswith(("#", "0x")) and "<unknown>" not in line])
            if not clean_r or clean_r.startswith("0x") or len(clean_r) < 3:
                clean_r = "Application paused for manual verification"
            if len(clean_r) > 115:
                clean_r = clean_r[:112] + "..."

            lbl_reason = QLabel(f"• {clean_r}")
            lbl_reason.setStyleSheet(f"font-size: 10px; color: {COLORS['text_dark']}; background: transparent; border: none;")
            lbl_reason.setToolTip(self.item.reason[:400])
            lbl_reason.setWordWrap(False)
            content_col.addWidget(lbl_reason)

        layout.addLayout(content_col, 1)

        # 3. Action Buttons (Primary CTA + More Options Menu)
        btn_box = QHBoxLayout()
        btn_box.setSpacing(6)
        btn_box.setAlignment(Qt.AlignVCenter)

        btn_label = self._format_action_label(self.item.recommended_action)
        is_urgent = self.item.urgency in ("URGENT", "HIGH")
        self.btn_action = QPushButton(btn_label)
        self.btn_action.setCursor(Qt.PointingHandCursor)

        if is_urgent:
            self.btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    font-weight: 700;
                    font-size: 11px;
                    padding: 5px 12px;
                    border-radius: 5px;
                    border: none;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                }}
            """)
        else:
            self.btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_elevated']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    font-weight: 600;
                    font-size: 11px;
                    padding: 5px 12px;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                    color: {COLORS['primary']};
                }}
            """)
        btn_box.addWidget(self.btn_action)

        self.btn_more = QPushButton("⋮")
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setToolTip("Options: Change status, mark handled, or dismiss")
        self.btn_more.setFixedSize(28, 26)
        self.btn_more.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_elevated']};
                color: #FFFFFF;
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                padding: 0px;
                margin: 0px;
                font-size: 15px;
                font-weight: 800;
                text-align: center;
            }}
            QPushButton:hover {{
                color: {COLORS['primary']};
                border-color: {COLORS['primary']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_more.clicked.connect(self._show_options_menu)
        btn_box.addWidget(self.btn_more)

        layout.addLayout(btn_box)

    def _show_options_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary_hover']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 6px;
            }}
        """)

        # Option 1: Mark as Done / Handled
        act_done = menu.addAction("✓ Mark as Done / Handled")
        act_done.triggered.connect(lambda: self.action_triggered.emit(
            "DISMISS_ITEM",
            {
                "item_id": self.item.id,
                "source_type": self.item.source_entity_type,
                "source_id": self.item.source_entity_id,
                "application_id": self.item.action_payload.get("application_id"),
            }
        ))

        # Option 2: Change Status (if application attached)
        app_id = self.item.action_payload.get("application_id")
        if app_id:
            menu.addSeparator()
            status_menu = menu.addMenu("🔄 Change Status")
            status_options = [
                ("SUBMITTED", "📄 Submitted"),
                ("UNDER_REVIEW", "⏳ Under Review"),
                ("INTERVIEW", "🎯 Interview"),
                ("OFFER", "🎉 Offer"),
                ("REJECTED", "❌ Rejected"),
                ("WITHDRAWN", "↩️ Withdrawn"),
                ("NOT_APPLIED", "⚪ Not Applied"),
                ("JUNK", "🗑 Junk"),
            ]
            for code, lbl in status_options:
                act = status_menu.addAction(lbl)
                act.triggered.connect(lambda _, c=code: self.action_triggered.emit(
                    "CHANGE_APPLICATION_STATUS",
                    {
                        "application_id": app_id,
                        "new_status": c,
                    }
                ))

        menu.addSeparator()
        act_dismiss = menu.addAction("🚫 Dismiss from Today's Queue")
        act_dismiss.triggered.connect(lambda: self.action_triggered.emit(
            "DISMISS_ITEM",
            {
                "item_id": self.item.id,
                "source_type": self.item.source_entity_type,
                "source_id": self.item.source_entity_id,
                "application_id": self.item.action_payload.get("application_id"),
            }
        ))

        menu.exec_(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height() + 2)))

    def _format_action_label(self, raw_action: str) -> str:
        mapping = {
            "PREPARE_INTERVIEW": "Prepare Interview →",
            "COMPOSE_FOLLOWUP": "Compose Follow-up →",
            "OPEN_CONVERSATION": "Open Conversation →",
            "REVIEW_APPLICATION": "Review Application →",
            "REVIEW_JOB": "Review Job →",
        }
        return mapping.get(raw_action, "Review →")


class TodaysJobHuntWidget(QFrame):
    """Hero container presenting prioritized Today's Job Hunt action queue."""

    action_triggered = Signal(str, dict)  # (action_type, payload)
    search_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: List[TodaysHuntItemDTO] = []
        self._is_expanded = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            TodaysJobHuntWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        self.layout_main = QVBoxLayout(self)
        self.layout_main.setContentsMargins(18, 14, 18, 14)
        self.layout_main.setSpacing(10)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        header_row.addWidget(lbl_icon)

        self.lbl_title = QLabel("TODAY'S JOB HUNT")
        self.lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        header_row.addWidget(self.lbl_title)

        self.badge_count = QLabel("0 actions")
        self.badge_count.setStyleSheet(f"""
            background-color: {COLORS['primary_subtle']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid {COLORS['primary']}40;
        """)
        header_row.addWidget(self.badge_count)
        header_row.addStretch(1)

        self.btn_toggle_expand = QPushButton("Show more actions ↓")
        self.btn_toggle_expand.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_expand.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['primary']};
                border: none;
                font-size: 11px;
                font-weight: 700;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {COLORS['primary_hover']};
                text-decoration: underline;
            }}
        """)
        self.btn_toggle_expand.clicked.connect(self._toggle_expand)
        self.btn_toggle_expand.hide()
        header_row.addWidget(self.btn_toggle_expand)

        self.layout_main.addLayout(header_row)

        # Container for action cards
        self.cards_container = QVBoxLayout()
        self.cards_container.setContentsMargins(0, 0, 0, 0)
        self.cards_container.setSpacing(6)
        self.layout_main.addLayout(self.cards_container)

    def _toggle_expand(self) -> None:
        self._is_expanded = not self._is_expanded
        self._render_cards()

    def set_items(self, items: List[TodaysHuntItemDTO]) -> None:
        """Updates the queue with prioritized, deduplicated action items."""
        self._items = items
        self._render_cards()

    def _render_cards(self) -> None:
        # Clear existing card widgets
        while self.cards_container.count():
            child = self.cards_container.takeAt(0)
            widget = child.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if not self._items:
            self.btn_toggle_expand.hide()
            self.badge_count.setText("Clear")
            self.badge_count.setStyleSheet(f"""
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 10px;
                border: 1px solid {COLORS['border']};
            """)

            # Compact, non-intrusive empty state
            empty_frame = QFrame()
            empty_frame.setStyleSheet("background: transparent; border: none;")
            e_layout = QHBoxLayout(empty_frame)
            e_layout.setContentsMargins(6, 4, 6, 4)
            e_layout.setSpacing(12)

            lbl_empty_title = QLabel("🎉 You're all caught up. No urgent actions pending.")
            lbl_empty_title.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_muted']};")
            e_layout.addWidget(lbl_empty_title)
            e_layout.addStretch(1)

            btn_search = QPushButton("Find New Jobs →")
            btn_search.setCursor(Qt.PointingHandCursor)
            btn_search.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['primary']};
                    border: 1px solid {COLORS['border_subtle']};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 4px 10px;
                    border-radius: 5px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                }}
            """)
            btn_search.clicked.connect(self.search_requested.emit)
            e_layout.addWidget(btn_search)

            self.cards_container.addWidget(empty_frame)
            empty_frame.show()
            return

        # Populated state
        count = len(self._items)
        self.badge_count.setText(f"{count} action{'s' if count != 1 else ''} need attention")
        self.badge_count.setStyleSheet(f"""
            background-color: {COLORS['primary_subtle']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
            border: 1px solid {COLORS['primary']}40;
        """)

        visible_items = self._items if self._is_expanded else self._items[:3]
        if count > 3:
            self.btn_toggle_expand.show()
            if self._is_expanded:
                self.btn_toggle_expand.setText("Show less ↑")
            else:
                self.btn_toggle_expand.setText(f"Show {count - 3} more actions ↓")
        else:
            self.btn_toggle_expand.hide()

        for item in visible_items:
            card = ActionCard(item)
            action_type = self._map_action_type(item.recommended_action)
            payload = dict(item.action_payload)
            card.action_triggered.connect(self.action_triggered.emit)
            card.btn_action.clicked.connect(
                lambda _, at=action_type, p=payload: self.action_triggered.emit(at, p)
            )
            self.cards_container.addWidget(card)
            card.show()

    def _map_action_type(self, raw_action: str) -> str:
        mapping = {
            "PREPARE_INTERVIEW": "NAVIGATE_INTERVIEW",
            "COMPOSE_FOLLOWUP": "NAVIGATE_FOLLOWUP",
            "OPEN_CONVERSATION": "NAVIGATE_OUTREACH",
            "REVIEW_APPLICATION": "NAVIGATE_APPLICATION",
            "REVIEW_JOB": "NAVIGATE_JOB",
        }
        return mapping.get(raw_action, "NAVIGATE_JOB")
