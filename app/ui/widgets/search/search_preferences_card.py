"""Polished, compact Search Preferences card."""

from typing import Optional
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchPreferencesCard(QFrame):
    """Clean 2-column configuration card for search pagination, freshness, and thresholds."""

    field_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchPreferencesCard")
        self.setStyleSheet(f"""
            #searchPreferencesCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']}40;
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QComboBox, QSpinBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QComboBox:focus, QSpinBox:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)

        # 1. Search Freshness
        fresh_box = QVBoxLayout()
        fresh_box.setSpacing(4)
        lbl_fresh = QLabel("Search Freshness")
        lbl_fresh.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        fresh_box.addWidget(lbl_fresh)

        self.cmb_date_posted = QComboBox()
        self.cmb_date_posted.addItems(["Past 24 hours", "Past week", "Past month", "Any time"])
        self.cmb_date_posted.setFixedHeight(34)
        self.cmb_date_posted.currentIndexChanged.connect(lambda _: self.field_changed.emit())
        fresh_box.addWidget(self.cmb_date_posted)

        lbl_fresh_hint = QLabel("Time horizon for discovered jobs")
        lbl_fresh_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        fresh_box.addWidget(lbl_fresh_hint)
        grid.addLayout(fresh_box, 0, 0)

        # 2. Max Pages / Keyword
        pages_box = QVBoxLayout()
        pages_box.setSpacing(4)
        lbl_pages = QLabel("Max Pages / Keyword")
        lbl_pages.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        pages_box.addWidget(lbl_pages)

        self.spn_max_pages = QSpinBox()
        self.spn_max_pages.setRange(1, 20)
        self.spn_max_pages.setValue(3)
        self.spn_max_pages.setSuffix(" pages")
        self.spn_max_pages.setFixedHeight(34)
        self.spn_max_pages.valueChanged.connect(lambda _: self.field_changed.emit())
        pages_box.addWidget(self.spn_max_pages)

        lbl_pages_hint = QLabel("Search result depth per query")
        lbl_pages_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        pages_box.addWidget(lbl_pages_hint)
        grid.addLayout(pages_box, 0, 1)

        # 3. Switch After N Applications
        switch_box = QVBoxLayout()
        switch_box.setSpacing(4)
        lbl_switch = QLabel("Keyword Switch Limit")
        lbl_switch.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        switch_box.addWidget(lbl_switch)

        self.spn_switch_number = QSpinBox()
        self.spn_switch_number.setRange(5, 200)
        self.spn_switch_number.setValue(30)
        self.spn_switch_number.setSuffix(" apps")
        self.spn_switch_number.setFixedHeight(34)
        self.spn_switch_number.valueChanged.connect(lambda _: self.field_changed.emit())
        switch_box.addWidget(self.spn_switch_number)

        lbl_switch_hint = QLabel("Rotate keyword after N successful applications")
        lbl_switch_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        switch_box.addWidget(lbl_switch_hint)
        grid.addLayout(switch_box, 1, 0)

        # 4. Consecutive Skips Limit
        skips_box = QVBoxLayout()
        skips_box.setSpacing(4)
        lbl_skips = QLabel("Consecutive Skip Limit")
        lbl_skips.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        skips_box.addWidget(lbl_skips)

        self.spn_skips_limit = QSpinBox()
        self.spn_skips_limit.setRange(3, 50)
        self.spn_skips_limit.setValue(10)
        self.spn_skips_limit.setSuffix(" skips")
        self.spn_skips_limit.setFixedHeight(34)
        self.spn_skips_limit.valueChanged.connect(lambda _: self.field_changed.emit())
        skips_box.addWidget(self.spn_skips_limit)

        lbl_skips_hint = QLabel("Rotate keyword if N jobs in a row are skipped")
        lbl_skips_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        skips_box.addWidget(lbl_skips_hint)
        grid.addLayout(skips_box, 1, 1)

        layout.addLayout(grid)

        # 5. Easy Apply Toggle Row
        easy_row = QHBoxLayout()
        easy_row.setSpacing(10)

        self.chk_easy_apply = QCheckBox("Easy Apply jobs only")
        self.chk_easy_apply.setToolTip("When checked, restricts applications to in-platform Easy Apply forms")
        self.chk_easy_apply.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
            }}
        """)
        self.chk_easy_apply.toggled.connect(lambda _: self.field_changed.emit())
        easy_row.addWidget(self.chk_easy_apply)

        lbl_easy_hint = QLabel("— uncheck to include company portal / external career site jobs")
        lbl_easy_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        easy_row.addWidget(lbl_easy_hint)
        easy_row.addStretch()

        layout.addLayout(easy_row)
