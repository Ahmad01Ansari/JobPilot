'''
Naukri Job Card Parser
Extracts structured data from Naukri DOM card elements and converts them into normalized Job objects.
'''

import re
from typing import Optional, Tuple, Dict, Any, List
from urllib.parse import urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job, job_from_naukri
from platforms.naukri.selectors import (
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_EXPERIENCE_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_DESCRIPTION_SNIPPET,
    CARD_POSTED_DATE,
)
from modules.helpers import print_lg


def parse_experience_string(exp_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses experience strings from Naukri listings into (min_years, max_years).
    Examples:
        '1-5 Yrs'       -> (1, 5)
        '0-2 Yrs'       -> (0, 2)
        '3 - 6 Yrs'     -> (3, 6)
        '2+ Yrs'        -> (2, None)
        'Fresher'       -> (0, 0)
        'Not Disclosed' -> (None, None)
    """
    if not exp_text or not exp_text.strip():
        return (None, None)

    text = exp_text.strip().lower()
    if "fresher" in text:
        return (0, 0)

    # 1. Range pattern: '1-5 Yrs', '1 - 3 Yrs', '2 to 4 years'
    range_match = re.search(r'(\d+)\s*(?:[-–—]|to)\s*(\d+)\s*(?:yr|year)?', text)
    if range_match:
        min_val = int(range_match.group(1))
        max_val = int(range_match.group(2))
        return (min_val, max_val)

    # 2. Plus pattern: '2+ Yrs', '5+ years'
    plus_match = re.search(r'(\d+)\s*\+\s*(?:yr|year)?', text)
    if plus_match:
        return (int(plus_match.group(1)), None)

    # 3. Single integer pattern: '2 Yrs'
    single_match = re.search(r'(\d+)\s*(?:yr|year)?', text)
    if single_match:
        return (int(single_match.group(1)), None)

    return (None, None)


def parse_salary_string(sal_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses salary strings from Naukri listings into annual figures in INR.
    Examples:
        '3-6 Lacs PA'          -> (300000, 600000)
        '3.5 - 5.5 Lacs PA'    -> (350000, 550000)
        '50,000 - 1,00,000 PA' -> (50000, 100000)
        'Not disclosed'        -> (None, None)
    """
    if not sal_text or not sal_text.strip():
        return (None, None)

    text = sal_text.strip().lower()
    if any(term in text for term in ["not disclosed", "unspecified", "hidden", "confidential"]):
        return (None, None)

    # 1. Lacs PA pattern: '3-6 Lacs PA' or '3.5 - 5.5 Lacs'
    if "lac" in text or "lpa" in text:
        lacs_match = re.search(r'([\d.]+)\s*(?:[-–—]|to)\s*([\d.]+)', text)
        if lacs_match:
            try:
                min_lac = float(lacs_match.group(1))
                max_lac = float(lacs_match.group(2))
                return (int(min_lac * 100000), int(max_lac * 100000))
            except ValueError:
                pass
        single_lac = re.search(r'([\d.]+)\s*(?:lac|lpa)', text)
        if single_lac:
            try:
                val = float(single_lac.group(1))
                return (int(val * 100000), None)
            except ValueError:
                pass

    # 2. Raw numbers: '50,000 - 1,00,000 PA'
    raw_match = re.search(r'([\d,]+)\s*(?:[-–—]|to)\s*([\d,]+)', text)
    if raw_match:
        try:
            min_num = int(raw_match.group(1).replace(",", ""))
            max_num = int(raw_match.group(2).replace(",", ""))
            return (min_num, max_num)
        except ValueError:
            pass

    return (None, None)


def parse_work_style(location_str: str, title_str: str, snippet_str: str = "") -> Optional[str]:
    """Infers work style (Remote, Hybrid, On-site) from listing text."""
    combined = f"{location_str} {title_str} {snippet_str}".lower()
    if "remote" in combined or "work from home" in combined or "wfh" in combined:
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    if location_str and location_str.strip():
        return "On-site"
    return None


def extract_job_id(card: Optional[WebElement] = None, source_url: str = "") -> str:
    """Extracts a unique job ID from the DOM element attributes or URL."""
    if card:
        for attr in ["data-job-id", "job-id", "data-jobid", "id"]:
            val = card.get_attribute(attr)
            if val and val.strip():
                return val.strip()

    # Fallback to URL parsing
    if source_url:
        match = re.search(r'-(\d{10,})(?:\?|$)', source_url)
        if match:
            return match.group(1)
        # Match alphanumeric slug ending with ID
        match2 = re.search(r'job-listings-([a-zA-Z0-9-]+?)(?:\?|$)', source_url)
        if match2:
            return match2.group(1)

    return ""


def _find_text_from_selectors(parent: WebElement, selectors: List[str]) -> str:
    """Attempts to find and return text from the first matching selector."""
    for sel in selectors:
        try:
            elems = parent.find_elements(By.CSS_SELECTOR, sel)
            for elem in elems:
                text = elem.text.strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def _find_attribute_from_selectors(parent: WebElement, selectors: List[str], attr_name: str) -> str:
    """Attempts to find and return an attribute from the first matching selector."""
    for sel in selectors:
        try:
            elems = parent.find_elements(By.CSS_SELECTOR, sel)
            for elem in elems:
                val = elem.get_attribute(attr_name)
                if val and val.strip():
                    return val.strip()
        except Exception:
            continue
    return ""


class NaukriJobParser:
    """Parses Naukri DOM elements into normalized Job instances."""

    @staticmethod
    def parse_card(card: WebElement) -> Optional[Job]:
        """Extracts job attributes from a single job card WebElement."""
        try:
            title = _find_text_from_selectors(card, CARD_TITLE_SELECTORS)
            if not title:
                return None

            company = _find_text_from_selectors(card, CARD_COMPANY_SELECTORS) or "Confidential / Unknown"
            location = _find_text_from_selectors(card, CARD_LOCATION_SELECTORS) or "India"
            exp_text = _find_text_from_selectors(card, CARD_EXPERIENCE_SELECTORS)
            sal_text = _find_text_from_selectors(card, CARD_SALARY_SELECTORS)
            desc_snippet = _find_text_from_selectors(card, CARD_DESCRIPTION_SNIPPET)
            posted_date = _find_text_from_selectors(card, CARD_POSTED_DATE)
            source_url = _find_attribute_from_selectors(card, CARD_TITLE_SELECTORS, "href")

            # Clean tracking parameters from URL
            if source_url and "?" in source_url:
                source_url = source_url.split("?")[0]

            exp_min, exp_max = parse_experience_string(exp_text)
            sal_min, sal_max = parse_salary_string(sal_text)
            work_style = parse_work_style(location, title, desc_snippet)

            job_id = extract_job_id(card=card, source_url=source_url)
            if not job_id and source_url:
                job_id = source_url.split("/")[-1]

            already_applied = False
            for sel in [
                "span.applied-txt",
                "span.already-applied",
                ".already-applied",
                "button.already-applied",
                "button[class*='applied']",
                "span[class*='applied-txt']",
                "span[class*='applied']",
                ".styles_applied__"
            ]:
                try:
                    if card.find_elements(By.CSS_SELECTOR, sel):
                        already_applied = True
                        break
                except Exception:
                    continue

            return job_from_naukri(
                job_id=job_id or f"naukri_{abs(hash(title + company))}",
                title=title,
                company=company,
                location=location,
                work_style=work_style,
                description=desc_snippet,
                required_experience_min=exp_min,
                required_experience_max=exp_max,
                salary_min=sal_min,
                salary_max=sal_max,
                source_url=source_url,
                apply_type="DIRECT",
                posted_date=posted_date,
                raw_metadata={
                    "raw_experience": exp_text,
                    "raw_salary": sal_text,
                    "already_applied": already_applied,
                },
            )
        except Exception as e:
            print_lg(f"[NaukriJobParser] Error parsing card: {e}")
            return None
