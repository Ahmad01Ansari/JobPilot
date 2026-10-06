"""Background worker for testing AI provider reachability and measuring endpoint latency."""

from typing import Optional
from PySide6.QtCore import QThread, Signal
from app.services.ai_service import UniversalAIService


class AITestWorker(QThread):
    """Runs UniversalAIService.test_connection() asynchronously and measures real round-trip latency."""

    result = Signal(bool, str, float)  # (success: bool, message: str, latency_ms: float)

    def __init__(
        self,
        ai_service: UniversalAIService,
        provider: str,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.ai_service = ai_service
        self.provider = provider
        self.api_key = api_key
        self.api_url = api_url
        self.model = model

    def run(self) -> None:
        try:
            ok, msg, latency = self.ai_service.test_connection(
                provider=self.provider,
                api_key=self.api_key,
                api_url=self.api_url,
                model=self.model,
            )
            self.result.emit(ok, msg, latency)
        except Exception as exc:
            self.result.emit(False, f"Connection test failed: {exc}", 0.0)
