'''
Glassdoor Authentication & Session Verification
Handles login detection, credentials entry, session cookies persistence, and modal wall bypassing.
'''

import time
from typing import Optional, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from platforms.glassdoor.selectors import (
    HOME_URL,
    LOGIN_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    LOGIN_EMAIL_INPUTS,
    LOGIN_PASSWORD_INPUTS,
    LOGIN_SUBMIT_BUTTONS,
)
from modules.helpers import print_lg
from modules.human_behavior import human_delay, human_type


class GlassdoorAuth:
    """Coordinates authentication and session verification on Glassdoor."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def check_session_state(self) -> str:
        """Determines if the session is AUTHENTICATED, LOGIN_REQUIRED, or UNKNOWN."""
        if not self.driver:
            return "UNKNOWN"

        if self.browser.is_logged_in():
            return "AUTHENTICATED"

        for sel in LOGIN_REQUIRED_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "LOGIN_REQUIRED"
            except Exception:
                continue

        return "UNKNOWN"

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Logs into Glassdoor if not already authenticated."""
        if not self.driver:
            return False

        if self.browser.is_logged_in():
            print_lg("[GlassdoorAuth] Already logged in via persistent session.")
            return True

        print_lg("[GlassdoorAuth] Navigating to login page...")
        self.driver.get(LOGIN_URL)
        human_delay(2.0, 3.5)
        self.browser.dismiss_overlays()

        if self.browser.is_logged_in():
            print_lg("[GlassdoorAuth] Verified active session after navigation.")
            return True

        if not username or not password:
            print_lg("[GlassdoorAuth] No credentials provided for automated login.")
            return False

        # Populate email
        for sel in LOGIN_EMAIL_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed():
                    human_type(el, username)
                    break
            except Exception:
                continue

        # Submit email / continue
        for sel in LOGIN_SUBMIT_BUTTONS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed():
                    el.click()
                    human_delay(1.5, 2.5)
                    break
            except Exception:
                continue

        # Populate password if prompted
        for sel in LOGIN_PASSWORD_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed():
                    human_type(el, password)
                    break
            except Exception:
                continue

        # Submit password
        for sel in LOGIN_SUBMIT_BUTTONS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed():
                    el.click()
                    human_delay(3.0, 5.0)
                    break
            except Exception:
                continue

        return self.browser.is_logged_in()
