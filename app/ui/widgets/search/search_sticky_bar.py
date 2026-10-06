"""Polished, compact Sticky Save Bar with dirty-state indicator and primary CTA."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.ui.theme import COLORS


class SearchStickyBar(QFrame):
    """Subtle, docked bottom bar providing Save/Reset actions and dirty state tracking."""

    save_clicked = Signal()
    reset_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_dirty = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchStickyBar")
        self.setFixedHeight(48)
        self.setStyleSheet(f"""
            #searchStickyBar {{
                background-color: {COLORS['surface_elevated']};
                border-top: 1px solid {COLORS['border']}60;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(12)

        # Dirty State Status Indicator
        self.lbl_status = QLabel("Strategy saved ✓")
        self.lbl_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

        # Reset Changes Button
        self.btn_reset = QPushButton("Reset Changes")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setFixedHeight(32)
        self.btn_reset.setEnabled(False)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover:enabled {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']}80;
                border-color: {COLORS['border']}60;
            }}
        """)
        self.btn_reset.clicked.connect(self.reset_clicked.emit)
        layout.addWidget(self.btn_reset)

        # Save Strategy Button (Primary Brand CTA)
        self.btn_save = QPushButton("Save Strategy")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setFixedHeight(32)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 4px 20px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_save.clicked.connect(self.save_clicked.emit)
        layout.addWidget(self.btn_save)

    def set_dirty(self, dirty: bool) -> None:
        """Updates the dirty state indicator."""
        self._is_dirty = dirty
        if dirty:
            self.lbl_status.setText("● Unsaved changes")
            self.lbl_status.setStyleSheet(f"color: {COLORS['warning']}; font-size: 12px; font-weight: 700;")
            self.btn_reset.setEnabled(True)
        else:
            self.lbl_status.setText("Strategy saved ✓")
            self.lbl_status.setStyleSheet(f"color: {COLORS['success']}; font-size: 12px; font-weight: 600;")
            self.btn_reset.setEnabled(False)
