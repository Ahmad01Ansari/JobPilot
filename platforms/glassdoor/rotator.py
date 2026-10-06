import re
import time
from typing import Optional, Dict, Any, Callable, List

from platforms.glassdoor.browser import GlassdoorBrowser
from platforms.glassdoor.auth import GlassdoorAuth
from platforms.glassdoor.search import GlassdoorSearch, GlassdoorJobItem
from platforms.glassdoor.parser import GlassdoorParser
from platforms.glassdoor.applier import GlassdoorApplier
from modules.helpers import print_lg
from modules.tracker import ApplicationTracker
from modules.config_loader import get_platform
from modules.qualification_engine import QualificationEngine


def is_job_relevant(job_title: str, search_term: str) -> bool:
    """Verifies that the job title has meaningful relevance to the search term."""
    if not job_title or not search_term:
        return True

    title_lower = job_title.lower()
    term_lower = search_term.lower()

    if term_lower in title_lower or title_lower in term_lower:
        return True

    stop_words = {"in", "and", "or", "for", "the", "of", "to", "at", "a", "an", "with", "senior", "junior", "lead", "sr", "jr"}
    term_words = [w for w in re.findall(r'\b\w+\b', term_lower) if w not in stop_words]
    title_words = [w for w in re.findall(r'\b\w+\b', title_lower) if w not in stop_words]

    if not term_words:
        return True

    for tw in term_words:
        for tlw in title_words:
            if tw == tlw:
                return True
            if (len(tw) >= 3 and len(tlw) >= 3) and (tw.startswith(tlw) or tlw.startswith(tw)):
                return True

    return False


class GlassdoorRotator:
    """Orchestrates keyword rotation, pagination, and application limits on Glassdoor."""

    def __init__(
        self,
        browser: GlassdoorBrowser,
        tracker: Optional[ApplicationTracker] = None,
        applier: Optional[GlassdoorApplier] = None,
        automation_bridge: Optional[Any] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.automation_bridge = automation_bridge
        self.user_id = user_id
        self.auth = GlassdoorAuth(browser=self.browser)
        self.search = GlassdoorSearch(browser=self.browser)
        gd_cfg = get_platform("glassdoor", user_id=self.user_id) or {}
        exp_years = gd_cfg.get("current_experience") or gd_cfg.get("experience_years") or 5
        pause = gd_cfg.get("pause_before_submit", False)
        qual_engine = QualificationEngine(
            candidate_experience=exp_years,
            negative_title_words=gd_cfg.get("negative_title_words"),
            bad_words=gd_cfg.get("bad_words"),
        )
        self.applier = applier or GlassdoorApplier(
            browser=self.browser,
            tracker=self.tracker,
            qualification_engine=qual_engine,
            automation_bridge=self.automation_bridge,
            pause_before_submit=pause,
            user_id=self.user_id,
            search=self.search,
        )
        if self.applier and hasattr(self.applier, "search"):
            self.applier.search = self.search

    def run(self, stop_check: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
        """Executes full search and application run across configured keywords."""
        cfg = get_platform("glassdoor", user_id=self.user_id) or {}
        search_terms = cfg.get("search_terms", ["RPA Developer"])
        location = cfg.get("search_location", "India")
        max_pages = cfg.get("max_pages_per_search", 3)
        switch_number = cfg.get("switch_number", 25)
        daily_goal = cfg.get("daily_application_goal", 50)
        negative_title_words = cfg.get("negative_title_words", [])

        # Configurable apply mode: Easy Apply Only vs Hybrid
        raw_mode = str(cfg.get("apply_mode", "direct_only")).strip().lower()
        if raw_mode in ["all", "hybrid", "hybrid_mode"]:
            easy_apply_only = False
        elif raw_mode in ["direct_only", "easy_apply_only", "easy_apply"]:
            easy_apply_only = True
        else:
            easy_apply_only = bool(cfg.get("easy_apply_only", True))

        stats = {
            "discovered": 0,
            "submitted": 0,
            "external": 0,
            "skipped": 0,
            "failed": 0,
        }

        # 1. Start browser & check session
        self.browser.start()
        main_window = None
        try:
            main_window = self.browser.driver.current_window_handle
        except Exception:
            pass

        # Recover any stale in-flight applications left behind from previously crashed sessions
        if self.tracker and hasattr(self.tracker, "reset_stale_in_flight"):
            recovered = self.tracker.reset_stale_in_flight(platform="glassdoor")
            if isinstance(recovered, int) and recovered > 0:
                print_lg(f"[GlassdoorRotator] Recovered {recovered} stale in-flight job(s) from previous session.")

        if hasattr(self.browser, "is_logged_in") and not self.browser.is_logged_in():
            print_lg("[GlassdoorRotator] Session not authenticated. Prompting user to log in...")
            if self.automation_bridge and hasattr(self.automation_bridge, "on_intervention") and self.automation_bridge.on_intervention:
                try:
                    from app.services.automation_events import AutomationInterventionEvent, InterventionType
                    self.automation_bridge.on_intervention(
                        AutomationInterventionEvent(
                            run_id="glassdoor_login",
                            platform="glassdoor",
                            intervention_type=InterventionType.LOGIN_REQUIRED,
                            message="Glassdoor login required. Please log into your Glassdoor account in the opened Chrome browser window.",
                        )
                    )
                except Exception as e:
                    print_lg(f"[GlassdoorRotator] Notice emitting login intervention: {e}")

            if hasattr(self.browser, "ensure_authenticated"):
                authenticated = self.browser.ensure_authenticated(max_wait_seconds=180)
                if not authenticated:
                    print_lg("[GlassdoorRotator] Login not completed within timeout. Halting run.")
                    return stats

        # 2. Iterate search terms
        for term in search_terms:
            if stop_check and stop_check():
                print_lg("[GlassdoorRotator] Stop requested before keyword.")
                break

            if stats["submitted"] >= daily_goal:
                print_lg(f"[GlassdoorRotator] Daily goal reached ({stats['submitted']}/{daily_goal}).")
                break

            print_lg(f"[GlassdoorRotator] === Starting search for: '{term}' in '{location}' (mode: {'Easy Apply' if easy_apply_only else 'Hybrid'}) ===")
            applied_for_term = 0

            for page in range(1, max_pages + 1):
                if stop_check and stop_check():
                    break

                if page == 1:
                    self.search.navigate_to_search(
                        keyword=term,
                        location=location,
                        page=1,
                        easy_apply_only=easy_apply_only,
                    )
                else:
                    advanced = self.search.paginate_next(current_page=page - 1, stop_check=stop_check)
                    if not advanced:
                        print_lg(f"[GlassdoorRotator] Could not advance beyond page {page - 1} for '{term}'.")
                        break

                # Refresh main_window handle and search_url to ensure it accurately points to search results page
                search_url = None
                try:
                    if self.browser.driver:
                        main_window = self.browser.driver.current_window_handle
                        search_url = self.browser.driver.current_url
                        self.search.last_search_url = search_url
                        if hasattr(self.applier, "last_search_url"):
                            self.applier.last_search_url = search_url
                except Exception:
                    pass

                # Dismiss job alert modals and overlays
                if hasattr(self.browser, "dismiss_overlays"):
                    self.browser.dismiss_overlays()

                # Upfront parsing of all job cards on this page to prevent stale references
                jobs = self.search.parse_job_cards(easy_apply_only=easy_apply_only)
                print_lg(f"[GlassdoorRotator] Page {page}: Parsed {len(jobs)} jobs upfront.")

                if not jobs:
                    print_lg(f"[GlassdoorRotator] No job cards found on page {page} for '{term}'.")
                    break

                # 2a. Record discovery for all discovered jobs
                for job in jobs:
                    stats["discovered"] += 1
                    job_obj = job.to_job()
                    if self.tracker:
                        try:
                            self.tracker.record_job(job_obj)
                        except Exception:
                            pass
                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import JobDiscoveredEvent
                            self.automation_bridge.handle_job_discovered(
                                JobDiscoveredEvent(
                                    run_id="glassdoor_run",
                                    platform="glassdoor",
                                    external_job_id=job.job_id,
                                    title=job.title,
                                    company=job.company,
                                    location=job.location,
                                    url=job.job_url,
                                    application_method="EASY_APPLY" if job.is_easy_apply else "COMPANY_PORTAL",
                                    application_url=job.job_url,
                                    description=job.description or f"{job.title} at {job.company}",
                                )
                            )
                        except Exception:
                            pass

                # 2b. Iterate and apply to jobs
                for idx, job in enumerate(jobs):
                    if stop_check and stop_check():
                        break

                    if applied_for_term >= switch_number or stats["submitted"] >= daily_goal:
                        break

                    # Dismiss any popup overlays before interacting with job card
                    if hasattr(self.browser, "dismiss_overlays"):
                        self.browser.dismiss_overlays()

                    job_obj = job.to_job()

                    # Pre-filter 1: Title relevance guard
                    if not is_job_relevant(job.title, term):
                        print_lg(f"[GlassdoorRotator] Relevance check SKIP for '{job.title}': doesn't match '{term}'")
                        stats["skipped"] += 1
                        if self.tracker:
                            self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=f"Title '{job.title}' does not match keyword '{term}'")
                        continue

                    # Pre-filter 2: Negative keywords
                    if negative_title_words:
                        title_lower = job.title.lower()
                        matched_neg = None
                        for neg in negative_title_words:
                            n_term = str(neg).strip().lower()
                            if n_term and re.search(r'\b' + re.escape(n_term) + r'\b', title_lower):
                                matched_neg = n_term
                                break
                        if matched_neg:
                            skip_msg = f"Title contains negative keyword '{matched_neg}'"
                            print_lg(f"[GlassdoorRotator] Negative keyword SKIP for '{job.title}': {skip_msg}")
                            stats["skipped"] += 1
                            if self.tracker:
                                self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=skip_msg)
                            continue

                    # Pre-filter 3: Check if already handled in tracker
                    is_handled = False
                    if self.tracker:
                        if hasattr(self.tracker, "is_already_handled"):
                            try:
                                res = self.tracker.is_already_handled(job.job_id, platform="glassdoor", user_id=self.user_id)
                                if isinstance(res, tuple) and len(res) >= 1:
                                    is_handled = bool(res[0])
                                elif isinstance(res, bool):
                                    is_handled = res
                            except Exception:
                                is_handled = False
                        if not is_handled and hasattr(self.tracker, "is_applied"):
                            try:
                                res_app = self.tracker.is_applied(job.job_id, platform="glassdoor")
                                if isinstance(res_app, bool):
                                    is_handled = res_app
                            except Exception:
                                is_handled = False

                    if is_handled:
                        print_lg(f"[GlassdoorRotator] Tracker SKIP for '{job.title}' ({job.job_id}): Already handled")
                        stats["skipped"] += 1
                        continue

                    # Execute Application (ownership of APPLYING state is managed by applier)
                    status = self.applier.apply(
                        job,
                        card_index=idx,
                        main_window=main_window,
                        search_url=search_url,
                        stop_check=stop_check,
                    )

                    if status == "submitted":
                        stats["submitted"] += 1
                        applied_for_term += 1
                        print_lg(f"[GlassdoorRotator] Application confirmed! ({stats['submitted']}/{daily_goal})")
                    elif status == "external":
                        stats["external"] += 1
                        stats["skipped"] += 1
                    elif status == "skipped":
                        stats["skipped"] += 1
                    elif status == "failed":
                        stats["failed"] += 1

                    if applied_for_term >= switch_number:
                        print_lg(f"[GlassdoorRotator] Reached switch threshold ({switch_number}) for '{term}'.")
                        break

                if applied_for_term >= switch_number:
                    break

        print_lg(f"[GlassdoorRotator] Run completed. Summary: {stats}")
        return stats

