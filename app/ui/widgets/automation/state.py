"""State container for Automation Control Center UI.

Provides a clean centralized data structure for real-time runner telemetry,
preventing direct signal-to-widget coupling.
"""

from dataclasses import dataclass
import time
from typing import Optional

from app.services.automation_events import (
    AutomationInterventionEvent,
    AutomationProgressEvent,
    AutomationRunResult,
    AutomationState,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
    ApplicationSubmittedEvent,
)


@dataclass
class AutomationUIState:
    """Snapshot of real-time runner state and telemetry."""

    state: str = AutomationState.IDLE.value
    platform: str = "linkedin"
    current_keyword: str = ""
    current_job_title: str = ""
    current_job_company: str = ""
    current_job_location: str = ""
    current_job_url: Optional[str] = None
    current_step_desc: str = ""

    jobs_discovered: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    applications_submitted: int = 0
    errors_count: int = 0

    active_processing_count: int = 0
    start_monotonic: Optional[float] = None
    finish_monotonic: Optional[float] = None
    last_run_result: Optional[AutomationRunResult] = None
    intervention: Optional[AutomationInterventionEvent] = None

    def is_running(self) -> bool:
        """Returns True if the engine is currently in an active, paused, or stopping state."""
        return self.state in (
            AutomationState.STARTING.value,
            AutomationState.RUNNING.value,
            AutomationState.PAUSED.value,
            AutomationState.STOP_REQUESTED.value,
            AutomationState.STOPPING.value,
        )

    def is_paused(self) -> bool:
        """Returns True if the engine is currently paused."""
        return self.state == AutomationState.PAUSED.value

    def elapsed_seconds(self) -> float:
        """Calculates elapsed runtime using monotonic time (drift-free)."""
        if self.start_monotonic is None:
            return 0.0
        end_time = self.finish_monotonic or time.monotonic()
        return max(0.0, end_time - self.start_monotonic)

    def formatted_elapsed_time(self) -> str:
        """Returns formatted MM:SS or HH:MM:SS string."""
        total_sec = int(self.elapsed_seconds())
        hrs = total_sec // 3600
        mins = (total_sec % 3600) // 60
        secs = total_sec % 60
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    def reset_for_run(self, platform: str) -> None:
        """Resets telemetry counters and starts stopwatch for a new run."""
        self.state = AutomationState.STARTING.value
        self.platform = platform
        self.current_keyword = ""
        self.current_job_title = ""
        self.current_job_company = ""
        self.current_job_location = ""
        self.current_job_url = None
        self.current_step_desc = "Initializing automation session..."
        self.jobs_discovered = 0
        self.jobs_evaluated = 0
        self.jobs_qualified = 0
        self.jobs_skipped = 0
        self.applications_submitted = 0
        self.errors_count = 0
        self.active_processing_count = 0
        self.start_monotonic = time.monotonic()
        self.finish_monotonic = None
        self.intervention = None

    def on_progress(self, progress: AutomationProgressEvent) -> None:
        """Updates counts from progress event."""
        self.jobs_discovered = progress.jobs_discovered
        self.jobs_evaluated = progress.jobs_evaluated
        self.jobs_qualified = progress.jobs_qualified
        self.jobs_skipped = progress.jobs_skipped
        self.applications_submitted = progress.applications_submitted
        self.errors_count = progress.errors_count
        if progress.current_term:
            self.current_keyword = progress.current_term
        if progress.current_job:
            self.current_step_desc = progress.current_job
            if "@" in progress.current_job:
                parts = progress.current_job.split("@", 1)
                self.current_job_title = parts[0].strip()
                self.current_job_company = parts[1].strip()
            elif "—" in progress.current_job:
                parts = progress.current_job.split("—", 1)
                self.current_job_title = parts[0].strip()
                self.current_job_company = parts[1].strip()
            elif " - " in progress.current_job:
                parts = progress.current_job.split(" - ", 1)
                self.current_job_title = parts[0].strip()
                self.current_job_company = parts[1].strip()
            else:
                self.current_job_title = progress.current_job

    def on_job_discovered(self, event: JobDiscoveredEvent) -> None:
        """Updates active job info on discovery."""
        self.current_job_title = event.title
        self.current_job_company = event.company
        self.current_job_location = event.location or ""
        self.current_job_url = event.url
        self.active_processing_count = 1
        self.current_step_desc = f"Evaluating job: {event.title} at {event.company}"

    def on_job_evaluated(self, event: JobEvaluatedEvent) -> None:
        """Updates active job state on evaluation."""
        self.current_job_title = event.title
        self.current_job_company = event.company
        if event.is_qualified:
            self.current_step_desc = f"Qualified: {event.title}. Preparing application..."
        else:
            reason = f" ({event.reason})" if event.reason else ""
            self.current_step_desc = f"Skipped: {event.title}{reason}"
            self.active_processing_count = 0

    def on_application_submitted(self, event: ApplicationSubmittedEvent) -> None:
        """Updates active job state on submission."""
        self.current_job_title = event.title
        self.current_job_company = event.company
        if event.source_url:
            self.current_job_url = event.source_url
        self.current_step_desc = f"Submitted application: {event.title} at {event.company}"
        self.active_processing_count = 0

    def on_intervention(self, event: AutomationInterventionEvent) -> None:
        """Stores active intervention event."""
        self.intervention = event

    def on_finished(self, result: AutomationRunResult) -> None:
        """Finalizes run metrics and stops stopwatch."""
        self.state = result.status.value
        self.finish_monotonic = time.monotonic()
        self.last_run_result = result
        self.active_processing_count = 0
        self.current_step_desc = f"Run {result.status.value.lower()}: {result.stop_reason or 'None'}"
