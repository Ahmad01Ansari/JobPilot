"""LinkedIn Browser Session Management.

Manages dedicated Chrome session with persistent profile and automatic stale lock cleanup.
"""

import os
import sys
import re
import time
import subprocess
from typing import Optional, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

import undetected_chromedriver as uc
from modules.browser_lock import cleanup_stale_profile_locks, get_profile_dir
from modules.helpers import print_lg, make_directories
from config.settings import run_in_background, stealth_mode, disable_extensions
from modules.stealth import apply_stealth_to_driver
from modules.captcha_detector import CaptchaDetector
from modules.human_behavior import human_delay, human_type, human_click
from platforms.linkedin.selectors import (
    HOME_URL,
    LOGIN_URL,
    LOGGED_IN_INDICATORS,
    GUEST_INDICATORS,
    TWO_FA_KEYWORDS,
    POST_LOGIN_DISMISS_XPATHS,
)


class LinkedInBrowser:
    """Manages dedicated browser session and authentication states for LinkedIn."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        user_id: Optional[int] = 1,
        headless: Optional[bool] = None,
        stealth: bool = True,
        **kwargs,
    ):
        self.user_id = user_id or 1
        self.profile_dir = profile_dir or get_profile_dir("linkedin", user_id=self.user_id)
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
        """Starts an isolated undetected Chrome session using persistent LinkedIn profile."""
        make_directories([self.profile_dir])
        cleanup_stale_profile_locks(self.profile_dir)

        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'

        prefs = {
            "profile.default_content_setting_values.geolocation": 2,
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
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
                    version_main=chrome_major,
                )
            else:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                )
        except Exception as e:
            print_lg(f"[LinkedInBrowser] Launch failed ({e}), attempting lock cleanup retry...")
            cleanup_stale_profile_locks(self.profile_dir)
            time.sleep(2)
            if chrome_major:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                    version_main=chrome_major,
                )
            else:
                self.driver = uc.Chrome(
                    options=options,
                    user_data_dir=self.profile_dir,
                    headless=self.headless,
                )

        self.driver.maximize_window()
        try:
            self.driver.set_page_load_timeout(35)
        except Exception:
            pass

        self.wait = WebDriverWait(self.driver, 10)
        self.actions = ActionChains(self.driver)
        apply_stealth_to_driver(self.driver)
        print_lg(f"[LinkedInBrowser] Started Chrome with profile: {self.profile_dir}")

    def navigate(self, url: str, timeout: int = 30) -> bool:
        """Navigates to URL with eager page-load strategy."""
        if not self.driver:
            raise RuntimeError("Browser not started. Call start() first.")
        from app.services.security.url_validator import is_safe_url
        is_safe, reason = is_safe_url(url, allow_local_ai=False)
        if not is_safe:
            print_lg(f"[LinkedInBrowser] Security blocked navigation to {url}: {reason}")
            return False
        try:
            self.driver.get(url)
            self.dismiss_post_login_prompts()
            return True
        except Exception as e:
            print_lg(f"[LinkedInBrowser] Navigation notice to {url}: {e}")
            return False

    def is_logged_in(self) -> bool:
        """Checks if current session is authenticated on LinkedIn."""
        if not self.driver:
            return False
        try:
            url = self.driver.current_url.lower()
        except Exception:
            return False

        if any(k in url for k in ["/checkpoint/", "/challenge/", "/login", "/signup", "/uas/", "/authwall"]):
            return False

        # Check for guest indicators
        for xp in GUEST_INDICATORS:
            try:
                elems = self.driver.find_elements(By.XPATH, xp)
                if any(e.is_displayed() for e in elems):
                    # Check if me-menu is present to override
                    me_elems = self.driver.find_elements(By.XPATH, '//img[contains(@class, "global-nav__me-photo")]')
                    if not any(m.is_displayed() for m in me_elems):
                        return False
            except Exception:
                pass

        # Check for positive logged in indicators
        for xp in LOGGED_IN_INDICATORS:
            try:
                elems = self.driver.find_elements(By.XPATH, xp)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass

        return "linkedin.com/feed" in url

    def is_2fa_or_challenge(self) -> bool:
        """Detects 2FA, OTP, or security verification challenges."""
        if not self.driver:
            return False
        # Check CaptchaDetector first
        detector = CaptchaDetector(platform="linkedin")
        is_cap, _ = detector.is_captcha_present(self.driver, platform="linkedin")
        if is_cap and not detector.is_captcha_solved(self.driver, platform="linkedin"):
            return True
        try:
            url = self.driver.current_url.lower()
            if any(k in url for k in ["/checkpoint/", "/challenge/", "consumer-captcha", "/two-step", "security-check"]):
                return True
            src = self.driver.page_source.lower()
            return any(k in src for k in TWO_FA_KEYWORDS)
        except Exception:
            return False

    def dismiss_post_login_prompts(self) -> bool:
        """Dismisses interstitials like 'Remember this device' or 'Trust this browser'."""
        if not self.driver:
            return False
        dismissed = False
        for xp in POST_LOGIN_DISMISS_XPATHS:
            try:
                elems = self.driver.find_elements(By.XPATH, xp)
                for el in elems:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        dismissed = True
                        time.sleep(0.5)
            except Exception:
                pass
        return dismissed

    def ensure_authenticated(self, max_wait_seconds: int = 180) -> bool:
        """Waits for user to complete manual login or 2FA challenge if unauthenticated."""
        if self.is_logged_in():
            return True

        if self.is_2fa_or_challenge():
            detector = CaptchaDetector(platform="linkedin")
            resolved = detector.handle_captcha(
                self.driver,
                platform="linkedin",
                timeout=max_wait_seconds,
            )
            if resolved and self.is_logged_in():
                return True

        print_lg(f"[LinkedInBrowser] Not authenticated. Waiting up to {max_wait_seconds}s for authentication...")
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            self.dismiss_post_login_prompts()
            if self.is_logged_in():
                print_lg("[LinkedInBrowser] Authentication confirmed!")
                return True
            time.sleep(3)

        return self.is_logged_in()

    def close(self) -> None:
        """Terminates browser session safely."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print_lg(f"[LinkedInBrowser] Error quitting driver: {e}")
            finally:
                self.driver = None
                self.wait = None
                self.actions = None
