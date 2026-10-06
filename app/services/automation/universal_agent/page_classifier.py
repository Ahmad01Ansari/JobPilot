"""
Universal AI Application Agent — Page Classification & Health Checking
Identifies the semantic category and operational health of any browser page.
"""

from __future__ import annotations
import asyncio
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PageClass(Enum):
    APPLICATION_FORM = "APPLICATION_FORM"
    APPLICATION_REVIEW = "APPLICATION_REVIEW"
    APPLICATION_SUCCESS = "APPLICATION_SUCCESS"
    LOGIN = "LOGIN"
    CAPTCHA = "CAPTCHA"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"
    JOB_DETAIL = "JOB_DETAIL"
    COOKIE_CONSENT = "COOKIE_CONSENT"
    EXTERNAL_AUTH = "EXTERNAL_AUTH"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    TWO_FACTOR_AUTH = "TWO_FACTOR_AUTH"
    UNKNOWN = "UNKNOWN"


@dataclass
class PageHealthStatus:
    is_healthy: bool
    page_class: PageClass
    url: str
    title: str
    has_dom: bool = True
    is_blank: bool = False
    has_error_marker: bool = False
    error_message: Optional[str] = None
    input_count: int = 0
    button_count: int = 0


class PageClassifier:
    """Classifies web pages using multi-signal heuristics: URL, title, visible text, and DOM structure."""

    ERROR_PATTERNS = [
        r"404\s+not\s+found",
        r"500\s+internal\s+server\s+error",
        r"502\s+bad\s+gateway",
        r"503\s+service\s+unavailable",
        r"504\s+gateway\s+timeout",
        r"something\s+went\s+wrong",
        r"page\s+not\s+found",
        r"this\s+page\s+is\s+unavailable",
        r"site\s+maintenance",
    ]

    LOGIN_PATTERNS = [
        r"sign\s+in\s+to\s+apply",
        r"log\s*in\s+to\s+your\s+account",
        r"welcome\s+back",
        r"forgot\s+password",
        r"enter\s+your\s+credentials",
    ]

    OTP_PATTERNS = [
        r"enter\s+(?:the\s+)?(?:verification\s+)?code",
        r"we(?:'ve|\s+have)?\s+sent\s+(?:a\s+)?(?:verification\s+)?(?:code|passcode|pin|otp)",
        r"verification\s+code(?:\s+was\s+sent)?",
        r"confirm\s+your\s+identity",
        r"type\s+the\s+code\s+into\s+the\s+field",
        r"when\s+you\s+get\s+the\s+code",
        r"security\s+code",
        r"one-time\s+pass(?:code|word)",
        r"confirm\s+(?:your\s+)?(?:email|identity|phone)",
        r"check\s+your\s+email",
        r"enter\s+otp",
        r"pin-code",
    ]

    CAPTCHA_PATTERNS = [
        r"verify\s+you\s+are\s+human",
        r"cloudflare",
        r"security\s+check",
        r"please\s+complete\s+the\s+security\s+check",
        r"recaptcha",
        r"hcaptcha",
        r"turnstile",
    ]

    SUCCESS_PATTERNS = [
        r"application\s+submitted",
        r"thank\s+you\s+for\s+applying",
        r"your\s+application\s+has\s+been\s+received",
        r"we\s+have\s+received\s+your\s+application",
        r"application\s+complete",
    ]

    REVIEW_PATTERNS = [
        r"review\s+your\s+application",
        r"please\s+review",
        r"application\s+summary",
        r"confirm\s+and\s+submit",
    ]

    @classmethod
    def classify(
        cls,
        url: str,
        title: str,
        text_content: str = "",
        input_count: int = 0,
        has_file_input: bool = False,
    ) -> PageClass:
        """Determines the PageClass based on multiple signals."""
        combined_text = f"{url} {title} {text_content[:2000]}".lower()

        # 1. Error page check
        for pat in cls.ERROR_PATTERNS:
            if re.search(pat, combined_text):
                if "maintenance" in pat:
                    return PageClass.MAINTENANCE
                return PageClass.ERROR

        # 2. CAPTCHA / Security check
        for pat in cls.CAPTCHA_PATTERNS:
            if re.search(pat, combined_text):
                return PageClass.CAPTCHA

        # 3. Authentication / Login check
        if any(re.search(pat, combined_text) for pat in cls.LOGIN_PATTERNS):
            if input_count <= 3 and any(w in combined_text for w in ["password", "login", "sign-in"]):
                return PageClass.LOGIN

        # 3b. One-Time Verification Code (OTP) / Two-Factor Auth check
        if any(re.search(pat, combined_text) for pat in cls.OTP_PATTERNS):
            if (input_count <= 12 or "pin-code" in combined_text) and not has_file_input:
                return PageClass.TWO_FACTOR_AUTH

        # 4. Success confirmation check
        for pat in cls.SUCCESS_PATTERNS:
            if re.search(pat, combined_text):
                return PageClass.APPLICATION_SUCCESS

        # 5. Review step check
        for pat in cls.REVIEW_PATTERNS:
            if re.search(pat, combined_text):
                return PageClass.APPLICATION_REVIEW

        # 6. Document upload step check
        if has_file_input and input_count <= 3 and "upload" in combined_text:
            return PageClass.DOCUMENT_UPLOAD

        # 7. Application form check
        if input_count >= 3 or ("apply" in url.lower() and input_count >= 1):
            return PageClass.APPLICATION_FORM

        # 8. Job detail landing check
        if any(w in combined_text for w in ["apply now", "job description", "responsibilities", "qualifications"]):
            return PageClass.JOB_DETAIL

        return PageClass.UNKNOWN


class PageHealthChecker:
    """Evaluates page readiness, DOM availability, and checks for loading states or errors."""

    @staticmethod
    async def evaluate_health(agent: Any) -> PageHealthStatus:
        """Inspects the active page and returns a detailed PageHealthStatus."""
        js_probe = """(() => {
            const body = document.body;
            if (!body) return { has_dom: false, is_blank: true, text: "", input_count: 0, button_count: 0, title: document.title, url: window.location.href };
            const text = (body.innerText || "").trim();
            const inputs = document.querySelectorAll('input:not([type="hidden"]), select, textarea').length;
            const buttons = document.querySelectorAll('button, a[role="button"], input[type="submit"]').length;
            const hasFileInput = document.querySelectorAll('input[type="file"]').length > 0;
            return {
                has_dom: true,
                is_blank: text.length === 0 && inputs === 0,
                text: text.slice(0, 3000),
                input_count: inputs,
                button_count: buttons,
                has_file_input: hasFileInput,
                title: document.title,
                url: window.location.href,
            };
        })()"""
        try:
            res = agent.evaluate(js_probe)
            if asyncio.iscoroutine(res):
                probe_data = await res
            else:
                probe_data = res
        except Exception as e:
            return PageHealthStatus(
                is_healthy=False,
                page_class=PageClass.ERROR,
                url="",
                title="",
                has_dom=False,
                is_blank=True,
                has_error_marker=True,
                error_message=f"Browser evaluation failed: {e}",
            )

        if not isinstance(probe_data, dict):
            return PageHealthStatus(
                is_healthy=True,
                page_class=PageClass.APPLICATION_FORM,
                url="",
                title="",
                has_dom=True,
                is_blank=False,
            )

        url = str(probe_data.get("url", "") or "")
        title = str(probe_data.get("title", "") or "")
        text = str(probe_data.get("text", "") or "")
        try:
            inputs = int(probe_data.get("input_count", 0))
        except (TypeError, ValueError):
            inputs = 0
        try:
            buttons = int(probe_data.get("button_count", 0))
        except (TypeError, ValueError):
            buttons = 0
        has_file = bool(probe_data.get("has_file_input", False))
        is_blank = bool(probe_data.get("is_blank", False))

        page_class = PageClassifier.classify(
            url=url,
            title=title,
            text_content=text,
            input_count=inputs,
            has_file_input=has_file,
        )

        is_error = page_class in (PageClass.ERROR, PageClass.MAINTENANCE) or is_blank
        err_msg = f"Page classified as {page_class.value}" if is_error else None

        return PageHealthStatus(
            is_healthy=not is_error,
            page_class=page_class,
            url=url,
            title=title,
            has_dom=probe_data.get("has_dom", True),
            is_blank=is_blank,
            has_error_marker=is_error,
            error_message=err_msg,
            input_count=inputs,
            button_count=buttons,
        )

    @staticmethod
    async def wait_for_page_ready(agent: Any, timeout: float = 12.0) -> bool:
        """Condition-based waiting for DOM completion and spinner/loader dismissal."""
        start_time = asyncio.get_event_loop().time()
        js_ready_check = """(() => {
            if (document.readyState !== 'complete' && document.readyState !== 'interactive') {
                return false;
            }
            // Check for full-page blocking loaders / spinners
            const loaders = document.querySelectorAll(
                '.loading, .spinner, .loader, [aria-busy="true"], .page-loader, #loading-overlay'
            );
            for (const el of loaders) {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 50 && rect.height > 50 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                    return false;
                }
            }
            return true;
        })()"""
        while (asyncio.get_event_loop().time() - start_time) < timeout:
            try:
                res = agent.evaluate(js_ready_check)
                if asyncio.iscoroutine(res):
                    ready = await res
                else:
                    ready = res
                if ready:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.3)
        return False
