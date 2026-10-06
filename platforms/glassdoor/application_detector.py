"""
Glassdoor Application Detector & Boundary Router
Identifies the application flow method from the active Glassdoor details pane:
- DIRECT_PLATFORM_APPLY: Native Glassdoor modal dialog.
- SMART_APPLY_WINDOW: Indeed Smart Apply SPA (smartapply.indeed.com) in child window/tab.
- EXTERNAL_APPLICATION: External ATS / career portal (Greenhouse, Lever, Workday) for Universal Agent handoff.
- LOGIN_REQUIRED: Authentication wall.
- CAPTCHA_REQUIRED: Security challenge blocking application.
- UNKNOWN: Ambiguous CTA requiring manual intervention.
"""

from __future__ import annotations
import logging
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass
from selenium.webdriver.common.by import By

from platforms.glassdoor.selectors import (
    APPLY_EASY_TRIGGERS,
    APPLY_EXTERNAL_TRIGGERS,
    APPLY_ALREADY_BADGES,
)
from modules.helpers import print_lg

logger = logging.getLogger(__name__)


class ApplicationMethod(Enum):
    DIRECT_PLATFORM_APPLY = "DIRECT_PLATFORM_APPLY"
    SMART_APPLY_WINDOW = "SMART_APPLY_WINDOW"
    EXTERNAL_APPLICATION = "EXTERNAL_APPLICATION"
    ALREADY_APPLIED = "ALREADY_APPLIED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    CAPTCHA_REQUIRED = "CAPTCHA_REQUIRED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ApplicationFlowContext:
    method: ApplicationMethod
    trigger_element: Optional[Any] = None
    target_url: Optional[str] = None
    button_text: str = ""
    is_easy_apply: bool = False
    requires_new_tab: bool = False
    confidence: float = 0.8
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


class GlassdoorApplicationDetector:
    """Discovers application actions semantically within the active job details panel."""

    @classmethod
    def detect_flow(cls, driver: Any) -> ApplicationFlowContext:
        """Inspects the active job details panel and classifies the application flow."""
        if not driver:
            return ApplicationFlowContext(method=ApplicationMethod.UNKNOWN, confidence=0.0)

        # 1. Check Already Applied indicators
        for sel in APPLY_ALREADY_BADGES:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        return ApplicationFlowContext(
                            method=ApplicationMethod.ALREADY_APPLIED,
                            button_text=el.text.strip(),
                            confidence=0.95,
                        )
            except Exception:
                continue

        # 2. Check Easy Apply triggers
        for sel in APPLY_EASY_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed() and el.is_enabled():
                        btn_txt = (el.text or "").strip()
                        return ApplicationFlowContext(
                            method=ApplicationMethod.DIRECT_PLATFORM_APPLY,
                            trigger_element=el,
                            button_text=btn_txt,
                            is_easy_apply=True,
                            confidence=0.9,
                        )
            except Exception:
                continue

        # 3. Dynamic JS inspection for Easy Apply button
        try:
            js_res = driver.execute_script('''
                var btns = Array.from(document.querySelectorAll(
                    "button[data-test='easyApply'], button[data-test*='easy-apply'], button[data-test*='easyApply'], " +
                    "button, a[role='button']"
                ));
                for (var b of btns) {
                    var txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                    var dt = (b.getAttribute('data-test') || '').toLowerCase();
                    if ((txt.includes('easy apply') || dt === 'easyapply') && b.offsetWidth > 0 && b.offsetHeight > 0) {
                        return { text: b.innerText.trim(), isEasy: true };
                    }
                }
                return null;
            ''')
            if js_res and isinstance(js_res, dict) and js_res.get("isEasy"):
                # Query actual element for reference
                el = driver.find_element(By.CSS_SELECTOR, "button[data-test='easyApply'], button[class*='easyApply']")
                return ApplicationFlowContext(
                    method=ApplicationMethod.DIRECT_PLATFORM_APPLY,
                    trigger_element=el,
                    button_text=js_res.get("text", "Easy Apply"),
                    is_easy_apply=True,
                    confidence=0.95,
                )
        except Exception:
            pass

        # 4. Check External Company Site Apply
        for sel in APPLY_EXTERNAL_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        href = el.get_attribute("href") or ""
                        btn_txt = (el.text or "").strip()
                        return ApplicationFlowContext(
                            method=ApplicationMethod.EXTERNAL_APPLICATION,
                            trigger_element=el,
                            target_url=href,
                            button_text=btn_txt,
                            is_easy_apply=False,
                            requires_new_tab=True,
                            confidence=0.85,
                        )
            except Exception:
                continue

        return ApplicationFlowContext(
            method=ApplicationMethod.UNKNOWN,
            confidence=0.2,
        )
