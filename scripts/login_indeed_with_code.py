"""Indeed Login with Email + OTP Verification Code.
Automates email entry and 'Sign in with a code instead' click.
Monitors browser for user to input OTP (or reads from scratch/otp.txt)
and verifies persistent session in ~/.jobpilot-indeed-profile.
"""

import os
import sys
import time
import subprocess
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException
import undetected_chromedriver as uc

PROFILE_DIR = os.path.expanduser("~/.jobpilot-indeed-profile")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "indeed_research_artifacts")
OTP_FILE = os.path.join(ARTIFACTS_DIR, "otp.txt")
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

USER_EMAIL = "candidate@example.com"

def save_screenshot(driver, name: str):
    path = os.path.join(ARTIFACTS_DIR, f"{name}.png")
    try:
        driver.save_screenshot(path)
        print(f"[Screenshot] Saved: {path}")
    except Exception as e:
        print(f"[Screenshot] Failed to save {name}: {e}")
    return path

def get_chrome_major():
    try:
        res = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
        m = re.search(r"(\d+)\.\d+\.\d+\.\d+", res.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

def handle_any_alert(driver):
    try:
        alert = driver.switch_to.alert
        txt = alert.text
        print(f"[Alert] Dismissing unexpected browser alert: {txt}")
        alert.accept()
        return True
    except Exception:
        return False

def check_logged_in(driver) -> bool:
    try:
        handle_any_alert(driver)
        url = (driver.current_url or "").lower()
        if "auth" not in url and ("indeed.com" in url):
            # Check for header elements present only when logged in
            elements = driver.find_elements(By.XPATH, 
                "//button[contains(@aria-label, 'Account')] | "
                "//button[contains(@aria-label, 'Profile')] | "
                "//a[contains(@href, '/myjobs')] | "
                "//a[contains(@href, 'profile.indeed.com')] | "
                "//div[contains(@class, 'gnav-AccountMenu')] | "
                "//span[contains(@class, 'nav-profile')] | "
                "//a[contains(text(), 'Find jobs')]"
            )
            # If sign in link is NOT visible and my jobs or account menu is visible
            sign_in_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Sign in')] | //button[contains(text(), 'Sign in')]")
            visible_sign_ins = [s for s in sign_in_links if s.is_displayed()]
            
            if not visible_sign_ins and any(e.is_displayed() for e in elements):
                return True
    except Exception:
        pass
    return False

def main():
    chrome_major = get_chrome_major()
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
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
        handle_any_alert(driver)

        if check_logged_in(driver):
            print(">>> ALREADY AUTHENTICATED! Persistent session active in profile.")
            save_screenshot(driver, "already_logged_in")
            return 0

        print("Navigating to https://secure.indeed.com/auth ...")
        driver.get("https://secure.indeed.com/auth")
        time.sleep(3)
        handle_any_alert(driver)

        # Accept cookies
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept All Cookies')] | //button[@id='onetrust-accept-btn-handler']")
            if cookie_btn.is_displayed():
                cookie_btn.click()
                time.sleep(1)
        except Exception:
            pass

        # Enter email
        email_elem = driver.find_element(By.XPATH, "//input[@type='email'] | //input[@name='__email']")
        print(f"Entering email: {USER_EMAIL}")
        email_elem.clear()
        for ch in USER_EMAIL:
            email_elem.send_keys(ch)
            time.sleep(0.02)
        time.sleep(1)

        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        print("Submitting email...")
        try:
            submit_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", submit_btn)

        # Wait for "Welcome back" screen with "Sign in with a code instead"
        print("Waiting for 'Sign in with a code instead' link...")
        code_link = None
        for _ in range(15):
            time.sleep(1)
            handle_any_alert(driver)
            try:
                elems = driver.find_elements(By.XPATH, "//a[contains(text(), 'Sign in with a code instead')] | //button[contains(., 'Sign in with a code instead')]")
                for el in elems:
                    if el.is_displayed():
                        code_link = el
                        break
                if code_link:
                    break
            except Exception:
                pass

        if code_link:
            print("Clicking 'Sign in with a code instead'...")
            try:
                code_link.click()
            except Exception:
                driver.execute_script("arguments[0].click();", code_link)
        else:
            print("Notice: 'Sign in with a code instead' not found, checking if already on OTP or code screen...")

        time.sleep(3)
        handle_any_alert(driver)
        save_screenshot(driver, "waiting_for_otp_entry")

        print("\n" + "="*70)
        print(">>> FRESH OTP SENT TO candidate@example.com")
        print(">>> You have 300 seconds (5 minutes) to complete authentication.")
        print(">>> Enter the 6-digit code directly in the open Chrome window OR write it to:")
        print(f">>> {OTP_FILE}")
        print("="*70 + "\n")

        # Wait up to 300 seconds (5 minutes) for OTP completion
        start_time = time.time()
        authenticated = False
        while time.time() - start_time < 300:
            time.sleep(2)
            handle_any_alert(driver)

            # Check if otp file exists
            if os.path.exists(OTP_FILE):
                try:
                    with open(OTP_FILE, "r") as f:
                        otp_code = f.read().strip()
                    if otp_code:
                        print(f"Read OTP '{otp_code}' from {OTP_FILE}. Filling into passcode input...")
                        passcode_input = driver.find_element(By.ID, "passcode-input")
                        passcode_input.clear()
                        passcode_input.send_keys(otp_code)
                        time.sleep(0.5)
                        sign_in_btn = driver.find_element(By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]")
                        sign_in_btn.click()
                        os.remove(OTP_FILE)
                        print("Submitted OTP. Waiting for page redirect...")
                        time.sleep(5)
                except Exception as ex:
                    print(f"Error handling OTP file: {ex}")

            # Check if logged in
            try:
                cur_url = (driver.current_url or "").lower()
                if ("in.indeed.com" in cur_url or "indeed.com" in cur_url) and "auth" not in cur_url and "login" not in cur_url:
                    authenticated = True
                    print("\n>>> SUCCESS! Successfully authenticated to Indeed!")
                    save_screenshot(driver, "login_success")
                    break
            except Exception:
                pass

            rem = int(300 - (time.time() - start_time))
            if rem % 15 == 0:
                print(f"Waiting for OTP... ({rem}s remaining)")

        if authenticated:
            print("Session cookies successfully saved to persistent profile:", PROFILE_DIR)
            print("Subsequent runs will NOT require logging in again!")
            time.sleep(5)
            return 0
        else:
            print("Authentication timed out after 300 seconds.")
            save_screenshot(driver, "login_timeout")
            return 1

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    sys.exit(main())
