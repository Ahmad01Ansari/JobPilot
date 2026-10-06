"""Domain Data Transfer Objects (DTOs) and Enums for JobPilot AI Services.

Provides normalized internal representations decoupled from any specific provider SDK.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Set


class AICapability(str, Enum):
    """Normalized capabilities an AI provider or model may support."""
    CHAT = "chat"
    STREAMING = "streaming"
    STRUCTURED_OUTPUT = "structured_output"  # Native schema-enforced output
    JSON_MODE = "json_mode"                  # Generic json_object output
    TOOL_CALLING = "tool_calling"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    MODEL_LIST = "model_list"


class CapabilityState(str, Enum):
    """Empirical verification state of a capability."""
    VERIFIED = "verified"          # Explicitly tested and confirmed working
    DECLARED = "declared"          # Reported by provider metadata, not yet tested
    UNSUPPORTED = "unsupported"    # Tested and confirmed unsupported or rejected
    UNKNOWN = "unknown"            # No test performed and no declaration


@dataclass
class ModelInfo:
    """Discovered or manually specified model metadata."""
    id: str
    name: str
    size: Optional[str] = None
    description: Optional[str] = None
    capabilities: Set[AICapability] = field(default_factory=set)


@dataclass
class AIUsage:
    """Token consumption metadata if provided by endpoint."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AIRequest:
    """Standardized chat completion / generation request."""
    messages: List[Dict[str, str]]
    model: str
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    stream: bool = False
    response_format: Optional[Dict[str, Any]] = None
    extra_headers: Optional[Dict[str, str]] = None
    provider_config: Optional[Dict[str, Any]] = None


@dataclass
class AIResponse:
    """Standardized chat completion / generation response."""
    content: str
    model: str
    provider_id: str
    usage: AIUsage = field(default_factory=AIUsage)
    latency_ms: float = 0.0
    raw: Optional[Dict[str, Any]] = None


@dataclass
class StructuredOutputResult:
    """Result of a schema-validated structured output request."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    raw_response: str = ""
    error_type: Optional[Literal[
        "none",
        "invalid_json",
        "schema_mismatch",
        "empty_response",
        "unsupported_feature"
    ]] = "none"
    validation_errors: List[str] = field(default_factory=list)


@dataclass
class ConnectionTestResult:
    """Outcome of a connectivity or compatibility diagnostic test."""
    success: bool
    status: Literal["verified", "failed", "unreachable", "unauthorized"]
    message: str
    latency_ms: float = 0.0
    provider_id: str = "unknown"
    model: str = "unknown"
    error_code: Optional[str] = None
    help_url: Optional[str] = None
    capabilities_verified: Set[AICapability] = field(default_factory=set)


@dataclass
class CapabilityReport:
    """Empirical report of capabilities for a given provider and model."""
    provider_id: str
    model: str
    capabilities: Dict[AICapability, CapabilityState] = field(default_factory=dict)
    last_verified_at: Optional[str] = None
