"""LinkedIn Search & Rotation Engine.

Iterates through search terms, pages through listings, and executes pre-filtering deduplication.
"""

import time
from typing import List, Optional, Callable, Dict, Any
from urllib.parse import urlencode
from selenium.webdriver.common.by import By

from modules.tracker import ApplicationTracker
from modules.helpers import print_lg
from platforms.linkedin.selectors import (
    JOB_RESULTS_CONTAINER,
    JOB_RESULTS_CONTAINERS,
    JOB_CARD_ITEMS,
    JOB_DETAILS_CONTAINER,
    NO_RESULTS_INDICATORS,
)
from platforms.linkedin.parser import LinkedInJobParser
from platforms.linkedin.applier import LinkedInApplier


class LinkedInRotator:
    """Orchestrates multi-term job search, deduplication pre-filtering, and application loop."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        applier: Optional[LinkedInApplier] = None,
        automation_bridge: Optional[Any] = None,
        search_terms: Optional[List[str]] = None,
        search_location: Optional[str] = None,
        easy_apply_only: bool = True,
        date_posted: Optional[str] = None,
        distance: Optional[int] = None,
        sort_by: Optional[str] = None,
        experience_level: Optional[List[str]] = None,
        on_site: Optional[List[str]] = None,
        max_pages_per_term: int = 5,
        consecutive_skips_limit: int = 25,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.applier = applier or LinkedInApplier(
            browser=browser,
            tracker=self.tracker,
            automation_bridge=automation_bridge,
            user_id=user_id,
        )
        self.automation_bridge = automation_bridge
        self.search_terms = search_terms or ["Software Engineer"]
        self.search_location = search_location
        self.easy_apply_only = easy_apply_only
        self.date_posted = date_posted
        self.distance = distance
        self.sort_by = sort_by
        self.experience_level = experience_level or []
        self.on_site = on_site or []
        self.max_pages_per_term = max_pages_per_term
        self.consecutive_skips_limit = consecutive_skips_limit
        self.user_id = user_id

        # Fallback to search config if specific search preferences were not passed
        try:
            import config.search as sc
            if self.search_location is None:
                self.search_location = getattr(sc, "search_location", "")
            if self.date_posted is None:
                self.date_posted = getattr(sc, "date_posted", "")
            if self.distance is None:
                self.distance = getattr(sc, "distance", None)
            if self.sort_by is None:
                self.sort_by = getattr(sc, "sort_by", "")
            if not self.experience_level:
                self.experience_level = getattr(sc, "experience_level", [])
            if not self.on_site:
                self.on_site = getattr(sc, "on_site", [])
        except Exception:
            pass

    def build_search_url(self, keyword: str, start: int = 0) -> str:
        """Constructs direct search URL for LinkedIn jobs with configured search preferences."""
        params = {"keywords": keyword}
        if self.search_location and str(self.search_location).strip():
            params["location"] = str(self.search_location).strip()
        if self.distance is not None:
            params["distance"] = str(self.distance)
        if self.easy_apply_only:
            params["f_AL"] = "true"
        if self.date_posted:
            tpr_map = {
                "Past 24 hours": "r86400",
                "Past week": "r604800",
                "Past month": "r2592000",
            }
            if self.date_posted in tpr_map:
                params["f_TPR"] = tpr_map[self.date_posted]
        if self.sort_by:
            sort_map = {"Most recent": "DD", "Most relevant": "R"}
            if self.sort_by in sort_map:
                params["sortBy"] = sort_map[self.sort_by]
        if self.experience_level:
            exp_map = {
                "Internship": "1",
                "Entry level": "2",
                "Associate": "3",
                "Mid-Senior level": "4",
                "Director": "5",
                "Executive": "6",
            }
            exp_vals = [exp_map[e] for e in self.experience_level if e in exp_map]
            if exp_vals:
                params["f_E"] = ",".join(exp_vals)
        if self.on_site:
            wt_map = {"On-site": "1", "Remote": "2", "Hybrid": "3"}
            wt_vals = [wt_map[w] for w in self.on_site if w in wt_map]
            if wt_vals:
                params["f_WT"] = ",".join(wt_vals)

        params["start"] = str(start)
        return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

    def scroll_job_list(self, driver: Any) -> None:
        """Progressively scrolls the left job listings container to hydrate all occludable cards."""
        try:
            container = None
            for sel in JOB_RESULTS_CONTAINERS:
                try:
                    if sel.startswith("."):
                        found = driver.find_elements(By.CLASS_NAME, sel[1:])
                    else:
                        found = driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in found:
                        if el.is_displayed():
                            container = el
                            break
                    if container:
                        break
                except Exception:
                    continue

            if container:
                for i in range(1, 6):
                    driver.execute_script(
                        "arguments[0].scrollTop = (arguments[0].scrollHeight * arguments[1]) / 5;",
                        container,
                        i,
                    )
                    time.sleep(0.3)
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
                time.sleep(0.5)
            else:
                for i in range(1, 4):
                    driver.execute_script(f"window.scrollTo(0, (document.body.scrollHeight * {i}) / 3);")
                    time.sleep(0.3)
        except Exception as e:
            print_lg(f"[LinkedInRotator] Notice scrolling job container: {e}")

    def wait_for_job_cards(self, driver: Any, max_wait: float = 12.0) -> List[Any]:
        """Waits for job cards to populate in DOM, checking for early zero-results signals."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            # 1. Check if any cards exist in DOM first
            for item_sel in JOB_CARD_ITEMS:
                try:
                    by_type = By.XPATH if item_sel.startswith("//") else By.CSS_SELECTOR
                    cards = driver.find_elements(by_type, item_sel)
                    if cards and any(getattr(c, "is_displayed", lambda: True)() for c in cards):
                        return cards
                except Exception:
                    pass

            # 2. If no cards, check for fast zero-results indicators with text verification
            for nr_sel in NO_RESULTS_INDICATORS:
                try:
                    by_type = By.XPATH if nr_sel.startswith("//") else By.CSS_SELECTOR
                    elems = driver.find_elements(by_type, nr_sel)
                    if elems and any(getattr(e, "is_displayed", lambda: False)() for e in elems):
                        banner_text = " ".join([getattr(e, "text", "") for e in elems]).lower()
                        if "no matching" in banner_text or "no jobs" in banner_text or nr_sel.startswith("//h1"):
                            print_lg("[LinkedInRotator] Detected 'No matching jobs found' banner on LinkedIn.")
                            return []
                except Exception:
                    pass

            time.sleep(1.0)

        # Final check across all selectors before concluding
        for item_sel in JOB_CARD_ITEMS:
            try:
                by_type = By.XPATH if item_sel.startswith("//") else By.CSS_SELECTOR
                cards = driver.find_elements(by_type, item_sel)
                if cards:
                    return cards
            except Exception:
                pass

        return []

    def run(self, stop_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """Runs the search rotation across all search terms."""
        stats = {
            "terms_searched": 0,
            "jobs_evaluated": 0,
            "jobs_skipped": 0,
            "jobs_applied": 0,
            "jobs_external": 0,
            "jobs_failed": 0,
        }

        driver = self.browser.driver
        if not driver:
            raise RuntimeError("Browser session not active.")

        for term in self.search_terms:
            if stop_check and stop_check():
                print_lg("[LinkedInRotator] Stop requested. Terminating search rotation.")
                break

            stats["terms_searched"] += 1
            print_lg(f"\n[LinkedInRotator] Starting search for term: '{term}'")

            consecutive_skips = 0

            for page in range(self.max_pages_per_term):
                if stop_check and stop_check():
                    break

                start_idx = page * 25
                search_url = self.build_search_url(term, start=start_idx)
                print_lg(f"[LinkedInRotator] Navigating to page {page + 1}: {search_url}")
                self.browser.navigate(search_url)

                # Wait for cards to populate with progressive DOM polling
                cards = self.wait_for_job_cards(driver, max_wait=12.0)

                # Hydrate occludable items by scrolling the listing container
                if cards:
                    self.scroll_job_list(driver)
                    # Re-query cards after scrolling to include hydrated elements
                    rehydrated = []
                    for item_sel in JOB_CARD_ITEMS:
                        try:
                            by_type = By.XPATH if item_sel.startswith("//") else By.CSS_SELECTOR
                            found = driver.find_elements(by_type, item_sel)
                            if len(found) > len(rehydrated):
                                rehydrated = found
                        except Exception:
                            pass
                    if rehydrated:
                        cards = rehydrated

                if not cards:
                    print_lg(f"[LinkedInRotator] No job cards found on page {page + 1} for '{term}'.")
                    break

                print_lg(f"[LinkedInRotator] Found {len(cards)} job listings on page {page + 1}.")

                should_switch_term = False
                for idx, card in enumerate(cards):
                    if stop_check and stop_check():
                        break

                    if consecutive_skips >= self.consecutive_skips_limit:
                        print_lg(
                            f"[LinkedInRotator] Relevance decay: {consecutive_skips} consecutive jobs skipped for '{term}'. Switching keyword."
                        )
                        should_switch_term = True
                        break

                    job_id = LinkedInJobParser.extract_job_id_from_card(card)
                    if not job_id:
                        continue

                    stats["jobs_evaluated"] += 1

                    # Fast pre-filtering against SSOT tracker before clicking
                    should_skip, reason = self.tracker.is_already_handled(
                        job_id, platform="linkedin", user_id=self.user_id
                    )
                    if should_skip:
                        print_lg(f"[LinkedInRotator] Pre-filter SKIP for Job {job_id}: {reason}")
                        stats["jobs_skipped"] += 1
                        consecutive_skips += 1
                        continue

                    # Click card to load details
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        time.sleep(0.5)
                        card.click()
                        time.sleep(2)
                    except Exception as e:
                        print_lg(f"[LinkedInRotator] Notice clicking job card {job_id}: {e}")
                        consecutive_skips += 1
                        continue

                    # Reset consecutive skips on a fresh viable candidate
                    consecutive_skips = 0

                    # Extract job details
                    title = LinkedInJobParser.extract_title(driver, card_element=card)
                    company = LinkedInJobParser.extract_company(driver, card_element=card)
                    location = LinkedInJobParser.extract_location(driver, card_element=card)
                    description = LinkedInJobParser.extract_full_description(driver)
                    source_url = f"https://www.linkedin.com/jobs/view/{job_id}"

                    # Execute application
                    res = self.applier.apply_to_job(
                        job_id=job_id,
                        title=title,
                        company=company,
                        location=location,
                        source_url=source_url,
                        description=description,
                    )

                    status = res.get("status")
                    if status == "SUBMITTED":
                        stats["jobs_applied"] += 1
                    elif status == "EXTERNAL":
                        stats["jobs_external"] += 1
                    elif status == "SKIPPED":
                        stats["jobs_skipped"] += 1
                    else:
                        stats["jobs_failed"] += 1

                if should_switch_term:
                    break

        return stats
