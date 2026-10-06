"""Typed exceptions and error normalization for JobPilot AI Services.

Translates low-level HTTP/network failures into user-friendly error guidance
without leaking raw technical exceptions or secrets into the UI.
"""

from typing import Optional, Tuple
import urllib.error


class AIError(Exception):
    """Base exception for all JobPilot AI errors."""
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", help_url: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.help_url = help_url


class AuthenticationError(AIError):
    """Raised when API credentials are rejected (HTTP 401/403)."""
    def __init__(self, message: str = "Authentication failed. Check your API key.", help_url: Optional[str] = None):
        super().__init__(message, error_code="AUTHENTICATION_FAILED", help_url=help_url)


class EndpointUnreachableError(AIError):
    """Raised when the server cannot be reached (DNS, connection refused, offline)."""
    def __init__(self, message: str = "Endpoint is unreachable. Ensure the server is running.", help_url: Optional[str] = None):
        super().__init__(message, error_code="ENDPOINT_UNREACHABLE", help_url=help_url)


class AITimeoutError(AIError):
    """Raised when the request times out."""
    def __init__(self, message: str = "AI request timed out.", help_url: Optional[str] = None):
        super().__init__(message, error_code="TIMEOUT", help_url=help_url)


class ModelNotFoundError(AIError):
    """Raised when the requested model is not found on the provider (HTTP 404)."""
    def __init__(self, model: str, message: Optional[str] = None, help_url: Optional[str] = None):
        msg = message or f"Model '{model}' was not found on this provider."
        super().__init__(msg, error_code="MODEL_NOT_FOUND", help_url=help_url)
        self.model = model


class RateLimitError(AIError):
    """Raised when rate limits are exceeded (HTTP 429)."""
    def __init__(self, message: str = "Provider rate limit reached.", retry_after_seconds: Optional[float] = None, help_url: Optional[str] = None):
        super().__init__(message, error_code="RATE_LIMITED", help_url=help_url)
        self.retry_after_seconds = retry_after_seconds


class QuotaExceededError(AIError):
    """Raised when account balance/quota is depleted."""
    def __init__(self, message: str = "Account quota or credits exceeded.", help_url: Optional[str] = None):
        super().__init__(message, error_code="QUOTA_EXCEEDED", help_url=help_url)


class UnsupportedFeatureError(AIError):
    """Raised when a model/provider lacks a requested capability."""
    def __init__(self, feature: str, message: Optional[str] = None, help_url: Optional[str] = None):
        msg = message or f"AI provider does not support feature: {feature}"
        super().__init__(msg, error_code="UNSUPPORTED_FEATURE", help_url=help_url)
        self.feature = feature


class SchemaValidationError(AIError):
    """Raised when model output fails JSON schema validation."""
    def __init__(self, message: str = "AI response failed JSON schema validation."):
        super().__init__(message, error_code="SCHEMA_VALIDATION_FAILED")


class AIErrorMapper:
    """Normalizes arbitrary exceptions into clean, user-facing error guidance."""

    @staticmethod
    def normalize(exc: Exception, provider_id: Optional[str] = None, model: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
        """Maps an exception to (user_message, error_code, help_url)."""
        prov_label = provider_id.capitalize() if provider_id else "Provider"

        if isinstance(exc, AIError):
            return exc.message, exc.error_code, exc.help_url

        if isinstance(exc, urllib.error.HTTPError):
            if exc.code in (401, 403):
                return (
                    f"Authentication failed ({exc.code}): Invalid or expired API key for {prov_label}.",
                    "AUTHENTICATION_FAILED",
                    None,
                )
            elif exc.code == 404:
                m_str = f" '{model}'" if model else ""
                return (
                    f"Model{m_str} or endpoint not found on {prov_label} (HTTP 404).",
                    "MODEL_NOT_FOUND",
                    None,
                )
            elif exc.code == 429:
                return (
                    f"Rate limit exceeded on {prov_label} (HTTP 429). Please wait before trying again.",
                    "RATE_LIMITED",
                    None,
                )
            elif exc.code >= 500:
                return (
                    f"{prov_label} service is currently unavailable (HTTP {exc.code}). Try again shortly.",
                    "PROVIDER_UNAVAILABLE",
                    None,
                )
            return f"{prov_label} returned HTTP Error {exc.code}: {exc.reason}", f"HTTP_{exc.code}", None

        if isinstance(exc, urllib.error.URLError):
            reason_str = str(exc.reason).lower()
            if "connection refused" in reason_str or "actively refused" in reason_str:
                if provider_id in ("ollama", "local"):
                    return (
                        "Cannot connect to local Ollama. Ensure 'ollama serve' is running.",
                        "ENDPOINT_UNREACHABLE",
                        "https://ollama.com",
                    )
                return (
                    f"Connection refused to {prov_label} endpoint. Check the URL and server status.",
                    "ENDPOINT_UNREACHABLE",
                    None,
                )
            elif "timed out" in reason_str:
                return f"Connection to {prov_label} timed out.", "TIMEOUT", None
            return f"Network error connecting to {prov_label}: {exc.reason}", "NETWORK_ERROR", None

        if isinstance(exc, TimeoutError):
            return f"Request to {prov_label} timed out.", "TIMEOUT", None

        return f"Unexpected {prov_label} error: {str(exc)}", "UNKNOWN_ERROR", None
