'''
Indeed Submission & Verification Engine
Executes final application submission on approved Indeed jobs.
Verifies confirmation indicators ('Your application was submitted to <Company>')
and safely closes the application tab before returning to search.
'''

import time
from typing import Optional, Tuple, Any, Callable
from selenium.webdriver.common.by import By

from modules.helpers import print_lg
from platforms.indeed.selectors import (
    FINAL_SUBMIT_BUTTONS,
    CONFIRMATION_HEADINGS,
    RETURN_TO_SEARCH_BUTTON,
    SPINNER_SELECTORS,
)
from platforms.indeed.captcha_handler import IndeedCaptchaHandler


class IndeedSubmitter:
    """Handles final submission execution and post-click verification on Indeed."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[Any] = None,
        automation_bridge: Optional[Any] = None,
        captcha_handler: Optional[IndeedCaptchaHandler] = None,
    ):
        self.browser = browser
        self.tracker = tracker
        self.automation_bridge = automation_bridge
        self.captcha_handler = captcha_handler or IndeedCaptchaHandler(browser, automation_bridge)

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def wait_for_spinner(self, timeout: int = 10) -> None:
        """Waits for loading spinners or overlays to clear."""
        if not self.driver:
            return
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.5)
            spinners = []
            for sel in SPINNER_SELECTORS:
                try:
                    spinners.extend(self.driver.find_elements(By.XPATH, sel))
                except Exception:
                    pass
            if not any(s.is_displayed() for s in spinners):
                break

    def find_submit_button(self, timeout: int = 15) -> Optional[Any]:
        """Polls with scrolling to locate the primary submit button on the review screen."""
        if not self.driver:
            return None

        self.wait_for_spinner(timeout=5)
        start = time.time()

        while time.time() - start < timeout:
            # 1. Scroll down to bottom of page to trigger rendering of bottom buttons
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception:
                pass

            # 2. Check XPaths in FINAL_SUBMIT_BUTTONS
            for sel in FINAL_SUBMIT_BUTTONS:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        try:
                            # Scroll element into center
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                            time.sleep(0.3)
                            if el.is_displayed():
                                return el
                        except Exception:
                            return el
                except Exception:
                    continue

            # 3. Dynamic JavaScript query across buttons, links, and divs
            try:
                js_btn = self.driver.execute_script("""
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
                if js_btn:
                    return js_btn
            except Exception:
                pass

            time.sleep(1)

        return None

    def verify_confirmation(
        self,
        timeout: int = 25,
        job_title: str = "",
        company: str = "",
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, str]:
        """Polls for application submission confirmation banner, handling potential CAPTCHA challenges."""
        if not self.driver:
            return (False, "No active driver session.")

        start = time.time()
        while time.time() - start < timeout:
            if stop_check and stop_check():
                return (False, "Operation paused or stopped by user.")

            time.sleep(1)

            # Check if a post-submit CAPTCHA was triggered
            if self.captcha_handler.is_captcha_present(self.driver) and not self.captcha_handler.is_captcha_solved(self.driver):
                print_lg("[IndeedSubmitter] ⚠️ CAPTCHA challenge triggered after submit click!")
                solved = self.captcha_handler.handle_captcha(
                    self.driver,
                    job_title=job_title,
                    company=company,
                    timeout=60,
                    stop_check=stop_check,
                    automation_bridge=self.automation_bridge,
                )
                if solved:
                    print_lg("[IndeedSubmitter] Re-clicking submit button following CAPTCHA resolution...")
                    retry_btn = self.find_submit_button(timeout=5)
                    if retry_btn:
                        self.driver.execute_script("arguments[0].click();", retry_btn)
                        time.sleep(3)
                else:
                    return (False, "CAPTCHA challenge encountered on Indeed. Manual intervention required.")

            # 1. Check explicit confirmation headings
            for sel in CONFIRMATION_HEADINGS:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed() and el.text.strip():
                            msg = el.text.strip()
                            print_lg(f"[IndeedSubmitter] Confirmation verified: '{msg}'")
                            return (True, msg)
                except Exception:
                    pass

            # 2. Check for Return to job search button on confirmation screen
            for sel in RETURN_TO_SEARCH_BUTTON:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            print_lg("[IndeedSubmitter] Confirmation verified via 'Return to job search' screen.")
                            return (True, "Your application was submitted.")
                except Exception:
                    pass

            # 3. Check page body text
            try:
                body_text = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
                if "application was submitted" in body_text or "application submitted" in body_text:
                    print_lg("[IndeedSubmitter] Confirmation verified in page body text.")
                    return (True, "Your application was submitted.")
            except Exception:
                pass

            # 4. Check URL for post-apply or confirmation
            try:
                cur_url = (self.driver.current_url or "").lower()
                if "post-apply" in cur_url or "confirmation" in cur_url or "applied" in cur_url:
                    print_lg(f"[IndeedSubmitter] Confirmation verified via URL: '{cur_url}'")
                    return (True, "Your application was submitted.")
            except Exception:
                pass

        return (False, "Submission confirmation not confirmed within timeout.")

    def submit_application(
        self,
        app_window: str,
        main_window: str,
        job_title: str = "",
        company: str = "",
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, str]:
        """Executes submit click, handles CAPTCHA if presented, asserts confirmation, and cleans up tab."""
        print_lg(f"[IndeedSubmitter] Initiating submission for '{job_title}' at '{company}'...")

        try:
            # Ensure focused on application tab
            if self.driver.current_window_handle != app_window:
                self.driver.switch_to.window(app_window)

            if stop_check and stop_check():
                return (False, "Operation paused or stopped by user.")

            # Ensure clean CAPTCHA state on bridge before evaluating new application
            if self.automation_bridge and hasattr(self.automation_bridge, "reset_captcha_status"):
                self.automation_bridge.reset_captcha_status()

            # Check if CAPTCHA challenge is currently displayed on review screen
            if self.captcha_handler.is_captcha_present(self.driver) and not self.captcha_handler.is_captcha_solved(self.driver):
                print_lg("[IndeedSubmitter] ⚠️ CAPTCHA challenge detected on review page!")
                solved = self.captcha_handler.handle_captcha(
                    self.driver,
                    job_title=job_title,
                    company=company,
                    timeout=60,
                    stop_check=stop_check,
                    automation_bridge=self.automation_bridge,
                )
                if not solved:
                    return (False, "CAPTCHA challenge encountered on Indeed. Manual intervention required.")

            print_lg("[IndeedSubmitter] Waiting for review page submit button (up to 15s)...")
            submit_btn = self.find_submit_button(timeout=15)
            if not submit_btn:
                # Re-check if CAPTCHA appeared while waiting for submit button
                if self.captcha_handler.is_captcha_present(self.driver) and not self.captcha_handler.is_captcha_solved(self.driver):
                    solved = self.captcha_handler.handle_captcha(
                        self.driver,
                        job_title=job_title,
                        company=company,
                        timeout=60,
                        stop_check=stop_check,
                        automation_bridge=self.automation_bridge,
                    )
                    if solved:
                        submit_btn = self.find_submit_button(timeout=10)

                if not submit_btn:
                    cur_url = getattr(self.driver, "current_url", "unknown")
                    print_lg(f"[IndeedSubmitter] Submit button not found on page: {cur_url}")
                    return (False, f"Final submit button not found on review page ({cur_url}).")

            # Final check: Ensure CAPTCHA is solved before clicking
            if self.captcha_handler.is_captcha_present(self.driver) and not self.captcha_handler.is_captcha_solved(self.driver):
                solved = self.captcha_handler.handle_captcha(
                    self.driver,
                    job_title=job_title,
                    company=company,
                    timeout=60,
                    stop_check=stop_check,
                    automation_bridge=self.automation_bridge,
                )
                if not solved:
                    return (False, "CAPTCHA challenge encountered on Indeed. Manual intervention required.")
                # Re-fetch submit button in case DOM re-rendered upon solving
                submit_btn = self.find_submit_button(timeout=5) or submit_btn

            btn_label = ""
            try:
                btn_label = (submit_btn.text or "").strip()
            except Exception:
                btn_label = "Submit"
            print_lg(f"[IndeedSubmitter] Found submit button ('{btn_label}'). Clicking...")

            # Human dwell time & smooth micro-scrolling to establish high CAPTCHA trust score
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
                time.sleep(1.0)
                # Gentle micro-scroll simulating reading of the review summary
                self.driver.execute_script("window.scrollBy({top: -100, behavior: 'smooth'});")
                time.sleep(0.8)
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", submit_btn)
                time.sleep(1.2)
            except Exception:
                time.sleep(2.5)

            clicked = False
            try:
                submit_btn.click()
                clicked = True
            except Exception:
                pass

            if not clicked:
                try:
                    self.driver.execute_script("arguments[0].click();", submit_btn)
                    clicked = True
                except Exception as e:
                    print_lg(f"[IndeedSubmitter] JS click notice: {e}")

            time.sleep(3)

            # Verify submission confirmation with up to 25s timeout
            success, message = self.verify_confirmation(
                timeout=25,
                job_title=job_title,
                company=company,
                stop_check=stop_check,
            )

            # If not verified yet, check if submit button is still present and re-attempt click once
            if not success:
                try:
                    retry_btn = self.find_submit_button(timeout=2)
                    if retry_btn:
                        print_lg("[IndeedSubmitter] Confirmation not detected yet. Re-attempting submit click via JS...")
                        self.driver.execute_script("arguments[0].click();", retry_btn)
                        success, message = self.verify_confirmation(
                            timeout=15,
                            job_title=job_title,
                            company=company,
                            stop_check=stop_check,
                        )
                except Exception:
                    pass

            if success:
                print_lg(f"[IndeedSubmitter] SUCCESS: Application submitted to {company}!")
                print_lg(
                    f"[APPLICATION_CONFIRMED] Job: '{job_title}' | "
                    f"Company: '{company}' | Platform: 'indeed' | "
                    f"Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                )
                time.sleep(2)
            else:
                print_lg(f"[IndeedSubmitter] WARNING: Confirmation not verified ({message})")

            return (success, message)

        finally:
            # Strictly enforce closing application tab and returning to search window
            try:
                if app_window in self.driver.window_handles:
                    self.driver.switch_to.window(app_window)
                    self.driver.close()
                    print_lg("[IndeedSubmitter] Application tab closed.")
            except Exception as e:
                print_lg(f"[IndeedSubmitter] Tab close notice: {e}")

            try:
                self.driver.switch_to.window(main_window)
                print_lg("[IndeedSubmitter] Successfully returned focus to main search window.")
            except Exception as e:
                print_lg(f"[IndeedSubmitter] Window focus return error: {e}")

    def execute_submission(
        self,
        app_window: Optional[str] = None,
        main_window: Optional[str] = None,
        job_title: str = "",
        company: str = "",
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Alias for submit_application returning boolean success."""
        app_win = app_window or self.driver.current_window_handle
        main_win = main_window or self.driver.window_handles[0]
        success, _ = self.submit_application(
            app_window=app_win,
            main_window=main_win,
            job_title=job_title,
            company=company,
            stop_check=stop_check,
        )
        return success
