'''
Indeed Smart Apply Form Engine
Automates multi-step Single Page Application (SPA) questionnaires on smartapply.indeed.com.
Handles:
1. Contact Information verification & auto-fill.
2. Location & Address filling from candidate profile.
3. Resume selection & CV replacement options.
4. Dynamic employer screening questions via QnAEngine.
5. Review application module verification.
'''

import os
import re
import time
from typing import Optional, List, Dict, Any, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    StaleElementReferenceException,
    NoSuchElementException,
    ElementClickInterceptedException,
)

from modules.helpers import print_lg
from modules.qna_engine import QnAEngine, Answer
from modules.config_loader import get_personal, get_resume, get_professional
from platforms.indeed.selectors import (
    SPINNER_SELECTORS,
    STEP_HEADING_SELECTORS,
    FORM_CONTINUE_BUTTONS,
    CONTACT_FIRST_NAME,
    CONTACT_LAST_NAME,
    CONTACT_EMAIL,
    CONTACT_PHONE,
    ADDRESS_POSTAL_CODE,
    ADDRESS_CITY,
    ADDRESS_STREET,
    RESUME_SELECTION_CARD,
    CV_OPTIONS_BUTTON,
    RESUME_FILE_INPUT,
    QUESTION_BLOCKS,
    FINAL_SUBMIT_BUTTONS,
    CONFIRMATION_HEADINGS,
)
from platforms.indeed.captcha_handler import IndeedCaptchaHandler


class IndeedForm:
    """Automates multi-step questionnaires inside Indeed Smart Apply application tabs."""

    def __init__(
        self,
        browser: Any,
        qna_engine: Optional[QnAEngine] = None,
        candidate_profile: Optional[Dict[str, Any]] = None,
        captcha_handler: Optional[IndeedCaptchaHandler] = None,
    ):
        self.browser = browser
        self.driver = browser.driver
        self.qna_engine = qna_engine or QnAEngine()
        self.personal = candidate_profile or get_personal()
        self.professional = getattr(self.qna_engine, "prof", {}) or get_professional()
        self.captcha_handler = captcha_handler or IndeedCaptchaHandler(browser)

    @staticmethod
    def _clean_phone_number(phone_raw: str) -> str:
        """Cleans phone number to pure digits, stripping non-digit symbols and redundant country codes."""
        if not phone_raw:
            return ""
        digits = re.sub(r'\D', '', str(phone_raw))
        # If 12 digits starting with 91 (India) -> 10-digit national number
        if len(digits) == 12 and digits.startswith("91"):
            return digits[-10:]
        # If 11 digits starting with 1 (US/Canada) -> 10-digit national number
        if len(digits) == 11 and digits.startswith("1"):
            return digits[-10:]
        # If 11 digits starting with 0 (e.g. 0XXXXXXXXXX) -> 10 digits
        if len(digits) == 11 and digits.startswith("0"):
            return digits[-10:]
        # If 10 or more digits, extract last 10 digits
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    @staticmethod
    def _resolve_safe_option(question_text: str, options: List[str], raw_val: str, qna_match: Optional[str]) -> str:
        """Picks the safest matching option without blind-defaulting to option[0] (which may be Afghanistan or Fiji Dollar)."""
        if qna_match:
            for opt in options:
                if opt.lower() == qna_match.lower():
                    return opt
        if raw_val:
            for opt in options:
                if opt.lower() == str(raw_val).lower():
                    return opt

        q_lower = question_text.lower()

        # Country / Phone Dial Code
        is_dial_code_list = any(re.search(r'\+\d{1,4}', o) for o in options)
        is_country_query = any(w in q_lower for w in ["country", "dial code", "phone code", "calling code"])
        if is_country_query or is_dial_code_list:
            # 1. Match India (+91) specifically (never match British Indian Ocean Territory (+246))
            for opt in options:
                opt_l = opt.lower()
                if "+91" in opt_l:
                    return opt
            for opt in options:
                opt_l = opt.lower()
                if re.search(r'\bindia\b', opt_l) and "british" not in opt_l and "+246" not in opt_l:
                    return opt
            # 2. Match United States / Canada (+1) specifically
            for opt in options:
                opt_l = opt.lower()
                if "+1" in opt_l or (re.search(r'\bunited states\b', opt_l) and "minor" not in opt_l):
                    return opt

        # Currency / Salary Unit
        has_currency_options = any(any(curr in o.lower() for curr in ["inr", "rupee", "₹", "usd", "dollar", "eur", "euro", "gbp", "pound", "cad", "aud"]) for o in options)
        if any(w in q_lower for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"]) or has_currency_options:
            for opt in options:
                opt_l = opt.lower()
                if any(curr in opt_l for curr in ["inr", "rupee", "₹", "indian"]):
                    return opt
            for opt in options:
                opt_l = opt.lower()
                if any(curr in opt_l for curr in ["usd", "dollar (usd)", "$"]):
                    return opt

        # Yes / No Questions
        if any(w in q_lower for w in ["sponsorship", "conflict", "relative", "felony", "crime", "previously employed", "discharged", "non-compete", "referred"]):
            for opt in options:
                if opt.lower() == "no" or "no" in opt.lower():
                    return opt
        if any(w in q_lower for w in ["authorized", "eligible", "relocate", "relocation", "hybrid", "remote"]):
            for opt in options:
                if opt.lower() == "yes" or "yes" in opt.lower():
                    return opt

        # Referral / Hearing source
        if any(w in q_lower for w in ["hear about", "referral source", "how did you hear"]):
            for opt in options:
                opt_l = opt.lower()
                if any(k in opt_l for k in ["indeed", "linkedin", "online", "website", "social", "job board", "internet", "career", "search", "other"]):
                    return opt
            for opt in options:
                opt_l = opt.lower()
                if opt_l not in ["select an option", "choose an option", "select...", "choose one"]:
                    return opt

        # Experience / Numeric ranges (strictly when question asks for experience/years/numerical level)
        if any(w in q_lower for w in ["experience", "years", "year", "level", "tenure"]):
            for opt in options:
                opt_l = opt.lower()
                if "1 to 2" in opt_l or "1-2" in opt_l or re.search(r'\b2\b', opt_l):
                    return opt

        return options[0] if options else ""

    def _select_native_option(self, select_elem, target_opt_text: str) -> str:
        """Selects an option in a native <select> element using React prototype descriptors and dispatches synthetic events."""
        try:
            res = self.driver.execute_script("""
                const sel = arguments[0];
                const targetText = (arguments[1] || '').trim().toLowerCase();
                if (!sel || !sel.options || sel.options.length === 0) return '';

                let matchedIdx = -1;
                // 1. Exact match on text or value
                for (let i = 0; i < sel.options.length; i++) {
                    const opt = sel.options[i];
                    const txt = (opt.text || opt.innerText || '').trim().toLowerCase();
                    const val = (opt.value || '').trim().toLowerCase();
                    if (txt === targetText || val === targetText) {
                        matchedIdx = i;
                        break;
                    }
                }
                // 2. Currency match
                if (matchedIdx === -1 && (targetText.includes('inr') || targetText.includes('rupee'))) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const opt = sel.options[i];
                        const txt = (opt.text || opt.innerText || '').trim().toLowerCase();
                        if (txt.includes('inr') || txt.includes('rupee') || txt.includes('₹') || txt.includes('indian')) {
                            matchedIdx = i;
                            break;
                        }
                    }
                }
                // 3. Substring match
                if (matchedIdx === -1 && targetText) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const opt = sel.options[i];
                        const txt = (opt.text || opt.innerText || '').trim().toLowerCase();
                        if (txt.includes(targetText) || targetText.includes(txt)) {
                            matchedIdx = i;
                            break;
                        }
                    }
                }
                // 4. Fallback to first non-placeholder option if still not matched
                if (matchedIdx === -1) {
                    for (let i = 0; i < sel.options.length; i++) {
                        const opt = sel.options[i];
                        const txt = (opt.text || opt.innerText || '').trim().toLowerCase();
                        if (txt && !txt.includes('select an option') && !txt.includes('choose')) {
                            matchedIdx = i;
                            break;
                        }
                    }
                }

                if (matchedIdx >= 0) {
                    sel.selectedIndex = matchedIdx;
                    for (let i = 0; i < sel.options.length; i++) {
                        sel.options[i].selected = (i === matchedIdx);
                    }
                    const targetVal = sel.options[matchedIdx].value;

                    // Reset React value tracker if present so React does not discard the change event
                    if (sel._valueTracker) {
                        try {
                            sel._valueTracker.setValue('');
                        } catch(e) {}
                    }

                    // Set value using prototype descriptor so React tracker sees it
                    try {
                        const descriptor = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value');
                        if (descriptor && descriptor.set) {
                            descriptor.set.call(sel, targetVal);
                        } else {
                            sel.value = targetVal;
                        }
                    } catch (e) {
                        sel.value = targetVal;
                    }

                    // Dispatch full synthetic event sequence with bubbles & composed
                    sel.dispatchEvent(new Event('focus', { bubbles: true }));
                    sel.dispatchEvent(new Event('input', { bubbles: true }));
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                    sel.dispatchEvent(new Event('blur', { bubbles: true }));
                    return sel.options[matchedIdx].text || targetVal;
                }
                return '';
            """, select_elem, target_opt_text)

            # Secondary Selenium Select fallback as safety confirmation
            try:
                sel = Select(select_elem)
                if target_opt_text:
                    sel.select_by_visible_text(target_opt_text)
            except Exception:
                pass

            return str(res or "")
        except Exception as e:
            print_lg(f"[IndeedForm] Error in _select_native_option: {e}")
            return ""

    def _get_custom_combobox_options(self, elem) -> List[str]:
        """Extracts available option labels from an expandable custom combobox / listbox without altering state."""
        try:
            opts = self.driver.execute_script("""
                const el = arguments[0];
                let listboxId = el.getAttribute('aria-controls') || el.getAttribute('aria-owns');
                let listbox = listboxId ? document.getElementById(listboxId) : null;
                if (!listbox) {
                    listbox = el.closest('div, fieldset')?.querySelector('[role="listbox"], ul[role="listbox"], ul, .icl-Select-list, [data-testid*="menu"], [data-testid*="dropdown"]');
                }
                if (!listbox) {
                    listbox = document.querySelector('[role="listbox"]:not([aria-hidden="true"]), ul[role="listbox"], .icl-Select-list, [data-testid*="menu"], [data-testid*="dropdown"]');
                }
                if (listbox) {
                    const items = Array.from(listbox.querySelectorAll('[role="option"], li, button, [data-testid*="option"], div[role="option"]'));
                    return items.map(o => (o.innerText || o.textContent || '').trim()).filter(t => t.length > 0 && !t.toLowerCase().includes('select an option') && !t.toLowerCase().includes('choose'));
                }
                // Check if backed by a native select inside the same container
                const backingSelect = el.closest('div, fieldset')?.querySelector('select');
                if (backingSelect && backingSelect.options && backingSelect.options.length > 0) {
                    return Array.from(backingSelect.options).map(o => (o.text || o.innerText || '').trim()).filter(t => t.length > 0 && !t.toLowerCase().includes('select an option') && !t.toLowerCase().includes('choose'));
                }
                return [];
            """, elem) or []
            return [str(o) for o in opts if o]
        except Exception:
            return []

    def _select_custom_combobox_option(self, elem, target_opt_text: str = "", question_context: str = "") -> str:
        """Expands custom combobox / button dropdown and clicks matching option using full pointer & mouse sequences."""
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
        except Exception:
            pass

        try:
            # Step 1: Check if backing native <select> exists in the immediate container
            try:
                backing_sel = self.driver.execute_script("""
                    const el = arguments[0];
                    return el.closest('div, fieldset')?.querySelector('select');
                """, elem)
                if backing_sel and target_opt_text:
                    native_chosen = self._select_native_option(backing_sel, target_opt_text)
                    if native_chosen:
                        time.sleep(0.2)
            except Exception:
                pass

            # Step 2: Check expansion state and open only if closed
            is_open = False
            try:
                is_open = bool(self.driver.execute_script("""
                    const el = arguments[0];
                    return el.getAttribute('aria-expanded') === 'true' ||
                           Boolean(document.querySelector('[role="listbox"]:not([aria-hidden="true"]), ul[role="listbox"], [data-testid*="menu"]'));
                """, elem))
            except Exception:
                is_open = False

            if not is_open:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", elem)
                    time.sleep(0.1)
                    elem.click()
                except Exception:
                    try:
                        ActionChains(self.driver).move_to_element(elem).click().perform()
                    except Exception:
                        try:
                            self.driver.execute_script("""
                                const el = arguments[0];
                                el.focus();
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                            """, elem)
                        except Exception:
                            pass
                time.sleep(0.35)

            # Step 3: Query options and select via DOM JavaScript
            res = self.driver.execute_script("""
                const btn = arguments[0];
                const targetText = (arguments[1] || '').trim().toLowerCase();
                const qContext = (arguments[2] || '').trim().toLowerCase();

                // 1. Locate options scoped to container, listbox, or popup dialog
                const listboxId = btn.getAttribute('aria-controls') || btn.getAttribute('aria-owns');
                let listbox = listboxId ? document.getElementById(listboxId) : null;
                if (!listbox) {
                    listbox = btn.closest('div, fieldset')?.querySelector('[role="listbox"], ul[role="listbox"], ul, .icl-Select-list, [data-testid*="dropdown"]');
                }
                if (!listbox) {
                    listbox = document.querySelector('[role="listbox"]:not([aria-hidden="true"]):not(header *):not(nav *), div[role="dialog"] [role="listbox"], .icl-Select-list, [data-testid*="dropdown"]');
                }

                let optionEls = [];
                if (listbox) {
                    optionEls = Array.from(listbox.querySelectorAll('[role="option"], li[role="option"], [data-testid*="option"], div[role="option"]'));
                }
                if (optionEls.length === 0) {
                    optionEls = Array.from(document.querySelectorAll(
                        '[role="listbox"]:not([aria-hidden="true"]):not(header *):not(nav *) [role="option"], [role="option"]:not(header *):not(nav *), li[role="option"]:not(header *):not(nav *), [data-testid*="select-option"], .icl-Select-option, div[class*="popover" i] li, div[class*="dropdown" i] li'
                    ));
                }

                // Filter visible options
                const validOptions = optionEls.filter(el => {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && (rect.width > 0 || rect.height > 0);
                });
                const searchPool = validOptions.length > 0 ? validOptions : optionEls;

                let matched = null;
                // A. Exact match
                if (targetText) {
                    for (const opt of searchPool) {
                        const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                        if (txt === targetText) {
                            matched = opt;
                            break;
                        }
                    }
                }

                // B. Currency-specific matching
                const poolHasCurrency = searchPool.some(opt => {
                    const t = (opt.innerText || opt.textContent || '').toLowerCase();
                    return ['inr', 'rupee', '₹', 'usd', 'dollar', 'eur', 'euro'].some(c => t.includes(c));
                });
                const isCurrency = qContext.includes('currency') || targetText.includes('inr') || targetText.includes('rupee') || poolHasCurrency;
                if (!matched && isCurrency) {
                    for (const opt of searchPool) {
                        const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                        if (txt.includes('inr') || txt.includes('rupee') || txt.includes('₹') || txt.includes('indian')) {
                            matched = opt;
                            break;
                        }
                    }
                    if (!matched) {
                        for (const opt of searchPool) {
                            const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                            if (txt.includes('usd') || txt.includes('dollar')) {
                                matched = opt;
                                break;
                            }
                        }
                    }
                }

                // C. Referral / hearing source matching
                const poolHasReferral = searchPool.some(opt => {
                    const t = (opt.innerText || opt.textContent || '').toLowerCase();
                    return ['indeed', 'linkedin', 'company website', 'referral', 'online'].some(c => t.includes(c));
                });
                const isReferral = qContext.includes('hear about') || qContext.includes('referral') || qContext.includes('source') || qContext.includes('sds') || poolHasReferral;
                if (!matched && isReferral) {
                    for (const opt of searchPool) {
                        const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                        if (['indeed', 'linkedin', 'company website', 'online', 'website', 'search', 'job board', 'internet', 'other'].some(k => txt.includes(k))) {
                            matched = opt;
                            break;
                        }
                    }
                }

                // D. Substring match
                if (!matched && targetText) {
                    for (const opt of searchPool) {
                        const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                        if (txt.includes(targetText) || targetText.includes(txt)) {
                            matched = opt;
                            break;
                        }
                    }
                }

                // E. Fallback to first non-placeholder option
                if (!matched && searchPool.length > 0) {
                    for (const opt of searchPool) {
                        const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                        if (txt && !txt.includes('select an option') && !txt.includes('choose an option') && !txt.includes('select...')) {
                            matched = opt;
                            break;
                        }
                    }
                }

                if (matched) {
                    const matchedText = (matched.innerText || matched.textContent || '').trim();
                    matched.scrollIntoView({block: 'nearest'});

                    try { matched.focus(); } catch(e) {}
                    try { matched.click(); } catch(e) {}

                    // Dispatch full pointer and mouse sequence to trigger React's selection
                    ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'].forEach(evt => {
                        try {
                            matched.dispatchEvent(new MouseEvent(evt, { bubbles: true, cancelable: true, view: window }));
                        } catch(e) {}
                    });

                    // Synchronize any underlying native <select> or hidden input
                    const container = btn.closest('div, fieldset');
                    if (container) {
                        const hiddenSelect = container.querySelector('select');
                        if (hiddenSelect && hiddenSelect.options) {
                            for (let i = 0; i < hiddenSelect.options.length; i++) {
                                const hTxt = (hiddenSelect.options[i].text || '').toLowerCase();
                                const hVal = (hiddenSelect.options[i].value || '').toLowerCase();
                                if (hTxt === matchedText.toLowerCase() || (targetText && (hTxt.includes(targetText) || hVal.includes(targetText)))) {
                                    hiddenSelect.selectedIndex = i;
                                    hiddenSelect.options[i].selected = true;
                                    hiddenSelect.dispatchEvent(new Event('input', { bubbles: true }));
                                    hiddenSelect.dispatchEvent(new Event('change', { bubbles: true }));
                                    break;
                                }
                            }
                        }
                    }

                    return matchedText;
                }
                return '';
            """, elem, target_opt_text, question_context)

            chosen_text = str(res or "").strip()

            # Step 4: Verification - Check if combobox displayed text updated
            time.sleep(0.3)
            current_disp = self.driver.execute_script("return (arguments[0].innerText || arguments[0].textContent || arguments[0].value || '').trim();", elem)
            current_disp_lower = str(current_disp).lower()
            if not current_disp or "select an option" in current_disp_lower or "choose an option" in current_disp_lower:
                # Fallback: ActionChains and Keyboard Enter navigation
                try:
                    ActionChains(self.driver).move_to_element(elem).click().send_keys(Keys.ARROW_DOWN).send_keys(Keys.ENTER).perform()
                    time.sleep(0.3)
                    new_disp = self.driver.execute_script("return (arguments[0].innerText || arguments[0].textContent || arguments[0].value || '').trim();", elem)
                    if new_disp and "select an option" not in new_disp.lower() and "choose an option" not in new_disp.lower():
                        chosen_text = new_disp
                except Exception:
                    pass

            return chosen_text
        except Exception as e:
            print_lg(f"[IndeedForm] Error in _select_custom_combobox_option: {e}")
            return ""

    def wait_for_spinner(self, timeout: int = 10) -> None:
        """Waits for any loading spinner / overlay to clear."""
        if not self.driver:
            return
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(0.5)
            spinners = []
            for sel in SPINNER_SELECTORS:
                try:
                    spinners.extend(self.driver.find_elements(By.XPATH, sel))
                except Exception:
                    pass
            if not any(s.is_displayed() for s in spinners):
                break
        time.sleep(0.5)

    def wait_for_page_ready(self, timeout: int = 15) -> bool:
        """Waits for loading spinner to disappear and actual form content/inputs to mount."""
        if not self.driver:
            return True
        self.wait_for_spinner(timeout=min(timeout, 8))
        start = time.time()
        while time.time() - start < timeout:
            try:
                is_ready = self.driver.execute_script('''
                    var spinners = document.querySelectorAll(
                        "[role='status'], [class*='spinner' i], [class*='Spinner' i], [class*='loading' i], " +
                        "svg[class*='spin' i], circle[class*='spin' i], [data-testid*='spinner' i]"
                    );
                    for (var s of spinners) {
                        if (s.offsetWidth > 0 && s.offsetHeight > 0) return false;
                    }
                    var content = document.querySelectorAll(
                        "main, form, [data-testid], h1, h2, legend, input, textarea, select, button[type='submit'], [role='heading']"
                    );
                    return content.length > 0;
                ''')
                if is_ready:
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return True

    def is_confirmation_page(self) -> bool:
        """Checks if the application is in a confirmed/submitted state."""
        if not self.driver:
            return False
        cur_url = (self.driver.current_url or "").lower()
        if "post-apply" in cur_url or "confirmation" in cur_url or "applied" in cur_url:
            return True
        for c_sel in CONFIRMATION_HEADINGS:
            try:
                elems = self.driver.find_elements(By.XPATH, c_sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass
        try:
            body_text = (self.driver.find_element(By.TAG_NAME, "body").text or "").lower()
            if "application was submitted" in body_text or "application submitted" in body_text:
                return True
        except Exception:
            pass
        return False

    def detect_step_type(self) -> str:
        """Determines the current form module type by inspecting URL, headings, and input signatures."""
        self.wait_for_spinner()
        cur_url = (self.driver.current_url or "").lower()

        # Check confirmation first
        for c_sel in CONFIRMATION_HEADINGS:
            try:
                elems = self.driver.find_elements(By.XPATH, c_sel)
                if any(e.is_displayed() for e in elems):
                    return "CONFIRMATION"
            except Exception:
                pass

        # Check for active blocking modal popup challenge overlay (e.g. Google reCAPTCHA image tiles popup)
        try:
            bframes = self.driver.find_elements(By.CSS_SELECTOR, "iframe[src*='recaptcha/api2/bframe'], iframe[src*='recaptcha/enterprise/bframe']")
            for b in bframes:
                loc = b.location
                sz = b.size
                if b.is_displayed() and sz.get("width", 0) >= 250 and sz.get("height", 0) >= 250 and loc.get("y", -1) >= 0:
                    print_lg("[IndeedForm] Active modal CAPTCHA popup challenge detected.")
                    return "CAPTCHA"
        except Exception:
            pass

        # Dismiss exit application modal if present
        self.dismiss_exit_modal()

        # Check URL path indicators first (highest deterministic signal)
        if "contact-info" in cur_url:
            return "CONTACT_INFO"
        if "location" in cur_url or "address" in cur_url:
            return "LOCATION"
        if "resume-selection" in cur_url or "resume" in cur_url:
            return "RESUME"
        if "questions" in cur_url:
            return "QUESTIONS"
        if "review" in cur_url:
            return "REVIEW"

        # Check final review module via submit buttons only if not on a known sub-module
        for s_sel in FINAL_SUBMIT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH, s_sel)
                if any(e.is_displayed() for e in elems):
                    return "REVIEW"
            except Exception:
                pass

        # Check explicit contact inputs first (if first name, last name, phone, or email is visible)
        try:
            for fn_sel in CONTACT_FIRST_NAME:
                for el in self.driver.find_elements(By.XPATH, fn_sel):
                    if el.is_displayed():
                        return "CONTACT_INFO"
            for ph_sel in CONTACT_PHONE:
                for el in self.driver.find_elements(By.XPATH, ph_sel):
                    if el.is_displayed():
                        return "CONTACT_INFO"
            for em_sel in CONTACT_EMAIL:
                for el in self.driver.find_elements(By.XPATH, em_sel):
                    if el.is_displayed():
                        return "CONTACT_INFO"
        except Exception:
            pass

        # Heading-based fallback
        headings = []
        for h_sel in STEP_HEADING_SELECTORS:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, h_sel):
                    if el.is_displayed() and el.text.strip():
                        headings.append(el.text.strip().lower())
            except Exception:
                pass

        heading_text = " ".join(headings)
        if "contact" in heading_text:
            return "CONTACT_INFO"
        if "location" in heading_text or "address" in heading_text:
            return "LOCATION"
        if "resume" in heading_text or "cv" in heading_text:
            return "RESUME"
        if "question" in heading_text or "qualification" in heading_text:
            return "QUESTIONS"

        # Input element fallback
        try:
            if any(el.is_displayed() for sel in ADDRESS_POSTAL_CODE + ADDRESS_CITY for el in self.driver.find_elements(By.XPATH, sel)):
                return "LOCATION"
            if any(el.is_displayed() for sel in CONTACT_FIRST_NAME + CONTACT_PHONE for el in self.driver.find_elements(By.XPATH, sel)):
                return "CONTACT_INFO"
            if self.driver.find_elements(By.XPATH, "//button[contains(., 'CV options') or contains(., 'Upload a CV')]"):
                return "RESUME"
        except Exception:
            pass

        # Check for standalone blocking CAPTCHA challenge page (only if NO application form inputs exist)
        try:
            has_app_inputs = len(self.driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), textarea, select, button[type='submit']")) > 0
            if not has_app_inputs and self.captcha_handler.is_captcha_present(self.driver) and not self.captcha_handler.is_captcha_solved(self.driver):
                return "CAPTCHA"
        except Exception:
            pass

        return "QUESTIONS"

    def _clear_and_type_input(self, elem: Any, value: str) -> bool:
        """Thoroughly clears an input/textarea element and sets value, dispatching React synthetic events."""
        if not elem:
            return False
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
        except Exception:
            pass
        time.sleep(0.1)

        # 1. Native key-based text deletion (Ctrl+A -> Backspace -> clear)
        try:
            elem.click()
            time.sleep(0.05)
            elem.send_keys(Keys.CONTROL + "a")
            elem.send_keys(Keys.BACKSPACE)
            elem.clear()
        except Exception:
            pass

        # 2. Reset React internal value tracker to blank
        try:
            self.driver.execute_script("""
                const el = arguments[0];
                const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                if (descriptor && descriptor.set) {
                    descriptor.set.call(el, '');
                } else {
                    el.value = '';
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, elem)
        except Exception:
            pass

        # 3. Type value via send_keys
        typed_ok = False
        try:
            elem.send_keys(value)
            typed_ok = True
        except Exception:
            pass

        # 4. Verification & React descriptor setter fallback (prevents concatenation e.g. '21-4 YEARS')
        try:
            current_val = (elem.get_attribute("value") or "").strip()
            if current_val != value:
                self.driver.execute_script("""
                    const el = arguments[0];
                    const val = arguments[1];
                    const proto = el instanceof HTMLTextAreaElement ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
                    const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
                    if (descriptor && descriptor.set) {
                        descriptor.set.call(el, val);
                    } else {
                        el.value = val;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """, elem, value)
                typed_ok = True
        except Exception:
            pass

        return typed_ok

    def fill_field_if_needed(self, selectors: List[str], value: str, clear_first: bool = False) -> bool:
        """Finds visible input matching selectors and fills value if empty or requested."""
        if not value:
            return False
        for sel in selectors:
            try:
                elems = self.driver.find_elements(By.XPATH, sel)
                for el in elems:
                    if el.is_displayed():
                        existing = (el.get_attribute("value") or "").strip()
                        if not existing or clear_first:
                            self._clear_and_type_input(el, value)
                            print_lg(f"[IndeedForm] Filled '{value}' into field ({sel[:35]})")
                            return True
            except Exception:
                continue
        return False

    def fill_contact_info(self) -> None:
        """Fills or verifies contact information fields."""
        print_lg("[IndeedForm] Processing Contact Information module...")
        first_name = self.personal.get("first_name", "Mohd Ahmad Raza")
        last_name = self.personal.get("last_name", "Ansari")
        phone_raw = self.personal.get("phone_number", "6388623967")
        clean_phone = self._clean_phone_number(phone_raw)

        self.fill_field_if_needed(CONTACT_FIRST_NAME, first_name)
        self.fill_field_if_needed(CONTACT_LAST_NAME, last_name)
        self.fill_field_if_needed(CONTACT_PHONE, clean_phone)

        # Select Country dropdown if present on contact page
        try:
            country_selects = self.driver.find_elements(
                By.XPATH,
                "//select[contains(@id, 'country') or contains(@name, 'country') or contains(@aria-label, 'country') or contains(@aria-label, 'Country')]"
            )
            for cs in country_selects:
                if cs.is_displayed():
                    opts = [o.text.strip() for o in Select(cs).options if o.text.strip()]
                    best_country = self._resolve_safe_option("country", opts, "", None)
                    if best_country:
                        self._select_native_option(cs, best_country)
        except Exception:
            pass

    def fill_location_info(self) -> None:
        """Fills location and address fields."""
        print_lg("[IndeedForm] Processing Location / Address module...")
        postal_code = self.personal.get("zipcode", "110001")
        city = self.personal.get("current_city", "Delhi")
        street = self.personal.get("street", "Delhi")

        self.fill_field_if_needed(ADDRESS_POSTAL_CODE, postal_code)
        self.fill_field_if_needed(ADDRESS_CITY, city)
        self.fill_field_if_needed(ADDRESS_STREET, street)

    def handle_resume_selection(self, custom_resume_path: Optional[str] = None) -> None:
        """Verifies selected resume card, or uploads custom resume if provided."""
        print_lg("[IndeedForm] Processing Resume module...")
        self.wait_for_spinner()

        if custom_resume_path and os.path.exists(custom_resume_path):
            print_lg(f"[IndeedForm] Custom resume requested: {custom_resume_path}")
            # Click CV options -> Upload different file
            for opt_sel in CV_OPTIONS_BUTTON:
                try:
                    for ob in self.driver.find_elements(By.XPATH, opt_sel):
                        if ob.is_displayed():
                            self.driver.execute_script("arguments[0].click();", ob)
                            time.sleep(1)
                            break
                except Exception:
                    pass

            for file_sel in RESUME_FILE_INPUT:
                try:
                    for fe in self.driver.find_elements(By.XPATH, file_sel):
                        fe.send_keys(os.path.abspath(custom_resume_path))
                        print_lg(f"[IndeedForm] Uploaded resume from: {custom_resume_path}")
                        time.sleep(2)
                        return
                except Exception:
                    pass

        print_lg("[IndeedForm] Standard candidate resume already active in Indeed profile.")

    def answer_screening_questions(self, job_title: str = "", company_name: str = "") -> List[Dict[str, str]]:
        """Discovers and answers employer screening questions using QnAEngine."""
        print_lg("[IndeedForm] Processing Employer Screening Questions module...")
        answered = []
        handled_inputs = set()

        # 1. Process Radio & Checkbox Groups (Fieldsets)
        fieldsets = []
        try:
            fieldsets = self.driver.find_elements(By.TAG_NAME, "fieldset")
        except Exception:
            pass

        for fs in fieldsets:
            try:
                if not fs.is_displayed():
                    continue

                # Question Title from legend or headings
                question_text = ""
                for l_sel in [".//legend", ".//h1", ".//h2", ".//h3", ".//h4", ".//h5", ".//span[contains(@class, 'label')]", ".//div[contains(@class, 'heading')]"]:
                    try:
                        lbls = fs.find_elements(By.XPATH, l_sel)
                        if lbls and lbls[0].text.strip():
                            question_text = lbls[0].text.strip().replace("\n", " ")
                            break
                    except Exception:
                        pass
                if not question_text:
                    question_text = fs.text.strip().split("\n")[0]
                if not question_text:
                    continue

                radio_inputs = fs.find_elements(By.XPATH, ".//input[@type='radio']")
                if radio_inputs:
                    options_map = []
                    for r in radio_inputs:
                        handled_inputs.add(r)
                        opt_text = ""
                        lbl_elem = None
                        r_id = r.get_attribute("id")
                        if r_id:
                            try:
                                lbls = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{r_id}']")
                                if lbls and lbls[0].text.strip():
                                    opt_text = lbls[0].text.strip()
                                    lbl_elem = lbls[0]
                            except Exception:
                                pass
                        if not opt_text:
                            try:
                                sibs = r.find_elements(By.XPATH, "following-sibling::label | following-sibling::span")
                                if sibs and sibs[0].text.strip():
                                    opt_text = sibs[0].text.strip()
                                    lbl_elem = sibs[0]
                            except Exception:
                                pass
                        if not opt_text:
                            try:
                                p = r.find_element(By.XPATH, "..")
                                if p.text.strip():
                                    opt_text = p.text.strip()
                                    lbl_elem = p
                            except Exception:
                                pass
                        if not opt_text:
                            opt_text = r.get_attribute("value") or ""

                        options_map.append((opt_text, r, lbl_elem))

                    available_opts = [om[0] for om in options_map if om[0]]
                    ans_obj: Answer = self.qna_engine.answer_question(
                        question=question_text,
                        options=available_opts,
                        field_type="radio",
                        job_context={"title": job_title, "company": company_name}
                    )
                    target_str = str(ans_obj.value if ans_obj else "No").strip()

                    # Match target against options
                    target_radio = None
                    target_lbl = None
                    for opt_text, r, lbl in options_map:
                        if target_str.lower() == opt_text.lower():
                            target_radio = r
                            target_lbl = lbl
                            break

                    # Numeric range matching for experience questions (e.g. '1 to 2 years' vs 'Less than 1 year')
                    if not target_radio and options_map:
                        try:
                            cand_exp = float(self.personal.get("years_of_experience", 2.0))
                        except Exception:
                            cand_exp = 2.0
                        for opt_text, r, lbl in options_map:
                            opt_lower = opt_text.lower()
                            # Parse ranges like "1 to 2", "1-2", "less than 1", "more than 4"
                            if "less than" in opt_lower or "under" in opt_lower:
                                digits = re.findall(r'\d+', opt_lower)
                                if digits and cand_exp < float(digits[0]):
                                    target_radio = r
                                    target_lbl = lbl
                                    target_str = opt_text
                                    break
                            elif "more than" in opt_lower or "greater than" in opt_lower or "+" in opt_lower:
                                digits = re.findall(r'\d+', opt_lower)
                                if digits and cand_exp >= float(digits[0]):
                                    target_radio = r
                                    target_lbl = lbl
                                    target_str = opt_text
                                    break
                            else:
                                digits = re.findall(r'\d+', opt_lower)
                                if len(digits) >= 2 and float(digits[0]) <= cand_exp <= float(digits[1]):
                                    target_radio = r
                                    target_lbl = lbl
                                    target_str = opt_text
                                    break

                    if not target_radio:
                        for opt_text, r, lbl in options_map:
                            if target_str.lower() in opt_text.lower():
                                target_radio = r
                                target_lbl = lbl
                                break

                    # Fallback to "No" for questions asking about conflicts, relatives, termination, etc.
                    if not target_radio and options_map:
                        for opt_text, r, lbl in options_map:
                            if "no" in opt_text.lower():
                                target_radio = r
                                target_lbl = lbl
                                break
                        if not target_radio:
                            target_radio = options_map[0][1]
                            target_lbl = options_map[0][2]

                    if target_radio:
                        if target_lbl:
                            try:
                                self.driver.execute_script("arguments[0].click();", target_lbl)
                            except Exception:
                                pass
                        try:
                            self.driver.execute_script(
                                "arguments[0].click(); arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                                target_radio
                            )
                        except Exception:
                            pass
                        print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Radio: '{target_str}'")
                        answered.append({"question": question_text, "answer": target_str})
                        continue

            except Exception as e:
                print_lg(f"[IndeedForm] Error answering fieldset: {e}")
                continue

        # 2. Process Standalone Inputs (Text, Number, Textarea, Select, Custom Comboboxes)
        standalone_elems = []
        try:
            standalone_elems = self.driver.find_elements(
                By.XPATH,
                "//input[not(@type='hidden') and not(@type='submit') and not(@type='button') and not(@type='file')] "
                "| //textarea "
                "| //select "
                "| //*[@role='combobox'] "
                "| //*[@aria-haspopup='listbox'] "
                "| //div[contains(@class, 'icl-Select') or contains(@data-testid, 'combobox') or contains(@data-testid, 'select')]//button"
            )
        except Exception:
            pass

        for elem in standalone_elems:
            try:
                if elem in handled_inputs:
                    continue

                # Safety Guard: strictly reject elements from headers, navigation bars, site menus, or modals
                is_non_form_control = bool(self.driver.execute_script("""
                    const el = arguments[0];
                    if (!el) return true;
                    if (el.closest('header, nav, [role="banner"], [role="navigation"], [id*="gnav"], [id*="AccountMenu"], [data-testid*="header"], [role="dialog"], [role="alertdialog"], .ia-ExitModal, [class*="ExitModal"]')) {
                        return true;
                    }
                    const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                    const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    const cls = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();
                    const combo = txt + ' ' + aria + ' ' + id + ' ' + cls;
                    if (combo.includes('save and close') || combo.includes('save & close') || combo.includes('save and exit') ||
                        combo.includes('account') || combo.includes('profile') || combo.includes('notification') ||
                        combo.includes('message') || combo.includes('salary guide') || combo.includes('company reviews') ||
                        combo.includes('find jobs') || combo.includes('report') || combo.includes('help') ||
                        combo.includes('sign in') || combo.includes('sign out') ||
                        combo.includes('back') || combo.includes('previous') || combo.includes('←') ||
                        combo.includes('exit') || combo.includes('cancel') || combo.includes('discard') ||
                        combo.includes('return to')) {
                        return true;
                    }
                    return false;
                """, elem))
                if is_non_form_control:
                    continue

                tag_name = elem.tag_name.lower()
                if tag_name in ("html", "body", "main", "form", "section", "article"):
                    continue
                if tag_name == "div" and elem.get_attribute("role") != "combobox" and not elem.get_attribute("aria-haspopup"):
                    continue

                inp_type = (elem.get_attribute("type") or "text").lower()

                # For <select> elements, do not skip if parent/wrapper is displayed (even if select itself has CSS opacity: 0)
                if tag_name == "select":
                    if not elem.is_displayed():
                        try:
                            parent_disp = bool(self.driver.execute_script("""
                                const el = arguments[0];
                                const parent = el.parentElement;
                                if (!parent) return false;
                                const rect = parent.getBoundingClientRect();
                                const style = window.getComputedStyle(parent);
                                return style.display !== 'none' && style.visibility !== 'hidden' && (rect.width > 0 || rect.height > 0);
                            """, elem))
                            if not parent_disp:
                                continue
                        except Exception:
                            continue
                else:
                    if not elem.is_displayed():
                        continue

                # Skip standard name/email inputs if they belong to contact info (keep phone to handle questions step)
                name_attr = (elem.get_attribute("name") or "").lower()
                id_attr = (elem.get_attribute("id") or "").lower()
                if any(k in name_attr or k in id_attr for k in ["first-name", "last-name", "email", "age", "recaptcha"]):
                    continue

                # Extract Question Label
                question_text = ""
                # 1. aria-labelledby
                aria_labelledby = elem.get_attribute("aria-labelledby")
                if aria_labelledby:
                    for l_id in aria_labelledby.split():
                        try:
                            l_elem = self.driver.find_element(By.ID, l_id)
                            if l_elem and l_elem.text.strip():
                                question_text = l_elem.text.strip().replace("\n", " ")
                                break
                        except Exception:
                            pass
                # 2. label[for='{elem_id}']
                elem_id = elem.get_attribute("id") or ""
                if not question_text and elem_id:
                    try:
                        lbls = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{elem_id}']")
                        if lbls and lbls[0].text.strip():
                            question_text = lbls[0].text.strip().replace("\n", " ")
                    except Exception:
                        pass
                # 3. aria-label
                if not question_text:
                    aria_lbl = elem.get_attribute("aria-label")
                    if aria_lbl and aria_lbl.strip():
                        question_text = aria_lbl.strip().replace("\n", " ")
                # 4. Nearest preceding label, legend, or heading
                if not question_text:
                    try:
                        prec_lbls = elem.find_elements(
                            By.XPATH,
                            "preceding::label[1] | preceding::legend[1] | preceding::h1[1] | preceding::h2[1] | preceding::h3[1] | preceding::h4[1] | preceding::span[contains(@class, 'label') or contains(@class, 'Label')][1]"
                        )
                        if prec_lbls and prec_lbls[0].is_displayed() and prec_lbls[0].text.strip():
                            question_text = prec_lbls[0].text.strip().replace("\n", " ")
                    except Exception:
                        pass
                # 5. Ancestor label or container label
                if not question_text:
                    try:
                        p_lbl = elem.find_element(By.XPATH, "ancestor::label[1]")
                        if p_lbl and p_lbl.text.strip():
                            question_text = p_lbl.text.strip().replace("\n", " ")
                    except Exception:
                        pass
                if not question_text:
                    try:
                        p_lbl = elem.find_element(
                            By.XPATH,
                            "ancestor::div[contains(@class, 'item') or @data-testid or contains(@class, 'Group') or contains(@class, 'Field') or contains(@class, 'form-group')][1]//label[1]"
                        )
                        if p_lbl and p_lbl.text.strip():
                            question_text = p_lbl.text.strip().replace("\n", " ")
                    except Exception:
                        pass
                # 6. Fallback from name/id/placeholder
                if not question_text:
                    if "currency" in name_attr or "currency" in id_attr:
                        question_text = "Select currency type"
                    else:
                        question_text = elem.get_attribute("placeholder") or name_attr or elem_id or "Question"

                q_lower = question_text.lower()

                # Explicit Checkbox Handler
                if inp_type == "checkbox":
                    handled_inputs.add(elem)
                    should_check = False
                    if any(w in q_lower for w in ["text message", "sms", "notification", "agree", "certify", "acknowledge", "consent", "terms"]):
                        should_check = True
                    elif any(w in q_lower for w in ["disability", "veteran", "felony"]):
                        should_check = False
                    else:
                        should_check = True

                    try:
                        is_checked = elem.is_selected()
                        if should_check and not is_checked:
                            self.driver.execute_script("arguments[0].click();", elem)
                            print_lg(f"[IndeedForm] Checkbox checked: '{question_text[:60]}'")
                        elif not should_check and is_checked:
                            self.driver.execute_script("arguments[0].click();", elem)
                            print_lg(f"[IndeedForm] Checkbox unchecked: '{question_text[:60]}'")
                    except Exception as e:
                        print_lg(f"[IndeedForm] Error toggling checkbox: {e}")
                    answered.append({"question": question_text, "answer": "Checked" if should_check else "Unchecked"})
                    continue

                # Dropdowns (<select>)
                if tag_name == "select":
                    handled_inputs.add(elem)
                    sel_elem = Select(elem)
                    raw_options = [o.text.strip() for o in sel_elem.options if o.text.strip()]
                    clean_options = [o for o in raw_options if o.lower() not in ["select an option", "select...", "choose an option", "choose one", "select", "-- select --"]]
                    options_for_qna = clean_options if clean_options else raw_options

                    is_currency = (
                        any(w in question_text.lower() for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"])
                        or "currency" in name_attr
                        or "currency" in id_attr
                        or any(any(c in o.lower() for c in ["inr", "rupee", "₹", "usd", "dollar", "eur", "euro"]) for o in options_for_qna)
                    )

                    if is_currency:
                        best_opt = self._resolve_safe_option("Select currency type", options_for_qna, "INR", "INR")
                    else:
                        sel_obj: Answer = self.qna_engine.answer_question(
                            question=question_text,
                            options=options_for_qna,
                            field_type="select",
                            job_context={"title": job_title, "company": company_name}
                        )
                        raw_val = sel_obj.value if sel_obj else ""
                        qna_match = self.qna_engine._match_option(str(raw_val), options_for_qna) if raw_val else None
                        best_opt = self._resolve_safe_option(question_text, options_for_qna, str(raw_val), qna_match)

                    selected_val = self._select_native_option(elem, best_opt)
                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Select: '{selected_val or best_opt}'")
                    answered.append({"question": question_text, "answer": str(selected_val or best_opt)})
                    continue

                # Custom Comboboxes / Dropdown Buttons
                is_combobox_or_btn = (
                    tag_name == "button"
                    or elem.get_attribute("role") == "combobox"
                    or elem.get_attribute("aria-haspopup") in ("listbox", "true", "menu")
                    or "select" in (elem.get_attribute("data-testid") or "").lower()
                    or "select" in (elem.get_attribute("class") or "").lower()
                    or "select an option" in (elem.text or "").lower()
                    or "choose an option" in (elem.text or "").lower()
                )

                if is_combobox_or_btn:
                    handled_inputs.add(elem)
                    is_currency = (
                        any(w in question_text.lower() for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"])
                        or "currency" in name_attr
                        or "currency" in id_attr
                    )
                    is_referral = any(w in question_text.lower() for w in ["hear about", "referral", "source", "sds"])

                    if is_currency:
                        best_opt = "INR"
                    elif is_referral:
                        best_opt = "Indeed"
                    else:
                        cb_options = self._get_custom_combobox_options(elem)
                        if cb_options:
                            sel_obj: Answer = self.qna_engine.answer_question(
                                question=question_text,
                                options=cb_options,
                                field_type="select",
                                job_context={"title": job_title, "company": company_name}
                            )
                            raw_val = sel_obj.value if sel_obj else ""
                            qna_match = self.qna_engine._match_option(str(raw_val), cb_options) if raw_val else None
                            best_opt = self._resolve_safe_option(question_text, cb_options, str(raw_val), qna_match)
                        else:
                            best_opt = self._resolve_safe_option(question_text, [], "", None)

                    selected_val = self._select_custom_combobox_option(elem, best_opt, question_context=question_text)
                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Custom Combobox: '{selected_val or best_opt}'")
                    answered.append({"question": question_text, "answer": str(selected_val or best_opt)})
                    continue

                # Check if this input is a combobox, searchable select, or has an active listbox/dropdown attached
                q_lower = question_text.lower()
                inputmode = (elem.get_attribute("inputmode") or "").lower()
                pattern = (elem.get_attribute("pattern") or "").lower()

                # Guard: textareas, tel/number inputs, and explicit non-combobox fields must NEVER be treated as comboboxes
                is_explicit_non_combobox = (
                    tag_name == "textarea"
                    or inp_type in ("tel", "number", "email", "password")
                    or inputmode in ("numeric", "decimal", "tel", "email")
                    or any(w in q_lower for w in [
                        "phone", "mobile", "amount", "salary", "why", "describe",
                        "cover letter", "tell us", "experience", "how many", "years",
                        "notice period", "rate yourself", "summary", "explanation"
                    ])
                )

                is_combobox = False
                combobox_options = []
                if not is_explicit_non_combobox:
                    try:
                        combobox_options = self.driver.execute_script("""
                            const el = arguments[0];
                            const role = (el.getAttribute('role') || '').toLowerCase();
                            const ariaAuto = (el.getAttribute('aria-autocomplete') || '').toLowerCase();
                            const ariaHasPopup = (el.getAttribute('aria-haspopup') || '').toLowerCase();
                            const isComboInput = role === 'combobox' || ariaAuto === 'list' || ariaHasPopup === 'listbox';

                            const container = el.closest('[role="combobox"], [role="listbox"], .icl-Select, [data-testid*="combobox"], [data-testid*="select"]') || (isComboInput ? el.parentElement : null);
                            if (!container || container === document.body || container === document.documentElement) {
                                return [];
                            }
                            const optionEls = Array.from(container.querySelectorAll('[role="option"], li[role="option"], ul[role="listbox"] li, .icl-Select-option'));
                            return optionEls.map(o => (o.innerText || o.textContent || '').trim()).filter(t => t.length > 0);
                        """, elem)
                        if combobox_options and len(combobox_options) > 0:
                            is_combobox = True
                    except Exception:
                        pass

                if is_combobox and combobox_options:
                    clean_cb_options = [o for o in combobox_options if o.lower() not in ["select an option", "select...", "choose an option", "choose one", "select", "-- select --"]]
                    cb_options = clean_cb_options if clean_cb_options else combobox_options

                    sel_obj: Answer = self.qna_engine.answer_question(
                        question=question_text,
                        options=cb_options,
                        field_type="select",
                        job_context={"title": job_title, "company": company_name}
                    )
                    raw_val = sel_obj.value if sel_obj else ""
                    qna_match = self.qna_engine._match_option(str(raw_val), cb_options) if raw_val else None
                    best_opt = self._resolve_safe_option(question_text, cb_options, str(raw_val), qna_match)

                    if best_opt:
                        try:
                            elem.clear()
                            elem.send_keys(best_opt)
                            time.sleep(0.3)
                        except Exception:
                            pass

                    clicked_opt = self.driver.execute_script("""
                        const targetText = arguments[0].toLowerCase();
                        const optionEls = Array.from(document.querySelectorAll('[role="option"], li[role="option"], ul[role="listbox"] li, .icl-Select-option'));
                        for (const opt of optionEls) {
                            const txt = (opt.innerText || opt.textContent || '').trim().toLowerCase();
                            if (txt === targetText || txt.includes(targetText) || targetText.includes(txt)) {
                                opt.scrollIntoView({block: 'nearest'});
                                opt.click();
                                return true;
                            }
                        }
                        return false;
                    """, best_opt)

                    if not clicked_opt:
                        try:
                            elem.send_keys(Keys.ENTER)
                        except Exception:
                            pass

                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Combobox: '{best_opt}'")
                    answered.append({"question": question_text, "answer": str(best_opt)})
                    continue

                # Text / Number inputs and Textareas
                is_numeric_field = (
                    inp_type == "number"
                    or inputmode in ("numeric", "decimal")
                    or "0-9" in pattern
                    or any(w in q_lower for w in [
                        "how many years", "years of experience", "total years",
                        "number of years", "years of relevant", "how many months",
                        "notice period", "rate yourself", "scale of", "scale 1-", "scale (1-"
                    ])
                )

                # Special Field Handlers: Phone, Salary Amount, Seeking Employment, Referrals, Bio
                is_phone_field = (
                    inp_type == "tel"
                    or inputmode == "tel"
                    or any(w in q_lower for w in ["phone", "mobile", "contact number"])
                )
                is_salary_amount_field = (
                    any(w in q_lower for w in [
                        "enter the amount", "please enter the amount", "salary amount", "desired salary",
                        "expected salary", "compensation amount", "salary expectation", "salary expectations",
                        "annual salary", "compensation expectation"
                    ])
                )
                is_seeking_employment_field = (
                    any(w in q_lower for w in ["why are you currently seeking employment", "reason for seeking", "why are you looking for a change", "reason for leaving"])
                )
                is_conditional_referral_field = (
                    any(w in q_lower for w in ["if you answered \"yes\"", "if you answered yes", "staffing agency, please provide", "please provide the name", "please specify"])
                )
                is_tell_us_bio_field = (
                    any(w in q_lower for w in ["tell us anything else about yourself", "anything else about yourself", "additional information", "cover letter", "message to hiring manager"])
                )

                is_home_phone = (
                    "home" in q_lower and any(w in q_lower for w in ["phone", "number", "tel"])
                ) or "homephone" in name_attr or "homephone" in id_attr
                is_required = (
                    elem.get_attribute("required") is not None
                    or elem.get_attribute("aria-required") == "true"
                    or "*" in question_text
                )

                if is_phone_field:
                    phone_raw = str(self.personal.get("phone_number", "6388623967")).strip()
                    clean_phone = self._clean_phone_number(phone_raw)
                    if is_home_phone:
                        home_raw = str(self.personal.get("home_phone", "")).strip()
                        if home_raw:
                            ans_str = self._clean_phone_number(home_raw)
                        elif is_required:
                            ans_str = clean_phone
                        else:
                            ans_str = ""  # Optional home phone: leave empty to avoid redundant or invalid input
                    else:
                        ans_str = clean_phone

                    # If optional home phone and empty, clear any invalid draft value
                    if ans_str == "" and is_home_phone and not is_required:
                        existing_val = (elem.get_attribute("value") or "").strip()
                        if existing_val:
                            self._clear_and_type_input(elem, "")
                            print_lg("[IndeedForm] Cleared optional home phone field.")
                        continue
                elif is_salary_amount_field:
                    salary_val = self.professional.get("desired_salary") or self.personal.get("desired_salary", 550000)
                    digits = re.findall(r'\d+', str(salary_val))
                    ans_str = digits[0] if digits else "550000"
                elif is_seeking_employment_field:
                    ans_str = "Seeking new opportunities to grow professionally and contribute technical expertise in enterprise automation and Python development."
                elif is_conditional_referral_field:
                    ans_str = "N/A"
                elif is_tell_us_bio_field:
                    ans_str = "I am a dedicated automation engineer with 2 years of experience in RPA and Python, eager to contribute to your team."
                else:
                    ans_obj: Answer = self.qna_engine.answer_question(
                        question=question_text,
                        options=[],
                        field_type="number" if is_numeric_field else "text",
                        job_context={"title": job_title, "company": company_name}
                    )
                    ans_str = str(ans_obj.value if ans_obj else "").strip()

                    if is_numeric_field:
                        # Indeed strictly enforces: "Answer must be a valid number (no decimals)."
                        digits = re.findall(r'\d+', ans_str)
                        if digits:
                            try:
                                cand_exp = int(round(float(self.personal.get("years_of_experience", 2))))
                            except Exception:
                                cand_exp = 2
                            if len(digits) > 1 and str(cand_exp) in digits:
                                ans_str = str(cand_exp)
                            elif len(digits) > 1 and int(digits[0]) <= cand_exp <= int(digits[-1]):
                                ans_str = str(cand_exp)
                            else:
                                ans_str = digits[0]
                        else:
                            try:
                                cand_exp = int(round(float(self.personal.get("years_of_experience", 2))))
                            except Exception:
                                cand_exp = 2
                            ans_str = str(cand_exp) if any(w in q_lower for w in ["experience", "years"]) else "0"

                existing_val = (elem.get_attribute("value") or "").strip()
                # If field is already populated with valid content and not flagged invalid, preserve it
                if existing_val and elem.get_attribute("aria-invalid") != "true":
                    if not is_numeric_field or existing_val.isdigit():
                        continue

                if not existing_val or existing_val != ans_str:
                    self._clear_and_type_input(elem, ans_str)
                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Input: '{ans_str}'")
                    answered.append({"question": question_text, "answer": ans_str})

            except Exception as e:
                print_lg(f"[IndeedForm] Error answering standalone input: {e}")
                continue

        # 3. Safety Fallback: Ensure no visible radio group is left unselected
        try:
            all_radios = self.driver.find_elements(By.XPATH, "//input[@type='radio']")
            radio_groups = {}
            for r in all_radios:
                if r.is_displayed():
                    name = r.get_attribute("name") or "default"
                    radio_groups.setdefault(name, []).append(r)

            for name, r_list in radio_groups.items():
                if not any(r.is_selected() for r in r_list):
                    chosen = r_list[0]
                    # Default to 'No' option if present (avoids unsolicited conflict disclosure)
                    for r in r_list:
                        try:
                            parent_txt = r.find_element(By.XPATH, "..").text.strip().lower()
                            if "no" in parent_txt:
                                chosen = r
                                break
                        except Exception:
                            pass
                    self.driver.execute_script(
                        "arguments[0].click(); arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                        chosen
                    )
                    print_lg(f"[IndeedForm] Fallback selected radio in group '{name}'.")
        except Exception:
            pass

        # 4. Safety Fallback: Ensure no visible dropdown / select or combobox is left unselected or on placeholder
        try:
            all_selects = self.driver.find_elements(By.TAG_NAME, "select")
            for sel in all_selects:
                try:
                    # Check if unselected or showing placeholder
                    is_unselected = bool(self.driver.execute_script("""
                        const sel = arguments[0];
                        if (!sel || !sel.options || sel.options.length === 0) return false;
                        if (sel.selectedIndex <= 0 && (!sel.value || sel.value === '')) return true;
                        const curText = (sel.options[sel.selectedIndex]?.text || '').toLowerCase();
                        return curText.includes('select an option') || curText.includes('choose an option') || curText.includes('select...');
                    """, sel))

                    if is_unselected:
                        q_name = (sel.get_attribute("name") or "").lower()
                        q_id = (sel.get_attribute("id") or "").lower()
                        aria_l = (sel.get_attribute("aria-label") or "").lower()

                        opts = self.driver.execute_script("""
                            const sel = arguments[0];
                            return Array.from(sel.options).map(o => (o.text || o.innerText || '').trim()).filter(t => t.length > 0);
                        """, sel) or []

                        clean_opts = [o for o in opts if o.lower() not in ["select an option", "choose an option", "select...", "choose one", "select"]]
                        is_curr = (
                            any(w in (q_name + q_id + aria_l) for w in ["currency", "payunit", "salary"])
                            or any(any(c in o.lower() for c in ["inr", "rupee", "₹", "usd", "dollar"]) for o in clean_opts)
                        )

                        if is_curr:
                            target = self._resolve_safe_option("Select currency type", clean_opts or opts, "INR", "INR")
                        else:
                            target = clean_opts[0] if clean_opts else (opts[1] if len(opts) > 1 else "")

                        if target:
                            chosen = self._select_native_option(sel, target)
                            print_lg(f"[IndeedForm] Fallback selected dropdown option '{chosen}' for field '{q_id or q_name or 'select'}'.")
                            answered.append({"question": q_id or q_name or "Select", "answer": chosen})
                except Exception:
                    pass
        except Exception:
            pass

        # 5. Safety Fallback: Ensure no custom combobox or button dropdown is left showing 'Select an option'
        try:
            custom_unselected = self.driver.find_elements(
                By.XPATH,
                "//button[contains(., 'Select an option') or contains(., 'Choose an option')] "
                "| //div[@role='combobox' and (contains(., 'Select an option') or contains(., 'Choose an option'))] "
                "| //*[self::div or self::span][@role='combobox' or @aria-haspopup][contains(., 'Select an option') or contains(., 'Choose an option')] "
                "| //*[not(self::option)][normalize-space(text())='Select an option' or normalize-space(.)='Select an option']"
            )
            for c_elem in custom_unselected:
                try:
                    c_text = (c_elem.text or "").lower()
                    if "select an option" in c_text or "choose an option" in c_text:
                        q_cxt = self.driver.execute_script("""
                            const el = arguments[0];
                            const ariaId = el.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const pLbl = el.closest('div, fieldset')?.querySelector('label, legend, [class*="label"], [class*="heading"]');
                            return pLbl ? pLbl.innerText.trim() : '';
                        """, c_elem) or ""
                        q_lower = q_cxt.lower()
                        if any(w in q_lower for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"]):
                            target_val = "INR"
                        elif any(w in q_lower for w in ["hear about", "referral", "source", "sds"]):
                            target_val = "Indeed"
                        else:
                            target_val = ""
                        chosen = self._select_custom_combobox_option(c_elem, target_val, question_context=q_cxt)
                        if chosen:
                            print_lg(f"[IndeedForm] Fallback selected custom combobox option '{chosen}' for '{q_cxt[:40]}'.")
                            answered.append({"question": q_cxt or "Select", "answer": chosen})
                except Exception:
                    pass
        except Exception:
            pass

        return answered

    def advance_to_next_step(self) -> bool:
        """Clicks the primary advance/continue button and waits for the step transition."""
        self.dismiss_exit_modal()
        self.wait_for_spinner()
        cont_btn = None

        def _is_safe_continue(btn) -> bool:
            try:
                txt = (btn.text or btn.get_attribute("value") or "").strip().lower()
                aria = (btn.get_attribute("aria-label") or "").strip().lower()
                combo = f"{txt} {aria}".strip()
                if any(bad in combo for bad in [
                    "save and close", "save & close", "save and exit", "back", "previous",
                    "edit", "exit", "cancel", "discard", "close", "report", "account", "profile", "sign out"
                ]):
                    return False
                if combo in ["←", "<", "save"]:
                    return False
                return True
            except Exception:
                return True

        # 1. Search via declared XPath selectors
        for sel in FORM_CONTINUE_BUTTONS:
            try:
                for b in self.driver.find_elements(By.XPATH, sel):
                    try:
                        if b.is_displayed() and _is_safe_continue(b):
                            cont_btn = b
                            break
                    except Exception:
                        pass
                if cont_btn:
                    break
            except Exception:
                continue

        # 2. JavaScript fallback search across all button-like elements
        if not cont_btn:
            try:
                js_btn = self.driver.execute_script("""
                    const candidates = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"]'));
                    for (const el of candidates) {
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        if (el.closest('header, nav, [role="banner"], [role="navigation"], [id*="gnav"], [id*="AccountMenu"], [data-testid*="header"], [role="dialog"], [role="alertdialog"], .ia-ExitModal')) {
                            continue;
                        }
                        const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                        const aria = (el.getAttribute('aria-label') || '').trim().toLowerCase();
                        const combo = txt + ' ' + aria;
                        if (combo.includes('save and close') || combo.includes('save & close') || combo.includes('save and exit') ||
                            combo.includes('back') || combo.includes('previous') || combo.includes('edit') ||
                            combo.includes('exit') || combo.includes('cancel') || combo.includes('discard') || combo.includes('close') ||
                            combo === '←' || combo === '<') {
                            continue;
                        }
                        if (txt.includes('continue') || txt.includes('next') || txt.includes('review your application') ||
                            txt.includes('review application') || txt.includes('save and continue') || txt.includes('save & continue')) {
                            return el;
                        }
                    }
                    return null;
                """)
                if js_btn and _is_safe_continue(js_btn):
                    cont_btn = js_btn
            except Exception:
                pass

        if not cont_btn:
            print_lg("[IndeedForm] No visible continue button found on current step.")
            return False

        old_url = self.driver.current_url
        try:
            btn_label = (cont_btn.text or cont_btn.get_attribute("value") or "").strip()
        except Exception:
            btn_label = "Continue"
        clicked = False
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", cont_btn)
            time.sleep(0.3)
            cont_btn.click()
            clicked = True
        except Exception:
            # Fallback: query fresh DOM and click via JavaScript to avoid stale element reference
            try:
                clicked = bool(self.driver.execute_script("""
                    const candidates = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"], a[role="button"]'));
                    for (const el of candidates) {
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;
                        const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                        if (txt.includes('continue') || txt.includes('next') || txt.includes('review your application') ||
                            txt.includes('review application') || txt.includes('save and continue') || txt.includes('save & continue')) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                """))
            except Exception as e:
                print_lg(f"[IndeedForm] Error clicking continue button: {e}")
                return False

        if not clicked:
            return False

        # Wait for transition: wait for spinner or DOM change (up to 4s)
        time.sleep(1)
        self.wait_for_spinner(timeout=4)
        for _ in range(6):
            if self.driver.current_url != old_url:
                break
            time.sleep(0.5)

        if self.driver.current_url == old_url:
            err_texts = []
            try:
                err_texts = self.driver.execute_script("""
                    const errs = Array.from(document.querySelectorAll(
                        '[class*="error" i], [class*="invalid" i], [role="alert"], [aria-invalid="true"]'
                    ));
                    return errs
                        .filter(e => e.offsetWidth > 0 && e.offsetHeight > 0)
                        .map(e => (e.innerText || e.textContent || '').trim())
                        .filter(t => t.length > 0 && !t.includes('cookie') && !t.includes('javascript'));
                """) or []
                if err_texts:
                    print_lg(f"[IndeedForm] Validation error(s) preventing advance: {err_texts[:3]}")
            except Exception:
                pass

            # Execute comprehensive Runtime Form Self-Healing on DOM
            healed = self._auto_heal_invalid_step_fields()
            if healed > 0:
                print_lg(f"[IndeedForm] Auto-healed {healed} invalid field(s). Re-triggering advance...")
                time.sleep(0.5)
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].click();", cont_btn)
                except Exception:
                    pass
                time.sleep(1)
                self.wait_for_spinner(timeout=4)
                for _ in range(6):
                    if self.driver.current_url != old_url:
                        return True
                    time.sleep(0.5)

            if self.driver.current_url == old_url and err_texts:
                print_lg(f"[IndeedForm] Step remained blocked after self-healing (URL: {self.driver.current_url}).")
                return False

        return True

    def _auto_heal_invalid_step_fields(self) -> int:
        """Runtime Form Self-Healing Engine.

        Inspects the live DOM for validation errors (aria-invalid, error alerts,
        unanswered dropdowns, unselected radios, empty required inputs) and dynamically
        resolves and repairs them in runtime.

        Returns the number of fields successfully healed.
        """
        print_lg("[IndeedForm] Runtime Self-Healer: Scanning DOM for validation errors and incomplete fields...")
        healed_count = 0

        # Pass 0: Direct Targeted Healing for elements flagged with "Choose an option to continue" or aria-invalid
        try:
            target_controls = self.driver.execute_script("""
                const errElements = Array.from(document.querySelectorAll('*')).filter(el => {
                    if (el.offsetWidth === 0 && el.offsetHeight === 0) return false;
                    const t = (el.innerText || el.textContent || '').trim().toLowerCase();
                    const hasErrText = t.includes('choose an option to continue') ||
                                       t.includes('select an option to continue') ||
                                       t.includes('this question is required') ||
                                       t.includes('please answer this question') ||
                                       t.includes('please select an option') ||
                                       t.includes('is required') ||
                                       t === 'choose an option to continue.' ||
                                       t === 'required';
                    const hasErrRole = el.getAttribute('role') === 'alert' ||
                                       el.getAttribute('aria-invalid') === 'true' ||
                                       (el.className && typeof el.className === 'string' && el.className.toLowerCase().includes('error'));
                    return hasErrText || hasErrRole;
                });

                const targets = [];
                for (const err of errElements) {
                    // 1. Check aria-describedby linkage
                    if (err.id) {
                        const linked = document.querySelector(`[aria-describedby*="${err.id}"]`);
                        if (linked && !targets.includes(linked)) {
                            targets.push(linked);
                            continue;
                        }
                    }
                    // 2. Check preceding siblings (direct or child control)
                    let sib = err.previousElementSibling;
                    let foundSibControl = null;
                    while (sib && !foundSibControl) {
                        if (sib.matches('select, button, [role="combobox"], [aria-haspopup], input, textarea')) {
                            foundSibControl = sib;
                        } else {
                            foundSibControl = sib.querySelector('select, button, [role="combobox"], [aria-haspopup], input:not([type="hidden"]), textarea');
                        }
                        sib = sib.previousElementSibling;
                    }
                    if (foundSibControl && !targets.includes(foundSibControl)) {
                        targets.push(foundSibControl);
                        continue;
                    }
                    // 3. Ascendant question container
                    const container = err.closest('fieldset, [data-testid*="question"], [class*="Questions-item"], [class*="question" i], [class*="form-group" i], [class*="field" i]');
                    if (container) {
                        const ctrl = container.querySelector('select, button, [role="combobox"], [aria-haspopup], input:not([type="hidden"]), textarea');
                        if (ctrl && !targets.includes(ctrl)) {
                            targets.push(ctrl);
                            continue;
                        }
                        if (!targets.includes(container)) {
                            targets.push(container);
                            continue;
                        }
                    }
                }
                return targets;
            """) or []

            for node in target_controls:
                try:
                    # 1. Native <select> (either node itself or inside node)
                    sel_elem = node if getattr(node, "tag_name", "").lower() == "select" else self.driver.execute_script("return arguments[0].querySelector ? arguments[0].querySelector('select') : null;", node)
                    if sel_elem:
                        q_txt = self.driver.execute_script("""
                            const sel = arguments[0];
                            const ariaId = sel.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const pLbl = sel.closest('div, fieldset')?.querySelector('label, legend, [class*="label"], [class*="heading"]');
                            return pLbl ? pLbl.innerText.trim() : '';
                        """, sel_elem) or "Question"
                        clean_opts = self.driver.execute_script("""
                            const sel = arguments[0];
                            return Array.from(sel.options).map(o => (o.text || o.innerText || '').trim()).filter(t => t.length > 0 && !t.toLowerCase().includes('select an option') && !t.toLowerCase().includes('choose'));
                        """, sel_elem) or []
                        if clean_opts:
                            best = self._resolve_safe_option(q_txt, clean_opts, "", None) or clean_opts[0]
                            chosen = self._select_native_option(sel_elem, best)
                            if chosen:
                                print_lg(f"[IndeedForm] Auto-healed error-flagged dropdown '{q_txt[:50]}' -> '{chosen}'")
                                healed_count += 1
                                continue

                    # 2. Custom Combobox / Dropdown Button
                    combo_elem = self.driver.execute_script("""
                        const n = arguments[0];
                        if (n.matches && n.matches('button, [role="combobox"], [aria-haspopup], [class*="select" i]')) return n;
                        return n.querySelector ? n.querySelector('button, [role="combobox"], [aria-haspopup], [class*="select" i]') : null;
                    """, node)
                    if combo_elem:
                        q_txt = self.driver.execute_script("""
                            const el = arguments[0];
                            const ariaId = el.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const pLbl = el.closest('div, fieldset')?.querySelector('label, legend, [class*="label"], [class*="heading"]');
                            return pLbl ? pLbl.innerText.trim() : '';
                        """, combo_elem) or "Question"
                        q_lower = q_txt.lower()
                        if any(w in q_lower for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"]):
                            target_opt = "INR"
                        elif any(w in q_lower for w in ["hear about", "referral", "source", "sds"]):
                            target_opt = "Indeed"
                        else:
                            target_opt = ""
                        chosen = self._select_custom_combobox_option(combo_elem, target_opt, question_context=q_txt)
                        if chosen:
                            print_lg(f"[IndeedForm] Auto-healed error-flagged combobox '{q_txt[:50]}' -> '{chosen}'")
                            healed_count += 1
                            continue

                    # 3. Text/Textarea input left empty or invalid
                    input_elem = node if getattr(node, "tag_name", "").lower() in ("input", "textarea") else self.driver.execute_script("return arguments[0].querySelector ? arguments[0].querySelector('input:not([type=\"hidden\"]), textarea') : null;", node)
                    if input_elem:
                        q_txt = self.driver.execute_script("""
                            const el = arguments[0];
                            const pLbl = el.closest('div, fieldset')?.querySelector('label, legend, [class*="label"]');
                            return pLbl ? pLbl.innerText.trim() : '';
                        """, input_elem) or ""
                        val = (input_elem.get_attribute("value") or "").strip()
                        if not val:
                            q_l = q_txt.lower()
                            if any(w in q_l for w in ["referral", "name of the person", "staffing agency", "if you answered yes"]):
                                fill_val = "N/A"
                            elif any(w in q_l for w in ["salary", "compensation"]):
                                fill_val = "550000"
                            elif any(w in q_l for w in ["experience", "years"]):
                                fill_val = "2"
                            else:
                                fill_val = "N/A"
                            self._clear_and_type_input(input_elem, fill_val)
                            print_lg(f"[IndeedForm] Auto-healed empty field '{q_txt[:50]}' -> '{fill_val}'")
                            healed_count += 1
                            continue
                except Exception:
                    pass
        except Exception as e:
            print_lg(f"[IndeedForm] Error in pass 0 error node healing: {e}")

        # Pass 1: Handle any <select> dropdowns left unselected or on placeholder
        try:
            selects_data = self.driver.execute_script("""
                const selects = Array.from(document.querySelectorAll('select'));
                return selects.map((s, idx) => {
                    const text = (s.options[s.selectedIndex]?.text || '').trim().toLowerCase();
                    const val = (s.value || '').trim();
                    const isUnselected = (s.selectedIndex <= 0 && !val) || text.includes('select an option') || text.includes('choose an option') || text.includes('select...');
                    const name = (s.getAttribute('name') || '').toLowerCase();
                    const id = (s.getAttribute('id') || '').toLowerCase();
                    const ariaLabel = (s.getAttribute('aria-label') || '').toLowerCase();
                    const cleanOpts = Array.from(s.options).map(o => (o.text || o.innerText || '').trim()).filter(t => t.length > 0 && !t.toLowerCase().includes('select an option') && !t.toLowerCase().includes('choose'));
                    return {
                        index: idx,
                        isUnselected: isUnselected,
                        name: name,
                        id: id,
                        ariaLabel: ariaLabel,
                        options: cleanOpts
                    };
                });
            """) or []

            for item in selects_data:
                if item.get("isUnselected"):
                    idx = item["index"]
                    all_sels = self.driver.find_elements(By.TAG_NAME, "select")
                    if idx >= len(all_sels):
                        continue
                    elem = all_sels[idx]
                    clean_opts = item.get("options") or []
                    if not clean_opts:
                        continue

                    context_str = f"{item.get('name')} {item.get('id')} {item.get('ariaLabel')}"
                    try:
                        lbl_txt = self.driver.execute_script("""
                            const sel = arguments[0];
                            const ariaId = sel.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const pLbl = sel.closest('div, fieldset')?.querySelector('label, legend, [class*="label"]');
                            if (pLbl && pLbl.innerText) return pLbl.innerText.trim();
                            return '';
                        """, elem) or ""
                    except Exception:
                        lbl_txt = ""

                    query = lbl_txt or context_str or "question"
                    best = self._resolve_safe_option(query, clean_opts, "", None)
                    if not best and clean_opts:
                        best = clean_opts[0]

                    if best:
                        chosen = self._select_native_option(elem, best)
                        print_lg(f"[IndeedForm] Auto-healed unselected dropdown '{query[:50]}' -> '{chosen}'")
                        healed_count += 1
        except Exception as e:
            print_lg(f"[IndeedForm] Error in dropdown self-healing: {e}")

        # Pass 2: Handle custom comboboxes / button selects showing placeholder or with error border
        try:
            custom_combos = self.driver.find_elements(
                By.XPATH,
                "//button[contains(., 'Select an option') or contains(., 'Choose an option') or @aria-invalid='true' or contains(@class, 'error')] "
                "| //div[@role='combobox' and (contains(., 'Select an option') or @aria-invalid='true')] "
                "| //*[self::div or self::span][@role='combobox' or @aria-haspopup][contains(., 'Select an option') or contains(., 'Choose an option') or @aria-invalid='true'] "
                "| //*[not(self::option)][normalize-space(text())='Select an option' or normalize-space(.)='Select an option']"
            )
            for c_elem in custom_combos:
                try:
                    c_txt = c_elem.text.lower()
                    if "select an option" in c_txt or "choose an option" in c_txt or c_elem.get_attribute("aria-invalid") == "true":
                        q_txt = self.driver.execute_script("""
                            const el = arguments[0];
                            const ariaId = el.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const pLbl = el.closest('div, fieldset')?.querySelector('label, legend, [class*="label"], [class*="heading"]');
                            return pLbl ? pLbl.innerText.trim() : '';
                        """, c_elem) or ""

                        q_lower = q_txt.lower()
                        is_currency = any(w in q_lower for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"])
                        if is_currency:
                            target_opt = "INR"
                        elif any(w in q_lower for w in ["hear about", "referral", "source"]):
                            target_opt = "Indeed"
                        else:
                            cb_opts = self._get_custom_combobox_options(c_elem)
                            if cb_opts:
                                target_opt = self._resolve_safe_option(q_txt, cb_opts, "", None)
                            else:
                                target_opt = ""

                        chosen = self._select_custom_combobox_option(c_elem, target_opt, question_context=q_txt)
                        if chosen:
                            print_lg(f"[IndeedForm] Auto-healed custom combobox '{q_txt[:50]}' -> '{chosen}'")
                            healed_count += 1
                except Exception:
                    pass
        except Exception as e:
            print_lg(f"[IndeedForm] Error in custom combobox self-healing: {e}")

        # Pass 3: Handle unselected radio groups in invalid fieldsets
        try:
            unselected_groups = self.driver.execute_script("""
                const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                const groups = {};
                for (const r of radios) {
                    const name = r.name || 'unnamed';
                    if (!groups[name]) groups[name] = { selected: false };
                    if (r.checked) groups[name].selected = true;
                }
                const unselected = [];
                for (const k in groups) {
                    if (!groups[k].selected) {
                        unselected.push(k);
                    }
                }
                return unselected;
            """) or []

            for g_name in unselected_groups:
                try:
                    r_list = self.driver.find_elements(By.XPATH, f"//input[@type='radio' and @name='{g_name}']")
                    if r_list and not any(r.is_selected() for r in r_list):
                        # Extract group question context
                        group_q = self.driver.execute_script("""
                            const r = arguments[0];
                            const p = r.closest('fieldset, div[role="radiogroup"], div');
                            const leg = p?.querySelector('legend, label, [class*="label"], [class*="heading"]');
                            return leg ? leg.innerText.trim() : '';
                        """, r_list[0]) or ""
                        group_q_lower = group_q.lower()

                        chosen = r_list[0]
                        # Match experience range if experience question
                        if any(w in group_q_lower for w in ["experience", "years", "year", "tenure"]):
                            for r in r_list:
                                try:
                                    parent_t = r.find_element(By.XPATH, "..").text.strip().lower()
                                    if "1 to 2" in parent_t or "1-2" in parent_t or "2" in parent_t:
                                        chosen = r
                                        break
                                except Exception:
                                    pass
                        elif any(w in group_q_lower for w in ["sponsorship", "conflict", "relative", "felony", "crime", "discharged", "referred"]):
                            for r in r_list:
                                try:
                                    parent_t = r.find_element(By.XPATH, "..").text.strip().lower()
                                    if "no" in parent_t:
                                        chosen = r
                                        break
                                except Exception:
                                    pass
                        elif any(w in group_q_lower for w in ["authorized", "eligible", "relocate", "relocation", "hybrid", "remote"]):
                            for r in r_list:
                                try:
                                    parent_t = r.find_element(By.XPATH, "..").text.strip().lower()
                                    if "yes" in parent_t:
                                        chosen = r
                                        break
                                except Exception:
                                    pass
                        else:
                            for r in r_list:
                                try:
                                    parent_t = r.find_element(By.XPATH, "..").text.strip().lower()
                                    if "no" in parent_t:
                                        chosen = r
                                        break
                                except Exception:
                                    pass

                        self.driver.execute_script(
                            "arguments[0].click(); arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                            chosen
                        )
                        print_lg(f"[IndeedForm] Auto-healed unselected radio group '{g_name}' ({group_q[:40]}).")
                        healed_count += 1
                except Exception:
                    pass
        except Exception as e:
            print_lg(f"[IndeedForm] Error in radio group self-healing: {e}")

        # Pass 4: Handle empty required text / textarea inputs
        try:
            empty_required = self.driver.find_elements(
                By.XPATH,
                "//input[(@required or @aria-required='true' or @aria-invalid='true') and not(@type='hidden') and not(@type='radio') and not(@type='checkbox') and not(@type='submit') and not(@type='button')] | //textarea[@required or @aria-required='true' or @aria-invalid='true']"
            )
            for inp in empty_required:
                try:
                    val = (inp.get_attribute("value") or "").strip()
                    p_txt = ""
                    try:
                        p_txt = self.driver.execute_script("""
                            const el = arguments[0];
                            const ariaId = el.getAttribute('aria-labelledby');
                            if (ariaId) {
                                const l = document.getElementById(ariaId);
                                if (l && l.innerText) return l.innerText.trim();
                            }
                            const p = el.closest('div, fieldset')?.querySelector('label, legend, [class*="label"]');
                            return p ? p.innerText.trim() : '';
                        """, inp) or ""
                    except Exception:
                        pass

                    if val:
                        # Field is already filled: preserve user data without unnecessary retries
                        print_lg(f"[IndeedForm] Field '{p_txt[:40]}' already filled ('{val}'). Preserving.")
                        continue

                    p_lower = p_txt.lower()
                    if any(w in p_lower for w in ["refer", "staffing", "agency", "name of the person", "if you answered"]):
                        ans = "N/A"
                    elif any(w in p_lower for w in ["salary", "amount", "expectation", "compensation"]):
                        salary_val = self.professional.get("desired_salary") or self.personal.get("desired_salary", 550000)
                        ans = str(salary_val)
                    elif any(w in p_lower for w in ["experience", "years", "number"]):
                        ans = "2"
                    else:
                        ans = "N/A"

                    self._clear_and_type_input(inp, ans)
                    print_lg(f"[IndeedForm] Auto-healed empty required text field '{p_txt[:40]}' -> '{ans}'")
                    healed_count += 1
                except Exception:
                    pass
        except Exception as e:
            print_lg(f"[IndeedForm] Error in text input self-healing: {e}")

        # Pass 5: Auto-clean non-digits in phone/number inputs
        try:
            fixed_digits = self.driver.execute_script("""
                let fixed = false;
                const badInputs = Array.from(document.querySelectorAll(
                    'input[aria-invalid="true"], [class*="error"] input, [class*="invalid"] input, input[type="tel"], input[type="number"]'
                ));
                for (const inp of badInputs) {
                    const val = (inp.value || '').trim();
                    if (val && /\\D/.test(val)) {
                        const digits = val.replace(/\\D/g, '');
                        const clean = digits.length >= 10 ? digits.slice(-10) : digits;
                        if (clean !== val) {
                            const proto = window.HTMLInputElement.prototype;
                            const desc = Object.getOwnPropertyDescriptor(proto, 'value');
                            if (desc && desc.set) {
                                desc.set.call(inp, clean);
                            } else {
                                inp.value = clean;
                            }
                            inp.dispatchEvent(new Event('input', { bubbles: true }));
                            inp.dispatchEvent(new Event('change', { bubbles: true }));
                            fixed = true;
                        }
                    }
                }
                return fixed;
            """)
            if fixed_digits:
                healed_count += 1
        except Exception:
            pass

        return healed_count

    def dismiss_exit_modal(self) -> bool:
        """Detects and dismisses Indeed 'Exit application?' modal by clicking 'Continue applying'."""
        if not self.driver:
            return False
        try:
            from platforms.indeed.selectors import EXIT_MODAL_CONTINUE_BUTTONS
            for sel in EXIT_MODAL_CONTINUE_BUTTONS:
                try:
                    for b in self.driver.find_elements(By.XPATH, sel):
                        if b.is_displayed():
                            print_lg("[IndeedForm] Detected exit application modal. Clicking 'Continue applying' to preserve flow...")
                            self.driver.execute_script("arguments[0].click();", b)
                            time.sleep(1)
                            return True
                except Exception:
                    pass

            dismissed = self.driver.execute_script("""
                const modals = Array.from(document.querySelectorAll('div[role="dialog"], div[role="alertdialog"], .ia-ExitModal, [class*="ExitModal"], [data-testid*="exit"]'));
                for (const modal of modals) {
                    const txt = (modal.innerText || modal.textContent || '').toLowerCase();
                    if (txt.includes('exit') || txt.includes('leave') || txt.includes('discard') || txt.includes('save your application') || txt.includes('save application progress')) {
                        const buttons = Array.from(modal.querySelectorAll('button, a[role="button"]'));
                        // 1. Try explicit continue/return buttons
                        for (const b of buttons) {
                            const bTxt = (b.innerText || b.textContent || b.value || '').trim().toLowerCase();
                            if (bTxt.includes('continue applying') || bTxt.includes('return to application') || bTxt.includes('keep applying') || bTxt.includes('stay') || bTxt === 'cancel' || bTxt === 'no') {
                                b.click();
                                return true;
                            }
                        }
                        // 2. Click modal close 'X' button to cancel exit and remain on application
                        const closeBtn = modal.querySelector('button[aria-label*="close" i], button[data-testid*="close" i], [aria-label*="dismiss" i], button.ia-ExitModal-close, button.close');
                        if (closeBtn) {
                            closeBtn.click();
                            return true;
                        }
                    }
                }
                return false;
            """)
            if dismissed:
                print_lg("[IndeedForm] Dismissed exit application modal via JS.")
                time.sleep(1)
                return True
        except Exception:
            pass
        return False

    def is_review_page_ready(self) -> bool:
        """Returns True if the final Review module is rendered and submit button is interactable."""
        cur_url = (getattr(self.driver, "current_url", "") or "").lower()
        if any(k in cur_url for k in ["contact-info", "resume-selection", "resume", "questions", "location"]):
            return False

        self.wait_for_spinner(timeout=5)
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        for s_sel in FINAL_SUBMIT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH, s_sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                pass

        try:
            has_btn = self.driver.execute_script("""
                const candidates = Array.from(document.querySelectorAll('button, a, div[role="button"], input[type="submit"]'));
                for (const el of candidates) {
                    const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                    if (txt.includes('submit your application') || txt.includes('submit application')) {
                        return true;
                    }
                }
                return false;
            """)
            if has_btn:
                return True
        except Exception:
            pass

        return False
