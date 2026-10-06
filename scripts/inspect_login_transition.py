"""Inspect Indeed login transition after entering email and clicking continue.
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

        # Accept cookies
        try:
            cookie_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Accept All Cookies')] | //button[@id='onetrust-accept-btn-handler']")
            if cookie_btn.is_displayed():
                cookie_btn.click()
                time.sleep(1)
        except Exception:
            pass

        email_elem = driver.find_element(By.XPATH, "//input[@type='email'] | //input[@name='__email']")
        print("Typing email...")
        email_elem.clear()
        for ch in USER_EMAIL:
            email_elem.send_keys(ch)
            time.sleep(0.03)
        time.sleep(1)

        submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        print("Clicking Continue...")
        try:
            submit_btn.click()
        except Exception:
            driver.execute_script("arguments[0].click();", submit_btn)

        # Monitor page every 2 seconds for up to 30 seconds
        for step in range(1, 16):
            time.sleep(2)
            cur_url = driver.current_url
            cur_title = driver.title
            print(f"[Step {step} | {step*2}s] Title: '{cur_title}', URL: {cur_url}")
            
            # Check for any error messages or text changes
            card_text = ""
            try:
                main_card = driver.find_element(By.XPATH, "//main | //div[contains(@class, 'pass-')] | //div[contains(@class, 'auth')]")
                card_text = main_card.text.strip().replace("\n", " | ")
                print(f"   Card text: {card_text[:120]}")
            except Exception:
                pass

            # Check if any new inputs appeared (password, code, etc.)
            inputs = driver.find_elements(By.XPATH, "//input")
            input_types = [inp.get_attribute('type') or inp.get_attribute('name') for inp in inputs if inp.is_displayed()]
            print(f"   Visible inputs: {input_types}")

            if "password" in input_types or "verification" in card_text.lower() or "code" in card_text.lower() or "challenge" in cur_url:
                print(f">>> Transition detected at step {step}!")
                save_screenshot(driver, f"transition_step_{step}")
                break

        save_screenshot(driver, "after_monitor")
        print("Monitoring finished, staying open 10s...")
        time.sleep(10)
    finally:
        driver.quit()
        print("Browser quit.")

if __name__ == "__main__":
    main()
