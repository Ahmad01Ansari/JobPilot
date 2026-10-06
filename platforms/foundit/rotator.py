'''
Foundit Search Rotation & Multi-Keyword Engine
Orchestrates multi-keyword search rotation, split-pane pagination,
relevance decay tracking (consecutive skips), job qualification,
and application pipeline execution.
'''

import time
import random
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job
from modules.config_loader import get_platform
from modules.qualification_engine import QualificationEngine, QualificationResult
from modules.tracker import ApplicationTracker
from platforms.foundit.search import FounditSearch
from platforms.foundit.parser import FounditJobParser
from modules.helpers import print_lg


@dataclass
class FounditRotationConfig:
    """Configuration for multi-keyword search rotation and pagination on Foundit."""
    search_terms: List[str] = field(default_factory=list)
    location: Optional[str] = "India"
    experience_years: Optional[int] = 2
    freshness_days: Optional[int] = 7
    max_pages_per_search: int = 3
    max_jobs_evaluated_per_search: int = 75
    consecutive_skips_limit: int = 20
    max_applications: Optional[int] = None
    daily_application_goal: int = 30
    apply_mode: str = "direct_only"
    pause_before_submit: bool = False
    easy_apply_only: bool = True
    sleep_duration_minutes: int = 10
    sleep_mode_enabled: bool = True
    run_non_stop: bool = False

    @classmethod
    def from_profile(cls) -> "FounditRotationConfig":
        """Loads rotation settings from database (with fallback to platforms.foundit in profile.json)."""
        try:
            from config.search import _read_platform_from_db
            db_cfg = _read_platform_from_db("foundit") or {}
        except Exception:
            db_cfg = {}
        cfg = get_platform("foundit") or {}
        merged = {**cfg, **db_cfg}
        apply_mode_val = merged.get("apply_mode", "direct_only")
        easy_apply_val = merged.get("easy_apply_only")
        if easy_apply_val is None:
            easy_apply_val = not (str(apply_mode_val).upper() in ["ALL", "HYBRID", "HYBRID_MODE"] or str(apply_mode_val).lower() == "all")
        else:
            easy_apply_val = bool(easy_apply_val)

        return cls(
            search_terms=list(merged.get("search_terms", ["RPA Developer"])),
            location=merged.get("search_location", "India"),
            experience_years=merged.get("experience_years") if merged.get("experience_years") is not None else merged.get("current_experience", 2),
            freshness_days=merged.get("freshness_days", 7),
            max_pages_per_search=merged.get("max_pages_per_search", 3),
            max_jobs_evaluated_per_search=merged.get("max_jobs_evaluated_per_search", 75),
            consecutive_skips_limit=merged.get("consecutive_skips_limit", 20),
            max_applications=merged.get("switch_number") or merged.get("max_applications", None),
            daily_application_goal=merged.get("daily_application_goal", 30),
            apply_mode=apply_mode_val,
            pause_before_submit=merged.get("pause_before_submit", False),
            easy_apply_only=easy_apply_val,
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
    daily_goal_reached: bool = False
    stopped_by_user: bool = False


class FounditRotator:
    """Executes search rotation and application pipeline on Foundit."""

    def __init__(
        self,
        browser: Any,
        config: Optional[FounditRotationConfig] = None,
        tracker: Optional[ApplicationTracker] = None,
        qualification_engine: Optional[QualificationEngine] = None,
        applier: Optional[Any] = None,
        automation_bridge: Optional[Any] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.config = config or FounditRotationConfig.from_profile()
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        from modules.config_loader import get_candidate_experience
        effective_exp = max(
            get_candidate_experience(user_id=user_id),
            self.config.experience_years or 0,
        )
        self.qualification_engine = qualification_engine or QualificationEngine(
            candidate_experience=effective_exp,
        )
        self.search = FounditSearch(browser=self.browser)
        self.parser = FounditJobParser(browser=self.browser)
        self.applier = applier
        self.automation_bridge = automation_bridge
        self.user_id = user_id

    def run(
        self,
        stop_check: Optional[Callable[[], bool]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """Main rotation loop across configured search terms."""
        rot_stats = RotationStats()
        terms = self.config.search_terms or ["RPA Developer"]
        print_lg(f"[FounditRotator] Starting search rotation for {len(terms)} terms: {terms}")

        for term_idx, term in enumerate(terms, start=1):
            if stop_check and stop_check():
                print_lg("[FounditRotator] Stop requested before starting term.")
                rot_stats.stopped_by_user = True
                break

            # Daily goal check
            daily_count = (
                self.tracker.get_daily_submitted_count(platform="foundit")
                if hasattr(self.tracker, "get_daily_submitted_count")
                else rot_stats.jobs_applied
            )
            if daily_count >= self.config.daily_application_goal:
                print_lg(f"[FounditRotator] Daily application goal reached ({daily_count}/{self.config.daily_application_goal}). Stopping.")
                rot_stats.daily_goal_reached = True
                break

            term_stats = TermStats(term=term)
            consecutive_skips = 0
            print_lg(f"\n[FounditRotator] === Term {term_idx}/{len(terms)}: '{term}' ===")

            for page in range(1, self.config.max_pages_per_search + 1):
                if stop_check and stop_check():
                    rot_stats.stopped_by_user = True
                    break

                # Daily goal check within page loop
                daily_count = (
                    self.tracker.get_daily_submitted_count(platform="foundit")
                    if hasattr(self.tracker, "get_daily_submitted_count")
                    else rot_stats.jobs_applied
                )
                if daily_count >= self.config.daily_application_goal:
                    rot_stats.daily_goal_reached = True
                    break

                # Max evaluations per term check
                if term_stats.jobs_evaluated >= self.config.max_jobs_evaluated_per_search:
                    print_lg(f"[FounditRotator] Max evaluations reached for '{term}' ({term_stats.jobs_evaluated}). Moving to next term.")
                    break

                is_hybrid = (
                    str(self.config.apply_mode).upper() in ["ALL", "HYBRID", "HYBRID_MODE"]
                    or str(self.config.apply_mode).lower() == "all"
                    or getattr(self.config, "easy_apply_only", True) is False
                )
                quick_apply_flag = not is_hybrid

                cards = self.search.search(
                    keyword=term,
                    location=self.config.location,
                    experience_years=self.config.experience_years,
                    freshness_days=self.config.freshness_days,
                    quick_apply=quick_apply_flag,
                    page=page,
                )
                term_stats.pages_processed += 1
                rot_stats.pages_processed += 1

                if not cards:
                    print_lg(f"[FounditRotator] No cards found on page {page} for '{term}'. Advancing.")
                    break

                print_lg(f"[FounditRotator] Page {page}: Discovered {len(cards)} job cards.")
                try:
                    search_window = self.browser.driver.current_window_handle
                except Exception:
                    search_window = None

                for card_idx, card_elem in enumerate(cards, start=1):
                    if stop_check and stop_check():
                        rot_stats.stopped_by_user = True
                        break

                    # Dynamic delay between card evaluations
                    if card_idx > 1:
                        time.sleep(random.uniform(1.5, 3.0))

                    term_stats.jobs_evaluated += 1
                    rot_stats.jobs_evaluated += 1

                    try:
                        try:
                            self.browser.driver.execute_script("arguments[0].scrollIntoView({block: 'nearest'});", card_elem)
                        except Exception:
                            pass

                        job = self.parser.parse_card(card_elem)

                        # If title is missing, enrich from active details pane
                        if not job.title or job.title == "Unknown Role":
                            try:
                                title_targets = card_elem.find_elements(By.CSS_SELECTOR, "div.jobTitle, div#jobCardTitle, a[href*='/job/']")
                                if title_targets:
                                    title_targets[0].click()
                                    time.sleep(0.4)
                                    pane_data = self.parser.parse_active_details_pane()
                                    if pane_data.get("title") and (not job.title or job.title == "Unknown Role"):
                                        job.title = pane_data["title"]
                                    if pane_data.get("company") and (not job.company or job.company == "Unknown Company"):
                                        job.company = pane_data["company"]
                                    if pane_data.get("description"):
                                        job.description = pane_data["description"]
                                    if pane_data.get("salary_text"):
                                        job.raw_metadata["salary_text"] = pane_data["salary_text"]
                                    if pane_data.get("salary_min"):
                                        job.salary_min = pane_data["salary_min"]
                                        job.salary_max = pane_data.get("salary_max")
                                    if pane_data.get("experience_text"):
                                        job.raw_metadata["experience_text"] = pane_data["experience_text"]
                                        job.required_experience_min = pane_data.get("required_experience_min")
                                        job.required_experience_max = pane_data.get("required_experience_max")
                                    if pane_data.get("location") and (not job.location or job.location == "India"):
                                        job.location = pane_data["location"]
                            except Exception:
                                pass
                    except Exception as e:
                        print_lg(f"[FounditRotator] Notice parsing card {card_idx}: {e}")
                        continue

                    # Record DISCOVERED state in tracker
                    if hasattr(self.tracker, "record_discovered"):
                        self.tracker.record_discovered(job)
                    elif hasattr(self.tracker, "record_job"):
                        self.tracker.record_job(job)
                    elif hasattr(self.tracker, "record_state"):
                        self.tracker.record_state(job, "DISCOVERED")

                    # Emit JobDiscoveredEvent to SQLite DB via AutomationBridge
                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import JobDiscoveredEvent
                            self.automation_bridge.handle_job_discovered(JobDiscoveredEvent(
                                platform="foundit",
                                external_job_id=job.job_id,
                                title=job.title or "Unknown Role",
                                company=job.company or "Unknown Company",
                                location=job.location,
                                url=job.source_url,
                                application_method=job.application_method,
                                application_url=job.application_url,
                                description=job.description,
                                experience_text=job.experience_text,
                                salary_text=job.salary_text,
                                salary_min=job.salary_min,
                                salary_max=job.salary_max,
                                required_experience_min=job.required_experience_min,
                                required_experience_max=job.required_experience_max,
                                work_style=job.work_style,
                            ))
                        except Exception:
                            pass

                    # Check easy_apply_only constraint before opening tab or deep processing
                    if self.config.easy_apply_only and job.application_method != "EASY_APPLY":
                        print_lg(f"[FounditRotator] SKIP Non-Easy-Apply: {job.title} | {job.company} (Easy Apply Only mode active)")
                        if hasattr(self.tracker, "record_skipped"):
                            self.tracker.record_skipped(job, reason="NOT_EASY_APPLY")
                        elif hasattr(self.tracker, "record_state"):
                            self.tracker.record_state(job, "SKIPPED", skip_reason="NOT_EASY_APPLY")
                        term_stats.jobs_skipped += 1
                        rot_stats.jobs_skipped += 1
                        continue

                    # Stage 1 Qualification (Fast Title & Company Check)
                    if hasattr(self.qualification_engine, "qualify_job_pre_click"):
                        qual_res_1 = self.qualification_engine.qualify_job_pre_click(job)
                    elif hasattr(self.qualification_engine, "qualify_title"):
                        qual_res_1 = self.qualification_engine.qualify_title(title=job.title, company=job.company, job_id=job.job_id)
                    elif hasattr(self.qualification_engine, "qualify"):
                        qual_res_1 = self.qualification_engine.qualify(job)
                    else:
                        qual_res_1 = QualificationResult(accepted=True)
                    if not qual_res_1:
                        print_lg(f"[FounditRotator] SKIP Stage 1: {job.title} | {job.company} -> {qual_res_1.reason}")
                        if hasattr(self.tracker, "record_skipped"):
                            self.tracker.record_skipped(job, reason=qual_res_1.reason or "STAGE_1_FILTER")
                        elif hasattr(self.tracker, "record_state"):
                            self.tracker.record_state(job, "SKIPPED", skip_reason=qual_res_1.reason or "STAGE_1_FILTER")
                        term_stats.jobs_skipped += 1
                        rot_stats.jobs_skipped += 1
                        consecutive_skips += 1

                        if consecutive_skips >= self.config.consecutive_skips_limit:
                            if page < self.config.max_pages_per_search:
                                print_lg(f"[FounditRotator] Consecutive skips limit ({self.config.consecutive_skips_limit}) reached on page {page} for '{term}'. Advancing to page {page + 1}.")
                                consecutive_skips = 0
                                break
                            else:
                                print_lg(f"[FounditRotator] Consecutive skips limit reached on final page {page} for '{term}'. Advancing to next keyword.")
                                term_stats.skip_limit_triggered = True
                                break
                        continue

                    # Stage 1 Passed: Open job in a new tab for deep inspection & full JD extraction
                    main_window = self.browser.driver.current_window_handle
                    initial_windows = set(self.browser.driver.window_handles)

                    job_href = ""
                    try:
                        for a in card_elem.find_elements(By.TAG_NAME, "a"):
                            href = a.get_attribute("href") or ""
                            if "/job/" in href:
                                job_href = href
                                break
                    except Exception:
                        pass
                    if not job_href and job.source_url and "/job/" in job.source_url:
                        job_href = job.source_url

                    opened_tab = False
                    if job_href:
                        try:
                            self.browser.driver.execute_script("window.open(arguments[0], '_blank');", job_href)
                            opened_tab = True
                        except Exception:
                            pass

                    if not opened_tab:
                        try:
                            title_targets = card_elem.find_elements(By.CSS_SELECTOR, "a[href*='/job/'], div.jobTitle, div#jobCardTitle, h2, h3")
                            if title_targets:
                                self.browser.driver.execute_script("arguments[0].click();", title_targets[0])
                                opened_tab = True
                        except Exception:
                            pass

                    time.sleep(1.2)
                    new_windows = [w for w in self.browser.driver.window_handles if w not in initial_windows]

                    if new_windows:
                        new_tab = new_windows[-1]
                        self.browser.driver.switch_to.window(new_tab)
                        time.sleep(1.5)

                        # Extract full JD, experience, package, already-applied status from dedicated page
                        page_data = self.parser.parse_full_job_page()
                        if page_data.get("title") and (not job.title or job.title == "Unknown Role"):
                            job.title = page_data["title"]
                        if page_data.get("company") and (not job.company or job.company == "Unknown Company"):
                            job.company = page_data["company"]
                        if page_data.get("location"):
                            job.location = page_data["location"]
                        if page_data.get("experience_text"):
                            job.experience_text = page_data["experience_text"]
                            job.required_experience_min = page_data.get("required_experience_min")
                            job.required_experience_max = page_data.get("required_experience_max")
                        if page_data.get("salary_text"):
                            job.salary_text = page_data["salary_text"]
                            job.salary_min = page_data.get("salary_min")
                            job.salary_max = page_data.get("salary_max")
                        if page_data.get("description"):
                            job.description = page_data["description"]
                        if page_data.get("work_style"):
                            job.work_style = page_data["work_style"]
                        if page_data.get("application_method"):
                            job.application_method = page_data["application_method"]
                            job.apply_type = page_data.get("apply_type", "DIRECT" if job.application_method == "EASY_APPLY" else "EXTERNAL")
                        job.source_url = self.browser.driver.current_url or job_href or job.source_url

                        # Check easy_apply_only constraint after full page inspection
                        if self.config.easy_apply_only and job.application_method != "EASY_APPLY":
                            print_lg(f"[FounditRotator] SKIP Non-Easy-Apply after page inspection: {job.title} | {job.company}")
                            if hasattr(self.tracker, "record_skipped"):
                                self.tracker.record_skipped(job, reason="NOT_EASY_APPLY")
                            elif hasattr(self.tracker, "record_state"):
                                self.tracker.record_state(job, "SKIPPED", skip_reason="NOT_EASY_APPLY")
                            try:
                                self.browser.driver.close()
                            except Exception:
                                pass
                            self.browser.driver.switch_to.window(main_window)
                            term_stats.jobs_skipped += 1
                            rot_stats.jobs_skipped += 1
                            continue

                        # Sync enriched job to DB via AutomationBridge
                        if self.automation_bridge:
                            try:
                                from app.services.automation_events import JobDiscoveredEvent
                                self.automation_bridge.handle_job_discovered(JobDiscoveredEvent(
                                    platform="foundit",
                                    external_job_id=job.job_id,
                                    title=job.title or "Unknown Role",
                                    company=job.company or "Unknown Company",
                                    location=job.location,
                                    url=job.source_url,
                                    application_method=job.application_method,
                                    application_url=job.application_url,
                                    description=job.description,
                                    experience_text=job.experience_text,
                                    salary_text=job.salary_text,
                                    salary_min=job.salary_min,
                                    salary_max=job.salary_max,
                                    required_experience_min=job.required_experience_min,
                                    required_experience_max=job.required_experience_max,
                                    work_style=job.work_style,
                                ))
                            except Exception:
                                pass

                        # 2.1 Identify already applied or not (Screenshot 2)
                        if page_data.get("is_applied"):
                            print_lg(f"[FounditRotator] Job '{job.title}' at '{job.company}' is ALREADY APPLIED on portal ({page_data.get('applied_status_text')}). Skipping.")
                            if hasattr(self.tracker, "record_skipped"):
                                self.tracker.record_skipped(job, reason="ALREADY_APPLIED_ON_PORTAL")
                            elif hasattr(self.tracker, "record_state"):
                                self.tracker.record_state(job, "SKIPPED", skip_reason="ALREADY_APPLIED_ON_PORTAL")
                            try:
                                self.browser.driver.close()
                            except Exception:
                                pass
                            self.browser.driver.switch_to.window(main_window)
                            term_stats.jobs_skipped += 1
                            rot_stats.jobs_skipped += 1
                            continue

                        # 2.2 Deep Stage 2 Qualification on full JD
                        qual_res_2 = self.qualification_engine.qualify(job)
                        if not qual_res_2:
                            print_lg(f"[FounditRotator] SKIP Stage 2: {job.title} | {job.company} -> {qual_res_2.reason}")
                            if hasattr(self.tracker, "record_skipped"):
                                self.tracker.record_skipped(job, reason=qual_res_2.reason or "STAGE_2_FILTER")
                            elif hasattr(self.tracker, "record_state"):
                                self.tracker.record_state(job, "SKIPPED", skip_reason=qual_res_2.reason or "STAGE_2_FILTER")
                            try:
                                self.browser.driver.close()
                            except Exception:
                                pass
                            self.browser.driver.switch_to.window(main_window)
                            term_stats.jobs_skipped += 1
                            rot_stats.jobs_skipped += 1
                            consecutive_skips += 1
                            if consecutive_skips >= self.config.consecutive_skips_limit:
                                if page < self.config.max_pages_per_search:
                                    print_lg(f"[FounditRotator] Consecutive skips limit reached on page {page} for '{term}'. Advancing to page {page + 1}.")
                                    consecutive_skips = 0
                                    break
                                else:
                                    print_lg(f"[FounditRotator] Consecutive skips limit reached on final page {page} for '{term}'. Advancing to next keyword.")
                                    term_stats.skip_limit_triggered = True
                                    break
                            continue

                        # Apply on dedicated job details page (handles Quick Apply & Screen Questionnaire)
                        print_lg(f"[FounditRotator] QUALIFIED Stage 2: {job.title} | {job.company}. Applying on job page...")
                        term_stats.jobs_qualified += 1
                        rot_stats.jobs_qualified += 1
                        if self.automation_bridge:
                            try:
                                from app.services.automation_events import JobQualifiedEvent
                                self.automation_bridge.handle_job_qualified(JobQualifiedEvent(
                                    platform="foundit",
                                    external_job_id=job.job_id,
                                    title=job.title or "Unknown Role",
                                    company=job.company or "Unknown Company",
                                ))
                            except Exception:
                                pass

                        if self.applier:
                            try:
                                apply_res = self.applier.apply_on_job_page(
                                    job,
                                    pause_before_submit=self.config.pause_before_submit,
                                    stop_check=stop_check,
                                )
                                status = apply_res.get("status")
                                if status in ["SUBMITTED", "EXTERNAL"]:
                                    consecutive_skips = 0
                                    term_stats.jobs_applied += 1
                                    rot_stats.jobs_applied += 1
                                elif status in ["SKIPPED", "ALREADY_APPLIED"]:
                                    term_stats.jobs_skipped += 1
                                    rot_stats.jobs_skipped += 1
                                elif status == "MANUAL_REQUIRED":
                                    term_stats.jobs_manual_required += 1
                                    rot_stats.jobs_manual_required += 1
                                elif status == "FAILED":
                                    term_stats.jobs_failed += 1
                                    rot_stats.jobs_failed += 1
                            except Exception as e:
                                print_lg(f"[FounditRotator] Application execution error: {e}")
                                term_stats.jobs_failed += 1
                                rot_stats.jobs_failed += 1

                        # Close job details tab cleanly and close all extra tabs (e.g. Applied Success)
                        try:
                            for h in list(self.browser.driver.window_handles):
                                if h != main_window:
                                    try:
                                        self.browser.driver.switch_to.window(h)
                                        time.sleep(0.15)
                                        self.browser.driver.close()
                                    except Exception:
                                        pass
                            self.browser.driver.switch_to.window(main_window)
                        except Exception:
                            pass
                    else:
                        # Fallback for environments where new window didn't open (e.g. unit mocks)
                        if self.applier:
                            try:
                                apply_res = self.applier.apply(
                                    job,
                                    card_elem=card_elem,
                                    qualification_engine=self.qualification_engine,
                                    pause_before_submit=self.config.pause_before_submit,
                                    stop_check=stop_check,
                                )
                                status = apply_res.get("status")
                                if status in ["SUBMITTED", "EXTERNAL"]:
                                    consecutive_skips = 0
                                    term_stats.jobs_qualified += 1
                                    rot_stats.jobs_qualified += 1
                                    term_stats.jobs_applied += 1
                                    rot_stats.jobs_applied += 1
                                elif status == "SKIPPED":
                                    term_stats.jobs_skipped += 1
                                    rot_stats.jobs_skipped += 1
                                    consecutive_skips += 1
                                    if consecutive_skips >= self.config.consecutive_skips_limit:
                                        if page < self.config.max_pages_per_search:
                                            print_lg(f"[FounditRotator] Consecutive skips limit reached on page {page} for '{term}'. Advancing to page {page + 1}.")
                                            consecutive_skips = 0
                                            break
                                        else:
                                            print_lg(f"[FounditRotator] Consecutive skips limit reached on final page {page} for '{term}'. Advancing to next keyword.")
                                            term_stats.skip_limit_triggered = True
                                            break
                                elif status == "MANUAL_REQUIRED":
                                    term_stats.jobs_manual_required += 1
                                    rot_stats.jobs_manual_required += 1
                                elif status == "FAILED":
                                    term_stats.jobs_failed += 1
                                    rot_stats.jobs_failed += 1
                            except Exception as e:
                                print_lg(f"[FounditRotator] Application execution error: {e}")
                                term_stats.jobs_failed += 1
                                rot_stats.jobs_failed += 1

                        # Clean up any extra tabs (e.g. Applied Success) opened during direct apply
                        try:
                            for h in list(self.browser.driver.window_handles):
                                if h != main_window:
                                    try:
                                        self.browser.driver.switch_to.window(h)
                                        time.sleep(0.15)
                                        self.browser.driver.close()
                                    except Exception:
                                        pass
                            self.browser.driver.switch_to.window(main_window)
                        except Exception:
                            pass

                if term_stats.skip_limit_triggered or (stop_check and stop_check()) or rot_stats.daily_goal_reached:
                    break

            rot_stats.terms_searched += 1
            if rot_stats.daily_goal_reached or (stop_check and stop_check()):
                break

        print_lg("\n======================================================================")
        print_lg(f"FOUNDIT ROTATION COMPLETE — Applied: {rot_stats.jobs_applied}, Qualified: {rot_stats.jobs_qualified}, Skipped: {rot_stats.jobs_skipped}")
        print_lg("======================================================================\n")

        return {
            "platform": "foundit",
            "terms_searched": rot_stats.terms_searched,
            "pages_processed": rot_stats.pages_processed,
            "jobs_evaluated": rot_stats.jobs_evaluated,
            "jobs_qualified": rot_stats.jobs_qualified,
            "jobs_skipped": rot_stats.jobs_skipped,
            "jobs_applied": rot_stats.jobs_applied,
            "jobs_manual_required": rot_stats.jobs_manual_required,
            "jobs_failed": rot_stats.jobs_failed,
            "daily_goal_reached": rot_stats.daily_goal_reached,
            "stopped_by_user": rot_stats.stopped_by_user,
        }


FounditSearchRotator = FounditRotator
