"""Status badge component for displaying platform, engine, and job statuses.

Provides uniform geometry, consistent dimensions, and standardized ATS color palettes
across all pages (Jobs, Applications, Interviews, Follow-ups, and Modals).
"""

from typing import List, Optional, Sequence
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QLabel, QMenu, QPushButton, QWidget
from app.repositories.validators import CANONICAL_STAGE_LABELS, normalize_display_status
from app.ui.theme import COLORS, ThemeManager

_DARK_BADGE_MAP = {
    "success": ("#34D399", "#064E3B", "#059669", "#065F46"),
    "warning": ("#FBBF24", "#451A03", "#D97706", "#78350F"),
    "danger": ("#F87171", "#450A0A", "#DC2626", "#7F1D1D"),
    "primary": ("#FB923C", "#431407", "#EA580C", "#7C2D12"),
    "info": ("#38BDF8", "#082F49", "#0284C7", "#075985"),
    "purple": ("#C084FC", "#2E1065", "#7C3AED", "#4C1D95"),
    "neutral": ("#9CA3AF", "#1F2937", "#374151", "#374151"),
    "muted": ("#8B949E", "#161B22", "#262C36", "#262C36"),
    "default": ("#9CA3AF", "#1F2937", "#374151", "#374151"),
}

_LIGHT_BADGE_MAP = {
    "success": ("#14532D", "#DCFCE7", "#86EFAC", "#BBF7D0"),
    "warning": ("#78350F", "#FEF3C7", "#FCD34D", "#FDE68A"),
    "danger": ("#7F1D1D", "#FEE2E2", "#FCA5A5", "#FECACA"),
    "primary": ("#9A3412", "#FFEDD5", "#FDBA74", "#FED7AA"),
    "info": ("#075985", "#E0F2FE", "#7DD3FC", "#BAE6FD"),
    "purple": ("#581C87", "#F3E8FF", "#D8B4FE", "#E9D5FF"),
    "neutral": ("#374151", "#F3F4F6", "#D1D5DB", "#E5E7EB"),
    "muted": ("#4B5563", "#F3F4F6", "#D1D5DB", "#E5E7EB"),
    "default": ("#374151", "#F3F4F6", "#D1D5DB", "#E5E7EB"),
}

STATUS_DISPLAY_LABELS = {
    **CANONICAL_STAGE_LABELS,
    "PENDING": "Pending",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
    "NO_SHOW": "No Show",
    "SCHEDULED": "Scheduled",
    "OVERDUE": "Overdue",
    "READY": "Ready",
    "ACTIVE": "Active",
    "IDLE": "Idle",
    "VERIFIED": "Verified",
    "NEEDS_REVIEW": "Needs Review",
    "DISCOVERED": "Not Applied",
    "QUALIFIED": "Not Applied",
    "EXTERNAL": "Not Applied",
}


class StatusBadge(QLabel):
    """Uniform pill badge displaying status with consistent geometry and colors across all pages."""

    DEFAULT_WIDTH = 110
    DEFAULT_HEIGHT = 24

    def __init__(
        self,
        text: str,
        status_type: str = "default",
        parent=None,
        variant: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ):
        self.raw_text = str(text or "")
        display_text = STATUS_DISPLAY_LABELS.get(
            self.raw_text.strip().upper(),
            self.raw_text.replace("_", " ").title()
        )
        super().__init__(display_text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip(f"Status: {self.raw_text}")

        # Uniform fixed geometry to ensure consistent appearance regardless of text length
        w = width or self.DEFAULT_WIDTH
        h = height or self.DEFAULT_HEIGHT
        self._h = h
        self._w = w
        self.setFixedSize(w, h)

        self.update_style(variant or status_type)

    def update_style(self, status_type: str):
        palette = _LIGHT_BADGE_MAP if ThemeManager.current_mode == "light" else _DARK_BADGE_MAP

        # Derive variant from raw text if not explicitly provided or if default
        st_upper = self.raw_text.strip().upper()
        if status_type in ["default", "neutral", None]:
            if st_upper in ["SUBMITTED", "OFFER", "COMPLETED", "READY", "QUALIFIED"]:
                status_type = "success"
            elif st_upper in ["UNDER_REVIEW", "WARNING", "MANUAL_REQUIRED", "PENDING"]:
                status_type = "warning"
            elif st_upper in ["SHORTLISTED", "RECRUITER_CONTACTED", "ACTIVE"]:
                status_type = "primary"
            elif st_upper in ["ASSESSMENT", "INTERVIEW", "SCHEDULED"]:
                status_type = "purple"
            elif st_upper in ["REJECTED", "FAILED", "OVERDUE", "CANCELLED"]:
                status_type = "danger"
            elif st_upper in ["JUNK"]:
                status_type = "muted"
            elif st_upper in ["WITHDRAWN", "SKIPPED", "NOT_APPLIED", "DISCOVERED", "IDLE"]:
                status_type = "neutral"

        fg, bg, border, _ = palette.get(status_type, palette["default"])
        radius = getattr(self, "_h", self.height()) // 2

        self.setStyleSheet(f"""
            QLabel {{
                color: {fg};
                background-color: {bg};
                border: 1px solid {border};
                border-radius: {radius}px;
                padding: 0px 4px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.2px;
            }}
        """)


class StatusDropdownButton(QPushButton):
    """Interactive status pill button with a dropdown chevron for 1-click stage transitions across all ATS views."""

    status_changed = Signal(str)  # target status string

    STATUS_OPTIONS = [
        ("SUBMITTED", "Submitted", "success"),
        ("UNDER_REVIEW", "Under Review", "warning"),
        ("SHORTLISTED", "Shortlisted", "primary"),
        ("RECRUITER_CONTACTED", "Recruiter Call", "primary"),
        ("ASSESSMENT", "Assessment", "purple"),
        ("INTERVIEW", "Interview", "purple"),
        ("OFFER", "Offer", "success"),
        ("REJECTED", "Rejected", "danger"),
        ("WITHDRAWN", "Withdrawn", "neutral"),
        ("MANUAL_REQUIRED", "Manual Check", "warning"),
        ("FAILED", "Failed", "danger"),
        ("SKIPPED", "Skipped", "neutral"),
        ("NOT_APPLIED", "Not Applied", "neutral"),
    ]

    def __init__(
        self,
        current_status: str,
        parent: Optional[QWidget] = None,
        allowed_statuses: Optional[Sequence[str]] = None,
    ):
        super().__init__(parent)
        self._allowed_statuses = set(allowed_statuses) if allowed_statuses else None
        self.current_status = normalize_display_status(current_status)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(118, 22)
        self.update_display(self.current_status)
        self.clicked.connect(self._show_menu)

    def update_display(self, status: str) -> None:
        self.current_status = normalize_display_status(status)
        display_label = STATUS_DISPLAY_LABELS.get(self.current_status, self.current_status.replace("_", " ").title())
        self.setText(f"{display_label} ▾")
        self.setToolTip(f"Current Stage: {display_label}\nClick to change job stage")

        palette = _LIGHT_BADGE_MAP if ThemeManager.current_mode == "light" else _DARK_BADGE_MAP
        st = "neutral"
        if self.current_status in ["SUBMITTED", "OFFER", "COMPLETED", "READY", "QUALIFIED"]:
            st = "success"
        elif self.current_status in ["UNDER_REVIEW", "WARNING", "MANUAL_REQUIRED", "PENDING"]:
            st = "warning"
        elif self.current_status in ["SHORTLISTED", "RECRUITER_CONTACTED", "ACTIVE"]:
            st = "primary"
        elif self.current_status in ["ASSESSMENT", "INTERVIEW", "SCHEDULED"]:
            st = "purple"
        elif self.current_status in ["REJECTED", "FAILED", "OVERDUE", "CANCELLED"]:
            st = "danger"

        fg, bg, border, hover_bg = palette.get(st, palette["neutral"])
        hover_fg = fg if ThemeManager.current_mode == "light" else "#FFFFFF"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 11px;
                padding: 0px 6px;
                font-size: 11px;
                font-weight: 700;
                text-align: center;
            }}
            QPushButton:hover {{
                border-color: {fg};
                background-color: {hover_bg};
                color: {hover_fg};
            }}
            QPushButton:focus {{
                border: 2px solid {COLORS["primary"]};
                padding: 0px 5px;
            }}
        """)

    def _show_menu(self) -> None:
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

        hdr = menu.addAction("Change Job Stage:")
        hdr.setEnabled(False)
        menu.addSeparator()

        for code, label, _ in self.STATUS_OPTIONS:
            if self._allowed_statuses and code not in self._allowed_statuses:
                continue
            act = menu.addAction(label)
            if code == self.current_status:
                act.setText(f"* {label}")
                act.setEnabled(False)
            act.triggered.connect(lambda _, c=code: self._on_action_triggered(c))

        menu.exec_(self.mapToGlobal(QPoint(0, self.height() + 2)))

    def _on_action_triggered(self, new_status: str) -> None:
        self.update_display(new_status)
        self.status_changed.emit(new_status)


