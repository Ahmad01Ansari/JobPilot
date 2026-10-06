"""Generic DOM Page Analyzer and schema extractor for career sites and ATS portals."""

import asyncio
from dataclasses import dataclass, field
import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.automation.universal_agent.browser_agent.base import BrowserAgent

logger = logging.getLogger(__name__)


@dataclass
class FormFieldInfo:
    """Represents a discovered and normalized interactive form input."""

    field_id: str
    name: str
    selector: str
    input_type: str  # text, email, tel, file, radio_group, select, textarea, checkbox
    label: str
    placeholder: str = ""
    required: bool = False
    options: List[Dict[str, str]] = field(default_factory=list)
    current_value: Optional[str] = None
    aria_label: Optional[str] = None
    has_autocomplete: bool = False
    autocomplete_type: Optional[str] = None


@dataclass
class FormAnalysisResult:
    """Complete structural analysis outcome of an application web page."""

    url: str
    title: str
    fields: List[FormFieldInfo] = field(default_factory=list)
    file_upload_fields: List[FormFieldInfo] = field(default_factory=list)
    submit_buttons: List[Dict[str, str]] = field(default_factory=list)
    next_buttons: List[Dict[str, str]] = field(default_factory=list)
    apply_now_buttons: List[Dict[str, str]] = field(default_factory=list)
    challenge_detected: Optional[str] = None  # None, "CAPTCHA_CHALLENGE", or "LOGIN_REQUIRED"
    is_multi_step: bool = False
    step_indicator: Optional[str] = None

    def get_field_by_id_or_name(self, identifier: str) -> Optional[FormFieldInfo]:
        """Looks up a field by matching field_id or name."""
        for f in self.fields:
            if f.field_id == identifier or f.name == identifier:
                return f
        return None

    def get_required_fields(self) -> List[FormFieldInfo]:
        """Returns all mandatory form fields requiring user/profile data."""
        return [f for f in self.fields if f.required]


# JavaScript extraction snippet executed directly inside page context
_DOM_EXTRACTION_JS = """(() => {
    // 1. Detect security challenges & login gates
    const hasPassword = !!document.querySelector('input[type="password"]');
    const hasCaptchaIframe = !!document.querySelector('iframe[src*="turnstile"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]');
    const hasCaptchaContainer = !!document.querySelector('#mock-cf-turnstile, .cf-turnstile, .g-recaptcha, .h-captcha');
    
    let hasCaptchaText = false;
    const captchaCandidates = document.querySelectorAll('[id*="captcha" i], [class*="captcha" i], input[name*="captcha" i], fieldset legend, div[class*="captcha" i]');
    for (const el of captchaCandidates) {
        const t = (el.innerText || el.textContent || el.id || el.getAttribute('name') || '').toLowerCase();
        if (t.includes('captcha') || t.includes('math question') || t.includes('security question') || t.includes('human visitor')) {
            hasCaptchaText = true;
            break;
        }
    }

    // Count visible application form inputs to distinguish blocking CAPTCHAs from inline ones
    const appInputs = document.querySelectorAll("input:not([type='hidden']):not([type='submit']):not([type='button']), textarea, select");
    let visibleAppInputCount = 0;
    for (const inp of appInputs) {
        const s = window.getComputedStyle(inp);
        if (s.display !== 'none' && s.visibility !== 'hidden' && inp.getBoundingClientRect().width > 0) {
            const n = (inp.name || inp.id || '').toLowerCase();
            // Exclude captcha-related hidden inputs (g-recaptcha-response, h-captcha-response)
            if (!n.includes('captcha') && !n.includes('recaptcha') && !n.includes('turnstile')) {
                visibleAppInputCount++;
            }
        }
    }

    let challenge = null;
    // Only flag CAPTCHA_CHALLENGE when CAPTCHA is the SOLE purpose of the page
    // (no visible application inputs). Inline CAPTCHAs on form pages are handled
    // by the pre-submit captcha check in the orchestrator.
    // Detect OTP / Two-Factor Challenge
    const otpInput = document.querySelector('input[autocomplete="one-time-code"], input[name*="code" i], input[id*="code" i], input[name*="otp" i], input[id*="otp" i], input[name*="pin" i], input[id*="pin" i], input[class*="pin-code"], .pin-code-input__input');
    const bodyText = (document.body ? document.body.innerText : '').toLowerCase();
    const isOtpChallenge = (!!otpInput && (/enter\s+(?:the\s+)?code|verification\s+code|when\s+you\s+get\s+the\s+code|one-time|passcode|check\s+your\s+email|security\s+code|sent\s+a\s+code|enter\s+otp/i.test(bodyText) || (visibleAppInputCount <= 6 && /code|otp|pin/i.test(bodyText)))) || /confirm\s+your\s+identity/i.test(bodyText) || !!document.querySelector('.pin-code-input__input, [class*="pin-code"]');

    if ((hasCaptchaIframe || hasCaptchaContainer || hasCaptchaText) && visibleAppInputCount === 0) {
        challenge = "CAPTCHA_CHALLENGE";
    } else if (hasPassword) {
        challenge = "LOGIN_REQUIRED";
    } else if (isOtpChallenge) {
        challenge = "TWO_FACTOR_AUTH";
    }

    // 2. Multi-step indicators
    const stepEl = document.querySelector('.step-indicator, [class*="step-indicator"], [class*="progress-bar"]');
    const stepText = stepEl ? stepEl.innerText.trim() : null;
    let isMultiStep = !!stepText || !!document.querySelector('button[id*="next" i], button[name*="next" i], input[value*="Next" i], button[class*="next" i], [data-automation-id*="next" i], [data-qa*="next" i], [aria-label*="next" i]');

    // Helper: find clean label text for an element
    function getCleanLabel(el) {
        let labelText = "";
        // 0. React-on-Rails / Pinpoint / modern ATS component container detection
        const reactComp = el.closest('[id*="-react-component-"], [data-dom-id*="-react-component-"]');
        if (reactComp) {
            const compId = reactComp.getAttribute('data-dom-id') || reactComp.id;
            if (compId) {
                const sc = document.querySelector(`script[data-dom-id="${CSS.escape(compId)}"]`);
                if (sc && sc.textContent) {
                    try {
                        const parsed = JSON.parse(sc.textContent);
                        if (parsed && parsed.questionDetails && parsed.questionDetails.title) {
                            return parsed.questionDetails.title.replace(/[*:]/g, '').trim();
                        }
                    } catch(e) {}
                }
            }
        }

        // 0b. Google Forms / Typeform / Survey question container detection
        const gformItem = el.closest('[role="listitem"], [jsmodel], .freebirdFormviewerViewItemsItemItem, .geS5n');
        if (gformItem) {
            const heading = gformItem.querySelector('[role="heading"], .M7eMe, [class*="ItemTitle"], [aria-level="3"]');
            if (heading && heading.innerText && heading.innerText.trim()) {
                const gTxt = heading.innerText.replace(/[*:]/g, '').trim();
                if (gTxt && !/^(your answer|answer|short answer text|long answer text)$/i.test(gTxt)) {
                    return gTxt;
                }
            }
        }

        // 1. Direct label for=id
        if (el.id) {
            const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
            if (lbl && lbl.innerText && lbl.innerText.trim()) labelText = lbl.innerText;
        }
        // 2. Direct label for=name
        if (!labelText && el.name) {
            const lbl = document.querySelector(`label[for="${CSS.escape(el.name)}"]`);
            if (lbl && lbl.innerText && lbl.innerText.trim()) labelText = lbl.innerText;
        }
        // 3. Wrapping label
        if (!labelText) {
            const parentLabel = el.closest('label');
            if (parentLabel && parentLabel.innerText && parentLabel.innerText.trim()) {
                const clone = parentLabel.cloneNode(true);
                const innerInputs = clone.querySelectorAll('input, select, textarea, button');
                innerInputs.forEach(i => i.remove());
                labelText = clone.innerText.trim();
            }
        }
        // 4. aria-labelledby
        if (!labelText && el.getAttribute('aria-labelledby')) {
            const labelled = document.getElementById(el.getAttribute('aria-labelledby'));
            if (labelled && labelled.innerText && labelled.innerText.trim()) labelText = labelled.innerText;
        }
        // 5. aria-label (ignore generic placeholder labels)
        if (!labelText && el.getAttribute('aria-label')) {
            const ariaVal = el.getAttribute('aria-label').trim();
            if (!/^(your answer|answer|short answer text|long answer text)$/i.test(ariaVal)) {
                labelText = ariaVal;
            }
        }
        // 5b. Direct element attributes (data-name, data-field-name, data-label, placeholder)
        if (!labelText || /^(yes|no|true|false|your answer|answer)$/i.test(labelText.trim())) {
            const attrLabel = el.getAttribute('data-name') || el.getAttribute('data-field-name') || el.getAttribute('data-label') || el.placeholder || '';
            if (attrLabel && attrLabel.trim().length > 1 && !/^(your answer|answer|short answer text|long answer text)$/i.test(attrLabel.trim())) {
                labelText = attrLabel;
            }
        }
        // 5c. If label is generic button text (e.g. 'Upload File', 'Browse', 'Choose File'), check data-name or parent title
        if (/^(upload\s*file|upload|browse|choose\s*file|select\s*file|attach\s*file)$/i.test(labelText.trim())) {
            const dataName = el.getAttribute('data-name') || el.getAttribute('data-field-name');
            if (dataName && dataName.trim().length > 1) {
                labelText = dataName;
            } else {
                const parentBox = el.closest('.w-file-upload, [class*="file-upload" i], .form-group, .field-group');
                if (parentBox) {
                    const headingLbl = parentBox.querySelector('label:not([class*="upload"]), [class*="label"]:not([class*="upload"]), b, h4, h5, span');
                    if (headingLbl && headingLbl.innerText && headingLbl.innerText.trim().length > 2) {
                        labelText = headingLbl.innerText.trim();
                    }
                }
            }
        }
        // 6. Immediate field group container search
        if (!labelText || /^(yes|no|true|false)$/i.test(labelText.trim())) {
            const group = el.closest('.form-group, .field-group, .input-group, .form-row, td, .col-lg-12, .col-md-12, .col-sm-12');
            if (group) {
                const groupLbl = group.querySelector('label, .control-label, [class*="label"]:not([class*="container"]):not([class*="form"]), h4, h5, b, span.asterisk + span');
                if (groupLbl && groupLbl !== el && !groupLbl.contains(el)) {
                    const txt = groupLbl.innerText.trim();
                    if (txt && !txt.includes('CAPTCHA') && !txt.includes('human visitor')) {
                        labelText = txt;
                    }
                }
            }
        }
        // 7. Preceding sibling search (stop if preceding sibling contains another form control)
        if (!labelText || /^(yes|no|true|false)$/i.test(labelText.trim())) {
            let prev = el.previousElementSibling;
            while (prev) {
                // If previous sibling is or contains another form control, STOP — do NOT steal its label!
                if (prev.matches('input, select, textarea, button, .w-file-upload, [class*="file-upload" i]') || prev.querySelector('input, select, textarea, button, [type="file"]')) {
                    break;
                }
                if (prev.tagName.toLowerCase() === 'label' || prev.tagName.toLowerCase() === 'span' || prev.tagName.toLowerCase() === 'b' || prev.querySelector('label')) {
                    const lbl = (prev.tagName.toLowerCase() === 'label') ? prev : (prev.querySelector('label') || prev);
                    if (lbl && lbl.innerText && lbl.innerText.trim()) {
                        const txt = lbl.innerText.trim();
                        if (!txt.includes('CAPTCHA')) {
                            labelText = txt;
                            break;
                        }
                    }
                }
                prev = prev.previousElementSibling;
            }
        }
        // 8. Section or Question Heading search for fieldset / custom question cards
        if (!labelText || /^(yes|no|true|false)$/i.test(labelText.trim())) {
            const qContainer = el.closest('[role="radiogroup"], [id*="-react-component-"], [class*="question" i], [id*="question" i], fieldset');
            if (qContainer) {
                const headingEl = qContainer.querySelector('legend, h1, h2, h3, h4, h5, h6, [class*="title" i], [class*="question" i] p, p:not([class*="option"]):not([class*="radio"]):not([class*="help"])');
                if (headingEl && headingEl !== el && !headingEl.contains(el)) {
                    const txt = (headingEl.innerText || headingEl.textContent || '').replace(/[*:]/g, '').trim();
                    if (txt && txt.length > 3 && !/^(yes|no|male|female|other|agree|disagree)$/i.test(txt) && !txt.includes('CAPTCHA')) {
                        labelText = txt;
                    }
                }
            }
        }
        // 9. Attributes fallback (placeholder, title, data-label, data-name, data-field-name)
        if (!labelText || /^(yes|no|true|false)$/i.test(labelText.trim())) {
            labelText = el.getAttribute('data-field-name') || el.getAttribute('data-name') || el.getAttribute('data-label') || el.placeholder || el.title || '';
        }
        // 9b. Select element first option placeholder fallback (e.g. <option value="">Experience*</option>)
        if (!labelText && el.tagName && el.tagName.toLowerCase() === 'select') {
            const firstOpt = el.querySelector('option[value=""], option:disabled, option:first-child');
            if (firstOpt && (firstOpt.text || firstOpt.innerText)) {
                const optTxt = (firstOpt.text || firstOpt.innerText).replace(/[*:]/g, '').trim();
                if (optTxt && !/^(select|choose|please select|--+|select an option)$/i.test(optTxt)) {
                    labelText = optTxt;
                }
            }
        }
        // 9c. Raw element name or id humanized fallback
        if (!labelText) {
            const rawKey = (el.name || el.id || '').replace(/[-_]/g, ' ').replace(/\d+$/, '').trim();
            if (rawKey && rawKey.length >= 3 && !/^[0-9a-f]{8,}$/i.test(rawKey)) {
                labelText = rawKey;
            }
        }
        // 8. Script tag ATS schema inspection if label is empty or looks like random hash / option
        const isHash = /^[a-z0-9_-]{7,}$/i.test(labelText.trim()) || /^(yes|no|true|false)$/i.test(labelText.trim());
        if (!labelText || isHash) {
            const fKey = el.id || el.name || '';
            if (fKey && fKey.length >= 4) {
                const scripts = Array.from(document.querySelectorAll('script[type="application/json"], script.js-react-on-rails-component, script'));
                for (const sc of scripts) {
                    const text = sc.textContent || '';
                    if (text.includes(fKey)) {
                        // Priority: questionDetails -> title
                        const mTitle = text.match(/"title"\s*:\s*"([^"]+)"/i);
                        if (mTitle && mTitle[1]) {
                            labelText = mTitle[1];
                            break;
                        }
                        const m = text.match(new RegExp('\\\\"' + CSS.escape(fKey) + '\\\\"(?:,\\\\"[^\\\\"]*\\\\"){1,4},\\\\"(street|city|state|postalcode|phone[^\\\\"]*)\\\",\\\\\"([^\\\\\\"]+)\\\\\"', 'i'));
                        if (m && m[2]) {
                            labelText = m[2];
                            break;
                        }
                        const m2 = text.match(new RegExp('["\\\']' + CSS.escape(fKey) + '["\\\'][^}\\]]*?["\\\'](?:question|label|mapping|title)["\\\']\\\\s*:\\\\s*["\\\']([^"\\\']+)["\\\']', 'i'));
                        if (m2 && m2[1]) {
                            labelText = m2[1];
                            break;
                        }
                    }
                }
            }
        }
        return labelText.replace(/[*:]/g, '').trim();
    }

    // Auto-rescue stale or rejected file upload tags on ATS forms (e.g. Pinpoint, Workday, Greenhouse)
    const pageText = document.body ? (document.body.innerText || '') : '';
    const hasFileError = /invalid content type|unsupported file format|invalid file|upload failed/i.test(pageText);
    const removeButtons = Array.from(document.querySelectorAll('button.bp3-tag-remove, button[aria-label="Remove"], .file-field .bp3-tag-remove, .file-field .remove, .file-tag-remove'));
    if (hasFileError && removeButtons.length > 0) {
        for (const btn of removeButtons) {
            try { btn.click(); } catch(e) {}
        }
    }

    // 3. Scan inputs, selects, and textareas (including accessible iframes)
    let rawElements = Array.from(document.querySelectorAll('input, select, textarea'));
    const iframes = Array.from(document.querySelectorAll('iframe'));
    for (const ifr of iframes) {
        try {
            const idoc = ifr.contentDocument || ifr.contentWindow.document;
            if (idoc) {
                rawElements = rawElements.concat(Array.from(idoc.querySelectorAll('input, select, textarea')));
            }
        } catch(e) {}
    }
    const elementsData = [];
    const radioGroups = {};

    for (const el of rawElements) {
        const type = (el.type || '').toLowerCase();
        if (['hidden', 'submit', 'button', 'reset'].includes(type)) continue;

        // Anti-bot honeypot trap detection (e.g. Oracle HCM honey-pot-1)
        const nameAttr = (el.name || '').toLowerCase();
        const idAttr = (el.id || '').toLowerCase();
        const classAttr = (el.className || '').toLowerCase();
        const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
        if (/honey|honeypot|fake[-_]?field|bot[-_]?field/i.test(nameAttr + ' ' + idAttr + ' ' + classAttr + ' ' + ariaLabel)) {
            continue;
        }

        // Visibility check: element must have rendered size and be visible
        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') continue;

        // Check if element is enclosed in an ancestral closed modal or hidden dialog
        if (el.parentElement) {
            const modalAncestor = el.parentElement.closest('.modal, dialog, [role="dialog"], .popup');
            if (modalAncestor) {
                if (modalAncestor.tagName.toLowerCase() === 'dialog' && !modalAncestor.open) continue;
                if (modalAncestor.getAttribute('aria-hidden') === 'true') continue;
                if (modalAncestor.classList.contains('fade') && !modalAncestor.classList.contains('show')) continue;
                const mStyle = window.getComputedStyle(modalAncestor);
                if (mStyle.display === 'none' || mStyle.visibility === 'hidden' || mStyle.opacity === '0') continue;
            }
        }

        const isCustomInput = type === 'checkbox' || type === 'radio' || type === 'file';
        if (!isCustomInput) {
            if (rect.width === 0 || rect.height === 0) continue;
            if (style.opacity === '0') continue;
            if (typeof el.checkVisibility === 'function' && !el.checkVisibility({ checkOpacity: true, checkVisibilityCSS: true })) continue;
        } else {
            // For custom/hidden inputs, ensure their parent or wrapper container is visible
            if (el.parentElement && typeof el.parentElement.checkVisibility === 'function' && !el.parentElement.checkVisibility()) {
                continue;
            }
            const wrapper = el.closest('label, .pretty, .custom-control, .checkbox, .radio, .form-check, .field-group, .file-upload, .upload-container, .w-file-upload, [class*="file-upload" i], [class*="upload" i]');
            if (wrapper) {
                const wStyle = window.getComputedStyle(wrapper);
                if (wStyle.display === 'none' || wStyle.visibility === 'hidden') continue;
            }
        }

        // Ignore elements inside site header, navigation bar, footer, search modal, or alert/newsletter containers
        if (el.closest('header, nav, footer, .header, .footer, .navbar, .nav, #header, #footer, #search, .search-form, .search-suggestion, #mainMenu, .main-menu, .menu, .dropdown-menu, .header-extras, .mega-menu, [class*="alert" i], [id*="alert" i], [class*="newsletter" i], [id*="newsletter" i], [class*="subscribe" i], [id*="subscribe" i], [class*="share" i]')) {
            continue;
        }

        const id = el.id || '';
        const name = el.name || '';
        const placeholder = el.placeholder || '';
        const lowerAll = (id + ' ' + name + ' ' + placeholder + ' ' + (el.className || '')).toLowerCase();

        // Ignore global site search, newsletter subscription, feedback, language selector
        if (type === 'search' || /search|keyword|nav-search|global-search|newsletter|subscribe|feedback|job-alert|alert-email/i.test(lowerAll)) {
            continue;
        }

        let required = el.required || el.getAttribute('aria-required') === 'true' || !!el.getAttribute('data-val-required') || placeholder.startsWith('*');
        if (!required) {
            const container = el.closest('.col-md-1-1, .col-1-1, .form-group, .field-group, [class*="form-group" i], [class*="field" i], [class*="question" i], [id*="question" i], fieldset, [id*="-react-component-"]');
            if (container) {
                if (container.querySelector('.required, [class*="required" i], [class*="asterisk" i]') || (container.innerText || '').includes('*')) {
                    required = true;
                }
                const compId = container.getAttribute?.('data-dom-id') || container.id;
                if (compId) {
                    const sc = document.querySelector(`script[data-dom-id="${compId.replace(/"/g, '\\"')}"]`);
                    if (sc && sc.textContent && sc.textContent.includes('"required":true')) {
                        required = true;
                    }
                }
            }
            if (!required && id) {
                try {
                    const lbl = document.querySelector(`label[for="${CSS.escape(id)}"]`) || el.closest('label');
                    if (lbl) {
                        const afterStr = window.getComputedStyle(lbl, '::after').content || '';
                        const beforeStr = window.getComputedStyle(lbl, '::before').content || '';
                        if (afterStr.includes('*') || beforeStr.includes('*')) {
                            required = true;
                        }
                    }
                } catch(e) {}
            }
        }
        if (type === 'file' && /resume|cv|curriculum|résumé/i.test(lowerAll)) {
            required = true;
        }

        const currentVal = el.value || '';
        const label = getCleanLabel(el);

        if (type === 'radio') {
            const groupContainer = el.closest('[role="radiogroup"], [id*="-react-component-"], fieldset, [class*="question" i], [id*="question" i], .form-group, .field-group') || el.parentElement?.parentElement;
            let groupLabel = label;
            let isGroupReq = required;

            if (groupContainer) {
                const reactComp = groupContainer.closest('[id*="-react-component-"], [data-dom-id*="-react-component-"]') || groupContainer;
                const compId = reactComp.getAttribute?.('data-dom-id') || reactComp.id;
                if (compId) {
                    const sc = document.querySelector(`script[data-dom-id="${compId.replace(/"/g, '\\"')}"]`);
                    if (sc && sc.textContent) {
                        try {
                            const parsed = JSON.parse(sc.textContent);
                            if (parsed && parsed.questionDetails) {
                                if (parsed.questionDetails.title) groupLabel = parsed.questionDetails.title.replace(/[*:]/g, '').trim();
                                if (parsed.questionDetails.required) isGroupReq = true;
                            }
                        } catch(e) {}
                    }
                }
                if (!groupLabel || /^(yes|no|true|false)$/i.test(groupLabel.trim())) {
                    const headingEl = groupContainer.querySelector('legend, h1, h2, h3, h4, h5, h6, [class*="title" i], [class*="label" i]:not([class*="checkable"]):not([class*="option"]):not([class*="radio"]), label:not([class*="checkable"]):not([class*="option"]):not([class*="radio"]), [class*="question" i] p, [class*="question" i] span, p:not([class*="option"]):not([class*="radio"])');
                    if (headingEl && headingEl.innerText) {
                        const t = headingEl.innerText.replace(/[*:]/g, '').trim();
                        if (t && t.length > 3 && !/^(yes|no)$/i.test(t)) {
                            groupLabel = t;
                        }
                    }
                }
            }

            const groupKey = name || groupLabel || id || 'unnamed_radio_group';
            if (!radioGroups[groupKey]) {
                const safeName = name ? name.replace(/"/g, '\\"') : '';
                radioGroups[groupKey] = {
                    field_id: id || groupKey,
                    name: name,
                    selector: safeName ? `input[name="${safeName}"]` : `input[type="radio"]`,
                    input_type: 'radio_group',
                    label: groupLabel,
                    required: isGroupReq,
                    options: [],
                    current_value: null,
                };
            }
            if (isGroupReq) radioGroups[groupKey].required = true;
            if (groupLabel && (!radioGroups[groupKey].label || /^(yes|no)$/i.test(radioGroups[groupKey].label.trim()))) {
                radioGroups[groupKey].label = groupLabel;
            }
            
            let optLabel = '';
            const lbl = el.closest('label');
            if (lbl) {
                const visibleSpan = lbl.querySelector('span:not(.sr-only), span[class*="label"], span[class*="text"]');
                if (visibleSpan && visibleSpan.innerText && visibleSpan.innerText.trim()) {
                    optLabel = visibleSpan.innerText.trim();
                } else {
                    optLabel = lbl.innerText.trim();
                }
            }
            if (!optLabel && el.getAttribute('aria-labelledby')) {
                const lblEl = document.getElementById(el.getAttribute('aria-labelledby'));
                if (lblEl) optLabel = lblEl.innerText.trim();
            }
            if (!optLabel && el.id) {
                const forLbl = document.querySelector(`label[for="${el.id.replace(/"/g, '\\"')}"]`);
                if (forLbl) optLabel = forLbl.innerText.trim();
            }
            if (!optLabel) optLabel = el.value;

            radioGroups[groupKey].options.push({ value: el.value, label: optLabel });
            if (el.checked) radioGroups[groupKey].current_value = el.value;
            continue;
        }

        if (el.tagName.toLowerCase() === 'select') {
            const options = Array.from(el.options).map(opt => ({
                value: opt.value,
                label: opt.text.trim(),
            })).filter(o => o.value !== '');

            let selSelector;
            if (id && /^[a-zA-Z0-9_-]+$/.test(id)) {
                selSelector = `#${id}`;
            } else if (name) {
                selSelector = `select[name="${name.replace(/"/g, '\\"')}"]`;
            } else if (id) {
                selSelector = `select[id="${id.replace(/"/g, '\\"')}"]`;
            } else {
                selSelector = 'select';
            }

            elementsData.push({
                field_id: id,
                name: name,
                selector: selSelector,
                input_type: 'select',
                label: label,
                placeholder: placeholder,
                required: required,
                options: options,
                current_value: currentVal,
            });
            continue;
        }

        // Standard text, email, tel, file, textarea, checkbox
        let selector;
        const tag = el.tagName.toLowerCase();
        if (id && /^[a-zA-Z0-9_-]+$/.test(id)) {
            selector = `#${id}`;
        } else if (name) {
            selector = `${tag}[name="${name.replace(/"/g, '\\"')}"]`;
        } else if (id) {
            selector = `${tag}[id="${id.replace(/"/g, '\\"')}"]`;
        } else {
            selector = tag;
        }
        const isCheckbox = type === 'checkbox';
        const autoAttr = (el.getAttribute('autocomplete') || '').toLowerCase();
        const roleAttr = (el.getAttribute('role') || '').toLowerCase();
        const ariaAuto = (el.getAttribute('aria-autocomplete') || '').toLowerCase();
        const hasAuto = (
            (autoAttr && !['off', 'false', 'none'].includes(autoAttr)) ||
            roleAttr === 'combobox' ||
            ariaAuto === 'list' ||
            ariaAuto === 'both' ||
            el.classList.contains('select2-input') ||
            el.classList.contains('typeahead') ||
            el.classList.contains('tt-input') ||
            el.classList.contains('ui-autocomplete-input') ||
            (el.getAttribute('data-provides') === 'typeahead')
        );
        elementsData.push({
            field_id: id,
            name: name,
            selector: selector,
            input_type: type === 'file' ? 'file' : (tag === 'textarea' ? 'textarea' : (type || 'text')),
            label: label,
            placeholder: placeholder,
            required: required,
            options: [],
            current_value: isCheckbox ? (el.checked ? (el.value || 'true') : '') : currentVal,
            has_autocomplete: hasAuto,
            autocomplete_type: autoAttr || null,
        });
    }

    // 3b. Scan custom radio groups and pill button containers (Oracle JET, Workday, etc.)
    const customRadioContainers = Array.from(document.querySelectorAll('[role="radiogroup"], .cx-select-pills-container, oj-buttonset-one, [class*="buttonset"]'));
    for (const container of customRadioContainers) {
        if (container.querySelector('input[type="radio"]')) continue;
        const optionButtons = Array.from(container.querySelectorAll('button, [role="radio"]')).filter(b => {
            const style = window.getComputedStyle(b);
            return style.display !== 'none' && style.visibility !== 'hidden';
        });
        if (optionButtons.length < 2) continue;

        let qLabel = container.getAttribute('aria-label') || '';
        if (!qLabel) {
            const parentBlock = container.closest('.input-row, [class*="question" i], [class*="field" i], [class*="row" i], fieldset, div');
            if (parentBlock) {
                const lblEl = parentBlock.querySelector('label, [class*="label" i], [class*="title" i], legend, p, span');
                if (lblEl && lblEl.innerText && lblEl.innerText.trim().length > 1 && !/^(yes|no|true|false)$/i.test(lblEl.innerText.trim())) {
                    qLabel = lblEl.innerText.trim();
                }
            }
        }
        if (!qLabel) continue;

        const containerId = container.id || ('custom_radio_' + Math.random().toString(36).substring(2, 9));
        const options = optionButtons.map(b => ({
            value: (b.innerText || b.value || b.getAttribute('aria-label') || '').trim(),
            label: (b.innerText || b.getAttribute('aria-label') || '').trim(),
        }));

        let currentVal = null;
        for (const b of optionButtons) {
            if (b.classList.contains('cx-select-pill-section--selected') || b.getAttribute('aria-checked') === 'true' || b.classList.contains('active') || b.classList.contains('selected')) {
                currentVal = (b.innerText || b.value || '').trim();
                break;
            }
        }

        const containerSel = container.id ? `#${CSS.escape(container.id)}` : getUniqueSelector(container);

        elementsData.push({
            field_id: containerId,
            name: containerId,
            selector: containerSel,
            input_type: 'radio_group',
            label: qLabel.replace(/[*:]/g, '').trim(),
            required: container.getAttribute('aria-required') === 'true' || /[*]/i.test(qLabel),
            options: options,
            current_value: currentVal,
        });
    }

    // Merge radio groups into elementsData
    for (const group of Object.values(radioGroups)) {
        elementsData.push(group);
    }

    // Check if the gathered fields contain real candidate application fields
    const hasCandidateFields = elementsData.some(f => {
        const str = (f.name + ' ' + f.label + ' ' + f.field_id + ' ' + f.placeholder).toLowerCase();
        return f.input_type === 'file' || f.input_type === 'radio_group' || /name|first|last|email|phone|mobile|tel|resume|cv|address|city|country|state|postal|zip|salary|ctc|notice|experience|education|university|degree|linkedin|github|portfolio|authorization|authorized|sponsorship|relocate|travel|schedule|flexible|gender|race|veteran|disability|privacy|consent|agree/i.test(str);
    });

    // If there are no candidate application fields, this is an overview page, NOT an application form!
    const isActualApplicationForm = hasCandidateFields && elementsData.length > 0;
    if (!isActualApplicationForm) {
        // Clear non-form inputs so the orchestrator knows this is an overview page
        elementsData.length = 0;
    }

    // 4. Scan submit, next, and apply entry buttons
    function getUniqueSelector(el) {
        if (el.id && !/\d{4,}/.test(el.id)) {
            try {
                const sel = `#${CSS.escape(el.id)}`;
                if (document.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
        if (el.tagName.toLowerCase() === 'a' && el.getAttribute('href')) {
            const href = el.getAttribute('href');
            if (href !== '#' && !href.startsWith('javascript:')) {
                try {
                    const sel = `a[href="${CSS.escape(href)}"]`;
                    if (document.querySelectorAll(sel).length === 1) return sel;
                } catch(e) {}
            }
        }
        if (el.getAttribute('data-automation-id')) {
            try {
                const sel = `[data-automation-id="${CSS.escape(el.getAttribute('data-automation-id'))}"]`;
                if (document.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
        if (el.getAttribute('data-qa')) {
            try {
                const sel = `[data-qa="${CSS.escape(el.getAttribute('data-qa'))}"]`;
                if (document.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
        if (el.getAttribute('data-testid')) {
            try {
                const sel = `[data-testid="${CSS.escape(el.getAttribute('data-testid'))}"]`;
                if (document.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(/\s+/).filter(c => c && !/\d{4,}/.test(c));
            for (const cls of classes) {
                if (/apply|submit|next|continue/i.test(cls)) {
                    try {
                        const sel = `${el.tagName.toLowerCase()}.${CSS.escape(cls)}`;
                        if (document.querySelectorAll(sel).length === 1) return sel;
                        const classOnly = `.${CSS.escape(cls)}`;
                        if (document.querySelectorAll(classOnly).length === 1) return classOnly;
                    } catch(e) {}
                }
            }
        }
        if (el.getAttribute('name')) {
            try {
                const sel = `[name="${CSS.escape(el.getAttribute('name'))}"]`;
                if (document.querySelectorAll(sel).length === 1) return sel;
            } catch(e) {}
        }
        let path = [];
        let curr = el;
        while (curr && curr.nodeType === Node.ELEMENT_NODE && curr.tagName.toLowerCase() !== 'html') {
            let tag = curr.tagName.toLowerCase();
            if (curr.id && !/\d{4,}/.test(curr.id)) {
                path.unshift(`#${CSS.escape(curr.id)}`);
                break;
            }
            let siblingIndex = 1;
            let sibling = curr.previousElementSibling;
            while (sibling) {
                if (sibling.tagName.toLowerCase() === tag) siblingIndex++;
                sibling = sibling.previousElementSibling;
            }
            path.unshift(`${tag}:nth-of-type(${siblingIndex})`);
            curr = curr.parentElement;
        }
        return path.join(' > ');
    }

    // Deep candidate button collection (supports custom Web Components, Oracle JET, and shadow DOM)
    const foundElements = new Set();
    const queried = document.querySelectorAll(
        'button, input[type="submit"], input[type="button"], a, [role="button"], div[role="button"], span[role="button"], ' +
        'oj-button, oj-c-button, [data-qa*="apply" i], [data-automation-id*="apply" i], [class*="apply" i], [id*="apply" i], ' +
        '[aria-label*="apply" i], [aria-label*="next" i], [aria-label*="continue" i]'
    );
    for (const el of queried) foundElements.add(el);

    // Scan all leaf elements for exact or prominent "Apply", "Apply Now", "Next", "Continue"
    const allLeafs = document.querySelectorAll('*:not(script):not(style)');
    for (const el of allLeafs) {
        if (el.shadowRoot) {
            const shadowButtons = el.shadowRoot.querySelectorAll('button, a, [role="button"], input[type="submit"]');
            for (const sb of shadowButtons) foundElements.add(sb);
        }
        if (el.children.length === 0) {
            const t = (el.innerText || el.textContent || '').trim();
            if (/^(apply\s+now|apply|continue|next\s*[›»▸▶>]?|submit\s+application|submit)$/i.test(t)) {
                foundElements.add(el);
                const p = el.closest('button, a, [role="button"], oj-button, oj-c-button, div, span');
                if (p) foundElements.add(p);
            }
        }
    }
    const candidates = Array.from(foundElements);
    const submitBtns = [];
    const nextBtns = [];
    const applyNowBtns = [];

    const hasInputFields = isActualApplicationForm;

    for (const btn of candidates) {
        const text = (btn.innerText || btn.value || btn.getAttribute('aria-label') || btn.textContent || '').trim();
        const lower = text.toLowerCase();
        const cleanLower = lower.replace(/[\s\u25b6\u25b8\u203a\u00bb>]+/g, ' ').trim();
        const href = (btn.getAttribute('href') || '').toLowerCase();
        const btnType = (btn.getAttribute('type') || '').toLowerCase();
        const dataQa = (btn.getAttribute('data-qa') || '').toLowerCase();
        const dataAuto = (btn.getAttribute('data-automation-id') || '').toLowerCase();

        const isExplicitApply = /apply/i.test(lower) || /apply/i.test(href) || /apply/i.test(dataQa) || /apply/i.test(dataAuto);

        // Exclude header, navigation, footer, menus, search modal, but NEVER exclude explicit apply buttons
        if (!isExplicitApply && btn.closest('header, nav, footer, #header, #footer, #mainMenu, .main-menu, .menu, .dropdown-menu, .navigation, .site-header, .site-footer, .header-extras, .mega-menu, #search, .search-form, .search-suggestion, [class*="navbar" i], [id*="mainmenu" i], [class*="dropdown-menu" i]')) {
            continue;
        }

        const rect = btn.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) {
            // For custom elements or leaf wrappers, check if inner button/target has rendered size
            const inner = btn.querySelector('button, a, input, span');
            if (inner) {
                const iRect = inner.getBoundingClientRect();
                if (iRect.width === 0 || iRect.height === 0) continue;
            } else {
                continue;
            }
        }
        const style = window.getComputedStyle(btn);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

        // Filter false-positive non-application buttons (cart, filters, cancellation, cookies, social share)
        if (/filter|refine|coupon|promo|discount|newsletter|share|save|bookmark|report|flag|sign\s*in|log\s*in|login|cart|add-to-cart|view-cart|shopping|cancel|reset|clear|close|dismiss|back\b/i.test(cleanLower)) {
            continue;
        }

        const selector = getUniqueSelector(btn);

        const isNextPattern = cleanLower.startsWith('next') || cleanLower.startsWith('continue') || cleanLower.startsWith('proceed') || cleanLower.includes('next:') || cleanLower.includes('continue to') || cleanLower.includes('step 2') || /^(next|continue|proceed)(\s|$)/i.test(cleanLower);
        const isSubmitPattern = cleanLower === 'submit' || cleanLower.includes('submit application') || cleanLower.includes('send application') || cleanLower.includes('complete application') || cleanLower.includes('finish application') || (btnType === 'submit' && !/cancel|reset|search|close|filter|back/i.test(cleanLower + ' ' + (btn.id || '') + ' ' + (btn.name || '')));
        const isModalTrigger = btn.getAttribute('data-bs-toggle') === 'modal' || btn.getAttribute('data-toggle') === 'modal' || btn.hasAttribute('data-bs-target') || btn.hasAttribute('data-target') || btn.getAttribute('aria-haspopup') === 'dialog';
        const isApplyPattern = isModalTrigger || cleanLower === 'apply' || cleanLower.startsWith('apply now') || cleanLower.includes('apply online') || cleanLower.includes('apply on') || cleanLower.includes('start application') || cleanLower.includes('register to apply') || href.includes('resume-registration') || href.includes('/apply') || href.includes('action=apply') || href.includes('job-apply') || (cleanLower.includes('apply') && !/services|solutions|portfolio|integration|architecture|consulting|outsourcing/i.test(cleanLower));

        let score = 0;
        if (isModalTrigger) {
            score += 120;
        }
        if (cleanLower === 'apply' || cleanLower === 'apply now' || cleanLower.startsWith('apply now') || cleanLower === 'apply online' || cleanLower === 'apply for this job') {
            score += 150;
        } else if (cleanLower.startsWith('apply') || cleanLower.includes('apply on')) {
            score += 90;
        } else if (cleanLower.includes('apply') || cleanLower.includes('submit application') || cleanLower.includes('submit resume')) {
            score += 60;
        }
        if (href.includes('resume-registration') || href.includes('/apply')) {
            score += 40;
        }
        if (btn.classList.contains('btn-primary') || btn.classList.contains('btn') || /apply-btn|apply-button/i.test(btn.className)) {
            score += 30;
        }
        if (btn.tagName === 'BUTTON' || (btn.tagName === 'INPUT' && btn.type === 'submit')) {
            score += 20;
        }
        if (btn.closest('main, article, .job-details, #job-details, [class*="job" i], .job-description, .content, table')) {
            score += 20;
        }

        if (isNextPattern) {
            let nextScore = 150;
            if (cleanLower.startsWith('next') || cleanLower.startsWith('continue')) nextScore += 50;
            if (btn.classList.contains('btn-primary') || /primary/i.test(btn.className || '')) nextScore += 30;
            nextBtns.push({ selector: selector, text: text || 'Next', top: rect.top, score: nextScore });
        } else if (isModalTrigger || !hasInputFields) {
            // Modal trigger buttons or buttons on landing pages lead to application forms
            if (isApplyPattern || isSubmitPattern || isModalTrigger) {
                applyNowBtns.push({ selector: selector, text: text || 'Apply Now', top: rect.top, score: score });
            }
        } else {
            // ON ACTUAL APPLICATION FORM PAGES:
            // Check if this is an email identification / entry step (only 1 or 2 fields, all email/phone, no resume)
            const isEmailIdentificationStep = elementsData.length <= 2 && !elementsData.some(f => f.input_type === 'file') && elementsData.every(f => /email|phone|tel/i.test(f.name + ' ' + f.label + ' ' + f.field_id));
            if (isEmailIdentificationStep && !/back|cancel|close|dismiss|save|reset/i.test(cleanLower)) {
                let emailNextScore = 100;
                if (/primary|submit/i.test(btn.className + ' ' + btnType)) emailNextScore += 40;
                nextBtns.push({ selector: selector, text: text || 'Continue', top: rect.top, score: emailNextScore });
            } else if (isSubmitPattern) {
                let subScore = (cleanLower === 'submit' || cleanLower.includes('submit application')) ? 100 : 50;
                if (btn.classList.contains('btn-primary')) subScore += 30;
                if (btn.id === 'submitBtn' || btn.id === 'submit') subScore += 30;
                submitBtns.push({ selector: selector, text: text || 'Submit Application', top: rect.top, score: subScore });
            } else if (isApplyPattern && !cleanLower.includes('apply now') && !cleanLower.includes('apply on') && !isModalTrigger) {
                // Secondary check: "Apply" on form if no explicit submit exists
                submitBtns.push({ selector: selector, text: text || 'Apply', top: rect.top, score: 50 });
            }
        }
    }

    applyNowBtns.sort((a, b) => (b.score || 0) - (a.score || 0));
    submitBtns.sort((a, b) => (b.score || 0) - (a.score || 0));
    nextBtns.sort((a, b) => (b.score || 0) - (a.score || 0));

    if (nextBtns.length > 0) {
        isMultiStep = true;
    }

    return {
        challenge_detected: challenge,
        is_multi_step: isMultiStep,
        step_indicator: stepText,
        fields: elementsData,
        submit_buttons: submitBtns,
        next_buttons: nextBtns,
        apply_now_buttons: applyNowBtns,
    };
})()"""


class PageAnalyzer:
    """Parses application portal DOM structures and produces FormAnalysisResult."""

    async def analyze(self, agent: BrowserAgent) -> FormAnalysisResult:
        """Inspects active agent page DOM, extracting fields, options, files, and challenges."""
        url = await agent.get_url()
        title = await agent.get_title()

        # Execute extraction script in page context
        try:
            content = await agent.get_content()
        except Exception:
            content = ""

        # Query page evaluation via agent.evaluate (benefiting from auto-resync & retry)
        raw_data: Dict[str, Any] = {}
        if hasattr(agent, "evaluate"):
            try:
                eval_res = agent.evaluate(_DOM_EXTRACTION_JS)
                res = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
                if isinstance(res, dict):
                    raw_data = res
            except Exception as e:
                logger.debug("PageAnalyzer agent.evaluate fallback: %s", e)

        # Fallback to agent.page.evaluate if mock or page object provided
        if not raw_data and hasattr(agent, "page") and getattr(agent, "page", None):
            page_obj = getattr(agent, "page")
            if hasattr(page_obj, "evaluate"):
                try:
                    eval_res = page_obj.evaluate(_DOM_EXTRACTION_JS)
                    res = await eval_res if asyncio.iscoroutine(eval_res) else eval_res
                    if isinstance(res, dict):
                        raw_data = res
                except Exception as e:
                    logger.debug("PageAnalyzer page.evaluate fallback: %s", e)

        # Parse FormFieldInfo list
        fields: List[FormFieldInfo] = []
        file_fields: List[FormFieldInfo] = []

        for f_data in raw_data.get("fields", []):
            field_info = FormFieldInfo(
                field_id=f_data.get("field_id", ""),
                name=f_data.get("name", ""),
                selector=f_data.get("selector", ""),
                input_type=f_data.get("input_type", "text"),
                label=(
                    f_data.get("label")
                    or f_data.get("placeholder")
                    or re.sub(r"[-_]", " ", f_data.get("name") or f_data.get("field_id") or "").replace("*", "").strip().title()
                ),
                placeholder=f_data.get("placeholder", ""),
                required=bool(f_data.get("required", False)),
                options=f_data.get("options", []),
                current_value=f_data.get("current_value"),
                has_autocomplete=bool(f_data.get("has_autocomplete", False)),
                autocomplete_type=f_data.get("autocomplete_type"),
            )
            fields.append(field_info)
            if field_info.input_type == "file":
                file_fields.append(field_info)

        return FormAnalysisResult(
            url=url,
            title=title,
            fields=fields,
            file_upload_fields=file_fields,
            submit_buttons=raw_data.get("submit_buttons", []),
            next_buttons=raw_data.get("next_buttons", []),
            apply_now_buttons=raw_data.get("apply_now_buttons", []),
            challenge_detected=raw_data.get("challenge_detected"),
            is_multi_step=bool(raw_data.get("is_multi_step", False)),
            step_indicator=raw_data.get("step_indicator"),
        )
