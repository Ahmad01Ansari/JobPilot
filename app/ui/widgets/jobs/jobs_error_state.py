"""Error state placeholder for Jobs table."""

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


class JobsErrorState(QFrame):
    """ATS error state shown when a database or search query fails."""

    retry_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['danger_subtle']};
                border-radius: 12px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(40, 50, 40, 50)

        # Error Icon
        icon_lbl = QLabel("⚠️")
        icon_lbl.setStyleSheet("font-size: 32px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_lbl)

        # Title
        title_lbl = QLabel("Unable to Load Jobs")
        title_lbl.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {COLORS['danger']};
            background: transparent;
            border: none;
        """)
        title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_lbl)

        # Subtitle / message
        self.lbl_error = QLabel(
            "An unexpected error occurred while querying the job repository.\n"
            "Please check your database connectivity and retry."
        )
        self.lbl_error.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS['text_muted']};
            line-height: 1.4;
            background: transparent;
            border: none;
        """)
        self.lbl_error.setAlignment(Qt.AlignCenter)
        self.lbl_error.setWordWrap(True)
        layout.addWidget(self.lbl_error)

        # Retry Button
        btn_box = QHBoxLayout()
        btn_box.setAlignment(Qt.AlignCenter)

        self.btn_retry = QPushButton("Retry")
        self.btn_retry.setCursor(Qt.PointingHandCursor)
        self.btn_retry.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 24px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_retry.clicked.connect(self.retry_clicked.emit)
        btn_box.addWidget(self.btn_retry)

        layout.addLayout(btn_box)

    def set_error(self, message: str) -> None:
        """Sets the descriptive error message."""
        self.lbl_error.setText(
            f"An error occurred while loading jobs:\n{message}\n"
            "Please check system logs or retry."
        )
