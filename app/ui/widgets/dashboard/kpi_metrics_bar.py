"""Top KPI Metrics Bar for Dashboard Command Center.

Displays 6 high-level pipeline cards matching the Applications pipeline aesthetic:
1. Total Jobs (Discovered)
2. Submitted
3. Under Review
4. Interviewing
5. Offers
6. Rejected
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class KPICard(QFrame):
    """Individual clickable metric card with colored top accent."""

    clicked = Signal(str)  # target_stage or "jobs"

    def __init__(
        self,
        title: str,
        value: str,
        color_hex: str,
        target_stage: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.title = title
        self.target_stage = target_stage
        self.color_hex = color_hex
        self._setup_ui(value)

    def _setup_ui(self, value: str) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"View {self.title}")
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {self.color_hex};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {self.color_hex};
                background-color: {COLORS['surface_hover']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(3)

        self.lbl_val = QLabel(value)
        self.lbl_val.setStyleSheet(
            f"font-size: 22px; font-weight: 800; color: {self.color_hex}; "
            "border: none; background: transparent;"
        )

        self.lbl_title = QLabel(self.title)
        self.lbl_title.setStyleSheet(
            f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.5px; border: none; background: transparent;"
        )

        layout.addWidget(self.lbl_val)
        layout.addWidget(self.lbl_title)

    def set_value(self, val: int) -> None:
        self.lbl_val.setText(f"{val:,}")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.target_stage)
        super().mousePressEvent(event)


class DashboardKPICardsBar(QFrame):
    """Horizontal 6-metric summary strip at the top of the dashboard."""

    navigation_requested = Signal(str, dict)  # (view_name, params)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Total Jobs Discovered
        self.card_total_jobs = KPICard(
            title="Total Discovered",
            value="0",
            color_hex=COLORS.get("secondary", "#60A5FA"),
            target_stage="jobs",
            parent=self,
        )
        self.card_total_jobs.clicked.connect(lambda: self.navigation_requested.emit("jobs", {}))
        layout.addWidget(self.card_total_jobs)

        # 2. Submitted
        self.card_submitted = KPICard(
            title="Submitted",
            value="0",
            color_hex=COLORS.get("info", "#38BDF8"),
            target_stage="SUBMITTED",
            parent=self,
        )
        self.card_submitted.clicked.connect(
            lambda: self.navigation_requested.emit("applications", {"status": "SUBMITTED"})
        )
        layout.addWidget(self.card_submitted)

        # 3. Under Review
        self.card_review = KPICard(
            title="Under Review",
            value="0",
            color_hex=COLORS.get("warning", "#FBBF24"),
            target_stage="UNDER_REVIEW",
            parent=self,
        )
        self.card_review.clicked.connect(
            lambda: self.navigation_requested.emit("applications", {"status": "UNDER_REVIEW"})
        )
        layout.addWidget(self.card_review)

        # 4. Interviewing
        self.card_interviewing = KPICard(
            title="Interviewing",
            value="0",
            color_hex=COLORS.get("purple", "#A78BFA"),
            target_stage="INTERVIEWING",
            parent=self,
        )
        self.card_interviewing.clicked.connect(
            lambda: self.navigation_requested.emit("interviews", {})
        )
        layout.addWidget(self.card_interviewing)

        # 5. Offers
        self.card_offers = KPICard(
            title="Offers",
            value="0",
            color_hex=COLORS.get("success", "#34D399"),
            target_stage="OFFER",
            parent=self,
        )
        self.card_offers.clicked.connect(
            lambda: self.navigation_requested.emit("applications", {"status": "OFFER"})
        )
        layout.addWidget(self.card_offers)

        # 6. Rejected
        self.card_rejected = KPICard(
            title="Rejected",
            value="0",
            color_hex=COLORS.get("danger", "#F87171"),
            target_stage="REJECTED",
            parent=self,
        )
        self.card_rejected.clicked.connect(
            lambda: self.navigation_requested.emit("applications", {"status": "REJECTED"})
        )
        layout.addWidget(self.card_rejected)

    def update_metrics(
        self,
        total_jobs: int = 0,
        submitted: int = 0,
        under_review: int = 0,
        interviewing: int = 0,
        offers: int = 0,
        rejected: int = 0,
    ) -> None:
        """Binds updated counts to each metric card."""
        self.card_total_jobs.set_value(total_jobs)
        self.card_submitted.set_value(submitted)
        self.card_review.set_value(under_review)
        self.card_interviewing.set_value(interviewing)
        self.card_offers.set_value(offers)
        self.card_rejected.set_value(rejected)
