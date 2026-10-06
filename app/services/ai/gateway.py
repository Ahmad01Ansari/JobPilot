"""Core AIGateway orchestrator.

Coordinates adapter resolution, execution policies, schema validation,
and telemetry without becoming a monolithic god-object.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.db.session import SessionLocal, get_db_session
from app.repositories.settings_repository import SettingsRepository
from app.services.ai.adapters.factory import AdapterFactory
from app.services.ai.errors import AIError, AIErrorMapper, RateLimitError
from app.services.ai.models import (
    AICapability,
    AIRequest,
    AIResponse,
    CapabilityReport,
    CapabilityState,
    ConnectionTestResult,
    ModelInfo,
    StructuredOutputResult,
)
from app.services.ai.policy import AIRequestPolicy
from app.services.ai.provider_registry import AIProviderRegistry
from app.services.ai.schema_validator import AISchemaValidator

logger = logging.getLogger("JobPilot.AIGateway")


class AIGateway:
    """Orchestrates AI request execution across resolved protocol adapters."""

    def __init__(
        self,
        session_factory=None,
        adapter_factory: Optional[AdapterFactory] = None,
        policy: Optional[AIRequestPolicy] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self.adapter_factory = adapter_factory or AdapterFactory()
        self.policy = policy or AIRequestPolicy()

    # -------------------------------------------------------------------------
    # Configuration Retrieval
    # -------------------------------------------------------------------------
    def get_config(self) -> Dict[str, Any]:
        """Retrieves active AI configuration and resolves credentials."""
        from app.services.secrets_service import SecretsService
        secrets_svc = SecretsService(session_factory=self._session_factory)

        with get_db_session(self._session_factory) as session:
            repo = SettingsRepository(session)
            enabled = bool(repo.get("ai.use_AI", True))
            prov_id = str(repo.get("ai.provider_id") or repo.get("ai.provider", "ollama")).strip().lower()
            model = str(repo.get("ai.model", "llama3.1:8b")).strip()
            base_url = str(repo.get("ai.api_url", "http://localhost:11434/v1")).strip()

        preset = AIProviderRegistry.get_provider(prov_id)
        if not base_url and preset:
            base_url = preset.default_base_url

        # Canonical provider-scoped secret lookup with legacy fallback
        api_key = secrets_svc.get_secret(f"ai.api_key.{prov_id}") or secrets_svc.get_secret("llm_api_key", default="") or ""

        return {
            "enabled": enabled,
            "provider_id": prov_id,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
        }

    # -------------------------------------------------------------------------
    # Execution & Telemetry
    # -------------------------------------------------------------------------
    def chat(self, request: AIRequest) -> AIResponse:
        """Executes a chat request with bounded retry and policy enforcement."""
        cfg = self.get_config()
        if not cfg["enabled"]:
            raise RuntimeError("AI Engine is disabled in JobPilot settings.")

        adapter = self.adapter_factory.get_adapter(cfg["provider_id"])
        base_url = cfg["base_url"]
        api_key = cfg["api_key"]

        attempts = 0
        last_error = None

        while attempts <= self.policy.max_retries:
            try:
                resp = adapter.chat(request, base_url=base_url, api_key=api_key)
                logger.info(
                    "AI execution success [provider=%s, model=%s, latency=%.1fms, tokens=%d]",
                    cfg["provider_id"],
                    request.model,
                    resp.latency_ms,
                    resp.usage.total_tokens,
                )
                return resp
            except RateLimitError as err:
                last_error = err
                attempts += 1
                if attempts <= self.policy.max_retries:
                    sleep_sec = self.policy.compute_backoff(attempts, err.retry_after_seconds)
                    logger.warning("AI rate limited. Retrying attempt %d after %.1fs", attempts, sleep_sec)
                    time.sleep(sleep_sec)
                else:
                    break
            except Exception as exc:
                last_error = exc
                break

        if last_error:
            raise last_error
        raise AIError("AI execution failed unexpectedly.", error_code="EXECUTION_FAILED")

    def request_structured_output(
        self,
        prompt: str,
        expected_schema: Any,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> StructuredOutputResult:
        """Executes an inference request and validates the JSON output against schema."""
        cfg = self.get_config()
        active_model = model or cfg["model"]

        schema_str = json.dumps(expected_schema) if isinstance(expected_schema, (dict, list)) else str(expected_schema)

        directives = (
            (system_prompt or "You are an expert AI data extraction assistant.")
            + "\n\nCRITICAL: You MUST respond ONLY with valid RFC 8259 JSON.\n"
            + "Do not include any introductory remarks, markdown code blocks, backticks (```json), or post-explanations.\n"
            + f"Output must conform strictly to this JSON schema structure:\n{schema_str}"
        )

        messages = [
            {"role": "system", "content": directives},
            {"role": "user", "content": prompt},
        ]

        req = AIRequest(
            messages=messages,
            model=active_model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        try:
            resp = self.chat(req)
            return AISchemaValidator.validate(resp.content, expected_schema=expected_schema)
        except Exception as exc:
            msg, code, _ = AIErrorMapper.normalize(exc, provider_id=cfg["provider_id"], model=active_model)
            return StructuredOutputResult(
                success=False,
                raw_response="",
                error_type="unsupported_feature" if code == "UNSUPPORTED_FEATURE" else "invalid_json",
                validation_errors=[msg],
            )

    # -------------------------------------------------------------------------
    # Diagnostics & Discovery
    # -------------------------------------------------------------------------
    def test_connection(
        self,
        provider_id: str,
        base_url: str,
        api_key: Optional[str],
        model: str,
    ) -> ConnectionTestResult:
        """Performs two-level diagnostic test: connectivity + minimal non-PII ping."""
        adapter = self.adapter_factory.get_adapter(provider_id)

        # Level 1: Connectivity check
        conn_ok, conn_msg, conn_lat = adapter.test_connectivity(base_url, api_key)
        if not conn_ok:
            return ConnectionTestResult(
                success=False,
                status="unauthorized" if "authentication" in conn_msg.lower() else "unreachable",
                message=conn_msg,
                latency_ms=conn_lat,
                provider_id=provider_id,
                model=model,
            )

        # Level 2: AI Compatibility check
        res = adapter.test_compatibility(base_url, api_key, model)
        res.provider_id = provider_id
        return res

    def discover_models(
        self,
        provider_id: str,
        base_url: str,
        api_key: Optional[str] = None,
    ) -> Tuple[List[ModelInfo], Optional[str]]:
        """Invokes provider-specific model discovery without treating failure as a fatal error."""
        adapter = self.adapter_factory.get_adapter(provider_id)
        return adapter.list_models(base_url, api_key)
