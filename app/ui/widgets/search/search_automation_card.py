"""Polished Automation Behavior card with modern toggle rows."""

from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchAutomationCard(QFrame):
    """Clean toggle rows for continuous automation mode and search cycle controls."""

    field_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchAutomationCard")
        self.setStyleSheet(f"""
            #searchAutomationCard {{
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
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # 1. Continuous Search Row
        row1 = self._build_toggle_row(
            title="Continuous search mode",
            subtitle="Continue rotating through active keywords with automatic sleep pauses until stopped",
        )
        self.chk_run_non_stop = QCheckBox()
        self.chk_run_non_stop.setStyleSheet(self._checkbox_style())
        self.chk_run_non_stop.toggled.connect(lambda _: self.field_changed.emit())
        row1.addWidget(self.chk_run_non_stop)
        layout.addLayout(row1)

        # 2. Date Freshness Cycling Row
        row2 = self._build_toggle_row(
            title="Automatic freshness cycling",
            subtitle="Expands search scope dynamically if fewer recent jobs are found (24h → week → month)",
        )
        self.chk_cycle_date = QCheckBox()
        self.chk_cycle_date.setStyleSheet(self._checkbox_style())
        self.chk_cycle_date.toggled.connect(lambda _: self.field_changed.emit())
        row2.addWidget(self.chk_cycle_date)
        layout.addLayout(row2)

        # 3. Alternate Search Sorting Row
        row3 = self._build_toggle_row(
            title="Alternate search sort order",
            subtitle="Switches between recent and relevant job feeds on successive search passes",
        )
        self.chk_alternate_sort = QCheckBox()
        self.chk_alternate_sort.setStyleSheet(self._checkbox_style())
        self.chk_alternate_sort.toggled.connect(lambda _: self.field_changed.emit())
        row3.addWidget(self.chk_alternate_sort)
        layout.addLayout(row3)

        # 4. Stop Date Cycle at 24h Row
        row4 = self._build_toggle_row(
            title="Stop freshness cycle at 24 hours",
            subtitle="Strictly locks discovery to the past 24 hours without falling back to older posts",
        )
        self.chk_stop_date_24h = QCheckBox()
        self.chk_stop_date_24h.setStyleSheet(self._checkbox_style())
        self.chk_stop_date_24h.toggled.connect(lambda _: self.field_changed.emit())
        row4.addWidget(self.chk_stop_date_24h)
        layout.addLayout(row4)

        # 5. Cycle Sleep Duration (Sleeping Mode) Row
        row5 = self._build_toggle_row(
            title="Cycle sleep duration (Sleeping Mode)",
            subtitle="Minutes the bot sleeps between search passes in continuous mode (0 to disable)",
        )
        self.spn_sleep_duration = QSpinBox()
        self.spn_sleep_duration.setRange(0, 180)
        self.spn_sleep_duration.setSingleStep(5)
        self.spn_sleep_duration.setValue(10)
        self.spn_sleep_duration.setSuffix(" mins")
        self.spn_sleep_duration.setSpecialValueText("0 (Disabled)")
        self.spn_sleep_duration.setFixedWidth(110)
        self.spn_sleep_duration.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 600;
            }}
        """)
        self.spn_sleep_duration.valueChanged.connect(lambda _: self.field_changed.emit())
        row5.addWidget(self.spn_sleep_duration)
        layout.addLayout(row5)

    def _build_toggle_row(self, title: str, subtitle: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS['text']};")
        text_box.addWidget(lbl_t)

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        text_box.addWidget(lbl_s)

        row.addLayout(text_box, 1)
        return row

    def _divider(self) -> QFrame:
        div = QFrame()
        div.setFrameShape(QFrame.HLine)
        div.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px; border: none;")
        return div

    def _checkbox_style(self) -> str:
        return f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['background']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['primary']};
                border-color: {COLORS['primary']};
            }}
        """
