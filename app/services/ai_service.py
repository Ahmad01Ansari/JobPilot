"""Universal AI Engine Service for JobPilot (High-Level Façade).

Provides a backwards-compatible interface for all JobPilot AI consumers
(QnAEngine, SemanticAIAdvisor, ResumeParser, OutreachAIService, Stagehand)
while delegating core execution to the decoupled AIGateway and Protocol Adapters.

CRITICAL INVARIANTS:
1. Cloud API keys are NEVER written to config/profile.json.
2. Existing Ollama and cloud configurations are preserved without breaking changes.
3. Structured output validation parses JSON without relying on unvalidated assumptions.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import SessionLocal, get_db_session
from app.repositories.settings_repository import SettingsRepository
from app.services.ai.gateway import AIGateway
from app.services.ai.models import AIRequest
from app.services.ai.provider_registry import AIProviderRegistry
from app.services.secrets_service import SecretsService

logger = logging.getLogger("JobPilot.UniversalAIService")

DEFAULT_OLLAMA_URL = "http://localhost:11434/v1"
DEFAULT_OPENAI_URL = "https://api.openai.com/v1"
DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/v1"


class UniversalAIService:
    """Universal AI Client provider and executor supporting local and cloud LLMs."""

    def __init__(self, session_factory=None, gateway: Optional[AIGateway] = None, secrets_service: Optional[Any] = None):
        self._session_factory = session_factory or SessionLocal
        self.gateway = gateway or AIGateway(session_factory=self._session_factory)
        self._secrets_service = secrets_service

    # -------------------------------------------------------------------------
    # Configuration Retrieval & Persistence
    # -------------------------------------------------------------------------
    def get_config(self) -> Dict[str, Any]:
        """Returns the active AI configuration and decrypted credentials."""
        cfg = self.gateway.get_config()
        return {
            "enabled": cfg["enabled"],
            "provider": cfg["provider_id"],
            "model": cfg["model"],
            "api_url": cfg["base_url"],
            "api_key": cfg["api_key"],
        }

    def get_provider_config(self, provider_id: str) -> Dict[str, Any]:
        """Returns the persisted or default configuration for a specific provider."""
        prov = (provider_id or "ollama").strip().lower()
        preset = AIProviderRegistry.get_provider(prov)
        def_model = preset.default_model if preset else "llama3.1:8b"
        def_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL

        model = def_model
        api_url = def_url

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            active_prov = (repo.get("ai.provider", "ollama") or "ollama").strip().lower()
            if active_prov == prov:
                model = repo.get("ai.model", def_model)
                api_url = repo.get("ai.api_url", def_url)
            else:
                model = repo.get(f"ai.{prov}.model", def_model)
                api_url = repo.get(f"ai.{prov}.api_url", def_url)

        if self._secrets_service is not None:
            secrets_svc = self._secrets_service
        else:
            from app.services.secrets_service import SecretsService
            secrets_svc = SecretsService(session_factory=self._session_factory)

        api_key = secrets_svc.get_ai_secret(prov)

        return {
            "provider": prov,
            "model": model,
            "api_url": api_url,
            "api_key": api_key,
        }

    def save_provider_config(
        self,
        provider: str,
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Persists isolated configuration for a specific provider without changing the active engine pointer."""
        prov = (provider or "ollama").strip().lower()
        clean_model = (model or "").strip()
        preset = AIProviderRegistry.get_provider(prov)

        if not clean_model:
            clean_model = preset.default_model if preset else "llama3.1:8b"

        clean_url = (api_url or "").strip()
        if not clean_url:
            clean_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            repo.set(f"ai.{prov}.model", clean_model, category="ai", description=f"{prov} Model Name")
            repo.set(f"ai.{prov}.api_url", clean_url, category="ai", description=f"{prov} Endpoint URL")
            session.commit()

        if api_key is not None and api_key != "••••••••" and api_key.strip():
            secrets_svc = self._secrets_service or SecretsService(session_factory=self._session_factory)
            secrets_svc.set_ai_secret(prov, api_key.strip())

    def save_config(
        self,
        enabled: bool = True,
        provider: str = "ollama",
        model: Optional[str] = None,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> None:
        """Persists AI settings to SQLite database and SecretsService.

        Strictly enforces that cloud credentials are NOT copied to profile.json.
        """
        if self._secrets_service is not None:
            secrets_svc = self._secrets_service
        else:
            from app.services.secrets_service import SecretsService
            secrets_svc = SecretsService(session_factory=self._session_factory)

        prov = (provider or "ollama").strip().lower()
        clean_model = (model or "").strip()
        preset = AIProviderRegistry.get_provider(prov)

        if not clean_model:
            clean_model = preset.default_model if preset else "llama3.1:8b"

        clean_url = (api_url or "").strip()
        if not clean_url:
            clean_url = preset.default_base_url if preset else DEFAULT_OLLAMA_URL

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            repo.set("ai.use_AI", enabled, category="ai", description="Master AI Engine Toggle")
            repo.set("ai.provider", prov, category="ai", description="Universal AI Provider")
            repo.set("ai.provider_id", prov, category="ai", description="Canonical Provider ID")
            repo.set("ai.model", clean_model, category="ai", description="Active Model Name")
            repo.set("ai.api_url", clean_url, category="ai", description="AI Endpoint URL")
            repo.set(f"ai.{prov}.model", clean_model, category="ai", description=f"{prov} Model Name")
            repo.set(f"ai.{prov}.api_url", clean_url, category="ai", description=f"{prov} Endpoint URL")
            session.commit()

        if api_key is not None and api_key != "••••••••":
            secrets_svc.set_ai_secret(prov, api_key.strip())

        # Sync non-secret configuration to config/profile.json (ZERO cloud keys stored)
        self._sync_to_profile_json(
            enabled=enabled,
            provider=prov,
            model=clean_model,
            api_url=clean_url,
        )

    def _sync_to_profile_json(
        self,
        enabled: bool,
        provider: str,
        model: str,
        api_url: str,
    ) -> None:
        """Updates the 'ai' section of config/profile.json with non-secret metadata only."""
        profile_path = Path(__file__).resolve().parent.parent.parent / "config" / "profile.json"
        if not profile_path.exists():
            return
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if "ai" not in data or not isinstance(data["ai"], dict):
                data["ai"] = {}

            data["ai"]["enabled"] = enabled
            data["ai"]["provider"] = provider
            data["ai"]["model"] = model
            data["ai"]["api_url"] = api_url

            # Enforce zero cloud secrets invariant in profile.json
            if provider == "ollama":
                data["ai"]["api_key"] = "ollama"
            else:
                data["ai"]["api_key"] = "MANAGED_BY_JOBPILOT_SECRETS_SERVICE"

            with open(profile_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            from modules import config_loader
            config_loader.invalidate_cache()
        except Exception as e:
            logger.warning("Failed to sync non-secret AI config to profile.json: %s", e)

    # -------------------------------------------------------------------------
    # Diagnostics & Testing
    # -------------------------------------------------------------------------
    def test_connection(
        self,
        provider: str,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Tuple[bool, str, float]:
        """Validates provider connectivity and compatibility through AIGateway."""
        prov = (provider or "ollama").strip().lower()
        if not AIProviderRegistry.is_supported(prov):
            return False, f"Unsupported AI provider: {provider}", 0.0

        preset = AIProviderRegistry.get_provider(prov)
        if preset and preset.requires_api_key and not (api_key or "").strip():
            return False, f"{preset.display_name} requires an API key.", 0.0

        clean_url = api_url or (preset.default_base_url if preset else DEFAULT_OLLAMA_URL)
        clean_model = model or (preset.default_model if preset else "llama3.1:8b")

        res = self.gateway.test_connection(
            provider_id=prov,
            base_url=clean_url,
            api_key=api_key,
            model=clean_model,
        )
        return res.success, res.message, res.latency_ms

    # -------------------------------------------------------------------------
    # Text Generation & Structured Extraction
    # -------------------------------------------------------------------------
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
    ) -> str:
        """Executes a chat completion query through the active AI provider."""
        cfg = self.get_config()
        if not cfg["enabled"]:
            raise RuntimeError("Universal AI Engine is disabled in settings.")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        req = AIRequest(
            messages=messages,
            model=cfg["model"],
            temperature=temperature,
        )
        resp = self.gateway.chat(req)
        clean = re.sub(r"<(think|thought|reasoning)>.*?</\1>", "", resp.content, flags=re.DOTALL | re.IGNORECASE).strip()
        return clean if clean else resp.content

    def extract_structured_json(
        self,
        prompt: str,
        schema_description: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Prompts the model for structured JSON and parses/validates against schema."""
        cfg = self.get_config()
        if not cfg["enabled"]:
            raise RuntimeError("Universal AI Engine is disabled in settings.")

        res = self.gateway.request_structured_output(
            prompt=prompt,
            expected_schema=schema_description,
            system_prompt=system_prompt,
            model=cfg["model"],
            temperature=0.0,
        )
        if not res.success or res.data is None:
            err_msg = "; ".join(res.validation_errors) if res.validation_errors else "Failed to parse structured JSON."
            raise ValueError(f"AI structured output validation error: {err_msg}")

        return res.data

    # -------------------------------------------------------------------------
    # Legacy Compatibility Client for External Bot Scripts
    # -------------------------------------------------------------------------
    def get_active_client(self) -> Any:
        """Returns an OpenAI SDK client instance for legacy bot compatibility."""
        cfg = self.get_config()
        if not cfg.get("enabled"):
            return None

        provider = cfg.get("provider", "ollama")
        api_url = cfg.get("api_url", DEFAULT_OLLAMA_URL)
        api_key = cfg.get("api_key", "") or "ollama"

        # Gemini does not use the OpenAI SDK
        if provider == "gemini":
            return None

        if provider == "azure_openai" or "openai.azure.com" in api_url:
            try:
                import urllib.parse
                from openai import AzureOpenAI
                parsed = urllib.parse.urlsplit(api_url)
                qs = urllib.parse.parse_qs(parsed.query)
                api_version = qs.get("api-version", ["2024-02-15-preview"])[0]
                base_endpoint = f"{parsed.scheme}://{parsed.netloc}"
                return AzureOpenAI(
                    azure_endpoint=base_endpoint,
                    api_key=api_key,
                    api_version=api_version,
                )
            except Exception:
                pass

        try:
            from openai import OpenAI
            return OpenAI(base_url=api_url, api_key=api_key)
        except ImportError:
            return None
        except Exception:
            return None
