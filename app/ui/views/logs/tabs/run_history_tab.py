"""Run History Tab providing historical automation session analytics and conversion funnel."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.run_persistence_bridge import RunPersistenceBridge
from app.ui.theme import ThemeManager


class FunnelStep(QFrame):
    """Visual conversion funnel step with count and percentage."""

    def __init__(self, title: str, count: int = 0, percentage: float = 100.0, color: Optional[str] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title_text = title
        self.count = count
        self.percentage = percentage
        self.bar_color = color
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        self.title_lbl = QLabel(self.title_text)
        self.title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c.get('text_muted', '#8B949E')}; text-transform: uppercase;")
        hdr.addWidget(self.title_lbl)
        hdr.addStretch()

        self.pct_lbl = QLabel(f"{self.percentage:.1f}%")
        self.pct_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {self.bar_color or c.get('primary', '#FF5F15')};")
        hdr.addWidget(self.pct_lbl)
        layout.addLayout(hdr)

        self.val_lbl = QLabel(str(self.count))
        self.val_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {c.get('text', '#F0F6FC')};")
        layout.addWidget(self.val_lbl)

        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(4)
        self.pbar.setTextVisible(False)
        self.pbar.setValue(int(self.percentage))
        bar_fill = self.bar_color or c.get("primary", "#FF5F15")
        self.pbar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {c.get('surface_alt', '#1C2128')};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {bar_fill};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.pbar)

        self.setStyleSheet(f"""
            FunnelStep {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-top: 3px solid {bar_fill};
                border-radius: 8px;
            }}
        """)

    def update_data(self, count: int, percentage: float) -> None:
        self.count = count
        self.percentage = percentage
        self.val_lbl.setText(str(count))
        self.pct_lbl.setText(f"{percentage:.1f}%")
        self.pbar.setValue(int(percentage))


class RunHistoryTab(QWidget):
    """Tab 2: Historical automation run table and step-by-step conversion funnels."""

    load_run_requested = Signal(str)  # run_id

    def __init__(self, persistence_bridge: Optional[RunPersistenceBridge] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.bridge = persistence_bridge or RunPersistenceBridge()
        self._runs_data: List[Dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # 1. Conversion Funnel Header
        funnel_box = QHBoxLayout()
        funnel_box.setSpacing(8)

        self.step_discovered = FunnelStep("Discovered", count=0, percentage=100.0, color=c.get("info", "#388BFD"))
        funnel_box.addWidget(self.step_discovered)

        self.step_qualified = FunnelStep("Qualified", count=0, percentage=0.0, color=c.get("cyan", "#39C5CF"))
        funnel_box.addWidget(self.step_qualified)

        self.step_applied = FunnelStep("Applications Submitted", count=0, percentage=0.0, color=c.get("primary", "#FF5F15"))
        funnel_box.addWidget(self.step_applied)

        layout.addLayout(funnel_box)

        # 2. Historical Runs Table
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Run ID", "Platform", "Status", "Started At", "Discovered", "Qualified", "Applied", "Errors", "Stop Reason"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_row_selected)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                gridline-color: {c.get('border_subtle', '#21262D')};
                color: {c.get('text', '#F0F6FC')};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text_muted', '#8B949E')};
                border: none;
                padding: 6px 10px;
                font-weight: 600;
            }}
            QTableWidget::item:selected {{
                background-color: {c.get('primary_subtle', '#FF5F1518')};
                color: {c.get('text', '#F0F6FC')};
            }}
        """)
        layout.addWidget(self.table, 1)

    def refresh_history(self) -> None:
        """Queries historical runs from SQLite and refreshes the table."""
        self._runs_data = self.bridge.list_historical_runs(limit=30)
        self.table.setRowCount(len(self._runs_data))

        # Overall sums for funnel if no single row is selected
        total_disc = sum(r.get("jobs_discovered", 0) for r in self._runs_data)
        total_qual = sum(r.get("jobs_qualified", 0) for r in self._runs_data)
        total_app = sum(r.get("applications_submitted", 0) for r in self._runs_data)

        self._update_funnel(total_disc, total_qual, total_app)

        for row, r in enumerate(self._runs_data):
            rid = r.get("run_id", "")[:10] + "..."
            started = r.get("started_at")
            started_str = started.strftime("%Y-%m-%d %H:%M") if isinstance(started, datetime) else str(started or "")

            items = [
                QTableWidgetItem(rid),
                QTableWidgetItem(str(r.get("platform", "")).capitalize()),
                QTableWidgetItem(str(r.get("status", ""))),
                QTableWidgetItem(started_str),
                QTableWidgetItem(str(r.get("jobs_discovered", 0))),
                QTableWidgetItem(str(r.get("jobs_qualified", 0))),
                QTableWidgetItem(str(r.get("applications_submitted", 0))),
                QTableWidgetItem(str(r.get("errors_count", 0))),
                QTableWidgetItem(str(r.get("stop_reason") or "—")),
            ]
            for col, item in enumerate(items):
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.table.setItem(row, col, item)

    def _update_funnel(self, discovered: int, qualified: int, applied: int) -> None:
        pct_qual = (qualified / discovered * 100.0) if discovered > 0 else 0.0
        pct_app = (applied / qualified * 100.0) if qualified > 0 else 0.0

        self.step_discovered.update_data(discovered, 100.0)
        self.step_qualified.update_data(qualified, pct_qual)
        self.step_applied.update_data(applied, pct_app)

    def _on_row_selected(self) -> None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows or not self._runs_data:
            return
        row = selected_rows[0].row()
        if 0 <= row < len(self._runs_data):
            r = self._runs_data[row]
            disc = r.get("jobs_discovered", 0)
            qual = r.get("jobs_qualified", 0)
            app = r.get("applications_submitted", 0)
            self._update_funnel(disc, qual, app)
