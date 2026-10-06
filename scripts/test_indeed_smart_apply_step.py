"""Step-by-step test for Indeed Smart Apply flow on real job listing.
Inspects Contact Info, Resume upload / CV options, Address, Questions, and Submit steps.
"""

import os
import sys
import time
import subprocess
import re
from typing import Optional, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc

PROFILE_DIR = os.path.expanduser("~/.jobpilot-indeed-profile")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "indeed_research_artifacts")
os.makedirs(PROFILE_DIR, exist_ok=True)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

CANDIDATE = {
    "first_name": "Mohd Ahmad Raza",
    "last_name": "Ansari",
    "email": "candidate@example.com",
    "phone": "+916388623967",
    "city": "Delhi",
    "state": "Delhi",
    "zipcode": "110001",
    "street": "Delhi"
}

def save_screenshot(driver, name: str):
    path = os.path.join(ARTIFACTS_DIR, f"{name}.png")
    try:
        driver.save_screenshot(path)
        print(f"[Screenshot] Saved: {path}")
    except Exception as e:
        print(f"[Screenshot] Failed: {e}")
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

def click_element_safely(driver, elem):
    try:
        elem.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

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
        search_url = "https://in.indeed.com/jobs?q=RPA+Developer&l=India"
        print(f"Navigating to {search_url} ...")
        driver.get(search_url)
        time.sleep(4)

        main_window = driver.current_window_handle
        print(f"Main search window: {main_window}")

        # Find job card
        cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
        print(f"Found {len(cards)} job cards")
        if not cards:
            print("No job cards found!")
            return

        # Pick first card
        target_card = cards[0]
        title_link = target_card.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
        job_title = title_link.text.strip()
        print(f"Selected Job: '{job_title}'")

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_card)
        time.sleep(1)
        click_element_safely(driver, title_link)
        time.sleep(3)

        save_screenshot(driver, "60_job_details_view")

        # Find Apply now button
        apply_elem = None
        for sel in [
            "//div[text()='Apply now']",
            "//*[text()='Apply now']",
            "//button[contains(., 'Apply now')]",
            "//a[contains(., 'Apply now')]"
        ]:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        apply_elem = el
                        break
                if apply_elem:
                    break
            except Exception:
                pass

        if not apply_elem:
            print("ERROR: Could not locate Apply now button!")
            return

        print(f"Located Apply now element: tag={apply_elem.tag_name}, text='{apply_elem.text}'")

        initial_windows = driver.window_handles
        # Click the element (or its parent)
        click_target = apply_elem
        try:
            parent = apply_elem.find_element(By.XPATH, "..")
            if parent.tag_name in ["button", "a", "div"]:
                click_target = parent
        except Exception:
            pass

        print(f"Clicking apply element: {click_target.tag_name}...")
        click_element_safely(driver, click_target)

        # Wait for new tab
        time.sleep(5)
        current_windows = driver.window_handles
        print(f"Windows after apply click: {current_windows}")

        if len(current_windows) > len(initial_windows):
            app_tab = [w for w in current_windows if w not in initial_windows][0]
            print(f"Switched to application tab: {app_tab}")
            driver.switch_to.window(app_tab)
        else:
            print("Opened in same window.")

        time.sleep(3)
        print(f"Application Tab Title: '{driver.title}', URL: {driver.current_url}")

        # Loop through application steps (up to 6 steps)
        for step_num in range(1, 7):
            print(f"\n{'='*50}\n--- Application Step {step_num} ---")
            time.sleep(2)
            save_screenshot(driver, f"61_app_step_{step_num}")

            # Print Step Heading / Header
            try:
                h1 = driver.find_element(By.TAG_NAME, "h1")
                print(f"Step {step_num} Title (h1): '{h1.text.strip()}'")
            except Exception:
                pass

            # Inspect all inputs on page
            inputs = driver.find_elements(By.XPATH, "//input | //select | //textarea")
            print(f"Found {len(inputs)} inputs on step {step_num}:")
            for inp in inputs:
                if inp.is_displayed():
                    tag = inp.tag_name
                    inp_id = inp.get_attribute("id") or ""
                    inp_name = inp.get_attribute("name") or ""
                    inp_type = inp.get_attribute("type") or ""
                    inp_val = inp.get_attribute("value") or ""
                    print(f"  - tag={tag}, id='{inp_id}', name='{inp_name}', type='{inp_type}', value='{inp_val}'")

            # Check for CV options button / Resume upload
            cv_opts = driver.find_elements(By.XPATH, "//button[contains(., 'CV options') or contains(., 'Resume options')] | //button[contains(@aria-label, 'options')]")
            for cv in cv_opts:
                if cv.is_displayed():
                    print(f"  [Resume] CV Options button visible: '{cv.text.strip()}'")

            # Check for Final Submit button
            submit_btn = None
            for s_sel in [
                "//button[contains(., 'Submit your application')]",
                "//button[contains(., 'Submit application')]",
                "//button[contains(., 'Apply now') and contains(@class, 'ia-')]"
            ]:
                try:
                    for sb in driver.find_elements(By.XPATH, s_sel):
                        if sb.is_displayed():
                            submit_btn = sb
                            break
                    if submit_btn:
                        break
                except Exception:
                    pass

            if submit_btn:
                print(f">>> FINAL SUBMIT BUTTON FOUND: '{submit_btn.text.strip()}' (id='{submit_btn.get_attribute('id')}')")
                save_screenshot(driver, f"62_final_submit_ready_step_{step_num}")
                print("Step analysis complete: Reached final review/submit screen!")
                break

            # Check for 'Continue' or 'Next' or 'Review your application' button to advance
            next_btn = None
            for n_sel in [
                "//button[contains(., 'Continue')]",
                "//button[contains(., 'Next')]",
                "//button[contains(., 'Review your application')]",
                "//button[@type='submit']"
            ]:
                try:
                    for nb in driver.find_elements(By.XPATH, n_sel):
                        if nb.is_displayed():
                            next_btn = nb
                            break
                    if next_btn:
                        break
                except Exception:
                    pass

            if not next_btn:
                print(f"No Continue button found on Step {step_num}. Checking text on page...")
                body_txt = driver.find_element(By.TAG_NAME, "body").text
                print(f"Page text snippet: {body_txt[:200].replace(chr(10), ' ')}")
                break

            print(f"Clicking Continue on Step {step_num}: '{next_btn.text.strip()}'...")
            click_element_safely(driver, next_btn)
            time.sleep(3)

        # Close application tab and return
        if len(driver.window_handles) > 1:
            print("Closing application tab...")
            driver.close()
            driver.switch_to.window(main_window)
            print("Returned to main search window.")

        time.sleep(5)
    finally:
        driver.quit()
        print("Test finished and browser quit.")

if __name__ == "__main__":
    main()
