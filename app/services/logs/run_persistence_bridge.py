"""Persistence bridge synchronizing live run metrics with SQLite AutomationRunRepository."""

import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import sessionmaker

from app.db.models.automation_run import AutomationRun
from app.db.session import SessionLocal, get_db_session
from app.repositories.automation_run_repository import AutomationRunRepository
from app.services.logs.automation_event import AutomationEvent, AutomationEventType
from app.services.logs.run_context import RunObservabilityContext, RunRegistry

logger = logging.getLogger(__name__)


class RunPersistenceBridge:
    """Synchronizes in-memory run contexts and terminal events to SQLite database."""

    def __init__(
        self,
        registry: Optional[RunRegistry] = None,
        session_factory: Optional[sessionmaker] = None,
    ):
        self.registry = registry or RunRegistry()
        self.session_factory = session_factory or SessionLocal

    def handle_event(self, event: AutomationEvent) -> None:
        """Updates in-memory run context and persists progress or finalization to DB."""
        ctx = self.registry.get_or_create(event.run_id, platform=event.platform)
        ctx.add_event(event)

        # Handle DB sync for lifecycle and progress events
        t = event.event_type
        if t in (
            AutomationEventType.JOB_DISCOVERED,
            AutomationEventType.JOB_QUALIFIED,
            AutomationEventType.JOB_SKIPPED,
            AutomationEventType.APPLICATION_SUBMITTED,
            AutomationEventType.APPLICATION_FAILED,
        ):
            self._sync_progress(ctx)
        elif t in (AutomationEventType.RUN_COMPLETED, AutomationEventType.RUN_STOPPED):
            self._finalize_run(ctx, stop_reason=event.action or "Completed")

    def _sync_progress(self, ctx: RunObservabilityContext) -> None:
        """Updates run progress in database."""
        try:
            with get_db_session(self.session_factory) as session:
                repo = AutomationRunRepository(session)
                run = repo.get_by_run_id(ctx.run_id)
                if not run:
                    repo.create_run(
                        run_id=ctx.run_id,
                        platform=ctx.platform,
                        status=ctx.status,
                        started_at=ctx.started_at,
                    )
                repo.update_progress(
                    run_id=ctx.run_id,
                    current_keyword=ctx.current_keyword,
                    discovered=ctx.jobs_discovered,
                    evaluated=ctx.jobs_evaluated,
                    qualified=ctx.jobs_qualified,
                    skipped=ctx.jobs_skipped,
                    applied=ctx.applications_submitted,
                    errors=ctx.errors_count,
                )
        except Exception as exc:
            logger.debug("Notice updating run progress in DB: %s", exc)

    def _finalize_run(self, ctx: RunObservabilityContext, stop_reason: str) -> None:
        """Marks run as finalized in database."""
        try:
            with get_db_session(self.session_factory) as session:
                repo = AutomationRunRepository(session)
                repo.finalize_run(
                    run_id=ctx.run_id,
                    status=ctx.status,
                    finished_at=ctx.finished_at,
                    stop_reason=stop_reason,
                    meta_data={
                        "interventions_count": ctx.interventions_count,
                        "duration_seconds": ctx.duration_seconds(),
                    },
                )
        except Exception as exc:
            logger.debug("Notice finalizing run in DB: %s", exc)

    def list_historical_runs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Returns historical runs for the Run History tab."""
        try:
            with get_db_session(self.session_factory) as session:
                repo = AutomationRunRepository(session)
                runs = repo.list_recent(limit=limit)
                out = []
                for r in runs:
                    out.append({
                        "run_id": r.run_id,
                        "platform": r.platform,
                        "status": r.status,
                        "started_at": r.started_at,
                        "finished_at": r.finished_at,
                        "current_keyword": r.current_keyword,
                        "jobs_discovered": r.jobs_discovered,
                        "jobs_qualified": r.jobs_qualified,
                        "jobs_skipped": r.jobs_skipped,
                        "applications_submitted": r.applications_submitted,
                        "errors_count": r.errors_count,
                        "stop_reason": r.stop_reason,
                        "meta_data": r.meta_data or {},
                    })
                return out
        except Exception as exc:
            logger.error("Error querying historical runs: %s", exc)
            return []
