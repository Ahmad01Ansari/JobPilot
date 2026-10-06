"""High-performance presentation-only time series vector chart component."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


@dataclass
class TrendChartSeries:
    """Represents one plottable line/area series."""

    id: str
    label: str
    color_hex: str
    values: List[int]
    is_visible: bool = True


@dataclass
class TrendChartData:
    """Presentation contract for time series trend visualization."""

    x_labels: List[str]
    series: List[TrendChartSeries]
    empty_message: Optional[str] = None


class _TrendChartCanvas(QWidget):
    """Inner QPainter canvas for vector curves, gridlines, and crosshairs."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(180)
        self.data: Optional[TrendChartData] = None
        self.hover_index: Optional[int] = None
        self.hover_pos: Optional[QPointF] = None

    def set_chart_data(self, data: TrendChartData) -> None:
        self.data = data
        self.hover_index = None
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.data or not self.data.x_labels:
            super().mouseMoveEvent(event)
            return

        x = event.position().x()
        left_margin = 40.0
        right_margin = 20.0
        plot_width = max(1.0, self.width() - left_margin - right_margin)
        n = len(self.data.x_labels)

        if n <= 1:
            idx = 0
        else:
            rel_x = max(0.0, min(plot_width, x - left_margin))
            idx = int(round((rel_x / plot_width) * (n - 1)))
            idx = max(0, min(n - 1, idx))

        self.hover_index = idx
        self.hover_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event: Any) -> None:
        self.hover_index = None
        self.hover_pos = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event: Any) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w = self.width()
        h = self.height()

        # Canvas Background
        painter.fillRect(0, 0, w, h, QColor(COLORS["surface"]))

        if not self.data or not self.data.x_labels or not any(s.values for s in self.data.series):
            # Empty State
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.setFont(QFont("sans-serif", 11))
            msg = self.data.empty_message if (self.data and self.data.empty_message) else "No activity data in this period"
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, msg)
            return

        visible_series = [s for s in self.data.series if s.is_visible]
        if not visible_series:
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.setFont(QFont("sans-serif", 11))
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "All series toggled off")
            return

        # Margins & Dimensions
        left_m = 44.0
        right_m = 24.0
        top_m = 20.0
        bottom_m = 32.0

        plot_w = max(10.0, w - left_m - right_m)
        plot_h = max(10.0, h - top_m - bottom_m)

        # Calculate Y scale (max count across visible series)
        max_val = 0
        for s in visible_series:
            if s.values:
                max_val = max(max_val, max(s.values))
        max_val = max(5, int(max_val * 1.15))  # Ceiling buffer

        # Grid lines (4 horizontal tiers)
        grid_col = QColor(COLORS["border"])
        grid_col.setAlpha(120)
        grid_pen = QPen(grid_col)
        grid_pen.setStyle(Qt.DashLine)
        grid_pen.setWidth(1)

        text_font = QFont("sans-serif", 9)
        painter.setFont(text_font)

        for step in range(5):
            val_tier = int((max_val / 4) * step)
            y = top_m + plot_h - (val_tier / max_val) * plot_h

            painter.setPen(grid_pen)
            painter.drawLine(QPointF(left_m, y), QPointF(left_m + plot_w, y))

            # Y-axis label
            painter.setPen(QColor(COLORS["text_muted"]))
            painter.drawText(QRectF(0, y - 7, left_m - 8, 14), Qt.AlignRight | Qt.AlignVCenter, str(val_tier))

        # X-axis Labels
        n = len(self.data.x_labels)
        step_x = plot_w / max(1, n - 1) if n > 1 else plot_w / 2

        # Draw reasonable number of X labels to avoid clutter
        label_skip = max(1, n // 8)
        for i, lbl in enumerate(self.data.x_labels):
            if i % label_skip == 0 or i == n - 1:
                x = left_m + i * step_x
                painter.setPen(QColor(COLORS["text_muted"]))
                painter.drawText(QRectF(x - 30, h - bottom_m + 6, 60, 20), Qt.AlignHCenter | Qt.AlignTop, lbl)

        # Plot Series
        for s in visible_series:
            if not s.values:
                continue

            pts: List[QPointF] = []
            for i, val in enumerate(s.values):
                x = left_m + i * step_x
                y = top_m + plot_h - (val / max_val) * plot_h
                pts.append(QPointF(x, y))

            if len(pts) < 2:
                continue

            color = QColor(s.color_hex)

            # 1. Underfill Area Gradient
            fill_path = QPainterPath()
            fill_path.moveTo(pts[0].x(), top_m + plot_h)
            for pt in pts:
                fill_path.lineTo(pt)
            fill_path.lineTo(pts[-1].x(), top_m + plot_h)
            fill_path.closeSubpath()

            grad = QLinearGradient(0, top_m, 0, top_m + plot_h)
            c_top = QColor(color)
            c_top.setAlpha(35)
            c_bottom = QColor(color)
            c_bottom.setAlpha(0)
            grad.setColorAt(0.0, c_top)
            grad.setColorAt(1.0, c_bottom)

            painter.fillPath(fill_path, QBrush(grad))

            # 2. Vector Stroke Line
            stroke_path = QPainterPath()
            stroke_path.moveTo(pts[0])
            for pt in pts[1:]:
                stroke_path.lineTo(pt)

            line_pen = QPen(color)
            line_pen.setWidthF(2.0)
            line_pen.setCapStyle(Qt.RoundCap)
            line_pen.setJoinStyle(Qt.RoundJoin)
            painter.strokePath(stroke_path, line_pen)

        # Hover Crosshair & Tooltip Card
        if self.hover_index is not None and 0 <= self.hover_index < n:
            hx = left_m + self.hover_index * step_x

            # Vertical guide line
            crosshair_pen = QPen(QColor(COLORS["text_muted"]))
            crosshair_pen.setStyle(Qt.DotLine)
            crosshair_pen.setWidth(1)
            painter.setPen(crosshair_pen)
            painter.drawLine(QPointF(hx, top_m), QPointF(hx, top_m + plot_h))

            # Dots at intersections
            for s in visible_series:
                if self.hover_index < len(s.values):
                    val = s.values[self.hover_index]
                    hy = top_m + plot_h - (val / max_val) * plot_h
                    painter.setBrush(QColor(s.color_hex))
                    painter.setPen(QPen(QColor(COLORS["surface"]), 2))
                    painter.drawEllipse(QPointF(hx, hy), 4.5, 4.5)

            # Tooltip Card Box
            date_str = self.data.x_labels[self.hover_index]
            lines = [f"{date_str}:"]
            for s in visible_series:
                if self.hover_index < len(s.values):
                    lines.append(f"{s.label}: {s.values[self.hover_index]}")

            card_w = 140.0
            card_h = 18.0 + len(lines) * 14.0
            card_x = min(w - card_w - 10, max(10, hx + 10))
            card_y = top_m + 10

            painter.setBrush(QColor(COLORS["surface_elevated"]))
            painter.setPen(QPen(QColor(COLORS["border"]), 1))
            painter.drawRoundedRect(QRectF(card_x, card_y, card_w, card_h), 6, 6)

            painter.setPen(QColor(COLORS["text"]))
            painter.setFont(QFont("sans-serif", 9, QFont.Bold))
            painter.drawText(QRectF(card_x + 8, card_y + 4, card_w - 16, 16), Qt.AlignLeft, date_str)

            painter.setFont(QFont("sans-serif", 9))
            for i, s in enumerate(visible_series):
                if self.hover_index < len(s.values):
                    v = s.values[self.hover_index]
                    painter.setPen(QColor(s.color_hex))
                    painter.drawText(QRectF(card_x + 8, card_y + 22 + i * 15, card_w - 16, 14), Qt.AlignLeft, f"{s.label}: {v}")


class AnalyticsTrendChart(QFrame):
    """Wrapper widget with header series toggles and the vector canvas."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.data: Optional[TrendChartData] = None
        self._toggle_buttons: Dict[str, QPushButton] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AnalyticsTrendChart {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header with Title and Series Toggles
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_title = QLabel("Application Activity Trend")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        self.toggles_container = QHBoxLayout()
        self.toggles_container.setSpacing(6)
        header_row.addLayout(self.toggles_container)
        layout.addLayout(header_row)

        # Canvas
        self.canvas = _TrendChartCanvas(self)
        layout.addWidget(self.canvas)

    def update_chart(self, chart_dict: Dict[str, Any]) -> None:
        """Transforms pre-aggregated service dictionary into TrendChartData and updates canvas."""
        x_labels = chart_dict.get("x_labels", [])
        raw_series = chart_dict.get("series", [])

        series_list: List[TrendChartSeries] = []
        for s in raw_series:
            s_id = s.get("id", "")
            # Preserve current visibility if toggle exists
            is_vis = self._toggle_buttons[s_id].isChecked() if s_id in self._toggle_buttons else True
            series_list.append(TrendChartSeries(
                id=s_id,
                label=s.get("label", ""),
                color_hex=s.get("color_hex", "#FF5F15"),
                values=s.get("values", []),
                is_visible=is_vis,
            ))

        self.data = TrendChartData(x_labels=x_labels, series=series_list)
        self._render_toggle_buttons()
        self.canvas.set_chart_data(self.data)

    def _render_toggle_buttons(self) -> None:
        if not self.data:
            return

        # Clear existing buttons
        while self.toggles_container.count():
            item = self.toggles_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._toggle_buttons.clear()

        for s in self.data.series:
            btn = QPushButton(f"● {s.label}")
            btn.setCheckable(True)
            btn.setChecked(s.is_visible)
            btn.setFixedHeight(24)
            btn.setStyleSheet(self._button_style(s.color_hex, s.is_visible))
            btn.clicked.connect(lambda checked=False, sid=s.id: self._on_toggle_clicked(sid))
            self.toggles_container.addWidget(btn)
            self._toggle_buttons[s.id] = btn

    def _button_style(self, color_hex: str, is_active: bool) -> str:
        if is_active:
            return f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {color_hex};
                    border: 1px solid {color_hex}80;
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 10px;
                    font-weight: 700;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                border-color: {COLORS['border_light']};
            }}
        """

    def _on_toggle_clicked(self, series_id: str) -> None:
        if not self.data:
            return
        for s in self.data.series:
            if s.id == series_id:
                s.is_visible = not s.is_visible
                btn = self._toggle_buttons.get(series_id)
                if btn:
                    btn.setChecked(s.is_visible)
                    btn.setStyleSheet(self._button_style(s.color_hex, s.is_visible))
                break
        self.canvas.update()
