"""Dual-mode Activity Stream & Raw Logs component for Automation Control Center.

Features:
- Tabbed [Activity] (Structured semantic feed) and [Raw Logs] (Technical debug terminal)
- Category filters (All, Jobs, Qualification, Submissions, System, Errors)
- Auto-scroll lock with pause on upward scroll and 'Jump to latest' indicator
- 100% backward compatibility with QTextEdit methods (append, clear, toPlainText).
"""

from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QClipboard, QGuiApplication, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class LiveActivityStream(QFrame):
    """Dual-mode live activity feed and raw technical logging component."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._autoscroll_enabled = True
        self._current_filter = "All"
        self._search_query = ""
        self._events: List[Tuple[str, str, str, str]] = []  # (timestamp, category, color_key, message)
        self._raw_lines: List[str] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("live_activity_stream")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # 1. Top Bar: View Tabs [Activity | Raw Logs] + Auto-scroll toggle + Clear
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        self.tab_activity = QPushButton("Activity Feed")
        self.tab_activity.setCheckable(True)
        self.tab_activity.setChecked(True)
        self.tab_activity.setCursor(Qt.PointingHandCursor)
        self.tab_activity.setFixedHeight(26)
        self.tab_activity.clicked.connect(lambda: self._set_active_view("activity"))

        self.tab_raw = QPushButton("Raw Logs")
        self.tab_raw.setCheckable(True)
        self.tab_raw.setCursor(Qt.PointingHandCursor)
        self.tab_raw.setFixedHeight(26)
        self.tab_raw.clicked.connect(lambda: self._set_active_view("raw"))

        self.view_btn_group = QButtonGroup(self)
        self.view_btn_group.setExclusive(True)
        self.view_btn_group.addButton(self.tab_activity)
        self.view_btn_group.addButton(self.tab_raw)

        top_bar.addWidget(self.tab_activity)
        top_bar.addWidget(self.tab_raw)
        top_bar.addStretch()

        # Jump to latest button (visible when auto-scroll is paused)
        self.btn_jump_latest = QPushButton("↓ Jump to latest")
        self.btn_jump_latest.setFixedHeight(24)
        self.btn_jump_latest.setCursor(Qt.PointingHandCursor)
        self.btn_jump_latest.setVisible(False)
        self.btn_jump_latest.clicked.connect(self._jump_to_bottom)
        top_bar.addWidget(self.btn_jump_latest)

        # Auto-scroll pause toggle
        self.btn_autoscroll = QPushButton("Auto-scroll: ON")
        self.btn_autoscroll.setFixedHeight(24)
        self.btn_autoscroll.setCursor(Qt.PointingHandCursor)
        self.btn_autoscroll.clicked.connect(self._toggle_autoscroll)
        top_bar.addWidget(self.btn_autoscroll)

        # Copy Logs Button
        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setFixedHeight(24)
        self.btn_copy.setCursor(Qt.PointingHandCursor)
        self.btn_copy.clicked.connect(self._copy_to_clipboard)
        top_bar.addWidget(self.btn_copy)

        # Clear button (legacy attribute preserved)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setFixedHeight(24)
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear)
        top_bar.addWidget(self.btn_clear)

        layout.addLayout(top_bar)

        # 2. Filter Bar (Filter Chips + Search Input)
        self.filter_bar = QWidget()
        filter_layout = QHBoxLayout(self.filter_bar)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(6)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons: Dict[str, QPushButton] = {}

        categories = ["All", "Jobs", "Qualification", "Submissions", "System", "Errors"]
        for cat in categories:
            btn = QPushButton(cat)
            btn.setCheckable(True)
            btn.setFixedHeight(22)
            btn.setCursor(Qt.PointingHandCursor)
            if cat == "All":
                btn.setChecked(True)
            btn.clicked.connect(lambda checked=False, c=cat: self._set_category_filter(c))
            self.filter_buttons[cat] = btn
            self.filter_group.addButton(btn)
            filter_layout.addWidget(btn)

        filter_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter events...")
        self.search_input.setFixedHeight(22)
        self.search_input.setFixedWidth(140)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        filter_layout.addWidget(self.search_input)

        layout.addWidget(self.filter_bar)

        # 3. Main Text Views (activity_stream exposed for backward compatibility)
        self.activity_stream = QTextEdit()
        self.activity_stream.setReadOnly(True)
        self.activity_stream.setMinimumHeight(170)
        self.activity_stream.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        layout.addWidget(self.activity_stream, 1)

        self._current_view_mode = "activity"
        self._refresh_styles()

    def _set_active_view(self, mode: str) -> None:
        """Switches between structured activity feed and raw monospace logs."""
        self._current_view_mode = mode
        self.tab_activity.setChecked(mode == "activity")
        self.tab_raw.setChecked(mode == "raw")
        self.filter_bar.setVisible(mode == "activity")
        self._refresh_styles()
        self._render_view()

    def _set_category_filter(self, category: str) -> None:
        """Applies category filter chip."""
        self._current_filter = category
        self._refresh_styles()
        self._render_view()

    def _on_search_text_changed(self, text: str) -> None:
        """Filters displayed events by text query."""
        self._search_query = text.strip().lower()
        self._render_view()

    def log_activity(self, timestamp: str, message: str) -> None:
        """Appends semantic event to stream with deterministic category assignment."""
        tokens = COLORS
        msg_clean = (message or "").strip()
        self._raw_lines.append(f"[{timestamp}] {msg_clean}")

        # Deterministic categorization
        msg_lower = msg_clean.lower()
        if "discovered" in msg_lower:
            category = "Jobs"
            color_key = "primary"
        elif "qualified" in msg_lower or "evaluating" in msg_lower or "skipped" in msg_lower:
            category = "Qualification"
            color_key = "accent" if "qualified" in msg_lower else "text_muted"
        elif "submitted" in msg_lower or "application" in msg_lower:
            category = "Submissions"
            color_key = "success"
        elif "error" in msg_lower or "failed" in msg_lower:
            category = "Errors"
            color_key = "danger"
        else:
            category = "System"
            color_key = "info"

        self._events.append((timestamp, category, color_key, msg_clean))

        # If matching current view and filter, append immediately
        if self._matches_filter(category, msg_clean):
            if self._current_view_mode == "activity":
                html_row = self._format_html_row(timestamp, category, color_key, msg_clean)
                self.activity_stream.append(html_row)
            else:
                self.activity_stream.append(f"[{timestamp}] {msg_clean}")

            if self._autoscroll_enabled:
                self._jump_to_bottom()

    def _matches_filter(self, category: str, message: str) -> bool:
        if self._current_filter != "All" and category != self._current_filter:
            return False
        if self._search_query and self._search_query not in message.lower():
            return False
        return True

    def _format_html_row(self, timestamp: str, category: str, color_key: str, message: str) -> str:
        tokens = COLORS
        color = tokens.get(color_key, tokens.get("text", "#F0F6FC"))
        ts_color = tokens.get("text_muted", "#8B949E")
        bg_chip = tokens.get("surface_alt", "#1C2128")

        return (
            f"<div style='margin-bottom: 5px; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; font-size: 12px;'>"
            f"<span style='color: {ts_color}; font-weight: 500;'>[{timestamp}]</span> &nbsp;"
            f"<span style='color: {color}; background-color: {bg_chip}; border-radius: 4px; padding: 1px 6px; font-size: 10px; font-weight: 700;'>{category.upper()}</span> &nbsp;"
            f"<span style='color: {tokens.get('text', '#F0F6FC')};'>{message}</span>"
            f"</div>"
        )

    def _render_view(self) -> None:
        """Re-renders complete text buffer according to active tab and filters."""
        self.activity_stream.clear()
        if self._current_view_mode == "activity":
            self.activity_stream.setFontFamily("-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif")
            for ts, cat, col_key, msg in self._events:
                if self._matches_filter(cat, msg):
                    self.activity_stream.append(self._format_html_row(ts, cat, col_key, msg))
        else:
            self.activity_stream.setFontFamily("JetBrains Mono, Courier New, monospace")
            for line in self._raw_lines:
                if not self._search_query or self._search_query in line.lower():
                    self.activity_stream.append(line)

        if self._autoscroll_enabled:
            self._jump_to_bottom()

    def _on_scroll_value_changed(self, value: int) -> None:
        """Detects manual upward scroll and pauses auto-scroll."""
        sb = self.activity_stream.verticalScrollBar()
        if sb.maximum() > 0:
            is_at_bottom = (value >= sb.maximum() - 10)
            if not is_at_bottom and self._autoscroll_enabled:
                self._autoscroll_enabled = False
                self.btn_autoscroll.setText("Auto-scroll: PAUSED")
                self.btn_jump_latest.setVisible(True)
                self._refresh_styles()
            elif is_at_bottom and not self._autoscroll_enabled:
                self._autoscroll_enabled = True
                self.btn_autoscroll.setText("Auto-scroll: ON")
                self.btn_jump_latest.setVisible(False)
                self._refresh_styles()

    def _toggle_autoscroll(self) -> None:
        self._autoscroll_enabled = not self._autoscroll_enabled
        if self._autoscroll_enabled:
            self.btn_autoscroll.setText("Auto-scroll: ON")
            self.btn_jump_latest.setVisible(False)
            self._jump_to_bottom()
        else:
            self.btn_autoscroll.setText("Auto-scroll: PAUSED")
            self.btn_jump_latest.setVisible(True)
        self._refresh_styles()

    def _jump_to_bottom(self) -> None:
        cursor = self.activity_stream.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.activity_stream.setTextCursor(cursor)
        self.btn_jump_latest.setVisible(False)

    def _copy_to_clipboard(self) -> None:
        text = self.activity_stream.toPlainText()
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def clear(self) -> None:
        self._events.clear()
        self._raw_lines.clear()
        self.activity_stream.clear()

    def append(self, text: str) -> None:
        """Legacy pass-through method."""
        self.log_activity("LOG", text)

    def toPlainText(self) -> str:
        """Legacy pass-through method."""
        return self.activity_stream.toPlainText()

    def _refresh_styles(self) -> None:
        tokens = COLORS

        self.setStyleSheet(f"""
            QFrame#live_activity_stream {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 10px;
            }}
        """)

        # Tabs
        for tab, active in [(self.tab_activity, self._current_view_mode == "activity"), (self.tab_raw, self._current_view_mode == "raw")]:
            if active:
                tab.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tokens.get('primary', '#FF5F15')};
                        color: #FFFFFF;
                        font-size: 11px;
                        font-weight: 700;
                        padding: 0 10px;
                        border-radius: 5px;
                        border: none;
                    }}
                """)
            else:
                tab.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tokens.get('surface_alt', '#1C2128')};
                        color: {tokens.get('text_muted', '#8B949E')};
                        font-size: 11px;
                        font-weight: 600;
                        padding: 0 10px;
                        border-radius: 5px;
                        border: 1px solid {tokens.get('border', '#262C36')};
                    }}
                    QPushButton:hover {{
                        color: {tokens.get('text', '#F0F6FC')};
                    }}
                """)

        # Filter Chips
        for cat, btn in self.filter_buttons.items():
            is_cat = (cat == self._current_filter)
            if is_cat:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tokens.get('primary', '#FF5F15')};
                        color: #FFFFFF;
                        font-size: 10px;
                        font-weight: 700;
                        padding: 0 8px;
                        border-radius: 4px;
                        border: none;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tokens.get('surface_alt', '#1C2128')};
                        color: {tokens.get('text_muted', '#8B949E')};
                        font-size: 10px;
                        font-weight: 600;
                        padding: 0 8px;
                        border-radius: 4px;
                        border: 1px solid {tokens.get('border', '#262C36')};
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.get('surface_hover', '#262C36')};
                        color: {tokens.get('text', '#F0F6FC')};
                    }}
                """)

        # Action Buttons
        for btn in (self.btn_autoscroll, self.btn_copy, self.btn_clear):
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {tokens.get('surface_alt', '#1C2128')};
                    color: {tokens.get('text_muted', '#8B949E')};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 0 8px;
                    border-radius: 4px;
                    border: 1px solid {tokens.get('border', '#262C36')};
                }}
                QPushButton:hover {{
                    color: {tokens.get('text', '#F0F6FC')};
                    border-color: {tokens.get('border_light', '#333A46')};
                }}
            """)

        self.btn_jump_latest.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('primary_subtle', '#FF5F1518')};
                color: {tokens.get('primary', '#FF5F15')};
                font-size: 11px;
                font-weight: 700;
                padding: 0 8px;
                border-radius: 4px;
                border: 1px solid {tokens.get('primary', '#FF5F15')}60;
            }}
        """)

        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {tokens.get('background', '#0F1117')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 11px;
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 4px;
                padding: 2px 6px;
            }}
            QLineEdit:focus {{
                border-color: {tokens.get('primary', '#FF5F15')};
            }}
        """)

        self.activity_stream.setStyleSheet(f"""
            QTextEdit {{
                background-color: {tokens.get('background', '#0F1117')};
                color: {tokens.get('text', '#F0F6FC')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
                padding: 8px;
                line-height: 1.4;
            }}
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
        self._render_view()
