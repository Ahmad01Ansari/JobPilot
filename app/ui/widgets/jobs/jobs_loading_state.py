"""Skeleton / visual loading state placeholder for Jobs table."""

from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class JobsLoadingState(QFrame):
    """Clean loading state placeholder displayed while jobs are being queried."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(14)
        layout.setContentsMargins(40, 60, 40, 60)

        # Loading Spinner / Indeterminate bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # Indeterminate animation
        self.progress.setFixedHeight(4)
        self.progress.setFixedWidth(200)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['surface_alt']};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress, alignment=Qt.AlignCenter)

        # Title
        self.lbl_title = QLabel("Loading job opportunities...")
        self.lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 600;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        # Subtitle
        self.lbl_sub = QLabel("Querying your local repository and matching applications")
        self.lbl_sub.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
        """)
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sub)
