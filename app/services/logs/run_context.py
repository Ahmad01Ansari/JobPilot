"""Multi-run observability context and active run registry."""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Deque, Dict, List, Optional

from app.services.logs.automation_event import AutomationEvent, AutomationEventType


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class RunObservabilityContext:
    """Live state, metric counters, and bounded event buffer for a single automation run."""

    run_id: str
    platform: str
    status: str = "STARTING"
    started_at: datetime = field(default_factory=_now_utc)
    finished_at: Optional[datetime] = None

    current_keyword: Optional[str] = None
    current_action: Optional[str] = None
    current_job_title: Optional[str] = None
    current_company: Optional[str] = None
    current_stage: Optional[str] = None

    # Scoped metric counters
    jobs_discovered: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    applications_submitted: int = 0
    errors_count: int = 0
    interventions_count: int = 0

    # Unresolved interventions
    active_interventions: List[AutomationEvent] = field(default_factory=list)

    # Bounded ring buffer for live timeline
    events_buffer: Deque[AutomationEvent] = field(default_factory=lambda: deque(maxlen=1000))

    def add_event(self, event: AutomationEvent) -> None:
        """Appends event to bounded buffer and updates live metrics and active state."""
        self.events_buffer.append(event)

        # Update stage & active context
        if event.stage:
            self.current_stage = event.stage
        if event.action:
            self.current_action = event.action
        if event.job_title:
            self.current_job_title = event.job_title
        if event.company:
            self.current_company = event.company

        # Metric increments
        t = event.event_type
        if t == AutomationEventType.JOB_DISCOVERED:
            count = event.metadata.get("count", 1) if event.metadata else 1
            self.jobs_discovered += count
        elif t == AutomationEventType.JOB_QUALIFIED:
            self.jobs_qualified += 1
            self.jobs_evaluated += 1
        elif t == AutomationEventType.JOB_SKIPPED:
            self.jobs_skipped += 1
            self.jobs_evaluated += 1
        elif t == AutomationEventType.APPLICATION_SUBMITTED:
            self.applications_submitted += 1
        elif t in (AutomationEventType.ERROR, AutomationEventType.APPLICATION_FAILED):
            self.errors_count += 1
        elif t in (
            AutomationEventType.CAPTCHA_DETECTED,
            AutomationEventType.LOGIN_REQUIRED,
            AutomationEventType.MANUAL_INTERVENTION,
        ):
            self.interventions_count += 1
            self.status = "ACTION_REQUIRED"
            self.active_interventions.append(event)
        elif t == AutomationEventType.RUN_COMPLETED:
            self.status = "COMPLETED"
            self.finished_at = _now_utc()
        elif t == AutomationEventType.RUN_STOPPED:
            self.status = "STOPPED"
            self.finished_at = _now_utc()
        elif t == AutomationEventType.RUN_PAUSED:
            self.status = "PAUSED"
        elif t == AutomationEventType.RUN_STARTED:
            self.status = "RUNNING"

    def resolve_intervention(self, intervention_id: str) -> None:
        """Resolves an active intervention by event_id."""
        self.active_interventions = [
            e for e in self.active_interventions if e.event_id != intervention_id
        ]
        if not self.active_interventions and self.status == "ACTION_REQUIRED":
            self.status = "RUNNING"

    def duration_seconds(self) -> float:
        """Returns elapsed runtime in seconds."""
        end = self.finished_at or _now_utc()
        return max(0.0, (end - self.started_at).total_seconds())

    def duration_str(self) -> str:
        """Formatted duration string (e.g. '8m 24s')."""
        secs = int(self.duration_seconds())
        mins = secs // 60
        rem_secs = secs % 60
        if mins > 0:
            return f"{mins}m {rem_secs:02d}s"
        return f"{rem_secs}s"


class RunRegistry:
    """Thread-safe registry managing live RunObservabilityContext instances."""

    def __init__(self):
        self._contexts: Dict[str, RunObservabilityContext] = {}

    def get_or_create(self, run_id: str, platform: str = "unknown") -> RunObservabilityContext:
        """Retrieves existing context or initializes a new one."""
        if run_id not in self._contexts:
            self._contexts[run_id] = RunObservabilityContext(
                run_id=run_id,
                platform=platform,
            )
        return self._contexts[run_id]

    def get(self, run_id: str) -> Optional[RunObservabilityContext]:
        """Retrieves a context if registered."""
        return self._contexts.get(run_id)

    def get_active_runs(self) -> List[RunObservabilityContext]:
        """Returns all runs in non-terminal states."""
        return [
            ctx for ctx in self._contexts.values()
            if ctx.status in ("STARTING", "RUNNING", "PAUSED", "ACTION_REQUIRED")
        ]

    def get_all_runs(self) -> List[RunObservabilityContext]:
        """Returns all registered run contexts ordered newest first."""
        return sorted(
            self._contexts.values(),
            key=lambda c: c.started_at,
            reverse=True,
        )

    def clear(self) -> None:
        """Clears all in-memory run contexts."""
        self._contexts.clear()
