'''
Naukri Error Recovery & Resilience Engine (Phase 13)
Provides defensive recovery mechanisms for browser timeouts, stale elements,
unexpected popups/overlays, network delays, session dropouts, and security challenges.
Guarantees every failure transitions cleanly to a controlled state (FAILED, MANUAL_REQUIRED, UNKNOWN, or EXTERNAL)
rather than crashing the application run.
'''

import time
from typing import Tuple, Any, Dict, Callable, Optional
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException,
    ElementNotInteractableException,
    WebDriverException,
)
from selenium.webdriver.common.by import By

from modules.models import Job
from modules.helpers import print_lg
from platforms.naukri.selectors import (
    POPUP_DISMISS_SELECTORS,
    MODAL_CLOSE_BUTTONS,
    CAPTCHA_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    OTP_SELECTORS,
    PROFILE_INCOMPLETE_SELECTORS,
)


def classify_error(exc: Exception, context: str = "general") -> Tuple[str, str]:
    """
    Maps an arbitrary exception and operational context to a controlled
    ApplicationState (FAILED, MANUAL_REQUIRED, UNKNOWN, or EXTERNAL) and a clean reason.

    Guarantees that unknown/unhandled exceptions never crash the runner.
    """
    exc_str = str(exc).lower()
    exc_name = type(exc).__name__

    # 1. Security / Authentication Checkpoints -> MANUAL_REQUIRED
    if any(w in exc_str for w in ["captcha", "recaptcha", "bot-detector", "geetest", "challenge"]):
        return ("MANUAL_REQUIRED", f"Security challenge (CAPTCHA) encountered during {context}")

    if any(w in exc_str for w in ["otp", "2fa", "two-factor", "verification code"]):
        return ("MANUAL_REQUIRED", f"OTP / Two-Factor authentication checkpoint encountered during {context}")

    if any(w in exc_str for w in ["login required", "session expired", "please login", "unauthorized", "sign in"]):
        return ("MANUAL_REQUIRED", f"Authentication session expired or login required during {context}")

    if any(w in exc_str for w in ["profile incomplete", "update profile", "missing mandatory profile"]):
        return ("MANUAL_REQUIRED", f"Incomplete profile modal detected during {context}")

    # 2. External Redirection -> EXTERNAL
    if any(w in exc_str for w in ["external", "company site", "redirected to external portal"]):
        return ("EXTERNAL", f"Application redirected to external portal during {context}: {exc}")

    # 3. Post-Click Submit Timeouts -> UNKNOWN (Strict Idempotency: Never Retry!)
    if context in ("submit", "submission") and (isinstance(exc, TimeoutException) or "timeout" in exc_str):
        return (
            "UNKNOWN",
            f"Submit button was clicked but confirmation timed out; recorded as UNKNOWN to prevent duplicate application: {exc}",
        )

    # 4. Browser / DOM Transient Errors -> FAILED
    if isinstance(exc, TimeoutException) or "timeout" in exc_str:
        return ("FAILED", f"Browser/Network timeout occurred during {context}: {exc_name}")

    if isinstance(exc, StaleElementReferenceException) or "stale" in exc_str:
        return ("FAILED", f"DOM updated or element went stale during {context}")

    if isinstance(exc, ElementClickInterceptedException) or "click intercepted" in exc_str:
        return ("FAILED", f"Click was intercepted by an unexpected popup or overlay during {context}")

    if isinstance(exc, (NoSuchElementException, ElementNotInteractableException)):
        return ("FAILED", f"Target element not interactable or missing during {context}: {exc_name}")

    if isinstance(exc, WebDriverException):
        return ("FAILED", f"WebDriver communication error during {context}: {exc_name}")

    # General Fallback
    return ("FAILED", f"Controlled failure during {context}: {exc_name} - {exc}")


def dismiss_unexpected_popups(driver: Any) -> int:
    """
    Scans the DOM for disruptive overlays, marketing banners, push notification prompts,
    location modals, and survey modals, attempting to dismiss them.
    Returns the count of dismissed popups.
    """
    if not driver:
        return 0

    dismissed_count = 0

    # 1. Selector-based dismiss
    for sel in POPUP_DISMISS_SELECTORS:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for elem in elems:
                if elem.is_displayed():
                    try:
                        elem.click()
                        dismissed_count += 1
                        time.sleep(0.15)
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", elem)
                            dismissed_count += 1
                            time.sleep(0.15)
                        except Exception:
                            continue
        except Exception:
            continue

    # 2. Text-based dismiss for common location & notification action buttons
    dismiss_xpaths = [
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'not now')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'later')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'skip')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'no thanks')]",
        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'cancel')]",
        "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'not now')]",
        "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'later')]",
        "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'skip')]",
        "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'not now')]",
        "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'later')]",
        "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'skip')]",
    ]

    for xp in dismiss_xpaths:
        try:
            elems = driver.find_elements(By.XPATH, xp)
            for elem in elems:
                if elem.is_displayed():
                    try:
                        elem.click()
                        dismissed_count += 1
                        time.sleep(0.15)
                    except Exception:
                        try:
                            driver.execute_script("arguments[0].click();", elem)
                            dismissed_count += 1
                            time.sleep(0.15)
                        except Exception:
                            continue
        except Exception:
            continue

    # 3. Clean up obstructive modal backdrops if no active questionnaire is present
    try:
        driver.execute_script("""
            const backdrops = document.querySelectorAll('.modal-backdrop, .overlay-backdrop');
            backdrops.forEach(b => {
                if (!document.querySelector('.chatbot_DrawerContent, .apply-modal, .form-container')) {
                    b.remove();
                }
            });
        """)
    except Exception:
        pass

    if dismissed_count > 0:
        print_lg(f"[ErrorRecovery] Dismissed {dismissed_count} unexpected popup(s)/overlay(s).")

    return dismissed_count


def retry_on_transient_error(
    func: Callable,
    retries: int = 3,
    delay: float = 0.5,
    driver: Optional[Any] = None,
) -> Any:
    """
    Executes a callable with automatic retries for transient WebDriver exceptions
    (e.g., StaleElementReferenceException or ElementClickInterceptedException).
    If click interception is detected, sweeps unexpected popups before retrying.
    """
    last_exc = None
    for attempt in range(retries):
        try:
            return func()
        except (StaleElementReferenceException, ElementClickInterceptedException) as e:
            last_exc = e
            print_lg(
                f"[ErrorRecovery] Transient error ({type(e).__name__}) on attempt {attempt + 1}/{retries}. Retrying in {delay}s..."
            )
            if driver and isinstance(e, ElementClickInterceptedException):
                dismiss_unexpected_popups(driver)
            time.sleep(delay)
        except Exception as e:
            # Non-transient exceptions are raised immediately
            raise e

    if last_exc:
        raise last_exc


def safe_apply_job(
    applier: Any,
    job: Job,
    job_description: Optional[str] = None,
    work_location: Optional[str] = None,
    card_element: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Safety harness wrapping an entire job application attempt.
    Guarantees:
    1. Pre-execution popup clearance.
    2. Try-catch envelope around all browser operations.
    3. Window/tab state restoration if rogue tabs were opened.
    4. Controlled state mapping (FAILED, MANUAL_REQUIRED, UNKNOWN, EXTERNAL).
    5. No uncaught exception escapes to crash the automation runner.
    """
    driver = getattr(applier, "driver", None)
    initial_windows = list(driver.window_handles) if driver else []

    try:
        # Pre-execution popup sweep
        if driver:
            dismiss_unexpected_popups(driver)

        # Execute application
        return applier.apply_to_job(
            job,
            job_description=job_description,
            work_location=work_location,
            card_element=card_element,
        )

    except Exception as exc:
        state, reason = classify_error(exc, context="safe_apply_job")
        print_lg(f"[ErrorRecovery] Recovered from exception for job '{job.job_id}' -> {state}: {reason}")

        # Restore window state: close any newly opened rogue tabs
        if driver and initial_windows:
            try:
                current_windows = list(driver.window_handles)
                for w in current_windows:
                    if w not in initial_windows:
                        driver.switch_to.window(w)
                        driver.close()
                driver.switch_to.window(initial_windows[0])
            except Exception as e:
                print_lg(f"[ErrorRecovery] Notice restoring window handles: {e}")

        # Dismiss lingering modals to clean page state
        try:
            if hasattr(applier, "flow_detector"):
                applier.flow_detector.close_modal_if_open()
        except Exception:
            pass

        # Update tracker
        if hasattr(applier, "tracker") and applier.tracker:
            applier.tracker.record_state(job, state, reason=reason)

        return {
            "status": state,
            "reason": reason,
            "error": str(exc),
            "recovered": True,
        }
