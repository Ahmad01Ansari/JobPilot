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
from modules.config_loader import get_personal, get_resume
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
        self.captcha_handler = captcha_handler or IndeedCaptchaHandler(browser)

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

        # Check final review module
        if "review" in cur_url:
            return "REVIEW"
        for s_sel in FINAL_SUBMIT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH, s_sel)
                if any(e.is_displayed() for e in elems):
                    return "REVIEW"
            except Exception:
                pass

        # Check URL path indicators
        if "contact-info" in cur_url:
            return "CONTACT_INFO"
        if "location" in cur_url or "address" in cur_url:
            return "LOCATION"
        if "resume-selection" in cur_url or "resume" in cur_url:
            return "RESUME"
        if "questions" in cur_url:
            return "QUESTIONS"

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
                            el.clear()
                            el.send_keys(value)
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
        phone = self.personal.get("phone_number", "+916388623967")

        self.fill_field_if_needed(CONTACT_FIRST_NAME, first_name)
        self.fill_field_if_needed(CONTACT_LAST_NAME, last_name)
        self.fill_field_if_needed(CONTACT_PHONE, phone)

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
                        if target_str.lower() == opt_text.lower() or target_str.lower() in opt_text.lower():
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

        # 2. Process Standalone Inputs (Text, Number, Textarea, Select)
        standalone_elems = []
        try:
            standalone_elems = self.driver.find_elements(
                By.XPATH,
                "//input[not(@type='hidden') and not(@type='submit') and not(@type='button') and not(@type='file')] | //textarea | //select"
            )
        except Exception:
            pass

        for elem in standalone_elems:
            try:
                if elem in handled_inputs or not elem.is_displayed():
                    continue

                # Skip standard name/phone/email inputs if they belong to contact info
                name_attr = (elem.get_attribute("name") or "").lower()
                id_attr = (elem.get_attribute("id") or "").lower()
                if any(k in name_attr or k in id_attr for k in ["first-name", "last-name", "phone", "email", "age", "recaptcha"]):
                    continue

                tag_name = elem.tag_name.lower()
                inp_type = (elem.get_attribute("type") or "text").lower()

                # Extract Question Label
                question_text = ""
                elem_id = elem.get_attribute("id")
                if elem_id:
                    try:
                        lbls = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{elem_id}']")
                        if lbls and lbls[0].text.strip():
                            question_text = lbls[0].text.strip().replace("\n", " ")
                    except Exception:
                        pass
                if not question_text:
                    try:
                        p_lbl = elem.find_element(By.XPATH, "ancestor::div[contains(@class, 'item') or @data-testid or contains(@class, 'Group')]//label")
                        if p_lbl and p_lbl.text.strip():
                            question_text = p_lbl.text.strip().replace("\n", " ")
                    except Exception:
                        pass
                if not question_text:
                    question_text = elem.get_attribute("aria-label") or elem.get_attribute("placeholder") or name_attr or "Question"

                # Dropdowns (<select>)
                if tag_name == "select":
                    sel_elem = Select(elem)
                    raw_options = [o.text.strip() for o in sel_elem.options if o.text.strip()]
                    clean_options = [o for o in raw_options if o.lower() not in ["select an option", "select...", "choose an option", "choose one", "select", "-- select --"]]
                    options_for_qna = clean_options if clean_options else raw_options

                    sel_obj: Answer = self.qna_engine.answer_question(
                        question=question_text,
                        options=options_for_qna,
                        field_type="select",
                        job_context={"title": job_title, "company": company_name}
                    )
                    raw_val = sel_obj.value if sel_obj else ""
                    best_opt = self.qna_engine._match_option(str(raw_val), options_for_qna) if raw_val else (options_for_qna[0] if options_for_qna else "")
                    if not best_opt and options_for_qna:
                        best_opt = options_for_qna[0]

                    selected_ok = False
                    if best_opt:
                        try:
                            sel_elem.select_by_visible_text(best_opt)
                            selected_ok = True
                        except Exception:
                            for idx, o in enumerate(sel_elem.options):
                                if o.text.strip().lower() == best_opt.lower() or best_opt.lower() in o.text.strip().lower():
                                    sel_elem.select_by_index(idx)
                                    selected_ok = True
                                    break
                    if not selected_ok and options_for_qna:
                        try:
                            sel_elem.select_by_visible_text(options_for_qna[0])
                        except Exception:
                            sel_elem.select_by_index(min(1, len(raw_options) - 1))

                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Select: '{best_opt}'")
                    answered.append({"question": question_text, "answer": str(best_opt)})
                    continue

                # Check if this input is a combobox, searchable select, or has an active listbox/dropdown attached
                is_combobox = False
                combobox_options = []
                try:
                    combobox_options = self.driver.execute_script("""
                        const el = arguments[0];
                        const role = el.getAttribute('role') || '';
                        const ariaAuto = el.getAttribute('aria-autocomplete') || '';
                        const ariaHasPopup = el.getAttribute('aria-haspopup') || '';
                        const cls = el.className || '';
                        const isComboInput = role === 'combobox' || ariaAuto === 'list' || ariaHasPopup === 'listbox' ||
                                            cls.includes('select') || cls.includes('combobox') || el.type === 'search';

                        const container = el.closest('[role="combobox"], [role="listbox"], .icl-Select, [class*="select" i], [class*="combobox" i], [class*="dropdown" i]') || document;
                        const optionEls = Array.from(container.querySelectorAll('[role="option"], li[role="option"], ul[role="listbox"] li, .icl-Select-option'));
                        if (optionEls.length > 0 || isComboInput) {
                            return optionEls.map(o => (o.innerText || o.textContent || '').trim()).filter(t => t.length > 0);
                        }
                        return [];
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
                    best_opt = self.qna_engine._match_option(str(raw_val), cb_options) if raw_val else (cb_options[0] if cb_options else "")
                    if not best_opt and cb_options:
                        best_opt = cb_options[0]

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
                        if (optionEls.length > 0) {
                            optionEls[0].click();
                            return true;
                        }
                        return false;
                    """, best_opt)

                    if not clicked_opt:
                        try:
                            from selenium.webdriver.common.keys import Keys
                            elem.send_keys(Keys.ENTER)
                        except Exception:
                            pass

                    print_lg(f"[IndeedForm] Q: '{question_text[:60]}' -> Combobox: '{best_opt}'")
                    answered.append({"question": question_text, "answer": str(best_opt)})
                    continue

                # Text / Number inputs and Textareas
                ans_obj: Answer = self.qna_engine.answer_question(
                    question=question_text,
                    options=[],
                    field_type="number" if inp_type == "number" else "text",
                    job_context={"title": job_title, "company": company_name}
                )
                ans_str = str(ans_obj.value if ans_obj else "").strip()

                if inp_type == "number":
                    num_match = re.search(r'\d+', ans_str)
                    ans_str = num_match.group(0) if num_match else "2"

                existing_val = (elem.get_attribute("value") or "").strip()
                if not existing_val or existing_val != ans_str:
                    elem.clear()
                    elem.send_keys(ans_str)
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('input', {bubbles: true})); arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                        elem, ans_str
                    )
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

        return answered

    def advance_to_next_step(self) -> bool:
        """Clicks the primary advance/continue button and waits for the step transition."""
        self.wait_for_spinner()
        cont_btn = None

        # 1. Search via declared XPath selectors
        for sel in FORM_CONTINUE_BUTTONS:
            try:
                for b in self.driver.find_elements(By.XPATH, sel):
                    try:
                        if b.is_displayed():
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
                        const txt = (el.innerText || el.textContent || el.value || '').trim().toLowerCase();
                        if (txt.includes('continue') || txt.includes('next') || txt.includes('review your application') ||
                            txt.includes('review application') || txt.includes('save and continue') || txt.includes('save & continue')) {
                            return el;
                        }
                    }
                    return null;
                """)
                if js_btn:
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

        return True

    def is_review_page_ready(self) -> bool:
        """Returns True if the final Review module is rendered and submit button is interactable."""
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
