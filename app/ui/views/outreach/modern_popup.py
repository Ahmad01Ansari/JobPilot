"""Modern Popup & Confirmation Dialogs for Outreach & Email Flow.

Replaces standard OS QMessageBox with sleek, branded, dark-themed modal dialogs:
  - High-contrast glowing icon badges (Success ✓, Warning ⚠, Error ✕, Info ℹ, Confirm ?)
  - Clean card surface with #161B22 background, rounded corners (12px), and subtle borders
  - Formatted typography matching JobPilot design system
  - Keyboard accessible (Enter to confirm/dismiss, Escape to cancel)
  - Headless/offscreen safe for automated testing
"""

import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class ModernPopup(QDialog):
    """Sleek dark-themed modal popup for notices, alerts, and confirmations."""

    # Popup Types
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"
    CONFIRM = "confirm"

    def __init__(
        self,
        popup_type: str,
        title: str,
        message: str,
        confirm_text: str = "OK",
        cancel_text: Optional[str] = None,
        is_danger: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.popup_type = popup_type
        self.confirmed = False

        self.setWindowTitle(title)
        self.setFixedWidth(460)
        self.setModal(True)

        self._setup_ui(title, message, confirm_text, cancel_text, is_danger)

    def _setup_ui(
        self,
        title: str,
        message: str,
        confirm_text: str,
        cancel_text: Optional[str],
        is_danger: bool,
    ):
        # Base dialog styling
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        # Style mapping for badge and accent
        badge_configs = {
            self.SUCCESS: ("✓", COLORS["success"], "#2EA04322", "#2EA04355"),
            self.WARNING: ("⚠", COLORS["warning"], "#D2992222", "#D2992255"),
            self.ERROR: ("✕", COLORS["danger"], "#F8514922", "#F8514955"),
            self.INFO: ("ℹ", COLORS["info"], "#388BFD22", "#388BFD55"),
            self.CONFIRM: ("?", COLORS["primary"], "#FF5F1522", "#FF5F1555"),
        }
        icon_char, accent_color, badge_bg, badge_border = badge_configs.get(
            self.popup_type, badge_configs[self.INFO]
        )

        # Header Row: Icon Badge + Title + Optional Close
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        lbl_badge = QLabel(icon_char)
        lbl_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_badge.setFixedSize(36, 36)
        lbl_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {badge_bg};
                color: {accent_color};
                border: 1px solid {badge_border};
                border-radius: 18px;
                font-size: 16px;
                font-weight: 700;
            }}
        """)
        header_row.addWidget(lbl_badge)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"""
            QLabel {{
                color: #F0F6FC;
                font-size: 15px;
                font-weight: 700;
                background: transparent;
                border: none;
            }}
        """)
        header_row.addWidget(lbl_title, 1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 12px;
                font-weight: 700;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        header_row.addWidget(btn_close)

        layout.addLayout(header_row)

        # Message Container Card
        msg_card = QFrame()
        msg_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        msg_layout = QVBoxLayout(msg_card)
        msg_layout.setContentsMargins(12, 10, 12, 10)
        msg_layout.setSpacing(4)

        lbl_message = QLabel(message)
        lbl_message.setWordWrap(True)
        lbl_message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_message.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 13px;
                line-height: 1.45;
                background: transparent;
                border: none;
            }}
        """)
        msg_layout.addWidget(lbl_message)
        layout.addWidget(msg_card)

        # Footer Button Row
        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)
        footer_row.addStretch(1)

        if cancel_text:
            btn_cancel = QPushButton(cancel_text)
            btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_cancel.setFixedHeight(32)
            btn_cancel.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                    padding: 0 16px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                QPushButton:hover {{
                    color: {COLORS['text']};
                    background-color: {COLORS['surface_hover']};
                }}
            """)
            btn_cancel.clicked.connect(self.reject)
            footer_row.addWidget(btn_cancel)

        # Confirm / Action Button
        btn_action = QPushButton(confirm_text)
        btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_action.setFixedHeight(32)

        if is_danger:
            action_bg = COLORS["danger"]
            action_hover = "#DA3633"
        elif self.popup_type == self.SUCCESS:
            action_bg = "#238636"
            action_hover = "#2EA043"
        else:
            action_bg = COLORS["primary"]
            action_hover = COLORS["primary_hover"]

        btn_action.setStyleSheet(f"""
            QPushButton {{
                background-color: {action_bg};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 0 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {action_hover};
            }}
        """)
        btn_action.clicked.connect(self._on_confirm_clicked)
        btn_action.setDefault(True)
        footer_row.addWidget(btn_action)

        layout.addLayout(footer_row)

    def _on_confirm_clicked(self):
        self.confirmed = True
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_confirm_clicked()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    # -------------------------------------------------------------------------
    # Convenience Static Methods
    # -------------------------------------------------------------------------

    @classmethod
    def success(cls, parent: Optional[QWidget], title: str, message: str, button_text: str = "Done") -> None:
        """Displays a modern success dialog."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        dlg = cls(cls.SUCCESS, title, message, confirm_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def information(cls, parent: Optional[QWidget], title: str, message: str, button_text: str = "Got it") -> None:
        """Displays a modern informational dialog."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        dlg = cls(cls.INFO, title, message, confirm_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def warning(cls, parent: Optional[QWidget], title: str, message: str, button_text: str = "Understood") -> None:
        """Displays a modern warning dialog."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        dlg = cls(cls.WARNING, title, message, confirm_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def error(cls, parent: Optional[QWidget], title: str, message: str, button_text: str = "Dismiss") -> None:
        """Displays a modern error dialog."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return
        dlg = cls(cls.ERROR, title, message, confirm_text=button_text, parent=parent)
        dlg.exec()

    @classmethod
    def confirm(
        cls,
        parent: Optional[QWidget],
        title: str,
        message: str,
        confirm_text: str = "Yes, Continue",
        cancel_text: str = "Cancel",
        is_danger: bool = False,
    ) -> bool:
        """Displays a confirmation dialog and returns True if confirmed."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return True
        dlg = cls(
            cls.CONFIRM,
            title,
            message,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            is_danger=is_danger,
            parent=parent,
        )
        dlg.exec()
        return dlg.confirmed
