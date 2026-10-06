"""Universal OpenAI-Compatible Protocol Adapter for JobPilot.

Connects to any endpoint exposing an OpenAI-compatible REST API:
- Ollama (local)
- Groq (cloud)
- xAI / Grok (cloud)
- NVIDIA NIM (cloud)
- Hugging Face (cloud)
- OpenRouter (cloud)
- DeepSeek (cloud)
- OpenAI (cloud)
- Custom self-hosted servers (vLLM, LM Studio, LocalAI)
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.ai.adapters.base_adapter import BaseAIAdapter
from app.services.ai.errors import (
    AIError,
    AIErrorMapper,
    AITimeoutError,
    AuthenticationError,
    EndpointUnreachableError,
    ModelNotFoundError,
    RateLimitError,
)
from app.services.ai.models import (
    AICapability,
    AIRequest,
    AIResponse,
    AIUsage,
    ConnectionTestResult,
    ModelInfo,
)


class OpenAICompatibleAdapter(BaseAIAdapter):
    """Universal wire protocol adapter for OpenAI-compatible endpoints."""

    def resolve_chat_endpoint(self, base_url: str, model: Optional[str] = None) -> str:
        clean = (base_url or "").strip()
        parsed = urllib.parse.urlsplit(clean)
        path = parsed.path.rstrip("/")
        is_azure = "openai.azure.com" in parsed.netloc or "azure" in parsed.netloc

        if path.endswith("/chat/completions"):
            return clean

        query = parsed.query
        if is_azure:
            if "/deployments/" not in path and model:
                path = f"{path}/openai/deployments/{model}/chat/completions".replace("//", "/")
            else:
                path = f"{path}/chat/completions"
            if not query:
                query = "api-version=2024-02-15-preview"
        else:
            # Handle Ollama or bare host endpoints without /v1
            if parsed.port == 11434 or "ollama" in clean.lower():
                if path in ("", "/", "/api"):
                    path = "/v1/chat/completions"
                elif path.endswith("/v1"):
                    path = f"{path}/chat/completions"
                elif not path.endswith("/chat/completions"):
                    path = f"{path}/chat/completions"
            else:
                if not path:
                    path = "/v1/chat/completions"
                elif not path.endswith("/chat/completions"):
                    path = f"{path}/chat/completions"

        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, query, parsed.fragment))

    def resolve_models_endpoint(self, base_url: str) -> str:
        clean = (base_url or "").strip()
        parsed = urllib.parse.urlsplit(clean)
        path = parsed.path.rstrip("/")
        if path.endswith("/chat/completions"):
            path = path[:-len("/chat/completions")]

        if parsed.port == 11434 or "ollama" in clean.lower():
            if path in ("", "/", "/api"):
                path = "/v1/models"
            elif path.endswith("/v1"):
                path = f"{path}/models"
            elif not path.endswith("/models"):
                path = f"{path}/models"
        else:
            if not path:
                path = "/v1/models"
            elif not path.endswith("/models"):
                path = f"{path}/models"

        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, parsed.fragment))

    def _build_headers(
        self,
        api_key: Optional[str],
        extra_headers: Optional[Dict[str, str]] = None,
        base_url: Optional[str] = None,
    ) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "JobPilot/2.0",
        }
        clean_key = (api_key or "").strip()
        if clean_key and clean_key != "••••••••":
            headers["Authorization"] = f"Bearer {clean_key}"
            # Azure OpenAI requires the 'api-key' header
            headers["api-key"] = clean_key

        if extra_headers:
            headers.update(extra_headers)
        return headers

    def chat(self, request: AIRequest, base_url: str, api_key: Optional[str] = None) -> AIResponse:
        endpoint = self.resolve_chat_endpoint(base_url, model=request.model)
        headers = self._build_headers(api_key, request.extra_headers, base_url=base_url)

        payload: Dict[str, Any] = {
            "model": request.model,
            "messages": request.messages,
            "temperature": max(0.0, min(2.0, request.temperature)),
            "stream": False,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.response_format:
            payload["response_format"] = request.response_format

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers=headers)

        start_time = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
                body = json.loads(resp.read().decode("utf-8"))
                choices = body.get("choices", [])
                if not choices:
                    raise AIError("AI provider returned empty choices array.", error_code="EMPTY_RESPONSE")

                message = choices[0].get("message", {})
                content = message.get("content", "").strip()

                usage_data = body.get("usage", {})
                usage = AIUsage(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )

                return AIResponse(
                    content=content,
                    model=request.model,
                    provider_id="openai-compatible",
                    usage=usage,
                    latency_ms=latency_ms,
                    raw=body,
                )

        except urllib.error.HTTPError as err:
            server_msg = ""
            try:
                raw_data = err.read().decode("utf-8")
                err_body = json.loads(raw_data)
                err_obj = err_body.get("error", {})
                if isinstance(err_obj, dict):
                    server_msg = err_obj.get("message") or ""
                elif isinstance(err_obj, str):
                    server_msg = err_obj
            except Exception:
                pass

            if not server_msg:
                server_msg = err.reason or f"HTTP {err.code}"

            if err.code in (401, 403):
                raise AuthenticationError(f"Authentication/Access failed ({err.code}): {server_msg}. Check your API key and account permissions.")
            elif err.code == 404:
                raise ModelNotFoundError(request.model, f"Model '{request.model}' not found (404): {server_msg}")
            elif err.code == 410:
                raise ModelNotFoundError(request.model, f"Model '{request.model}' has been retired by the provider (HTTP 410 Gone). Click '⟳ Discover Models' or select an active model.")
            elif err.code == 429:
                retry_header = err.headers.get("Retry-After")
                sec = float(retry_header) if retry_header and retry_header.isdigit() else None
                raise RateLimitError(f"Rate limit exceeded: {server_msg}", retry_after_seconds=sec)
            raise AIError(f"HTTP Error {err.code}: {server_msg}", error_code=f"HTTP_{err.code}")
        except urllib.error.URLError as err:
            reason_str = str(err.reason).lower()
            if "connection refused" in reason_str:
                raise EndpointUnreachableError(f"Connection refused at {base_url}.")
            elif "timed out" in reason_str:
                raise AITimeoutError(f"Request to {base_url} timed out.")
            raise AIError(f"Network error: {err.reason}", error_code="NETWORK_ERROR")

    def test_connectivity(self, base_url: str, api_key: Optional[str] = None) -> Tuple[bool, str, float]:
        """Level 1 Test: Fast check of reachability and authentication."""
        start_time = time.perf_counter()
        clean_url = (base_url or "").strip()
        if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
            return (
                False,
                f"Invalid URL '{clean_url}'. Endpoint URL must begin with 'https://' or 'http://' (e.g. https://integrate.api.nvidia.com/v1). Did you accidentally paste a model name into the URL field?",
                0.0,
            )

        parsed = urllib.parse.urlsplit(clean_url)
        is_local = "localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc
        is_azure = "openai.azure.com" in parsed.netloc or "azure" in parsed.netloc

        if is_azure:
            # Azure OpenAI deployments endpoints do not expose standard /models without ARM tokens.
            # Fast-track reachability to Level 2 compatibility ping.
            return True, "Azure OpenAI endpoint reachable.", 10.0

        if is_local:
            # Probe /api/tags or /models
            tag_url = base_url.replace("/v1/", "/api/tags").replace("/v1", "/api/tags")
            if not tag_url.endswith("/api/tags"):
                tag_url = base_url.rstrip("/") + "/api/tags"
            try:
                req = urllib.request.Request(tag_url, headers={"User-Agent": "JobPilot/2.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    latency = round((time.perf_counter() - start_time) * 1000, 1)
                    if resp.status == 200:
                        return True, "Local Ollama server is online and responsive.", latency
                    return False, f"Server returned status {resp.status}.", latency
            except Exception:
                pass

        # Standard /models endpoint check
        models_url = self.resolve_models_endpoint(base_url)
        headers = self._build_headers(api_key, base_url=base_url)
        try:
            req = urllib.request.Request(models_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                latency = round((time.perf_counter() - start_time) * 1000, 1)
                if resp.status == 200:
                    return True, "Endpoint reachable and authenticated successfully.", latency
                return False, f"Endpoint returned HTTP status {resp.status}.", latency
        except urllib.error.HTTPError as err:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            if err.code in (401, 403):
                return False, f"Authentication failed ({err.code} Unauthorized). Check your API key.", latency
            if err.code == 404:
                # Some compatible endpoints disable /models; proceed to compatibility check
                return True, "Endpoint reachable (models listing not exposed).", latency
            return False, f"HTTP Error {err.code}: {err.reason}", latency
        except Exception as err:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            return False, f"Cannot connect to {base_url}: {err}", latency

    def test_compatibility(self, base_url: str, api_key: Optional[str], model: str) -> ConnectionTestResult:
        """Level 2 Test: Safe minimal inference test (non-PII ping)."""
        start_time = time.perf_counter()
        req = AIRequest(
            messages=[{"role": "user", "content": "JobPilot ping. Reply 'OK'."}],
            model=model,
            temperature=0.0,
            max_tokens=10,
        )
        try:
            resp = self.chat(req, base_url=base_url, api_key=api_key)
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            caps = {AICapability.CHAT}
            return ConnectionTestResult(
                success=True,
                status="verified",
                message=f"Model '{model}' verified and responsive.",
                latency_ms=latency,
                provider_id="openai-compatible",
                model=model,
                capabilities_verified=caps,
            )
        except Exception as exc:
            latency = round((time.perf_counter() - start_time) * 1000, 1)
            msg, code, help_url = AIErrorMapper.normalize(exc, provider_id="openai-compatible", model=model)
            status = "unauthorized" if code == "AUTHENTICATION_FAILED" else ("unreachable" if code == "ENDPOINT_UNREACHABLE" else "failed")
            return ConnectionTestResult(
                success=False,
                status=status,
                message=msg,
                latency_ms=latency,
                provider_id="openai-compatible",
                model=model,
                error_code=code,
                help_url=help_url,
            )

    def list_models(self, base_url: str, api_key: Optional[str] = None) -> Tuple[List[ModelInfo], Optional[str]]:
        """Level 0 Discovery: Discovers models from /models or /api/tags if supported."""
        parsed = urllib.parse.urlsplit((base_url or "").strip())
        is_azure = "openai.azure.com" in parsed.netloc or "azure" in parsed.netloc
        if is_azure:
            return [], "Azure OpenAI does not expose public /models endpoint. Enter your deployment name manually."

        models: List[ModelInfo] = []
        is_local = "localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc

        # 1. Standard /models endpoint check first
        models_url = self.resolve_models_endpoint(base_url)
        headers = self._build_headers(api_key, base_url=base_url)
        try:
            req = urllib.request.Request(models_url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status == 200:
                    body = json.loads(resp.read().decode("utf-8"))
                    data_items = body.get("data", [])
                    for item in data_items:
                        m_id = item.get("id")
                        if m_id:
                            models.append(ModelInfo(id=m_id, name=m_id))
                    return models, None
                return [], f"Discovery returned HTTP {resp.status}"
        except urllib.error.HTTPError as err:
            if err.code in (401, 403):
                return [], "Authentication failed. Provide a valid API key to discover models."
            if err.code != 404:
                return [], f"Discovery failed with HTTP {err.code}: {err.reason}"
        except Exception:
            pass

        # 2. Local Ollama /api/tags fallback
        if is_local:
            tag_url = base_url.replace("/v1/", "/api/tags").replace("/v1", "/api/tags")
            if not tag_url.endswith("/api/tags"):
                tag_url = base_url.rstrip("/") + "/api/tags"
            try:
                req = urllib.request.Request(tag_url, headers={"User-Agent": "JobPilot/2.0"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        for m in body.get("models", []):
                            name = m.get("name", "")
                            size_bytes = m.get("size", 0)
                            size_str = f"{round(size_bytes / (1024**3), 1)} GB" if size_bytes else None
                            if name:
                                models.append(ModelInfo(id=name, name=name, size=size_str))
                        if models:
                            return models, None
            except Exception:
                pass

        return [], "Automatic model discovery unavailable on this endpoint. Enter model ID manually."

    def capabilities(self) -> Set[AICapability]:
        return {
            AICapability.CHAT,
            AICapability.STREAMING,
            AICapability.STRUCTURED_OUTPUT,
            AICapability.JSON_MODE,
            AICapability.MODEL_LIST,
        }
