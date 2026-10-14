"""Status badge component for displaying platform, engine, and job statuses.

Provides uniform geometry, consistent dimensions, and standardized ATS color palettes
across all pages (Jobs, Applications, Interviews, Follow-ups, and Modals).
"""

from typing import Optional
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QLabel, QMenu, QPushButton, QWidget
from app.ui.theme import COLORS

STATUS_DISPLAY_LABELS = {
    "SUBMITTED": "Submitted",
    "UNDER_REVIEW": "Under Review",
    "SHORTLISTED": "Shortlisted",
    "RECRUITER_CONTACTED": "Recruiter Call",
    "ASSESSMENT": "Assessment",
    "INTERVIEW": "Interview",
    "OFFER": "Offer",
    "REJECTED": "Rejected",
    "WITHDRAWN": "Withdrawn",
    "APPLYING": "Applying",
    "MANUAL_REQUIRED": "Manual Check",
    "FAILED": "Failed",
    "DISCOVERED": "Discovered",
    "QUALIFIED": "Qualified",
    "SKIPPED": "Skipped",
    "JUNK": "Junk",
    "PENDING": "Pending",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
    "SCHEDULED": "Scheduled",
    "OVERDUE": "Overdue",
    "NOT_APPLIED": "Not Applied",
    "READY": "Ready",
    "ACTIVE": "Active",
    "IDLE": "Idle",
    "VERIFIED": "Verified",
    "NEEDS_REVIEW": "Needs Review",
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
        color_map = {
            "success": ("#34D399", "#064E3B", "#059669"),
            "warning": ("#FBBF24", "#451A03", "#D97706"),
            "danger": ("#F87171", "#450A0A", "#DC2626"),
            "primary": ("#FB923C", "#431407", "#EA580C"),
            "info": ("#38BDF8", "#082F49", "#0284C7"),
            "purple": ("#C084FC", "#2E1065", "#7C3AED"),
            "neutral": ("#9CA3AF", "#1F2937", "#374151"),
            "muted": ("#8B949E", "#161B22", "#262C36"),
            "default": ("#9CA3AF", "#1F2937", "#374151"),
        }

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

        fg, bg, border = color_map.get(status_type, color_map["default"])
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
        ("SUBMITTED", "📄 Submitted", "success"),
        ("UNDER_REVIEW", "⏳ Under Review", "warning"),
        ("SHORTLISTED", "🌟 Shortlisted", "primary"),
        ("ASSESSMENT", "📝 Assessment", "purple"),
        ("INTERVIEW", "🗓️ Interview", "purple"),
        ("OFFER", "🎉 Offer", "success"),
        ("REJECTED", "❌ Rejected", "danger"),
        ("WITHDRAWN", "↩️ Withdrawn", "neutral"),
        ("FAILED", "⚠️ Failed", "danger"),
        ("MANUAL_REQUIRED", "🖐️ Manual Check", "warning"),
        ("NOT_APPLIED", "⚪ Not Applied", "neutral"),
    ]

    def __init__(self, current_status: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_status = (current_status or "NOT_APPLIED").strip().upper()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(112, 22)
        self.update_display(self.current_status)
        self.clicked.connect(self._show_menu)

    def update_display(self, status: str) -> None:
        self.current_status = (status or "NOT_APPLIED").strip().upper()
        display_label = STATUS_DISPLAY_LABELS.get(self.current_status, self.current_status.replace("_", " ").title())
        self.setText(f"{display_label} ▾")
        self.setToolTip(f"Current Stage: {display_label}\nClick to change job stage")

        color_map = {
            "success": ("#34D399", "#064E3B", "#059669"),
            "warning": ("#FBBF24", "#451A03", "#D97706"),
            "danger": ("#F87171", "#450A0A", "#DC2626"),
            "primary": ("#FB923C", "#431407", "#EA580C"),
            "purple": ("#C084FC", "#2E1065", "#7C3AED"),
            "neutral": ("#9CA3AF", "#1F2937", "#374151"),
        }
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

        fg, bg, border = color_map.get(st, color_map["neutral"])
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
                background-color: {border}40;
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
            act = menu.addAction(label)
            if code == self.current_status:
                act.setText(f"✓ {label}")
                act.setEnabled(False)
            act.triggered.connect(lambda _, c=code: self._on_action_triggered(c))

        menu.exec_(self.mapToGlobal(QPoint(0, self.height() + 2)))

    def _on_action_triggered(self, new_status: str) -> None:
        self.update_display(new_status)
        self.status_changed.emit(new_status)


