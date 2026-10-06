"""Search Performance widget presenting ATS conversion funnel and visual platform analytics."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.dashboard_dto import PlatformMetricDTO, SearchPerformanceDTO
from app.ui.theme import COLORS
from app.ui.widgets.platform_chart_card import DonutChartCanvas, PLATFORM_COLORS, PLATFORM_ICONS


class FunnelStepRow(QWidget):
    """Horizontal funnel conversion step displaying stage name, bar, count, and rate."""

    def __init__(self, stage_name: str, count: int, total_baseline: int, color: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.color = color

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(10)

        # Stage label
        lbl_name = QLabel(f"● {stage_name}")
        lbl_name.setFixedWidth(85)
        lbl_name.setStyleSheet(f"color: {self.color}; font-size: 11px; font-weight: 700; background: transparent; border: none;")
        layout.addWidget(lbl_name)

        # Progress bar
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['surface_alt']};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.color};
                border-radius: 4px;
            }}
        """)
        pct = int((count / max(1, total_baseline)) * 100) if total_baseline > 0 else 0
        self.bar.setValue(min(100, pct))
        layout.addWidget(self.bar, 1)

        # Count
        self.lbl_count = QLabel(str(count))
        self.lbl_count.setFixedWidth(38)
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_count.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: 800; background: transparent; border: none;")
        layout.addWidget(self.lbl_count)

        # Conversion % from baseline
        self.lbl_pct = QLabel(f"{pct}%" if total_baseline > 0 else "—")
        self.lbl_pct.setFixedWidth(40)
        self.lbl_pct.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_pct.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent; border: none;")
        layout.addWidget(self.lbl_pct)

    def set_data(self, count: int, total_baseline: int) -> None:
        pct = int((count / max(1, total_baseline)) * 100) if total_baseline > 0 else 0
        self.bar.setValue(min(100, pct))
        self.lbl_count.setText(str(count))
        self.lbl_pct.setText(f"{pct}%" if total_baseline > 0 else "—")


class PlatformMetricBarRow(QWidget):
    """Horizontal comparative visual bar showing Platform, Applied vs Discovered, and rates."""

    def __init__(self, metric: PlatformMetricDTO, max_discovered: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui(metric, max_discovered)

    def _setup_ui(self, m: PlatformMetricDTO, max_discovered: int) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(8)

        # 1. Platform Icon & Name
        p_key = (m.platform_key or "").lower()
        icon = PLATFORM_ICONS.get(p_key, "🌐")
        color = PLATFORM_COLORS.get(p_key, COLORS.get("primary", "#FF5F15"))
        name = m.platform_name or p_key.title()

        lbl_plat = QLabel(f"{icon} {name}")
        lbl_plat.setFixedWidth(92)
        lbl_plat.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        layout.addWidget(lbl_plat)

        # 2. Applied progress bar proportional to discovered baseline
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setFixedHeight(8)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['surface_alt']};
                border: none;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)
        baseline = max(1, max_discovered)
        pct = int((m.applied_count / baseline) * 100) if baseline > 0 else 0
        bar.setValue(min(100, pct))
        layout.addWidget(bar, 1)

        # 3. Discovered / Applied Counts
        lbl_counts = QLabel(f"{m.applied_count} applied")
        lbl_counts.setFixedWidth(78)
        lbl_counts.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lbl_counts.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent; border: none;")
        layout.addWidget(lbl_counts)

        # 4. App Rate Pill
        app_rate_str = f"{m.application_rate:.1f}%" if m.application_rate > 0 else "0.0%"
        lbl_rate = QLabel(app_rate_str)
        lbl_rate.setFixedWidth(46)
        lbl_rate.setAlignment(Qt.AlignCenter)
        lbl_rate.setStyleSheet(f"""
            background-color: {color}20;
            color: {color};
            font-size: 10px;
            font-weight: 700;
            border-radius: 4px;
            padding: 1px 4px;
            border: 1px solid {color}40;
        """)
        layout.addWidget(lbl_rate)

        # 5. IV Pill if any
        if m.interview_count > 0:
            lbl_iv = QLabel(f"{m.interview_count} IV")
            lbl_iv.setFixedWidth(36)
            lbl_iv.setAlignment(Qt.AlignCenter)
            lbl_iv.setStyleSheet(f"""
                background-color: {COLORS.get('purple', '#A78BFA')}25;
                color: {COLORS.get('purple', '#A78BFA')};
                font-size: 10px;
                font-weight: 800;
                border-radius: 4px;
                padding: 1px 4px;
                border: 1px solid {COLORS.get('purple', '#A78BFA')}50;
            """)
            layout.addWidget(lbl_iv)
        else:
            sp = QLabel("")
            sp.setFixedWidth(36)
            layout.addWidget(sp)


class SearchPerformanceWidget(QFrame):
    """Search Performance card consolidating ATS funnel stages and visual platform analytics."""

    preset_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.active_preset = "ALL"
        self._preset_buttons: dict = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            SearchPerformanceWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # 1. Header
        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(8)

        lbl_icon = QLabel("📊")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        hdr_row.addWidget(lbl_icon)

        lbl_title = QLabel("SEARCH PERFORMANCE")
        lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        hdr_row.addWidget(lbl_title)
        hdr_row.addStretch(1)

        self.lbl_total_applied = QLabel("0 Applied")
        self.lbl_total_applied.setStyleSheet(f"""
            background-color: {COLORS['surface_alt']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid {COLORS['border_subtle']};
        """)
        hdr_row.addWidget(self.lbl_total_applied)
        layout.addLayout(hdr_row)

        # Timeframe Preset Selector
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        presets = [("TODAY", "Today"), ("7D", "7 Days"), ("30D", "30 Days"), ("ALL", "All Time")]
        for p_key, p_label in presets:
            btn = QPushButton(p_label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("preset_key", p_key)
            btn.clicked.connect(lambda _, k=p_key: self._on_preset_clicked(k))
            self._preset_buttons[p_key] = btn
            preset_row.addWidget(btn)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)
        self._update_preset_styles()

        # 2. Recruitment Funnel Section Header
        funnel_hdr = QLabel("CONVERSION FUNNEL")
        funnel_hdr.setStyleSheet(f"font-size: 11px; font-weight: 800; letter-spacing: 0.5px; color: {COLORS['text_muted']};")
        layout.addWidget(funnel_hdr)
        self.funnel_rows_container = QVBoxLayout()
        self.funnel_rows_container.setContentsMargins(0, 0, 0, 0)
        self.funnel_rows_container.setSpacing(4)

        self.row_disc = FunnelStepRow("Discovered", 0, 1, COLORS['text_muted'])
        self.row_qual = FunnelStepRow("Qualified", 0, 1, COLORS['primary'])
        self.row_appl = FunnelStepRow("Applied", 0, 1, COLORS.get('secondary', '#60A5FA'))
        self.row_resp = FunnelStepRow("Responses", 0, 1, COLORS['warning'])
        self.row_intv = FunnelStepRow("Interviews", 0, 1, COLORS.get('purple', '#C084FC'))
        self.row_offr = FunnelStepRow("Offers", 0, 1, COLORS['success'])

        self.funnel_rows_container.addWidget(self.row_disc)
        self.funnel_rows_container.addWidget(self.row_qual)
        self.funnel_rows_container.addWidget(self.row_appl)
        self.funnel_rows_container.addWidget(self.row_resp)
        self.funnel_rows_container.addWidget(self.row_intv)
        self.funnel_rows_container.addWidget(self.row_offr)

        layout.addLayout(self.funnel_rows_container)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"border: none; border-bottom: 1px solid {COLORS['border_subtle']};")
        layout.addWidget(divider)

        # 3. Platform Visual Analytics Section
        plat_hdr = QHBoxLayout()
        lbl_plat_title = QLabel("PLATFORM ANALYTICS")
        lbl_plat_title.setStyleSheet(f"font-size: 11px; font-weight: 800; letter-spacing: 0.5px; color: {COLORS['text_muted']};")
        plat_hdr.addWidget(lbl_plat_title)
        plat_hdr.addStretch(1)

        # Chart view switcher
        switcher_frame = QFrame()
        switcher_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 6px;
            }}
        """)
        sw_layout = QHBoxLayout(switcher_frame)
        sw_layout.setContentsMargins(2, 2, 2, 2)
        sw_layout.setSpacing(2)

        self.btn_view_bars = QPushButton("📊 Bars")
        self.btn_view_donut = QPushButton("🍩 Share")
        for b in (self.btn_view_bars, self.btn_view_donut):
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 600;
                }}
                QPushButton:checked {{
                    background-color: {COLORS['primary']};
                    color: white;
                    font-weight: 700;
                }}
                QPushButton:hover:!checked {{
                    background-color: {COLORS['surface_hover']};
                    color: {COLORS['text']};
                }}
            """)
        self.btn_view_bars.setChecked(True)
        self.btn_view_bars.clicked.connect(lambda: self._set_chart_view(0))
        self.btn_view_donut.clicked.connect(lambda: self._set_chart_view(1))

        sw_layout.addWidget(self.btn_view_bars)
        sw_layout.addWidget(self.btn_view_donut)
        plat_hdr.addWidget(switcher_frame)
        layout.addLayout(plat_hdr)

        # Stacked Visualizations (Bars vs Donut Share)
        self.stacked_charts = QStackedWidget()
        self.stacked_charts.setFixedHeight(185)

        # View 0: Horizontal Performance Bars
        self.bars_container_widget = QWidget()
        self.bars_layout = QVBoxLayout(self.bars_container_widget)
        self.bars_layout.setContentsMargins(0, 2, 0, 2)
        self.bars_layout.setSpacing(4)
        self.stacked_charts.addWidget(self.bars_container_widget)

        # View 1: Donut Share Chart + Legend
        self.donut_container_widget = QWidget()
        donut_h_layout = QHBoxLayout(self.donut_container_widget)
        donut_h_layout.setContentsMargins(0, 0, 0, 0)
        donut_h_layout.setSpacing(12)

        self.donut_canvas = DonutChartCanvas(self.donut_container_widget)
        self.donut_canvas.setFixedSize(160, 160)
        donut_h_layout.addWidget(self.donut_canvas)

        self.donut_legend_layout = QVBoxLayout()
        self.donut_legend_layout.setContentsMargins(0, 8, 0, 8)
        self.donut_legend_layout.setSpacing(4)
        donut_h_layout.addLayout(self.donut_legend_layout, 1)

        self.stacked_charts.addWidget(self.donut_container_widget)
        layout.addWidget(self.stacked_charts)

    def _set_chart_view(self, index: int) -> None:
        self.stacked_charts.setCurrentIndex(index)
        self.btn_view_bars.setChecked(index == 0)
        self.btn_view_donut.setChecked(index == 1)

    def _on_preset_clicked(self, key: str) -> None:
        if self.active_preset != key:
            self.active_preset = key
            self._update_preset_styles()
            self.preset_changed.emit(key)

    def _update_preset_styles(self) -> None:
        for key, btn in self._preset_buttons.items():
            if key == self.active_preset:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['primary_subtle']};
                        color: {COLORS['primary']};
                        border: 1px solid {COLORS['primary']}50;
                        font-size: 11px;
                        font-weight: 700;
                        padding: 3px 10px;
                        border-radius: 5px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['surface_alt']};
                        color: {COLORS['text_muted']};
                        border: 1px solid {COLORS['border_subtle']};
                        font-size: 11px;
                        font-weight: 600;
                        padding: 3px 10px;
                        border-radius: 5px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['surface_hover']};
                        color: {COLORS['text']};
                    }}
                """)

    def set_performance(self, perf: SearchPerformanceDTO) -> None:
        """Binds SearchPerformanceDTO to funnel bars and platform visual analytics."""
        # 1. Update Funnel
        baseline = max(1, perf.total_discovered)
        self.row_disc.set_data(perf.total_discovered, baseline)
        self.row_qual.set_data(perf.total_qualified, baseline)
        self.row_appl.set_data(perf.total_applied, baseline)
        self.row_resp.set_data(perf.total_responses, baseline)
        self.row_intv.set_data(perf.total_interviews, baseline)
        self.row_offr.set_data(perf.total_offers, baseline)

        self.lbl_total_applied.setText(f"{perf.total_applied} Applied")

        # 2. Update Performance Bars
        while self.bars_layout.count():
            item = self.bars_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        platforms = perf.platform_metrics or []
        max_disc = max((p.discovered_count for p in platforms), default=1)
        max_appl = max((p.applied_count for p in platforms), default=1)

        donut_slices = []
        for p in platforms:
            bar_row = PlatformMetricBarRow(p, max_discovered=max_appl)
            self.bars_layout.addWidget(bar_row)

            # Build donut slice if applied > 0
            if p.applied_count > 0:
                p_key = (p.platform_key or "").lower()
                donut_slices.append({
                    "fraction": p.applied_count / max(1, perf.total_applied),
                    "color": PLATFORM_COLORS.get(p_key, COLORS.get("primary", "#FF5F15")),
                    "name": p.platform_name or p_key.title(),
                    "count": p.applied_count,
                })

        self.bars_layout.addStretch(1)

        # 3. Update Donut Chart & Legend
        while self.donut_legend_layout.count():
            item = self.donut_legend_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        self.donut_canvas.set_data(donut_slices, total_jobs=perf.total_applied)

        for s in donut_slices:
            leg_row = QHBoxLayout()
            leg_row.setSpacing(6)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: {s['color']}; font-size: 11px; background: transparent; border: none;")
            leg_row.addWidget(dot)

            name_lbl = QLabel(s["name"])
            name_lbl.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            leg_row.addWidget(name_lbl)
            leg_row.addStretch(1)

            pct_lbl = QLabel(f"{s['count']} ({s['fraction']*100:.1f}%)")
            pct_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            leg_row.addWidget(pct_lbl)

            container = QWidget()
            container.setLayout(leg_row)
            self.donut_legend_layout.addWidget(container)

        self.donut_legend_layout.addStretch(1)
