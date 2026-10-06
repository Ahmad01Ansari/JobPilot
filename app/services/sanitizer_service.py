"""Log and data sanitization filter preventing sensitive credential leakage."""

import logging
import re
from typing import Any, Dict, List, Tuple


class LogSanitizer:
    """Pre-persistence sanitization engine redacting sensitive credentials and tokens."""

    # Patterns matching known credential structures
    PATTERNS: List[Tuple[re.Pattern, str]] = [
        # OpenAI / DeepSeek / Anthropic / Groq / NVIDIA API keys
        (re.compile(r"sk-[A-Za-z0-9_-]{20,}"), "[REDACTED_API_KEY]"),
        (re.compile(r"gsk_[A-Za-z0-9_-]{20,}"), "[REDACTED_API_KEY]"),
        (re.compile(r"nvapi-[A-Za-z0-9_-]{20,}"), "[REDACTED_API_KEY]"),
        # Google Gemini API keys
        (re.compile(r"AIza[0-9A-Za-z-_]{30,}"), "[REDACTED_API_KEY]"),
        # GitHub personal access tokens
        (re.compile(r"(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}"), "[REDACTED_TOKEN]"),
        (re.compile(r"github_pat_[A-Za-z0-9_]{50,}"), "[REDACTED_TOKEN]"),
        # AWS Access Key IDs
        (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_KEY]"),
        # JWT authentication tokens
        (re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED_JWT]"),
        # Authorization Bearer tokens
        (re.compile(r"(?i)(Authorization:\s*Bearer\s+)[A-Za-z0-9._~+/-]+=*"), r"\1[REDACTED_TOKEN]"),
        (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{15,}=*"), r"\1[REDACTED_TOKEN]"),
        # Sensitive assignment patterns
        (
            re.compile(r"(?i)(password|passwd|pwd|client_secret|secret|api_key|apikey|access_token|refresh_token|private_key)\s*[:=]\s*['\"]?([^'\";\s,]+)['\"]?"),
            r"\1=[REDACTED]",
        ),
        # Platform session cookies
        (re.compile(r"(?i)(li_at|JSESSIONID|remember_token|sessionid|auth_token)=([^;\s]+)"), r"\1=[REDACTED_COOKIE]"),
        # URLs with embedded basic auth credentials (database URLs, HTTP proxies, SMTP)
        (re.compile(r"([a-zA-Z0-9+.-]+://[^:]+):([^@]+)@"), r"\1:[REDACTED]@"),
        # Encryption key assignments
        (
            re.compile(r"(?i)(fernet_key|encryption_key|master_key)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{43}=)['\"]?"),
            r"\1=[REDACTED_KEY]",
        ),
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Applies sanitization regex passes against string text."""
        if not text:
            return text
        sanitized = str(text)
        for pattern, replacement in cls.PATTERNS:
            sanitized = pattern.sub(replacement, sanitized)
        return sanitized

    @classmethod
    def sanitize_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deeply sanitizes string values and sensitive dictionary keys."""
        sensitive_keys = {
            "password", "passwd", "pwd", "secret", "client_secret",
            "api_key", "apikey", "access_token", "refresh_token",
            "token", "cookie", "cookies", "authorization",
        }
        sanitized_dict: Dict[str, Any] = {}
        for k, v in data.items():
            if str(k).lower() in sensitive_keys:
                sanitized_dict[k] = "[REDACTED]"
            elif isinstance(v, str):
                sanitized_dict[k] = cls.sanitize_text(v)
            elif isinstance(v, dict):
                sanitized_dict[k] = cls.sanitize_dict(v)
            elif isinstance(v, (list, tuple)):
                sanitized_dict[k] = [
                    cls.sanitize_dict(item) if isinstance(item, dict)
                    else (cls.sanitize_text(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                sanitized_dict[k] = v
        return sanitized_dict


class SanitizingLogFilter(logging.Filter):
    """Logging filter applied to handlers to scrub sensitive values before persistence."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = LogSanitizer.sanitize_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = LogSanitizer.sanitize_dict(record.args)
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    LogSanitizer.sanitize_text(str(v)) if isinstance(v, str) else v
                    for v in record.args
                )
        if record.exc_text:
            record.exc_text = LogSanitizer.sanitize_text(record.exc_text)
        return True


def install_root_sanitizer() -> None:
    """Attaches SanitizingLogFilter to root logging handlers and default logger hierarchy."""
    log_filter = SanitizingLogFilter()
    root_logger = logging.getLogger()
    # Check if filter already attached
    for f in root_logger.filters:
        if isinstance(f, SanitizingLogFilter):
            return
    root_logger.addFilter(log_filter)
    for handler in root_logger.handlers:
        handler.addFilter(log_filter)
