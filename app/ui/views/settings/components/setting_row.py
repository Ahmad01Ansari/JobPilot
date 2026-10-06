"""Standardized desktop setting row component adhering to DesignUI.md specifications."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS


class SettingRow(QFrame):
    """Clean desktop-first setting row with title & subtitle on left, interactive control on right."""

    def __init__(
        self,
        title: str,
        description: str,
        control_widget: QWidget,
        is_caution: bool = False,
        is_last: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.control_widget = control_widget
        self.is_caution = is_caution
        self.is_last = is_last
        self._setup_ui(title, description)

    def _setup_ui(self, title: str, description: str) -> None:
        self.setObjectName("SettingRow")
        bottom_border = "none" if self.is_last else f"1px solid {COLORS.get('border_subtle', '#ffffff0d')}"
        self.setStyleSheet(f"""
            QFrame#SettingRow {{
                background-color: transparent;
                border: none;
                border-bottom: {bottom_border};
                padding: 10px 4px;
            }}
            QFrame#SettingRow:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')}22;
                border-radius: 6px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(16)

        # Left Column: Title + Subtitle
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        title_prefix = "⚠️ " if self.is_caution else ""
        self.lbl_title = QLabel(f"{title_prefix}{title}")
        title_color = COLORS.get("warning", "#D29922") if self.is_caution else COLORS.get("text", "#F0F6FC")
        self.lbl_title.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {title_color};
            background: transparent;
        """)
        text_layout.addWidget(self.lbl_title)

        if description:
            self.lbl_desc = QLabel(description)
            self.lbl_desc.setWordWrap(True)
            self.lbl_desc.setStyleSheet(f"""
                font-size: 12px;
                color: {COLORS.get('text_muted', '#8B949E')};
                background: transparent;
            """)
            text_layout.addWidget(self.lbl_desc)

        layout.addLayout(text_layout, 1)

        # Right Column: Control Widget (aligned right)
        layout.addWidget(self.control_widget, 0, Qt.AlignRight | Qt.AlignVCenter)
