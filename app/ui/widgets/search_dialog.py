"""Interactive Global Search & Command Palette Modal Dialog.

Provides an asynchronous, Raycast/Linear-style command palette querying across
all 10 application entity types with deterministic ranking, category grouping,
match highlighting, and generation-tracked background workers.
"""

from dataclasses import dataclass, field
import html
import inspect
import logging
import re
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.search.global_search_service import GlobalSearchService
from app.services.search.ranking import normalize_query
from app.services.search.search_result import GlobalSearchBatch, NavigationAction, SearchResult
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge

logger = logging.getLogger(__name__)


def execute_service_search(service: Any, query: str, category: str, request_id: int = 0) -> GlobalSearchBatch:
    """Dispatches search to either GlobalSearchService or legacy SearchService."""
    try:
        sig = inspect.signature(service.search)
        if "global_limit" in sig.parameters:
            return service.search(
                query=query,
                category=category,
                limit_per_category=8,
                global_limit=50,
                request_id=request_id,
            )
        else:
            legacy = service.search(
                query=query,
                category=category,
                limit_per_category=8,
            )
            items: List[SearchResult] = []
            categories: Dict[str, List[SearchResult]] = {}
            for it in getattr(legacy, "items", []):
                res = SearchResult(
                    entity_type=it.entity_type,
                    entity_id=it.entity_id,
                    category=it.entity_type.capitalize(),
                    title=it.title,
                    subtitle=it.subtitle,
                    route=it.target_page,
                    badge_text=it.badge_text,
                    badge_variant=it.badge_type,
                    action="open",
                    metadata=it.extra_data,
                )
                items.append(res)
                cat_key = it.entity_type
                categories.setdefault(cat_key, []).append(res)
            return GlobalSearchBatch(
                query=query,
                total_count=getattr(legacy, "total_count", len(items)),
                items=items,
                categories=categories,
                request_id=request_id,
            )
    except Exception as e:
        logger.exception("Error executing service search: %s", e)
        return GlobalSearchBatch(
            query=query,
            total_count=0,
            items=[],
            categories={},
            request_id=request_id,
        )


class SearchWorker(QThread):
    """Background worker executing deterministic multi-provider search off the Qt main thread."""

    results_ready = Signal(int, object)  # (request_id, GlobalSearchBatch)
    error_occurred = Signal(int, str)

    def __init__(
        self,
        service: Any,
        query: str,
        category: str,
        request_id: int,
    ) -> None:
        super().__init__()
        self.service = service
        self.query = query
        self.category = category
        self.request_id = request_id

    def run(self) -> None:
        try:
            batch = execute_service_search(
                service=self.service,
                query=self.query,
                category=self.category,
                request_id=self.request_id,
            )
            self.results_ready.emit(self.request_id, batch)
        except Exception as e:
            logger.exception("Background search error for query '%s': %s", self.query, e)
            self.error_occurred.emit(self.request_id, str(e))


def highlight_tokens(text: str, tokens: List[str]) -> str:
    """Escapes HTML and highlights query tokens with accent styling."""
    if not text:
        return ""
    escaped = html.escape(str(text))
    if not tokens:
        return escaped

    # Build regex matching any token
    pattern = "|".join(re.escape(html.escape(t)) for t in tokens if t.strip())
    if not pattern:
        return escaped

    def replace_match(m: re.Match) -> str:
        return f'<span style="color: #FF5F15; font-weight: 700;">{m.group(0)}</span>'

    try:
        return re.sub(f"({pattern})", replace_match, escaped, flags=re.IGNORECASE)
    except Exception:
        return escaped


class SearchResultItemWidget(QWidget):
    """Custom row widget rendering a single search result card with match highlighting."""

    def __init__(
        self,
        result: SearchResult,
        tokens: List[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.result = result

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Entity Badge
        badge_text = result.badge_text or result.category or result.entity_type.capitalize()
        badge = StatusBadge(badge_text, variant=result.badge_variant)
        badge.setFixedWidth(88)
        layout.addWidget(badge)

        # Text column
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        lbl_title = QLabel()
        highlighted_title = highlight_tokens(result.title, tokens)
        lbl_title.setTextFormat(Qt.RichText)
        lbl_title.setText(highlighted_title)
        lbl_title.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {COLORS['text']};
            background: transparent;
        """)
        text_col.addWidget(lbl_title)

        lbl_sub = QLabel()
        highlighted_sub = highlight_tokens(result.subtitle, tokens)
        lbl_sub.setTextFormat(Qt.RichText)
        lbl_sub.setText(highlighted_sub)
        lbl_sub.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
            background: transparent;
        """)
        text_col.addWidget(lbl_sub)

        layout.addLayout(text_col, 1)

        # Action tag
        action_text = "Open ↵" if (result.action == "open" or result.action == NavigationAction.OPEN) else "View ↵"
        lbl_action = QLabel(action_text)
        lbl_action.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['text_muted']};
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 2px 6px;
        """)
        layout.addWidget(lbl_action)

        self.setStyleSheet("""
            SearchResultItemWidget {
                background-color: transparent;
                border-radius: 6px;
            }
        """)


class GlobalSearchDialog(QDialog):
    """Command palette style global search modal querying across all application entities."""

    # Backward-compatible signal: (target_page: str, entity_id: int)
    result_selected = Signal(str, int)
    # Full item signal: (result: SearchResult)
    result_item_selected = Signal(object)

    # Class-level recent searches cache
    _recent_searches: List[str] = []

    def __init__(
        self,
        search_service: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.search_service = search_service or GlobalSearchService()
        self.active_category: str = "all"
        self._current_results: List[SearchResult] = []
        self._list_item_map: Dict[int, SearchResult] = {}  # row -> SearchResult

        # Generation counter to prevent out-of-order async worker overwrites
        self._current_request_id: int = 0
        self._active_worker: Optional[SearchWorker] = None

        self.setWindowTitle("JobPilot Global Search (Ctrl+K)")
        self.resize(880, 580)
        self.setMinimumSize(800, 480)
        self.setWindowFlags(self.windowFlags() | Qt.Dialog)

        self._init_ui()

        # Debounce timer for search queries (150ms)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(150)
        self._debounce_timer.timeout.connect(self._trigger_search)

    def _init_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(12)

        # 1. Search Bar Container
        search_box_frame = QFrame()
        search_box_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: 4px;
            }}
        """)
        search_box_layout = QHBoxLayout(search_box_frame)
        search_box_layout.setContentsMargins(10, 4, 10, 4)
        search_box_layout.setSpacing(8)

        lbl_icon = QLabel("🔍")
        lbl_icon.setStyleSheet("font-size: 16px; background: transparent; border: none;")
        search_box_layout.addWidget(lbl_icon)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText(
            "Search jobs, applications, companies, contacts, interviews, resumes... (Esc to close)"
        )
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                color: {COLORS['text']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                outline: none;
            }}
        """)
        self.txt_search.textChanged.connect(self._on_text_changed)
        self.txt_search.returnPressed.connect(self._on_enter_pressed)
        search_box_layout.addWidget(self.txt_search, 1)

        main_layout.addWidget(search_box_frame)

        # 2. Filter Category Chips (in a smooth scroll area so all buttons show full text)
        chips_scroll = QScrollArea()
        chips_scroll.setWidgetResizable(True)
        chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        chips_scroll.setFixedHeight(44)
        chips_scroll.setFrameShape(QFrame.NoFrame)
        chips_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 3px;
                background: transparent;
            }
            QScrollBar::handle:horizontal {
                background: #333333;
                border-radius: 1px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        chips_container = QWidget()
        chips_container.setStyleSheet("background: transparent;")
        chips_layout = QHBoxLayout(chips_container)
        chips_layout.setContentsMargins(2, 2, 2, 2)
        chips_layout.setSpacing(8)

        self.cat_group = QButtonGroup(self)
        self.cat_buttons = {}

        categories = [
            ("all", "All"),
            ("jobs", "Jobs"),
            ("applications", "Applications"),
            ("companies", "Companies"),
            ("contacts", "Contacts"),
            ("interviews", "Interviews"),
            ("followups", "Follow-ups"),
            ("outreach", "Outreach"),
            ("resumes", "Resumes"),
            ("qna", "Knowledge"),
        ]

        for cat_id, cat_name in categories:
            btn = QPushButton(cat_name)
            btn.setCheckable(True)
            btn.setProperty("category_id", cat_id)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            if cat_id == "all":
                btn.setChecked(True)
            self._style_chip_button(btn)
            btn.clicked.connect(lambda checked=False, cid=cat_id: self._set_category(cid))
            self.cat_group.addButton(btn)
            self.cat_buttons[cat_id] = btn
            chips_layout.addWidget(btn)

        chips_layout.addStretch()
        chips_scroll.setWidget(chips_container)
        main_layout.addWidget(chips_scroll)

        # 3. Results List
        self.results_list = QListWidget()
        self.results_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QListWidget::item {{
                border-bottom: 1px solid {COLORS['border']}40;
                border-radius: 6px;
                margin: 2px 4px;
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['surface_hover']};
            }}
            QListWidget::item:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.results_list.itemActivated.connect(self._on_item_activated)
        self.results_list.itemClicked.connect(self._on_item_activated)
        main_layout.addWidget(self.results_list, 1)

        # 4. Footer info bar
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(4, 0, 4, 0)

        self.lbl_status = QLabel("Type at least 1 character to search")
        self.lbl_status.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        footer_layout.addWidget(self.lbl_status)

        footer_layout.addStretch()

        lbl_hints = QLabel("↑/↓ to navigate • Enter to select • Esc to close")
        lbl_hints.setStyleSheet(f"font-size: 11px; color: {COLORS['text_dark']};")
        footer_layout.addWidget(lbl_hints)

        main_layout.addLayout(footer_layout)

    def _style_chip_button(self, btn: QPushButton) -> None:
        """Applies pill styling to category chips."""
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 13px;
                padding: 4px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
            QPushButton:checked {{
                background-color: {COLORS['primary']};
                color: white;
                border-color: {COLORS['primary']};
            }}
        """)

    def _set_category(self, cat_id: str) -> None:
        """Changes the active category filter and re-executes search."""
        self.active_category = cat_id
        for cid, btn in self.cat_buttons.items():
            btn.setChecked(cid == cat_id)
        self._trigger_search()

    def _on_text_changed(self, text: str) -> None:
        """Debounces user keystrokes."""
        self._debounce_timer.start()

    def _on_enter_pressed(self) -> None:
        """Selects the currently active item on Enter key."""
        current_item = self.results_list.currentItem()
        if current_item:
            self._on_item_activated(current_item)
        elif self.results_list.count() > 0:
            for row in range(self.results_list.count()):
                item = self.results_list.item(row)
                if item and (item.flags() & Qt.ItemIsEnabled):
                    self._on_item_activated(item)
                    break

    def _on_item_activated(self, list_item: QListWidgetItem) -> None:
        """Handles item selection, updates recent searches, and emits navigation signal."""
        row = self.results_list.row(list_item)
        selected = self._list_item_map.get(row)
        if selected:
            # Save query to recent searches
            query = self.txt_search.text().strip()
            if query and query not in self._recent_searches:
                self._recent_searches.insert(0, query)
                if len(self._recent_searches) > 8:
                    self._recent_searches.pop()

            self.result_selected.emit(selected.route, selected.entity_id)
            self.result_item_selected.emit(selected)
            self.accept()

    def _perform_search(self) -> None:
        """Synchronously executes search query (called directly by tests or on demand)."""
        self._debounce_timer.stop()
        query = self.txt_search.text().strip()
        self.results_list.clear()
        self._list_item_map.clear()
        self._current_results.clear()

        if not query:
            self.lbl_status.setText("Type at least 1 character to search")
            return

        self._current_request_id += 1
        req_id = self._current_request_id
        batch = execute_service_search(self.search_service, query, self.active_category, req_id)
        self._on_results_ready(req_id, batch)

    def closeEvent(self, event) -> None:
        self._debounce_timer.stop()
        if self._active_worker and self._active_worker.isRunning():
            self._active_worker.quit()
            self._active_worker.wait(200)
        super().closeEvent(event)

    def _trigger_search(self) -> None:
        """Spawns an asynchronous background search worker."""
        query = self.txt_search.text().strip()
        if not query:
            self.results_list.clear()
            self._list_item_map.clear()
            self._current_results.clear()
            self.lbl_status.setText("Type at least 1 character to search")
            return

        self._current_request_id += 1
        req_id = self._current_request_id

        self.lbl_status.setText(f"Searching for '{query}'...")

        self._active_worker = SearchWorker(
            service=self.search_service,
            query=query,
            category=self.active_category,
            request_id=req_id,
        )
        self._active_worker.results_ready.connect(self._on_results_ready)
        self._active_worker.error_occurred.connect(self._on_error_occurred)
        self._active_worker.start()

    def _on_results_ready(self, req_id: int, batch: GlobalSearchBatch) -> None:
        """Processes search batch on UI thread, discarding stale responses."""
        if req_id != self._current_request_id:
            logger.debug("Discarding stale search result for request_id=%d (current=%d)", req_id, self._current_request_id)
            return

        self.results_list.clear()
        self._list_item_map.clear()
        self._current_results = batch.items

        _, tokens = normalize_query(batch.query)
        self.lbl_status.setText(f"Found {batch.total_count} results for '{batch.query}'")

        if not batch.items:
            empty_item = QListWidgetItem(self.results_list)
            empty_item.setFlags(Qt.NoItemFlags)
            lbl_empty = QLabel(f"No results found for '{batch.query}'.\nTry searching by title, company name, skill, or ID (e.g. JOB-12).")
            lbl_empty.setAlignment(Qt.AlignCenter)
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 36px; font-size: 13px; line-height: 1.5;")
            self.results_list.setItemWidget(empty_item, lbl_empty)
            empty_item.setSizeHint(lbl_empty.sizeHint())
            return

        # Category Grouping: if active_category == 'all', group by categories
        grouped: Dict[str, List[SearchResult]] = {}
        for res in batch.items:
            cat_name = res.category or res.entity_type.capitalize()
            grouped.setdefault(cat_name, []).append(res)

        if self.active_category == "all" and len(grouped) > 1:
            for cat_title, cat_items in grouped.items():
                if not cat_items:
                    continue

                # Section Header Item
                header_item = QListWidgetItem(self.results_list)
                header_item.setFlags(Qt.NoItemFlags)
                header_label = QLabel(f"  {cat_title.upper()} ({len(cat_items)})")
                header_label.setStyleSheet(f"""
                    font-size: 11px;
                    font-weight: 800;
                    color: {COLORS['text_dark']};
                    letter-spacing: 0.8px;
                    padding: 6px 8px 3px 8px;
                    background: transparent;
                """)
                self.results_list.setItemWidget(header_item, header_label)
                header_item.setSizeHint(header_label.sizeHint())

                # Section Result Items
                for res in cat_items:
                    list_item = QListWidgetItem(self.results_list)
                    widget = SearchResultItemWidget(res, tokens)
                    list_item.setSizeHint(widget.sizeHint())
                    row_idx = self.results_list.row(list_item)
                    self._list_item_map[row_idx] = res
                    self.results_list.setItemWidget(list_item, widget)
        else:
            for res in batch.items:
                list_item = QListWidgetItem(self.results_list)
                widget = SearchResultItemWidget(res, tokens)
                list_item.setSizeHint(widget.sizeHint())
                row_idx = self.results_list.row(list_item)
                self._list_item_map[row_idx] = res
                self.results_list.setItemWidget(list_item, widget)

        # Highlight first selectable result
        for row in range(self.results_list.count()):
            item = self.results_list.item(row)
            if item and (item.flags() & Qt.ItemIsEnabled):
                self.results_list.setCurrentRow(row)
                break

    def _on_error_occurred(self, req_id: int, error_msg: str) -> None:
        """Handles background worker failure."""
        if req_id != self._current_request_id:
            return
        self.lbl_status.setText(f"Search failed: {error_msg}")

    def showEvent(self, event) -> None:
        """Focuses and selects all text in search input when opened."""
        super().showEvent(event)
        self.txt_search.selectAll()
        self.txt_search.setFocus()
