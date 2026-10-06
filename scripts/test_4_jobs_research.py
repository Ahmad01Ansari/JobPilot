"""Phase 2 Research: Automated Multi-Job Application Flow Analysis (v2).
Handles async step transitions, dynamic waits, screening questions,
and tab closing across 4 sample jobs.
"""

import os
import sys
import time
import subprocess
import re
import json
from typing import Optional, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException
)
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

def click_element_safely(driver, elem):
    try:
        elem.click()
    except Exception:
        driver.execute_script("arguments[0].click();", elem)

def fill_field_if_empty(driver, elem, val: str):
    try:
        existing = elem.get_attribute("value") or ""
        if not existing.strip():
            elem.clear()
            elem.send_keys(val)
            print(f"      [AutoFill] Filled '{val}' into {elem.get_attribute('name') or elem.get_attribute('id')}")
    except Exception:
        pass

def wait_for_step_transition(driver, old_url: str, timeout: int = 10) -> bool:
    """Waits until URL changes or spinner disappears."""
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(1)
        cur_url = driver.current_url
        if cur_url != old_url:
            return True
        # Check if spinner is gone
        spinners = driver.find_elements(By.XPATH, "//div[contains(@class, 'spinner') or contains(@class, 'loading')] | //button[@disabled and contains(., '')]")
        if not any(s.is_displayed() for s in spinners):
            # Check if a new heading or form appeared
            return True
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

    report_jobs: List[Dict] = []

    try:
        search_url = "https://in.indeed.com/jobs?q=RPA+Developer&l=India"
        print(f"\n[Search] Navigating to: {search_url}")
        driver.get(search_url)
        time.sleep(4)

        main_window = driver.current_window_handle
        print(f"Main search window handle: {main_window}")

        cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
        print(f"Discovered {len(cards)} job cards on page")

        total_to_test = min(4, len(cards))

        for idx in range(total_to_test):
            print(f"\n{'='*70}\n[JOB #{idx+1} OF {total_to_test}] STARTING ANALYSIS\n{'='*70}")
            
            # Re-fetch cards
            current_cards = driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
            if idx >= len(current_cards):
                break
            card = current_cards[idx]
            
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(1)

            title_elem = card.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
            job_title = title_elem.text.strip()
            
            company_name = "Unknown"
            try:
                company_name = card.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']").text.strip()
            except Exception:
                pass

            location_name = "India"
            try:
                location_name = card.find_element(By.CSS_SELECTOR, "div[data-testid='text-location']").text.strip()
            except Exception:
                pass

            card_has_easy_apply = "Easily apply" in card.text or "Easy Apply" in card.text
            
            print(f"Title:    {job_title}")
            print(f"Company:  {company_name}")
            print(f"Location: {location_name}")
            print(f"Badge:    {'Easily apply' if card_has_easy_apply else 'Company Apply'}")

            job_data = {
                "index": idx + 1,
                "title": job_title,
                "company": company_name,
                "location": location_name,
                "has_easy_apply_badge": card_has_easy_apply,
                "apply_mode": "",
                "steps_completed": [],
                "questions_encountered": []
            }

            # Click job title to open details view
            click_element_safely(driver, title_elem)
            time.sleep(3)
            save_screenshot(driver, f"job_{idx+1}_details_pane")

            # Check for Apply button
            apply_now_elems = driver.find_elements(By.XPATH, "//div[text()='Apply now'] | //*[text()='Apply now'] | //button[contains(., 'Apply now')]")
            external_apply_elems = driver.find_elements(By.XPATH, "//*[contains(text(), 'Apply on company site')] | //button[contains(., 'Apply on company site')] | //a[contains(., 'Apply on company site')]")

            if external_apply_elems and not apply_now_elems:
                job_data["apply_mode"] = "EXTERNAL"
                print(f"Result: EXTERNAL JOB ('Apply on company site'). Skipping external redirect as per rule.")
                report_jobs.append(job_data)
                continue

            if not apply_now_elems:
                print(f"Result: No Apply now button found (Already applied or unavailable).")
                job_data["apply_mode"] = "UNAVAILABLE"
                report_jobs.append(job_data)
                continue

            job_data["apply_mode"] = "SMART_APPLY"
            apply_target = apply_now_elems[0]
            try:
                parent = apply_target.find_element(By.XPATH, "..")
                if parent.tag_name in ["button", "a", "div"]:
                    apply_target = parent
            except Exception:
                pass

            pre_click_handles = driver.window_handles
            print("Clicking 'Apply now' button...")
            click_element_safely(driver, apply_target)
            time.sleep(4)

            post_click_handles = driver.window_handles
            app_tab = None
            if len(post_click_handles) > len(pre_click_handles):
                app_tab = [h for h in post_click_handles if h not in pre_click_handles][0]
                print(f"Switched to Smart Apply tab: {app_tab}")
                driver.switch_to.window(app_tab)
            else:
                print("Smart Apply opened in current window.")
                app_tab = driver.current_window_handle

            time.sleep(3)

            # Process form steps
            for step in range(1, 8):
                time.sleep(2)
                cur_url = driver.current_url
                save_screenshot(driver, f"job_{idx+1}_step_{step}")
                print(f"\n   --- Step {step} | URL: {cur_url} ---")

                # Detect step heading
                step_title = ""
                try:
                    for h_sel in ["h1", "h2", "legend", "div[role='heading']"]:
                        for he in driver.find_elements(By.CSS_SELECTOR, h_sel):
                            if he.is_displayed() and he.text.strip():
                                step_title = he.text.strip()
                                break
                        if step_title:
                            break
                except Exception:
                    pass

                print(f"   Step Title: '{step_title}'")
                job_data["steps_completed"].append(f"Step {step}: {step_title or 'Form'}")

                # 1. Contact Information
                if "contact" in step_title.lower() or "contact-info" in cur_url:
                    print("   [Step: Contact Info] Verifying name, email, phone...")
                    for el in driver.find_elements(By.XPATH, "//input[contains(@name, 'first-name')]"):
                        fill_field_if_empty(driver, el, CANDIDATE["first_name"])
                    for el in driver.find_elements(By.XPATH, "//input[contains(@name, 'last-name')]"):
                        fill_field_if_empty(driver, el, CANDIDATE["last_name"])

                # 2. Location / Address
                elif "location" in step_title.lower() or "address" in step_title.lower() or "address" in cur_url:
                    print("   [Step: Location] Auto-filling city, postal code, street...")
                    for el in driver.find_elements(By.XPATH, "//input[contains(@id, 'postal-code') or contains(@name, 'postal-code')]"):
                        fill_field_if_empty(driver, el, CANDIDATE["zipcode"])
                    for el in driver.find_elements(By.XPATH, "//input[contains(@id, 'locality') or contains(@name, 'locality')]"):
                        fill_field_if_empty(driver, el, CANDIDATE["city"])
                    for el in driver.find_elements(By.XPATH, "//input[contains(@id, 'address') or contains(@name, 'address')]"):
                        fill_field_if_empty(driver, el, CANDIDATE["street"])

                # 3. Resume Selection
                elif "resume" in step_title.lower() or "cv" in step_title.lower() or "resume-selection" in cur_url:
                    print("   [Step: Resume] Resume already selected. Checking 'CV options'...")
                    cv_opts = driver.find_elements(By.XPATH, "//button[contains(., 'CV options') or contains(., 'Resume options')]")
                    if cv_opts and cv_opts[0].is_displayed():
                        print(f"      CV options button present: '{cv_opts[0].text.strip()}'")

                # 4. Screening Questions
                q_items = driver.find_elements(By.XPATH, "//fieldset | //div[contains(@class, 'ia-Questions')]//div[contains(@class, 'item')]")
                if q_items:
                    print(f"   [Step: Questions] Found {len(q_items)} screening questions:")
                    for q in q_items:
                        try:
                            qt = q.text.strip().replace("\n", " ")
                            if qt:
                                print(f"      Q: {qt[:80]}...")
                                job_data["questions_encountered"].append(qt[:80])
                                # If there's an empty text/number input, fill default
                                for inp in q.find_elements(By.XPATH, ".//input[@type='text' or @type='number']"):
                                    if not (inp.get_attribute("value") or "").strip():
                                        inp.send_keys("2")
                        except Exception:
                            pass

                # Check for Review & Final Submit Button
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
                    print(f"\n   >>> REACHED FINAL REVIEW/SUBMIT SCREEN: '{submit_btn.text.strip()}'!")
                    save_screenshot(driver, f"job_{idx+1}_final_review_screen")
                    print("   (Preserving real application: not clicking final submit during research probe)")
                    break

                # Advance button
                continue_btn = None
                for c_sel in [
                    "//button[contains(., 'Continue')]",
                    "//button[contains(., 'Next')]",
                    "//button[contains(., 'Review your application')]",
                    "//button[@type='submit']"
                ]:
                    try:
                        for cb in driver.find_elements(By.XPATH, c_sel):
                            if cb.is_displayed():
                                continue_btn = cb
                                break
                        if continue_btn:
                            break
                    except Exception:
                        pass

                if not continue_btn:
                    print(f"   No continue button visible on step {step}. Form completed or stopped.")
                    break

                btn_label = continue_btn.text.strip()
                print(f"   Clicking '{btn_label}'...")
                click_element_safely(driver, continue_btn)
                
                # Wait for transition
                wait_for_step_transition(driver, cur_url, timeout=6)
                time.sleep(2)

            # Close application tab and return
            if app_tab and app_tab != main_window:
                print(f"Closing application tab {app_tab}...")
                driver.close()
                driver.switch_to.window(main_window)
                print("Successfully returned to main search window.")
                time.sleep(2)

            report_jobs.append(job_data)

        # Write final JSON findings
        findings_file = os.path.join(ARTIFACTS_DIR, "live_4_jobs_research_findings.json")
        with open(findings_file, "w") as f:
            json.dump(report_jobs, f, indent=2)
        print(f"\n[Report] Live 4-job test findings saved to: {findings_file}")

    finally:
        driver.quit()
        print("[Done] Research session complete and browser closed.")

if __name__ == "__main__":
    main()
