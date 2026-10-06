"""Modal dialog for previewing the search queue and execution rotation sequence."""

from typing import List, Optional
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchPreviewDialog(QDialog):
    """Modal displaying the simulated search sequence generated from current criteria."""

    def __init__(
        self,
        keywords: List[str],
        location: str,
        platforms: List[str],
        date_posted: str,
        easy_apply: bool,
        experience: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Search Queue Preview")
        self.resize(680, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header Info
        lbl_heading = QLabel("Search Execution Sequence")
        lbl_heading.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(lbl_heading)

        lbl_desc = QLabel(
            "Below is the exact multi-keyword search queue JobPilot will rotate through "
            "based on your active criteria."
        )
        lbl_desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(lbl_desc)

        # Sequence Table
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Order", "Platform", "Search Query", "Location", "Mode"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        table.setShowGrid(False)
        table.verticalHeader().setVisible(False)

        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 700;
                font-size: 11px;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

        # Generate rows: for each platform, for each keyword
        rows = []
        for plat in platforms:
            plat_display = "LinkedIn" if plat.lower() == "linkedin" else plat.title()
            for kw in (keywords or ["(No keywords configured)"]):
                rows.append((plat_display, kw, location or "Any", "Easy Apply" if easy_apply else "All"))

        table.setRowCount(len(rows))
        for idx, (plat, kw, loc, mode) in enumerate(rows):
            table.setItem(idx, 0, QTableWidgetItem(f"#{idx + 1}"))
            table.setItem(idx, 1, QTableWidgetItem(plat))
            table.setItem(idx, 2, QTableWidgetItem(kw))
            table.setItem(idx, 3, QTableWidgetItem(loc))
            table.setItem(idx, 4, QTableWidgetItem(mode))

        layout.addWidget(table, 1)

        # Footer Actions
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)
