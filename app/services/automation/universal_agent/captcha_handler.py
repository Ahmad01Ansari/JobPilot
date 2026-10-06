"""Universal CAPTCHA Detection & Resolution Layer.

Detects and resolves hCaptcha, Google reCAPTCHA, and Cloudflare Turnstile
across external ATS portals using automated checkbox clicks, Buster extension
cooperation, and Human-in-the-Loop (HITL) cooperative wait loops.
"""

import asyncio
import json
import logging
import random
from typing import Any, Dict, Optional, Tuple

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent

logger = logging.getLogger(__name__)


class UniversalCaptchaHandler:
    """Manages anti-bot and CAPTCHA challenge detection, auto-solving, and HITL handling."""

    # Selectors for visible CAPTCHA iframes and containers
    CAPTCHA_SELECTORS = [
        "iframe[src*='hcaptcha']",
        "iframe[src*='hcaptcha.com']",
        "iframe[title*='hCaptcha']",
        "iframe[title*='checkbox for hCaptcha']",
        ".h-captcha",
        "[data-hcaptcha-widget-id]",
        "div[id*='hcaptcha']",
        "iframe[src*='recaptcha']:not([src*='bframe'])",
        "iframe[src*='google.com/recaptcha']",
        "iframe[src*='bframe']",
        ".g-recaptcha",
        "iframe[src*='challenges.cloudflare.com']",
        "iframe[src*='turnstile']",
        "#challenge-stage",
    ]

    # Text patterns indicating a mandatory CAPTCHA challenge or submission block
    CHALLENGE_TEXT_PATTERNS = [
        "verification is required before submitting",
        "please complete the captcha",
        "captcha verification failed",
        "verify you are human",
        "i am human",
        "solve this challenge",
        "security check",
    ]

    async def detect_captcha(self, agent: BrowserAgent) -> Tuple[bool, Optional[str], Optional[str]]:
        """Inspects page DOM for visible, active CAPTCHA challenges.
        
        Returns:
            (is_present, captcha_type, message)
        """
        js_detect = """(() => {
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

            // 1. Check hCaptcha
            const hFrames = document.querySelectorAll("iframe[src*='hcaptcha'], iframe[title*='hCaptcha'], .h-captcha, [data-hcaptcha-widget-id], #captcha-field");
            for (const h of hFrames) {
                if (isVisible(h)) {
                    // Check if token already exists
                    let token = '';
                    const tEl = document.querySelector("textarea[name='h-captcha-response'], [id*='h-captcha-response']");
                    if (tEl) token = tEl.value || '';
                    if (!token || token.length < 15) {
                        return { present: true, type: 'hCaptcha', selector: "iframe[src*='hcaptcha'], .h-captcha, #captcha-field" };
                    }
                }
            }

            // 2. Check reCAPTCHA v2 / Enterprise
            const bframes = document.querySelectorAll("iframe[src*='bframe']");
            for (const b of bframes) {
                const rect = b.getBoundingClientRect();
                if (isVisible(b) && rect.width >= 200 && rect.height >= 200) {
                    return { present: true, type: 'reCAPTCHA', selector: "iframe[src*='bframe']" };
                }
            }
            const anchors = document.querySelectorAll("iframe[src*='recaptcha']:not([src*='bframe'])");
            for (const a of anchors) {
                if (isVisible(a)) {
                    const rect = a.getBoundingClientRect();
                    if (rect.width >= 120 && rect.height >= 40) {
                        let token = '';
                        const gEl = document.querySelector("textarea[id='g-recaptcha-response'], textarea[name='g-recaptcha-response']");
                        if (gEl) token = gEl.value || '';
                        if (!token || token.length < 15) {
                            return { present: true, type: 'reCAPTCHA', selector: "iframe[src*='recaptcha']" };
                        }
                    }
                }
            }

            // 3. Check Cloudflare Turnstile
            const cfFrames = document.querySelectorAll("iframe[src*='challenges.cloudflare.com'], iframe[src*='turnstile'], #challenge-stage");
            for (const cf of cfFrames) {
                if (isVisible(cf)) {
                    let token = '';
                    const cfInput = document.querySelector("input[name='cf-turnstile-response']");
                    if (cfInput) token = cfInput.value || '';
                    if (!token || token.length < 15) {
                        return { present: true, type: 'Cloudflare Turnstile', selector: "iframe[src*='turnstile']" };
                    }
                }
            }

            // 4. Check for explicit validation text error on page
            const bodyTxt = (document.body ? document.body.innerText : '').toLowerCase();
            if (bodyTxt.includes("verification is required before submitting") ||
                bodyTxt.includes("captcha verification failed") ||
                bodyTxt.includes("please complete the captcha")) {
                return { present: true, type: 'hCaptcha', selector: "#captcha-field, iframe[src*='hcaptcha'], .h-captcha", error_text: true };
            }

            return { present: false };
        })()"""
        try:
            eval_res = agent.evaluate(js_detect)
            res = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
            if isinstance(res, dict) and res.get("present"):
                c_type = res.get("type", "CAPTCHA")
                msg = f"Active {c_type} security challenge detected."
                return True, c_type, msg
        except Exception as e:
            logger.warning("Error evaluating CAPTCHA detection script: %s", e)

        return False, None, None

    async def is_captcha_solved(self, agent: BrowserAgent) -> bool:
        """Verifies if the CAPTCHA response token has been generated and populated."""
        js_check = """(() => {
            // Check hCaptcha response
            const hResp = document.querySelector("textarea[name='h-captcha-response'], [id*='h-captcha-response']");
            if (hResp && hResp.value && hResp.value.trim().length >= 20) return true;

            // Check reCAPTCHA response
            const gResp = document.querySelector("textarea[id='g-recaptcha-response'], textarea[name='g-recaptcha-response']");
            if (gResp && gResp.value && gResp.value.trim().length >= 20) return true;

            // Check Cloudflare Turnstile response
            const cfResp = document.querySelector("input[name='cf-turnstile-response']");
            if (cfResp && cfResp.value && cfResp.value.trim().length >= 20) return true;

            // Check if bframe puzzle has closed and error text is gone
            const bframes = document.querySelectorAll("iframe[src*='bframe']");
            let hasOpenBframe = false;
            for (const b of bframes) {
                const style = window.getComputedStyle(b);
                const rect = b.getBoundingClientRect();
                if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width >= 200) {
                    hasOpenBframe = true;
                }
            }
            if (hasOpenBframe) return false;

            // Check if aria-checked is true on checkboxes
            const checkedBoxes = document.querySelectorAll("[aria-checked='true']");
            for (const cb of checkedBoxes) {
                const id = cb.id || '';
                const role = cb.getAttribute('role') || '';
                if (role === 'checkbox' || id.includes('recaptcha') || id.includes('hcaptcha')) {
                    return true;
                }
            }

            return false;
        })()"""
        try:
            eval_res = agent.evaluate(js_check)
            solved = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
            return bool(solved)
        except Exception:
            return False

    async def attempt_auto_click(self, agent: BrowserAgent) -> bool:
        """Attempts to click the interactive 'I am human' checkbox using coordinate-based clicking.

        Stagehand's locator does not support complex CSS selectors for cross-origin
        iframes.  The proven approach is to calculate the checkbox position via
        getBoundingClientRect() and use page.click(x, y) for a hardware-level click.
        """
        logger.info("Attempting automated click on interactive CAPTCHA checkbox...")
        try:
            # Scroll CAPTCHA into view smoothly
            try:
                eval_scroll = agent.evaluate("""(() => {
                    const el = document.querySelector("#captcha-field, .h-captcha, iframe[src*='hcaptcha'], iframe[src*='recaptcha'], .g-recaptcha");
                    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                })()""")
                if asyncio.iscoroutine(eval_scroll):
                    await eval_scroll
            except Exception:
                pass
            await asyncio.sleep(random.uniform(0.8, 1.4))

            # ── Method 1: Coordinate-based Page.click(x, y) on the checkbox iframe ──
            # This is the most reliable method for Stagehand which uses CDP-level input.
            if hasattr(agent, "page") and agent.page and hasattr(agent.page, "click"):
                js_get_coords = """(() => {
                    // Priority order: hCaptcha anchor → reCAPTCHA anchor → .g-recaptcha container
                    const selectors = [
                        "iframe[src*='hcaptcha']:not([src*='bframe'])",
                        "iframe[title*='hCaptcha']",
                        "iframe[data-hcaptcha-widget-id]",
                        "iframe[src*='recaptcha']:not([src*='bframe'])",
                        "iframe[title='reCAPTCHA']",
                        ".g-recaptcha iframe",
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (!el) continue;
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        const r = el.getBoundingClientRect();
                        if (r.width < 50 || r.height < 20) continue;
                        // The checkbox is at approximately 28px from left, 39px from top
                        // within the standard reCAPTCHA / hCaptcha anchor iframe
                        return { x: r.left + 28, y: r.top + Math.min(39, r.height / 2) };
                    }
                    // Fallback: try .g-recaptcha or .h-captcha container center
                    const container = document.querySelector('.g-recaptcha, .h-captcha, #captcha-field');
                    if (container) {
                        const r = container.getBoundingClientRect();
                        if (r.width > 50 && r.height > 20) {
                            return { x: r.left + 28, y: r.top + 39 };
                        }
                    }
                    return null;
                })()"""
                try:
                    eval_res = agent.evaluate(js_get_coords)
                    coords = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
                    if coords and isinstance(coords, dict) and "x" in coords and "y" in coords:
                        cx, cy = float(coords["x"]), float(coords["y"])
                        logger.info("Clicking CAPTCHA checkbox at viewport coordinates (%.1f, %.1f)...", cx, cy)
                        await agent.page.click(x=cx, y=cy)
                        logger.info("Coordinate-based CAPTCHA click sent successfully.")

                        # Wait for checkbox animation + Buster / auto-clear (up to 12s)
                        for wait_idx in range(24):
                            await asyncio.sleep(0.5)
                            if await self.is_captcha_solved(agent):
                                logger.info("CAPTCHA successfully auto-cleared after coordinate click!")
                                return True
                            # Check if bframe image challenge opened (means checkbox was clicked)
                            if wait_idx == 4:
                                try:
                                    bframe_check = agent.evaluate("""(() => {
                                        const b = document.querySelector("iframe[src*='bframe']");
                                        if (!b) return false;
                                        const r = b.getBoundingClientRect();
                                        return r.width >= 250 && r.height >= 250;
                                    })()""")
                                    has_bframe = await bframe_check if asyncio.iscoroutine(bframe_check) else bframe_check
                                    if has_bframe:
                                        logger.info("CAPTCHA image challenge (bframe) opened — requires human resolution.")
                                        return False  # Human must solve image tiles
                                except Exception:
                                    pass
                except Exception as coord_err:
                    logger.debug("Coordinate-based CAPTCHA click failed: %s", coord_err)

            # ── Method 2: Fallback — selector-based agent.click() ──
            for sel in [
                "iframe[data-hcaptcha-widget-id]",
                "iframe[src*='hcaptcha']",
                "iframe[title*='hCaptcha']",
                "#captcha-field",
                ".h-captcha",
                ".g-recaptcha",
            ]:
                try:
                    clicked = await agent.click(sel)
                    if clicked:
                        logger.info("Clicked CAPTCHA element with selector '%s'", sel)
                        break
                except Exception:
                    continue

            # Wait briefly to see if it clears or Buster solves it
            for _ in range(8):
                await asyncio.sleep(0.5)
                if await self.is_captcha_solved(agent):
                    logger.info("CAPTCHA successfully auto-cleared after fallback click!")
                    return True
        except Exception as e:
            logger.warning("Auto-click attempt on CAPTCHA failed: %s", e)

        return False

    async def poll_until_solved(self, agent: BrowserAgent, timeout_seconds: int = 60) -> bool:
        """Polls periodically to verify if the user or solver extension resolved the CAPTCHA."""
        for _ in range(timeout_seconds):
            if await self.is_captcha_solved(agent):
                return True
            await asyncio.sleep(1.0)
        return False
