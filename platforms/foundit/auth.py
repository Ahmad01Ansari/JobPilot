'''
Foundit Authentication Engine
Manages credential-based login, modal interactions, OTP/Password switching,
and session state transitions on Foundit India (foundit.in).
'''

import time
from typing import Tuple, Optional, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from platforms.foundit.selectors import (
    HOME_URL,
    LOGIN_URL,
    HEADER_LOGIN_BUTTONS,
    LOGIN_USERNAME_INPUT,
    LOGIN_PASSWORD_SWITCH_LINKS,
    LOGIN_PASSWORD_INPUT,
    LOGIN_SUBMIT_BUTTON,
)
from platforms.foundit.exceptions import FounditLoginError, FounditCaptchaError
from modules.helpers import print_lg


class FounditAuth:
    """Handles candidate login and authentication flows for Foundit."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: int = 25,
    ) -> Tuple[bool, str]:
        """Executes full login sequence using configured credentials.
        Returns: (success: bool, message: str)
        """
        if not self.driver:
            raise RuntimeError("Browser not started. Call browser.start() first.")

        # 1. Ensure we are on a Foundit page so cookies and profile session are active
        current_url = (self.driver.current_url or "").lower()
        if "foundit.in" not in current_url:
            self.browser.navigate(HOME_URL)
            time.sleep(2)

        # 2. Check if session is already authenticated via stored cookies or profile
        initial_state = self.browser.check_session_state()
        if initial_state == "LOGGED_IN":
            print_lg("[FounditAuth] Stored session is active and verified (cookies/profile confirmed). Skipping login.")
            return (True, "Already logged in.")

        if initial_state in ["CAPTCHA", "OTP_REQUIRED"]:
            return (False, f"Challenge encountered ({initial_state}). Manual intervention required.")

        # Resolve credentials if not explicitly passed
        if not username or not password:
            try:
                from config.secrets import foundit_username, foundit_password
                username = username or foundit_username
                password = password or foundit_password
            except Exception:
                pass

        if not username or not password:
            return (False, "Missing Foundit credentials (username/password).")

        masked_user = f"{username[:2]}***{username[username.find('@'):]}" if "@" in username else f"{username[:2]}***"
        print_lg(f"[FounditAuth] Initiating login for candidate: {masked_user}")

        # 3. Locate and click header Login button to open login modal
        modal_opened = False
        # Check if username input is already visible on the current page
        user_elems = self.driver.find_elements(By.CSS_SELECTOR, LOGIN_USERNAME_INPUT)
        if any(e.is_displayed() for e in user_elems):
            modal_opened = True

        if not modal_opened:
            for xp in HEADER_LOGIN_BUTTONS:
                try:
                    btns = self.driver.find_elements(By.XPATH if xp.startswith("//") else By.CSS_SELECTOR, xp)
                    for b in btns:
                        if b.is_displayed():
                            self.driver.execute_script("arguments[0].click();", b)
                            modal_opened = True
                            time.sleep(1.5)
                            break
                    if modal_opened:
                        break
                except Exception:
                    continue

        # If modal didn't open from header, navigate directly to LOGIN_URL
        user_elems = self.driver.find_elements(By.CSS_SELECTOR, LOGIN_USERNAME_INPUT)
        if not any(e.is_displayed() for e in user_elems):
            print_lg("[FounditAuth] Login modal not open, navigating directly to login URL...")
            self.browser.navigate(LOGIN_URL)
            time.sleep(2)

        # 4. Fill Username
        user_input = None
        for sel in [LOGIN_USERNAME_INPUT, "input#userName", "input[name='userName']"]:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        user_input = el
                        break
                if user_input:
                    break
            except Exception:
                continue

        if not user_input:
            return (False, "Username input field not found on login view.")

        user_input.clear()
        user_input.send_keys(username)
        time.sleep(0.5)

        # 5. Switch to Password Mode (from OTP prompt)
        switched = False
        for xp in LOGIN_PASSWORD_SWITCH_LINKS:
            try:
                elems = self.driver.find_elements(By.XPATH if xp.startswith("//") else By.CSS_SELECTOR, xp)
                for el in elems:
                    if el.is_displayed():
                        self.driver.execute_script("arguments[0].click();", el)
                        switched = True
                        time.sleep(1)
                        break
                if switched:
                    break
            except Exception:
                continue

        # 6. Fill Password
        pwd_input = None
        for sel in [LOGIN_PASSWORD_INPUT, "input#password", "input[type='password']"]:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        pwd_input = el
                        break
                if pwd_input:
                    break
            except Exception:
                continue

        if not pwd_input:
            return (False, "Password input field not displayed after switching to password mode.")

        pwd_input.clear()
        pwd_input.send_keys(password)
        time.sleep(0.5)

        # 7. Click Submit
        submit_btn = None
        for sel in [LOGIN_SUBMIT_BUTTON, "button#loginSubmit", "button[type='submit']"]:
            try:
                for b in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if b.is_displayed() and "login" in (b.text or "").strip().lower():
                        submit_btn = b
                        break
                if submit_btn:
                    break
            except Exception:
                continue

        if not submit_btn:
            return (False, "Login submit button not found.")

        try:
            submit_btn.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", submit_btn)

        print_lg("[FounditAuth] Submitted credentials, waiting for session state transition...")

        # 8. Dynamic Polling for State Transition
        start_t = time.time()
        while time.time() - start_t < timeout:
            time.sleep(1)
            state = self.browser.check_session_state()

            if state == "LOGGED_IN":
                print_lg("[FounditAuth] Login successfully confirmed.")
                return (True, "Login successful.")

            if state in ["CAPTCHA", "OTP_REQUIRED"]:
                print_lg(f"[FounditAuth] Challenge required during login: {state}")
                return (False, f"Challenge encountered ({state}). Manual intervention required.")

            # Check for invalid credentials error messages
            for err_sel in ["div.error", "span.error-msg", "div[class*='error']", "p[class*='error']"]:
                try:
                    for err_el in self.driver.find_elements(By.CSS_SELECTOR, err_sel):
                        txt = (err_el.text or "").strip()
                        if err_el.is_displayed() and any(w in txt.lower() for w in ["invalid", "incorrect", "wrong password", "not registered"]):
                            print_lg(f"[FounditAuth] Authentication failed with error: {txt}")
                            return (False, f"Authentication error: {txt}")
                except Exception:
                    pass

        # Final check
        if self.browser.is_logged_in():
            return (True, "Login successful.")

        return (False, f"Authentication timed out after {timeout} seconds.")
