'''
Naukri Application Flow Detector & Applier Engine
Determines application modal type upon clicking Apply.
Classifies flows into: DIRECT, QUESTIONNAIRE, EXTERNAL, LOGIN_REQUIRED, CAPTCHA, PROFILE_INCOMPLETE, or UNKNOWN.
Enforces the safety gate: NO automatic submission is performed in Phase 8.
'''

from typing import Literal, Optional, Tuple, Any, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from platforms.naukri.selectors import (
    APPLY_BUTTON_SELECTORS,
    EXTERNAL_APPLY_TEXTS,
    QUESTIONNAIRE_MODAL_SELECTORS,
    DIRECT_APPLY_SUCCESS_SELECTORS,
    PROFILE_INCOMPLETE_SELECTORS,
    CAPTCHA_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    MODAL_CLOSE_BUTTONS,
)
from modules.helpers import print_lg
from platforms.naukri.diagnostics import capture_naukri_diagnostics
from modules.captcha_detector import CaptchaDetector
from modules.human_behavior import human_delay, human_click

FlowType = Literal[
    "DIRECT",
    "QUESTIONNAIRE",
    "EXTERNAL",
    "LOGIN_REQUIRED",
    "CAPTCHA",
    "PROFILE_INCOMPLETE",
    "ALREADY_APPLIED",
    "RATE_LIMITED",
    "APPLY_UNAVAILABLE",
    "UNKNOWN",
]


class NaukriFlowDetector:
    """Classifies the application modal/flow on Naukri."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def is_already_applied(self) -> bool:
        """Checks if the current job page indicates the user has already applied."""
        if not self.driver:
            return False

        from platforms.naukri.selectors import ALREADY_APPLIED_SELECTORS, ALREADY_APPLIED_XPATHS

        # 1. Check CSS selectors
        for sel in ALREADY_APPLIED_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass

        # 2. Check XPath selectors
        for xp in ALREADY_APPLIED_XPATHS:
            try:
                elems = self.driver.find_elements(By.XPATH, xp)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass

        return False

    def detect_apply_button_type(self, button_elem: Optional[WebElement] = None) -> FlowType:
        """Inspects apply button text, attributes, innerText, and DOM context before clicking."""
        if not button_elem:
            button_elem = self.find_apply_button()
        if not button_elem:
            return "UNKNOWN"

        from platforms.naukri.selectors import EXTERNAL_APPLY_TEXTS, EXTERNAL_APPLY_XPATHS

        text = (button_elem.text or "").strip().lower()
        inner_text = (button_elem.get_attribute("innerText") or "").strip().lower()
        text_content = (button_elem.get_attribute("textContent") or "").strip().lower()
        title = (button_elem.get_attribute("title") or "").strip().lower()
        aria = (button_elem.get_attribute("aria-label") or "").strip().lower()
        href = (button_elem.get_attribute("href") or "").strip().lower()
        btn_class = (button_elem.get_attribute("class") or "").strip().lower()
        btn_id = (button_elem.get_attribute("id") or "").strip().lower()
        combined = f"{btn_id} {text} {inner_text} {text_content} {title} {aria} {btn_class}"

        if "company-site" in btn_id or "company-site" in btn_class or "company-site" in combined:
            return "EXTERNAL"

        for ext_text in EXTERNAL_APPLY_TEXTS:
            if ext_text in combined:
                return "EXTERNAL"

        if href and href.startswith("http") and "naukri.com" not in href.lower():
            return "EXTERNAL"

        # Check if disabled or already applied before clicking
        disabled_val = button_elem.get_attribute("disabled")
        aria_disabled = (button_elem.get_attribute("aria-disabled") or "").strip().lower()
        is_disabled = (
            disabled_val in (True, "true", "disabled")
            or aria_disabled in ("true", "1")
            or ("disabled" in btn_class.split())
        )
        if is_disabled:
            if any(w in combined for w in ["applied", "already"]):
                return "ALREADY_APPLIED"
            return "APPLY_UNAVAILABLE"

        # Check if parent or container mentions external apply
        try:
            parent = button_elem.find_element(By.XPATH, "./..")
            p_text = (parent.get_attribute("innerText") or "").strip().lower()
            for ext_text in EXTERNAL_APPLY_TEXTS:
                if ext_text in p_text:
                    return "EXTERNAL"
        except Exception:
            pass

        # Page-level external apply indicator check
        if self.driver:
            for xp in EXTERNAL_APPLY_XPATHS:
                try:
                    ext_elems = self.driver.find_elements(By.XPATH, xp)
                    for ee in ext_elems:
                        if ee.is_displayed() and ee.is_enabled():
                            return "EXTERNAL"
                except Exception:
                    continue

        return "DIRECT"

    def detect_flow_after_click(
        self,
        initial_windows: Optional[List[str]] = None,
        timeout: float = 6.0,
        check_interval: float = 0.5,
    ) -> Tuple[FlowType, Optional[str]]:
        """Polls the browser state after clicking Apply to determine the application flow.
        Allows up to `timeout` seconds for async AJAX / React SPA animation to settle.
        """
        if not self.driver:
            return ("UNKNOWN", "Browser driver not available")

        import time
        from platforms.naukri.selectors import SUBMISSION_SUCCESS_SELECTORS, SUBMISSION_CONFIRMATION_TEXTS

        active_job_tab = None
        if self.driver and hasattr(self.driver, "current_window_handle"):
            try:
                active_job_tab = self.driver.current_window_handle
            except Exception:
                active_job_tab = None
        target_tab = active_job_tab or (initial_windows[-1] if initial_windows else None)

        start = time.time()
        while time.time() - start < timeout:
            # 1. Check if a new tab / window opened (External Application indicator)
            current_windows = list(getattr(self.driver, "window_handles", []))
            if initial_windows and len(current_windows) > len(initial_windows):
                new_window = [w for w in current_windows if w not in initial_windows][-1]
                ext_url_found = None
                try:
                    self.driver.switch_to.window(new_window)
                    # Poll briefly for external redirect to resolve
                    t_end = time.time() + 2.5
                    while time.time() < t_end:
                        new_url = getattr(self.driver, "current_url", "") or ""
                        if isinstance(new_url, str) and new_url.startswith("http") and "about:blank" not in new_url:
                            if "naukri.com" not in new_url.lower():
                                ext_url_found = new_url
                                break
                            # Check if tracker contains url= or redirect= query parameter
                            from urllib.parse import urlparse, parse_qs, unquote
                            try:
                                qs = parse_qs(urlparse(new_url).query)
                                for qk in ["url", "target", "redirect", "destination"]:
                                    if qk in qs and qs[qk]:
                                        unwrapped = unquote(qs[qk][0]).strip()
                                        if unwrapped.startswith("http") and "naukri.com" not in unwrapped.lower():
                                            ext_url_found = unwrapped
                                            break
                            except Exception:
                                pass
                            if ext_url_found:
                                break
                        time.sleep(0.2)
                    if not ext_url_found:
                        new_url = getattr(self.driver, "current_url", "") or ""
                        if isinstance(new_url, str) and new_url.startswith("http"):
                            ext_url_found = new_url
                except Exception as e:
                    print_lg(f"[NaukriFlowDetector] Notice reading new window: {e}")
                finally:
                    # Close the spawned external window so background tabs don't accumulate
                    try:
                        curr_handle = getattr(self.driver, "current_window_handle", None)
                        if curr_handle == new_window:
                            self.driver.close()
                    except Exception:
                        pass
                    # Switch back to the active job tab
                    try:
                        if target_tab and target_tab in getattr(self.driver, "window_handles", []):
                            self.driver.switch_to.window(target_tab)
                        elif initial_windows:
                            self.driver.switch_to.window(initial_windows[-1])
                    except Exception:
                        pass

                if ext_url_found:
                    return ("EXTERNAL", f"Redirected to external portal: {ext_url_found}")

            # Check if current URL transitioned to external
            curr_url = getattr(self.driver, "current_url", None)
            if isinstance(curr_url, str) and curr_url.startswith("http") and "naukri.com" not in curr_url.lower():
                try:
                    self.driver.back()
                except Exception:
                    pass
                return ("EXTERNAL", f"Redirected to external portal: {curr_url}")

            # 2. Check for Security Checkpoint / CAPTCHA (requires MANUAL_REQUIRED)
            for sel in CAPTCHA_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        return ("CAPTCHA", "Encountered CAPTCHA anti-bot challenge")
                except Exception:
                    pass

            try:
                curr_url = (getattr(self.driver, "current_url", "") or "").lower()
                if "challenge" in curr_url or "captcha" in curr_url:
                    return ("CAPTCHA", "Security challenge in URL")
            except Exception:
                pass

            # 3. Check for Login Required / Session Expired (requires MANUAL_REQUIRED)
            for sel in LOGIN_REQUIRED_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        return ("LOGIN_REQUIRED", "Login session expired or re-authentication required")
                except Exception:
                    pass

            # 4. Check for Incomplete Profile Modal (requires MANUAL_REQUIRED)
            for sel in PROFILE_INCOMPLETE_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        return ("PROFILE_INCOMPLETE", "Profile incomplete or missing required fields")
                except Exception:
                    pass

            # 4b. Check for Rate Limit / Block / Access Restriction (Section 15 Case G)
            from platforms.naukri.selectors import RATE_LIMIT_SELECTORS, RATE_LIMIT_TEXTS
            for sel in RATE_LIMIT_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        return ("RATE_LIMITED", "Rate limit or access restriction encountered")
                except Exception:
                    pass
            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_text = (body_elem.text or "").lower()
                for r_phrase in RATE_LIMIT_TEXTS:
                    if r_phrase in body_text:
                        return ("RATE_LIMITED", f"Rate limit indicator matched: '{r_phrase}'")
            except Exception:
                pass

            # 5. Check for Questionnaire / Chatbot Drawer Modal
            drawer_detected = False
            for sel in QUESTIONNAIRE_MODAL_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if any(e.is_displayed() for e in elems):
                        drawer_detected = True
                        return ("QUESTIONNAIRE", "Recruiter screening questionnaire modal detected")
                except Exception:
                    pass

            # Also check for interactive questionnaire inputs inside modal/drawer containers
            try:
                q_inputs = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(@class, 'drawer') or contains(@class, 'chatbot') or contains(@class, 'modal') or contains(@class, 'bot-')]//input | "
                    "//div[contains(@class, 'drawer') or contains(@class, 'chatbot') or contains(@class, 'modal') or contains(@class, 'bot-')]//textarea | "
                    "//div[contains(@class, 'DrawerContent') or contains(@class, 'Drawer')]//input | "
                    "//div[contains(@class, 'chat-bubble') or contains(@class, 'bot-msg')] | "
                    "//input[contains(@placeholder, 'Type message')] | "
                    "//button[contains(@class, 'save') or normalize-space(.)='Save']"
                )
                if any(i.is_displayed() for i in q_inputs):
                    drawer_detected = True
                    return ("QUESTIONNAIRE", "Recruiter screening questionnaire inputs detected in active drawer")
            except Exception:
                pass

            # 6. Check for Direct Apply Success / Confirmation ONLY if no questionnaire drawer is present
            if not drawer_detected:
                for sel in DIRECT_APPLY_SUCCESS_SELECTORS:
                    try:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        for e in elems:
                            if e.is_displayed():
                                txt = (e.text or "").strip().lower()
                                # Require meaningful confirmation text in the element
                                if any(c in txt for c in ["applied", "success", "submitted", "confirmed", "interview preparation", "interview questions"]):
                                    return ("DIRECT", f"Application submitted directly: {txt}")
                    except Exception:
                        pass

                # Check if button or badge changed to "Applied"
                if self.is_already_applied():
                    return ("DIRECT", "Application submitted directly (button transitioned to Applied)")

                # Check body text for unambiguous direct apply confirmation phrases
                try:
                    body_elem = self.driver.find_element(By.TAG_NAME, "body")
                    body_text = (body_elem.text or "").lower()
                    for phrase in SUBMISSION_CONFIRMATION_TEXTS:
                        if phrase in body_text:
                            return ("DIRECT", f"Confirmation text matched: '{phrase}'")
                except Exception:
                    pass

            time.sleep(check_interval)

        return ("UNKNOWN", "Could not ascertain modal or application state")

    def find_apply_button(self, card_elem: Optional[WebElement] = None) -> Optional[WebElement]:
        """Locates the primary Apply or Company Site button on the current job page or within card element.
        Uses both CSS selectors and XPath text-based selectors for Naukri's dynamic DOM.
        Carefully excludes Save, Bookmark, Share, Follow, and OAuth sign-in buttons.
        """
        from platforms.naukri.selectors import APPLY_BUTTON_XPATH_SELECTORS, APPLY_BUTTON_SELECTORS

        def _is_valid_apply_button(elem: WebElement) -> bool:
            try:
                elem_id = (elem.get_attribute("id") or "").lower()
                cls = (elem.get_attribute("class") or "").lower()
                txt = (elem.text or elem.get_attribute("innerText") or elem.get_attribute("textContent") or "").strip().lower()
                # Reject login / OAuth buttons
                if any(ign in elem_id or ign in cls for ign in ["google", "facebook", "login", "signup", "register"]):
                    return False
                # Reject save / bookmark / share / report / follow buttons
                if any(ign in elem_id or ign in cls for ign in ["saved", "save-button", "share", "report", "follow", "bookmark"]):
                    return False
                if txt in ["save", "saved", "share", "report", "follow", "continue with google", "sign in"]:
                    return False
                # Skip already applied
                if "already" in txt or txt == "applied":
                    return False
                return True
            except Exception:
                return False

        # 1. Try CSS selectors on card element first
        if card_elem:
            for sel in APPLY_BUTTON_SELECTORS:
                try:
                    elems = card_elem.find_elements(By.CSS_SELECTOR, sel)
                    for elem in elems:
                        if elem.is_displayed() and elem.is_enabled() and _is_valid_apply_button(elem):
                            return elem
                except Exception:
                    continue

        if not self.driver:
            return None

        # 2. Try CSS selectors on the full page
        for sel in APPLY_BUTTON_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled() and _is_valid_apply_button(elem):
                        return elem
            except Exception:
                continue

        # 3. Fallback: XPath text-based selectors (most reliable for Naukri's dynamic classes)
        for xpath in APPLY_BUTTON_XPATH_SELECTORS:
            try:
                elems = self.driver.find_elements(By.XPATH, xpath)
                for elem in elems:
                    if elem.is_displayed() and elem.is_enabled() and _is_valid_apply_button(elem):
                        text = (elem.text or elem.get_attribute("innerText") or "").strip().lower()
                        if "already" in text or "applied" == text:
                            continue
                        if any(w in text for w in ["apply", "quick apply", "apply now", "company site", "company website"]):
                            return elem
                        # If it matched by id/class (e.g. company-site-button or apply-button) but has no visible text
                        if not text:
                            return elem
            except Exception:
                continue

        return None

    def close_modal_if_open(self) -> bool:
        """Attempts to close any open modal/drawer to restore a clean state."""
        if not self.driver:
            return False
        for sel in MODAL_CLOSE_BUTTONS:
            try:
                btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for btn in btns:
                    if btn.is_displayed():
                        try:
                            btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", btn)
                        return True
            except Exception:
                continue
        return False


class NaukriApplier:
    """
    High-level application engine for Naukri jobs.
    Coordinates flow detection, questionnaire filling, and human safety review.
    Enforces the Phase 11 safety lock: halts at the final screen for human review.
    """

    def __init__(
        self,
        browser: Any,
        form: Optional[Any] = None,
        safety_gate: Optional[Any] = None,
        submitter: Optional[Any] = None,
        flow_detector: Optional[NaukriFlowDetector] = None,
        tracker: Optional[Any] = None,
        automation_bridge: Optional[Any] = None,
    ):
        self.browser = browser
        self.flow_detector = flow_detector or NaukriFlowDetector(browser)
        self.form = form
        self.safety_gate = safety_gate
        self.submitter = submitter
        self.tracker = tracker
        self.automation_bridge = automation_bridge


        # Lazy initialize form, safety_gate, and submitter if not provided
        if not self.form:
            from platforms.naukri.form import NaukriForm
            self.form = NaukriForm(browser)
        if not self.safety_gate:
            from platforms.naukri.safety_gate import NaukriSafetyGate
            self.safety_gate = NaukriSafetyGate(browser)
        if not self.submitter:
            from platforms.naukri.submitter import NaukriSubmitter
            self.submitter = NaukriSubmitter(browser, tracker=self.tracker)

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def submit_application(self, job: Any) -> Tuple[bool, str]:
        """Directly delegates submission to NaukriSubmitter."""
        return self.submitter.submit_application(job)

    def _extract_external_apply_url(self, apply_btn: Optional[WebElement], job_url: str = "") -> Optional[str]:
        """Extracts the direct external company portal URL from an external apply button.

        Attempts static attribute extraction first (href, data-href, onclick regex, child/parent anchors).
        If unresolved or pointing to internal Naukri redirector, safely clicks the button to capture
        the resolved company portal URL in the new tab or redirect, then closes the tab and restores window state.
        """
        if not apply_btn or not self.driver:
            return None

        import re
        from urllib.parse import urlparse, parse_qs, unquote

        def _is_clean_external_url(url: Optional[str]) -> bool:
            if not url or not isinstance(url, str):
                return False
            u = url.strip()
            if not (u.startswith("http://") or u.startswith("https://")):
                return False
            low = u.lower()
            if "about:blank" in low or "javascript:" in low:
                return False
            if any(dom in low for dom in ["naukri.com", "linkedin.com"]):
                return False
            return True

        def _unwrap_redirect_url(url: Optional[str]) -> Optional[str]:
            if not url or not isinstance(url, str):
                return None
            u = url.strip()
            try:
                parsed = urlparse(u)
                qs = parse_qs(parsed.query)
                for key in ["url", "target", "redirect", "redirect_url", "dest", "destination", "link"]:
                    if key in qs and qs[key]:
                        candidate = unquote(qs[key][0]).strip()
                        if _is_clean_external_url(candidate):
                            return candidate
            except Exception:
                pass
            return u if _is_clean_external_url(u) else None

        # 1. Direct attribute inspection
        candidate_attrs = [
            "href", "data-href", "data-url", "data-target-url",
            "data-apply-url", "data-session-redirect-url", "data-outbound-url"
        ]
        for attr in candidate_attrs:
            try:
                val = apply_btn.get_attribute(attr)
                unwrapped = _unwrap_redirect_url(val)
                if unwrapped:
                    return unwrapped
            except Exception:
                pass

        # 2. Check child anchor <a> or ancestor <a>
        try:
            anchors = apply_btn.find_elements(By.TAG_NAME, "a")
            for a in anchors:
                href = a.get_attribute("href")
                unwrapped = _unwrap_redirect_url(href)
                if unwrapped:
                    return unwrapped
        except Exception:
            pass

        try:
            parent_a = apply_btn.find_elements(By.XPATH, "./ancestor::a")
            for a in parent_a:
                href = a.get_attribute("href")
                unwrapped = _unwrap_redirect_url(href)
                if unwrapped:
                    return unwrapped
        except Exception:
            pass

        # 3. Check onclick attribute or inner script for URLs
        try:
            onclick_val = apply_btn.get_attribute("onclick") or ""
            match = re.search(r"https?://[^\s'\"<>\)]+", onclick_val)
            if match:
                unwrapped = _unwrap_redirect_url(match.group(0))
                if unwrapped:
                    return unwrapped
        except Exception:
            pass

        # 4. Dynamic extraction: Click button and capture resolved external tab/window
        try:
            handles_before = list(getattr(self.driver, "window_handles", []))
            active_handle = None
            try:
                active_handle = self.driver.current_window_handle
            except Exception:
                active_handle = handles_before[0] if handles_before else None

            # Attempt click
            try:
                apply_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", apply_btn)

            # Poll for new window / tab (up to 4.0s)
            import time
            start = time.time()
            resolved_ext_url = None

            while time.time() - start < 4.0:
                current_handles = list(getattr(self.driver, "window_handles", []))
                if len(current_handles) > len(handles_before):
                    new_tab = [h for h in current_handles if h not in handles_before][-1]
                    try:
                        self.driver.switch_to.window(new_tab)
                        # Wait up to 2.5s for tab redirect away from about:blank or tracking link
                        t_wait = time.time()
                        while time.time() - t_wait < 2.5:
                            curr_url = getattr(self.driver, "current_url", "") or ""
                            if curr_url and curr_url.startswith("http") and "about:blank" not in curr_url:
                                unwrapped = _unwrap_redirect_url(curr_url)
                                if unwrapped:
                                    resolved_ext_url = unwrapped
                                    break
                                elif "naukri.com" not in curr_url.lower():
                                    resolved_ext_url = curr_url
                                    break
                            time.sleep(0.3)

                        if not resolved_ext_url:
                            curr_url = getattr(self.driver, "current_url", "") or ""
                            resolved_ext_url = _unwrap_redirect_url(curr_url) or (
                                curr_url if _is_clean_external_url(curr_url) else None
                            )
                    except Exception as tab_e:
                        print_lg(f"[NaukriApplier] Notice inspecting external tab: {tab_e}")
                    finally:
                        # Close the spawned external tab to prevent tab accumulation
                        try:
                            self.driver.close()
                        except Exception:
                            pass
                        # Switch back to the original Naukri tab
                        try:
                            if active_handle and active_handle in getattr(self.driver, "window_handles", []):
                                self.driver.switch_to.window(active_handle)
                            elif handles_before:
                                self.driver.switch_to.window(handles_before[0])
                        except Exception:
                            pass
                    break

                # Check if current window navigated directly to external portal
                curr_main = getattr(self.driver, "current_url", "") or ""
                if _is_clean_external_url(curr_main):
                    resolved_ext_url = curr_main
                    try:
                        self.driver.back()
                    except Exception:
                        pass
                    break

                time.sleep(0.3)

            if resolved_ext_url:
                return resolved_ext_url
        except Exception as click_e:
            print_lg(f"[NaukriApplier] Notice resolving external apply URL: {click_e}")

        return None

    def apply_to_job(
        self,
        job: Any,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None,
        card_element: Optional[WebElement] = None,
    ) -> Dict[str, Any]:
        """
        Executes the application pipeline for a single job up to the human review gate:
        1. Transitions tracker state to APPLYING.
        2. Opens job detail in isolated tab so search results page DOM is never destroyed.
        3. Checks if already applied (skips without error).
        4. Inspects apply button for external redirects.
        5. Clicks apply and inspects post-click modal flow with polling.
        6. Fills questionnaires if required.
        7. Halts at Phase 11 Safety Gate for human review.
        8. On APPROVE, executes Phase 12 final submission and verifies confirmation.
        9. Guarantees tab cleanup in finally block, returning to search tab.
        """
        import time
        from platforms.naukri.recovery import dismiss_unexpected_popups

        job_url = getattr(job, "source_url", None)
        search_window = None
        opened_tab = False

        try:
            if self.tracker:
                self.tracker.record_state(job, "APPLYING")

            # Identify current search window
            if self.driver and hasattr(self.driver, "current_window_handle"):
                try:
                    search_window = self.driver.current_window_handle
                except Exception:
                    search_window = None

            # Open job detail in isolated tab to preserve search results page DOM
            if job_url and self.driver:
                try:
                    if hasattr(self.driver, "switch_to") and hasattr(self.driver.switch_to, "new_window"):
                        self.driver.switch_to.new_window('tab')
                        self.driver.get(job_url)
                        opened_tab = True
                    elif search_window and hasattr(self.driver, "execute_script"):
                        self.driver.execute_script("window.open(arguments[0], '_blank');", job_url)
                        new_handles = [h for h in getattr(self.driver, "window_handles", []) if h != search_window]
                        if new_handles:
                            self.driver.switch_to.window(new_handles[-1])
                            opened_tab = True
                        else:
                            self.driver.get(job_url)
                    else:
                        self.driver.get(job_url)
                except Exception as tab_err:
                    print_lg(f"[NaukriApplier] Tab open error: {tab_err}. Navigating directly...")
                    try:
                        self.driver.get(job_url)
                    except Exception:
                        pass

                from modules.config_loader import get_platform
                page_load_delay = float(get_platform("naukri").get("page_load_delay", 3.0))
                time.sleep(page_load_delay)  # Allow React SPA to hydrate
                dismiss_unexpected_popups(self.driver)

            # Extract full job description from job details page
            try:
                from platforms.naukri.selectors import JOB_DETAILS_DESCRIPTION_SELECTORS
                full_jd = ""
                for jd_sel in JOB_DETAILS_DESCRIPTION_SELECTORS:
                    try:
                        jd_elems = self.driver.find_elements(By.CSS_SELECTOR, jd_sel)
                        for jd_elem in jd_elems:
                            text_val = (jd_elem.text or "").strip()
                            if len(text_val) > len(full_jd):
                                full_jd = text_val
                    except Exception:
                        continue
                if full_jd and len(full_jd) > len(getattr(job, "description", "") or ""):
                    job.description = full_jd
                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import JobDiscoveredEvent
                            self.automation_bridge.handle_job_discovered(
                                JobDiscoveredEvent(
                                    run_id="naukri_run",
                                    platform="naukri",
                                    title=job.title,
                                    company=job.company,
                                    external_job_id=getattr(job, "job_id", None),
                                    location=job.location,
                                    url=job.source_url,
                                    application_method=getattr(job, "application_method", "EASY_APPLY") or "EASY_APPLY",
                                    application_url=getattr(job, "application_url", None),
                                    description=job.description,
                                )
                            )
                        except Exception:
                            pass
            except Exception as jd_err:
                print_lg(f"[NaukriApplier] Notice extracting full JD: {jd_err}")

            # Check if this job was already applied to
            if getattr(self.flow_detector, "is_already_applied", lambda: False)() is True:
                print_lg(f"[NaukriApplier] Job '{getattr(job, 'job_id', 'unknown')}' is already applied. Skipping.")
                if self.tracker:
                    self.tracker.record_state(job, "SKIPPED", reason="Already applied")
                return {"status": "SKIPPED", "reason": "Already applied"}

            # Poll for Apply button with retries
            apply_btn = None
            for attempt in range(3):
                apply_btn = self.flow_detector.find_apply_button(card_elem=card_element)
                if apply_btn:
                    break
                time.sleep(1.5)
                dismiss_unexpected_popups(self.driver)

            if not apply_btn:
                # Double-check if it's already applied (e.g. disabled button)
                if getattr(self.flow_detector, "is_already_applied", lambda: False)() is True:
                    print_lg(f"[NaukriApplier] Job '{getattr(job, 'job_id', 'unknown')}' is already applied. Skipping.")
                    if self.tracker:
                        self.tracker.record_state(job, "SKIPPED", reason="Already applied")
                    return {"status": "SKIPPED", "reason": "Already applied"}

                # Check if job is expired or closed or already applied
                try:
                    body_elem = self.driver.find_element(By.TAG_NAME, "body")
                    body_text = (body_elem.text or "").lower()
                    if any(phrase in body_text for phrase in [
                        "job is no longer active",
                        "this job has expired",
                        "opening is closed",
                        "no longer accepting applications",
                        "job has been removed",
                        "already applied",
                        "you have already applied",
                        "applied to",
                        "start your interview preparation",
                    ]):
                        skip_msg = "Job is no longer active or already applied"
                        print_lg(f"[NaukriApplier] Job '{getattr(job, 'job_id', 'unknown')}': {skip_msg}. Skipping.")
                        if self.tracker:
                            self.tracker.record_state(job, "SKIPPED", reason=skip_msg)
                        return {"status": "SKIPPED", "reason": skip_msg}
                except Exception:
                    pass

                msg = f"Apply button not found on job page: {job_url or 'no URL'}"
                print_lg(f"[NaukriApplier] {msg}")
                if self.tracker:
                    self.tracker.record_state(job, "FAILED", reason=msg)
                return {"status": "FAILED", "reason": msg}

            # Pre-click inspect
            btn_type = self.flow_detector.detect_apply_button_type(apply_btn)
            if btn_type == "EXTERNAL":
                ext_url = self._extract_external_apply_url(apply_btn, job_url=job_url or "")

                job.apply_type = "EXTERNAL"
                job.application_method = "COMPANY_PORTAL"
                job.application_url = ext_url

                if self.automation_bridge:
                    try:
                        from app.services.automation_events import JobDiscoveredEvent
                        self.automation_bridge.handle_job_discovered(
                            JobDiscoveredEvent(
                                run_id="naukri_run",
                                platform="naukri",
                                title=job.title,
                                company=job.company,
                                external_job_id=getattr(job, "job_id", None),
                                location=job.location,
                                url=job.source_url,
                                application_method="COMPANY_PORTAL",
                                application_url=ext_url,
                                description=getattr(job, "description", None),
                            )
                        )
                    except Exception:
                        pass

                msg = f"Direct apply on company site: {ext_url}" if ext_url else "Direct apply only; job requires external company application"
                if self.tracker:
                    self.tracker.record_state(job, "EXTERNAL", reason=msg, application_type="EXTERNAL")
                return {"status": "EXTERNAL", "reason": msg, "application_url": ext_url}


            initial_windows = list(self.driver.window_handles) if self.driver else []

            # Click Apply
            click_success = False
            try:
                apply_btn.click()
                click_success = True
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", apply_btn)
                    click_success = True
                except Exception as e:
                    msg = f"Failed clicking apply button: {e}"
                    print_lg(f"[NaukriApplier] {msg}")

            if not click_success:
                msg = "Failed to click apply button on job page"
                if self.tracker:
                    self.tracker.record_state(job, "FAILED", reason=msg)
                return {"status": "FAILED", "reason": msg}

            # Detect flow with polling (configurable timeout, defaults to 8.0s)
            from modules.config_loader import get_platform
            flow_timeout = float(get_platform("naukri").get("flow_detection_timeout", 8.0))
            flow, flow_reason = self.flow_detector.detect_flow_after_click(
                initial_windows=initial_windows,
                timeout=flow_timeout,
            )

            if flow == "EXTERNAL":
                ext_url = None
                if flow_reason and "portal: " in flow_reason:
                    candidate = flow_reason.split("portal: ")[-1].strip()
                    if candidate.startswith("http") and "naukri.com" not in candidate.lower():
                        ext_url = candidate
                elif self.driver:
                    try:
                        curr = self.driver.current_url
                        if curr and curr.startswith("http") and "naukri.com" not in curr.lower():
                            ext_url = curr
                    except Exception:
                        pass

                job.apply_type = "EXTERNAL"
                job.application_method = "COMPANY_PORTAL"
                job.application_url = ext_url

                if self.automation_bridge:
                    try:
                        from app.services.automation_events import JobDiscoveredEvent
                        self.automation_bridge.handle_job_discovered(
                            JobDiscoveredEvent(
                                run_id="naukri_run",
                                platform="naukri",
                                title=job.title,
                                company=job.company,
                                external_job_id=getattr(job, "job_id", None),
                                location=job.location,
                                url=job.source_url,
                                application_method="COMPANY_PORTAL",
                                application_url=ext_url,
                                description=getattr(job, "description", None),
                            )
                        )
                    except Exception:
                        pass

                if self.tracker:
                    self.tracker.record_state(job, "EXTERNAL", reason=flow_reason, application_type="EXTERNAL")
                return {"status": "EXTERNAL", "reason": flow_reason, "application_url": ext_url}


            if flow == "ALREADY_APPLIED":
                print_lg(f"[NaukriApplier] Job '{getattr(job, 'job_id', 'unknown')}' is already applied. Skipping.")
                if self.tracker:
                    self.tracker.record_state(job, "SKIPPED", reason="Already applied")
                return {"status": "SKIPPED", "reason": "Already applied"}

            if flow == "RATE_LIMITED":
                msg = f"Rate limited or access restricted: {flow_reason}"
                print_lg(f"[NaukriApplier] {msg}")
                if self.tracker:
                    self.tracker.record_state(job, "FAILED", reason=msg)
                return {"status": "FAILED", "reason": msg, "rate_limited": True}

            if flow == "APPLY_UNAVAILABLE":
                msg = f"Apply unavailable or disabled: {flow_reason}"
                print_lg(f"[NaukriApplier] {msg}")
                if self.tracker:
                    self.tracker.record_state(job, "SKIPPED", reason=msg)
                return {"status": "SKIPPED", "reason": msg}

            if flow == "CAPTCHA":
                print_lg(f"[NaukriApplier] CAPTCHA detected for job '{getattr(job, 'job_id', 'unknown')}'. Cooperatively awaiting resolution...")
                detector = CaptchaDetector(platform="naukri")
                solved = detector.handle_captcha(
                    self.driver,
                    platform="naukri",
                    job_title=getattr(job, "title", ""),
                    company=getattr(job, "company", ""),
                    timeout=60,
                )
                if solved:
                    print_lg("[NaukriApplier] CAPTCHA resolved! Re-detecting apply flow...")
                    flow, flow_reason = self.flow_detector.detect_flow()
                else:
                    if self.tracker:
                        self.tracker.record_state(job, "MANUAL_REQUIRED", reason=flow_reason)
                    return {"status": "MANUAL_REQUIRED", "reason": flow_reason}

            if flow in ("LOGIN_REQUIRED", "PROFILE_INCOMPLETE"):
                if self.tracker:
                    self.tracker.record_state(job, "MANUAL_REQUIRED", reason=flow_reason)
                return {"status": "MANUAL_REQUIRED", "reason": flow_reason}

            if flow == "QUESTIONNAIRE":
                desc = job_description or getattr(job, "description", None)
                loc = work_location or getattr(job, "location", None)
                form_result = self.form.fill_form(job_description=desc, work_location=loc)

                if form_result.get("status") in ("FAILED", "REJECTED", "VALIDATION_FAILED", "INPUT_FAILED", "QUESTION_UNRESOLVED"):
                    err = form_result.get("reason") or form_result.get("error") or "Questionnaire interaction error"
                    print_lg(f"[NaukriApplier] Job '{getattr(job, 'job_id', 'unknown')}' questionnaire error: {err}")
                    try:
                        capture_naukri_diagnostics(
                            self.driver,
                            job_id=getattr(job, "job_id", "unknown"),
                            context=f"questionnaire_{form_result.get('status').lower()}",
                            question=form_result.get("field"),
                            error=err,
                            extra_info=form_result,
                        )
                    except Exception:
                        pass
                    # Cleanly close lingering modal/drawer so it never blocks subsequent jobs in search rotation
                    try:
                        self.flow_detector.close_modal_if_open()
                    except Exception:
                        pass
                    if self.tracker:
                        self.tracker.record_state(job, "FAILED", reason=err)
                    return {"status": "FAILED", "reason": err}

                filled_fields = form_result.get("filled_fields", [])

                # Check if submission was already completed inside the form/chatbot flow
                if form_result.get("status") == "SUBMITTED":
                    sub_reason = form_result.get("reason", "Submitted via chatbot flow")
                    print_lg(
                        f"[APPLICATION_CONFIRMED] Job: '{getattr(job, 'title', getattr(job, 'job_id', 'Unknown'))}' | "
                        f"Company: '{getattr(job, 'company', 'Unknown')}' | "
                        f"URL: '{job_url or 'N/A'}' | Platform: 'naukri' | Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                    )
                    # Cleanly close lingering modal/card
                    try:
                        self.flow_detector.close_modal_if_open()
                    except Exception:
                        pass
                    if self.tracker:
                        self.tracker.record_state(job, "SUBMITTED", reason=sub_reason)
                    return {
                        "status": "SUBMITTED",
                        "reason": sub_reason,
                        "filled_fields": filled_fields,
                    }

                # Phase 11 Safety Gate: Human Review (safety_gate internally enforces pause_before_submit)
                gate_result = self.safety_gate.review(job, filled_fields=filled_fields)
                if gate_result.decision == "DISCARD":
                    self.flow_detector.close_modal_if_open()
                    if self.tracker:
                        self.tracker.record_state(job, "SKIPPED", reason="Discarded during human review")
                    return {"status": "SKIPPED", "reason": "Discarded during human review"}
                elif gate_result.decision != "APPROVE":
                    if self.tracker:
                        self.tracker.record_state(job, "MANUAL_REQUIRED", reason="Held for manual completion by user")
                    return {"status": "MANUAL_REQUIRED", "reason": "Held for manual completion by user"}

                sub_success, sub_reason = self.submitter.submit_application(job)
                if sub_success:
                    print_lg(
                        f"[APPLICATION_CONFIRMED] Job: '{getattr(job, 'title', getattr(job, 'job_id', 'Unknown'))}' | "
                        f"Company: '{getattr(job, 'company', 'Unknown')}' | "
                        f"URL: '{job_url or 'N/A'}' | Platform: 'naukri' | Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                    )
                status = "SUBMITTED" if sub_success else ("UNKNOWN" if "TIMEOUT_UNKNOWN" in sub_reason else "FAILED")
                res = {
                    "status": status,
                    "reason": sub_reason,
                    "filled_fields": filled_fields,
                }
                if gate_result:
                    res["gate_result"] = gate_result
                return res

            if flow == "DIRECT":
                # Check if an intermediate submit button exists (e.g. multi-step direct modal)
                sub_btn = self.submitter.find_submit_button()
                if sub_btn:
                    from modules.config_loader import get_platform
                    pause_required = bool(get_platform("naukri").get("pause_before_submit", False))
                    if pause_required:
                        gate_result = self.safety_gate.review(job, filled_fields=[])
                        if gate_result.decision != "APPROVE":
                            self.flow_detector.close_modal_if_open()
                            decision_state = "SKIPPED" if gate_result.decision == "DISCARD" else "MANUAL_REQUIRED"
                            if self.tracker:
                                self.tracker.record_state(job, decision_state, reason="Cancelled during human review")
                            return {"status": decision_state, "reason": "Cancelled during human review"}
                    sub_success, sub_reason = self.submitter.submit_application(job)
                    if sub_success:
                        print_lg(
                            f"[APPLICATION_CONFIRMED] Job: '{getattr(job, 'title', getattr(job, 'job_id', 'Unknown'))}' | "
                            f"Company: '{getattr(job, 'company', 'Unknown')}' | "
                            f"URL: '{job_url or 'N/A'}' | Platform: 'naukri' | Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                        )
                    status = "SUBMITTED" if sub_success else ("UNKNOWN" if "TIMEOUT_UNKNOWN" in sub_reason else "FAILED")
                    return {
                        "status": status,
                        "reason": sub_reason,
                        "filled_fields": [],
                    }
                else:
                    # Direct 1-click apply: Naukri submitted the application upon initial click
                    confirmed, reason = self.submitter.verify_submission(timeout=5.0)
                    if confirmed or self.flow_detector.is_already_applied():
                        conf_msg = reason or "1-click apply confirmed successfully"
                        print_lg(
                            f"[APPLICATION_CONFIRMED] Job: '{getattr(job, 'title', getattr(job, 'job_id', 'Unknown'))}' | "
                            f"Company: '{getattr(job, 'company', 'Unknown')}' | "
                            f"URL: '{job_url or 'N/A'}' | Platform: 'naukri' | Time: '{time.strftime('%Y-%m-%d %H:%M:%S')}'"
                        )
                        print_lg(f"[NaukriApplier] Direct 1-click application confirmed for '{getattr(job, 'job_id', 'unknown')}': {conf_msg}")
                        if self.tracker:
                            self.tracker.record_state(job, "SUBMITTED")
                        # Cleanly close confirmation modal/card if open
                        try:
                            self.flow_detector.close_modal_if_open()
                        except Exception:
                            pass
                        return {
                            "status": "SUBMITTED",
                            "reason": conf_msg,
                            "filled_fields": [],
                        }
                    else:
                        print_lg(f"[NaukriApplier] Notice: 1-click apply unconfirmed: {reason}")
                        if self.tracker:
                            self.tracker.record_state(job, "UNKNOWN", reason=f"1-click apply unconfirmed: {reason}")
                        return {
                            "status": "UNKNOWN",
                            "reason": f"1-click apply unconfirmed: {reason}",
                            "filled_fields": [],
                        }

            # UNKNOWN flow - Capture diagnostic snapshot
            try:
                capture_naukri_diagnostics(
                    self.driver,
                    job_id=getattr(job, "job_id", "unknown"),
                    context="unknown_apply_state",
                    error=flow_reason,
                )
            except Exception:
                pass
            msg = f"Unknown flow encountered after click: {flow_reason}"
            if self.tracker:
                self.tracker.record_state(job, "UNKNOWN", reason=msg)
            return {"status": "UNKNOWN", "reason": msg}

        except Exception as exc:
            from platforms.naukri.recovery import classify_error
            state, reason = classify_error(exc, context="apply_to_job")
            print_lg(f"[NaukriApplier] Controlled error recovery for job '{getattr(job, 'job_id', 'unknown')}': {state} - {reason}")
            try:
                self.flow_detector.close_modal_if_open()
            except Exception:
                pass
            if self.tracker:
                self.tracker.record_state(job, state, reason=reason)
            return {"status": state, "reason": reason, "error": str(exc), "recovered": True}

        finally:
            # Always close the isolated job detail tab and restore search window safely
            if opened_tab and self.driver and search_window:
                try:
                    handles = list(getattr(self.driver, "window_handles", []))
                    if search_window in handles:
                        curr = getattr(self.driver, "current_window_handle", None)
                        if curr and curr != search_window:
                            try:
                                self.driver.close()
                            except Exception:
                                pass
                        self.driver.switch_to.window(search_window)
                    elif handles:
                        self.driver.switch_to.window(handles[0])
                except Exception as tab_err:
                    print_lg(f"[NaukriApplier] Notice restoring search window: {tab_err}")



