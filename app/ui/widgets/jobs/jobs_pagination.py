"""Pagination controls bar for Jobs view."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.ui.theme import COLORS


class JobsPagination(QFrame):
    """Pagination and result summary bar for the jobs data grid."""

    page_changed = Signal(int)           # new_page (1-indexed)
    page_size_changed = Signal(int)      # new_page_size

    def __init__(self, parent: Optional[QWidget] = None, item_name: str = "jobs"):
        super().__init__(parent)
        self._item_name = item_name
        self._current_page = 1
        self._total_items = 0
        self._page_size = 50
        self._total_pages = 1

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(12)

        # 1. Left: Summary text
        self.lbl_summary = QLabel(f"Showing 0 of 0 {self._item_name}")
        self.lbl_summary.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.lbl_summary)

        layout.addStretch()

        # 2. Center: Page navigation controls
        self.btn_prev = QPushButton("‹  Previous")
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        self.btn_prev.setStyleSheet(self._btn_style())
        self.btn_prev.clicked.connect(self._on_prev_clicked)
        layout.addWidget(self.btn_prev)

        self.lbl_page = QLabel("Page 1 of 1")
        self.lbl_page.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.lbl_page)

        self.btn_next = QPushButton("Next  ›")
        self.btn_next.setCursor(Qt.PointingHandCursor)
        self.btn_next.setStyleSheet(self._btn_style())
        self.btn_next.clicked.connect(self._on_next_clicked)
        layout.addWidget(self.btn_next)

        layout.addStretch()

        # 3. Right: Page size selector
        lbl_size_label = QLabel("Per page:")
        lbl_size_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(lbl_size_label)

        self.cmb_page_size = QComboBox()
        self.cmb_page_size.addItems(["25", "50", "100"])
        self.cmb_page_size.setCurrentText("50")
        self.cmb_page_size.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: 500;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['surface_hover']};
            }}
        """)
        self.cmb_page_size.currentIndexChanged.connect(self._on_page_size_changed)
        layout.addWidget(self.cmb_page_size)

    def _btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']};
                border-color: {COLORS['border']};
            }}
        """

    def set_pagination(self, current_page: int, total_items: int, page_size: int) -> None:
        """Updates pagination state and UI elements."""
        self._current_page = max(1, current_page)
        self._total_items = max(0, total_items)
        self._page_size = max(1, page_size)
        self._total_pages = max(1, (self._total_items + self._page_size - 1) // self._page_size)

        if self._total_items == 0:
            self.lbl_summary.setText(f"No {self._item_name} found")
            self.lbl_page.setText("Page 0 of 0")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        start_idx = (self._current_page - 1) * self._page_size + 1
        end_idx = min(self._current_page * self._page_size, self._total_items)

        self.lbl_summary.setText(f"Showing {start_idx}–{end_idx} of {self._total_items} {self._item_name}")
        self.lbl_page.setText(f"Page {self._current_page} of {self._total_pages}")

        self.btn_prev.setEnabled(self._current_page > 1)
        self.btn_next.setEnabled(self._current_page < self._total_pages)

    def _on_prev_clicked(self) -> None:
        if self._current_page > 1:
            self.page_changed.emit(self._current_page - 1)

    def _on_next_clicked(self) -> None:
        if self._current_page < self._total_pages:
            self.page_changed.emit(self._current_page + 1)

    def _on_page_size_changed(self) -> None:
        try:
            size = int(self.cmb_page_size.currentText())
            self.page_size_changed.emit(size)
        except ValueError:
            pass
