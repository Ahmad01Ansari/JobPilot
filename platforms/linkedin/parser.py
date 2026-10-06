"""LinkedIn Job Parser.

Extracts structured job attributes, descriptions, and application methods from LinkedIn listings.
"""

import re
from typing import Optional, Dict, Any, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job
from platforms.linkedin.selectors import (
    JOB_DESCRIPTION_SELECTORS,
    JOB_TITLE_SELECTORS,
    JOB_COMPANY_SELECTORS,
    JOB_LOCATION_SELECTORS,
    EASY_APPLY_BUTTON_XPATHS,
)


class LinkedInJobParser:
    """Parses LinkedIn job cards and detail panes into structured data."""

    @staticmethod
    def extract_job_id_from_card(card_element: WebElement) -> Optional[str]:
        """Extracts LinkedIn job ID from card attributes or anchor links."""
        # 1. Direct attribute on element
        for attr in ["data-job-id", "data-occludable-job-id"]:
            val = card_element.get_attribute(attr)
            if val and val.strip().isdigit():
                return val.strip()

        # 2. Look for child anchor with /jobs/view/<id>
        try:
            links = card_element.find_elements(By.XPATH, ".//a[contains(@href, '/jobs/view/')]")
            for link in links:
                href = link.get_attribute("href") or ""
                match = re.search(r"/jobs/view/(\d+)", href)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    @staticmethod
    def extract_title(driver) -> str:
        """Extracts job title from current active details pane."""
        for selector in JOB_TITLE_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text:
                        return text
            except Exception:
                continue
        return "Unknown Title"

    @staticmethod
    def extract_company(driver) -> str:
        """Extracts company name from current active details pane."""
        for selector in JOB_COMPANY_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text:
                        return text.split("\n")[0].strip()
            except Exception:
                continue
        return "Unknown Company"

    @staticmethod
    def extract_location(driver) -> str:
        """Extracts job location from current active details pane."""
        for selector in JOB_LOCATION_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text:
                        return text.split("·")[0].strip()
            except Exception:
                continue
        return "Unknown Location"

    @staticmethod
    def extract_full_description(driver) -> str:
        """Extracts complete plain-text job description across modern LinkedIn variants."""
        for selector in JOB_DESCRIPTION_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if len(text) > 40:
                        return text
            except Exception:
                continue
        return ""

    @staticmethod
    def detect_application_method(driver) -> Tuple[str, Optional[str]]:
        """Determines if the job is EASY_APPLY or COMPANY_PORTAL, plus external link if present.
        
        Returns:
            Tuple of (application_method: "EASY_APPLY" | "COMPANY_PORTAL", application_url: Optional[str])
        """
        # Check classic Easy Apply button
        for xpath in EASY_APPLY_BUTTON_XPATHS[:2]:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                if any(e.is_displayed() for e in elems):
                    return ("EASY_APPLY", None)
            except Exception:
                pass

        # Check URL pattern on apply link
        try:
            elems = driver.find_elements(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
            if any(e.is_displayed() for e in elems):
                return ("EASY_APPLY", None)
        except Exception:
            pass

        # Check if button leads externally
        try:
            apply_buttons = driver.find_elements(By.XPATH, ".//button[contains(@class,'jobs-apply-button')]")
            for btn in apply_buttons:
                if btn.is_displayed():
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    if "easy" in aria:
                        return ("EASY_APPLY", None)
                    # Often external apply has aria-label="Apply to ... on company website"
                    if "company website" in aria or "external" in aria:
                        return ("COMPANY_PORTAL", None)
        except Exception:
            pass

        return ("COMPANY_PORTAL", None)
