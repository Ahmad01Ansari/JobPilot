"""
Primary Desktop Window Shell for JobPilot.
Assembles Sidebar, TopBar, NotificationBar, Stacked Content Views, and StatusBar.
"""

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QStackedWidget,
)
from PySide6.QtGui import QKeySequence, QShortcut

from app.ui.theme import COLORS, ThemeManager
from app.ui.state import AppState
from app.ui.navigation import NAV_ITEMS
from app.ui.sidebar import Sidebar
from app.ui.top_bar import TopBar
from app.ui.status_bar import StatusBar
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.search_dialog import GlobalSearchDialog
from app.services.navigation_service import AppNavigator
from app.services.notification_service import NotificationService
from app.services.search.global_search_service import GlobalSearchService
from app.services.search.search_result import NavigationAction, NavigationRequest, SearchResult
from app.services.search_service import SearchService


class MainWindow(QMainWindow):
    """Main desktop application window."""

    def __init__(self, state: AppState = None, splash=None, parent=None):
        super().__init__(parent)
        self.state = state or AppState(self)
        self.splash = splash
        self.page_index_map: Dict[str, int] = {}
        self.view_instances: Dict[str, QWidget] = {}

        self.setWindowTitle("JobPilot — Desktop Job Automation Platform")
        app_icon = ThemeManager.get_app_icon()
        if not app_icon.isNull():
            self.setWindowIcon(app_icon)
        self.setMinimumSize(1024, 680)
        self.resize(1600, 900)
        self.setWindowState(Qt.WindowMaximized)

        # Central Widget & Root Layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = Sidebar(self)
        root_layout.addWidget(self.sidebar)

        # 2. Right Content Area (TopBar + Notifications + Viewport Stack)
        content_area = QWidget()
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # 2a. Top Bar
        self.top_bar = TopBar(self)
        content_layout.addWidget(self.top_bar)

        # 2b. Notification Banner
        self.notification_bar = NotificationBar(self)
        content_layout.addWidget(self.notification_bar)

        # 2c. Central Stacked Widget
        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setStyleSheet(f"background-color: {COLORS['background']}; border: none;")

        # Dynamically register all views from NAV_ITEMS
        for idx, item in enumerate(NAV_ITEMS):
            if self.splash:
                try:
                    from PySide6.QtGui import QColor
                    self.splash.showMessage(
                        f"Loading {item.label}...",
                        Qt.AlignBottom | Qt.AlignHCenter,
                        QColor("#FF5F15")
                    )
                    self.splash.repaint()
                    from PySide6.QtWidgets import QApplication
                    QApplication.processEvents()
                except Exception:
                    pass
            view = item.view_class()
            if hasattr(view, "data_updated"):
                view.data_updated.connect(self.state.emit_data_updated)
            if hasattr(view, "set_app_state"):
                view.set_app_state(self.state)
            elif hasattr(view, "app_state"):
                setattr(view, "app_state", self.state)
            self.stacked_widget.addWidget(view)
            self.page_index_map[item.id] = idx
            self.view_instances[item.id] = view

            # Register keyboard shortcut if present
            if item.shortcut:
                shortcut = QShortcut(QKeySequence(item.shortcut), self)
                shortcut.activated.connect(lambda page_id=item.id: self.navigate_to(page_id))

        content_layout.addWidget(self.stacked_widget, 1)
        root_layout.addWidget(content_area, 1)

        # 3. Status Bar
        self.status_bar = StatusBar(self)
        self.setStatusBar(self.status_bar)

        self.sidebar.item_selected.connect(self.navigate_to)
        self.sidebar.filter_requested.connect(self._on_filter_requested)
        self.state.page_changed.connect(self._on_state_page_changed)
        self.state.notification_emitted.connect(self.notification_bar.show_message)
        self.state.status_changed.connect(self._on_status_changed)
        self.state.data_updated.connect(self._on_data_updated)

        # Reflect current initial status in status bar
        self.status_bar.set_database_status(self.state.database_status)
        self.status_bar.set_engine_status(self.state.engine_status)
        self.status_bar.set_automation_status(self.state.automation_status)

        # 4. Phase 15: Search & Notification Services
        self.search_service = SearchService()
        self.global_search_service = GlobalSearchService()
        self.navigator = AppNavigator(self)
        self.notification_service = NotificationService(parent=self)
        self.notification_service.notification_triggered.connect(
            lambda level, title, msg: self.state.notify(level, f"{title}: {msg}")
        )

        # Wire background outreach cadence coordinator
        try:
            from app.services.outreach_coordinator import OutreachCadenceCoordinator
            self.outreach_coordinator = OutreachCadenceCoordinator.get_instance()
            self.outreach_coordinator.due_followups_detected.connect(self._on_due_followups_detected)
            self.outreach_coordinator.start()
        except Exception as e:
            logger.debug("OutreachCadenceCoordinator startup: %s", e)

        # Wire automation manager signals to notification service and live real-time view updates
        automation_view = self.view_instances.get("automation")
        dashboard_view = self.view_instances.get("dashboard")
        logs_view = self.view_instances.get("logs")
        if automation_view and hasattr(automation_view, "manager"):
            mgr = automation_view.manager
            self.notification_service.connect_automation_manager(mgr)
            if dashboard_view and hasattr(dashboard_view, "set_automation_manager"):
                dashboard_view.set_automation_manager(mgr)
            if logs_view and hasattr(logs_view, "connect_automation_manager"):
                logs_view.connect_automation_manager(mgr)
            for sig_name in ("application_submitted", "run_finished"):
                sig = getattr(mgr, sig_name, None)
                if sig is not None and hasattr(sig, "connect"):
                    try:
                        sig.connect(lambda *_: self.state.emit_data_updated("pipeline"))
                    except Exception:
                        pass

        # Trigger initial reminder scan and start background timer
        self.notification_service.check_reminders()
        self.notification_service.start_reminder_timer(15)

        # Trigger background maintenance: auto-close stale applications if enabled
        QTimer.singleShot(1500, self._check_stale_applications)

        # Trigger background update check (delayed 4.5s so startup remains instantaneous)
        QTimer.singleShot(4500, self._check_for_updates)

        # Wire dashboard navigation & action requests
        if dashboard_view and hasattr(dashboard_view, "navigation_requested"):
            dashboard_view.navigation_requested.connect(self.navigate_to)
        if dashboard_view and hasattr(dashboard_view, "action_requested"):
            dashboard_view.action_requested.connect(self._on_dashboard_action_requested)


        # Wire jobs view universal application requests
        jobs_view = self.view_instances.get("jobs")
        if jobs_view and hasattr(jobs_view, "apply_universal_requested"):
            jobs_view.apply_universal_requested.connect(self._on_apply_universal_job)

        self.top_bar.toggle_sidebar_requested.connect(self.sidebar.toggle_collapse)
        self.top_bar.search_requested.connect(self.open_search_dialog)
        self.top_bar.refresh_requested.connect(self._on_global_refresh_requested)
        self.top_bar.profile_clicked.connect(lambda: self.navigate_to("profile"))
        self.top_bar.about_clicked.connect(self._show_about_dialog)
        self.shortcut_search = QShortcut(QKeySequence("Ctrl+K"), self)
        self.shortcut_search.activated.connect(self.open_search_dialog)
        self.shortcut_refresh_f5 = QShortcut(QKeySequence("F5"), self)
        self.shortcut_refresh_f5.activated.connect(self._on_global_refresh_requested)
        self.shortcut_refresh_ctrl_r = QShortcut(QKeySequence("Ctrl+R"), self)
        self.shortcut_refresh_ctrl_r.activated.connect(self._on_global_refresh_requested)

        # Reflect real candidate name in TopBar
        self._update_top_bar_user_name()

        # Initialize starting page to the AI Pilot Command Center
        self.navigate_to("pilot")

        # Auto-launch Onboarding Wizard on first run
        self._check_onboarding()

    def _update_top_bar_user_name(self) -> None:
        """Fetches and displays candidate's actual name in the top bar profile pill."""
        try:
            from app.services.profile_service import ProfileService
            user, _, _ = ProfileService().get_primary_user_profile()
            if user and user.name:
                self.top_bar.set_candidate_name(user.name)
        except Exception:
            pass

    def _check_onboarding(self) -> None:
        """Checks if onboarding has been completed; if not, schedules wizard launch."""
        import os
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return  # Skip in headless / test-run mode
        try:
            from app.db.session import SessionLocal, get_db_session
            from app.repositories.settings_repository import SettingsRepository
            with get_db_session(SessionLocal) as session:
                repo = SettingsRepository(session)
                completed = repo.get("general.onboarding_completed", False)
            if not completed:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(600, self.launch_onboarding)
        except Exception:
            pass

    def launch_onboarding(self) -> None:
        """Opens the Onboarding Setup Wizard dialog."""
        # Ensure any lingering splash screen is completely closed before showing modal wizard
        try:
            from PySide6.QtWidgets import QApplication, QSplashScreen
            for w in QApplication.topLevelWidgets():
                if isinstance(w, QSplashScreen):
                    w.close()
                    w.deleteLater()
        except Exception:
            pass
        from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
        wizard = OnboardingWizardDialog(parent=self)
        wizard.onboarding_completed.connect(self._on_onboarding_done)
        wizard.raise_()
        wizard.activateWindow()
        wizard.exec()

    def launch_product_tour(self) -> None:
        """Launches the contextual 11-stop product tour overlay."""
        if hasattr(self, "_product_tour") and self._product_tour and self._product_tour.isVisible():
            return
        from app.ui.widgets.tour_overlay import ProductTourOverlay
        self._product_tour = ProductTourOverlay(main_window=self, parent=self)
        self._product_tour.start()

    def _on_onboarding_done(self, data: dict) -> None:
        """Callback after the onboarding wizard finishes successfully."""
        self._update_top_bar_user_name()
        self.state.notify("success", "Welcome! Your profile, resume, and Q&A knowledge base are ready.")
        
        # Refresh views with the latest onboarding profile and facts
        for view_key in ("dashboard", "profile", "resumes", "qna"):
            view_inst = self.view_instances.get(view_key)
            if view_inst and hasattr(view_inst, "refresh"):
                try:
                    view_inst.refresh()
                except Exception:
                    pass

        # Trigger single product tour overlay
        from PySide6.QtCore import QTimer
        QTimer.singleShot(400, self.launch_product_tour)

    def open_search_dialog(self) -> None:
        """Opens the global command palette search dialog."""
        dialog = GlobalSearchDialog(search_service=self.global_search_service, parent=self)
        dialog.result_item_selected.connect(self._on_search_result_selected)
        dialog.exec()

    def _on_search_result_selected(self, result_or_route: object, entity_id: Optional[int] = None) -> None:
        """Navigates to the page and exact entity corresponding to the selected search result."""
        if isinstance(result_or_route, SearchResult):
            action_mode = (
                NavigationAction.FILTER
                if result_or_route.action == "filter"
                else (NavigationAction(result_or_route.action) if isinstance(result_or_route.action, str) else result_or_route.action)
            )
            request = NavigationRequest(
                route=result_or_route.target_route,
                entity_type=result_or_route.entity_type,
                entity_id=result_or_route.entity_id,
                action=action_mode,
                focus=True,
            )
            self.navigator.navigate(request)
        elif isinstance(result_or_route, str):
            if entity_id is not None:
                action_mode = NavigationAction.FILTER if result_or_route in ("jobs", "applications") else NavigationAction.FOCUS
                request = NavigationRequest(
                    route=result_or_route,
                    entity_type=result_or_route.rstrip("s"),
                    entity_id=entity_id,
                    action=action_mode,
                    focus=True,
                )
                self.navigator.navigate(request)
            else:
                self.navigate_to(result_or_route)

    def navigate_to(self, page_id: str):
        """Switches the active view to page_id."""
        if page_id == "qna":
            self.navigate_to("profile")
            profile_view = self.view_instances.get("profile")
            if profile_view and hasattr(profile_view, "tabs"):
                profile_view.tabs.setCurrentIndex(1)
            return

        if page_id in self.page_index_map:
            self.state.set_current_page(page_id)

    def _on_state_page_changed(self, page_id: str):
        if page_id in self.page_index_map:
            idx = self.page_index_map[page_id]
            self.stacked_widget.setCurrentIndex(idx)
            self.sidebar.set_active_item(page_id)
            self.top_bar.set_active_page(page_id)

            # Ensure newly activated view displays the latest real-time data
            widget = self.stacked_widget.widget(idx)
            if hasattr(widget, "refresh"):
                try:
                    widget.refresh()
                except Exception:
                    pass

    def _on_filter_requested(self, filter_key: str) -> None:
        """Routes sidebar filter requests (Easy Apply, Company Portal) to the jobs view."""
        jobs_view = self.view_instances.get("jobs")
        if jobs_view and hasattr(jobs_view, "apply_external_filter"):
            jobs_view.apply_external_filter(filter_key)

    def _on_apply_universal_job(self, job: object) -> None:
        """Switches to automation cockpit and pre-populates target for Universal ATS Agent."""
        self.navigate_to("automation")
        automation_view = self.view_instances.get("automation")
        if automation_view and hasattr(automation_view, "prepare_universal_run"):
            automation_view.prepare_universal_run(job)

    def _on_dashboard_action_requested(self, action_type: str, payload: dict) -> None:
        """Handles deep action routing from the Dashboard work queues to target views."""
        if action_type in ("NAVIGATE_JOB", "REVIEW_JOB"):
            job_id = payload.get("job_id")
            self.navigate_to("jobs")
            jobs_view = self.view_instances.get("jobs")
            if jobs_view and job_id and hasattr(jobs_view, "inspect_job_by_id"):
                jobs_view.inspect_job_by_id(job_id)

        elif action_type in ("NAVIGATE_OUTREACH", "OPEN_CONVERSATION", "DRAFT_REPLY"):
            app_id = payload.get("application_id") or payload.get("conversation_id")
            self.navigate_to("outreach")
            outreach_view = self.view_instances.get("outreach")
            if outreach_view and app_id and hasattr(outreach_view, "select_conversation"):
                outreach_view.select_conversation(app_id)

        elif action_type in ("NAVIGATE_INTERVIEW", "PREPARE_INTERVIEW"):
            iv_id = payload.get("interview_id")
            self.navigate_to("interviews")
            iv_view = self.view_instances.get("interviews")
            if iv_view and iv_id and hasattr(iv_view, "inspect_interview_by_id"):
                iv_view.inspect_interview_by_id(iv_id)

        elif action_type in ("NAVIGATE_FOLLOWUP", "REVIEW_FOLLOWUP", "COMPOSE_FOLLOWUP"):
            fu_id = payload.get("followup_id")
            self.navigate_to("followups")
            fu_view = self.view_instances.get("followups")
            if fu_view and fu_id and hasattr(fu_view, "highlight_follow_up"):
                fu_view.highlight_follow_up(fu_id)

        elif action_type in ("NAVIGATE_APPLICATION", "REVIEW_APPLICATION"):
            app_id = payload.get("application_id")
            self.navigate_to("applications")
            apps_view = self.view_instances.get("applications")
            if apps_view and app_id and hasattr(apps_view, "inspect_application_by_id"):
                apps_view.inspect_application_by_id(app_id)

        elif action_type == "OPEN_URL":
            url = payload.get("url")
            if url:
                from PySide6.QtCore import QUrl
                from PySide6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl(url))

        elif action_type == "SEARCH_JOBS":
            self.navigate_to("jobs")

        elif action_type.startswith("NAVIGATE_"):
            page_id = action_type.replace("NAVIGATE_", "").lower()
            self.navigate_to(page_id)

    def _on_data_updated(self, entity: str = "general") -> None:
        """Broadcasts real-time entity updates to all views."""
        # Always refresh dashboard to ensure live mission control metrics
        dashboard = self.view_instances.get("dashboard")
        if dashboard and hasattr(dashboard, "refresh"):
            try:
                dashboard.refresh()
            except Exception:
                pass

        # Also refresh active view if it is not dashboard
        curr = self.get_current_view()
        if curr and curr is not dashboard and hasattr(curr, "refresh"):
            try:
                curr.refresh()
            except Exception:
                pass

        # If pipeline, applications, interviews, followups, jobs, outreach or dashboard updated, ensure related views are refreshed
        if entity in ["applications", "interviews", "followups", "pipeline", "jobs", "outreach", "dashboard", "general", "all"]:
            for v_id in ["applications", "interviews", "followups", "jobs", "analytics", "automation", "outreach"]:
                v = self.view_instances.get(v_id)
                if v and v != curr and hasattr(v, "refresh"):
                    try:
                        v.refresh()
                    except Exception:
                        pass

        # If search criteria updated, refresh search and platform views
        if entity in ["search", "platforms", "all"]:
            for v_id in ["search", "platforms"]:
                v = self.view_instances.get(v_id)
                if v and v != curr and hasattr(v, "refresh"):
                    try:
                        v.refresh()
                    except Exception:
                        pass

        # If profile/candidate updated, refresh TopBar candidate badge
        if entity in ["profile", "candidate", "all"]:
            self._update_top_bar_user_name()

    def _on_global_refresh_requested(self) -> None:
        """Global refresh trigger from TopBar or F5/Ctrl+R: refreshes active view and broadcasts to all."""
        curr = self.get_current_view()
        if curr and hasattr(curr, "refresh"):
            try:
                curr.refresh()
            except Exception:
                pass
        self._on_data_updated("all")
        self.state.notify("info", "All views refreshed and synchronized.")

    def _check_stale_applications(self) -> None:
        """Background maintenance check to auto-close stale applications based on configured settings."""
        try:
            from app.services.application_service import ApplicationService
            app_service = ApplicationService()
            res = app_service.auto_close_stale_applications()
            if res.get("closed_count", 0) > 0:
                count = res["closed_count"]
                days = res.get("inactivity_days", 60)
                self.state.notify(
                    "info",
                    f"Auto-archived {count} stale application{'s' if count > 1 else ''} older than {days} days.",
                )
                self._on_data_updated("pipeline")
        except Exception as e:
            logger.debug("Auto-close stale applications check: %s", e)


    def _on_status_changed(self, component: str, status_text: str):
        """Updates status bar labels when AppState status changes."""
        if component == "engine":
            self.status_bar.set_engine_status(status_text)
            # Mirror engine status to sidebar footer
            ok = "ready" in status_text.lower() or "idle" in status_text.lower()
            self.sidebar.set_engine_status(status_text, ok)
        elif component == "database":
            self.status_bar.set_database_status(status_text)
        elif component == "automation":
            self.status_bar.set_automation_status(status_text)

    def _on_theme_changed(self, mode: str) -> None:
        """Propagates theme change to sidebar, top bar, and all active views."""
        if hasattr(self, "sidebar") and hasattr(self.sidebar, "update_theme"):
            self.sidebar.update_theme()
        if hasattr(self, "top_bar") and hasattr(self.top_bar, "update_theme"):
            self.top_bar.update_theme(mode)
        for view in self.view_instances.values():
            if hasattr(view, "refresh"):
                try:
                    view.refresh()
                except Exception:
                    pass

    def get_current_view(self) -> QWidget:
        """Returns the currently active view widget."""
        return self.stacked_widget.currentWidget()

    def _show_about_dialog(self) -> None:
        """Displays official About JobPilot modal with brand assets and platform specs."""
        from app.ui.widgets.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_due_followups_detected(self, due_list: list) -> None:
        """Surfaces due follow-ups in the global notification bar with interactive review."""
        if not due_list:
            return
        first = due_list[0]
        comp = first.get("company_name") or "Recruiter"
        role = first.get("job_title") or "Application"
        last_sent = str(first.get("last_email_sent_at") or "")[:10]
        time_str = f" (last sent {last_sent})" if last_sent else ""
        msg = f"Follow-up reminder: {len(due_list)} cadence due for {comp} — {role}{time_str}."

        def _open_review():
            try:
                from app.ui.views.outreach.followup_review_dialog import FollowUpReviewDialog
                dialog = FollowUpReviewDialog(first, parent=self)
                dialog.exec()
            except Exception as e:
                self.notification_bar.show_message("warning", f"Could not open review: {e}")

        self.notification_bar.show_action("warning", msg, "Review Follow-Up", _open_review, duration_ms=15000)

    def _check_for_updates(self) -> None:
        """Asynchronously checks for newer JobPilot releases without blocking UI."""
        from app.services.update_service import UpdateService, UpdateCheckWorker
        from app.services.automation_service import AutomationService

        # Safety gate: never check or prompt if automation engine is actively running
        mgr = AutomationService.get_instance()
        if mgr and mgr.is_running():
            return

        self._update_service = UpdateService()
        self._update_worker = UpdateCheckWorker(self._update_service, parent=self)
        self._update_worker.update_found.connect(self._on_update_found)
        self._update_worker.start()

    def _on_update_found(self, update_info: object) -> None:
        """Surfaces non-intrusive notification banner with 1-click update action."""
        from app.ui.dialogs.update_dialog import UpdateDialog

        def open_update_modal():
            dialog = UpdateDialog(update_info=update_info, update_service=self._update_service, parent=self)
            dialog.exec()

        ver_str = getattr(update_info, "version", "")
        self.notification_bar.show_action(
            "info",
            f"JobPilot v{ver_str} is available with new improvements!",
            "View & Update",
            open_update_modal,
            duration_ms=15000,
        )

    def closeEvent(self, event) -> None:
        """Gracefully stops timers, background workers, and coordinates system teardown."""
        if hasattr(self, "outreach_coordinator") and self.outreach_coordinator:
            try:
                self.outreach_coordinator.stop()
            except Exception:
                pass

        dashboard = self.view_instances.get("dashboard")
        if dashboard and hasattr(dashboard, "stop_workers"):
            try:
                dashboard.stop_workers()
            except Exception:
                pass
        logs_view = self.view_instances.get("logs")
        if logs_view and hasattr(logs_view, "_poll_timer") and logs_view._poll_timer.isActive():
            try:
                logs_view._poll_timer.stop()
            except Exception:
                pass

        # Trigger authoritative application lifecycle shutdown
        try:
            from app.services.os.lifecycle_manager import ApplicationLifecycleManager
            ApplicationLifecycleManager.shutdown_application(timeout_ms=2500)
        except Exception:
            pass

        super().closeEvent(event)

