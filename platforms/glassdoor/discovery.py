"""
Glassdoor Discovery Runner
Captures live DOM state, discovers job cards, detail panels, application CTAs,
classifies the page, redacts sensitive credentials, and produces human-readable
discovery reports with structured artifacts in debug/glassdoor/<timestamp>/.
"""

from __future__ import annotations
import os
import json
import time
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict

from platforms.glassdoor.page_classifier import GlassdoorPageClassifier, GlassdoorPageType


SENSITIVE_PATTERNS = [
    re.compile(r'password["\']?\s*[:=]\s*["\']?[^"\'\s&]+', re.IGNORECASE),
    re.compile(r'session_id["\']?\s*[:=]\s*["\']?[^"\'\s&]+', re.IGNORECASE),
    re.compile(r'bearer\s+[a-zA-Z0-9_\-\.]+', re.IGNORECASE),
    re.compile(r'cookie["\']?\s*[:=]\s*["\']?[^"\'\s;]+', re.IGNORECASE),
]


def redact_sensitive_text(text: Any) -> str:
    """Redacts passwords, tokens, cookies, and secrets from diagnostic dumps."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    sanitized = text
    for pattern in SENSITIVE_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
    return sanitized


@dataclass
class JobCardCandidate:
    candidate_index: int
    title: str
    company: str
    location: str
    link: str
    job_id: str
    is_easy_apply: bool
    salary: Optional[str] = None
    rating: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8


@dataclass
class JobDetailCandidate:
    title: str
    company: str
    location: str
    description_length: int
    description_preview: str
    apply_cta_text: Optional[str] = None
    application_method: str = "UNKNOWN"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlassdoorDiscoveryReport:
    timestamp: str
    url: str
    title: str
    viewport: Dict[str, int]
    page_type: str
    page_type_confidence: float
    matched_signals: List[str]
    detected_features: Dict[str, bool]
    job_cards: List[JobCardCandidate]
    job_detail: Optional[JobDetailCandidate]
    buttons_count: int
    links_count: int
    inputs_count: int
    iframes_count: int
    artifacts_dir: str

    def to_human_readable(self) -> str:
        """Formats discovery report according to JobPilot specification."""
        lines = [
            "============================================================",
            "GLASSDOOR REAL-TIME UI DISCOVERY REPORT",
            "============================================================",
            f"TIMESTAMP: {self.timestamp}",
            f"URL: {self.url}",
            f"TITLE: {self.title}",
            f"PAGE TYPE: {self.page_type} (Confidence: {self.page_type_confidence:.2f})",
            "",
            "Detected Features:",
        ]
        for feat, present in self.detected_features.items():
            mark = "[✓]" if present else "[ ]"
            lines.append(f"  {mark} {feat.replace('_', ' ').title()}")

        lines.extend([
            "",
            f"JOB CARD CANDIDATES ({len(self.job_cards)} discovered):",
            "------------------------------------------------------------",
        ])
        for card in self.job_cards[:10]:
            lines.extend([
                f"Candidate {card.candidate_index + 1}:",
                f"  Title:       {card.title}",
                f"  Company:     {card.company}",
                f"  Location:    {card.location}",
                f"  Job ID:      {card.job_id}",
                f"  Link:        {card.link}",
                f"  Easy Apply:  {card.is_easy_apply}",
                f"  Salary:      {card.salary or 'N/A'}",
                f"  Confidence:  {card.confidence:.2f}",
                "",
            ])
        if len(self.job_cards) > 10:
            lines.append(f"  ... and {len(self.job_cards) - 10} more job card candidates.")

        lines.extend([
            "",
            "DETAIL PAGE CANDIDATE:",
            "------------------------------------------------------------",
        ])
        if self.job_detail:
            lines.extend([
                f"Title:              {self.job_detail.title}",
                f"Company:            {self.job_detail.company}",
                f"Location:           {self.job_detail.location}",
                f"Description Length: {self.job_detail.description_length} chars",
                f"Apply CTA:          {self.job_detail.apply_cta_text or 'None detected'}",
                f"Application Method: {self.job_detail.application_method}",
                f"Description Snippet: {self.job_detail.description_preview[:150]}...",
            ])
        else:
            lines.append("No active job detail panel detected in current DOM.")

        lines.extend([
            "",
            f"Diagnostic Artifacts Saved To: {self.artifacts_dir}",
            "============================================================",
        ])
        return "\n".join(lines)


class GlassdoorDiscoveryRunner:
    """Executes non-destructive discovery and observation of real Glassdoor runtime DOM."""

    def __init__(self, browser: Any, base_debug_dir: str = "debug/glassdoor"):
        self.browser = browser
        self.base_debug_dir = base_debug_dir

    @property
    def driver(self):
        if hasattr(self.browser, "execute_script"):
            return self.browser
        return getattr(self.browser, "driver", self.browser)

    def run_discovery(self, custom_name: Optional[str] = None) -> GlassdoorDiscoveryReport:
        """Inspects live browser DOM, extracts structured candidate elements, and saves sanitized artifacts."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder_name = f"{ts}_{custom_name}" if custom_name else ts
        out_dir = os.path.join(self.base_debug_dir, folder_name)
        os.makedirs(out_dir, exist_ok=True)

        url = self.driver.current_url or ""
        title = self.driver.title or ""

        # Viewport measurement
        viewport = {"width": 1280, "height": 800}
        try:
            viewport = self.driver.execute_script('''
                return {
                    width: window.innerWidth || document.documentElement.clientWidth || 0,
                    height: window.innerHeight || document.documentElement.clientHeight || 0
                };
            ''')
        except Exception:
            pass

        # 1. Capture Full DOM HTML (Sanitized)
        raw_html = ""
        try:
            raw_html = self.driver.page_source or ""
        except Exception:
            pass
        sanitized_html = redact_sensitive_text(raw_html)
        with open(os.path.join(out_dir, "page.html"), "w", encoding="utf-8") as f:
            f.write(sanitized_html)

        # 2. Capture Screenshot
        png_path = os.path.join(out_dir, "page.png")
        try:
            self.driver.save_screenshot(png_path)
        except Exception:
            pass

        # 3. Comprehensive JavaScript DOM Observation
        dom_data = self.driver.execute_script('''
            function clean(str) {
                return (str || '').replace(/\\s+/g, ' ').trim();
            }

            // A. Headings
            var headings = Array.from(document.querySelectorAll("h1, h2, h3, h4"))
                .map(h => ({ tag: h.tagName, text: clean(h.innerText), id: h.id || null }))
                .filter(h => h.text.length > 0);

            // B. Buttons and CTA candidates
            var buttons = Array.from(document.querySelectorAll("button, a[role='button'], [data-test*='button'], [data-test*='apply']"))
                .map(b => ({
                    tag: b.tagName,
                    text: clean(b.innerText || b.textContent),
                    dataTest: b.getAttribute('data-test') || null,
                    ariaLabel: b.getAttribute('aria-label') || null,
                    disabled: b.disabled || false,
                    className: b.className || null,
                    visible: (b.offsetWidth > 0 && b.offsetHeight > 0)
                }))
                .filter(b => b.visible && (b.text.length > 0 || b.ariaLabel));

            // C. Inputs
            var inputs = Array.from(document.querySelectorAll("input, textarea, select"))
                .map(i => ({
                    tag: i.tagName,
                    type: i.type || null,
                    name: i.name || null,
                    id: i.id || null,
                    placeholder: i.placeholder || null,
                    valueLength: (i.value || '').length,
                    ariaLabel: i.getAttribute('aria-label') || null,
                    required: i.required || false,
                    visible: (i.offsetWidth > 0 && i.offsetHeight > 0)
                }));

            // D. Links
            var links = Array.from(document.querySelectorAll("a[href]"))
                .slice(0, 150)
                .map(a => ({
                    text: clean(a.innerText).substring(0, 100),
                    href: a.href,
                    dataTest: a.getAttribute('data-test') || null
                }));

            // E. Iframes
            var iframes = Array.from(document.querySelectorAll("iframe"))
                .map(f => ({
                    id: f.id || null,
                    name: f.name || null,
                    src: f.src || null,
                    title: f.title || null
                }));

            // F. Body visible text
            var visibleText = document.body ? clean(document.body.innerText) : "";

            // G. Job Card Candidates (Multi-heuristic detection)
            var cardNodes = Array.from(document.querySelectorAll(
                "ul[data-test='job-listing-list'] > li, li[data-test='jobListing'], article[data-test='job-listing-wrapper'], div[class*='JobCard'], div.jobCard"
            ));

            var jobCards = cardNodes.map((card, idx) => {
                var titleEl = card.querySelector("[data-test='job-title'], a[data-test='job-title'], h2, h3, a");
                var compEl = card.querySelector("[data-test='employer-name'], span[class*='employerName'], div[class*='employer']");
                var locEl = card.querySelector("[data-test='job-location'], span[class*='location'], div[class*='location']");
                var salEl = card.querySelector("[data-test='detailSalary'], span[class*='salary']");
                var ratEl = card.querySelector("[data-test='rating-headline'], span[class*='rating']");
                var cardText = (card.innerText || '').toLowerCase();
                var hasEasyApply = cardText.includes('easy apply') || !!card.querySelector("[data-test*='easyApply'], [data-test*='easy-apply']");
                var linkEl = card.querySelector("a[href*='/job'], a[href]");
                var href = linkEl ? linkEl.href : "";
                var jid = card.getAttribute('data-jobid') || card.getAttribute('data-id') || "";
                if (!jid && href) {
                    var m = href.match(/jl=(\\d+)|jobListingId=(\\d+)/);
                    if (m) jid = m[1] || m[2];
                }

                return {
                    candidateIndex: idx,
                    title: titleEl ? clean(titleEl.innerText) : "",
                    company: compEl ? clean(compEl.innerText) : "",
                    location: locEl ? clean(locEl.innerText) : "",
                    salary: salEl ? clean(salEl.innerText) : null,
                    rating: ratEl ? clean(ratEl.innerText) : null,
                    link: href,
                    jobId: jid || ("discovered_" + idx),
                    isEasyApply: hasEasyApply
                };
            }).filter(c => c.title.length > 0);

            // H. Job Detail Candidate
            var detailPane = document.querySelector(
                "div[data-test='job-details'], div[class*='JobDetails'], #JobDescriptionContainer, #jobDescriptionText, main[class*='JobDetails']"
            );
            var detailCandidate = null;
            if (detailPane) {
                var dTitle = detailPane.querySelector("h1, h2, [data-test='job-title']");
                var dComp = detailPane.querySelector("[data-test='employer-name'], a[data-test='employer-name']");
                var dLoc = detailPane.querySelector("[data-test='location'], span[data-test='location']");
                var dDesc = detailPane.querySelector("#jobDescriptionText, [data-test='jobDescriptionContent'], [class*='jobDescription']");
                var dApply = detailPane.querySelector("button[data-test='easyApply'], button[data-test='apply-button'], button[class*='apply']");

                var descText = dDesc ? clean(dDesc.innerText) : "";
                var applyText = dApply ? clean(dApply.innerText) : null;
                var appMethod = "EXTERNAL";
                if (applyText && applyText.toLowerCase().includes("easy apply")) {
                    appMethod = "DIRECT_EASY_APPLY";
                }

                detailCandidate = {
                    title: dTitle ? clean(dTitle.innerText) : "",
                    company: dComp ? clean(dComp.innerText) : "",
                    location: dLoc ? clean(dLoc.innerText) : "",
                    descriptionLength: descText.length,
                    descriptionPreview: descText.substring(0, 300),
                    applyCtaText: applyText,
                    applicationMethod: appMethod
                };
            }

            return {
                headings: headings,
                buttons: buttons,
                inputs: inputs,
                links: links,
                iframes: iframes,
                visibleText: visibleText,
                jobCards: jobCards,
                jobDetail: detailCandidate
            };
        ''') or {}

        if not isinstance(dom_data, dict):
            dom_data = {}

        # 4. Save JSON and Text Artifacts (Redacted)
        with open(os.path.join(out_dir, "visible_text.txt"), "w", encoding="utf-8") as f:
            f.write(redact_sensitive_text(dom_data.get("visibleText", "")))

        with open(os.path.join(out_dir, "buttons.json"), "w", encoding="utf-8") as f:
            json.dump(dom_data.get("buttons", []), f, indent=2)

        with open(os.path.join(out_dir, "inputs.json"), "w", encoding="utf-8") as f:
            json.dump(dom_data.get("inputs", []), f, indent=2)

        with open(os.path.join(out_dir, "links.json"), "w", encoding="utf-8") as f:
            json.dump(dom_data.get("links", []), f, indent=2)

        with open(os.path.join(out_dir, "iframes.json"), "w", encoding="utf-8") as f:
            json.dump(dom_data.get("iframes", []), f, indent=2)

        # 5. Classify the page
        classification = GlassdoorPageClassifier.classify_dom_snapshot(
            url=url,
            title=title,
            html=raw_html,
            visible_text=dom_data.get("visibleText", ""),
            headings=[h.get("text", "") for h in dom_data.get("headings", []) if h.get("text")],
            button_texts=[b.get("text", "") for b in dom_data.get("buttons", []) if b.get("text")],
            input_names=[(i.get("name") or i.get("id") or "") for i in dom_data.get("inputs", []) if (i.get("name") or i.get("id"))],
        )

        seen_job_ids = set()
        job_cards_list = []
        for c in dom_data.get("jobCards", []):
            jid = c.get("jobId")
            if jid and jid in seen_job_ids:
                continue
            if jid:
                seen_job_ids.add(jid)
            job_cards_list.append(
                JobCardCandidate(
                    candidate_index=len(job_cards_list),
                    title=c["title"],
                    company=c["company"],
                    location=c["location"],
                    link=c["link"],
                    job_id=c["jobId"],
                    is_easy_apply=c["isEasyApply"],
                    salary=c.get("salary"),
                    rating=c.get("rating"),
                )
            )

        detail_cand = None
        if dom_data.get("jobDetail"):
            d = dom_data["jobDetail"]
            detail_cand = JobDetailCandidate(
                title=d.get("title", ""),
                company=d.get("company", ""),
                location=d.get("location", ""),
                description_length=d.get("descriptionLength", 0),
                description_preview=d.get("descriptionPreview", ""),
                apply_cta_text=d.get("applyCtaText"),
                application_method=d.get("applicationMethod", "UNKNOWN"),
            )

        detected_features = {
            "job_result_list": len(job_cards_list) > 0,
            "job_cards": len(job_cards_list) > 0,
            "job_detail_panel": detail_cand is not None and detail_cand.description_length > 0,
            "search_box": any("job title" in (i.get("placeholder") or "").lower() or "keyword" in (i.get("name") or "").lower() for i in dom_data.get("inputs", [])),
            "apply_cta": detail_cand is not None and detail_cand.apply_cta_text is not None,
            "application_form": classification.page_type in (GlassdoorPageType.APPLICATION_FORM, GlassdoorPageType.APPLICATION_STEP),
            "login_required": classification.page_type == GlassdoorPageType.LOGIN,
            "captcha_challenge": classification.page_type == GlassdoorPageType.CAPTCHA,
        }

        report = GlassdoorDiscoveryReport(
            timestamp=ts,
            url=url,
            title=title,
            viewport=viewport,
            page_type=classification.page_type.value,
            page_type_confidence=classification.confidence,
            matched_signals=classification.matched_signals,
            detected_features=detected_features,
            job_cards=job_cards_list,
            job_detail=detail_cand,
            buttons_count=len(dom_data.get("buttons", [])),
            links_count=len(dom_data.get("links", [])),
            inputs_count=len(dom_data.get("inputs", [])),
            iframes_count=len(dom_data.get("iframes", [])),
            artifacts_dir=out_dir,
        )

        with open(os.path.join(out_dir, "discovery.json"), "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, default=str)

        human_text = report.to_human_readable()
        with open(os.path.join(out_dir, "discovery_report.txt"), "w", encoding="utf-8") as f:
            f.write(human_text)

        return report
