"""Centralized crash telemetry and global uncaught exception handling."""

import json
import logging
import sys
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.services.os.app_paths import AppPaths
from app.services.os.system_service import SystemService
from app.services.sanitizer_service import LogSanitizer

logger = logging.getLogger(__name__)

_CRASH_HANDLER_INSTALLED = False


def _write_sanitized_crash_dump(exc_type: Any, exc_value: Any, exc_traceback: Any, thread_name: Optional[str] = None) -> Optional[Path]:
    """Formats and writes a sanitized crash report to the crash_dumps directory."""
    try:
        raw_traceback = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        sanitized_tb = LogSanitizer.sanitize_text(raw_traceback)
        sanitized_err = LogSanitizer.sanitize_text(str(exc_value))

        dumps_dir = AppPaths.get_crash_dumps_dir(project_root=Path.cwd())
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        dump_file = dumps_dir / f"crash_{timestamp}.json"

        report: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "thread_name": thread_name or threading.current_thread().name,
            "exception_type": getattr(exc_type, "__name__", str(exc_type)),
            "exception_message": sanitized_err,
            "traceback": sanitized_tb,
            "system_info": SystemService.get_system_diagnostics(),
        }

        with open(dump_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.critical(
            "UNCAUGHT_FATAL_EXCEPTION captured in thread '%s': %s (Crash dump saved to %s)",
            report["thread_name"],
            sanitized_err,
            dump_file,
        )
        return dump_file
    except Exception as hook_err:
        logger.critical("Failed to write sanitized crash dump: %s", hook_err)
        return None


def install_global_crash_handler() -> None:
    """Installs sys.excepthook and threading.excepthook handlers for sanitized crash telemetry."""
    global _CRASH_HANDLER_INSTALLED
    if _CRASH_HANDLER_INSTALLED:
        return

    original_sys_excepthook = sys.excepthook

    def _sys_crash_hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            original_sys_excepthook(exc_type, exc_value, exc_traceback)
            return

        _write_sanitized_crash_dump(exc_type, exc_value, exc_traceback, thread_name="MainThread")
        original_sys_excepthook(exc_type, exc_value, exc_traceback)

    sys.excepthook = _sys_crash_hook

    if hasattr(threading, "excepthook"):
        original_threading_excepthook = threading.excepthook

        def _threading_crash_hook(args):
            _write_sanitized_crash_dump(
                args.exc_type,
                args.exc_value,
                args.exc_traceback,
                thread_name=getattr(args.thread, "name", "UnknownThread"),
            )
            original_threading_excepthook(args)

        threading.excepthook = _threading_crash_hook

    _CRASH_HANDLER_INSTALLED = True
    logger.debug("Global crash reporting handlers installed.")
