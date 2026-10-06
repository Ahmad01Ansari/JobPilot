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
    JOB_CARD_ITEMS,
    JOB_DETAILS_CONTAINER,
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
        max_pages_per_term: int = 5,
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
        self.max_pages_per_term = max_pages_per_term
        self.user_id = user_id

    def build_search_url(self, keyword: str, start: int = 0) -> str:
        """Constructs direct search URL for LinkedIn jobs."""
        params = {
            "keywords": keyword,
            "f_AL": "true",  # Easy Apply filter
            "start": str(start),
        }
        return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"

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

            for page in range(self.max_pages_per_term):
                if stop_check and stop_check():
                    break

                start_idx = page * 25
                search_url = self.build_search_url(term, start=start_idx)
                print_lg(f"[LinkedInRotator] Navigating to page {page + 1}: {search_url}")
                self.browser.navigate(search_url)
                time.sleep(3)

                # Find job cards
                cards = []
                for item_sel in JOB_CARD_ITEMS:
                    cards = driver.find_elements(By.CSS_SELECTOR, item_sel)
                    if cards:
                        break

                if not cards:
                    print_lg(f"[LinkedInRotator] No job cards found on page {page + 1} for '{term}'.")
                    break

                print_lg(f"[LinkedInRotator] Found {len(cards)} job listings on page {page + 1}.")

                for idx, card in enumerate(cards):
                    if stop_check and stop_check():
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
                        continue

                    # Click card to load details
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card)
                        time.sleep(0.5)
                        card.click()
                        time.sleep(2)
                    except Exception as e:
                        print_lg(f"[LinkedInRotator] Notice clicking job card {job_id}: {e}")
                        continue

                    # Extract job details
                    title = LinkedInJobParser.extract_title(driver)
                    company = LinkedInJobParser.extract_company(driver)
                    location = LinkedInJobParser.extract_location(driver)
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

        return stats
