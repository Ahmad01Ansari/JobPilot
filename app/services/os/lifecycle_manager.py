"""Centralized application lifecycle and graceful shutdown coordinator."""

import logging
from typing import Optional

from app.db.session import dispose_engine

logger = logging.getLogger(__name__)


class ApplicationLifecycleManager:
    """Coordinates deterministic, graceful teardown of workers, browsers, pools, and DB."""

    _is_shutting_down = False

    @classmethod
    def is_shutting_down(cls) -> bool:
        """Returns True if application shutdown is currently in progress."""
        return cls._is_shutting_down

    @classmethod
    def shutdown_application(cls, timeout_ms: int = 3000) -> None:
        """Executes graceful application shutdown across all subsystem layers."""
        if cls._is_shutting_down:
            return
        cls._is_shutting_down = True
        logger.info("ApplicationLifecycleManager: Initiating graceful application shutdown...")

        # 1. Stop active automation runs (AutomationManager)
        try:
            from app.services.automation_service import AutomationManager
            mgr = AutomationManager.get_instance()
            if mgr and mgr.is_running():
                logger.info("Stopping active automation worker...")
                mgr.stop_and_wait(timeout_ms=timeout_ms)
        except Exception as exc:
            logger.debug("Notice stopping AutomationManager: %s", exc)

        # 2. Shutdown background thread pool (JobRunnerPool)
        try:
            from app.services.task_runner import JobRunnerPool
            pool = JobRunnerPool.get_instance()
            logger.info("Shutting down JobRunnerPool...")
            pool.shutdown(wait=False)
        except Exception as exc:
            logger.debug("Notice shutting down JobRunnerPool: %s", exc)

        # 3. Clean up lingering Chrome locks or orphaned browser instances
        try:
            from modules.browser_lock import kill_profile_processes, get_profile_dir
            for plat in ["linkedin", "naukri", "indeed", "glassdoor", "foundit"]:
                try:
                    pdir = get_profile_dir(plat)
                    kill_profile_processes(pdir)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Notice cleaning browser profile processes: %s", exc)

        # 4. Dispose database engine pool
        try:
            logger.info("Disposing database connection pool...")
            dispose_engine()
        except Exception as exc:
            logger.debug("Notice disposing database engine: %s", exc)

        logger.info("ApplicationLifecycleManager: Graceful shutdown completed.")
