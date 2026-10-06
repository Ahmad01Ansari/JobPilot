"""
Universal AI Application Agent — Form Validation Error Resolver
Detects active client-side and server-side form validation errors after submission/navigation.
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FormFieldError:
    field_identifier: str
    error_text: str
    selector: Optional[str] = None
    input_type: Optional[str] = None


@dataclass
class ValidationReport:
    has_errors: bool
    field_errors: List[FormFieldError]
    summary_banners: List[str]


class ValidationResolver:
    """Extracts field-level and summary-level form validation errors from the active page."""

    @classmethod
    async def inspect_validation_errors(cls, agent: Any) -> ValidationReport:
        """Inspects DOM for aria-invalid fields, error text spans, and alert banners."""
        js_probe = """(() => {
            const fieldErrors = [];
            const summaryBanners = [];

            // 1. Detect aria-invalid inputs
            const invalidInputs = Array.from(document.querySelectorAll(
                'input[aria-invalid="true"], select[aria-invalid="true"], textarea[aria-invalid="true"], .is-invalid, .has-error input'
            ));
            for (const el of invalidInputs) {
                const id = el.id || el.name || el.getAttribute('aria-label') || 'unknown';
                // Look for sibling or parent error message
                let errText = '';
                const parent = el.closest('.form-group, .field, div');
                if (parent) {
                    const errEl = parent.querySelector('.error, .error-message, .invalid-feedback, [role="alert"], .text-danger');
                    if (errEl) {
                        errText = (errEl.innerText || '').trim();
                    }
                }
                fieldErrors.push({
                    field_identifier: id,
                    error_text: errText || 'Field is invalid or required.',
                    selector: el.id ? `#${el.id}` : (el.name ? `[name="${el.name}"]` : ''),
                    input_type: el.type || el.tagName.toLowerCase(),
                });
            }

            // 2. Detect visible error text spans adjacent to inputs
            const visibleErrorElements = Array.from(document.querySelectorAll(
                '.field-error, .error-message, .invalid-feedback, span[id*="error" i], div[id*="error" i]'
            )).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (el.innerText || '').trim().length > 0;
            });

            for (const el of visibleErrorElements) {
                const text = el.innerText.trim();
                // Check if already captured
                if (!fieldErrors.some(fe => fe.error_text === text)) {
                    fieldErrors.push({
                        field_identifier: el.id || 'form_field',
                        error_text: text,
                        selector: el.id ? `#${el.id}` : '',
                        input_type: 'unknown',
                    });
                }
            }

            // 3. Detect summary alert banners
            const alerts = Array.from(document.querySelectorAll(
                '[role="alert"], .alert-danger, .alert-error, .validation-summary-errors'
            )).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (el.innerText || '').trim().length > 0;
            });

            for (const el of alerts) {
                const bannerText = (el.innerText || '').trim();
                // Filter out OTP notifications, info banners, and success notices
                if (/verification\s+code|confirm\s+your\s+identity|code\s+was\s+sent|when\s+you\s+get\s+the\s+code|one-time|passcode|check\s+your\s+email|security\s+code|thank\s+you|successfully\s+submitted/i.test(bannerText)) {
                    continue;
                }
                if (bannerText && !summaryBanners.includes(bannerText)) {
                    summaryBanners.push(bannerText);
                }
            }

            return {
                field_errors: fieldErrors,
                summary_banners: summaryBanners,
            };
        })()"""

        try:
            res = agent.evaluate(js_probe)
            if asyncio.iscoroutine(res):
                data = await res
            else:
                data = res
        except Exception as e:
            logger.warning("Validation inspection failed: %s", e)
            return ValidationReport(has_errors=False, field_errors=[], summary_banners=[])

        f_errors = []
        for fe in data.get("field_errors", []):
            f_errors.append(
                FormFieldError(
                    field_identifier=fe.get("field_identifier", ""),
                    error_text=fe.get("error_text", ""),
                    selector=fe.get("selector"),
                    input_type=fe.get("input_type"),
                )
            )

        banners = data.get("summary_banners", [])
        has_errors = len(f_errors) > 0 or len(banners) > 0

        return ValidationReport(
            has_errors=has_errors,
            field_errors=f_errors,
            summary_banners=banners,
        )

    @classmethod
    async def attempt_auto_remedy(cls, agent: Any, report: ValidationReport) -> int:
        """Attempts to auto-correct common form validation errors (e.g. unchecked required checkboxes,
        stale aria-invalid markers on already filled inputs).
        Returns count of remedied elements.
        """
        if not report.has_errors:
            return 0

        js_remedy = """(() => {
            let fixed = 0;
            // 1. Check unchecked required/invalid checkboxes
            const invalidChecks = Array.from(document.querySelectorAll('input[type="checkbox"][aria-invalid="true"], input[type="checkbox"]:invalid'));
            for (const chk of invalidChecks) {
                if (!chk.checked) {
                    chk.checked = true;
                    chk.dispatchEvent(new Event('input', { bubbles: true }));
                    chk.dispatchEvent(new Event('change', { bubbles: true }));
                    fixed++;
                }
            }
            // 2. Clear aria-invalid on inputs with existing values
            const invalidInputs = Array.from(document.querySelectorAll('[aria-invalid="true"]'));
            for (const inp of invalidInputs) {
                if (inp.value && inp.value.trim().length > 0) {
                    inp.removeAttribute('aria-invalid');
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    fixed++;
                }
            }
            return fixed;
        })()"""
        try:
            res = agent.evaluate(js_remedy)
            return int(await res if asyncio.iscoroutine(res) else res)
        except Exception as e:
            logger.debug("Validation auto-remedy failed: %s", e)
            return 0
