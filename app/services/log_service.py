"""Service for reading, filtering, and managing execution log files."""

import os
from pathlib import Path
from typing import List, Optional

from app.services.sanitizer_service import LogSanitizer, SanitizingLogFilter


class LogService:
    """Provides safe reading, tailing, filtering, and truncation of application logs."""

    def __init__(self, log_path: Optional[str] = None):
        if log_path:
            self.log_path = Path(log_path)
        else:
            base_dir = Path(__file__).resolve().parent.parent.parent
            self.log_path = base_dir / "logs" / "log.txt"

    def ensure_log_file(self) -> bool:
        """Ensures the log directory and file exist."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_path.exists():
                self.log_path.touch()
            return True
        except Exception:
            return False

    def tail(self, n_lines: int = 500) -> List[str]:
        """Reads the last n_lines from the log file, sanitizing sensitive content."""
        self.ensure_log_file()
        if not self.log_path.exists():
            return []

        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                return [LogSanitizer.sanitize_text(line.rstrip("\r\n")) for line in lines[-n_lines:]]
        except Exception:
            return []


    def filter_logs(
        self,
        lines: List[str],
        level: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[str]:
        """Filters log lines by severity level and/or substring query."""
        filtered = lines

        if level and level.upper() not in ("ALL", ""):
            lvl = level.upper()
            level_keywords = {
                "INFO": ["INFO", "LAUNCHING", "INITIALIZING", "COMPLETED", "SUCCESS"],
                "WARNING": ["WARN", "WARNING", "NOTICE"],
                "WARN": ["WARN", "WARNING", "NOTICE"],
                "ERROR": ["ERROR", "FAILED", "CRITICAL", "EXCEPTION"],
                "CRITICAL": ["CRITICAL", "FATAL"],
            }
            keywords = level_keywords.get(lvl, [lvl])
            filtered = [
                line for line in filtered
                if any(kw in line.upper() for kw in keywords)
            ]

        if search and search.strip():
            query = search.strip().lower()
            filtered = [line for line in filtered if query in line.lower()]

        return filtered

    def safe_clear(self, confirm: bool = False) -> bool:
        """Safely truncates the log file if explicit confirmation is provided."""
        if not confirm:
            return False
        try:
            self.ensure_log_file()
            with open(self.log_path, "w", encoding="utf-8") as f:
                f.truncate(0)
            return True
        except Exception:
            return False
