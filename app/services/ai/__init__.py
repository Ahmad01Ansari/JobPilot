"""JobPilot AI Services Module.

Exposes the decoupled AI Gateway, provider registry, adapters, and domain models.
"""

from app.services.ai.errors import (
    AIError,
    AIErrorMapper,
    AuthenticationError,
    EndpointUnreachableError,
    ModelNotFoundError,
    RateLimitError,
    SchemaValidationError,
    UnsupportedFeatureError,
)
from app.services.ai.gateway import AIGateway
from app.services.ai.models import (
    AICapability,
    AIRequest,
    AIResponse,
    AIUsage,
    CapabilityReport,
    CapabilityState,
    ConnectionTestResult,
    ModelInfo,
    StructuredOutputResult,
)
from app.services.ai.policy import AIRequestPolicy
from app.services.ai.provider_registry import AIProviderRegistry, ProviderDefinition
from app.services.ai.prompt_guard import PromptSecurityGuard

__all__ = [
    "AIGateway",
    "AIProviderRegistry",
    "ProviderDefinition",
    "PromptSecurityGuard",
    "AICapability",
    "CapabilityState",
    "ModelInfo",
    "AIRequest",
    "AIResponse",
    "AIUsage",
    "StructuredOutputResult",
    "ConnectionTestResult",
    "CapabilityReport",
    "AIRequestPolicy",
    "AIError",
    "AIErrorMapper",
    "AuthenticationError",
    "EndpointUnreachableError",
    "ModelNotFoundError",
    "RateLimitError",
    "QuotaExceededError",
    "UnsupportedFeatureError",
    "SchemaValidationError",
]
