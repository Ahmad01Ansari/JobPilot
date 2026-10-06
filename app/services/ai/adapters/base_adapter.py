"""Abstract base adapter contract for AI protocol implementations."""

from abc import ABC, abstractmethod
from typing import List, Optional, Set, Tuple

from app.services.ai.models import (
    AICapability,
    AIRequest,
    AIResponse,
    ConnectionTestResult,
    ModelInfo,
)


class BaseAIAdapter(ABC):
    """Abstract communication adapter for a specific protocol."""

    @abstractmethod
    def chat(self, request: AIRequest, base_url: str, api_key: Optional[str] = None) -> AIResponse:
        """Executes a chat completion query and returns an AIResponse."""

    @abstractmethod
    def test_connectivity(self, base_url: str, api_key: Optional[str] = None) -> Tuple[bool, str, float]:
        """Level 1 Test: Validates network reachability and authentication."""

    @abstractmethod
    def test_compatibility(self, base_url: str, api_key: Optional[str], model: str) -> ConnectionTestResult:
        """Level 2 Test: Validates that the configured model can execute minimal inference."""

    @abstractmethod
    def list_models(self, base_url: str, api_key: Optional[str] = None) -> Tuple[List[ModelInfo], Optional[str]]:
        """Discovers available models from the endpoint or returns empty list with notice."""

    @abstractmethod
    def capabilities(self) -> Set[AICapability]:
        """Returns the capabilities natively supported by this protocol adapter."""
