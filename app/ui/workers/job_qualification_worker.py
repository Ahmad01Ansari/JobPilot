"""Background QThread worker for asynchronous job qualification execution."""

import logging
from typing import Dict, List, Optional
from PySide6.QtCore import QThread, Signal

from app.services.dto.qualification_dto import QualificationResultDTO
from app.services.job_qualification_service import JobQualificationService

logger = logging.getLogger("JobPilot.JobQualificationWorker")


class JobQualificationWorker(QThread):
    """Executes deterministic and optional AI qualification in background thread."""

    job_qualified = Signal(object)      # QualificationResultDTO
    job_failed = Signal(int, str)       # job_id, error_message
    progress = Signal(int, int)         # current, total
    bulk_finished = Signal(dict)        # summary statistics dict

    def __init__(
        self,
        service: Optional[JobQualificationService] = None,
        job_id: Optional[int] = None,
        job_ids: Optional[List[int]] = None,
        user_id: Optional[int] = None,
        force_reevaluate: bool = True,
        use_ai: bool = False,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.service = service or JobQualificationService()
        self.job_id = job_id
        self.job_ids = list(job_ids) if job_ids else ([job_id] if job_id is not None else [])
        self.user_id = user_id
        self.force_reevaluate = force_reevaluate
        self.use_ai = use_ai
        self._is_cancelled = False

    def cancel(self) -> None:
        """Requests cooperative cancellation of bulk evaluation."""
        self._is_cancelled = True

    def run(self) -> None:
        total = len(self.job_ids)
        if total == 0:
            self.bulk_finished.emit({"processed": 0, "qualified": 0, "errors": 0})
            return

        processed = 0
        qualified = 0
        errors = 0

        for idx, jid in enumerate(self.job_ids, 1):
            if self._is_cancelled:
                logger.info("Qualification worker cancelled by user after %d jobs", processed)
                break

            try:
                result = self.service.qualify_job(
                    job_id=jid,
                    user_id=self.user_id,
                    force_reevaluate=self.force_reevaluate,
                    use_ai=self.use_ai,
                )
                processed += 1
                if result.decision.value in ("STRONG_MATCH", "GOOD_MATCH", "POSSIBLE_MATCH"):
                    qualified += 1
                self.job_qualified.emit(result)
            except Exception as exc:
                errors += 1
                logger.exception("Failed to qualify job_id %s in background worker", jid)
                self.job_failed.emit(jid, str(exc))

            self.progress.emit(idx, total)

        self.bulk_finished.emit({
            "total": total,
            "processed": processed,
            "qualified": qualified,
            "errors": errors,
            "cancelled": self._is_cancelled,
        })
