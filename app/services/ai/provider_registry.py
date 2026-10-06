"""Provider Registry and Official Documentation Catalog for JobPilot.

Defines supported provider presets, verified official documentation URLs,
setup guidance steps, and default endpoints.

CRITICAL INVARIANTS:
1. Zero hardcoded pricing or free-tier claims. Always link to official pricing_url.
2. Suggested models are strictly non-authoritative UI convenience hints, NOT validation gates.
3. Official documentation and API key URLs point exclusively to first-party portals.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


@dataclass(frozen=True)
class ProviderDefinition:
    """Metadata and verified documentation links for an AI provider preset."""
    id: str
    display_name: str
    category: Literal["local", "cloud", "custom"]
    protocol: Literal["openai-compatible", "gemini-native"]
    default_base_url: str
    default_model: str
    suggested_models: List[str] = field(default_factory=list)
    requires_api_key: bool = True
    docs_url: str = ""
    api_key_url: Optional[str] = None
    pricing_url: Optional[str] = None
    is_local: bool = False
    setup_steps: List[str] = field(default_factory=list)


PROVIDER_REGISTRY: Dict[str, ProviderDefinition] = {
    "ollama": ProviderDefinition(
        id="ollama",
        display_name="Ollama (Local Inference)",
        category="local",
        protocol="openai-compatible",
        default_base_url="http://localhost:11434/v1",
        default_model="llama3.1:8b",
        suggested_models=["llama3.1:8b", "llama3.2:3b", "qwen2.5:7b", "mistral:7b"],
        requires_api_key=False,
        docs_url="https://ollama.com/",
        api_key_url=None,
        pricing_url=None,
        is_local=True,
        setup_steps=[
            "Install Ollama from ollama.com",
            "Run 'ollama serve' in your terminal",
            "Pull a model: 'ollama run llama3.1:8b'",
            "Click Test Connection to verify local reachability",
        ],
    ),
    "groq": ProviderDefinition(
        id="groq",
        display_name="Groq",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.groq.com/openai/v1",
        default_model="openai/gpt-oss-120b",
        suggested_models=[
            "openai/gpt-oss-120b",
            "openai/gpt-oss-20b",
            "qwen/qwen3.8-27b",
            "llama-3.1-8b-instant",
            "llama-3.3-70b-versatile",
        ],
        requires_api_key=True,
        docs_url="https://console.groq.com/docs/openai",
        api_key_url="https://console.groq.com/keys",
        pricing_url="https://groq.com/pricing/",
        is_local=False,
        setup_steps=[
            "Sign up or log in at console.groq.com",
            "Navigate to API Keys and create a new key",
            "Copy the key into JobPilot and test connection",
            "Select an active model like openai/gpt-oss-120b or qwen/qwen3.8-27b",
        ],
    ),
    "xai": ProviderDefinition(
        id="xai",
        display_name="xAI (Grok)",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.x.ai/v1",
        default_model="grok-beta",
        suggested_models=["grok-beta", "grok-2-1212", "grok-2-vision-1212"],
        requires_api_key=True,
        docs_url="https://docs.x.ai/",
        api_key_url="https://console.x.ai/",
        pricing_url="https://x.ai/api",
        is_local=False,
        setup_steps=[
            "Sign in to the xAI Developer Console at console.x.ai",
            "Create an API key under your team settings",
            "Paste the key into JobPilot and test connection",
        ],
    ),
    "nvidia": ProviderDefinition(
        id="nvidia",
        display_name="NVIDIA NIM",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://integrate.api.nvidia.com/v1",
        default_model="meta/llama-3.2-11b-vision-instruct",
        suggested_models=[
            "meta/llama-3.2-11b-vision-instruct",
            "meta/llama-3.2-90b-vision-instruct",
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            "nvidia/nemotron-3-ultra-550b-a55b",
        ],
        requires_api_key=True,
        docs_url="https://docs.api.nvidia.com/",
        api_key_url="https://build.nvidia.com/",
        pricing_url="https://www.nvidia.com/en-us/ai/",
        is_local=False,
        setup_steps=[
            "Create an account on build.nvidia.com",
            "Explore NIM models and generate an API key",
            "Ensure Endpoint URL is https://integrate.api.nvidia.com/v1",
            "Select an active model like meta/llama-3.2-11b-vision-instruct",
            "Enter your key and test connection",
        ],
    ),
    "huggingface": ProviderDefinition(
        id="huggingface",
        display_name="Hugging Face Inference",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api-inference.huggingface.co/v1",
        default_model="meta-llama/Llama-3.2-3B-Instruct",
        suggested_models=["meta-llama/Llama-3.2-3B-Instruct", "mistralai/Mistral-7B-Instruct-v0.3"],
        requires_api_key=True,
        docs_url="https://huggingface.co/docs/api-inference/",
        api_key_url="https://huggingface.co/settings/tokens",
        pricing_url="https://huggingface.co/pricing",
        is_local=False,
        setup_steps=[
            "Log in to huggingface.co and open Settings -> Access Tokens",
            "Create a User Access Token with 'read' permissions",
            "Paste the token into JobPilot and configure your model",
        ],
    ),
    "openrouter": ProviderDefinition(
        id="openrouter",
        display_name="OpenRouter",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://openrouter.ai/api/v1",
        default_model="anthropic/claude-3.5-sonnet",
        suggested_models=["meta-llama/llama-3.3-70b-instruct", "google/gemini-2.0-flash-exp:free"],
        requires_api_key=True,
        docs_url="https://openrouter.ai/docs",
        api_key_url="https://openrouter.ai/keys",
        pricing_url="https://openrouter.ai/pricing",
        is_local=False,
        setup_steps=[
            "Sign up at openrouter.ai",
            "Navigate to Keys and create an API Key",
            "Paste the key into JobPilot and select any supported model ID",
        ],
    ),
    "openai": ProviderDefinition(
        id="openai",
        display_name="OpenAI",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        suggested_models=["gpt-4o-mini", "gpt-4o", "o3-mini"],
        requires_api_key=True,
        docs_url="https://platform.openai.com/docs",
        api_key_url="https://platform.openai.com/api-keys",
        pricing_url="https://openai.com/pricing",
        is_local=False,
        setup_steps=[
            "Log in to platform.openai.com",
            "Go to API Keys and create a secret key",
            "Ensure you have an active billing plan / usage credits",
            "Enter the key into JobPilot and test connection",
        ],
    ),
    "deepseek": ProviderDefinition(
        id="deepseek",
        display_name="DeepSeek",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://api.deepseek.com/v1",
        default_model="deepseek-chat",
        suggested_models=["deepseek-chat", "deepseek-reasoner"],
        requires_api_key=True,
        docs_url="https://api-docs.deepseek.com/",
        api_key_url="https://platform.deepseek.com/api_keys",
        pricing_url="https://www.deepseek.com/pricing",
        is_local=False,
        setup_steps=[
            "Sign in to platform.deepseek.com",
            "Generate an API Key under API Keys",
            "Paste the key into JobPilot and test connection",
        ],
    ),
    "gemini": ProviderDefinition(
        id="gemini",
        display_name="Google Gemini",
        category="cloud",
        protocol="gemini-native",
        default_base_url="https://generativelanguage.googleapis.com",
        default_model="gemini-1.5-flash",
        suggested_models=["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash"],
        requires_api_key=True,
        docs_url="https://ai.google.dev/docs",
        api_key_url="https://aistudio.google.com/app/apikey",
        pricing_url="https://ai.google.dev/pricing",
        is_local=False,
        setup_steps=[
            "Open Google AI Studio at aistudio.google.com",
            "Click 'Get API key' and create a new key",
            "Paste the key into JobPilot and test connection",
        ],
    ),
    "azure_openai": ProviderDefinition(
        id="azure_openai",
        display_name="Azure OpenAI",
        category="cloud",
        protocol="openai-compatible",
        default_base_url="https://<your-resource-name>.openai.azure.com",
        default_model="gpt-4o-mini",
        suggested_models=["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-35-turbo"],
        requires_api_key=True,
        docs_url="https://learn.microsoft.com/en-us/azure/ai-services/openai/",
        api_key_url="https://portal.azure.com/",
        pricing_url="https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/",
        is_local=False,
        setup_steps=[
            "Create an Azure OpenAI resource in the Azure Portal",
            "Deploy your model (e.g. gpt-4.1-mini) in Azure OpenAI Studio -> Deployments",
            "Copy your Endpoint URL (e.g. https://<resource>.openai.azure.com or full deployments completions URL)",
            "Copy Key 1 or Key 2 from Azure Portal -> Keys and Endpoint",
            "Enter your deployment name as the Model Name",
            "Click Test Connection to verify reachability",
        ],
    ),
    "custom_openai": ProviderDefinition(
        id="custom_openai",
        display_name="Custom OpenAI-Compatible",
        category="custom",
        protocol="openai-compatible",
        default_base_url="http://localhost:8000/v1",
        default_model="custom-model",
        suggested_models=[],
        requires_api_key=False,
        docs_url="https://platform.openai.com/docs/api-reference",
        api_key_url=None,
        pricing_url=None,
        is_local=False,
        setup_steps=[
            "Ensure your self-hosted server (vLLM, LM Studio, LocalAI) is running",
            "Enter the full base URL (e.g. http://localhost:8000/v1)",
            "Enter the model identifier used by your server",
            "If authentication is enabled on your server, enter the API key",
        ],
    ),
}


class AIProviderRegistry:
    """Helper query interface for the provider registry."""

    @staticmethod
    def get_provider(provider_id: str) -> Optional[ProviderDefinition]:
        return PROVIDER_REGISTRY.get((provider_id or "").strip().lower())

    @staticmethod
    def list_providers() -> List[ProviderDefinition]:
        return list(PROVIDER_REGISTRY.values())

    @staticmethod
    def is_supported(provider_id: str) -> bool:
        return (provider_id or "").strip().lower() in PROVIDER_REGISTRY

    @staticmethod
    def get_default_provider_id() -> str:
        return "ollama"
