"""Settings header component with title, search input (Ctrl+K), dirty indicator, and action buttons."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS


class SettingsHeader(QFrame):
    """Header for SettingsView providing contextual search, dirty-state feedback, and section-scoped CTAs."""

    save_requested = Signal()
    reset_requested = Signal()
    search_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("SettingsHeader")
        self.setStyleSheet(f"""
            QFrame#SettingsHeader {{
                background-color: transparent;
                border: none;
                border-bottom: 1px solid {COLORS.get('border', '#262C36')};
                padding-bottom: 14px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(16)

        # Left Column: Title and Subtitle
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)

        lbl_title = QLabel("System Settings & Security")
        lbl_title.setStyleSheet(f"""
            font-size: 20px;
            font-weight: 700;
            color: {COLORS.get('text', '#F0F6FC')};
        """)
        text_layout.addWidget(lbl_title)

        lbl_subtitle = QLabel("Configure operational parameters, encrypted credentials, AI providers, and system backups.")
        lbl_subtitle.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS.get('text_muted', '#8B949E')};
        """)
        text_layout.addWidget(lbl_subtitle)
        layout.addLayout(text_layout, 1)

        # Middle Column: Search settings
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search settings (Ctrl+K)...")
        self.txt_search.setFixedWidth(240)
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS.get('accent', '#FF5F15')};
            }}
        """)
        self.txt_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.txt_search)

        # Keyboard Shortcuts: Ctrl+K or Ctrl+F focuses search
        shortcut_k = QShortcut(QKeySequence("Ctrl+K"), self)
        shortcut_k.activated.connect(self.focus_search)
        shortcut_f = QShortcut(QKeySequence("Ctrl+F"), self)
        shortcut_f.activated.connect(self.focus_search)

        # Right Column: Dirty State & Action Buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)

        self.lbl_dirty = QLabel("✓ All changes saved")
        self.lbl_dirty.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {COLORS.get('text_muted', '#8B949E')};")
        actions_layout.addWidget(self.lbl_dirty)

        self.btn_reset = QPushButton("Reset Section")
        self.btn_reset.setToolTip("Restore defaults for the currently active section")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
            }}
        """)
        self.btn_reset.clicked.connect(self.reset_requested.emit)
        actions_layout.addWidget(self.btn_reset)

        self.btn_save = QPushButton("Save Changes")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setEnabled(False)
        self.btn_save.setStyleSheet(self._save_btn_style(enabled=False))
        self.btn_save.clicked.connect(self.save_requested.emit)
        actions_layout.addWidget(self.btn_save)

        layout.addLayout(actions_layout)

    def focus_search(self) -> None:
        self.txt_search.setFocus()
        self.txt_search.selectAll()

    def set_dirty_state(self, is_dirty: bool) -> None:
        self.btn_save.setEnabled(is_dirty)
        self.btn_save.setStyleSheet(self._save_btn_style(enabled=is_dirty))
        if is_dirty:
            self.lbl_dirty.setText("● Unsaved changes")
            self.lbl_dirty.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('warning', '#D29922')};")
        else:
            self.lbl_dirty.setText("✓ All changes saved")
            self.lbl_dirty.setStyleSheet(f"font-size: 12px; font-weight: 500; color: {COLORS.get('text_muted', '#8B949E')};")

    def set_saving(self, is_saving: bool) -> None:
        if is_saving:
            self.btn_save.setEnabled(False)
            self.lbl_dirty.setText("Saving changes...")
            self.lbl_dirty.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

    def _save_btn_style(self, enabled: bool) -> str:
        if enabled:
            return f"""
                QPushButton {{
                    background-color: {COLORS.get('accent', '#FF5F15')};
                    border: none;
                    color: #FFFFFF;
                    padding: 6px 16px;
                    border-radius: 6px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {COLORS.get('accent_hover', '#E04F0B')};
                }}
            """
        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text_dark', '#6E7681')};
                padding: 6px 16px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 600;
            }}
        """
