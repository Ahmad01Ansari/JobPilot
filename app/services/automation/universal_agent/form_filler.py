"""Hybrid Form Filler with Deterministic Playwright Actions and AI Fallback.

Executes rapid, deterministic form input, dropdown selection, radio toggling,
and resume uploading, with AI Stagehand fallback for complex custom controls.
Enforces 100% required field completion before pre-submission human review.
"""

import asyncio
from dataclasses import dataclass, field
import json
import logging
import os
import random
from typing import Any, Dict, List, Optional, Tuple

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent
from app.services.automation.universal_agent.field_mapper import FieldMapping, MappingResult
from app.services.automation.universal_agent.file_uploader import FileUploader

logger = logging.getLogger(__name__)


@dataclass
class FormFillResult:
    """Outcome of attempting to populate an application form."""

    total_fields: int = 0
    filled_fields: int = 0
    failed_fields: List[str] = field(default_factory=list)
    required_fields_total: int = 0
    required_fields_filled: int = 0
    is_complete: bool = False
    completion_rate: float = 0.0
    required_completion_rate: float = 0.0
    field_details: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class FormFiller:
    """Fills web form elements deterministically with AI fallback."""

    def __init__(self, file_uploader: Optional[FileUploader] = None) -> None:
        self.file_uploader = file_uploader or FileUploader()

    async def fill_form(self, agent: BrowserAgent, mapping_result: MappingResult) -> FormFillResult:
        """Populates all mapped form fields on the active page and verifies completion."""
        mappings = mapping_result.mappings
        total_fields = len(mappings)
        filled_count = 0
        failed_names: List[str] = []
        req_total = 0
        req_filled = 0
        field_details: Dict[str, Dict[str, Any]] = {}

        # Prioritize file upload fields (resume/cv) first to allow background parsers to fire early
        sorted_mappings = sorted(mappings, key=lambda m: 0 if m.field_info.input_type.lower() == "file" else 1)

        for mapping in sorted_mappings:
            f_info = mapping.field_info
            is_req = f_info.required
            if is_req:
                req_total += 1

            field_name = f_info.label or f_info.name or f_info.field_id
            # If field could not be resolved from candidate data
            if not mapping.is_resolved or mapping.effective_value is None:
                if is_req:
                    failed_names.append(field_name)
                    if f_info.field_id and f_info.field_id != field_name:
                        failed_names.append(f_info.field_id)
                    if f_info.name and f_info.name not in (field_name, f_info.field_id):
                        failed_names.append(f_info.name)
                    field_details[field_name] = {
                        "status": "FAILED_UNRESOLVED",
                        "label": field_name,
                        "value": "",
                        "required": True,
                        "provenance": "UNRESOLVED",
                        "error": "Required field could not be mapped from candidate facts.",
                    }
                else:
                    field_details[field_name] = {
                        "status": "SKIPPED_OPTIONAL",
                        "label": field_name,
                        "value": "",
                        "required": False,
                        "provenance": "OPTIONAL",
                    }
                continue

            # Humanic delay before filling field (prevents bot detection)
            await asyncio.sleep(random.uniform(0.18, 0.42))

            # Attempt to fill the field
            success, err_msg = await self.fill_single_field(agent, mapping)
            field_name = f_info.label or f_info.name or f_info.field_id
            prov_str = getattr(mapping.provenance, "value", str(mapping.provenance)) if getattr(mapping, "provenance", None) else "PROFILE_FACT"

            # If file was uploaded, wait for any asynchronous ATS resume parser to finish
            if success and f_info.input_type.lower() == "file":
                logger.info("Resume uploaded. Allowing 2.0s for background ATS parser to settle...")
                await asyncio.sleep(2.0)

            if success:
                filled_count += 1
                if is_req:
                    req_filled += 1
                field_details[field_name] = {
                    "status": "FILLED",
                    "label": f_info.label or field_name,
                    "value": mapping.effective_value,
                    "required": is_req,
                    "input_type": f_info.input_type,
                    "field_id": f_info.field_id,
                    "name": f_info.name,
                    "provenance": prov_str,
                }
            else:
                if is_req:
                    failed_names.append(field_name)
                    if f_info.field_id and f_info.field_id != field_name:
                        failed_names.append(f_info.field_id)
                    if f_info.name and f_info.name not in (field_name, f_info.field_id):
                        failed_names.append(f_info.name)
                field_details[field_name] = {
                    "status": "FAILED_FILL",
                    "label": f_info.label or field_name,
                    "error": err_msg,
                    "required": is_req,
                    "value": mapping.effective_value,
                    "input_type": f_info.input_type,
                    "field_id": f_info.field_id,
                    "name": f_info.name,
                    "provenance": prov_str,
                }

        # Post-Fill Reconciliation Pass:
        # Prevents ATS resume parsers (CatsOne, Lever, etc.) from overwriting candidate facts (e.g. Mohd vs Mohd Ahmad Raza)
        try:
            reconciled_cnt = await self.reconcile_fields(agent, sorted_mappings)
            if reconciled_cnt > 0:
                logger.debug("Post-fill reconciliation verified/restored %d fields.", reconciled_cnt)
        except Exception as e:
            logger.warning("Error during post-fill reconciliation pass: %s", e)

        # Mandatory Consent & Privacy Policy Sweeper
        # Ensures that required data processing, privacy notice, and terms checkboxes are accepted
        try:
            swept_consent = await self.ensure_mandatory_consent_accepted(agent)
            if swept_consent > 0:
                logger.info("Accepted %d consent/privacy checkboxes during form fill.", swept_consent)
        except Exception as e:
            logger.warning("Error running mandatory consent sweep during fill_form: %s", e)

        req_rate = (req_filled / req_total) if req_total > 0 else 1.0
        comp_rate = (filled_count / total_fields) if total_fields > 0 else 1.0
        is_complete = (req_filled == req_total) and (req_total > 0 or filled_count > 0 or total_fields == 0)

        return FormFillResult(
            total_fields=total_fields,
            filled_fields=filled_count,
            failed_fields=failed_names,
            required_fields_total=req_total,
            required_fields_filled=req_filled,
            is_complete=is_complete,
            completion_rate=comp_rate,
            required_completion_rate=req_rate,
            field_details=field_details,
        )

    async def fill_single_field(self, agent: BrowserAgent, mapping: FieldMapping) -> Tuple[bool, Optional[str]]:
        """Populates a single form field using deterministic Playwright operations, falling back to AI."""
        f_info = mapping.field_info
        val = mapping.effective_value
        if val is None:
            return False, "No value provided to fill."

        input_type = f_info.input_type.lower()
        selector = f_info.selector

        try:
            # 1. File Upload Field
            if input_type == "file":
                js_clear_stale = f"""(() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el || el.offsetParent === null) {{
                        const container = el ? el.closest('[data-component-name*="Filefield"], .file-field, div') : document;
                        const btn = container ? container.querySelector('button.bp3-tag-remove, button[aria-label="Remove"], .file-tag-remove') : null;
                        if (btn) {{ try {{ btn.click(); }} catch(e) {{}} }}
                    }}
                }})()"""
                try:
                    await agent.evaluate(js_clear_stale)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

                success, err = await self.file_uploader.upload_file(agent, selector, val)
                if not success:
                    return False, err
                return True, None

            # 2. Native Select Dropdown
            elif input_type == "select":
                # Primary: Playwright select_option
                ok = await agent.select_option(selector, val)
                if not ok:
                    # Fallback 1: JavaScript value assignment and event dispatch
                    js_select = f"""(() => {{
                        const el = document.querySelector({json.dumps(selector)});
                        if (!el) return false;
                        el.value = {json.dumps(val)};
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return el.value === {json.dumps(val)};
                    }})()"""
                    ok = bool(await agent.evaluate(js_select))

                if not ok:
                    # Fallback 2: Stagehand AI act
                    try:
                        await agent.act(f"Select '{val}' in dropdown '{f_info.label}'")
                        ok = True
                    except Exception as e:
                        return False, f"Dropdown selection failed: {e}"

                return ok, None if ok else "Failed to select option."

            # 3. Radio Group or Radio Button
            elif input_type in ["radio_group", "radio"]:
                val_str = str(val).strip().lower()
                ok = False

                # Primary: JavaScript semantic matching by value, label text, and boolean equivalence
                # Handles custom-styled radio buttons (e.g. Pinpoint, Workday, Greenhouse) where inputs have opacity: 0
                js_radio = f"""(() => {{
                    const sel = {json.dumps(f_info.selector)};
                    const nameAttr = {json.dumps(f_info.name or '')};
                    let radios = [];
                    if (nameAttr) {{
                        radios = Array.from(document.querySelectorAll(`input[type="radio"][name="${{nameAttr.replace(/"/g, '\\"')}}"]`));
                    }}
                    if (!radios.length) {{
                        const container = document.querySelector(sel)?.closest('[role="radiogroup"], [id*="-react-component-"], fieldset, .form-group, .field-group, .cx-select-pills-container') || document.querySelector(sel) || null;
                        if (container) {{
                            radios = Array.from(container.querySelectorAll('input[type="radio"], button, [role="radio"], .cx-select-pill-section'));
                        }}
                    }}
                    if (!radios.length) {{
                        radios = Array.from(document.querySelectorAll(sel));
                    }}
                    const target = {json.dumps(val_str)};
                    for (const r of radios) {{
                        const valAttr = (r.value || '').toLowerCase();
                        const lbl = (r.closest('label')?.innerText || r.innerText || r.parentElement?.innerText || '').trim().toLowerCase();
                        const isMatch = (
                            valAttr === target ||
                            lbl === target ||
                            (/\byes\b/i.test(lbl) && (target === 'yes' || target === 'true' || target === '1')) ||
                            (/\bno\b/i.test(lbl) && (target === 'no' || target === 'false' || target === '0')) ||
                            (valAttr === 'true' && (target === 'yes' || target === 'true' || target === '1')) ||
                            (valAttr === 'false' && (target === 'no' || target === 'false' || target === '0')) ||
                            (valAttr === '1' && (target === 'yes' || target === 'true' || target === '1')) ||
                            (valAttr === '0' && (target === 'no' || target === 'false' || target === '0'))
                        );
                        if (isMatch) {{
                            try {{ r.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                            const parentLabel = r.closest('label');
                            if (parentLabel) try {{ parentLabel.click(); }} catch(e) {{}}
                            try {{ r.click(); }} catch(e) {{}}
                            if (r.tagName === 'INPUT') {{
                                r.checked = true;
                            }} else {{
                                r.setAttribute('aria-checked', 'true');
                            }}
                            r.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            r.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            r.dispatchEvent(new Event('click', {{ bubbles: true }}));
                            return true;
                        }}
                    }}
                    return false;
                }})()"""
                try:
                    eval_res = agent.evaluate(js_radio)
                    ok = bool(await eval_res if asyncio.iscoroutine(eval_res) else eval_res)
                except Exception:
                    ok = False

                if not ok and f_info.name:
                    # Fallback 1: Playwright click by name & value (properly escaped for CSS selectors)
                    try:
                        radio_sel = f'input[name={json.dumps(f_info.name)}][value={json.dumps(val)}]'
                        ok = await agent.click(radio_sel)
                    except Exception:
                        ok = False

                if not ok:
                    # Fallback 2: Stagehand AI act
                    try:
                        await agent.act(f"Select radio option '{val}' for '{f_info.label}'")
                        ok = True
                    except Exception as e:
                        return False, f"Radio selection failed: {e}"

                return ok, None if ok else "Failed to select radio option."

            # 4. Checkbox
            elif input_type == "checkbox":
                should_check = str(val).strip().lower() in ["yes", "true", "1", "on"]
                js_checkbox = f"""(() => {{
                    if (typeof CSS === 'undefined' || !CSS.escape) {{ window.CSS = window.CSS || {{}}; CSS.escape = function(s) {{ return String(s).replace(/([!"#$%&'()*+,./:;<=>?@[\\\\\\]^`{{|}}~])/g, '\\\\$1'); }}; }}
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    const desired = {'true' if should_check else 'false'};
                    try {{ el.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); }} catch(e) {{}}

                    if (el.checked !== desired) {{
                        const proto = window.HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                        if (setter) {{
                            setter.call(el, desired);
                        }} else {{
                            el.checked = desired;
                        }}
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        // Trigger click on associated label or wrapper if needed (pretty-checkbox, etc.)
                        const id = el.id;
                        const lbl = (id ? document.querySelector('label[for="' + CSS.escape(id) + '"]') : null) ||
                                     el.closest('label') ||
                                     el.closest('.pretty, .custom-control, .form-check, .checkbox') ||
                                     el.parentElement?.querySelector('label');
                        if (lbl && lbl !== el) {{
                            try {{ lbl.click(); }} catch(e) {{}}
                        }}

                        if (el.checked !== desired) {{
                            try {{ el.click(); }} catch(e) {{}}
                        }}

                        if (el.checked !== desired) {{
                            el.checked = desired;
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                    return el.checked === desired;
                }})()"""
                try:
                    eval_res = agent.evaluate(js_checkbox)
                    ok = bool(await eval_res if asyncio.iscoroutine(eval_res) else eval_res)
                except Exception:
                    ok = False

                if not ok:
                    try:
                        act_cmd = f"Check the checkbox for '{f_info.label}'" if should_check else f"Uncheck the checkbox for '{f_info.label}'"
                        await agent.act(act_cmd)
                        ok = True
                    except Exception as e:
                        return False, f"Checkbox toggle failed: {e}"

                return ok, None if ok else "Failed to toggle checkbox."

            # 5. Textual Inputs (text, email, tel, textarea, number, url)
            else:
                # Safety Guard: Never type a local filesystem path into a text input or textarea!
                if isinstance(val, str) and (os.path.isabs(val) or val.startswith("~")) and any(val.lower().endswith(ext) for ext in [".pdf", ".docx", ".doc", ".txt", ".rtf"]):
                    logger.warning(
                        "Safety Guard: Prevented typing file path '%s' into non-file field '%s' (%s).",
                        val, f_info.label, selector
                    )
                    return True, None

                # BUG-07: Typeahead / Autocomplete handler for location, university, etc.
                is_typeahead = getattr(f_info, "has_autocomplete", False) or any(
                    k in (f_info.name + " " + f_info.label).lower()
                    for k in ["location", "city", "university", "college", "school"]
                )
                if is_typeahead:
                    typeahead_ok, _ = await self._fill_with_typeahead(agent, selector, val)
                    if typeahead_ok:
                        return True, None

                # Scroll into view smoothly and apply React/Knockout-safe property setter with humanic event dispatch
                js_fill = f"""(() => {{
                    const rawEl = document.querySelector({json.dumps(selector)});
                    if (!rawEl) return false;
                    let el = rawEl.querySelector('input, textarea');
                    if (!el && rawEl.shadowRoot) {{
                        el = rawEl.shadowRoot.querySelector('input, textarea');
                    }}
                    if (!el) el = rawEl;

                    try {{ el.scrollIntoView({{ behavior: 'smooth', block: 'center' }}); }} catch(e) {{}}
                    el.focus();
                    let fillVal = {json.dumps(val)};
                    if (el.type === 'tel' || /phone/i.test(el.name || el.id || '')) {{
                        let digits = String(fillVal).replace(/\D/g, '');
                        if (digits.length === 12 && digits.startsWith('91')) {{
                            digits = digits.substring(2);
                        }}
                        if (digits.length === 11 && digits.startsWith('0')) {{
                            digits = digits.substring(1);
                        }}
                        if (digits.length === 10) {{
                            fillVal = digits;
                        }}
                    }}
                    const isTextarea = el.tagName.toLowerCase() === 'textarea';
                    const proto = isTextarea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) {{
                        setter.call(el, fillVal);
                    }} else {{
                        el.value = fillVal;
                    }}
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.blur();

                    if (rawEl !== el) {{
                        try {{ rawEl.value = fillVal; }} catch(e) {{}}
                        try {{ rawEl.dispatchEvent(new CustomEvent('valueChanged', {{ detail: {{ value: fillVal }} }})); }} catch(e) {{}}
                        try {{ rawEl.dispatchEvent(new Event('input', {{ bubbles: true }})); }} catch(e) {{}}
                        try {{ rawEl.dispatchEvent(new Event('change', {{ bubbles: true }})); }} catch(e) {{}}
                    }}
                    return el.value === fillVal || rawEl.value === fillVal;
                }})()"""
                try:
                    eval_res = agent.evaluate(js_fill)
                    if asyncio.iscoroutine(eval_res):
                        ok = bool(await eval_res)
                    else:
                        ok = bool(eval_res)
                except Exception:
                    ok = False

                await asyncio.sleep(random.uniform(0.08, 0.16))

                if not ok:
                    # Fallback to standard fill
                    fill_res = agent.fill(selector, val)
                    ok = bool(await fill_res if asyncio.iscoroutine(fill_res) else fill_res)

                if not ok:
                    # Fallback 2: Stagehand AI act
                    try:
                        await agent.act(f"Type '{val}' into input '{f_info.label}'")
                        ok = True
                    except Exception as e:
                        return False, f"Text input failed: {e}"

                return ok, None if ok else "Failed to fill input."

        except Exception as e:
            logger.error("Error filling field '%s': %s", f_info.name or selector, e)
            return False, str(e)

    async def ensure_mandatory_consent_accepted(self, agent: BrowserAgent) -> int:
        """Finds and auto-accepts all mandatory privacy notices, consent policies, data processing agreements,
        and required non-marketing checkboxes across the current DOM.
        Handles standard checkboxes, pretty-checkboxes, custom controls, and ARIA checkboxes.
        Returns the number of consent checkboxes successfully accepted.
        """
        js_consent_sweep = """(() => {
            let acceptedCount = 0;
            if (typeof CSS === 'undefined' || !CSS.escape) { window.CSS = window.CSS || {}; CSS.escape = function(s) { return String(s).replace(/([!"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1'); }; }
            const consentRegex = /privacy|privacy[\\s_-]*notice|privacy[\\s_-]*policy|personal[\\s_-]*information|personal[\\s_-]*data|store[\\s_-]*(?:your[\\s_-]*)?personal|process[\\s_-]*(?:your[\\s_-]*)?personal|consent|data[\\s_-]*protection|terms|terms[\\s_-]*and[\\s_-]*conditions|terms[\\s_-]*of[\\s_-]*service|terms[\\s_-]*of[\\s_-]*use|agree|agreement|acknowledg|certify|declaration|accurate|true[\\s_-]*and[\\s_-]*correct|gdpr/i;
            const marketingRegex = /marketing|newsletter|promotional|updates[\\s_-]*via[\\s_-]*email/i;

            const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"], [role="checkbox"]'));
            for (const el of checkboxes) {
                // If it's a native checkbox and already checked, skip
                if (el.tagName.toLowerCase() === 'input' && el.checked) continue;
                // If it's an ARIA checkbox and already checked, skip
                if (el.getAttribute('aria-checked') === 'true') continue;

                // Inspect labels, container text, id, name, aria-label
                const id = el.id || '';
                const name = el.name || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                
                let labelText = '';
                if (id) {
                    const lblEl = document.querySelector('label[for="' + CSS.escape(id) + '"]');
                    if (lblEl) labelText = lblEl.innerText || lblEl.textContent || '';
                }
                if (!labelText) {
                    const parentLbl = el.closest('label');
                    if (parentLbl) labelText = parentLbl.innerText || parentLbl.textContent || '';
                }
                const container = el.closest('.pretty, .custom-control, .form-check, .checkbox, .field-group, .form-group, fieldset, div');
                const containerText = container ? (container.innerText || container.textContent || '') : '';
                
                const allText = (id + ' ' + name + ' ' + ariaLabel + ' ' + labelText + ' ' + containerText).toLowerCase();

                // Skip marketing / newsletter subscriptions
                if (marketingRegex.test(allText)) continue;

                const isRequired = el.required || 
                                   el.getAttribute('aria-required') === 'true' || 
                                   labelText.includes('*') || 
                                   labelText.toLowerCase().includes('(required)') ||
                                   (container && (container.querySelector('.required, [class*="asterisk" i]') !== null || containerText.includes('*')));

                const isConsent = consentRegex.test(allText);

                if (isConsent || isRequired) {
                    try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch(e) {}

                    if (el.tagName.toLowerCase() === 'input') {
                        const proto = window.HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                        if (setter) {
                            setter.call(el, true);
                        } else {
                            el.checked = true;
                        }
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));

                        // Click associated label or pretty wrapper if needed
                        const targetLabel = (id ? document.querySelector('label[for="' + CSS.escape(id) + '"]') : null) || 
                                            el.closest('label') || 
                                            el.closest('.pretty, .custom-control, .form-check') || 
                                            el;
                        if (targetLabel && targetLabel !== el) {
                            try { targetLabel.click(); } catch(e) {}
                        }

                        if (!el.checked) {
                            try { el.click(); } catch(e) {}
                        }

                        if (!el.checked) {
                            el.checked = true;
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                        }

                        if (el.checked) acceptedCount++;
                    } else {
                        // ARIA checkbox
                        el.setAttribute('aria-checked', 'true');
                        try { el.click(); } catch(e) {}
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        acceptedCount++;
                    }
                }
            }
            return acceptedCount;
        })()"""
        try:
            res = agent.evaluate(js_consent_sweep)
            count = int(await res if asyncio.iscoroutine(res) else res)
            if count > 0:
                logger.info("Universal Consent Sweeper accepted %d mandatory privacy/consent agreements.", count)
            return count
        except Exception as e:
            logger.warning("Universal Consent Sweeper encountered exception: %s", e)
            return 0

    @classmethod
    async def reconcile_fields(cls, agent: Any, mappings: List[FieldMapping]) -> int:
        """Re-reconciles form fields against candidate facts to prevent late ATS resume parser
        overwrites (e.g. Mohd vs Mohd Ahmad Raza, overwritten selects, or changed radio buttons).
        Handles text, textarea, email, tel, select, and radio_group fields.
        Returns count of successfully reconciled/verified fields.
        """
        reconciled_count = 0
        for m in mappings:
            if not (m.is_resolved and m.effective_value):
                continue
            inp_type = m.field_info.input_type.lower()
            expected = m.effective_value
            sel = m.field_info.selector

            # 1. Textual inputs (text, textarea, email, tel)
            if inp_type in ["text", "textarea", "email", "tel"]:
                js = f"""(() => {{
                    const el = document.querySelector({json.dumps(sel)});
                    if (!el) return null;
                    let exp = {json.dumps(expected)};
                    if (el.type === 'tel' || /phone/i.test(el.name || el.id || '')) {{
                        let digits = String(exp).replace(/\\D/g, '');
                        if (digits.length === 12 && digits.startsWith('91')) digits = digits.substring(2);
                        if (digits.length === 11 && digits.startsWith('0')) digits = digits.substring(1);
                        if (digits.length === 10) exp = digits;
                    }}
                    if (el.value !== exp) {{
                        const isTextarea = el.tagName.toLowerCase() === 'textarea';
                        const proto = isTextarea ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                        if (setter) {{
                            setter.call(el, exp);
                        }} else {{
                            el.value = exp;
                        }}
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return 'UPDATED';
                    }}
                    return 'MATCH';
                }})()"""
                try:
                    res = agent.evaluate(js)
                    out = await res if asyncio.iscoroutine(res) else res
                    if out in ('UPDATED', 'MATCH'):
                        reconciled_count += 1
                except Exception:
                    pass

            # 2. Select dropdowns
            elif inp_type == "select":
                js_select = f"""(() => {{
                    const el = document.querySelector({json.dumps(sel)});
                    if (!el || el.tagName.toLowerCase() !== 'select') return null;
                    const exp = {json.dumps(str(expected).strip().lower())};
                    const currOpt = el.options[el.selectedIndex];
                    if (currOpt && (currOpt.value.toLowerCase() === exp || currOpt.text.trim().toLowerCase() === exp)) {{
                        return 'MATCH';
                    }}
                    for (let i = 0; i < el.options.length; i++) {{
                        const opt = el.options[i];
                        if (opt.value.toLowerCase() === exp || opt.text.trim().toLowerCase() === exp ||
                            opt.text.trim().toLowerCase().includes(exp) || exp.includes(opt.text.trim().toLowerCase())) {{
                            el.selectedIndex = i;
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return 'UPDATED';
                        }}
                    }}
                    return null;
                }})()"""
                try:
                    res = agent.evaluate(js_select)
                    out = await res if asyncio.iscoroutine(res) else res
                    if out in ('UPDATED', 'MATCH'):
                        reconciled_count += 1
                except Exception:
                    pass

            # 3. Radio groups
            elif inp_type == "radio_group":
                name = m.field_info.name
                js_radio = f"""(() => {{
                    if (typeof CSS === 'undefined' || !CSS.escape) {{ window.CSS = window.CSS || {{}}; CSS.escape = function(s) {{ return String(s).replace(/([!"#$%&'()*+,./:;<=>?@[\\\]^`{{|}}~])/g, '\\\\$1'); }}; }}
                    let radios = [];
                    if ({json.dumps(name)}) {{
                        radios = Array.from(document.querySelectorAll('input[type="radio"][name=' + CSS.escape({json.dumps(name)}) + ']'));
                    }}
                    if (radios.length === 0) {{
                        const container = document.querySelector({json.dumps(sel)});
                        if (container) {{
                            radios = Array.from(container.querySelectorAll('input[type="radio"]'));
                        }}
                    }}
                    if (radios.length === 0) return null;
                    const exp = {json.dumps(str(expected).strip().lower())};
                    for (const r of radios) {{
                        const rVal = (r.value || '').toLowerCase();
                        let rText = '';
                        const lbl = r.closest('label') || (r.id ? document.querySelector('label[for=' + CSS.escape(r.id) + ']') : null);
                        if (lbl) rText = (lbl.innerText || lbl.textContent || '').trim().toLowerCase();
                        if (rVal === exp || rText === exp || (rVal && exp.includes(rVal)) || (rText && exp.includes(rText))) {{
                            if (!r.checked) {{
                                r.checked = true;
                                try {{ r.click(); }} catch(e) {{}}
                                r.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                return 'UPDATED';
                            }}
                            return 'MATCH';
                        }}
                    }}
                    return null;
                }})()"""
                try:
                    res = agent.evaluate(js_radio)
                    out = await res if asyncio.iscoroutine(res) else res
                    if out in ('UPDATED', 'MATCH'):
                        reconciled_count += 1
                except Exception:
                    pass

        return reconciled_count

    async def _fill_with_typeahead(self, agent: Any, selector: str, val: str) -> Tuple[bool, Optional[str]]:
        """Handles autocomplete/typeahead inputs (e.g. Greenhouse/Lever location or university dropdowns)
        by typing the value, waiting for suggestions dropdown, and picking matching option.
        """
        try:
            # 1. Type text into input element
            fill_ok = False
            if hasattr(agent, "fill"):
                try:
                    res = agent.fill(selector, val)
                    fill_ok = bool(await res if asyncio.iscoroutine(res) else res)
                except Exception:
                    fill_ok = False

            if not fill_ok:
                js_type = f"""(() => {{
                    const el = document.querySelector({json.dumps(selector)});
                    if (!el) return false;
                    el.focus();
                    el.value = {json.dumps(val)};
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }})()"""
                try:
                    r = agent.evaluate(js_type)
                    fill_ok = bool(await r if asyncio.iscoroutine(r) else r)
                except Exception:
                    pass

            await asyncio.sleep(0.5)

            # 2. Check for suggestion list/dropdown and click matching option
            js_pick = f"""(() => {{
                const target = {json.dumps(str(val).lower().strip())};
                const suggestions = Array.from(document.querySelectorAll(
                    '.tt-suggestion, .typeahead-suggestion, .select2-result, .select2-results__option, ' +
                    '.ui-menu-item, [role="listbox"] [role="option"], [role="option"], ul.suggestions li, .pac-item'
                )).filter(el => {{
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && (el.innerText || '').trim().length > 0;
                }});

                if (suggestions.length > 0) {{
                    let best = suggestions[0];
                    for (const s of suggestions) {{
                        const txt = (s.innerText || '').toLowerCase();
                        if (txt.includes(target) || target.includes(txt)) {{
                            best = s;
                            break;
                        }}
                    }}
                    best.click();
                    return true;
                }}
                return false;
            }})()"""
            try:
                pick_res = agent.evaluate(js_pick)
                picked = bool(await pick_res if asyncio.iscoroutine(pick_res) else pick_res)
                if picked:
                    await asyncio.sleep(0.2)
                    return True, None
            except Exception:
                pass

            return fill_ok, None if fill_ok else "Typeahead input could not be populated."
        except Exception as e:
            logger.debug("Typeahead fill encountered error: %s", e)
            return False, str(e)
