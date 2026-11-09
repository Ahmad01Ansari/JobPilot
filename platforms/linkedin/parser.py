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
        """Extracts LinkedIn job ID from card attributes, child elements, or anchor links."""
        # 1. Check componentkey attribute (Genesis SDUI: componentkey="job-card-component-ref-4459126215")
        for ck_attr in ["componentkey", "data-component-key"]:
            try:
                ck = card_element.get_attribute(ck_attr)
                if ck:
                    m = re.search(r"job-card-component-ref-(\d+)", str(ck))
                    if m:
                        return m.group(1)
                    m_num = re.search(r"(\d{8,})", str(ck))
                    if m_num:
                        return m_num.group(1)
            except Exception:
                pass

        # 2. Direct attributes on card element
        for attr in ["data-job-id", "data-occludable-job-id", "data-chameleon-result-urn", "data-entity-urn"]:
            try:
                val = card_element.get_attribute(attr)
                if val:
                    val_str = str(val).strip()
                    if val_str.isdigit():
                        return val_str
                    # Check for URN pattern urn:li:fsd_jobPosting:12345678 or trailing digits
                    urn_match = re.search(r"(?:jobPosting:|job_id=|_item_)(\d+)", val_str)
                    if urn_match:
                        return urn_match.group(1)
                    # Generic long numeric string in attribute (6+ digits)
                    num_match = re.search(r"(\d{6,})", val_str)
                    if num_match:
                        return num_match.group(1)
            except Exception:
                pass

        # Safe check on id attribute (avoiding ember auto-generated component IDs)
        try:
            elem_id = card_element.get_attribute("id")
            if elem_id:
                id_str = str(elem_id).strip()
                if not id_str.lower().startswith("ember") and any(k in id_str.lower() for k in ["job", "posting"]):
                    m = re.search(r"(\d+)", id_str)
                    if m:
                        return m.group(1)
        except Exception:
            pass

        # 3. Look in child elements with job ID attributes or componentkey
        try:
            child_elems = card_element.find_elements(
                By.XPATH, ".//*[@data-job-id or @data-occludable-job-id or @data-entity-urn or @data-chameleon-result-urn or @componentkey]"
            )
            for child in child_elems:
                # Check componentkey on children first
                ck = child.get_attribute("componentkey")
                if ck:
                    m = re.search(r"job-card-component-ref-(\d+)", str(ck))
                    if m:
                        return m.group(1)
                for attr in ["data-job-id", "data-occludable-job-id", "data-entity-urn", "data-chameleon-result-urn"]:
                    val = child.get_attribute(attr)
                    if val:
                        val_str = str(val).strip()
                        if val_str.isdigit():
                            return val_str
                        match = re.search(r"(?:jobPosting:|job_id=|_item_)(\d+)", val_str)
                        if match:
                            return match.group(1)
                        m6 = re.search(r"(\d{6,})", val_str)
                        if m6:
                            return m6.group(1)
        except Exception:
            pass

        # 4. Look for child anchor with /jobs/view/<id> or currentJobId=<id>
        try:
            links = card_element.find_elements(
                By.XPATH,
                ".//a[contains(@href, '/jobs/view/') or contains(@href, 'currentJobId=') or contains(@href, 'jobId=')]"
            )
            for link in links:
                href = link.get_attribute("href") or ""
                match = re.search(r"(?:/jobs/view/|currentJobId=|jobId=)(\d+)", href)
                if match:
                    return match.group(1)
        except Exception:
            pass

        # 5. Fallback search across all child anchors
        try:
            anchors = card_element.find_elements(By.TAG_NAME, "a")
            for a in anchors:
                href = a.get_attribute("href") or ""
                match = re.search(r"(?:/jobs/view/|currentJobId=|jobId=)(\d+)", href)
                if match:
                    return match.group(1)
        except Exception:
            pass

        return None

    @staticmethod
    def extract_title(driver, card_element: Optional[WebElement] = None) -> str:
        """Extracts job title from current active details pane or card fallback."""
        for selector in JOB_TITLE_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text and len(text) > 2 and "\n" not in text:
                        return text
            except Exception:
                continue

        # Fallback to card element
        if card_element:
            for card_sel in ["a.job-card-list__title", ".job-card-container__link", "a[data-control-id]", "h2", "h3"]:
                try:
                    elems = card_element.find_elements(By.CSS_SELECTOR, card_sel)
                    for el in elems:
                        text = el.text.strip()
                        if text:
                            return text.split("\n")[0].strip()
                except Exception:
                    continue

            # Fallback to parsing card text lines (Genesis SDUI)
            try:
                raw_text = card_element.text.strip()
                if raw_text:
                    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                    for line in lines:
                        c = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", line, flags=re.IGNORECASE).strip()
                        c = re.sub(r"\s*\(Verified\s*job\)$", "", c, flags=re.IGNORECASE).strip()
                        if len(c) > 2 and not any(k in c.lower() for k in ["saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            return c
            except Exception:
                pass

        return "Unknown Title"

    @staticmethod
    def extract_company(driver, card_element: Optional[WebElement] = None) -> str:
        """Extracts company name from current active details pane or card fallback."""
        for selector in JOB_COMPANY_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text and len(text) > 1:
                        return text.split("\n")[0].strip()
            except Exception:
                continue

        # Fallback to card element
        if card_element:
            for card_sel in [".job-card-container__company-name", ".artdeco-entity-lockup__subtitle", ".job-card-container__primary-description"]:
                try:
                    elems = card_element.find_elements(By.CSS_SELECTOR, card_sel)
                    for el in elems:
                        text = el.text.strip()
                        if text:
                            return text.split("\n")[0].strip()
                except Exception:
                    continue

            # Fallback to parsing card text lines (Genesis SDUI)
            try:
                raw_text = card_element.text.strip()
                if raw_text:
                    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                    extracted_title = ""
                    for line in lines:
                        c = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", line, flags=re.IGNORECASE).strip()
                        c = re.sub(r"\s*\(Verified\s*job\)$", "", c, flags=re.IGNORECASE).strip()
                        if len(c) > 2 and not any(k in c.lower() for k in ["saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            extracted_title = c.lower()
                            break

                    for line in lines:
                        c = line.split("·")[0].strip()
                        clean_line = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", c, flags=re.IGNORECASE).strip()
                        clean_line = re.sub(r"\s*\(Verified\s*job\)$", "", clean_line, flags=re.IGNORECASE).strip()
                        if clean_line.lower() == extracted_title or clean_line.lower() in extracted_title or extracted_title in clean_line.lower():
                            continue
                        if not any(k in clean_line.lower() for k in ["selected", "verified", "saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            return clean_line
            except Exception:
                pass

        return "Unknown Company"

    @staticmethod
    def extract_location(driver, card_element: Optional[WebElement] = None) -> str:
        """Extracts job location from current active details pane or card fallback."""
        for selector in JOB_LOCATION_SELECTORS:
            try:
                elems = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elems:
                    text = el.text.strip()
                    if text and len(text) > 1:
                        return text.split("·")[0].strip()
            except Exception:
                continue

        # Fallback to card element
        if card_element:
            for card_sel in [".job-card-container__metadata-item", ".artdeco-entity-lockup__caption"]:
                try:
                    elems = card_element.find_elements(By.CSS_SELECTOR, card_sel)
                    for el in elems:
                        text = el.text.strip()
                        if text:
                            return text.split("·")[0].strip()
                except Exception:
                    continue

            # Fallback to parsing card text lines (Genesis SDUI)
            try:
                raw_text = card_element.text.strip()
                if raw_text:
                    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
                    extracted_title = ""
                    extracted_company = ""
                    for line in lines:
                        c = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", line, flags=re.IGNORECASE).strip()
                        c = re.sub(r"\s*\(Verified\s*job\)$", "", c, flags=re.IGNORECASE).strip()
                        if len(c) > 2 and not any(k in c.lower() for k in ["saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            extracted_title = c.lower()
                            break

                    for line in lines:
                        c = line.split("·")[0].strip()
                        clean_line = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", c, flags=re.IGNORECASE).strip()
                        clean_line = re.sub(r"\s*\(Verified\s*job\)$", "", clean_line, flags=re.IGNORECASE).strip()
                        if clean_line.lower() == extracted_title or clean_line.lower() in extracted_title:
                            continue
                        if not any(k in clean_line.lower() for k in ["selected", "verified", "saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            extracted_company = clean_line.lower()
                            break

                    for line in lines:
                        c = line.split("·")[0].strip()
                        clean_line = re.sub(r"^(Selected,\s*|Verified\s*job\s*)", "", c, flags=re.IGNORECASE).strip()
                        clean_line = re.sub(r"\s*\(Verified\s*job\)$", "", clean_line, flags=re.IGNORECASE).strip()
                        if clean_line.lower() in (extracted_title, extracted_company) or extracted_title in clean_line.lower():
                            continue
                        if not any(k in clean_line.lower() for k in ["selected", "verified", "saved", "alumni", "easy apply", "actively", "reviewing", "applied", "·"]):
                            return clean_line
            except Exception:
                pass

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
        # Check Easy Apply button across all xpath variants
        for xpath in EASY_APPLY_BUTTON_XPATHS:
            try:
                elems = driver.find_elements(By.XPATH, xpath)
                for el in elems:
                    if getattr(el, "is_displayed", lambda: True)():
                        aria = (el.get_attribute("aria-label") or "").lower()
                        text = (getattr(el, "text", "") or "").lower()
                        if "easy apply" in aria or "easy apply" in text or "openSDUIApplyFlow" in (el.get_attribute("href") or ""):
                            return ("EASY_APPLY", None)
            except Exception:
                pass

        # Check for external apply links or buttons
        try:
            links = driver.find_elements(By.XPATH, ".//a[contains(@href, 'linkedin.com/safety/go') or contains(@aria-label, 'company website')]")
            for a in links:
                if getattr(a, "is_displayed", lambda: True)():
                    return ("COMPANY_PORTAL", a.get_attribute("href"))
        except Exception:
            pass

        return ("COMPANY_PORTAL", None)
