"""Welcome Banner component for Modern ATS Dashboard.

Features personalized candidate greeting, status summary, and direct action triggers.
Inspired by modern HR / ATS dashboard headers.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget
from app.ui.theme import COLORS


class WelcomeBanner(QFrame):
    """Personalized ATS command center greeting banner with direct action shortcuts."""

    start_automation_clicked = Signal()
    add_job_clicked = Signal()
    refresh_clicked = Signal()

    def __init__(
        self,
        candidate_name: str = "Candidate",
        status_summary: str = "Automation engines ready • Pipeline active",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._setup_ui(candidate_name, status_summary)

    def _setup_ui(self, candidate_name: str, status_summary: str) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 14px;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(18)

        # Left Avatar / Logo circle
        avatar_lbl = QLabel("🎯")
        avatar_lbl.setFixedSize(48, 48)
        avatar_lbl.setAlignment(Qt.AlignCenter)
        avatar_lbl.setStyleSheet("""
            QLabel {
                background-color: #FF5F1520;
                color: #FF5F15;
                border: 1px solid #FF5F1540;
                border-radius: 24px;
                font-size: 22px;
            }
        """)
        layout.addWidget(avatar_lbl)

        # Greeting & Subtitle text column
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(4)

        self.lbl_greeting = QLabel(f"Welcome Back, {candidate_name}")
        self.lbl_greeting.setStyleSheet("""
            QLabel {
                color: #F0F6FC;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: -0.3px;
                background: transparent;
                border: none;
            }
        """)
        text_col.addWidget(self.lbl_greeting)

        self.lbl_status = QLabel(status_summary)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("""
            QLabel {
                color: #8B949E;
                font-size: 12px;
                font-weight: 500;
                background: transparent;
                border: none;
            }
        """)
        text_col.addWidget(self.lbl_status)

        layout.addLayout(text_col, 1)

        # Right Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_refresh = QPushButton("🔄 Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #F0F6FC;
                border: 1px solid #333A46;
                border-radius: 8px;
                padding: 8px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #262C36;
                border-color: #FF5F15;
            }
        """)
        self.btn_refresh.clicked.connect(self.refresh_clicked.emit)
        btn_layout.addWidget(self.btn_refresh)

        self.btn_add_job = QPushButton("+ Add Job")
        self.btn_add_job.setCursor(Qt.PointingHandCursor)
        self.btn_add_job.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #F0F6FC;
                border: 1px solid #333A46;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #262C36;
                border-color: #FF5F15;
            }
        """)
        self.btn_add_job.clicked.connect(self.add_job_clicked.emit)
        btn_layout.addWidget(self.btn_add_job)

        self.btn_run = QPushButton("▶ Run Automation")
        self.btn_run.setCursor(Qt.PointingHandCursor)
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #FF5F15;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #E04F0B;
            }
        """)
        self.btn_run.clicked.connect(self.start_automation_clicked.emit)
        btn_layout.addWidget(self.btn_run)

        layout.addLayout(btn_layout)

    def set_candidate_name(self, name: str) -> None:
        self.lbl_greeting.setText(f"Welcome Back, {name}")

    def set_status_summary(self, text: str) -> None:
        self.lbl_status.setText(text)
