"""Platform performance comparison table with sortable columns and click-to-filter."""

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


class _NumericTableWidgetItem(QTableWidgetItem):
    """Custom table item enabling natural numeric sorting instead of alphabetic."""

    def __init__(self, text: str, sort_value: float):
        super().__init__(text)
        self.sort_value = sort_value

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, _NumericTableWidgetItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class AnalyticsPlatformTable(QFrame):
    """Sortable comparative grid evaluating volume and conversion across platforms."""

    platform_selected = Signal(str)  # Emits platform_key: 'linkedin', 'naukri', etc.

    COLUMNS = [
        ("Platform", 110),
        ("Jobs", 75),
        ("Applications", 90),
        ("Replies", 75),
        ("Progressed", 85),
        ("Interviews", 85),
        ("Offers", 65),
        ("App Rate", 80),
        ("Response Rate", 95),
        ("Interview Rate", 95),
        ("Offer Rate", 85),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            AnalyticsPlatformTable {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        lbl_title = QLabel("Platform Performance Comparison")
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        header_row.addWidget(lbl_title)
        header_row.addStretch()

        lbl_hint = QLabel("Click row to filter analytics • Sort by any column")
        lbl_hint.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
        header_row.addWidget(lbl_hint)
        layout.addLayout(header_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(self.COLUMNS)):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.setStyleSheet(f"""
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
                padding: 4px 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
                font-weight: 700;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 10px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 6px 8px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        self.table.cellClicked.connect(self._on_cell_clicked)
        layout.addWidget(self.table)

    def update_data(self, platform_data: List[Dict[str, Any]]) -> None:
        """Populates the table with factual numbers and numeric sort items."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(platform_data))
        total_h = 36 * max(len(platform_data), 1) + 38
        self.table.setMinimumHeight(total_h)
        self.table.setMaximumHeight(total_h)

        for row_idx, item in enumerate(platform_data):
            plat_key = item.get("platform_key", "")
            plat_name = item.get("platform", "")

            # 0. Platform Name
            p_item = QTableWidgetItem(plat_name)
            p_item.setData(Qt.UserRole, plat_key)
            p_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row_idx, 0, p_item)

            # 1. Jobs
            jobs = item.get("jobs", 0)
            self.table.setItem(row_idx, 1, self._make_num_item(f"{jobs:,}", float(jobs)))

            # 2. Applications
            apps = item.get("applications", 0)
            self.table.setItem(row_idx, 2, self._make_num_item(f"{apps:,}", float(apps)))

            # 3. Direct Replies
            resp = item.get("responses", 0)
            self.table.setItem(row_idx, 3, self._make_num_item(f"{resp:,}", float(resp)))

            # 4. Progressed
            prog = item.get("progression", 0)
            self.table.setItem(row_idx, 4, self._make_num_item(f"{prog:,}", float(prog)))

            # 5. Interviews
            iv = item.get("interviews", 0)
            self.table.setItem(row_idx, 5, self._make_num_item(f"{iv:,}", float(iv)))

            # 6. Offers
            off = item.get("offers", 0)
            self.table.setItem(row_idx, 6, self._make_num_item(f"{off:,}", float(off)))

            # 7. App Rate
            app_rate = item.get("application_rate", 0.0)
            self.table.setItem(row_idx, 7, self._make_num_item(f"{app_rate}%", app_rate))

            # 8. Response Rate
            resp_rate = item.get("response_rate", 0.0)
            self.table.setItem(row_idx, 8, self._make_num_item(f"{resp_rate}%", resp_rate))

            # 9. Interview Rate
            iv_rate = item.get("interview_rate", 0.0)
            self.table.setItem(row_idx, 9, self._make_num_item(f"{iv_rate}%", iv_rate))

            # 10. Offer Rate
            off_rate = item.get("offer_rate", 0.0)
            self.table.setItem(row_idx, 10, self._make_num_item(f"{off_rate}%", off_rate))

        self.table.setSortingEnabled(True)

    def _make_num_item(self, display_text: str, sort_val: float) -> _NumericTableWidgetItem:
        item = _NumericTableWidgetItem(display_text, sort_val)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        return item

    def _on_cell_clicked(self, row: int, col: int) -> None:
        item = self.table.item(row, 0)
        if item:
            plat_key = item.data(Qt.UserRole)
            if plat_key:
                self.platform_selected.emit(plat_key)
