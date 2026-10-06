"""Top Opportunities widget presenting qualified unapplied job listings as sleek, modern cards."""

from typing import List, Optional, Tuple
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.dashboard_dto import TopOpportunityDTO
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class OpportunityRowCard(QFrame):
    """Sleek individual card for a top qualified opportunity."""

    clicked = Signal(int)  # job_id
    action_triggered = Signal(str, dict)  # (action_type, payload)

    def minimumSizeHint(self) -> QSize:
        return QSize(460, 56)

    def __init__(self, rank: int, opp: TopOpportunityDTO, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rank = rank
        self.opp = opp
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            OpportunityRowCard {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_subtle']};
                border-radius: 8px;
            }}
            OpportunityRowCard:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # 1. Rank Badge
        lbl_rank = QLabel(f"#{self.rank}")
        lbl_rank.setFixedSize(30, 24)
        lbl_rank.setAlignment(Qt.AlignCenter)
        lbl_rank.setStyleSheet(f"""
            background-color: {COLORS['primary_subtle']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 800;
            border-radius: 5px;
            border: 1px solid {COLORS['primary']}40;
        """)
        layout.addWidget(lbl_rank, alignment=Qt.AlignVCenter)

        # 2. Main Details (Title, Company, Location, Skills, Explainability)
        details_col = QVBoxLayout()
        details_col.setContentsMargins(0, 0, 0, 0)
        details_col.setSpacing(3)

        # Title Row
        title_row = QHBoxLayout()
        title_row.setSpacing(6)

        clean_title = self.opp.title if len(self.opp.title) <= 34 else f"{self.opp.title[:32]}..."
        lbl_title = QLabel(clean_title)
        lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        title_row.addWidget(lbl_title)

        loc_str = self.opp.location or "Remote"
        clean_loc = loc_str if len(loc_str) <= 14 else f"{loc_str[:12]}..."
        comp_str = self.opp.company if len(self.opp.company) <= 18 else f"{self.opp.company[:16]}..."
        lbl_comp_loc = QLabel(f"•  {comp_str}  ({clean_loc})")
        lbl_comp_loc.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        title_row.addWidget(lbl_comp_loc)
        title_row.addStretch(1)
        details_col.addLayout(title_row)

        # Skills & Reason Row
        skills_row = QHBoxLayout()
        skills_row.setSpacing(6)

        # Matched skills (up to 3)
        matched = self.opp.matched_skills[:3]
        for s in matched:
            s_lbl = s if len(s) <= 15 else s[:13] + "…"
            pill = QLabel(f"✓ {s_lbl}")
            pill.setStyleSheet(f"""
                background-color: {COLORS['success']}18;
                color: {COLORS['success']};
                font-size: 10px;
                font-weight: 600;
                padding: 1px 6px;
                border-radius: 4px;
                border: 1px solid {COLORS['success']}30;
            """)
            skills_row.addWidget(pill)

        # Explainability snippet
        if self.opp.reasons:
            reason_text = self.opp.reasons[0]
            clean_reason = reason_text if len(reason_text) <= 34 else f"{reason_text[:31]}..."
            lbl_reason = QLabel(f"• {clean_reason}")
            lbl_reason.setStyleSheet(f"font-size: 11px; color: {COLORS['text_dark']}; background: transparent; border: none;")
            skills_row.addWidget(lbl_reason)
        elif len(self.opp.matched_skills) > 3:
            more_count = len(self.opp.matched_skills) - 3
            lbl_more = QLabel(f"+{more_count} more skills")
            lbl_more.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']}; background: transparent; border: none;")
            skills_row.addWidget(lbl_more)

        skills_row.addStretch(1)
        details_col.addLayout(skills_row)
        layout.addLayout(details_col, 1)

        # 3. Source & Match Column (Fixed width for strict tabular alignment)
        meta_widget = QWidget()
        meta_widget.setFixedWidth(110)
        meta_widget.setStyleSheet("background: transparent; border: none;")
        meta_col = QVBoxLayout(meta_widget)
        meta_col.setContentsMargins(0, 0, 0, 0)
        meta_col.setSpacing(3)
        meta_col.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Match Score Badge
        score_text = f"{self.opp.score}% Match"
        score_variant = "success" if self.opp.score >= 70 else "warning"
        lbl_score = StatusBadge(score_text, status_type=score_variant, width=95, height=20)
        meta_col.addWidget(lbl_score, alignment=Qt.AlignRight)

        # Source / Method
        method_str = "Easy Apply" if "EASY" in self.opp.application_method.upper() else "Portal"
        lbl_src = QLabel(f"{self.opp.platform.title()} • {method_str}")
        lbl_src.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; background: transparent; border: none;")
        meta_col.addWidget(lbl_src, alignment=Qt.AlignRight)

        layout.addWidget(meta_widget, alignment=Qt.AlignVCenter)

        # 4. Contextual Primary Action Button (Fixed size 110x28 for uniform column alignment)
        action_btn_text, action_type, is_urgent = self._resolve_action()
        self.btn_action = QPushButton(action_btn_text)
        self.btn_action.setFixedSize(110, 28)
        self.btn_action.setCursor(Qt.PointingHandCursor)

        if is_urgent:
            self.btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    font-weight: 700;
                    font-size: 11px;
                    border-radius: 5px;
                    border: none;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                }}
            """)
        else:
            self.btn_action.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_elevated']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    font-size: 11px;
                    font-weight: 600;
                    border-radius: 5px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                    color: {COLORS['primary']};
                }}
            """)

        self.btn_action.clicked.connect(self._on_action_clicked)
        layout.addWidget(self.btn_action, alignment=Qt.AlignVCenter)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.opp.job_id)
        super().mousePressEvent(event)

    def _resolve_action(self) -> Tuple[str, str, bool]:
        """Resolves contextual button label, action type, and visual emphasis."""
        method = (self.opp.application_method or "").upper()
        if "EASY" in method:
            return "Apply →", "NAVIGATE_JOB", True
        elif "PORTAL" in method:
            if self.opp.application_url:
                return "Open Portal ↗", "OPEN_URL", False
            return "Review →", "NAVIGATE_JOB", False
        return "Review →", "NAVIGATE_JOB", False

    def _on_action_clicked(self) -> None:
        self.clicked.emit(self.opp.job_id)
        action_btn_text, action_type, is_urgent = self._resolve_action()
        if action_type == "OPEN_URL" and self.opp.application_url:
            self.action_triggered.emit("OPEN_URL", {"url": self.opp.application_url})
        else:
            self.action_triggered.emit("NAVIGATE_JOB", {"job_id": self.opp.job_id})


class TopOpportunitiesWidget(QFrame):
    """Modern card-list presenting top qualified opportunities with rich skill explainability."""

    review_requested = Signal(int)  # job_id
    search_requested = Signal()
    action_triggered = Signal(str, dict)  # (action_type, payload)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._opportunities: List[TopOpportunityDTO] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            TopOpportunitiesWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        lbl_icon = QLabel("🎯")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        header_row.addWidget(lbl_icon, alignment=Qt.AlignVCenter)

        lbl_title = QLabel("TOP OPPORTUNITIES")
        lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.5px;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        header_row.addWidget(lbl_title, alignment=Qt.AlignVCenter)

        self.lbl_subtitle = QLabel("Ranked by Fit Score • Unapplied")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        header_row.addWidget(self.lbl_subtitle, alignment=Qt.AlignVCenter)
        header_row.addStretch(1)

        layout.addLayout(header_row)

        # Cards Container
        self.rows_container = QVBoxLayout()
        self.rows_container.setContentsMargins(0, 0, 0, 0)
        self.rows_container.setSpacing(8)
        layout.addLayout(self.rows_container)

        # Empty State Widget
        self.empty_widget = QFrame()
        self.empty_widget.setStyleSheet("background: transparent; border: none;")
        e_layout = QVBoxLayout(self.empty_widget)
        e_layout.setContentsMargins(12, 16, 12, 16)
        e_layout.setSpacing(6)
        e_layout.setAlignment(Qt.AlignCenter)

        lbl_empty_title = QLabel("No qualified unapplied opportunities yet")
        lbl_empty_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        lbl_empty_title.setAlignment(Qt.AlignCenter)

        lbl_empty_desc = QLabel("Discover new roles or run qualification to surface your highest match jobs.")
        lbl_empty_desc.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        lbl_empty_desc.setAlignment(Qt.AlignCenter)

        btn_search = QPushButton("Search Jobs →")
        btn_search.setCursor(Qt.PointingHandCursor)
        btn_search.setFixedWidth(130)
        btn_search.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['border_subtle']};
                font-size: 11px;
                font-weight: 700;
                padding: 5px 12px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        btn_search.clicked.connect(self.search_requested.emit)

        e_layout.addWidget(lbl_empty_title)
        e_layout.addWidget(lbl_empty_desc)
        e_layout.addWidget(btn_search, alignment=Qt.AlignCenter)
        layout.addWidget(self.empty_widget)
        layout.addStretch(1)

    def set_opportunities(self, opportunities: List[TopOpportunityDTO]) -> None:
        """Populates the list with high-match opportunities."""
        self._opportunities = opportunities

        # Clear existing row cards
        while self.rows_container.count():
            child = self.rows_container.takeAt(0)
            widget = child.widget()
            if widget:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        if not opportunities:
            self.empty_widget.setVisible(True)
            return

        self.empty_widget.setVisible(False)
        for idx, opp in enumerate(opportunities[:7], 1):
            row_card = OpportunityRowCard(rank=idx, opp=opp)
            row_card.clicked.connect(self.review_requested.emit)
            row_card.action_triggered.connect(self.action_triggered.emit)
            self.rows_container.addWidget(row_card)
            row_card.show()
