"""Reusable exact-record filter banner chip widget for isolating single records in data tables."""

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


class ExactFilterChip(QFrame):
    """Notification and filter banner indicating that the current view is isolated to a single record.

    Allows the user to exit exact-record mode and restore their full table/view state by clicking '✕ Clear'.
    """

    clear_requested = Signal()

    def __init__(
        self,
        entity_name: str = "",
        entity_id: Optional[int] = None,
        category: str = "Record",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._setup_ui()
        if entity_name:
            self.set_record(entity_name, entity_id, category)
        self.setVisible(False)

    def _setup_ui(self) -> None:
        self.setObjectName("ExactFilterChip")
        self.setFixedHeight(34)
        self.setStyleSheet(f"""
            #ExactFilterChip {{
                background-color: {COLORS['surface_elevated']};
                border: 1px solid {COLORS['primary']}80;
                border-left: 3px solid {COLORS['primary']};
                border-radius: 6px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # Icon / Target indicator
        lbl_target = QLabel("🎯")
        lbl_target.setStyleSheet("font-size: 13px; background: transparent; border: none;")
        layout.addWidget(lbl_target)

        # Content Label
        self.lbl_text = QLabel("Filtered to exact record")
        self.lbl_text.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 500;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(self.lbl_text, 1)

        # Clear Button
        self.btn_clear = QPushButton("✕ Clear Filter")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setToolTip("Exit exact record isolation and restore previous view filters")
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['primary']};
                font-size: 11px;
                font-weight: 700;
                border: 1px solid {COLORS['primary']}50;
                border-radius: 4px;
                padding: 3px 10px;
                margin: 0px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_clear.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self.btn_clear)

    def set_record(self, entity_name: str, entity_id: Optional[int] = None, category: str = "Record") -> None:
        """Sets the active record metadata and displays the banner."""
        id_str = f" #{entity_id}" if entity_id is not None else ""
        self.lbl_text.setText(f"Filtered to exact {category}: <b style='color: #FFFFFF;'>{entity_name}</b>{id_str}")
        self.setVisible(True)

    def clear(self) -> None:
        """Hides the banner."""
        self.setVisible(False)
