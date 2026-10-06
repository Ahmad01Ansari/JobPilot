"""Test Indeed Google Login button interaction inside GSI iframe.
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
        except Exception as e:
            print(f"Cookie banner note: {e}")

        save_screenshot(driver, "10_login_cookies_handled")

        # 2. Look for Google button / iframe
        initial_handles = driver.window_handles
        print(f"Initial window handles: {initial_handles}")

        gsi_iframes = driver.find_elements(By.XPATH, "//iframe[contains(@src, 'accounts.google.com/gsi/button')]")
        print(f"Found {len(gsi_iframes)} GSI iframes")

        if gsi_iframes:
            iframe = gsi_iframes[0]
            print(f"Switching to GSI iframe id={iframe.get_attribute('id')}...")
            driver.switch_to.frame(iframe)

            # Dump elements inside the iframe
            inner_elements = driver.find_elements(By.XPATH, "//*")
            print(f"Iframe has {len(inner_elements)} elements")
            for elem in inner_elements:
                tag = elem.tag_name
                role = elem.get_attribute("role")
                aria = elem.get_attribute("aria-label")
                txt = elem.text.strip()
                if txt or role or aria:
                    print(f" - tag={tag}, role={role}, aria-label={aria}, text='{txt}'")

            # Click the interactive button inside iframe
            click_target = None
            try:
                click_target = driver.find_element(By.XPATH, "//*[@role='button'] | //div[contains(@class, 'nsm7Bb-HzV7fe-LgbsSe')] | //button")
            except Exception:
                pass

            if not click_target and len(inner_elements) > 1:
                click_target = inner_elements[1]

            if click_target:
                print(f"Clicking Google button inside iframe: {click_target.tag_name}")
                try:
                    click_target.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", click_target)

            # Switch back to main document
            driver.switch_to.default_content()
            time.sleep(3)

        # 3. Check if new popup window opened
        handles_after = driver.window_handles
        print(f"Window handles after click: {handles_after}")

        if len(handles_after) > len(initial_handles):
            new_handle = [h for h in handles_after if h not in initial_handles][0]
            print(f"Switching to new window/popup: {new_handle}")
            driver.switch_to.window(new_handle)
            time.sleep(3)
            save_screenshot(driver, "11_google_popup_opened")
            print(f"Popup Title: {driver.title}")
            print(f"Popup URL: {driver.current_url}")

            # Inspect elements in Google popup
            print("Inspecting Google popup DOM...")
            inputs = driver.find_elements(By.XPATH, "//input")
            for inp in inputs:
                print(f"Input: type={inp.get_attribute('type')}, id={inp.get_attribute('id')}, name={inp.get_attribute('name')}, displayed={inp.is_displayed()}")

            # If identifier / email field is displayed
            email_field = None
            for sel in ["//input[@id='identifierId']", "//input[@type='email']", "//input[@name='identifier']"]:
                try:
                    ef = driver.find_element(By.XPATH, sel)
                    if ef.is_displayed():
                        email_field = ef
                        break
                except Exception:
                    pass

            if email_field:
                print(f"Found Google email field, typing {USER_EMAIL}...")
                email_field.clear()
                email_field.send_keys(USER_EMAIL)
                save_screenshot(driver, "12_google_email_typed")
                time.sleep(1)

                # Look for Next button
                next_btn = None
                for n_sel in ["//div[@id='identifierNext']//button", "//button[contains(., 'Next')]", "//button//span[contains(text(), 'Next')]"]:
                    try:
                        nb = driver.find_element(By.XPATH, n_sel)
                        if nb.is_displayed():
                            next_btn = nb
                            break
                    except Exception:
                        pass

                if next_btn:
                    print("Clicking Next button on Google login...")
                    try:
                        next_btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", next_btn)
                    time.sleep(5)
                    save_screenshot(driver, "13_google_after_email_submitted")
                    print(f"After Next: Title: {driver.title}, URL: {driver.current_url}")
            else:
                # Check if account selection list is shown
                accs = driver.find_elements(By.XPATH, f"//*[contains(text(), '{USER_EMAIL}')]")
                print(f"Found {len(accs)} account elements matching {USER_EMAIL}")
                if accs:
                    print("Selecting account...")
                    accs[0].click()
                    time.sleep(5)
                    save_screenshot(driver, "13_google_account_selected")
        else:
            print("No new popup window opened. Checking main window for navigation...")
            save_screenshot(driver, "11_no_popup_current_state")
            print(f"Current Title: {driver.title}, URL: {driver.current_url}")

        print("Leaving browser alive for 15 seconds to observe state...")
        time.sleep(15)

    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
