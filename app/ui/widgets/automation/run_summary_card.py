"""Compact Run History component for Automation Control Center.

Displays recent historical execution sessions from AutomationManager.get_recent_runs()
with interactive click-to-inspect integration for the RunDetailsDrawer.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.db.models.automation_run import AutomationRun
from app.ui.theme import COLORS
from app.ui.widgets.automation.state import AutomationUIState
from app.ui.widgets.status_badge import StatusBadge


class RunHistoryRow(QFrame):
    """Interactive row displaying a single historical run record."""

    clicked = Signal(object)  # AutomationRun

    def __init__(self, run: AutomationRun, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.run = run
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('border_light', '#333A46')};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(8)

        # Platform
        p_name = getattr(self.run, "platform", "Unknown")
        self.lbl_platform = QLabel(p_name.capitalize())
        self.lbl_platform.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(self.lbl_platform)

        # Start Time
        st_time = getattr(self.run, "started_at", None)
        st_str = st_time.strftime("%b %d, %H:%M") if st_time else "—"
        self.lbl_time = QLabel(st_str)
        self.lbl_time.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.lbl_time)

        # Duration
        fin_time = getattr(self.run, "finished_at", None)
        if st_time and fin_time:
            secs = max(0, int((fin_time - st_time).total_seconds()))
            dur_str = f"{secs // 60:02d}m {secs % 60:02d}s"
        else:
            dur_str = "—"
        self.lbl_duration = QLabel(dur_str)
        self.lbl_duration.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; font-family: monospace; background: transparent; border: none;")
        layout.addWidget(self.lbl_duration)

        layout.addStretch()

        # Counts
        disc = getattr(self.run, "jobs_discovered", 0)
        appld = getattr(self.run, "applications_submitted", 0)
        self.lbl_counts = QLabel(f"{disc} disc • {appld} applied")
        self.lbl_counts.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.lbl_counts)

        # Status Badge
        st = getattr(self.run, "status", "UNKNOWN").upper()
        v_type = "success" if st == "COMPLETED" else ("danger" if st in ("FAILED", "ERROR") else "neutral")
        self.badge = StatusBadge(st, status_type=v_type, width=92, height=22)
        layout.addWidget(self.badge)

        # Action Button
        self.btn_details = QPushButton("Details ↗")
        self.btn_details.setFixedHeight(22)
        self.btn_details.setCursor(Qt.PointingHandCursor)
        self.btn_details.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface', '#161B22')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
                border-radius: 5px;
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('primary', '#FF5F15')};
                color: {tokens.get('primary', '#FF5F15')};
            }}
        """)
        self.btn_details.clicked.connect(lambda: self.clicked.emit(self.run))
        layout.addWidget(self.btn_details)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
            }}
            QFrame:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('border_light', '#333A46')};
            }}
        """)
        self.lbl_platform.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        self.lbl_time.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; background: transparent; border: none;")
        self.lbl_duration.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; font-family: monospace; background: transparent; border: none;")
        self.lbl_counts.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 11px; background: transparent; border: none;")
        self.btn_details.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface', '#161B22')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
                border-radius: 5px;
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('primary', '#FF5F15')};
                color: {tokens.get('primary', '#FF5F15')};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.run)
        super().mousePressEvent(event)


class RunSummaryCard(QFrame):
    """Compact history view displaying recent runs with slide-out drawer trigger."""

    run_selected = Signal(object)  # AutomationRun
    view_all_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._runs: List[AutomationRun] = []
        self._rows: List[RunHistoryRow] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("run_summary_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header Row
        top_row = QHBoxLayout()
        self.lbl_hdr = QLabel("Run History")
        top_row.addWidget(self.lbl_hdr)
        top_row.addStretch()

        self.btn_view_all = QPushButton("View All ↗")
        self.btn_view_all.setFixedHeight(22)
        self.btn_view_all.setCursor(Qt.PointingHandCursor)
        self.btn_view_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('accent', '#FF7A3D')};
                font-size: 11px;
                font-weight: 700;
                padding: 0 8px;
                border-radius: 4px;
                border: 1px solid {COLORS.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        self.btn_view_all.clicked.connect(self.view_all_requested.emit)
        top_row.addWidget(self.btn_view_all)
        layout.addLayout(top_row)

        # Backward compatibility dummy box attributes
        self.session_box = QWidget()
        self.session_box.setVisible(False)
        self.lbl_session_status = QLabel("")
        self.lbl_session_stats = QLabel("")

        # Scroll Area for Rows Container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 6px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS.get('border_light', '#333A46')};
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS.get('primary', '#FF5F15')};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        # Rows Container
        self.rows_container = QWidget()
        self.rows_container.setStyleSheet("background: transparent;")
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setContentsMargins(0, 0, 4, 0)
        self.rows_layout.setSpacing(6)

        self.lbl_empty = QLabel("No previous automation runs recorded.")
        self.lbl_empty.setStyleSheet(f"color: {COLORS.get('text_dark', '#6E7681')}; font-size: 11px; font-style: italic;")
        self.rows_layout.addWidget(self.lbl_empty)

        self.scroll_area.setWidget(self.rows_container)
        layout.addWidget(self.scroll_area, 1)
        self._refresh_styles()

    def set_recent_runs(self, runs: List[Any], max_display: int = 8) -> None:
        """Populates history rows from AutomationRun instances."""
        self._runs = runs or []

        # Clear existing rows and stretchers
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item.widget() and item.widget() != self.lbl_empty:
                item.widget().deleteLater()
        self._rows.clear()

        if not self._runs:
            self.lbl_empty.setVisible(True)
            self.rows_layout.addWidget(self.lbl_empty)
            return

        self.lbl_empty.setVisible(False)
        for run in self._runs[:max_display]:
            row = RunHistoryRow(run, self.rows_container)
            row.clicked.connect(self.run_selected.emit)
            self._rows.append(row)
            self.rows_layout.addWidget(row)

        self.rows_layout.addStretch()

    def update_from_state(self, state: AutomationUIState) -> None:
        """Backward-compatibility update stub."""
        pass

    def _refresh_styles(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QFrame#run_summary_card {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 10px;
            }}
        """)
        self.lbl_hdr.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 13px; font-weight: 700;")

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
        for row in self._rows:
            row.apply_theme(tokens)

