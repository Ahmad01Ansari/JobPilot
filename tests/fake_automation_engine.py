"""Fake automation engine for deterministic testing of worker, bridge, and UI."""

import time
from typing import List, Optional
from datetime import datetime, timezone

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    AutomationProgressEvent,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)


class FakeAutomationEngine:
    """Simulates multi-platform automation runs without launching Chrome or Selenium."""

    def __init__(
        self,
        jobs_to_discover: int = 3,
        jobs_to_apply: int = 2,
        simulate_intervention: Optional[InterventionType] = None,
        simulate_error: Optional[str] = None,
        delay_seconds: float = 0.0,
    ):
        self.jobs_to_discover = jobs_to_discover
        self.jobs_to_apply = jobs_to_apply
        self.simulate_intervention = simulate_intervention
        self.simulate_error = simulate_error
        self.delay_seconds = delay_seconds

    def run(self, worker: "AutomationWorker") -> None:
        """Executes the simulated automation loop with cooperative stop checking."""
        run_id = worker.run_id
        platform = worker.platform

        worker.progress.current_term = "Python Developer"
        worker.progress_updated.emit(worker.progress)

        if self.simulate_intervention:
            worker.record_intervention(
                AutomationInterventionEvent(
                    run_id=run_id,
                    platform=platform,
                    intervention_type=self.simulate_intervention,
                    message=f"Simulated intervention: {self.simulate_intervention.value}",
                )
            )

        for i in range(1, self.jobs_to_discover + 1):
            if worker.is_stop_requested():
                worker.emit_activity("Fake engine halted due to stop request.")
                return

            if self.delay_seconds > 0:
                time.sleep(self.delay_seconds)

            ext_id = f"fake-{platform}-{run_id[:6]}-{i}"
            title = f"Senior Software Engineer #{i}"
            company = f"TechCorp {i}"

            # 1. Discover job
            worker.progress.current_job = f"{title} @ {company}"
            disc_event = JobDiscoveredEvent(
                run_id=run_id,
                platform=platform,
                title=title,
                company=company,
                external_job_id=ext_id,
                location="Remote",
                url=f"https://{platform}.example.com/jobs/{ext_id}",
            )
            job_id = worker.record_job_discovered(disc_event)

            # 2. Evaluate job
            is_qualified = i <= self.jobs_to_apply
            eval_event = JobEvaluatedEvent(
                run_id=run_id,
                platform=platform,
                title=title,
                company=company,
                is_qualified=is_qualified,
                external_job_id=ext_id,
                reason="Match criteria satisfied" if is_qualified else "Experience mismatch",
            )
            worker.record_job_evaluated(eval_event)

            # 3. Apply if qualified
            if is_qualified:
                if worker.is_stop_requested():
                    return
                app_event = ApplicationSubmittedEvent(
                    run_id=run_id,
                    platform=platform,
                    job_id=job_id,
                    external_job_id=ext_id,
                    title=title,
                    company=company,
                    source_url=f"https://{platform}.example.com/jobs/{ext_id}",
                )
                worker.record_application_submitted(app_event)

        if self.simulate_error:
            raise RuntimeError(self.simulate_error)
