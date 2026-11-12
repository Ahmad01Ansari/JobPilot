"""Full pending actions modal dialog for the Dashboard Next Best Action workflow."""

from typing import Callable, List, Optional
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.dashboard_dto import TodaysHuntItemDTO
from app.ui.theme import COLORS
from app.ui.widgets.dashboard.todays_job_hunt import ActionCard


class AllActionsDialog(QDialog):
    """Modal displaying all upcoming and pending actions across interviews, replies, follow-ups, reviews, and opportunities."""

    action_triggered = Signal(str, dict)  # (action_type, payload)

    _ACTION_NAV_MAP = {
        "PREPARE_INTERVIEW": "NAVIGATE_INTERVIEW",
        "COMPOSE_FOLLOWUP": "NAVIGATE_FOLLOWUP",
        "OPEN_CONVERSATION": "NAVIGATE_OUTREACH",
        "REVIEW_APPLICATION": "NAVIGATE_APPLICATION",
        "REVIEW_JOB": "NAVIGATE_JOB",
    }

    _CATEGORY_FILTERS = [
        ("ALL", "All Actions"),
        ("INTERVIEWS", "Interviews"),
        ("REPLIES", "Recruiter Replies"),
        ("FOLLOWUPS", "Follow-Ups"),
        ("MANUAL", "Manual Check"),
        ("OPPORTUNITIES", "Top Opportunities"),
    ]

    def __init__(
        self,
        fetch_items_fn: Callable[[], List[TodaysHuntItemDTO]],
        initial_items: Optional[List[TodaysHuntItemDTO]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._fetch_items_fn = fetch_items_fn
        self._all_items: List[TodaysHuntItemDTO] = list(initial_items or [])
        self._setup_ui()
        if initial_items is None:
            self.reload_items()
        else:
            self._render_items()

    def _setup_ui(self) -> None:
        self.setWindowTitle("All Upcoming & Pending Actions")
        self.setFixedWidth(840)
        self.setMinimumHeight(560)
        self.resize(840, 620)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("All Upcoming & Pending Actions")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLORS['text']};")
        lbl_sub = QLabel("Attend to any interview, follow-up, recruiter reply, manual check, or top opportunity in any order.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_sub)
        hdr.addLayout(title_col, 1)

        self.lbl_count = QLabel("0 actions")
        self.lbl_count.setStyleSheet(f"""
            background-color: {COLORS['primary_subtle']};
            color: {COLORS['primary']};
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 10px;
            border: 1px solid {COLORS['primary']}50;
        """)
        hdr.addWidget(self.lbl_count, alignment=Qt.AlignVCenter)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.reload_items)
        hdr.addWidget(self.btn_refresh, alignment=Qt.AlignVCenter)
        root.addLayout(hdr)

        # Filter Toolbar
        filter_bar = QFrame()
        filter_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        f_layout = QHBoxLayout(filter_bar)
        f_layout.setContentsMargins(10, 8, 10, 8)
        f_layout.setSpacing(10)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filter by company, role, or reason...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.txt_search.textChanged.connect(self._render_items)
        f_layout.addWidget(self.txt_search, 1)

        self.cmb_category = QComboBox()
        for code, label in self._CATEGORY_FILTERS:
            self.cmb_category.addItem(label, code)
        self.cmb_category.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-width: 155px;
            }}
        """)
        self.cmb_category.currentIndexChanged.connect(self._render_items)
        f_layout.addWidget(self.cmb_category)
        root.addWidget(filter_bar)

        # Scrollable Items List (strictly fixed on X-axis; Y-axis scrollable only)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                width: 8px;
                background: {COLORS['background']};
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border_light']};
                min-height: 28px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['primary']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: transparent;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
        """)

        self.list_container = QWidget()
        self.list_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.list_container.setMinimumWidth(0)
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 14, 0)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch(1)

        self.scroll.setWidget(self.list_container)
        self.scroll.viewport().installEventFilter(self)
        root.addWidget(self.scroll, 1)

        # Footer
        footer = QHBoxLayout()
        lbl_tip = QLabel("Tip: Use the options menu on any card to change stage or mark it handled without leaving this list.")
        lbl_tip.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        footer.addWidget(lbl_tip, 1)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        root.addLayout(footer)

    def eventFilter(self, obj, event) -> bool:
        """Locks inner scroll container width to viewport width so X-axis never overflows."""
        if obj is self.scroll.viewport() and event.type() == QEvent.Resize:
            self.list_container.setMaximumWidth(max(200, event.size().width()))
        return super().eventFilter(obj, event)

    def reload_items(self) -> None:
        """Reloads pending actions from DashboardService."""
        try:
            self._all_items = list(self._fetch_items_fn() or [])
        except Exception:
            self._all_items = []
        self._render_items()

    def _matches_category(self, item: TodaysHuntItemDTO, cat_code: str) -> bool:
        if cat_code == "ALL":
            return True
        if cat_code == "INTERVIEWS":
            return item.item_type in ("INTERVIEW_TODAY", "UPCOMING_INTERVIEW")
        if cat_code == "REPLIES":
            return item.item_type == "RECRUITER_REPLY"
        if cat_code == "FOLLOWUPS":
            return item.item_type in ("OVERDUE_FOLLOWUP", "FOLLOWUP_DUE_TODAY")
        if cat_code == "MANUAL":
            return item.item_type == "MANUAL_REVIEW"
        if cat_code == "OPPORTUNITIES":
            return item.item_type == "TOP_OPPORTUNITY"
        return True

    def _render_items(self) -> None:
        # Clear existing cards preserving trailing stretch
        while self.list_layout.count() > 1:
            child = self.list_layout.takeAt(0)
            w = child.widget()
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        query = self.txt_search.text().strip().lower()
        cat_code = self.cmb_category.currentData() or "ALL"

        filtered = []
        for it in self._all_items:
            if not self._matches_category(it, cat_code):
                continue
            if query:
                haystack = f"{it.title} {it.company} {it.subtitle} {it.reason}".lower()
                if query not in haystack:
                    continue
            filtered.append(it)

        total = len(self._all_items)
        shown = len(filtered)
        if cat_code == "ALL" and not query:
            self.lbl_count.setText(f"{total} action{'s' if total != 1 else ''}")
        else:
            self.lbl_count.setText(f"{shown} of {total} actions")

        if not filtered:
            empty_lbl = QLabel("No matching upcoming or pending actions.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; padding: 40px;")
            self.list_layout.insertWidget(0, empty_lbl)
            return

        for idx, item in enumerate(filtered):
            card = ActionCard(item)
            nav_action = self._ACTION_NAV_MAP.get(item.recommended_action, "NAVIGATE_JOB")
            payload = dict(item.action_payload)
            card.action_triggered.connect(self._on_card_action)
            card.btn_action.clicked.connect(
                lambda _, at=nav_action, p=payload: self._on_card_action(at, p)
            )
            self.list_layout.insertWidget(idx, card)

    def _on_card_action(self, action_type: str, payload: dict) -> None:
        if action_type in ("CHANGE_APPLICATION_STATUS", "DISMISS_ITEM"):
            self.action_triggered.emit(action_type, payload)
            self.reload_items()
        else:
            self.accept()
            self.action_triggered.emit(action_type, payload)

