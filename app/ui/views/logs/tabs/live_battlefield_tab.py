"""Live Battlefield Tab providing interactive vertical event timeline and detail inspection."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.automation_event import AutomationEvent, AutomationEventType
from app.ui.theme import ThemeManager
from app.ui.views.logs.widgets.event_detail_drawer import EventDetailDrawer
from app.ui.widgets.status_badge import StatusBadge


class TimelineCard(QFrame):
    """Individual event card within the vertical timeline."""

    clicked = Signal(object)  # AutomationEvent

    def __init__(self, event: AutomationEvent, is_selected: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.automation_event = event
        self._is_selected = is_selected
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Status Dot
        st = (self.automation_event.status or "").upper()
        lvl = (self.automation_event.level or "").upper()
        if st == "SUCCESS" or self.automation_event.event_type == AutomationEventType.APPLICATION_SUBMITTED:
            dot_color = c.get("success", "#2EA043")
            dot_char = "✓"
        elif "FAIL" in st or lvl == "ERROR":
            dot_color = c.get("danger", "#F85149")
            dot_char = "✕"
        elif "INTERVENTION" in st or "CAPTCHA" in str(self.automation_event.event_type):
            dot_color = c.get("warning", "#D29922")
            dot_char = "⚠"
        else:
            dot_color = c.get("primary", "#FF5F15")
            dot_char = "●"

        dot_lbl = QLabel(dot_char)
        dot_lbl.setFixedWidth(16)
        dot_lbl.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {dot_color}; background: transparent; border: none;")
        layout.addWidget(dot_lbl)

        # Timestamp & Sequence
        time_str = self.automation_event.timestamp.strftime("%H:%M:%S")
        ts_lbl = QLabel(f"{time_str} · #{self.automation_event.sequence}")
        ts_lbl.setFixedWidth(88)
        ts_lbl.setStyleSheet(f"font-size: 11px; font-family: monospace; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")
        layout.addWidget(ts_lbl)

        # Event Description
        desc_layout = QVBoxLayout()
        desc_layout.setSpacing(2)

        raw_job = (self.automation_event.job_title or "").strip()
        raw_company = (self.automation_event.company or "").strip()
        raw_action = (self.automation_event.action or "").strip()
        raw_msg = (self.automation_event.message or "").strip()

        if raw_job and raw_company:
            title_text = f"{raw_job} @ {raw_company}"
            detail_text = raw_msg or raw_action or "Automation action in progress"
        elif raw_job:
            title_text = raw_job
            detail_text = raw_msg if raw_msg and raw_msg.lower() != raw_job.lower() else (raw_action or "Active job evaluation")
        elif raw_action:
            title_text = raw_action
            detail_text = raw_msg if raw_msg and raw_msg.lower() != raw_action.lower() else ""
        else:
            title_text = raw_msg[:65] if raw_msg else "System Event"
            detail_text = raw_msg[65:] if len(raw_msg) > 65 else ""

        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {c.get('text', '#F0F6FC')}; background: transparent; border: none;")
        desc_layout.addWidget(title_lbl)

        if detail_text:
            detail_lbl = QLabel(detail_text)
            detail_lbl.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")
            desc_layout.addWidget(detail_lbl)

        layout.addLayout(desc_layout, 1)

        # Standardized StatusBadge (with rigorous error/warn/success precedence)
        stage_str = self.automation_event.stage or self.automation_event.event_type.value
        st_clean = stage_str.upper()
        evt_status = (self.automation_event.status or "").upper()
        evt_level = (self.automation_event.level or "").upper()

        if "FAIL" in st_clean or "ERROR" in st_clean or "FAIL" in evt_status or evt_level == "ERROR":
            badge_var = "danger"
            badge_text = "Failed" if "FAIL" in evt_status else "Error"
        elif "REVIEW" in st_clean or "WARN" in st_clean or "PAUSE" in st_clean or "ACTION" in evt_status or "WARN" in evt_level:
            badge_var = "warning"
            badge_text = "Paused" if "PAUSE" in evt_status else "Action Req"
        elif "SUBMIT" in st_clean or "APPLY" in st_clean or "SUCCESS" in st_clean or evt_status == "SUCCESS":
            badge_var = "success"
            badge_text = "Submitted" if "SUBMIT" in st_clean else stage_str.replace("_", " ").title()
        elif "SEARCH" in st_clean or "DISCOVER" in st_clean:
            badge_var = "info"
            badge_text = stage_str.replace("_", " ").title()
        elif "QUALIFY" in st_clean:
            badge_var = "purple"
            badge_text = stage_str.replace("_", " ").title()
        else:
            badge_var = "neutral"
            badge_text = stage_str.replace("_", " ").title()

        self.stage_badge = StatusBadge(badge_text, status_type=badge_var, width=105, height=22)
        layout.addWidget(self.stage_badge)

        self._apply_style()

    def set_selected(self, selected: bool) -> None:
        self._is_selected = selected
        self._apply_style()

    def _apply_style(self) -> None:
        c = ThemeManager.get_instance().colors
        st = (self.automation_event.status or "").upper()
        lvl = (self.automation_event.level or "").upper()

        if "FAIL" in st or lvl == "ERROR":
            accent_bar = c.get("danger", "#F85149")
        elif "INTERVENTION" in st or "WARN" in lvl or "PAUSED" in st:
            accent_bar = c.get("warning", "#D29922")
        elif st == "SUCCESS" or self.automation_event.event_type == AutomationEventType.APPLICATION_SUBMITTED:
            accent_bar = c.get("success", "#2EA043")
        else:
            accent_bar = c.get("primary", "#FF5F15")

        card_bg = c.get("surface_hover", "#262C36") if self._is_selected else c.get("surface_alt", "#1C2128")
        border = c.get("primary", "#FF5F15") if self._is_selected else c.get("border", "#262C36")

        self.setStyleSheet(f"""
            TimelineCard {{
                background-color: {card_bg};
                border: 1px solid {border};
                border-left: 4px solid {accent_bar};
                border-radius: 8px;
            }}
            TimelineCard:hover {{
                border-color: {accent_bar};
                background-color: {c.get('surface_hover', '#262C36')};
            }}
        """)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.automation_event)
        super().mousePressEvent(event)


class LiveBattlefieldTab(QWidget):
    """Tab 1: Interactive real-time event timeline and detail inspector."""

    open_job_requested = Signal(int)
    open_application_requested = Signal(int)
    view_in_raw_logs_requested = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._events: List[AutomationEvent] = []
        self._selected_card: Optional[TimelineCard] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        # 1. Filter Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(10)

        # Search Input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter events by keyword or company...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.get('surface', '#161B22')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {c.get('primary', '#FF5F15')};
                background-color: {c.get('surface_hover', '#262C36')};
            }}
        """)
        self.search_input.textChanged.connect(self._reapply_filter)
        filter_bar.addWidget(self.search_input, 1)

        # Level Filter
        self.level_combo = QComboBox()
        self.level_combo.addItems(["All Levels", "INFO", "WARNING", "ERROR"])
        self.level_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c.get('surface', '#161B22')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 500;
            }}
            QComboBox:hover {{
                border-color: {c.get('primary', '#FF5F15')};
            }}
        """)
        self.level_combo.currentIndexChanged.connect(self._reapply_filter)
        filter_bar.addWidget(self.level_combo)

        # Auto-scroll Toggle
        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet(f"""
            QCheckBox {{
                font-size: 12px;
                font-weight: 500;
                color: {c.get('text', '#F0F6FC')};
                spacing: 6px;
            }}
            QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border-radius: 3px;
                border: 1px solid {c.get('border', '#262C36')};
                background: {c.get('surface', '#161B22')};
            }}
            QCheckBox::indicator:checked {{
                background: {c.get('primary', '#FF5F15')};
                border-color: {c.get('primary', '#FF5F15')};
            }}
        """)
        filter_bar.addWidget(self.chk_autoscroll)

        root_layout.addLayout(filter_bar)

        # 2. Splitter: Timeline (Left) + Detail Drawer (Right)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: transparent; }")

        # Left: Scrollable Timeline
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.timeline_container = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(0, 0, 8, 0)
        self.timeline_layout.setSpacing(6)
        self.timeline_layout.addStretch()

        self.timeline_scroll.setWidget(self.timeline_container)
        splitter.addWidget(self.timeline_scroll)

        # Right: Detail Drawer
        self.drawer = EventDetailDrawer()
        self.drawer.setVisible(False)
        self.drawer.closed.connect(lambda: self.drawer.setVisible(False))
        self.drawer.open_job_requested.connect(self.open_job_requested.emit)
        self.drawer.open_application_requested.connect(self.open_application_requested.emit)
        self.drawer.view_in_raw_logs_requested.connect(self.view_in_raw_logs_requested.emit)
        splitter.addWidget(self.drawer)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root_layout.addWidget(splitter, 1)

    MAX_TIMELINE_CARDS = 80

    def add_event(self, event: AutomationEvent) -> None:
        """Appends an event card to the timeline with bounded memory footprint."""
        self._events.append(event)
        if len(self._events) > 200:
            self._events = self._events[-200:]

        # Prune oldest widgets if timeline exceeds card limit
        while self.timeline_layout.count() > self.MAX_TIMELINE_CARDS:
            item = self.timeline_layout.takeAt(0)
            if item:
                w = item.widget()
                if w:
                    w.deleteLater()

        card = TimelineCard(event=event, parent=self.timeline_container)
        card.clicked.connect(self._on_card_clicked)

        # Insert before the stretch at the end
        idx = max(0, self.timeline_layout.count() - 1)
        self.timeline_layout.insertWidget(idx, card)

        # Auto-scroll to bottom if enabled
        if self.chk_autoscroll.isChecked():
            sb = self.timeline_scroll.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear(self) -> None:
        """Clears all cards from the timeline."""
        self._events.clear()
        while self.timeline_layout.count() > 1:
            item = self.timeline_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.drawer.setVisible(False)

    def _on_card_clicked(self, event: AutomationEvent) -> None:
        """Handles selecting an event card to inspect in the drawer."""
        for i in range(self.timeline_layout.count() - 1):
            w = self.timeline_layout.itemAt(i).widget()
            if isinstance(w, TimelineCard):
                w.set_selected(w.automation_event.event_id == event.event_id)
        self.drawer.inspect_event(event)
        self.drawer.setVisible(True)

    def _reapply_filter(self) -> None:
        """Filters visible cards based on keyword and level."""
        query = self.search_input.text().strip().lower()
        level_sel = self.level_combo.currentText()

        for i in range(self.timeline_layout.count() - 1):
            w = self.timeline_layout.itemAt(i).widget()
            if isinstance(w, TimelineCard):
                evt = w.automation_event
                match_query = True
                if query:
                    search_str = f"{evt.message} {evt.company or ''} {evt.job_title or ''} {evt.action or ''}".lower()
                    match_query = (query in search_str)

                match_lvl = True
                if level_sel != "All Levels":
                    match_lvl = (evt.level == level_sel)

                w.setVisible(match_query and match_lvl)
