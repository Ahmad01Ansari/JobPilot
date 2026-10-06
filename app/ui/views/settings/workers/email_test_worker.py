"""Background worker for testing SMTP and IMAP email outreach connections asynchronously."""

from typing import Optional
from PySide6.QtCore import QThread, Signal
from app.services.secrets_service import SecretsService


class EmailTestWorker(QThread):
    """Asynchronous worker to test SMTP and IMAP connection without blocking the Qt event loop."""

    # Emits (success: bool, step: str, message: str)
    progress = Signal(str, str)  # (step_name, status_message)
    finished = Signal(bool, str)  # (overall_success, final_summary_message)

    def __init__(
        self,
        secrets_service: SecretsService,
        user: str,
        password: str,
        smtp_host: str,
        smtp_port: int,
        imap_host: str,
        imap_port: int,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.secrets_service = secrets_service
        self.user = user
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.imap_host = imap_host
        self.imap_port = imap_port

    def run(self) -> None:
        try:
            self.progress.emit("smtp", f"Connecting to SMTP server {self.smtp_host}:{self.smtp_port}...")
            ok, msg = self.secrets_service.test_email_connection(
                user=self.user,
                password=self.password,
                smtp_host=self.smtp_host,
                smtp_port=self.smtp_port,
                imap_host=self.imap_host,
                imap_port=self.imap_port,
            )
            if ok:
                self.progress.emit("imap", "SMTP authenticated. Verifying IMAP mailbox access...")
            self.finished.emit(ok, msg)
        except Exception as exc:
            self.finished.emit(False, f"Connection failed: {exc}")
