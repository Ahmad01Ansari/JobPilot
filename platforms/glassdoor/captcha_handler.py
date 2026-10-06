'''
Glassdoor CAPTCHA & Security Challenge Handler
Detects Cloudflare Turnstile, Google reCAPTCHA, and anti-bot verification challenges on Glassdoor.
Provides cooperative manual resolution polling without anti-bypass violations.
'''

import time
from typing import Optional, Any, Callable
from selenium.webdriver.common.by import By

from platforms.glassdoor.selectors import (
    CAPTCHA_IFRAME_SELECTORS,
    CAPTCHA_CONTAINER_SELECTORS,
)
from modules.helpers import print_lg


class GlassdoorCaptchaHandler:
    """Handles detection and cooperative manual resolution of CAPTCHAs on Glassdoor."""

    def __init__(self, browser: Optional[Any] = None, automation_bridge: Optional[Any] = None):
        self.browser = browser
        self.automation_bridge = automation_bridge

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def is_captcha_present(self, driver: Optional[Any] = None) -> bool:
        """Checks if an active, visible challenge is present on the page."""
        drv = driver or self.driver
        if not drv:
            return False

        try:
            # Check visible blocking iframes
            for sel in CAPTCHA_IFRAME_SELECTORS:
                elems = drv.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        rect = el.rect or {}
                        if rect.get("width", 0) >= 100 and rect.get("height", 0) >= 30:
                            return True
            # Check challenge stage
            for sel in CAPTCHA_CONTAINER_SELECTORS:
                elems = drv.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
        except Exception:
            pass

        return False

    def handle_captcha(
        self,
        driver: Optional[Any] = None,
        max_wait_seconds: int = 60,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Cooperatively waits for user to resolve verification challenge."""
        drv = driver or self.driver
        if not self.is_captcha_present(drv):
            return True

        print_lg("[GlassdoorCaptchaHandler] ⚠️ Security Challenge Detected on Glassdoor!")
        print_lg(f"[GlassdoorCaptchaHandler] Pausing for up to {max_wait_seconds}s for human resolution...")

        if self.automation_bridge:
            try:
                self.automation_bridge.emit_captcha_detected("glassdoor")
            except Exception:
                pass

        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            if stop_check and stop_check():
                print_lg("[GlassdoorCaptchaHandler] Stop signal received during CAPTCHA wait.")
                return False

            if not self.is_captcha_present(drv):
                print_lg("[GlassdoorCaptchaHandler] Challenge cleared. Resuming automation.")
                return True

            time.sleep(1.5)

        print_lg("[GlassdoorCaptchaHandler] Timed out waiting for manual verification resolution.")
        return False
