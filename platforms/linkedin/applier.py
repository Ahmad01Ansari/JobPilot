"""LinkedIn Application Execution Engine.

Handles Easy Apply wizard steps, screening questions, and direct event emission.
"""

import time
from typing import Optional, Any, Dict, Tuple
from urllib.parse import urlparse, parse_qs, unquote
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from modules.tracker import ApplicationTracker
from modules.qna_engine import QnAEngine
from modules.helpers import print_lg
from platforms.linkedin.selectors import (
    EASY_APPLY_BUTTON_XPATHS,
    EASY_APPLY_MODAL_CLASS,
    EASY_APPLY_MODAL_SELECTORS,
    EASY_APPLY_MODAL_XPATHS,
    MODAL_NEXT_BUTTON_XPATH,
    MODAL_REVIEW_BUTTON_XPATH,
    MODAL_SUBMIT_BUTTON_XPATH,
    MODAL_DISMISS_BUTTON_XPATH,
    CONFIRM_DISCARD_BUTTON_XPATH,
)
from modules.human_behavior import human_delay, human_type, human_click, human_review_dwell
from modules.captcha_detector import CaptchaDetector


class LinkedInApplier:
    """Manages the application lifecycle and Easy Apply form automation for LinkedIn."""

    def __init__(
        self,
        browser: Any,
        tracker: Optional[ApplicationTracker] = None,
        automation_bridge: Optional[Any] = None,
        qna_engine: Optional[QnAEngine] = None,
        user_id: int = 1,
    ):
        self.browser = browser
        self.tracker = tracker or ApplicationTracker(user_id=user_id)
        self.automation_bridge = automation_bridge
        self.qna_engine = qna_engine or QnAEngine()
        self.user_id = user_id
        self.captcha_detector = CaptchaDetector(platform="linkedin", automation_bridge=automation_bridge)

    def _find_modal(self, driver) -> Optional[Any]:
        """Locates the active Easy Apply modal across legacy and Genesis SDUI DOM structures."""
        for xpath in EASY_APPLY_MODAL_XPATHS:
            try:
                modals = driver.find_elements(By.XPATH, xpath)
                for m in modals:
                    if m.is_displayed():
                        return m
            except Exception:
                continue
        for css in EASY_APPLY_MODAL_SELECTORS:
            try:
                modals = driver.find_elements(By.CSS_SELECTOR, css)
                for m in modals:
                    if m.is_displayed():
                        return m
            except Exception:
                continue
        return None

    def discard_modal(self) -> None:
        """Closes any open Easy Apply modal and confirms discard."""
        driver = self.browser.driver
        if not driver:
            return
        try:
            # 1. If confirmation modal ("Save this application?") is already visible, click Discard immediately
            driver.execute_script("""
                const buttons = Array.from(document.querySelectorAll('button'));
                const discardBtn = buttons.find(b => {
                    const txt = (b.textContent || '').trim().toLowerCase();
                    const cname = (b.getAttribute('data-control-name') || '').toLowerCase();
                    const testId = (b.getAttribute('data-test-dialog-secondary-action') || '').toLowerCase();
                    return (txt === 'discard' || txt.includes('discard') || cname.includes('discard') || testId.includes('discard'));
                });
                if (discardBtn) discardBtn.click();
            """)
            time.sleep(0.4)

            # Direct Selenium click on Discard button if present
            try:
                d_btns = driver.find_elements(By.XPATH, "//button[normalize-space(.)='Discard' or contains(., 'Discard') or contains(@data-control-name, 'discard')]")
                for d in d_btns:
                    if d.is_displayed():
                        driver.execute_script("arguments[0].click();", d)
                        time.sleep(0.5)
                        break
            except Exception:
                pass

            # 2. Click dismiss [X] if Easy Apply modal is open
            dismiss_buttons = driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Dismiss') or contains(@aria-label, 'Close') or normalize-space(.)='✕' or contains(@class, 'artdeco-modal__dismiss')]"
            )
            for btn in dismiss_buttons:
                if btn.is_displayed():
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    time.sleep(0.8)
                    break

            # 3. Check and click "Discard" button on secondary confirmation dialog ("Save this application?")
            for _ in range(3):
                discarded = driver.execute_script("""
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const discardBtn = buttons.find(b => {
                        const txt = (b.textContent || '').trim().toLowerCase();
                        const cname = (b.getAttribute('data-control-name') || '').toLowerCase();
                        const testId = (b.getAttribute('data-test-dialog-secondary-action') || '').toLowerCase();
                        return (txt === 'discard' || txt.includes('discard') || cname.includes('discard') || testId.includes('discard'));
                    });
                    if (discardBtn) {
                        discardBtn.click();
                        return true;
                    }
                    return false;
                """)
                if discarded:
                    time.sleep(0.4)
                    break
                try:
                    d_btns = driver.find_elements(By.XPATH, "//button[normalize-space(.)='Discard' or contains(., 'Discard') or contains(@data-control-name, 'discard')]")
                    for d in d_btns:
                        if d.is_displayed():
                            driver.execute_script("arguments[0].click();", d)
                            time.sleep(0.4)
                            discarded = True
                            break
                except Exception:
                    pass
                if discarded:
                    break
                time.sleep(0.4)

            # 4. Fallback ESC key
            try:
                self.browser.actions.send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass
        except Exception as e:
            logger.debug("Notice in discard_modal: %s", e)

    def _answer_radio_groups(self, driver, modal, job_description: str = "", work_location: str = "") -> None:
        """Discovers and answers all radio button groups on the current modal step."""
        try:
            all_radios = modal.find_elements(By.XPATH, ".//input[@type='radio']")
            if not all_radios:
                return

            radio_groups = {}
            for r in all_radios:
                try:
                    name = r.get_attribute("name")
                    if not name:
                        try:
                            parent_el = r.find_element(By.XPATH, "./ancestor::div[.//input[@type='radio']][last()]")
                            name = str(id(parent_el))
                        except Exception:
                            name = "unnamed_group"
                    radio_groups.setdefault(name, []).append(r)
                except Exception:
                    continue

            for group_name, r_list in radio_groups.items():
                try:
                    is_selected = any(r.is_selected() or (r.get_attribute("checked") in ["true", "checked", "True"]) for r in r_list)
                    if is_selected:
                        continue

                    # Extract question prompt
                    question_title = ""
                    ancestor = None
                    for anc_xpath in [
                        "./ancestor::fieldset[1]",
                        "./ancestor::div[@role='radiogroup'][1]",
                        "./ancestor::div[contains(@class, 'form-element') or contains(@class, 'group') or contains(@class, 'field')][1]",
                        "./ancestor::div[.//p or .//h3 or .//legend or .//label][1]",
                        "./ancestor::div[2]",
                        "./ancestor::div[3]",
                    ]:
                        try:
                            cand = r_list[0].find_element(By.XPATH, anc_xpath)
                            if cand and (cand.find_elements(By.XPATH, ".//p | .//legend | .//h3 | .//span[contains(@class, 'title')]")):
                                ancestor = cand
                                break
                        except Exception:
                            continue

                    if ancestor:
                        for p_xpath in [".//legend", ".//span[contains(@class, 'title')]", ".//p", ".//h3", ".//label"]:
                            try:
                                titles = ancestor.find_elements(By.XPATH, p_xpath)
                                for t in titles:
                                    if t.is_displayed() and t.text.strip():
                                        question_title = t.text.strip()
                                        break
                                if question_title:
                                    break
                            except Exception:
                                continue

                    if not question_title:
                        try:
                            question_title = r_list[0].get_attribute("aria-label") or ""
                        except Exception:
                            pass
                    if not question_title:
                        question_title = "Radio Question"

                    # Extract options
                    options_info = []
                    for r_el in r_list:
                        r_id = r_el.get_attribute("id")
                        opt_lbl_el = None
                        opt_text = ""
                        if r_id:
                            try:
                                lbls = modal.find_elements(By.XPATH, f".//label[@for='{r_id}']")
                                if lbls and lbls[0].text.strip():
                                    opt_text = lbls[0].text.strip()
                                    opt_lbl_el = lbls[0]
                            except Exception:
                                pass
                        if not opt_text:
                            for lbl_xpath in ["./following-sibling::label", "./parent::label", "./ancestor::label[1]", "./following-sibling::*[1]", "./.."]:
                                try:
                                    cand_lbl = r_el.find_element(By.XPATH, lbl_xpath)
                                    if cand_lbl and cand_lbl.text.strip():
                                        opt_text = cand_lbl.text.strip()
                                        opt_lbl_el = cand_lbl
                                        break
                                except Exception:
                                    continue
                        if not opt_text:
                            opt_text = r_el.get_attribute("aria-label") or r_el.get_attribute("value") or "Option"
                        options_info.append((opt_text, r_el, opt_lbl_el))

                    # Determine answer
                    q_lower = question_title.lower()
                    clean_opt_names = [o[0] for o in options_info]
                    answer = "Yes"

                    if any(w in q_lower for w in ["hybrid", "remote", "on-site", "onsite", "commute", "relocat", "travel"]):
                        answer = "Yes"
                    elif any(w in q_lower for w in [
                        "sponsorship", "require sponsorship", "future sponsorship", "employer sponsorship",
                        "require visa", "need visa", "visa sponsorship", "h-1b", "h1b"
                    ]) and not any(w in q_lower for w in ["without", "no sponsorship", "not require"]):
                        answer = "No"
                    elif any(w in q_lower for w in [
                        "ever been employed", "currently employed", "previously employed", "ever worked for",
                        "former employee", "prior employee", "worked at", "subsidiaries before", "affiliates before",
                        "relative", "family member", "conflict of interest", "non-compete", "disciplin", "terminated",
                        "felony", "misdemeanor", "crime", "convicted", "lawsuit", "referred by", "referral by"
                    ]):
                        answer = "No"
                    elif any(w in q_lower for w in ["authorized", "eligib", "legal"]):
                        answer = "Yes"
                    elif any(w in q_lower for w in ["background check", "drug"]):
                        answer = "Yes"
                    elif any(w in q_lower for w in ["comfortable", "willing", "able to", "agree", "accept"]):
                        answer = "Yes"
                    else:
                        if self.qna_engine:
                            clean_opts_only = [lbl.split('"<')[0].strip('"') for lbl in clean_opt_names]
                            q_target, ai_choice = self.qna_engine.answer_select_or_radio(question_title, clean_opts_only, work_location)
                            if q_target:
                                answer = q_target
                            elif ai_choice:
                                answer = ai_choice

                    target_choice = None
                    ans_lower = answer.lower()
                    for opt_text, r_el, lbl_el in options_info:
                        if opt_text.lower().strip() == ans_lower:
                            target_choice = (opt_text, r_el, lbl_el)
                            break
                    if not target_choice:
                        for opt_text, r_el, lbl_el in options_info:
                            if ans_lower in opt_text.lower() or opt_text.lower() in ans_lower:
                                target_choice = (opt_text, r_el, lbl_el)
                                break
                    if not target_choice and options_info:
                        target_choice = options_info[0]

                    if target_choice:
                        chosen_text, chosen_r, chosen_lbl = target_choice
                        if chosen_lbl:
                            try:
                                human_click(driver, chosen_lbl, smooth_scroll=True)
                            except Exception:
                                pass
                        try:
                            driver.execute_script("""
                                const r = arguments[0];
                                const lbl = arguments[1];
                                r.scrollIntoView({ block: 'center', behavior: 'instant' });
                                if (lbl) {
                                    try { lbl.click(); } catch(e) {}
                                }
                                try { r.click(); } catch(e) {}
                                if (!r.checked) {
                                    r.checked = true;
                                }
                                r.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                                r.dispatchEvent(new Event('input', { bubbles: true }));
                                r.dispatchEvent(new Event('change', { bubbles: true }));
                            """, chosen_r, chosen_lbl)
                        except Exception:
                            pass
                        print_lg(f"[LinkedInApplier] Selected radio '{chosen_text}' for '{question_title}'")
                except Exception as e:
                    print_lg(f"[LinkedInApplier] Notice handling radio group: {e}")
        except Exception as e:
            print_lg(f"[LinkedInApplier] Notice discovering radio groups: {e}")

    def _answer_custom_dropdowns(self, driver, modal, job_description: str = "", work_location: str = "") -> None:
        """Discovers and answers custom comboboxes, Artdeco dropdowns, and select buttons."""
        placeholder_values = {
            "", "select an option", "choose an option", "select option",
            "choose option", "select one", "choose one", "select...", "choose...",
            "please select", "-- select --", "-- choose --", "none selected"
        }
        try:
            combobox_xpaths = [
                ".//div[@role='combobox']",
                ".//input[@role='combobox']",
                ".//button[@aria-haspopup='listbox']",
                ".//button[@aria-haspopup='true']",
                ".//button[contains(@class, 'artdeco-dropdown__trigger')]",
                ".//button[contains(@data-test-select-trigger, '')]",
                ".//div[contains(@class, 'fb-dropdown')]//button",
                ".//div[contains(@class, 'artdeco-dropdown')]//button",
            ]
            comboboxes = modal.find_elements(By.XPATH, " | ".join(combobox_xpaths))
            for cb in comboboxes:
                if not cb.is_displayed():
                    continue
                try:
                    cb_label = (cb.get_attribute("aria-label") or "").strip()
                    if not cb_label:
                        try:
                            lbl = cb.find_element(By.XPATH, "./ancestor::div[.//label or .//p][1]//(label|p)[1]")
                            cb_label = lbl.text.strip()
                        except Exception:
                            pass
                    if not cb_label:
                        cb_label = "Dropdown Question"

                    curr_val = (cb.get_attribute("value") or cb.text or "").strip()
                    if curr_val and curr_val.lower() not in placeholder_values:
                        continue

                    # Open dropdown
                    try:
                        cb.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", cb)
                    human_delay(0.3, 0.6, action="click")

                    options_xpath = (
                        "//div[@role='listbox']//*[@role='option'] | "
                        "//ul[@role='listbox']//li | "
                        "//div[contains(@class, 'artdeco-dropdown__content')]//li | "
                        "//div[contains(@class, 'artdeco-dropdown__content')]//span | "
                        "//div[contains(@class, 'fb-dropdown')]//li | "
                        "//div[contains(@class, 'basic-typeahead')]//li | "
                        "//ul[contains(@class, 'typeahead')]//li"
                    )
                    options = driver.find_elements(By.XPATH, options_xpath)
                    visible_opts = []
                    opt_texts = []
                    for opt in options:
                        try:
                            if opt.is_displayed():
                                t = opt.text.strip()
                                if t:
                                    visible_opts.append(opt)
                                    opt_texts.append(t)
                        except Exception:
                            continue

                    matched_opt = None
                    is_currency = any(w in cb_label.lower() for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"])
                    has_currency = any(any(c in t.lower() for c in ["inr", "usd", "rupee", "dollar", "₹", "$"]) for t in opt_texts)

                    if is_currency or has_currency:
                        pref_curr = "inr"
                        if self.qna_engine and hasattr(self.qna_engine, "salary_currency"):
                            pref_curr = str(self.qna_engine.salary_currency).lower()
                        for opt in visible_opts:
                            try:
                                t = opt.text.lower()
                                if any(c in t for c in [pref_curr, "inr", "rupee", "₹", "indian"]):
                                    matched_opt = opt
                                    break
                            except Exception:
                                continue
                        if not matched_opt:
                            for opt in visible_opts:
                                try:
                                    t = opt.text.lower()
                                    if any(c in t for c in ["usd", "$", "dollar"]):
                                        matched_opt = opt
                                        break
                                except Exception:
                                    continue
                    elif self.qna_engine and opt_texts:
                        _, matched_text = self.qna_engine.answer_select_or_radio(cb_label, opt_texts, work_location=work_location)
                        if matched_text:
                            for opt in visible_opts:
                                try:
                                    if opt.text.strip().lower() == matched_text.strip().lower():
                                        matched_opt = opt
                                        break
                                except Exception:
                                    continue

                    if not matched_opt and visible_opts:
                        # Fallback to first non-placeholder option
                        for opt in visible_opts:
                            try:
                                if opt.text.strip().lower() not in placeholder_values:
                                    matched_opt = opt
                                    break
                            except Exception:
                                continue

                    if matched_opt:
                        opt_label_str = ""
                        try:
                            opt_label_str = matched_opt.text.strip()
                        except Exception:
                            pass
                        try:
                            matched_opt.click()
                        except Exception:
                            try:
                                driver.execute_script("arguments[0].click();", matched_opt)
                            except Exception:
                                pass
                        if opt_label_str:
                            print_lg(f"[LinkedInApplier] Selected custom dropdown option '{opt_label_str}' for '{cb_label[:60]}'")
                except Exception as e:
                    print_lg(f"[LinkedInApplier] Notice handling custom dropdown item: {e}")
        except Exception as e:
            print_lg(f"[LinkedInApplier] Notice discovering custom dropdowns: {e}")

    def _answer_step_questions(self, driver, modal, job_description: str = "", work_location: str = "") -> None:
        """Fills interactive form inputs, selects, and radios on the current modal step."""
        placeholder_values = {
            "", "select an option", "choose an option", "select option",
            "choose option", "select one", "choose one", "select...", "choose...",
            "please select", "-- select --", "-- choose --", "none selected"
        }
        try:
            # 1. Fill radio button groups
            self._answer_radio_groups(driver, modal, job_description=job_description, work_location=work_location)

            # 2. Fill native dropdown selects (inspects both visible and custom-layered select elements)
            select_elements = modal.find_elements(By.TAG_NAME, "select")
            for sel_el in select_elements:
                try:
                    # Determine label / prompt for this select
                    prompt = (sel_el.get_attribute("aria-label") or "").strip()
                    if not prompt:
                        sel_id = sel_el.get_attribute("id")
                        if sel_id:
                            try:
                                lbl = modal.find_element(By.XPATH, f".//label[@for='{sel_id}']")
                                prompt = lbl.text.strip()
                            except Exception:
                                pass
                    if not prompt:
                        try:
                            parent_lbl = sel_el.find_element(By.XPATH, "./ancestor::div[.//label or .//p][1]//(label|p)[1]")
                            prompt = parent_lbl.text.strip()
                        except Exception:
                            pass
                    if not prompt:
                        prompt = "Select Option"

                    # Check current selected text
                    selected_text = driver.execute_script(
                        "return arguments[0].options[arguments[0].selectedIndex] ? arguments[0].options[arguments[0].selectedIndex].text : '';",
                        sel_el
                    ) or ""
                    curr_val = (sel_el.get_attribute("value") or "").strip()
                    if selected_text.strip().lower() not in placeholder_values and curr_val.lower() not in placeholder_values:
                        continue

                    # Extract all options
                    options_raw = driver.execute_script("""
                        const opts = [];
                        for (let i = 0; i < arguments[0].options.length; i++) {
                            const o = arguments[0].options[i];
                            opts.push({ index: i, value: o.value, text: o.text.trim() });
                        }
                        return opts;
                    """, sel_el) or []

                    valid_opts = [o for o in options_raw if o["text"].lower() not in placeholder_values and o["text"]]
                    if not valid_opts:
                        continue

                    target_choice = None
                    opt_texts = [o["text"] for o in valid_opts]
                    is_currency_q = any(w in prompt.lower() for w in ["currency", "pay unit", "salary unit", "pay currency", "salary currency"])
                    has_currency_opts = any(any(c in t.lower() for c in ["inr", "usd", "rupee", "dollar", "₹", "$"]) for t in opt_texts)

                    if is_currency_q or has_currency_opts:
                        pref_curr = "inr"
                        if self.qna_engine and hasattr(self.qna_engine, "salary_currency"):
                            pref_curr = str(self.qna_engine.salary_currency).lower()
                        for o in valid_opts:
                            ot = o["text"].lower()
                            if any(c in ot for c in [pref_curr, "inr", "rupee", "₹", "indian"]):
                                target_choice = o
                                break
                        if not target_choice:
                            for o in valid_opts:
                                ot = o["text"].lower()
                                if any(c in ot for c in ["usd", "$", "dollar"]):
                                    target_choice = o
                                    break
                    elif self.qna_engine:
                        _, matched = self.qna_engine.answer_select_or_radio(prompt, opt_texts, work_location=work_location)
                        if matched:
                            for o in valid_opts:
                                if o["text"].strip().lower() == matched.strip().lower():
                                    target_choice = o
                                    break

                    if not target_choice:
                        target_choice = valid_opts[0]

                    target_idx = target_choice["index"]
                    target_val = target_choice["value"]

                    # Attempt native Selenium select if interactable
                    if sel_el.is_displayed():
                        try:
                            from selenium.webdriver.support.ui import Select
                            Select(sel_el).select_by_index(target_idx)
                        except Exception:
                            pass

                    # Execute JavaScript to ensure selectedIndex, value, and DOM synthetic events are dispatched
                    driver.execute_script("""
                        const sel = arguments[0];
                        const idx = arguments[1];
                        const val = arguments[2];
                        sel.selectedIndex = idx;
                        if (val) sel.value = val;
                        sel.dispatchEvent(new Event('focus', { bubbles: true }));
                        sel.dispatchEvent(new Event('input', { bubbles: true }));
                        sel.dispatchEvent(new Event('change', { bubbles: true }));
                        sel.dispatchEvent(new Event('blur', { bubbles: true }));
                    """, sel_el, target_idx, target_val)

                    print_lg(f"[LinkedInApplier] Selected dropdown option '{target_choice['text']}' for question '{prompt[:60]}'")
                except Exception as e:
                    print_lg(f"[LinkedInApplier] Notice handling select element: {e}")

            # 3. Fill custom comboboxes / typeahead dropdowns
            self._answer_custom_dropdowns(driver, modal, job_description=job_description, work_location=work_location)

            # 4. Fill text / number inputs
            text_inputs = modal.find_elements(
                By.XPATH,
                ".//input[not(@type) or @type='text' or @type='number' or @type='tel' or @type='email'] | .//textarea"
            )
            for inp in text_inputs:
                if not inp.is_displayed():
                    continue
                curr_val = inp.get_attribute("value") or ""
                if curr_val.strip():
                    continue
                # Determine prompt
                prompt = (inp.get_attribute("aria-label") or "").strip()
                if not prompt:
                    try:
                        prompt = driver.execute_script("""
                            const inp = arguments[0];
                            const id = inp.id;
                            if (id) {
                                try {
                                    const lbl = document.querySelector(`label[for="${CSS.escape(id)}"]`);
                                    if (lbl && lbl.textContent && lbl.textContent.trim()) return lbl.textContent.trim();
                                } catch (e) {}
                            }
                            const parent = inp.closest('.fb-dash-form-element, .jobs-easy-apply-form-section__grouping, div[class*="form-element"], fieldset');
                            if (parent) {
                                const lbl = parent.querySelector('label, p, span[class*="label"], legend');
                                if (lbl && lbl.textContent && lbl.textContent.trim()) return lbl.textContent.trim();
                            }
                            return '';
                        """, inp) or ""
                    except Exception:
                        pass
                if not prompt:
                    try:
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            lbl = modal.find_element(By.XPATH, f".//label[@for='{inp_id}']")
                            prompt = lbl.text.strip()
                    except Exception:
                        pass
                if not prompt:
                    try:
                        p_el = inp.find_element(By.XPATH, "./ancestor::div[p or label or span][1]//(label|p|span)[1]")
                        prompt = p_el.text.strip()
                    except Exception:
                        pass

                cand_exp = "1"
                if self.qna_engine and hasattr(self.qna_engine, "prof"):
                    cand_exp = str(int(round(float(self.qna_engine.prof.get("years_of_experience", 1)))))
                answer = cand_exp
                if prompt and self.qna_engine:
                    ans = self.qna_engine.answer_text_question(prompt, job_description=job_description, work_location=work_location)
                    if ans:
                        answer = ans

                # Defensive sanitization for numeric inputs and specific domains
                inp_type = (inp.get_attribute("type") or "text").lower()
                p_lower = prompt.lower()
                is_num_field = inp_type in ["number", "tel"] or any(u in p_lower for u in ["(in days)", "in days", "number of days", "years", "in lpa", "how many"])
                if is_num_field:
                    if answer.lower() in ["yes", "no", "true", "false"] or not any(c.isdigit() for c in answer):
                        if any(w in p_lower for w in ["join", "notice", "start", "day"]):
                            n_days = 30
                            if self.qna_engine and hasattr(self.qna_engine, "notice_period"):
                                n_days = getattr(self.qna_engine, "notice_period", 30)
                            answer = str(n_days)
                        elif any(w in p_lower for w in ["salary", "ctc", "lpa", "pay"]):
                            if "lpa" in p_lower or "lac" in p_lower:
                                d_sal = 550000
                                if self.qna_engine and hasattr(self.qna_engine, "desired_salary"):
                                    d_sal = getattr(self.qna_engine, "desired_salary", 550000)
                                answer = f"{round(d_sal / 100000, 2):.2f}"
                            else:
                                answer = "550000"
                        else:
                            answer = cand_exp

                # Check maxlength constraint (e.g. 0/20 in LinkedIn Easy Apply form elements)
                max_len_attr = inp.get_attribute("maxlength")
                if max_len_attr:
                    try:
                        m_len = int(max_len_attr)
                        if m_len > 0 and len(answer) > m_len:
                            if any(w in p_lower for w in ["exp", "role", "developer", "experience", "year"]):
                                answer = "2 years" if m_len >= 7 else "2"
                            elif any(w in p_lower for w in ["salary", "ctc", "lpa"]):
                                answer = "550000" if m_len >= 6 else "5.5"
                            elif any(w in p_lower for w in ["notice", "join", "day"]):
                                answer = "15" if m_len >= 2 else "1"
                            else:
                                answer = answer[:m_len]
                    except Exception:
                        pass

                try:
                    inp.clear()
                    inp.send_keys(answer)
                except Exception:
                    pass
                try:
                    # Enforce exact clean value via React descriptor setter to prevent concatenation
                    driver.execute_script("""
                        const inp = arguments[0];
                        const val = arguments[1];
                        inp.focus();
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
                            || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                        if (nativeSetter) {
                            nativeSetter.call(inp, val);
                        } else {
                            inp.value = val;
                        }
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    """, inp, answer)
                except Exception:
                    pass

            # 5. Final Safety Fallback: ensure no visible radio group is left unselected
            try:
                unselected_radios = modal.find_elements(By.XPATH, ".//input[@type='radio']")
                groups = {}
                for r in unselected_radios:
                    gname = r.get_attribute("name") or "default"
                    groups.setdefault(gname, []).append(r)
                for gname, r_items in groups.items():
                    if not any(r.is_selected() for r in r_items):
                        first_r = r_items[0]
                        driver.execute_script("""
                            const r = arguments[0];
                            r.scrollIntoView({ block: 'center', behavior: 'instant' });
                            r.checked = true;
                            r.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
                            r.dispatchEvent(new Event('input', { bubbles: true }));
                            r.dispatchEvent(new Event('change', { bubbles: true }));
                        """, first_r)
                        print_lg(f"[LinkedInApplier] Safety fallback selected first option for radio group '{gname}'")
            except Exception:
                pass

            # 6. Checkbox handling (Consent, acknowledgements, terms, declarations)
            try:
                checkboxes = modal.find_elements(
                    By.XPATH,
                    ".//input[@type='checkbox'] | .//div[@role='checkbox']"
                )
                for cb in checkboxes:
                    try:
                        if not cb.is_displayed():
                            continue
                        is_checked = (
                            cb.is_selected()
                            or cb.get_attribute("aria-checked") == "true"
                            or cb.get_attribute("checked") in ["true", "checked", "True"]
                        )
                        if is_checked:
                            continue

                        # Extract label or prompt text
                        cb_text = ""
                        cb_id = cb.get_attribute("id")
                        if cb_id:
                            try:
                                lbl = modal.find_element(By.XPATH, f".//label[@for='{cb_id}']")
                                cb_text = lbl.text.strip()
                            except Exception:
                                pass
                        if not cb_text:
                            try:
                                parent_lbl = cb.find_element(By.XPATH, "./ancestor::label[1]")
                                cb_text = parent_lbl.text.strip()
                            except Exception:
                                pass
                        if not cb_text:
                            cb_text = cb.get_attribute("aria-label") or ""

                        cb_lower = cb_text.lower()
                        is_required = (
                            cb.get_attribute("required") is not None
                            or cb.get_attribute("aria-required") == "true"
                            or "*" in cb_text
                        )
                        # Consent, terms, certifications, privacy, background check, authorizations
                        should_check = is_required or any(w in cb_lower for w in [
                            "agree", "consent", "acknowledge", "certify", "terms", "condition",
                            "privacy", "policy", "confirm", "understand", "truth", "accurate",
                            "background check", "authorized", "authorization", "declare", "declaration"
                        ])

                        # Explicit negative opt-ins should not be checked
                        if any(w in cb_lower for w in ["decline", "do not agree", "opt out", "disagree", "not wish"]):
                            should_check = False

                        if should_check:
                            try:
                                cb.click()
                            except Exception:
                                driver.execute_script("arguments[0].click();", cb)
                            print_lg(f"[LinkedInApplier] Checked required/consent checkbox: '{cb_text[:60]}'")
                    except Exception as e:
                        print_lg(f"[LinkedInApplier] Notice checking individual checkbox: {e}")
            except Exception as e:
                print_lg(f"[LinkedInApplier] Notice discovering checkboxes: {e}")
        except Exception:
            pass

    def _fill_pending_fields(self, driver, modal, user_input: str) -> None:
        """Populates any empty or invalid text inputs on the current modal with the candidate-provided answer."""
        try:
            inputs = modal.find_elements(
                By.XPATH,
                ".//input[not(@type) or @type='text' or @type='number' or @type='tel' or @type='email'] | .//textarea"
            )
            for inp in inputs:
                if not inp.is_displayed():
                    continue
                curr = inp.get_attribute("value") or ""
                if not curr.strip():
                    driver.execute_script("""
                        const inp = arguments[0];
                        const val = arguments[1];
                        inp.focus();
                        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set
                            || Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                        if (nativeSetter) {
                            nativeSetter.call(inp, val);
                        } else {
                            inp.value = val;
                        }
                        inp.dispatchEvent(new Event('input', { bubbles: true }));
                        inp.dispatchEvent(new Event('change', { bubbles: true }));
                        inp.dispatchEvent(new Event('blur', { bubbles: true }));
                    """, inp, user_input)
                    print_lg(f"[LinkedInApplier] Populated candidate answer '{user_input}' into form field.")
        except Exception as e:
            logger.debug("Notice filling pending fields: %s", e)

    def _try_advance_step(self, driver, modal) -> bool:
        """Attempts to click Review, Next, or Submit to advance after human input."""
        for xpath in [MODAL_SUBMIT_BUTTON_XPATH, MODAL_REVIEW_BUTTON_XPATH, MODAL_NEXT_BUTTON_XPATH]:
            try:
                btns = modal.find_elements(By.XPATH, xpath)
                for b in btns:
                    if b.is_displayed():
                        try:
                            b.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", b)
                        time.sleep(1.0)
                        return True
            except Exception:
                continue
        return False

    def apply_to_job(
        self,
        job_id: str,
        title: str,
        company: str,
        location: str,
        source_url: str,
        description: str = "",
    ) -> Dict[str, Any]:
        """Executes application for the currently active job listing."""
        driver = self.browser.driver
        if not driver:
            raise RuntimeError("Browser not initialized.")

        # Check deduplication / SSOT
        should_skip, reason = self.tracker.is_already_handled(job_id, platform="linkedin", user_id=self.user_id)
        if should_skip:
            print_lg(f"[LinkedInApplier] Skipping job {job_id} ({title}): {reason}")
            return {"status": "SKIPPED", "reason": reason}

        # Emit initial discovery event
        if self.automation_bridge:
            try:
                from app.services.automation_events import JobDiscoveredEvent
                self.automation_bridge.handle_job_discovered(
                    JobDiscoveredEvent(
                        run_id="linkedin_modular_run",
                        platform="linkedin",
                        external_job_id=str(job_id),
                        title=title,
                        company=company,
                        location=location,
                        url=source_url,
                        application_method="EASY_APPLY",
                        description=description,
                    )
                )
            except Exception as e:
                print_lg(f"[LinkedInApplier] Notice emitting JobDiscoveredEvent: {e}")

        # Check for Apply button
        apply_btn = None
        for xp in EASY_APPLY_BUTTON_XPATHS:
            try:
                elems = driver.find_elements(By.XPATH, xp)
                for el in elems:
                    if el.is_displayed():
                        apply_btn = el
                        break
                if apply_btn:
                    break
            except Exception:
                pass

        if not apply_btn:
            print_lg(f"[LinkedInApplier] No apply button found for job {job_id}. Marking as SKIPPED.")
            self.tracker.record_state(
                {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                state="SKIPPED",
                skip_reason="No apply button available",
                user_id=self.user_id,
            )
            return {"status": "SKIPPED", "reason": "No apply button"}

        # Track window handles before clicking to detect external apply tabs
        handles_before = list(driver.window_handles)
        current_handle = driver.current_window_handle

        human_click(driver, apply_btn, smooth_scroll=True, dwell_before=True)
        human_delay(1.5, 2.5, action="click")
        handles_after = list(driver.window_handles)

        # Case 1: External apply opened in a new tab
        if len(handles_after) > len(handles_before):
            new_tab = [h for h in handles_after if h not in handles_before][-1]
            driver.switch_to.window(new_tab)
            # Allow brief redirect wait for destination company website
            t_wait = time.time()
            ext_url = ""
            while time.time() - t_wait < 3.0:
                curr = getattr(driver, "current_url", "") or ""
                if curr and curr.startswith("http") and "about:blank" not in curr:
                    try:
                        qs = parse_qs(urlparse(curr).query)
                        for qk in ["url", "target", "redirect", "destination"]:
                            if qk in qs and qs[qk]:
                                cand = unquote(qs[qk][0]).strip()
                                if cand.startswith("http") and "linkedin.com" not in cand.lower():
                                    ext_url = cand
                                    break
                    except Exception:
                        pass
                    if ext_url:
                        break
                    if "linkedin.com" not in curr.lower():
                        ext_url = curr
                        break
                time.sleep(0.3)

            if not ext_url:
                curr = getattr(driver, "current_url", "") or ""
                if curr.startswith("http") and "linkedin.com" not in curr.lower():
                    ext_url = curr

            driver.close()
            driver.switch_to.window(current_handle)

            print_lg(f"[LinkedInApplier] External apply detected ({ext_url or 'no URL'}).")
            self.tracker.record_state(
                {
                    "platform": "linkedin",
                    "job_id": job_id,
                    "title": title,
                    "company": company,
                    "location": location,
                    "source_url": source_url,
                    "apply_type": "EXTERNAL",
                    "application_url": ext_url or None,
                },
                state="EXTERNAL",
                reason=f"External application portal: {ext_url or 'N/A'}",
                user_id=self.user_id,
            )
            if self.automation_bridge:
                try:
                    from app.services.automation_events import JobDiscoveredEvent
                    self.automation_bridge.handle_job_discovered(
                        JobDiscoveredEvent(
                            run_id="linkedin_modular_run",
                            platform="linkedin",
                            external_job_id=str(job_id),
                            title=title,
                            company=company,
                            location=location,
                            url=source_url,
                            application_method="COMPANY_PORTAL",
                            application_url=ext_url,
                            description=description,
                        )
                    )
                except Exception:
                    pass
            return {"status": "EXTERNAL", "application_url": ext_url}

        # Case 2: In-page Easy Apply modal
        modal = self._find_modal(driver)

        if not modal:
            print_lg(f"[LinkedInApplier] Easy Apply modal did not open for job {job_id}.")
            return {"status": "FAILED", "reason": "Modal did not open"}

        self.tracker.record_state(
            {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
            state="APPLYING",
            user_id=self.user_id,
        )

        # Wizard stepper loop
        step_counter = 0
        max_steps = 12
        while step_counter < max_steps:
            step_counter += 1
            human_delay(0.8, 1.6, action="click")

            # Always re-acquire the live modal to prevent StaleElementReferenceException across wizard steps
            live_modal = self._find_modal(driver)
            if live_modal:
                modal = live_modal

            # Check if security challenge was triggered mid-wizard
            if self.captcha_detector.is_captcha_present(driver, platform="linkedin")[0] and not self.captcha_detector.is_captcha_solved(driver, platform="linkedin"):
                print_lg(f"[LinkedInApplier] Security challenge detected during Easy Apply wizard for '{title}'!")
                solved = self.captcha_detector.handle_captcha(
                    driver,
                    platform="linkedin",
                    job_title=title,
                    company=company,
                    timeout=60,
                    automation_bridge=self.automation_bridge,
                )
                if not solved:
                    self.discard_modal()
                    self.tracker.record_state(
                        {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                        state="MANUAL_REQUIRED",
                        failure_reason="Security challenge / CAPTCHA unresolved",
                        user_id=self.user_id,
                    )
                    return {"status": "MANUAL_REQUIRED", "reason": "CAPTCHA"}

            # Answer any input or screening questions on the current step
            self._answer_step_questions(driver, modal, job_description=description, work_location=location)

            # Check for Submit button
            submit_buttons = driver.find_elements(By.XPATH, MODAL_SUBMIT_BUTTON_XPATH)
            for s_btn in submit_buttons:
                if s_btn.is_displayed():
                    # Human review dwell time & subtle micro-scroll before final submission
                    human_review_dwell(driver, min_s=1.2, max_s=2.8)

                    try:
                        human_click(driver, s_btn, smooth_scroll=True, dwell_before=True)
                    except Exception:
                        driver.execute_script("arguments[0].click();", s_btn)
                    human_delay(1.5, 2.5, action="click")

                    # Check if post-submit CAPTCHA was triggered
                    if self.captcha_detector.is_captcha_present(driver, platform="linkedin")[0] and not self.captcha_detector.is_captcha_solved(driver, platform="linkedin"):
                        print_lg(f"[LinkedInApplier] Security challenge detected after Submit click!")
                        self.captcha_detector.handle_captcha(
                            driver,
                            platform="linkedin",
                            job_title=title,
                            company=company,
                            timeout=60,
                            automation_bridge=self.automation_bridge,
                        )

                    self.discard_modal()  # Closes post-submit success banner if any

                    print_lg(f"[LinkedInApplier] Successfully applied to {title} at {company} ({job_id})!")
                    self.tracker.record_state(
                        {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                        state="SUBMITTED",
                        user_id=self.user_id,
                    )
                    if self.automation_bridge:
                        try:
                            from app.services.automation_events import ApplicationSubmittedEvent
                            self.automation_bridge.handle_application_submitted(
                                ApplicationSubmittedEvent(
                                    run_id="linkedin_modular_run",
                                    platform="linkedin",
                                    external_job_id=str(job_id),
                                    title=title,
                                    company=company,
                                    source_url=source_url,
                                )
                            )
                        except Exception:
                            pass
                    return {"status": "SUBMITTED"}

            # Check for Review button
            review_buttons = driver.find_elements(By.XPATH, MODAL_REVIEW_BUTTON_XPATH)
            clicked_review = False
            for r_btn in review_buttons:
                if r_btn.is_displayed():
                    try:
                        human_click(driver, r_btn, smooth_scroll=True, dwell_before=True)
                    except Exception:
                        driver.execute_script("arguments[0].click();", r_btn)
                    human_delay(0.6, 1.4, action="click")
                    clicked_review = True
                    break

            if clicked_review:
                # Check if clicking review advanced or if validation errors kept us on the same step
                time.sleep(1.0)
                submits_now = driver.find_elements(By.XPATH, MODAL_SUBMIT_BUTTON_XPATH)
                if any(s.is_displayed() for s in submits_now):
                    continue
                err_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'artdeco-inline-feedback--error')] | //*[contains(@class, 'form-element--error')]")
                has_errors = any(e.is_displayed() for e in err_elements)
                if not has_errors:
                    continue

            # Check for Next button
            next_buttons = driver.find_elements(By.XPATH, MODAL_NEXT_BUTTON_XPATH)
            clicked_next = False
            for n_btn in next_buttons:
                if n_btn.is_displayed():
                    try:
                        human_click(driver, n_btn, smooth_scroll=True, dwell_before=True)
                    except Exception:
                        driver.execute_script("arguments[0].click();", n_btn)
                    human_delay(0.6, 1.4, action="click")
                    clicked_next = True
                    break

            if clicked_next:
                continue

            # Step could not be advanced automatically: form requires human intervention
            is_headless = False
            if self.browser and hasattr(self.browser, "headless"):
                is_headless = bool(self.browser.headless)

            if not is_headless and self.automation_bridge:
                print_lg(f"[LinkedInApplier] Application requires candidate intervention on '{title}' @ '{company}'. Pausing automation and waiting for user...")
                self.automation_bridge.reset_captcha_status()
                self.tracker.record_state(
                    {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
                    state="MANUAL_REQUIRED",
                    failure_reason="Unanswered screening questions or candidate input needed",
                    user_id=self.user_id,
                )

                start_wait = time.time()
                step_resolved = False
                while time.time() - start_wait < 180:
                    # 1. Did candidate cancel / skip via UI?
                    if self.automation_bridge.is_captcha_cancelled_by_user():
                        print_lg("[LinkedInApplier] Candidate cancelled or skipped this application.")
                        break

                    # 2. Did candidate provide answer via UI dialog?
                    u_input = self.automation_bridge.get_pending_input()
                    if u_input:
                        print_lg(f"[LinkedInApplier] Candidate provided answer: '{u_input}'. Applying to form fields...")
                        live_modal = self._find_modal(driver) or modal
                        if live_modal:
                            self._fill_pending_fields(driver, live_modal, u_input)
                            time.sleep(0.5)
                            if self._try_advance_step(driver, live_modal):
                                step_resolved = True
                                break

                    # 3. Did candidate solve directly in open browser?
                    if self.automation_bridge.is_captcha_resolved_by_user():
                        print_lg("[LinkedInApplier] Candidate marked manual resolution in browser.")
                        live_modal = self._find_modal(driver) or modal
                        if live_modal:
                            self._try_advance_step(driver, live_modal)
                        step_resolved = True
                        break

                    time.sleep(1.0)

                if step_resolved:
                    continue

            # Headless run, user cancelled, or wait timeout expired without input
            break

        # If reached here without submitting, modal requires cleanup
        print_lg(f"[LinkedInApplier] Application incomplete for {job_id}. Cleaning up modal.")
        self.discard_modal()
        self.tracker.record_state(
            {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
            state="MANUAL_REQUIRED",
            failure_reason="Unanswered screening questions or complex form step",
            user_id=self.user_id,
        )
        return {"status": "MANUAL_REQUIRED", "reason": "Unanswered screening questions"}
