'''
Glassdoor Application Submitter & Positive Verification
Handles the final review step, checks manual pause gates, executes humanized submit clicks,
and verifies real positive submission confirmation signals.
'''

import os
import time
from typing import Optional, Any
from selenium.webdriver.common.by import By

from platforms.glassdoor.selectors import (
    FORM_SUBMIT_BUTTONS,
    SUBMIT_SUCCESS_CONTAINERS,
    APPLY_ALREADY_BADGES,
)
from modules.helpers import print_lg
from modules.human_behavior import human_delay, smooth_scroll


class GlassdoorSubmitter:
    """Manages the final submission step and confirms positive application status."""

    def __init__(self, browser: Any, pause_before_submit: bool = False):
        self.browser = browser
        self.pause_before_submit = pause_before_submit

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def submit_application(self) -> bool:
        """Clicks final submit and confirms success."""
        if not self.driver:
            return False

        if self.pause_before_submit:
            print_lg("[GlassdoorSubmitter] 'pause_before_submit' is enabled. Pausing for user manual review...")
            return False

        # Locate submit button by scrolling to bottom first
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
        except Exception:
            pass

        submit_btn = None
        for sel in FORM_SUBMIT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for btn in elems:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.3)
                    except Exception:
                        pass
                    if btn.is_displayed():
                        submit_btn = btn
                        break
                if submit_btn:
                    break
            except Exception:
                continue

        # Dynamic JS fallback to find submit button
        if not submit_btn:
            try:
                submit_btn = self.driver.execute_script("""
                    const candidates = Array.from(document.querySelectorAll('button, a, div[role="button"], input[type="submit"]'));
                    for (const el of candidates) {
                        const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                        if (txt.includes('submit your application') || txt.includes('submit application') || txt === 'submit') {
                            el.scrollIntoView({block: 'center'});
                            return el;
                        }
                    }
                    return null;
                """)
            except Exception:
                pass

        if not submit_btn:
            print_lg("[GlassdoorSubmitter] Final submit button not found.")
            return False

        # Natural dwell and click
        smooth_scroll(self.driver, submit_btn)
        human_delay(1.0, 1.8)
        try:
            submit_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", submit_btn)
        print_lg("[GlassdoorSubmitter] Clicked Submit Application.")
        human_delay(3.0, 5.0)

        # Confirm positive verification
        return self.verify_submission()

    def verify_submission(self, max_wait_sec: int = 10) -> bool:
        """Polls for explicit positive confirmation signals."""
        if not self.driver:
            return False

        start_time = time.time()
        while time.time() - start_time < max_wait_sec:
            for sel in SUBMIT_SUCCESS_CONTAINERS + APPLY_ALREADY_BADGES:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        print_lg("[GlassdoorSubmitter] Positive application confirmation verified!")
                        return True
                except Exception:
                    continue
            time.sleep(1.0)

        print_lg("[GlassdoorSubmitter] Warning: Positive confirmation signal not observed within timeout.")
        return False
