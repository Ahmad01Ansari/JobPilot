"""Background coordinator managing cadence evaluations and due follow-up notifications."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal

from app.db.session import SessionLocal
from app.services.followup_scheduler import FollowUpScheduler
from app.services.inbound_sync_service import InboundSyncService
from app.ui.state import AppState

logger = logging.getLogger(__name__)


class OutreachCadenceCoordinator(QObject):
    """Background lifecycle manager that regularly evaluates follow-up cadences and triggers user review."""

    due_followups_detected = Signal(list)    # List[Dict[str, Any]]
    followup_dispatched = Signal(dict)       # Result Dict
    mailbox_synced = Signal(dict)            # Inbound sync result

    _instance: Optional["OutreachCadenceCoordinator"] = None

    @classmethod
    def get_instance(cls) -> "OutreachCadenceCoordinator":
        if cls._instance is None:
            cls._instance = OutreachCadenceCoordinator()
        return cls._instance

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        OutreachCadenceCoordinator._instance = self
        self._scheduler = FollowUpScheduler(session_factory=SessionLocal)
        self._inbound_sync = InboundSyncService(session_factory=SessionLocal)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.run_cadence_cycle)
        self._is_running = False

    def start(self, interval_ms: int = 900000):  # Default 15 minutes
        """Starts periodic background cadence evaluation."""
        if not self._is_running:
            self._is_running = True
            self._timer.start(interval_ms)
            # Run initial check shortly after startup (3 seconds)
            QTimer.singleShot(3000, self.run_cadence_cycle)
            logger.info("OutreachCadenceCoordinator started (cadence interval: %d ms)", interval_ms)

    def stop(self):
        """Stops the periodic evaluation timer."""
        if self._is_running:
            self._timer.stop()
            self._is_running = False
            logger.info("OutreachCadenceCoordinator stopped.")

    def run_cadence_cycle(self):
        """Executes a single check: synchronizes inbound mail and evaluates due cadences."""
        try:
            # 1. Background inbound mail sync to auto-pause cadences if recruiter replied
            sync_res = self._inbound_sync.sync_mailbox()
            if sync_res.get("new_messages", 0) > 0:
                self.mailbox_synced.emit(sync_res)
                try:
                    AppState.get_instance().notify_data_updated("outreach")
                except Exception:
                    pass

            # 2. Evaluate due follow-ups
            due_list = self._scheduler.get_due_followups_for_user()
            if due_list:
                self.due_followups_detected.emit(due_list)
                try:
                    app_state = AppState.get_instance()
                    app_state.set("due_followups", due_list)
                    app_state.notify_data_updated("outreach")
                    app_state.notify_data_updated("dashboard")
                except Exception:
                    pass
                logger.info("OutreachCadenceCoordinator: %d due follow-ups require user review.", len(due_list))
        except Exception as e:
            logger.error("OutreachCadenceCoordinator error during cadence cycle: %s", e)

    def execute_approved_followup(
        self,
        followup_id: int,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches an approved follow-up email after user confirmation."""
        res = self._scheduler.execute_followup(
            followup_id=followup_id,
            custom_subject=custom_subject,
            custom_body=custom_body,
        )
        self.followup_dispatched.emit(res)
        try:
            AppState.get_instance().notify_data_updated("outreach")
            AppState.get_instance().notify_data_updated("dashboard")
        except Exception:
            pass
        return res

    def snooze_followup(self, followup_id: int, days: int = 3) -> bool:
        """Snoozes follow-up cadence by X days."""
        res = self._scheduler.snooze_followup(followup_id, days=days)
        try:
            AppState.get_instance().notify_data_updated("outreach")
        except Exception:
            pass
        return res

    def cancel_followup(self, followup_id: int, reason: str = "Cancelled by user") -> bool:
        """Cancels a scheduled cadence."""
        res = self._scheduler.cancel_followup(followup_id, reason=reason)
        try:
            AppState.get_instance().notify_data_updated("outreach")
        except Exception:
            pass
        return res

