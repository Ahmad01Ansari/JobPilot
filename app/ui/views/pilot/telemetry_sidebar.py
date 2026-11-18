"""Right-side telemetry and operational status sidebar for the AI Pilot."""

from typing import Any, Dict
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.services.pilot.pilot_models import PilotTelemetry
from app.ui.theme import COLORS


class PilotTelemetrySidebar(QFrame):
    """Telemetry sidebar reporting live metrics and platform health."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self.setStyleSheet(f"""
            PilotTelemetrySidebar {{
                background-color: {COLORS.get('surface', '#161B22')};
                border-left: 1px solid {COLORS.get('border', '#262C36')};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 1. Operational Status Card
        status_card = QFrame()
        status_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 10px;
        """)
        sc_layout = QVBoxLayout(status_card)
        sc_layout.setContentsMargins(10, 8, 10, 8)
        sc_layout.setSpacing(4)

        status_header = QLabel("COPILOT STATUS")
        status_header.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: bold;")
        sc_layout.addWidget(status_header)

        self.status_val = QLabel("READY")
        self.status_val.setStyleSheet(f"color: {COLORS.get('success', '#2EA043')}; font-size: 14px; font-weight: bold;")
        sc_layout.addWidget(self.status_val)
        layout.addWidget(status_card)

        # 2. Today's Progress Card
        metrics_card = QFrame()
        metrics_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 10px;
        """)
        mc_layout = QVBoxLayout(metrics_card)
        mc_layout.setContentsMargins(10, 8, 10, 8)
        mc_layout.setSpacing(8)

        m_header = QLabel("TODAY'S HUNT")
        m_header.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: bold;")
        mc_layout.addWidget(m_header)

        self.quota_label = QLabel("Applications: 0 / 25")
        self.quota_label.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 12px;")
        mc_layout.addWidget(self.quota_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setRange(0, 25)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                border-radius: 3px;
            }}
        """)
        mc_layout.addWidget(self.progress_bar)

        self.analyzed_label = QLabel("Jobs Discovered: 0")
        self.analyzed_label.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
        mc_layout.addWidget(self.analyzed_label)

        self.score_label = QLabel("Avg Match Score: 82%")
        self.score_label.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
        mc_layout.addWidget(self.score_label)
        layout.addWidget(metrics_card)

        # 3. Active Rules & Deal-Breakers Card
        rules_card = QFrame()
        rules_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 10px;
        """)
        rc_layout = QVBoxLayout(rules_card)
        rc_layout.setContentsMargins(10, 8, 10, 8)
        rc_layout.setSpacing(6)

        r_header = QLabel("ACTIVE RULES")
        r_header.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: bold;")
        rc_layout.addWidget(r_header)

        self.min_score_label = QLabel("Min Match Score: 70%")
        self.min_score_label.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 12px;")
        rc_layout.addWidget(self.min_score_label)

        self.breakers_label = QLabel("Deal-Breakers: None")
        self.breakers_label.setWordWrap(True)
        self.breakers_label.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
        rc_layout.addWidget(self.breakers_label)
        layout.addWidget(rules_card)

        # 4. Platform Engine Health
        platform_card = QFrame()
        platform_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 10px;
        """)
        pc_layout = QVBoxLayout(platform_card)
        pc_layout.setContentsMargins(10, 8, 10, 8)
        pc_layout.setSpacing(6)

        p_header = QLabel("AUTOMATION ENGINES")
        p_header.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: bold;")
        pc_layout.addWidget(p_header)

        for p_name in ["LinkedIn", "Indeed", "Naukri", "Universal ATS"]:
            p_row = QHBoxLayout()
            p_lbl = QLabel(p_name)
            p_lbl.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px;")
            p_row.addWidget(p_lbl)
            p_row.addStretch()
            status_dot = QLabel("Active")
            status_dot.setStyleSheet(f"color: {COLORS.get('success', '#2EA043')}; font-size: 10px; font-weight: bold;")
            p_row.addWidget(status_dot)
            pc_layout.addLayout(p_row)

        layout.addWidget(platform_card)
        layout.addStretch()

    def update_telemetry(self, telemetry: PilotTelemetry, rules: Dict[str, Any]):
        """Updates values on the sidebar from telemetry snapshot."""
        # Status
        if telemetry.status == "intervention_required":
            self.status_val.setText("ACTION NEEDED")
            self.status_val.setStyleSheet(f"color: {COLORS.get('warning', '#D29922')}; font-size: 14px; font-weight: bold;")
        elif telemetry.status == "paused":
            self.status_val.setText("PAUSED")
            self.status_val.setStyleSheet(f"color: {COLORS.get('warning', '#D29922')}; font-size: 14px; font-weight: bold;")
        elif telemetry.status == "working":
            self.status_val.setText("WORKING")
            self.status_val.setStyleSheet(f"color: {COLORS.get('info', '#388BFD')}; font-size: 14px; font-weight: bold;")
        else:
            self.status_val.setText("READY")
            self.status_val.setStyleSheet(f"color: {COLORS.get('success', '#2EA043')}; font-size: 14px; font-weight: bold;")

        # Progress
        self.quota_label.setText(f"Applications: {telemetry.daily_applies} / {telemetry.daily_limit}")
        self.progress_bar.setRange(0, max(telemetry.daily_limit, 1))
        self.progress_bar.setValue(telemetry.daily_applies)
        self.analyzed_label.setText(f"Jobs Discovered: {telemetry.jobs_analyzed_today}")
        self.score_label.setText(f"Avg Match Score: {telemetry.avg_match_score}%")

        # Rules
        self.min_score_label.setText(f"Min Match Score: {rules.get('min_score', 70)}%")
        breakers = rules.get("deal_breakers", [])
        if breakers:
            self.breakers_label.setText("Deal-Breakers: " + ", ".join(breakers))
        else:
            self.breakers_label.setText("Deal-Breakers: None configured")

