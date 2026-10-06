"""Empty state placeholder for the Jobs data grid."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class JobsEmptyState(QFrame):
    """Clean ATS-style empty state shown when no jobs match the active filters."""

    clear_filters_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px dashed {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 40, 40, 40)

        # Icon / Emoji
        icon_lbl = QLabel("🔍")
        icon_lbl.setStyleSheet("font-size: 36px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # Title
        title_lbl = QLabel("No Jobs Found")
        title_lbl.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        # Subtitle
        sub_lbl = QLabel(
            "No job opportunities match your active search terms or filter criteria.\n"
            "Try broadening your search or resetting filters."
        )
        sub_lbl.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS['text_muted']};
            line-height: 1.4;
            background: transparent;
            border: none;
        """)
        sub_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub_lbl)

        # Clear Filters Button
        btn_box = QHBoxLayout()
        btn_box.setAlignment(Qt.AlignCenter)

        btn_clear = QPushButton("Clear All Filters")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_clear.clicked.connect(self.clear_filters_clicked.emit)
        btn_box.addWidget(btn_clear)

        layout.addLayout(btn_box)
