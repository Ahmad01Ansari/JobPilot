"""Factory for resolving protocol adapters based on provider definition."""

from typing import Dict, Optional

from app.services.ai.adapters.base_adapter import BaseAIAdapter
from app.services.ai.adapters.gemini_adapter import GeminiNativeAdapter
from app.services.ai.adapters.openai_adapter import OpenAICompatibleAdapter
from app.services.ai.provider_registry import AIProviderRegistry


class AdapterFactory:
    """Instantiates and caches protocol adapters."""

    def __init__(self):
        self._openai_adapter = OpenAICompatibleAdapter()
        self._gemini_adapter = GeminiNativeAdapter()

    def get_adapter(self, provider_id: str) -> BaseAIAdapter:
        """Resolves protocol adapter for the specified provider ID."""
        prov = AIProviderRegistry.get_provider(provider_id)
        protocol = prov.protocol if prov else "openai-compatible"

        if protocol == "gemini-native":
            return self._gemini_adapter
        return self._openai_adapter

    def get_adapter_by_protocol(self, protocol: str) -> BaseAIAdapter:
        if protocol == "gemini-native":
            return self._gemini_adapter
        return self._openai_adapter
