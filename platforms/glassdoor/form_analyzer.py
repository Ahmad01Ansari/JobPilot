"""
Glassdoor Application Form Analyzer & Step Discoverer
Performs live DOM inspection on active application modal or child window:
1. Dynamic step categorization (CONTACT_INFO, RESUME_UPLOAD, WORK_HISTORY, QUESTIONS, REVIEW, CONFIRMATION).
2. Semantic field discovery (name, phone, email, location, custom questions, file uploads).
3. Read-back verification (FIND -> FILL -> READ BACK -> VERIFY).
4. Validation error detection.
5. Re-analyzes on every step to prevent stale element reference errors.
"""

from __future__ import annotations
import re
import time
import logging
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from selenium.webdriver.common.by import By

from modules.helpers import print_lg

logger = logging.getLogger(__name__)


class FormStepCategory(Enum):
    CONTACT_INFO = "CONTACT_INFO"
    RESUME_UPLOAD = "RESUME_UPLOAD"
    WORK_HISTORY = "WORK_HISTORY"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    REVIEW = "REVIEW"
    CONFIRMATION = "CONFIRMATION"
    UNKNOWN = "UNKNOWN"


@dataclass
class FormFieldDescriptor:
    semantic_name: str
    label_text: str
    field_type: str  # text, email, tel, select, radio, checkbox, file
    selector: str
    is_required: bool = False
    current_value: Optional[str] = None
    options: List[str] = field(default_factory=list)


@dataclass
class StepAnalysisResult:
    step_category: FormStepCategory
    step_title: str
    progress_percentage: Optional[int] = None
    fields: List[FormFieldDescriptor] = field(default_factory=list)
    has_validation_errors: bool = False
    error_messages: List[str] = field(default_factory=list)
    is_review_step: bool = False
    can_proceed: bool = True
    can_submit: bool = False


class GlassdoorFormAnalyzer:
    """Discovers, maps, and verifies form fields dynamically on each application step."""

    @classmethod
    def analyze_step(cls, driver: Any) -> StepAnalysisResult:
        """Inspects the current active form DOM and extracts structured field mappings."""
        if not driver:
            return StepAnalysisResult(
                step_category=FormStepCategory.UNKNOWN,
                step_title="Unavailable",
                can_proceed=False,
            )

        try:
            dom_data = driver.execute_script('''
                function clean(s) { return (s || '').replace(/\\s+/g, ' ').trim(); }

                var title = "";
                var h = document.querySelector("h1, h2, h3, [class*='modalTitle'], [class*='Header_title']");
                if (h) title = clean(h.innerText);

                // Detect validation errors
                var errEls = document.querySelectorAll(
                    "[class*='error' i], [class*='Error' i], [role='alert'], [data-test*='error'], p[id*='error']"
                );
                var errors = [];
                for (var e of errEls) {
                    var t = clean(e.innerText);
                    if (t.length > 5 && t.length < 200 && e.offsetWidth > 0) errors.push(t);
                }

                // Detect fields
                var fieldList = [];
                var inputs = Array.from(document.querySelectorAll("input, select, textarea"));
                for (var inp of inputs) {
                    if (inp.type === 'hidden') continue;
                    if (inp.offsetWidth === 0 && inp.offsetHeight === 0 && inp.type !== 'file') continue;

                    var lbl = "";
                    if (inp.id) {
                        var lEl = document.querySelector("label[for='" + inp.id + "']");
                        if (lEl) lbl = clean(lEl.innerText);
                    }
                    if (!lbl && inp.closest("label")) {
                        lbl = clean(inp.closest("label").innerText);
                    }
                    if (!lbl) lbl = inp.getAttribute('aria-label') || inp.placeholder || inp.name || "";

                    var fType = inp.tagName.toLowerCase() === 'select' ? 'select' :
                                (inp.tagName.toLowerCase() === 'textarea' ? 'textarea' : (inp.type || 'text'));

                    var opts = [];
                    if (fType === 'select') {
                        opts = Array.from(inp.options).map(o => clean(o.text)).filter(t => t.length > 0);
                    }

                    fieldList.push({
                        name: inp.name || inp.id || "",
                        label: lbl,
                        type: fType,
                        id: inp.id || "",
                        required: inp.required || inp.getAttribute('aria-required') === 'true',
                        value: (inp.value || '').substring(0, 100),
                        options: opts
                    });
                }

                // Buttons
                var btns = Array.from(document.querySelectorAll("button, input[type='submit']"))
                    .map(b => clean(b.innerText || b.value || ''))
                    .filter(t => t.length > 0);

                var isReview = title.toLowerCase().includes("review") ||
                               btns.some(b => /submit|send application/i.test(b));

                return {
                    title: title,
                    errors: errors,
                    fields: fieldList,
                    buttons: btns,
                    isReview: isReview,
                    url: window.location.href
                };
            ''') or {}

            raw_title = dom_data.get("title", "")
            fields_data = dom_data.get("fields", [])
            errors = dom_data.get("errors", [])
            is_review = bool(dom_data.get("isReview", False))

            # Categorize step
            title_lower = raw_title.lower()
            if is_review or "review" in title_lower or "review your application" in title_lower:
                step_cat = FormStepCategory.REVIEW
            elif any(f.get("type") == "file" for f in fields_data) or "resume" in title_lower:
                step_cat = FormStepCategory.RESUME_UPLOAD
            elif any("phone" in f.get("label", "").lower() or "email" in f.get("label", "").lower() for f in fields_data):
                step_cat = FormStepCategory.CONTACT_INFO
            elif len(fields_data) > 0:
                step_cat = FormStepCategory.QUESTIONNAIRE
            else:
                step_cat = FormStepCategory.UNKNOWN

            descriptors = []
            for fd in fields_data:
                # Semantic mapping
                lbl = fd.get("label", "").lower()
                sem_name = "unknown"
                if "first name" in lbl or "given name" in lbl:
                    sem_name = "first_name"
                elif "last name" in lbl or "surname" in lbl:
                    sem_name = "last_name"
                elif "email" in lbl:
                    sem_name = "email"
                elif "phone" in lbl or "mobile" in lbl or "contact number" in lbl:
                    sem_name = "phone"
                elif "city" in lbl or "location" in lbl:
                    sem_name = "city"
                elif "resume" in lbl or fd.get("type") == "file":
                    sem_name = "resume_file"
                else:
                    sem_name = re.sub(r'[^a-zA-Z0-9_]+', '_', lbl).strip('_')[:30] or "field"

                descriptors.append(FormFieldDescriptor(
                    semantic_name=sem_name,
                    label_text=fd.get("label", ""),
                    field_type=fd.get("type", "text"),
                    selector=f"#{fd['id']}" if fd.get("id") else f"[name='{fd.get('name')}']",
                    is_required=bool(fd.get("required")),
                    current_value=fd.get("value"),
                    options=fd.get("options", []),
                ))

            return StepAnalysisResult(
                step_category=step_cat,
                step_title=raw_title or step_cat.value,
                fields=descriptors,
                has_validation_errors=len(errors) > 0,
                error_messages=errors,
                is_review_step=is_review,
                can_proceed=True,
                can_submit=is_review,
            )
        except Exception as e:
            logger.debug(f"[FormAnalyzer] Step analysis error: {e}")
            return StepAnalysisResult(
                step_category=FormStepCategory.UNKNOWN,
                step_title="Error",
                can_proceed=False,
            )

    @classmethod
    def verify_field_fill(cls, driver: Any, selector: str, expected_val: str) -> bool:
        """Reads back the value from an input or textarea to verify the fill succeeded."""
        if not driver or not selector:
            return False

        try:
            actual = driver.execute_script(f'''
                var el = document.querySelector("{selector}");
                if (!el) return null;
                return (el.value || el.innerText || '').trim();
            ''')
            if actual is None:
                return False
            # Check prefix or substring match to account for formatting (e.g. phone spacing)
            return expected_val.strip().lower() in str(actual).lower()
        except Exception:
            return False
