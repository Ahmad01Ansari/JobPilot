'''
Naukri Browser Session Management
Manages isolated Chrome sessions with persistent profile for Naukri.com.
Profile directory: ~/.jobpilot-naukri-profile (with legacy fallback)
'''

import os
import sys
import re
import time
import subprocess
from typing import Optional, Literal, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

import undetected_chromedriver as uc
from platforms.naukri.selectors import (
    LOGIN_URL,
    HOME_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    LOGIN_ERROR_SELECTORS,
    CAPTCHA_SELECTORS,
    OTP_SELECTORS,
)
from modules.helpers import print_lg, make_directories
from config.settings import run_in_background, stealth_mode, disable_extensions
from modules.stealth import apply_stealth_to_driver
from modules.human_behavior import human_delay, human_type, human_click
from modules.captcha_detector import CaptchaDetector


def get_default_naukri_profile_dir() -> str:
    """Returns persistent profile directory for Naukri (~/.jobpilot-naukri-profile)."""
    return os.path.expanduser("~/.jobpilot-naukri-profile")


DEFAULT_NAUKRI_PROFILE_DIR = get_default_naukri_profile_dir()


def _cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Removes stale Chrome lock files (SingletonLock, SingletonCookie, SingletonSocket) if not in use."""
    from modules.browser_lock import cleanup_stale_profile_locks
    cleanup_stale_profile_locks(profile_dir)


class NaukriBrowser:
    """Manages dedicated browser instance and authentication states for Naukri.com."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        headless: Optional[bool] = None,
        stealth: bool = True,
        **kwargs,
    ):
        self.profile_dir = profile_dir or DEFAULT_NAUKRI_PROFILE_DIR
        self.headless = headless if headless is not None else run_in_background
        self.stealth = stealth
        self.driver: Optional[uc.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.actions: Optional[ActionChains] = None

    @staticmethod
    def _get_chrome_major_version() -> Optional[int]:
        """Detects installed Chrome major version on host system."""
        commands: list[list[str]] = []
        if os.name == "nt":
            commands.extend([
                [r"C:\Program Files\Google\Chrome\Application\chrome.exe", "--version"],
                [r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "--version"]
            ])
        elif sys.platform == "darwin":
            commands.append(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"])
        else:
            commands.extend([["google-chrome", "--version"], ["google-chrome-stable", "--version"], ["chromium", "--version"]])

        for command in commands:
            try:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=5)
                output = (completed.stdout or completed.stderr or "").strip()
                match = re.search(r"(\d+)\.\d+\.\d+\.\d+", output)
                if match:
                    return int(match.group(1))
            except Exception:
                continue
        return None

    def start(self) -> None:
        """Starts an isolated undetected Chrome session using the Naukri profile."""
        make_directories([self.profile_dir])
        _cleanup_stale_profile_locks(self.profile_dir)

        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'

        # Block browser-level permission prompts (Location / Geolocation and Notifications)
        prefs = {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.popups": 1,
        }
        options.add_experimental_option("prefs", prefs)
        options.add_argument("--start-maximized")
        options.add_argument("--deny-permission-prompts")
        options.add_argument("--disable-geolocation")
        options.add_argument("--disable-popup-blocking")

        if disable_extensions:
            options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        chrome_major = self._get_chrome_major_version()
        
        try:
            if chrome_major:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                    version_main=chrome_major
                )
            else:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless
                )
        except Exception as e:
            print_lg(f"[NaukriBrowser] Initial Chrome launch failed ({e}), attempting lock cleanup retry...")
            _cleanup_stale_profile_locks(self.profile_dir)
            time.sleep(2)
            if chrome_major:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                    version_main=chrome_major
                )
            else:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless
                )

        self.driver.maximize_window()
        try:
            self.driver.set_page_load_timeout(35)
        except Exception:
            pass

        self.wait = WebDriverWait(self.driver, 10)
        self.actions = ActionChains(self.driver)
        apply_stealth_to_driver(self.driver)
        print_lg(f"[NaukriBrowser] Started Chrome with profile: {self.profile_dir}")

    def navigate(self, url: str, timeout: int = 30) -> bool:
        """Navigates to URL with eager page-load strategy, timeout handling, and popup auto-dismissal."""
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")
        from app.services.security.url_validator import is_safe_url
        is_safe, reason = is_safe_url(url, allow_local_ai=False)
        if not is_safe:
            print_lg(f"[NaukriBrowser] Security blocked navigation to {url}: {reason}")
            return False
        try:
            self.driver.get(url)
            try:
                from platforms.naukri.recovery import dismiss_unexpected_popups
                dismiss_unexpected_popups(self.driver)
            except Exception:
                pass
            return True
        except TimeoutException:
            # Eager strategy triggers timeout after DOM interactive, which is safe to proceed
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass
            try:
                from platforms.naukri.recovery import dismiss_unexpected_popups
                dismiss_unexpected_popups(self.driver)
            except Exception:
                pass
            return True
        except Exception as e:
            print_lg(f"[NaukriBrowser] Navigation error to {url}: {e}")
            return False

    def check_session_state(self) -> Literal["LOGGED_IN", "LOGIN_REQUIRED", "CAPTCHA", "OTP_REQUIRED", "UNKNOWN"]:
        """Inspects DOM to determine authentication and anti-bot state."""
        if not self.driver:
            return "UNKNOWN"

        # 1. Check CAPTCHA / Anti-bot Challenge first (requires MANUAL_REQUIRED)
        detector = CaptchaDetector(platform="naukri")
        is_cap, _ = detector.is_captcha_present(self.driver, platform="naukri")
        if is_cap and not detector.is_captcha_solved(self.driver, platform="naukri"):
            return "CAPTCHA"

        for sel in CAPTCHA_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "CAPTCHA"
            except Exception:
                pass

        # 2. Check OTP / 2FA checkpoint
        for sel in OTP_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "OTP_REQUIRED"
            except Exception:
                pass

        # 3. Quick URL-based LOGGED_IN signal: mnjuser paths are only accessible when authenticated
        current_url = (self.driver.current_url or "").lower()
        if "mnjuser" in current_url:
            return "LOGGED_IN"

        # 4. Check Login Required indicators
        # If Login / Register buttons or login form inputs are visible, the session is definitely unauthenticated
        for sel in LOGIN_REQUIRED_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                pass

        # XPath check for prominent header Login/Register buttons only
        # Use parent context to avoid matching footer/sidebar links
        try:
            unauth_elems = self.driver.find_elements(
                By.XPATH,
                "//a[@id='login_Layer'] | //header//a[normalize-space(text())='Login'] | //header//button[normalize-space(text())='Login'] | //header//a[normalize-space(text())='Register'] | //header//button[normalize-space(text())='Register'] | //nav//a[normalize-space(text())='Login'] | //nav//a[normalize-space(text())='Register']"
            )
            if any(e.is_displayed() for e in unauth_elems):
                return "LOGIN_REQUIRED"
        except Exception:
            pass

        # Check URL path for login page
        if "nlogin" in current_url or "/login" in current_url:
            return "LOGIN_REQUIRED"

        # 5. Check Logged In DOM indicators (must be actually visible and displayed)
        for sel in LOGGED_IN_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGGED_IN"
            except Exception:
                pass

        return "UNKNOWN"

    def is_logged_in(self) -> bool:
        """Returns True if the current session state is LOGGED_IN."""
        return self.check_session_state() == "LOGGED_IN"

    def login(self, username: str, password: str, timeout: int = 15) -> Tuple[bool, str]:
        """Attempts credential login on Naukri.com.
        If CAPTCHA or OTP challenge is encountered, safely returns False and halts automated bypass.
        """
        if self.is_logged_in():
            return (True, "Already logged in.")

        from platforms.naukri.selectors import (
            LOGIN_USERNAME_INPUT,
            LOGIN_PASSWORD_INPUT,
            LOGIN_SUBMIT_BUTTON,
        )

        self.navigate(LOGIN_URL)
        time.sleep(2)

        state = self.check_session_state()
        if state in ["CAPTCHA", "OTP_REQUIRED"]:
            return (False, f"Challenge encountered ({state}). Manual intervention required.")

        try:
            # Locate username input with fallbacks
            user_elem = None
            username_selectors = [
                LOGIN_USERNAME_INPUT,
                "#usernameField",
                "input[placeholder*='Email']",
                "input[placeholder*='Username']",
                "input[type='text']",
                "input[name='email']",
                "input[name='username']",
            ]
            for u_sel in username_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, u_sel)
                    for e in elems:
                        if e.is_displayed():
                            user_elem = e
                            break
                    if user_elem:
                        break
                except Exception:
                    continue

            if not user_elem:
                return (False, "Username input field not found on login page.")

            human_type(user_elem, username, clear_first=True, driver=self.driver)
            human_delay(0.4, 0.8, action="click")

            # Locate password input with fallbacks
            pwd_elem = None
            password_selectors = [
                LOGIN_PASSWORD_INPUT,
                "#passwordField",
                "input[placeholder*='Password']",
                "input[type='password']",
                "input[name='password']",
            ]
            for p_sel in password_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, p_sel)
                    for e in elems:
                        if e.is_displayed():
                            pwd_elem = e
                            break
                    if pwd_elem:
                        break
                except Exception:
                    continue

            if not pwd_elem:
                return (False, "Password input field not found on login page.")

            human_type(pwd_elem, password, clear_first=True, driver=self.driver)
            human_delay(0.5, 1.0, action="click")

            # Locate and click submit
            sub_elem = None
            submit_selectors = [
                LOGIN_SUBMIT_BUTTON,
                "button.loginButton",
                "button[type='submit'].btn-primary",
                "button[type='submit']",
                "button.btn-primary",
            ]
            for s_sel in submit_selectors:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, s_sel)
                    for e in elems:
                        if e.is_displayed():
                            sub_elem = e
                            break
                    if sub_elem:
                        break
                except Exception:
                    continue

            if sub_elem:
                human_click(self.driver, sub_elem, smooth_scroll=True, dwell_before=True)
            else:
                pwd_elem.send_keys(Keys.RETURN)

            # Wait for session state transition
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(1)

                # Check for on-page login error messages
                for err_sel in LOGIN_ERROR_SELECTORS:
                    try:
                        err_elems = self.driver.find_elements(By.CSS_SELECTOR, err_sel)
                        for ee in err_elems:
                            if ee.is_displayed() and ee.text.strip():
                                return (False, f"Login failed: {ee.text.strip()}")
                    except Exception:
                        pass

                st = self.check_session_state()
                if st == "LOGGED_IN":
                    return (True, "Login successful.")
                elif st in ["CAPTCHA", "OTP_REQUIRED"]:
                    return (False, f"Challenge presented ({st}). Manual intervention required.")

            if self.is_logged_in():
                return (True, "Login successful.")
            return (False, "Login timeout or unconfirmed credentials.")
        except Exception as e:
            return (False, f"Login exception: {e}")

    def ensure_authenticated(self, max_wait_seconds: int = 180) -> bool:
        """Verifies session. If login is required or CAPTCHA appears, triggers MANUAL_REQUIRED route.
        Never attempts automated bypass of security checkpoints.
        """
        state = self.check_session_state()

        if state == "LOGGED_IN":
            print_lg("[NaukriBrowser] Existing session is active (LOGGED_IN).")
            return True

        current_url = (self.driver.current_url if self.driver else "").lower()
        if "login" not in current_url and state not in ["CAPTCHA", "OTP_REQUIRED"]:
            self.navigate(LOGIN_URL)

        if state in ["CAPTCHA", "OTP_REQUIRED"]:
            print_lg(f"[NaukriBrowser] MANUAL_REQUIRED: Encountered {state}. Please resolve manually in browser.")
        else:
            print_lg("[NaukriBrowser] MANUAL_REQUIRED: Please complete login/OTP in the open Chrome browser.")

        return self._wait_for_manual_resolution(max_wait_seconds)

    def _wait_for_manual_resolution(self, max_wait_seconds: int) -> bool:
        """Waits for human user to complete login or CAPTCHA in browser window."""
        detector = CaptchaDetector(platform="naukri")
        is_cap, _ = detector.is_captcha_present(self.driver, platform="naukri")
        if is_cap and not detector.is_captcha_solved(self.driver, platform="naukri"):
            resolved = detector.handle_captcha(
                self.driver,
                platform="naukri",
                timeout=max_wait_seconds,
            )
            if resolved and self.is_logged_in():
                return True

        print_lg(f"[NaukriBrowser] Waiting up to {max_wait_seconds}s for authentication completion in browser...")
        start_time = time.time()
        last_logged = 0
        while time.time() - start_time < max_wait_seconds:
            time.sleep(2)
            if self.is_logged_in():
                print_lg("[NaukriBrowser] Authentication confirmed! Session saved to profile.")
                return True
            elapsed = int(time.time() - start_time)
            if elapsed - last_logged >= 15:
                remaining = max_wait_seconds - elapsed
                print_lg(f"[NaukriBrowser] Still waiting for login in browser ({remaining}s remaining)...")
                last_logged = elapsed

        print_lg("[NaukriBrowser] Authentication timed out. Session not confirmed.")
        return False

    def is_alive(self) -> bool:
        """Checks if browser window is alive and reachable."""
        if not self.driver:
            return False
        try:
            _ = self.driver.title
            return True
        except Exception:
            return False

    def quit(self) -> None:
        """Alias for close()."""
        self.close()

    def close(self) -> None:
        """Gracefully shuts down the browser."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            finally:
                self.driver = None
                self.wait = None
                self.actions = None
                _cleanup_stale_profile_locks(self.profile_dir)
                print_lg("[NaukriBrowser] Browser session closed.")
