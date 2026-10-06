"""Page header component displaying section title, subtitle, and optional action widget."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from app.ui.theme import COLORS


class PageHeader(QWidget):
    """Consistent header bar for views with title, subtitle, and action slots."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 16)
        layout.setSpacing(16)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")

        self.subtitle_label = QLabel(subtitle)
        self.subtitle_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        self.subtitle_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        if subtitle:
            text_layout.addWidget(self.subtitle_label)

        layout.addLayout(text_layout, 1)

        self.actions_layout = QHBoxLayout()
        self.actions_layout.setSpacing(10)
        self.actions_layout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(self.actions_layout, 0)

    def add_action_widget(self, widget: QWidget) -> None:
        """Add an action widget (such as a button) to the right side of the header."""
        self.actions_layout.addWidget(widget)

    def apply_theme(self) -> None:
        """Re-applies font styling with the latest dynamic COLORS."""
        self.title_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        self.subtitle_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent; border: none;")
