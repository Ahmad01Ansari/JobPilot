'''
Indeed Browser Session Management
Manages isolated Chrome sessions with persistent profile for Indeed India (in.indeed.com).
Profile directory: ~/.jobpilot-indeed-profile
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
from platforms.indeed.selectors import (
    HOME_URL,
    LOGIN_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    LOGIN_EMAIL_INPUT,
    LOGIN_CONTINUE_BUTTON,
    SIGN_IN_WITH_CODE_LINK,
    OTP_PASSCODE_INPUT,
    OTP_SUBMIT_BUTTON,
    PASSKEY_NOT_NOW_BUTTON,
    COOKIE_ACCEPT_BUTTON,
)
from modules.helpers import print_lg, make_directories
from config.settings import run_in_background, stealth_mode, disable_extensions


def get_default_indeed_profile_dir() -> str:
    """Returns persistent profile directory for Indeed (~/.jobpilot-indeed-profile)."""
    return os.path.expanduser("~/.jobpilot-indeed-profile")


DEFAULT_INDEED_PROFILE_DIR = get_default_indeed_profile_dir()


def _cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Removes stale Chrome lock files if not in use."""
    from modules.browser_lock import cleanup_stale_profile_locks
    cleanup_stale_profile_locks(profile_dir)


class IndeedBrowser:
    """Manages dedicated browser instance and authentication states for Indeed."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        headless: Optional[bool] = None,
        stealth: bool = True,
        **kwargs,
    ):
        self.profile_dir = profile_dir or DEFAULT_INDEED_PROFILE_DIR
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
        """Starts an isolated undetected Chrome session using the Indeed profile."""
        make_directories([self.profile_dir])
        _cleanup_stale_profile_locks(self.profile_dir)

        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'

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
        options.add_argument("--window-size=1600,1000")

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
            print_lg(f"[IndeedBrowser] Initial Chrome launch failed ({e}), attempting lock cleanup retry...")
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
        print_lg(f"[IndeedBrowser] Started Chrome with profile: {self.profile_dir}")

    def dismiss_alerts_and_popups(self) -> None:
        """Dismisses any unexpected JavaScript alerts or popover modals."""
        if not self.driver:
            return
        try:
            alert = self.driver.switch_to.alert
            print_lg(f"[IndeedBrowser] Dismissed alert: {alert.text}")
            alert.accept()
        except Exception:
            pass

        # Dismiss passkey prompt if present
        for sel in PASSKEY_NOT_NOW_BUTTON:
            try:
                for el in self.driver.find_elements(By.XPATH, sel):
                    if el.is_displayed():
                        print_lg("[IndeedBrowser] Dismissing Passkey prompt ('Not now')...")
                        self.driver.execute_script("arguments[0].click();", el)
                        break
            except Exception:
                pass

        # Dismiss cookie banners if present
        for c_sel in COOKIE_ACCEPT_BUTTON:
            try:
                for cb in self.driver.find_elements(By.XPATH, c_sel):
                    if cb.is_displayed():
                        self.driver.execute_script("arguments[0].click();", cb)
                        break
            except Exception:
                pass

    def navigate(self, url: str, timeout: int = 30) -> bool:
        """Navigates to URL with eager page-load strategy and popup handling."""
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")
        from app.services.security.url_validator import is_safe_url
        is_safe, reason = is_safe_url(url, allow_local_ai=False)
        if not is_safe:
            print_lg(f"[IndeedBrowser] Security blocked navigation to {url}: {reason}")
            return False
        try:
            self.driver.get(url)
            self.dismiss_alerts_and_popups()
            return True
        except TimeoutException:
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass
            self.dismiss_alerts_and_popups()
            return True
        except Exception as e:
            print_lg(f"[IndeedBrowser] Navigation error to {url}: {e}")
            return False

    def check_session_state(self) -> Literal["LOGGED_IN", "LOGIN_REQUIRED", "OTP_REQUIRED", "PASSKEY", "UNKNOWN"]:
        """Inspects DOM to determine authentication state."""
        if not self.driver:
            return "UNKNOWN"

        self.dismiss_alerts_and_popups()

        cur_url = (self.driver.current_url or "").lower()

        # Check if passkey prompt is active
        try:
            if "passkey" in self.driver.page_source.lower() and any(
                el.is_displayed() for el in self.driver.find_elements(By.XPATH, "//button[contains(., 'passkey')] | //*[text()='Not now']")
            ):
                return "PASSKEY"
        except Exception:
            pass

        # Check if OTP code entry screen is active
        try:
            for otp_sel in OTP_PASSCODE_INPUT:
                elems = self.driver.find_elements(By.CSS_SELECTOR, otp_sel)
                if any(e.is_displayed() for e in elems):
                    return "OTP_REQUIRED"
        except Exception:
            pass

        # Check if logged in
        if "auth" not in cur_url:
            for sel in LOGGED_IN_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    if any(e.is_displayed() for e in elems):
                        return "LOGGED_IN"
                except Exception:
                    pass

        # Check if login is explicitly required
        for req_sel in LOGIN_REQUIRED_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH, req_sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                pass

        if "secure.indeed.com/auth" in cur_url or "secure.indeed.com/account/login" in cur_url:
            return "LOGIN_REQUIRED"

        return "UNKNOWN"

    def is_logged_in(self) -> bool:
        """Returns True if the current session state is LOGGED_IN."""
        return self.check_session_state() == "LOGGED_IN"

    def ensure_authenticated(self, email: Optional[str] = None, max_wait_seconds: int = 180) -> bool:
        """Verifies session. If login is required, triggers Email + Login Code flow."""
        self.navigate(HOME_URL)
        time.sleep(2)

        if self.is_logged_in():
            print_lg("[IndeedBrowser] Active authenticated session confirmed.")
            return True

        if not email:
            try:
                from modules.config_loader import load_profile
                prof = load_profile()
                email = prof.get("personal", {}).get("email") or prof.get("personal_information", {}).get("email")
            except Exception:
                pass

        print_lg("[IndeedBrowser] Session not authenticated. Initiating Email + Code login...")
        self.navigate(LOGIN_URL)
        time.sleep(3)
        self.dismiss_alerts_and_popups()

        state = self.check_session_state()
        if state == "PASSKEY":
            self.dismiss_alerts_and_popups()
            time.sleep(2)
            if self.is_logged_in():
                return True

        # Locate email input
        email_elem = None
        for sel in LOGIN_EMAIL_INPUT:
            try:
                for el in self.driver.find_elements(By.XPATH, sel):
                    if el.is_displayed():
                        email_elem = el
                        break
                if email_elem:
                    break
            except Exception:
                pass

        if email_elem and email:
            print_lg(f"[IndeedBrowser] Entering email: {email}...")
            email_elem.clear()
            for ch in email:
                email_elem.send_keys(ch)
                time.sleep(0.02)
            time.sleep(1)

            # Submit email
            for c_sel in LOGIN_CONTINUE_BUTTON:
                try:
                    for cb in self.driver.find_elements(By.XPATH, c_sel):
                        if cb.is_displayed():
                            self.driver.execute_script("arguments[0].click();", cb)
                            break
                except Exception:
                    pass

            time.sleep(4)
            self.dismiss_alerts_and_popups()

            # Click 'Sign in with a code instead'
            code_link = None
            for _ in range(10):
                time.sleep(1)
                for sel in SIGN_IN_WITH_CODE_LINK:
                    try:
                        for el in self.driver.find_elements(By.XPATH, sel):
                            if el.is_displayed():
                                code_link = el
                                break
                        if code_link:
                            break
                    except Exception:
                        pass
                if code_link:
                    break

            if code_link:
                print_lg("[IndeedBrowser] Clicking 'Sign in with a code instead'...")
                self.driver.execute_script("arguments[0].click();", code_link)
                time.sleep(3)

        print_lg("="*70)
        print_lg(f"[IndeedBrowser] OTP SENT TO {email}!")
        print_lg(f"[IndeedBrowser] Waiting up to {max_wait_seconds}s for verification in browser...")
        print_lg("="*70)

        start = time.time()
        while time.time() - start < max_wait_seconds:
            time.sleep(2)
            self.dismiss_alerts_and_popups()

            if self.is_logged_in():
                print_lg("[IndeedBrowser] Successfully authenticated! Session saved to profile.")
                return True

            rem = int(max_wait_seconds - (time.time() - start))
            if rem % 15 == 0:
                print_lg(f"[IndeedBrowser] Waiting for login completion ({rem}s remaining)...")

        print_lg("[IndeedBrowser] Authentication timed out.")
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
                print_lg("[IndeedBrowser] Browser session closed.")
