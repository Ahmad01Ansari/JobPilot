'''
Foundit Submission & Verification Engine
Executes final application submission on approved jobs.
Rigorously verifies confirmation indicators before declaring success.
Enforces the idempotency rule: unconfirmed submissions after a click are recorded as UNKNOWN and never retried.
'''

import time
import random
from typing import Optional, Tuple, Any
from selenium.webdriver.common.by import By

from modules.models import Job
from modules.helpers import print_lg
from modules.human_behavior import human_review_dwell, human_click, human_delay
from modules.captcha_detector import CaptchaDetector
from platforms.foundit.selectors import (
    PRIMARY_APPLY_BUTTON_SELECTORS,
    SUBMISSION_SUCCESS_TEXTS,
    APPLIED_BUTTON_TEXTS,
)


class FounditSubmitter:
    """Handles final submission execution and post-click verification on Foundit."""

    def __init__(self, browser: Any, tracker: Optional[Any] = None):
        self.browser = browser
        self.tracker = tracker
        self.captcha_detector = CaptchaDetector(platform="foundit")

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def find_apply_button(self) -> Optional[Any]:
        """Locates the primary Apply Now button in the active details pane."""
        if not self.driver:
            return None
        for sel in PRIMARY_APPLY_BUTTON_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        return None

    def verify_submission(self, timeout: int = 15, card_elem: Optional[Any] = None) -> bool:
        """Polls DOM for explicit application confirmation text, top banner, or button state transition."""
        if not self.driver:
            return False

        start_t = time.time()
        while time.time() - start_t < timeout:
            time.sleep(0.8)

            # Check if a post-submit CAPTCHA was triggered
            if self.captcha_detector.is_captcha_present(self.driver, platform="foundit")[0] and not self.captcha_detector.is_captcha_solved(self.driver, platform="foundit"):
                print_lg("[FounditSubmitter] ⚠️ Security challenge detected after submit click!")
                solved = self.captcha_detector.handle_captcha(
                    self.driver,
                    platform="foundit",
                    timeout=60,
                )
                if solved:
                    print_lg("[FounditSubmitter] Challenge resolved! Continuing confirmation check...")

            # 1. Check for top success notification banner / toast element (e.g. 'You have applied successfully')
            banner_xpaths = [
                "//*[contains(normalize-space(), 'applied successfully') or contains(normalize-space(), 'You have applied successfully')]",
                "//*[contains(normalize-space(), 'Applied just now') or contains(normalize-space(), 'applied just now')]",
                "//*[contains(normalize-space(), 'Your application status') or contains(normalize-space(), 'Application sent')]",
                "//div[contains(@class, 'success') or contains(@class, 'toast') or contains(@class, 'banner') or contains(@class, 'alert')][contains(., 'applied') or contains(., 'Applied')]",
            ]
            for bx in banner_xpaths:
                try:
                    elems = self.driver.find_elements(By.XPATH, bx)
                    for el in elems:
                        if el.is_displayed():
                            txt = (el.text or "").strip()
                            print_lg(f"[FounditSubmitter] Confirmed submission via top success banner: '{txt or 'You have applied successfully'}'")
                            return True
                except Exception:
                    continue

            # 2. Check if the card button transitioned to "Applied"
            if card_elem:
                try:
                    card_applied = card_elem.find_elements(
                        By.XPATH,
                        ".//button[contains(normalize-space(), 'Applied') or contains(normalize-space(), 'Already Applied')]"
                    )
                    if any(b.is_displayed() and any(t in (b.text or "").lower() for t in APPLIED_BUTTON_TEXTS) for b in card_applied):
                        print_lg("[FounditSubmitter] Confirmed submission via card button state: 'Applied'")
                        return True
                except Exception:
                    pass

            # 3. Check for visible success message in notification / toast elements
            for sel in [
                "div.toast, div.notification, div[class*='toast'], div[class*='snackbar']",
                "div.modal, div.popup, div[class*='successModal']",
                "div[class*='successMessage']",
                "div[class*='applySuccess']",
                "div.alert-success",
            ]:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if el.is_displayed():
                            t = (el.text or "").strip().lower()
                            if any(msg in t for msg in SUBMISSION_SUCCESS_TEXTS):
                                print_lg(f"[FounditSubmitter] Confirmed submission via notification element: '{t[:60]}'")
                                return True
                except Exception:
                    pass

            # 4. Check if the active apply button transitioned to "Applied"
            btn = self.find_apply_button()
            if btn:
                try:
                    b_txt = (btn.text or "").strip().lower()
                    if any(app_text in b_txt for app_text in APPLIED_BUTTON_TEXTS):
                        print_lg(f"[FounditSubmitter] Confirmed submission via button state: '{b_txt}'")
                        return True
                except Exception:
                    pass

        return False

    def submit(
        self,
        job: Job,
        pause_before_submit: bool = False,
        card_elem: Optional[Any] = None,
    ) -> Tuple[bool, str]:
        """Executes application submission and strictly validates the outcome."""
        if not self.driver:
            return (False, "Browser not running.")

        # 1. Locate apply button on card or details pane
        btn = None
        if card_elem:
            try:
                # Check if already applied on card
                card_applied = card_elem.find_elements(
                    By.XPATH,
                    ".//button[contains(normalize-space(), 'Applied') or contains(normalize-space(), 'Already Applied')]"
                )
                if any(b.is_displayed() and any(t in (b.text or "").lower() for t in APPLIED_BUTTON_TEXTS) for b in card_applied):
                    print_lg(f"[FounditSubmitter] Job already applied on card: '{job.title}'")
                    return (True, "ALREADY_APPLIED")

                card_btns = card_elem.find_elements(
                    By.XPATH,
                    ".//button[contains(normalize-space(), 'Quick Apply') or contains(normalize-space(), 'Apply Now') or contains(normalize-space(), 'Apply')]"
                )
                for b in card_btns:
                    if b.is_displayed():
                        btn = b
                        break
            except Exception:
                pass

        if not btn:
            btn = self.find_apply_button()

        if not btn:
            # Check if submission banner already appeared
            if self.verify_submission(timeout=2, card_elem=card_elem):
                return (True, "SUBMITTED")
            return (False, "Apply button not found on job view.")

        # Check if already applied
        btn_text = (btn.text or "").strip().lower()
        if any(t in btn_text for t in APPLIED_BUTTON_TEXTS):
            print_lg(f"[FounditSubmitter] Job already applied: '{job.title}'")
            return (True, "ALREADY_APPLIED")

        if pause_before_submit:
            print_lg("[FounditSubmitter] PAUSE BEFORE SUBMIT: Manual approval enabled. Halting before click.")
            return (False, "MANUAL_REQUIRED")

        # Check and handle pre-submit CAPTCHA
        if self.captcha_detector.is_captcha_present(self.driver, platform="foundit")[0] and not self.captcha_detector.is_captcha_solved(self.driver, platform="foundit"):
            print_lg(f"[FounditSubmitter] ⚠️ Pre-submit security challenge detected for '{job.title}'!")
            solved = self.captcha_detector.handle_captcha(
                self.driver,
                platform="foundit",
                job_title=job.title,
                company=job.company,
                timeout=60,
            )
            if not solved:
                return (False, "MANUAL_REQUIRED")
            # Refresh button in case DOM re-rendered
            btn = self.find_apply_button() or btn

        # Human review dwell time & smooth micro-scroll
        human_review_dwell(self.driver, min_s=1.0, max_s=2.2)

        print_lg(f"[FounditSubmitter] Clicking '{btn.text.strip() or 'Apply'}' for '{job.title}' at '{job.company}'...")
        clicked = human_click(self.driver, btn, smooth_scroll=True, dwell_before=True)
        if not clicked:
            return (False, "CLICK_FAILED")

        # Dynamic delay (1.2 - 2.2s) for post-click response and potential popup
        human_delay(1.2, 2.2, action="click")

        # Strictly verify confirmation
        confirmed = self.verify_submission(timeout=12, card_elem=card_elem)
        if confirmed:
            print_lg(f"[FounditSubmitter] SUBMISSION VERIFIED: '{job.title}' at '{job.company}'")
            return (True, "SUBMITTED")

        # Unconfirmed submission click: must be recorded as UNKNOWN to prevent auto-retrying
        print_lg(f"[FounditSubmitter] UNCONFIRMED SUBMISSION: Click occurred but confirmation signal missing for '{job.title}'. Setting UNKNOWN.")
        return (False, "UNKNOWN")
