'''
Glassdoor Easy Apply Form Handler
Traverses multi-step Easy Apply dialogs, fills candidate personal info, handles resume upload,
and resolves screening questions using the shared QnA Engine.
'''

import time
from typing import Optional, Any, List, Dict
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from platforms.glassdoor.selectors import (
    EASY_APPLY_MODAL_CONTAINERS,
    FORM_FIRST_NAME_INPUTS,
    FORM_LAST_NAME_INPUTS,
    FORM_EMAIL_INPUTS,
    FORM_PHONE_INPUTS,
    FORM_LOCATION_INPUTS,
    FORM_RESUME_FILE_INPUTS,
    FORM_CONTINUE_BUTTONS,
    FORM_SUBMIT_BUTTONS,
)
from modules.helpers import print_lg
from modules.config_loader import get_personal, get_resume
from modules.qna_engine import QnAEngine
from modules.human_behavior import human_delay, human_type, smooth_scroll


class GlassdoorForm:
    """Manages multi-step application form progression on Glassdoor."""

    def __init__(self, browser: Any, qna_engine: Optional[QnAEngine] = None):
        self.browser = browser
        self.qna_engine = qna_engine or QnAEngine()

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def is_form_open(self) -> bool:
        """Checks if an Easy Apply modal is actively displayed."""
        if not self.driver:
            return False
        for sel in EASY_APPLY_MODAL_CONTAINERS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue
        return False

    def fill_personal_info(self) -> None:
        """Populates candidate contact information from unified profile."""
        if not self.driver:
            return

        personal = get_personal()
        fname = personal.get("first_name", "")
        lname = personal.get("last_name", "")
        email = personal.get("email", "")
        phone = personal.get("phone_number", "")
        city = personal.get("current_city", "")

        # First Name
        for sel in FORM_FIRST_NAME_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed() and not el.get_attribute("value"):
                    human_type(el, fname)
                    break
            except Exception:
                continue

        # Last Name
        for sel in FORM_LAST_NAME_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed() and not el.get_attribute("value"):
                    human_type(el, lname)
                    break
            except Exception:
                continue

        # Email
        for sel in FORM_EMAIL_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed() and not el.get_attribute("value"):
                    human_type(el, email)
                    break
            except Exception:
                continue

        # Phone
        for sel in FORM_PHONE_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed() and not el.get_attribute("value"):
                    human_type(el, phone)
                    break
            except Exception:
                continue

        # Location / City
        for sel in FORM_LOCATION_INPUTS:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR if not sel.startswith("/") else By.XPATH, sel)
                if el.is_displayed() and not el.get_attribute("value"):
                    human_type(el, city)
                    break
            except Exception:
                continue

    def upload_resume_if_needed(self, resume_path: Optional[str] = None) -> bool:
        """Uploads candidate PDF resume or confirms selected existing profile resume."""
        if not self.driver:
            return False

        # 1. Check if an existing profile resume is already selected
        try:
            selected_resume = self.driver.execute_script('''
                var radios = document.querySelectorAll("input[type='radio']");
                for (var r of radios) {
                    if (r.checked && (r.value.toLowerCase().includes('resume') || (r.labels && r.labels[0] && r.labels[0].innerText.toLowerCase().includes('resume')))) {
                        return true;
                    }
                }
                var selectedPill = document.querySelector("[data-test='selected-resume'], div[class*='resumeSelected']");
                if (selectedPill && selectedPill.offsetParent !== null) return true;
                return false;
            ''')
            if selected_resume is True:
                print_lg("[GlassdoorForm] Existing profile resume already selected.")
                return True
        except Exception:
            pass

        # 2. Upload file if file input present
        path = resume_path or get_resume()
        if not path:
            return False

        for sel in FORM_RESUME_FILE_INPUTS:
            try:
                elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    el.send_keys(path)
                    print_lg(f"[GlassdoorForm] Uploaded resume: {path}")
                    human_delay(1.5, 2.5)
                    return True
            except Exception:
                continue
        return False

    def answer_screening_questions(self) -> int:
        """Inspects and answers screening questions in the active modal dialog using QnAEngine."""
        if not self.driver:
            return 0

        answered = 0
        try:
            # 1. Radio groups (e.g. Yes/No work auth, driving license)
            radios = self.driver.find_elements(By.CSS_SELECTOR, "div[role='radiogroup'], fieldset")
            for group in radios:
                try:
                    if not group.is_displayed():
                        continue
                    legend = group.find_element(By.CSS_SELECTOR, "legend, [class*='label' i], label")
                    q_text = legend.text.strip()
                    if not q_text:
                        continue
                    ans = self.qna_engine.answer_question(q_text)
                    if ans:
                        # Click matching radio option
                        options = group.find_elements(By.CSS_SELECTOR, "label, input[type='radio']")
                        for opt in options:
                            if ans.lower() in opt.text.lower() or ans.lower() == opt.get_attribute("value"):
                                self.driver.execute_script("arguments[0].click();", opt)
                                answered += 1
                                human_delay(0.2, 0.4)
                                break
                except Exception:
                    continue

            # 2. Text / Numeric inputs
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "div[data-test='easy-apply-modal'] input[type='text'], div[data-test='easy-apply-modal'] input[type='number']")
            for inp in inputs:
                try:
                    if not inp.is_displayed() or inp.get_attribute("value"):
                        continue
                    lbl = ""
                    try:
                        lbl_el = inp.find_element(By.XPATH, "./preceding::label[1] | ./ancestor::div[1]//label")
                        lbl = lbl_el.text.strip()
                    except Exception:
                        pass
                    if not lbl:
                        lbl = inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or ""
                    if lbl:
                        ans = self.qna_engine.answer_question(lbl)
                        if ans:
                            human_type(inp, str(ans))
                            answered += 1
                            human_delay(0.2, 0.4)
                except Exception:
                    continue
        except Exception as e:
            print_lg(f"[GlassdoorForm] Notice answering questions: {e}")

        return answered

    def is_review_step(self) -> bool:
        """Determines if the form has reached the final review and submit step."""
        if not self.driver:
            return False

        # 1. URL-based check
        try:
            cur_url = (self.driver.current_url or "").lower()
            if "review" in cur_url:
                return True
        except Exception:
            pass

        # 2. Heading-based check
        try:
            headings = self.driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3, [role='heading']")
            for h in headings:
                txt = (h.text or "").lower()
                if "review" in txt:
                    return True
        except Exception:
            pass

        # 3. Submit button check with scroll to reveal
        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except Exception:
            pass

        for sel in FORM_SUBMIT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                if any(e.is_displayed() for e in elems):
                    return True
            except Exception:
                continue

        # 4. JavaScript check for submit application button
        try:
            has_submit = self.driver.execute_script("""
                const btn = document.querySelector("button[data-testid='submit-application-button'], button[type='submit']");
                if (btn && (btn.innerText || '').toLowerCase().includes('submit')) return true;
                return false;
            """)
            if has_submit:
                return True
        except Exception:
            pass

        return False

    def click_continue(self) -> bool:
        """Clicks the Next or Continue button to advance form step with JS fallback."""
        if not self.driver:
            return False
        for sel in FORM_CONTINUE_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("/") else By.CSS_SELECTOR, sel)
                for btn in elems:
                    if btn.is_displayed() and btn.is_enabled():
                        smooth_scroll(self.driver, btn)
                        human_delay(0.5, 1.0)
                        try:
                            btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", btn)
                        human_delay(1.8, 3.0)
                        return True
            except Exception:
                continue
        return False
