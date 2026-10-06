"""Global analytics filter toolbar and active filter chips component."""

from datetime import datetime
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.analytics_service import AnalyticsFilter
from app.ui.theme import COLORS
from app.utils_time import format_local_time


class AnalyticsFilterBar(QFrame):
    """Global filter toolbar with date presets, platform/method/status selectors, and active chips."""

    filter_changed = Signal(object)  # Emits AnalyticsFilter
    refresh_requested = Signal()
    export_requested = Signal()

    DATE_PRESETS = ["TODAY", "7D", "30D", "90D", "6M", "1Y", "ALL"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_filter = AnalyticsFilter(date_preset="30D")
        self._preset_buttons: dict[str, QPushButton] = {}
        self._last_refresh_time = datetime.now()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AnalyticsFilterBar {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 10, 14, 10)
        main_layout.setSpacing(10)

        # Row 1: Controls Toolbar
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        # A. Date Presets Segmented Bar
        preset_bar = QFrame()
        preset_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        preset_layout = QHBoxLayout(preset_bar)
        preset_layout.setContentsMargins(2, 2, 2, 2)
        preset_layout.setSpacing(2)

        for p in self.DATE_PRESETS:
            label = "6 Months" if p == "6M" else ("1 Year" if p == "1Y" else ("All Time" if p == "ALL" else (p if p == "TODAY" else f"Last {p}")))
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(p == self.current_filter.date_preset)
            btn.setFixedHeight(26)
            btn.setStyleSheet(self._preset_button_style(p == self.current_filter.date_preset))
            btn.clicked.connect(lambda checked=False, val=p: self._on_preset_clicked(val))
            preset_layout.addWidget(btn)
            self._preset_buttons[p] = btn

        top_row.addWidget(preset_bar)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        top_row.addWidget(sep)

        # B. Platform Dropdown
        self.combo_platform = QComboBox()
        self.combo_platform.addItems([
            "All Platforms",
            "LinkedIn",
            "Naukri",
            "Indeed",
            "Foundit",
            "Glassdoor",
            "Manual",
        ])
        self.combo_platform.setFixedHeight(28)
        self.combo_platform.setStyleSheet(self._combo_style())
        self.combo_platform.currentIndexChanged.connect(self._on_combo_changed)
        top_row.addWidget(self.combo_platform)

        # C. Application Method Dropdown
        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "All Methods",
            "Easy Apply",
            "Direct Apply",
            "Questionnaire",
            "Manual",
        ])
        self.combo_method.setFixedHeight(28)
        self.combo_method.setStyleSheet(self._combo_style())
        self.combo_method.currentIndexChanged.connect(self._on_combo_changed)
        top_row.addWidget(self.combo_method)

        # D. Status Dropdown
        self.combo_status = QComboBox()
        self.combo_status.addItems([
            "All Statuses",
            "Submitted",
            "Under Review",
            "Shortlisted",
            "Interview",
            "Offer",
            "Rejected",
            "Withdrawn",
        ])
        self.combo_status.setFixedHeight(28)
        self.combo_status.setStyleSheet(self._combo_style())
        self.combo_status.currentIndexChanged.connect(self._on_combo_changed)
        top_row.addWidget(self.combo_status)

        top_row.addStretch()

        # E. Export CSV Button
        self.btn_export = QPushButton("📥 Export CSV")
        self.btn_export.setFixedHeight(28)
        self.btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_export.clicked.connect(self.export_requested.emit)
        top_row.addWidget(self.btn_export)

        # F. Refresh Control
        refresh_box = QHBoxLayout()
        refresh_box.setSpacing(6)

        self.lbl_updated = QLabel("Updated just now")
        self.lbl_updated.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        refresh_box.addWidget(self.lbl_updated)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setFixedHeight(28)
        self.btn_refresh.setToolTip("Refresh analytics data")
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['surface_elevated']};
            }}
        """)
        self.btn_refresh.clicked.connect(self._on_refresh_clicked)
        refresh_box.addWidget(self.btn_refresh)
        top_row.addLayout(refresh_box)

        main_layout.addLayout(top_row)

        # Row 2: Active Filter Chips
        self.chips_container = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)
        main_layout.addWidget(self.chips_container)

        self._render_chips()

    def _preset_button_style(self, is_active: bool) -> str:
        if is_active:
            return f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: #FFFFFF;
                    border: none;
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 500;
                min-width: 110px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['border_light']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['primary']};
                selection-color: white;
                color: {COLORS['text']};
                outline: none;
                padding: 4px;
            }}
        """

    def _on_preset_clicked(self, preset: str) -> None:
        self.current_filter.date_preset = preset
        for p, btn in self._preset_buttons.items():
            active = (p == preset)
            btn.setChecked(active)
            btn.setStyleSheet(self._preset_button_style(active))

        self._render_chips()
        self.filter_changed.emit(self.current_filter)

    def _on_combo_changed(self) -> None:
        plat = self.combo_platform.currentText()
        self.current_filter.platform = None if plat == "All Platforms" else plat.lower()

        meth = self.combo_method.currentText()
        if meth == "All Methods":
            self.current_filter.application_method = None
        else:
            self.current_filter.application_method = meth.upper().replace(" ", "_")

        st = self.combo_status.currentText()
        if st == "All Statuses":
            self.current_filter.status = None
        else:
            self.current_filter.status = st.upper().replace(" ", "_")

        self._render_chips()
        self.filter_changed.emit(self.current_filter)

    def _on_refresh_clicked(self) -> None:
        self._last_refresh_time = datetime.now()
        self.lbl_updated.setText(f"Updated {format_local_time(self._last_refresh_time, '%H:%M')}")
        self.refresh_requested.emit()

    def set_platform_filter(self, platform_key: str) -> None:
        """Sets the platform filter programmatically from drill-down."""
        target = platform_key.title()
        idx = self.combo_platform.findText(target)
        if idx >= 0:
            self.combo_platform.setCurrentIndex(idx)
        elif platform_key.lower() == "all":
            self.combo_platform.setCurrentIndex(0)

    def set_status_filter(self, status_name: str) -> None:
        """Sets the status filter programmatically from drill-down."""
        target = status_name.replace("_", " ").title()
        idx = self.combo_status.findText(target)
        if idx >= 0:
            self.combo_status.setCurrentIndex(idx)

    def _render_chips(self) -> None:
        """Renders removable chips for currently active filters."""
        # Clear existing chips
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        chips_added = 0

        # Date chip
        date_label = f"Period: {self.current_filter.date_preset}"
        self._add_chip(date_label, on_remove=lambda: self._on_preset_clicked("30D"))
        chips_added += 1

        # Platform chip
        if self.current_filter.platform:
            self._add_chip(
                f"Platform: {self.current_filter.platform.title()}",
                on_remove=lambda: self.combo_platform.setCurrentIndex(0),
            )
            chips_added += 1

        # Method chip
        if self.current_filter.application_method:
            self._add_chip(
                f"Method: {self.current_filter.application_method.replace('_', ' ').title()}",
                on_remove=lambda: self.combo_method.setCurrentIndex(0),
            )
            chips_added += 1

        # Status chip
        if self.current_filter.status:
            self._add_chip(
                f"Status: {self.current_filter.status.replace('_', ' ').title()}",
                on_remove=lambda: self.combo_status.setCurrentIndex(0),
            )
            chips_added += 1

        # Clear All button if any non-default filter is set
        has_non_default = (
            self.current_filter.date_preset != "30D"
            or self.current_filter.platform is not None
            or self.current_filter.application_method is not None
            or self.current_filter.status is not None
        )

        if has_non_default:
            btn_clear = QPushButton("Reset Filters")
            btn_clear.setFixedHeight(22)
            btn_clear.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    font-size: 11px;
                    text-decoration: underline;
                    padding: 0 4px;
                }}
                QPushButton:hover {{
                    color: {COLORS['primary']};
                }}
            """)
            btn_clear.clicked.connect(self._reset_all_filters)
            self.chips_layout.addWidget(btn_clear)

        self.chips_layout.addStretch()

    def _add_chip(self, text: str, on_remove: Any) -> None:
        chip = QFrame()
        chip.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
            }}
        """)
        c_layout = QHBoxLayout(chip)
        c_layout.setContentsMargins(6, 2, 6, 2)
        c_layout.setSpacing(4)

        lbl = QLabel(text)
        lbl.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text']}; border: none; background: transparent;")
        c_layout.addWidget(lbl)

        btn_x = QPushButton("×")
        btn_x.setFixedSize(14, 14)
        btn_x.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 12px;
                font-weight: 700;
                line-height: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['primary']};
            }}
        """)
        btn_x.clicked.connect(on_remove)
        c_layout.addWidget(btn_x)

        self.chips_layout.addWidget(chip)

    def _reset_all_filters(self) -> None:
        self.combo_platform.setCurrentIndex(0)
        self.combo_method.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self._on_preset_clicked("30D")
