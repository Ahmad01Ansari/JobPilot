"""Background worker for discovering models across AI providers."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from app.services.ai.gateway import AIGateway
from app.services.ai_service import DEFAULT_OLLAMA_URL


class ModelDiscoveryWorker(QThread):
    """Fetches installed/available models asynchronously across local and cloud providers."""

    result = Signal(list, str)  # (models: List[Dict[str, Any]], error: str)

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        provider_id: str = "ollama",
        api_key: Optional[str] = None,
        gateway: Optional[AIGateway] = None,
        parent: Optional[QThread] = None,
    ):
        super().__init__(parent)
        self.endpoint_url = (endpoint_url or DEFAULT_OLLAMA_URL).strip()
        self.provider_id = (provider_id or "ollama").strip().lower()
        self.api_key = api_key
        self.gateway = gateway or AIGateway()

    def run(self) -> None:
        try:
            models, err = self.gateway.discover_models(
                provider_id=self.provider_id,
                base_url=self.endpoint_url,
                api_key=self.api_key,
            )
            if err:
                self.result.emit([], err)
                return

            parsed_models: List[Dict[str, Any]] = []
            for m in models:
                parsed_models.append({
                    "name": m.id,
                    "size": m.size or m.description or "",
                })
            self.result.emit(parsed_models, "")
        except Exception as exc:
            self.result.emit([], str(exc))

