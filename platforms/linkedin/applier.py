"""LinkedIn Application Execution Engine.

Handles Easy Apply wizard steps, screening questions, and direct event emission.
"""

import time
from typing import Optional, Any, Dict, Tuple
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
            dismiss_buttons = driver.find_elements(By.XPATH, MODAL_DISMISS_BUTTON_XPATH)
            for btn in dismiss_buttons:
                if btn.is_displayed():
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    break

            confirm_buttons = driver.find_elements(By.XPATH, CONFIRM_DISCARD_BUTTON_XPATH)
            for btn in confirm_buttons:
                if btn.is_displayed():
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1)
                    break
        except Exception:
            try:
                self.browser.actions.send_keys(Keys.ESCAPE).perform()
            except Exception:
                pass

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
                    elif any(w in q_lower for w in ["require visa", "need visa", "visa sponsorship", "future sponsorship"]):
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
        """Discovers and answers custom comboboxes and dropdown buttons."""
        try:
            comboboxes = modal.find_elements(By.XPATH, ".//div[@role='combobox'] | .//input[@role='combobox'] | .//button[@aria-haspopup='listbox']")
            for cb in comboboxes:
                if not cb.is_displayed():
                    continue
                try:
                    cb_label = cb.get_attribute("aria-label") or ""
                    if not cb_label:
                        try:
                            lbl = cb.find_element(By.XPATH, "./ancestor::div[.//label or .//p][1]//(label|p)[1]")
                            cb_label = lbl.text.strip()
                        except Exception:
                            pass
                    if not cb_label:
                        cb_label = "Dropdown Question"

                    curr_val = cb.get_attribute("value") or cb.text or ""
                    if curr_val.strip() and curr_val.strip().lower() not in ["select an option", "choose an option"]:
                        continue

                    answer = "Yes"
                    if self.qna_engine:
                        ans = self.qna_engine.answer_text_question(cb_label, job_description=job_description, work_location=work_location)
                        if ans:
                            answer = ans

                    try:
                        cb.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", cb)
                    human_delay(0.3, 0.6, action="click")

                    options_xpath = "//div[@role='listbox']//*[@role='option'] | //ul[contains(@class, 'typeahead')]//li | //ul[@role='listbox']//li | //div[contains(@class, 'basic-typeahead')]//li"
                    options = driver.find_elements(By.XPATH, options_xpath)
                    clicked_opt = False
                    for opt in options:
                        if opt.is_displayed():
                            opt_text = opt.text.strip()
                            if opt_text and (answer.lower() in opt_text.lower() or opt_text.lower() in answer.lower()):
                                try:
                                    opt.click()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", opt)
                                clicked_opt = True
                                break
                    if not clicked_opt and options:
                        for opt in options:
                            if opt.is_displayed():
                                try:
                                    opt.click()
                                except Exception:
                                    driver.execute_script("arguments[0].click();", opt)
                                break
                except Exception:
                    pass
        except Exception:
            pass

    def _answer_step_questions(self, driver, modal, job_description: str = "", work_location: str = "") -> None:
        """Fills interactive form inputs, selects, and radios on the current modal step."""
        try:
            # 1. Fill radio button groups
            self._answer_radio_groups(driver, modal, job_description=job_description, work_location=work_location)

            # 2. Fill native dropdown selects
            select_elements = modal.find_elements(By.TAG_NAME, "select")
            for sel_el in select_elements:
                if not sel_el.is_displayed():
                    continue
                try:
                    from selenium.webdriver.support.ui import Select
                    sel = Select(sel_el)
                    first_opt = sel.first_selected_option.text if sel.options else ""
                    if not first_opt or first_opt.strip().lower() in ["select an option", "choose an option"]:
                        if len(sel.options) > 1:
                            sel.select_by_index(1)
                except Exception:
                    pass

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
                        inp_id = inp.get_attribute("id")
                        if inp_id:
                            lbl = modal.find_element(By.XPATH, f".//label[@for='{inp_id}']")
                            prompt = lbl.text.strip()
                    except Exception:
                        pass
                if not prompt:
                    try:
                        p_el = inp.find_element(By.XPATH, "./ancestor::div[p][1]//p[1]")
                        prompt = p_el.text.strip()
                    except Exception:
                        pass

                answer = "3"
                if prompt and self.qna_engine:
                    ans = self.qna_engine.answer_text_question(prompt, job_description=job_description, work_location=work_location)
                    if ans:
                        answer = ans

                try:
                    inp.clear()
                    inp.send_keys(answer)
                except Exception:
                    pass
                try:
                    driver.execute_script("""
                        arguments[0].focus();
                        arguments[0].value = arguments[1];
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
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
        except Exception:
            pass

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
            import time
            from urllib.parse import urlparse, parse_qs, unquote
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

            if not clicked_next:
                # Neither Next, Review, nor Submit was found/clickable
                break

        # If reached here without submitting, modal requires manual input or encountered error
        print_lg(f"[LinkedInApplier] Could not automatically complete application for {job_id}. Discarding modal.")
        self.discard_modal()
        self.tracker.record_state(
            {"platform": "linkedin", "job_id": job_id, "title": title, "company": company, "location": location, "source_url": source_url},
            state="MANUAL_REQUIRED",
            failure_reason="Unanswered screening questions or complex form step",
            user_id=self.user_id,
        )
        return {"status": "MANUAL_REQUIRED", "reason": "Unanswered screening questions"}
