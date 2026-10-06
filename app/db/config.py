"""Database configuration and path resolution for JobPilot."""

import os
from pathlib import Path
from typing import Optional


class DatabaseConfig:
    """Manages database connection paths and parameters."""

    DEFAULT_DIR = Path.home() / ".jobpilot"
    DEFAULT_FILENAME = "jobpilot.db"

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = Path(db_path)
        else:
            env_path = os.environ.get("JOBPILOT_DB_PATH")
            if env_path:
                self._db_path = Path(env_path)
            else:
                self._db_path = self.DEFAULT_DIR / self.DEFAULT_FILENAME

    @property
    def db_path(self) -> Path:
        return self._db_path

    def ensure_directory(self) -> None:
        """Ensures the parent directory for the database file exists."""
        if str(self._db_path) not in (":memory:", "sqlite:///:memory:"):
            self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def get_url(self) -> str:
        """Returns the SQLAlchemy SQLite database URL."""
        if str(self._db_path) in (":memory:", "sqlite:///:memory:"):
            return "sqlite:///:memory:"
        self.ensure_directory()
        return f"sqlite:///{self._db_path.resolve()}"


_default_config = DatabaseConfig()


def get_db_path() -> Path:
    return _default_config.db_path


def get_db_url() -> str:
    return _default_config.get_url()
