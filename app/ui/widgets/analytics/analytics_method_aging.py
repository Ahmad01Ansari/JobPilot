"""Two-column widget showing application method efficiency and active application aging."""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.services.analytics_service import ResponseTimeStats
from app.ui.theme import COLORS


class AnalyticsMethodAgingWidget(QWidget):
    """Two-column layout displaying method breakdown, response latency forensics, and aging."""

    method_clicked = Signal(str)  # Emits method_key: 'EASY_APPLY', etc.
    aging_clicked = Signal(str)   # Emits age_bucket: '< 3 days', etc.

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # -------------------------------------------------------------
        # Left Card: Application Method Efficiency
        # -------------------------------------------------------------
        self.method_card = QFrame()
        self.method_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        m_layout = QVBoxLayout(self.method_card)
        m_layout.setContentsMargins(14, 12, 14, 12)
        m_layout.setSpacing(10)

        m_head = QHBoxLayout()
        lbl_m_title = QLabel("Application Methods")
        lbl_m_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        m_head.addWidget(lbl_m_title)
        m_head.addStretch()

        lbl_m_hint = QLabel("Volume & Response Rate")
        lbl_m_hint.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        m_head.addWidget(lbl_m_hint)
        m_layout.addLayout(m_head)

        self.method_container = QVBoxLayout()
        self.method_container.setSpacing(6)
        m_layout.addLayout(self.method_container)
        m_layout.addStretch()

        layout.addWidget(self.method_card, 1)

        # -------------------------------------------------------------
        # Right Card: Active Application Aging & Response Latency
        # -------------------------------------------------------------
        self.aging_card = QFrame()
        self.aging_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        a_layout = QVBoxLayout(self.aging_card)
        a_layout.setContentsMargins(14, 12, 14, 12)
        a_layout.setSpacing(10)

        a_head = QHBoxLayout()
        lbl_a_title = QLabel("Active Application Aging")
        lbl_a_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        a_head.addWidget(lbl_a_title)
        a_head.addStretch()

        lbl_a_hint = QLabel("Days since submission (Active only)")
        lbl_a_hint.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        a_head.addWidget(lbl_a_hint)
        a_layout.addLayout(a_head)

        # Aging distribution rows
        self.aging_container = QVBoxLayout()
        self.aging_container.setSpacing(6)
        a_layout.addLayout(self.aging_container)

        # Response Time Forensics Strip
        self.response_forensics_frame = QFrame()
        self.response_forensics_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px;
            }}
        """)
        rf_layout = QVBoxLayout(self.response_forensics_frame)
        rf_layout.setContentsMargins(8, 6, 8, 6)
        rf_layout.setSpacing(3)

        self.lbl_resp_time_title = QLabel("Response Latency:")
        self.lbl_resp_time_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text']};")
        rf_layout.addWidget(self.lbl_resp_time_title)

        self.lbl_resp_time_sub = QLabel("No data")
        self.lbl_resp_time_sub.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        rf_layout.addWidget(self.lbl_resp_time_sub)

        a_layout.addWidget(self.response_forensics_frame)
        layout.addWidget(self.aging_card, 1)

    def update_data(
        self,
        methods: List[Dict[str, Any]],
        aging: Dict[str, int],
        resp_stats: ResponseTimeStats,
    ) -> None:
        """Updates method rows, aging bars, and response latency forensics."""
        self._render_methods(methods)
        self._render_aging(aging)
        self._render_response_stats(resp_stats)

    def _render_methods(self, methods: List[Dict[str, Any]]) -> None:
        while self.method_container.count():
            item = self.method_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not methods or all(m.get("applications", 0) == 0 for m in methods):
            lbl = QLabel("No application method data in this period")
            lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            lbl.setAlignment(Qt.AlignCenter)
            self.method_container.addWidget(lbl)
            return

        for m in methods:
            m_key = m.get("method_key", "")
            name = m.get("method", "")
            apps = m.get("applications", 0)
            resp = m.get("responses", 0)
            rate = m.get("response_rate", 0.0)

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
            r_lay = QHBoxLayout(row)
            r_lay.setContentsMargins(10, 6, 10, 6)
            r_lay.setSpacing(8)

            lbl_name = QLabel(name)
            lbl_name.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text']}; border: none; background: transparent;")
            r_lay.addWidget(lbl_name)
            r_lay.addStretch()

            lbl_count = QLabel(f"{apps} apps")
            lbl_count.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; border: none; background: transparent;")
            r_lay.addWidget(lbl_count)

            lbl_rate = QLabel(f"{rate}% response")
            lbl_rate.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; border: none; background: transparent;")
            r_lay.addWidget(lbl_rate)

            row.mousePressEvent = lambda ev, mk=m_key: self.method_clicked.emit(mk)
            self.method_container.addWidget(row)

    def _render_aging(self, aging: Dict[str, int]) -> None:
        while self.aging_container.count():
            item = self.aging_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        total_active = sum(aging.values())
        if total_active == 0:
            lbl = QLabel("No active applications currently aging")
            lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            lbl.setAlignment(Qt.AlignCenter)
            self.aging_container.addWidget(lbl)
            return

        for bucket_name, count in aging.items():
            pct = round((count / total_active * 100), 1) if total_active > 0 else 0.0

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
            r_lay = QVBoxLayout(row)
            r_lay.setContentsMargins(10, 6, 10, 6)
            r_lay.setSpacing(4)

            top = QHBoxLayout()
            lbl_b = QLabel(bucket_name)
            lbl_b.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text']}; border: none; background: transparent;")
            top.addWidget(lbl_b)
            top.addStretch()

            lbl_c = QLabel(f"{count} ({pct}%)")
            lbl_c.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text']}; border: none; background: transparent;")
            top.addWidget(lbl_c)
            r_lay.addLayout(top)

            # Mini bar
            pbar = QProgressBar()
            pbar.setFixedHeight(4)
            pbar.setTextVisible(False)
            pbar.setRange(0, total_active)
            pbar.setValue(count)
            # Orange for older items
            bar_color = COLORS["danger"] if bucket_name in ["30–60 days", "60+ days"] else COLORS["primary"]
            pbar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {COLORS['surface']};
                    border: none;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background-color: {bar_color};
                    border-radius: 2px;
                }}
            """)
            r_lay.addWidget(pbar)

            row.mousePressEvent = lambda ev, bk=bucket_name: self.aging_clicked.emit(bk)
            self.aging_container.addWidget(row)

    def _render_response_stats(self, stats: ResponseTimeStats) -> None:
        if not stats.has_sufficient_data:
            self.lbl_resp_time_title.setText("Response Latency: Insufficient data yet")
            self.lbl_resp_time_sub.setText("Requires at least 3 response events with timestamps to compute statistics.")
            return

        source_label = "Inbound Recruiter Communication" if stats.source_type == "COMMUNICATION" else "Stage Progression Proxy"
        self.lbl_resp_time_title.setText(
            f"Response Latency: Avg {stats.avg_days}d  •  Median {stats.median_days}d  (Fastest: {stats.fastest_days}d, Slowest: {stats.slowest_days}d)"
        )
        self.lbl_resp_time_sub.setText(f"Source: {source_label} ({stats.sample_count} samples)")
