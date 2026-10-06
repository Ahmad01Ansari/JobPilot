'''
Glassdoor Job Parser & Description Extractor
Extracts card metadata, parses details pane, and retrieves full Job Descriptions with multi-level fallbacks.
'''

import re
import json
from typing import Optional, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from platforms.glassdoor.search import GlassdoorJobItem
from platforms.glassdoor.selectors import (
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_RATING_SELECTORS,
    CARD_EASY_APPLY_INDICATORS,
    CARD_ALREADY_APPLIED_INDICATORS,
    DETAILS_PANE_SELECTORS,
    DETAIL_TITLE_SELECTORS,
    DETAIL_COMPANY_SELECTORS,
    DETAIL_LOCATION_SELECTORS,
    JOB_DESCRIPTION_SELECTORS,
    JD_SHOW_MORE_BUTTONS,
)
from modules.helpers import print_lg


def clean_text(text: Optional[str]) -> str:
    """Removes extra whitespaces, newlines, and strips text."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()


def is_valid_job_description(text: Optional[str]) -> bool:
    """Validates that extracted JD text is genuine content and not a placeholder or login wall."""
    if not text:
        return False
    cleaned = clean_text(text)
    if len(cleaned) < 40:
        return False
    # Reject error or login stubs
    lower = cleaned.lower()
    if "sign in to view" in lower or "please log in" in lower:
        return False
    return True


class GlassdoorParser:
    """Extracts job attributes and descriptions from Glassdoor DOM."""

    @staticmethod
    def parse_job_card(
        card: WebElement,
        card_index: int = 0,
        default_easy_apply: bool = False,
    ) -> Optional[GlassdoorJobItem]:
        """Parses a single job card element from SRP into GlassdoorJobItem."""
        try:
            # 1. Title
            title = ""
            for sel in CARD_TITLE_SELECTORS:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        title = clean_text(el.text)
                        break
                except Exception:
                    continue

            if not title:
                return None

            # 2. Company
            company = ""
            for sel in CARD_COMPANY_SELECTORS:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        company = clean_text(el.text)
                        break
                except Exception:
                    continue

            # 3. Location
            location = ""
            for sel in CARD_LOCATION_SELECTORS:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        location = clean_text(el.text)
                        break
                except Exception:
                    continue

            # 4. Salary
            salary = None
            for sel in CARD_SALARY_SELECTORS:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        salary = clean_text(el.text)
                        break
                except Exception:
                    continue

            # 5. Rating
            rating = None
            for sel in CARD_RATING_SELECTORS:
                try:
                    el = card.find_element(By.CSS_SELECTOR, sel)
                    if el.text.strip():
                        rating = clean_text(el.text)
                        break
                except Exception:
                    continue

            # 6. Easy Apply & Applied Status
            is_easy_apply = bool(default_easy_apply)
            if not is_easy_apply:
                for sel in CARD_EASY_APPLY_INDICATORS:
                    try:
                        by = By.XPATH if (sel.startswith("/") or sel.startswith(".")) else By.CSS_SELECTOR
                        elems = card.find_elements(by, sel)
                        if any(e.is_displayed() for e in elems):
                            is_easy_apply = True
                            break
                    except Exception:
                        continue

            if not is_easy_apply:
                try:
                    card_txt = (card.text or "").lower()
                    if "easy apply" in card_txt:
                        is_easy_apply = True
                except Exception:
                    pass

            is_applied = False
            for sel in CARD_ALREADY_APPLIED_INDICATORS:
                try:
                    elems = card.find_elements(By.XPATH, sel)
                    if any(e.is_displayed() for e in elems):
                        is_applied = True
                        break
                except Exception:
                    continue

            # 7. Job ID & URL
            job_id = card.get_attribute("data-jobid") or card.get_attribute("data-id") or ""
            job_url = ""
            try:
                link_el = card.find_element(By.CSS_SELECTOR, "a[data-test='job-title'], a[href*='/job-listing/'], a")
                job_url = link_el.get_attribute("href") or ""
                if not job_id and job_url:
                    match = re.search(r'jobListingId=(\d+)|jl=(\d+)', job_url)
                    if match:
                        job_id = match.group(1) or match.group(2)
            except Exception:
                pass

            if not job_id:
                job_id = f"gd_{abs(hash(title + company + location))}"

            return GlassdoorJobItem(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                job_url=job_url,
                salary=salary,
                rating=rating,
                is_easy_apply=is_easy_apply,
                is_applied=is_applied,
                card_element=card,
                card_index=card_index,
            )
        except Exception as e:
            print_lg(f"[GlassdoorParser] Error parsing job card: {e}")
            return None

    @staticmethod
    def extract_job_description(driver: Any) -> str:
        """Extracts complete job description text with multi-tier fallbacks."""
        if not driver:
            return ""

        # Level 0: Active JS extraction from details pane
        try:
            js_text = driver.execute_script('''
                var el = document.querySelector("#jobDescriptionText") ||
                         document.querySelector("[data-test='jobDescriptionContent']") ||
                         document.querySelector("div[class*='jobDescription']") ||
                         document.querySelector("#JobDescriptionContainer") ||
                         document.querySelector("div[data-test='job-description']") ||
                         document.querySelector("div[class*='JobDetails_jobDetailsContainer']") ||
                         document.querySelector("section[class*='JobDetails']") ||
                         document.querySelector("main[class*='JobDetails']");
                if (el) {
                    var t = (el.innerText || el.textContent || '').trim();
                    if (t.length > 40) return t;
                }
                return "";
            ''')
            if js_text and is_valid_job_description(js_text):
                return clean_text(js_text)
        except Exception:
            pass

        # Expand "Show More" if present
        for sel in JD_SHOW_MORE_BUTTONS:
            try:
                btns = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        break
            except Exception:
                continue

        # Level 1: Primary JD Containers
        for sel in JOB_DESCRIPTION_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                for el in elems:
                    text = el.text or el.get_attribute("innerText") or ""
                    if is_valid_job_description(text):
                        return clean_text(text)
            except Exception:
                continue

        # Level 2: JSON-LD Structured Data
        try:
            scripts = driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            for s in scripts:
                content = s.get_attribute("innerHTML") or ""
                if "JobPosting" in content:
                    data = json.loads(content)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        desc = data.get("description", "")
                        if is_valid_job_description(desc):
                            return clean_text(desc)
        except Exception:
            pass

        return ""
