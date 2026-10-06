'''
Glassdoor Search Engine
Constructs filtered search URLs, manages SRP pagination, and collects job cards on Glassdoor.
'''

import re
import time
from urllib.parse import urlencode, quote_plus
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException,
)

from platforms.glassdoor.selectors import (
    HOME_URL,
    SEARCH_BASE_URL,
    JOBS_SECTION_URL,
    JOBS_NAV_SELECTORS,
    JOB_CARD_ELEMENTS,
    PAGINATION_NEXT_BUTTONS,
    SEARCH_KEYWORD_INPUTS,
    SEARCH_LOCATION_INPUTS,
    SEARCH_SUBMIT_BUTTONS,
    EASY_APPLY_FILTER_BUTTONS,
)
from modules.helpers import print_lg
from modules.human_behavior import human_delay, human_type, smooth_scroll
from modules.models import Job


@dataclass
class GlassdoorJobItem:
    """Normalized representation of a job item discovered from Glassdoor SRP."""
    job_id: str
    title: str
    company: str
    location: str
    job_url: str
    salary: Optional[str] = None
    rating: Optional[str] = None
    description: Optional[str] = None
    is_easy_apply: bool = False
    is_applied: bool = False
    card_element: Optional[WebElement] = None
    card_index: int = 0

    def to_job(self) -> Job:
        """Converts GlassdoorJobItem into standard unified Job model."""
        raw_meta = {}
        if self.salary:
            raw_meta["salary_text"] = self.salary
        if self.rating:
            raw_meta["rating"] = self.rating

        return Job(
            platform="glassdoor",
            job_id=str(self.job_id),
            title=self.title or "Unknown Title",
            company=self.company or "Unknown Company",
            location=self.location or "India",
            source_url=self.job_url,
            apply_type="DIRECT" if self.is_easy_apply else "EXTERNAL",
            application_method="EASY_APPLY" if self.is_easy_apply else "COMPANY_PORTAL",
            application_url=self.job_url,
            description=self.description or f"{self.title} at {self.company}",
            raw_metadata=raw_meta,
        )


def build_search_url(
    keyword: str,
    location: Optional[str] = None,
    from_age: Optional[int] = None,
    page: int = 1,
    base_url: Optional[str] = None,
) -> str:
    """Constructs direct Glassdoor search URL with query parameters."""
    target_base = base_url or SEARCH_BASE_URL
    params: Dict[str, Any] = {
        "sc.keyword": keyword,
    }
    if location:
        params["locKeyword"] = location
    if from_age is not None and from_age > 0:
        params["fromAge"] = from_age
    if page > 1:
        params["p"] = page

    return f"{target_base}?{urlencode(params, quote_via=quote_plus)}"


class GlassdoorSearch:
    """Orchestrates job search operations and pagination on Glassdoor."""

    def __init__(self, browser: Any):
        self.browser = browser
        self.last_search_url: Optional[str] = None

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def go_to_jobs_section(self) -> bool:
        """Navigates to the Glassdoor Jobs section via navbar link or direct URL."""
        if not self.driver:
            return False

        try:
            curr_url = (self.driver.current_url or "").lower()
            if "/job/" in curr_url or "/jobs" in curr_url:
                print_lg("[GlassdoorSearch] Already on Glassdoor Jobs section.")
                return True
        except Exception:
            pass

        print_lg("[GlassdoorSearch] Navigating to Glassdoor Jobs section...")
        self.browser.dismiss_overlays()

        # 1. Try finding and clicking the Jobs nav link in header
        for sel in JOBS_NAV_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        human_delay(2.0, 3.5)
                        self.browser.dismiss_overlays()
                        curr = (self.driver.current_url or "").lower()
                        if "/job" in curr:
                            print_lg("[GlassdoorSearch] Reached Jobs section via header link.")
                            return True
            except Exception:
                continue

        # 2. Direct launch of Job section URL
        print_lg(f"[GlassdoorSearch] Launching direct Jobs section URL: {JOBS_SECTION_URL}")
        try:
            self.driver.get(JOBS_SECTION_URL)
            human_delay(2.5, 4.0)
            self.browser.dismiss_overlays()
        except Exception as e:
            print_lg(f"[GlassdoorSearch] Notice launching Jobs URL: {e}")

        return True

    def _type_into_input_field(
        self,
        selectors: List[str],
        text: str,
        field_name: str = "field",
        press_enter_after: bool = False,
        max_attempts: int = 4,
    ) -> bool:
        """Types text into an input field on the page with retry on stale element or interception."""
        if not self.driver:
            return False

        for attempt in range(max_attempts):
            try:
                self.browser.dismiss_overlays()
                target_elem = None
                for sel in selectors:
                    try:
                        elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                        for el in elems:
                            if el.is_displayed():
                                target_elem = el
                                break
                        if target_elem:
                            break
                    except Exception:
                        continue

                if not target_elem:
                    print_lg(f"[GlassdoorSearch] {field_name} input not immediately visible (attempt {attempt + 1}/{max_attempts}). Waiting...")
                    human_delay(0.8, 1.5)
                    continue

                # Scroll into view and focus/click
                smooth_scroll(self.driver, target_elem)
                human_delay(0.2, 0.4)
                try:
                    target_elem.click()
                except Exception:
                    self.driver.execute_script("arguments[0].focus(); arguments[0].click();", target_elem)

                human_delay(0.2, 0.4)

                # Clear existing content safely
                target_elem.send_keys(Keys.CONTROL + "a")
                target_elem.send_keys(Keys.BACKSPACE)
                human_delay(0.1, 0.3)

                # Ensure cleared in DOM
                val = target_elem.get_attribute("value")
                if val:
                    self.driver.execute_script(
                        "arguments[0].value = ''; arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        target_elem,
                    )
                    human_delay(0.1, 0.2)

                # Type new content
                human_type(target_elem, text)
                human_delay(0.4, 0.8)
                print_lg(f"[GlassdoorSearch] Successfully entered '{text}' into {field_name} input.")

                if press_enter_after:
                    human_delay(0.3, 0.6)
                    target_elem.send_keys(Keys.ENTER)
                    print_lg(f"[GlassdoorSearch] Pressed ENTER on {field_name} input to trigger search.")

                return True

            except (StaleElementReferenceException, NoSuchElementException) as e:
                print_lg(f"[GlassdoorSearch] DOM updated during {field_name} interaction ({type(e).__name__}). Re-locating fresh element (attempt {attempt + 1}/{max_attempts})...")
                human_delay(1.0, 1.8)
            except ElementClickInterceptedException:
                print_lg(f"[GlassdoorSearch] Click intercepted on {field_name}. Dismissing overlays and retrying...")
                self.browser.dismiss_overlays()
                human_delay(0.8, 1.5)
            except Exception as e:
                print_lg(f"[GlassdoorSearch] Notice typing into {field_name}: {e}")
                human_delay(0.8, 1.5)

        return False

    def search_via_ui(
        self,
        keyword: str,
        location: Optional[str] = None,
        easy_apply_only: bool = True,
    ) -> bool:
        """Navigates to Jobs section, enters keyword and location via UI, submits search, and configures filters."""
        if not self.driver:
            return False

        print_lg(f"[GlassdoorSearch] Interacting with UI search controls for: '{keyword}' (loc: '{location or 'Any'}')...")

        # 1. Direct launch / ensure on Jobs section
        self.go_to_jobs_section()

        # 2. Type Keyword with stale element protection
        kw_success = self._type_into_input_field(
            selectors=SEARCH_KEYWORD_INPUTS,
            text=keyword,
            field_name="Keyword",
            press_enter_after=(not location),
        )
        if not kw_success:
            print_lg("[GlassdoorSearch] Warning: Could not locate or type into keyword input on UI.")
            return False

        # 3. Type Location with stale element protection and press ENTER
        loc_submitted = False
        if location:
            loc_success = self._type_into_input_field(
                selectors=SEARCH_LOCATION_INPUTS,
                text=location,
                field_name="Location",
                press_enter_after=True,
            )
            if loc_success:
                loc_submitted = True
            else:
                print_lg(f"[GlassdoorSearch] Notice: Location input not found or failed to type '{location}'.")

        # 4. Explicit Search button submission (targeting main hero search bar only, never header)
        button_submitted = False
        for sel in SEARCH_SUBMIT_BUTTONS:
            try:
                btns = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed() and btn.is_enabled():
                        smooth_scroll(self.driver, btn)
                        human_delay(0.3, 0.6)
                        try:
                            btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", btn)
                        button_submitted = True
                        print_lg("[GlassdoorSearch] Clicked search submit button on UI.")
                        break
                if button_submitted:
                    break
            except (StaleElementReferenceException, Exception):
                continue

        submitted = loc_submitted or button_submitted or (not location and kw_success)
        if not submitted and kw_success:
            try:
                kw_elems = self.driver.find_elements(By.CSS_SELECTOR, "#searchBar-jobTitle, input#searchBar-jobTitle, input[data-test='search-bar-keyword-input']")
                for el in kw_elems:
                    if el.is_displayed():
                        el.send_keys(Keys.ENTER)
                        submitted = True
                        print_lg("[GlassdoorSearch] Triggered search submission via ENTER on keyword input fallback.")
                        break
            except Exception:
                pass

        # 5. Wait for search results and pill filter bar to render
        print_lg("[GlassdoorSearch] Waiting for search results and filter pills to render...")
        human_delay(2.5, 4.0)
        self.browser.dismiss_overlays()

        # 6. Configurable Easy Apply vs Hybrid Filter
        if easy_apply_only:
            print_lg("[GlassdoorSearch] Filter mode: Easy Apply Only. Applying 'Easy Apply only' filter pill...")
            self.apply_easy_apply_filter()
        else:
            print_lg("[GlassdoorSearch] Filter mode: Hybrid. Allowing both Easy Apply and external jobs.")

        # 7. Wait for actual job results to populate
        self.browser.dismiss_overlays()
        print_lg("[GlassdoorSearch] Waiting for actual job cards to load on SRP...")
        cards_found = False
        for _ in range(6):
            cards = self.get_job_card_elements()
            if cards and len(cards) > 0:
                print_lg(f"[GlassdoorSearch] Actual search results loaded: {len(cards)} job cards found.")
                cards_found = True
                break
            human_delay(0.8, 1.2)

        try:
            self.last_search_url = self.driver.current_url
        except Exception:
            pass

        return submitted

    def apply_easy_apply_filter(self, max_retries: int = 3) -> bool:
        """Finds and clicks the Easy Apply filter button on SRP with stale element protection."""
        if not self.driver:
            return False

        for attempt in range(max_retries):
            for sel in EASY_APPLY_FILTER_BUTTONS:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                    for el in elems:
                        if el.is_displayed():
                            aria_pressed = el.get_attribute("aria-pressed")
                            aria_checked = el.get_attribute("aria-checked")
                            btn_class = el.get_attribute("class") or ""
                            if aria_pressed == "true" or aria_checked == "true" or "active" in btn_class or "selected" in btn_class:
                                print_lg("[GlassdoorSearch] Easy Apply filter already active.")
                                return True
                            smooth_scroll(self.driver, el)
                            human_delay(0.5, 0.8)
                            try:
                                el.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", el)
                            print_lg("[GlassdoorSearch] Clicked 'Easy Apply' filter button on UI.")
                            human_delay(2.5, 4.0)
                            self.browser.dismiss_overlays()
                            return True
                except (StaleElementReferenceException, Exception):
                    continue
            human_delay(1.0, 1.5)
        return False

    def navigate_to_search(
        self,
        keyword: str,
        location: Optional[str] = None,
        from_age: Optional[int] = None,
        page: int = 1,
        easy_apply_only: bool = True,
    ) -> bool:
        """Navigates to search results, prioritizing UI automation over raw URL manipulation."""
        if not self.driver:
            return False

        try:
            success = self.search_via_ui(keyword=keyword, location=location, easy_apply_only=easy_apply_only)
            if success:
                return True
        except Exception as e:
            print_lg(f"[GlassdoorSearch] Notice during UI search attempt: {e}")

        # Fallback to direct URL only if UI input completely fails on initial search
        curr_u = (self.driver.current_url or "").lower() if self.driver else ""
        base = "https://www.glassdoor.co.in/Job/jobs.htm" if "glassdoor.co.in" in curr_u else None
        url = build_search_url(keyword=keyword, location=location, from_age=from_age, page=page, base_url=base)
        print_lg(f"[GlassdoorSearch] Fallback navigating to URL: {url}")
        self.driver.get(url)
        human_delay(3.0, 5.0)
        self.browser.dismiss_overlays()
        if easy_apply_only:
            self.apply_easy_apply_filter()
        return True

    def get_job_card_elements(self) -> List[WebElement]:
        """Finds all visible job card elements on current results page with semantic fallbacks."""
        if not self.driver:
            return []

        # 1. Primary selectors from selectors.py
        for sel in JOB_CARD_ELEMENTS:
            try:
                cards = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                if cards:
                    return cards
            except Exception:
                continue

        # 2. Semantic repeated container discovery via JavaScript
        try:
            semantic_cards = self.driver.execute_script('''
                var selectors = [
                    "ul[data-test='job-listing-list'] > li",
                    "li[data-test='jobListing']",
                    "article[data-test='job-listing-wrapper']",
                    "div[class*='JobCard']",
                    "div.jobCard"
                ];
                for (var s of selectors) {
                    var els = document.querySelectorAll(s);
                    if (els.length > 0) return Array.from(els);
                }
                var lis = Array.from(document.querySelectorAll("li, article")).filter(function(el) {
                    return el.querySelector("a[href*='/job'], [data-test='job-title']") !== null && el.offsetWidth > 100 && el.offsetHeight > 40;
                });
                return lis;
            ''')
            if semantic_cards and isinstance(semantic_cards, list) and len(semantic_cards) > 0:
                return semantic_cards
        except Exception:
            pass

        return []

    def parse_job_cards(self, easy_apply_only: bool = False) -> List[GlassdoorJobItem]:
        """Parses all currently visible job cards on the SRP upfront into structured GlassdoorJobItems."""
        if not self.driver:
            return []

        self.browser.dismiss_overlays()
        raw_cards = self.get_job_card_elements()

        if not raw_cards:
            from platforms.glassdoor.page_classifier import GlassdoorPageClassifier
            from platforms.glassdoor.discovery import GlassdoorDiscoveryRunner

            classification = GlassdoorPageClassifier.classify_driver(self.driver)
            print_lg(f"[GlassdoorSearch] 0 job cards found. Page classified as: {classification.page_type.value} (Confidence: {classification.confidence:.2f})")
            try:
                runner = GlassdoorDiscoveryRunner(browser=self.browser)
                report = runner.run_discovery(custom_name="zero_cards_found")
                print_lg(f"[GlassdoorSearch] Captured diagnostic snapshot in: {report.artifacts_dir}")
            except Exception as e:
                print_lg(f"[GlassdoorSearch] Notice capturing diagnostic snapshot: {e}")
            return []

        print_lg(f"[GlassdoorSearch] Found {len(raw_cards)} visible job card elements on SRP.")

        from platforms.glassdoor.parser import GlassdoorParser
        job_items: List[GlassdoorJobItem] = []
        for idx, card in enumerate(raw_cards):
            try:
                item = GlassdoorParser.parse_job_card(
                    card,
                    card_index=idx,
                    default_easy_apply=easy_apply_only,
                )
                if item:
                    item.card_index = idx
                    job_items.append(item)
            except Exception as e:
                print_lg(f"[GlassdoorSearch] Notice parsing card {idx}: {e}")
                continue

        print_lg(f"[GlassdoorSearch] Successfully extracted {len(job_items)} structured job items.")
        return job_items

    def paginate_next(self, current_page: int = 1, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        """Attempts to click next page button with humanized interaction, scroll, and popup dismissal."""
        if not self.driver:
            return False

        if stop_check and stop_check():
            return False

        self.browser.dismiss_overlays()
        next_page = current_page + 1

        # 1. Scroll the job cards container to the bottom to reveal pagination controls
        try:
            self.driver.execute_script('''
                var listContainer = document.querySelector("div[class*='JobsList'], ul[class*='JobsList'], [data-test='job-list'], main");
                if (listContainer) {
                    listContainer.scrollTop = listContainer.scrollHeight;
                }
                window.scrollTo(0, document.body.scrollHeight);
            ''')
            human_delay(0.8, 1.5)
        except Exception:
            pass

        target_selectors = [
            f"//button[@data-test='pagination-page' and (text()='{next_page}' or normalize-space()='{next_page}')]",
            f"//button[text()='{next_page}' or normalize-space()='{next_page}']",
            f"//a[contains(@href, 'p={next_page}') or contains(@href, 'page={next_page}')]",
        ] + PAGINATION_NEXT_BUTTONS

        for sel in target_selectors:
            try:
                btns = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed() and btn.is_enabled():
                        smooth_scroll(self.driver, btn)
                        human_delay(0.8, 1.5)
                        try:
                            btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", btn)
                        print_lg(f"[GlassdoorSearch] Advanced to page {next_page} via pagination button.")
                        human_delay(3.0, 5.0)
                        self.browser.dismiss_overlays()
                        return True
            except Exception:
                continue
        return False
