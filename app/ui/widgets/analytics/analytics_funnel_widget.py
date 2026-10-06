"""Recruitment funnel visualization displaying stage-to-stage conversion and drop-off."""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class AnalyticsFunnelWidget(QFrame):
    """Funnel component showing conversion efficiency and volume loss across stages."""

    stage_clicked = Signal(str)  # Emits stage_id: 'discovered', 'qualified', 'submitted', 'responses', 'interviews', 'offers'

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AnalyticsFunnelWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        lbl_title = QLabel("Recruitment Funnel & Conversion")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        lbl_sub = QLabel("Stage-to-stage conversion & drop-off")
        lbl_sub.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        header_row.addWidget(lbl_sub)
        layout.addLayout(header_row)

        # Container for stages
        self.stages_container = QVBoxLayout()
        self.stages_container.setSpacing(6)
        layout.addLayout(self.stages_container)

    def update_funnel(self, funnel_data: Dict[str, Any]) -> None:
        """Renders factual stages with conversion bars and drop-off percentages."""
        # Clear existing
        while self.stages_container.count():
            item = self.stages_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        stages: List[Dict[str, Any]] = funnel_data.get("stages", [])
        if not stages:
            empty_lbl = QLabel("No funnel data available")
            empty_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            empty_lbl.setAlignment(Qt.AlignCenter)
            self.stages_container.addWidget(empty_lbl)
            return

        max_cohort_count = max(1, max(s.get("count", 0) for s in stages))

        for idx, s in enumerate(stages):
            stage_id = s.get("stage_id", "")
            label = s.get("label", "")
            count = s.get("count", 0)
            conv_pct = s.get("conversion_pct", 0.0)
            drop_pct = s.get("drop_off_pct", 0.0)
            cohort_type = s.get("cohort_type", "")

            # If transitioning from Discovery to Application cohort, add a subtle divider pill
            if idx > 0 and stages[idx - 1].get("cohort_type") == "DISCOVERY" and cohort_type == "APPLICATION":
                sep_frame = QFrame()
                sep_frame.setStyleSheet(f"background-color: {COLORS['border_subtle']}; min-height: 1px; max-height: 1px;")
                self.stages_container.addWidget(sep_frame)

            row = QFrame()
            row.setCursor(Qt.PointingHandCursor)
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                }}
                QFrame:hover {{
                    border-color: {COLORS['primary']};
                    background-color: {COLORS['surface_hover']};
                }}
            """)
            r_layout = QVBoxLayout(row)
            r_layout.setContentsMargins(10, 8, 10, 8)
            r_layout.setSpacing(4)

            # Top label row: Name + Count + Conversion/Drop-off
            meta_row = QHBoxLayout()
            meta_row.setSpacing(8)

            lbl_name = QLabel(label)
            lbl_name.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text']}; border: none; background: transparent;")
            meta_row.addWidget(lbl_name)

            lbl_cohort = QLabel(f"[{cohort_type.title()}]")
            lbl_cohort.setStyleSheet(f"font-size: 9px; color: {COLORS['text_muted']}; border: none; background: transparent;")
            meta_row.addWidget(lbl_cohort)

            meta_row.addStretch()

            # If not the very first stage, show step-to-step conversion & drop-off
            if idx > 0:
                conv_tag = QLabel(f"{conv_pct}% conv ({drop_pct}% drop)")
                conv_tag.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; border: none; background: transparent;")
                meta_row.addWidget(conv_tag)

            lbl_cnt = QLabel(f"{count:,}")
            lbl_cnt.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {COLORS['primary']}; border: none; background: transparent;")
            meta_row.addWidget(lbl_cnt)
            r_layout.addLayout(meta_row)

            # Visual volume bar
            pbar = QProgressBar()
            pbar.setFixedHeight(6)
            pbar.setTextVisible(False)
            pbar.setRange(0, max_cohort_count)
            pbar.setValue(count)
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {COLORS['surface']};
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background-color: {COLORS['primary']};
                    border-radius: 3px;
                }}
            """)
            r_layout.addWidget(pbar)

            # Connect click to drill-down
            row.mousePressEvent = lambda ev, sid=stage_id: self.stage_clicked.emit(sid)

            self.stages_container.addWidget(row)
