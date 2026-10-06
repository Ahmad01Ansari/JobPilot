'''
Naukri Search Rotation & Multi-Page Pagination Engine (Phase 14)
Orchestrates multi-keyword search rotation, multi-page DOM parsing,
relevance decay tracking (consecutive skips), job qualification,
and application pipeline execution.
'''

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Iterator, Callable
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job
from modules.config_loader import get_platform
from modules.qualification_engine import QualificationEngine, QualificationResult
from modules.tracker import ApplicationTracker
from platforms.naukri.search import NaukriSearch
from platforms.naukri.parser import NaukriJobParser
from platforms.naukri.recovery import safe_apply_job
from modules.helpers import print_lg


@dataclass
class SearchRotationConfig:
    """Configuration for multi-keyword search rotation and pagination."""
    search_terms: List[str] = field(default_factory=list)
    location: Optional[str] = "India"
    experience_years: Optional[int] = 2
    freshness_days: Optional[int] = 7
    max_pages_per_search: int = 5
    max_jobs_evaluated_per_search: int = 75
    consecutive_skips_limit: int = 20
    max_applications: Optional[int] = None
    daily_application_goal: int = 50
    apply_mode: str = "direct_only"
    sleep_duration_minutes: int = 10
    sleep_mode_enabled: bool = True
    run_non_stop: bool = False

    @classmethod
    def from_profile(cls) -> "SearchRotationConfig":
        """Loads rotation settings from database (with fallback to platforms.naukri in profile.json)."""
        try:
            from config.search import _read_platform_from_db
            db_cfg = _read_platform_from_db("naukri") or {}
        except Exception:
            db_cfg = {}
        cfg = get_platform("naukri") or {}
        merged = {**cfg, **db_cfg}
        return cls(
            search_terms=list(merged.get("search_terms", [])),
            location=merged.get("search_location", "India"),
            experience_years=merged.get("experience_years", 2),
            freshness_days=merged.get("freshness_days", 7),
            max_pages_per_search=merged.get("max_pages_per_search", 5),
            max_jobs_evaluated_per_search=merged.get("max_jobs_evaluated_per_search", 75),
            consecutive_skips_limit=merged.get("consecutive_skips_limit", 20),
            max_applications=merged.get("switch_number") or merged.get("max_applications", None),
            daily_application_goal=merged.get("daily_application_goal", 50),
            apply_mode=merged.get("apply_mode", "direct_only"),
            sleep_duration_minutes=int(merged.get("sleep_duration_minutes", 10)),
            sleep_mode_enabled=bool(merged.get("sleep_mode_enabled", True)),
            run_non_stop=bool(merged.get("run_non_stop", False)),
        )


@dataclass
class TermStats:
    """Metrics recorded for an individual search term."""
    term: str
    pages_processed: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    jobs_applied: int = 0
    jobs_manual_required: int = 0
    jobs_failed: int = 0
    skip_limit_triggered: bool = False
    max_eval_triggered: bool = False


@dataclass
class RotationStats:
    """Metrics accumulated across the entire search rotation."""
    terms_searched: int = 0
    pages_processed: int = 0
    jobs_evaluated: int = 0
    jobs_qualified: int = 0
    jobs_skipped: int = 0
    jobs_applied: int = 0
    jobs_manual_required: int = 0
    jobs_failed: int = 0
    consecutive_skips_triggered: int = 0
    term_stats: Dict[str, TermStats] = field(default_factory=dict)


@dataclass
class RotationJobItem:
    """Encapsulates a qualified job discovered during rotation."""
    term: str
    page: int
    job: Job
    card_element: Any
    qualification: QualificationResult


class SearchRotationEngine:
    """
    Executes search rotation across multiple keywords and pages on Naukri.com.
    Enforces evaluation limits, consecutive skips relevance decay, and application caps.
    """

    def __init__(
        self,
        browser: Any = None,
        config: Optional[SearchRotationConfig] = None,
        search: Optional[NaukriSearch] = None,
        parser: Optional[NaukriJobParser] = None,
        qualification_engine: Optional[QualificationEngine] = None,
        tracker: Optional[ApplicationTracker] = None,
        applier: Optional[Any] = None,
        automation_bridge: Optional[Any] = None,
    ):
        self.browser = browser
        self.config = config or SearchRotationConfig.from_profile()
        self.search = search or (NaukriSearch(browser) if browser else None)
        self.parser = parser or NaukriJobParser()
        self.qualification_engine = qualification_engine or QualificationEngine()
        self.tracker = tracker or ApplicationTracker()
        self.applier = applier
        self.automation_bridge = automation_bridge
        if self.automation_bridge is None:
            try:
                from app.services.automation_bridge import AutomationBridge
                self.automation_bridge = AutomationBridge()
            except Exception:
                self.automation_bridge = None
        if self.applier and hasattr(self.applier, "automation_bridge") and not getattr(self.applier, "automation_bridge", None):
            self.applier.automation_bridge = self.automation_bridge


    def iter_qualified_jobs(self) -> Iterator[RotationJobItem]:
        """
        Yields qualified jobs across configured search terms and pages.
        Skips unqualified jobs, updates tracker with SKIPPED state,
        and enforces consecutive_skips_limit and max_jobs_evaluated_per_search.
        """
        if not self.search:
            print_lg("[NaukriRotator] Error: No search engine or browser instance available.")
            return

        for term in self.config.search_terms:
            term_evaluated_count = 0
            consecutive_skips = 0

            print_lg(f"\n>>>> [NaukriRotator] Starting search for keyword: '{term}' <<<<")

            for page in range(1, self.config.max_pages_per_search + 1):
                if term_evaluated_count >= self.config.max_jobs_evaluated_per_search:
                    print_lg(f"[NaukriRotator] Max jobs limit ({self.config.max_jobs_evaluated_per_search}) reached for '{term}'.")
                    break

                if consecutive_skips >= self.config.consecutive_skips_limit:
                    print_lg(f"[NaukriRotator] Consecutive skips limit ({self.config.consecutive_skips_limit}) reached for '{term}'.")
                    break

                cards = self.search.search(
                    keyword=term,
                    location=self.config.location,
                    experience_years=self.config.experience_years,
                    freshness_days=self.config.freshness_days,
                    page=page,
                )

                if not cards or self.search._is_zero_results():
                    print_lg(f"[NaukriRotator] No more results found on page {page} for keyword '{term}'.")
                    break

                for card in cards:
                    if term_evaluated_count >= self.config.max_jobs_evaluated_per_search:
                        break
                    if consecutive_skips >= self.config.consecutive_skips_limit:
                        break

                    job = self.parser.parse_card(card)
                    if not job:
                        continue

                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import JobDiscoveredEvent
                            self.automation_bridge.handle_job_discovered(
                                JobDiscoveredEvent(
                                    run_id="naukri_run",
                                    platform="naukri",
                                    external_job_id=job.job_id,
                                    title=job.title,
                                    company=job.company,
                                    location=job.location,
                                    url=job.source_url,
                                    application_method=getattr(job, "application_method", "EASY_APPLY") or "EASY_APPLY",
                                    application_url=getattr(job, "application_url", None),
                                    description=getattr(job, "description", None),
                                )
                            )
                        except Exception:
                            pass


                    # Pre-filter: skip if already handled in tracker or marked as already applied on search card
                    is_card_applied = bool(job.raw_metadata and job.raw_metadata.get("already_applied"))
                    is_handled = False
                    handled_reason = ""
                    if self.tracker and hasattr(self.tracker, "is_already_handled"):
                        try:
                            res = self.tracker.is_already_handled(job.job_id, platform="naukri")
                            if isinstance(res, tuple) and len(res) >= 1:
                                is_handled = bool(res[0])
                                handled_reason = str(res[1]) if len(res) > 1 and res[1] else ""
                            elif isinstance(res, bool):
                                is_handled = res
                            else:
                                is_handled = False
                        except Exception:
                            is_handled = False

                    if is_card_applied or is_handled:
                        skip_msg = handled_reason or "Already applied (detected on search card/tracker)"
                        term_evaluated_count += 1
                        # Note: Already applied/handled jobs do NOT increment consecutive_skips
                        # to avoid prematurely aborting keywords due to past applications.
                        if self.tracker:
                            self.tracker.record_evaluation(job, "SKIPPED", skip_reason=skip_msg)
                        print_lg(
                            f"[NaukriRotator] Pre-filter skipped '{job.title} | {job.company}': {skip_msg} "
                            f"(Already handled - consecutive relevance skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                        continue

                    term_evaluated_count += 1
                    qual_res = self.qualification_engine.qualify(job)

                    if not qual_res.accepted:
                        consecutive_skips += 1
                        if self.tracker:
                            self.tracker.record_evaluation(job, "SKIPPED", skip_reason=qual_res.reason)
                        print_lg(
                            f"[NaukriRotator] Skipped '{job.title} | {job.company}': "
                            f"{qual_res.reason} (Consecutive skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                        continue

                    # Job is qualified: reset consecutive skips counter
                    consecutive_skips = 0
                    if self.tracker:
                        self.tracker.record_state(job, "QUALIFIED")

                    yield RotationJobItem(
                        term=term,
                        page=page,
                        job=job,
                        card_element=card,
                        qualification=qual_res,
                    )

                if consecutive_skips >= self.config.consecutive_skips_limit:
                    break
                if term_evaluated_count >= self.config.max_jobs_evaluated_per_search:
                    break
                if page >= self.config.max_pages_per_search:
                    break
                if not self.search.has_next_page():
                    print_lg(f"[NaukriRotator] No next page indicator found after page {page} for '{term}'.")
                    break

    def run(
        self,
        applier: Optional[Any] = None,
        on_qualified_job: Optional[Callable[[Job, WebElement], Any]] = None,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> RotationStats:
        """
        Executes full search rotation, evaluating jobs and applying if an applier is provided.
        Returns comprehensive RotationStats summarizing all actions across terms and pages.
        """
        if not self.search:
            print_lg("[NaukriRotator] Error: No search engine or browser instance available.")
            return RotationStats()

        target_applier = applier or self.applier
        stats = RotationStats()

        for term in self.config.search_terms:
            if stop_check and stop_check():
                print_lg("[NaukriRotator] Stop requested by user. Terminating rotation.")
                break

            if self.config.max_applications is not None and stats.jobs_applied >= self.config.max_applications:
                print_lg(f"[NaukriRotator] Global application cap ({self.config.max_applications}) reached. Terminating rotation.")
                break

            term_stats = TermStats(term=term)
            stats.terms_searched += 1
            consecutive_skips = 0

            print_lg(f"\n>>>> [NaukriRotator] Starting search for keyword: '{term}' <<<<")

            for page in range(1, self.config.max_pages_per_search + 1):
                if stop_check and stop_check():
                    break

                if self.config.max_applications is not None and stats.jobs_applied >= self.config.max_applications:
                    break

                if term_stats.jobs_evaluated >= self.config.max_jobs_evaluated_per_search:
                    term_stats.max_eval_triggered = True
                    print_lg(f"[NaukriRotator] Max jobs limit ({self.config.max_jobs_evaluated_per_search}) reached for '{term}'.")
                    break

                if consecutive_skips >= self.config.consecutive_skips_limit:
                    if not term_stats.skip_limit_triggered:
                        term_stats.skip_limit_triggered = True
                        stats.consecutive_skips_triggered += 1
                    print_lg(f"[NaukriRotator] Relevance decay: {consecutive_skips} consecutive skips reached for '{term}'. Switching keyword.")
                    break

                cards = self.search.search(
                    keyword=term,
                    location=self.config.location,
                    experience_years=self.config.experience_years,
                    freshness_days=self.config.freshness_days,
                    page=page,
                )

                if not cards or self.search._is_zero_results():
                    print_lg(f"[NaukriRotator] No more results found on page {page} for keyword '{term}'.")
                    break

                term_stats.pages_processed += 1
                stats.pages_processed += 1

                # Pre-parse ALL cards into Job objects before applying to any.
                # apply_to_job() navigates to job detail pages, which destroys
                # the search results DOM and makes remaining card WebElements stale.
                parsed_jobs = []
                for card in cards:
                    try:
                        job = self.parser.parse_card(card)
                        if job:
                            parsed_jobs.append(job)
                            if self.tracker:
                                self.tracker.record_job(job)
                            if self.automation_bridge:
                                try:
                                    from app.services.automation_events import JobDiscoveredEvent
                                    self.automation_bridge.handle_job_discovered(
                                        JobDiscoveredEvent(
                                            run_id="naukri_run",
                                            platform="naukri",
                                            external_job_id=job.job_id,
                                            title=job.title,
                                            company=job.company,
                                            location=job.location,
                                            url=job.source_url,
                                            application_method=getattr(job, "application_method", "EASY_APPLY") or "EASY_APPLY",
                                            application_url=getattr(job, "application_url", None),
                                            description=getattr(job, "description", None),
                                        )
                                    )
                                except Exception:
                                    pass

                    except Exception as parse_err:
                        print_lg(f"[NaukriRotator] Card parse error (skipping): {parse_err}")
                        continue

                for job in parsed_jobs:
                    if stop_check and stop_check():
                        break

                    if self.config.max_applications is not None and stats.jobs_applied >= self.config.max_applications:
                        break

                    if term_stats.jobs_evaluated >= self.config.max_jobs_evaluated_per_search:
                        term_stats.max_eval_triggered = True
                        break

                    if consecutive_skips >= self.config.consecutive_skips_limit:
                        if not term_stats.skip_limit_triggered:
                            term_stats.skip_limit_triggered = True
                            stats.consecutive_skips_triggered += 1
                        print_lg(f"[NaukriRotator] Relevance decay: {consecutive_skips} consecutive skips reached for '{term}'. Switching keyword.")
                        break

                    term_stats.jobs_evaluated += 1
                    stats.jobs_evaluated += 1

                    # Pre-filter: skip if already handled in tracker or marked as already applied on search card
                    is_card_applied = bool(job.raw_metadata and job.raw_metadata.get("already_applied"))
                    is_handled = False
                    handled_reason = ""
                    if self.tracker and hasattr(self.tracker, "is_already_handled"):
                        try:
                            res = self.tracker.is_already_handled(job.job_id, platform="naukri")
                            if isinstance(res, tuple) and len(res) >= 1:
                                is_handled = bool(res[0])
                                handled_reason = str(res[1]) if len(res) > 1 and res[1] else ""
                            elif isinstance(res, bool):
                                is_handled = res
                            else:
                                is_handled = False
                        except Exception:
                            is_handled = False

                    if is_card_applied or is_handled:
                        skip_msg = handled_reason or "Already applied (detected on search card/tracker)"
                        term_stats.jobs_skipped += 1
                        stats.jobs_skipped += 1
                        if self.tracker:
                            self.tracker.record_evaluation(job, "SKIPPED", skip_reason=skip_msg)
                        print_lg(
                            f"[NaukriRotator] Pre-filter skipped '{job.title} | {job.company}': {skip_msg} "
                            f"(Already handled - consecutive relevance skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                        continue

                    qual_res = self.qualification_engine.qualify(job)

                    if not qual_res.accepted:
                        consecutive_skips += 1
                        term_stats.jobs_skipped += 1
                        stats.jobs_skipped += 1
                        if self.tracker:
                            self.tracker.record_evaluation(job, "SKIPPED", skip_reason=qual_res.reason)
                        print_lg(
                            f"[NaukriRotator] Skipped '{job.title} | {job.company}': "
                            f"{qual_res.reason} (Consecutive skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                        continue

                    # Qualified - reset consecutive skips counter since this search term yielded a relevant job
                    consecutive_skips = 0
                    term_stats.jobs_qualified += 1
                    stats.jobs_qualified += 1
                    if self.tracker:
                        self.tracker.record_state(job, "QUALIFIED")

                    # Handle application or callback
                    # Note: card_element is NOT passed since we pre-parsed and the DOM has changed
                    if on_qualified_job:
                        try:
                            cb_res = on_qualified_job(job, None)
                            status = cb_res if isinstance(cb_res, str) else "SUBMITTED"
                        except Exception as e:
                            print_lg(f"[NaukriRotator] Error in qualified job callback: {e}")
                            status = "FAILED"
                    elif target_applier:
                        app_res = safe_apply_job(target_applier, job, card_element=None)
                        status = app_res.get("status", "UNKNOWN")
                    else:
                        status = "QUALIFIED"

                    if status == "SUBMITTED":
                        consecutive_skips = 0
                        term_stats.jobs_applied += 1
                        stats.jobs_applied += 1

                        if self.automation_bridge:
                            try:
                                from app.services.automation_bridge import ApplicationSubmittedEvent
                                self.automation_bridge.handle_application_submitted(
                                    ApplicationSubmittedEvent(
                                        platform="naukri",
                                        external_job_id=job.job_id,
                                        title=job.title,
                                        company=job.company,
                                        source_url=job.source_url,
                                    )
                                )
                            except Exception:
                                pass

                        if stats.jobs_applied >= self.config.daily_application_goal:
                            from modules.helpers import show_modern_goal_dialog
                            print_lg(
                                f"\n🎯 [Naukri Daily Goal Reached] Reached daily goal of {self.config.daily_application_goal} "
                                f"applications on Naukri (Total applied: {stats.jobs_applied})."
                            )
                            should_cont, add_apps = show_modern_goal_dialog(
                                "Naukri.com", stats.jobs_applied, self.config.daily_application_goal
                            )
                            if should_cont and add_apps > 0:
                                self.config.daily_application_goal += add_apps
                                print_lg(
                                    f"🎯 [Naukri Daily Goal Extended] Extended daily goal by +{add_apps} applications. "
                                    f"New goal: {self.config.daily_application_goal}. Resuming automation...\n"
                                )
                            else:
                                print_lg(
                                    f"🎯 [Naukri Daily Goal Completed] Finishing automation run cleanly at {stats.jobs_applied} applications.\n"
                                )
                                return stats
                    elif status == "SKIPPED":
                        consecutive_skips += 1
                        term_stats.jobs_skipped += 1
                        stats.jobs_skipped += 1
                        print_lg(
                            f"[NaukriRotator] Application skipped for '{job.title} | {job.company}'. "
                            f"(Consecutive skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                    elif status == "EXTERNAL":
                        consecutive_skips += 1
                        term_stats.jobs_skipped += 1
                        stats.jobs_skipped += 1
                        print_lg(
                            f"[NaukriRotator] External job skipped for '{job.title} | {job.company}'. "
                            f"(Consecutive skips: {consecutive_skips}/{self.config.consecutive_skips_limit})"
                        )
                    elif status == "MANUAL_REQUIRED":
                        term_stats.jobs_manual_required += 1
                        stats.jobs_manual_required += 1
                    elif status == "FAILED":
                        term_stats.jobs_failed += 1
                        stats.jobs_failed += 1

                # Page-level exit checks
                if consecutive_skips >= self.config.consecutive_skips_limit:
                    if not term_stats.skip_limit_triggered:
                        term_stats.skip_limit_triggered = True
                        stats.consecutive_skips_triggered += 1
                    print_lg(f"\n>>>> Relevance decay: {consecutive_skips} consecutive jobs skipped for '{term}'. Switching to next keyword! <<<<\n")
                    break
                if term_stats.jobs_evaluated >= self.config.max_jobs_evaluated_per_search:
                    term_stats.max_eval_triggered = True
                    print_lg(f"[NaukriRotator] Max jobs evaluated limit ({self.config.max_jobs_evaluated_per_search}) reached for '{term}'.")
                    break
                if page >= self.config.max_pages_per_search:
                    print_lg(f"[NaukriRotator] Max pages limit ({self.config.max_pages_per_search}) reached for '{term}'.")
                    break
                if not self.search.has_next_page():
                    print_lg(f"[NaukriRotator] No next page indicator found after page {page} for '{term}'.")
                    break

            stats.term_stats[term] = term_stats
            print_lg(
                f"[NaukriRotator] Finished '{term}': Pages={term_stats.pages_processed}, "
                f"Evaluated={term_stats.jobs_evaluated}, Qualified={term_stats.jobs_qualified}, "
                f"Skipped={term_stats.jobs_skipped}, Applied={term_stats.jobs_applied}"
            )

        print_lg("\n======================================================================")
        print_lg("NAUKRI SEARCH ROTATION SUMMARY")
        print_lg("======================================================================")
        print_lg(f"Terms Searched       : {stats.terms_searched}")
        print_lg(f"Pages Processed      : {stats.pages_processed}")
        print_lg(f"Jobs Evaluated       : {stats.jobs_evaluated}")
        print_lg(f"Jobs Qualified       : {stats.jobs_qualified}")
        print_lg(f"Jobs Skipped         : {stats.jobs_skipped}")
        print_lg(f"Applications Made    : {stats.jobs_applied}")
        print_lg(f"Manual Interventions : {stats.jobs_manual_required}")
        print_lg(f"Failed Applications  : {stats.jobs_failed}")
        print_lg(f"Relevance Decay Hits : {stats.consecutive_skips_triggered}")
        print_lg("======================================================================\n")

        return stats
