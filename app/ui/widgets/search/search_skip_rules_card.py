"""Polished Instant Skip Rules and Description Filters card."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS
from app.ui.widgets.search.search_keyword_input import SearchKeywordInput


class SearchSkipRulesCard(QFrame):
    """Clean, unified card for title instant-skip rules and job description blacklist phrases."""

    load_rpa_clicked = Signal()
    load_standard_bad_clicked = Signal()
    rules_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("searchSkipRulesCard")
        self.setStyleSheet(f"""
            #searchSkipRulesCard {{
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
        layout.setSpacing(16)

        # 1. Instant Skip Rules Section
        self.btn_rpa_exclusions = QPushButton("+ Load RPA Exclusions")
        self.btn_rpa_exclusions.setCursor(Qt.PointingHandCursor)
        self.btn_rpa_exclusions.setToolTip("Appends web-dev, android, full-stack, mechanical, civil to instant skip keywords")
        self.btn_rpa_exclusions.setStyleSheet(self._btn_preset_style())
        self.btn_rpa_exclusions.clicked.connect(self.load_rpa_clicked.emit)

        layout.addWidget(self._build_section_header(
            title="Instant Skip Rules",
            subtitle="Jobs containing these title keywords are skipped before opening the listing (0.01s pre-filter)",
            action_btn=self.btn_rpa_exclusions,
        ))

        self.tag_negative_titles = SearchKeywordInput(
            placeholder="e.g. android, full stack, react, java, mechanical, civil...",
            badge_prefix="exclusions",
            parent=self,
        )
        self.tag_negative_titles.tags_changed.connect(lambda _: self.rules_changed.emit())
        layout.addWidget(self.tag_negative_titles)

        # 2. Description Blacklist Words Section
        self.btn_common_bad = QPushButton("+ Load Standard Blacklist")
        self.btn_common_bad.setCursor(Qt.PointingHandCursor)
        self.btn_common_bad.setToolTip("Appends US Citizen Only, Security Clearance, Polygraph, etc.")
        self.btn_common_bad.setStyleSheet(self._btn_preset_style())
        self.btn_common_bad.clicked.connect(self.load_standard_bad_clicked.emit)

        layout.addWidget(self._build_section_header(
            title="Description Filters",
            subtitle="Skip jobs after reading the description when any of these terms or phrases are detected",
            action_btn=self.btn_common_bad,
        ))

        self.tag_bad_words = SearchKeywordInput(
            placeholder="e.g. US Citizen Only, Security Clearance, Polygraph, Unpaid...",
            badge_prefix="phrases",
            parent=self,
        )
        self.tag_bad_words.tags_changed.connect(lambda _: self.rules_changed.emit())
        layout.addWidget(self.tag_bad_words)

    def _build_section_header(self, title: str, subtitle: str, action_btn: Optional[QPushButton] = None) -> QWidget:
        header_widget = QWidget()
        h_layout = QVBoxLayout(header_widget)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        top_row.addWidget(lbl_t)
        top_row.addStretch()

        if action_btn:
            top_row.addWidget(action_btn)

        h_layout.addLayout(top_row)

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        h_layout.addWidget(lbl_s)

        return header_widget

    def _btn_preset_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['accent']};
                border: none;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_alt']};
                text-decoration: underline;
            }}
        """
