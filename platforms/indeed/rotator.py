'''
Indeed Search Rotation & Multi-Keyword Engine
Orchestrates multi-keyword search rotation, pagination, and application quota tracking.
Reads configuration from config/profile.json platforms.indeed.
'''

import time
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from modules.config_loader import get_platform
from modules.tracker import ApplicationTracker
from modules.helpers import print_lg
from platforms.indeed.browser import IndeedBrowser
from platforms.indeed.search import IndeedSearch, IndeedJobItem
from platforms.indeed.applier import IndeedApplier


def is_job_relevant(job_title: str, search_term: str) -> bool:
    """Verifies that the job title has meaningful relevance to the search term."""
    if not job_title or not search_term:
        return True
    
    title_lower = job_title.lower()
    term_lower = search_term.lower()
    
    # 1. Direct substring check
    if term_lower in title_lower or title_lower in term_lower:
        return True
        
    stop_words = {"in", "and", "or", "for", "the", "of", "to", "at", "a", "an", "with", "senior", "junior", "lead", "sr", "jr"}
    term_words = [w for w in re.findall(r'\b\w+\b', term_lower) if w not in stop_words]
    title_words = [w for w in re.findall(r'\b\w+\b', title_lower) if w not in stop_words]
    
    if not term_words:
        return True
        
    # Check if any significant term word matches or is a prefix/stem of a title word (e.g. dev in developer)
    for tw in term_words:
        for tlw in title_words:
            if tw == tlw:
                return True
            # Prefix check for abbreviations (dev -> developer, auto -> automation, etc.)
            if (len(tw) >= 3 and len(tlw) >= 3) and (tw.startswith(tlw) or tlw.startswith(tw)):
                return True

    return False


@dataclass
class IndeedRotationConfig:
    """Configuration for Indeed multi-keyword search rotation."""
    search_terms: List[str] = field(default_factory=list)
    location: str = "India"
    freshness_days: Optional[int] = 7
    easy_apply_only: bool = True
    max_pages_per_search: int = 3
    switch_number: int = 30
    daily_application_goal: int = 50
    auto_relax_date_filter: bool = True
    negative_title_words: List[str] = field(default_factory=list)
    bad_words: List[str] = field(default_factory=list)
    sleep_duration_minutes: int = 10
    sleep_mode_enabled: bool = True
    run_non_stop: bool = False

    @classmethod
    def from_profile(cls) -> "IndeedRotationConfig":
        """Loads rotation settings from profile.json (platforms.indeed)."""
        cfg = get_platform("indeed") or {}
        date_posted = cfg.get("date_posted", "Past week")
        freshness_map = {
            "Past 24 hours": 1,
            "Past 3 days": 3,
            "Past week": 7,
            "Past month": 30,
            "Any time": None,
            "": None,
        }
        if date_posted in freshness_map:
            freshness_days = freshness_map[date_posted]
        else:
            freshness_days = 7

        neg_words = cfg.get("negative_title_words")
        if neg_words is None:
            try:
                import config.search as search_cfg
                neg_words = getattr(search_cfg, "negative_title_words", [])
            except Exception:
                neg_words = []

        bad_words = cfg.get("bad_words")
        if bad_words is None:
            try:
                import config.search as search_cfg
                bad_words = getattr(search_cfg, "bad_words", [])
            except Exception:
                bad_words = []

        return cls(
            search_terms=list(cfg.get("search_terms", ["RPA Developer", "Automation Engineer"])),
            location=cfg.get("search_location", "India"),
            freshness_days=freshness_days,
            easy_apply_only=cfg.get("easy_apply_only", True),
            max_pages_per_search=cfg.get("max_pages_per_search", 3),
            switch_number=cfg.get("switch_number", 30),
            daily_application_goal=cfg.get("daily_application_goal", 50),
            auto_relax_date_filter=cfg.get("auto_relax_date_filter", True),
            negative_title_words=list(neg_words or []),
            bad_words=list(bad_words or []),
            sleep_duration_minutes=int(cfg.get("sleep_duration_minutes", 10)),
            sleep_mode_enabled=bool(cfg.get("sleep_mode_enabled", True)),
            run_non_stop=bool(cfg.get("run_non_stop", False)),
        )


@dataclass
class IndeedRotationStats:
    """Aggregated metrics across the rotation run."""
    terms_searched: int = 0
    pages_processed: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_applied: int = 0
    jobs_external: int = 0
    jobs_skipped: int = 0
    jobs_failed: int = 0
    jobs_manual_required: int = 0
    consecutive_skips_triggered: int = 0


class IndeedRotator:
    """Executes multi-keyword search rotation for Indeed."""

    def __init__(
        self,
        browser: IndeedBrowser,
        tracker: Optional[ApplicationTracker] = None,
        config: Optional[IndeedRotationConfig] = None,
        applier: Optional[IndeedApplier] = None,
        automation_bridge: Optional[Any] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.config = config or IndeedRotationConfig.from_profile()
        self.search = IndeedSearch(browser)
        self.automation_bridge = automation_bridge
        self.applier = applier or IndeedApplier(browser, self.tracker, automation_bridge=self.automation_bridge, bad_words=self.config.bad_words)
        self.user_id = user_id
        self.stats = IndeedRotationStats()

    def run(
        self,
        applier: Optional[IndeedApplier] = None,
        stop_check: Optional[Any] = None,
    ) -> IndeedRotationStats:
        """Runs the search and application loop across all search terms."""
        target_applier = applier or self.applier
        print_lg(f"[IndeedRotator] Starting search rotation across {len(self.config.search_terms)} terms.")
        try:
            main_window = self.browser.driver.current_window_handle
        except Exception:
            main_window = None

        try:
            for term in self.config.search_terms:
                if stop_check and stop_check():
                    print_lg("[IndeedRotator] Stop check triggered. Stopping rotation.")
                    break

                if self.stats.jobs_applied >= self.config.daily_application_goal:
                    print_lg("[IndeedRotator] Daily application goal reached! Halting rotation.")
                    break

                self.stats.terms_searched += 1
                print_lg(f"\n{'='*70}\n[IndeedRotator] Starting Keyword: '{term}' (Goal: {self.config.switch_number} apps)\n{'='*70}")
                term_applied = 0
                active_freshness = self.config.freshness_days

                for page in range(1, self.config.max_pages_per_search + 1):
                    if stop_check and stop_check():
                        print_lg("[IndeedRotator] Stop check triggered. Stopping pagination.")
                        break

                    if term_applied >= self.config.switch_number:
                        print_lg(f"[IndeedRotator] Reached switch_number ({self.config.switch_number}) for '{term}'.")
                        break

                    if self.stats.jobs_applied >= self.config.daily_application_goal:
                        break

                    self.stats.pages_processed += 1
                    print_lg(f"[IndeedRotator] Keyword '{term}' - Loading Page {page}...")
                    try:
                        jobs: List[IndeedJobItem] = self.search.search(
                            keyword=term,
                            location=self.config.location,
                            freshness_days=active_freshness,
                            easy_apply_only=self.config.easy_apply_only,
                            page=page,
                        )
                    except Exception as e:
                        if stop_check and stop_check():
                            print_lg("[IndeedRotator] Browser closed or stop requested during search.")
                            break
                        print_lg(f"[IndeedRotator] Error during search on page {page}: {e}")
                        break

                    # Auto-relaxation fallback: If page 1 yields 0 jobs with a date filter, try relaxing it
                    if not jobs and page == 1 and self.config.auto_relax_date_filter and active_freshness is not None:
                        fallback_steps = [30, None] if (isinstance(active_freshness, int) and active_freshness <= 7) else [None]
                        for next_freshness in fallback_steps:
                            if stop_check and stop_check():
                                break
                            prev_desc = f"{active_freshness} days" if active_freshness else "Any time"
                            next_desc = f"{next_freshness} days" if next_freshness else "Any time"
                            print_lg(f"[IndeedRotator] '{term}' yielded 0 jobs with {prev_desc} filter. Auto-relaxing date filter to '{next_desc}'...")
                            try:
                                relaxed_jobs = self.search.search(
                                    keyword=term,
                                    location=self.config.location,
                                    freshness_days=next_freshness,
                                    easy_apply_only=self.config.easy_apply_only,
                                    page=1,
                                )
                            except Exception as e:
                                print_lg(f"[IndeedRotator] Error during relaxed search: {e}")
                                relaxed_jobs = []

                            if relaxed_jobs:
                                print_lg(f"[IndeedRotator] ✅ Auto-relaxation successful: Found {len(relaxed_jobs)} jobs with '{next_desc}' filter for '{term}'.")
                                active_freshness = next_freshness
                                jobs = relaxed_jobs
                                break
                            else:
                                active_freshness = next_freshness

                    if not jobs:
                        print_lg(f"[IndeedRotator] No job cards found on page {page} for '{term}'. Advancing keyword.")
                        break

                    # 1. First record discovery for all discovered jobs
                    for job in jobs:
                        job_obj = job.to_job()
                        if self.tracker:
                            try:
                                self.tracker.record_job(job_obj)
                            except Exception as ex:
                                print_lg(f"[IndeedRotator] Notice tracking discovery: {ex}")

                        if self.automation_bridge:
                            try:
                                from app.services.automation_events import JobDiscoveredEvent
                                self.automation_bridge.handle_job_discovered(
                                    JobDiscoveredEvent(
                                        run_id="indeed_run",
                                        platform="indeed",
                                        external_job_id=job.job_id,
                                        title=job.title,
                                        company=job.company,
                                        location=job.location,
                                        url=job.source_url,
                                        application_method="EASY_APPLY" if job.is_easy_apply else "COMPANY_PORTAL",
                                        application_url=job.job_url,
                                        description=job.description or f"{job.title} at {job.company}",
                                        experience_text=job.experience_text,
                                        salary_text=job.salary,
                                        salary_min=job.salary_min,
                                        salary_max=job.salary_max,
                                        required_experience_min=job.required_experience_min,
                                        required_experience_max=job.required_experience_max,
                                        work_style=job.work_style,
                                    )
                                )
                            except Exception:
                                pass

                    # 2. Iterate and process application lifecycle
                    for job in jobs:
                        if stop_check and stop_check():
                            print_lg("[IndeedRotator] Stop check triggered. Halting job applications.")
                            break

                        if term_applied >= self.config.switch_number:
                            break
                        if self.stats.jobs_applied >= self.config.daily_application_goal:
                            break

                        job_obj = job.to_job()
                        self.stats.jobs_evaluated += 1

                        # Pre-filter 1: Keyword Relevance Guard (rejects unrelated recommendations like 'Similar to jobs you explored')
                        if not is_job_relevant(job.title, term):
                            skip_msg = f"Title '{job.title}' does not match keyword '{term}'"
                            print_lg(f"[IndeedRotator] Relevance check SKIP for '{job.title}': {skip_msg}")
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=skip_msg)
                            continue

                        # Pre-filter 1b: Negative Keywords Guard (e.g. skips roles with words in negative_title_words)
                        if self.config.negative_title_words:
                            title_lower = job.title.lower()
                            matched_neg = None
                            for neg in self.config.negative_title_words:
                                n_term = str(neg).strip().lower()
                                if n_term and re.search(r'\b' + re.escape(n_term) + r'\b', title_lower):
                                    matched_neg = n_term
                                    break
                            if matched_neg:
                                skip_msg = f"Title contains negative keyword '{matched_neg}'"
                                print_lg(f"[IndeedRotator] Negative keyword SKIP for '{job.title}': {skip_msg}")
                                self.stats.jobs_skipped += 1
                                if self.tracker:
                                    self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=skip_msg)
                                continue

                        # Pre-filter 2: Easy Apply Only Mode Guard
                        if self.config.easy_apply_only and not job.is_easy_apply:
                            skip_msg = "External portal application in Easy Apply only mode"
                            print_lg(f"[IndeedRotator] Pre-filter SKIP for '{job.title} | {job.company}': {skip_msg}")
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=skip_msg)
                            continue

                        # Pre-filter 3: Check if already handled in tracker
                        is_handled = False
                        handled_reason = ""
                        if self.tracker:
                            if hasattr(self.tracker, "is_already_handled"):
                                try:
                                    res = self.tracker.is_already_handled(job.job_id, platform="indeed")
                                    if isinstance(res, tuple) and len(res) >= 1:
                                        is_handled = bool(res[0])
                                        handled_reason = str(res[1]) if len(res) > 1 and res[1] else ""
                                    elif isinstance(res, bool):
                                        is_handled = res
                                except Exception:
                                    is_handled = False
                            if not is_handled and hasattr(self.tracker, "is_applied"):
                                try:
                                    res_app = self.tracker.is_applied(job.job_id, platform="indeed")
                                    if isinstance(res_app, bool) and res_app:
                                        is_handled = True
                                        handled_reason = "Already applied"
                                    elif not isinstance(res_app, bool) and hasattr(res_app, "__bool__") and bool(res_app):
                                        # Handle mock side_effects where bool returns True
                                        is_handled = bool(res_app)
                                        handled_reason = "Already applied"
                                except TypeError:
                                    try:
                                        is_handled = bool(self.tracker.is_applied(job.job_id))
                                        if is_handled:
                                            handled_reason = "Already applied"
                                    except Exception:
                                        pass
                                except Exception:
                                    pass

                        if is_handled:
                            skip_msg = handled_reason or "Already handled in tracker"
                            print_lg(f"[IndeedRotator] Pre-filter skipped '{job.title} | {job.company}': {skip_msg}")
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_evaluation(job_obj, "SKIPPED", skip_reason=skip_msg)
                            continue

                        # Mark Qualified
                        self.stats.jobs_qualified += 1
                        if self.tracker:
                            self.tracker.record_state(job_obj, "QUALIFIED")

                        # Mark Applying (updates Current Job Workspace in UI)
                        if self.tracker:
                            self.tracker.record_state(job_obj, "APPLYING")

                        # Execute application
                        try:
                            if stop_check is not None:
                                success, message = target_applier.apply_to_job(job, main_window=main_window, stop_check=stop_check)
                            else:
                                success, message = target_applier.apply_to_job(job, main_window=main_window)
                        except Exception as e:
                            if stop_check and stop_check():
                                print_lg("[IndeedRotator] Stop check active during application. Breaking.")
                                break
                            success, message = False, f"Exception during application: {e}"

                        # Refresh job_obj with enriched details from extraction
                        job_obj = job.to_job()

                        if success:
                            self.stats.jobs_applied += 1
                            term_applied += 1
                            if self.tracker:
                                self.tracker.record_state(job_obj, "SUBMITTED")
                            print_lg(
                                f"[APPLICATION_CONFIRMED] Job: '{job.title}' | "
                                f"Company: '{job.company}' | Platform: 'indeed' | "
                                f"Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                            )
                            print_lg(f"[IndeedRotator] Total Applied Today: {self.stats.jobs_applied}/{self.config.daily_application_goal}")
                        elif "external" in message.lower():
                            self.stats.jobs_external += 1
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_state(job_obj, "EXTERNAL", reason=message, application_type="EXTERNAL")
                        elif "already applied" in message.lower() or "blacklisted" in message.lower() or "skip" in message.lower():
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_state(job_obj, "SKIPPED", skip_reason=message)
                        elif "manual" in message.lower() or "captcha" in message.lower():
                            self.stats.jobs_skipped += 1
                            if self.tracker:
                                self.tracker.record_state(job_obj, "MANUAL_REQUIRED", reason=message)
                        else:
                            self.stats.jobs_failed += 1
                            if self.tracker:
                                self.tracker.record_state(job_obj, "FAILED", failure_reason=message)

                        # Polite throttle delay between jobs
                        if stop_check and stop_check():
                            break
                        time.sleep(2)

        except Exception as err:
            if stop_check and stop_check():
                print_lg("[IndeedRotator] Rotation terminated cooperatively upon user stop request.")
            else:
                print_lg(f"[IndeedRotator] Error during rotation: {err}")

        print_lg("\n" + "="*70)
        print_lg("[IndeedRotator] Rotation Complete!")
        print_lg(f"  Terms Searched:  {self.stats.terms_searched}")
        print_lg(f"  Pages Processed: {self.stats.pages_processed}")
        print_lg(f"  Total Evaluated: {self.stats.jobs_evaluated}")
        print_lg(f"  Total Applied:   {self.stats.jobs_applied}")
        print_lg(f"  Total External:  {self.stats.jobs_external}")
        print_lg(f"  Total Skipped:   {self.stats.jobs_skipped}")
        print_lg(f"  Total Failed:    {self.stats.jobs_failed}")
        print_lg("="*70 + "\n")

        return self.stats
