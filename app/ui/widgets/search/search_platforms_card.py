"""Platform selection and multi-platform synchronization card."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchPlatformsCard(QFrame):
    """Card for selecting the target platform and toggling multi-platform synchronization."""

    platform_changed = Signal(str)
    sync_all_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchPlatformsCard")
        self.setStyleSheet(f"""
            #searchPlatformsCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']}40;
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        lbl_title = QLabel("Target Platform:")
        lbl_title.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        header_row.addWidget(lbl_title)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["LinkedIn", "Naukri", "Indeed", "Glassdoor"])
        self.cmb_platform.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 140px;
                font-weight: 600;
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['accent']};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['surface_hover']};
            }}
        """)
        self.cmb_platform.currentTextChanged.connect(self._on_platform_changed)
        header_row.addWidget(self.cmb_platform)

        # Status Chips
        self.lbl_li_status = QLabel("LinkedIn: Ready")
        self.lbl_li_status.setStyleSheet(self._chip_style(True))
        header_row.addWidget(self.lbl_li_status)

        self.lbl_nk_status = QLabel("Naukri: Ready")
        self.lbl_nk_status.setStyleSheet(self._chip_style(True))
        header_row.addWidget(self.lbl_nk_status)

        header_row.addStretch()
        layout.addLayout(header_row)

        # Multi-Platform Sync Checkbox
        self.chk_apply_all_platforms = QCheckBox(
            "Use this search strategy across ALL platforms (LinkedIn, Naukri, Indeed, Glassdoor)"
        )
        self.chk_apply_all_platforms.setToolTip(
            "When checked, saving updates search keywords, locations, filters, and skip rules across all platforms."
        )
        self.chk_apply_all_platforms.setStyleSheet(f"""
            QCheckBox {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 500;
                spacing: 8px;
            }}
        """)
        self.chk_apply_all_platforms.toggled.connect(self.sync_all_toggled.emit)
        layout.addWidget(self.chk_apply_all_platforms)

    def _chip_style(self, ready: bool) -> str:
        color = COLORS['success'] if ready else COLORS['text_muted']
        bg = COLORS['success_subtle'] if ready else COLORS['surface_alt']
        return f"""
            color: {color};
            background-color: {bg};
            border: 1px solid {color}40;
            border-radius: 10px;
            padding: 2px 8px;
            font-size: 11px;
            font-weight: 600;
        """

    def _on_platform_changed(self, name: str) -> None:
        self.platform_changed.emit(name.strip().lower())
