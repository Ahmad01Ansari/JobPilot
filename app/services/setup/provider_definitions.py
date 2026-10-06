"""
Data-driven Provider Definitions and Metadata for JobPilot AI Setup.
Avoids hardcoding pricing/tier claims; provides maintainable links to official documentation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ProviderMetadata:
    """External metadata and documentation endpoints for an AI Provider."""
    id: str
    name: str
    adapter_type: str                # "openai_compatible", "ollama", "native"
    default_endpoint: str
    default_model: str
    available_models: List[str]
    api_key_url: str
    documentation_url: str
    privacy_policy_url: str
    supports_model_discovery: bool
    requires_api_key: bool
    description: str
    notice: str = "Provider terms, quotas, and model availability may change over time."


# Canonical provider registry with official documentation URLs
PROVIDER_REGISTRY: Dict[str, ProviderMetadata] = {
    "groq": ProviderMetadata(
        id="groq",
        name="Groq Cloud",
        adapter_type="openai_compatible",
        default_endpoint="https://api.groq.com/openai/v1",
        default_model="llama-3.3-70b-versatile",
        available_models=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
        ],
        api_key_url="https://console.groq.com/keys",
        documentation_url="https://console.groq.com/docs/quickstart",
        privacy_policy_url="https://groq.com/privacy-policy",
        supports_model_discovery=False,
        requires_api_key=True,
        description="Ultra-fast cloud inference with LPU acceleration.",
    ),
    "nvidia": ProviderMetadata(
        id="nvidia",
        name="NVIDIA NIM",
        adapter_type="openai_compatible",
        default_endpoint="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.1-70b-instruct",
        available_models=[
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            "mistralai/mixtral-8x7b-instruct-v0.1",
        ],
        api_key_url="https://build.nvidia.com/",
        documentation_url="https://docs.api.nvidia.com/nim/reference",
        privacy_policy_url="https://www.nvidia.com/en-us/about-nvidia/privacy-policy",
        supports_model_discovery=False,
        requires_api_key=True,
        description="Enterprise-grade microservices for foundation models.",
    ),
    "ollama": ProviderMetadata(
        id="ollama",
        name="Ollama (Local / Private)",
        adapter_type="ollama",
        default_endpoint="http://localhost:11434/api",
        default_model="llama3.1:8b",
        available_models=["llama3.1:8b", "mistral:latest", "qwen2.5:7b"],
        api_key_url="",
        documentation_url="https://github.com/ollama/ollama",
        privacy_policy_url="https://ollama.com",
        supports_model_discovery=True,
        requires_api_key=False,
        description="100% local, private, and offline inference. Zero data leaves your computer.",
    ),
    "openai": ProviderMetadata(
        id="openai",
        name="OpenAI",
        adapter_type="openai_compatible",
        default_endpoint="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        available_models=["gpt-4o-mini", "gpt-4o"],
        api_key_url="https://platform.openai.com/api-keys",
        documentation_url="https://platform.openai.com/docs/overview",
        privacy_policy_url="https://openai.com/policies/privacy-policy",
        supports_model_discovery=False,
        requires_api_key=True,
        description="Industry standard general-purpose models.",
    ),
    "anthropic": ProviderMetadata(
        id="anthropic",
        name="Anthropic Claude",
        adapter_type="native",
        default_endpoint="https://api.anthropic.com/v1",
        default_model="claude-3-5-sonnet-latest",
        available_models=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        api_key_url="https://console.anthropic.com/settings/keys",
        documentation_url="https://docs.anthropic.com/claude/reference",
        privacy_policy_url="https://www.anthropic.com/legal/privacy",
        supports_model_discovery=False,
        requires_api_key=True,
        description="High-reasoning intelligence with strong instruction following.",
    ),
    "gemini": ProviderMetadata(
        id="gemini",
        name="Google Gemini",
        adapter_type="native",
        default_endpoint="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-1.5-flash",
        available_models=["gemini-1.5-flash", "gemini-2.0-flash-exp", "gemini-1.5-pro"],
        api_key_url="https://aistudio.google.com/app/apikey",
        documentation_url="https://ai.google.dev/docs",
        privacy_policy_url="https://policies.google.com/privacy",
        supports_model_discovery=False,
        requires_api_key=True,
        description="Large-context multimodal models from Google AI Studio.",
    ),
    "openai_compatible": ProviderMetadata(
        id="openai_compatible",
        name="Custom OpenAI-Compatible",
        adapter_type="openai_compatible",
        default_endpoint="",
        default_model="",
        available_models=[],
        api_key_url="",
        documentation_url="https://platform.openai.com/docs/api-reference",
        privacy_policy_url="",
        supports_model_discovery=False,
        requires_api_key=True,
        description="Connect any custom or self-hosted endpoint matching OpenAI's specification (OpenRouter, Together, LM Studio, vLLM).",
    ),
}


def get_all_providers() -> List[ProviderMetadata]:
    """Returns a list of all registered provider metadata."""
    return list(PROVIDER_REGISTRY.values())


def get_provider_by_id(provider_id: str) -> Optional[ProviderMetadata]:
    """Retrieves metadata for a specific provider by identifier."""
    return PROVIDER_REGISTRY.get(provider_id.lower())
