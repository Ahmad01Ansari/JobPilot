"""Background worker for creating system backups asynchronously."""

from typing import Any, Dict, Optional
from PySide6.QtCore import QThread, Signal
from app.services.backup_service import BackupService


class BackupWorker(QThread):
    """Packages DB, profiles, and resumes into a zip archive off the Qt main thread."""

    finished = Signal(bool, str, dict)  # (success: bool, archive_path_or_err: str, manifest: dict)

    def __init__(
        self,
        backup_service: BackupService,
        target_dir: Optional[str] = None,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.backup_service = backup_service
        self.target_dir = target_dir

    def run(self) -> None:
        try:
            ok, archive_path, manifest = self.backup_service.create_backup(target_dir=self.target_dir)
            self.finished.emit(ok, archive_path, manifest)
        except Exception as exc:
            self.finished.emit(False, str(exc), {})
