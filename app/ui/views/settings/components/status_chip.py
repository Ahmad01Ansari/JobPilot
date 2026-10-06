"""Interactive status chip component for ConfigurationHealthBar and section badges."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from app.ui.theme import COLORS


class StatusChip(QFrame):
    """Clickable status chip with colored indicator dot and text label."""

    clicked = Signal(str)  # Emits target section_id

    def __init__(
        self,
        section_id: str,
        label: str,
        status: str = "neutral",  # "success", "warning", "danger", "info", "neutral"
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.section_id = section_id
        self._status = status
        self._setup_ui(label)

    def _setup_ui(self, label: str) -> None:
        self.setObjectName("StatusChip")
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        self.lbl_dot = QLabel("●")
        self.lbl_dot.setStyleSheet("font-size: 9px; background: transparent;")
        layout.addWidget(self.lbl_dot)

        self.lbl_text = QLabel(label)
        self.lbl_text.setStyleSheet("font-size: 11px; font-weight: 600; background: transparent;")
        layout.addWidget(self.lbl_text)

        self.update_status(self._status, label)

    def update_status(self, status: str, label: Optional[str] = None) -> None:
        self._status = status
        if label:
            self.lbl_text.setText(label)

        color_map = {
            "success": (COLORS.get("success", "#2EA043"), f"{COLORS.get('success', '#2EA043')}18"),
            "warning": (COLORS.get("warning", "#D29922"), f"{COLORS.get('warning', '#D29922')}18"),
            "danger": (COLORS.get("danger", "#F85149"), f"{COLORS.get('danger', '#F85149')}18"),
            "info": (COLORS.get("info", "#388BFD"), f"{COLORS.get('info', '#388BFD')}18"),
            "neutral": (COLORS.get("text_muted", "#8B949E"), f"{COLORS.get('surface_alt', '#1C2128')}"),
        }
        fg, bg = color_map.get(status, color_map["neutral"])

        self.lbl_dot.setStyleSheet(f"color: {fg}; font-size: 9px; background: transparent;")
        self.lbl_text.setStyleSheet(f"color: {fg}; font-size: 11px; font-weight: 600; background: transparent;")
        base_fg = fg[:7]
        bg_hover = f"{base_fg}33"
        border_color = f"{base_fg}44"
        self.setStyleSheet(f"""
            QFrame#StatusChip {{
                background-color: {bg};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
            QFrame#StatusChip:hover {{
                background-color: {bg_hover};
                border: 1px solid {fg};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.section_id)
        super().mousePressEvent(event)
