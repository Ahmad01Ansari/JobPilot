'''
Naukri Search Engine
Constructs flexible search URLs and extracts raw job card DOM elements from Naukri.com search results.
'''

import re
import time
from urllib.parse import urlencode
from typing import Optional, List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from platforms.naukri.selectors import (
    SEARCH_BASE_URL,
    JOB_CARD_SELECTORS,
    NO_JOBS_SELECTORS,
    PAGINATION_NEXT_BUTTONS,
)
from modules.helpers import print_lg


def slugify(text: str) -> str:
    """Converts a phrase into a clean URL-friendly slug.
    Example: 'RPA Developer' -> 'rpa-developer', 'Delhi / NCR' -> 'delhi-ncr'.
    """
    cleaned = re.sub(r'[/\\_]+', ' ', text)
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', cleaned)
    slug = re.sub(r'[\s-]+', '-', cleaned).strip('-').lower()
    return slug


def build_search_url(
    keyword: str,
    location: Optional[str] = None,
    experience_years: Optional[int] = None,
    freshness_days: Optional[int] = None,
    page: int = 1,
) -> str:
    """Builds a verified, standardized search URL for Naukri.com.
    Treats URL structure flexibly as an implementation detail.
    """
    kw_slug = slugify(keyword)
    loc_slug = slugify(location) if location and location.strip() else None

    # Construct canonical base path
    if loc_slug:
        base_path = f"/{kw_slug}-jobs-in-{loc_slug}"
    else:
        base_path = f"/{kw_slug}-jobs"

    if page > 1:
        base_path = f"{base_path}-{page}"

    # Build query params
    params: Dict[str, Any] = {"k": keyword.strip()}
    if location and location.strip():
        params["l"] = location.strip()
    if experience_years is not None and experience_years >= 0:
        params["experience"] = str(experience_years)
        params["nignrpmexp"] = "Y"
    if freshness_days is not None and freshness_days > 0:
        params["jobAge"] = str(freshness_days)

    query_string = urlencode(params)
    return f"{SEARCH_BASE_URL}{base_path}?{query_string}"


class NaukriSearch:
    """Executes searches and discovers job listing elements on Naukri.com."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return self.browser.driver

    def search(
        self,
        keyword: str,
        location: Optional[str] = None,
        experience_years: Optional[int] = None,
        freshness_days: Optional[int] = None,
        page: int = 1,
        scroll_to_hydrate: bool = True,
    ) -> List[WebElement]:
        """Navigates to search results and returns list of raw job card elements."""
        search_url = build_search_url(
            keyword=keyword,
            location=location,
            experience_years=experience_years,
            freshness_days=freshness_days,
            page=page,
        )
        print_lg(f"[NaukriSearch] Navigating to: {search_url}")
        success = self.browser.navigate(search_url)
        if not success:
            print_lg(f"[NaukriSearch] Failed to navigate to {search_url}")
            return []

        time.sleep(2)

        # Dismiss any disruptive location, marketing, or notification popups
        try:
            from platforms.naukri.recovery import dismiss_unexpected_popups
            dismiss_unexpected_popups(self.driver)
        except Exception:
            pass

        # Check for zero results / no jobs indicators
        if self._is_zero_results():
            print_lg(f"[NaukriSearch] Zero search results found for '{keyword}'.")
            return []

        if scroll_to_hydrate and self.driver:
            self._hydrate_virtual_cards()
            try:
                from platforms.naukri.recovery import dismiss_unexpected_popups
                dismiss_unexpected_popups(self.driver)
            except Exception:
                pass

        cards = self._find_job_cards()
        print_lg(f"[NaukriSearch] Discovered {len(cards)} job cards on page {page} for '{keyword}'.")
        return cards

    def _is_zero_results(self) -> bool:
        """Checks if the page displays a 'no results found' banner."""
        if not self.driver:
            return True
        for sel in NO_JOBS_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass
        return False

    def _hydrate_virtual_cards(self) -> None:
        """Progressively scrolls window to trigger lazy-loading / hydration of job cards."""
        if not self.driver:
            return
        try:
            total_height = self.driver.execute_script("return document.body.scrollHeight;")
            steps = 4
            for i in range(1, steps + 1):
                scroll_pos = int((total_height / steps) * i)
                self.driver.execute_script(f"window.scrollTo(0, {scroll_pos});")
                time.sleep(0.4)
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.3)
        except Exception as e:
            print_lg(f"[NaukriSearch] Notice during scroll hydration: {e}")

    def _find_job_cards(self) -> List[WebElement]:
        """Finds all job card elements matching supported selectors."""
        if not self.driver:
            return []
        for sel in JOB_CARD_SELECTORS:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if cards:
                    return cards
            except Exception:
                continue
        return []

    def has_next_page(self) -> bool:
        """Checks if next page pagination control is available."""
        if not self.driver:
            return False

        # 1. CSS Selectors
        for sel in PAGINATION_NEXT_BUTTONS:
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(b.is_displayed() and b.is_enabled() for b in btns):
                    return True
            except Exception:
                continue

        # 2. XPath text-based fallback (most reliable across DOM framework updates)
        try:
            xpath_btns = self.driver.find_elements(
                By.XPATH,
                "//a[contains(translate(normalize-space(.), 'NEXT', 'next'), 'next')] | "
                "//div[contains(@class, 'pagination')]//a[contains(translate(., 'NEXT', 'next'), 'next')] | "
                "//a[contains(@class, 'styles_btn') and contains(translate(., 'NEXT', 'next'), 'next')]"
            )
            if any(b.is_displayed() and b.is_enabled() for b in xpath_btns):
                return True
        except Exception:
            pass

        return False
