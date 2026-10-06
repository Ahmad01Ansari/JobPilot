"""Automation Control Center and live runner monitor view component.

Production-grade automation cockpit providing:
- High-density visual hierarchy
- Single vertical scroll context
- Platform health status strip
- Segmented platform switcher
- Active run hero with truthful action updates
- Compact horizontal execution pipeline
- KPI metrics rail
- Platform-aware current job inspector
- Dual-mode activity feed & raw technical log terminal
- Read-only historical run details drawer
- 100% backward-compatibility with test contracts and backend engines.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationRunResult,
    AutomationState,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.automation_service import AutomationManager
from app.services.platform_service import PlatformService
from app.ui.theme import COLORS, DARK_COLORS, LIGHT_COLORS, ThemeManager
from app.ui.widgets.automation import (
    AutomationHeader,
    AutomationHero,
    AutomationMetricRow,
    AutomationPipeline,
    AutomationUIState,
    CaptchaInterventionDialog,
    CurrentJobCard,
    InterventionBanner,
    LiveActivityStream,
    PlatformSelector,
    PlatformStrip,
    RunDetailsDrawer,
    RunSummaryCard,
    UniversalTimelineWidget,
    UniversalTargetCard,
)
from app.ui.views.automation.universal_review_dialog import UniversalReviewDialog
from app.ui.views.automation.universal_intervention_dialog import UniversalInterventionDialog
from app.ui.widgets.notification_bar import NotificationBar


class AutomationView(QWidget):
    """Modern ATS Automation Control Center and real-time execution cockpit."""

    def __init__(
        self,
        automation_manager: Optional[AutomationManager] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.manager = automation_manager or AutomationManager()
        self.platform_service = PlatformService()
        self.ui_state = AutomationUIState()
        self._active_captcha_dialog = None
        self._active_review_dialog = None
        self._active_int_dialog = None

        self._setup_ui()
        self._bind_legacy_attributes()
        self._connect_signals()
        self._check_platform_readiness()
        self._refresh_recent_runs()
        self._update_state_ui(self.manager.get_state().value)

        ThemeManager.add_listener(self._apply_theme)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 10)
        main_layout.setSpacing(8)

        # 1. Page Header with Controls and Telemetry
        self.header = AutomationHeader(self)
        self.header.start_clicked.connect(self._on_start_clicked)
        self.header.stop_clicked.connect(self._on_stop_clicked)
        self.header.pause_clicked.connect(self._on_pause_clicked)
        main_layout.addWidget(self.header)

        # 2. Notification Toast Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Manual Intervention Banner (Hidden by default)
        self.intervention_banner = InterventionBanner(self)
        self.intervention_banner.captcha_resolved.connect(self._on_captcha_resolved)
        main_layout.addWidget(self.intervention_banner)

        # 4. Viewport Layout (Main Scrollable Canvas + Slide-out Drawer)
        viewport_layout = QHBoxLayout()
        viewport_layout.setContentsMargins(0, 0, 0, 0)
        viewport_layout.setSpacing(10)

        # Scrollable Main Canvas
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(8)

        # Platform Health Strip
        self.platform_strip = PlatformStrip(container)
        self.platform_strip.platform_selected.connect(self._on_platform_strip_selected)
        c_layout.addWidget(self.platform_strip)

        # Segmented Platform Switcher
        self.platform_selector = PlatformSelector(container)
        self.platform_selector.platform_changed.connect(self._on_platform_selected)
        c_layout.addWidget(self.platform_selector)

        # Universal ATS Target Input Card (Active when Universal ATS is chosen)
        self.universal_target_card = UniversalTargetCard(container)
        self.universal_target_card.setVisible(False)
        c_layout.addWidget(self.universal_target_card)

        # Live Automation Hero Centerpiece
        self.hero = AutomationHero(container)
        self.hero.start_clicked.connect(self._on_start_clicked)
        self.hero.stop_clicked.connect(self._on_stop_clicked)
        self.hero.pause_clicked.connect(self._on_pause_clicked)
        c_layout.addWidget(self.hero)

        # Execution Pipeline (Horizontal compact funnel)
        self.pipeline = AutomationPipeline(container)
        c_layout.addWidget(self.pipeline)

        # Universal AI Agent Step Timeline
        self.universal_timeline = UniversalTimelineWidget(container)
        self.universal_timeline.setVisible(False)
        c_layout.addWidget(self.universal_timeline)

        # Compact KPI Metrics Row
        self.metrics_row = AutomationMetricRow(container)
        c_layout.addWidget(self.metrics_row)

        # Two-Column Workspace (Current Job + History vs Activity Feed)
        workspace_layout = QHBoxLayout()
        workspace_layout.setSpacing(10)

        # Left Column: Current Job Card + Run History
        left_col = QVBoxLayout()
        left_col.setSpacing(8)

        self.current_job_card = CurrentJobCard(container)
        left_col.addWidget(self.current_job_card)

        self.run_summary_card = RunSummaryCard(container)
        self.run_summary_card.run_selected.connect(self._on_run_selected)
        self.run_summary_card.view_all_requested.connect(self._on_view_all_runs)
        left_col.addWidget(self.run_summary_card, 1)

        workspace_layout.addLayout(left_col, 5)

        # Right Column: Dual-mode Live Activity Stream
        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        self.live_activity_stream = LiveActivityStream(container)
        right_col.addWidget(self.live_activity_stream, 1)

        workspace_layout.addLayout(right_col, 7)
        c_layout.addLayout(workspace_layout)

        scroll.setWidget(container)
        viewport_layout.addWidget(scroll, 1)

        # Slide-out Run Diagnostics Drawer (Placed right of scrollable viewport)
        self.run_details_drawer = RunDetailsDrawer(self)
        viewport_layout.addWidget(self.run_details_drawer)

        main_layout.addLayout(viewport_layout, 1)

    def _bind_legacy_attributes(self) -> None:
        """Exposes public attributes to maintain 100% backward compatibility with test contracts."""
        # Controls & badges
        self.btn_start = self.header.btn_start
        self.btn_stop = self.header.btn_stop
        self.btn_pause = self.header.btn_pause
        self.badge_status = self.header.badge_status
        self.combo_platform = self.platform_selector.combo_platform

        # Metrics labels
        self.val_discovered = self.metrics_row.val_discovered
        self.val_evaluated = self.metrics_row.val_evaluated
        self.val_qualified = self.metrics_row.val_qualified
        self.val_applied = self.metrics_row.val_applied
        self.val_skipped = self.metrics_row.val_skipped
        self.val_errors = self.metrics_row.val_errors

        # Activity stream & intervention banner
        self.activity_stream = self.live_activity_stream.activity_stream
        self.btn_clear_stream = self.live_activity_stream.btn_clear
        self.intervention_card = self.intervention_banner
        self.lbl_intervention = self.intervention_banner.lbl_intervention
        self.btn_dismiss_intervention = self.intervention_banner.btn_dismiss_intervention

    def _connect_signals(self) -> None:
        """Connects manager events to local UI slots."""
        self.manager.state_changed.connect(self._on_state_changed)
        self.manager.progress_updated.connect(self._on_progress_updated)
        self.manager.job_discovered.connect(self._on_job_discovered)
        self.manager.job_evaluated.connect(self._on_job_evaluated)
        self.manager.application_submitted.connect(self._on_application_submitted)
        self.manager.intervention_required.connect(self._on_intervention_required)
        self.manager.activity_logged.connect(self._on_activity_logged)
        self.manager.run_finished.connect(self._on_run_finished)

    def _check_platform_readiness(self) -> None:
        """Checks platform enablement and updates status strip."""
        li_ready = False
        nk_ready = False
        in_ready = False
        fo_ready = False
        gd_ready = False
        try:
            for p in self.platform_service.list_platforms():
                if p.name == "linkedin":
                    li_ready = bool(p.is_enabled)
                elif p.name == "naukri":
                    nk_ready = bool(p.is_enabled)
                elif p.name == "indeed":
                    in_ready = bool(p.is_enabled)
                elif p.name == "foundit":
                    fo_ready = bool(p.is_enabled)
                elif p.name == "glassdoor":
                    gd_ready = bool(p.is_enabled)
        except Exception:
            pass

        self.platform_strip.set_platform_readiness(li_ready, nk_ready, in_ready, fo_ready, gd_ready)
        self.header.set_platform_readiness(li_ready, nk_ready, in_ready, fo_ready, gd_ready)

    def _refresh_platform_status(self) -> None:
        """Alias for _check_platform_readiness."""
        self._check_platform_readiness()

    def _refresh_recent_runs(self) -> None:
        """Loads recent run history from database."""
        try:
            runs = self.manager.get_recent_runs(limit=10)
            self.run_summary_card.set_recent_runs(runs, max_display=8)
        except Exception:
            self.run_summary_card.set_recent_runs([])

    def refresh(self) -> None:
        """Refreshes platform readiness and recent runs from database."""
        self._check_platform_readiness()
        self._refresh_recent_runs()

    def _on_platform_selected(self, platform_key: str) -> None:
        """Handles platform switcher selection."""
        self.ui_state.platform = platform_key
        self.hero.update_from_state(self.ui_state)
        self.current_job_card.update_from_state(self.ui_state)

        is_universal = platform_key.lower() == "universal"
        if hasattr(self, "universal_target_card"):
            self.universal_target_card.setVisible(is_universal)
            if is_universal:
                self.universal_target_card.refresh_portal_jobs()
        if hasattr(self, "universal_timeline"):
            self.universal_timeline.setVisible(is_universal)

    def _on_platform_strip_selected(self, platform_key: str) -> None:
        """Syncs platform selection when a strip chip is clicked."""
        self.platform_selector.select_platform(platform_key)

    def _on_run_selected(self, run: object) -> None:
        """Opens slide-out drawer with read-only run diagnostics."""
        self.run_details_drawer.set_run(run)

    def _on_view_all_runs(self) -> None:
        """Opens full AllRunHistoryDialog with search and filter capabilities."""
        all_runs = self.manager.get_recent_runs(limit=1000)
        dialog = AllRunHistoryDialog(
            runs=all_runs,
            on_inspect=self._on_run_selected,
            parent=self,
        )
        dialog.exec()

    def _on_start_clicked(self) -> None:
        """Starts automation session for the selected platform."""
        platform = self.platform_selector.current_platform()
        if platform == "universal":
            target_url = self.universal_target_card.get_target_url()
            if not target_url:
                self.notification_bar.show_message(
                    "Please enter or select a Company Portal application URL before starting.", "warning"
                )
                return
            self.ui_state.reset_for_run(platform=platform)
            self._sync_all_widgets()
            success, err = self.manager.start_automation(
                platform=platform,
                target_url=target_url,
                job_title=self.universal_target_card.get_job_title(),
                company=self.universal_target_card.get_company(),
            )
        else:
            self.ui_state.reset_for_run(platform=platform)
            self._sync_all_widgets()
            success, err = self.manager.start_automation(platform=platform)

        if not success:
            self.notification_bar.show_message(err or "Failed to start automation.", "danger")
        else:
            self.notification_bar.show_message(f"Starting automation for {platform.capitalize()}...", "info")
            if platform in ("linkedin", "naukri", "indeed", "foundit", "glassdoor"):
                self.platform_strip.update_platform(platform, "RUNNING")

    def prepare_universal_run(self, job_or_url: object, job_title: str = "", company: str = "") -> None:
        """Pre-populates Universal Automation with a target portal job and switches view context."""
        self.platform_selector.select_platform("universal")
        if hasattr(self, "universal_target_card"):
            self.universal_target_card.set_target_job(job_or_url, job_title=job_title, company=company)
            comp = self.universal_target_card.get_company() or "Company Portal"
            pos = self.universal_target_card.get_job_title() or "Position"
            self.notification_bar.show_message(
                f"Loaded target portal job: '{pos}' at '{comp}'. Click 'Start Automation' when ready.", "info"
            )

    def _on_stop_clicked(self) -> None:
        """Requests graceful cancellation of active run."""
        success, err = self.manager.request_stop()
        if not success:
            self.notification_bar.show_message(err or "Failed to request stop.", "danger")
        else:
            self.notification_bar.show_message("Stopping automation gracefully...", "warning")

    def _on_pause_clicked(self) -> None:
        """Toggles pause/resume state for active automation session."""
        success, err = self.manager.toggle_pause()
        if not success and err:
            self.notification_bar.show_message(err, "warning")
        else:
            is_paused = self.manager.is_paused()
            msg = "Automation execution paused." if is_paused else "Automation execution resumed."
            self.notification_bar.show_message(msg, "info")

    def _on_state_changed(self, run_id: str, state_str: str) -> None:
        """Updates UI state when engine transition occurs."""
        self.ui_state.state = state_str
        self._update_state_ui(state_str)
        self._sync_all_widgets()
        if hasattr(self, "universal_timeline"):
            self.universal_timeline.update_state(state_str)

        # Update platform status strip
        plat = self.ui_state.platform.lower()
        if plat in ("linkedin", "naukri", "indeed", "foundit", "glassdoor"):
            if state_str == AutomationState.RUNNING.value:
                self.platform_strip.update_platform(plat, "RUNNING")
            elif state_str == AutomationState.PAUSED.value:
                self.platform_strip.update_platform(plat, "PAUSED")
            elif state_str in (AutomationState.COMPLETED.value, AutomationState.IDLE.value):
                self.platform_strip.update_platform(plat, "READY")
            elif state_str == AutomationState.FAILED.value:
                self.platform_strip.update_platform(plat, "ERROR")

    def _update_state_ui(self, state_str: str) -> None:
        """Updates header, hero, and control enablement based on state string."""
        self.header.update_state(state_str)
        is_running = self.ui_state.is_running()
        self.platform_selector.setEnabled(not is_running)

    def _on_progress_updated(self, progress: AutomationProgressEvent) -> None:
        """Handles telemetry progress updates."""
        self.ui_state.on_progress(progress)
        self._sync_all_widgets()

    def _on_job_discovered(self, event: JobDiscoveredEvent) -> None:
        """Handles job card discovery."""
        self.ui_state.on_job_discovered(event)
        self.current_job_card.update_from_state(self.ui_state)
        self.hero.update_from_state(self.ui_state)
        self.pipeline.update_from_state(self.ui_state)
        self.metrics_row.update_from_state(self.ui_state)

    def _on_job_evaluated(self, event: JobEvaluatedEvent) -> None:
        """Handles job qualification evaluation."""
        self.ui_state.on_job_evaluated(event)
        self.current_job_card.update_from_state(self.ui_state)
        self.hero.update_from_state(self.ui_state)
        self.pipeline.update_from_state(self.ui_state)
        self.metrics_row.update_from_state(self.ui_state)

    def _on_application_submitted(self, event: ApplicationSubmittedEvent) -> None:
        """Handles successful application submission."""
        self.ui_state.on_application_submitted(event)
        self.current_job_card.update_from_state(self.ui_state)
        self.hero.update_from_state(self.ui_state)
        self.pipeline.update_from_state(self.ui_state)
        self.metrics_row.update_from_state(self.ui_state)

        # Clear any active dialogs and banners
        if self._active_captcha_dialog:
            try:
                self._active_captcha_dialog.accept()
            except Exception:
                pass
            self._active_captcha_dialog = None

        if self._active_review_dialog:
            try:
                self._active_review_dialog.accept()
            except Exception:
                pass
            self._active_review_dialog = None

        if self._active_int_dialog:
            try:
                self._active_int_dialog.accept()
            except Exception:
                pass
            self._active_int_dialog = None

        self.intervention_banner.dismiss()

    def _on_intervention_required(self, event: AutomationInterventionEvent) -> None:
        """Handles manual interaction request (review, CAPTCHA, login, OTP, fields)."""
        self.ui_state.on_intervention(event)
        self.intervention_banner.show_intervention(event)

        plat = event.platform.lower()
        if plat in ("linkedin", "naukri", "indeed", "foundit", "glassdoor"):
            self.platform_strip.update_platform(plat, "MANUAL_REQUIRED")

        type_str = event.intervention_type.value if hasattr(event.intervention_type, "value") else str(event.intervention_type)
        if type_str == "PRE_SUBMISSION_REVIEW":
            self._show_review_dialog(event)
        elif type_str in ("CAPTCHA_DETECTED", "CAPTCHA_CHALLENGE") or "captcha" in str(getattr(event, "message", "")).lower() or "verification is required" in str(getattr(event, "message", "")).lower():
            self._show_captcha_dialog(event)
        else:
            self._show_universal_intervention_dialog(event)

    def _show_review_dialog(self, event: AutomationInterventionEvent) -> None:
        """Displays interactive Pre-Submission Review dialog for V1 human gate."""
        try:
            if hasattr(self, "_active_review_dialog") and self._active_review_dialog and self._active_review_dialog.isVisible():
                return
            details = getattr(event, "details", None) or {}
            field_details = details.get("fill_result", {}) if isinstance(details, dict) else {}
            dialog = UniversalReviewDialog(
                job_title=getattr(self.ui_state, "current_job_title", None) or "Target Position",
                company=getattr(self.ui_state, "current_job_company", None) or "Target Company",
                target_url=getattr(event, "action_url", None) or "",
                field_details=field_details,
                on_confirmed=lambda notes: self.manager.confirm_current_review(notes=notes),
                on_takeover=lambda notes: self.manager.takeover_current_manually(notes=notes),
                on_rejected=lambda reason: self.manager.cancel_current_review(reason=reason),
                parent=self.window() or self,
            )
            self._active_review_dialog = dialog
            dialog.show()
        except Exception as e:
            print(f"[AutomationView] Error displaying review dialog: {e}")

    def _show_universal_intervention_dialog(self, event: AutomationInterventionEvent) -> None:
        """Displays interactive intervention dialog for security challenges, logins, or missing fields."""
        try:
            if hasattr(self, "_active_int_dialog") and self._active_int_dialog and self._active_int_dialog.isVisible():
                return
            dialog = UniversalInterventionDialog(
                intervention_type=event.intervention_type,
                message=getattr(event, "message", ""),
                action_url=getattr(event, "action_url", None),
                details=getattr(event, "details", None),
                on_resumed=lambda data: self.manager.confirm_current_review(notes=data.get("value") or data.get("code"), data=data),
                on_takeover=lambda notes: self.manager.takeover_current_manually(notes=notes),
                on_cancelled=lambda reason: self.manager.cancel_current_review(reason=reason),
                parent=self.window() or self,
            )
            self._active_int_dialog = dialog
            dialog.show()
        except Exception as e:
            print(f"[AutomationView] Error displaying universal intervention dialog: {e}")

    def _show_captcha_dialog(self, event: AutomationInterventionEvent) -> None:
        """Displays interactive Human-in-the-Loop dialog asking user to resolve CAPTCHA in Chrome."""
        try:
            if self._active_captcha_dialog and self._active_captcha_dialog.isVisible():
                return
            dialog = CaptchaInterventionDialog(
                message=getattr(event, "message", ""),
                on_resolved=self._on_captcha_resolved,
                parent=self.window() or self,
            )
            self._active_captcha_dialog = dialog
            dialog.show()
        except Exception as e:
            print(f"[AutomationView] Error displaying CAPTCHA dialog: {e}")

    def _on_captcha_resolved(self) -> None:
        """Invoked when user clicks resolved on dialog or banner."""
        self.manager.mark_captcha_resolved()
        self.intervention_banner.dismiss()
        self.notification_bar.show_message("Action marked resolved. Resuming automation...", "success")
        if self._active_captcha_dialog:
            try:
                self._active_captcha_dialog.accept()
            except Exception:
                pass
            self._active_captcha_dialog = None

    def _on_activity_logged(self, timestamp: str, message: str) -> None:
        """Appends semantic event to live activity timeline."""
        self.live_activity_stream.log_activity(timestamp, message)
        if hasattr(self, "universal_timeline") and self.universal_timeline:
            self.universal_timeline.lbl_status_msg.setText(message[:50])

    def _on_run_finished(self, result: AutomationRunResult) -> None:
        """Handles session completion or termination."""
        self.ui_state.on_finished(result)
        self._sync_all_widgets()
        self._refresh_recent_runs()
        if hasattr(self, "universal_timeline"):
            self.universal_timeline.update_state(result.status.value, f"Run {result.status.value}")

        plat = result.platform.lower()
        if plat in ("linkedin", "naukri", "indeed", "foundit", "glassdoor"):
            self.platform_strip.update_platform(plat, "READY")

        msg = f"Run {result.status.value}: {result.applications_submitted} applied, {result.jobs_discovered} discovered."
        self.notification_bar.show_message(
            msg,
            "success" if result.status == AutomationState.COMPLETED else "warning",
        )

    def _sync_all_widgets(self) -> None:
        """Synchronizes current UI state to all child widgets."""
        self.hero.update_from_state(self.ui_state)
        self.pipeline.update_from_state(self.ui_state)
        self.metrics_row.update_from_state(self.ui_state)
        self.current_job_card.update_from_state(self.ui_state)
        self.run_summary_card.update_from_state(self.ui_state)

    def _clear_stream(self) -> None:
        """Clears timeline stream contents."""
        self.live_activity_stream.clear()

    def _apply_theme(self, mode: str) -> None:
        """Refreshes all components dynamically upon theme switch."""
        tokens = LIGHT_COLORS if mode == "light" else DARK_COLORS
        COLORS.clear()
        COLORS.update(tokens)
        self.setStyleSheet(f"background-color: {tokens.get('background', '#0F1117')};")
        self.header.apply_theme(tokens)
        self.platform_strip.apply_theme(tokens)
        self.platform_selector.apply_theme(tokens)
        self.hero.apply_theme(tokens)
        self.pipeline.apply_theme(tokens)
        if hasattr(self, "universal_target_card"):
            self.universal_target_card.apply_theme(tokens)
        if hasattr(self, "universal_timeline"):
            self.universal_timeline.apply_theme(tokens)
        self.metrics_row.apply_theme(tokens)
        self.current_job_card.apply_theme(tokens)
        self.run_summary_card.apply_theme(tokens)
        self.run_details_drawer.apply_theme(tokens)
        self.live_activity_stream.apply_theme(tokens)
        self.intervention_banner.apply_theme(tokens)
