"""
Glassdoor Page Classifier
Multi-signal page classification for Glassdoor automation.
Classifies the current page into semantic types:
SEARCH_RESULTS, JOB_DETAIL, APPLICATION_FORM, APPLICATION_STEP,
LOGIN, CAPTCHA, COOKIE_CONSENT, ERROR, MAINTENANCE, EXTERNAL_APPLICATION, UNKNOWN.
Does NOT rely on URL alone. Uses DOM landmarks, headings, forms, and interactive elements.
"""

from __future__ import annotations
import re
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


class GlassdoorPageType(Enum):
    SEARCH_RESULTS = "SEARCH_RESULTS"
    JOB_DETAIL = "JOB_DETAIL"
    APPLICATION_FORM = "APPLICATION_FORM"
    APPLICATION_STEP = "APPLICATION_STEP"
    LOGIN = "LOGIN"
    CAPTCHA = "CAPTCHA"
    COOKIE_CONSENT = "COOKIE_CONSENT"
    ERROR = "ERROR"
    MAINTENANCE = "MAINTENANCE"
    EXTERNAL_APPLICATION = "EXTERNAL_APPLICATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class PageClassificationResult:
    page_type: GlassdoorPageType
    confidence: float
    matched_signals: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_search_results(self) -> bool:
        return self.page_type == GlassdoorPageType.SEARCH_RESULTS

    @property
    def is_job_detail(self) -> bool:
        return self.page_type == GlassdoorPageType.JOB_DETAIL

    @property
    def is_application(self) -> bool:
        return self.page_type in (
            GlassdoorPageType.APPLICATION_FORM,
            GlassdoorPageType.APPLICATION_STEP,
            GlassdoorPageType.EXTERNAL_APPLICATION,
        )

    @property
    def requires_intervention(self) -> bool:
        return self.page_type in (
            GlassdoorPageType.LOGIN,
            GlassdoorPageType.CAPTCHA,
            GlassdoorPageType.ERROR,
            GlassdoorPageType.MAINTENANCE,
        )


class GlassdoorPageClassifier:
    """Classifies Glassdoor pages using multi-signal heuristics across URL, title, visible text, and DOM."""

    # Pre-compiled regex patterns for resilient signal matching
    RE_CAPTCHA = re.compile(
        r"verify\s+you\s+are\s+human|security\s+check|challenge-stage|cloudflare|recaptcha|hcaptcha|turnstile|arkoselabs|datadome",
        re.IGNORECASE,
    )
    RE_LOGIN = re.compile(
        r"sign\s+in|log\s+in|welcome\s+back|enter\s+your\s+email|create\s+account|continue\s+with\s+google|inlineUserEmail",
        re.IGNORECASE,
    )
    RE_ERROR = re.compile(
        r"404\s+not\s+found|500\s+internal|502\s+bad\s+gateway|503\s+service\s+unavailable|page\s+not\s+found|something\s+went\s+wrong",
        re.IGNORECASE,
    )
    RE_COOKIE = re.compile(
        r"cookie\s+preferences|accept\s+all\s+cookies|we\s+value\s+your\s+privacy|onetrust",
        re.IGNORECASE,
    )
    RE_JOB_DETAIL = re.compile(
        r"jobDescriptionText|JobDescriptionContainer|jobDescriptionContent|apply-button|easyApply|easy-apply",
        re.IGNORECASE,
    )
    RE_SEARCH_RESULTS = re.compile(
        r"job-listing-list|job-listings|JobsList|searchBar-jobTitle|searchBar-location|easy-apply-filter",
        re.IGNORECASE,
    )

    @classmethod
    def classify_dom_snapshot(
        cls,
        url: str = "",
        title: str = "",
        html: str = "",
        visible_text: str = "",
        headings: Optional[List[str]] = None,
        button_texts: Optional[List[str]] = None,
        input_names: Optional[List[str]] = None,
    ) -> PageClassificationResult:
        """Performs classification on extracted DOM snapshot data without requiring active WebDriver."""
        matched_signals: List[str] = []
        headings = [str(h) for h in (headings or []) if h]
        button_texts = [str(b).lower() for b in (button_texts or []) if b]
        input_names = [str(i).lower() for i in (input_names or []) if i]
        url_lower = (url or "").lower()
        title_lower = (title or "").lower()
        combined_text = f"{title_lower} {(visible_text or '').lower()[:3000]}"

        # 1. CAPTCHA / Security Challenge Detection (Active challenges only, ignore CDN scripts)
        captcha_score = 0.0
        if cls.RE_CAPTCHA.search(combined_text):
            captcha_score += 0.5
            matched_signals.append("captcha_text_in_body")
        if "challenge-stage" in html.lower() or "challenges.cloudflare.com" in html.lower() or "cf-turnstile" in html.lower():
            captcha_score += 0.5
            matched_signals.append("cloudflare_challenge_container")
        if "recaptcha/api2/bframe" in html.lower() or "recaptcha/enterprise/bframe" in html.lower():
            captcha_score += 0.5
            matched_signals.append("recaptcha_active_bframe")
        if captcha_score >= 0.7:
            return PageClassificationResult(
                page_type=GlassdoorPageType.CAPTCHA,
                confidence=min(1.0, captcha_score),
                matched_signals=matched_signals,
            )

        # 2. Error Page Detection
        if cls.RE_ERROR.search(combined_text):
            matched_signals.append("error_text_in_body")
            return PageClassificationResult(
                page_type=GlassdoorPageType.ERROR,
                confidence=0.9,
                matched_signals=matched_signals,
            )

        # 3. External Application Page (e.g., smartapply.indeed.com, greenhouse, lever, workday)
        if "smartapply.indeed.com" in url_lower:
            matched_signals.append("smartapply_indeed_domain")
            if "review-module" in url_lower or any("review" in b for b in button_texts):
                matched_signals.append("review_step_marker")
                return PageClassificationResult(
                    page_type=GlassdoorPageType.APPLICATION_STEP,
                    confidence=0.95,
                    matched_signals=matched_signals,
                    details={"provider": "indeed_smart_apply", "step": "review"},
                )
            return PageClassificationResult(
                page_type=GlassdoorPageType.APPLICATION_FORM,
                confidence=0.95,
                matched_signals=matched_signals,
                details={"provider": "indeed_smart_apply"},
            )

        if any(ats in url_lower for ats in ["greenhouse.io", "lever.co", "myworkdayjobs.com", "ashbyhq.com", "icims.com"]):
            matched_signals.append("external_ats_domain")
            return PageClassificationResult(
                page_type=GlassdoorPageType.EXTERNAL_APPLICATION,
                confidence=0.95,
                matched_signals=matched_signals,
                details={"external_url": url},
            )

        # 4. Login Wall / Authentication Required
        login_score = 0.0
        if "/profile/login" in url_lower or "login" in url_lower:
            login_score += 0.4
            matched_signals.append("login_in_url")
        if any(cls.RE_LOGIN.search(b) for b in button_texts):
            login_score += 0.3
            matched_signals.append("sign_in_button")
        if any("password" in i or "email" in i for i in input_names) and any("sign in" in b or "continue" in b for b in button_texts):
            login_score += 0.4
            matched_signals.append("login_input_fields")
        if login_score >= 0.6:
            return PageClassificationResult(
                page_type=GlassdoorPageType.LOGIN,
                confidence=min(1.0, login_score),
                matched_signals=matched_signals,
            )

        # 5. Search Results Page (SRP)
        srp_score = 0.0
        if "/job/" in url_lower or "/jobs" in url_lower or "jobs.htm" in url_lower:
            srp_score += 0.25
            matched_signals.append("jobs_url_pattern")
        if "searchbar-jobtitle" in html.lower() or "sc.keyword" in html.lower():
            srp_score += 0.3
            matched_signals.append("search_inputs_present")
        if "job-listing" in html.lower() or "jobslist" in html.lower() or "jobcard" in html.lower():
            srp_score += 0.4
            matched_signals.append("job_cards_container_present")
        if any("easy apply" in b for b in button_texts):
            srp_score += 0.2
            matched_signals.append("easy_apply_filter_or_button")
        if srp_score >= 0.5:
            return PageClassificationResult(
                page_type=GlassdoorPageType.SEARCH_RESULTS,
                confidence=min(1.0, srp_score),
                matched_signals=matched_signals,
            )

        # 6. Standalone Job Detail Page
        detail_score = 0.0
        if "/job-listing/" in url_lower or "jl=" in url_lower or "joblistingid" in url_lower:
            detail_score += 0.35
            matched_signals.append("job_detail_url_pattern")
        if "jobdescriptiontext" in html.lower() or "jobdescriptioncontainer" in html.lower():
            detail_score += 0.4
            matched_signals.append("job_description_container")
        if any("apply" in b for b in button_texts):
            detail_score += 0.2
            matched_signals.append("apply_button_present")
        if detail_score >= 0.5:
            return PageClassificationResult(
                page_type=GlassdoorPageType.JOB_DETAIL,
                confidence=min(1.0, detail_score),
                matched_signals=matched_signals,
            )

        # Fallback: UNKNOWN
        return PageClassificationResult(
            page_type=GlassdoorPageType.UNKNOWN,
            confidence=0.2,
            matched_signals=["insufficient_signals"],
        )

    @classmethod
    def classify_driver(cls, driver: Any) -> PageClassificationResult:
        """Classifies the live browser page using Selenium WebDriver."""
        if not driver:
            return PageClassificationResult(
                page_type=GlassdoorPageType.UNKNOWN,
                confidence=0.0,
                matched_signals=["null_driver"],
            )

        try:
            url = driver.current_url or ""
            title = driver.title or ""

            # Extract sample text and elements via lightweight JS script
            js_data = driver.execute_script('''
                var btns = Array.from(document.querySelectorAll("button, a[role='button']"))
                    .map(b => (b.innerText || b.textContent || '').trim())
                    .filter(t => t.length > 0 && t.length < 50);
                var inputs = Array.from(document.querySelectorAll("input"))
                    .map(i => i.name || i.id || i.placeholder || '')
                    .filter(t => t.length > 0);
                var hds = Array.from(document.querySelectorAll("h1, h2, h3"))
                    .map(h => (h.innerText || h.textContent || '').trim())
                    .filter(t => t.length > 0 && t.length < 80);
                var bodyText = (document.body ? document.body.innerText : '').substring(0, 4000);
                return {
                    buttons: btns.slice(0, 30),
                    inputs: inputs.slice(0, 20),
                    headings: hds.slice(0, 15),
                    text: bodyText,
                    htmlSnippet: document.documentElement.outerHTML.substring(0, 25000)
                };
            ''') or {}

            return cls.classify_dom_snapshot(
                url=url,
                title=title,
                html=js_data.get("htmlSnippet", ""),
                visible_text=js_data.get("text", ""),
                headings=js_data.get("headings", []),
                button_texts=js_data.get("buttons", []),
                input_names=js_data.get("inputs", []),
            )
        except Exception as e:
            return PageClassificationResult(
                page_type=GlassdoorPageType.UNKNOWN,
                confidence=0.1,
                matched_signals=[f"driver_error_{type(e).__name__}"],
                details={"error": str(e)},
            )
