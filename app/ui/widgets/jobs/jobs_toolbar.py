"""Toolbar component for Jobs page with search, filters, location, density toggle, column selector, and active chips."""

from typing import Dict, Optional
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class JobsToolbar(QWidget):
    """Toolbar providing search, platform/status/method/location filters, density toggle, columns toggle, and filter chips."""

    filters_changed = Signal()
    column_visibility_changed = Signal(int, bool)  # col_idx, visible
    density_changed = Signal(str)                  # 'comfortable' | 'compact'
    clear_all_requested = Signal()
    calculate_all_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(200)
        self._debounce_timer.timeout.connect(self.filters_changed.emit)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # 1. Main Controls Bar (Card)
        self.card = QFrame()
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        controls_layout = QHBoxLayout(self.card)
        controls_layout.setContentsMargins(12, 10, 12, 10)
        controls_layout.setSpacing(10)

        # Global Search
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Search jobs, companies, keywords...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setStyleSheet(self._input_style())
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        controls_layout.addWidget(self.txt_search, 2)

        # Location Filter Input
        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("📍  Location...")
        self.txt_location.setClearButtonEnabled(True)
        self.txt_location.setMaximumWidth(150)
        self.txt_location.setStyleSheet(self._input_style())
        self.txt_location.textChanged.connect(self._on_search_text_changed)
        controls_layout.addWidget(self.txt_location, 1)

        # Platform Filter
        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems([
            "All Platforms",
            "LinkedIn",
            "Naukri",
            "Indeed",
            "Foundit",
            "Glassdoor",
            "Manual",
            "Referral",
        ])
        self.cmb_platform.setStyleSheet(self._combo_style())
        self.cmb_platform.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.cmb_platform)

        # Status Filter
        self.cmb_status = QComboBox()
        self.cmb_status.addItems([
            "All Statuses",
            "Not Applied",
            "Applying",
            "Submitted",
            "Skipped",
            "Failed",
            "External",
            "Already Applied",
            "Junk",
        ])
        self.cmb_status.setStyleSheet(self._combo_style())
        self.cmb_status.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.cmb_status)

        # Method Filter
        self.cmb_method = QComboBox()
        self.cmb_method.addItems([
            "All Methods",
            "Easy Apply",
            "Company Portal",
        ])
        self.cmb_method.setStyleSheet(self._combo_style())
        self.cmb_method.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.cmb_method)

        # Match Score Filter
        self.cmb_match_score = QComboBox()
        self.cmb_match_score.addItems([
            "All Scores",
            "≤ 10%",
            "≤ 20%",
            "≤ 30%",
            "≤ 40%",
            "≤ 50%",
            "≥ 50%",
            "≥ 60%",
            "≥ 70%",
            "≥ 80%",
            "Not Evaluated",
        ])
        self.cmb_match_score.setStyleSheet(self._combo_style())
        self.cmb_match_score.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.cmb_match_score)

        # Calculate All Match Scores Button
        self.btn_calculate_all = QPushButton("⚡ Calculate All")
        self.btn_calculate_all.setCursor(Qt.PointingHandCursor)
        self.btn_calculate_all.setToolTip("Calculate match scores for all jobs in the current view")
        self.btn_calculate_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        self.btn_calculate_all.clicked.connect(self.calculate_all_requested.emit)
        controls_layout.addWidget(self.btn_calculate_all)

        # Density Toggle Button
        self.btn_density = QPushButton("Density ▾")
        self.btn_density.setStyleSheet(self._btn_menu_style())
        self._setup_density_menu()
        controls_layout.addWidget(self.btn_density)

        # Columns Visibility Menu
        self.btn_columns = QPushButton("Columns ▾")
        self.btn_columns.setStyleSheet(self._btn_menu_style())
        self._setup_columns_menu()
        controls_layout.addWidget(self.btn_columns)

        main_layout.addWidget(self.card)

        # 2. Active Filter Chips Row
        self.chips_widget = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_widget)
        self.chips_layout.setContentsMargins(4, 2, 4, 2)
        self.chips_layout.setSpacing(6)
        self.chips_widget.setVisible(False)
        main_layout.addWidget(self.chips_widget)

    def _input_style(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['accent']};
            }}
        """

    def _combo_style(self) -> str:
        return f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 500;
                min-width: 105px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['border_light']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['surface_hover']};
                selection-color: {COLORS['text']};
                padding: 4px;
            }}
        """

    def _btn_menu_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """

    def _setup_density_menu(self) -> None:
        self.density_menu = QMenu(self)
        self.density_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        act_comfortable = self.density_menu.addAction("Comfortable (Default)")
        act_compact = self.density_menu.addAction("Compact")

        act_comfortable.triggered.connect(lambda: self.density_changed.emit("comfortable"))
        act_compact.triggered.connect(lambda: self.density_changed.emit("compact"))

        self.btn_density.setMenu(self.density_menu)

    def _setup_columns_menu(self) -> None:
        self.columns_menu = QMenu(self)
        self.columns_menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px 6px 24px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.column_actions = {}
        # Matches JobsTable.COLUMNS: 0: Checkbox, 1: Title, 2: Company, 3: Platform, 4: Location, 5: Exp, 6: Method, 7: Match, 8: Status, 9: Discovered
        columns = [
            (1, "Job Title", True, False),
            (2, "Company", True, True),
            (3, "Platform", True, True),
            (4, "Location", True, True),
            (5, "Experience", True, True),
            (6, "Method", True, True),
            (7, "Match Score", True, True),
            (8, "Status", True, True),
            (9, "Discovered", False, True),
        ]
        for col_idx, label, is_checked, allow_toggle in columns:
            action = self.columns_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(is_checked)
            if not allow_toggle:
                action.setEnabled(False)
            else:
                action.triggered.connect(
                    lambda chk, idx=col_idx: self.column_visibility_changed.emit(idx, chk)
                )
            self.column_actions[col_idx] = action

        self.btn_columns.setMenu(self.columns_menu)

    def _on_search_text_changed(self, text: str) -> None:
        self.update_chips()
        self._debounce_timer.start()

    def _on_filter_changed(self) -> None:
        self.update_chips()
        self.filters_changed.emit()

    def update_chips(self) -> None:
        """Refreshes the active filter chips display."""
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        active_chips = []

        search_val = self.txt_search.text().strip()
        if search_val:
            active_chips.append(("Search", search_val, lambda: self.txt_search.clear()))

        loc_val = self.txt_location.text().strip()
        if loc_val:
            active_chips.append(("Location", loc_val, lambda: self.txt_location.clear()))

        plat_val = self.cmb_platform.currentText()
        if plat_val != "All Platforms":
            active_chips.append(("Platform", plat_val, lambda: self.cmb_platform.setCurrentIndex(0)))

        stat_val = self.cmb_status.currentText()
        if stat_val != "All Statuses":
            active_chips.append(("Status", stat_val, lambda: self.cmb_status.setCurrentIndex(0)))

        meth_val = self.cmb_method.currentText()
        if meth_val != "All Methods":
            active_chips.append(("Method", meth_val, lambda: self.cmb_method.setCurrentIndex(0)))

        match_val = self.cmb_match_score.currentText()
        if match_val != "All Scores":
            active_chips.append(("Match Score", match_val, lambda: self.cmb_match_score.setCurrentIndex(0)))

        if not active_chips:
            self.chips_widget.setVisible(False)
            return

        self.chips_widget.setVisible(True)

        lbl_prefix = QLabel("Active filters:")
        lbl_prefix.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;")
        self.chips_layout.addWidget(lbl_prefix)

        for category, label_text, clear_fn in active_chips:
            chip = QFrame()
            chip.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    padding: 2px 6px;
                }}
            """)
            c_layout = QHBoxLayout(chip)
            c_layout.setContentsMargins(6, 1, 6, 1)
            c_layout.setSpacing(4)

            text_lbl = QLabel(f"{category}: <b>{label_text}</b>")
            text_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px;")
            c_layout.addWidget(text_lbl)

            btn_x = QPushButton("✕")
            btn_x.setCursor(Qt.PointingHandCursor)
            btn_x.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 0 2px;
                }}
                QPushButton:hover {{
                    color: {COLORS['danger']};
                }}
            """)
            btn_x.clicked.connect(clear_fn)
            c_layout.addWidget(btn_x)

            self.chips_layout.addWidget(chip)

        # Clear All button
        btn_clear_all = QPushButton("Clear all")
        btn_clear_all.setCursor(Qt.PointingHandCursor)
        btn_clear_all.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['accent']};
                border: none;
                font-size: 11px;
                font-weight: 600;
                padding: 2px 6px;
                text-decoration: underline;
            }}
            QPushButton:hover {{
                color: {COLORS['primary_hover']};
            }}
        """)
        btn_clear_all.clicked.connect(self.clear_all_filters)
        self.chips_layout.addWidget(btn_clear_all)
        self.chips_layout.addStretch()

    def clear_all_filters(self) -> None:
        """Resets all filters and search input."""
        self.txt_search.blockSignals(True)
        self.txt_search.clear()
        self.txt_search.blockSignals(False)

        self.txt_location.blockSignals(True)
        self.txt_location.clear()
        self.txt_location.blockSignals(False)

        self.cmb_platform.blockSignals(True)
        self.cmb_platform.setCurrentIndex(0)
        self.cmb_platform.blockSignals(False)

        self.cmb_status.blockSignals(True)
        self.cmb_status.setCurrentIndex(0)
        self.cmb_status.blockSignals(False)

        self.cmb_method.blockSignals(True)
        self.cmb_method.setCurrentIndex(0)
        self.cmb_method.blockSignals(False)

        self.cmb_match_score.blockSignals(True)
        self.cmb_match_score.setCurrentIndex(0)
        self.cmb_match_score.blockSignals(False)

        self.update_chips()
        self.clear_all_requested.emit()
        self.filters_changed.emit()

    def get_filters(self) -> Dict[str, Optional[str]]:
        """Returns the current filter values formatted for JobFilter."""
        search = self.txt_search.text().strip() or None
        location = self.txt_location.text().strip() or None

        plat = self.cmb_platform.currentText().strip().lower()
        platform = None if plat in ["all platforms", "all", ""] else plat

        stat = self.cmb_status.currentText().strip().upper().replace(" ", "_")
        status = None if stat in ["ALL_STATUSES", "ALL", ""] else stat

        meth = self.cmb_method.currentText().strip().upper().replace(" ", "_")
        method = None if meth in ["ALL_METHODS", "ALL", ""] else meth

        # Parse match score filter text into structured values
        match_score_filter = self.cmb_match_score.currentText().strip()
        match_score_max = None
        match_score_min = None
        match_not_evaluated = False
        if match_score_filter == "Not Evaluated":
            match_not_evaluated = True
        elif match_score_filter.startswith("≤"):
            match_score_max = int(match_score_filter.replace("≤", "").replace("%", "").strip())
        elif match_score_filter.startswith("≥"):
            match_score_min = int(match_score_filter.replace("≥", "").replace("%", "").strip())

        return {
            "search": search,
            "location": location,
            "platform": platform,
            "status": status,
            "method": method,
            "match_score_max": match_score_max,
            "match_score_min": match_score_min,
            "match_not_evaluated": match_not_evaluated,
        }

    def set_method(self, method: Optional[str]) -> None:
        """Programmatically sets the method dropdown (e.g. from category tabs)."""
        self.cmb_method.blockSignals(True)
        if method == "EASY_APPLY":
            self.cmb_method.setCurrentText("Easy Apply")
        elif method == "COMPANY_PORTAL":
            self.cmb_method.setCurrentText("Company Portal")
        else:
            self.cmb_method.setCurrentIndex(0)
        self.cmb_method.blockSignals(False)
        self.update_chips()
