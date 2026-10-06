"""
Universal AI Application Agent — Centralized Recovery Engine
Provides structured failure classification, retry policies, and diagnostic persistence.
"""

from __future__ import annotations
import os
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FailureCategory(Enum):
    TRANSIENT = "TRANSIENT"
    PAGE_STATE_CHANGED = "PAGE_STATE_CHANGED"
    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_NOT_INTERACTABLE = "ELEMENT_NOT_INTERACTABLE"
    NAVIGATION_FAILURE = "NAVIGATION_FAILURE"
    SESSION_FAILURE = "SESSION_FAILURE"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    UNKNOWN_PAGE = "UNKNOWN_PAGE"
    BROWSER_ERROR = "BROWSER_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    UNSUPPORTED_COMPONENT = "UNSUPPORTED_COMPONENT"
    USER_INTERVENTION_REQUIRED = "USER_INTERVENTION_REQUIRED"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"


@dataclass
class FailureReport:
    operation: str
    current_url: str
    page_title: str
    current_state: str
    category: FailureCategory
    exception_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    recovery_action: str = ""
    recovery_result: str = ""
    screenshot_path: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    job_id: Optional[str] = None
    is_retryable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation": self.operation,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "current_state": self.current_state,
            "category": self.category.value,
            "exception_message": self.exception_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "recovery_action": self.recovery_action,
            "recovery_result": self.recovery_result,
            "screenshot_path": self.screenshot_path,
            "timestamp": self.timestamp,
            "job_id": self.job_id,
            "is_retryable": self.is_retryable,
        }


class RecoveryManager:
    """Centralized manager for classifying failures, enforcing retry limits, and managing recovery strategies."""

    # Maximum permitted retries per failure category
    RETRY_BUDGETS: Dict[FailureCategory, int] = {
        FailureCategory.TRANSIENT: 3,
        FailureCategory.NETWORK_ERROR: 2,
        FailureCategory.ELEMENT_NOT_FOUND: 2,
        FailureCategory.ELEMENT_NOT_INTERACTABLE: 2,
        FailureCategory.PAGE_STATE_CHANGED: 2,
        FailureCategory.VALIDATION_ERROR: 1,
        FailureCategory.NAVIGATION_FAILURE: 1,
        FailureCategory.UNKNOWN_PAGE: 1,
        # Strictly non-retryable without human intervention
        FailureCategory.AUTH_REQUIRED: 0,
        FailureCategory.CAPTCHA_REQUIRED: 0,
        FailureCategory.RATE_LIMITED: 0,
        FailureCategory.SAFETY_BLOCK: 0,
        FailureCategory.UNSUPPORTED_COMPONENT: 0,
        FailureCategory.USER_INTERVENTION_REQUIRED: 0,
        FailureCategory.TERMINAL_FAILURE: 0,
    }

    def __init__(self, run_id: Optional[str] = None, artifacts_dir: Optional[str] = None) -> None:
        self.run_id = run_id or f"run_{int(time.time())}"
        self.artifacts_dir = artifacts_dir or os.path.join("debug", "runs", self.run_id)
        os.makedirs(self.artifacts_dir, exist_ok=True)
        self._retry_counts: Dict[str, int] = {}
        self.history: list[FailureReport] = []

    def classify_exception(self, exc: Exception, context_hint: str = "") -> FailureCategory:
        """Classifies an arbitrary exception into a standard FailureCategory."""
        msg = (str(exc) + " " + context_hint).lower()

        if any(w in msg for w in ["captcha", "turnstile", "recaptcha", "hcaptcha", "human verification", "cloudflare"]):
            return FailureCategory.CAPTCHA_REQUIRED

        if any(w in msg for w in ["login", "sign in", "unauthorized", "session expired", "auth_required", "401", "403"]):
            return FailureCategory.AUTH_REQUIRED

        if any(w in msg for w in ["rate limit", "too many requests", "429"]):
            return FailureCategory.RATE_LIMITED

        if any(w in msg for w in ["validation", "aria-invalid", "invalid email", "required field"]):
            return FailureCategory.VALIDATION_ERROR

        if any(w in msg for w in ["target closed", "browser has been closed", "browser closed", "browser disconnected", "connection closed", "broken pipe", "session closed", "target page"]):
            return FailureCategory.BROWSER_ERROR

        if any(w in msg for w in ["net::err", "network", "dns", "econnrefused", "etimedout", "socket"]):
            return FailureCategory.NETWORK_ERROR

        if any(w in msg for w in ["obscures it", "not visible", "not interactable", "pointer-events: none"]):
            return FailureCategory.ELEMENT_NOT_INTERACTABLE

        if any(w in msg for w in ["cannot find element", "waiting for selector", "not found", "no such element"]):
            return FailureCategory.ELEMENT_NOT_FOUND

        if any(w in msg for w in ["stale element", "execution context was destroyed", "navigated away", "detached"]):
            return FailureCategory.PAGE_STATE_CHANGED

        if any(w in msg for w in ["timeout", "timed out", "navigation timeout"]):
            return FailureCategory.TRANSIENT

        return FailureCategory.TRANSIENT

    def can_retry(self, operation_key: str, category: FailureCategory) -> bool:
        """Checks if the operation has remaining retry budget for this category."""
        current_retries = self._retry_counts.get(operation_key, 0)
        max_allowed = self.RETRY_BUDGETS.get(category, 0)
        return current_retries < max_allowed

    def record_attempt(
        self,
        operation_key: str,
        category: FailureCategory,
        url: str = "",
        title: str = "",
        state: str = "",
        exc: Optional[Exception] = None,
        recovery_action: str = "",
        screenshot_path: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> FailureReport:
        """Records a failure attempt and increments its operation retry count."""
        current_retries = self._retry_counts.get(operation_key, 0)
        self._retry_counts[operation_key] = current_retries + 1
        max_allowed = self.RETRY_BUDGETS.get(category, 0)
        is_retryable = (current_retries + 1) <= max_allowed

        report = FailureReport(
            operation=operation_key,
            current_url=self.sanitize_url(url),
            page_title=title,
            current_state=state,
            category=category,
            exception_message=str(exc) if exc else None,
            retry_count=current_retries + 1,
            max_retries=max_allowed,
            recovery_action=recovery_action,
            screenshot_path=screenshot_path,
            job_id=job_id,
            is_retryable=is_retryable,
        )
        self.history.append(report)
        logger.warning(
            "Failure recorded [%s] in op '%s' (Attempt %d/%d, Retryable: %s): %s",
            category.value,
            operation_key,
            report.retry_count,
            max_allowed,
            is_retryable,
            report.exception_message or "N/A",
        )
        return report

    def reset_budget(self, operation_key: str) -> None:
        """Resets the retry counter for a successfully recovered operation."""
        self._retry_counts.pop(operation_key, None)

    @staticmethod
    def sanitize_url(url: str) -> str:
        """Strips query parameters containing sensitive tokens or passwords."""
        if not url:
            return ""
        if "?" not in url:
            return url
        base, query = url.split("?", 1)
        params = query.split("&")
        safe_params = []
        for p in params:
            if "=" in p:
                k, v = p.split("=", 1)
                if any(sec in k.lower() for sec in ["token", "key", "secret", "auth", "pwd", "password"]):
                    safe_params.append(f"{k}=REDACTED")
                else:
                    safe_params.append(p)
            else:
                safe_params.append(p)
        return f"{base}?{'&'.join(safe_params)}"
