"""Visual ATS Application Pipeline Funnel component.

Displays horizontal recruitment stage distribution bars with percentages and counts.
Inspired by modern ATS pipeline analytics.
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        # Stage indicator dot and name
        lbl_name = QLabel(f"●  {label}")
        lbl_name.setFixedWidth(110)
        lbl_name.setStyleSheet(f"""
            QLabel {{
                color: {self.color};
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(lbl_name)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1C2128;
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.color};
                border-radius: 4px;
            }}
        """)
        val = int((count / max(1, max_count)) * 100) if max_count > 0 else 0
        self.progress.setValue(val)
        layout.addWidget(self.progress, 1)

        # Count & Percentage
        self.lbl_count = QLabel(f"{count}")
        self.lbl_count.setFixedWidth(50)
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_count.setStyleSheet("""
            QLabel {
                color: #F0F6FC;
                font-size: 13px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.lbl_count)

    def set_data(self, count: int, max_count: int) -> None:
        val = int((count / max(1, max_count)) * 100) if max_count > 0 else 0
        self.progress.setValue(val)
        self.lbl_count.setText(str(count))


class PipelineFunnelCard(QFrame):
    """Card displaying recruitment stage funnel progression."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        top_row = QHBoxLayout()
        lbl_title = QLabel("Recruitment Pipeline Funnel")
        lbl_title.setStyleSheet("""
            QLabel {
                color: #F0F6FC;
                font-size: 14px;
                font-weight: 700;
                background: transparent;
                border: none;
            }
        """)
        top_row.addWidget(lbl_title)
        top_row.addStretch()

        self.lbl_total_apps = QLabel("0 Total Active")
        self.lbl_total_apps.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-size: 11px;
                font-weight: 600;
                background-color: #1C2128;
                border: 1px solid #262C36;
                padding: 3px 8px;
                border-radius: 6px;
            }
        """)
        top_row.addWidget(self.lbl_total_apps)
        layout.addLayout(top_row)

        # Stage rows
        self.stage_rows: Dict[str, FunnelStageRow] = {}

        stages = [
            ("Discovered", COLORS.get("cyan", "#06b6d4")),
            ("Submitted", COLORS.get("info", "#0284c7")),
            ("Under Review", COLORS.get("warning", "#f59e0b")),
            ("Interview", COLORS.get("purple", "#8b5cf6")),
            ("Offer", COLORS.get("success", "#10b981")),
            ("Withdrawn", "#8B949E"),
            ("Rejected", "#EF4444"),
        ]

        for stage_name, color in stages:
            row = FunnelStageRow(stage_name, 0, 100, color)
            self.stage_rows[stage_name] = row
            layout.addWidget(row)

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
        """Updates counts and recalculates bar widths."""
        max_c = max(discovered, submitted, under_review, interview, offer, withdrawn, rejected, 1)
        self.stage_rows["Discovered"].set_data(discovered, max_c)
        self.stage_rows["Submitted"].set_data(submitted, max_c)
        self.stage_rows["Under Review"].set_data(under_review, max_c)
        self.stage_rows["Interview"].set_data(interview, max_c)
        self.stage_rows["Offer"].set_data(offer, max_c)
        if "Withdrawn" in self.stage_rows:
            self.stage_rows["Withdrawn"].set_data(withdrawn, max_c)
        if "Rejected" in self.stage_rows:
            self.stage_rows["Rejected"].set_data(rejected, max_c)

        total_active = submitted + under_review + interview + offer
        self.lbl_total_apps.setText(f"{total_active} In Pipeline")

