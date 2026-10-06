"""LinkedIn Application Execution Engine.

Handles Easy Apply wizard steps, screening questions, and direct event emission.
"""

import time
from typing import Optional, Any, Dict, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from modules.tracker import ApplicationTracker
from modules.qna_engine import QnAEngine
from modules.helpers import print_lg
from platforms.linkedin.selectors import (
    EASY_APPLY_BUTTON_XPATHS,
    EASY_APPLY_MODAL_CLASS,
    MODAL_NEXT_BUTTON_XPATH,
    MODAL_REVIEW_BUTTON_XPATH,
    MODAL_SUBMIT_BUTTON_XPATH,
    MODAL_DISMISS_BUTTON_XPATH,
    CONFIRM_DISCARD_BUTTON_XPATH,
)
from modules.human_behavior import human_delay, human_type, human_click, human_review_dwell
from modules.captcha_detector import CaptchaDetector


class LinkedInApplier:
    """Manages the application lifecycle and Easy Apply form automation for LinkedIn."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        automation_bridge: Optional[Any] = None,
        qna_engine: Optional[QnAEngine] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.automation_bridge = automation_bridge
        self.qna_engine = qna_engine or QnAEngine()
        self.user_id = user_id
        self.captcha_detector = CaptchaDetector(platform="linkedin", automation_bridge=automation_bridge)

    def discard_modal(self) -> None:
        """Closes any open Easy Apply modal and confirms discard."""
        driver = self.browser.driver
        if not driver:
            return
        try:
            dismiss_buttons = driver.find_elements(By.XPATH, MODAL_DISMISS_BUTTON_XPATH)
            for btn in dismiss_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    break

            confirm_buttons = driver.find_elements(By.XPATH, CONFIRM_DISCARD_BUTTON_XPATH)
            for btn in confirm_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    break
        except Exception:
            try:
                self.browser.actions.send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass

    def apply_to_job(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        source_url: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Executes application for the currently active job listing."""
        driver = self.browser.driver
        if not driver:
            raise RuntimeError("Browser not initialized.")

        # Check deduplication / SSOT
        should_skip, reason = self.tracker.is_already_handled(job_id, platform="linkedin", user_id=self.user_id)
        if should_skip:
            print_lg(f"[LinkedInApplier] Skipping job {job_id} ({title}): {reason}")
            return {"status": "SKIPPED", "reason": reason}

        # Emit initial discovery event
        if self.automation_bridge:
            try:
                from app.services.automation_events import JobDiscoveredEvent
                self.automation_bridge.handle_job_discovered(
                    JobDiscoveredEvent(
                        run_id="linkedin_modular_run",
                        platform="linkedin",
                        external_job_id=str(job_id),
                        title=title,
                        company=company,
                        location=location,
                        url=source_url,
                        application_method="EASY_APPLY",
                        description=description,
                    )
                )
            except Exception as e:
                print_lg(f"[LinkedInApplier] Notice emitting JobDiscoveredEvent: {e}")

        # Check for Apply button
        apply_btn = None
        for xp in EASY_APPLY_BUTTON_XPATHS:
            try:
                elems = driver.find_elements(By.XPATH, xp)
                for el in elems:
                    if el.is_displayed():
                        apply_btn = el
                        break
                if apply_btn:
                    break
            except Exception:
                pass

        if not apply_btn:
            print_lg(f"[LinkedInApplier] No apply button found for job {job_id}. Marking as SKIPPED.")
            self.tracker.record_state(
                {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                state="SKIPPED",
                skip_reason="No apply button available",
                user_id=self.user_id,
            )
            return {"status": "SKIPPED", "reason": "No apply button"}

        # Track window handles before clicking to detect external apply tabs
        handles_before = list(driver.window_handles)
        current_handle = driver.current_window_handle

        human_click(driver, apply_btn, smooth_scroll=True, dwell_before=True)
        human_delay(1.5, 2.5, action="click")
        handles_after = list(driver.window_handles)

        # Case 1: External apply opened in a new tab
        if len(handles_after) > len(handles_before):
            new_tab = [h for h in handles_after if h not in handles_before][-1]
            driver.switch_to.window(new_tab)
            # Allow brief redirect wait for destination company website
            import time
            from urllib.parse import urlparse, parse_qs, unquote
            t_wait = time.time()
            ext_url = ""
            while time.time() - t_wait < 3.0:
                curr = getattr(driver, "current_url", "") or ""
                if curr and curr.startswith("http") and "about:blank" not in curr:
                    try:
                        qs = parse_qs(urlparse(curr).query)
                        for qk in ["url", "target", "redirect", "destination"]:
                            if qk in qs and qs[qk]:
                                cand = unquote(qs[qk][0]).strip()
                                if cand.startswith("http") and "linkedin.com" not in cand.lower():
                                    ext_url = cand
                                    break
                    except Exception:
                        pass
                    if ext_url:
                        break
                    if "linkedin.com" not in curr.lower():
                        ext_url = curr
                        break
                time.sleep(0.3)

            if not ext_url:
                curr = getattr(driver, "current_url", "") or ""
                if curr.startswith("http") and "linkedin.com" not in curr.lower():
                    ext_url = curr

            driver.close()
            driver.switch_to.window(current_handle)

            print_lg(f"[LinkedInApplier] External apply detected ({ext_url or 'no URL'}).")
            self.tracker.record_state(
                {
                    "platform": "linkedin",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "source_url": source_url,
                    "apply_type": "EXTERNAL",
                    "application_url": ext_url or None,
                },
                state="EXTERNAL",
                reason=f"External application portal: {ext_url or 'N/A'}",
                user_id=self.user_id,
            )
            if self.automation_bridge:
                try:
                    from app.services.automation_events import JobDiscoveredEvent
                    self.automation_bridge.handle_job_discovered(
                        JobDiscoveredEvent(
                            run_id="linkedin_modular_run",
                            platform="linkedin",
                            external_job_id=str(job_id),
                            title=title,
                            company=company,
                            location=location,
                            url=source_url,
                            application_method="COMPANY_PORTAL",
                            application_url=ext_url,
                            description=description,
                        )
                    )
                except Exception:
                    pass
            return {"status": "EXTERNAL", "application_url": ext_url}

        # Case 2: In-page Easy Apply modal
        try:
            modal = driver.find_element(By.CLASS_NAME, EASY_APPLY_MODAL_CLASS)
        except Exception:
            # Check if modal is inside an iframe or not opened
            modal = None

        if not modal:
            print_lg(f"[LinkedInApplier] Easy Apply modal did not open for job {job_id}.")
            return {"status": "FAILED", "reason": "Modal did not open"}

        self.tracker.record_state(
            {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
            state="APPLYING",
            user_id=self.user_id,
        )

        # Wizard stepper loop
        step_counter = 0
        max_steps = 12
        while step_counter < max_steps:
            step_counter += 1
            human_delay(0.8, 1.6, action="click")

            # Check if security challenge was triggered mid-wizard
            if self.captcha_detector.is_captcha_present(driver, platform="linkedin")[0] and not self.captcha_detector.is_captcha_solved(driver, platform="linkedin"):
                print_lg(f"[LinkedInApplier] ⚠️ Security challenge detected during Easy Apply wizard for '{title}'!")
                solved = self.captcha_detector.handle_captcha(
                    driver,
                    platform="linkedin",
                    job_title=title,
                    company=company,
                    timeout=60,
                    automation_bridge=self.automation_bridge,
                )
                if not solved:
                    self.discard_modal()
                    self.tracker.record_state(
                        {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                        state="MANUAL_REQUIRED",
                        failure_reason="Security challenge / CAPTCHA unresolved",
                        user_id=self.user_id,
                    )
                    return {"status": "MANUAL_REQUIRED", "reason": "CAPTCHA"}

            # Check for Submit button
            submit_buttons = driver.find_elements(By.XPATH, MODAL_SUBMIT_BUTTON_XPATH)
            for s_btn in submit_buttons:
                if s_btn.is_displayed():
                    # Human review dwell time & subtle micro-scroll before final submission
                    human_review_dwell(driver, min_s=1.2, max_s=2.8)

                    human_click(driver, s_btn, smooth_scroll=True, dwell_before=True)
                    human_delay(1.5, 2.5, action="click")

                    # Check if post-submit CAPTCHA was triggered
                    if self.captcha_detector.is_captcha_present(driver, platform="linkedin")[0] and not self.captcha_detector.is_captcha_solved(driver, platform="linkedin"):
                        print_lg(f"[LinkedInApplier] ⚠️ Security challenge detected after Submit click!")
                        self.captcha_detector.handle_captcha(
                            driver,
                            platform="linkedin",
                            job_title=title,
                            company=company,
                            timeout=60,
                            automation_bridge=self.automation_bridge,
                        )

                    self.discard_modal()  # Closes post-submit success banner if any

                    print_lg(f"[LinkedInApplier] Successfully applied to {title} at {company} ({job_id})!")
                    self.tracker.record_state(
                        {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                        state="SUBMITTED",
                        user_id=self.user_id,
                    )
                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import ApplicationSubmittedEvent
                            self.automation_bridge.handle_application_submitted(
                                ApplicationSubmittedEvent(
                                    run_id="linkedin_modular_run",
                                    platform="linkedin",
                                    external_job_id=str(job_id),
                                    title=title,
                                    company=company,
                                    source_url=source_url,
                                )
                            )
                        except Exception:
                            pass
                    return {"status": "SUBMITTED"}

            # Check for Review button
            review_buttons = driver.find_elements(By.XPATH, MODAL_REVIEW_BUTTON_XPATH)
            clicked_review = False
            for r_btn in review_buttons:
                if r_btn.is_displayed():
                    human_click(driver, r_btn, smooth_scroll=True, dwell_before=True)
                    human_delay(0.6, 1.4, action="click")
                    clicked_review = True
                    break

            if clicked_review:
                continue

            # Check for Next button
            next_buttons = driver.find_elements(By.XPATH, MODAL_NEXT_BUTTON_XPATH)
            clicked_next = False
            for n_btn in next_buttons:
                if n_btn.is_displayed():
                    human_click(driver, n_btn, smooth_scroll=True, dwell_before=True)
                    human_delay(0.6, 1.4, action="click")
                    clicked_next = True
                    break

            if not clicked_next:
                # Neither Next, Review, nor Submit was found/clickable
                break

        # If reached here without submitting, modal requires manual input or encountered error
        print_lg(f"[LinkedInApplier] Could not automatically complete application for {job_id}. Discarding modal.")
        self.discard_modal()
        self.tracker.record_state(
            {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
            state="MANUAL_REQUIRED",
            failure_reason="Unanswered screening questions or complex form step",
            user_id=self.user_id,
        )
        return {"status": "MANUAL_REQUIRED", "reason": "Unanswered screening questions"}
