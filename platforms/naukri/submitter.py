'''
Naukri Submission & Verification Engine (Phase 12)
Executes final application submission on approved jobs.
Rigorously verifies confirmation indicators before declaring success.
Enforces the idempotency rule: unconfirmed submissions after a click are recorded as UNKNOWN and never retried.
'''

import time
from typing import Optional, Tuple, Any
from selenium.webdriver.common.by import By

from modules.models import Job
from modules.helpers import print_lg
from modules.human_behavior import human_review_dwell, human_click, human_delay
from modules.captcha_detector import CaptchaDetector
from platforms.naukri.selectors import (
    FORM_SUBMIT_BUTTON_SELECTORS,
    SUBMISSION_SUCCESS_SELECTORS,
    SUBMISSION_CONFIRMATION_TEXTS,
    CHATBOT_CONFIRMATION_TEXTS,
    QUESTIONNAIRE_MODAL_SELECTORS,
    SUBMISSION_ERROR_TEXTS,
    APPLIED_BUTTON_SELECTORS,
)


class NaukriSubmitter:
    """
    Handles final submission execution and post-click verification on Naukri.
    """

    def __init__(self, browser: Any, tracker: Optional[Any] = None):
        self.browser = browser
        self.tracker = tracker
        self.captcha_detector = CaptchaDetector(platform="naukri")

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def find_submit_button(self, container: Optional[Any] = None) -> Optional[Any]:
        """Locates the primary submit button in the active modal or on the page."""
        if not self.driver:
            return None

        # If a chatbot drawer is open, there is NO external submit button!
        # The chatbot automatically submits applications when all questions are answered.
        if container is None:
            try:
                chatbots = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div._chatBotContainer, div[class*='_chatBotContainer'], div.chatbot_Drawer, div[class*='chatbot_Drawer']"
                )
                real_chatbots = []
                for cb in chatbots:
                    try:
                        cls_val = cb.get_attribute("class")
                        if isinstance(cls_val, str) and any(w in cls_val.lower() for w in ["chatbot", "drawer"]) and cb.is_displayed():
                            real_chatbots.append(cb)
                    except Exception:
                        pass
                if real_chatbots:
                    return None
            except Exception:
                pass

        ctx = container or self.driver

        def _is_invalid_submit_button(btn: Any) -> bool:
            try:
                b_cls = (btn.get_attribute("class") or "").lower()
                b_id = (btn.get_attribute("id") or "").lower()
                b_txt = (btn.text or "").strip().lower()
                # Exclude bookmark "Save Job" buttons
                if any(w in b_cls or w in b_id for w in ["save-job", "bookmark", "styles_save"]):
                    return True
                # Exclude intermediate Next/Continue buttons
                if any(w in b_txt for w in ["next", "continue", "save and next"]):
                    return True
                return False
            except Exception:
                return True

        for sel in FORM_SUBMIT_BUTTON_SELECTORS:
            try:
                btns = ctx.find_elements(By.CSS_SELECTOR, sel)
                for b in btns:
                    if b.is_displayed() and b.is_enabled() and not _is_invalid_submit_button(b):
                        return b
            except Exception:
                continue

        # XPath fallback for submit buttons
        try:
            xpath_btns = ctx.find_elements(
                By.XPATH,
                ".//button[normalize-space(translate(text(), 'SUBMIT', 'submit'))='submit'] | "
                ".//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]"
            )
            for b in xpath_btns:
                if b.is_displayed() and b.is_enabled() and not _is_invalid_submit_button(b):
                    return b
        except Exception:
            pass

        return None

    def verify_submission(
        self,
        timeout: float = 8.0,
        check_interval: float = 0.5,
    ) -> Tuple[bool, Optional[str]]:
        """
        Polls the active DOM to confirm that the application was successfully submitted.
        
        CRITICAL: Only returns True when there is unambiguous proof of submission.
        Avoids false positives from generic page text or promotional banners.
        """
        if not self.driver:
            return (False, "Browser driver not available")

        start = time.time()
        while time.time() - start < timeout:
            # Check if a post-submit CAPTCHA was triggered
            if self.captcha_detector.is_captcha_present(self.driver, platform="naukri")[0] and not self.captcha_detector.is_captcha_solved(self.driver, platform="naukri"):
                print_lg("[NaukriSubmitter] ⚠️ Security challenge detected after submit click!")
                solved = self.captcha_detector.handle_captcha(
                    self.driver,
                    platform="naukri",
                    timeout=60,
                )
                if solved:
                    print_lg("[NaukriSubmitter] Challenge resolved! Continuing confirmation check...")

            # 0. Check for explicit error/rejection messages on the page
            body_text = ""
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_text = (body_elem.text or "").lower()
                for err_phrase in SUBMISSION_ERROR_TEXTS:
                    if err_phrase in body_text:
                        return (False, f"Application rejected by Naukri: '{err_phrase}'")
            except Exception:
                pass

            # 1. Applied button status (most reliable indicator on main page)
            for sel in APPLIED_BUTTON_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed():
                            txt = (e.text or "").strip().lower()
                            if "applied" in txt:
                                return (True, f"Applied button detected: {txt}")
                except Exception:
                    pass

            # 2. Check for chatbot-specific confirmation in active drawer or modal
            for q_sel in QUESTIONNAIRE_MODAL_SELECTORS:
                try:
                    drawers = self.driver.find_elements(By.CSS_SELECTOR, q_sel)
                    for d in drawers:
                        if d.is_displayed():
                            d_text = (d.text or "").lower()
                            for c_phrase in CHATBOT_CONFIRMATION_TEXTS:
                                if c_phrase in d_text:
                                    return (True, f"Chatbot confirmation matched: '{c_phrase}'")
                except Exception:
                    pass

            # 3. Strict confirmation text phrases on main page
            if body_text:
                for phrase in SUBMISSION_CONFIRMATION_TEXTS:
                    if phrase in body_text:
                        return (True, f"Confirmation text matched: '{phrase}'")

            # 4. Success message elements (check with caution)
            for sel in SUBMISSION_SUCCESS_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed():
                            txt = (e.text or "").strip()
                            txt_lower = txt.lower()
                            if any(err in txt_lower for err in SUBMISSION_ERROR_TEXTS):
                                return (False, f"Rejection indicator in element: '{txt}'")
                            # Require element to contain meaningful confirmation text
                            if txt and any(c in txt_lower for c in [
                                "applied", "success", "submitted", "confirmed",
                                "application", "congratulations",
                            ]):
                                return (True, f"Success indicator found: {txt or sel}")
                except Exception:
                    pass

            time.sleep(check_interval)

        return (False, f"Verification timed out after {timeout}s without confirmation")

    def submit_application(
        self,
        job: Job,
        container: Optional[Any] = None,
        timeout: float = 8.0,
    ) -> Tuple[bool, str]:
        """
        Clicks the submit button and strictly verifies confirmation.

        CRITICAL SAFETY & IDEMPOTENCY:
        - If submit button was clicked but confirmation times out:
          Records UNKNOWN state in ApplicationTracker.
          UNKNOWN states must NEVER be automatically retried!
        - If verified:
          Records SUBMITTED state in ApplicationTracker.
        """
        if not self.driver:
            return (False, "NO_DRIVER")

        btn = self.find_submit_button(container=container)
        if not btn:
            # Check if the application was already verified/completed (e.g. via chatbot flow)
            confirmed, reason = self.verify_submission(timeout=3.0)
            if confirmed:
                print_lg(f"[NaukriSubmitter] Application for '{job.job_id}' already confirmed: {reason}")
                if self.tracker:
                    self.tracker.record_state(job, "SUBMITTED", reason=reason)
                return (True, reason or "Application confirmed successfully")

            print_lg(f"[NaukriSubmitter] Submit button not found for job '{job.job_id}'")
            if self.tracker:
                self.tracker.record_state(job, "FAILED", reason="Submit button not found")
            return (False, "SUBMIT_BUTTON_NOT_FOUND")

        # Pre-submit CAPTCHA challenge check
        if self.captcha_detector.is_captcha_present(self.driver, platform="naukri")[0] and not self.captcha_detector.is_captcha_solved(self.driver, platform="naukri"):
            print_lg(f"[NaukriSubmitter] ⚠️ Pre-submit CAPTCHA challenge detected for '{job.title}'!")
            solved = self.captcha_detector.handle_captcha(
                self.driver,
                platform="naukri",
                job_title=job.title,
                company=job.company,
                timeout=60,
            )
            if not solved:
                if self.tracker:
                    self.tracker.record_state(job, "MANUAL_REQUIRED", reason="CAPTCHA_UNRESOLVED")
                return (False, "CAPTCHA_UNRESOLVED")
            # Refresh submit button in case DOM changed
            btn = self.find_submit_button(container=container) or btn

        # Human review dwell time & subtle micro-scroll to establish high trust score
        human_review_dwell(self.driver, min_s=1.0, max_s=2.5)

        # Execute Click with human_click and JS fallback
        clicked = human_click(self.driver, btn, smooth_scroll=True, dwell_before=True)
        if not clicked:
            print_lg(f"[NaukriSubmitter] Failed clicking submit button")
            if self.tracker:
                self.tracker.record_state(job, "FAILED", reason="Click failed")
            return (False, "CLICK_FAILED")

        # Strictly verify confirmation
        confirmed, reason = self.verify_submission(timeout=timeout)
        if confirmed:
            print_lg(f"[NaukriSubmitter] Submission confirmed for job '{job.job_id}': {reason}")
            if self.tracker:
                self.tracker.record_state(job, "SUBMITTED")
            return (True, "CONFIRMED_SUBMITTED")
        else:
            # Button was clicked, but confirmation timed out!
            # IDEMPOTENCY RULE: NEVER RETRY! Set state to UNKNOWN.
            print_lg(
                f"[NaukriSubmitter] WARNING: Submit button clicked but verification timed out. Setting UNKNOWN state."
            )
            if self.tracker:
                self.tracker.record_state(
                    job,
                    "UNKNOWN",
                    reason=f"Click dispatched but confirmation timed out: {reason}",
                )
            return (False, f"TIMEOUT_UNKNOWN: {reason}")
