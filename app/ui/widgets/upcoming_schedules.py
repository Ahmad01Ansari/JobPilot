"""Upcoming recruitment schedules and interview cards widget."""

from typing import List, Optional
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class ScheduleItemWidget(QFrame):
    """Single upcoming interview or due follow-up item card."""

    action_triggered = Signal(str, dict)

    def __init__(
        self,
        round_name: str,
        role_company: str,
        time_str: str,
        mode_or_link: Optional[str] = None,
        item_type: str = "INTERVIEW",
        action_payload: Optional[dict] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.link = mode_or_link
        self.item_type = item_type
        self.action_payload = action_payload or {}
        self.setStyleSheet(f"""
            ScheduleItemWidget {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 8px;
            }}
            ScheduleItemWidget:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # 1. Type Badge
        badge_variant = "purple" if "INTERVIEW" in self.item_type.upper() else "warning"
        lbl_badge = StatusBadge(round_name, status_type=badge_variant, width=88, height=20)
        layout.addWidget(lbl_badge, alignment=Qt.AlignVCenter)

        # 2. Main Details
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(2)

        lbl_title = QLabel(role_company)
        lbl_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        info_col.addWidget(lbl_title)

        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent; border: none;")
        info_col.addWidget(lbl_time)

        layout.addLayout(info_col, 1)

        # 3. Action Button
        if self.link and self.link.startswith("http"):
            btn_action = QPushButton("Join Call ↗")
            btn_action.setCursor(Qt.PointingHandCursor)
            btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                }}
            """)
            btn_action.clicked.connect(self._open_link)
            layout.addWidget(btn_action, alignment=Qt.AlignVCenter)
        else:
            action_btn_text = "Prepare →" if "INTERVIEW" in self.item_type.upper() else "Review →"
            btn_action = QPushButton(action_btn_text)
            btn_action.setCursor(Qt.PointingHandCursor)
            btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_elevated']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 5px;
                    padding: 5px 12px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                    color: {COLORS['primary']};
                }}
            """)
            action_name = "PREPARE_INTERVIEW" if "INTERVIEW" in self.item_type.upper() else "REVIEW_FOLLOWUP"
            btn_action.clicked.connect(lambda: self.action_triggered.emit(action_name, self.action_payload))
            layout.addWidget(btn_action, alignment=Qt.AlignVCenter)

    def _open_link(self) -> None:
        if self.link:
            QDesktopServices.openUrl(QUrl(self.link))


class UpcomingSchedulesCard(QFrame):
    """Card displaying upcoming interview rounds and recruiter follow-ups."""

    navigation_requested = Signal(str)
    action_triggered = Signal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            UpcomingSchedulesCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(18, 14, 18, 14)
        self.card_layout.setSpacing(10)

        # Header
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        lbl_icon = QLabel("📅")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        top_row.addWidget(lbl_icon, alignment=Qt.AlignVCenter)

        lbl_title = QLabel("UPCOMING")
        lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        top_row.addWidget(lbl_title, alignment=Qt.AlignVCenter)
        top_row.addStretch()

        self.lbl_count = QLabel("0 Scheduled")
        self.lbl_count.setFixedHeight(22)
        self.lbl_count.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 11px;
            font-weight: 600;
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border_subtle']};
            padding: 2px 8px;
            border-radius: 6px;
        """)
        top_row.addWidget(self.lbl_count, alignment=Qt.AlignVCenter)
        self.card_layout.addLayout(top_row)

        # Items container
        self.items_container = QVBoxLayout()
        self.items_container.setContentsMargins(0, 0, 0, 0)
        self.items_container.setSpacing(6)
        self.card_layout.addLayout(self.items_container)

        # Empty state widget
        self.empty_widget = QFrame()
        self.empty_widget.setStyleSheet("background: transparent; border: none;")
        e_layout = QVBoxLayout(self.empty_widget)
        e_layout.setContentsMargins(6, 12, 6, 12)
        e_layout.setSpacing(8)
        e_layout.setAlignment(Qt.AlignCenter)

        self.lbl_empty = QLabel("No interviews or follow-ups scheduled.")
        self.lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; background: transparent; border: none;")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        e_layout.addWidget(self.lbl_empty)

        btn_view_rec = QPushButton("View Recruitment →")
        btn_view_rec.setCursor(Qt.PointingHandCursor)
        btn_view_rec.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['border_subtle']};
                font-size: 11px;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        btn_view_rec.clicked.connect(lambda: self.navigation_requested.emit("interviews"))
        e_layout.addWidget(btn_view_rec, alignment=Qt.AlignCenter)

        self.items_container.addWidget(self.empty_widget)
        self.card_layout.addStretch(1)

    def set_schedules(self, schedules: List[dict]) -> None:
        """Populates schedules list. Each dict: round_name, role_company, time_str, link, item_type."""
        # Clear only dynamically added item widgets (preserve self.empty_widget)
        for i in reversed(range(self.items_container.count())):
            item = self.items_container.itemAt(i)
            w = item.widget() if item else None
            if w and w != self.empty_widget:
                self.items_container.removeWidget(w)
                w.deleteLater()

        if not schedules:
            self.lbl_count.setText("0 Scheduled")
            self.empty_widget.show()
            return

        self.empty_widget.hide()
        self.lbl_count.setText(f"{len(schedules)} Scheduled")
        for s in schedules[:3]:  # Show next 3 items per specification
            item_widget = ScheduleItemWidget(
                round_name=s.get("round_name", "Interview"),
                role_company=s.get("role_company", "Role @ Company"),
                time_str=s.get("time_str", "Scheduled"),
                mode_or_link=s.get("link"),
                item_type=s.get("item_type", "INTERVIEW"),
                action_payload=s.get("payload", {}),
            )
            item_widget.action_triggered.connect(self.action_triggered.emit)
            self.items_container.addWidget(item_widget)
            item_widget.show()
