'''
Foundit Questionnaire & Form Engine
Handles multi-step screening question forms using the unified QnAEngine and Resume Manager.
'''

import os
import time
import random
from typing import Optional, List, Dict, Any, Tuple
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select

from modules.qna_engine import QnAEngine, validate_answer, Answer
from modules.config_loader import get_resume
from modules.helpers import print_lg
from modules.human_behavior import human_type, human_delay, human_click


class FounditForm:
    """Manages questionnaire fields, screening questions, and file uploads on Foundit."""

    def __init__(self, browser: Any, qna_engine: Optional[QnAEngine] = None, user_id: int = 1):
        self.browser = browser
        self.qna_engine = qna_engine or QnAEngine()
        self.user_id = user_id

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def is_questionnaire_open(self) -> bool:
        """Checks if a screening questionnaire modal/drawer/form is currently open."""
        if not self.driver:
            return False
        for sel in [
            "//*[contains(normalize-space(), 'Screen Questionnaire')]",
            "//*[contains(normalize-space(), 'questionnaire submission')]",
            "//div[contains(@class, 'questionnaire')]",
            "//div[contains(@class, 'drawer') and .//*[contains(., 'Ques ')]]",
            "div[class*='modal'] form",
            "div[role='dialog']",
            "div[class*='questionnaire']",
            "div[class*='applyModal']",
        ]:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue
        return False

    def get_questionnaire_container(self) -> Optional[WebElement]:
        """Finds the active container element for the questionnaire (drawer or modal)."""
        if not self.driver:
            return None
        for sel in [
            "//div[contains(., 'Screen Questionnaire') and not(self::body)]",
            "//div[contains(@class, 'drawer') and .//*[contains(., 'Ques ')]]",
            "//div[contains(@class, 'questionnaire')]",
            "div[class*='modal']",
            "div[role='dialog']",
        ]:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        return el
            except Exception:
                continue
        return None

    def fill_all_visible_fields(self, job_context: str = "") -> Tuple[int, int]:
        """Discovers and answers all visible form controls in the active questionnaire.
        Returns: (fields_answered: int, fields_failed: int)
        """
        if not self.driver:
            return (0, 0)

        container = self.get_questionnaire_container() or self.driver
        answered = 0
        failed = 0

        # A. Handled Question Blocks (e.g. "Ques 1 ...", "Ques 2 ...") - Screenshot 1
        ques_elements = container.find_elements(
            By.XPATH,
            ".//*[starts-with(normalize-space(), 'Ques ') or starts-with(normalize-space(), 'Question ') or contains(@class, 'questionTitle')]"
        )
        if ques_elements:
            print_lg(f"[FounditForm] Discovered {len(ques_elements)} screening questions in questionnaire.")
            for q_elem in ques_elements:
                try:
                    q_text = (q_elem.text or "").strip()
                    # If q_elem only contains short prefix like "Ques 1", expand to parent or sibling
                    if len(q_text) < 15:
                        try:
                            parent_txt = (q_elem.find_element(By.XPATH, "..").text or "").strip()
                            if len(parent_txt) > len(q_text):
                                q_text = parent_txt
                        except Exception:
                            pass
                    if len(q_text) < 15:
                        try:
                            sib_txt = (q_elem.find_element(By.XPATH, "./following-sibling::*[1]").text or "").strip()
                            if sib_txt:
                                q_text = f"{q_text} {sib_txt}".strip()
                        except Exception:
                            pass

                    if not q_text or len(q_text) < 3:
                        continue

                    # Find parent block containing this question and its options
                    block = None
                    try:
                        block = q_elem.find_element(By.XPATH, "./ancestor::div[.//input or .//label][1]")
                    except Exception:
                        block = q_elem.find_element(By.XPATH, "..")

                    if not block:
                        continue

                    # 1. Radio Options (e.g. Yes / No)
                    radios = block.find_elements(By.XPATH, ".//input[@type='radio']")
                    if radios:
                        radio_options = []
                        for r in radios:
                            opt_text = ""
                            try:
                                t = r.find_element(By.XPATH, "./..").text
                                if isinstance(t, str):
                                    opt_text = t.strip()
                            except Exception:
                                pass
                            if not opt_text:
                                val = r.get_attribute("value")
                                if isinstance(val, str):
                                    opt_text = val.strip()
                            if not opt_text:
                                opt_text = "Yes" if len(radio_options) == 0 else "No"
                            radio_options.append(str(opt_text))

                        ans = self.qna_engine.answer_question(
                            question=q_text,
                            field_type="radio",
                            options=radio_options or ["Yes", "No"],
                            job_context=job_context,
                        )

                        clean_opts = [str(opt).strip().lower() for opt in radio_options]
                        # Special handling for Foundit binary Yes/No screening questions
                        if set(clean_opts) == {"yes", "no"} or ("yes" in clean_opts and "no" in clean_opts):
                            if ans and ans.value is not None:
                                val_str = str(ans.value).strip().lower()
                                if val_str in ["no", "false", "0", "none"]:
                                    chosen = "no"
                                else:
                                    chosen = "yes"
                            else:
                                chosen = "yes"
                        else:
                            chosen = str(ans.value).strip().lower() if ans and ans.value else "yes"

                        target_r = radios[0]
                        for idx, opt_lbl in enumerate(radio_options):
                            if chosen in opt_lbl.lower() or opt_lbl.lower() in chosen:
                                target_r = radios[idx]
                                break

                        # Click radio input and parent label to guarantee React state updates
                        try:
                            self.driver.execute_script("arguments[0].click();", target_r)
                        except Exception:
                            pass
                        try:
                            parent_lbl = target_r.find_element(By.XPATH, "./ancestor::label[1] | ./..")
                            self.driver.execute_script("arguments[0].click();", parent_lbl)
                        except Exception:
                            pass

                        answered += 1
                        time.sleep(0.2)
                        continue

                    # 2. Text / Number Inputs
                    inputs = block.find_elements(By.XPATH, ".//input[@type='text' or @type='number' or not(@type)] | .//textarea")
                    if inputs and inputs[0].is_displayed():
                        inp = inputs[0]
                        cur_val = inp.get_attribute("value") or ""
                        if not cur_val:
                            ans = self.qna_engine.answer_question(
                                question=q_text,
                                field_type="text",
                                job_context=job_context,
                            )
                            val_to_type = str(ans.value).strip() if ans and ans.value else "Yes"
                            human_type(inp, val_to_type, clear_first=True, driver=self.driver)
                            answered += 1
                            time.sleep(0.2)
                            continue
                except Exception as e:
                    print_lg(f"[FounditForm] Notice answering question block: {e}")
                    failed += 1

        # B. General Text and Textarea Inputs in Container
        text_inputs = container.find_elements(By.XPATH, ".//input[@type='text' or @type='tel' or @type='number'] | .//textarea")
        for inp in text_inputs:
            if not inp.is_displayed():
                continue
            try:
                label = self._find_field_label(inp)
                current_val = inp.get_attribute("value") or ""
                if current_val and len(current_val) > 1:
                    continue

                ans = self.qna_engine.answer_question(
                    question=label,
                    field_type="text",
                    job_context=job_context,
                )
                val_to_type = str(ans.value).strip() if ans and ans.value else "Yes"
                human_type(inp, val_to_type, clear_first=True, driver=self.driver)
                answered += 1
                time.sleep(0.2)
            except Exception as e:
                print_lg(f"[FounditForm] Notice answering text field: {e}")
                failed += 1

        # C. Select Dropdowns
        select_elems = container.find_elements(By.XPATH, ".//select")
        for s in select_elems:
            if not s.is_displayed():
                continue
            try:
                label = self._find_field_label(s)
                sel_obj = Select(s)
                options = [opt.text.strip() for opt in sel_obj.options if opt.text.strip()]
                if not options:
                    continue

                ans = self.qna_engine.answer_question(
                    question=label,
                    field_type="select",
                    options=options,
                    job_context=job_context,
                )
                chosen = str(ans.value).strip() if ans and ans.value else options[0]

                matched = False
                for opt in options:
                    if chosen.lower() in opt.lower() or opt.lower() in chosen.lower():
                        sel_obj.select_by_visible_text(opt)
                        matched = True
                        break
                if not matched and options:
                    sel_obj.select_by_index(0)

                answered += 1
                time.sleep(0.2)
            except Exception as e:
                print_lg(f"[FounditForm] Notice answering select dropdown: {e}")
                failed += 1

        # D. Radio Groups not covered in blocks
        radio_groups: Dict[str, List[WebElement]] = {}
        for r in container.find_elements(By.XPATH, ".//input[@type='radio']"):
            if not r.is_displayed():
                continue
            group_name = r.get_attribute("name") or "default_group"
            radio_groups.setdefault(group_name, []).append(r)

        for gname, radios in radio_groups.items():
            try:
                if any(r.is_selected() for r in radios):
                    continue
                label = self._find_field_label(radios[0])
                options = [self._find_field_label(r) for r in radios]
                ans = self.qna_engine.answer_question(
                    question=label,
                    field_type="radio",
                    options=options,
                    job_context=job_context,
                )
                chosen = str(ans.value).strip().lower() if ans and ans.value else "yes"

                target_radio = radios[0]
                for r, opt_lbl in zip(radios, options):
                    if chosen in opt_lbl.lower() or opt_lbl.lower() in chosen:
                        target_radio = r
                        break
                self.driver.execute_script("arguments[0].click();", target_radio)
                answered += 1
                time.sleep(0.2)
            except Exception as e:
                print_lg(f"[FounditForm] Notice answering radio group: {e}")
                failed += 1

        # E. Resume File Upload
        file_inputs = container.find_elements(By.XPATH, ".//input[@type='file']")
        for finp in file_inputs:
            try:
                resume_path = get_resume(user_id=self.user_id)
                if resume_path and os.path.exists(resume_path):
                    abs_path = os.path.abspath(resume_path)
                    finp.send_keys(abs_path)
                    print_lg(f"[FounditForm] Uploaded candidate resume: {abs_path}")
                    answered += 1
                    time.sleep(1)
            except Exception as e:
                print_lg(f"[FounditForm] Notice uploading resume: {e}")

        return (answered, failed)

    def submit_questionnaire(self) -> bool:
        """Finds and clicks the Submit button in the active questionnaire drawer/modal."""
        if not self.driver:
            return False
        container = self.get_questionnaire_container() or self.driver
        for sel in [
            ".//button[normalize-space()='Submit' or contains(normalize-space(), 'Submit')]",
            ".//input[@type='submit' or @value='Submit']",
            "button[type='submit']",
        ]:
            try:
                elems = container.find_elements(By.XPATH if sel.startswith(".") or sel.startswith("//") else By.CSS_SELECTOR, sel)
                for b in elems:
                    if b.is_displayed():
                        print_lg("[FounditForm] Clicking questionnaire Submit button...")
                        time.sleep(random.uniform(0.6, 1.2))
                        try:
                            b.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", b)
                        time.sleep(random.uniform(1.5, 2.5))
                        return True
            except Exception:
                continue
        return False

    def _find_field_label(self, elem: WebElement) -> str:
        """Finds descriptive label for an element using attributes and nearby DOM."""
        label_text = (
            elem.get_attribute("aria-label")
            or elem.get_attribute("placeholder")
            or elem.get_attribute("name")
            or ""
        )
        elem_id = elem.get_attribute("id")
        if elem_id:
            try:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{elem_id}']")
                if labels and labels[0].text.strip():
                    return labels[0].text.strip()
            except Exception:
                pass

        if not label_text or len(label_text) < 3:
            try:
                parent = elem.find_element(By.XPATH, "..")
                parent_txt = (parent.text or "").strip()
                if parent_txt and len(parent_txt) < 80:
                    return parent_txt
            except Exception:
                pass

        return label_text or "General Question"
