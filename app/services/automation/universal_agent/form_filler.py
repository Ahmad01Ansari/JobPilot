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
            
            # Guard: Never overwrite Workday repeater fields that are managed by fill_workday_repeaters
            fid = (f_info.field_id or "").lower()
            fsel = (f_info.selector or "").lower()
            flab = (f_info.label or "").lower()
            fnam = (f_info.name or "").lower()
            combined_desc = f"{fid} {fsel} {flab} {fnam}"
            if any(k in combined_desc for k in [
                "workexperience", "education", "datesection", "degree", "school",
                "fieldofstudy", "responsivemoniker", "promptleaf", "promptoption", "menuitem"
            ]):
                continue

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

            # 2. Select Dropdown (Native <select> or Custom Workday/Combobox)
            elif input_type in ["select", "combobox"]:
                is_custom = getattr(f_info, "is_custom_dropdown", False) or any(
                    k in selector.lower() for k in ["dropdown", "prompt", "combobox", "button", "div"]
                )

                if is_custom:
                    ok, err = await self._fill_workday_dropdown(agent, selector, val, f_info.label)
                    if ok:
                        return True, None

                # Primary: Playwright select_option for standard <select> elements
                ok = await agent.select_option(selector, val)
                if not ok:
                    # Fallback 1: JavaScript value assignment and event dispatch
                    js_select = f"""(() => {{
                        const el = document.querySelector({json.dumps(selector)});
                        if (!el) return false;
                        if (el.tagName.toLowerCase() !== 'select') return false;
                        el.value = {json.dumps(val)};
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        return el.value === {json.dumps(val)};
                    }})()"""
                    try:
                        ok = bool(await agent.evaluate(js_select))
                    except Exception:
                        ok = False

                if not ok:
                    # Fallback 2: Workday / Custom Dropdown handler
                    ok, err = await self._fill_workday_dropdown(agent, selector, val, f_info.label)

                if not ok:
                    # Fallback 3: Stagehand AI act
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
                            const proto = window.HTMLInputElement.prototype;
                            const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                            if (setter) {{
                                setter.call(el, desired);
                            }} else {{
                                el.checked = desired;
                            }}
                            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            el.dispatchEvent(new Event('click', {{ bubbles: true }}));
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

                    // If this is a multiselect or skills input (Workday/tag input), dispatch Enter key to commit the tag/pill
                    const isMultiTag = el.closest('[data-automation-id="multiselectInputContainer"], [class*="multiselect" i], [class*="tag" i], [class*="token" i]') ||
                                       /skill/i.test(el.id || el.name || el.getAttribute('data-automation-id') || '');
                    if (isMultiTag) {{
                        el.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                        el.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                    }}

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

            const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"], [role="checkbox"], [data-automation-id*="checkbox" i]'));
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
                    if (lblEl) labelText = (lblEl.innerText || lblEl.textContent || '').trim();
                }
                if (!labelText) {
                    const parentLbl = el.closest('label');
                    if (parentLbl) labelText = (parentLbl.innerText || parentLbl.textContent || '').trim();
                }

                let containerText = '';
                let hasRequiredIndicator = false;
                let p = el.parentElement;
                for (let depth = 0; depth < 5 && p && p !== document.body && !/^(form|main|body|html|section)$/i.test(p.tagName); depth++, p = p.parentElement) {
                    // Do not expand to ancestor containers that hold multiple different form controls
                    if (p.querySelectorAll('input:not([type="hidden"]), select, textarea').length > 3) {
                        break;
                    }
                    const txt = (p.innerText || p.textContent || '').trim();
                    if (txt.length > containerText.length) {
                        containerText = txt;
                    }
                    if (p.querySelector('.required, [class*="required" i], [class*="asterisk" i]') !== null || txt.includes('*')) {
                        hasRequiredIndicator = true;
                    }
                    if (!labelText) {
                        const lbl = p.querySelector('label, [data-automation-id="formLabel"], legend, span, p');
                        if (lbl && (lbl.innerText || '').trim()) {
                            labelText = lbl.innerText.trim();
                        }
                    }
                }
                
                const fieldText = (id + ' ' + name + ' ' + ariaLabel + ' ' + labelText).toLowerCase();
                const allText = (fieldText + ' ' + containerText).toLowerCase();

                // Skip if this specific field is a marketing / newsletter subscription
                const isMarketing = marketingRegex.test(fieldText) || (!consentRegex.test(fieldText) && marketingRegex.test(allText));
                if (isMarketing) continue;

                const isRequired = el.required || 
                                   el.getAttribute('aria-required') === 'true' || 
                                   labelText.includes('*') || 
                                   labelText.toLowerCase().includes('(required)') ||
                                   hasRequiredIndicator;

                const isConsent = consentRegex.test(allText);

                if (isConsent || isRequired) {
                    try { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch(e) {}

                    if (el.tagName.toLowerCase() === 'input') {
                        if (!el.checked) {
                            try { el.click(); } catch(e) {}
                        }
                        if (!el.checked) {
                            const targetLabel = (id ? document.querySelector('label[for="' + CSS.escape(id) + '"]') : null) || 
                                                el.closest('label') || 
                                                el.closest('.pretty, .custom-control, .form-check, .checkbox') || 
                                                el.parentElement?.querySelector('label');
                            if (targetLabel && targetLabel !== el) {
                                try { targetLabel.click(); } catch(e) {}
                            }
                        }
                        if (!el.checked) {
                            const proto = window.HTMLInputElement.prototype;
                            const setter = Object.getOwnPropertyDescriptor(proto, 'checked')?.set;
                            if (setter) {
                                setter.call(el, true);
                            } else {
                                el.checked = true;
                            }
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            el.dispatchEvent(new Event('change', { bubbles: true }));
                            el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
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

    async def _fill_workday_dropdown(self, agent: BrowserAgent, selector: str, val: str, label_hint: str = "") -> Tuple[bool, Optional[str]]:
        """Handles custom Workday comboboxes, popup prompt widgets, and ARIA listboxes."""
        val_clean = str(val).strip()
        val_lower = val_clean.lower()
        hint_lower = str(label_hint).strip().lower()

        # Step 1: Open dropdown/prompt popup
        js_open_dropdown = f"""(() => {{
            const rawSel = {json.dumps(selector)};
            const hint = {json.dumps(hint_lower)};
            let trigger = null;
            // Try selector parts individually or as combined
            try {{
                trigger = document.querySelector(rawSel);
            }} catch(e) {{
                const parts = rawSel.split(',');
                for (const p of parts) {{
                    try {{
                        const found = document.querySelector(p.trim());
                        if (found) {{ trigger = found; break; }}
                    }} catch(err) {{}}
                }}
            }}
            if (!trigger) {{
                // Fallback by automation-id, aria-label, or parent form field label
                const candidates = Array.from(document.querySelectorAll(
                    'button[data-automation-id*="dropdown" i], button[data-automation-id*="prompt" i], ' +
                    'button[data-automation-id*="select" i], [data-automation-id*="select-one" i], [data-automation-id*="selectOne" i], ' +
                    'button[data-automation-id*="combobox" i], button[data-automation-id*="option" i], ' +
                    'button[aria-haspopup="listbox"], button[aria-haspopup], div[role="combobox"], [data-automation-id="sourceDropdown"], ' +
                    '[data-automation-id="sourcePrompt"], button[data-automation-id*="source" i], button[data-automation-id*="hear" i], ' +
                    '[data-automation-id="phoneDevice-dropdown"], button[data-automation-id*="phone" i], button[data-automation-id*="device" i], ' +
                    '[data-automation-id*="phone-device" i], [data-automation-id*="phoneDevice" i], [id*="phoneType" i], [id*="phoneNumber" i], ' +
                    'button[data-automation-id*="gender" i], [data-automation-id*="gender" i], ' +
                    'button[data-automation-id*="disability" i], [data-automation-id*="disability" i], ' +
                    '[data-automation-id="addressSection_countryRegion"], [data-automation-id="stateDropdown"], ' +
                    '#source--source, input[data-automation-id="searchBox"]'
                ));
                trigger = candidates.find(b => {{
                    let pTxt = '';
                    let p = b.parentElement;
                    for (let d = 0; d < 8 && p && p !== document.body; d++, p = p.parentElement) {{
                        const t = (p.innerText || '').toLowerCase();
                        if (t.length > pTxt.length) pTxt = t;
                    }}
                    const t = (b.innerText || b.getAttribute('aria-label') || b.getAttribute('data-automation-id') || b.id || '').toLowerCase();
                    return hint && (t.includes(hint) || hint.includes(t) || pTxt.includes(hint));
                }});
            }}
            if (trigger && trigger.tagName.toLowerCase() !== 'button' && trigger.tagName.toLowerCase() !== 'input') {{
                const innerClickable = trigger.querySelector('button, [role="button"], [role="combobox"], input');
                if (innerClickable) trigger = innerClickable;
            }}
            if (!trigger) return false;

            try {{ trigger.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
            try {{ trigger.focus(); }} catch(e) {{}}
            const opts = {{ bubbles: true, cancelable: true, view: window }};
            trigger.dispatchEvent(new PointerEvent('pointerdown', opts));
            trigger.dispatchEvent(new MouseEvent('mousedown', opts));
            trigger.dispatchEvent(new PointerEvent('pointerup', opts));
            trigger.dispatchEvent(new MouseEvent('mouseup', opts));
            trigger.click();

            // If the trigger itself is an input (e.g. #source--source or Workday search input), type and enter directly
            if (trigger.tagName && trigger.tagName.toLowerCase() === 'input') {{
                const proto = window.HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                const targetVal = {json.dumps(val_clean)};
                if (setter) setter.call(trigger, targetVal); else trigger.value = targetVal;
                trigger.dispatchEvent(new Event('input', {{ bubbles: true }}));
                trigger.dispatchEvent(new Event('change', {{ bubbles: true }}));
                trigger.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                trigger.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
            }}
            return true;
        }})()"""

        try:
            opened = bool(await agent.evaluate(js_open_dropdown))
        except Exception as e:
            logger.debug("Failed opening custom dropdown %s via JS: %s", selector, e)
            opened = False

        if not opened:
            # Also try native Playwright locator click on first primary selector to ensure popup event fires
            first_sel = selector.split(",")[0].strip()
            try:
                await agent.click(first_sel)
                opened = True
            except Exception:
                pass

        await asyncio.sleep(0.8)

        # Step 2: Search/filter and click the option inside the popup
        js_search_and_select = f"""(() => {{
            const targetVal = {json.dumps(val_clean)};
            const targetLower = {json.dumps(val_lower)};
            const hint = {json.dumps(hint_lower)};

            // Scope listbox container
            const listbox = document.querySelector(
                '[data-automation-id="popup-listbox"], [role="listbox"], ' +
                'div[data-automation-id="select-options-list"], ul[role="listbox"], ' +
                'div[role="dialog"], [data-automation-id="wd-popup-content"], div[id*="popup" i], ' +
                'div[data-automation-id*="popup" i], ul[data-automation-id*="popup" i]'
            );

            // Scope search input strictly INSIDE the popup dialog/listbox
            const searchInput = listbox ? listbox.querySelector(
                'input[data-automation-id="searchBox"], input[data-automation-id*="search" i], input[type="text"], input[role="searchbox"]'
            ) : null;
            if (searchInput) {{
                try {{ searchInput.focus(); }} catch(e) {{}}
                const proto = window.HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                if (setter) setter.call(searchInput, targetVal); else searchInput.value = targetVal;
                searchInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                searchInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                searchInput.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                searchInput.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
            }}

            const searchScope = listbox || document.body;
            const options = Array.from(searchScope.querySelectorAll(
                '[role="option"], [data-automation-id="menuItem"], [data-automation-id*="promptOption" i], ' +
                'li, div[data-automation-id*="option" i], [data-automation-id="select-option"], ' +
                'div[data-automation-id*="item" i], div[data-automation-id*="leaf" i], [role="treeitem"], ' +
                'div[data-automation-id*="row" i], [role="menuitem"], [role="button"]'
            )).filter(opt => {{
                const s = window.getComputedStyle(opt);
                return s.display !== 'none' && s.visibility !== 'hidden';
            }});

            const getOptText = (o) => {{
                const autoLabel = o.getAttribute('data-automation-label') || '';
                const inner = o.innerText || o.textContent || '';
                return (autoLabel || inner).trim().toLowerCase();
            }};

            // 1. Exact match
            let matched = options.find(o => getOptText(o) === targetLower);
            // 2. Contains match
            if (!matched) {{
                matched = options.find(o => {{
                    const t = getOptText(o);
                    return t === targetLower || t.includes(targetLower) || targetLower.includes(t);
                }});
            }}
            // 2b. Phone device type smart matching (Mobile / Telephone / Cell / Landline)
            if (!matched && (hint.includes('phone') || hint.includes('device') || targetLower.includes('mobile') || targetLower.includes('telephone') || targetLower.includes('cell'))) {{
                matched = options.find(o => {{
                    const t = getOptText(o);
                    return t.includes('mobile') || t.includes('cell') || t.includes('telephone') || t.includes('phone');
                }}) || options.find(o => {{
                    const t = getOptText(o);
                    return !t.includes('select') && !t.includes('choose');
                }});
            }}
            // 2c. Gender smart matching
            if (!matched && (hint.includes('gender') || hint.includes('sex'))) {{
                if (targetLower.includes('male') && !targetLower.includes('female')) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return (t === 'male' || t.startsWith('male ') || t.includes('man') || t.includes('he/him')) && !t.includes('female');
                    }});
                }} else if (targetLower.includes('female')) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return t === 'female' || t.includes('woman') || t.includes('she/her');
                    }});
                }}
                if (!matched) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return t.includes('decline') || t.includes('prefer not') || t.includes('not disclose') || t.includes('do not wish');
                    }});
                }}
                if (!matched && options.length > 0) {{
                    matched = options.find(o => !/select|choose/i.test(getOptText(o))) || options[0];
                }}
            }}
            // 2d. Disability smart matching
            if (!matched && hint.includes('disability')) {{
                if (targetLower === 'no' || targetLower.includes('do not have') || targetLower.includes("don't have")) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return t.includes('no') || t.includes('do not have') || t.includes("don't have") || t.includes('no disability');
                    }});
                }} else if (targetLower === 'yes' || targetLower.includes('have a disability')) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return (t.includes('yes') || t.includes('have a disability')) && !t.includes('do not');
                    }});
                }}
                if (!matched) {{
                    matched = options.find(o => {{
                        const t = getOptText(o);
                        return t.includes('decline') || t.includes('prefer not') || t.includes('not disclose') || t.includes('do not wish');
                    }});
                }}
            }}
            // 3. Category drill-down fallback (e.g. LinkedIn -> Job Board / Social Media)
            if (!matched && (targetLower === 'linkedin' || hint.includes('source') || hint.includes('hear'))) {{
                matched = options.find(o => {{
                    const t = getOptText(o);
                    return t.includes('linkedin') || t.includes('job board') || t.includes('social media') || t.includes('career site') || t.includes('internet') || t.includes('website');
                }});
            }}
            // 4. Degree fallback: match any Bachelor / Undergraduate option
            if (!matched && (targetLower.includes('bachelor') || targetLower.includes('degree'))) {{
                matched = options.find(o => {{
                    const t = getOptText(o);
                    return t.includes('bachelor') || t.includes('degree') || t.includes('undergraduate');
                }});
            }}
            if (!matched && hint.includes('degree') && options.length > 0) {{
                matched = options.find(o => !o.getAttribute('aria-haspopup')) || options[0];
            }}

            if (matched) {{
                try {{ matched.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                try {{ matched.focus(); }} catch(e) {{}}
                const opts = {{ bubbles: true, cancelable: true, view: window }};
                matched.dispatchEvent(new PointerEvent('pointerdown', opts));
                matched.dispatchEvent(new MouseEvent('mousedown', opts));
                matched.dispatchEvent(new PointerEvent('pointerup', opts));
                matched.dispatchEvent(new MouseEvent('mouseup', opts));
                matched.click();
                return true;
            }}
            return false;
        }})()"""

        try:
            selected = bool(await agent.evaluate(js_search_and_select))
            if selected:
                await asyncio.sleep(0.6)
                # If a category was clicked, check if child options (e.g. LinkedIn) are now displayed to complete drill-down
                js_drilldown = f"""(() => {{
                    const targetLower = {json.dumps(val_lower)};
                    const listbox = document.querySelector(
                        '[data-automation-id="popup-listbox"], [role="listbox"], ' +
                        'div[data-automation-id="select-options-list"], ul[role="listbox"], ' +
                        'div[role="dialog"], [data-automation-id="wd-popup-content"], div[id*="popup" i]'
                    );
                    const scope = listbox || document.body;
                    const subOpts = Array.from(scope.querySelectorAll(
                        '[role="option"], [data-automation-id="menuItem"], [data-automation-id*="promptOption" i], ' +
                        'li, div[data-automation-id*="option" i], [data-automation-id="select-option"], ' +
                        'div[data-automation-id*="item" i], div[data-automation-id*="leaf" i]'
                    )).filter(opt => {{
                        const s = window.getComputedStyle(opt);
                        return s.display !== 'none' && s.visibility !== 'hidden';
                    }});
                    const subMatch = subOpts.find(o => {{
                        const autoLabel = o.getAttribute('data-automation-label') || '';
                        const t = (autoLabel || o.innerText || o.textContent || '').trim().toLowerCase();
                        return t === targetLower || t.includes(targetLower);
                    }}) || (subOpts.length > 0 ? subOpts[0] : null);
                    if (subMatch) {{
                        try {{ subMatch.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                        try {{ subMatch.focus(); }} catch(e) {{}}
                        const opts = {{ bubbles: true, cancelable: true, view: window }};
                        subMatch.dispatchEvent(new PointerEvent('pointerdown', opts));
                        subMatch.dispatchEvent(new MouseEvent('mousedown', opts));
                        subMatch.dispatchEvent(new PointerEvent('pointerup', opts));
                        subMatch.dispatchEvent(new MouseEvent('mouseup', opts));
                        subMatch.click();
                        return true;
                    }}
                    return false;
                }})()"""
                sub_selected = bool(await agent.evaluate(js_drilldown))
                await asyncio.sleep(0.4)
                return True, None
        except Exception as e:
            logger.debug("Workday dropdown option selection error: %s", e)

        # Fallback 3: Stagehand AI act (if LLM is configured)
        if hasattr(agent, "act") and getattr(agent, "stagehand", None) and getattr(agent.stagehand, "model", None):
            try:
                logger.info("Attempting Stagehand AI fallback to select '%s' for '%s'...", val, label_hint)
                act_res = await agent.act(f"Select '{val}' in the '{label_hint}' dropdown")
                if act_res:
                    return True, None
            except Exception as act_err:
                logger.debug("Stagehand AI act fallback failed: %s", act_err)

        return False, f"Could not select '{val}' in custom dropdown '{label_hint}'"

    async def fill_workday_repeaters(self, agent: BrowserAgent, candidate_context: Dict[str, Any]) -> None:
        """Populates Workday's dynamic repeater sections (Work Experience, Education, Skills, Social Links)."""
        try:
            # Check if we are on Workday application flow
            is_exp_page = await agent.evaluate("""(() => {
                const page = document.querySelector('[data-automation-id="applyFlowMyExpPage"]');
                const bodyText = (document.body ? document.body.innerText : '').toLowerCase();
                return !!page || (bodyText.includes('work experience') && bodyText.includes('education'));
            })()""")
            if not is_exp_page:
                return

            work_exps = candidate_context.get("work_experience") or candidate_context.get("profile.work_experiences") or []
            edu_list = candidate_context.get("education") or candidate_context.get("profile.education") or []
            skills = candidate_context.get("skills") or candidate_context.get("profile.skills") or []
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",") if s.strip()]

            # 1. Work Experience Section
            if work_exps:
                await self._populate_workday_work_experience(agent, work_exps)

            # 2. Education Section
            if edu_list:
                await self._populate_workday_education(agent, edu_list)

            # 3. Skills Section
            if skills:
                await self._populate_workday_skills(agent, skills)

            # 4. Social Network (LinkedIn)
            linkedin_url = (
                candidate_context.get("profile", {}).get("linkedin_url")
                or candidate_context.get("profile.linkedin_url")
                or candidate_context.get("social_urls", {}).get("linkedin")
                or candidate_context.get("linkedin")
                or "https://www.linkedin.com/in/ahmad10raza/"
            )
            if linkedin_url:
                js_social = f"""(() => {{
                    const li = document.querySelector('input[id*="linkedInAccount"], input[name*="linkedInAccount"]');
                    if (li && !li.value) {{
                        li.focus();
                        li.value = {json.dumps(str(linkedin_url))};
                        li.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        li.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        li.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }})()"""
                await agent.evaluate(js_social)
        except Exception as e:
            logger.warning("Error during Workday repeater filling: %s", e)

    async def _populate_workday_work_experience(self, agent: BrowserAgent, work_exps: List[Dict[str, Any]]) -> None:
        """Expands and populates Workday work experience items."""
        month_map = {
            "january": "01", "jan": "01", "1": "01", "01": "01",
            "february": "02", "feb": "02", "2": "02", "02": "02",
            "march": "03", "mar": "03", "3": "03", "03": "03",
            "april": "04", "apr": "04", "4": "04", "04": "04",
            "may": "05", "5": "05", "05": "05",
            "june": "06", "jun": "06", "6": "06", "06": "06",
            "july": "07", "jul": "07", "7": "07", "07": "07",
            "august": "08", "aug": "08", "8": "08", "08": "08",
            "september": "09", "sep": "09", "9": "09", "09": "09",
            "october": "10", "oct": "10", "10": "10",
            "november": "11", "nov": "11", "11": "11",
            "december": "12", "dec": "12", "12": "12",
        }

        for idx, exp in enumerate(work_exps[:3]):
            title = exp.get("title") or exp.get("job_title") or ""
            company = exp.get("company") or exp.get("employer") or ""
            loc = exp.get("location") or ""
            is_curr = bool(exp.get("is_current", True))
            desc = exp.get("description") or ""

            raw_s_m = str(exp.get("start_month", "11")).strip().lower()
            s_month = month_map.get(raw_s_m, raw_s_m.zfill(2) if raw_s_m.isdigit() else "11")
            s_year = str(exp.get("start_year", "2024")).strip()

            raw_e_m = str(exp.get("end_month", "")).strip().lower()
            e_month = month_map.get(raw_e_m, raw_e_m.zfill(2) if raw_e_m.isdigit() else "")
            e_year = str(exp.get("end_year", "")).strip()

            # Click Add / Add Another if needed
            js_open = f"""(() => {{
                const page = document.querySelector('[data-automation-id="applyFlowMyExpPage"]') || document.body;
                const existing = page.querySelectorAll('input[id*="jobTitle"], [data-automation-id="jobTitle"]');
                if (existing.length > {idx}) return "ready";

                if ({idx} === 0) {{
                    const firstAdd = page.querySelector('button[data-automation-id="add-button"]');
                    if (firstAdd) {{
                        try {{ firstAdd.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                        firstAdd.click();
                        return "clicked";
                    }}
                }} else {{
                    const allAddAnother = Array.from(page.querySelectorAll('button')).filter(b => (b.innerText || '').trim().toLowerCase() === 'add another');
                    if (allAddAnother.length > 0) {{
                        try {{ allAddAnother[0].scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                        allAddAnother[0].click();
                        return "clicked";
                    }}
                }}
                return "none";
            }})()"""
            open_res = await agent.evaluate(js_open)
            if open_res == "clicked":
                await asyncio.sleep(1.5)
            elif open_res == "none" and idx > 0:
                break

            # Populate fields for item idx
            js_fill = f"""(() => {{
                function setVal(el, val) {{
                    if (!el) return;
                    el.focus();
                    const proto = window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) setter.call(el, val); else el.value = val;
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}
                function setTextarea(el, val) {{
                    if (!el) return;
                    el.focus();
                    const proto = window.HTMLTextAreaElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) setter.call(el, val); else el.value = val;
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}

                const titles = document.querySelectorAll('input[id*="jobTitle"], [data-automation-id="jobTitle"]');
                const companies = document.querySelectorAll('input[id*="companyName"], [data-automation-id="company"]');
                const locations = document.querySelectorAll('input[id*="location"], [data-automation-id="location"]');
                const currentChks = document.querySelectorAll('input[id*="currentlyWorkHere"], [data-automation-id="currentlyWorkHere"]');
                const sMonths = document.querySelectorAll('input[id*="startDate-dateSectionMonth-input"], [data-automation-id="dateSectionMonth-input"]');
                const sYears = document.querySelectorAll('input[id*="startDate-dateSectionYear-input"], [data-automation-id="dateSectionYear-input"]');
                const eMonths = document.querySelectorAll('input[id*="endDate-dateSectionMonth-input"]');
                const eYears = document.querySelectorAll('input[id*="endDate-dateSectionYear-input"]');
                const descBoxes = document.querySelectorAll('textarea[id*="roleDescription"], [data-automation-id="description"], textarea');

                if (titles[{idx}]) setVal(titles[{idx}], {json.dumps(title)});
                if (companies[{idx}]) setVal(companies[{idx}], {json.dumps(company)});
                if (locations[{idx}]) setVal(locations[{idx}], {json.dumps(loc)});
                if (sMonths[{idx}]) setVal(sMonths[{idx}], {json.dumps(s_month)});
                if (sYears[{idx}]) setVal(sYears[{idx}], {json.dumps(s_year)});
                if (descBoxes[{idx}]) setTextarea(descBoxes[{idx}], {json.dumps(desc)});

                const chk = currentChks[{idx}];
                if (chk) {{
                    if ({json.dumps(is_curr)} && !chk.checked) {{
                        chk.click();
                    }} else if (!{json.dumps(is_curr)}) {{
                        if (chk.checked) chk.click();
                        if (eMonths[{idx}]) setVal(eMonths[{idx}], {json.dumps(e_month)});
                        if (eYears[{idx}]) setVal(eYears[{idx}], {json.dumps(e_year)});
                    }}
                }}
                return true;
            }})()"""
            await agent.evaluate(js_fill)
            logger.info("Populated Work Experience #%d: '%s' at '%s'", idx + 1, title, company)
            await asyncio.sleep(0.5)

    async def _populate_workday_education(self, agent: BrowserAgent, edu_list: List[Dict[str, Any]]) -> None:
        """Expands and populates Workday education items."""
        for idx, edu in enumerate(edu_list[:2]):
            degree = edu.get("degree") or ""
            school = edu.get("institution") or edu.get("school") or edu.get("university") or ""
            field_study = edu.get("field_of_study") or edu.get("major") or ""
            gpa = str(edu.get("gpa") or edu.get("cgpa") or "")

            js_open = f"""(() => {{
                const page = document.querySelector('[data-automation-id="applyFlowMyExpPage"]') || document.body;
                const existing = page.querySelectorAll('input[id*="school"], [data-automation-id="school"]');
                if (existing.length > {idx}) return "ready";

                if ({idx} === 0) {{
                    const inst = page.querySelector('[data-automation-id="instructionalText"]');
                    let eduBtn = inst ? inst.parentElement.querySelector('button[data-automation-id="add-button"]') : null;
                    if (!eduBtn) {{
                        const addBtns = Array.from(page.querySelectorAll('button[data-automation-id="add-button"]'));
                        if (addBtns.length > 0) eduBtn = addBtns[addBtns.length - 1];
                    }}
                    if (eduBtn) {{
                        try {{ eduBtn.scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                        eduBtn.click();
                        return "clicked";
                    }}
                }} else {{
                    const allAddAnother = Array.from(page.querySelectorAll('button')).filter(b => (b.innerText || '').trim().toLowerCase() === 'add another');
                    if (allAddAnother.length > 1) {{
                        try {{ allAddAnother[1].scrollIntoView({{ behavior: 'instant', block: 'center' }}); }} catch(e) {{}}
                        allAddAnother[1].click();
                        return "clicked";
                    }}
                }}
                return "none";
            }})()"""
            open_res = await agent.evaluate(js_open)
            if open_res == "clicked":
                await asyncio.sleep(1.5)
            elif open_res == "none" and idx > 0:
                break

            # 1. School or University typeahead
            js_search_school = f"""(() => {{
                const schools = Array.from(document.querySelectorAll('input[id*="--school"], input[id*="school"], [data-automation-id="school"]'));
                const targetInp = schools[{idx}] || schools[0];
                if (!targetInp) return false;
                targetInp.scrollIntoView({{ behavior: 'instant', block: 'center' }});
                targetInp.focus();
                targetInp.click();

                const proto = window.HTMLInputElement.prototype;
                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                const val = "School Not Found";
                if (setter) setter.call(targetInp, val); else targetInp.value = val;
                targetInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                targetInp.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                targetInp.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                return true;
            }})()"""
            await agent.evaluate(js_search_school)
            await asyncio.sleep(1.5)

            # Confirm School selection from visible options
            js_confirm_school = """(() => {
                const allOpts = Array.from(document.querySelectorAll('[role="option"], [data-automation-id="menuItem"], [data-automation-id*="promptOption"], [data-automation-id="select-option"], li')).filter(o => {
                    const r = o.getBoundingClientRect();
                    return r.width > 0 && r.height > 0 && window.getComputedStyle(o).visibility !== 'hidden';
                });
                const match = allOpts.find(o => {
                    const t = (o.innerText || o.textContent || '').toLowerCase();
                    return t.includes('not found');
                }) || allOpts.find(o => !/no items/i.test(o.innerText || ''));
                if (match) {
                    try { match.scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
                    match.click();
                    return true;
                }
                return false;
            })()"""
            try:
                await agent.evaluate(js_confirm_school)
            except Exception:
                pass
            await asyncio.sleep(1.5)

            # 2. Degree dropdown - open and select option
            try:
                await agent.click('button[id*="--degree"], button[id*="degree"]')
            except Exception:
                await agent.evaluate("""(() => {
                    const degBtn = document.querySelector('button[id*="--degree"], button[id*="degree"], [data-automation-id*="degree" i]');
                    if (degBtn) {
                        degBtn.scrollIntoView({ behavior: 'instant', block: 'center' });
                        degBtn.focus();
                        degBtn.click();
                    }
                })()""")

            await asyncio.sleep(1.2)

            # Select Bachelor option via native click or JS evaluate
            selected_deg_text = None
            try:
                clicked = await agent.click('ul[role="listbox"] li[role="option"] >> text=Bachelor', timeout_ms=3000)
                if clicked:
                    selected_deg_text = "Bachelor's Degree (Other)"
                    logger.info("Workday degree selected via agent.click: %s", selected_deg_text)
            except Exception:
                pass

            if not selected_deg_text:
                js_select_degree = """(() => {
                    const opts = Array.from(document.querySelectorAll('ul[role="listbox"] li[role="option"], [role="listbox"] [role="option"]'));
                    const match = opts.find(o => (o.innerText || o.textContent || '').toLowerCase().includes('bachelor')) ||
                                  opts.find(o => {
                                      const t = (o.innerText || o.textContent || '').toLowerCase();
                                      return (t.includes('degree') || t.includes('undergraduate') || t.includes('associate')) && !t.includes('not found') && !t.includes('no items');
                                  });
                    if (match) {
                        try { match.scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
                        try { match.focus(); } catch(e) {}
                        match.click();
                        return (match.innerText || '').trim();
                    }
                    return null;
                })()"""
                for attempt in range(8):
                    await asyncio.sleep(0.5)
                    try:
                        res = await agent.evaluate(js_select_degree)
                        if res:
                            selected_deg_text = res
                            logger.info("Workday degree selection result: %s (attempt %d)", selected_deg_text, attempt + 1)
                            break
                    except Exception:
                        pass

            await asyncio.sleep(0.5)
            deg_check = await agent.evaluate("""(() => {
                const degBtn = document.querySelector('button[id*="--degree"], button[id*="degree"], [data-automation-id*="degree" i]');
                return degBtn ? (degBtn.innerText || '').trim() : '';
            })()""")
            logger.info("Degree button text after selection: '%s'", deg_check)

            # 3. Field of Study & GPA
            if field_study or gpa:
                js_fill_other = f"""(() => {{
                    function setVal(el, val) {{
                        if (!el) return;
                        el.focus();
                        const proto = window.HTMLInputElement.prototype;
                        const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                        if (setter) setter.call(el, val); else el.value = val;
                        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    const fields = document.querySelectorAll('input[id*="fieldOfStudy"], [data-automation-id="field-of-study"]');
                    const gpas = document.querySelectorAll('input[id*="gpa"], [data-automation-id="gpa"]');
                    if (fields[{idx}] && {json.dumps(field_study)}) setVal(fields[{idx}], {json.dumps(field_study)});
                    if (gpas[{idx}] && {json.dumps(gpa)}) setVal(gpas[{idx}], {json.dumps(gpa)});
                }})()"""
                try:
                    await agent.evaluate(js_fill_other)
                except Exception:
                    pass

            logger.info("Populated Education #%d: '%s' at '%s'", idx + 1, degree, school)
            await asyncio.sleep(0.5)

    async def _populate_workday_skills(self, agent: BrowserAgent, skills: List[str]) -> None:
        """Finds Workday skills input and types candidate skills."""
        for skill in skills[:7]:
            js_search = f"""(() => {{
                const input = document.querySelector(
                    'input[id="skills--skills"], [data-automation-id="skillsPromptSearch"], ' +
                    'input[placeholder*="skill" i], div[data-automation-id*="skill" i] input'
                );
                if (!input) return false;
                input.focus();
                input.value = {json.dumps(skill)};
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                input.dispatchEvent(new KeyboardEvent('keyup', {{ key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }}));
                return true;
            }})()"""
            try:
                found = bool(await agent.evaluate(js_search))
                if found:
                    await asyncio.sleep(0.8)
                    # Click first visible option if dropdown appeared
                    await agent.evaluate("""(() => {
                        const allOpts = Array.from(document.querySelectorAll('[role="option"], [data-automation-id="menuItem"], [data-automation-id*="promptOption"], li')).filter(o => {
                            const r = o.getBoundingClientRect();
                            return r.width > 0 && r.height > 0 && window.getComputedStyle(o).visibility !== 'hidden' && !/no items/i.test(o.innerText || '');
                        });
                        if (allOpts.length > 0) {
                            try { allOpts[0].scrollIntoView({ behavior: 'instant', block: 'center' }); } catch(e) {}
                            allOpts[0].click();
                        }
                    })()""")
                    await asyncio.sleep(0.4)
            except Exception:
                pass
