"""Lightweight In-Process Task Runner & Job Execution Pool.

Provides concurrent task scheduling, execution, and state tracking for multi-user
automation runs using Python's native standard library (concurrent.futures).
Zero external dependencies (no Redis, no Celery, no external message brokers).
"""

import time
import uuid
import logging
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List

logger = logging.getLogger(__name__)


@dataclass
class TaskExecutionRecord:
    task_id: str
    platform: str
    user_id: int
    status: str  # PENDING, RUNNING, COMPLETED, STOPPED, FAILED
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    stop_event: threading.Event = field(default_factory=threading.Event)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "platform": self.platform,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "result": self.result,
            "error": self.error,
        }


class JobRunnerPool:
    """Manages concurrent automation executions with thread-safe cancellation and state tracking."""

    _instance: Optional["JobRunnerPool"] = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls, max_workers: int = 4) -> "JobRunnerPool":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(max_workers=max_workers)
            return cls._instance

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="JobPilotWorker")
        self._tasks: Dict[str, TaskExecutionRecord] = {}
        self._futures: Dict[str, Future] = {}
        self._registry_lock = threading.Lock()

    def submit_job_run(
        self,
        platform: str,
        user_id: int = 1,
        runner_override: Optional[Callable[[Callable[[], bool]], Dict[str, Any]]] = None,
    ) -> str:
        """Schedules a platform application run in the worker pool."""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        record = TaskExecutionRecord(
            task_id=task_id,
            platform=platform.lower(),
            user_id=user_id,
            status="PENDING",
        )

        with self._registry_lock:
            self._tasks[task_id] = record

        future = self._executor.submit(
            self._execute_task,
            record=record,
            runner_override=runner_override,
        )
        with self._registry_lock:
            self._futures[task_id] = future

        logger.info("Submitted task %s for platform=%s, user_id=%s", task_id, platform, user_id)
        return task_id

    def _execute_task(
        self,
        record: TaskExecutionRecord,
        runner_override: Optional[Callable[[Callable[[], bool]], Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        record.status = "RUNNING"
        record.started_at = datetime.utcnow()

        def stop_check() -> bool:
            return record.stop_event.is_set()

        try:
            if runner_override:
                res = runner_override(stop_check)
            else:
                from platforms.router import PlatformRouter
                from modules.tracker import ApplicationTracker

                tracker = ApplicationTracker(user_id=record.user_id)
                router = PlatformRouter()
                res = router.route(
                    platform_name=record.platform,
                    stop_check=stop_check,
                )

            record.result = res
            record.status = "STOPPED" if stop_check() else "COMPLETED"
            return res
        except Exception as exc:
            logger.error("Task %s failed: %s", record.task_id, exc, exc_info=True)
            record.status = "FAILED"
            record.error = str(exc)
            return {"error": str(exc)}
        finally:
            record.finished_at = datetime.utcnow()

    def stop_task(self, task_id: str) -> bool:
        """Signals a running task to gracefully stop via its stop_event."""
        with self._registry_lock:
            record = self._tasks.get(task_id)
            if not record:
                return False
            record.stop_event.set()
            if record.status == "PENDING":
                record.status = "STOPPED"
            return True

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Returns the task state dictionary or None if not found."""
        with self._registry_lock:
            record = self._tasks.get(task_id)
            return record.to_dict() if record else None

    def list_tasks(
        self,
        user_id: Optional[int] = None,
        platform: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """Lists tasks filtered by user_id, platform, or activity status."""
        with self._registry_lock:
            records = list(self._tasks.values())

        results = []
        for r in records:
            if user_id is not None and r.user_id != user_id:
                continue
            if platform is not None and r.platform != platform.lower():
                continue
            if active_only and r.status not in ("PENDING", "RUNNING"):
                continue
            results.append(r.to_dict())

        return results

    def shutdown(self, wait: bool = False) -> None:
        """Shuts down the executor pool."""
        with self._registry_lock:
            for r in self._tasks.values():
                r.stop_event.set()
        self._executor.shutdown(wait=wait)
