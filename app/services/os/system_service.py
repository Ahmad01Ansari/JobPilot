"""Cross-platform operating system interaction service for JobPilot."""

import logging
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SystemService:
    """Provides high-level operating system actions and environment diagnostics."""

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
