'''
Foundit Job Card Parser & JD Extraction Pipeline
Extracts structured data from Foundit card elements and right-pane JD views into normalized Job objects.
'''

import re
import json
import time
from typing import Optional, Tuple, Dict, Any, List
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job, job_from_foundit
from platforms.foundit.selectors import (
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_EXPERIENCE_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_POSTED_DATE_SELECTORS,
    CARD_TAGS_SELECTORS,
    JD_CONTAINER_SELECTORS,
    DETAILS_CONTAINER_SELECTORS,
    DETAILS_TITLE_SELECTORS,
    DETAILS_COMPANY_SELECTORS,
    DETAILS_LOCATION_SELECTORS,
    DETAILS_EXPERIENCE_SELECTORS,
    DETAILS_SALARY_SELECTORS,
)
from modules.helpers import print_lg


def extract_element_text(elem) -> str:
    """Robust text extraction getting visible text, innerText, or textContent."""
    if not elem:
        return ""
    try:
        t = (elem.text or "").strip()
        if t:
            return t
        t = (elem.get_attribute("innerText") or "").strip()
        if t:
            return t
        t = (elem.get_attribute("textContent") or "").strip()
        return t
    except Exception:
        return ""


def parse_experience_string(exp_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses experience strings from Foundit listings into (min_years, max_years).
    Examples:
        '4 - 6 Years'   -> (4, 6)
        '0-2 Yrs'       -> (0, 2)
        '2+ Years'      -> (2, None)
        'Fresher'       -> (0, 0)
        'Not Disclosed' -> (None, None)
    """
    if not exp_text or not exp_text.strip():
        return (None, None)

    text = exp_text.strip().lower()
    if "fresher" in text:
        return (0, 0)

    # 1. Range pattern: '4 - 6 Years', '1 - 3 Yrs', '2 to 4 years'
    range_match = re.search(r'(\d+)\s*(?:[-–—]|to)\s*(\d+)\s*(?:yr|year)?', text)
    if range_match:
        min_val = int(range_match.group(1))
        max_val = int(range_match.group(2))
        return (min_val, max_val)

    # 2. Plus pattern: '2+ Years', '5+ yrs'
    plus_match = re.search(r'(\d+)\s*\+\s*(?:yr|year)?', text)
    if plus_match:
        return (int(plus_match.group(1)), None)

    # 3. Single integer pattern: '3 Years'
    single_match = re.search(r'(\d+)\s*(?:yr|year)?', text)
    if single_match:
        return (int(single_match.group(1)), None)

    return (None, None)


def parse_salary_string(sal_text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses salary strings into annual figures in INR.
    Examples:
        '3-6 Lacs PA'          -> (300000, 600000)
        '3.5 - 5.5 LPA'        -> (350000, 550000)
        '50,000 - 1,00,000 PA' -> (50000, 100000)
        'Not disclosed'        -> (None, None)
    """
    if not sal_text or not sal_text.strip():
        return (None, None)

    text = sal_text.strip().lower()
    if any(term in text for term in ["not disclosed", "unspecified", "hidden", "confidential"]):
        return (None, None)

    # 1. Lacs / LPA pattern: '3-6 Lacs PA' or '3.5 - 5.5 LPA'
    if "lac" in text or "lpa" in text:
        lacs_match = re.search(r'([\d.]+)\s*(?:[-–—]|to)\s*([\d.]+)', text)
        if lacs_match:
            try:
                min_val = int(float(lacs_match.group(1)) * 100000)
                max_val = int(float(lacs_match.group(2)) * 100000)
                return (min_val, max_val)
            except ValueError:
                pass

        single_lac = re.search(r'([\d.]+)\s*(?:lac|lpa)', text)
        if single_lac:
            try:
                val = int(float(single_lac.group(1)) * 100000)
                return (val, None)
            except ValueError:
                pass

    # 2. Plain comma-separated numbers: '3,00,000 - 6,00,000'
    raw_nums = re.findall(r'[\d,]+', text)
    clean_nums = []
    for n in raw_nums:
        c = n.replace(',', '').strip()
        if c.isdigit() and len(c) >= 5:
            clean_nums.append(int(c))

    if len(clean_nums) >= 2:
        return (min(clean_nums), max(clean_nums))
    elif len(clean_nums) == 1:
        return (clean_nums[0], None)

    return (None, None)


def is_valid_job_description(text: str) -> bool:
    """Validates extracted job description content, rejecting stubs or error messages."""
    if not text or not text.strip():
        return False
    cleaned = text.strip()
    if len(cleaned) < 60:
        return False
    lower = cleaned.lower()
    reject_patterns = [
        "loading...",
        "please login to view",
        "access denied",
        "404 not found",
        "page not found",
        "an error occurred",
        "this job is no longer available",
    ]
    if any(p in lower for p in reject_patterns) and len(cleaned) < 150:
        return False
    return True


class FounditJobParser:
    """Extracts metadata from card DOM elements and right-pane descriptions."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def parse_card(self, card_elem: WebElement) -> Job:
        """Parses a Foundit job card element into a normalized Job object."""
        # Extract full inner text lines for robust structured fallback
        raw_text = extract_element_text(card_elem)
        lines = [l.strip() for l in raw_text.splitlines() if l.strip()]

        clean_lines = []
        for l in lines:
            ll = l.lower()
            if any(ign == ll for ign in ["save", "quick apply", "apply", "applied", "select all", "clear all"]):
                continue
            if any(ll.startswith(p) for p in ["showing", "results for", "scan to", "all filter"]):
                continue
            clean_lines.append(l)

        # 1. Job ID
        job_id = card_elem.get_attribute("id") or ""
        if not job_id or not job_id.isdigit():
            job_id = card_elem.get_attribute("data-job-id") or card_elem.get_attribute("data-jobid") or ""
        if not job_id or not job_id.isdigit():
            try:
                for a in card_elem.find_elements(By.TAG_NAME, "a"):
                    href = a.get_attribute("href") or ""
                    m = re.search(r'/job/([a-zA-Z0-9_-]+)', href) or re.search(r'-(\d{6,10})(?:\.html|\?|$)', href)
                    if m:
                        job_id = m.group(1)
                        break
            except Exception:
                pass

        # 2. Title
        title = ""
        for sel in CARD_TITLE_SELECTORS:
            try:
                elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    t = extract_element_text(e)
                    if t and len(t) > 2 and not any(ign in t.lower() for ign in ["showing", "results", "apply", "filter"]):
                        title = t
                        break
                if title:
                    break
            except Exception:
                continue

        if not title:
            try:
                for h in card_elem.find_elements(By.CSS_SELECTOR, "h2, h3, h4, a[href*='/job/'], div.infoSection > div"):
                    t = extract_element_text(h)
                    if t and len(t) > 3 and not any(w in t.lower() for w in ["apply", "posted", "year", "lacs", "showing", "results"]):
                        title = t
                        break
            except Exception:
                pass

        # Title fallback from clean lines (first valid line is title)
        if not title and clean_lines:
            for l in clean_lines:
                ll = l.lower()
                if not any(w in ll for w in ["skills:", "posted", "save", "apply", "showing", "results", "select all"]):
                    # Don't treat standalone experience lines (e.g. "2-4 yrs") as title
                    if re.match(r'^\s*(?:\d+(?:\s*(?:[-–—]|to)\s*\d+)?\s*(?:yrs?|years?)|\+?\s*\d+\s*(?:yrs?|years?)|fresher)\s*$', ll):
                        continue
                    title = l
                    break

        # 3. Company
        company = ""
        for sel in CARD_COMPANY_SELECTORS:
            try:
                elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    c = extract_element_text(e)
                    if c and len(c) > 1 and not any(w in c.lower() for w in ["apply", "posted", "year", "showing", "results", "skills:"]):
                        company = c
                        break
                if company:
                    break
            except Exception:
                continue

        # Company fallback from clean lines (line immediately following title)
        if not company and len(clean_lines) >= 2:
            for idx, l in enumerate(clean_lines):
                if l == title and idx + 1 < len(clean_lines):
                    next_l = clean_lines[idx + 1]
                    nll = next_l.lower()
                    if not any(w in nll for w in ["skills:", "posted", "lpa", "lacs", "apply"]):
                        if not re.match(r'^\s*(?:\d+(?:\s*(?:[-–—]|to)\s*\d+)?\s*(?:yrs?|years?)|\+?\s*\d+\s*(?:yrs?|years?)|fresher)\b', nll):
                            company = next_l
                            break
            if not company:
                for l in clean_lines:
                    if l != title:
                        ll = l.lower()
                        if not any(w in ll for w in ["skills:", "posted", "lpa", "lacs", "apply"]):
                            if not re.match(r'^\s*(?:\d+(?:\s*(?:[-–—]|to)\s*\d+)?\s*(?:yrs?|years?)|\+?\s*\d+\s*(?:yrs?|years?)|fresher)\b', ll):
                                company = l
                                break

        # 4. Location
        location = ""
        for sel in CARD_LOCATION_SELECTORS:
            try:
                elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    loc = extract_element_text(e)
                    if loc and len(loc) > 1:
                        location = loc
                        break
                if location:
                    break
            except Exception:
                continue

        # 5. Experience
        exp_text = ""
        for sel in CARD_EXPERIENCE_SELECTORS:
            try:
                elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    et = extract_element_text(e)
                    if et and any(w in et.lower() for w in ["yr", "year", "fresher"]):
                        exp_text = et
                        break
                if exp_text:
                    break
            except Exception:
                continue

        # Experience & Location fallback from clean lines
        card_skills = ""
        posted_date = None
        for l in clean_lines:
            ll = l.lower()
            if not exp_text and l != title and any(w in ll for w in ["yr", "year", "fresher"]):
                exp_text = l
                # Extract location from remaining part of line if present (e.g. "2-4 yrs Patan - Gujarat")
                loc_part = re.sub(r'\b\d+(?:\s*(?:[-–—]|to)\s*\d+)?\s*(?:yrs?|years?|fresher)\b', '', l, flags=re.I).strip(" -|,\t")
                if loc_part and len(loc_part) > 2 and not location:
                    location = loc_part
            if ll.startswith("skills:") or "skills:" in ll:
                card_skills = l
            if not posted_date and (ll.startswith("posted") or "ago" in ll):
                posted_date = l

        if not location:
            location = "India"

        req_min, req_max = parse_experience_string(exp_text)

        # 6. Salary
        sal_text = ""
        for sel in CARD_SALARY_SELECTORS:
            try:
                elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                for e in elems:
                    st = extract_element_text(e)
                    if st and any(w in st.lower() for w in ["lac", "lpa", "inr", "₹", "pa"]):
                        sal_text = st
                        break
                if sal_text:
                    break
            except Exception:
                continue

        if not sal_text:
            for l in clean_lines:
                ll = l.lower()
                if any(w in ll for w in ["lac", "lpa", "inr", "₹", "per annum", "p.a."]):
                    sal_text = l
                    break

        sal_min, sal_max = parse_salary_string(sal_text)

        # 7. Posted Date
        if not posted_date:
            for sel in CARD_POSTED_DATE_SELECTORS:
                try:
                    elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        pd = extract_element_text(e)
                        if pd:
                            posted_date = pd
                            break
                    if posted_date:
                        break
                except Exception:
                    continue

        if not job_id:
            safe_title = re.sub(r'[^a-zA-Z0-9]', '', title or "job")[:20]
            safe_comp = re.sub(r'[^a-zA-Z0-9]', '', company or "co")[:15]
            job_id = f"f_{safe_title}_{safe_comp}"

        # Canonical Source URL
        source_url = f"https://www.foundit.in/job/{job_id}" if job_id else ""

        # Work style detection
        combined_text = f"{title} {location}".lower()
        work_style = None
        if "remote" in combined_text or "work from home" in combined_text:
            work_style = "Remote"
        elif "hybrid" in combined_text:
            work_style = "Hybrid"
        elif "on-site" in combined_text or "onsite" in combined_text or "office" in combined_text:
            work_style = "On-site"

        # Construct meaningful initial job description from card details
        desc_parts = []
        if title:
            desc_parts.append(f"Position: {title}")
        if company:
            desc_parts.append(f"Company: {company}")
        if location:
            desc_parts.append(f"Location: {location}")
        if exp_text:
            desc_parts.append(f"Experience: {exp_text}")
        if card_skills:
            desc_parts.append(card_skills)
        initial_description = "\n".join(desc_parts)

        # Determine application method from card indicators
        card_text_lower = (card_elem.text or "").lower()
        card_html_lower = ""
        try:
            card_html_lower = (card_elem.get_attribute("outerHTML") or "").lower()
        except Exception:
            pass

        has_quick_apply = (
            "quick apply" in card_text_lower
            or "quickapply" in card_html_lower
            or bool(card_elem.find_elements(By.XPATH, ".//*[contains(translate(normalize-space(), 'QUICK APPLY', 'quick apply'), 'quick apply')]"))
            or bool(card_elem.find_elements(By.CSS_SELECTOR, "[class*='quickApply'], [class*='quick-apply']"))
        )
        app_method = "EASY_APPLY" if has_quick_apply else "COMPANY_PORTAL"
        app_type = "DIRECT" if has_quick_apply else "EXTERNAL"

        raw_meta = {
            "experience_text": exp_text,
            "salary_text": sal_text,
            "card_classes": card_elem.get_attribute("class") or "",
            "skills": card_skills,
        }

        return job_from_foundit(
            job_id=job_id,
            title=title or "Unknown Role",
            company=company or "Unknown Company",
            location=location or "India",
            work_style=work_style,
            description=initial_description,
            required_experience_min=req_min,
            required_experience_max=req_max,
            salary_min=sal_min,
            salary_max=sal_max,
            source_url=source_url,
            apply_type=app_type,
            application_method=app_method,
            posted_date=posted_date,
            raw_metadata=raw_meta,
        )

    def parse_active_details_pane(self) -> Dict[str, Any]:
        """Extracts rich job details (title, company, location, salary, experience, JD) from the right-hand details pane."""
        if not self.driver:
            return {}
        details: Dict[str, Any] = {}

        # 1. Title
        for sel in DETAILS_TITLE_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    t = extract_element_text(el)
                    if t and len(t) > 2 and el.is_displayed():
                        details["title"] = t
                        break
                if details.get("title"):
                    break
            except Exception:
                continue

        # 2. Company
        for sel in DETAILS_COMPANY_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    c = extract_element_text(el)
                    if c and len(c) > 1 and el.is_displayed():
                        details["company"] = c
                        break
                if details.get("company"):
                    break
            except Exception:
                continue

        # 3. Location
        for sel in DETAILS_LOCATION_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    loc = extract_element_text(el)
                    if loc and el.is_displayed():
                        details["location"] = loc
                        break
                if details.get("location"):
                    break
            except Exception:
                continue

        # 4. Experience
        for sel in DETAILS_EXPERIENCE_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    et = extract_element_text(el)
                    if et and any(w in et.lower() for w in ["yr", "year", "fresher"]) and el.is_displayed():
                        details["experience_text"] = et
                        min_e, max_e = parse_experience_string(et)
                        details["required_experience_min"] = min_e
                        details["required_experience_max"] = max_e
                        break
                if details.get("experience_text"):
                    break
            except Exception:
                continue

        # 5. Salary
        for sel in DETAILS_SALARY_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    st = extract_element_text(el)
                    if st and any(w in st.lower() for w in ["lac", "lpa", "inr", "₹", "pa"]) and el.is_displayed():
                        details["salary_text"] = st
                        s_min, s_max = parse_salary_string(st)
                        details["salary_min"] = s_min
                        details["salary_max"] = s_max
                        break
                if details.get("salary_text"):
                    break
            except Exception:
                continue

        # 6. Description
        desc = self.extract_job_description()
        if desc:
            details["description"] = desc

        # 7. Detect application method from apply button in details pane
        try:
            apply_btns = self.driver.find_elements(
                By.XPATH,
                "//div[contains(@class, 'srpRightContainer') or contains(@class, 'detailsContainer') or contains(@class, 'headerContent')]//button[contains(normalize-space(), 'Apply')] | //div[contains(@class, 'srpRightContainer') or contains(@class, 'detailsContainer')]//a[contains(normalize-space(), 'Apply')]"
            )
            for b in apply_btns:
                if b.is_displayed():
                    btxt = (b.text or b.get_attribute("innerText") or "").strip().lower()
                    bhtml = (b.get_attribute("outerHTML") or "").lower()
                    if "quick apply" in btxt or "quickapply" in bhtml:
                        details["application_method"] = "EASY_APPLY"
                        details["apply_type"] = "DIRECT"
                    else:
                        details["application_method"] = "COMPANY_PORTAL"
                        details["apply_type"] = "EXTERNAL"
                    break
        except Exception:
            pass

        return details

    def extract_job_description(self) -> str:
        """Extracts job description from active split pane or page using 5-level hierarchy."""
        if not self.driver:
            return ""

        # Level 1: Primary JD Containers
        for sel in JD_CONTAINER_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    txt = extract_element_text(el)
                    if el.is_displayed() and is_valid_job_description(txt):
                        return txt
            except Exception:
                continue

        # Level 2: Details Pane Container
        for sel in DETAILS_CONTAINER_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    txt = extract_element_text(el)
                    if el.is_displayed() and is_valid_job_description(txt):
                        return txt
            except Exception:
                continue

        # Level 3: JSON-LD Structured Data
        try:
            scripts = self.driver.find_elements(By.CSS_SELECTOR, "script[type='application/ld+json']")
            for s in scripts:
                raw_html = s.get_attribute("innerHTML")
                if raw_html and "JobPosting" in raw_html:
                    parsed = json.loads(raw_html)
                    if isinstance(parsed, dict) and parsed.get("description"):
                        clean_desc = re.sub(r'<[^>]+>', ' ', str(parsed["description"])).strip()
                        if is_valid_job_description(clean_desc):
                            return clean_desc
        except Exception:
            pass

        # Level 4: Semantic content blocks
        for sel in ["article", "section[class*='description']", "section[class*='details']"]:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    txt = extract_element_text(el)
                    if el.is_displayed() and is_valid_job_description(txt):
                        return txt
            except Exception:
                continue

        return ""

    def parse_full_job_page(self) -> Dict[str, Any]:
        """Extracts complete job metadata, already-applied status, and full expanded JD from a dedicated job details tab/page."""
        if not self.driver:
            return {}

        result: Dict[str, Any] = {
            "is_applied": False,
            "applied_status_text": "",
            "title": "",
            "company": "",
            "location": "",
            "experience_text": "",
            "required_experience_min": None,
            "required_experience_max": None,
            "salary_text": "",
            "salary_min": None,
            "salary_max": None,
            "description": "",
            "work_style": None,
            "application_method": "EASY_APPLY",
            "apply_type": "DIRECT",
        }

        # 1. Detect already applied status vs active apply button (Screenshot 2)
        has_active_apply_btn = False
        try:
            for b in self.driver.find_elements(
                By.XPATH,
                "//button[contains(normalize-space(), 'Quick Apply') or contains(normalize-space(), 'Apply Now')] | "
                "//a[contains(normalize-space(), 'Quick Apply') or contains(normalize-space(), 'Apply Now')] | "
                "//*[@id='applyNowBtn' or contains(@class, 'applyBtn')]"
            ):
                if b.is_displayed():
                    has_active_apply_btn = True
                    break
        except Exception:
            pass

        # If there is an active Quick Apply or Apply Now button, the candidate has NOT applied yet
        if not has_active_apply_btn:
            status_elements = self.driver.find_elements(
                By.XPATH,
                "//*[self::h1 or self::h2 or self::h3 or self::h4 or self::div or self::span][normalize-space()='Your application status'] | "
                "//*[self::button or self::span or self::div or self::p][starts-with(normalize-space(), 'Applied') or normalize-space()='Already Applied'] | "
                "//div[contains(@class, 'application-status') or contains(@class, 'applied-status')]"
            )
            for el in status_elements:
                try:
                    if el.is_displayed():
                        txt = (el.text or "").strip()
                        # Reject recruiter / total applicant count stats e.g. "Over 100 applicants have applied"
                        if "applicants have applied" in txt.lower() or "applicant have applied" in txt.lower():
                            continue
                        if txt.lower() == "applied" or txt.lower().startswith("applied") or any(ind in txt.lower() for ind in ["your application status", "application sent", "already applied"]):
                            result["is_applied"] = True
                            result["applied_status_text"] = txt[:80]
                            break
                except Exception:
                    continue

        # 1.1 Detect application method from apply button on page
        try:
            for b in self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(), 'Apply')] | //a[contains(normalize-space(), 'Apply')]"):
                if b.is_displayed():
                    btxt = (b.text or b.get_attribute("innerText") or "").strip().lower()
                    bhtml = (b.get_attribute("outerHTML") or "").lower()
                    if "quick apply" in btxt or "quickapply" in bhtml:
                        result["application_method"] = "EASY_APPLY"
                        result["apply_type"] = "DIRECT"
                    else:
                        result["application_method"] = "COMPANY_PORTAL"
                        result["apply_type"] = "EXTERNAL"
                    break
        except Exception:
            pass

        # 2. Extract Job Title (h1)
        try:
            h1_elems = self.driver.find_elements(By.TAG_NAME, "h1")
            for h in h1_elems:
                t = extract_element_text(h)
                if t and len(t) > 2 and not any(ign in t.lower() for ign in ["showing", "results", "login"]):
                    result["title"] = t
                    break
        except Exception:
            pass

        if not result["title"]:
            for sel in DETAILS_TITLE_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        t = extract_element_text(el)
                        if t and len(t) > 2:
                            result["title"] = t
                            break
                    if result["title"]:
                        break
                except Exception:
                    continue

        # 3. Extract Company Name
        try:
            company_elems = self.driver.find_elements(
                By.XPATH,
                "//h1/following-sibling::*[contains(@class, 'company') or self::div or self::a or self::p][1] | //div[contains(@class, 'companyName')] | //a[contains(@href, '/company/')]"
            )
            for el in company_elems:
                c = extract_element_text(el)
                if c and len(c) > 1 and not any(ign in c.lower() for ign in ["years", "lpa", "lacs", "apply", "save", "posted"]):
                    first_line = c.splitlines()[0].strip()
                    if first_line and len(first_line) > 1:
                        result["company"] = first_line
                        break
        except Exception:
            pass

        if not result["company"]:
            for sel in DETAILS_COMPANY_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        c = extract_element_text(el)
                        if c and len(c) > 1:
                            result["company"] = c
                            break
                    if result["company"]:
                        break
                except Exception:
                    continue

        # 4. Extract Meta Badges (Experience, Salary, Location) from header section
        try:
            meta_candidates = self.driver.find_elements(
                By.XPATH,
                "//h1/ancestor::div[1]//*[self::span or self::div or self::p] | //div[contains(@class, 'headerContent')]//*[self::span or self::div or self::p] | //div[contains(@class, 'detailsContainer')]//*[self::span or self::div or self::p]"
            )
            for el in meta_candidates:
                txt = extract_element_text(el)
                if not txt:
                    continue
                ltxt = txt.lower()

                # Experience
                if not result["experience_text"] and re.search(r'\b\d+(?:\s*(?:[-–—]|to)\s*\d+)?\s*(?:yr|year|yrs|years|fresher)\b', ltxt):
                    result["experience_text"] = txt
                    min_e, max_e = parse_experience_string(txt)
                    result["required_experience_min"] = min_e
                    result["required_experience_max"] = max_e

                # Salary
                elif not result["salary_text"] and any(s in ltxt for s in ["₹", "lpa", "lac", "lacs", "per annum", "p.a."]):
                    result["salary_text"] = txt
                    s_min, s_max = parse_salary_string(txt)
                    result["salary_min"] = s_min
                    result["salary_max"] = s_max

                # Location
                elif not result["location"] and len(txt) > 2 and len(txt) < 40:
                    if not any(ign in ltxt for ign in ["early applicant", "quick apply", "save", "applied", "posted", "ago", "years", "yrs", "lpa", "lac", "₹"]):
                        result["location"] = txt
        except Exception:
            pass

        # Fallbacks for experience, salary, location
        if not result["experience_text"]:
            for sel in DETAILS_EXPERIENCE_SELECTORS:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        et = extract_element_text(el)
                        if et and any(w in et.lower() for w in ["yr", "year", "fresher"]):
                            result["experience_text"] = et
                            result["required_experience_min"], result["required_experience_max"] = parse_experience_string(et)
                            break
                    if result["experience_text"]:
                        break
                except Exception:
                    continue

        if not result["salary_text"]:
            for sel in DETAILS_SALARY_SELECTORS:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        st = extract_element_text(el)
                        if st and any(w in st.lower() for w in ["lac", "lpa", "inr", "₹", "pa"]):
                            result["salary_text"] = st
                            result["salary_min"], result["salary_max"] = parse_salary_string(st)
                            break
                    if result["salary_text"]:
                        break
                except Exception:
                    continue

        if not result["location"]:
            for sel in DETAILS_LOCATION_SELECTORS:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        loc = extract_element_text(el)
                        if loc and len(loc) > 1 and not any(ign in loc.lower() for ign in ["apply", "save", "posted", "ago"]):
                            result["location"] = loc
                            break
                    if result["location"]:
                        break
                except Exception:
                    continue

        # 5. Expand "View More" under Job Description
        try:
            view_more_elems = self.driver.find_elements(
                By.XPATH,
                "//button[contains(normalize-space(), 'View More')] | //div[contains(normalize-space(), 'View More') and not(descendant::button)] | //span[contains(normalize-space(), 'View More')]"
            )
            for vm in view_more_elems:
                if vm.is_displayed():
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vm)
                        time.sleep(0.2)
                        self.driver.execute_script("arguments[0].click();", vm)
                        time.sleep(0.4)
                        break
                    except Exception:
                        pass
        except Exception:
            pass

        # 6. Extract Full Job Description
        jd_text = ""
        try:
            jd_heading_blocks = self.driver.find_elements(
                By.XPATH,
                "//*[contains(normalize-space(), 'Job Description')]/ancestor::div[contains(@class, 'card') or contains(@class, 'section') or contains(@class, 'Container') or contains(@class, 'desc')][1]"
            )
            for block in jd_heading_blocks:
                t = extract_element_text(block)
                if t and len(t) > 60 and is_valid_job_description(t):
                    clean = re.sub(r'^(?:Job Description\s*)+', '', t, flags=re.I).strip()
                    clean = re.sub(r'View More.*$', '', clean, flags=re.I).strip()
                    if len(clean) > 50:
                        jd_text = clean
                        break
        except Exception:
            pass

        if not jd_text:
            jd_text = self.extract_job_description()

        if not jd_text:
            try:
                body_txt = self.driver.find_element(By.TAG_NAME, "body").text
                if len(body_txt) > 200:
                    jd_text = body_txt[:3000]
            except Exception:
                pass

        result["description"] = jd_text

        # Work style
        comb = f"{result['title']} {result['location']} {jd_text[:300]}".lower()
        if "remote" in comb or "work from home" in comb:
            result["work_style"] = "Remote"
        elif "hybrid" in comb:
            result["work_style"] = "Hybrid"
        elif "on-site" in comb or "onsite" in comb or "office" in comb:
            result["work_style"] = "On-site"

        return result
