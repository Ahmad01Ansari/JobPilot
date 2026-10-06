"""Full Automation Run History modal dialog with filtering and search."""

from datetime import datetime
from typing import Any, Callable, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.models.automation_run import AutomationRun
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge

from pathlib import Path
_ICONS_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "icons"
_CHEVRON_DOWN_PATH = str(_ICONS_DIR / "chevron_down.svg")
_CHEVRON_DOWN_HOVER_PATH = str(_ICONS_DIR / "chevron_down_hover.svg")


class AllRunHistoryDialog(QDialog):
    """Full-screen modal displaying all historical automation sessions with search & filter."""

    inspect_run = Signal(object)  # AutomationRun

    def __init__(
        self,
        runs: List[Any],
        on_inspect: Optional[Callable[[Any], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Automation Execution History")
        self.resize(960, 620)
        self.setMinimumSize(800, 500)
        self._all_runs: List[Any] = runs or []
        self._filtered_runs: List[Any] = []
        self._on_inspect_cb = on_inspect

        self._setup_ui()
        self._apply_filters()

    def _setup_ui(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tokens.get('background', '#0F1117')};
                color: {tokens.get('text', '#F0F6FC')};
            }}
            QLabel {{
                color: {tokens.get('text', '#F0F6FC')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # 1. Header Row
        hdr_row = QHBoxLayout()
        hdr_left = QVBoxLayout()
        hdr_left.setSpacing(2)

        lbl_title = QLabel("Automation Execution History")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {tokens.get('text', '#F0F6FC')};")
        hdr_left.addWidget(lbl_title)

        lbl_sub = QLabel("Complete persistent audit trail of all automated job search and application runs.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {tokens.get('text_muted', '#8B949E')};")
        hdr_left.addWidget(lbl_sub)
        hdr_row.addLayout(hdr_left)
        hdr_row.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {tokens.get('text_muted', '#8B949E')};
                border: none;
                font-size: 14px;
                font-weight: 700;
                border-radius: 14px;
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                color: {tokens.get('text', '#F0F6FC')};
            }}
        """)
        btn_close.clicked.connect(self.close)
        hdr_row.addWidget(btn_close)
        layout.addLayout(hdr_row)

        # 2. Search & Filter Bar
        filter_bar = QFrame()
        filter_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        fb_layout = QHBoxLayout(filter_bar)
        fb_layout.setContentsMargins(10, 8, 10, 8)
        fb_layout.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Search by keyword, run ID, or notes...")
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {tokens.get('primary', '#FF5F15')};
            }}
        """)
        self.txt_search.textChanged.connect(self._apply_filters)
        fb_layout.addWidget(self.txt_search, 1)

        # Platform Filter
        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["All Platforms", "LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"])
        self._style_combo(self.cmb_platform)
        self.cmb_platform.currentIndexChanged.connect(self._apply_filters)
        fb_layout.addWidget(self.cmb_platform)

        # Status Filter
        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["All Statuses", "COMPLETED", "STOPPED", "FAILED", "RUNNING"])
        self._style_combo(self.cmb_status)
        self.cmb_status.currentIndexChanged.connect(self._apply_filters)
        fb_layout.addWidget(self.cmb_status)

        # Reset button
        btn_reset = QPushButton("Reset")
        btn_reset.setCursor(Qt.PointingHandCursor)
        btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text_muted', '#8B949E')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {tokens.get('text', '#F0F6FC')};
                border-color: {tokens.get('border_light', '#333A46')};
            }}
        """)
        btn_reset.clicked.connect(self._reset_filters)
        fb_layout.addWidget(btn_reset)

        self.lbl_count = QLabel("Showing 0 runs")
        self.lbl_count.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; font-weight: 600;")
        fb_layout.addWidget(self.lbl_count)

        layout.addWidget(filter_bar)

        # 3. Data Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Platform",
            "Started Time",
            "Duration",
            "Discovered",
            "Submitted",
            "Errors",
            "Status",
            "Action",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 100)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 90)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 85)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 85)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 75)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 125)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 105)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {tokens.get('surface', '#161B22')};
                alternate-background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
                gridline-color: transparent;
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border-bottom: 1px solid {tokens.get('border', '#262C36')}40;
            }}
            QHeaderView::section {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text_muted', '#8B949E')};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 8px;
                border: none;
                border-bottom: 1px solid {tokens.get('border', '#262C36')};
            }}
        """)
        layout.addWidget(self.table, 1)

    def _style_combo(self, combo: QComboBox) -> None:
        tokens = COLORS
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 26px 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border-color: {tokens.get('border_light', '#333A46')};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: url({_CHEVRON_DOWN_PATH});
                width: 8px;
                height: 5px;
            }}
            QComboBox::down-arrow:hover {{
                image: url({_CHEVRON_DOWN_HOVER_PATH});
            }}
            QComboBox QAbstractItemView {{
                background-color: {tokens.get('surface', '#161B22')};
                color: {tokens.get('text', '#F0F6FC')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
                padding: 4px;
                selection-background-color: {tokens.get('primary', '#FF5F15')};
                selection-color: #FFFFFF;
                outline: none;
            }}
        """)

    def _reset_filters(self) -> None:
        self.txt_search.clear()
        self.cmb_platform.setCurrentIndex(0)
        self.cmb_status.setCurrentIndex(0)
        self._apply_filters()

    def _apply_filters(self) -> None:
        query = self.txt_search.text().strip().lower()
        sel_platform = self.cmb_platform.currentText().strip().lower()
        sel_status = self.cmb_status.currentText().strip().upper()

        filtered = []
        for run in self._all_runs:
            p = getattr(run, "platform", "").lower()
            st = getattr(run, "status", "").upper()
            rid = getattr(run, "run_id", "").lower()
            reason = getattr(run, "stop_reason", "") or ""

            if sel_platform != "all platforms" and sel_platform != p:
                continue

            if sel_status != "ALL STATUSES" and sel_status != st:
                continue

            if query:
                if query not in p and query not in rid and query not in reason.lower():
                    continue

            filtered.append(run)

        self._filtered_runs = filtered
        self.lbl_count.setText(f"Showing {len(filtered)} of {len(self._all_runs)} runs")
        self._populate_table()

    def _populate_table(self) -> None:
        self.table.setRowCount(len(self._filtered_runs))
        tokens = COLORS

        for row_idx, run in enumerate(self._filtered_runs):
            # 0. Platform
            p_name = getattr(run, "platform", "Unknown").capitalize()
            it_plat = QTableWidgetItem(f"  {p_name}")
            it_plat.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 0, it_plat)

            # 1. Started
            st_time = getattr(run, "started_at", None)
            st_str = st_time.strftime("%b %d, %Y  %H:%M:%S") if st_time else "—"
            it_time = QTableWidgetItem(st_str)
            it_time.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 1, it_time)

            # 2. Duration
            fin_time = getattr(run, "finished_at", None)
            if st_time and fin_time:
                secs = max(0, int((fin_time - st_time).total_seconds()))
                dur_str = f"{secs // 60:02d}m {secs % 60:02d}s"
            else:
                dur_str = "—"
            it_dur = QTableWidgetItem(dur_str)
            it_dur.setTextAlignment(Qt.AlignCenter)
            it_dur.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 2, it_dur)

            # 3. Discovered
            disc = getattr(run, "jobs_discovered", 0)
            it_disc = QTableWidgetItem(str(disc))
            it_disc.setTextAlignment(Qt.AlignCenter)
            it_disc.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 3, it_disc)

            # 4. Submitted
            appld = getattr(run, "applications_submitted", 0)
            it_appld = QTableWidgetItem(str(appld))
            it_appld.setTextAlignment(Qt.AlignCenter)
            it_appld.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 4, it_appld)

            # 5. Errors
            errs = getattr(run, "errors_count", 0)
            it_errs = QTableWidgetItem(str(errs))
            it_errs.setTextAlignment(Qt.AlignCenter)
            it_errs.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row_idx, 5, it_errs)

            # 6. Status Badge
            st = getattr(run, "status", "UNKNOWN").upper()
            v_type = "success" if st == "COMPLETED" else ("danger" if st in ("FAILED", "ERROR") else "neutral")
            badge = StatusBadge(st, status_type=v_type, width=96, height=22)
            c_widget = QWidget()
            c_widget.setStyleSheet("background: transparent; border: none;")
            c_lay = QHBoxLayout(c_widget)
            c_lay.setContentsMargins(0, 0, 0, 0)
            c_lay.setAlignment(Qt.AlignCenter)
            c_lay.addWidget(badge)
            self.table.setCellWidget(row_idx, 6, c_widget)

            # 7. Action Button
            btn_inspect = QPushButton("Inspect ↗")
            btn_inspect.setFixedHeight(24)
            btn_inspect.setCursor(Qt.PointingHandCursor)
            btn_inspect.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tokens.get('surface_alt', '#1C2128')};
                    color: {tokens.get('text', '#F0F6FC')};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 10px;
                    border-radius: 4px;
                    border: 1px solid {tokens.get('border', '#262C36')};
                }}
                QPushButton:hover {{
                    border-color: {tokens.get('primary', '#FF5F15')};
                    color: {tokens.get('primary', '#FF5F15')};
                    background-color: {tokens.get('surface_hover', '#262C36')};
                }}
            """)
            btn_inspect.clicked.connect(lambda _, r=run: self._on_inspect_clicked(r))
            w_btn = QWidget()
            w_btn.setStyleSheet("background: transparent; border: none;")
            w_lay = QHBoxLayout(w_btn)
            w_lay.setContentsMargins(0, 0, 0, 0)
            w_lay.setAlignment(Qt.AlignCenter)
            w_lay.addWidget(btn_inspect)
            self.table.setCellWidget(row_idx, 7, w_btn)

    def _on_inspect_clicked(self, run: Any) -> None:
        self.inspect_run.emit(run)
        if self._on_inspect_cb:
            self._on_inspect_cb(run)
        self.accept()
