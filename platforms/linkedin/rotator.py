"""LinkedIn Search & Rotation Engine.

Iterates through search terms, pages through listings, and executes pre-filtering deduplication.
"""

import re
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
    JOB_CARD_CLICKABLE_SELECTORS,
    JOB_DETAILS_CONTAINER,
    NO_RESULTS_INDICATORS,
)
from platforms.linkedin.parser import LinkedInJobParser
from platforms.linkedin.applier import LinkedInApplier
from modules.qualification_engine import QualificationEngine, is_job_relevant
from modules.models import Job
from modules.config_loader import get_candidate_experience, get_professional, get_platform


class LinkedInRotator:
    """Orchestrates multi-term job search, deduplication pre-filtering, and application loop."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        applier: Optional[LinkedInApplier] = None,
        automation_bridge: Optional[Any] = None,
        qualification_engine: Optional[Any] = None,
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
        cand_exp = get_candidate_experience(user_id=user_id)
        prof = get_professional(user_id=user_id)
        ln_plat = get_platform("linkedin")

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

        # Extract verified candidate skills and search terms as core domain skills
        cand_core = set()
        for s in (prof.get("skills") or []):
            if isinstance(s, str) and s.strip():
                cand_core.add(s.lower().strip())
        for t in (self.search_terms or []):
            cand_core.add(t.lower().strip())
            for word in t.lower().split():
                if len(word) > 2 and word not in ["developer", "engineer"]:
                    cand_core.add(word)

        all_tech = [
            "angular", "vue", "php", "ruby", "c++", ".net", "dotnet", "golang", "rust",
            "android", "ios", "swift", "flutter", "salesforce", "sap abap", "mainframe",
            "embedded", "devops engineer", "cloud architect", "data engineer"
        ]
        irrelevant_tech = [w for w in all_tech if w not in cand_core]

        cfg_neg = ln_plat.get("negative_title_words", [])
        cfg_bad = ln_plat.get("bad_words", [])

        self.qualification_engine = qualification_engine or QualificationEngine(
            candidate_experience=cand_exp,
            negative_title_words=cfg_neg,
            bad_words=cfg_bad,
            core_skills=list(cand_core) if cand_core else None,
            irrelevant_tech_words=irrelevant_tech if cand_core else None,
        )

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

        # Automatic experience level filtering on LinkedIn based on verified candidate experience
        if not self.experience_level:
            if cand_exp <= 2:
                self.experience_level = ["Entry level", "Associate"]
            elif cand_exp <= 5:
                self.experience_level = ["Associate", "Mid-Senior level"]

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

    @staticmethod
    def _is_senior_title_mismatch(title: str, cand_exp: float) -> bool:
        """Determines if a title implies seniority exceeding candidate's years of experience."""
        if not title or not isinstance(title, str) or hasattr(title, "_mock_return_value"):
            return False
        lower = title.lower()
        if cand_exp < 8:
            for w in ["principal", "director", "vice president", "head of", "chief", "fellow"]:
                if re.search(r'\b' + re.escape(w) + r'\b', lower):
                    return True
        if cand_exp < 5:
            for w in ["staff", "architect", "lead", "tech lead", "team lead", "manager", "engineering manager", "sde 3", "sde iii", "sde-3", "sde-iii", "sde 4", "sde iv"]:
                if re.search(r'\b' + re.escape(w) + r'\b', lower):
                    return True
        if cand_exp < 3:
            for w in ["senior", "sr", "sr.", "sde 2", "sde ii", "sde-2", "sde-ii", "level 2", "level ii"]:
                if re.search(r'\b' + re.escape(w) + r'\b', lower):
                    return True
        return False

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
        """Waits for job cards to populate in DOM, ensuring cards take priority over banners."""
        start_time = time.time()
        while time.time() - start_time < max_wait:
            # 1. Check if any cards exist in DOM first (cards ALWAYS take priority)
            for item_sel in JOB_CARD_ITEMS:
                try:
                    by_type = By.XPATH if item_sel.startswith("//") else By.CSS_SELECTOR
                    cards = driver.find_elements(by_type, item_sel)
                    if cards and any(getattr(c, "is_displayed", lambda: True)() for c in cards):
                        # Deduplicate in case selector matched nested elements
                        deduped = []
                        seen_ids = set()
                        for c in cards:
                            jid = LinkedInJobParser.extract_job_id_from_card(c)
                            if jid:
                                if jid not in seen_ids:
                                    seen_ids.add(jid)
                                    deduped.append(c)
                            else:
                                deduped.append(c)
                        if deduped:
                            return deduped
                except Exception:
                    pass

            # 2. Check for zero-results indicator ONLY after allowing at least 4.0 seconds for cards to render.
            # Never exit early on t=0 because eager page-load returns before async cards finish rendering.
            elapsed = time.time() - start_time
            if elapsed >= 4.0:
                for nr_sel in NO_RESULTS_INDICATORS:
                    try:
                        by_type = By.XPATH if nr_sel.startswith("//") else By.CSS_SELECTOR
                        elems = driver.find_elements(by_type, nr_sel)
                        displayed_elems = [e for e in elems if getattr(e, "is_displayed", lambda: False)()]
                        if displayed_elems:
                            banner_text = " ".join([getattr(e, "text", "") for e in displayed_elems]).lower()
                            if "no matching jobs" in banner_text or "no jobs found" in banner_text:
                                # Even if banner is present, verify there are genuinely no cards on screen
                                any_cards_present = False
                                for item_sel in JOB_CARD_ITEMS[:8]:
                                    try:
                                        by_t = By.XPATH if item_sel.startswith("//") else By.CSS_SELECTOR
                                        if driver.find_elements(by_t, item_sel):
                                            any_cards_present = True
                                            break
                                    except Exception:
                                        pass
                                if not any_cards_present:
                                    print_lg("[LinkedInRotator] Detected genuine 'No matching jobs found' banner on LinkedIn.")
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
                    deduped = []
                    seen_ids = set()
                    for c in cards:
                        jid = LinkedInJobParser.extract_job_id_from_card(c)
                        if jid:
                            if jid not in seen_ids:
                                seen_ids.add(jid)
                                deduped.append(c)
                        else:
                            deduped.append(c)
                    return deduped if deduped else cards
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
                        # Attempt to activate card to reveal job ID in URL or DOM
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", card)
                            time.sleep(0.3)
                            for click_sel in JOB_CARD_CLICKABLE_SELECTORS:
                                targets = card.find_elements(By.CSS_SELECTOR, click_sel)
                                if targets:
                                    try:
                                        targets[0].click()
                                    except Exception:
                                        driver.execute_script("arguments[0].click();", targets[0])
                                    break
                            time.sleep(1.0)
                            curr_url = getattr(driver, "current_url", "") or ""
                            m_url = re.search(r"(?:/jobs/view/|currentJobId=)(\d+)", curr_url)
                            if m_url:
                                job_id = m_url.group(1)
                            else:
                                job_id = LinkedInJobParser.extract_job_id_from_card(card)
                        except Exception:
                            pass

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

                    # Fast Pre-Click Filter on card title & company
                    raw_title = LinkedInJobParser.extract_title(driver, card_element=card)
                    raw_company = LinkedInJobParser.extract_company(driver, card_element=card)
                    card_title = raw_title if isinstance(raw_title, str) and not hasattr(raw_title, "_mock_return_value") and raw_title.strip() else None
                    card_company = raw_company if isinstance(raw_company, str) and not hasattr(raw_company, "_mock_return_value") and raw_company.strip() else ""

                    if card_title:
                        neg_title_words = getattr(self.qualification_engine, "negative_title_words", None)
                        core_skills = getattr(self.qualification_engine, "core_skills", None)
                        if not is_job_relevant(card_title, term, core_skills=core_skills, negative_words=neg_title_words):
                            skip_msg = f"Title '{card_title}' does not match keyword '{term}'"
                            print_lg(f"[LinkedInRotator] Relevance check SKIP for '{card_title}': {skip_msg}")
                            if self.tracker:
                                job_stub = Job(
                                    platform="linkedin",
                                    job_id=job_id,
                                    title=card_title or "Unknown",
                                    company=card_company or "Unknown",
                                    location="",
                                )
                                self.tracker.record_evaluation(job_stub, "SKIPPED", skip_reason=skip_msg)
                            stats["jobs_skipped"] += 1
                            consecutive_skips += 1
                            continue

                        title_res = self.qualification_engine.qualify_title(title=card_title, company=card_company, job_id=job_id)
                        if not title_res.accepted:
                            print_lg(f"[LinkedInRotator] Pre-filter SKIP for '{card_title} | {card_company}': {title_res.reason}")
                            if self.tracker:
                                job_stub = Job(
                                    platform="linkedin",
                                    job_id=job_id,
                                    title=card_title or "Unknown",
                                    company=card_company or "Unknown",
                                    location="",
                                )
                                self.tracker.record_evaluation(job_stub, "SKIPPED", skip_reason=title_res.reason)
                            stats["jobs_skipped"] += 1
                            consecutive_skips += 1
                            continue

                        # Check seniority barrier on card title before clicking
                        cand_exp = getattr(self.qualification_engine, "candidate_experience", 0)
                        if cand_exp > -1 and self._is_senior_title_mismatch(card_title, cand_exp):
                            skip_reason = f"Title '{card_title}' indicates seniority exceeding candidate experience ({cand_exp} yr)"
                            print_lg(f"[LinkedInRotator] Pre-filter SKIP for '{card_title}': {skip_reason}")
                            if self.tracker:
                                job_stub = Job(
                                    platform="linkedin",
                                    job_id=job_id,
                                    title=card_title,
                                    company=card_company or "Unknown",
                                    location="",
                                )
                                self.tracker.record_evaluation(job_stub, "SKIPPED", skip_reason=skip_reason)
                            stats["jobs_skipped"] += 1
                            consecutive_skips += 1
                            continue

                    # Click card to load details using robust inner target + JS fallback
                    clicked = False
                    try:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", card)
                        time.sleep(0.3)
                    except Exception:
                        pass

                    for click_sel in JOB_CARD_CLICKABLE_SELECTORS:
                        try:
                            targets = card.find_elements(By.CSS_SELECTOR, click_sel)
                            for target in targets:
                                if getattr(target, "is_displayed", lambda: True)():
                                    try:
                                        target.click()
                                        clicked = True
                                        break
                                    except Exception:
                                        driver.execute_script("arguments[0].click();", target)
                                        clicked = True
                                        break
                            if clicked:
                                break
                        except Exception:
                            continue

                    if not clicked:
                        try:
                            card.click()
                            clicked = True
                        except Exception:
                            try:
                                driver.execute_script("arguments[0].click();", card)
                                clicked = True
                            except Exception as e:
                                print_lg(f"[LinkedInRotator] Notice clicking job card {job_id}: {e}")
                                consecutive_skips += 1
                                continue

                    time.sleep(1.5)

                    # Extract job details
                    post_title = LinkedInJobParser.extract_title(driver, card_element=card)
                    title = post_title if isinstance(post_title, str) and not hasattr(post_title, "_mock_return_value") and post_title.strip() else (card_title or "Developer")
                    post_company = LinkedInJobParser.extract_company(driver, card_element=card)
                    company = post_company if isinstance(post_company, str) and not hasattr(post_company, "_mock_return_value") and post_company.strip() else (card_company or "")
                    post_loc = LinkedInJobParser.extract_location(driver, card_element=card)
                    location = post_loc if isinstance(post_loc, str) and not hasattr(post_loc, "_mock_return_value") else ""
                    post_desc = LinkedInJobParser.extract_full_description(driver)
                    description = post_desc if isinstance(post_desc, str) and not hasattr(post_desc, "_mock_return_value") else ""
                    source_url = f"https://www.linkedin.com/jobs/view/{job_id}"

                    # Full qualification evaluation (experience bounds, domain skills, bad words)
                    job = Job(
                        platform="linkedin",
                        job_id=job_id,
                        title=title,
                        company=company,
                        location=location,
                        description=description,
                        source_url=source_url,
                    )
                    qual_res = self.qualification_engine.qualify(job)
                    if not qual_res.accepted:
                        print_lg(f"[LinkedInRotator] Qualification SKIP for '{title} | {company}': {qual_res.reason}")
                        if self.tracker:
                            self.tracker.record_evaluation(job, "SKIPPED", skip_reason=qual_res.reason)
                        stats["jobs_skipped"] += 1
                        consecutive_skips += 1
                        continue

                    # Reset consecutive skips on a qualified candidate
                    consecutive_skips = 0
                    if self.tracker:
                        self.tracker.record_state(job, "QUALIFIED")

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
