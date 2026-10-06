"""Status badge component for displaying platform, engine, and job statuses.

Provides uniform geometry, consistent dimensions, and standardized ATS color palettes
across all pages (Jobs, Applications, Interviews, Follow-ups, and Modals).
"""

from typing import Optional
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Qt
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

