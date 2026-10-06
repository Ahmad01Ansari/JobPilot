"""Test Indeed 'Sign in with a code instead' flow and inspect the OTP entry screen.
"""

import os
import sys
import time
import subprocess
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

def get_chrome_major():
    try:
        res = subprocess.run(["google-chrome", "--version"], capture_output=True, text=True)
        m = re.search(r"(\d+)\.\d+\.\d+\.\d+", res.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return None

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
        print("Navigating to https://secure.indeed.com/auth ...")
        driver.get("https://secure.indeed.com/auth")
        time.sleep(3)

        # Accept cookies if any
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept All Cookies')] | //button[@id='onetrust-accept-btn-handler']")
            if cookie_btn.is_displayed():
                cookie_btn.click()
                time.sleep(1)
        except Exception:
            pass

        email_elem = driver.find_element(By.XPATH, "//input[@type='email'] | //input[@name='__email']")
        print(f"Typing email: {USER_EMAIL}...")
        email_elem.clear()
        for ch in USER_EMAIL:
            email_elem.send_keys(ch)
            time.sleep(0.02)
        time.sleep(1)

        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        print("Clicking Continue...")
        try:
            submit_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", submit_btn)

        time.sleep(6)
        save_screenshot(driver, "30_welcome_back_screen")

        # Find and click "Sign in with a code instead"
        code_link = None
        for sel in [
            "//a[contains(text(), 'Sign in with a code instead')]",
            "//button[contains(., 'Sign in with a code instead')]",
            "//*[contains(text(), 'Sign in with a code instead')]",
            "//a[contains(@href, 'code') or contains(@href, 'otp')]"
        ]:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        code_link = el
                        break
                if code_link:
                    break
            except Exception:
                pass

        if not code_link:
            print("ERROR: Could not find 'Sign in with a code instead' link!")
            save_screenshot(driver, "error_no_code_link")
            return

        print(f"Clicking: '{code_link.text.strip()}' (tag={code_link.tag_name}, href={code_link.get_attribute('href')})")
        try:
            code_link.click()
        except Exception:
            driver.execute_script("arguments[0].click();", code_link)

        time.sleep(5)
        save_screenshot(driver, "31_otp_screen")
        print(f"OTP Screen Title: '{driver.title}', URL: {driver.current_url}")

        # Inspect OTP input fields
        inputs = driver.find_elements(By.XPATH, "//input")
        print(f"Found {len(inputs)} input elements on OTP page:")
        for inp in inputs:
            print(f"  - tag={inp.tag_name}, id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, type={inp.get_attribute('type')}, class={inp.get_attribute('class')}, displayed={inp.is_displayed()}")

        # Inspect buttons
        btns = driver.find_elements(By.XPATH, "//button")
        print(f"Found {len(btns)} button elements on OTP page:")
        for b in btns:
            if b.is_displayed():
                print(f"  - button text='{b.text.strip()}', type={b.get_attribute('type')}, id={b.get_attribute('id')}")

        print("\n" + "="*70)
        print(">>> OTP SENT TO candidate@example.com!")
        print(">>> Browser will remain open for 180 seconds.")
        print(">>> Enter the code in the browser to complete authentication.")
        print("="*70 + "\n")

        start = time.time()
        while time.time() - start < 180:
            time.sleep(3)
            url = (driver.current_url or "").lower()
            if ("in.indeed.com" in url or "indeed.com" in url) and "auth" not in url and "login" not in url:
                print(">>> AUTHENTICATION DETECTED! Successfully logged in!")
                save_screenshot(driver, "32_authenticated_home")
                break
            rem = int(180 - (time.time() - start))
            if rem % 15 == 0:
                print(f"Waiting for OTP entry... ({rem}s remaining)")

        time.sleep(5)
    finally:
        driver.quit()
        print("Browser session ended.")

if __name__ == "__main__":
    main()
