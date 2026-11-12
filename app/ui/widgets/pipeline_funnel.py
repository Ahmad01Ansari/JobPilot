"""Visual ATS Application Pipeline Funnel component.

Displays horizontal recruitment stage distribution bars with counts and conversion percentages.
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from app.ui.theme import COLORS


class FunnelStageRow(QWidget):
    """Single stage row in the recruitment pipeline funnel."""

    def __init__(self, label: str, count: int, max_count: int, color: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color = color
        self._label = label

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        # Stage indicator dot + accessible label
        self.dot = QFrame()
        self.dot.setFixedSize(8, 8)
        self.dot.setStyleSheet(f"background-color: {self.color}; border-radius: 4px; border: none;")
        layout.addWidget(self.dot)

        self.lbl_name = QLabel(label)
        self.lbl_name.setFixedWidth(100)
        self.lbl_name.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text"]};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        layout.addWidget(self.lbl_name)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress, 1)

        # Count & conversion share
        self.lbl_count = QLabel("0")
        self.lbl_count.setObjectName("FunnelCount")
        self.lbl_count.setFixedWidth(82)
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.lbl_count)

        self.apply_theme()
        self.set_data(count, max_count)

    def apply_theme(self) -> None:
        """Applies current ThemeManager tokens to row label, bar track, and count readout."""
        self.lbl_name.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text"]};
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }}
        """)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS["surface_alt"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.color};
                border-radius: 3px;
            }}
        """)
        self.lbl_count.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text"]};
                font-size: 12px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)

    def set_data(self, count: int, max_count: int, ratio_base: int = 0) -> None:
        """Updates stage bar fill, raw count, and optional percentage share."""
        val = int((count / max(1, max_count)) * 100) if max_count > 0 else 0
        self.progress.setValue(val)
        if ratio_base > 0:
            pct = round((count / ratio_base) * 100)
            self.lbl_count.setText(f"{count} ({pct}%)")
        else:
            self.lbl_count.setText(str(count))


class PipelineFunnelCard(QFrame):
    """Card displaying recruitment stage funnel progression."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        top_row = QHBoxLayout()
        self.lbl_title = QLabel("Recruitment Pipeline Funnel")
        self.lbl_title.setObjectName("FunnelTitle")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.lbl_total_apps = QLabel("0 In Pipeline")
        self.lbl_total_apps.setObjectName("FunnelTotal")
        top_row.addWidget(self.lbl_total_apps)
        layout.addLayout(top_row)

        # Stage rows
        self.stage_rows: Dict[str, FunnelStageRow] = {}
        stages = [
            ("Discovered", COLORS.get("cyan", "#39C5CF")),
            ("Submitted", COLORS.get("info", "#388BFD")),
            ("Under Review", COLORS.get("warning", "#D29922")),
            ("Interview", COLORS.get("purple", "#A371F7")),
            ("Offer", COLORS.get("success", "#2EA043")),
            ("Withdrawn", COLORS.get("text_muted", "#8B949E")),
            ("Rejected", COLORS.get("danger", "#F85149")),
        ]

        for stage_name, color in stages:
            row = FunnelStageRow(stage_name, 0, 100, color)
            self.stage_rows[stage_name] = row
            layout.addWidget(row)

        self.apply_theme()

    def apply_theme(self) -> None:
        """Applies current ThemeManager tokens to card container and stage rows."""
        self.setStyleSheet(f"""
            PipelineFunnelCard {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
            }}
        """)
        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text"]};
                font-size: 14px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_total_apps.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text_muted"]};
                font-size: 11px;
                font-weight: 600;
                background-color: {COLORS["surface_alt"]};
                border: 1px solid {COLORS["border"]};
                padding: 3px 8px;
                border-radius: 6px;
            }}
        """)
        for row in self.stage_rows.values():
            row.apply_theme()

    def update_stages(
        self,
        discovered: int,
        submitted: int,
        under_review: int,
        interview: int,
        offer: int,
        withdrawn: int = 0,
        rejected: int = 0,
    ) -> None:
        """Updates counts, conversion shares, and bar widths."""
        max_c = max(discovered, submitted, under_review, interview, offer, withdrawn, rejected, 1)
        pipeline_base = submitted if submitted > 0 else discovered

        self.stage_rows["Discovered"].set_data(discovered, max_c, discovered if discovered > 0 else 0)
        self.stage_rows["Submitted"].set_data(submitted, max_c, discovered if discovered > 0 else 0)
        self.stage_rows["Under Review"].set_data(under_review, max_c, pipeline_base)
        self.stage_rows["Interview"].set_data(interview, max_c, pipeline_base)
        self.stage_rows["Offer"].set_data(offer, max_c, pipeline_base)
        if "Withdrawn" in self.stage_rows:
            self.stage_rows["Withdrawn"].set_data(withdrawn, max_c, pipeline_base)
        if "Rejected" in self.stage_rows:
            self.stage_rows["Rejected"].set_data(rejected, max_c, pipeline_base)

        total_active = submitted + under_review + interview + offer
        self.lbl_total_apps.setText(f"{total_active} In Pipeline")
