"""
Notification bar component for displaying temporary alert banners.
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, QTimer
from app.ui.theme import COLORS


class NotificationBar(QFrame):
    """Dismissible notification banner positioned at the top of the main viewport."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 12, 8)
        layout.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setFixedSize(24, 24)

        self.message_label = QLabel()
        self.message_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text']}; font-weight: 500;")

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS['text_muted']};
                font-size: 12px;
                font-weight: bold;
                border-radius: 11px;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.08);
                color: #FFFFFF;
            }}
        """)
        close_btn.clicked.connect(self.hide)

        layout.addWidget(self.icon_label)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(close_btn)

    def show_message(self, level: str, message: str, duration_ms: int = 4000) -> None:
        """Displays notification banner with modern dark card styling and accent stripe."""
        valid_levels = ("success", "warning", "danger", "info")
        if level not in valid_levels and message in valid_levels:
            level, message = message, level

        styles = {
            "success": (COLORS["success"], "#111A15", "#2EA04320", "✓"),
            "warning": (COLORS["warning"], "#1C1811", "#D2992220", "⚠"),
            "danger": (COLORS["danger"], "#1C1213", "#F8514920", "✕"),
            "info": (COLORS["info"], "#111822", "#388BFD20", "ℹ"),
        }
        accent_color, bg_color, badge_bg, icon = styles.get(level, styles["info"])

        self.setStyleSheet(f"""
            NotificationBar {{
                background-color: {bg_color};
                border: 1px solid #262C36;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
            }}
        """)
        self.icon_label.setText(icon)
        self.icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {badge_bg};
                color: {accent_color};
                font-size: 12px;
                font-weight: 700;
                border-radius: 12px;
            }}
        """)
        self.message_label.setText(message)
        self.setVisible(True)

        if duration_ms > 0:
            self.timer.start(duration_ms)
