"""Compact, unboxed Strategy Summary header card with clean status and preview button."""

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

from app.ui.theme import COLORS


class SearchSummaryCard(QFrame):
    """Compact summary header card displaying active strategy attributes and readiness status."""

    preview_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchSummaryCard")
        self.setStyleSheet(f"""
            #searchSummaryCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']}40;
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        # Header Row (Title + Status Dot + Preview Button)
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        title_lbl = QLabel("Active Strategy")
        title_lbl.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        top_row.addWidget(title_lbl)

        self.lbl_health = QLabel("● Strategy Ready")
        self.lbl_health.setStyleSheet(f"""
            color: {COLORS['success']};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        top_row.addWidget(self.lbl_health)

        top_row.addStretch()

        self.btn_preview = QPushButton("Preview Search 👁")
        self.btn_preview.setCursor(Qt.PointingHandCursor)
        self.btn_preview.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']}60;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_preview.clicked.connect(self.preview_clicked.emit)
        top_row.addWidget(self.btn_preview)

        layout.addLayout(top_row)

        # Two-line clean summary text
        self.lbl_roles = QLabel("Configuring target roles...")
        self.lbl_roles.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.lbl_roles)

        self.lbl_meta = QLabel("Configuring search scope...")
        self.lbl_meta.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.lbl_meta)

    def update_summary(
        self,
        keywords: List[str],
        location: str,
        platform: str,
        sync_all: bool,
        experience: int,
        date_posted: str,
        easy_apply: bool,
        continuous: bool,
    ) -> None:
        """Refreshes the summary card lines and status health dot."""
        has_keywords = len(keywords) > 0
        has_location = bool(location.strip())

        if not has_keywords:
            self.lbl_health.setText("● No Target Keywords")
            self.lbl_health.setStyleSheet(f"color: {COLORS['danger']}; font-size: 12px; font-weight: 600;")
        elif not has_location:
            self.lbl_health.setText("● Location Unstated")
            self.lbl_health.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; font-weight: 600;")
        else:
            self.lbl_health.setText("● Strategy Ready")
            self.lbl_health.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px; font-weight: 600;")

        # Roles line
        roles_text = " · ".join(keywords[:4]) if keywords else "No keywords configured"
        if len(keywords) > 4:
            roles_text += f" (+{len(keywords) - 4} more)"
        self.lbl_roles.setText(roles_text)

        # Metadata line
        plat_display = "LinkedIn" if platform.lower() == "linkedin" else platform.title()
        plat_str = "LinkedIn · Naukri · Indeed" if sync_all else plat_display
        method_str = "Easy Apply" if easy_apply else "All Listings"
        exp_str = f"0–{experience} yrs" if experience >= 0 else "Any experience"
        cycle_str = "Continuous" if continuous else "Single Run"

        self.lbl_meta.setText(
            f"{plat_str}  ·  {location or 'Any Location'}  ·  {exp_str}  ·  {date_posted}  ·  {method_str}  ·  {cycle_str}"
        )
