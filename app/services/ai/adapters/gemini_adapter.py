"""Native Google Gemini Protocol Adapter for JobPilot.

Uses direct REST calls to Google's generativelanguage v1beta API without forcing
Gemini through artificial OpenAI SDK emulation.
"""

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.ai.adapters.base_adapter import BaseAIAdapter
from app.services.ai.errors import (
    AIError,
    AIErrorMapper,
    AuthenticationError,
    ModelNotFoundError,
)
from app.services.ai.models import (
    AICapability,
    AIRequest,
    AIResponse,
    AIUsage,
    ConnectionTestResult,
    ModelInfo,
)


class GeminiNativeAdapter(BaseAIAdapter):
    """Native REST adapter for Google Gemini generativelanguage.googleapis.com API."""

    def chat(self, request: AIRequest, base_url: str, api_key: Optional[str] = None) -> AIResponse:
        clean_key = (api_key or "").strip()
        if not clean_key:
            raise AuthenticationError("API key is required for Google Gemini.")

        clean_model = request.model if request.model.startswith("models/") else f"models/{request.model}"
        clean_base = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        url = f"{clean_base}/v1beta/{clean_model}:generateContent?key={clean_key}"

        contents = []
        for msg in request.messages:
            role = "user" if msg.get("role") in ("user", "system") else "model"
            contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": max(0.0, min(1.0, request.temperature)),
                "maxOutputTokens": request.max_tokens or 4096,
            },
        }
        if request.response_format:
            payload["generationConfig"]["responseMimeType"] = "application/json"

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "JobPilot/2.0"})

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                body = json.loads(resp.read().decode("utf-8"))
                candidates = body.get("candidates", [])
                if not candidates:
                    raise AIError("Gemini returned empty candidates.", error_code="EMPTY_RESPONSE")

                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise AIError("Gemini candidate has no parts.", error_code="EMPTY_RESPONSE")

                content = parts[0].get("text", "").strip()
                usage_metadata = body.get("usageMetadata", {})
                usage = AIUsage(
                    prompt_tokens=usage_metadata.get("promptTokenCount", 0),
                    completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
                    total_tokens=usage_metadata.get("totalTokenCount", 0),
                )

                return AIResponse(
                    content=content,
                    model=request.model,
                    provider_id="gemini",
                    usage=usage,
                    latency_ms=latency_ms,
                    raw=body,
                )

        except urllib.error.HTTPError as err:
            if err.code in (400, 403):
                raise AuthenticationError("Authentication failed: Check your Google Gemini API key.")
            elif err.code == 404:
                raise ModelNotFoundError(request.model, f"Gemini model '{request.model}' was not found.")
            raise AIError(f"Gemini HTTP Error {err.code}: {err.reason}", error_code=f"HTTP_{err.code}")
        except Exception as e:
            raise AIError(f"Gemini request failed: {e}", error_code="NETWORK_ERROR")

    def test_connectivity(self, base_url: str, api_key: Optional[str] = None) -> Tuple[bool, str, float]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return False, "API key is required for Google Gemini.", 0.0

        clean_base = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        url = f"{clean_base}/v1beta/models?key={clean_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "JobPilot/2.0"})

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                if resp.status == 200:
                    return True, "Google Gemini API connected and verified.", latency
                return False, f"Gemini returned HTTP status {resp.status}.", latency
        except urllib.error.HTTPError as err:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            if err.code in (400, 403):
                return False, f"Authentication failed ({err.code}): Invalid Google Gemini API key.", latency
            return False, f"HTTP Error {err.code}: {err.reason}", latency
        except Exception as err:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            return False, f"Cannot connect to Gemini: {err}", latency

    def test_compatibility(self, base_url: str, api_key: Optional[str], model: str) -> ConnectionTestResult:
        start_time = time.perf_counter()
        req = AIRequest(
            messages=[{"role": "user", "content": "Ping"}],
            model=model,
            temperature=0.0,
            max_tokens=10,
        )
        try:
            resp = self.chat(req, base_url=base_url, api_key=api_key)
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            return ConnectionTestResult(
                success=True,
                status="verified",
                message=f"Gemini model '{model}' verified and responsive.",
                latency_ms=latency,
                provider_id="gemini",
                model=model,
                capabilities_verified={AICapability.CHAT, AICapability.STRUCTURED_OUTPUT},
            )
        except Exception as exc:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            msg, code, help_url = AIErrorMapper.normalize(exc, provider_id="gemini", model=model)
            status = "unauthorized" if code == "AUTHENTICATION_FAILED" else "failed"
            return ConnectionTestResult(
                success=False,
                status=status,
                message=msg,
                latency_ms=latency,
                provider_id="gemini",
                model=model,
                error_code=code,
                help_url=help_url,
            )

    def list_models(self, base_url: str, api_key: Optional[str] = None) -> Tuple[List[ModelInfo], Optional[str]]:
        clean_key = (api_key or "").strip()
        if not clean_key:
            return [], "API key is required to list Gemini models."

        clean_base = (base_url or "https://generativelanguage.googleapis.com").rstrip("/")
        url = f"{clean_base}/v1beta/models?key={clean_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "JobPilot/2.0"})

        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    models = []
                    for m in body.get("models", []):
                        m_name = m.get("name", "")
                        clean_id = m_name.replace("models/", "") if m_name.startswith("models/") else m_name
                        if "gemini" in clean_id.lower():
                            models.append(ModelInfo(
                                id=clean_id,
                                name=m.get("displayName", clean_id),
                                description=m.get("description"),
                            ))
                    return models, None
                return [], f"Gemini returned status {resp.status}"
        except Exception as err:
            return [], f"Failed to discover Gemini models: {err}"

    def capabilities(self) -> Set[AICapability]:
        return {
            AICapability.CHAT,
            AICapability.STRUCTURED_OUTPUT,
            AICapability.VISION,
            AICapability.MODEL_LIST,
        }
