"""Resume Library KPI Summary Bar.

Displays 5 factual domain metrics:
1. Total Active Resumes
2. Active Lineages (Version Families)
3. Default Resume Status
4. Technical Health Breakdown (Valid, Needs Attention, Invalid)
5. Total Applications Linked
"""

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class KpiPill(QFrame):
    """Modern card pill displaying a single domain KPI."""

    def __init__(
        self,
        icon: str,
        label: str,
        value: str,
        subtext: Optional[str] = None,
        badge_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("kpiPill")
        self.setStyleSheet(f"""
            QFrame#kpiPill {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
            QFrame#kpiPill:hover {{
                border-color: {COLORS['border_hover'] if 'border_hover' in COLORS else COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Icon container
        self.icon_label = QLabel(icon)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                background-color: {badge_color or COLORS['surface_alt']};
                color: {COLORS['text']};
                border-radius: 6px;
                min-width: 36px;
                max-width: 36px;
                min-height: 36px;
                max-height: 36px;
            }}
        """)
        layout.addWidget(self.icon_label)

        # Text column
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.lbl_title = QLabel(label.upper())
        self.lbl_title.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 700;
            color: {COLORS['text_muted']};
            letter-spacing: 0.5px;
        """)
        text_layout.addWidget(self.lbl_title)

        val_row = QHBoxLayout()
        val_row.setContentsMargins(0, 0, 0, 0)
        val_row.setSpacing(6)

        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet(f"""
            font-size: 15px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        val_row.addWidget(self.lbl_value)

        if subtext:
            self.lbl_subtext = QLabel(subtext)
            self.lbl_subtext.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['text_secondary'] if 'text_secondary' in COLORS else COLORS['text_muted']};
            """)
            val_row.addWidget(self.lbl_subtext)
        else:
            self.lbl_subtext = None

        val_row.addStretch()
        text_layout.addLayout(val_row)
        layout.addLayout(text_layout)

    def update_data(self, value: str, subtext: Optional[str] = None):
        self.lbl_value.setText(value)
        if self.lbl_subtext and subtext is not None:
            self.lbl_subtext.setText(subtext)


class ResumeSummaryBar(QWidget):
    """Bar presenting 5 domain KPI pills across the top of the resume workspace."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Total Active Resumes
        self.pill_active = KpiPill(
            icon="📄",
            label="Active Resumes",
            value="0",
            subtext="in library",
        )
        layout.addWidget(self.pill_active, 1)

        # 2. Lineages (Families)
        self.pill_lineages = KpiPill(
            icon="🧬",
            label="Version Families",
            value="0",
            subtext="lineages",
        )
        layout.addWidget(self.pill_lineages, 1)

        # 3. Default Resume
        self.pill_default = KpiPill(
            icon="⭐",
            label="Default Resume",
            value="None",
            subtext="for auto-apply",
        )
        layout.addWidget(self.pill_default, 2)

        # 4. Technical Health
        self.pill_health = KpiPill(
            icon="🩺",
            label="Technical Health",
            value="0 Valid",
            subtext="0 Attention",
        )
        layout.addWidget(self.pill_health, 2)

        # 5. Application Usage
        self.pill_usage = KpiPill(
            icon="🚀",
            label="Applications",
            value="0",
            subtext="linked",
        )
        layout.addWidget(self.pill_usage, 1)

    def set_summary(self, summary_data: Dict[str, Any]):
        """Populates KPI pills from ResumeService.get_library_summary dictionary."""
        total_active = str(summary_data.get("total_resumes", 0))
        archived = summary_data.get("archived_count", 0)
        self.pill_active.update_data(
            value=total_active,
            subtext=f"+{archived} archived" if archived else "in library",
        )

        lineages = str(summary_data.get("active_lineages_count", 0))
        self.pill_lineages.update_data(
            value=lineages,
            subtext="lineages",
        )

        default_name = summary_data.get("default_resume_name", "None")
        if len(default_name) > 22:
            display_name = default_name[:20] + "..."
        else:
            display_name = default_name
        self.pill_default.update_data(
            value=display_name,
            subtext="auto-apply",
        )

        health = summary_data.get("health_summary", {})
        valid = health.get("valid", 0)
        attention = health.get("needs_attention", 0)
        invalid = health.get("invalid", 0)

        health_val = f"{valid} Valid"
        health_sub = f"{attention} Attention" if attention else (f"{invalid} Invalid" if invalid else "100% Sound")
        self.pill_health.update_data(
            value=health_val,
            subtext=health_sub,
        )

        apps = str(summary_data.get("total_applications_linked", 0))
        self.pill_usage.update_data(
            value=apps,
            subtext="linked",
        )
