'''
Foundit Browser Session Management
Manages isolated Chrome sessions with persistent profile for Foundit India (foundit.in).
Profile directory: ~/.jobpilot-foundit-profile
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
from platforms.foundit.selectors import (
    HOME_URL,
    LOGIN_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    CAPTCHA_SELECTORS,
    OTP_SELECTORS,
    HEADER_LOGIN_BUTTONS,
    HEADER_REGISTER_BUTTONS,
    MODAL_CLOSE_BUTTONS,
)
from modules.helpers import print_lg
from config.settings import run_in_background, stealth_mode, disable_extensions
from modules.stealth import apply_stealth_to_driver
from modules.captcha_detector import CaptchaDetector
from modules.human_behavior import human_delay, human_type, human_click


def get_default_foundit_profile_dir() -> str:
    """Returns persistent profile directory for Foundit (~/.jobpilot-foundit-profile)."""
    return os.path.expanduser("~/.jobpilot-foundit-profile")


DEFAULT_FOUNDIT_PROFILE_DIR = get_default_foundit_profile_dir()


def _cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Removes stale Chrome lock files (SingletonLock, SingletonCookie, SingletonSocket) if not in use."""
    from modules.browser_lock import cleanup_stale_profile_locks
    cleanup_stale_profile_locks(profile_dir)


class FounditBrowser:
    """Manages dedicated browser instance and authentication states for Foundit."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        headless: Optional[bool] = None,
        stealth: bool = True,
        user_id: int = 1,
        **kwargs,
    ):
        self.profile_dir = profile_dir or DEFAULT_FOUNDIT_PROFILE_DIR
        self.headless = headless if headless is not None else run_in_background
        self.stealth = stealth
        self.user_id = user_id
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
            commands.extend([
                ["google-chrome", "--version"],
                ["google-chrome-stable", "--version"],
                ["chromium", "--version"]
            ])

        for command in commands:
            try:
                output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True).strip()
                match = re.search(r"(\d+)\.", output)
                if match:
                    return int(match.group(1))
            except Exception:
                continue
        return None

    def start(self) -> uc.Chrome:
        """Starts an isolated Chrome session with persistent profile."""
        if self.driver:
            return self.driver

        os.makedirs(self.profile_dir, exist_ok=True)
        _cleanup_stale_profile_locks(self.profile_dir)

        options = uc.ChromeOptions()
        # Crucial for Foundit: Eager strategy stops blocking on background analytics websockets
        options.page_load_strategy = "eager"

        if self.headless:
            options.add_argument("--headless=new")

        if disable_extensions:
            options.add_argument("--disable-extensions")

        options.add_argument("--window-size=1400,900")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-blink-features=AutomationControlled")

        chrome_version = self._get_chrome_major_version()
        init_kwargs = {
            "user_data_dir": self.profile_dir,
            "options": options,
        }
        if chrome_version:
            init_kwargs["version_main"] = chrome_version

        try:
            self.driver = uc.Chrome(**init_kwargs)
        except Exception as e:
            print_lg(f"[FounditBrowser] Failed to start Chrome with version_main: {e}. Retrying with auto-detect...")
            init_kwargs.pop("version_main", None)
            self.driver = uc.Chrome(**init_kwargs)

        try:
            self.driver.set_page_load_timeout(35)
        except Exception:
            pass

        self.wait = WebDriverWait(self.driver, 10)
        self.actions = ActionChains(self.driver)
        apply_stealth_to_driver(self.driver)
        print_lg(f"[FounditBrowser] Started Chrome with profile: {self.profile_dir}")
        return self.driver

    def dismiss_unexpected_popups(self) -> None:
        """Closes app download prompts or survey overlays if present."""
        if not self.driver:
            return
        for sel in MODAL_CLOSE_BUTTONS:
            try:
                for btn in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
            except Exception:
                pass

    def navigate(self, url: str, timeout: int = 30) -> bool:
        """Navigates to URL with eager page-load strategy and timeout handling."""
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")
        from app.services.security.url_validator import is_safe_url
        is_safe, reason = is_safe_url(url, allow_local_ai=False)
        if not is_safe:
            print_lg(f"[FounditBrowser] Security blocked navigation to {url}: {reason}")
            return False
        try:
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(url)
            self.dismiss_unexpected_popups()
            return True
        except TimeoutException:
            try:
                self.driver.execute_script("window.stop();")
            except Exception:
                pass
            self.dismiss_unexpected_popups()
            return True
        except Exception as e:
            print_lg(f"[FounditBrowser] Navigation error to {url}: {e}")
            return False

    def check_session_state(self) -> Literal["LOGGED_IN", "LOGIN_REQUIRED", "CAPTCHA", "OTP_REQUIRED", "UNKNOWN"]:
        """Inspects DOM to determine authentication and anti-bot state."""
        if not self.driver:
            return "UNKNOWN"

        # 1. Check CAPTCHA / Anti-bot Challenge first
        detector = CaptchaDetector(platform="foundit")
        is_cap, _ = detector.is_captcha_present(self.driver, platform="foundit")
        if is_cap and not detector.is_captcha_solved(self.driver, platform="foundit"):
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

        # 3. Check persistent session cookies first (deterministic and fast)
        try:
            cookies = {c.get("name"): c.get("value") for c in self.driver.get_cookies()}
            if cookies.get("IS_LOGGED_IN") == "true" or (cookies.get("MSSOAT") and len(cookies.get("MSSOAT")) > 10):
                return "LOGGED_IN"
        except Exception:
            pass

        current_url = (self.driver.current_url or "").lower()

        # 4. Check Logged In URL and DOM indicators
        if any(w in current_url for w in ["/home/user", "/seeker/", "/dashboard", "/my-profile"]):
            return "LOGGED_IN"

        for sel in LOGGED_IN_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGGED_IN"
            except Exception:
                pass

        # 5. Check if login modal or form is currently open
        for sel in LOGIN_REQUIRED_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                pass

        # 6. Check for prominent unauthenticated Login/Register buttons in header
        for xp in HEADER_LOGIN_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if xp.startswith("//") else By.CSS_SELECTOR, xp)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                pass

        for xp in HEADER_REGISTER_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if xp.startswith("//") else By.CSS_SELECTOR, xp)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                pass

        return "UNKNOWN"

    def is_logged_in(self) -> bool:
        """Returns True if the current session is verified as authenticated."""
        return self.check_session_state() == "LOGGED_IN"

    def close(self) -> None:
        """Closes browser session cleanly."""
        if self.driver:
            try:
                self.driver.quit()
                print_lg("[FounditBrowser] Closed Chrome session cleanly.")
            except Exception as e:
                print_lg(f"[FounditBrowser] Notice closing browser: {e}")
            finally:
                self.driver = None
                self.wait = None
                self.actions = None
                _cleanup_stale_profile_locks(self.profile_dir)
