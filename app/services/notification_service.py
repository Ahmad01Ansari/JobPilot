"""Desktop notification and reminder service for JobPilot.

Handles native desktop tray notifications, in-app alert propagation, scheduled
interview reminders, due follow-up alerts, and real-time automation intervention alerts.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, Optional, Set

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon
from sqlalchemy import func, or_, select
from sqlalchemy.orm import joinedload, sessionmaker

from app.db.base import utc_now
from app.db.models import Application, Contact, FollowUp, Interview, Job
from app.db.session import SessionLocal, get_db_session
from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationRunResult,
    AutomationState,
)

logger = logging.getLogger(__name__)


class NotificationService(QObject):
    """Central service managing system tray notifications, interview reminders, and bot alerts."""

    # Signals: (level, title, message)
    notification_triggered = Signal(str, str, str)
    # Signal emitted when periodic reminder scan finishes: (interviews_count, followups_count)
    reminders_checked = Signal(int, int)

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        parent: Optional[QObject] = None,
        enable_tray: bool = True,
    ):
        super().__init__(parent)
        self._session_factory = session_factory or SessionLocal
        self._notified_interview_ids: Set[int] = set()
        self._notified_followup_ids: Set[int] = set()

        # Settings
        self.desktop_notifications_enabled: bool = True
        self.notify_interviews: bool = True
        self.notify_followups: bool = True
        self.notify_automation_interventions: bool = True
        self.notify_automation_completion: bool = True
        self.notify_application_submitted: bool = True

        # System Tray initialization
        self.tray_icon: Optional[QSystemTrayIcon] = None
        if enable_tray and QSystemTrayIcon.isSystemTrayAvailable():
            self._init_tray_icon()

        # Periodic reminder poller timer
        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self.check_reminders)

    def _init_tray_icon(self) -> None:
        """Initializes the QSystemTrayIcon if available."""
        try:
            from app.ui.theme import ThemeManager
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setToolTip("JobPilot — Desktop Job Automation Platform")
            tray_icon = ThemeManager.get_tray_icon(active=False)
            if not tray_icon.isNull():
                self.tray_icon.setIcon(tray_icon)

            tray_menu = QMenu()
            action_reminders = tray_menu.addAction("Check Reminders Now")
            action_reminders.triggered.connect(self.check_reminders)
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.show()
        except Exception as exc:
            logger.warning("Failed to initialize QSystemTrayIcon: %s", exc)
            self.tray_icon = None

    def set_tray_active(self, active: bool = True) -> None:
        """Updates system tray icon to show active status indicator or idle state."""
        if self.tray_icon:
            try:
                from app.ui.theme import ThemeManager
                self.tray_icon.setIcon(ThemeManager.get_tray_icon(active=active))
            except Exception:
                pass

    def start_reminder_timer(self, interval_minutes: int = 15) -> None:
        """Starts periodic reminder check timer."""
        interval_ms = max(1, interval_minutes) * 60 * 1000
        self._reminder_timer.start(interval_ms)

    def stop_reminder_timer(self) -> None:
        """Stops periodic reminder check timer."""
        if self._reminder_timer.isActive():
            self._reminder_timer.stop()

    def notify(
        self,
        title: str,
        message: str,
        level: str = "info",
        category: str = "general",
    ) -> None:
        """Dispatches notification via desktop balloon and in-app signal.

        Args:
            title: Notification header.
            message: Body text.
            level: 'info', 'success', 'warning', or 'error'.
            category: 'interview', 'followup', 'automation', 'general'.
        """
        # 1. Desktop Notification
        if self.desktop_notifications_enabled and self.tray_icon and self.tray_icon.isVisible():
            icon_map = {
                "info": QSystemTrayIcon.MessageIcon.Information,
                "success": QSystemTrayIcon.MessageIcon.Information,
                "warning": QSystemTrayIcon.MessageIcon.Warning,
                "error": QSystemTrayIcon.MessageIcon.Critical,
            }
            tray_msg_icon = icon_map.get(level.lower(), QSystemTrayIcon.MessageIcon.Information)
            try:
                self.tray_icon.showMessage(title, message, tray_msg_icon, 6000)
            except Exception as exc:
                logger.debug("Failed to display system tray message: %s", exc)

        # 2. In-App Notification Signal
        self.notification_triggered.emit(level, title, message)

    def check_reminders(self) -> Dict[str, int]:
        """Scans database for upcoming interviews and due/overdue follow-ups."""
        interviews_count = 0
        followups_count = 0

        now = utc_now()
        interview_horizon = now + timedelta(hours=24)
        followup_horizon = now + timedelta(hours=12)

        with get_db_session(self._session_factory) as session:
            # 1. Check Interviews
            if self.notify_interviews:
                stmt_int = (
                    select(Interview)
                    .options(
                        joinedload(Interview.application).joinedload(Application.job)
                    )
                    .where(
                        Interview.status == "SCHEDULED",
                        Interview.scheduled_at >= now,
                        Interview.scheduled_at <= interview_horizon,
                    )
                    .order_by(Interview.scheduled_at.asc())
                )
                upcoming_interviews = session.execute(stmt_int).scalars().all()

                for interview in upcoming_interviews:
                    if interview.id not in self._notified_interview_ids:
                        self._notified_interview_ids.add(interview.id)
                        interviews_count += 1

                        app = interview.application
                        job = app.job if app else None
                        company = job.company_raw if job else "Company"
                        role = job.title if job else "Position"
                        time_str = interview.scheduled_at.strftime("%I:%M %p, %b %d")

                        self.notify(
                            title=f"Upcoming Interview: {role}",
                            message=f"{interview.round_name} Round with {company} at {time_str} ({interview.mode}).",
                            level="info",
                            category="interview",
                        )

            # 2. Check Follow-Ups
            if self.notify_followups:
                stmt_fu = (
                    select(FollowUp)
                    .options(
                        joinedload(FollowUp.application).joinedload(Application.job),
                        joinedload(FollowUp.contact),
                    )
                    .where(
                        FollowUp.status == "PENDING",
                        FollowUp.due_at <= followup_horizon,
                    )
                    .order_by(FollowUp.due_at.asc())
                )
                due_followups = session.execute(stmt_fu).scalars().all()

                for fu in due_followups:
                    if fu.id not in self._notified_followup_ids:
                        self._notified_followup_ids.add(fu.id)
                        followups_count += 1

                        is_overdue = fu.due_at < now
                        app = fu.application
                        job = app.job if app else None
                        company = job.company_raw if job else "Recruiter"
                        notes_hint = f": {fu.notes[:60]}" if fu.notes else ""

                        if is_overdue:
                            title = "Overdue Follow-up Reminder"
                            level = "warning"
                        else:
                            title = "Follow-up Due Today"
                            level = "info"

                        self.notify(
                            title=title,
                            message=f"Follow-up pending for {company}{notes_hint}",
                            level=level,
                            category="followup",
                        )

        self.reminders_checked.emit(interviews_count, followups_count)
        return {
            "interviews_notified": interviews_count,
            "followups_notified": followups_count,
        }

    def clear_reminder_cache(self) -> None:
        """Clears the deduplication sets to allow re-alerting."""
        self._notified_interview_ids.clear()
        self._notified_followup_ids.clear()

    # --- Automation Hooks ---

    def connect_automation_manager(self, manager: Any) -> None:
        """Connects signals from an AutomationManager instance to notification alerts."""
        if not manager:
            return

        manager.intervention_required.connect(self._on_intervention_required)
        manager.run_finished.connect(self._on_run_finished)
        manager.application_submitted.connect(self._on_application_submitted)

    def _on_intervention_required(self, event: AutomationInterventionEvent) -> None:
        """Dispatches critical intervention alert."""
        if not self.notify_automation_interventions:
            return

        plat = event.platform.capitalize()
        itype = event.intervention_type.value.replace("_", " ").title()
        self.notify(
            title=f"⚠️ Action Required: {plat}",
            message=f"{itype} detected during {plat} automation: {event.message}",
            level="warning",
            category="automation",
        )

    def _on_run_finished(self, result: AutomationRunResult) -> None:
        """Dispatches automation run finished alert."""
        if not self.notify_automation_completion:
            return

        plat = result.platform.upper()
        if result.status == AutomationState.COMPLETED:
            self.notify(
                title=f"Automation Completed ({plat})",
                message=(
                    f"Session finished successfully. Applied: {result.applications_submitted}, "
                    f"Qualified: {result.jobs_qualified}, Skipped: {result.jobs_skipped}."
                ),
                level="success",
                category="automation",
            )
        elif result.status == AutomationState.FAILED:
            reason = f": {result.stop_reason}" if result.stop_reason else ""
            self.notify(
                title=f"Automation Terminated ({plat})",
                message=f"Automation run encountered an error{reason}.",
                level="error",
                category="automation",
            )

    def _on_application_submitted(self, event: ApplicationSubmittedEvent) -> None:
        """Dispatches notification on application submission."""
        if not self.notify_application_submitted:
            return

        self.notify(
            title="Application Submitted",
            message=f"Successfully applied to '{event.title}' at {event.company} ({event.platform.capitalize()}).",
            level="success",
            category="automation",
        )
