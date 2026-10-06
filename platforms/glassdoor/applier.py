'''
Glassdoor Application Coordinator
Orchestrates end-to-end job application lifecycle on Glassdoor:
1. Stage 1 Fast Qualification (title, company, previous applications).
2. Job card interaction and details pane inspection.
3. Stage 2 Deep Qualification (JD extraction, experience, bad keywords).
4. Application flow detection (Easy Apply vs External company site vs Already Applied).
5. Multi-step form progression and QnA resolution.
6. Submitter and positive confirmation logging in ApplicationTracker.
'''

import time
from typing import Optional, Tuple, Any, Dict, Callable
from selenium.webdriver.common.by import By

from platforms.glassdoor.search import GlassdoorJobItem
from platforms.glassdoor.parser import GlassdoorParser
from platforms.glassdoor.form import GlassdoorForm
from platforms.glassdoor.submitter import GlassdoorSubmitter
from platforms.glassdoor.captcha_handler import GlassdoorCaptchaHandler
from platforms.glassdoor.selectors import (
    APPLY_EASY_TRIGGERS,
    APPLY_EXTERNAL_TRIGGERS,
    APPLY_ALREADY_BADGES,
)
from modules.helpers import print_lg
from modules.tracker import ApplicationTracker
from modules.qualification_engine import QualificationEngine
from modules.models import Job
from modules.human_behavior import human_delay, smooth_scroll


class GlassdoorFlowDetector:
    """Classifies a Glassdoor job into EASY_APPLY, EXTERNAL, ALREADY_APPLIED, or UNAVAILABLE."""

    @staticmethod
    def detect_flow(driver: Any) -> Tuple[str, Optional[Any]]:
        """Inspects details pane and returns (flow_type, element)."""
        if not driver:
            return ("UNAVAILABLE", None)

        # 1. Already Applied badge check
        for sel in APPLY_ALREADY_BADGES:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return ("ALREADY_APPLIED", None)
            except Exception:
                continue

        # 2. Easy Apply triggers
        for sel in APPLY_EASY_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed() and el.is_enabled():
                        return ("EASY_APPLY", el)
            except Exception:
                continue

        # 3. External Company Site triggers
        for sel in APPLY_EXTERNAL_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        return ("EXTERNAL", el)
            except Exception:
                continue

        # 4. Dynamic JS fallback for Easy Apply button (real browser only, ignore mock)
        try:
            js_btn = driver.execute_script('''
                var btns = Array.from(document.querySelectorAll("button, a[role='button']"));
                for (var b of btns) {
                    var txt = (b.innerText || b.textContent || '').trim().toLowerCase();
                    var dt = (b.getAttribute('data-test') || '').toLowerCase();
                    if ((txt.includes('easy apply') || dt === 'easyapply') && b.offsetWidth > 0 && b.offsetHeight > 0) {
                        return b;
                    }
                }
                return null;
            ''')
            if js_btn and not type(js_btn).__name__.startswith("MagicMock") and not type(js_btn).__name__.startswith("Mock"):
                return ("EASY_APPLY", js_btn)
        except Exception:
            pass

        return ("UNAVAILABLE", None)


def _safe_handles(driver: Any) -> list:
    """Safely extracts window handles list from driver or mock."""
    if not driver:
        return []
    try:
        handles = getattr(driver, "window_handles", [])
        if isinstance(handles, (list, tuple)):
            return list(handles)
        return [h for h in handles]
    except Exception:
        return []


def _safe_current_handle(driver: Any) -> Optional[str]:
    """Safely extracts current window handle from driver or mock."""
    if not driver:
        return None
    try:
        h = getattr(driver, "current_window_handle", None)
        return str(h) if h is not None else None
    except Exception:
        return None


class GlassdoorApplier:
    """Orchestrates single-job application workflow on Glassdoor."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        qualification_engine: Optional[QualificationEngine] = None,
        automation_bridge: Optional[Any] = None,
        pause_before_submit: bool = False,
        user_id: int = 1,
        search: Optional[Any] = None,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.qualification_engine = qualification_engine or QualificationEngine()
        self.automation_bridge = automation_bridge
        self.user_id = user_id
        self.form = GlassdoorForm(browser=self.browser)
        self.submitter = GlassdoorSubmitter(browser=self.browser, pause_before_submit=pause_before_submit)
        self.captcha_handler = GlassdoorCaptchaHandler(browser=self.browser, automation_bridge=self.automation_bridge)
        from platforms.glassdoor.search import GlassdoorSearch
        self.search = search or GlassdoorSearch(browser=self.browser)

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def _record_submission(self, job_item: GlassdoorJobItem) -> None:
        """Records submitted application to tracker and dispatches UI events."""
        self.tracker.record_application(
            platform="glassdoor",
            job_id=job_item.job_id,
            title=job_item.title,
            company=job_item.company,
            location=job_item.location,
            url=job_item.job_url,
            status="SUBMITTED",
        )
        if self.automation_bridge:
            try:
                from app.services.automation_events import ApplicationSubmittedEvent
                self.automation_bridge.handle_application_submitted(
                    ApplicationSubmittedEvent(
                        run_id="glassdoor_run",
                        platform="glassdoor",
                        job_id=job_item.job_id,
                        title=job_item.title,
                        company=job_item.company,
                        location=job_item.location,
                        application_method="EASY_APPLY",
                        timestamp=time.time(),
                    )
                )
            except Exception:
                pass

    def _locate_job_card(self, job_item: GlassdoorJobItem, card_index: Optional[int]) -> Optional[Any]:
        """Re-locates fresh card element from current DOM."""
        if not self.driver:
            return None

        # 1. By job ID attributes
        if job_item.job_id:
            id_selectors = [
                f"li[data-jobid='{job_item.job_id}']",
                f"[data-test='jobListing'][data-id='{job_item.job_id}']",
                f"a[data-jobid='{job_item.job_id}']",
                f"a[href*='{job_item.job_id}']",
                f"//li[.//a[contains(@href, '{job_item.job_id}')]]",
            ]
            for id_sel in id_selectors:
                try:
                    elems = self.driver.find_elements(By.XPATH if id_sel.startswith("/") else By.CSS_SELECTOR, id_sel)
                    for el in elems:
                        if el.is_displayed():
                            return el
                except Exception:
                    continue

        # 2. Fresh query via get_job_card_elements
        if card_index is not None:
            try:
                fresh_cards = self.search.get_job_card_elements()
                if fresh_cards:
                    visible_cards = [c for c in fresh_cards if c.is_displayed()]
                    if visible_cards and card_index < len(visible_cards):
                        return visible_cards[card_index]
                    elif card_index < len(fresh_cards):
                        return fresh_cards[card_index]
            except Exception:
                pass

            # Fallback to selectors.JOB_CARD_ELEMENTS
            try:
                from platforms.glassdoor.selectors import JOB_CARD_ELEMENTS
                for sel in JOB_CARD_ELEMENTS:
                    try:
                        elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                        visible_cards = [e for e in elems if e.is_displayed()]
                        if visible_cards and card_index < len(visible_cards):
                            return visible_cards[card_index]
                        elif elems and card_index < len(elems):
                            return elems[card_index]
                    except Exception:
                        continue
            except Exception:
                pass

        # 3. Fallback to saved card element if not stale
        if job_item.card_element:
            try:
                if job_item.card_element.is_displayed():
                    return job_item.card_element
            except Exception:
                pass

        return None

    def apply(
        self,
        job_item: GlassdoorJobItem,
        card_index: Optional[int] = None,
        main_window: Optional[str] = None,
        stop_check: Optional[Callable[[], bool]] = None,
        search_url: Optional[str] = None,
    ) -> str:
        """Processes a single discovered job item with safe element re-querying and full application traversal."""
        if not self.driver:
            return "failed"

        if stop_check and stop_check():
            return "stopped"

        if not main_window:
            main_window = _safe_current_handle(self.driver)

        # Ensure we start focused on main_window and close any orphaned tabs left from prior runs
        cur_handles = _safe_handles(self.driver)
        if main_window and cur_handles and main_window in cur_handles:
            for h in cur_handles:
                if h != main_window:
                    try:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                    except Exception:
                        pass
            try:
                self.driver.switch_to.window(main_window)
            except Exception:
                pass

        # Search Window Integrity Guard: Ensure main_window is actually on search results, not stuck on single job page or recommended page
        search_target_url = search_url or getattr(self, "last_search_url", None) or getattr(self.search, "last_search_url", None)
        curr_main_url = (self.driver.current_url or "").lower()
        is_single_job = "/job-listing/" in curr_main_url
        is_home_recommended = "/index.htm" in curr_main_url or curr_main_url.endswith("/job/")
        if (is_single_job or is_home_recommended) and search_target_url and search_target_url.lower() != curr_main_url:
            print_lg(f"[GlassdoorApplier] Main window was on {curr_main_url} instead of search results. Restoring search page: {search_target_url}...")
            try:
                self.driver.get(search_target_url)
                human_delay(2.0, 3.5)
            except Exception:
                pass

        # 1. Stage 1 Qualification (Fast title / company check)
        title_res = self.qualification_engine.qualify_title(job_item.title, company=job_item.company or "", job_id=job_item.job_id)
        if not title_res.accepted:
            print_lg(f"[GlassdoorApplier] SKIP: Title '{job_item.title}' disqualified: {title_res.reason}")
            self.tracker.record_application(
                platform="glassdoor",
                job_id=job_item.job_id,
                title=job_item.title,
                company=job_item.company,
                location=job_item.location,
                url=job_item.job_url,
                status="SKIPPED",
                reason=title_res.reason,
            )
            return "skipped"

        # Check existing application in tracker
        if hasattr(self.tracker, "is_already_handled"):
            res = self.tracker.is_already_handled(job_item.job_id, platform="glassdoor", user_id=self.user_id)
            if isinstance(res, tuple):
                should_skip, reason = res[0], res[1] if len(res) > 1 else None
            else:
                should_skip = (res is True)
                reason = "Already applied or handled"
            if should_skip:
                print_lg(f"[GlassdoorApplier] SKIP: Already handled {job_item.title} ({job_item.job_id}): {reason}")
                return "skipped"
        elif hasattr(self.tracker, "is_applied"):
            if self.tracker.is_applied(job_item.job_id, platform="glassdoor") is True:
                print_lg(f"[GlassdoorApplier] SKIP: Already applied to {job_item.title} ({job_item.job_id})")
                return "skipped"

        job_tab = None
        app_tab = None

        try:
            # 2. Re-locate and Click Job Card (Preserving Search Page)
            if hasattr(self.browser, "dismiss_overlays"):
                self.browser.dismiss_overlays()

            card_elem = self._locate_job_card(job_item, card_index)
            pre_card_handles = _safe_handles(self.driver)

            if card_elem:
                try:
                    smooth_scroll(self.driver, card_elem)
                    human_delay(0.3, 0.6)
                    # Click the card body container (NOT the anchor) to select card in split view without navigating away
                    self.driver.execute_script("""
                        var card = arguments[0];
                        var target = card.querySelector("div[class*='jobCard'], div[class*='JobCard'], div[class*='header'], div[data-test='jobCard']") || card;
                        target.click();
                    """, card_elem)
                    human_delay(1.5, 2.5)
                    if hasattr(self.browser, "dismiss_overlays"):
                        self.browser.dismiss_overlays()
                except Exception as e:
                    print_lg(f"[GlassdoorApplier] Notice clicking job card: {e}")

            # Check if clicking the card opened a new window/tab
            post_card_handles = _safe_handles(self.driver)
            new_handles = [h for h in post_card_handles if h not in pre_card_handles]
            if new_handles:
                job_tab = new_handles[-1]
                self.driver.switch_to.window(job_tab)
                print_lg(f"[GlassdoorApplier] Job opened in new tab: {job_tab}")
                human_delay(1.5, 2.5)
            else:
                job_tab = None
                curr_u = (self.driver.current_url or "").lower()
                if "/job-listing/" in curr_u:
                    # In case the click navigated main_window to /job-listing/, immediately isolate it into a new tab
                    # and restore main_window to search results page
                    print_lg("[GlassdoorApplier] Notice: Job card click navigated main window. Moving job to new tab and restoring search page...")
                    job_nav_url = self.driver.current_url
                    self.driver.execute_script("window.open(arguments[0], '_blank');", job_nav_url)
                    time.sleep(1.0)
                    fresh_h = _safe_handles(self.driver)
                    new_tabs = [h for h in fresh_h if h != main_window and h not in pre_card_handles]
                    if new_tabs:
                        job_tab = new_tabs[-1]
                    self.driver.switch_to.window(main_window)
                    if search_target_url:
                        self.driver.get(search_target_url)
                    human_delay(1.5, 2.5)
                    if job_tab:
                        self.driver.switch_to.window(job_tab)
                        human_delay(1.5, 2.5)
                else:
                    print_lg("[GlassdoorApplier] Job displayed in details pane (same window).")

            # Check CAPTCHA / bot walls
            if self.captcha_handler.is_captcha_present(self.driver):
                solved = self.captcha_handler.handle_captcha(self.driver, stop_check=stop_check)
                if not solved:
                    return "manual_required"

            # Wait up to 8s for details pane or new tab to populate
            for _ in range(16):
                has_details = False
                try:
                    has_details = self.driver.execute_script("""
                        var el = document.querySelector("#jobDescriptionText") ||
                                 document.querySelector("div[data-test='jobDescriptionContent']") ||
                                 document.querySelector(".jobDescriptionContent") ||
                                 document.querySelector("div[class*='JobDetails_jobDescription']") ||
                                 document.querySelector("[data-test='job-description-content']") ||
                                 document.querySelector("#JobDescriptionContainer") ||
                                 document.querySelector("div[class*='JobDetails_jobDetailsContainer']") ||
                                 document.querySelector("div[class*='JobDetails_jobDescriptionWrapper']") ||
                                 document.querySelector("div[class*='JobDetails_jobDetails']") ||
                                 document.querySelector("section[data-test='job-description']") ||
                                 document.querySelector("main[class*='JobDetails']") ||
                                 document.querySelector("article");
                        if (el && (el.innerText || el.textContent || '').trim().length > 30) return true;
                        var scripts = document.querySelectorAll("script[type='application/ld+json']");
                        for (var s of scripts) {
                            if (s.textContent && s.textContent.includes('JobPosting')) return true;
                        }
                        return false;
                    """)
                except Exception:
                    pass
                if has_details:
                    break
                time.sleep(0.5)

            # Expand "Show more" button if present
            try:
                self.driver.execute_script("""
                    var moreBtns = document.querySelectorAll(
                        "[data-test='show-more-button'], button[class*='showMore'], button[class*='ShowMore'], " +
                        "button[aria-label*='Show more' i], button[aria-label*='Read more' i]"
                    );
                    for (var b of moreBtns) {
                        if (b.offsetWidth > 0 && b.offsetHeight > 0) {
                            b.click();
                            break;
                        }
                    }
                """)
            except Exception:
                pass

            # 3. Extract Full JD & Stage 2 Deep Qualification
            from platforms.glassdoor.extractor import GlassdoorJobDescriptionExtractor
            jd_res = GlassdoorJobDescriptionExtractor.extract_from_dom(self.driver)
            if jd_res.is_usable:
                jd_text = jd_res.description
                job_item.description = jd_text
            else:
                fallback_text = GlassdoorParser.extract_job_description(self.driver)
                if fallback_text and len(fallback_text) > 0:
                    jd_text = fallback_text
                    job_item.description = fallback_text
                else:
                    print_lg(f"[GlassdoorApplier] SKIP: JD extraction failed for '{job_item.title}': {jd_res.failure_reason}")
                    self.tracker.record_application(
                        platform="glassdoor",
                        job_id=job_item.job_id,
                        title=job_item.title,
                        company=job_item.company,
                        location=job_item.location,
                        url=job_item.job_url,
                        status="SKIPPED",
                        reason=f"JD extraction failed: {jd_res.failure_reason}",
                    )
                    return "skipped"

            # Enrich company, location, salary if missing or generic
            if not job_item.company or job_item.company.lower() in ["apply", "jobs", "glassdoor", "unknown company"]:
                try:
                    c_text = self.driver.execute_script("""
                        var el = document.querySelector("[data-test='employer-name'], [class*='EmployerProfile_employerName'], [class*='JobDetails_employerName']");
                        return el ? (el.innerText || el.textContent || '').trim() : '';
                    """)
                    if c_text:
                        job_item.company = c_text
                except Exception:
                    pass

            if not job_item.salary:
                try:
                    sal_el = self.driver.find_element(By.CSS_SELECTOR, "[data-test='detailSalary'], [class*='salaryEstimate'], [class*='SalaryEstimate']")
                    if sal_el and sal_el.text.strip():
                        job_item.salary = sal_el.text.strip()
                except Exception:
                    pass

            if self.tracker:
                try:
                    self.tracker.record_state(job_item.to_job(), "QUALIFIED")
                except Exception as e:
                    print_lg(f"[GlassdoorApplier] Notice syncing qualified job state: {e}")

            desc_res = self.qualification_engine.qualify_description(jd_text, title=job_item.title)
            if not desc_res.accepted:
                print_lg(f"[GlassdoorApplier] SKIP: JD disqualified for '{job_item.title}': {desc_res.reason}")
                self.tracker.record_application(
                    platform="glassdoor",
                    job_id=job_item.job_id,
                    title=job_item.title,
                    company=job_item.company,
                    location=job_item.location,
                    url=job_item.job_url,
                    status="SKIPPED",
                    reason=desc_res.reason,
                )
                return "skipped"

            # 4. Detect Flow
            flow_type, trigger_btn = GlassdoorFlowDetector.detect_flow(self.driver)
            print_lg(f"[GlassdoorApplier] Detected flow for '{job_item.title}': {flow_type}")

            if flow_type == "EASY_APPLY":
                job_item.is_easy_apply = True
            elif flow_type == "EXTERNAL":
                job_item.is_easy_apply = False

            if flow_type == "ALREADY_APPLIED":
                self.tracker.record_application(
                    platform="glassdoor",
                    job_id=job_item.job_id,
                    title=job_item.title,
                    company=job_item.company,
                    location=job_item.location,
                    url=job_item.job_url,
                    status="ALREADY_APPLIED",
                )
                return "skipped"

            if flow_type == "EXTERNAL":
                self.tracker.record_application(
                    platform="glassdoor",
                    job_id=job_item.job_id,
                    title=job_item.title,
                    company=job_item.company,
                    location=job_item.location,
                    url=job_item.job_url,
                    status="EXTERNAL",
                )
                return "external"

            if flow_type != "EASY_APPLY" or not trigger_btn:
                print_lg(f"[GlassdoorApplier] Job '{job_item.title}' has no actionable Easy Apply button.")
                return "skipped"

            # 5. Execute Easy Apply Flow
            if self.tracker:
                try:
                    self.tracker.record_state(job_item.to_job(), "APPLYING")
                except Exception:
                    pass

            pre_apply_handles = _safe_handles(self.driver)

            if hasattr(self.browser, "dismiss_overlays"):
                self.browser.dismiss_overlays()

            smooth_scroll(self.driver, trigger_btn)
            human_delay(0.8, 1.5)
            try:
                trigger_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", trigger_btn)

            # Poll for new application window/tab (up to 10 seconds)
            start_poll = time.time()
            while time.time() - start_poll < 10.0:
                cur_poll_handles = _safe_handles(self.driver)
                if len(cur_poll_handles) > len(pre_apply_handles):
                    new_h = [h for h in cur_poll_handles if h not in pre_apply_handles]
                    if new_h:
                        app_tab = new_h[-1]
                        break
                time.sleep(0.5)

            if app_tab:
                self.driver.switch_to.window(app_tab)
                print_lg(f"[GlassdoorApplier] Switched to new application tab: {app_tab}")
                start_u = time.time()
                while time.time() - start_u < 10.0:
                    cur_u = (self.driver.current_url or "").lower()
                    if "smartapply" in cur_u or "indeed" in cur_u or ("about:blank" not in cur_u and "chrome://" not in cur_u):
                        break
                    time.sleep(0.5)

            cur_url = (self.driver.current_url or "").lower()
            is_indeed_smartapply = ("indeed" in cur_url or "smartapply" in cur_url)

            # Branch A: Indeed Smart Apply SPA (smartapply.indeed.com)
            if is_indeed_smartapply:
                from platforms.indeed.form import IndeedForm
                from platforms.indeed.submitter import IndeedSubmitter
                from platforms.indeed.captcha_handler import IndeedCaptchaHandler

                indeed_captcha = IndeedCaptchaHandler(self.browser, self.automation_bridge)
                indeed_form = IndeedForm(self.browser, qna_engine=self.form.qna_engine, captcha_handler=indeed_captcha)
                indeed_submitter = IndeedSubmitter(self.browser, tracker=self.tracker, automation_bridge=self.automation_bridge, captcha_handler=indeed_captcha)

                # Wait for initial React mount & spinner clearing on Smart Apply tab
                indeed_form.wait_for_page_ready(timeout=15)

                max_steps = 12
                for step_num in range(1, max_steps + 1):
                    if stop_check and stop_check():
                        return "stopped"

                    indeed_form.wait_for_page_ready(timeout=6)
                    step_type = indeed_form.detect_step_type()
                    print_lg(f"[GlassdoorApplier] Smart Apply step #{step_num}: {step_type}")

                    if step_type == "CONFIRMATION" or indeed_form.is_confirmation_page():
                        print_lg("[GlassdoorApplier] Application confirmation detected!")
                        self._record_submission(job_item)
                        return "submitted"

                    if step_type == "REVIEW" or indeed_form.is_review_page_ready():
                        print_lg(f"[GlassdoorApplier] Review module reached on step {step_num}.")
                        if self.submitter.pause_before_submit:
                            print_lg("[GlassdoorApplier] 'pause_before_submit' is enabled. Awaiting user verification in browser...")
                            if self.automation_bridge:
                                try:
                                    from app.services.automation_events import AutomationInterventionEvent, InterventionType
                                    ev = AutomationInterventionEvent(
                                        run_id="glassdoor_run",
                                        platform="glassdoor",
                                        intervention_type=InterventionType.PRE_SUBMISSION_REVIEW,
                                        message=f"Review step reached for '{job_item.title}' at '{job_item.company}'. Please verify and click Submit in the browser.",
                                        action_url=self.driver.current_url,
                                    )
                                    if hasattr(self.automation_bridge, "handle_intervention"):
                                        self.automation_bridge.handle_intervention(ev)
                                    elif callable(getattr(self.automation_bridge, "on_intervention", None)):
                                        self.automation_bridge.on_intervention(ev)
                                except Exception as exc:
                                    print_lg(f"[GlassdoorApplier] Notice dispatching review intervention: {exc}")

                            start_wait = time.time()
                            user_submitted = False
                            while time.time() - start_wait < 120:
                                if stop_check and stop_check():
                                    return "stopped"
                                cur_u = (self.driver.current_url or "").lower()
                                if indeed_form.is_confirmation_page() or "post-apply" in cur_u or "applied" in cur_u:
                                    user_submitted = True
                                    break
                                time.sleep(1.5)

                            if user_submitted:
                                print_lg("[GlassdoorApplier] Manual application submission confirmed!")
                                self._record_submission(job_item)
                                return "submitted"
                            else:
                                print_lg("[GlassdoorApplier] Manual review window closed or timeout elapsed.")
                                return "manual_required"

                        if indeed_captcha.is_captcha_present(self.driver):
                            print_lg("[GlassdoorApplier] Security verification / CAPTCHA challenge present on review page.")
                            if self.automation_bridge:
                                try:
                                    from app.services.automation_events import AutomationInterventionEvent, InterventionType
                                    ev = AutomationInterventionEvent(
                                        run_id="glassdoor_run",
                                        platform="glassdoor",
                                        intervention_type=InterventionType.CAPTCHA_DETECTED,
                                        message="Security verification / CAPTCHA detected on application window. Please solve the puzzle in the browser window to submit.",
                                        action_url=self.driver.current_url,
                                    )
                                    if hasattr(self.automation_bridge, "handle_intervention"):
                                        self.automation_bridge.handle_intervention(ev)
                                    elif callable(getattr(self.automation_bridge, "on_intervention", None)):
                                        self.automation_bridge.on_intervention(ev)
                                except Exception as exc:
                                    print_lg(f"[GlassdoorApplier] Notice dispatching CAPTCHA intervention: {exc}")

                            start_wait = time.time()
                            while time.time() - start_wait < 180:
                                if stop_check and stop_check():
                                    return "stopped"
                                is_enabled = self.driver.execute_script('''
                                    var btn = document.querySelector("button[data-testid='submit-application-button'], button[type='submit']");
                                    return Boolean(btn && !btn.disabled && btn.offsetWidth > 0);
                                ''')
                                if is_enabled:
                                    print_lg("[GlassdoorApplier] CAPTCHA resolved! Submit button enabled.")
                                    break
                                time.sleep(1.5)

                        success = indeed_submitter.execute_submission(
                            app_window=app_tab,
                            main_window=main_window,
                            job_title=job_item.title,
                            company=job_item.company,
                            stop_check=stop_check,
                        )
                        if success:
                            self._record_submission(job_item)
                            return "submitted"
                        else:
                            print_lg("[GlassdoorApplier] Submit action did not produce verified success.")
                            return "failed"

                    elif step_type == "CAPTCHA":
                        print_lg("[GlassdoorApplier] CAPTCHA step detected during questionnaire!")
                        indeed_captcha.handle_captcha(self.driver, stop_check=stop_check)
                        continue
                    elif step_type == "CONTACT_INFO":
                        indeed_form.fill_contact_info()
                    elif step_type == "LOCATION":
                        indeed_form.fill_location_info()
                    elif step_type == "RESUME":
                        indeed_form.handle_resume_selection()
                    elif step_type == "QUESTIONS":
                        indeed_form.answer_screening_questions(job_item.title, job_item.company)

                    advanced = indeed_form.advance_to_next_step()
                    if not advanced:
                        time.sleep(1.5)
                        if indeed_form.is_review_page_ready():
                            continue
                        print_lg(f"[GlassdoorApplier] Could not advance Smart Apply beyond step {step_num}.")
                        break

            # Branch B: Glassdoor Internal / Native Easy Apply
            else:
                max_steps = 10
                for step_num in range(1, max_steps + 1):
                    if stop_check and stop_check():
                        return "stopped"

                    if self.submitter.pause_before_submit and self.form.is_review_step():
                        print_lg("[GlassdoorApplier] Pausing at review step for manual verification.")
                        return "manual_required"

                    if self.form.is_review_step():
                        print_lg(f"[GlassdoorApplier] Review step reached on step {step_num}. Submitting...")
                        success = self.submitter.submit_application()
                        if success:
                            self._record_submission(job_item)
                            return "submitted"
                        else:
                            print_lg("[GlassdoorApplier] Submit action did not produce verified success.")
                            return "failed"

                    self.form.fill_personal_info()
                    self.form.answer_screening_questions()
                    self.form.upload_resume_if_needed()

                    advanced = self.form.click_continue()
                    if not advanced:
                        print_lg(f"[GlassdoorApplier] Could not advance beyond step {step_num}.")
                        break

            return "failed"
        except Exception as e:
            print_lg(f"[GlassdoorApplier] Exception during apply: {e}")
            return "failed"
        finally:
            # GUARANTEED CLEANUP: Close application tab and secondary job tab, restore focus to main search window
            fin_handles = _safe_handles(self.driver)
            if app_tab and fin_handles and app_tab in fin_handles:
                try:
                    self.driver.switch_to.window(app_tab)
                    self.driver.close()
                except Exception:
                    pass
            fin_handles = _safe_handles(self.driver)
            if job_tab and fin_handles and job_tab in fin_handles and job_tab != main_window:
                try:
                    self.driver.switch_to.window(job_tab)
                    self.driver.close()
                except Exception:
                    pass
            fin_handles = _safe_handles(self.driver)
            if main_window and fin_handles and main_window in fin_handles:
                for h in fin_handles:
                    if h != main_window:
                        try:
                            self.driver.switch_to.window(h)
                            self.driver.close()
                        except Exception:
                            pass
                try:
                    self.driver.switch_to.window(main_window)
                    human_delay(0.5, 1.0)
                    curr_fin_url = (self.driver.current_url or "").lower()
                    if search_target_url and ("/job-listing/" in curr_fin_url or "/index.htm" in curr_fin_url):
                        print_lg(f"[GlassdoorApplier] Search window restored from {curr_fin_url} to search URL.")
                        self.driver.get(search_target_url)
                        human_delay(1.5, 2.5)
                except Exception:
                    pass
