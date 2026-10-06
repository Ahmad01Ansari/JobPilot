'''
Indeed CAPTCHA & Security Challenge Handler
Detects Google reCAPTCHA, Cloudflare Turnstile, and other anti-bot challenges on Indeed.
Provides automated detection, user intervention alerting via Desktop UI / logs,
and cooperative polling for manual resolution without violating anti-bypass rules.
'''

import time
from typing import Optional, Any, Callable
from selenium.webdriver.common.by import By

from modules.helpers import print_lg
from platforms.indeed.selectors import (
    CAPTCHA_IFRAME_SELECTORS,
    CAPTCHA_CONTAINER_SELECTORS,
    CAPTCHA_RESPONSE_INPUTS,
)


class IndeedCaptchaHandler:
    """Handles detection and cooperative manual resolution of CAPTCHAs on Indeed."""

    def __init__(self, browser: Optional[Any] = None, automation_bridge: Optional[Any] = None):
        self.browser = browser
        self.automation_bridge = automation_bridge

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def is_captcha_present(self, driver: Optional[Any] = None) -> bool:
        """Checks if an active, visible CAPTCHA or security verification challenge is present on the page.
        Distinguishes genuine blocking challenges (checkboxes, image tiles, Cloudflare) from background reCAPTCHA v3 telemetry scripts.
        """
        drv = driver or self.driver
        if not drv:
            return False

        try:
            # 1. Execute strict visibility check in JavaScript
            is_present = drv.execute_script("""
                function isVisible(el) {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity || '1') === 0) {
                        return false;
                    }
                    const p = el.parentElement ? window.getComputedStyle(el.parentElement) : null;
                    if (p && (p.display === 'none' || p.visibility === 'hidden')) {
                        return false;
                    }
                    const rect = el.getBoundingClientRect();
                    return rect.width >= 30 && rect.height >= 20;
                }

                // A. Visible interactive checkbox anchor (recaptcha.net or google.com)
                // MUST NOT be inside invisible reCAPTCHA badge (.grecaptcha-badge)
                const anchors = document.querySelectorAll("iframe[src*='anchor'], iframe[src*='recaptcha']:not([src*='bframe'])");
                for (let i = 0; i < anchors.length; i++) {
                    const a = anchors[i];
                    if (a.closest && a.closest('.grecaptcha-badge')) {
                        continue;
                    }
                    if (a.parentElement && (a.parentElement.className || '').toString().includes('grecaptcha-badge')) {
                        continue;
                    }
                    const src = (a.src || "").toLowerCase();
                    if (src.includes("size=invisible") || src.includes("badge=bottomright") || src.includes("badge=inline")) {
                        continue;
                    }
                    if (isVisible(a)) {
                        const rect = a.getBoundingClientRect();
                        if (rect.top >= 0 && rect.top <= window.innerHeight && rect.width >= 150 && rect.height >= 50) {
                            return true;
                        }
                    }
                }

                // B. Google reCAPTCHA v2 / Enterprise interactive image challenge popup (bframe)
                const bframes = document.querySelectorAll("iframe[src*='bframe']");
                for (let i = 0; i < bframes.length; i++) {
                    const b = bframes[i];
                    const rect = b.getBoundingClientRect();
                    const style = window.getComputedStyle(b);
                    const parentStyle = b.parentElement ? window.getComputedStyle(b.parentElement) : null;
                    if (style.visibility !== 'hidden' && style.display !== 'none' && parseFloat(style.opacity || '1') > 0 &&
                        (!parentStyle || (parentStyle.visibility !== 'hidden' && parentStyle.display !== 'none')) &&
                        rect.top >= 0 && rect.width >= 250 && rect.height >= 250) {
                        return true;
                    }
                }

                // C. Cloudflare Turnstile / Challenge iframe (must be visible and in viewport)
                const turnstiles = document.querySelectorAll("iframe[src*='challenges.cloudflare.com']");
                for (let i = 0; i < turnstiles.length; i++) {
                    const t = turnstiles[i];
                    const rect = t.getBoundingClientRect();
                    const style = window.getComputedStyle(t);
                    if (style.visibility !== 'hidden' && style.display !== 'none' && rect.top >= 0 && rect.top <= window.innerHeight && rect.width >= 100 && rect.height >= 40) {
                        return true;
                    }
                }

                // D. Cloudflare under-attack full page challenge
                const cfStages = document.querySelectorAll("#challenge-stage, #challenge-running");
                for (let i = 0; i < cfStages.length; i++) {
                    const el = cfStages[i];
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (style.visibility !== 'hidden' && style.display !== 'none' && rect.width >= 100 && rect.height >= 50) {
                        return true;
                    }
                }

                // E. Active challenge heading or banner on dedicated security check page
                // Only consider if there are NO active application inputs on the page
                const appInputs = document.querySelectorAll("input:not([type='hidden']), textarea, select, button[type='submit']");
                let visibleAppInputs = 0;
                for (let i = 0; i < appInputs.length; i++) {
                    if (isVisible(appInputs[i])) visibleAppInputs++;
                }

                if (visibleAppInputs === 0) {
                    const headings = document.querySelectorAll("h1, h2, .challenge-title");
                    for (let i = 0; i < headings.length; i++) {
                        if (isVisible(headings[i])) {
                            const txt = (headings[i].innerText || "").toLowerCase();
                            if (txt.includes("verify you are human") || txt.includes("complete the security check") || txt.includes("solve this challenge")) {
                                return true;
                            }
                        }
                    }
                }

                return false;
            """)
            if is_present:
                return True
        except Exception:
            pass

        # 2. Fallback check via Selenium By.CSS_SELECTOR on visible interactive challenge elements only
        for sel in [
            "iframe[src*='anchor']:not([src*='size=invisible'])",
            "iframe[src*='recaptcha/api2/bframe']",
            "iframe[src*='recaptcha/enterprise/bframe']",
            "iframe[src*='bframe']",
        ]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    parent_cls = ""
                    try:
                        parent_cls = (el.find_element(By.XPATH, "..").get_attribute("class") or "").lower()
                    except Exception:
                        pass
                    if "grecaptcha-badge" in parent_cls:
                        continue
                    loc = el.location
                    sz = el.size
                    if el.is_displayed() and sz.get("width", 0) >= 150 and sz.get("height", 0) >= 50 and loc.get("y", -1) >= 0:
                        return True
            except Exception:
                continue

        for sel in ["#challenge-stage", "#challenge-running"]:
            try:
                for el in drv.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed() and el.size.get("width", 0) >= 100:
                        return True
            except Exception:
                continue

        return False

    def is_captcha_solved(self, driver: Optional[Any] = None) -> bool:
        """Checks if the CAPTCHA response has been populated or verified in the browser DOM."""
        drv = driver or self.driver
        if not drv:
            return False

        # If no active visible challenge is present, it is not blocking
        if not self.is_captcha_present(drv):
            return True

        try:
            solved = drv.execute_script("""
                // A. If an active image challenge tile popup (bframe) is open and visible, definitely NOT solved
                const bframes = document.querySelectorAll("iframe[src*='bframe']");
                for (let i = 0; i < bframes.length; i++) {
                    const b = bframes[i];
                    const s = window.getComputedStyle(b);
                    const p = b.parentElement ? window.getComputedStyle(b.parentElement) : null;
                    if (s.visibility !== 'hidden' && s.display !== 'none' && (!p || p.visibility !== 'hidden')) {
                        const rect = b.getBoundingClientRect();
                        if (rect.top >= 0 && rect.width >= 250 && rect.height >= 250) {
                            return false;
                        }
                    }
                }

                // B. Check if a visible interactive checkbox anchor exists (excluding invisible badges)
                const anchors = document.querySelectorAll("iframe[src*='anchor']:not([src*='size=invisible'])");
                let hasVisibleAnchor = false;
                for (let i = 0; i < anchors.length; i++) {
                    const a = anchors[i];
                    if (a.closest && a.closest('.grecaptcha-badge')) continue;
                    if (a.parentElement && (a.parentElement.className || '').toString().includes('grecaptcha-badge')) continue;
                    const rect = a.getBoundingClientRect();
                    const s = window.getComputedStyle(a);
                    if (s.visibility !== 'hidden' && s.display !== 'none' && rect.top >= 0 && rect.top <= window.innerHeight && rect.width >= 150 && rect.height >= 50) {
                        hasVisibleAnchor = true;
                        break;
                    }
                }

                // C. Cloudflare Turnstile token check
                const cfIframe = document.querySelector("iframe[src*='challenges.cloudflare.com']");
                if (cfIframe) {
                    const cfInput = document.querySelector("input[name='cf-turnstile-response']");
                    if (cfInput && (cfInput.value || "").trim().length > 20) {
                        return true;
                    }
                    return false;
                }

                // D. If a visible interactive anchor was found, verify response token
                if (hasVisibleAnchor) {
                    const primary = document.getElementById("g-recaptcha-response");
                    if (primary && (primary.value || "").trim().length > 20) {
                        return true;
                    }
                    return false;
                }

                // If no active bframe and no active visible anchor, it is not blocking
                return true;
            """)
            if solved is False:
                return False
            if solved is True:
                return True
        except Exception:
            pass

        # Fallback check on primary response input via Selenium
        try:
            primary = drv.find_element(By.ID, "g-recaptcha-response")
            val = (primary.get_attribute("value") or "").strip()
            if len(val) >= 20:
                return True
        except Exception:
            pass

        return True

    def handle_captcha(
        self,
        driver: Optional[Any] = None,
        job_title: str = "",
        company: str = "",
        timeout: int = 60,
        stop_check: Optional[Callable[[], bool]] = None,
        automation_bridge: Optional[Any] = None,
    ) -> bool:
        """Alerts user and cooperatively awaits manual CAPTCHA completion in open browser."""
        drv = driver or self.driver
        if not drv:
            return False

        if not self.is_captcha_present(drv):
            return True

        if self.is_captcha_solved(drv):
            return True

        print_lg("\n" + "=" * 70)
        print_lg("[IndeedCaptchaHandler] ⚠️  CAPTCHA CHALLENGE DETECTED ON INDEED!")
        print_lg(f"[IndeedCaptchaHandler] Job: '{job_title}' | Company: '{company}'")
        print_lg("[IndeedCaptchaHandler] ACTION REQUIRED: Please check 'I'm not a robot' in the Chrome browser window.")
        print_lg(f"[IndeedCaptchaHandler] Waiting up to {timeout} seconds for manual resolution...")
        print_lg("=" * 70 + "\n")

        # Emit intervention event to Desktop UI / Manager
        bridge = automation_bridge or self.automation_bridge
        if bridge and hasattr(bridge, "handle_intervention"):
            try:
                from app.services.automation_events import AutomationInterventionEvent, InterventionType
                bridge.handle_intervention(
                    AutomationInterventionEvent(
                        run_id="indeed_run",
                        platform="indeed",
                        intervention_type=InterventionType.CAPTCHA_DETECTED,
                        message=f"CAPTCHA challenge detected on Indeed for '{job_title}' at '{company}'. Please solve it in the browser window.",
                    )
                )
            except Exception as ex:
                print_lg(f"[IndeedCaptchaHandler] Notice dispatching intervention event: {ex}")

        # Reset bridge captcha status before waiting
        if bridge and hasattr(bridge, "reset_captcha_status"):
            bridge.reset_captcha_status()

        # Bring window to front
        try:
            drv.switch_to.window(drv.current_window_handle)
        except Exception:
            pass

        start_time = time.time()
        last_logged = 0

        try:
            while time.time() - start_time < timeout:
                if stop_check and stop_check():
                    print_lg("[IndeedCaptchaHandler] Cooperative stop/pause triggered during CAPTCHA wait.")
                    return False

                # 1. Check if user clicked 'I have resolved the CAPTCHA' in Desktop UI dialog
                if bridge and hasattr(bridge, "is_captcha_resolved_by_user") and bridge.is_captcha_resolved_by_user():
                    print_lg("[IndeedCaptchaHandler] ✅ CAPTCHA confirmed resolved by user via Human-in-the-Loop dialog! Proceeding.")
                    time.sleep(1.0)
                    return True

                # 2. Check if DOM detects CAPTCHA token / checkbox completion
                if self.is_captcha_solved(drv):
                    print_lg("[IndeedCaptchaHandler] ✅ CAPTCHA challenge resolved in browser!")
                    time.sleep(1.5)  # Allow React state / submit button to update
                    return True

                time.sleep(1)

                elapsed = int(time.time() - start_time)
                if elapsed - last_logged >= 10:
                    remaining = timeout - elapsed
                    print_lg(f"[IndeedCaptchaHandler] Still awaiting CAPTCHA solution in browser ({remaining}s remaining)...")
                    last_logged = elapsed

            print_lg(f"[IndeedCaptchaHandler] ❌ CAPTCHA was not resolved within {timeout}s.")
            return False
        finally:
            if bridge and hasattr(bridge, "reset_captcha_status"):
                bridge.reset_captcha_status()
