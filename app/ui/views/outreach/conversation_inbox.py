"""Conversation Inbox — Modern, responsive conversation card list.

Left panel of the 3-zone Outreach Center workspace.
Features:
  - Modern card hierarchy (Company, Role/Recruiter, Status Pill, Sanitized Snippet)
  - Responsive ElidedLabel for clean ellipsis truncation on resize
  - Elimination of vertical text clipping / half-cut lines from raw newlines
  - Modern Safety Orange active indicators and refined dark canvas aesthetics
  - Quick filter tabs (All, Unread, Starred) with count badges
  - Real-time debounced search bar
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.outreach_viewmodels import (
    OutreachConversationViewModel,
    PresentationConversationState,
)
from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.Outreach.ConversationInbox")

# State → (pill color, pill label)
_STATE_PILL_MAP = {
    PresentationConversationState.NEEDS_ACTION: (COLORS["danger"], "Action"),
    PresentationConversationState.WAITING: (COLORS["warning"], "Waiting"),
    PresentationConversationState.FOLLOW_UP_DUE: (COLORS["accent"], "Due"),
    PresentationConversationState.REPLIED: (COLORS["info"], "Replied"),
    PresentationConversationState.SCHEDULED: (COLORS["purple"], "Scheduled"),
    PresentationConversationState.PAUSED: (COLORS["text_muted"], "Paused"),
    PresentationConversationState.COMPLETED: (COLORS["success"], "Closed"),
    PresentationConversationState.NEEDS_REVIEW: (COLORS["warning"], "Review"),
}


def _relative_time(dt: Optional[datetime]) -> str:
    """Formats a datetime into a human-readable relative string."""
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "now"
    if seconds < 3600:
        mins = int(seconds // 60)
        return f"{mins}m ago"
    if seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours}h ago"
    days = int(seconds // 86400)
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d")


class ElidedLabel(QLabel):
    """A QLabel that automatically elides text with an ellipsis (...) when horizontal space is constrained."""

    def __init__(self, text: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._full_text = text or ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(10)
        self._update_elided_text()

    def setText(self, text: str):
        self._full_text = text or ""
        if len(self._full_text) > 25:
            self.setToolTip(self._full_text)
        else:
            self.setToolTip("")
        self._update_elided_text()

    def fullText(self) -> str:
        return self._full_text

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self):
        w = max(self.width(), 10)
        metrics = self.fontMetrics()
        elided = metrics.elidedText(self._full_text, Qt.TextElideMode.ElideRight, w)
        super().setText(elided)


class ConversationCard(QFrame):
    """Modern conversation entry with distinct hierarchy, auto-elision, and no vertical clipping."""

    clicked = Signal(int)  # emits application_id
    priority_toggled = Signal(int)  # emits application_id
    mark_read_requested = Signal(int, bool)  # emits (application_id, is_read)

    def __init__(
        self,
        vm: OutreachConversationViewModel,
        is_selected: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._app_id = vm.application_id
        self._vm = vm
        self._is_selected = is_selected
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(94)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        # -------------------------------------------------------------
        # Row 1: (Unread Dot) · Company Name · [Stretch] · Time · Star
        # -------------------------------------------------------------
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(6)

        if vm.unread_count > 0:
            self._unread_dot = QLabel("●")
            self._unread_dot.setStyleSheet(f"font-size: 10px; color: {COLORS['info']}; background: transparent; border: none;")
            self._unread_dot.setToolTip("Unread messages")
            row1.addWidget(self._unread_dot)

        comp_name = (vm.company_name or "Unknown Company").strip()
        self._company_label = ElidedLabel(comp_name)
        fw = "700" if vm.unread_count > 0 else "650"
        comp_color = "#FFFFFF" if vm.unread_count > 0 else "#E6EDF3"
        self._company_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: {fw};
            color: {comp_color};
            background: transparent;
            border: none;
        """)
        row1.addWidget(self._company_label, 1)

        time_str = _relative_time(vm.last_activity_at)
        if time_str:
            time_label = QLabel(time_str)
            time_label.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['text_muted']};
                background: transparent;
                border: none;
                font-weight: 500;
            """)
            row1.addWidget(time_label)

        # Star / Priority Button
        self._star_btn = QPushButton("★" if vm.is_priority else "☆")
        self._star_btn.setFixedSize(18, 18)
        self._star_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._star_btn.setToolTip("Remove Priority Star" if vm.is_priority else "Mark as Priority")
        star_color = "#F59E0B" if vm.is_priority else "#545D68"
        self._star_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 14px;
                color: {star_color};
                padding: 0;
            }}
            QPushButton:hover {{
                color: {COLORS['primary']};
            }}
        """)
        self._star_btn.clicked.connect(self._on_star_clicked)
        row1.addWidget(self._star_btn)

        layout.addLayout(row1)

        # -------------------------------------------------------------
        # Row 2: Role Target & Recruiter · [Stretch] · Status Pill
        # -------------------------------------------------------------
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(6)

        role_parts = []
        if vm.job_title:
            role_parts.append(vm.job_title.strip())
        if vm.recruiter_name:
            role_parts.append(f"with {vm.recruiter_name.strip()}")
        role_text = " · ".join(role_parts) if role_parts else (vm.recruiter_email or "Direct Outreach")

        self._role_label = ElidedLabel(role_text)
        self._role_label.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 500;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
        """)
        row2.addWidget(self._role_label, 1)

        # State pill
        pill_color, pill_text = _STATE_PILL_MAP.get(
            vm.state, (COLORS["text_muted"], "—")
        )
        state_pill = QLabel(f"● {pill_text}")
        state_pill.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 600;
            color: {pill_color};
            padding: 2px 7px;
            border-radius: 4px;
            background: {pill_color}18;
            border: 1px solid {pill_color}33;
        """)
        row2.addWidget(state_pill)

        layout.addLayout(row2)

        # -------------------------------------------------------------
        # Row 3: Sanitized Single-Line Snippet + Draft indicator
        # -------------------------------------------------------------
        row3 = QHBoxLayout()
        row3.setContentsMargins(0, 0, 0, 0)
        row3.setSpacing(6)

        # Critical: Strip all newlines and excessive whitespace so text never wraps or slices vertically
        raw_snippet = vm.last_snippet or ""
        cleaned_snippet = " ".join(raw_snippet.split()).strip()
        if not cleaned_snippet:
            cleaned_snippet = "No messages yet"

        self._snippet_label = ElidedLabel(cleaned_snippet)
        self._snippet_label.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_dark']};
            background: transparent;
            border: none;
        """)
        row3.addWidget(self._snippet_label, 1)

        if vm.active_draft_preview:
            draft_badge = QLabel("📝 Draft")
            draft_badge.setToolTip("Unsent reply draft in progress")
            draft_badge.setStyleSheet("""
                font-size: 10px;
                font-weight: 600;
                color: #D29922;
                background: rgba(210, 153, 34, 0.15);
                border: 1px solid rgba(210, 153, 34, 0.3);
                border-radius: 3px;
                padding: 1px 5px;
            """)
            row3.addWidget(draft_badge)

        layout.addLayout(row3)

        self._apply_style()

    def _apply_style(self):
        if self._is_selected:
            self.setStyleSheet(f"""
                ConversationCard {{
                    background: #1C222C;
                    border-left: 3px solid {COLORS['primary']};
                    border-top: none;
                    border-right: none;
                    border-bottom: 1px solid #222935;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                ConversationCard {{
                    background: #12161E;
                    border-left: 3px solid transparent;
                    border-top: none;
                    border-right: none;
                    border-bottom: 1px solid #1C212A;
                }}
                ConversationCard:hover {{
                    background: #181D26;
                }}
            """)

    def _on_star_clicked(self):
        if self._app_id:
            self.priority_toggled.emit(self._app_id)

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface_elevated']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
            }}
        """)

        # Toggle Read / Unread
        is_currently_read = self._vm.unread_count == 0
        read_act_text = "Mark as Unread ✉️" if is_currently_read else "Mark as Read ✓"
        act_read = menu.addAction(read_act_text)
        act_read.triggered.connect(lambda: self.mark_read_requested.emit(self._app_id, not is_currently_read))

        # Toggle Priority
        star_act_text = "⭐ Mark as Priority" if not self._vm.is_priority else "☆ Remove Priority Star"
        act_star = menu.addAction(star_act_text)
        act_star.triggered.connect(lambda: self.priority_toggled.emit(self._app_id))

        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._app_id)
        super().mousePressEvent(event)


class ConversationInbox(QWidget):
    """Searchable, filterable list of conversation cards with read/priority tabs."""

    conversation_selected = Signal(int)  # emits application_id
    priority_toggled = Signal(int)        # emits application_id
    mark_read_requested = Signal(int, bool)  # emits (application_id, is_read)
    search_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._conversations: List[OutreachConversationViewModel] = []
        self._selected_id: Optional[int] = None
        self._active_tag_filter: str = "ALL"  # "ALL", "UNREAD", "STARRED"
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._emit_search)
        self._pending_search = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header: Modern Search Bar + Quick Filter Pills
        top_container = QWidget()
        top_container.setStyleSheet(f"""
            background: #141820;
            border-bottom: 1px solid #202632;
        """)
        top_layout = QVBoxLayout(top_container)
        top_layout.setContentsMargins(10, 10, 10, 10)
        top_layout.setSpacing(8)

        # Search Bar
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Search companies, roles, recruiters...")
        self._search_input.setFixedHeight(32)
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: #0B0E14;
                color: {COLORS['text']};
                border: 1px solid #282E3A;
                border-radius: 6px;
                padding: 0 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
                background: #0F131A;
            }}
            QLineEdit::placeholder {{
                color: #5B6574;
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_typed)
        top_layout.addWidget(self._search_input)

        # Filter Pills: Work Queue (All | Today | Waiting | Upcoming | Closed)
        pills_row = QHBoxLayout()
        pills_row.setSpacing(4)

        self._btn_filter_all = QPushButton("All")
        self._btn_filter_today = QPushButton("Today")
        self._btn_filter_waiting = QPushButton("Waiting")
        self._btn_filter_upcoming = QPushButton("Upcoming")
        self._btn_filter_closed = QPushButton("Closed")

        self._pills_list = [
            (self._btn_filter_all, "ALL"),
            (self._btn_filter_today, "TODAY"),
            (self._btn_filter_waiting, "WAITING"),
            (self._btn_filter_upcoming, "UPCOMING"),
            (self._btn_filter_closed, "CLOSED"),
        ]

        for btn, tag in self._pills_list:
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, t=tag: self._set_filter_tag(t))
            pills_row.addWidget(btn)

        pills_row.addStretch(1)

        top_layout.addLayout(pills_row)
        layout.addWidget(top_container)

        self._update_filter_pill_styles()

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: #0E1218;
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: #282E3A;
                border-radius: 3px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['primary']};
            }}
        """)

        self._cards_container = QWidget()
        self._cards_container.setStyleSheet("background: transparent;")
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(0)
        self._cards_layout.addStretch(1)

        scroll.setWidget(self._cards_container)
        layout.addWidget(scroll)

        self.setStyleSheet(f"""
            ConversationInbox {{
                background: #0E1218;
                border-right: 1px solid #202632;
            }}
        """)

    def _set_filter_tag(self, tag: str):
        self._active_tag_filter = tag
        self._update_filter_pill_styles()
        self._render_cards()

    def _update_filter_pill_styles(self):
        active_style = f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: 1px solid {COLORS['primary']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }}
        """
        inactive_style = f"""
            QPushButton {{
                background: #181D26;
                color: {COLORS['text_muted']};
                border: 1px solid #252B36;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: #202632;
                color: #FFFFFF;
                border-color: #343C4A;
            }}
        """
        for btn, tag in self._pills_list:
            btn.setStyleSheet(active_style if self._active_tag_filter == tag else inactive_style)

    def set_conversations(self, conversations: List[OutreachConversationViewModel]):
        """Replaces the card list with new data."""
        self._conversations = conversations
        self._render_cards()

    def select_conversation(self, app_id: int):
        """Programmatically selects a conversation."""
        self._selected_id = app_id
        self._render_cards()

    def _render_cards(self):
        # Clear existing cards
        while self._cards_layout.count() > 1:  # keep the bottom stretch
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Apply active tag filter and real-time search
        filtered_convs = []
        for vm in self._conversations:
            is_today = vm.state in (
                PresentationConversationState.NEEDS_ACTION,
                PresentationConversationState.FOLLOW_UP_DUE,
                PresentationConversationState.NEEDS_REVIEW,
                PresentationConversationState.REPLIED,
            )
            is_waiting = vm.state in (PresentationConversationState.WAITING, PresentationConversationState.REPLIED)
            is_upcoming = vm.state in (PresentationConversationState.SCHEDULED, PresentationConversationState.FOLLOW_UP_DUE)
            is_closed = vm.state in (PresentationConversationState.COMPLETED, PresentationConversationState.PAUSED)

            if self._active_tag_filter == "TODAY" and not is_today:
                continue
            if self._active_tag_filter == "WAITING" and not is_waiting:
                continue
            if self._active_tag_filter == "UPCOMING" and not is_upcoming:
                continue
            if self._active_tag_filter == "CLOSED" and not is_closed:
                continue
            if self._active_tag_filter == "UNREAD" and vm.unread_count == 0:
                continue
            if self._active_tag_filter == "STARRED" and not vm.is_priority:
                continue

            # Substring match if user typed something in search bar for instant 0ms response
            if self._pending_search:
                q = self._pending_search.lower()
                matched = (
                    q in (vm.company_name or "").lower() or
                    q in (vm.job_title or "").lower() or
                    q in (vm.recruiter_name or "").lower() or
                    q in (getattr(vm, "last_snippet", "") or "").lower()
                )
                if not matched:
                    continue

            filtered_convs.append(vm)

        for vm in filtered_convs:
            card = ConversationCard(
                vm=vm,
                is_selected=(vm.application_id == self._selected_id),
            )
            card.clicked.connect(self._on_card_clicked)
            card.priority_toggled.connect(self.priority_toggled.emit)
            card.mark_read_requested.connect(self.mark_read_requested.emit)
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

        if not filtered_convs:
            msg = "No unread conversations" if self._active_tag_filter == "UNREAD" else (
                "No starred conversations" if self._active_tag_filter == "STARRED" else "No conversations found"
            )
            empty = QLabel(f"📬  {msg}")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"""
                color: {COLORS['text_dark']};
                font-size: 13px;
                font-weight: 500;
                padding: 40px;
                background: transparent;
                border: none;
            """)
            self._cards_layout.insertWidget(0, empty)

    def _on_card_clicked(self, app_id: int):
        self._selected_id = app_id
        self._render_cards()
        self.conversation_selected.emit(app_id)

    def _on_search_typed(self, text: str):
        self._pending_search = text.strip()
        self._search_timer.start()

    def _emit_search(self):
        self.search_changed.emit(self._pending_search)
