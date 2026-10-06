"""Test Indeed UI Search input filling, submission, and date filter.
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

def save_screenshot(driver, name: str):
    path = os.path.join(ARTIFACTS_DIR, f"{name}.png")
    try:
        driver.save_screenshot(path)
        print(f"[Screenshot] Saved: {path}")
    except Exception as e:
        print(f"[Screenshot] Failed to save {name}: {e}")
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

def apply_date_posted_filter(driver, freshness_days: int = 3):
    print(f"[TestFilter] Applying date posted filter for {freshness_days} days...")
    # Open popover
    opened = bool(driver.execute_script("""
        const btn = document.querySelector("#fromAge_filter_button, button[id*='fromAge'], button[aria-label*='Date posted' i]");
        if (!btn) return false;
        btn.focus();
        btn.click();
        return true;
    """))
    if not opened:
        for sel in ["#fromAge_filter_button", "button[id*='fromAge']", "//button[contains(., 'Date posted')]"]:
            elems = driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
            for b in elems:
                if b.is_displayed():
                    b.click()
                    opened = True
                    break
            if opened:
                break
    
    print(f"[TestFilter] Popover opened: {opened}")
    time.sleep(1.5)
    save_screenshot(driver, "test_ui_filter_popover_open")

    # Select option and update
    res = driver.execute_script("""
        // 3 days is option-3
        let targetOpt = document.querySelector("li[data-testid='selection-pill-option-3']");
        if (!targetOpt) {
            const opts = Array.from(document.querySelectorAll("ul[role='listbox'] li[role='option'], li[data-testid*='selection-pill-option']"));
            targetOpt = opts.find(o => {
                const l = (o.getAttribute('aria-label') || o.innerText || '').toLowerCase();
                return l.includes('3 days');
            });
        }
        if (targetOpt) {
            targetOpt.click();
        } else {
            return {success: false, reason: "Option not found"};
        }
        
        // Click update
        const updateBtns = Array.from(document.querySelectorAll("button")).filter(b => {
            const txt = (b.innerText || '').trim().toLowerCase();
            return txt === 'update' || txt.includes('update');
        });
        if (updateBtns.length > 0) {
            updateBtns[0].click();
            return {success: true, updateClicked: true};
        }
        return {success: true, updateClicked: false};
    """)
    print(f"[TestFilter] Selection result: {res}")
    time.sleep(3)
    save_screenshot(driver, "test_ui_filter_after_update")
    print(f"[TestFilter] URL after update: {driver.current_url}")

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
    driver.set_page_load_timeout(30)

    try:
        print("[TestSearch] Navigating to https://in.indeed.com/ ...")
        driver.get("https://in.indeed.com/")
        time.sleep(4)

        keyword = "RPA Developer"
        location = "India"

        # Find what input
        what_elem = None
        for sel in ["#text-input-what", "input[name='q']", "input[id*='what']"]:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                if el.is_displayed():
                    what_elem = el
                    break
            if what_elem:
                break

        if what_elem:
            what_elem.click()
            time.sleep(0.3)
            what_elem.send_keys(Keys.CONTROL + "a")
            what_elem.send_keys(Keys.BACKSPACE)
            time.sleep(0.2)
            what_elem.send_keys(keyword)
            time.sleep(0.3)

        # Find where input
        where_elem = None
        for sel in ["#text-input-where", "input[name='l']", "input[id*='where']"]:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elems:
                if el.is_displayed():
                    where_elem = el
                    break
            if where_elem:
                break

        if where_elem:
            where_elem.click()
            time.sleep(0.3)
            cur_loc = where_elem.get_attribute("value") or ""
            if cur_loc.strip().lower() != location.lower():
                where_elem.send_keys(Keys.CONTROL + "a")
                where_elem.send_keys(Keys.BACKSPACE)
                time.sleep(0.2)
                where_elem.send_keys(location)
                time.sleep(0.3)

        # Submit search
        print("[TestSearch] Submitting search...")
        btn_found = False
        for sel in ["button[type='submit']", ".yosegi-InlineWhatWhere-primaryButton", "form button[type='submit']"]:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for b in elems:
                if b.is_displayed():
                    b.click()
                    btn_found = True
                    break
            if btn_found:
                break

        if not btn_found and what_elem:
            what_elem.send_keys(Keys.ENTER)

        time.sleep(4)
        print(f"[TestSearch] Search results URL: {driver.current_url}")

        apply_date_posted_filter(driver, freshness_days=3)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
