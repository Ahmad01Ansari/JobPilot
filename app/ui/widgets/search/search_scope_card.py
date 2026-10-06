"""Unified Search Scope card combining platform selection, location, and experience."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchScopeCard(QFrame):
    """Clean, single-surface card combining Platform selection, Location suggestions, and Experience."""

    field_changed = Signal()
    platform_changed = Signal(str)
    sync_all_toggled = Signal(bool)

    QUICK_LOCATIONS = ["Bangalore", "Hyderabad", "Delhi NCR", "Pune", "Mumbai", "Remote", "India"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchScopeCard")
        self.setStyleSheet(f"""
            #searchScopeCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']}40;
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)

        # 1. Platform Row
        plat_row = QHBoxLayout()
        plat_row.setSpacing(12)

        lbl_plat = QLabel("Platform:")
        lbl_plat.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        plat_row.addWidget(lbl_plat)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"])
        self.cmb_platform.setMinimumWidth(130)
        self.cmb_platform.currentTextChanged.connect(self._on_platform_changed)
        plat_row.addWidget(self.cmb_platform)

        # Subtle Platform Readiness Dots (No ugly brown boxes!)
        lbl_li = QLabel("LinkedIn ● Ready")
        lbl_li.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px; font-weight: 600;")
        plat_row.addWidget(lbl_li)

        lbl_nk = QLabel("Naukri ● Ready")
        lbl_nk.setStyleSheet(f"color: {COLORS['success']}; font-size: 11px; font-weight: 600;")
        plat_row.addWidget(lbl_nk)

        plat_row.addStretch()

        self.chk_apply_all_platforms = QCheckBox("Apply strategy across all platforms")
        self.chk_apply_all_platforms.setToolTip(
            "When checked, saving updates search terms, locations, filters, and skip rules across LinkedIn, Naukri, and Indeed."
        )
        self.chk_apply_all_platforms.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text_muted']};
                font-size: 12px;
                spacing: 6px;
            }}
            QCheckBox:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.chk_apply_all_platforms.toggled.connect(self._on_sync_all_toggled)
        plat_row.addWidget(self.chk_apply_all_platforms)

        layout.addLayout(plat_row)

        # 2. Location & Experience Grid (2 Columns)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        # Column 1: Location
        lbl_loc = QLabel("Target Location")
        lbl_loc.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        grid.addWidget(lbl_loc, 0, 0)

        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("e.g. Bangalore, India or Remote")
        self.txt_location.setFixedHeight(34)
        self.txt_location.textChanged.connect(lambda _: self.field_changed.emit())
        grid.addWidget(self.txt_location, 1, 0)

        # Column 2: Experience
        lbl_exp = QLabel("Experience")
        lbl_exp.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        grid.addWidget(lbl_exp, 0, 1)

        exp_box = QHBoxLayout()
        exp_box.setSpacing(8)

        lbl_min = QLabel("0 —")
        lbl_min.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; font-weight: 500;")
        exp_box.addWidget(lbl_min)

        self.spn_experience = QSpinBox()
        self.spn_experience.setRange(-1, 30)
        self.spn_experience.setSpecialValueText("All (-1)")
        self.spn_experience.setSuffix(" yrs")
        self.spn_experience.setValue(5)
        self.spn_experience.setFixedHeight(34)
        self.spn_experience.setMinimumWidth(110)
        self.spn_experience.valueChanged.connect(lambda _: self.field_changed.emit())
        exp_box.addWidget(self.spn_experience)

        lbl_exp_hint = QLabel("(Max required)")
        lbl_exp_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        exp_box.addWidget(lbl_exp_hint)
        exp_box.addStretch()

        grid.addLayout(exp_box, 1, 1)
        layout.addLayout(grid)

        # Location suggestions row
        sugg_box = QHBoxLayout()
        sugg_box.setSpacing(6)
        lbl_sugg = QLabel("Suggestions:")
        lbl_sugg.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        sugg_box.addWidget(lbl_sugg)

        for loc in self.QUICK_LOCATIONS:
            btn = QPushButton(loc)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']}50;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['border_light']};
                    color: {COLORS['text']};
                    background-color: {COLORS['surface_hover']};
                }}
            """)
            btn.clicked.connect(lambda _, l=loc: self._apply_location(l))
            sugg_box.addWidget(btn)

        sugg_box.addStretch()
        layout.addLayout(sugg_box)

    def _apply_location(self, loc: str) -> None:
        self.txt_location.setText(loc)
        self.field_changed.emit()

    def _on_platform_changed(self, name: str) -> None:
        self.platform_changed.emit(name.strip().lower())

    def _on_sync_all_toggled(self, checked: bool) -> None:
        self.sync_all_toggled.emit(checked)
        self.field_changed.emit()


# Backward-compatible aliases
SearchPlatformsCard = SearchScopeCard
SearchLocationCard = SearchScopeCard
