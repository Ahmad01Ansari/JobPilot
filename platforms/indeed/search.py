'''
Indeed Search Engine
Constructs parametric search URLs and extracts raw job card DOM elements from Indeed India (in.indeed.com).
'''

import re
import time
import urllib.parse
from urllib.parse import urlencode, quote_plus
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from platforms.indeed.selectors import (
    HOME_URL,
    SEARCH_BASE_URL,
    SEARCH_WHAT_INPUT,
    SEARCH_WHERE_INPUT,
    SEARCH_SUBMIT_BUTTON,
    DATE_POSTED_FILTER_BUTTON,
    DATE_POSTED_OPTIONS,
    FILTER_UPDATE_BUTTON,
    JOB_CARD_SELECTORS,
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_SALARY_SELECTORS,
    EASILY_APPLY_BADGE_SELECTORS,
    CARD_SNIPPET_SELECTORS,
)
from modules.helpers import print_lg


from modules.models import Job


def parse_indeed_salary(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parses salary string into annual INR bounds.
    Examples:
        '₹4,00,000 - ₹8,00,000 a year' -> (400000, 800000)
        '₹25,000 - ₹35,000 a month' -> (300000, 420000)
        '₹50,000 a month' -> (600000, 600000)
    """
    if not text or not text.strip():
        return (None, None)
    clean = text.replace('\xa0', ' ').replace(',', '').strip()

    is_month = bool(re.search(r'\b(month|monthly|mo)\b', clean, re.I))
    is_hour = bool(re.search(r'\b(hour|hourly|hr)\b', clean, re.I))
    multiplier = 12 if is_month else (2080 if is_hour else 1)

    # Range
    m = re.search(r'[₹$€£]?\s*([0-9]+(?:\.[0-9]+)?)\s*(?:[-–—]|to)\s*[₹$€£]?\s*([0-9]+(?:\.[0-9]+)?)', clean)
    if m:
        try:
            low = int(float(m.group(1)) * multiplier)
            high = int(float(m.group(2)) * multiplier)
            return (low, high)
        except ValueError:
            pass

    # Single figure
    m_single = re.search(r'[₹$€£]\s*([0-9]+(?:\.[0-9]+)?)', clean)
    if m_single:
        try:
            val = int(float(m_single.group(1)) * multiplier)
            return (val, val)
        except ValueError:
            pass

    return (None, None)


def parse_indeed_experience(text: str) -> Tuple[Optional[int], Optional[int], Optional[str]]:
    """Extracts required experience min, max, and display text from JD or details pane text.
    Handles:
        'Experience: 1–4 Years' -> (1, 4, '1-4 Years')
        'Experience: 3+ years' -> (3, None, '3+ Years')
        'Experience: 2 Years' -> (2, 2, '2 Years')
        '3-5 years of experience' -> (3, 5, '3-5 Years')
    """
    if not text or not text.strip():
        return (None, None, None)
    clean = text.replace('\xa0', ' ')

    # 1. Range with label: 'Experience: 1–4 Years'
    m = re.search(
        r'(?:experience|exp|work\s+experience|relevant\s+experience)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*(?:[-–—]|to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low, high = int(float(m.group(1))), int(float(m.group(2)))
            return (low, high, f"{low}-{high} Years")
        except ValueError:
            pass

    # 2. Plus with label: 'Experience: 3+ years'
    m = re.search(
        r'(?:experience|exp|work\s+experience|relevant\s+experience)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*\+\s*(?:years?|yrs?)',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low = int(float(m.group(1)))
            return (low, None, f"{low}+ Years")
        except ValueError:
            pass

    # 3. Single with label: 'Experience: 2 Years'
    m = re.search(
        r'(?:experience|exp|work\s+experience|relevant\s+experience)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            val = int(float(m.group(1)))
            return (val, val, f"{val} Years")
        except ValueError:
            pass

    # 4. Range before word experience: '1-4 years of experience'
    m = re.search(
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:[-–—]|to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)(?:\s+of)?\s+experience',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low, high = int(float(m.group(1))), int(float(m.group(2)))
            return (low, high, f"{low}-{high} Years")
        except ValueError:
            pass

    # 5. Plus before word experience: '3+ years experience'
    m = re.search(
        r'([0-9]+(?:\.[0-9]+)?)\s*\+\s*(?:years?|yrs?)(?:\s+of)?\s+experience',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low = int(float(m.group(1)))
            return (low, None, f"{low}+ Years")
        except ValueError:
            pass

    # 6. Single before word experience: '2 years experience'
    m = re.search(
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)(?:\s+of)?\s+experience',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            val = int(float(m.group(1)))
            return (val, val, f"{val} Years")
        except ValueError:
            pass

    # 7. Minimum / At least: 'min 2 years', 'minimum 3 years', 'at least 2 years', 'min. 3 yrs'
    m = re.search(
        r'\b(?:min(?:imum)?\.?|at\s+least)[\s:]*([0-9]+(?:\.[0-9]+)?)\s*(?:[-–—]|to)?\s*([0-9]+(?:\.[0-9]+)?)?\s*(?:years?|yrs?)\b',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low = int(float(m.group(1)))
            high = int(float(m.group(2))) if m.group(2) else None
            if 0 <= low <= 30:
                if high is not None and 0 <= high <= 35 and low <= high:
                    return (low, high, f"{low}-{high} Years")
                return (low, None, f"{low}+ Years")
        except ValueError:
            pass

    # 8. Isolated range: '4-6 Years' or '4 to 6 years' or '4-6 yrs'
    m = re.search(
        r'\b([0-9]+(?:\.[0-9]+)?)\s*(?:[-–—]|to)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:years?|yrs?)\b',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low, high = int(float(m.group(1))), int(float(m.group(2)))
            if 0 <= low <= 30 and 0 <= high <= 35 and low <= high:
                return (low, high, f"{low}-{high} Years")
        except ValueError:
            pass

    # 9. Plus with qualifier: '3+ years', '3+ yrs'
    m = re.search(
        r'\b([0-9]+(?:\.[0-9]+)?)\s*\+\s*(?:years?|yrs?)\b',
        clean,
        re.IGNORECASE,
    )
    if m:
        try:
            low = int(float(m.group(1)))
            if 0 <= low <= 30:
                return (low, None, f"{low}+ Years")
        except ValueError:
            pass

    return (None, None, None)


def parse_indeed_work_style(location: str = "", title: str = "", text: str = "") -> Optional[str]:
    """Infers work style (Remote, Hybrid, On-site) from Indeed job data."""
    combined = f"{location} {title} {text}".lower()
    if any(k in combined for k in ["remote", "work from home", "wfh"]):
        return "Remote"
    if "hybrid" in combined:
        return "Hybrid"
    if any(k in combined for k in ["on-site", "work from office", "office mandatory", "in office"]):
        return "On-site"
    if location and location.strip() and location.strip().lower() != "india":
        return "On-site"
    return None


@dataclass
class IndeedJobItem:
    """Structured representation of an Indeed job search result."""
    job_id: str
    title: str
    company: str
    location: str = "India"
    salary: str = ""
    is_easy_apply: bool = True
    job_url: str = ""
    card_element: Optional[WebElement] = None
    description: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    experience_text: Optional[str] = None
    required_experience_min: Optional[int] = None
    required_experience_max: Optional[int] = None
    work_style: Optional[str] = None
    application_url: Optional[str] = None

    @property
    def source_url(self) -> str:
        return self.job_url or f"https://in.indeed.com/viewjob?jk={self.job_id}"

    def to_job(self) -> Job:
        """Converts IndeedJobItem into standard unified Job model."""
        raw_meta = {}
        if self.salary:
            raw_meta["salary_text"] = self.salary
        if self.experience_text:
            raw_meta["experience_text"] = self.experience_text

        app_url = self.application_url or (self.job_url if not self.is_easy_apply else None)

        return Job(
            platform="indeed",
            job_id=str(self.job_id),
            title=self.title or "Unknown Title",
            company=self.company or "Unknown Company",
            location=self.location or "India",
            source_url=self.source_url,
            apply_type="DIRECT" if self.is_easy_apply else "EXTERNAL",
            application_method="EASY_APPLY" if self.is_easy_apply else "COMPANY_PORTAL",
            application_url=app_url,
            description=self.description or f"{self.title} at {self.company}",
            work_style=self.work_style,
            required_experience_min=self.required_experience_min,
            required_experience_max=self.required_experience_max,
            salary_min=self.salary_min,
            salary_max=self.salary_max,
            raw_metadata=raw_meta,
        )


def build_search_url(
    keyword: str,
    location: Optional[str] = "India",
    freshness_days: Optional[int] = None,
    easy_apply_only: bool = True,
    page: int = 1,
    sort_by: str = "relevance",
) -> str:
    """Builds a verified, standardized search URL for Indeed India.
    Example: https://in.indeed.com/jobs?q=RPA+Developer&l=India&fromage=7&sort=date
    """
    params: Dict[str, Any] = {
        "q": keyword.strip(),
        "l": location.strip() if location and location.strip() else "India",
    }

    if freshness_days is not None and freshness_days > 0:
        params["fromage"] = str(freshness_days)

    if sort_by == "date":
        params["sort"] = "date"

    if page > 1:
        params["start"] = str((page - 1) * 10)

    # Base query string
    query_string = urlencode(params, quote_via=quote_plus)

    # Attribute filter for Easy Apply only
    if easy_apply_only:
        # sc=0kf:attr(DS3S6); is Indeed's canonical Easy Apply filter
        query_string += "&sc=0kf%3Aattr%28DS3S6%29%3B"

    return f"{SEARCH_BASE_URL}?{query_string}"


class IndeedSearch:
    """Executes searches and discovers job listing elements on Indeed."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return self.browser.driver

    def apply_date_posted_filter(self, freshness_days: int) -> bool:
        """Opens Date posted filter chip popover, selects matching freshness option, and updates results."""
        if not self.driver or freshness_days <= 0:
            return False

        print_lg(f"[IndeedSearch] Applying 'Date posted' filter on UI for freshness: {freshness_days} days...")
        
        # 1. Open the Date posted popover
        opened = False
        try:
            opened = bool(self.driver.execute_script("""
                const btn = document.getElementById("filter-dateposted") ||
                            document.getElementById("fromAge_filter_button") || 
                            Array.from(document.querySelectorAll("button, a[role='button'], div[role='button']")).find(b => {
                                const t = (b.innerText || '').toLowerCase();
                                const a = (b.getAttribute('aria-label') || '').toLowerCase();
                                const id = (b.id || '').toLowerCase();
                                return (t.includes("date posted") || a.includes("date posted") || id.includes("dateposted")) && !t.includes("clear");
                            });
                if (!btn) return false;
                
                btn.focus();
                const rect = btn.getBoundingClientRect();
                const cx = rect.left + rect.width / 2;
                const cy = rect.top + rect.height / 2;
                
                btn.dispatchEvent(new MouseEvent('mousedown', {bubbles: true, cancelable: true, clientX: cx, clientY: cy}));
                btn.dispatchEvent(new MouseEvent('mouseup', {bubbles: true, cancelable: true, clientX: cx, clientY: cy}));
                btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, clientX: cx, clientY: cy}));
                return true;
            """))
        except Exception as e:
            print_lg(f"[IndeedSearch] Notice clicking date posted filter via JS: {e}")

        if not opened:
            for sel in DATE_POSTED_FILTER_BUTTON:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
                    for b in elems:
                        if b.is_displayed():
                            b.click()
                            opened = True
                            break
                    if opened:
                        break
                except Exception:
                    continue

        if not opened:
            print_lg("[IndeedSearch] Could not open 'Date posted' filter chip.")
            return False

        time.sleep(1.5)

        # Map freshness_days to option testid / label
        # 1 day -> option-2 ("Last 24 hours")
        # 3 days -> option-3 ("Last 3 days")
        # 7 days -> option-4 ("Last 7 days")
        # 14 days -> option-5 ("Last 14 days")
        target_option_id = 3
        target_label = "3 days"
        if freshness_days <= 1:
            target_option_id = 2
            target_label = "24 hours"
        elif freshness_days <= 3:
            target_option_id = 3
            target_label = "3 days"
        elif freshness_days <= 7:
            target_option_id = 4
            target_label = "7 days"
        else:
            target_option_id = 5
            target_label = "14 days"

        print_lg(f"[IndeedSearch] Selecting filter option '{target_label}'...")

        selected_and_updated = False
        try:
            res = self.driver.execute_script("""
                const optId = arguments[0];
                const targetText = arguments[1].toLowerCase();
                
                // 1. Find option element
                let targetOpt = document.querySelector(`li[data-testid='selection-pill-option-${optId}']`);
                if (!targetOpt) {
                    const opts = Array.from(document.querySelectorAll("ul[role='listbox'] li, li[data-testid*='selection-pill-option'], ul[role='menu'] li, div[role='dialog'] li, div[role='dialog'] a, div[role='dialog'] button, div[class*='dropdown'] a, div[class*='popover'] a, #filter-dateposted-menu a, #filter-dateposted-menu li, a[href*='fromage'], [role='option']"));
                    targetOpt = opts.find(o => {
                        const l = (o.getAttribute('aria-label') || o.innerText || o.textContent || '').toLowerCase();
                        return l.includes(targetText) || (targetText === '3 days' && l.includes('3 days')) || (targetText === '7 days' && l.includes('7 days')) || (targetText === '24 hours' && (l.includes('24 hours') || l.includes('1 day')));
                    });
                }
                
                if (targetOpt) {
                    targetOpt.click();
                } else {
                    return {success: false, reason: "Option not found"};
                }
                
                // 2. Find and click Update button ONLY inside popover/listbox/dialog container
                const popover = targetOpt.closest("ul, div[role='dialog'], div[role='menu'], div[class*='popover'], div[class*='dropdown']");
                if (popover) {
                    const updateBtn = Array.from(popover.querySelectorAll("button")).find(b => {
                        const txt = (b.innerText || '').trim().toLowerCase();
                        return txt === 'update' || txt.includes('update');
                    });
                    if (updateBtn) {
                        updateBtn.click();
                        return {success: true, updateClicked: true};
                    }
                }
                
                return {success: true, updateClicked: false};
            """, target_option_id, target_label)
            if res and res.get("success"):
                selected_and_updated = True
        except Exception as e:
            print_lg(f"[IndeedSearch] Notice selecting date option via JS: {e}")

        if not selected_and_updated:
            try:
                opt_sel = f"li[data-testid='selection-pill-option-{target_option_id}'], li[aria-label*='{target_label}']"
                elems = self.driver.find_elements(By.CSS_SELECTOR, opt_sel)
                if elems and elems[0].is_displayed():
                    elems[0].click()
                    time.sleep(0.5)
                up_elems = self.driver.find_elements(By.XPATH, "//button[contains(., 'Update') or contains(span, 'Update')]")
                if up_elems and up_elems[0].is_displayed():
                    up_elems[0].click()
                    selected_and_updated = True
            except Exception:
                pass

        time.sleep(3)
        print_lg("[IndeedSearch] 'Date posted' filter applied successfully.")
        return True

    def search_via_ui(
        self,
        keyword: str,
        location: Optional[str] = "India",
        freshness_days: Optional[int] = None,
        scroll_to_hydrate: bool = True,
    ) -> List[IndeedJobItem]:
        """Executes search via native UI inputs (What/Where) with keystrokes and applies Date posted filter."""
        loc = location.strip() if location and location.strip() else "India"
        target_kw = keyword.strip()
        print_lg(f"[IndeedSearch] Initiating search via UI inputs: keyword='{target_kw}', location='{loc}'...")

        cur_url = getattr(self.driver, "current_url", "")
        # Check if What input exists and is displayed on current page
        has_input = False
        for sel in SEARCH_WHAT_INPUT:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
                if any(el.is_displayed() for el in elems):
                    has_input = True
                    break
            except Exception:
                continue

        if not has_input or "indeed.com" not in cur_url:
            print_lg("[IndeedSearch] Inputs not visible on current page. Navigating to home page...")
            self.browser.navigate(HOME_URL)
            time.sleep(3)

        # 1. Fill What input using native keystrokes & React prototype synchronization
        what_elem = None
        for sel in SEARCH_WHAT_INPUT:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        what_elem = el
                        break
                if what_elem:
                    break
            except Exception:
                continue

        if what_elem:
            try:
                what_elem.click()
                time.sleep(0.2)
                what_elem.send_keys(Keys.CONTROL + "a")
                what_elem.send_keys(Keys.BACKSPACE)
                time.sleep(0.1)
                what_elem.send_keys(target_kw)
                time.sleep(0.2)

                # Ensure React value tracker is synchronized
                self.driver.execute_script("""
                    const el = arguments[0];
                    const val = arguments[1];
                    if (el) {
                        el.focus();
                        const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                        if (setter) {
                            setter.call(el, val);
                        } else {
                            el.value = val;
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                """, what_elem, target_kw)
                time.sleep(0.1)

                if what_elem.get_attribute("value") != target_kw:
                    what_elem.send_keys(Keys.CONTROL + "a")
                    what_elem.send_keys(target_kw)
            except Exception as e:
                print_lg(f"[IndeedSearch] Setting What input notice: {e}")
        else:
            print_lg("[IndeedSearch] What input not found on page.")

        # 2. Fill Where input using native keystrokes & React synchronization
        where_elem = None
        for sel in SEARCH_WHERE_INPUT:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        where_elem = el
                        break
                if where_elem:
                    break
            except Exception:
                continue

        if where_elem:
            try:
                cur_val = (where_elem.get_attribute("value") or "").strip()
                if cur_val.lower() != loc.lower():
                    where_elem.click()
                    time.sleep(0.2)
                    where_elem.send_keys(Keys.CONTROL + "a")
                    where_elem.send_keys(Keys.BACKSPACE)
                    time.sleep(0.1)
                    where_elem.send_keys(loc)
                    time.sleep(0.2)

                    self.driver.execute_script("""
                        const el = arguments[0];
                        const val = arguments[1];
                        if (el) {
                            el.focus();
                            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
                            if (setter) {
                                setter.call(el, val);
                            } else {
                                el.value = val;
                            }
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }
                    """, where_elem, loc)
                    time.sleep(0.1)
            except Exception as e:
                print_lg(f"[IndeedSearch] Setting Where input notice: {e}")

        # 3. Submit search via button click or Enter key
        print_lg("[IndeedSearch] Submitting search...")
        clicked = False
        for sel in SEARCH_SUBMIT_BUTTON:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("//") else By.XPATH, sel)
                for b in elems:
                    if b.is_displayed():
                        try:
                            b.click()
                            clicked = True
                            break
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", b)
                            clicked = True
                            break
                if clicked:
                    break
            except Exception:
                continue

        if not clicked and what_elem:
            try:
                what_elem.send_keys(Keys.ENTER)
                clicked = True
            except Exception:
                pass

        time.sleep(4)

        # 4. Verify that search results actually reflect the keyword in the URL/DOM
        cur_url = getattr(self.driver, "current_url", "")
        parsed = urllib.parse.urlparse(cur_url)
        qs = urllib.parse.parse_qs(parsed.query)
        q_in_url = qs.get("q", [""])[0].strip()

        # If keyword was requested but URL has empty query (e.g. q=), fallback to direct URL
        if target_kw and not q_in_url:
            print_lg(f"[IndeedSearch] UI search submitted with empty query parameter (url={cur_url}). Falling back to direct URL navigation.")
            direct_url = build_search_url(
                keyword=target_kw,
                location=loc,
                freshness_days=freshness_days,
            )
            self.browser.navigate(direct_url)
            time.sleep(3)
        else:
            # Apply Date posted filter if specified and not already applied
            if freshness_days is not None and freshness_days > 0:
                self.apply_date_posted_filter(freshness_days)

        if scroll_to_hydrate:
            self._scroll_results_pane()

        return self.parse_job_cards()

    def search(
        self,
        keyword: str,
        location: Optional[str] = "India",
        freshness_days: Optional[int] = None,
        easy_apply_only: bool = True,
        page: int = 1,
        sort_by: str = "relevance",
        scroll_to_hydrate: bool = True,
        use_ui_filters: bool = True,
    ) -> List[IndeedJobItem]:
        """Navigates to search results and returns list of parsed IndeedJobItems.
        When page == 1 and use_ui_filters is True, applies keyword and location via UI inputs
        and selects the Date posted filter from the popover (preventing URL query distortion).
        Falls back to parametric URL search for pagination (page > 1) or when UI search fails.
        """
        if page == 1 and use_ui_filters and self.driver:
            try:
                items = self.search_via_ui(
                    keyword=keyword,
                    location=location,
                    freshness_days=freshness_days,
                    scroll_to_hydrate=scroll_to_hydrate,
                )
                if items:
                    return items
            except Exception as e:
                print_lg(f"[IndeedSearch] UI search fallback to URL search: {e}")

        search_url = build_search_url(
            keyword=keyword,
            location=location,
            freshness_days=freshness_days,
            easy_apply_only=easy_apply_only,
            page=page,
            sort_by=sort_by,
        )
        print_lg(f"[IndeedSearch] Navigating to: {search_url}")
        success = self.browser.navigate(search_url)
        if not success:
            print_lg(f"[IndeedSearch] Failed to navigate to {search_url}")
            return []

        time.sleep(3)

        if scroll_to_hydrate:
            self._scroll_results_pane()

        return self.parse_job_cards()

    def _scroll_results_pane(self) -> None:
        """Gradually scrolls page to trigger lazy loading of all job cards."""
        try:
            for scroll_step in range(1, 4):
                self.driver.execute_script(f"window.scrollTo(0, {scroll_step * 500});")
                time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
        except Exception:
            pass

    def is_zero_results(self) -> bool:
        """Detects whether Indeed explicitly returned zero search results for the keyword.
        
        When zero results match, Indeed displays 'The search <keyword> did not match any jobs'
        and injects 'Similar to jobs you explored' or recommended jobs which must NOT be treated as results.
        """
        if not self.driver:
            return False
        try:
            return bool(self.driver.execute_script('''
                var bodyText = (document.body ? document.body.innerText : '') || '';
                if (bodyText.includes("did not match any jobs") || 
                    bodyText.includes("No jobs found") || 
                    bodyText.includes("did not match any job results")) {
                    return true;
                }
                var zeroEl = document.querySelector("#no_results_header, .no_results, [data-testid='no-results']");
                if (zeroEl && (zeroEl.innerText || '').length > 5) return true;
                return false;
            '''))
        except Exception:
            return False

    def parse_job_cards(self) -> List[IndeedJobItem]:
        """Parses currently visible job card elements into structured IndeedJobItems.
        Discards 'Similar to jobs you explored' recommendations when zero exact results exist.
        """
        if self.is_zero_results():
            print_lg("[IndeedSearch] Zero exact search results found. Discarding fallback recommendation cards.")
            return []

        raw_cards = []
        try:
            # Query card elements that do NOT belong to 'Similar to jobs you explored'
            cards = self.driver.execute_script('''
                var similarHeading = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, div, p")).find(el => {
                    var t = (el.innerText || '').trim().toLowerCase();
                    return t.includes("similar to jobs you explored") || t.includes("jobs you may be interested in");
                });
                
                var allCards = Array.from(document.querySelectorAll("div.job_seen_beacon, div.cardOutline, div.slider_item"));
                if (!similarHeading) return allCards;
                
                return allCards.filter(c => {
                    if (similarHeading.parentElement && similarHeading.parentElement.contains(c)) return false;
                    var pos = similarHeading.compareDocumentPosition(c);
                    if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return false;
                    return true;
                });
            ''')
            if isinstance(cards, list) and len(cards) > 0:
                raw_cards = [c for c in cards if hasattr(c, "is_displayed") and c.is_displayed()]
        except Exception:
            pass

        if not raw_cards:
            for sel in JOB_CARD_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    visible = [e for e in elems if e.is_displayed()]
                    if visible:
                        raw_cards = visible
                        break
                except Exception:
                    continue

        print_lg(f"[IndeedSearch] Found {len(raw_cards)} visible job cards on page.")
        job_items: List[IndeedJobItem] = []

        for idx, card in enumerate(raw_cards):
            item = self._parse_job_card(card, idx)
            if item:
                job_items.append(item)

        return job_items

    def _parse_job_card(self, card: Any, idx: int = 0) -> Optional[IndeedJobItem]:
        """Parses an individual job card element into an IndeedJobItem."""
        try:
            # 1. Title & Link
            title = "Unknown Role"
            job_url = ""
            job_id = f"indeed_card_{idx+1}"
            title_elem = None

            for t_sel in CARD_TITLE_SELECTORS:
                try:
                    elems = card.find_elements(By.CSS_SELECTOR, t_sel)
                    if elems:
                        title_elem = elems[0]
                        title = title_elem.text.strip()
                        job_url = title_elem.get_attribute("href") or ""
                        # Extract jk from id or href
                        el_id = title_elem.get_attribute("id") or ""
                        if "job_" in el_id:
                            job_id = el_id.replace("job_", "")
                        elif "jk=" in job_url:
                            match = re.search(r"jk=([a-zA-Z0-9]+)", job_url)
                            if match:
                                job_id = match.group(1)
                        break
                except Exception:
                    continue

            # Fallback data-jk on card itself
            card_jk = card.get_attribute("data-jk")
            if card_jk:
                job_id = card_jk

            # 2. Company Name
            company = "Unknown Company"
            for c_sel in CARD_COMPANY_SELECTORS:
                try:
                    elems = card.find_elements(By.CSS_SELECTOR, c_sel)
                    if elems:
                        company = elems[0].text.strip()
                        break
                except Exception:
                    continue

            # 3. Location
            location = "India"
            for l_sel in CARD_LOCATION_SELECTORS:
                try:
                    elems = card.find_elements(By.CSS_SELECTOR, l_sel)
                    if elems:
                        location = elems[0].text.strip()
                        break
                except Exception:
                    continue

            # 4. Salary
            salary = ""
            for s_sel in CARD_SALARY_SELECTORS:
                try:
                    elems = card.find_elements(By.CSS_SELECTOR, s_sel)
                    if elems:
                        salary = elems[0].text.strip()
                        break
                except Exception:
                    continue

            # 5. Easy Apply Badge
            card_text = getattr(card, "text", "") or ""
            is_easy_apply = "Easily apply" in card_text or "Easy Apply" in card_text

            sal_min, sal_max = parse_indeed_salary(salary) if salary else (None, None)
            work_style = parse_indeed_work_style(location, title, card_text)

            # 6. Card Snippet / Summary & Experience Extraction
            snippet_texts = []
            for snip_sel in CARD_SNIPPET_SELECTORS:
                try:
                    elems = card.find_elements(By.CSS_SELECTOR, snip_sel)
                    for el in elems:
                        st = el.text.strip()
                        if st and st not in snippet_texts:
                            snippet_texts.append(st)
                except Exception:
                    continue

            snippet = "\n".join(snippet_texts) if snippet_texts else ""
            if not snippet and card_text:
                # Fallback to lines in card_text excluding title/company/location
                non_hdr = [
                    l.strip() for l in card_text.splitlines()
                    if l.strip() and l.strip() not in (title, company, location, salary)
                ]
                if non_hdr:
                    snippet = "\n".join(non_hdr)

            # Parse experience from combined card text & snippet
            combined_card_text = f"{card_text}\n{snippet}"
            exp_min, exp_max, exp_text = parse_indeed_experience(combined_card_text)

            # Build enriched description so discovered jobs have instant previews in UI repository
            desc_lines = [f"{title} at {company}"]
            if location:
                desc_lines.append(f"Location: {location}")
            if salary:
                desc_lines.append(f"Salary: {salary}")
            if exp_text:
                desc_lines.append(f"Experience: {exp_text}")
            if snippet:
                desc_lines.append(f"\nSummary:\n{snippet}")
            full_desc = "\n".join(desc_lines)

            return IndeedJobItem(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                salary=salary,
                salary_min=sal_min,
                salary_max=sal_max,
                work_style=work_style,
                is_easy_apply=is_easy_apply,
                job_url=job_url,
                card_element=card,
                description=full_desc,
                experience_text=exp_text,
                required_experience_min=exp_min,
                required_experience_max=exp_max,
            )
        except Exception as e:
            print_lg(f"[IndeedSearch] Error parsing card #{idx+1}: {e}")
            return None

