"""Application-centric top applied roles and companies breakdown tables."""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class AnalyticsRoleBreakdownWidget(QWidget):
    """Two-column compact tables showing roles and companies actually applied to."""

    role_clicked = Signal(str)     # Emits role title
    company_clicked = Signal(str)  # Emits company name

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Left: Roles Table
        self.role_card = self._create_table_card(
            title="Top Applied Roles",
            subtitle="Job titles from submitted applications",
            col_name="Role Title",
        )
        self.role_table: QTableWidget = self.role_card.findChild(QTableWidget)
        self.role_table.cellClicked.connect(self._on_role_cell_clicked)
        layout.addWidget(self.role_card, 1)

        # Right: Companies Table
        self.comp_card = self._create_table_card(
            title="Top Applied Companies",
            subtitle="Employer distribution of submitted applications",
            col_name="Company",
        )
        self.comp_table: QTableWidget = self.comp_card.findChild(QTableWidget)
        self.comp_table.cellClicked.connect(self._on_comp_cell_clicked)
        layout.addWidget(self.comp_card, 1)

    def _create_table_card(self, title: str, subtitle: str, col_name: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(8)

        head = QHBoxLayout()
        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        head.addWidget(lbl_t)
        head.addStretch()

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        head.addWidget(lbl_s)
        c_layout.addLayout(head)

        tbl = QTableWidget()
        tbl.setColumnCount(2)
        tbl.setHorizontalHeaderLabels([col_name, "Applications"])
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        tbl.verticalHeader().setVisible(False)
        tbl.verticalHeader().setDefaultSectionSize(28)
        tbl.setAlternatingRowColors(True)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setSelectionMode(QTableWidget.SingleSelection)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setMinimumHeight(120)
        tbl.setMaximumHeight(220)

        tbl.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                gridline-color: transparent;
                color: {COLORS['text']};
                font-size: 11px;
            }}
            QTableWidget::item {{
                padding: 2px 8px;
                border: none;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 4px 8px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        c_layout.addWidget(tbl)
        return card

    def update_data(self, data: Dict[str, List[Dict[str, Any]]]) -> None:
        """Populates the role and company tables."""
        roles = data.get("roles", [])
        self.role_table.setRowCount(len(roles))
        calc_h_r = 28 * max(len(roles), 2) + 32
        self.role_table.setFixedHeight(min(max(calc_h_r, 120), 220))

        for row, r in enumerate(roles):
            name_item = QTableWidgetItem(r.get("title", ""))
            name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.role_table.setItem(row, 0, name_item)

            cnt_item = QTableWidgetItem(str(r.get("count", 0)))
            cnt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.role_table.setItem(row, 1, cnt_item)

        comps = data.get("companies", [])
        self.comp_table.setRowCount(len(comps))
        calc_h_c = 28 * max(len(comps), 2) + 32
        self.comp_table.setFixedHeight(min(max(calc_h_c, 120), 220))
        for row, c in enumerate(comps):
            c_name_item = QTableWidgetItem(c.get("company", ""))
            c_name_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.comp_table.setItem(row, 0, c_name_item)

            c_cnt_item = QTableWidgetItem(str(c.get("count", 0)))
            c_cnt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.comp_table.setItem(row, 1, c_cnt_item)

    def _on_role_cell_clicked(self, row: int, col: int) -> None:
        item = self.role_table.item(row, 0)
        if item and item.text():
            self.role_clicked.emit(item.text())

    def _on_comp_cell_clicked(self, row: int, col: int) -> None:
        item = self.comp_table.item(row, 0)
        if item and item.text():
            self.company_clicked.emit(item.text())
