"""AutomationRun repository for recording and querying automation run history."""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.db.models.automation_run import AutomationRun
from app.repositories.base import BaseRepository


class AutomationRunRepository(BaseRepository):
    """Repository handling CRUD and metric updates for AutomationRun entities."""

    def create_run(
        self,
        run_id: str,
        platform: str,
        status: str = "STARTING",
        started_at: Optional[datetime] = None,
    ) -> AutomationRun:
        run = AutomationRun(
            run_id=run_id,
            platform=platform,
            status=status,
            started_at=started_at or datetime.now(timezone.utc),
            jobs_discovered=0,
            jobs_evaluated=0,
            jobs_qualified=0,
            jobs_skipped=0,
            applications_submitted=0,
            errors_count=0,
        )
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def get_by_run_id(self, run_id: str) -> Optional[AutomationRun]:
        stmt = select(AutomationRun).where(AutomationRun.run_id == run_id)
        return self.session.scalar(stmt)

    def update_progress(
        self,
        run_id: str,
        current_keyword: Optional[str] = None,
        discovered: int = 0,
        evaluated: int = 0,
        qualified: int = 0,
        skipped: int = 0,
        applied: int = 0,
        errors: int = 0,
    ) -> Optional[AutomationRun]:
        run = self.get_by_run_id(run_id)
        if not run:
            return None
        if current_keyword:
            run.current_keyword = current_keyword
        run.jobs_discovered = discovered
        run.jobs_evaluated = evaluated
        run.jobs_qualified = qualified
        run.jobs_skipped = skipped
        run.applications_submitted = applied
        run.errors_count = errors
        self.session.commit()
        self.session.refresh(run)
        return run

    def finalize_run(
        self,
        run_id: str,
        status: str,
        finished_at: Optional[datetime] = None,
        stop_reason: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[AutomationRun]:
        run = self.get_by_run_id(run_id)
        if not run:
            return None
        run.status = status
        run.finished_at = finished_at or datetime.now(timezone.utc)
        if stop_reason:
            run.stop_reason = stop_reason
        if meta_data:
            run.meta_data = meta_data
        self.session.commit()
        self.session.refresh(run)
        return run

    def list_recent(self, limit: int = 20) -> List[AutomationRun]:
        stmt = select(AutomationRun).order_by(desc(AutomationRun.started_at)).limit(limit)
        return list(self.session.scalars(stmt).all())
