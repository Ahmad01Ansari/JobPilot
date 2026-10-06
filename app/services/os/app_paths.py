"""Cross-platform directory and filesystem path resolution for JobPilot."""

import os
import sys
from pathlib import Path
from typing import Optional


class AppPaths:
    """Provides canonical directory paths and permissions across Windows, Linux, and macOS."""

    _APP_NAME = "JobPilot"

    @classmethod
    def is_windows(cls) -> bool:
        """Returns True if the runtime operating system is Windows."""
        return sys.platform == "win32" or os.name == "nt"

    @classmethod
    def is_linux(cls) -> bool:
        """Returns True if the runtime operating system is Linux."""
        return sys.platform.startswith("linux")

    @classmethod
    def is_macos(cls) -> bool:
        """Returns True if the runtime operating system is macOS."""
        return sys.platform == "darwin"

    @classmethod
    def get_user_data_dir(cls) -> Path:
        """Resolves the canonical user data directory for application storage.

        Checks for legacy ~/.jobpilot first to maintain full backwards compatibility.
        Otherwise falls back to standard OS-specific user data conventions:
        - Windows: %APPDATA%/JobPilot
        - macOS: ~/Library/Application Support/JobPilot
        - Linux: ~/.config/jobpilot (or $XDG_CONFIG_HOME/jobpilot)
        """
        home = Path.home()
        legacy_dir = home / ".jobpilot"
        if legacy_dir.exists() and legacy_dir.is_dir():
            return legacy_dir

        if cls.is_windows():
            appdata = os.environ.get("APPDATA")
            if appdata:
                return Path(appdata) / cls._APP_NAME
            return home / ".jobpilot"

        if cls.is_macos():
            return home / "Library" / "Application Support" / cls._APP_NAME

        # Linux / Unix XDG base directory specification
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config) / "jobpilot"

        return home / ".jobpilot"

    @classmethod
    def get_logs_dir(cls, project_root: Optional[Path] = None) -> Path:
        """Returns directory path where runtime logs are stored."""
        if project_root and (project_root / "logs").exists():
            return project_root / "logs"
        return cls.get_user_data_dir() / "logs"

    @classmethod
    def get_crash_dumps_dir(cls, project_root: Optional[Path] = None) -> Path:
        """Returns directory where sanitized crash reports are written."""
        dumps_dir = cls.get_logs_dir(project_root) / "crash_dumps"
        dumps_dir.mkdir(parents=True, exist_ok=True)
        return dumps_dir

    @classmethod
    def get_profiles_dir(cls) -> Path:
        """Returns directory where isolated browser profiles are stored."""
        profiles_dir = cls.get_user_data_dir() / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        return profiles_dir

    @classmethod
    def get_resumes_dir(cls, project_root: Optional[Path] = None) -> Path:
        """Returns directory where managed candidate resumes are stored."""
        if project_root and (project_root / "managed_resumes").exists():
            cand = project_root / "managed_resumes"
            if os.access(cand, os.W_OK):
                return cand
        resumes_dir = cls.get_user_data_dir() / "managed_resumes"
        resumes_dir.mkdir(parents=True, exist_ok=True)
        return resumes_dir

    @classmethod
    def get_snapshots_dir(cls, project_root: Optional[Path] = None) -> Path:
        """Returns directory where application audit snapshots are written."""
        if project_root and (project_root / "snapshots").exists():
            cand = project_root / "snapshots"
            if os.access(cand, os.W_OK):
                return cand
        snaps_dir = cls.get_user_data_dir() / "snapshots"
        snaps_dir.mkdir(parents=True, exist_ok=True)
        return snaps_dir

    @classmethod
    def safe_set_permissions(cls, path: Path, mode: int = 0o600) -> bool:
        """Sets restrictive file permissions on POSIX systems while failing safely on Windows.

        Args:
            path: Target file or directory path.
            mode: Desired permission bits (e.g. 0o600 for secrets, 0o700 for directories).

        Returns:
            True if permissions were set or safely skipped on Windows; False on unexpected error.
        """
        try:
            if cls.is_windows():
                # Windows uses NTFS Access Control Lists (ACLs); os.chmod only toggles read-only flag.
                return True
            os.chmod(path, mode)
            return True
        except Exception:
            return False
