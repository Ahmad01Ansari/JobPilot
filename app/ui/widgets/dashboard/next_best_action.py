"""Hero Card for the Next Best Action.

Presents the single highest-leverage operational task right now based on
deterministic waterfall prioritization from DashboardService.get_next_best_action().
"""

from typing import Optional
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

from app.services.dto.dashboard_dto import NextBestActionDTO
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class NextBestActionWidget(QFrame):
    """Prominent Hero Card guiding the candidate toward their single highest-leverage action."""

    action_triggered = Signal(str, dict)  # (action_type, payload)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._action: Optional[NextBestActionDTO] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("NextBestActionWidget")
        self._apply_border_style(COLORS['primary'])

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 12, 18, 12)
        main_layout.setSpacing(6)

        # 1. Top Bar: Star icon, tag, urgency badge, category
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_star = QLabel("★")
        lbl_star.setStyleSheet(f"color: {COLORS['primary']}; font-size: 13px; font-weight: 900; background: transparent; border: none;")
        top_bar.addWidget(lbl_star)

        lbl_tag = QLabel("NEXT BEST ACTION")
        lbl_tag.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.8px;
            color: {COLORS['primary']};
            background: transparent;
            border: none;
        """)
        top_bar.addWidget(lbl_tag)

        self.urgency_badge = StatusBadge("HIGH PRIORITY", status_type="danger", height=18, width=120)
        top_bar.addWidget(self.urgency_badge)

        self.action_category_lbl = QLabel("")
        self.action_category_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        top_bar.addWidget(self.action_category_lbl)

        top_bar.addStretch(1)
        main_layout.addLayout(top_bar)

        # 2. Body Area (Horizontal: Content left, Action buttons right)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        left_content = QVBoxLayout()
        left_content.setContentsMargins(0, 0, 0, 0)
        left_content.setSpacing(2)

        self.lbl_title = QLabel("Loading recommendations...")
        self.lbl_title.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {COLORS['text']}; background: transparent; border: none;")
        left_content.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel("")
        self.lbl_subtitle.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent; border: none;")
        left_content.addWidget(self.lbl_subtitle)

        # Explainability reason
        self.lbl_reason = QLabel("")
        self.lbl_reason.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
            background-color: transparent;
            padding: 1px 0px;
            border: none;
        """)
        self.lbl_reason.setVisible(False)
        left_content.addWidget(self.lbl_reason, alignment=Qt.AlignLeft)

        body_layout.addLayout(left_content, 1)

        # Right Action Column
        right_actions = QVBoxLayout()
        right_actions.setContentsMargins(0, 0, 0, 0)
        right_actions.setSpacing(4)
        right_actions.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Action Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        btn_row.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        self.btn_primary_action = QPushButton("Take Action →")
        self.btn_primary_action.setCursor(Qt.PointingHandCursor)
        self.btn_primary_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_primary_action.clicked.connect(self._on_primary_action_clicked)
        btn_row.addWidget(self.btn_primary_action)

        self.btn_more = QPushButton("⋮")
        self.btn_more.setCursor(Qt.PointingHandCursor)
        self.btn_more.setToolTip("Options: Change status, mark handled, or dismiss")
        self.btn_more.setFixedSize(30, 30)
        self.btn_more.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_elevated']};
                color: #FFFFFF;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0px;
                margin: 0px;
                font-size: 16px;
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
        btn_row.addWidget(self.btn_more)

        right_actions.addLayout(btn_row)

        self.btn_secondary_action = QPushButton("Join Call ↗")
        self.btn_secondary_action.setCursor(Qt.PointingHandCursor)
        self.btn_secondary_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['border']};
                font-weight: 600;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_secondary_action.setVisible(False)
        self.btn_secondary_action.clicked.connect(self._on_secondary_action_clicked)
        right_actions.addWidget(self.btn_secondary_action)

        body_layout.addLayout(right_actions)
        main_layout.addLayout(body_layout)

    def _apply_border_style(self, accent_color: str) -> None:
        self.setStyleSheet(f"""
            #NextBestActionWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {accent_color}50;
                border-left: 5px solid {accent_color};
                border-radius: 12px;
            }}
        """)

    def set_action(self, action: Optional[NextBestActionDTO]) -> None:
        """Binds NextBestActionDTO to hero card. Uses DTO fields directly."""
        self._action = action
        if not action:
            self._render_empty_state()
            return

        # Badge variant -> border color mapping
        variant_color_map = {
            "danger": COLORS['danger'],
            "warning": COLORS['warning'],
            "success": COLORS['success'],
            "purple": COLORS['purple'],
            "primary": COLORS['primary'],
        }
        accent_color = variant_color_map.get(action.badge_variant, COLORS['primary'])
        self._apply_border_style(accent_color)

        # Recreate the urgency badge with new text and variant
        self.urgency_badge.raw_text = action.badge_text
        self.urgency_badge.setText(action.badge_text)
        self.urgency_badge.update_style(action.badge_variant)

        # Category label
        category_map = {
            "INTERVIEW_TODAY": "Scheduled Interview",
            "RECRUITER_REPLY": "Recruiter Inbound",
            "OVERDUE_FOLLOWUP": "Follow-Up Overdue",
            "FOLLOWUP_DUE_TODAY": "Follow-Up Due Today",
            "MANUAL_REVIEW": "Manual Review Pending",
            "TOP_OPPORTUNITY_REVIEW": "#1 Top Matched Job",
            "ALL_CAUGHT_UP": "Queue Clear",
        }
        self.action_category_lbl.setText(f"•  {category_map.get(action.action_type, 'Action Item')}")

        self.lbl_title.setText(action.title)
        self.lbl_subtitle.setText(action.subtitle)

        if action.reason:
            self.lbl_reason.setText(f"💡 {action.reason}")
            self.lbl_reason.setVisible(True)
        else:
            self.lbl_reason.setVisible(False)

        # Primary button label from DTO
        self.btn_primary_action.setText(f"{action.button_label} →")
        self.btn_more.setVisible(action.action_type != "ALL_CAUGHT_UP")

        # Secondary button (meeting link / external URL)
        meeting_link = action.action_payload.get("meeting_link")
        ext_url = action.action_payload.get("url") or action.action_payload.get("application_url")
        if meeting_link:
            self.btn_secondary_action.setText("Join Meeting ↗")
            self.btn_secondary_action.setVisible(True)
        elif ext_url:
            self.btn_secondary_action.setText("Open Link ↗")
            self.btn_secondary_action.setVisible(True)
        else:
            self.btn_secondary_action.setVisible(False)

    def _render_empty_state(self) -> None:
        self._apply_border_style(COLORS['success'])
        self.urgency_badge.raw_text = "ALL CLEAR"
        self.urgency_badge.setText("All Clear")
        self.urgency_badge.update_style("success")
        self.action_category_lbl.setText("•  Job search queue up to date")
        self.lbl_title.setText("You are completely caught up!")
        self.lbl_subtitle.setText("No urgent interviews, replies, or follow-ups pending. Search or qualify new jobs to unlock opportunities.")
        self.lbl_reason.setVisible(False)
        self.btn_primary_action.setText("Search New Jobs →")
        self.btn_secondary_action.setVisible(False)
        self.btn_more.setVisible(False)

    def _show_options_menu(self) -> None:
        if not self._action:
            return

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

        # Option 1: Mark Handled
        act_done = menu.addAction("✓ Mark as Done / Handled")
        act_done.triggered.connect(lambda: self.action_triggered.emit(
            "DISMISS_ITEM",
            {
                "item_id": self._action.action_id,
                "application_id": self._action.action_payload.get("application_id"),
            }
        ))

        # Option 2: Change Status
        app_id = self._action.action_payload.get("application_id")
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
        act_dismiss = menu.addAction("🚫 Dismiss from Hero Card")
        act_dismiss.triggered.connect(lambda: self.action_triggered.emit(
            "DISMISS_ITEM",
            {
                "item_id": self._action.action_id,
                "application_id": self._action.action_payload.get("application_id"),
            }
        ))

        menu.exec_(self.btn_more.mapToGlobal(QPoint(0, self.btn_more.height() + 2)))

    def _on_primary_action_clicked(self) -> None:
        if not self._action:
            self.action_triggered.emit("NAVIGATE_JOBS", {})
            return

        # Map action_name to a navigation action_type for MainWindow routing
        nav_map = {
            "PREPARE_INTERVIEW": "NAVIGATE_INTERVIEW",
            "OPEN_CONVERSATION": "NAVIGATE_OUTREACH",
            "COMPOSE_FOLLOWUP": "NAVIGATE_FOLLOWUP",
            "REVIEW_APPLICATION": "NAVIGATE_APPLICATION",
            "REVIEW_JOB": "NAVIGATE_JOB",
            "NAVIGATE_JOBS": "NAVIGATE_JOBS",
        }
        nav_action = nav_map.get(self._action.action_name, self._action.action_name)
        self.action_triggered.emit(nav_action, dict(self._action.action_payload))

    def _on_secondary_action_clicked(self) -> None:
        if not self._action:
            return
        link = (
            self._action.action_payload.get("meeting_link")
            or self._action.action_payload.get("url")
            or self._action.action_payload.get("application_url")
        )
        if link:
            self.action_triggered.emit("OPEN_URL", {"url": link})
