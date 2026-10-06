"""Indeed Live Portal Visual Research Script (Phase 2).
Uses authenticated ~/.jobpilot-indeed-profile to:
1. Navigate to Indeed India job search (q=RPA Developer, l=India).
2. Inspect search filters (Date posted, Easy Apply / Easily apply).
3. Extract job cards and distinguish Smart Apply vs External Apply.
4. Test clicking into job cards and launching Smart Apply in new tab.
5. Step through and inspect all multi-step form elements:
   - Contact Info (Name, Email, Phone)
   - Resume selection & 'CV options'
   - Address fields (Address, City, State, Pin code)
   - Screening questions
   - Review & Confirmation screen
6. Save comprehensive artifacts to docs/indeed_research_artifacts/
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
from selenium.common.exceptions import UnexpectedAlertPresentException, TimeoutException
import undetected_chromedriver as uc

PROFILE_DIR = os.path.expanduser("~/.jobpilot-indeed-profile")
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "indeed_research_artifacts")
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

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

def dismiss_alerts_and_popups(driver):
    try:
        alert = driver.switch_to.alert
        print(f"[Alert] Dismissed: {alert.text}")
        alert.accept()
    except Exception:
        pass

    # Check for Indeed email subscription / close modal popups
    for close_sel in [
        "//button[@aria-label='close']",
        "//button[@aria-label='Close']",
        "//div[contains(@class, 'popover')]//button",
        "//button[contains(@class, 'icl-CloseButton')]"
    ]:
        try:
            close_btns = driver.find_elements(By.XPATH, close_sel)
            for cb in close_btns:
                if cb.is_displayed():
                    cb.click()
                    print(f"[Popup] Closed modal with selector {close_sel}")
        except Exception:
            pass

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

    findings: Dict = {
        "search_url": "",
        "job_cards_count": 0,
        "sample_jobs": [],
        "selectors": {}
    }

    try:
        # Step 1: Navigate to Job Search
        search_query = "RPA Developer"
        location = "India"
        search_url = f"https://in.indeed.com/jobs?q={search_query.replace(' ', '+')}&l={location.replace(' ', '+')}"
        findings["search_url"] = search_url
        print(f"\n[Search] Navigating to: {search_url}")
        driver.get(search_url)
        time.sleep(4)
        dismiss_alerts_and_popups(driver)
        save_screenshot(driver, "40_search_results_page")

        print(f"Page Title: {driver.title}")

        # Step 2: Inspect Filter Chips / Dropdowns on Search Page
        print("\n[Filters] Inspecting filter chips...")
        filter_buttons = driver.find_elements(By.XPATH, "//div[@id='filter-dateposted'] | //button[contains(@id, 'filter-')] | //button[contains(@aria-label, 'Date posted') or contains(@aria-label, 'date posted')] | //ul[contains(@class, 'filterList')]//button")
        for fb in filter_buttons:
            if fb.is_displayed():
                print(f"Filter button: id={fb.get_attribute('id')}, text='{fb.text.strip()}'")

        # Step 3: Extract Job Cards from Results List
        print("\n[JobCards] Inspecting job cards...")
        job_card_selectors = [
            "//div[contains(@class, 'job_seen_beacon')]",
            "//div[contains(@class, 'cardOutline')]",
            "//div[contains(@class, 'slider_item')]",
            "//li[contains(@class, 'css-5lfssm')]//div[contains(@class, 'cardOutline')]",
            "//div[@id='mosaic-provider-jobcards']//li"
        ]

        job_cards = []
        chosen_card_sel = ""
        for sel in job_card_selectors:
            elems = driver.find_elements(By.XPATH, sel)
            valid = [e for e in elems if e.is_displayed() and ("₹" in e.text or "Developer" in e.text or "RPA" in e.text or len(e.text) > 30)]
            print(f"Selector '{sel}': found {len(elems)} elements, {len(valid)} valid job cards")
            if len(valid) > len(job_cards):
                job_cards = valid
                chosen_card_sel = sel

        findings["job_cards_count"] = len(job_cards)
        findings["selectors"]["job_card"] = chosen_card_sel
        print(f"Selected job card selector: {chosen_card_sel} ({len(job_cards)} cards)")

        main_window = driver.current_window_handle
        print(f"Main search window handle: {main_window}")

        # Step 4: Iterate and test 4–5 sample jobs
        sample_count = min(5, len(job_cards))
        print(f"\n[SampleJobs] Testing details and apply flow for {sample_count} jobs...")

        for i in range(sample_count):
            print(f"\n{'='*60}\nExamining Job {i+1} of {sample_count}...")
            # Re-find job cards to avoid stale element reference
            cards = driver.find_elements(By.XPATH, chosen_card_sel)
            if i >= len(cards):
                break
            card = cards[i]

            # Scroll card into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
            time.sleep(1)

            # Extract job metadata
            card_text = card.text.strip().replace("\n", " | ")
            print(f"Card raw text: {card_text[:120]}...")

            job_title = "Unknown"
            try:
                title_elem = card.find_element(By.XPATH, ".//h2[contains(@class, 'jobTitle')]//span | .//a[contains(@class, 'jcs-JobTitle')]")
                job_title = title_elem.text.strip()
            except Exception:
                pass

            company_name = "Unknown"
            try:
                comp_elem = card.find_element(By.XPATH, ".//span[@data-testid='company-name'] | .//span[contains(@class, 'companyName')]")
                company_name = comp_elem.text.strip()
            except Exception:
                pass

            is_easy_apply_badge = "Easily apply" in card.text or "Easy Apply" in card.text
            print(f"Job #{i+1}: '{job_title}' at '{company_name}' | EasyApply Badge: {is_easy_apply_badge}")

            job_info = {
                "index": i + 1,
                "title": job_title,
                "company": company_name,
                "is_easy_apply_badge": is_easy_apply_badge,
                "apply_type": "UNKNOWN",
                "apply_url": "",
                "steps_reached": []
            }

            # Click card to open right-side job details view
            try:
                title_link = card.find_element(By.XPATH, ".//a[contains(@class, 'jcs-JobTitle')] | .//h2//a")
                title_link.click()
            except Exception:
                card.click()

            time.sleep(3)
            dismiss_alerts_and_popups(driver)
            save_screenshot(driver, f"41_job_{i+1}_details_pane")

            # Inspect Apply button on details view
            apply_button = None
            apply_selectors = [
                "//div[@id='jobsearch-ViewJobPaneWrapper']//button[contains(@id, 'indeedApplyButton') or contains(., 'Apply now')]",
                "//div[@id='jobDetailsSection']//following::button[contains(., 'Apply')]",
                "//div[contains(@class, 'jobsearch-IndeedApplyButton')]//button",
                "//button[contains(@id, 'indeedApplyButton')]",
                "//button[contains(., 'Apply now')]",
                "//button[contains(., 'Apply on company site')]",
                "//a[contains(., 'Apply on company site')]"
            ]

            for a_sel in apply_selectors:
                try:
                    elems = driver.find_elements(By.XPATH, a_sel)
                    for el in elems:
                        if el.is_displayed():
                            apply_button = el
                            print(f"Found Apply Button with: {a_sel} -> text='{el.text.strip()}', tag={el.tag_name}")
                            break
                    if apply_button:
                        break
                except Exception:
                    pass

            if not apply_button:
                print(f"No visible apply button found for Job #{i+1}")
                job_info["apply_type"] = "NONE_FOUND"
                findings["sample_jobs"].append(job_info)
                continue

            btn_text = apply_button.text.strip()
            if "company site" in btn_text.lower():
                job_info["apply_type"] = "EXTERNAL"
                job_info["apply_url"] = apply_button.get_attribute("href") or "external_link"
                print(f"Job #{i+1} is EXTERNAL apply: '{btn_text}'")
                findings["sample_jobs"].append(job_info)
                continue

            # It is a Smart Apply / Easy Apply button!
            job_info["apply_type"] = "SMART_APPLY"
            print(f"Job #{i+1} is SMART APPLY ('{btn_text}')! Testing click & new tab...")

            pre_handles = driver.window_handles
            try:
                apply_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", apply_button)

            time.sleep(4)
            post_handles = driver.window_handles
            print(f"Window handles after click: pre={len(pre_handles)}, post={len(post_handles)}")

            app_window = None
            if len(post_handles) > len(pre_handles):
                app_window = [h for h in post_handles if h not in pre_handles][0]
                print(f"Switched to application tab: {app_window}")
                driver.switch_to.window(app_window)
            else:
                print("Application opened in same window or modal.")
                app_window = driver.current_window_handle

            time.sleep(3)
            save_screenshot(driver, f"42_job_{i+1}_smart_apply_step1")
            print(f"App tab Title: '{driver.title}', URL: {driver.current_url}")

            # Inspect Step 1 (Contact info or Resume)
            body_text = driver.find_element(By.TAG_NAME, "body").text
            print(f"App step text snippet: {body_text[:180].replace(chr(10), ' ')}")

            # Check for input fields
            inputs = driver.find_elements(By.XPATH, "//input")
            input_details = []
            for inp in inputs:
                if inp.is_displayed():
                    input_details.append(f"{inp.get_attribute('id') or inp.get_attribute('name')} ({inp.get_attribute('type')})")
            print(f"Visible inputs on step: {input_details}")
            job_info["steps_reached"].append({
                "step": 1,
                "url": driver.current_url,
                "inputs": input_details
            })

            # Check for 'Continue' or 'Review your application' button
            cont_btn = None
            for cb_sel in [
                "//button[contains(., 'Continue')]",
                "//button[contains(., 'Next')]",
                "//button[contains(., 'Review your application')]",
                "//button[@type='submit']"
            ]:
                try:
                    cbs = driver.find_elements(By.XPATH, cb_sel)
                    for c in cbs:
                        if c.is_displayed():
                            cont_btn = c
                            break
                    if cont_btn:
                        break
                except Exception:
                    pass

            if cont_btn:
                print(f"Clicking Continue button on Step 1: '{cont_btn.text.strip()}'...")
                try:
                    cont_btn.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", cont_btn)

                time.sleep(3)
                save_screenshot(driver, f"43_job_{i+1}_smart_apply_step2")
                print(f"App Step 2 Title: '{driver.title}', URL: {driver.current_url}")

                # Check Step 2 content (e.g. CV options / Resume / Questions)
                step2_inputs = [inp.get_attribute('id') or inp.get_attribute('name') for inp in driver.find_elements(By.XPATH, "//input") if inp.is_displayed()]
                print(f"Step 2 inputs: {step2_inputs}")
                job_info["steps_reached"].append({
                    "step": 2,
                    "url": driver.current_url,
                    "inputs": step2_inputs
                })

            # Clean up: Close application tab and return to main window
            if app_window and app_window != main_window:
                print(f"Closing application tab {app_window}...")
                driver.close()
                driver.switch_to.window(main_window)
                print("Returned to main search window.")
            time.sleep(2)

            findings["sample_jobs"].append(job_info)

        # Step 5: Save findings JSON report
        report_path = os.path.join(ARTIFACTS_DIR, "indeed_research_findings.json")
        with open(report_path, "w") as f:
            json.dump(findings, f, indent=2)
        print(f"\n[Report] Findings saved to: {report_path}")

    finally:
        driver.quit()
        print("Driver closed.")

if __name__ == "__main__":
    main()
