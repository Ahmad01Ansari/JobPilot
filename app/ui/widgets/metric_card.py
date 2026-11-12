"""Modern ATS KPI Metric Card component.

Displays a circular vector icon badge, title, high-contrast numeric metric, and trend indicator.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.ui.theme import COLORS
from app.ui.sidebar_icons import render_vector_pixmap

_EMOJI_TO_VECTOR_ICON = {
    "📊": "chart",
    "✉️": "mail",
    "🎯": "dashboard",
    "⚡": "lightning",
    "📅": "calendar",
    "🔍": "search",
    "✓": "check",
    "🛡️": "shield",
    "⚠️": "alert",
    "📄": "file_text",
}


class ModernMetricCard(QFrame):
    """Sleek KPI metric card with icon badge, large metric display, and trend pill."""

    def __init__(
        self,
        title: str,
        value: str = "0",
        icon: str = "chart",
        accent_color: Optional[str] = None,
        trend_text: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.accent_color = accent_color or COLORS["primary"]
        self._icon_spec = icon
        self._setup_ui(title, value, trend_text)

    def _setup_ui(self, title: str, value: str, trend_text: Optional[str]) -> None:
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)

        # Top row: Icon circle on left + Trend/Category Pill on right
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.icon_badge = QLabel()
        self.icon_badge.setFixedSize(30, 30)
        self.icon_badge.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.icon_badge)
        top_row.addStretch(1)

        self.lbl_trend = QLabel(trend_text or "Active")
        top_row.addWidget(self.lbl_trend)
        layout.addLayout(top_row)

        # Middle: Large Value
        self.lbl_value = QLabel(str(value))
        self.lbl_value.setObjectName("MetricValue")
        layout.addWidget(self.lbl_value)

        # Bottom: Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("MetricTitle")
        layout.addWidget(self.lbl_title)

        self.apply_theme()

    def apply_theme(self) -> None:
        """Applies current ThemeManager tokens to card surfaces, typography, and vector icon."""
        accent = self.accent_color
        self.setStyleSheet(f"""
            ModernMetricCard {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
            }}
            ModernMetricCard:hover {{
                border-color: {accent}80;
                background-color: {COLORS["surface_alt"]};
            }}
        """)
        self.icon_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {accent}20;
                color: {accent};
                border: 1px solid {accent}40;
                border-radius: 15px;
                font-size: 13px;
                font-weight: 700;
            }}
        """)
        vector_name = _EMOJI_TO_VECTOR_ICON.get(self._icon_spec, self._icon_spec)
        if vector_name and vector_name.isascii() and vector_name.replace("_", "").isalnum():
            self.icon_badge.setPixmap(render_vector_pixmap(vector_name, accent, 15))
        else:
            self.icon_badge.setText(self._icon_spec)

        self.lbl_trend.setStyleSheet(f"""
            QLabel {{
                color: {accent};
                background-color: {accent}18;
                border: 1px solid {accent}30;
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
        """)
        self.lbl_value.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text"]};
                font-size: 24px;
                font-weight: 800;
                letter-spacing: -0.5px;
                background: transparent;
                border: none;
            }}
        """)
        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS["text_muted"]};
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
            }}
        """)

    def set_value(self, value: str, trend_text: Optional[str] = None) -> None:
        """Updates metric value and optional trend badge."""
        self.lbl_value.setText(str(value))
        if trend_text is not None:
            self.lbl_trend.setText(trend_text)
