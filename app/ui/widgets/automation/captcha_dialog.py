"""Interactive Human-in-the-Loop CAPTCHA Resolution Dialog for JobPilot Desktop UI."""

from typing import Callable, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
)

from app.ui.theme import COLORS


class CaptchaInterventionDialog(QDialog):
    """Human-in-the-loop dialog prompting the user to solve a browser CAPTCHA challenge."""

    resolved = Signal()

    def __init__(
        self,
        message: str = "",
        on_resolved: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.on_resolved_cb = on_resolved
        self.message_text = message or "A CAPTCHA challenge requires human verification in the browser."

        self.setWindowTitle("Action Required: CAPTCHA Verification")
        self.setFixedSize(540, 360)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # Header with Alert Icon and Title
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(14)

        icon_label = QLabel("🛡️")
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(44, 44)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('warning_subtle', '#D2992218')};
                border: 1px solid {COLORS.get('border_light', '#333A46')};
                border-radius: 10px;
                font-size: 22px;
            }}
        """)
        hdr_layout.addWidget(icon_label)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_lbl = QLabel("CAPTCHA Verification Required")
        title_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 17px;
                font-weight: 700;
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Human-in-the-Loop Intervention")
        sub_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                font-weight: 600;
                color: {COLORS.get('warning', '#D29922')};
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        title_box.addWidget(sub_lbl)
        hdr_layout.addLayout(title_box, 1)

        layout.addLayout(hdr_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLORS.get('border_light', '#21262D')}; max-height: 1px;")
        layout.addWidget(sep)

        # Instruction Card
        inst_card = QFrame()
        inst_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS.get('surface_alt', '#0D1117')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        inst_layout = QVBoxLayout(inst_card)
        inst_layout.setContentsMargins(10, 8, 10, 8)
        inst_layout.setSpacing(8)

        inst_msg = QLabel(
            "<b>1.</b> Switch to the Google Chrome window running your job application.<br>"
            "<b>2.</b> Solve the CAPTCHA (check 'I'm not a robot' or select matching images).<br>"
            "<b>3.</b> Once verified, click the button below to resume automation immediately."
        )
        inst_msg.setWordWrap(True)
        inst_msg.setStyleSheet(f"""
            QLabel {{
                font-size: 13px;
                line-height: 1.5;
                color: {COLORS.get('text_secondary', '#8B949E')};
            }}
            b {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)
        inst_layout.addWidget(inst_msg)
        layout.addWidget(inst_card)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("Skip / Cancel")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#21262D')};
                color: {COLORS.get('text_secondary', '#8B949E')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('border', '#30363D')};
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_resolved = QPushButton("✓ I Have Resolved the CAPTCHA")
        self.btn_resolved.setFixedHeight(38)
        self.btn_resolved.setCursor(Qt.PointingHandCursor)
        self.btn_resolved.setStyleSheet(f"""
            QPushButton {{
                background-color: #238636;
                color: #FFFFFF;
                border: 1px solid #2ea043;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: #2ea043;
                border-color: #3fb950;
            }}
            QPushButton:pressed {{
                background-color: #1b6528;
            }}
        """)
        self.btn_resolved.clicked.connect(self._on_resolved_clicked)
        btn_layout.addWidget(self.btn_resolved, 1)

        layout.addLayout(btn_layout)

    def _on_resolved_clicked(self) -> None:
        """Invokes resolution handler and closes dialog."""
        if callable(self.on_resolved_cb):
            self.on_resolved_cb()
        self.resolved.emit()
        self.accept()
