'''
Humanoid Behavior & Dynamic Delay Engine
Provides human-like interaction cadence:
- Gaussian and randomized jitter delays
- Natural keystroke intervals with pause on punctuation and spaces
- Smooth micro-scrolling and review dwell time
- Humanoid clicks with aim dwell and scroll-into-view
'''

import os
import sys
import time
import random
from typing import Optional, Any
from selenium.webdriver.common.keys import Keys


def _is_testing() -> bool:
    """Detects if execution is running in automated unit test mode."""
    if os.environ.get("TESTING") == "1" or os.environ.get("UNIT_TEST") == "1":
        return True
    if any("unittest" in arg or "pytest" in arg for arg in sys.argv):
        return True
    return False


def human_delay(
    min_s: float = 0.8,
    max_s: float = 2.0,
    action: str = "default",
    testing_override: Optional[float] = None,
) -> float:
    """Calculates and sleeps for a natural, human-like delay with Gaussian jitter.

    Action presets:
    - "keystroke": ~0.04s - 0.11s (typing cadence)
    - "click": ~0.5s - 1.2s (reaction time before/after click)
    - "review": ~1.5s - 3.2s (reading form/summary before submitting)
    - "page_load": ~1.8s - 3.5s (waiting for page transition)
    - "scroll": ~0.3s - 0.8s (pause during reading/scrolling)
    - "default": uses min_s and max_s
    """
    if testing_override is not None:
        if testing_override > 0:
            time.sleep(testing_override)
        return testing_override

    if _is_testing():
        sleep_dur = 0.001
        time.sleep(sleep_dur)
        return sleep_dur

    if action == "keystroke":
        min_s, max_s = 0.035, 0.110
    elif action == "click":
        min_s, max_s = 0.50, 1.25
    elif action == "review":
        min_s, max_s = 1.50, 3.20
    elif action == "page_load":
        min_s, max_s = 1.80, 3.50
    elif action == "scroll":
        min_s, max_s = 0.30, 0.80

    mean = (min_s + max_s) / 2.0
    sigma = (max_s - min_s) / 4.0
    delay = random.gauss(mean, sigma)
    delay = max(min_s, min(max_s, delay))

    time.sleep(delay)
    return delay


def human_type(
    element: Any,
    text: str,
    clear_first: bool = True,
    driver: Optional[Any] = None,
    trigger_events: bool = True,
) -> bool:
    """Types text character by character with micro-jitter and pauses on punctuation/spaces.

    Emulates real human cognitive cadence, and ensures reactive frameworks
    (React, Vue, Angular) register input events.
    """
    if not element or text is None:
        return False

    str_val = str(text)

    # In testing mode, type instantly to keep test suites fast
    if _is_testing():
        try:
            if clear_first:
                try:
                    element.clear()
                except Exception:
                    pass
            element.send_keys(str_val)
            if driver and trigger_events:
                try:
                    driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true})); "
                        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                        element,
                    )
                except Exception:
                    pass
            return True
        except Exception:
            return False

    # 1. Clear field if requested
    if clear_first:
        try:
            element.clear()
        except Exception:
            pass
        try:
            element.send_keys(Keys.CONTROL + "a")
            element.send_keys(Keys.BACKSPACE)
        except Exception:
            pass
        time.sleep(random.uniform(0.1, 0.25))

    # 2. Type character-by-character with jitter
    for i, char in enumerate(str_val):
        try:
            element.send_keys(char)
        except Exception:
            # Fallback to direct value assignment
            if driver:
                try:
                    driver.execute_script("arguments[0].value = arguments[1];", element, str_val)
                except Exception:
                    pass
            break

        # Cadence delay: longer pauses on punctuation and spaces
        if char in ".,!?;:\n":
            time.sleep(random.uniform(0.12, 0.24))
        elif char == " ":
            time.sleep(random.uniform(0.06, 0.15))
        else:
            time.sleep(random.uniform(0.03, 0.09))

    # 3. Trigger DOM events for dynamic form frameworks
    if driver and trigger_events:
        try:
            driver.execute_script(
                "arguments[0].dispatchEvent(new Event('input', {bubbles: true})); "
                "arguments[0].dispatchEvent(new Event('change', {bubbles: true})); "
                "arguments[0].dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));",
                element,
            )
        except Exception:
            pass

    time.sleep(random.uniform(0.15, 0.35))
    return True


def smooth_scroll(driver: Optional[Any], element: Any, block: str = "center") -> None:
    """Smoothly scrolls element into viewport."""
    if not driver or not element:
        return
    try:
        driver.execute_script(
            f"arguments[0].scrollIntoView({{behavior: 'smooth', block: '{block}'}});",
            element,
        )
    except Exception:
        pass


def human_click(
    driver: Optional[Any],
    element: Any,
    smooth_scroll: bool = True,
    dwell_before: bool = True,
) -> bool:
    """Executes a human-like click with smooth scroll-into-view, aim dwell, and JS fallback."""
    if not element:
        return False

    if smooth_scroll and driver:
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element,
            )
        except Exception:
            pass

    if dwell_before and not _is_testing():
        human_delay(0.25, 0.65, action="click")

    clicked = False
    try:
        element.click()
        clicked = True
    except Exception:
        if driver:
            try:
                driver.execute_script("arguments[0].removeAttribute('disabled'); arguments[0].click();", element)
                clicked = True
            except Exception:
                pass

    if not _is_testing():
        human_delay(0.20, 0.50, action="click")

    return clicked


def human_review_dwell(
    driver: Optional[Any],
    min_s: float = 1.2,
    max_s: float = 2.8,
) -> None:
    """Simulates a candidate reviewing form contents before final submission.

    Executes subtle micro-scrolling up and back to establish higher trust score
    with behavioral anti-bot classifiers (reCAPTCHA v3 / Cloudflare Turnstile).
    """
    if _is_testing():
        return

    if driver:
        try:
            # Micro-scroll up slightly
            driver.execute_script("window.scrollBy({top: -70, behavior: 'smooth'});")
            time.sleep(random.uniform(0.4, 0.7))
            # Micro-scroll back down
            driver.execute_script("window.scrollBy({top: 70, behavior: 'smooth'});")
            time.sleep(random.uniform(0.5, 0.9))
        except Exception:
            pass

    human_delay(min_s=min_s, max_s=max_s, action="review")


def cycle_sleep(
    duration_minutes: float,
    platform_name: str = "",
    stop_check: Optional[Any] = None,
    log_callback: Optional[Any] = None,
    step_s: float = 1.0,
) -> bool:
    """Executes a configurable sleeping mode delay between automation cycles.

    - Responsive: Polls stop_check() at 1-second step intervals.
    - Test-safe: Skips instantly in unit tests to ensure fast testing suites.
    - Transparent: Emits countdown logs at milestone intervals.

    Returns:
        True if sleep completed naturally, False if interrupted early by stop_check.
    """
    def _log(msg: str):
        try:
            from modules.helpers import print_lg
            print_lg(msg)
        except Exception:
            print(msg)
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    if _is_testing():
        _log(f"[{platform_name.upper() or 'BOT'}] Sleeping Mode: Testing mode detected, skipping sleep.")
        return True

    if duration_minutes <= 0:
        _log(f"[{platform_name.upper() or 'BOT'}] Sleeping Mode disabled (0 min). Continuing to next cycle.")
        return True

    total_seconds = duration_minutes * 60.0
    prefix = f"[{platform_name.upper()}] " if platform_name else ""
    _log(f"{prefix}💤 Entering Sleeping Mode for {duration_minutes:.1f} min ({int(total_seconds)}s) before next cycle...")

    elapsed = 0.0
    last_logged_min = int(duration_minutes)

    while elapsed < total_seconds:
        if stop_check and stop_check():
            _log(f"{prefix}Sleeping Mode interrupted by stop request.")
            return False

        current_step = min(step_s, total_seconds - elapsed)
        time.sleep(current_step)
        elapsed += current_step

        remaining_s = total_seconds - elapsed
        remaining_min = int(remaining_s // 60)

        # Log milestone updates: 10m, 5m, 2m, 1m, 30s
        if remaining_s > 0 and remaining_min != last_logged_min:
            if remaining_min in [10, 5, 2, 1] or (remaining_min < 1 and int(remaining_s) in [30, 15]):
                last_logged_min = remaining_min
                rem_text = f"{remaining_min} min" if remaining_min > 0 else f"{int(remaining_s)}s"
                _log(f"{prefix}💤 Sleeping Mode: {rem_text} remaining before next cycle...")

    _log(f"{prefix}⏰ Sleeping Mode completed. Starting next automation cycle!")
    return True

