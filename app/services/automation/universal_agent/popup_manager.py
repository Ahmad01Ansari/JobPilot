"""
Universal AI Application Agent — Global Popup & Modal Handler
Detects, classifies, and safely resolves unexpected overlays, banners, and modals.
"""

from __future__ import annotations
import asyncio
import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PopupClassification(Enum):
    BENIGN = "BENIGN"
    ACTIONABLE = "ACTIONABLE"
    AUTHENTICATION = "AUTHENTICATION"
    SECURITY = "SECURITY"
    DESTRUCTIVE = "DESTRUCTIVE"
    UNKNOWN = "UNKNOWN"


@dataclass
class DetectedPopup:
    element_selector: str
    text_content: str
    classification: PopupClassification
    dismiss_button_selector: Optional[str] = None
    title: str = ""


class PopupManager:
    """Detects and safely handles modal popups, cookie consent banners, and promotional overlays."""

    # Selectors for common cookie, consent, and location modal containers
    CONSENT_SELECTORS = [
        "#onetrust-banner-sdk",
        ".onetrust-pc-dark-filter",
        "#cookie-law-info-bar",
        ".cc-window",
        "#CybotCookiebotDialog",
        ".cookie-banner",
        ".consent-banner",
        "oj-dialog",
        "[data-oj-binding-provider]",
        "[class*='location-modal']",
        "[id*='location-modal']",
        "[class*='location-prompt']",
        "[id*='location-prompt']",
        "[id*='cookie']",
        "[class*='cookie-consent']",
        "[aria-label*='cookie' i]",
        "[aria-label*='location' i]",
    ]

    # Safe dismiss button text patterns for benign banners and location prompts
    BENIGN_DISMISS_PATTERNS = [
        r"^(accept all|accept cookies|agree|i agree|got it|allow all|allow|accept|close|dismiss|ok|okay|understood|proceed|use current location)$",
        r"^(no thanks|not now|maybe later|don't allow|dont allow|block|reject all|reject|decline|deny|never|skip|cancel|continue without location)$",
    ]

    DESTRUCTIVE_PATTERNS = [
        r"(delete|discard|cancel application|withdraw|terminate|remove all)",
    ]

    AUTH_PATTERNS = [
        r"(sign in|log in|session expired|enter your password|create an account to continue)",
    ]

    CAPTCHA_PATTERNS = [
        r"(verify you are human|security check|cloudflare|turnstile|recaptcha)",
    ]

    @classmethod
    async def scan_and_dismiss_popups(cls, agent: Any) -> Tuple[bool, Optional[DetectedPopup]]:
        """Scans for visible modal overlays, cookie banners, location/notification popups anywhere on page and dismisses benign ones safely."""
        js_scan = """(() => {
            const candidateOverlays = Array.from(document.querySelectorAll(
                'dialog[open], [role="dialog"], [role="alertdialog"], .modal.show, .modal.is-active, #onetrust-banner-sdk, .cc-window, .cookie-banner, .popup-overlay, [class*="cookie"], [id*="cookie"], [class*="consent"], [id*="consent"], [aria-label*="cookie" i], [aria-label*="consent" i]'
            ));

            // Also check fixed or sticky elements at top/bottom/center
            const fixedElements = Array.from(document.querySelectorAll('div, section, aside')).filter(el => {
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                const pos = style.position;
                if (pos === 'fixed' || pos === 'sticky') {
                    const z = parseInt(style.zIndex, 10);
                    const rect = el.getBoundingClientRect();
                    if ((z >= 40 || isNaN(z)) && rect.width > 200 && rect.height > 30) {
                        const lower = (el.innerText || '').toLowerCase();
                        if (lower.includes('cookie') || lower.includes('consent') || lower.includes('notification') || lower.includes('location') || lower.includes('subscribe') || lower.includes('privacy') || lower.includes('we use cookies')) {
                            return true;
                        }
                    }
                }
                return false;
            });

            const allOverlays = [...candidateOverlays, ...fixedElements].filter(el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 80 && rect.height > 30 && style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
            });

            if (allOverlays.length === 0) return null;

            const target = allOverlays[0];
            const text = (target.innerText || "").slice(0, 1000);
            
            // Look for buttons inside the overlay
            const buttons = Array.from(target.querySelectorAll('button, a[role="button"], input[type="button"], input[type="submit"], .close, [aria-label*="close" i], [aria-label*="dismiss" i]'))
                .filter(b => {
                    const r = b.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                })
                .map((b, idx) => ({
                    idx,
                    text: (b.innerText || b.getAttribute('aria-label') || b.getAttribute('title') || b.value || "").trim(),
                    tag: b.tagName.toLowerCase(),
                    id: b.id || "",
                    className: b.className || "",
                }));

            // Mark unique target identifier
            if (!target.id && !target.dataset.jobpilotPopup) {
                target.dataset.jobpilotPopup = "active";
            }

            return {
                text: text,
                buttons: buttons,
                tagName: target.tagName.toLowerCase(),
                id: target.id || "",
                className: target.className || "",
            };
        })()"""

        try:
            res = agent.evaluate(js_scan)
            if asyncio.iscoroutine(res):
                data = await res
            else:
                data = res
        except Exception:
            return False, None

        if not data or not isinstance(data, dict):
            return False, None

        popup_text = str(data.get("text", "") or "")
        raw_buttons = data.get("buttons", [])
        buttons = raw_buttons if isinstance(raw_buttons, list) else []

        classification = cls.classify_popup(popup_text)

        # Handle BENIGN popups (Cookie banners, newsletters, location/notification permission requests)
        if classification == PopupClassification.BENIGN:
            dismiss_btn = cls._find_safe_dismiss_button(buttons)
            if dismiss_btn:
                btn_idx = dismiss_btn.get("idx", 0)
                logger.info("Dismissing benign popup: '%s' via button '%s'", popup_text[:60], dismiss_btn.get("text"))
                js_click_btn = f"""(() => {{
                    const target = document.querySelector('[data-jobpilot-popup="active"]') || document.querySelector(
                        'dialog[open], [role="dialog"], [role="alertdialog"], .modal.show, .modal.is-active, #onetrust-banner-sdk, .cc-window, .cookie-banner, .popup-overlay'
                    );
                    if (!target) return false;
                    const btns = Array.from(target.querySelectorAll('button, a[role="button"], input[type="button"], input[type="submit"], .close, [aria-label*="close" i], [aria-label*="dismiss" i]'))
                        .filter(b => b.getBoundingClientRect().width > 0);
                    if (btns[{btn_idx}]) {{
                        btns[{btn_idx}].click();
                        return true;
                    }}
                    return false;
                }})()"""
                try:
                    c_res = agent.evaluate(js_click_btn)
                    if asyncio.iscoroutine(c_res):
                        await c_res
                    await asyncio.sleep(0.5)
                    return True, DetectedPopup(
                        element_selector=data.get("id") or data.get("className") or "overlay",
                        text_content=popup_text,
                        classification=classification,
                        dismiss_button_selector=dismiss_btn.get("text"),
                    )
                except Exception as e:
                    logger.warning("Failed to click popup dismiss button: %s", e)

        detected = DetectedPopup(
            element_selector=data.get("id") or data.get("className") or "overlay",
            text_content=popup_text,
            classification=classification,
        )
        return False, detected

    @classmethod
    def classify_popup(cls, text: str) -> PopupClassification:
        """Classifies the popup based on its text content."""
        lower_text = text.lower()

        # Check for CAPTCHA / Security first
        for pat in cls.CAPTCHA_PATTERNS:
            if re.search(pat, lower_text):
                return PopupClassification.SECURITY

        # Check for Login / Session expired
        for pat in cls.AUTH_PATTERNS:
            if re.search(pat, lower_text):
                return PopupClassification.AUTHENTICATION

        # Check for Destructive warnings (discard application, delete data)
        for pat in cls.DESTRUCTIVE_PATTERNS:
            if re.search(pat, lower_text):
                return PopupClassification.DESTRUCTIVE

        # Check for Cookie consent / Newsletters / Benign notices / Notifications / Location requests
        if any(w in lower_text for w in [
            "cookie", "cookies", "privacy policy", "consent", "newsletter",
            "stay updated", "subscribe", "notification", "notifications",
            "location", "job alert", "job alerts", "allow access"
        ]):
            return PopupClassification.BENIGN

        # Actionable job application warning (e.g. duplicate application warning)
        if any(w in lower_text for w in ["already applied", "warning", "attention", "resume replace"]):
            return PopupClassification.ACTIONABLE

        return PopupClassification.UNKNOWN

    @classmethod
    def _find_safe_dismiss_button(cls, buttons: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Identifies a benign dismiss button from the detected button list."""
        for b in buttons:
            btn_text = b.get("text", "").strip().lower()
            for pat in cls.BENIGN_DISMISS_PATTERNS:
                if re.match(pat, btn_text, re.IGNORECASE):
                    return b

        # Fallback to close icons or X buttons
        for b in buttons:
            btn_text = b.get("text", "").strip().lower()
            if btn_text in ["x", "×", "✕", "close", "dismiss"]:
                return b
        return None
