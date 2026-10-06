'''
Multi-Platform Anti-Bot Challenge & CAPTCHA Detector
Provides automated detection, user intervention alerting via Desktop UI / logs,
and cooperative Human-in-the-Loop (HITL) resolution across LinkedIn, Naukri, Foundit, and Indeed.
'''

import time
from typing import Optional, Any, Callable, Tuple
from selenium.webdriver.common.by import By

from modules.helpers import print_lg


class CaptchaDetector:
    """Multi-platform anti-bot, CAPTCHA, and checkpoint challenge handler for Selenium."""

    def __init__(self, platform: str = "generic", automation_bridge: Optional[Any] = None):
        self.platform = (platform or "generic").lower()
        self.automation_bridge = automation_bridge

    def is_captcha_present(self, driver: Any, platform: Optional[str] = None) -> Tuple[bool, str]:
        """Checks if an active, visible CAPTCHA, Cloudflare, or security challenge is present on the page.

        Returns:
            (is_present, challenge_type_or_description)
        """
        if not driver:
            return (False, "")

        plat = (platform or self.platform).lower()

        # 1. Platform-specific URL / checkpoint inspection
        try:
            curr_url = (getattr(driver, "current_url", "") or "").lower()
            if plat == "linkedin":
                if any(k in curr_url for k in ["/checkpoint/", "/challenge/", "consumer-captcha", "/two-step", "security-check"]):
                    return (True, "LinkedIn Security Checkpoint / 2FA")
            elif plat == "naukri":
                if "captcha" in curr_url or "challenge" in curr_url:
                    return (True, "Naukri Security Challenge")
            elif plat == "foundit":
                if "challenge" in curr_url or "captcha" in curr_url:
                    return (True, "Foundit Security Check")
        except Exception:
            pass

        # 2. Strict JavaScript DOM challenge detection (reCAPTCHA, Turnstile, hCaptcha, Arkose)
        try:
            js_res = driver.execute_script("""
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

                // A. Google reCAPTCHA v2 / Enterprise interactive anchor checkbox
                const anchors = document.querySelectorAll("iframe[src*='anchor'], iframe[src*='recaptcha']:not([src*='bframe'])");
                for (let i = 0; i < anchors.length; i++) {
                    const a = anchors[i];
                    if (a.closest && a.closest('.grecaptcha-badge')) continue;
                    if (a.parentElement && (a.parentElement.className || '').toString().includes('grecaptcha-badge')) continue;
                    const src = (a.src || "").toLowerCase();
                    if (src.includes("size=invisible") || src.includes("badge=bottomright") || src.includes("badge=inline")) continue;
                    if (isVisible(a)) {
                        const rect = a.getBoundingClientRect();
                        if (rect.top >= 0 && rect.top <= window.innerHeight && rect.width >= 120 && rect.height >= 40) {
                            return { present: true, type: "Google reCAPTCHA Checkbox" };
                        }
                    }
                }

                // B. Google reCAPTCHA interactive bframe image challenge popup
                const bframes = document.querySelectorAll("iframe[src*='bframe']");
                for (let i = 0; i < bframes.length; i++) {
                    const b = bframes[i];
                    const rect = b.getBoundingClientRect();
                    const style = window.getComputedStyle(b);
                    const parentStyle = b.parentElement ? window.getComputedStyle(b.parentElement) : null;
                    if (style.visibility !== 'hidden' && style.display !== 'none' && parseFloat(style.opacity || '1') > 0 &&
                        (!parentStyle || (parentStyle.visibility !== 'hidden' && parentStyle.display !== 'none')) &&
                        rect.top >= 0 && rect.width >= 200 && rect.height >= 200) {
                        return { present: true, type: "Google reCAPTCHA Image Puzzle" };
                    }
                }

                // C. Cloudflare Turnstile / Challenge iframe
                const turnstiles = document.querySelectorAll("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], .cf-turnstile");
                for (let i = 0; i < turnstiles.length; i++) {
                    const t = turnstiles[i];
                    if (isVisible(t)) {
                        const rect = t.getBoundingClientRect();
                        if (rect.top >= 0 && rect.top <= window.innerHeight && rect.width >= 100 && rect.height >= 40) {
                            return { present: true, type: "Cloudflare Turnstile" };
                        }
                    }
                }

                // D. Cloudflare Under-Attack Challenge Stage
                const cfStages = document.querySelectorAll("#challenge-stage, #challenge-running");
                for (let i = 0; i < cfStages.length; i++) {
                    const el = cfStages[i];
                    if (isVisible(el)) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width >= 100 && rect.height >= 50) {
                            return { present: true, type: "Cloudflare Challenge Stage" };
                        }
                    }
                }

                // E. hCaptcha Checkbox / Frame
                const hFrames = document.querySelectorAll("iframe[src*='hcaptcha'], .h-captcha, [data-hcaptcha-widget-id]");
                for (let i = 0; i < hFrames.length; i++) {
                    const h = hFrames[i];
                    if (isVisible(h)) {
                        let token = '';
                        const tEl = document.querySelector("textarea[name='h-captcha-response']");
                        if (tEl) token = tEl.value || '';
                        if (!token || token.length < 15) {
                            return { present: true, type: "hCaptcha" };
                        }
                    }
                }

                // F. Arkose Labs / FunCaptcha
                const arkose = document.querySelectorAll("iframe[src*='arkoselabs'], iframe[src*='funcaptcha']");
                for (let i = 0; i < arkose.length; i++) {
                    if (isVisible(arkose[i])) {
                        return { present: true, type: "Arkose Labs Challenge" };
                    }
                }

                // G. Check for explicit CAPTCHA validation error text on page
                const bodyTxt = (document.body ? document.body.innerText : '').toLowerCase();
                if (bodyTxt.includes("verification is required before submitting") ||
                    bodyTxt.includes("please complete the security check") ||
                    bodyTxt.includes("verify you are human") ||
                    bodyTxt.includes("solve this challenge")) {
                    // Only consider blocking if no regular interactive application forms are visible
                    const appInputs = document.querySelectorAll("input:not([type='hidden']), textarea, select");
                    let visibleInputs = 0;
                    for (let i = 0; i < appInputs.length; i++) {
                        if (isVisible(appInputs[i])) visibleInputs++;
                    }
                    if (visibleInputs <= 1) {
                        return { present: true, type: "Security Verification Wall" };
                    }
                }

                return { present: false };
            """)
            if isinstance(js_res, dict) and js_res.get("present"):
                return (True, js_res.get("type", "CAPTCHA Challenge"))
        except Exception:
            pass

        # 3. Selenium DOM fallback selectors for specific platforms
        fallback_selectors = []
        if plat == "naukri":
            fallback_selectors.extend([
                ".captcha-container",
                "div[class*='captcha']",
                "div[id*='captcha']",
                "iframe[src*='recaptcha']",
                "iframe[src*='hcaptcha']",
            ])
        elif plat == "foundit":
            fallback_selectors.extend([
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='recaptcha']",
                "iframe[src*='arkoselabs']",
                "div[id*='turnstile']",
                "div.cf-turnstile",
                "div[class*='captcha']",
                "#challenge-running",
            ])
        elif plat == "linkedin":
            fallback_selectors.extend([
                "iframe[src*='checkpoint']",
                "iframe[src*='challenge']",
                "div.challenge-dialog",
                "#captcha-internal",
            ])
        else:
            fallback_selectors.extend([
                "iframe[src*='anchor']:not([src*='size=invisible'])",
                "iframe[src*='recaptcha/api2/bframe']",
                "iframe[src*='bframe']",
                "#challenge-stage",
            ])

        for sel in fallback_selectors:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed() and el.size.get("width", 0) >= 60 and el.size.get("height", 0) >= 30:
                        return (True, f"Visible challenge matching '{sel}'")
            except Exception:
                continue

        return (False, "")

    def is_captcha_solved(self, driver: Any, platform: Optional[str] = None) -> bool:
        """Checks if the CAPTCHA has been solved, dismissed, or bypassed by user action."""
        if not driver:
            return False

        plat = (platform or self.platform).lower()

        # If challenge is no longer present, it is solved/bypassed
        is_pres, _ = self.is_captcha_present(driver, platform=plat)
        if not is_pres:
            return True

        # Check platform URL redirect
        try:
            curr_url = (getattr(driver, "current_url", "") or "").lower()
            if plat == "linkedin":
                if any(p in curr_url for p in ["/feed", "/mynetwork", "/jobs", "/in/"]):
                    if not any(k in curr_url for k in ["/checkpoint/", "/challenge/"]):
                        return True
        except Exception:
            pass

        # Check token injection via JavaScript
        try:
            solved = driver.execute_script("""
                // A. If an active image challenge puzzle is open, not solved
                const bframes = document.querySelectorAll("iframe[src*='bframe']");
                for (let i = 0; i < bframes.length; i++) {
                    const b = bframes[i];
                    const s = window.getComputedStyle(b);
                    if (s.visibility !== 'hidden' && s.display !== 'none') {
                        const rect = b.getBoundingClientRect();
                        if (rect.top >= 0 && rect.width >= 200 && rect.height >= 200) {
                            return false;
                        }
                    }
                }

                // B. reCAPTCHA token check
                const gResp = document.getElementById("g-recaptcha-response") || document.querySelector("textarea[name='g-recaptcha-response']");
                if (gResp && (gResp.value || "").trim().length > 20) {
                    return true;
                }

                // C. Cloudflare token check
                const cfInput = document.querySelector("input[name='cf-turnstile-response']");
                if (cfInput && (cfInput.value || "").trim().length > 20) {
                    return true;
                }

                // D. hCaptcha token check
                const hResp = document.querySelector("textarea[name='h-captcha-response']");
                if (hResp && (hResp.value || "").trim().length > 20) {
                    return true;
                }

                // E. Check aria-checked on interactive checkbox
                const checkedBoxes = document.querySelectorAll("[aria-checked='true']");
                for (let i = 0; i < checkedBoxes.length; i++) {
                    const id = checkedBoxes[i].id || '';
                    if (id.includes('recaptcha') || id.includes('hcaptcha') || checkedBoxes[i].getAttribute('role') === 'checkbox') {
                        return true;
                    }
                }

                return false;
            """)
            if solved is True:
                return True
        except Exception:
            pass

        return False

    def handle_captcha(
        self,
        driver: Any,
        platform: Optional[str] = None,
        job_title: str = "",
        company: str = "",
        timeout: int = 60,
        stop_check: Optional[Callable[[], bool]] = None,
        automation_bridge: Optional[Any] = None,
    ) -> bool:
        """Cooperatively pauses and awaits human resolution in open browser window.

        Emits an intervention event to the Desktop UI / AutomationBridge,
        logs clear instructions to the console, and polls periodically until solved.
        """
        if not driver:
            return False

        plat = (platform or self.platform).lower()

        is_pres, challenge_desc = self.is_captcha_present(driver, platform=plat)
        if not is_pres:
            return True

        if self.is_captcha_solved(driver, platform=plat):
            return True

        plat_title = plat.upper() if plat != "generic" else "WEB"
        print_lg("\n" + "=" * 70)
        print_lg(f"[{plat_title} Anti-Bot] ⚠️  SECURITY CHALLENGE / CAPTCHA DETECTED ON {plat_title}!")
        if job_title or company:
            print_lg(f"[{plat_title} Anti-Bot] Context: '{job_title}' at '{company}'")
        print_lg(f"[{plat_title} Anti-Bot] Detected: {challenge_desc}")
        print_lg(f"[{plat_title} Anti-Bot] ACTION REQUIRED: Please complete the challenge in your open Chrome browser window.")
        print_lg(f"[{plat_title} Anti-Bot] Waiting up to {timeout} seconds for manual completion...")
        print_lg("=" * 70 + "\n")

        bridge = automation_bridge or self.automation_bridge
        if bridge and hasattr(bridge, "handle_intervention"):
            try:
                from app.services.automation_events import AutomationInterventionEvent, InterventionType
                itype = InterventionType.TWO_FACTOR_AUTH if "2fa" in challenge_desc.lower() else InterventionType.CAPTCHA_DETECTED
                bridge.handle_intervention(
                    AutomationInterventionEvent(
                        run_id=f"{plat}_run",
                        platform=plat,
                        intervention_type=itype,
                        message=f"{challenge_desc} detected on {plat_title}. Please solve it in the browser window.",
                    )
                )
            except Exception as ex:
                print_lg(f"[{plat_title} Anti-Bot] Notice emitting intervention event: {ex}")

        if bridge and hasattr(bridge, "reset_captcha_status"):
            try:
                bridge.reset_captcha_status()
            except Exception:
                pass

        start_time = time.time()
        while time.time() - start_time < timeout:
            if stop_check and stop_check():
                print_lg(f"[{plat_title} Anti-Bot] Operation paused or stopped by user.")
                return False

            if bridge and hasattr(bridge, "is_captcha_resolved") and bridge.is_captcha_resolved():
                print_lg(f"[{plat_title} Anti-Bot] ✅ CAPTCHA confirmed resolved via Human-in-the-Loop dialog!")
                return True

            if self.is_captcha_solved(driver, platform=plat):
                print_lg(f"[{plat_title} Anti-Bot] ✅ Security challenge resolved in browser! Resuming automation.")
                if bridge and hasattr(bridge, "dismiss_intervention"):
                    try:
                        bridge.dismiss_intervention()
                    except Exception:
                        pass
                return True

            time.sleep(1.0)

        print_lg(f"[{plat_title} Anti-Bot] ❌ Challenge was not resolved within {timeout}s.")
        return False
