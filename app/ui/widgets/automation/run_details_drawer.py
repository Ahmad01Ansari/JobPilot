"""Read-only Run Details slide-out drawer component for Automation Control Center.

Displays detailed telemetry and metrics for historical automation runs without
initiating destructive actions or pretending non-existent relational database joins.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.db.models.automation_run import AutomationRun
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class RunDetailsDrawer(QFrame):
    """Slide-out drawer displaying read-only diagnostics for a selected historical run."""

    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(340)
        self.setVisible(False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("run_details_drawer")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        # 1. Header Row
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.lbl_title = QLabel("Run Diagnostics")
        top_row.addWidget(self.lbl_title)
        top_row.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setFixedSize(28, 28)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Close diagnostics (Esc)")
        self.btn_close.clicked.connect(self.close_drawer)
        top_row.addWidget(self.btn_close)
        layout.addLayout(top_row)

        # 2. Status & Platform Banner
        meta_row = QHBoxLayout()
        meta_row.setSpacing(8)

        self.lbl_platform = QLabel("LinkedIn")
        meta_row.addWidget(self.lbl_platform)
        meta_row.addStretch()

        self.badge_status = StatusBadge("COMPLETED", status_type="success")
        meta_row.addWidget(self.badge_status)
        layout.addLayout(meta_row)

        # 3. Key-Value Info Grid
        self.info_frame = QFrame()
        grid = QGridLayout(self.info_frame)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(8)

        self.val_run_id = QLabel("—")
        self.val_start = QLabel("—")
        self.val_end = QLabel("—")
        self.val_duration = QLabel("—")
        self.val_keyword = QLabel("—")

        labels = [
            ("Run ID", self.val_run_id),
            ("Started", self.val_start),
            ("Finished", self.val_end),
            ("Duration", self.val_duration),
            ("Keyword", self.val_keyword),
        ]

        for row, (lbl_txt, val_widget) in enumerate(labels):
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px; font-weight: 600;")
            val_widget.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px; font-family: 'JetBrains Mono', monospace;")
            val_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(lbl, row, 0)
            grid.addWidget(val_widget, row, 1)

        layout.addWidget(self.info_frame)

        # 4. Pipeline Summary Metrics
        lbl_pipeline = QLabel("METRICS BREAKDOWN")
        lbl_pipeline.setStyleSheet(f"""
            color: {COLORS.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_pipeline)

        self.metrics_grid = QFrame()
        m_grid = QGridLayout(self.metrics_grid)
        m_grid.setContentsMargins(10, 8, 10, 8)
        m_grid.setSpacing(10)

        self.cnt_discovered = QLabel("0")
        self.cnt_evaluated = QLabel("0")
        self.cnt_qualified = QLabel("0")
        self.cnt_submitted = QLabel("0")
        self.cnt_skipped = QLabel("0")
        self.cnt_errors = QLabel("0")

        metric_items = [
            ("Discovered", self.cnt_discovered, "primary"),
            ("Evaluated", self.cnt_evaluated, "text"),
            ("Qualified", self.cnt_qualified, "accent"),
            ("Submitted", self.cnt_submitted, "success"),
            ("Skipped", self.cnt_skipped, "text_muted"),
            ("Errors", self.cnt_errors, "danger"),
        ]

        for idx, (title, val_w, c_key) in enumerate(metric_items):
            r = idx // 2
            c = idx % 2
            box = QVBoxLayout()
            box.setSpacing(2)
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: 600;")
            val_w.setStyleSheet(f"color: {COLORS.get(c_key, COLORS.get('text', '#F0F6FC'))}; font-size: 16px; font-weight: 800;")
            box.addWidget(t_lbl)
            box.addWidget(val_w)
            m_grid.addLayout(box, r, c)

        layout.addWidget(self.metrics_grid)

        # 5. Stop Reason / Error Callout (if any)
        self.lbl_reason_title = QLabel("REASON / NOTES")
        self.lbl_reason_title.setStyleSheet(f"""
            color: {COLORS.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        self.lbl_reason_val = QLabel("None")
        self.lbl_reason_val.setWordWrap(True)
        self.lbl_reason_val.setStyleSheet(f"""
            color: {COLORS.get('text_muted', '#8B949E')};
            font-size: 11px;
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            padding: 6px 10px;
            border-radius: 6px;
        """)
        layout.addWidget(self.lbl_reason_title)
        layout.addWidget(self.lbl_reason_val)

        layout.addStretch()

        # 6. Bottom Close Action
        self.btn_footer_close = QPushButton("✕ Close Drawer")
        self.btn_footer_close.setCursor(Qt.PointingHandCursor)
        self.btn_footer_close.clicked.connect(self.close_drawer)
        layout.addWidget(self.btn_footer_close)

        self._refresh_styles()

    def set_run(self, run: AutomationRun) -> None:
        """Populates drawer fields from an AutomationRun model."""
        if not run:
            return

        # Platform
        p_name = getattr(run, "platform", "Unknown")
        self.lbl_platform.setText(p_name.capitalize())

        # Status Badge
        st = getattr(run, "status", "UNKNOWN").upper()
        v_type = "success" if st == "COMPLETED" else ("danger" if st in ("FAILED", "ERROR") else "warning")
        self.badge_status.setText(st)
        self.badge_status.update_style(v_type)

        # Basic Info
        rid = str(getattr(run, "run_id", "—"))
        self.val_run_id.setText(f"{rid[:8]}..." if len(rid) > 12 else rid)
        self.val_run_id.setToolTip(rid)

        st_time = getattr(run, "started_at", None)
        fin_time = getattr(run, "finished_at", None)
        self.val_start.setText(st_time.strftime("%b %d, %H:%M:%S") if st_time else "—")
        self.val_end.setText(fin_time.strftime("%b %d, %H:%M:%S") if fin_time else "In Progress")

        # Duration
        if st_time and fin_time:
            secs = max(0, int((fin_time - st_time).total_seconds()))
            mins = secs // 60
            self.val_duration.setText(f"{mins:02d}m {secs % 60:02d}s")
        else:
            self.val_duration.setText("—")

        self.val_keyword.setText(getattr(run, "current_keyword", "—") or "—")

        # Metrics
        self.cnt_discovered.setText(str(getattr(run, "jobs_discovered", 0)))
        self.cnt_evaluated.setText(str(getattr(run, "jobs_evaluated", 0)))
        self.cnt_qualified.setText(str(getattr(run, "jobs_qualified", 0)))
        self.cnt_submitted.setText(str(getattr(run, "applications_submitted", 0)))
        self.cnt_skipped.setText(str(getattr(run, "jobs_skipped", 0)))
        self.cnt_errors.setText(str(getattr(run, "errors_count", 0)))

        reason = getattr(run, "stop_reason", None) or "Completed cleanly."
        self.lbl_reason_val.setText(reason)

        self.setVisible(True)

    def close_drawer(self) -> None:
        """Hides drawer and notifies listeners."""
        self.setVisible(False)
        self.closed.emit()

    def keyPressEvent(self, event) -> None:
        """Closes drawer on Escape key."""
        if event.key() == Qt.Key_Escape:
            self.close_drawer()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _refresh_styles(self) -> None:
        tokens = COLORS

        self.setStyleSheet(f"""
            QFrame#run_details_drawer {{
                background-color: {tokens.get('surface', '#161B22')};
                border-left: 1px solid {tokens.get('border', '#262C36')};
            }}
        """)

        self.lbl_title.setStyleSheet(f"""
            color: {tokens.get('text', '#F0F6FC')};
            font-size: 14px;
            font-weight: 700;
        """)

        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 14px;
                font-weight: bold;
                border-radius: 6px;
                border: 1px solid {tokens.get('border', '#262C36')};
                padding: 0px;
                margin: 0px;
                text-align: center;
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('border_light', '#3B4354')};
            }}
        """)

        self.btn_footer_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 12px;
                font-weight: 600;
                padding: 8px 14px;
                border-radius: 6px;
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('border_light', '#3B4354')};
            }}
            QPushButton:pressed {{
                background-color: {tokens.get('surface', '#161B22')};
            }}
        """)

        self.lbl_platform.setStyleSheet(f"""
            color: {tokens.get('text', '#F0F6FC')};
            font-size: 13px;
            font-weight: 700;
        """)

        self.info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
            }}
        """)

        self.metrics_grid.setStyleSheet(f"""
            QFrame {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
            }}
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
