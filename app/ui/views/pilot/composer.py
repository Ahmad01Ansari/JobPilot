"""Rich prompt and URL composer widget for the JobPilot AI Pilot."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QInputMethodEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from app.ui.theme import COLORS


class _ComposerTextEdit(QPlainTextEdit):
    """Custom text editor capturing Enter to submit and Shift+Enter for newlines.

    Dynamically manages placeholder visibility during speech-to-text dictation and IME pre-edit
    streaming to eliminate text overlapping and ghosting artifacts.
    """

    submit_pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._default_placeholder: str = ""
        self._has_preedit: bool = False
        self.textChanged.connect(self._on_text_changed)

    def setPlaceholderText(self, text: str) -> None:
        self._default_placeholder = text
        super().setPlaceholderText(text)

    def _update_placeholder_visibility(self) -> None:
        """Hides placeholder immediately whenever any committed or pre-edit text exists."""
        has_content = bool(self.toPlainText()) or self._has_preedit
        current_placeholder = super().placeholderText()
        if has_content and current_placeholder:
            super().setPlaceholderText("")
        elif not has_content and not current_placeholder and self._default_placeholder:
            super().setPlaceholderText(self._default_placeholder)

    def _on_text_changed(self) -> None:
        """Forces placeholder visibility update and repaints the viewport."""
        self._update_placeholder_visibility()
        self.viewport().update()

    def inputMethodEvent(self, event: QInputMethodEvent) -> None:
        """Captures streaming speech-to-text and IME dictation chunks before document commit."""
        preedit = event.preeditString()
        self._has_preedit = bool(preedit)
        self._update_placeholder_visibility()
        super().inputMethodEvent(event)
        if not preedit and not self.toPlainText():
            self._has_preedit = False
            self._update_placeholder_visibility()
        self.viewport().update()

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
                background-color: {COLORS.get('surface', '#161B22')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: none;
                font-size: 13px;
                line-height: 1.4;
                placeholder-text-color: {COLORS.get('text_dark', '#6E7681')};
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

