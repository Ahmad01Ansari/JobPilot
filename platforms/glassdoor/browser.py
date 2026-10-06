'''
Glassdoor Browser Session Management
Manages isolated Chrome sessions with persistent profile for Glassdoor (glassdoor.com / glassdoor.co.in).
Profile directory: ~/.jobpilot-glassdoor-profile
'''

import os
import sys
import time
from typing import Optional, Literal, Tuple, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

import undetected_chromedriver as uc
from platforms.glassdoor.selectors import (
    HOME_URL,
    LOGIN_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    CAPTCHA_IFRAME_SELECTORS,
    CAPTCHA_CONTAINER_SELECTORS,
    MODAL_CLOSE_BUTTONS,
    COOKIE_ACCEPT_BUTTONS,
)
from modules.helpers import print_lg
from config.settings import run_in_background, stealth_mode, disable_extensions
from modules.stealth import apply_stealth_to_driver
from modules.human_behavior import human_delay, human_type, human_click


def get_default_glassdoor_profile_dir() -> str:
    """Returns persistent profile directory for Glassdoor (~/.jobpilot-glassdoor-profile)."""
    return os.path.expanduser("~/.jobpilot-glassdoor-profile")


DEFAULT_GLASSDOOR_PROFILE_DIR = get_default_glassdoor_profile_dir()


def _cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Removes stale Chrome lock files (SingletonLock, SingletonCookie, SingletonSocket) if not in use."""
    from modules.browser_lock import cleanup_stale_profile_locks
    cleanup_stale_profile_locks(profile_dir)


class GlassdoorBrowser:
    """Manages dedicated browser instance and authentication states for Glassdoor."""

    def __init__(
        self,
        profile_dir: Optional[str] = None,
        headless: Optional[bool] = None,
        stealth: bool = True,
        user_id: int = 1,
    ):
        self.profile_dir = profile_dir or DEFAULT_GLASSDOOR_PROFILE_DIR
        self.headless = run_in_background if headless is None else headless
        self.stealth = stealth
        self.user_id = user_id
        self.driver: Optional[uc.Chrome] = None

    @staticmethod
    def _get_chrome_major_version() -> Optional[int]:
        """Detects installed Chrome major version on host system."""
        import subprocess, re
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

    def start(self) -> uc.Chrome:
        """Launches Chrome driver with Glassdoor persistent profile and stealth capabilities."""
        if self.driver:
            return self.driver

        os.makedirs(self.profile_dir, exist_ok=True)
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
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1600,1000")

        if disable_extensions:
            options.add_argument("--disable-extensions")

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
            err_msg = str(e).strip() or repr(e)
            print_lg(f"[GlassdoorBrowser] Initial Chrome launch failed ({err_msg}), attempting lock cleanup retry...")
            from modules.browser_lock import kill_profile_processes
            kill_profile_processes(self.profile_dir)
            time.sleep(2)
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
            except Exception as e2:
                err_detail = str(e2).strip() or repr(e2)
                print_lg(f"[GlassdoorBrowser] Failed to initialize Chrome: {err_detail}")
                raise RuntimeError(f"Failed to launch Chrome with profile {self.profile_dir}: {err_detail}") from e2

        if self.stealth:
            apply_stealth_to_driver(self.driver)

        try:
            self.driver.maximize_window()
        except Exception:
            pass

        print_lg(f"[GlassdoorBrowser] Chrome initialized with profile: {self.profile_dir}")
        return self.driver

    def close(self) -> None:
        """Gracefully quits the browser and frees locks."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print_lg(f"[GlassdoorBrowser] Error closing driver: {e}")
            finally:
                self.driver = None
                time.sleep(1.0)
                _cleanup_stale_profile_locks(self.profile_dir)

    def is_logged_in(self) -> bool:
        """Checks if session is currently authenticated on Glassdoor."""
        if not self.driver:
            return False

        # 1. URL redirect check
        try:
            curr_url = self.driver.current_url.lower()
            if "/member/home" in curr_url or "/community" in curr_url:
                return True
        except Exception:
            pass

        # 2. DOM elements check (User avatar, member profile, account dropdown)
        for sel in LOGGED_IN_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue

        return False

    def dismiss_overlays(self) -> int:
        """Dismisses any blocking modals, cookie consents, job alerts, or backdrop walls."""
        if not self.driver:
            return 0
        dismissed = 0

        # 1. Send ESCAPE key to dismiss modal dialogs
        try:
            from selenium.webdriver.common.keys import Keys
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        # 2. Aggressive JS-level close of job alert and overlay dialogs
        try:
            count = self.driver.execute_script('''
                var count = 0;
                // Direct query for alert modal close / cancel buttons
                var btns = document.querySelectorAll(
                    "button[data-test='job-alert-modal-close'], button[aria-label='Cancel'], .modal_CloseButton__faPZA button, " +
                    "button[data-test='modal-close'], button[aria-label='Close'], button[aria-label='close'], " +
                    "button.CloseButton, [data-test='job-alert-modal-close'], div[role='dialog'] button[aria-label='Close'], " +
                    "button[class*='close' i], button[class*='Close' i], div[class*='Modal'] button, " +
                    "div[class*='ContentWall'] button[aria-label='Close']"
                );
                for (var b of btns) {
                    if (b && (b.offsetParent !== null || b.offsetWidth > 0 || b.offsetHeight > 0)) {
                        b.click();
                        count++;
                    }
                }

                // Content-based detection for 'Create job alert' dialog
                var alertModals = Array.from(document.querySelectorAll("div, section, dialog")).filter(function(el) {
                    var txt = (el.innerText || '');
                    return txt.includes('Create job alert') && (el.offsetWidth > 150 && el.offsetHeight > 100);
                });
                for (var m of alertModals) {
                    var cb = m.querySelector("button[data-test*='close' i], button[aria-label*='Cancel' i], button[aria-label*='Close' i], button[class*='close' i], button[class*='Close' i], button svg, button");
                    if (cb) {
                        cb.click();
                        count++;
                    } else if (m.className && (m.className.includes('Modal') || m.className.includes('modal'))) {
                        m.remove();
                        count++;
                    }
                }

                // Remove backdrops if lingering
                var backdrops = document.querySelectorAll(".hiding-modal, .ModalBackdrop, div[class*='backdrop' i], div[class*='modal_ModalOverlay' i], div[class*='Overlay' i]");
                for (var bd of backdrops) {
                    bd.remove();
                }
                document.body.style.overflow = 'auto';
                return count;
            ''')
            if isinstance(count, int) and count > 0:
                dismissed += count
        except Exception:
            pass

        # 3. DOM selector inspection fallback
        for sel in MODAL_CLOSE_BUTTONS + COOKIE_ACCEPT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        dismissed += 1
                        time.sleep(0.3)
            except Exception:
                continue
        return dismissed

    def navigate(self, url: str) -> None:
        """Navigates to URL safely."""
        if self.driver:
            from app.services.security.url_validator import is_safe_url
            is_safe, reason = is_safe_url(url, allow_local_ai=False)
            if not is_safe:
                print_lg(f"[GlassdoorBrowser] Security blocked navigation to {url}: {reason}")
                return
            self.driver.get(url)

    def ensure_authenticated(self, max_wait_seconds: int = 120) -> bool:
        """Navigates to Glassdoor and waits for user to log in if not already authenticated."""
        if not self.driver:
            return False
        if self.is_logged_in():
            return True

        from platforms.glassdoor.selectors import HOME_URL, LOGIN_URL
        print_lg("[GlassdoorBrowser] Navigating to Glassdoor login page...")
        self.navigate(LOGIN_URL)
        time.sleep(2)
        self.dismiss_overlays()

        if self.is_logged_in():
            return True

        print_lg(f"[GlassdoorBrowser] Please log in to your Glassdoor account in the opened browser window. Waiting up to {max_wait_seconds}s...")
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            self.dismiss_overlays()
            if self.is_logged_in():
                print_lg("[GlassdoorBrowser] Login detected successfully!")
                return True
            time.sleep(2)

        return self.is_logged_in()
