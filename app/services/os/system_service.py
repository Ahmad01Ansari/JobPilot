"""Cross-platform operating system interaction service for JobPilot."""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SystemWakelock:
    """Manages cross-platform system display and sleep inhibitor lock."""
    _active_lock_proc: Optional[subprocess.Popen] = None
    _windows_lock_active: bool = False

    @classmethod
    def acquire(cls, reason: str = "JobPilot automation running") -> bool:
        """Prevents system sleep and display blanking while automation runs."""
        if sys.platform == "win32":
            try:
                import ctypes
                ES_CONTINUOUS = 0x80000000
                ES_SYSTEM_REQUIRED = 0x00000001
                ES_DISPLAY_REQUIRED = 0x00000002
                ctypes.windll.kernel32.SetThreadExecutionState(
                    ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
                )
                cls._windows_lock_active = True
                logger.info("[SystemWakelock] Windows system display/sleep wakelock acquired.")
                return True
            except Exception as e:
                logger.warning("[SystemWakelock] Failed to acquire Windows sleep lock: %s", e)
                return False
        elif sys.platform.startswith("linux"):
            try:
                import shutil
                if shutil.which("systemd-inhibit"):
                    cls._active_lock_proc = subprocess.Popen(
                        [
                            "systemd-inhibit",
                            "--what=idle:sleep",
                            "--who=JobPilot",
                            f"--why={reason}",
                            "sleep",
                            "86400",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logger.info("[SystemWakelock] Linux systemd-inhibit wakelock acquired.")
                    return True
            except Exception as e:
                logger.warning("[SystemWakelock] Linux sleep inhibitor fallback: %s", e)
            return False
        elif sys.platform == "darwin":
            try:
                import shutil
                if shutil.which("caffeinate"):
                    cls._active_lock_proc = subprocess.Popen(
                        ["caffeinate", "-d", "-i", "-m", "-u"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    logger.info("[SystemWakelock] macOS caffeinate wakelock acquired.")
                    return True
            except Exception as e:
                logger.warning("[SystemWakelock] macOS caffeinate fallback: %s", e)
            return False
        return False

    @classmethod
    def release(cls) -> None:
        """Releases acquired system sleep lock."""
        if sys.platform == "win32" and cls._windows_lock_active:
            try:
                import ctypes
                ES_CONTINUOUS = 0x80000000
                ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                cls._windows_lock_active = False
                logger.info("[SystemWakelock] Windows system display/sleep wakelock released.")
            except Exception as e:
                logger.warning("[SystemWakelock] Failed to release Windows sleep lock: %s", e)
        if cls._active_lock_proc:
            try:
                cls._active_lock_proc.terminate()
                cls._active_lock_proc.wait(timeout=2)
            except Exception:
                try:
                    cls._active_lock_proc.kill()
                except Exception:
                    pass
            finally:
                cls._active_lock_proc = None
                logger.info("[SystemWakelock] Subprocess sleep inhibitor released.")


class SystemService:
    """Provides high-level operating system actions and environment diagnostics."""

    @classmethod
    def acquire_wakelock(cls, reason: str = "JobPilot automation running") -> bool:
        """Acquires a cross-platform system display and sleep inhibitor lock."""
        return SystemWakelock.acquire(reason)

    @classmethod
    def release_wakelock(cls) -> None:
        """Releases any active system sleep inhibitor lock."""
        SystemWakelock.release()

    @classmethod
    def open_file_or_dir(cls, target_path: Path | str) -> Tuple[bool, Optional[str]]:
        """Opens a file or directory using the OS default application or file manager.

        Uses PySide6 QDesktopServices first for seamless GUI integration, falling back
        to native OS subprocesses (os.startfile on Windows, open on macOS, xdg-open on Linux).

        Args:
            target_path: Path to the file or directory to open.

        Returns:
            (success, error_message)
        """
        p = Path(target_path).resolve()
        if not p.exists():
            return False, f"Path does not exist: {p}"

        # 1. Try PySide6 QDesktopServices
        try:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            url = QUrl.fromLocalFile(str(p))
            if QDesktopServices.openUrl(url):
                return True, None
        except Exception as exc:
            logger.debug("QDesktopServices.openUrl fallback triggered: %s", exc)

        # 2. Native OS fallback
        try:
            if sys.platform == "win32":
                # Windows native file opener
                os.startfile(str(p))  # type: ignore[attr-defined]
                return True, None
            elif sys.platform == "darwin":
                # macOS native open command
                subprocess.Popen(["open", str(p)])
                return True, None
            elif sys.platform.startswith("linux"):
                # Linux freedesktop xdg-open
                subprocess.Popen(["xdg-open", str(p)])
                return True, None
            else:
                return False, f"Unsupported operating system: {sys.platform}"
        except Exception as exc:
            err_msg = f"Failed to launch system viewer: {exc}"
            logger.warning(err_msg)
            return False, err_msg

    @classmethod
    def get_system_diagnostics(cls) -> Dict[str, Any]:
        """Gathers system environment telemetry for diagnostics and crash reporting."""
        return {
            "os_name": os.name,
            "platform": sys.platform,
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "python_version": sys.version.split()[0],
            "is_64bit": sys.maxsize > 2**32,
        }
