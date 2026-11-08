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

            // 1. Detect aria-invalid inputs (strictly visible, unpopulated, and active)
            const invalidInputs = Array.from(document.querySelectorAll(
                'input[aria-invalid="true"], select[aria-invalid="true"], textarea[aria-invalid="true"], button[aria-invalid="true"], [role="combobox"][aria-invalid="true"], .is-invalid, .has-error input'
            )).filter(el => {
                if (el.type === 'hidden') return false;
                const s = window.getComputedStyle(el);
                const r = el.getBoundingClientRect();
                if (s.display === 'none' || s.visibility === 'hidden' || (r.width === 0 && r.height === 0)) return false;
                const closedContainer = el.closest('[aria-hidden="true"], dialog:not([open]), .modal:not(.show), .popup:not(.active), div[hidden]');
                if (closedContainer) return false;
                // Ignore searchBox inputs if a selection pill already exists in the container
                const multiselect = el.closest('[data-automation-id="multiselectInputContainer"], [class*="multiselect" i]');
                if (multiselect) {
                    const tagEl = multiselect.querySelector('[data-automation-id="selectedItem"], [data-automation-id="promptSelectionLabel"], [class*="pill" i], [class*="tag" i]');
                    if (tagEl && tagEl.innerText && tagEl.innerText.trim().length > 0) return false;
                }
                // Ignore stale aria-invalid if input already contains a valid non-empty value (and not Select One)
                const val = (el.value || el.innerText || '').trim();
                if (val.length > 0 && !/^(select\s*one|select|choose)$/i.test(val) && el.getAttribute('data-automation-id') !== 'searchBox') return false;
                return true;
            });
            for (const el of invalidInputs) {
                const autoId = el.getAttribute('data-automation-id');
                const id = autoId || el.id || el.name || el.getAttribute('aria-label') || 'unknown';
                // Look for sibling or parent error message
                let errText = '';
                const parent = el.closest('[data-automation-id^="formField-"], .form-group, .field, div');
                if (parent) {
                    const errEl = parent.querySelector('[data-automation-id*="error" i], .error, .error-message, .invalid-feedback, [role="alert"], .text-danger');
                    if (errEl) {
                        errText = (errEl.innerText || '').trim();
                    }
                }
                fieldErrors.push({
                    field_identifier: id,
                    error_text: errText || 'Field is invalid or required.',
                    selector: autoId ? `[data-automation-id="${autoId.replace(/"/g, '\\"')}"]` : (el.id ? `#${el.id}` : (el.name ? `[name="${el.name}"]` : '')),
                    input_type: el.type || el.tagName.toLowerCase(),
                });
            }

            // 2. Detect visible error text spans adjacent to inputs
            const visibleErrorElements = Array.from(document.querySelectorAll(
                '.field-error, .error-message, .invalid-feedback, span[id*="error" i], div[id*="error" i], [data-automation-id*="error" i]'
            )).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (el.innerText || '').trim().length > 0;
            });

            for (const el of visibleErrorElements) {
                const text = el.innerText.trim();
                // Check if related parent container or field has already been populated
                const parent = el.closest('[data-automation-id^="formField-"], .form-group, .field, div');
                if (parent) {
                    const inputEl = parent.querySelector('input, select, textarea, button[aria-haspopup="listbox"], [role="combobox"]');
                    if (inputEl) {
                        const v = (inputEl.value || inputEl.innerText || '').trim();
                        if (v.length > 0 && !/^(select\s*one|select|choose)$/i.test(v)) {
                            continue; // Stale error text, field already populated!
                        }
                    }
                }
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
                '[role="alert"], .alert-danger, .alert-error, .validation-summary-errors, [data-automation-id="errorBanner"], [data-automation-id*="error" i]'
            )).filter(el => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0 && (el.innerText || '').trim().length > 0;
            });

            for (const el of alerts) {
                const bannerText = (el.innerText || '').trim();
                // Filter out OTP notifications, email verification notices, info banners, and success notices
                if (/verification\s+code|confirm\s+your\s+(?:email|identity)|code\s+was\s+sent|when\s+you\s+get\s+the\s+code|one-time|passcode|check\s+your\s+email|security\s+code|thank\s+you|successfully\s+submitted|sent\s+(?:a\s+)?verification\s+link|activation\s+link/i.test(bannerText)) {
                    continue;
                }
                // Check if all field errors were cleared and invalid inputs count is 0
                if (fieldErrors.length === 0) {
                    const bLower = bannerText.toLowerCase();
                    const stateFilled = !bLower.includes('state') || (() => {
                        const st = document.querySelector('#address--countryRegion, [data-automation-id="addressSection_countryRegion"]');
                        const txt = st ? (st.value || st.innerText || '').trim() : '';
                        return txt.length > 0 && !/select/i.test(txt);
                    })();
                    const phoneFilled = !bLower.includes('phone device') || (() => {
                        const pt = document.querySelector('#phoneNumber--phoneType, [data-automation-id="phoneDevice-dropdown"]');
                        const txt = pt ? (pt.value || pt.innerText || '').trim() : '';
                        return txt.length > 0 && !/select/i.test(txt);
                    })();
                    if (stateFilled && phoneFilled) {
                        continue; // Banner is stale from previous submission attempt
                    }
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
    async def attempt_auto_remedy(cls, agent: Any, report: ValidationReport, candidate_facts: Optional[Dict[str, Any]] = None) -> int:
        """Attempts to auto-correct common form validation errors (e.g. unchecked required checkboxes,
        stale aria-invalid markers on already filled inputs, and missing Workday dropdowns).
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
            // 2. Clear aria-invalid on inputs and buttons with existing non-empty values
            const invalidInputs = Array.from(document.querySelectorAll('[aria-invalid="true"]'));
            for (const inp of invalidInputs) {
                const val = (inp.value || inp.innerText || '').trim();
                if (val.length > 0 && !/^(select\s*one|select|choose)$/i.test(val)) {
                    inp.removeAttribute('aria-invalid');
                    inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    fixed++;
                }
            }
            return fixed;
        })()"""
        fixed = 0
        try:
            res = agent.evaluate(js_remedy)
            fixed += int(await res if asyncio.iscoroutine(res) else res)
        except Exception as e:
            logger.debug("Validation auto-remedy failed: %s", e)

        # 3. Workday and ATS dropdown validation error auto-resolution
        all_err_text = " ".join(
            [e.error_text for e in report.field_errors] +
            [e.field_identifier for e in report.field_errors] +
            [(e.selector or "") for e in report.field_errors] +
            report.summary_banners
        ).lower()
        if any(k in all_err_text for k in ["state", "phone device", "device type", "phone type", "phonetype", "hear about", "source", "region", "province", "countryregion", "upload a file", "upload a resume", "resume", "cv", "upload", "5mb", "gender", "sex", "consent", "privacy", "policy"]):
            facts = candidate_facts or {}
            state_val = facts.get("profile.state", (None,))[0] if isinstance(facts.get("profile.state"), tuple) else (facts.get("profile.state") or facts.get("state") or "Uttar Pradesh")
            device_val = facts.get("phone_device_type", (None,))[0] if isinstance(facts.get("phone_device_type"), tuple) else (facts.get("phone_device_type") or facts.get("device_type") or "Mobile")
            source_val = facts.get("source", (None,))[0] if isinstance(facts.get("source"), tuple) else (facts.get("source") or "LinkedIn")
            gender_val = facts.get("personal.gender", (None,))[0] if isinstance(facts.get("personal.gender"), tuple) else (facts.get("personal.gender") or facts.get("gender") or "Male")

            try:
                from app.services.automation.universal_agent.form_filler import FormFiller
                filler = FormFiller()

                if any(k in all_err_text for k in ["state", "region", "province", "countryregion"]):
                    ok, err = await filler._fill_workday_dropdown(
                        agent,
                        '#address--countryRegion, button[data-automation-id="addressSection_countryRegion"], [data-automation-id="addressSection_countryRegion"], button[data-automation-id*="countryRegion" i], button[data-automation-id*="state" i]',
                        str(state_val),
                        "State",
                    )
                    if ok:
                        logger.info("Auto-remedied Workday State dropdown with '%s'", state_val)
                        fixed += 1
                    else:
                        logger.warning("Auto-remedy State dropdown failed: %s", err)

                if any(k in all_err_text for k in ["phone device", "device type", "phone type", "phonetype", "phonedevice"]):
                    ok, err = await filler._fill_workday_dropdown(
                        agent,
                        '#phoneNumber--phoneType, button[data-automation-id="phoneDevice-dropdown"], [data-automation-id="phoneDevice-dropdown"], button[data-automation-id*="phoneDevice" i], button[data-automation-id*="device" i], button[data-automation-id*="phone" i], div[data-automation-id*="phone-device" i] button',
                        str(device_val),
                        "Phone Device Type",
                    )
                    if ok:
                        logger.info("Auto-remedied Workday Phone Device Type dropdown with '%s'", device_val)
                        fixed += 1
                    else:
                        logger.warning("Auto-remedy Phone Device Type dropdown failed: %s", err)

                if any(k in all_err_text for k in ["hear about", "source", "how did you hear"]):
                    ok, err = await filler._fill_workday_dropdown(
                        agent,
                        '#source--source, [data-automation-id="sourceDropdown"], [data-automation-id="sourcePrompt"], button[data-automation-id*="source" i], button[data-automation-id*="hear" i], input[data-automation-id="searchBox"]',
                        str(source_val),
                        "How Did You Hear About Us",
                    )
                    if ok:
                        logger.info("Auto-remedied Workday Source dropdown with '%s'", source_val)
                        fixed += 1
                    else:
                        logger.warning("Auto-remedy Source dropdown failed: %s", err)

                if any(k in all_err_text for k in ["gender", "sex"]):
                    ok, err = await filler._fill_workday_dropdown(
                        agent,
                        'button[data-automation-id*="gender" i], div[data-automation-id*="gender" i] button, [data-automation-id*="select-one" i], button[data-automation-id*="select" i], button[aria-haspopup="listbox"], button[aria-haspopup]',
                        str(gender_val),
                        "Gender",
                    )
                    if ok:
                        logger.info("Auto-remedied Workday Gender dropdown with '%s'", gender_val)
                        fixed += 1
                    else:
                        logger.warning("Auto-remedy Gender dropdown failed: %s", err)

                if any(k in all_err_text for k in ["consent", "privacy", "terms", "policy", "agreement"]):
                    c_cnt = await filler.ensure_mandatory_consent_accepted(agent)
                    if c_cnt > 0:
                        logger.info("Auto-remedied %d mandatory consent/privacy checkboxes", c_cnt)
                        fixed += c_cnt

                # 4. Resume / File upload error auto-remedy
                if any(k in all_err_text for k in ["upload a file", "upload a resume", "resume", "cv", "upload a file (5mb max)"]):
                    resume_path = (
                        facts.get("resume.file_path", (None,))[0]
                        or facts.get("resume_path", (None,))[0]
                        or facts.get("profile.resume_path", (None,))[0]
                    )
                    if not resume_path:
                        try:
                            from modules.config_loader import get_resume
                            resume_path = get_resume()
                        except Exception:
                            pass
                    if resume_path and os.path.exists(str(resume_path)):
                        from app.services.automation.universal_agent.file_uploader import FileUploader
                        uploader = FileUploader()
                        cv_sel = 'input[type="file"][data-automation-id*="file" i], input[type="file"][data-automation-id*="upload" i], input[type="file"][data-automation-id*="resume" i], input[type="file"]'
                        ok_up, err_up = await uploader.upload_file(agent, cv_sel, str(resume_path))
                        if ok_up:
                            logger.info("Auto-remedied file upload error with '%s'", resume_path)
                            fixed += 1
                        else:
                            logger.warning("Auto-remedy file upload failed: %s", err_up)
            except Exception as wd_err:
                logger.debug("Workday auto-remedy encountered error: %s", wd_err)

        return fixed
