"""Rich prompt and URL composer widget for the JobPilot AI Pilot."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import COLORS


class _ComposerTextEdit(QPlainTextEdit):
    """Custom text editor capturing Enter to submit and Shift+Enter for newlines."""

    submit_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if not (event.modifiers() & Qt.ShiftModifier):
                event.accept()
                self.submit_pressed.emit()
                return
        super().keyPressEvent(event)


class PilotComposer(QFrame):
    """Bottom input bar for candidate messages, URLs, and commands."""

    message_submitted = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            PilotComposer {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 12px;
                padding: 4px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self.editor = _ComposerTextEdit()
        self.editor.setPlaceholderText("Ask the Pilot, paste a job URL, or set a rule (Enter to send, Shift+Enter for newline)...")
        self.editor.setFixedHeight(48)
        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background: transparent;
                color: {COLORS.get('text', '#F0F6FC')};
                border: none;
                font-size: 13px;
                line-height: 1.4;
            }}
        """)
        self.editor.submit_pressed.connect(self._handle_submit)
        layout.addWidget(self.editor, 1)

        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(68, 36)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('primary_hover', '#E04F0B')};
            }}
            QPushButton:disabled {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                color: {COLORS.get('text_dark', '#6E7681')};
            }}
        """)
        self.send_btn.clicked.connect(self._handle_submit)
        layout.addWidget(self.send_btn)

    def _handle_submit(self):
        text = self.editor.toPlainText().strip()
        if text:
            self.editor.clear()
            self.message_submitted.emit(text)

    def set_text(self, text: str):
        self.editor.setPlainText(text)
        self.editor.setFocus()

