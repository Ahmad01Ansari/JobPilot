'''
Indeed Application Coordinator
Orchestrates end-to-end job application lifecycle on Indeed India:
1. Detects application flow (Smart Apply vs External vs Already Applied).
2. Manages multi-window context switching.
3. Coordinates Form filling, Safety Gate evaluation, and Submission.
4. Reports metrics to ApplicationTracker.
'''

import json
import html
import re
import time
from typing import Optional, Tuple, Any, Dict, Callable, List
from selenium.webdriver.common.by import By

from modules.helpers import print_lg
from platforms.indeed.search import (
    IndeedJobItem,
    parse_indeed_salary,
    parse_indeed_experience,
    parse_indeed_work_style,
)
from platforms.indeed.form import IndeedForm
from platforms.indeed.safety_gate import IndeedSafetyGate, SafetyGateResult
from platforms.indeed.submitter import IndeedSubmitter
from platforms.indeed.captcha_handler import IndeedCaptchaHandler
from platforms.indeed.selectors import (
    APPLY_NOW_TRIGGERS,
    APPLY_EXTERNAL_TRIGGERS,
    DETAILS_PANE_SELECTORS,
    JOB_DESCRIPTION_SELECTORS,
    JOB_DETAILS_SECTION_SELECTORS,
    SALARY_DETAIL_SELECTORS,
    DETAIL_TITLE_SELECTORS,
    DETAIL_COMPANY_SELECTORS,
    DETAIL_LOCATION_SELECTORS,
)


class IndeedFlowDetector:
    """Classifies an Indeed job into SMART_APPLY, EXTERNAL, or UNAVAILABLE."""

    @staticmethod
    def detect_flow(driver: Any) -> Tuple[str, Optional[Any]]:
        """Inspects the right-side job details pane and returns (flow_type, apply_element)."""
        # 1. Check for Smart Apply ("Apply now")
        for sel in APPLY_NOW_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        return ("SMART_APPLY", el)
            except Exception:
                continue

        # 2. Check for External Apply ("Apply on company site")
        for sel in APPLY_EXTERNAL_TRIGGERS:
            try:
                elems = driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        return ("EXTERNAL", el)
            except Exception:
                continue

        # 3. Check for already applied badge
        try:
            applied_elems = driver.find_elements(By.XPATH, "//*[contains(text(), 'Applied') or contains(text(), 'You applied')]")
            if any(e.is_displayed() for e in applied_elems):
                return ("ALREADY_APPLIED", None)
        except Exception:
            pass

        return ("UNAVAILABLE", None)


def _get_elem_text(el: Any) -> str:
    """Safely extracts innerText, textContent, or .text attribute as string without raising or crashing on mocks."""
    if el is None:
        return ""
    try:
        val = el.get_attribute("innerText")
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    try:
        val = el.get_attribute("textContent")
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    try:
        val = getattr(el, "text", "")
        if isinstance(val, str) and val.strip():
            return val.strip()
    except Exception:
        pass
    return ""


def extract_external_portal_url(driver: Any, apply_elem: Optional[Any], job_id: str) -> Optional[str]:
    """Extracts external company application portal URL from apply element or Indeed redirect."""
    url = None
    if apply_elem:
        try:
            val = apply_elem.get_attribute("href")
            if isinstance(val, str) and val.strip():
                url = val.strip()
            if not url:
                parent = apply_elem.find_element(By.XPATH, "..")
                if getattr(parent, "tag_name", "") == "a":
                    pval = parent.get_attribute("href")
                    if isinstance(pval, str) and pval.strip():
                        url = pval.strip()
            if not url:
                dval = apply_elem.get_attribute("data-href") or apply_elem.get_attribute("data-url")
                if isinstance(dval, str) and dval.strip():
                    url = dval.strip()
            if not url:
                try:
                    inner_a = apply_elem.find_element(By.TAG_NAME, "a")
                    ival = inner_a.get_attribute("href")
                    if isinstance(ival, str) and ival.strip():
                        url = ival.strip()
                except Exception:
                    pass
        except Exception:
            pass

    if not url:
        try:
            res = driver.execute_script('''
                var btns = document.querySelectorAll("a, button, div[role='button']");
                for (var b of btns) {
                    var t = (b.innerText || b.textContent || '').trim().toLowerCase();
                    if (t.includes('apply on company site')) {
                        var h = b.getAttribute('href') || b.getAttribute('data-href');
                        if (h) return h;
                        var a = b.querySelector('a');
                        if (a && a.getAttribute('href')) return a.getAttribute('href');
                        var p = b.closest('a');
                        if (p && p.getAttribute('href')) return p.getAttribute('href');
                    }
                }
                return null;
            ''')
            if isinstance(res, str) and res.strip():
                url = res.strip()
        except Exception:
            pass

    if url and isinstance(url, str):
        if url.startswith("/"):
            url = "https://in.indeed.com" + url
    elif job_id:
        url = f"https://in.indeed.com/applystart?jk={job_id}"

    return url


def is_valid_job_description(desc: Optional[str], min_chars: int = 250) -> bool:
    """Validates that extracted job description is substantial (>= 250 chars) and not a stub or boilerplate."""
    if not desc or not isinstance(desc, str):
        return False
    clean = desc.strip()
    if len(clean) < min_chars:
        return False
    lower = clean.lower()
    reject_patterns = [
        "javascript must be enabled",
        "please enable cookies",
        "access to this page has been denied",
        "job not found",
        "this job has expired",
        "page not found",
        "loading job description",
    ]
    if any(p in lower for p in reject_patterns):
        return False
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    if len(lines) <= 2 and len(clean) < min_chars:
        return False
    return True


class IndeedApplier:
    """Coordinates the safe application process for a single Indeed job."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[Any] = None,
        safety_gate: Optional[IndeedSafetyGate] = None,
        submitter: Optional[IndeedSubmitter] = None,
        automation_bridge: Optional[Any] = None,
        bad_words: Optional[List[str]] = None,
    ):
        self.browser = browser
        self.driver = getattr(browser, "driver", browser)
        self.tracker = tracker
        self.safety_gate = safety_gate or IndeedSafetyGate()
        self.automation_bridge = automation_bridge
        self.captcha_handler = IndeedCaptchaHandler(browser, automation_bridge)
        self.submitter = submitter or IndeedSubmitter(
            browser,
            tracker,
            automation_bridge=automation_bridge,
            captcha_handler=self.captcha_handler,
        )
        self.form = IndeedForm(browser, captcha_handler=self.captcha_handler)
        if bad_words is not None:
            self.bad_words = list(bad_words)
        else:
            try:
                from modules.config_loader import get_platform
                cfg_plat = get_platform("indeed") or {}
                self.bad_words = list(cfg_plat.get("bad_words", []))
                if not self.bad_words:
                    import config.search as search_cfg
                    self.bad_words = list(getattr(search_cfg, "bad_words", []))
            except Exception:
                self.bad_words = []

    def _extract_jd_level1_inpage(self) -> str:
        """Level 1: Extracts Job Description from active split-view details pane or main DOM."""
        desc_text = ""
        try:
            res = self.driver.execute_script('''
                function getJD() {
                    // 1. Check embedded JSON-LD scripts on the page
                    var ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (var s of ldScripts) {
                        try {
                            var d = JSON.parse(s.innerText || s.textContent || '');
                            if (d && d.description && d.description.length > 50) {
                                var tmp = document.createElement('div');
                                tmp.innerHTML = d.description;
                                var t = (tmp.innerText || tmp.textContent || '').trim();
                                if (t.length > 80) return t;
                            }
                        } catch(e) {}
                    }

                    // 2. Check heading anchor ("Full job description" or "Job description")
                    var allHeadings = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, h6, div, span, p"));
                    var jdHeading = allHeadings.find(el => {
                        if (el.children.length > 2) return false;
                        var txt = (el.innerText || '').trim().toLowerCase();
                        return txt === "full job description" || txt === "job description";
                    });

                    if (jdHeading) {
                        var siblingTexts = [];
                        var cur = jdHeading.nextElementSibling;
                        while (cur) {
                            var st = (cur.innerText || cur.textContent || '').trim();
                            if (st) siblingTexts.push(st);
                            cur = cur.nextElementSibling;
                        }
                        if (siblingTexts.length > 0) {
                            var combined = siblingTexts.join('\\n\\n').trim();
                            if (combined.length > 50) return combined;
                        }

                        var parent = jdHeading.parentElement;
                        if (parent) {
                            var pt = (parent.innerText || parent.textContent || '').trim();
                            var bodyText = pt.replace(jdHeading.innerText, '').trim();
                            if (bodyText.length > 50) return bodyText;
                        }
                    }

                    // 3. Standalone viewjob heading sibling
                    var vHeading = document.querySelector('[data-testid="vj-job-description-heading"]');
                    if (vHeading && vHeading.nextElementSibling) {
                        var ht = (vHeading.nextElementSibling.innerText || vHeading.nextElementSibling.textContent || '').trim();
                        if (ht.length > 50) return ht;
                    }

                    // 4. Standard container selectors
                    var selectors = [
                        '#jobDescriptionText',
                        '[data-testid="jobsearch-JobDescriptionText"]',
                        '.jobsearch-jobDescriptionText',
                        '.jobsearch-JobComponent-description',
                        '#jobDescriptionSection',
                        '[data-testid="viewjob-job-content"]',
                        '[data-testid="jobsearch-ViewJobContent"]',
                        '.simple-job-description-html',
                        '.react-native-html-content',
                        'div.jobsearch-ViewJobBody',
                        '[data-testid="job-description"]',
                        '#vjs-desc',
                        '#vjs-jobinfo',
                        'div[id*="jobDescription" i]',
                        'div[class*="jobDescription" i]',
                        'div[class*="JobDescription" i]'
                    ];
                    for (var s of selectors) {
                        var el = document.querySelector(s);
                        if (el) {
                            var t = (el.innerText || el.textContent || '').trim();
                            if (t.length > 50) return t;
                        }
                    }

                    // 5. Right details pane wrapper extraction
                    var paneSelectors = [
                        '#jobsearch-ViewJobPaneWrapper',
                        '[data-testid="jobsearch-ViewjobPaneWrapper"]',
                        '[data-testid="jobsearch-ViewJobPaneWrapper"]',
                        'div.jobsearch-RightPane',
                        'div.fastviewjob',
                        'div#vjs-container',
                        '[data-testid="jobsearch-ViewJobPane"]',
                        'div.jobsearch-ViewJobPane'
                    ];
                    for (var ps of paneSelectors) {
                        var pane = document.querySelector(ps);
                        if (pane) {
                            var innerSelectors = [
                                '#jobDescriptionText',
                                '[data-testid="jobsearch-JobDescriptionText"]',
                                '.jobsearch-JobComponent-description',
                                '.simple-job-description-html',
                                '.react-native-html-content',
                                '[data-testid="viewjob-job-content"]',
                                '[data-testid="job-description"]'
                            ];
                            for (var isel of innerSelectors) {
                                var descInPane = pane.querySelector(isel);
                                if (descInPane) {
                                    var dt = (descInPane.innerText || descInPane.textContent || '').trim();
                                    if (dt.length > 50) return dt;
                                }
                            }
                        }
                    }

                    // 6. Check iframes via contentDocument
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var doc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            if (doc) {
                                for (var s of selectors) {
                                    var el = doc.querySelector(s);
                                    if (el) {
                                        var t = (el.innerText || el.textContent || '').trim();
                                        if (t.length > 50) return t;
                                    }
                                }
                            }
                        } catch(e) {}
                    }
                    return '';
                }
                return getJD();
            ''')
            if isinstance(res, str):
                desc_text = res.strip()
        except Exception as e:
            print_lg(f"[IndeedApplier] Level 1 JS extraction notice: {e}")

        # Selenium fallback with defined selectors if JS returned empty
        if not desc_text:
            for sel in JOB_DESCRIPTION_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        t = _get_elem_text(el)
                        if t and len(t) > len(desc_text):
                            desc_text = t
                    if desc_text and len(desc_text) > 50:
                        break
                except Exception:
                    continue

        return desc_text

    def _extract_jd_level2_viewjob_tab(self, job_id: str) -> Tuple[str, Dict[str, Any]]:
        """Level 2: Opens standalone viewjob page in a secondary tab and extracts full JD & metadata."""
        if not job_id:
            return ("", {})
        desc_text = ""
        extra_meta: Dict[str, Any] = {}
        orig_handle = None
        try:
            orig_handle = self.driver.current_window_handle
            viewjob_url = f"https://in.indeed.com/viewjob?jk={job_id}"
            self.driver.execute_script("window.open(arguments[0], '_blank');", viewjob_url)
            time.sleep(1.5)
            handles = self.driver.window_handles
            if len(handles) > 1:
                new_tab = [h for h in handles if h != orig_handle][-1]
                self.driver.switch_to.window(new_tab)

                # Wait up to 4s for JD container or JSON-LD to render
                for _ in range(8):
                    has_el = self.driver.execute_script("""
                        const el = document.getElementById("jobDescriptionText") ||
                                   document.querySelector("[data-testid='jobsearch-JobDescriptionText']") ||
                                   document.querySelector(".simple-job-description-html") ||
                                   document.querySelector("[data-testid='viewjob-job-content']") ||
                                   document.querySelector('script[type="application/ld+json"]');
                        return Boolean(el);
                    """)
                    if has_el:
                        break
                    time.sleep(0.5)

                res = self.driver.execute_script("""
                    // 1. Check JSON-LD
                    const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
                    for (const s of ldScripts) {
                        try {
                            const d = JSON.parse(s.innerText || s.textContent || '');
                            if (d && d.description && d.description.length > 50) {
                                const tmp = document.createElement('div');
                                tmp.innerHTML = d.description;
                                const t = (tmp.innerText || tmp.textContent || '').trim();
                                if (t.length > 80) return {desc: t, source: 'json-ld'};
                            }
                        } catch(e) {}
                    }

                    // 2. Check Standard Selectors
                    const selectors = [
                        '#jobDescriptionText',
                        '[data-testid="jobsearch-JobDescriptionText"]',
                        '.jobsearch-jobDescriptionText',
                        '.jobsearch-JobComponent-description',
                        '.simple-job-description-html',
                        '.react-native-html-content',
                        '[data-testid="viewjob-job-content"]',
                        '#jobDescriptionSection'
                    ];
                    for (const s of selectors) {
                        const el = document.querySelector(s);
                        if (el) {
                            const t = (el.innerText || el.textContent || '').trim();
                            if (t.length > 80) return {desc: t, source: s};
                        }
                    }

                    // 3. Heading Anchor fallback
                    const headings = Array.from(document.querySelectorAll("h1, h2, h3, h4, div")).filter(h => {
                        const t = (h.innerText || '').trim().toLowerCase();
                        return t === "full job description" || t === "job description";
                    });
                    for (const h of headings) {
                        if (h.parentElement) {
                            const pt = (h.parentElement.innerText || '').replace(h.innerText, '').trim();
                            if (pt.length > 80) return {desc: pt, source: 'heading'};
                        }
                    }

                    return {desc: '', source: 'none'};
                """)

                if res and isinstance(res, dict) and res.get("desc"):
                    desc_text = str(res["desc"]).strip()

                # Grab salary/metadata if present on standalone tab
                try:
                    sal_el = self.driver.execute_script("""
                        const salSelectors = ['#salaryInfoAndJobType', '[data-testid="jobsearch-JobDetailsSection-attribute"]', '.jobsearch-JobMetadataHeader-item'];
                        for (const s of salSelectors) {
                            const el = document.querySelector(s);
                            if (el && (el.innerText || '').trim()) return el.innerText.trim();
                        }
                        return '';
                    """)
                    if sal_el:
                        extra_meta["salary"] = sal_el
                except Exception:
                    pass

                self.driver.close()
                self.driver.switch_to.window(orig_handle)
        except Exception as e:
            print_lg(f"[IndeedApplier] Level 2 standalone viewjob extraction notice: {e}")
            try:
                if orig_handle and orig_handle in self.driver.window_handles:
                    self.driver.switch_to.window(orig_handle)
            except Exception:
                pass
        return (desc_text, extra_meta)

    def _extract_jd_level3_browser_fetch(self, job_id: str) -> str:
        """Level 3: Fetches viewjob HTML using in-session JavaScript fetch() and parses structured markup."""
        if not job_id:
            return ""
        try:
            fetch_script = """
                const callback = arguments[arguments.length - 1];
                const url = '/viewjob?jk=' + encodeURIComponent(arguments[0]) + '&viewtype=embedded';
                fetch(url, {credentials: 'include'})
                    .then(response => response.text())
                    .then(html => callback(html))
                    .catch(err => callback(''));
            """
            html_raw = self.driver.execute_async_script(fetch_script, job_id)
            if not html_raw or not isinstance(html_raw, str):
                return ""

            # Check JSON-LD in fetched HTML
            ld_matches = re.findall(r'<script[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', html_raw, re.DOTALL | re.IGNORECASE)
            for ld_str in ld_matches:
                try:
                    data = json.loads(ld_str.strip())
                    if isinstance(data, dict):
                        desc = data.get("description")
                        if desc and len(desc.strip()) > 80:
                            clean = re.sub(r'<[^>]+>', ' ', desc)
                            clean = html.unescape(clean)
                            clean = re.sub(r'\s+', ' ', clean).strip()
                            if len(clean) > 80:
                                return clean
                except Exception:
                    pass

            # Check container regex in fetched HTML
            container_m = re.search(r'<div[^>]*id=[\'"]jobDescriptionText[\'"][^>]*>(.*?)</div>\s*</div>', html_raw, re.DOTALL | re.IGNORECASE)
            if not container_m:
                container_m = re.search(r'<div[^>]*class=[\'"][^\'"]*jobDescriptionText[^\'"]*[\'"][^>]*>(.*?)</div>', html_raw, re.DOTALL | re.IGNORECASE)
            if container_m:
                raw_jd = container_m.group(1)
                clean = re.sub(r'<[^>]+>', '\n', raw_jd)
                clean = html.unescape(clean)
                lines = [l.strip() for l in clean.splitlines() if l.strip()]
                clean_jd = '\n'.join(lines)
                if len(clean_jd) > 80:
                    return clean_jd
        except Exception as e:
            print_lg(f"[IndeedApplier] Level 3 fetch notice: {e}")
        return ""

    def _extract_jd_level4_fallback(self, job: IndeedJobItem) -> str:
        """Level 4: Composes a structured fallback summary from available job card attributes."""
        lines = [f"{job.title} at {job.company}"]
        if job.location:
            lines.append(f"Location: {job.location}")
        if job.salary:
            lines.append(f"Compensation: {job.salary}")
        if job.experience_text:
            lines.append(f"Experience Required: {job.experience_text}")
        if job.description and len(job.description.strip()) > len(lines[0]):
            lines.append(f"\nRole Overview:\n{job.description.strip()}")
        return "\n".join(lines)

    def extract_job_details(self, job: IndeedJobItem) -> Dict[str, Any]:
        """Extracts complete Job Description, Salary, Experience, and Work Style from active details pane or page."""
        extracted: Dict[str, Any] = {}

        # 1. Job Description - Multilevel Extraction Pipeline
        desc_text = self._extract_jd_level1_inpage()
        level_used = "Level 1 (In-Page Split-View)"

        if not is_valid_job_description(desc_text) and job.job_id:
            print_lg(f"[IndeedApplier] Level 1 JD extraction invalid/empty for job '{job.job_id}'. Escalating to Level 2 (Standalone ViewJob tab)...")
            desc_text_l2, extra_meta = self._extract_jd_level2_viewjob_tab(job.job_id)
            if is_valid_job_description(desc_text_l2):
                desc_text = desc_text_l2
                level_used = "Level 2 (Standalone ViewJob Tab)"
                if extra_meta:
                    if not job.salary and extra_meta.get("salary"):
                        job.salary = extra_meta["salary"]
                    if not job.experience_text and extra_meta.get("experience_text"):
                        job.experience_text = extra_meta["experience_text"]

        if not is_valid_job_description(desc_text) and job.job_id:
            print_lg(f"[IndeedApplier] Level 2 JD extraction invalid/empty for job '{job.job_id}'. Escalating to Level 3 (In-Session Browser Fetch)...")
            desc_text_l3 = self._extract_jd_level3_browser_fetch(job.job_id)
            if is_valid_job_description(desc_text_l3):
                desc_text = desc_text_l3
                level_used = "Level 3 (Browser Session Fetch)"

        if not is_valid_job_description(desc_text):
            print_lg(f"[IndeedApplier] Level 3 JD extraction unavailable. Applying Level 4 Fallback (Card snippet & metadata)...")
            desc_text = self._extract_jd_level4_fallback(job)
            level_used = "Level 4 (Card Summary Fallback)"

        if is_valid_job_description(desc_text):
            job.description = desc_text
            extracted["description"] = desc_text
            print_lg(f"[IndeedApplier] Extracted Job Description ({len(desc_text)} chars via {level_used}).")
        else:
            job.description = desc_text
            extracted["description"] = desc_text
            print_lg(f"[IndeedApplier] Notice: Job description populated using best available summary ({len(desc_text)} chars via {level_used}).")

        # 2. Details Pane text / section for metadata via JS innerText
        details_text = ""
        try:
            res = self.driver.execute_script('''
                var selectors = [
                    '#salaryInfoAndJobType',
                    '#jobDetailsSection',
                    '[data-testid="jobsearch-JobDetailsSection-attribute"]',
                    '[data-testid="attribute_snippet_testid"]',
                    '.jobsearch-JobMetadataHeader-item',
                    '.jobsearch-JobInfoHeader-subtitle'
                ];
                var parts = [];
                for (var s of selectors) {
                    var els = document.querySelectorAll(s);
                    for (var el of els) {
                        var t = (el.innerText || el.textContent || '').trim();
                        if (t) parts.push(t);
                    }
                }
                return parts.join('\\n');
            ''')
            if isinstance(res, str):
                details_text = res.strip()
        except Exception:
            pass

        if not details_text:
            for sel in JOB_DETAILS_SECTION_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elems:
                        t = _get_elem_text(el)
                        if t:
                            details_text += "\n" + t
                except Exception:
                    continue

        # 3. Salary extraction
        sal_text = ""
        for sel in SALARY_DETAIL_SELECTORS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    t = _get_elem_text(el)
                    if t and any(c in t for c in ["₹", "$", "€", "£", "year", "month", "hour", "annum", "LPA"]):
                        sal_text = t
                        break
                if sal_text:
                    break
            except Exception:
                continue

        # If not found via specific salary selectors, search details_text or header
        if not sal_text and details_text and isinstance(details_text, str):
            sal_m = re.search(r'([₹$€£]\s*[\d,]+(?:\s*[-–—to]+\s*[₹$€£]?[\d,]+)?(?:\s*(?:a|per)\s*(?:year|month|hour|annum|yr|mo))?)', details_text)
            if sal_m:
                sal_text = sal_m.group(1).strip()

        # Clean sal_text to isolate the actual salary figure if it contains surrounding labels
        if sal_text:
            clean_m = re.search(r'([₹$€£]\s*[\d,]+(?:\s*[-–—to]+\s*[₹$€£]?[\d,]+)?(?:\s*(?:a|per)\s*(?:year|month|hour|annum|yr|mo))?)', sal_text)
            if clean_m:
                sal_text = clean_m.group(1).strip()

        if sal_text:
            job.salary = sal_text
            extracted["salary_text"] = sal_text
            min_sal, max_sal = parse_indeed_salary(sal_text)
            if min_sal is not None:
                job.salary_min = min_sal
                extracted["salary_min"] = min_sal
            if max_sal is not None:
                job.salary_max = max_sal
                extracted["salary_max"] = max_sal
            print_lg(f"[IndeedApplier] Extracted Salary: '{sal_text}' -> ({min_sal}, {max_sal})")

        # 4. Experience extraction
        search_corpus = f"{desc_text}\n{details_text}"
        exp_min, exp_max, exp_str = parse_indeed_experience(search_corpus)
        if exp_str:
            job.experience_text = exp_str
            job.required_experience_min = exp_min
            job.required_experience_max = exp_max
            extracted["experience_text"] = exp_str
            extracted["required_experience_min"] = exp_min
            extracted["required_experience_max"] = exp_max
            print_lg(f"[IndeedApplier] Extracted Experience: '{exp_str}' -> ({exp_min}, {exp_max})")

        # 5. Work Style
        work_style = parse_indeed_work_style(job.location, job.title, search_corpus)
        if work_style:
            job.work_style = work_style
            extracted["work_style"] = work_style

        # 6. Refine Company & Location if missing or generic
        if not job.company or job.company in ("Unknown Company", "Unknown Role"):
            for sel in DETAIL_COMPANY_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        t = _get_elem_text(elems[0])
                        if t:
                            job.company = t
                            extracted["company"] = job.company
                            break
                except Exception:
                    continue

        if not job.location or job.location in ("India", "Unknown Location", ""):
            for sel in DETAIL_LOCATION_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    if elems:
                        t = _get_elem_text(elems[0])
                        if t:
                            job.location = t
                            extracted["location"] = job.location
                            break
                except Exception:
                    continue

        # 7. Push to Tracker and Automation Bridge immediately
        if self.tracker:
            try:
                self.tracker.record_state(job.to_job(), "APPLYING")
            except Exception as e:
                print_lg(f"[IndeedApplier] Notice syncing rich details to tracker: {e}")

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
                        application_url=job.application_url or job.job_url,
                        description=job.description,
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

        return extracted

    def apply_to_job(
        self,
        job: IndeedJobItem,
        main_window: str,
        custom_resume_path: Optional[str] = None,
        stop_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, str]:
        """Executes safe application for given job item with cooperative pause/stop checks."""
        if stop_check and stop_check():
            return (False, "Operation paused or stopped by user.")

        # Ensure any leftover CAPTCHA flag from a previous job is cleared
        if self.automation_bridge and hasattr(self.automation_bridge, "reset_captcha_status"):
            self.automation_bridge.reset_captcha_status()

        print_lg(f"\n[IndeedApplier] Processing job: '{job.title}' at '{job.company}' (ID: {job.job_id})...")

        # 1. Click job card to display details pane
        if job.card_element:
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", job.card_element)
                time.sleep(0.5)
                # Click the job title link
                title_link = job.card_element.find_element(By.CSS_SELECTOR, "a.jcs-JobTitle")
                self.driver.execute_script("arguments[0].click();", title_link)
            except Exception:
                try:
                    self.driver.execute_script("arguments[0].click();", job.card_element)
                except Exception as e:
                    print_lg(f"[IndeedApplier] Failed to click card: {e}")
                    return (False, f"Could not select job card: {e}")

        # Active polling (up to 6s) for AJAX details pane or JD container to load
        for _ in range(12):
            has_jd = False
            try:
                has_jd = self.driver.execute_script('''
                    var el = document.querySelector("#jobDescriptionText") ||
                             document.querySelector("[data-testid='jobsearch-JobDescriptionText']") ||
                             document.querySelector(".jobsearch-jobDescriptionText") ||
                             document.querySelector(".jobsearch-JobComponent-description") ||
                             document.querySelector("#jobDescriptionSection") ||
                             document.querySelector(".simple-job-description-html") ||
                             document.querySelector(".react-native-html-content") ||
                             document.querySelector("[data-testid='vj-job-description-heading']") ||
                             document.querySelector("[data-testid='viewjob-job-content']") ||
                             document.querySelector("#vjs-container") ||
                             document.querySelector("#jobsearch-ViewJobPaneWrapper") ||
                             document.querySelector("[data-testid='jobsearch-ViewjobPaneWrapper']") ||
                             document.querySelector("div.jobsearch-RightPane");
                    if (el && (el.innerText || el.textContent || '').trim().length > 20) return true;
                    var heading = Array.from(document.querySelectorAll("h1, h2, h3, h4, h5, div, span")).find(h => {
                        var t = (h.innerText || '').trim().toLowerCase();
                        return t === "full job description" || t === "job description";
                    });
                    if (heading && heading.parentElement && heading.parentElement.innerText.length > 20) return true;
                    var iframes = document.querySelectorAll("iframe");
                    for (var i = 0; i < iframes.length; i++) {
                        try {
                            var doc = iframes[i].contentDocument || iframes[i].contentWindow.document;
                            if (doc && (doc.getElementById("jobDescriptionText") || doc.querySelector("[data-testid='jobsearch-JobDescriptionText']"))) return true;
                        } catch(e) {}
                    }
                    return false;
                ''')
            except Exception:
                pass
            if has_jd:
                break
            time.sleep(0.5)

        if stop_check and stop_check():
            return (False, "Operation paused or stopped by user.")

        # Extract full Job Description, Salary, Experience, etc. from details pane
        try:
            self.extract_job_details(job)
        except Exception as e:
            print_lg(f"[IndeedApplier] Notice extracting details: {e}")

        # Check Description Filter / Bad Words Blacklist
        if self.bad_words and job.description:
            desc_lower = job.description.lower()
            matched_bad = None
            for bw in self.bad_words:
                bw_clean = bw.strip().lower()
                if bw_clean and bw_clean in desc_lower:
                    matched_bad = bw.strip()
                    break
            if matched_bad:
                skip_msg = f"Job description contains blacklisted phrase: '{matched_bad}'"
                print_lg(f"[IndeedApplier] Description Filter SKIP for '{job.title}': {skip_msg}")
                job_obj = job.to_job()
                if self.tracker:
                    self.tracker.record_state(job_obj, "SKIPPED", skip_reason=skip_msg)
                return (False, skip_msg)

        if stop_check and stop_check():
            return (False, "Operation paused or stopped by user.")

        # 2. Detect Flow Type
        flow_type, apply_elem = IndeedFlowDetector.detect_flow(self.driver)
        print_lg(f"[IndeedApplier] Detected apply flow: {flow_type}")

        if flow_type == "ALREADY_APPLIED":
            print_lg(f"[IndeedApplier] Job '{job.job_id}' is already applied. Skipping.")
            return (False, "Already applied.")

        if flow_type == "EXTERNAL":
            ext_url = extract_external_portal_url(self.driver, apply_elem, job.job_id)
            job.application_url = ext_url
            job.is_easy_apply = False
            print_lg(f"[IndeedApplier] Job '{job.job_id}' requires EXTERNAL company site apply. Captured portal link: {ext_url}")
            job_obj = job.to_job()
            if self.tracker:
                try:
                    self.tracker.record_state(
                        job_obj,
                        "EXTERNAL",
                        reason=f"External company site application: {ext_url}",
                        application_type="COMPANY_PORTAL",
                    )
                except Exception as ex:
                    print_lg(f"[IndeedApplier] Notice recording external to tracker: {ex}")
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
                            application_method="COMPANY_PORTAL",
                            application_url=ext_url,
                            description=job.description,
                            experience_text=job.experience_text,
                            salary_text=job.salary,
                        )
                    )
                except Exception:
                    pass
            return (False, f"External company site application: {ext_url}")

        if flow_type != "SMART_APPLY" or not apply_elem:
            print_lg(f"[IndeedApplier] Apply button not available for job '{job.job_id}'.")
            return (False, "Apply button not available.")

        if stop_check and stop_check():
            return (False, "Operation paused or stopped by user.")

        # 3. Launch Smart Apply in new tab
        pre_handles = self.driver.window_handles

        # Target clickable ancestor if div
        click_target = apply_elem
        try:
            parent = apply_elem.find_element(By.XPATH, "..")
            if parent.tag_name in ["button", "a", "div"]:
                click_target = parent
        except Exception:
            pass

        print_lg("[IndeedApplier] Launching Smart Apply...")
        try:
            click_target.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", click_target)

        # Wait up to 8s for new tab
        app_window = None
        start_wait = time.time()
        while time.time() - start_wait < 8:
            if stop_check and stop_check():
                return (False, "Operation paused or stopped by user.")
            time.sleep(1)
            cur_handles = self.driver.window_handles
            if len(cur_handles) > len(pre_handles):
                app_window = [h for h in cur_handles if h not in pre_handles][0]
                break

        if not app_window:
            print_lg("[IndeedApplier] Application opened in current window or failed to launch.")
            app_window = self.driver.current_window_handle

        print_lg(f"[IndeedApplier] Switched to application tab: {app_window}")
        self.driver.switch_to.window(app_window)
        time.sleep(2)

        answers_log = []

        try:
            # 4. Step through questionnaire form
            prev_step_type = None
            prev_step_url = None

            for step_num in range(1, 10):
                if stop_check and stop_check():
                    print_lg("[IndeedApplier] Stop/pause check active. Halting form step.")
                    return (False, "Operation paused or stopped by user.")

                step_type = self.form.detect_step_type()

                # If detected step is identical to previous step and URL hasn't changed,
                # wait briefly in case the DOM is still transitioning from the previous click
                if step_num > 1 and step_type == prev_step_type and self.driver.current_url == prev_step_url:
                    time.sleep(1.5)
                    step_type = self.form.detect_step_type()

                prev_step_type = step_type
                prev_step_url = self.driver.current_url
                print_lg(f"[IndeedApplier] Form Step #{step_num} detected as: {step_type}")

                if step_type == "CONFIRMATION":
                    print_lg("[IndeedApplier] Instant confirmation detected!")
                    return (True, "Application confirmed.")

                if step_type == "REVIEW":
                    print_lg("[IndeedApplier] Review module reached.")
                    break

                if step_type == "CAPTCHA":
                    print_lg("[IndeedApplier] CAPTCHA step detected during questionnaire!")
                    solved = self.captcha_handler.handle_captcha(
                        self.driver,
                        job_title=job.title,
                        company=job.company,
                        timeout=60,
                        stop_check=stop_check,
                        automation_bridge=self.automation_bridge,
                    )
                    if not solved:
                        return (False, "CAPTCHA challenge encountered on Indeed. Manual intervention required.")
                    time.sleep(2)
                    continue

                if step_type == "CONTACT_INFO":
                    self.form.fill_contact_info()
                elif step_type == "LOCATION":
                    self.form.fill_location_info()
                elif step_type == "RESUME":
                    self.form.handle_resume_selection(custom_resume_path)
                elif step_type == "QUESTIONS":
                    ans = self.form.answer_screening_questions(job.title, job.company)
                    answers_log.extend(ans)

                if stop_check and stop_check():
                    return (False, "Operation paused or stopped by user.")

                # Check if review submit button is already present on this step
                if self.form.is_review_page_ready():
                    print_lg("[IndeedApplier] Final submit button is present on step.")
                    break

                # Advance to next step
                advanced = self.form.advance_to_next_step()
                if not advanced:
                    print_lg("[IndeedApplier] No advance button found immediately. Checking if review page ready or transition pending...")
                    # Poll up to 6 seconds for transition or late-rendering button
                    for poll_idx in range(6):
                        time.sleep(1)
                        if self.form.is_review_page_ready():
                            advanced = True
                            break
                        if self.form.detect_step_type() == "CONFIRMATION":
                            return (True, "Application confirmed.")
                        # Scroll down in case button is below the fold
                        try:
                            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        except Exception:
                            pass
                        if self.form.advance_to_next_step():
                            advanced = True
                            break

                    if self.form.is_review_page_ready():
                        break

                    if not advanced:
                        print_lg("[IndeedApplier] Form step could not advance after retries. Halting application.")
                        return (False, "Could not advance form step.")

                if stop_check and stop_check():
                    return (False, "Operation paused or stopped by user.")

                time.sleep(1)

            if stop_check and stop_check():
                return (False, "Operation paused or stopped by user.")

            # 5. Evaluate Safety Gate
            gate_res: SafetyGateResult = self.safety_gate.evaluate(
                job_title=job.title,
                company=job.company,
                answers=answers_log,
                job_metadata={"job_id": job.job_id, "location": job.location}
            )

            if not gate_res.approved:
                print_lg(f"[IndeedApplier] Safety Gate halted submission: {gate_res.reason}")
                return (False, gate_res.reason)

            if stop_check and stop_check():
                return (False, "Operation paused or stopped by user.")

            # 6. Execute Final Submission
            success, msg = self.submitter.submit_application(
                app_window=app_window,
                main_window=main_window,
                job_title=job.title,
                company=job.company,
                stop_check=stop_check,
            )

            if not success and ("captcha" in msg.lower() or "manual" in msg.lower()):
                if self.tracker:
                    try:
                        self.tracker.record_state(
                            job.to_job(),
                            "MANUAL_REQUIRED",
                            reason=msg,
                            application_type="EASY_APPLY",
                        )
                    except Exception as ex:
                        print_lg(f"[IndeedApplier] Notice recording MANUAL_REQUIRED to tracker: {ex}")

            return (success, msg)

        finally:
            # Guarantee tab closure and return to main window
            try:
                if app_window in self.driver.window_handles and app_window != main_window:
                    self.driver.switch_to.window(app_window)
                    self.driver.close()
            except Exception:
                pass

            try:
                self.driver.switch_to.window(main_window)
            except Exception:
                pass
