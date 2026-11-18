"""AI Pilot Command Center View for JobPilot Desktop.

Provides a unified single-window conversational copilot where candidates
can talk, type, and trigger real automation actions (search, apply, tailor, rules)
without ever navigating across separate tabs.
"""

from collections import deque
import logging
from typing import Deque, Dict, Optional
from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.pilot.pilot_models import (
    PilotAuthor,
    PilotMessage,
    PilotRuleChange,
    PilotStep,
)
from app.services.pilot.pilot_service import PilotService
from app.ui.theme import COLORS
from app.ui.views.pilot.composer import PilotComposer
from app.ui.views.pilot.tag_bar import SmartTagBar
from app.ui.views.pilot.telemetry_sidebar import PilotTelemetrySidebar
from app.ui.views.pilot.timeline_cards import (
    NeedsYouCard,
    PilotMessageCard,
    RuleChangeCard,
    UserMessageCard,
)

logger = logging.getLogger("JobPilot.PilotView")


class _PilotPromptWorker(QThread):
    """Background worker processing user prompt through PilotService without freezing GUI."""

    prompt_processed = Signal(object)  # PilotMessage

    def __init__(self, service: PilotService, text: str):
        super().__init__()
        self._service = service
        self._text = text

    def run(self):
        try:
            msg = self._service.process_user_prompt(self._text)
            self.prompt_processed.emit(msg)
        except Exception as e:
            logger.error("Error processing prompt in worker: %s", str(e), exc_info=True)


class PilotView(QWidget):
    """Unified conversational copilot command center."""

    data_updated = Signal()
    service_event_received = Signal(str, object)  # Thread-safe event queue to main thread

    def __init__(self, parent=None):
        super().__init__(parent)
        self.app_state = None
        self._service = PilotService()
        self._active_worker: Optional[_PilotPromptWorker] = None
        self._is_busy: bool = False
        self._prompt_queue: Deque[str] = deque()
        self._message_cards: Dict[str, QWidget] = {}
        self._latest_pilot_card: Optional[QWidget] = None

        self._build_ui()
        self._subscribe_service_events()
        self._render_initial_timeline()
        self._refresh_telemetry()

        # Telemetry polling timer to refresh gauges during active automation runs
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(3000)
        self._telemetry_timer.timeout.connect(self._refresh_telemetry)
        self._telemetry_timer.start()

    def set_app_state(self, state):
        self.app_state = state

    # -------------------------------------------------------------------------
    # UI Assembly
    # -------------------------------------------------------------------------
    def _build_ui(self):
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Left Column: Conversation & Command Center ──────────────────────
        main_column = QWidget()
        main_layout = QVBoxLayout(main_column)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)

        # Top Header Bar
        header_bar = QHBoxLayout()
        header_title = QLabel("AI PILOT COMMAND CENTER")
        header_title.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 15px; font-weight: bold; letter-spacing: 0.5px;")
        header_bar.addWidget(header_title)

        header_sub = QLabel("Autonomous Career Copilot")
        header_sub.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 12px; margin-left: 8px;")
        header_bar.addWidget(header_sub)
        header_bar.addStretch()

        # Autopilot Toggle
        self.autopilot_btn = QPushButton("Autopilot: OFF")
        self.autopilot_btn.setCheckable(True)
        self.autopilot_btn.setCursor(Qt.PointingHandCursor)
        self.autopilot_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text_muted', '#8B949E')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 14px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:checked {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border-color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        self.autopilot_btn.toggled.connect(self._toggle_autopilot)
        header_bar.addWidget(self.autopilot_btn)

        main_layout.addLayout(header_bar)

        # Timeline Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.timeline_container = QWidget()
        self.timeline_container.setStyleSheet("background: transparent;")
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setContentsMargins(0, 4, 0, 4)
        self.timeline_layout.setSpacing(8)
        self.timeline_layout.addStretch()

        self.scroll_area.setWidget(self.timeline_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Quick Tag Bar
        self.tag_bar = SmartTagBar()
        self.tag_bar.tag_selected.connect(self._on_tag_selected)
        main_layout.addWidget(self.tag_bar)

        # Composer Input
        self.composer = PilotComposer()
        self.composer.message_submitted.connect(self._on_prompt_submitted)
        main_layout.addWidget(self.composer)

        root_layout.addWidget(main_column, 1)

        # ── Right Column: Telemetry & Rules Sidebar ─────────────────────────
        self.sidebar = PilotTelemetrySidebar()
        root_layout.addWidget(self.sidebar)

    # -------------------------------------------------------------------------
    # Thread-Safe Service Events & Rendering
    # -------------------------------------------------------------------------
    def _subscribe_service_events(self):
        self.service_event_received.connect(self._handle_service_event_on_main_thread)
        self._service.register_listener(lambda name, payload: self.service_event_received.emit(name, payload))

    def _handle_service_event_on_main_thread(self, event_name: str, payload):
        if event_name == "message_added":
            msg: PilotMessage = payload
            if msg and msg.id not in self._message_cards:
                card = self._create_card_for_message(msg, is_live=True)
                if card:
                    self.timeline_layout.insertWidget(self.timeline_layout.count() - 1, card)
                    self._message_cards[msg.id] = card
                    if msg.author == PilotAuthor.PILOT:
                        self._latest_pilot_card = card
                    self._scroll_to_bottom()
            self._refresh_telemetry()
        elif event_name == "step_emitted":
            step = payload
            if self._latest_pilot_card and hasattr(self._latest_pilot_card, "update_step"):
                self._latest_pilot_card.update_step(step)
        elif event_name == "metrics_updated":
            if self._latest_pilot_card and hasattr(self._latest_pilot_card, "update_metrics"):
                self._latest_pilot_card.update_metrics(payload)
        elif event_name in ("rule_changed", "rule_undone", "intervention_created", "intervention_resolved"):
            self._render_initial_timeline()
            self._refresh_telemetry()

    def _render_initial_timeline(self):
        while self.timeline_layout.count() > 1:
            item = self.timeline_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._message_cards.clear()
        self._latest_pilot_card = None

        timeline = self._service.get_timeline()
        for msg in timeline:
            card = self._create_card_for_message(msg, is_live=False)
            if card:
                self.timeline_layout.insertWidget(self.timeline_layout.count() - 1, card)
                self._message_cards[msg.id] = card
                if msg.author == PilotAuthor.PILOT:
                    self._latest_pilot_card = card

        self._scroll_to_bottom()

    def _create_card_for_message(self, msg: PilotMessage, is_live: bool = False) -> Optional[QWidget]:
        if msg.author == PilotAuthor.USER:
            return UserMessageCard(msg)

        if msg.intervention:
            card = NeedsYouCard(msg)
            card.answered.connect(self._on_intervention_answered)
            return card

        if msg.rule_change:
            card = RuleChangeCard(msg)
            card.undo_clicked.connect(self._on_rule_undo_clicked)
            return card

        return PilotMessageCard(msg, is_live=is_live)

    def _scroll_to_bottom(self):
        QTimer.singleShot(50, self._do_scroll)

    def _do_scroll(self):
        sb = self.scroll_area.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _refresh_telemetry(self):
        telemetry = self._service.get_telemetry()
        rules = self._service.get_rules()
        self.sidebar.update_telemetry(telemetry, rules)
        self.autopilot_btn.setChecked(rules.get("autopilot_enabled", False))
        self.autopilot_btn.setText(f"Autopilot: {'ON' if rules.get('autopilot_enabled') else 'OFF'}")

    # -------------------------------------------------------------------------
    # Interactions
    # -------------------------------------------------------------------------
    def _on_prompt_submitted(self, text: str):
        if not text or not text.strip():
            return

        clean_text = text.strip()

        # Enforce single-action constraint: queue message if currently busy
        if self._is_busy:
            self._prompt_queue.append(clean_text)
            self.composer.editor.setPlaceholderText(
                f"Task queued ({len(self._prompt_queue)} pending). AI Copilot is executing current action..."
            )
            return

        self._is_busy = True
        self.composer.send_btn.setEnabled(False)
        self.composer.send_btn.setText("Working...")
        self.composer.editor.setPlaceholderText("AI Copilot is executing task...")

        self._active_worker = _PilotPromptWorker(self._service, clean_text)
        self._active_worker.prompt_processed.connect(self._on_prompt_worker_done)
        self._active_worker.start()

    def _on_prompt_worker_done(self, reply_msg: PilotMessage):
        # Update existing message card in-place with complete response and completed steps
        if reply_msg and reply_msg.id in self._message_cards:
            card = self._message_cards[reply_msg.id]
            if hasattr(card, "update_message"):
                card.update_message(reply_msg)
            self._scroll_to_bottom()
        elif reply_msg and reply_msg.id not in self._message_cards:
            card = self._create_card_for_message(reply_msg)
            if card:
                self.timeline_layout.insertWidget(self.timeline_layout.count() - 1, card)
                self._message_cards[reply_msg.id] = card
                if reply_msg.author == PilotAuthor.PILOT:
                    self._latest_pilot_card = card
                self._scroll_to_bottom()

        # If more tasks are waiting in queue, process next item sequentially
        if self._prompt_queue:
            next_text = self._prompt_queue.popleft()
            self.composer.editor.setPlaceholderText(
                f"Processing queued task ({len(self._prompt_queue)} remaining)..."
            )
            self._active_worker = _PilotPromptWorker(self._service, next_text)
            self._active_worker.prompt_processed.connect(self._on_prompt_worker_done)
            self._active_worker.start()
        else:
            self._is_busy = False
            self.composer.send_btn.setEnabled(True)
            self.composer.send_btn.setText("Send")
            self.composer.editor.setPlaceholderText(
                "Ask the Pilot, paste a job URL, or set a rule (Enter to send, Shift+Enter for newline)..."
            )

        self._refresh_telemetry()
        self.data_updated.emit()

    def _on_tag_selected(self, prompt: str):
        # Directly execute prompt when tag is clicked
        self._on_prompt_submitted(prompt)

    def _on_intervention_answered(self, intervention_id: str, answer: str):
        self._service.resolve_intervention(intervention_id, answer)
        self._render_initial_timeline()
        self._refresh_telemetry()
        self.data_updated.emit()

    def _on_rule_undo_clicked(self, rule_change_id: str):
        self._service.undo_rule_change(rule_change_id)
        self._render_initial_timeline()
        self._refresh_telemetry()
        self.data_updated.emit()

    def _toggle_autopilot(self, checked: bool):
        self._service.update_rule(
            "pilot.autopilot_enabled",
            checked,
            f"Turn Autopilot {'ON' if checked else 'OFF'}",
        )
        self._refresh_telemetry()
