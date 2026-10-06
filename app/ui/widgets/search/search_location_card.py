"""Location and experience constraints card with quick suggestions."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchLocationCard(QFrame):
    """Configuration card for target geographic location and experience parameters."""

    field_changed = Signal()

    QUICK_LOCATIONS = ["Bangalore", "Hyderabad", "Delhi NCR", "Pune", "Mumbai", "Remote", "India"]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchLocationCard")
        self.setStyleSheet(f"""
            #searchLocationCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']}40;
                border-radius: 8px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QLineEdit, QSpinBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Title
        lbl_title = QLabel("Location & Experience Constraints")
        lbl_title.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLORS['text']};
            letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_title)

        grid = QGridLayout()
        grid.setSpacing(12)

        # Location Field
        grid.addWidget(QLabel("Target Location:"), 0, 0)
        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("e.g. Bangalore, India or Remote")
        self.txt_location.textChanged.connect(lambda _: self.field_changed.emit())
        grid.addWidget(self.txt_location, 0, 1)

        # Experience Field
        grid.addWidget(QLabel("Max Experience:"), 0, 2)
        self.spn_experience = QSpinBox()
        self.spn_experience.setRange(-1, 30)
        self.spn_experience.setSpecialValueText("All Experiences (-1)")
        self.spn_experience.setSuffix(" Yrs")
        self.spn_experience.setValue(5)
        self.spn_experience.valueChanged.connect(lambda _: self.field_changed.emit())
        grid.addWidget(self.spn_experience, 0, 3)

        layout.addLayout(grid)

        # Quick Location Suggestions Row
        sugg_box = QHBoxLayout()
        sugg_box.setSpacing(6)
        lbl_sugg = QLabel("Quick suggestions:")
        lbl_sugg.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        sugg_box.addWidget(lbl_sugg)

        for loc in self.QUICK_LOCATIONS:
            btn = QPushButton(loc)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                    color: {COLORS['accent']};
                }}
            """)
            btn.clicked.connect(lambda _, l=loc: self._apply_location(l))
            sugg_box.addWidget(btn)

        sugg_box.addStretch()
        layout.addLayout(sugg_box)

    def _apply_location(self, loc: str) -> None:
        self.txt_location.setText(loc)
        self.field_changed.emit()
