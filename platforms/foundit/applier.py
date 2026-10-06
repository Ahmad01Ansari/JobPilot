'''
Foundit Application Flow Detector & Applier Engine
Determines application flow type upon inspecting/clicking Apply.
Classifies flows into: DIRECT, QUESTIONNAIRE, EXTERNAL, ALREADY_APPLIED, LOGIN_REQUIRED, CAPTCHA, or UNKNOWN.
Executes application and records lifecycle transitions in the unified ApplicationTracker and database.
'''

import time
import random
from typing import Literal, Optional, Tuple, Any, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from modules.models import Job
from modules.tracker import ApplicationTracker
from platforms.foundit.selectors import (
    PRIMARY_APPLY_BUTTON_SELECTORS,
    EXTERNAL_APPLY_INDICATORS,
    APPLIED_BUTTON_TEXTS,
    CAPTCHA_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
)
from platforms.foundit.submitter import FounditSubmitter
from platforms.foundit.form import FounditForm
from modules.helpers import print_lg
from modules.captcha_detector import CaptchaDetector
from modules.human_behavior import human_delay, human_click


FlowType = Literal[
    "DIRECT",
    "QUESTIONNAIRE",
    "EXTERNAL",
    "ALREADY_APPLIED",
    "LOGIN_REQUIRED",
    "CAPTCHA",
    "MANUAL_REQUIRED",
    "UNKNOWN",
]


class FounditFlowDetector:
    """Classifies the application modal/flow on Foundit."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def detect_flow(self, button_elem: Optional[WebElement] = None) -> FlowType:
        """Inspects apply button text, attributes, and page state to classify flow."""
        if not self.driver:
            return "UNKNOWN"

        # 1. Check CAPTCHA
        for sel in CAPTCHA_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return "CAPTCHA"
            except Exception:
                pass

        try:
            curr_url = (getattr(self.driver, "current_url", "") or "").lower()
            if "challenge" in curr_url or "captcha" in curr_url:
                return "CAPTCHA"
        except Exception:
            pass

        if not button_elem:
            for sel in PRIMARY_APPLY_BUTTON_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                    for el in elems:
                        if el.is_displayed():
                            button_elem = el
                            break
                    if button_elem:
                        break
                except Exception:
                    continue

        if not button_elem:
            return "UNKNOWN"

        text = (button_elem.text or "").strip().lower()
        cls = (button_elem.get_attribute("class") or "").lower()
        href = (button_elem.get_attribute("href") or "").lower()
        target = (button_elem.get_attribute("target") or "").lower()
        combined = f"{text} {cls} {href}"

        # 2. Check already applied
        if any(t in combined for t in APPLIED_BUTTON_TEXTS):
            return "ALREADY_APPLIED"

        # 3. Check external link
        if target == "_blank" or any(ext in combined for ext in EXTERNAL_APPLY_INDICATORS):
            return "EXTERNAL"
        if href and "foundit.in" not in href and (href.startswith("http://") or href.startswith("https://")):
            return "EXTERNAL"
        if "quick apply" not in text and "quickapply" not in cls and ("apply now" in text or "external" in text):
            return "EXTERNAL"

        # 4. Check if a questionnaire modal is already open
        modal_elems = self.driver.find_elements(By.CSS_SELECTOR, "div[class*='modal'] form, div[role='dialog'] form")
        if any(m.is_displayed() for m in modal_elems):
            return "QUESTIONNAIRE"

        return "DIRECT"


class FounditApplier:
    """Coordinates flow detection, questionnaire answering, submission, and state tracking on Foundit."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        automation_bridge: Optional[Any] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.automation_bridge = automation_bridge
        self.user_id = user_id
        self.detector = FounditFlowDetector(browser=self.browser)
        self.submitter = FounditSubmitter(browser=self.browser, tracker=self.tracker)
        self.form_handler = FounditForm(browser=self.browser, user_id=user_id)

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def close_extra_tabs(self, keep_handle: Optional[str] = None) -> None:
        """Closes all browser windows/tabs except keep_handle (e.g. 'Applied Success' tabs)."""
        if not self.driver:
            return
        try:
            target = keep_handle
            handles = list(self.driver.window_handles)
            if not target:
                target = handles[0] if handles else None
            if not target:
                return

            for h in handles:
                if h != target:
                    try:
                        self.driver.switch_to.window(h)
                        time.sleep(random.uniform(0.15, 0.35))
                        self.driver.close()
                    except Exception:
                        pass
            self.driver.switch_to.window(target)
        except Exception as e:
            print_lg(f"[FounditApplier] Notice closing extra tabs: {e}")

    def apply(
        self,
        job: Job,
        card_elem: Optional[WebElement] = None,
        qualification_engine: Optional[Any] = None,
        pause_before_submit: bool = False,
        stop_check: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Applies to a single job posting, tracking state transitions across new tab or modal."""
        if not self.driver:
            return {"status": "FAILED", "error": "Browser not initialized"}

        # Deduplication check in tracker
        if self.tracker.is_applied(job.job_id, platform="foundit"):
            print_lg(f"[FounditApplier] Job '{job.job_id}' is already applied according to tracker. Skipping.")
            return {"status": "ALREADY_APPLIED", "job_id": job.job_id}

        main_window = self.driver.current_window_handle
        initial_windows = set(self.driver.window_handles)

        # 1. Check if already marked as Applied on the card element
        if card_elem:
            try:
                card_applied = card_elem.find_elements(
                    By.XPATH,
                    ".//button[contains(normalize-space(), 'Applied') or contains(normalize-space(), 'Already Applied')]"
                )
                if any(b.is_displayed() and any(t in (b.text or "").lower() for t in APPLIED_BUTTON_TEXTS) for b in card_applied):
                    print_lg(f"[FounditApplier] Job '{job.title}' is already marked as Applied on card. Skipping.")
                    self.tracker.record_skipped(job, reason="ALREADY_APPLIED_ON_PORTAL")
                    return {"status": "ALREADY_APPLIED", "job_id": job.job_id}
            except Exception:
                pass

        # 2. Locate apply button (on card or in details pane)
        btn = None
        if card_elem:
            try:
                card_btns = card_elem.find_elements(
                    By.XPATH,
                    ".//button[contains(normalize-space(), 'Quick Apply') or contains(normalize-space(), 'Apply Now') or contains(normalize-space(), 'Apply')]"
                )
                for b in card_btns:
                    if b.is_displayed():
                        btn = b
                        break
            except Exception:
                pass

        if not btn:
            btn = self.submitter.find_apply_button()

        flow = self.detector.detect_flow(btn)
        print_lg(f"[FounditApplier] Detected pre-click flow: {flow} for '{job.title}'")

        if flow == "ALREADY_APPLIED":
            self.tracker.record_skipped(job, reason="ALREADY_APPLIED_ON_PORTAL")
            return {"status": "ALREADY_APPLIED", "job_id": job.job_id}

        if flow == "CAPTCHA":
            print_lg(f"[FounditApplier] CAPTCHA detected during apply for '{job.title}'. Cooperatively awaiting resolution...")
            detector = CaptchaDetector(platform="foundit", automation_bridge=self.automation_bridge)
            solved = detector.handle_captcha(
                self.driver,
                platform="foundit",
                job_title=job.title,
                company=job.company,
                timeout=60,
                automation_bridge=self.automation_bridge,
            )
            if solved:
                print_lg(f"[FounditApplier] CAPTCHA resolved for '{job.title}'! Re-detecting apply flow...")
                flow = self.detect_flow(btn)
                if flow == "CAPTCHA":
                    self.tracker.record_manual_required(job, reason="CAPTCHA_DETECTED")
                    return {"status": "MANUAL_REQUIRED", "reason": "CAPTCHA"}
            else:
                self.tracker.record_manual_required(job, reason="CAPTCHA_DETECTED")
                return {"status": "MANUAL_REQUIRED", "reason": "CAPTCHA"}

        # 3. Check manual approval pause before clicking
        if pause_before_submit:
            print_lg("[FounditApplier] PAUSE BEFORE SUBMIT: Manual approval enabled. Halting before click.")
            self.tracker.record_manual_required(job, reason="PAUSE_BEFORE_SUBMIT")
            return {"status": "MANUAL_REQUIRED", "job_id": job.job_id}

        # 3.1 Handle External Company Portal flow without false submission
        if flow == "EXTERNAL" or getattr(job, "application_method", "") == "COMPANY_PORTAL":
            print_lg(f"[FounditApplier] External job application detected for '{job.title}'. Extracting external URL...")
            ext_url = self.extract_external_apply_url(btn or card_elem)
            effective_url = ext_url or job.source_url
            job.application_url = effective_url
            job.application_method = "COMPANY_PORTAL"
            job.apply_type = "EXTERNAL"
            self.tracker.record_external(job, external_url=effective_url)
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
                        application_method="COMPANY_PORTAL",
                        application_url=effective_url,
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
            return {"status": "EXTERNAL", "job_id": job.job_id, "external_url": effective_url}

        # 4. Click the apply button (or card) with dynamic human pause
        target_clickable = btn or card_elem
        if target_clickable:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_clickable)
                time.sleep(random.uniform(0.4, 0.8))
                try:
                    target_clickable.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", target_clickable)
            except Exception as e:
                print_lg(f"[FounditApplier] Error clicking apply button: {e}")

        # Dynamic delay (1.5 - 2.5s) for Foundit to register click, show success on page, and trigger popup
        time.sleep(random.uniform(1.5, 2.5))

        # Check if already successfully submitted via Quick Apply banner or card state
        if self.submitter.verify_submission(timeout=4, card_elem=card_elem):
            # Dynamic wait (1-2s) for success page to pop up, then close any extra tabs
            time.sleep(random.uniform(1.0, 1.8))
            self.close_extra_tabs(keep_handle=main_window)
            self.tracker.record_submitted(job)
            if self.automation_bridge:
                try:
                    from app.services.automation_events import ApplicationSubmittedEvent, JobDiscoveredEvent
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
                    self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                        platform="foundit",
                        title=job.title,
                        company=job.company,
                        external_job_id=job.job_id,
                        source_url=job.source_url,
                    ))
                except Exception:
                    pass
            print_lg(f"[FounditApplier] QUICK APPLY SUCCESS: Successfully submitted '{job.title}' at '{job.company}'")
            return {"status": "SUBMITTED", "job_id": job.job_id}

        # Check if a new tab opened or modal appeared
        current_windows = self.driver.window_handles
        new_windows = [w for w in current_windows if w not in initial_windows]

        # =====================================================================
        # CASE A: A new tab / window opened
        # =====================================================================
        if new_windows:
            new_tab = new_windows[-1]
            print_lg(f"[FounditApplier] Switched to new tab: {new_tab}")
            self.driver.switch_to.window(new_tab)
            time.sleep(random.uniform(1.2, 2.0))

            new_tab_url = (self.driver.current_url or "").strip().lower() if isinstance(self.driver.current_url, str) else ""
            new_tab_title = (self.driver.title or "").strip().lower() if isinstance(self.driver.title, str) else ""
            print_lg(f"[FounditApplier] New tab URL: {new_tab_url} | Title: {new_tab_title}")

            # Check if this new tab is an "Applied Success" confirmation page
            if (
                (new_tab_title and any(ind in new_tab_title for ind in ["applied success", "success"]))
                or (new_tab_url and any(ind in new_tab_url for ind in ["applied success", "/success"]))
            ):
                print_lg(f"[FounditApplier] Detected 'Applied Success' page tab ('{new_tab_title}'). Closing tab and confirming submission.")
                try:
                    self.driver.close()
                except Exception:
                    pass
                self.driver.switch_to.window(main_window)
                self.close_extra_tabs(keep_handle=main_window)
                self.tracker.record_submitted(job)
                if self.automation_bridge:
                    try:
                        from app.services.automation_events import ApplicationSubmittedEvent, JobDiscoveredEvent
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
                        ))
                        self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                            platform="foundit",
                            title=job.title,
                            company=job.company,
                            external_job_id=job.job_id,
                            source_url=job.source_url,
                        ))
                    except Exception:
                        pass
                print_lg(f"[FounditApplier] QUICK APPLY SUCCESS: Successfully submitted '{job.title}' at '{job.company}'")
                return {"status": "SUBMITTED", "job_id": job.job_id}

            # 1. Extract full job details (JD, experience, salary) from new tab
            try:
                from platforms.foundit.parser import FounditJobParser
                parser = FounditJobParser(self.browser)
                tab_jd = parser.extract_job_description()
            except Exception:
                tab_jd = ""

            if not tab_jd or len(tab_jd) < 50:
                try:
                    tab_jd = self.driver.find_element(By.TAG_NAME, "body").text
                except Exception:
                    tab_jd = ""

            if tab_jd:
                job.description = tab_jd
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

            # 2. Perform Qualification Validation if engine is provided
            if qualification_engine:
                if hasattr(qualification_engine, "qualify_job_post_click"):
                    qual_res = qualification_engine.qualify_job_post_click(job)
                elif hasattr(qualification_engine, "qualify"):
                    qual_res = qualification_engine.qualify(job)
                elif hasattr(qualification_engine, "qualify_description"):
                    qual_res = qualification_engine.qualify_description(
                        description=job.description,
                        required_experience_min=job.required_experience_min,
                        title=job.title,
                    )
                else:
                    qual_res = None

                if qual_res is not None and not qual_res:
                    print_lg(f"[FounditApplier] SKIP: Job '{job.title}' not qualified on full JD: {qual_res.reason}")
                    self.tracker.record_skipped(job, reason=qual_res.reason or "STAGE_2_FILTER")
                    try:
                        self.driver.close()
                    except Exception:
                        pass
                    self.driver.switch_to.window(main_window)
                    return {"status": "SKIPPED", "job_id": job.job_id, "reason": qual_res.reason}

            # 3. Check if External Employer / Third-Party Website
            is_external = (
                "foundit.in" not in new_tab_url.lower()
                or any(ind in new_tab_url.lower() for ind in ["linkedin.com", "indeed.com", "myworkday", "greenhouse.io", "lever.co", "smartrecruiters", "oraclecloud"])
            )

            if is_external:
                print_lg(f"[FounditApplier] External employer website detected: {new_tab_url}")
                job.source_url = new_tab_url
                self.tracker.record_external(job, external_url=new_tab_url)
                if self.automation_bridge:
                    try:
                        from app.services.automation_events import JobDiscoveredEvent
                        self.automation_bridge.handle_job_discovered(JobDiscoveredEvent(
                            platform="foundit",
                            external_job_id=job.job_id,
                            title=job.title,
                            company=job.company,
                            location=job.location,
                            url=new_tab_url,
                            application_method="COMPANY_PORTAL",
                            application_url=new_tab_url,
                            description=job.description,
                        ))
                    except Exception:
                        pass
                try:
                    self.driver.close()
                except Exception:
                    pass
                self.driver.switch_to.window(main_window)
                return {"status": "EXTERNAL", "job_id": job.job_id, "external_url": new_tab_url}

            # 4. Native Foundit Apply on New Tab
            self.tracker.record_applying(job)

            # Check for questionnaire / form fields
            answered, failed = self.form_handler.fill_all_visible_fields(job_context=job.description)
            if answered > 0:
                print_lg(f"[FounditApplier] Form handled on new tab: {answered} answered, {failed} failed.")

            # Submit application
            success, outcome = self.submitter.submit(job, pause_before_submit=pause_before_submit)

            # Close new tab and return to main search window
            try:
                self.driver.close()
            except Exception:
                pass
            self.driver.switch_to.window(main_window)

            if outcome == "SUBMITTED":
                self.tracker.record_submitted(job)
                if self.automation_bridge:
                    try:
                        from app.services.automation_events import ApplicationSubmittedEvent, JobDiscoveredEvent
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
                        self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                            platform="foundit",
                            title=job.title,
                            company=job.company,
                            external_job_id=job.job_id,
                            source_url=job.source_url,
                        ))
                    except Exception:
                        pass
                return {"status": "SUBMITTED", "job_id": job.job_id}
            elif outcome == "MANUAL_REQUIRED":
                self.tracker.record_manual_required(job, reason="PAUSE_BEFORE_SUBMIT")
                return {"status": "MANUAL_REQUIRED", "job_id": job.job_id}
            elif outcome == "UNKNOWN":
                self.tracker.record_unknown(job, failure_reason="UNCONFIRMED_SUBMISSION")
                return {"status": "UNKNOWN", "job_id": job.job_id}
            else:
                self.tracker.record_failed(job, failure_reason=outcome)
                return {"status": "FAILED", "job_id": job.job_id, "error": outcome}

        # =====================================================================
        # CASE B: Same window (Quick Apply or Modal on SRP)
        # =====================================================================
        if flow == "EXTERNAL":
            ext_url = btn.get_attribute("href") if btn else None
            self.tracker.record_external(job, external_url=ext_url)
            print_lg(f"[FounditApplier] Recorded EXTERNAL job: {ext_url or job.source_url}")
            return {"status": "EXTERNAL", "job_id": job.job_id, "external_url": ext_url}

        # Check questionnaire modal or form on SRP
        modal_open = any(
            m.is_displayed()
            for m in self.driver.find_elements(By.CSS_SELECTOR, "div[class*='modal'] form, div[role='dialog'] form")
        )

        # Record APPLYING state
        self.tracker.record_applying(job)

        if modal_open or flow == "QUESTIONNAIRE":
            print_lg(f"[FounditApplier] Answering screening questions for '{job.title}'...")
            answered, failed = self.form_handler.fill_all_visible_fields(job_context=job.description)
            print_lg(f"[FounditApplier] Screening form: {answered} answered, {failed} failed.")

        success, outcome = self.submitter.submit(job, pause_before_submit=pause_before_submit, card_elem=card_elem)

        # Dynamic wait and clean up extra tabs (e.g. Applied Success tab)
        time.sleep(random.uniform(1.2, 2.0))
        self.close_extra_tabs(keep_handle=main_window)

        if outcome == "SUBMITTED":
            self.tracker.record_submitted(job)
            if self.automation_bridge:
                try:
                    from app.services.automation_events import ApplicationSubmittedEvent, JobDiscoveredEvent
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
                    self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                        platform="foundit",
                        title=job.title,
                        company=job.company,
                        external_job_id=job.job_id,
                        source_url=job.source_url,
                    ))
                except Exception:
                    pass
            return {"status": "SUBMITTED", "job_id": job.job_id}
        elif outcome == "MANUAL_REQUIRED":
            self.tracker.record_manual_required(job, reason="PAUSE_BEFORE_SUBMIT")
            return {"status": "MANUAL_REQUIRED", "job_id": job.job_id}
        elif outcome == "UNKNOWN":
            self.tracker.record_unknown(job, failure_reason="UNCONFIRMED_SUBMISSION")
            return {"status": "UNKNOWN", "job_id": job.job_id}
        else:
            self.tracker.record_failed(job, failure_reason=outcome)
            return {"status": "FAILED", "job_id": job.job_id, "error": outcome}

    def extract_external_apply_url(self, apply_btn: WebElement) -> Optional[str]:
        """
        Extracts the destination external application URL from an 'Apply Now' button
        via attributes (href, data-url, redirect query) or by safely clicking and capturing the opened tab.
        """
        if not self.driver or not apply_btn:
            return None

        try:
            job_window = self.driver.current_window_handle
        except Exception:
            job_window = None

        # 1. Attribute Inspection
        try:
            raw_href = apply_btn.get_attribute("href")
            btn_href = raw_href.strip() if isinstance(raw_href, str) else ""
            if not btn_href:
                try:
                    a_elem = apply_btn.find_element(By.XPATH, "./ancestor-or-self::a")
                    a_raw = a_elem.get_attribute("href")
                    btn_href = a_raw.strip() if isinstance(a_raw, str) else ""
                except Exception:
                    pass

            if btn_href and btn_href.startswith("http") and "foundit.in" not in btn_href.lower():
                return btn_href

            # Check for redirect parameter in foundit link
            if btn_href and "foundit.in" in btn_href.lower():
                from urllib.parse import urlparse, parse_qs, unquote
                parsed = urlparse(btn_href)
                query_params = parse_qs(parsed.query)
                for key in [
                    "url", "dest", "destination", "redirect", "redirectUrl", "redirect_url",
                    "target", "targetUrl", "target_url", "link", "jobUrl", "job_url",
                    "applyUrl", "apply_url", "applyLink", "externalUrl", "external_url"
                ]:
                    if key in query_params and query_params[key]:
                        candidate = unquote(query_params[key][0])
                        if candidate.startswith("http") and "foundit.in" not in candidate.lower():
                            return candidate

            # Check data attributes
            for attr in [
                "data-href", "data-url", "data-redirect-url", "data-redirect",
                "data-external-url", "data-target", "data-apply-url", "data-job-url"
            ]:
                val = apply_btn.get_attribute(attr)
                if isinstance(val, str) and val.strip().startswith("http") and "foundit.in" not in val.lower():
                    return val.strip()

            # Check onclick attribute for URL
            onclick = apply_btn.get_attribute("onclick")
            if isinstance(onclick, str) and onclick.strip():
                import re as _re
                m = _re.search(r"https?://[^\s'\"\\)]+", onclick)
                if m and "foundit.in" not in m.group(0).lower():
                    return m.group(0)
        except Exception as e:
            print_lg(f"[FounditApplier] Notice reading button attributes: {e}")

        # 2. Click and capture opened tab / redirect
        try:
            initial_windows = list(self.driver.window_handles)
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                time.sleep(0.3)
                try:
                    apply_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", apply_btn)
            except Exception as e:
                print_lg(f"[FounditApplier] Notice clicking apply button for URL extraction: {e}")

            # Wait for opened window
            new_tab = None
            for _ in range(8):
                time.sleep(0.5)
                current_handles = self.driver.window_handles
                diff = [w for w in current_handles if w not in initial_windows]
                if diff:
                    new_tab = diff[-1]
                    break

            if new_tab:
                ext_url = ""
                try:
                    self.driver.switch_to.window(new_tab)
                    for _ in range(6):
                        time.sleep(0.5)
                        curr = (self.driver.current_url or "").strip()
                        if curr and curr != "about:blank" and "foundit.in" not in curr.lower():
                            ext_url = curr
                            break
                    if not ext_url:
                        ext_url = (self.driver.current_url or "").strip()
                finally:
                    try:
                        self.driver.close()
                    except Exception:
                        pass
                    if job_window:
                        self.driver.switch_to.window(job_window)

                if ext_url and ext_url != "about:blank" and "foundit.in" not in ext_url.lower():
                    return ext_url

            # If no new tab opened, check if current tab navigated
            curr = (self.driver.current_url or "").strip()
            if curr and "foundit.in" not in curr.lower():
                try:
                    self.driver.back()
                    time.sleep(1.0)
                except Exception:
                    pass
                return curr

        except Exception as e:
            print_lg(f"[FounditApplier] Error during external URL click extraction: {e}")
            if job_window:
                try:
                    self.driver.switch_to.window(job_window)
                except Exception:
                    pass

        return None

    def apply_on_job_page(
        self,
        job: Job,
        pause_before_submit: bool = False,
        stop_check: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Applies to a job directly from its dedicated details page/tab."""
        if not self.driver:
            return {"status": "FAILED", "error": "Browser not initialized"}

        # Deduplication check in tracker
        if self.tracker.is_applied(job.job_id, platform="foundit"):
            print_lg(f"[FounditApplier] Job '{job.job_id}' is already applied according to tracker. Skipping.")
            return {"status": "ALREADY_APPLIED", "job_id": job.job_id}

        # 1. Indicators that the candidate has already applied on their profile (Screenshot 2)
        applied_indicators = [
            "//*[self::h1 or self::h2 or self::h3 or self::h4 or self::div or self::span][normalize-space()='Your application status']",
            "//*[self::button or self::span or self::div or self::p][starts-with(normalize-space(), 'Applied') or normalize-space()='Already Applied']",
            "//div[contains(@class, 'application-status') or contains(@class, 'applied-status')]",
        ]

        # 2. Check for manual approval pause
        if pause_before_submit:
            print_lg("[FounditApplier] PAUSE BEFORE SUBMIT: Manual approval enabled. Halting before click.")
            self.tracker.record_manual_required(job, reason="PAUSE_BEFORE_SUBMIT")
            return {"status": "MANUAL_REQUIRED", "job_id": job.job_id}

        # 3. Locate Quick Apply / Apply button or Already Applied status (allow up to 6.0s for React to hydrate)
        apply_btn = None
        start_wait = time.time()
        while time.time() - start_wait < 6.0:
            # Check already applied on page first during hydration
            for sel in applied_indicators:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    for el in elems:
                        if el.is_displayed():
                            txt = (el.text or "").strip()
                            if "applicants have applied" in txt.lower() or "applicant have applied" in txt.lower():
                                continue
                            if txt.lower() == "applied" or txt.lower().startswith("applied") or any(ind in txt.lower() for ind in ["your application status", "application sent", "already applied"]):
                                print_lg(f"[FounditApplier] Job '{job.title}' is already marked as Applied on page ({txt[:60]}). Skipping.")
                                self.tracker.record_skipped(job, reason="ALREADY_APPLIED_ON_PORTAL")
                                return {"status": "ALREADY_APPLIED", "job_id": job.job_id}
                except Exception:
                    pass

            for sel in [
                "//*[self::button or self::a or @role='button'][contains(normalize-space(), 'Quick Apply')]",
                "//*[self::button or self::a or @role='button'][contains(normalize-space(), 'Apply Now')]",
                "//*[self::button or self::a or @role='button'][contains(normalize-space(), 'Apply') and not(contains(normalize-space(), 'Applied'))]",
                "button#applyNowBtn",
                "a#applyNowBtn",
                "#applyNowBtn",
                "a[href*='/redirect']",
                "button.applyBtnCont",
                "button[class*='quickApply']",
                "button[class*='applyNowBtn']",
                "div.applyBtnCont button",
                "div.applyBtnCont a",
            ]:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                    for b in elems:
                        if b.is_displayed():
                            apply_btn = b
                            break
                    if apply_btn:
                        break
                except Exception:
                    continue

            if apply_btn:
                break
            time.sleep(0.8)

        if not apply_btn:
            # Final check for already applied before reporting failure
            for sel in applied_indicators:
                try:
                    elems = self.driver.find_elements(By.XPATH, sel)
                    if any(e.is_displayed() for e in elems):
                        print_lg(f"[FounditApplier] Job '{job.title}' is already marked as Applied on page. Skipping.")
                        self.tracker.record_skipped(job, reason="ALREADY_APPLIED_ON_PORTAL")
                        return {"status": "ALREADY_APPLIED", "job_id": job.job_id}
                except Exception:
                    pass

            print_lg(f"[FounditApplier] No active Apply button found on page for '{job.title}'.")
            return {"status": "FAILED", "job_id": job.job_id, "error": "APPLY_BUTTON_NOT_FOUND"}

        # Check if external link
        btn_text = (apply_btn.text or apply_btn.get_attribute("innerText") or "").strip().lower()
        btn_html = (apply_btn.get_attribute("outerHTML") or "").lower()
        btn_href = (apply_btn.get_attribute("href") or "").strip()
        if not btn_href:
            try:
                a_tag = apply_btn.find_element(By.XPATH, "./ancestor-or-self::a")
                btn_href = (a_tag.get_attribute("href") or "").strip()
            except Exception:
                pass

        is_quick_apply = "quick apply" in btn_text or "quickapply" in btn_html
        is_external = (
            not is_quick_apply
            and (
                getattr(job, "application_method", "") == "COMPANY_PORTAL"
                or "apply now" in btn_text
                or "external" in btn_text
                or "company site" in btn_text
                or "company website" in btn_text
                or (btn_href and "foundit.in" not in btn_href.lower())
                or 'target="_blank"' in btn_html
                or "svg" in btn_html
            )
        )

        if is_external:
            print_lg(f"[FounditApplier] External job application detected ('{btn_text}') for '{job.title}'. Extracting external URL...")
            ext_url = self.extract_external_apply_url(apply_btn)
            effective_url = ext_url or job.source_url
            print_lg(f"[FounditApplier] External company application link captured: {effective_url}")
            job.application_url = effective_url
            job.application_method = "COMPANY_PORTAL"
            job.apply_type = "EXTERNAL"
            self.tracker.record_external(job, external_url=effective_url)
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
                        application_method="COMPANY_PORTAL",
                        application_url=effective_url,
                        description=job.description,
                        experience_text=job.experience_text,
                        salary_text=job.salary_text,
                        salary_min=job.salary_min,
                        salary_max=job.salary_max,
                        required_experience_min=job.required_experience_min,
                        required_experience_max=job.required_experience_max,
                        work_style=job.work_style,
                    ))
                except Exception as e:
                    print_lg(f"[FounditApplier] Notice syncing external job to bridge: {e}")
            return {"status": "EXTERNAL", "job_id": job.job_id, "external_url": effective_url}

        # 4. Click the Apply button
        self.tracker.record_applying(job)
        print_lg(f"[FounditApplier] Clicking 'Quick Apply' for '{job.title}' at '{job.company}'...")
        current_job_window = self.driver.current_window_handle
        initial_handles = set(self.driver.window_handles)
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
            time.sleep(random.uniform(0.4, 0.8))
            try:
                apply_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", apply_btn)
        except Exception as e:
            print_lg(f"[FounditApplier] Error clicking apply button: {e}")

        # Dynamic delay (1.5 - 2.5s) for click to register, banner to show, and success tab to open
        time.sleep(random.uniform(1.5, 2.5))

        # Check if an Applied Success popup tab opened after click
        for w in list(self.driver.window_handles):
            if w not in initial_handles:
                try:
                    self.driver.switch_to.window(w)
                    w_title = (self.driver.title or "").strip().lower() if isinstance(self.driver.title, str) else ""
                    w_url = (self.driver.current_url or "").strip().lower() if isinstance(self.driver.current_url, str) else ""
                    if (w_title and any(ind in w_title for ind in ["applied success", "success"])) or (w_url and any(ind in w_url for ind in ["applied success", "/success"])):
                        print_lg(f"[FounditApplier] Closing 'Applied Success' tab: {w_title}")
                        self.driver.close()
                except Exception:
                    pass
        self.driver.switch_to.window(current_job_window)

        # 5. Check if Screen Questionnaire drawer appeared (Screenshot 1)
        if self.form_handler.is_questionnaire_open():
            print_lg(f"[FounditApplier] Screen Questionnaire drawer opened for '{job.title}'. Answering questions...")
            answered, failed = self.form_handler.fill_all_visible_fields(job_context=job.description)
            print_lg(f"[FounditApplier] Screening form: {answered} answered, {failed} failed. Submitting...")
            self.form_handler.submit_questionnaire()
            time.sleep(random.uniform(1.5, 2.5))
            # Again check for any Applied Success popup tab
            for w in list(self.driver.window_handles):
                if w not in initial_handles:
                    try:
                        self.driver.switch_to.window(w)
                        w_title = (self.driver.title or "").strip().lower() if isinstance(self.driver.title, str) else ""
                        w_url = (self.driver.current_url or "").strip().lower() if isinstance(self.driver.current_url, str) else ""
                        if (w_title and any(ind in w_title for ind in ["applied success", "success"])) or (w_url and any(ind in w_url for ind in ["applied success", "/success"])):
                            print_lg(f"[FounditApplier] Closing 'Applied Success' tab: {w_title}")
                            self.driver.close()
                    except Exception:
                        pass
            self.driver.switch_to.window(current_job_window)

        # 6. Verify submission confirmation
        if self.submitter.verify_submission(timeout=5):
            # Dynamic wait and clean up any popup tabs
            time.sleep(random.uniform(1.0, 1.8))
            for w in list(self.driver.window_handles):
                if w != current_job_window:
                    try:
                        self.driver.switch_to.window(w)
                        w_title = (self.driver.title or "").strip().lower() if isinstance(self.driver.title, str) else ""
                        w_url = (self.driver.current_url or "").strip().lower() if isinstance(self.driver.current_url, str) else ""
                        if (w_title and any(ind in w_title for ind in ["applied success", "success"])) or (w_url and any(ind in w_url for ind in ["applied success", "/success"])):
                            self.driver.close()
                    except Exception:
                        pass
            self.driver.switch_to.window(current_job_window)
            self.tracker.record_submitted(job)
            if self.automation_bridge:
                try:
                    from app.services.automation_events import ApplicationSubmittedEvent, JobDiscoveredEvent
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
                    self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                        platform="foundit",
                        title=job.title,
                        company=job.company,
                        external_job_id=job.job_id,
                        source_url=job.source_url,
                    ))
                except Exception:
                    pass
            print_lg(f"[FounditApplier] APPLICATION SUCCESSFUL: Successfully submitted '{job.title}' at '{job.company}'")
            return {"status": "SUBMITTED", "job_id": job.job_id}

        # Check if button changed to Applied or Your application status appeared
        try:
            status_elems = self.driver.find_elements(
                By.XPATH,
                "//*[contains(normalize-space(), 'Your application status') or contains(normalize-space(), 'Applied')]"
            )
            if any(e.is_displayed() for e in status_elems):
                self.tracker.record_submitted(job)
                if self.automation_bridge:
                    try:
                        from app.services.automation_events import ApplicationSubmittedEvent
                        self.automation_bridge.handle_application_submitted(ApplicationSubmittedEvent(
                            platform="foundit",
                            title=job.title,
                            company=job.company,
                            external_job_id=job.job_id,
                            source_url=job.source_url,
                        ))
                    except Exception:
                        pass
                print_lg(f"[FounditApplier] APPLICATION SUCCESSFUL (Status verified): '{job.title}' at '{job.company}'")
                return {"status": "SUBMITTED", "job_id": job.job_id}
        except Exception:
            pass

        self.tracker.record_unknown(job, failure_reason="UNCONFIRMED_SUBMISSION")
        return {"status": "UNKNOWN", "job_id": job.job_id}
