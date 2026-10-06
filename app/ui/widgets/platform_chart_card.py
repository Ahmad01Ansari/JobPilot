"""Interactive Platform Analytics & Chart Card for ATS Dashboard.

Provides a multi-view switchable chart component allowing users to toggle between:
1. Volume Share Distribution Bars
2. Vector-painted Donut Share Chart with Legend
3. Detailed Platform Performance Cards
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


PLATFORM_COLORS = {
    "naukri": "#0284C7",   # Sky blue
    "linkedin": "#0A66C2", # LinkedIn azure
    "indeed": "#8B5CF6",   # Purple
    "foundit": "#6E00BE",  # Foundit purple
    "glassdoor": "#0CAA41", # Glassdoor green
    "manual": "#FF5F15",   # Safety orange
    "other": "#10B981",    # Emerald
}

PLATFORM_ICONS = {
    "naukri": "💼",
    "linkedin": "🔗",
    "indeed": "🔍",
    "foundit": "🎯",
    "glassdoor": "🏢",
    "manual": "✍️",
    "other": "🌐",
}


class DonutChartCanvas(QWidget):
    """Vector-painted anti-aliased Donut Chart."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.slices: List[Dict[str, Any]] = []
        self.total_jobs: int = 0
        self.setMinimumSize(150, 150)

    def set_data(self, slices: List[Dict[str, Any]], total_jobs: int) -> None:
        self.slices = slices
        self.total_jobs = total_jobs
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        side = min(w, h) - 16
        if side <= 20:
            return

        rect = QRectF((w - side) / 2, (h - side) / 2, side, side)
        thickness = max(18.0, side * 0.18)

        if not self.slices or self.total_jobs <= 0:
            # Draw placeholder empty track
            pen = QPen(QColor("#262C36"), thickness)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            inner_rect = rect.adjusted(thickness / 2, thickness / 2, -thickness / 2, -thickness / 2)
            painter.drawEllipse(inner_rect)

            painter.setPen(QColor("#8B949E"))
            font = QFont(self.font().family(), 10, QFont.Bold)
            painter.setFont(font)
            painter.drawText(rect, Qt.AlignCenter, "No Data")
            return

        # Draw slices
        inner_rect = rect.adjusted(thickness / 2, thickness / 2, -thickness / 2, -thickness / 2)
        start_angle = 90.0 * 16  # 12 o'clock start in 1/16ths of a degree

        for s in self.slices:
            span_angle = -(s["fraction"] * 360.0 * 16)
            pen = QPen(QColor(s["color"]), thickness)
            pen.setCapStyle(Qt.FlatCap)
            painter.setPen(pen)
            painter.drawArc(inner_rect, int(start_angle), int(span_angle))
            start_angle += span_angle

        # Draw center label perfectly aligned in donut hole
        center_y = rect.center().y()
        painter.setPen(QColor("#F0F6FC"))
        f_val = QFont(self.font().family(), 18, QFont.Bold)
        painter.setFont(f_val)
        val_rect = QRectF(rect.x(), center_y - 20, rect.width(), 24)
        painter.drawText(val_rect, Qt.AlignCenter, str(self.total_jobs))

        painter.setPen(QColor("#8B949E"))
        f_sub = QFont(self.font().family(), 10, QFont.Medium)
        painter.setFont(f_sub)
        sub_rect = QRectF(rect.x(), center_y + 4, rect.width(), 18)
        painter.drawText(sub_rect, Qt.AlignCenter, "Total Jobs")



class PlatformBarRow(QWidget):
    """Horizontal comparative volume bar for a platform."""

    def __init__(
        self,
        platform_name: str,
        jobs_count: int,
        apps_count: int,
        total_jobs: int,
        color: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.color = color
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 4)
        layout.setSpacing(4)

        # Header Row: Icon + Name + Percentage + Counts
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        icon = PLATFORM_ICONS.get(platform_name.lower(), "🌐")
        lbl_name = QLabel(f"{icon}  {platform_name.title()}")
        lbl_name.setStyleSheet("color: #F0F6FC; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        top_row.addWidget(lbl_name)

        pct = (jobs_count / max(1, total_jobs)) * 100.0 if total_jobs > 0 else 0.0
        lbl_pct = QLabel(f"{pct:.1f}%")
        lbl_pct.setStyleSheet(f"""
            QLabel {{
                color: {self.color};
                background-color: {self.color}20;
                border: 1px solid {self.color}40;
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
        """)
        top_row.addWidget(lbl_pct)
        top_row.addStretch(1)

        lbl_detail = QLabel(f"Jobs: {jobs_count}  •  Apps: {apps_count}")
        lbl_detail.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        top_row.addWidget(lbl_detail)
        layout.addLayout(top_row)

        # Progress bar
        self.bar = QProgressBar()
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setRange(0, 100)
        self.bar.setValue(int(pct))
        self.bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: #1C2128;
                border: 1px solid #262C36;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background-color: {self.color};
                border-radius: 3px;
            }}
        """)
        layout.addWidget(self.bar)


class PlatformChartCard(QFrame):
    """Switchable multi-chart platform distribution card."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            PlatformChartCard {
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 12px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # 1. Header with Title & Chart View Switcher
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        icon_lbl = QLabel("📊")
        icon_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        hdr.addWidget(icon_lbl)

        title_lbl = QLabel("Platform Distribution")
        title_lbl.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC; background: transparent; border: none;")
        hdr.addWidget(title_lbl)
        hdr.addStretch(1)

        # Segmented Switcher Buttons
        self.btn_group = QButtonGroup(self)
        switcher_frame = QFrame()
        switcher_frame.setStyleSheet("""
            QFrame {
                background-color: #1C2128;
                border: 1px solid #262C36;
                border-radius: 14px;
                padding: 2px;
            }
        """)
        sw_layout = QHBoxLayout(switcher_frame)
        sw_layout.setContentsMargins(2, 2, 2, 2)
        sw_layout.setSpacing(4)

        self.btn_bars = QPushButton("📊  Bars")
        self.btn_donut = QPushButton("🍩  Donut")
        self.btn_cards = QPushButton("📋  Cards")

        for idx, btn in enumerate([self.btn_bars, self.btn_donut, self.btn_cards]):
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #8B949E;
                    border: none;
                    border-radius: 11px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:checked {
                    background-color: #FF5F15;
                    color: #FFFFFF;
                    font-weight: 700;
                }
                QPushButton:hover:!checked {
                    background-color: #262C36;
                    color: #F0F6FC;
                }
            """)
            self.btn_group.addButton(btn, idx)
            sw_layout.addWidget(btn)

        self.btn_bars.setChecked(True)
        self.btn_group.idClicked.connect(self._on_switch_chart_view)
        hdr.addWidget(switcher_frame)
        main_layout.addLayout(hdr)

        # 2. Central Stacked Widget
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

        # View 0: Volume Share Bars
        self.view_bars = QWidget()
        self.layout_bars = QVBoxLayout(self.view_bars)
        self.layout_bars.setContentsMargins(0, 4, 0, 4)
        self.layout_bars.setSpacing(10)
        self.stack.addWidget(self.view_bars)

        # View 1: Donut Chart + Legend
        self.view_donut = QWidget()
        donut_layout = QHBoxLayout(self.view_donut)
        donut_layout.setContentsMargins(10, 8, 10, 8)
        donut_layout.setSpacing(24)

        self.donut_canvas = DonutChartCanvas()
        self.donut_canvas.setFixedSize(180, 180)
        donut_layout.addWidget(self.donut_canvas, 0, Qt.AlignCenter)

        self.donut_legend_layout = QVBoxLayout()
        self.donut_legend_layout.setSpacing(8)
        self.donut_legend_layout.setAlignment(Qt.AlignVCenter)
        donut_layout.addLayout(self.donut_legend_layout, 1)
        self.stack.addWidget(self.view_donut)

        # View 2: Platform Metric Cards
        self.view_cards = QWidget()
        self.layout_cards = QVBoxLayout(self.view_cards)
        self.layout_cards.setContentsMargins(0, 4, 0, 4)
        self.layout_cards.setSpacing(8)
        self.stack.addWidget(self.view_cards)

        main_layout.addWidget(self.stack, 1)

    def minimumSizeHint(self) -> QSize:
        return QSize(350, 200)

    def _on_switch_chart_view(self, view_index: int) -> None:
        self.stack.setCurrentIndex(view_index)

    def set_data(self, platform_data: Dict[str, Dict[str, int]]) -> None:
        """Populates and refreshes all chart views from live platform metrics."""
        # 1. Clear old widgets
        self._clear_layout(self.layout_bars)
        self._clear_layout(self.donut_legend_layout)
        self._clear_layout(self.layout_cards)

        total_jobs = sum(stats.get("jobs", 0) for stats in platform_data.values())

        # Sort platforms by volume descending
        sorted_plats = sorted(
            platform_data.items(),
            key=lambda x: x[1].get("jobs", 0),
            reverse=True,
        )

        slices: List[Dict[str, Any]] = []

        for plat_key, stats in sorted_plats:
            jobs = stats.get("jobs", 0)
            apps = stats.get("applications", 0)
            color = PLATFORM_COLORS.get(plat_key.lower(), PLATFORM_COLORS["other"])
            icon = PLATFORM_ICONS.get(plat_key.lower(), "🌐")

            pct = (jobs / max(1, total_jobs)) * 100.0 if total_jobs > 0 else 0.0

            if jobs > 0 and total_jobs > 0:
                slices.append({
                    "platform": plat_key,
                    "jobs": jobs,
                    "fraction": jobs / total_jobs,
                    "percent": pct,
                    "color": color,
                })

            # Populate View 0: Bars
            bar_row = PlatformBarRow(
                platform_name=plat_key,
                jobs_count=jobs,
                apps_count=apps,
                total_jobs=total_jobs,
                color=color,
            )
            self.layout_bars.addWidget(bar_row)

            # Populate View 1 Legend (Structured full-width card row)
            leg_row = QFrame()
            leg_row.setStyleSheet(f"""
                QFrame {{
                    background-color: #1C2128;
                    border: 1px solid #262C36;
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    background-color: #22272E;
                    border-color: {color}80;
                }}
            """)
            leg_l = QHBoxLayout(leg_row)
            leg_l.setContentsMargins(12, 7, 14, 7)
            leg_l.setSpacing(10)

            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent; border: none;")
            leg_l.addWidget(dot)

            name_lbl = QLabel(f"{icon}  {plat_key.title()}")
            name_lbl.setStyleSheet("color: #F0F6FC; font-size: 12px; font-weight: 700; min-width: 90px; background: transparent; border: none;")
            leg_l.addWidget(name_lbl)

            pct_lbl = QLabel(f"{pct:.1f}%")
            pct_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {color};
                    background-color: {color}20;
                    border: 1px solid {color}40;
                    border-radius: 6px;
                    padding: 2px 7px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
            leg_l.addWidget(pct_lbl)

            leg_l.addStretch(1)

            cnt_lbl = QLabel(f"{jobs} jobs  •  {apps} applied")
            cnt_lbl.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 600; background: transparent; border: none;")
            cnt_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            leg_l.addWidget(cnt_lbl)

            self.donut_legend_layout.addWidget(leg_row)

            # Populate View 2: Detailed Card
            card_row = QWidget()
            card_row.setStyleSheet("""
                QWidget {
                    background-color: #1C2128;
                    border: 1px solid #262C36;
                    border-radius: 8px;
                }
            """)
            c_l = QHBoxLayout(card_row)
            c_l.setContentsMargins(12, 8, 12, 8)
            c_l.setSpacing(10)

            c_icon = QLabel(icon)
            c_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
            c_l.addWidget(c_icon)

            c_title = QLabel(plat_key.title())
            c_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #F0F6FC; min-width: 70px; background: transparent; border: none;")
            c_l.addWidget(c_title)

            c_info = QLabel(
                f"Jobs: {jobs}   |   Apps: {apps}   |   Interviews: {stats.get('interviews', 0)}   |   Offers: {stats.get('offers', 0)}"
            )
            c_info.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500; background: transparent; border: none;")
            c_l.addWidget(c_info, 1)

            self.layout_cards.addWidget(card_row)

        self.layout_bars.addStretch(1)
        self.donut_legend_layout.addStretch(1)
        self.layout_cards.addStretch(1)

        # Update Donut Canvas
        self.donut_canvas.set_data(slices, total_jobs)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
