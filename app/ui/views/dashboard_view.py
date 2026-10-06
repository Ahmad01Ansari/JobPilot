"""Redesigned Dashboard Command Center and Today's Job Hunt view.

Acts as the operational home of JobPilot answering:
    "What should I do today to maximize my chances of getting my next job?"

Layout Hierarchy:
    1. Top Header & Readiness Strip (compact factual indicators)
    2. Next Best Action (Hero card)
    3. Today's Job Hunt (work queue cards or clean empty state)
    4. Today's Progress (5-card metrics strip)
    5. Workspace split: Left = Top Opportunities, Right = Search Performance
    6. Secondary row: Pipeline Funnel (Left) + Recent Activity (Right)
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QSize, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardService
from app.services.dto.dashboard_dto import DashboardSnapshotDTO, SearchPerformanceDTO
from app.services.profile_service import ProfileService
from app.services.recruitment_service import RecruitmentService
from app.ui.theme import COLORS
from app.ui.widgets.dashboard.daily_progress import DailyProgressWidget
from app.ui.widgets.dashboard.kpi_metrics_bar import DashboardKPICardsBar
from app.ui.widgets.dashboard.needs_attention import NeedsAttentionWidget
from app.ui.widgets.dashboard.next_best_action import NextBestActionWidget
from app.ui.widgets.dashboard.readiness_strip import ReadinessStrip
from app.ui.widgets.dashboard.search_performance import SearchPerformanceWidget
from app.ui.widgets.dashboard.todays_job_hunt import TodaysJobHuntWidget
from app.ui.widgets.dashboard.top_opportunities import TopOpportunitiesWidget
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.pipeline_funnel import PipelineFunnelCard
from app.ui.widgets.upcoming_schedules import UpcomingSchedulesCard
from app.utils_time import format_local_datetime, get_application_timezone, to_local_datetime


class _DashboardLoadWorker(QThread):
    """Background worker fetching complete dashboard snapshot without freezing the GUI."""

    snapshot_loaded = Signal(object)  # DashboardSnapshotDTO
    load_failed = Signal(str)

    def __init__(self, service: DashboardService):
        super().__init__()
        self._service = service

    def run(self) -> None:
        try:
            # 1. INSTANT FIRST PAINT: Fetch and emit local DB snapshot immediately (<100ms)
            snapshot = self._service.get_dashboard_snapshot()
            self.snapshot_loaded.emit(snapshot)

            # 2. BACKGROUND SYNC: Check external mailbox without delaying UI load
            try:
                from app.services.inbound_sync_service import InboundSyncService
                inbound_sync = InboundSyncService(session_factory=self._service._session_factory)
                sync_res = inbound_sync.sync_mailbox()
                # If new recruiter messages or replies were ingested, refresh snapshot
                if sync_res and (sync_res.get("ingested_count", 0) > 0 or sync_res.get("replies_count", 0) > 0):
                    fresh_snapshot = self._service.get_dashboard_snapshot()
                    self.snapshot_loaded.emit(fresh_snapshot)
            except Exception as sync_err:
                logger.debug("Background mailbox sync skipped/idle: %s", sync_err)
        except Exception as e:
            self.load_failed.emit(str(e))


class _SearchPerfWorker(QThread):
    """Background worker fetching search performance for a timeframe preset."""

    perf_loaded = Signal(object)
    load_failed = Signal(str)

    def __init__(self, service: DashboardService, preset: str):
        super().__init__()
        self._service = service
        self._preset = preset

    def run(self) -> None:
        try:
            perf = self._service.get_search_performance(preset=self._preset)
            self.perf_loaded.emit(perf)
        except Exception as e:
            self.load_failed.emit(str(e))





class DashboardView(QWidget):
    """Dashboard Command Center view for JobPilot."""

    navigation_requested = Signal(str)
    action_requested = Signal(str, dict)  # (action_type, payload)

    def __init__(
        self,
        service: Optional[DashboardService] = None,
        profile_service: Optional[ProfileService] = None,
        recruitment_service: Optional[RecruitmentService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or DashboardService()
        self.profile_service = profile_service or ProfileService()
        self.recruitment_service = recruitment_service or RecruitmentService()
        self.automation_manager = None
        self._load_worker: Optional[_DashboardLoadWorker] = None
        self._perf_worker: Optional[_SearchPerfWorker] = None

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Page Header with Integrated Readiness Strip and Refresh
        self.header = PageHeader(
            title="Dashboard Overview",
            subtitle="Your job-search command center.",
        )

        self.readiness_strip = ReadinessStrip(self)
        self.readiness_strip.navigate_requested.connect(self.navigation_requested.emit)
        self.header.add_action_widget(self.readiness_strip)

        self.btn_refresh = QPushButton("↻ Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # 2. Notification Toast Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # Subtle "Finish Setting Up JobPilot" banner (visible if onboarding is not finished)
        self.setup_banner = QFrame()
        self.setup_banner.setVisible(False)
        self.setup_banner.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-left: 4px solid {COLORS['primary']};
                border-radius: 8px;
                padding: 10px 16px;
            }}
        """)
        sb_layout = QHBoxLayout(self.setup_banner)
        sb_layout.setContentsMargins(12, 6, 12, 6)
        sb_layout.setSpacing(10)
        self.lbl_setup_msg = QLabel("⚡ Finish setting up JobPilot: complete your recommended workspace steps.")
        self.lbl_setup_msg.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        sb_layout.addWidget(self.lbl_setup_msg)
        sb_layout.addStretch()

        self.btn_dismiss_setup = QPushButton("Dismiss / Mark Done ✓")
        self.btn_dismiss_setup.setCursor(Qt.PointingHandCursor)
        self.btn_dismiss_setup.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_dismiss_setup.clicked.connect(self._on_dismiss_setup_clicked)
        sb_layout.addWidget(self.btn_dismiss_setup)

        self.btn_resume_setup = QPushButton("Continue Setup ►")
        self.btn_resume_setup.setCursor(Qt.PointingHandCursor)
        self.btn_resume_setup.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 11px;
                border-radius: 6px;
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_resume_setup.clicked.connect(self._on_continue_setup_clicked)
        sb_layout.addWidget(self.btn_resume_setup)
        main_layout.addWidget(self.setup_banner)

        # 3. Scrollable Main Canvas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(0, 2, 0, 8)
        self.content_layout.setSpacing(14)

        # A. Top KPI Cards Bar (Command Center Pipeline Overview)
        self.kpi_bar = DashboardKPICardsBar(container)
        self.kpi_bar.navigation_requested.connect(self._on_kpi_navigation)
        self.content_layout.addWidget(self.kpi_bar)

        # B. Hero: Next Best Action
        self.nba_widget = NextBestActionWidget(container)
        self.nba_widget.action_triggered.connect(self._on_dashboard_action)
        self.content_layout.addWidget(self.nba_widget)

        # C. Today's Job Hunt Work Queue
        self.todays_hunt_widget = TodaysJobHuntWidget(container)
        self.todays_hunt_widget.action_triggered.connect(self._on_dashboard_action)
        self.todays_hunt_widget.search_requested.connect(lambda: self.navigation_requested.emit("search"))
        self.content_layout.addWidget(self.todays_hunt_widget)

        # D. Two-Column Main Workspace: Left = Top Opportunities, Right = Search Performance
        # D. Row 3: Top Opportunities (Left, 55%) | Search Performance (Right, 45%)
        row3_layout = QHBoxLayout()
        row3_layout.setContentsMargins(0, 0, 0, 0)
        row3_layout.setSpacing(14)

        self.top_opportunities_widget = TopOpportunitiesWidget(container)
        self.top_opportunities_widget.review_requested.connect(
            lambda jid: self.action_requested.emit("NAVIGATE_JOB", {"job_id": jid})
        )
        self.top_opportunities_widget.search_requested.connect(
            lambda: self.navigation_requested.emit("search")
        )
        self.top_opportunities_widget.action_triggered.connect(self.action_requested.emit)
        row3_layout.addWidget(self.top_opportunities_widget, 52)

        self.search_perf_widget = SearchPerformanceWidget(container)
        self.search_perf_widget.preset_changed.connect(self._on_search_perf_preset_changed)
        row3_layout.addWidget(self.search_perf_widget, 48)
        self.content_layout.addLayout(row3_layout)

        # E. Row 4: Upcoming Schedules (Left, 50%) | Recent Activity (Right, 50%)
        row4_layout = QHBoxLayout()
        row4_layout.setContentsMargins(0, 0, 0, 0)
        row4_layout.setSpacing(14)

        self.schedules_card = UpcomingSchedulesCard(container)
        self.schedules_card.action_triggered.connect(self.action_requested.emit)
        self.schedules_card.navigation_requested.connect(self.navigation_requested.emit)
        row4_layout.addWidget(self.schedules_card, 1)

        # Recent Human-Readable Activity Stream
        self.activity_frame = QFrame(container)
        self.activity_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        self.activity_layout = QVBoxLayout(self.activity_frame)
        self.activity_layout.setContentsMargins(16, 14, 16, 14)
        self.activity_layout.setSpacing(10)

        hdr_act = QHBoxLayout()
        hdr_act.setSpacing(8)
        lbl_act_icon = QLabel("🕒")
        lbl_act_icon.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        hdr_act.addWidget(lbl_act_icon)

        lbl_act_title = QLabel("RECENT ACTIVITY")
        lbl_act_title.setStyleSheet(f"font-size: 13px; font-weight: 800; letter-spacing: 0.5px; color: {COLORS['text']}; background: transparent; border: none;")
        hdr_act.addWidget(lbl_act_title)
        hdr_act.addStretch(1)

        self.btn_view_all_activity = QPushButton("View All Activity →")
        self.btn_view_all_activity.setCursor(Qt.PointingHandCursor)
        self.btn_view_all_activity.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['primary']};
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_view_all_activity.clicked.connect(self._on_view_all_activity_clicked)
        hdr_act.addWidget(self.btn_view_all_activity)
        self.activity_layout.addLayout(hdr_act)

        self.activity_container = QVBoxLayout()
        self.activity_container.setContentsMargins(0, 4, 0, 0)
        self.activity_container.setSpacing(6)
        self.activity_layout.addLayout(self.activity_container)
        self.activity_layout.addStretch(1)

        row4_layout.addWidget(self.activity_frame, 1)
        self.content_layout.addLayout(row4_layout)

        # Retain backwards-compatible references isolated in a hidden sink
        self._hidden_sink = QWidget()
        self._hidden_sink.hide()
        from app.ui.widgets.platform_trigger_deck import PlatformTriggerDeck
        self.trigger_deck = PlatformTriggerDeck(self._hidden_sink)
        self.funnel_card = PipelineFunnelCard(self._hidden_sink)
        self.cockpit_trigger_card = QFrame(self._hidden_sink)
        self.needs_attention_widget = NeedsAttentionWidget(self._hidden_sink)
        self.needs_attention_widget.action_triggered.connect(self.action_requested.emit)

        # Add vertical stretch so content never stretches unnaturally downwards
        self.content_layout.addStretch(1)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def refresh(self) -> None:
        """Launches asynchronous load worker to update all dashboard sections."""
        if self._load_worker and self._load_worker.isRunning():
            return

        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("Refreshing...")

        self._load_worker = _DashboardLoadWorker(self.service)
        self._load_worker.snapshot_loaded.connect(self._on_snapshot_loaded)
        self._load_worker.load_failed.connect(self._on_load_failed)
        self._load_worker.start()

    def _on_snapshot_loaded(self, snapshot: DashboardSnapshotDTO) -> None:
        """Applies loaded snapshot to all widgets safely on the Qt main thread."""
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("↻ Refresh")

        # 1. Next Best Action Hero Card
        self.nba_widget.set_action(snapshot.next_best_action)

        # 1. Top KPI Metrics Bar
        sub_count = snapshot.pipeline_summary.get("submitted", 0)
        rev_count = snapshot.pipeline_summary.get("under_review", 0)
        iv_count = snapshot.pipeline_summary.get("interviews", 0)
        off_count = snapshot.pipeline_summary.get("offers", 0)
        wd_count = snapshot.pipeline_summary.get("withdrawn", 0)
        rej_count = snapshot.pipeline_summary.get("rejected", 0)
        disc_count = snapshot.pipeline_summary.get("total_jobs", 0)
        if not disc_count and snapshot.search_performance:
            disc_count = snapshot.search_performance.total_discovered

        self.kpi_bar.update_metrics(
            total_jobs=disc_count,
            submitted=sub_count,
            under_review=rev_count,
            interviewing=iv_count,
            offers=off_count,
            rejected=rej_count,
        )

        # 2. Today's Job Hunt Queue
        self.todays_hunt_widget.set_items(snapshot.hunt_items)

        # 3. Top Qualified Opportunities
        self.top_opportunities_widget.set_opportunities(snapshot.top_opportunities)

        # 4. Needs Attention (compact summary, driven by same hunt items)
        self.needs_attention_widget.set_items(snapshot.hunt_items)

        # 5. Readiness Strip
        self.readiness_strip.set_readiness(snapshot.readiness)

        # 5b. Update subtle setup banner
        try:
            is_dismissed = self.settings_service.get("general.setup_banner_dismissed", False)
            is_completed = self.settings_service.get("general.onboarding_completed", False)
            if is_dismissed or is_completed:
                self.setup_banner.setVisible(False)
            else:
                from app.services.setup.setup_readiness import SetupReadinessService
                r_report = SetupReadinessService().evaluate()
                if not r_report.is_core_ready:
                    self.setup_banner.setVisible(True)
                    self.lbl_setup_msg.setText(f"⚡ Finish setting up JobPilot: {r_report.core_summary}.")
                elif not r_report.is_automation_ready:
                    self.setup_banner.setVisible(True)
                    self.lbl_setup_msg.setText(f"⚡ Unlock autonomous agent: {r_report.recommended_summary}.")
                else:
                    self.setup_banner.setVisible(False)
        except Exception:
            self.setup_banner.setVisible(False)

        # 6. Search Performance & Funnel
        if snapshot.search_performance:
            self.search_perf_widget.set_performance(snapshot.search_performance)

        # 7. Pipeline Funnel (legacy widget, still useful as secondary view)
        self.funnel_card.update_stages(
            discovered=disc_count,
            submitted=sub_count,
            under_review=rev_count,
            interview=iv_count,
            offer=off_count,
            withdrawn=wd_count,
            rejected=rej_count,
        )

        # 8. Upcoming Schedules
        self._render_schedules()

        # 9. Recent Activities
        self._render_activities(snapshot.recent_activities)

    def _on_dashboard_action(self, action_type: str, payload: dict) -> None:
        """Handles dashboard actions, status overrides, and dismissals locally or forwards navigation."""
        if action_type == "CHANGE_APPLICATION_STATUS":
            app_id = payload.get("application_id")
            new_status = payload.get("new_status")
            if app_id and new_status:
                try:
                    self.service.application_service.transition_status(
                        application_id=app_id,
                        new_status=new_status,
                        source="USER",
                        notes=f"Status changed to {new_status} via Dashboard",
                        allow_override=True,
                    )
                    clean_name = new_status.replace("_", " ").title()
                    self.notification_bar.show_message("success", f"Application updated to {clean_name}.")
                    self.refresh()
                    return
                except Exception as e:
                    self.notification_bar.show_message("danger", f"Failed to update status: {e}")
                    return

        elif action_type == "DISMISS_ITEM":
            app_id = payload.get("application_id")
            source_type = payload.get("source_type")
            source_id = payload.get("source_id")

            try:
                if app_id:
                    self.service.application_service.transition_status(
                        application_id=app_id,
                        new_status="NOT_APPLIED",
                        source="USER",
                        notes="Dismissed from Dashboard Today's Hunt queue",
                        allow_override=True,
                    )
                elif source_type == "followup" and source_id:
                    self.recruitment_service.update_follow_up(source_id, status="COMPLETED")
                elif source_type == "interview" and source_id:
                    self.recruitment_service.update_interview(source_id, status="COMPLETED")

                self.notification_bar.show_message("info", "Item dismissed from queue.")
                self.refresh()
                return
            except Exception as e:
                self.notification_bar.show_message("warning", f"Could not dismiss item: {e}")
                return

        # Forward navigation actions to MainWindow
        self.action_requested.emit(action_type, payload)

    def _on_kpi_navigation(self, target_view: str, params: Optional[dict] = None) -> None:
        """Handles drill-down navigation from top KPI metric cards."""
        self.navigation_requested.emit(target_view)

    def _on_load_failed(self, error_msg: str) -> None:
        """Handles background fetch failure gracefully."""
        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("↻ Refresh")
        self.notification_bar.show_message("warning", f"Failed to refresh dashboard: {error_msg}")

    def _render_schedules(self) -> None:
        """Fetches upcoming scheduled interview rounds for the schedules card."""
        try:
            interviews = self.recruitment_service.list_interviews(status="SCHEDULED", limit=3)
            schedules = []
            for iv in interviews:
                app = iv.application
                job = app.job if app else None
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Role")
                time_str = (
                    format_local_datetime(iv.scheduled_at, "%b %d, %I:%M %p")
                    if iv.scheduled_at
                    else "Scheduled"
                )
                schedules.append({
                    "round_name": iv.round_name or "Interview",
                    "role_company": f"{title} @ {company}",
                    "time_str": time_str,
                    "link": iv.meeting_link,
                })
            self.schedules_card.set_schedules(schedules)
        except Exception:
            self.schedules_card.set_schedules([])

    def _on_search_perf_preset_changed(self, preset: str) -> None:
        """Asynchronously updates the search performance metrics when timeframe preset changes."""
        if self._perf_worker and self._perf_worker.isRunning():
            self._perf_worker.terminate()
            self._perf_worker.wait(200)

        self._perf_worker = _SearchPerfWorker(self.service, preset)
        self._perf_worker.perf_loaded.connect(self.search_perf_widget.set_performance)
        self._perf_worker.start()

    def _render_activities(self, events: List[Any]) -> None:
        """Renders recent human-readable timeline events."""
        while self.activity_container.count():
            item = self.activity_container.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not events:
            lbl_empty = QLabel("No recent system activity recorded.")
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; padding: 16px; background: transparent; border: none;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.activity_container.addWidget(lbl_empty)
            lbl_empty.show()
            return

        def _format_event_time(dt: Optional[datetime], platform_str: str) -> str:
            if not dt:
                return platform_str
            loc_dt = to_local_datetime(dt)
            if not loc_dt:
                return platform_str
            now_local = datetime.now(get_application_timezone())
            if loc_dt.date() == now_local.date():
                time_part = loc_dt.strftime("%I:%M %p").lstrip("0")
                return f"Today, {time_part} • {platform_str}"
            elif loc_dt.date() == (now_local.date() - timedelta(days=1)):
                return f"Yesterday • {platform_str}"
            else:
                return f"{loc_dt.strftime('%b %d')} • {platform_str}"

        labels_map = {
            "APPLICATION_SUBMITTED": "Application submitted",
            "RECRUITER_REPLIED": "Recruiter replied",
            "INTERVIEW_SCHEDULED": "Interview scheduled",
            "JOB_QUALIFIED": "Job qualified",
            "JOB_DISCOVERED": "Job discovered",
            "STATUS_CHANGED": "Status updated",
        }

        for ev in events[:4]:  # Display top 4 recent human activities
            row = QFrame()
            row.setCursor(Qt.PointingHandCursor)
            row.setFixedHeight(52)
            row.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border_subtle']};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                }}
            """)
            r_layout = QHBoxLayout(row)
            r_layout.setContentsMargins(12, 6, 12, 6)
            r_layout.setSpacing(10)

            plat_str = (ev.platform or "Portal").title()
            event_label = labels_map.get(ev.event_type, "Activity update")
            meta_str = _format_event_time(ev.timestamp, plat_str)

            desc_layout = QVBoxLayout()
            desc_layout.setContentsMargins(0, 0, 0, 0)
            desc_layout.setSpacing(2)

            top_meta = QHBoxLayout()
            top_meta.setContentsMargins(0, 0, 0, 0)
            top_meta.setSpacing(8)

            lbl_cat = QLabel(event_label)
            lbl_cat.setStyleSheet(f"font-weight: 700; color: {COLORS['primary']}; font-size: 11px; background: transparent; border: none;")
            top_meta.addWidget(lbl_cat)

            lbl_m = QLabel(f"• {meta_str}")
            lbl_m.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent; border: none;")
            top_meta.addWidget(lbl_m)
            top_meta.addStretch(1)
            desc_layout.addLayout(top_meta)

            clean_title = ev.title if len(ev.title) <= 52 else f"{ev.title[:49]}..."
            lbl_t = QLabel(clean_title)
            lbl_t.setStyleSheet(f"font-weight: 700; color: {COLORS['text']}; font-size: 12px; background: transparent; border: none;")
            desc_layout.addWidget(lbl_t)

            r_layout.addLayout(desc_layout, 1)

            btn_details = QPushButton("Details →")
            btn_details.setCursor(Qt.PointingHandCursor)
            btn_details.setFixedHeight(26)
            btn_details.setStyleSheet(f"""
                QPushButton {{
                    color: {COLORS['primary']};
                    background-color: {COLORS['surface_elevated']};
                    border: 1px solid {COLORS['border_subtle']};
                    border-radius: 5px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 10px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    border-color: {COLORS['primary']};
                }}
            """)
            btn_details.clicked.connect(lambda _, event=ev: self._show_event_detail(event))
            r_layout.addWidget(btn_details, alignment=Qt.AlignVCenter)

            row.mousePressEvent = lambda e, event=ev: self._show_event_detail(event)
            self.activity_container.addWidget(row)
            row.show()

    def _show_event_detail(self, event: Any) -> None:
        """Opens detail dialog for an activity record."""
        from app.ui.widgets.activity_dialogs import ActivityDetailDialog
        dlg = ActivityDetailDialog(event, session_factory=self.service._session_factory, parent=self)
        dlg.exec()

    def _on_view_all_activity_clicked(self) -> None:
        """Opens full activity history dialog with platform filtering."""
        from app.ui.widgets.activity_dialogs import AllActivityDialog
        all_events = self.service.get_recent_activity(limit=100)
        dlg = AllActivityDialog(all_events, session_factory=self.service._session_factory, parent=self)
        dlg.exec()

    def set_automation_manager(self, manager: Any) -> None:
        """Preserves automation manager connection for background runner compatibility."""
        self.automation_manager = manager

    @property
    def plat_container(self):
        class _CompatPlatformContainer:
            def count(self):
                return 4
            def itemAt(self, idx):
                return None
        return _CompatPlatformContainer()

    def _on_continue_setup_clicked(self) -> None:
        """Launches the Setup Wizard from the subtle dashboard banner."""
        win = self.window()
        if win and hasattr(win, "launch_onboarding"):
            win.launch_onboarding()

    def _on_dismiss_setup_clicked(self) -> None:
        """Dismisses the subtle dashboard banner and marks setup reminder as complete."""
        try:
            self.settings_service.set("general.setup_banner_dismissed", True)
            self.settings_service.set("general.onboarding_completed", True)
        except Exception:
            pass
        self.setup_banner.setVisible(False)

    def stop_workers(self) -> None:
        """Gracefully waits for background loaders to avoid QThread destruction aborts."""
        for worker in (self._load_worker, self._perf_worker):
            if worker and worker.isRunning():
                worker.requestInterruption()
                if not worker.wait(400):
                    try:
                        worker.terminate()
                        worker.wait(300)
                    except Exception:
                        pass

    def closeEvent(self, event) -> None:
        self.stop_workers()
        super().closeEvent(event)

