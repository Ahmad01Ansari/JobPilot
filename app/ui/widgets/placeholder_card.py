"""
Placeholder card widget communicating feature roadmap status cleanly without fake data.
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from app.ui.theme import COLORS


class PlaceholderCard(QFrame):
    """Informational card displayed in placeholder views explaining roadmap milestone."""

    def __init__(
        self,
        title: str,
        description: str,
        roadmap_phase: str,
        parent=None,
    ):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS["surface"]};
                border: 1px solid {COLORS["border"]};
                border-radius: 12px;
                padding: 24px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignCenter)

        badge_label = QLabel(f"Scheduled for {roadmap_phase}")
        badge_label.setStyleSheet(f"""
            color: {COLORS["accent"]};
            background-color: {COLORS["surface_alt"]};
            border: 1px solid {COLORS["accent"]}30;
            border-radius: 6px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        badge_label.setAlignment(Qt.AlignCenter)

        h_label = QLabel(title)
        h_label.setStyleSheet(f"""
            font-size: 18px;
            font-weight: 700;
            color: {COLORS["text"]};
        """)
        h_label.setAlignment(Qt.AlignCenter)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS["text_muted"]};
            line-height: 1.5;
        """)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)

        layout.addWidget(badge_label, 0, Qt.AlignCenter)
        layout.addWidget(h_label, 0, Qt.AlignCenter)
        layout.addWidget(desc_label, 0, Qt.AlignCenter)
