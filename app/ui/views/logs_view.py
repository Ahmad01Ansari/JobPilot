"""Automation Mission Control Cockpit (Logs View).

Observability, multi-run telemetry, interactive timeline, incident response,
and raw diagnostic log inspection.
"""

from datetime import datetime
import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.automation_event import AutomationEvent, AutomationEventType, LogFileReference
from app.services.logs.automation_log_bridge import AutomationLogBridge
from app.services.logs.event_correlator import EventCorrelator
from app.services.logs.run_context import RunObservabilityContext, RunRegistry
from app.services.logs.run_persistence_bridge import RunPersistenceBridge
from app.ui.state import AppState
from app.ui.theme import ThemeManager
from app.ui.views.logs.current_action_card import CurrentActionCard
from app.ui.views.logs.mission_header import MissionHeader
from app.ui.views.logs.mission_status_strip import MissionStatusStrip
from app.ui.views.logs.pipeline_flow_map import PipelineFlowMap
from app.ui.views.logs.tabs.error_center_tab import ErrorCenterTab
from app.ui.views.logs.tabs.live_battlefield_tab import LiveBattlefieldTab
from app.ui.views.logs.tabs.live_raw_console_tab import LiveRawConsoleTab
from app.ui.views.logs.tabs.run_history_tab import RunHistoryTab
from app.ui.views.logs.tabs.system_diagnostics_tab import SystemDiagnosticsTab
from app.ui.widgets.notification_bar import NotificationBar


class LogsView(QWidget):
    """Automation Mission Control Cockpit replacing legacy raw text logs."""

    def __init__(
        self,
        log_file_path: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.app_state: Optional[AppState] = None

        # Core Domain Infrastructure
        self.registry = RunRegistry()
        self.correlator = EventCorrelator(deduplication_window_seconds=5.0)
        self.bridge = AutomationLogBridge(correlator=self.correlator)
        self.persistence_bridge = RunPersistenceBridge(registry=self.registry)

        # File reader state
        self._log_file_path = log_file_path or Path("logs/log.txt")
        self._file_offset = 0
        self._line_counter = 0
        self._is_paused = False
        self._active_run_id = "default"

        self._setup_ui()
        self._connect_signals()

        # Log polling timer (1.5s interval)
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_log_file)
        self._poll_timer.start(1500)

        # Initial read of existing logs
        self._poll_log_file()

    def set_app_state(self, state: AppState) -> None:
        """Injects application-wide UI state bus."""
        self.app_state = state

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # 1. Header with run selector chips and control toggles
        self.header = MissionHeader()
        layout.addWidget(self.header)

        # Notification banner
        self.notification_bar = NotificationBar(self)
        layout.addWidget(self.notification_bar)

        # 2. Scoped KPI Metric Strip (placed directly below Header, matching Dashboard layout)
        self.status_strip = MissionStatusStrip()
        layout.addWidget(self.status_strip)

        # 3. Hero Section: Unified Active Automation Session Cockpit (with integrated stage stepper)
        self.current_action_card = CurrentActionCard()
        self.pipeline_flow_map = self.current_action_card.pipeline_flow_map
        layout.addWidget(self.current_action_card)

        # 4. Five Diagnostic & Control Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 10px;
                background-color: {c.get('surface', '#161B22')};
                padding: 14px;
            }}
            QTabBar {{
                background: transparent;
                qproperty-drawBase: 0;
            }}
            QTabBar::tab {{
                background-color: {c.get('surface', '#161B22')};
                color: {c.get('text_muted', '#8B949E')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 11px;
                font-weight: 600;
                margin-right: 6px;
                margin-bottom: 6px;
            }}
            QTabBar::tab:selected {{
                background-color: {c.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border: 1px solid {c.get('primary', '#FF5F15')};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {c.get('surface_hover', '#262C36')};
                color: {c.get('text', '#F0F6FC')};
                border-color: {c.get('primary', '#FF5F15')};
            }}
        """)

        # Tab 1: Live Battlefield
        self.tab_battlefield = LiveBattlefieldTab()
        self.tabs.addTab(self.tab_battlefield, "Live Battlefield")

        # Tab 2: Run History
        self.tab_history = RunHistoryTab(persistence_bridge=self.persistence_bridge)
        self.tabs.addTab(self.tab_history, "Run History & Funnel")

        # Tab 3: Error & Incident Center
        self.tab_errors = ErrorCenterTab(correlator=self.correlator)
        self.tabs.addTab(self.tab_errors, "Error & Incident Center")

        # Tab 4: Raw Logs Console
        self.tab_raw_console = LiveRawConsoleTab()
        self.tabs.addTab(self.tab_raw_console, "Raw Console")

        # Tab 5: System Diagnostics
        self.tab_diagnostics = SystemDiagnosticsTab()
        self.tabs.addTab(self.tab_diagnostics, "System Diagnostics")

        layout.addWidget(self.tabs, 1)

    def _connect_signals(self) -> None:
        """Wires up event delivery, control toggles, and deep link navigation."""
        # Bridge events
        self.bridge.event_emitted.connect(self._on_automation_event)

        # Header controls
        self.header.run_selected.connect(self._on_run_selected)
        self.header.pause_stream_toggled.connect(self._on_pause_toggled)
        self.header.clear_view_clicked.connect(self._on_clear_view)
        self.header.export_clicked.connect(self._on_export_clicked)

        # Hero actions
        self.current_action_card.stop_requested.connect(self._on_emergency_stop)
        self.current_action_card.resolve_requested.connect(lambda: self.tabs.setCurrentIndex(2))

        # Tab 1 Deep links
        self.tab_battlefield.open_job_requested.connect(self._on_open_job)
        self.tab_battlefield.open_application_requested.connect(self._on_open_application)
        self.tab_battlefield.view_in_raw_logs_requested.connect(self._on_view_raw_reference)

        # Tab 2 Run selection
        self.tab_history.load_run_requested.connect(self._on_run_selected)

        # Tab 3 Incident actions
        self.tab_errors.intervention_resolved.connect(self._on_intervention_resolved)
        self.tab_errors.intervention_skip.connect(self._on_intervention_skip)
        self.tab_errors.add_qna_requested.connect(self._on_add_qna)
        self.tab_errors.browser_requested.connect(self._on_browser_requested)

        # Metric Card filter
        self.status_strip.filter_requested.connect(self._on_status_strip_filter)

        # Tabs changed
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # -------------------------------------------------------------------------
    # Real-Time Event Dispatcher
    # -------------------------------------------------------------------------

    def _on_automation_event(self, event: AutomationEvent) -> None:
        """Handles a normalized, deduplicated AutomationEvent."""
        # 1. Forward to persistence bridge
        self.persistence_bridge.handle_event(event)

        # 2. Update Run Registry context
        ctx = self.registry.get_or_create(event.run_id, platform=event.platform)

        # 3. Update Run Header chips if new run detected
        active_runs = self.registry.get_all_runs()
        self.header.set_runs(active_runs, selected_run_id=self._active_run_id)

        # 4. If matching active run (or default), update live UI components
        if event.run_id == self._active_run_id or self._active_run_id == "default":
            self._active_run_id = event.run_id
            self.current_action_card.update_from_context(ctx)
            self.pipeline_flow_map.set_current_stage(ctx.current_stage)
            self.status_strip.update_metrics(ctx)

            if not self._is_paused:
                self.tab_battlefield.add_event(event)

        # 5. Route errors and interventions to Tab 3
        if event.level == "ERROR" or event.event_type in (
            AutomationEventType.ERROR,
            AutomationEventType.APPLICATION_FAILED,
        ):
            self.tab_errors.record_error_event(event)

        if event.event_type in (
            AutomationEventType.CAPTCHA_DETECTED,
            AutomationEventType.LOGIN_REQUIRED,
            AutomationEventType.MANUAL_INTERVENTION,
        ):
            self.tab_errors.set_active_interventions(ctx.active_interventions)
            # Update Tab 3 badge text
            self.tabs.setTabText(2, f"Error Center ({len(ctx.active_interventions)})")

    def _poll_log_file(self) -> None:
        """Incrementally reads new lines from logs/log.txt without blocking."""
        if not self._log_file_path.exists():
            return

        try:
            curr_size = self._log_file_path.stat().st_size
            if curr_size < self._file_offset:
                # File was truncated or rotated
                self._file_offset = 0
                self._line_counter = 0

            # On initial startup, if the log file is large, tail only the last 32 KB
            if self._file_offset == 0 and curr_size > 32 * 1024:
                with open(self._log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(max(0, curr_size - 32 * 1024))
                    f.readline()  # Discard partial line
                    lines = [line for line in f.readlines() if line.strip()][-60:]
                    self._file_offset = f.tell()
            else:
                with open(self._log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(self._file_offset)
                    # Limit to at most 100 lines per poll cycle to guarantee responsive UI
                    lines = []
                    for _ in range(100):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line)
                    self._file_offset = f.tell()

            for line in lines:
                self._line_counter += 1
                clean_line = line.rstrip("\r\n")
                if not clean_line:
                    continue

                # Forward to raw console
                self.tab_raw_console.append_log_line(clean_line)

                # Process through fallback normalizer in the bridge
                self.bridge.on_log_line(
                    line=clean_line,
                    run_id=self._active_run_id,
                    line_number=self._line_counter,
                    byte_offset=self._file_offset,
                )
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # User Interactions & Deep Linking
    # -------------------------------------------------------------------------

    def _on_run_selected(self, run_id: str) -> None:
        """Switches active run view scope."""
        self._active_run_id = run_id
        ctx = self.registry.get(run_id)
        if ctx:
            self.current_action_card.update_from_context(ctx)
            self.pipeline_flow_map.set_current_stage(ctx.current_stage)
            self.status_strip.update_metrics(ctx)
            self.tab_errors.set_active_interventions(ctx.active_interventions)

            # Re-populate battlefield with this run's buffered events
            self.tab_battlefield.clear()
            for evt in ctx.events_buffer:
                self.tab_battlefield.add_event(evt)

    def _on_pause_toggled(self, is_paused: bool) -> None:
        self._is_paused = is_paused
        if is_paused:
            self.notification_bar.show_message("warning", "Event stream paused. Background logging continues.")
        else:
            self.notification_bar.show_message("info", "Event stream resumed.")

    def _on_clear_view(self) -> None:
        self.tab_battlefield.clear()
        self.tab_raw_console.clear_view()
        self.notification_bar.show_message("info", "View cleared (Logs on disk preserved).")

    def _on_export_clicked(self) -> None:
        """Exports diagnostic bundle."""
        ctx = self.registry.get(self._active_run_id)
        report = (
            f"JobPilot Mission Control Diagnostic Report\n"
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Run ID: {self._active_run_id}\n"
            f"Discovered: {ctx.jobs_discovered if ctx else 0}\n"
            f"Qualified: {ctx.jobs_qualified if ctx else 0}\n"
            f"Applied: {ctx.applications_submitted if ctx else 0}\n"
            f"Errors: {ctx.errors_count if ctx else 0}\n"
        )
        try:
            out_file = Path(f"logs/diagnostic_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            out_file.write_text(report, encoding="utf-8")
            self.notification_bar.show_message("success", f"Diagnostic report exported to {out_file.as_posix()}")
        except Exception as exc:
            self.notification_bar.show_message("error", f"Export failed: {exc}")

    def _on_emergency_stop(self) -> None:
        if self.app_state:
            self.app_state.notify("warning", "Emergency Stop requested by user.")
        ctx = self.registry.get(self._active_run_id)
        if ctx:
            ctx.status = "STOPPED"
            self.current_action_card.update_from_context(ctx)

    def _on_open_job(self, job_id: int) -> None:
        """Deep links to the Jobs view."""
        if self.app_state:
            self.app_state.set_current_page("jobs")
            self.app_state.notify("info", f"Navigated to Job #{job_id}")

    def _on_open_application(self, application_id: int) -> None:
        """Deep links to the Applications view."""
        if self.app_state:
            self.app_state.set_current_page("applications")
            self.app_state.notify("info", f"Navigated to Application #{application_id}")

    def _on_view_raw_reference(self, ref: LogFileReference) -> None:
        """Switches to Raw Logs tab and jumps directly to line."""
        self.tabs.setCurrentIndex(3)  # Raw Logs Tab
        self.tab_raw_console.jump_to_reference(ref)

    def _on_intervention_resolved(self, event_id: str) -> None:
        ctx = self.registry.get(self._active_run_id)
        if ctx:
            ctx.resolve_intervention(event_id)
            self.tab_errors.set_active_interventions(ctx.active_interventions)
            self.current_action_card.update_from_context(ctx)
            count = len(ctx.active_interventions)
            tab_title = f"Error Center ({count})" if count > 0 else "Error & Incident Center"
            self.tabs.setTabText(2, tab_title)
        self.notification_bar.show_message("success", "Intervention resolved. Automation resuming.")

    def _on_intervention_skip(self, event_id: str) -> None:
        ctx = self.registry.get(self._active_run_id)
        if ctx:
            ctx.resolve_intervention(event_id)
            self.tab_errors.set_active_interventions(ctx.active_interventions)
            self.current_action_card.update_from_context(ctx)
        self.notification_bar.show_message("warning", "Job skipped. Proceeding to next listing.")

    def _on_add_qna(self, question: str) -> None:
        if self.app_state:
            self.app_state.set_current_page("profile")
            self.app_state.notify("info", "Navigated to Profile / Q&A Bank.")

    def _on_browser_requested(self) -> None:
        self.notification_bar.show_message("info", "Active browser window brought to foreground.")

    def _on_status_strip_filter(self, metric_key: str) -> None:
        """Switches to Live Battlefield and sets the filter."""
        self.tabs.setCurrentIndex(0)
        if metric_key == "failed":
            self.tab_battlefield.level_combo.setCurrentText("ERROR")
        elif metric_key == "action req":
            self.tab_battlefield.level_combo.setCurrentText("WARNING")
        else:
            self.tab_battlefield.level_combo.setCurrentText("All Levels")

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self.tab_history.refresh_history()
        elif index == 4:
            self.tab_diagnostics.refresh_diagnostics()
