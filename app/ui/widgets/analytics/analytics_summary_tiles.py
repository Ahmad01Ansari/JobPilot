"""Compact KPI summary metric tiles row with period comparisons and tooltip definitions."""

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.services.analytics_service import MetricWithComparison, ResponseTimeStats
from app.ui.theme import COLORS


class AnalyticsSummaryTiles(QWidget):
    """Row of 6 compact analytical metric tiles answering core funnel questions."""

    tile_clicked = Signal(str)  # Emits metric key: 'submitted', 'responses', 'progression', 'interviews', 'offers', 'velocity'

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._tile_widgets: Dict[str, Dict[str, QLabel]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Tile 1: Submitted Applications
        t_apps = self._create_tile(
            key="submitted",
            title="Applications",
            value="0",
            sub="Submitted in period",
            color_hex=COLORS["text"],
            tooltip="Total applications successfully submitted in this date range.",
        )
        layout.addWidget(t_apps)

        # Tile 2: Direct Recruiter Response Rate
        t_resp = self._create_tile(
            key="responses",
            title="Response Rate",
            value="0.0%",
            sub="0 direct replies",
            color_hex=COLORS["info"],
            tooltip="Direct Recruiter Response Rate:\nApplications with at least one inbound recruiter message ÷ submitted applications.",
        )
        layout.addWidget(t_resp)

        # Tile 3: Pipeline Progression Rate
        t_prog = self._create_tile(
            key="progression",
            title="Progression Rate",
            value="0.0%",
            sub="0 advanced",
            color_hex=COLORS["warning"],
            tooltip="Pipeline Progression Rate:\nApplications that advanced to Under Review, Shortlisted, or Interview ÷ submitted applications.",
        )
        layout.addWidget(t_prog)

        # Tile 4: Interview Conversion Rate
        t_iv = self._create_tile(
            key="interviews",
            title="Interview Rate",
            value="0.0%",
            sub="0 interviewed",
            color_hex=COLORS["purple"],
            tooltip="Interview Conversion Rate:\nDistinct applications with at least one scheduled interview ÷ submitted applications.",
        )
        layout.addWidget(t_iv)

        # Tile 5: Offer Conversion Rate
        t_off = self._create_tile(
            key="offers",
            title="Offer Rate",
            value="0.0%",
            sub="0 received",
            color_hex=COLORS["success"],
            tooltip="Offer Conversion Rate:\nDistinct applications with an employment offer ÷ submitted applications.",
        )
        layout.addWidget(t_off)

        # Tile 6: Weekly Velocity
        t_vel = self._create_tile(
            key="velocity",
            title="Weekly Velocity",
            value="0 / wk",
            sub="Pace of submission",
            color_hex=COLORS["primary"],
            tooltip="Application Velocity:\nAverage number of submitted applications per 7 calendar days.",
        )
        layout.addWidget(t_vel)

    def _create_tile(
        self,
        key: str,
        title: str,
        value: str,
        sub: str,
        color_hex: str,
        tooltip: str,
    ) -> QWidget:
        tile = QFrame()
        tile.setCursor(Qt.PointingHandCursor)
        tile.setToolTip(tooltip)
        tile.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {color_hex}80;
                background-color: {COLORS['surface_hover']};
            }}
        """)
        t_layout = QVBoxLayout(tile)
        t_layout.setContentsMargins(12, 10, 12, 10)
        t_layout.setSpacing(4)

        # Title + Trend Row
        header_row = QHBoxLayout()
        lbl_title = QLabel(title.upper())
        lbl_title.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 700;
            color: {COLORS['text_muted']};
            letter-spacing: 0.5px;
            border: none;
            background: transparent;
        """)
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        lbl_trend = QLabel("")
        lbl_trend.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 700;
            color: {COLORS['text_muted']};
            border: none;
            background: transparent;
        """)
        header_row.addWidget(lbl_trend)
        t_layout.addLayout(header_row)

        # Numeric value
        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 800;
            color: {color_hex};
            letter-spacing: -0.5px;
            border: none;
            background: transparent;
        """)
        t_layout.addWidget(lbl_val)

        # Subtitle / context
        lbl_sub = QLabel(sub)
        lbl_sub.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_muted']};
            border: none;
            background: transparent;
        """)
        t_layout.addWidget(lbl_sub)

        # Mouse click connection
        tile.mousePressEvent = lambda ev: self.tile_clicked.emit(key)

        self._tile_widgets[key] = {
            "title": lbl_title,
            "trend": lbl_trend,
            "val": lbl_val,
            "sub": lbl_sub,
        }
        return tile

    def update_metrics(self, data: Dict[str, Any]) -> None:
        """Updates tile values, subtitles, and period-over-period comparisons."""
        # 1. Submitted Applications
        comp_apps: MetricWithComparison = data.get("submitted_applications", MetricWithComparison(value=0))
        self._tile_widgets["submitted"]["val"].setText(str(comp_apps.value))
        if comp_apps.comparison_available and comp_apps.pct_change is not None:
            sign = "↑" if comp_apps.pct_change >= 0 else "↓"
            trend_color = COLORS["success"] if comp_apps.pct_change >= 0 else COLORS["danger"]
            self._tile_widgets["submitted"]["trend"].setText(f"{sign} {abs(comp_apps.pct_change)}%")
            self._tile_widgets["submitted"]["trend"].setStyleSheet(f"font-size: 10px; font-weight: 700; color: {trend_color};")
            self._tile_widgets["submitted"]["sub"].setText(f"vs {comp_apps.prev_value} prior period")
        elif comp_apps.reason:
            self._tile_widgets["submitted"]["trend"].setText("")
            self._tile_widgets["submitted"]["sub"].setText(comp_apps.reason)

        # 2. Direct Recruiter Responses
        resp_rate = data.get("response_rate", 0.0)
        direct_cnt = data.get("direct_responses", 0)
        self._tile_widgets["responses"]["val"].setText(f"{resp_rate}%")
        self._tile_widgets["responses"]["sub"].setText(f"{direct_cnt} direct replies logged")

        # 3. Pipeline Progression
        prog_rate = data.get("progression_rate", 0.0)
        prog_cnt = data.get("progressed_applications", 0)
        self._tile_widgets["progression"]["val"].setText(f"{prog_rate}%")
        self._tile_widgets["progression"]["sub"].setText(f"{prog_cnt} advanced to review")

        # 4. Interviews
        iv_rate = data.get("interview_rate", 0.0)
        iv_cnt = data.get("interviewed_applications", 0)
        self._tile_widgets["interviews"]["val"].setText(f"{iv_rate}%")
        self._tile_widgets["interviews"]["sub"].setText(f"{iv_cnt} distinct candidates")

        # 5. Offers
        off_rate = data.get("offer_rate", 0.0)
        off_cnt = data.get("offer_applications", 0)
        self._tile_widgets["offers"]["val"].setText(f"{off_rate}%")
        self._tile_widgets["offers"]["sub"].setText(f"{off_cnt} received offers" if off_cnt > 0 else "No offers in period")

        # 6. Weekly Velocity
        vel: MetricWithComparison = data.get("velocity", MetricWithComparison(value=0))
        self._tile_widgets["velocity"]["val"].setText(f"{vel.value} / wk")
        if vel.comparison_available and vel.pct_change is not None:
            sign = "↑" if vel.pct_change >= 0 else "↓"
            trend_color = COLORS["success"] if vel.pct_change >= 0 else COLORS["danger"]
            self._tile_widgets["velocity"]["trend"].setText(f"{sign} {abs(vel.pct_change)}%")
            self._tile_widgets["velocity"]["trend"].setStyleSheet(f"font-size: 10px; font-weight: 700; color: {trend_color};")
            self._tile_widgets["velocity"]["sub"].setText(f"vs {vel.prev_value}/wk prior")
        elif vel.reason:
            self._tile_widgets["velocity"]["trend"].setText("")
            self._tile_widgets["velocity"]["sub"].setText(vel.reason)
