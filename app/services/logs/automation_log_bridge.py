"""AutomationLogBridge connecting typed worker signals and log feeds into normalized AutomationEvents."""

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationState,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.logs.automation_event import (
    AutomationEvent,
    AutomationEventType,
    EventSource,
)
from app.services.logs.event_correlator import EventCorrelator
from app.services.logs.log_normalizer import LogNormalizer

logger = logging.getLogger(__name__)


class AutomationLogBridge(QObject):
    """Bridge converting raw and typed execution events into normalized, deduplicated AutomationEvents.
    
    Provides thread-safe signal delivery to Mission Control UI components.
    """

    event_emitted = Signal(object)  # AutomationEvent

    def __init__(
        self,
        correlator: Optional[EventCorrelator] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.correlator = correlator or EventCorrelator()

    def _dispatch(self, event: AutomationEvent) -> None:
        """Runs event through deduplicator; emits if accepted."""
        correlated = self.correlator.correlate(event)
        if correlated is not None:
            self.event_emitted.emit(correlated)

    # -------------------------------------------------------------------------
    # Typed Signal Handlers (PRIMARY SOURCE)
    # -------------------------------------------------------------------------

    def on_job_discovered(self, event: JobDiscoveredEvent) -> None:
        """Translates JobDiscoveredEvent from engine into an AutomationEvent."""
        norm_event = AutomationEvent(
            run_id=getattr(event, "run_id", "default"),
            source=EventSource.SIGNAL,
            level="INFO",
            event_type=AutomationEventType.JOB_DISCOVERED,
            platform=getattr(event, "platform", "unknown"),
            stage="DISCOVER",
            job_title=getattr(event, "title", None),
            company=getattr(event, "company", None),
            action=f"Discovered: {getattr(event, 'title', 'Job')}",
            status="SUCCESS",
            message=f"Discovered '{getattr(event, 'title', 'Unknown')}' at '{getattr(event, 'company', 'Unknown')}'",
            metadata={
                "external_job_id": getattr(event, "external_job_id", None),
                "url": getattr(event, "url", None),
                "location": getattr(event, "location", None),
                "application_method": getattr(event, "application_method", "EASY_APPLY"),
            },
        )
        self._dispatch(norm_event)

    def on_job_evaluated(self, event: JobEvaluatedEvent) -> None:
        """Translates JobEvaluatedEvent into JOB_QUALIFIED or JOB_SKIPPED."""
        is_qual = getattr(event, "is_qualified", False)
        e_type = AutomationEventType.JOB_QUALIFIED if is_qual else AutomationEventType.JOB_SKIPPED
        status = "SUCCESS" if is_qual else "SKIPPED"
        reason = getattr(event, "reason", "Criteria evaluation")

        norm_event = AutomationEvent(
            run_id=getattr(event, "run_id", "default"),
            source=EventSource.SIGNAL,
            level="INFO" if is_qual else "WARNING",
            event_type=e_type,
            platform=getattr(event, "platform", "unknown"),
            stage="QUALIFY",
            job_title=getattr(event, "title", None),
            company=getattr(event, "company", None),
            action="Qualified" if is_qual else "Skipped",
            status=status,
            message=f"{'Qualified' if is_qual else 'Skipped'} '{getattr(event, 'title', 'Job')}': {reason}",
            metadata={"reason": reason, "is_qualified": is_qual},
        )
        self._dispatch(norm_event)

    def on_application_submitted(self, event: ApplicationSubmittedEvent) -> None:
        """Translates ApplicationSubmittedEvent into an APPLICATION_SUBMITTED event."""
        norm_event = AutomationEvent(
            run_id=getattr(event, "run_id", "default"),
            source=EventSource.SIGNAL,
            level="INFO",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform=getattr(event, "platform", "unknown"),
            stage="SUBMISSION",
            job_id=getattr(event, "job_id", None),
            job_title=getattr(event, "title", None),
            company=getattr(event, "company", None),
            action="Application Submitted",
            status="SUCCESS",
            message=f"Successfully applied to '{getattr(event, 'title', 'Job')}' at '{getattr(event, 'company', 'Unknown')}'",
            metadata={"source_url": getattr(event, "source_url", None)},
        )
        self._dispatch(norm_event)

    def on_intervention_required(self, event: AutomationInterventionEvent) -> None:
        """Translates AutomationInterventionEvent into structured intervention event."""
        int_type = getattr(event, "intervention_type", InterventionType.MANUAL_ACTION_REQUIRED)
        e_type = AutomationEventType.MANUAL_INTERVENTION

        if int_type == InterventionType.CAPTCHA_DETECTED:
            e_type = AutomationEventType.CAPTCHA_DETECTED
        elif int_type == InterventionType.LOGIN_REQUIRED:
            e_type = AutomationEventType.LOGIN_REQUIRED
        elif int_type == InterventionType.RATE_LIMITED:
            e_type = AutomationEventType.RATE_LIMITED

        norm_event = AutomationEvent(
            run_id=getattr(event, "run_id", "default"),
            source=EventSource.SIGNAL,
            level="WARNING",
            event_type=e_type,
            platform=getattr(event, "platform", "unknown"),
            stage="REVIEW",
            action=str(int_type.value if hasattr(int_type, "value") else int_type),
            status="INTERVENTION",
            message=getattr(event, "message", "Manual intervention required"),
            metadata=getattr(event, "details", {}) or {},
        )
        self._dispatch(norm_event)

    def on_state_changed(self, run_id: str, new_state: str) -> None:
        """Translates worker state changes into lifecycle events."""
        st = str(new_state).upper()
        e_type = AutomationEventType.RUN_STARTED

        if "RUNNING" in st or "STARTING" in st:
            e_type = AutomationEventType.RUN_STARTED
        elif "PAUSED" in st:
            e_type = AutomationEventType.RUN_PAUSED
        elif "STOP" in st:
            e_type = AutomationEventType.RUN_STOPPED
        elif "COMPLETED" in st:
            e_type = AutomationEventType.RUN_COMPLETED

        norm_event = AutomationEvent(
            run_id=run_id,
            source=EventSource.SIGNAL,
            level="INFO",
            event_type=e_type,
            action=f"State changed to {st}",
            status=st,
            message=f"Automation run entered {st} state.",
        )
        self._dispatch(norm_event)

    # -------------------------------------------------------------------------
    # Fallback Log Line Processing
    # -------------------------------------------------------------------------

    def on_log_line(
        self,
        line: str,
        run_id: str = "default",
        line_number: int = 0,
        byte_offset: int = 0,
    ) -> None:
        """Processes a raw log line through LogNormalizer and correlator."""
        event = LogNormalizer.parse_line(
            line=line,
            run_id=run_id,
            line_number=line_number,
            byte_offset=byte_offset,
        )
        self._dispatch(event)
