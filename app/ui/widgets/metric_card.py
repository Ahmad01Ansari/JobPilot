"""Modern ATS KPI Metric Card component.

Displays a circular icon badge, title, high-contrast numeric metric, and trend indicator.
Inspired by modern SaaS / ATS dashboards.
"""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget
from app.ui.theme import COLORS


class ModernMetricCard(QFrame):
    """Sleek KPI metric card with icon badge, large metric display, and trend pill."""

    def __init__(
        self,
        title: str,
        value: str = "0",
        icon: str = "📊",
        accent_color: str = "#ff5b37",
        trend_text: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.accent_color = accent_color
        self._setup_ui(title, value, icon, trend_text)

    def _setup_ui(self, title: str, value: str, icon: str, trend_text: Optional[str]) -> None:
        from PySide6.QtWidgets import QSizePolicy
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {self.accent_color}80;
                background-color: #1C2128;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)

        # Top row: Icon circle on left + Trend/Category Pill on right
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.icon_badge = QLabel(icon)
        self.icon_badge.setFixedSize(30, 30)
        self.icon_badge.setAlignment(Qt.AlignCenter)
        self.icon_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {self.accent_color}20;
                color: {self.accent_color};
                border: 1px solid {self.accent_color}40;
                border-radius: 15px;
                font-size: 14px;
            }}
        """)
        top_row.addWidget(self.icon_badge)
        top_row.addStretch(1)

        self.lbl_trend = QLabel(trend_text or "Active")
        self.lbl_trend.setStyleSheet(f"""
            QLabel {{
                color: {self.accent_color};
                background-color: {self.accent_color}18;
                border: 1px solid {self.accent_color}30;
                border-radius: 9px;
                padding: 1px 8px;
                font-size: 10px;
                font-weight: 700;
            }}
        """)
        top_row.addWidget(self.lbl_trend)
        layout.addLayout(top_row)

        # Middle: Large Value
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("""
            QLabel {
                color: #F0F6FC;
                font-size: 24px;
                font-weight: 800;
                letter-spacing: -0.5px;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.lbl_value)

        # Bottom: Title
        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.lbl_title)

    def set_value(self, value: str, trend_text: Optional[str] = None) -> None:
        """Updates metric value and optional trend badge."""
        self.lbl_value.setText(str(value))
        if trend_text is not None:
            self.lbl_trend.setText(trend_text)
