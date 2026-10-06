"""Indeed Live Portal Research Script: Email + Login Code (OTP) Authentication.
Enters candidate email, requests login code / handles password/OTP,
and waits up to 3 minutes for human OTP completion in the browser.
Persists session in ~/.jobpilot-indeed-profile.
"""

import os
import sys
import time
import subprocess
import re
from typing import Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

PROFILE_DIR = os.path.expanduser("~/.jobpilot-indeed-profile")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "indeed_research_artifacts")
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

USER_EMAIL = "candidate@example.com"

def save_screenshot(driver, name: str):
    path = os.path.join(ARTIFACTS_DIR, f"{name}.png")
    driver.save_screenshot(path)
    print(f"[Screenshot] Saved: {path}")
    return path

def get_chrome_major() -> Optional[int]:
    try:
        res = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
        m = re.search(r"(\d+)\.\d+\.\d+\.\d+", res.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

def is_logged_in_state(driver) -> bool:
    try:
        url = (driver.current_url or "").lower()
        if "auth" not in url and ("indeed.com" in url):
            # Check for profile avatar, account menu, or my jobs link
            indicators = driver.find_elements(By.XPATH, 
                "//button[contains(@aria-label, 'Account')] | "
                "//button[contains(@aria-label, 'Profile')] | "
                "//a[contains(@href, '/myjobs')] | "
                "//a[contains(@href, 'profile.indeed.com')] | "
                "//div[contains(@class, 'gnav-AccountMenu')] | "
                "//span[contains(@class, 'nav-profile')]"
            )
            if any(ind.is_displayed() for ind in indicators):
                return True
    except Exception:
        pass
    return False

def main():
    chrome_major = get_chrome_major()
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    prefs = {
        "profile.default_content_setting_values.geolocation": 2,
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.popups": 1,
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--deny-permission-prompts")
    options.add_argument("--disable-geolocation")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1000")

    driver = uc.Chrome(
        options=options,
        user_data_dir=PROFILE_DIR,
        headless=False,
        version_main=chrome_major
    )

    try:
        print("Checking if already logged into Indeed...")
        driver.get("https://in.indeed.com/")
        time.sleep(3)
        if is_logged_in_state(driver):
            print(">>> ALREADY LOGGED IN! Indeed session is active in profile.")
            save_screenshot(driver, "already_logged_in")
            return

        print("Navigating to https://secure.indeed.com/auth ...")
        driver.get("https://secure.indeed.com/auth")
        time.sleep(3)

        # 1. Accept cookies if present
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept All Cookies')] | //button[@id='onetrust-accept-btn-handler']")
            if cookie_btn.is_displayed():
                print("Accepting cookies...")
                cookie_btn.click()
                time.sleep(1)
        except Exception:
            pass

        save_screenshot(driver, "20_email_login_page")

        # 2. Find email input
        email_elem = None
        for sel in ["//input[@type='email']", "//input[@name='__email']", "//input[contains(@id, 'email') or contains(@id, 'Email')]"]:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        email_elem = el
                        break
                if email_elem:
                    break
            except Exception:
                pass

        if not email_elem:
            print("ERROR: Could not locate email input on login page.")
            save_screenshot(driver, "error_no_email_input")
            return

        print(f"Entering email: {USER_EMAIL}")
        email_elem.clear()
        email_elem.send_keys(USER_EMAIL)
        time.sleep(1)
        save_screenshot(driver, "21_email_typed")

        # 3. Click Continue button
        continue_btn = None
        for sel in ["//button[@type='submit']", "//button[contains(., 'Continue')]", "//button[contains(., 'Next')]"]:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        continue_btn = el
                        break
                if continue_btn:
                    break
            except Exception:
                pass

        if continue_btn:
            print(f"Clicking Continue button: {continue_btn.text.strip()}")
            try:
                continue_btn.click()
            except Exception:
                driver.execute_script("arguments[0].click();", continue_btn)
        else:
            email_elem.send_keys(Keys.RETURN)

        time.sleep(4)
        save_screenshot(driver, "22_after_email_continue")
        print(f"URL after email submit: {driver.current_url}")
        print(f"Title after email submit: {driver.title}")

        # 4. Check for 'Log in with code' or 'Send login code' or password prompt
        code_buttons = driver.find_elements(By.XPATH, 
            "//button[contains(., 'code') or contains(., 'Code') or contains(., 'login code')] | "
            "//a[contains(., 'code') or contains(., 'Code') or contains(., 'login code')] | "
            "//button[contains(., 'Email me a code')] | "
            "//button[contains(., 'Send a code')] | "
            "//span[contains(text(), 'Login with a code')]/parent::*"
        )
        print(f"Found {len(code_buttons)} potential 'Login with code' buttons")
        for b in code_buttons:
            if b.is_displayed():
                print(f"Clicking 'Login with code' option: '{b.text.strip()}'")
                try:
                    b.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", b)
                time.sleep(3)
                break

        save_screenshot(driver, "23_code_prompt_screen")

        # 5. Wait up to 180 seconds (3 minutes) for user to enter OTP in the browser
        print("\n" + "="*70)
        print(">>> ACTION REQUIRED: OTP / LOGIN VERIFICATION")
        print(f">>> A login code has been sent to {USER_EMAIL}.")
        print(">>> Please enter the 6-digit code directly into the open Chrome window.")
        print(">>> Waiting up to 180 seconds for authentication to complete...")
        print("="*70 + "\n")

        start_time = time.time()
        authenticated = False
        while time.time() - start_time < 180:
            time.sleep(3)
            # Check if login completed
            if is_logged_in_state(driver):
                authenticated = True
                print("\n>>> AUTHENTICATION SUCCESSFUL! Detected active Indeed session!")
                save_screenshot(driver, "24_authenticated_success")
                break

            # Check if URL redirected to home or profile
            cur_url = (driver.current_url or "").lower()
            if ("in.indeed.com" in cur_url or "indeed.com" in cur_url) and "auth" not in cur_url and "login" not in cur_url and "challenge" not in cur_url:
                # Double check with title
                if "sign in" not in driver.title.lower():
                    authenticated = True
                    print("\n>>> AUTHENTICATION SUCCESSFUL! Redirected away from auth page!")
                    save_screenshot(driver, "24_authenticated_success")
                    break

            remaining = int(180 - (time.time() - start_time))
            if remaining % 15 == 0:
                print(f"Waiting for OTP entry... ({remaining}s remaining)")

        if not authenticated:
            print("Authentication timed out or was not confirmed within 180 seconds.")
            save_screenshot(driver, "25_auth_timed_out")
        else:
            print("Indeed session is now saved in profile directory:", PROFILE_DIR)
            print("Subsequent runs will NOT require logging in again!")
            time.sleep(5)

    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
