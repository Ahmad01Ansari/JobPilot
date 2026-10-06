"""Polished, compact tag and chip input component for keywords, exclusions, and blacklists.

Designed for modern ATS/SaaS look: zero unnecessary bounding boxes, natural content sizing,
compact chips, comma-separated pasting, deduplication, and count tracking.
"""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class SearchKeywordInput(QWidget):
    """Compact tag container displaying chips with natural flow, comma-paste parsing, and count badge."""

    tags_changed = Signal(list)

    def __init__(
        self,
        placeholder: str = "Type keyword and press Enter (or paste comma-separated)...",
        badge_prefix: str = "keywords",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.tags: List[str] = []
        self._badge_prefix = badge_prefix
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self._setup_ui(placeholder)

    def _setup_ui(self, placeholder: str) -> None:
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(6)

        # Input Row (Text line edit + Add button + Count Badge)
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self.txt_input = QLineEdit()
        self.txt_input.setPlaceholderText(placeholder)
        self.txt_input.returnPressed.connect(self._add_tag)
        self.txt_input.setFixedHeight(34)
        self.txt_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

        self.btn_add = QPushButton("+ Add")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setFixedHeight(34)
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_add.clicked.connect(self._add_tag)

        self.lbl_count = QLabel(f"0 {self._badge_prefix}")
        self.lbl_count.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 11px;
            font-weight: 600;
            padding: 4px 8px;
            background-color: {COLORS['surface_alt']};
            border-radius: 4px;
        """)

        input_row.addWidget(self.txt_input, 1)
        input_row.addWidget(self.btn_add)
        input_row.addWidget(self.lbl_count)
        self.main_layout.addLayout(input_row)

        # Tags Display Container (Lightweight, zero nested box borders)
        self.tags_frame = QWidget()
        self.tags_frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.tags_layout = QGridLayout(self.tags_frame)
        self.tags_layout.setContentsMargins(0, 4, 0, 4)
        self.tags_layout.setSpacing(6)
        self.tags_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.main_layout.addWidget(self.tags_frame)
        self._render_tags()

    def set_tags(self, tags: List[str]) -> None:
        """Sets the active list of keyword tags."""
        seen = set()
        clean = []
        for t in tags:
            s = str(t).strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                clean.append(s)
        self.tags = clean
        self._render_tags()

    def get_tags(self) -> List[str]:
        """Returns the list of current tags, flushing uncommitted text from the input."""
        val = self.txt_input.text().strip()
        if val:
            self._process_and_add_text(val)
        return list(self.tags)

    def _add_tag(self) -> None:
        val = self.txt_input.text().strip()
        if val:
            self._process_and_add_text(val)

    def _process_and_add_text(self, text: str) -> None:
        """Parses comma-separated text or single keyword and appends to tags without duplicates."""
        parts = [p.strip() for p in text.split(",") if p.strip()]
        changed = False
        existing_lower = {t.lower() for t in self.tags}

        for p in parts:
            if p.lower() not in existing_lower:
                self.tags.append(p)
                existing_lower.add(p.lower())
                changed = True

        self.txt_input.clear()
        if changed:
            self._render_tags()
            self.tags_changed.emit(list(self.tags))

    def _remove_tag(self, tag: str) -> None:
        if tag in self.tags:
            self.tags.remove(tag)
            self._render_tags()
            self.tags_changed.emit(list(self.tags))

    def clear(self) -> None:
        self.tags.clear()
        self.txt_input.clear()
        self._render_tags()
        self.tags_changed.emit([])

    def _render_tags(self) -> None:
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        count = len(self.tags)
        self.lbl_count.setText(f"{count} {self._badge_prefix}")

        if not self.tags:
            lbl_empty = QLabel(f"No {self._badge_prefix} configured.")
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-style: italic;")
            self.tags_layout.addWidget(lbl_empty, 0, 0)
            return

        # Up to 4 compact chips per row
        cols_per_row = 4
        for i, tag in enumerate(self.tags):
            row = i // cols_per_row
            col = i % cols_per_row

            pill = QFrame()
            pill.setObjectName("keywordTagPill")
            pill.setStyleSheet(f"""
                #keywordTagPill {{
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']}60;
                    border-radius: 6px;
                }}
                #keywordTagPill:hover {{
                    border-color: {COLORS['border_light']};
                    background-color: {COLORS['surface_hover']};
                }}
                QLabel {{
                    background: transparent;
                    border: none;
                }}
            """)
            pill_layout = QHBoxLayout(pill)
            pill_layout.setContentsMargins(8, 4, 6, 4)
            pill_layout.setSpacing(6)

            lbl_tag = QLabel(tag)
            lbl_tag.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: 500;")
            pill_layout.addWidget(lbl_tag)

            btn_del = QPushButton("×")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setToolTip(f"Remove '{tag}'")
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 0px 2px;
                }}
                QPushButton:hover {{
                    color: {COLORS['danger']};
                }}
            """)
            btn_del.clicked.connect(lambda _, t=tag: self._remove_tag(t))
            pill_layout.addWidget(btn_del)

            self.tags_layout.addWidget(pill, row, col)


# Backward-compatible alias
KeywordTagContainer = SearchKeywordInput
