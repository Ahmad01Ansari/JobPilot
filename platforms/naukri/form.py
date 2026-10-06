'''
Naukri Form Interaction Engine
Discovers, answers, validates, and fills screening questions and application form controls.
Supports text, number, textarea, radio, checkbox, dropdown/select, and file upload.
Strictly enforces the Phase 10 / 11 safety gate: STOPS before final submission.
'''

import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Any, Dict, Set
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import StaleElementReferenceException

from modules.helpers import print_lg
from modules.qna_engine import QnAEngine, Answer, validate_answer
from modules.config_loader import get_resume
from modules.human_behavior import human_type, human_delay, human_click
from platforms.naukri.selectors import (
    QUESTIONNAIRE_MODAL_SELECTORS,
    QUESTION_LABEL_SELECTORS,
    FORM_TEXT_INPUT_SELECTORS,
    FORM_TEXTAREA_SELECTORS,
    CONTENTEDITABLE_SELECTORS,
    FORM_RADIO_SELECTORS,
    FORM_CHECKBOX_SELECTORS,
    FORM_SELECT_SELECTORS,
    FORM_FILE_SELECTORS,
    FORM_NEXT_BUTTON_SELECTORS,
    FORM_SUBMIT_BUTTON_SELECTORS,
    SUBMISSION_SUCCESS_SELECTORS,
    SUBMISSION_CONFIRMATION_TEXTS,
    CHATBOT_CONFIRMATION_TEXTS,
    SUBMISSION_ERROR_TEXTS,
    APPLIED_BUTTON_SELECTORS,
    MODAL_CLOSE_BUTTONS,
)
from platforms.naukri.diagnostics import log_input_debug


@dataclass
class FormField:
    """Represents an interactable form field discovered in the questionnaire modal."""
    field_type: str                        # "text", "number", "textarea", "contenteditable", "radio", "checkbox", "select", "file", "unknown"
    label: str
    element: Any                           # Primary WebElement
    options: List[str] = field(default_factory=list)
    raw_elements: List[Any] = field(default_factory=list)  # Elements to click for choices (radio/checkbox/option)
    required: bool = False
    current_value: Optional[str] = None


class NaukriForm:
    """
    Form interaction engine for Naukri application modals and screening questionnaires.
    """

    def __init__(
        self,
        browser: Any,
        qna_engine: Optional[QnAEngine] = None,
        resume_path: Optional[str] = None,
    ):
        self.browser = browser
        self.qna_engine = qna_engine or QnAEngine()
        self.resume_path = resume_path or get_resume()
        self._chatbot_mode: bool = False
        self._chatbot_thank_you_detected: bool = False

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def get_container(self) -> Optional[Any]:
        """Locates active questionnaire modal or drawer, strictly avoiding navigation headers and job page bars."""
        if not self.driver:
            return None

        # 1. Primary: Locate explicit Naukri chatbot drawer containers
        for sel in [
            "div._chatBotContainer",
            "div[class*='_chatBotContainer']",
            "div.chatbot_Drawer",
            "div[class*='chatbot_Drawer']",
            "div.chatbot_MessageContainer",
            "div[class*='chatbot_MessageContainer']",
        ]:
            try:
                drawers = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for d in drawers:
                    if d.is_displayed():
                        return d
            except Exception:
                pass

        # 2. Secondary: Check explicit modal / drawer container selectors
        for sel in QUESTIONNAIRE_MODAL_SELECTORS:
            try:
                modals = self.driver.find_elements(By.CSS_SELECTOR, sel)
                for m in modals:
                    if not m.is_displayed():
                        continue
                    m_cls = (m.get_attribute("class") or "").lower()
                    m_id = (m.get_attribute("id") or "").lower()
                    if any(nav in m_cls or nav in m_id for nav in ["ni-gnb", "gnb", "navbar", "header", "menu", "styles_jhc"]):
                        continue
                    return m
            except Exception:
                continue

        # 3. Tertiary: Anchor-based search (chat inputs or bot message bubbles inside drawer)
        try:
            drawer_anchors = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[placeholder*='Type message'], textarea[placeholder*='Type message'], "
                "input[placeholder*='type message'], textarea[placeholder*='type message'], "
                "div[contenteditable='true'], [role='textbox'][contenteditable], "
                "div[class*='chat-input'], div[class*='bot-input'], div.textArea, "
                ".bot-msg, .chat-bubble, div[class*='botMsg'], div[class*='bot-msg']"
            )
            for da in drawer_anchors:
                if da.is_displayed():
                    try:
                        container = da.find_element(
                            By.XPATH,
                            "./ancestor::*[contains(@class, 'Drawer') or contains(@class, 'drawer') or "
                            "contains(@class, 'chatbot') or contains(@class, 'modal') or "
                            "contains(@class, 'chat') or contains(@class, 'bot') or @role='dialog']"
                            "[not(contains(@class, 'nI-gNb')) and not(contains(@class, 'gnb')) and not(contains(@class, 'styles_jhc'))][last()]"
                        )
                        if container and container.is_displayed():
                            return container
                    except Exception:
                        pass
        except Exception:
            pass

        return None

    def is_chatbot(self, container: Optional[Any] = None) -> bool:
        """Determines whether the active container is a conversational chatbot drawer."""
        if not self.driver:
            return False

        # If explicit chatbot drawer is visible, we are definitely in chatbot mode!
        try:
            drawers = self.driver.find_elements(
                By.CSS_SELECTOR,
                "div._chatBotContainer, div[class*='_chatBotContainer'], div.chatbot_Drawer, div[class*='chatbot_Drawer']"
            )
            for d in drawers:
                if d.is_displayed():
                    return True
        except Exception:
            pass

        # If a chat input or contenteditable or bot message is visible anywhere on the page, we are in chatbot mode!
        try:
            chat_indicators = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[placeholder*='Type message'], textarea[placeholder*='Type message'], "
                "input[placeholder*='type message'], textarea[placeholder*='type message'], "
                "div[contenteditable='true'], [role='textbox'][contenteditable], "
                "div[class*='chat-input'], div[class*='bot-input'], div.textArea, "
                "div[class*='chatbot'], div[class*='bot-msg'], div[class*='chat-bubble'], "
                "div[class*='botMsg'], div[class*='chatLayer']"
            )
            for ci in chat_indicators:
                try:
                    if ci.is_displayed():
                        cls = (ci.get_attribute("class") or "").lower()
                        if "gnb" not in cls and "navbar" not in cls:
                            return True
                except Exception:
                    pass
        except Exception:
            pass

        ctx = container or self.get_container()
        if not ctx:
            return False
        try:
            cls = (ctx.get_attribute("class") or "").lower()
            if any(w in cls for w in ["chatbot", "chat", "bot", "drawer"]) and "gnb" not in cls:
                return True
            elems = ctx.find_elements(
                By.CSS_SELECTOR,
                "div[class*='chatbot'], div[class*='bot-msg'], div[class*='chat-bubble'], div[class*='botMsg']"
            )
            return len(elems) > 0
        except (StaleElementReferenceException, Exception):
            return False

    def wait_for_chatbot_ready(self, container: Optional[Any] = None, timeout: float = 8.0) -> bool:
        """
        In a chatbot drawer, actively waits for typing indicators (• • • •) or initial greetings to resolve
        into a real question bubble, interactive choice chips, or confirmation screen.
        """
        if not self.is_chatbot(container):
            return True

        start = time.time()
        while time.time() - start < timeout:
            ctx = container or self.get_container() or self.driver
            if not ctx:
                return False

            if self._check_submission_confirmed():
                return True

            # 1. Check if typing indicator is visible
            typing_active = False
            try:
                typing_nodes = ctx.find_elements(
                    By.XPATH,
                    ".//*[contains(@class, 'typing') or contains(@class, 'dot') or contains(@class, 'loader') or contains(@class, 'spinner')] | "
                    ".//*[contains(text(), '•') or contains(text(), '...')]"
                )
                for tn in typing_nodes:
                    try:
                        if tn.is_displayed():
                            typing_active = True
                            break
                    except (StaleElementReferenceException, Exception):
                        typing_active = True
                        break
            except Exception:
                pass

            if typing_active:
                time.sleep(0.4)
                continue

            # 2. Check if choice chips / radio options have appeared
            try:
                for sel in FORM_RADIO_SELECTORS:
                    radios = ctx.find_elements(By.CSS_SELECTOR, sel)
                    for r in radios:
                        try:
                            if r.is_displayed():
                                return True
                        except StaleElementReferenceException:
                            pass
            except Exception:
                pass

            # 3. Check if a real question bubble is present
            try:
                msg_nodes = ctx.find_elements(
                    By.XPATH,
                    ".//*[contains(@class, 'bot-msg') or contains(@class, 'botMsg') or contains(@class, 'chat-bubble') or contains(@class, 'msg-wrapper') or contains(@class, 'message')]//p | "
                    ".//*[contains(@class, 'bot-msg') or contains(@class, 'botMsg') or contains(@class, 'chat-bubble') or contains(@class, 'msg-wrapper') or contains(@class, 'message')]"
                )
                for node in reversed(msg_nodes):
                    try:
                        txt = (node.text or "").strip()
                    except StaleElementReferenceException:
                        continue
                    if (
                        txt
                        and not txt.startswith("Hi ")
                        and "thank you for showing interest" not in txt.lower()
                        and "kindly answer all" not in txt.lower()
                        and not all(c in "•.  " for c in txt)
                    ):
                        return True
            except Exception:
                pass

            time.sleep(0.4)

        return False

    def _get_latest_chatbot_question(self, container: Optional[Any] = None) -> Optional[str]:
        """Extracts the latest active recruiter/bot question bubble in the chatbot conversation."""
        if not self.driver:
            return None

        ctx = container or self.get_container()
        search_roots = [ctx] if ctx else []
        if not search_roots:
            try:
                drawers = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='drawer'], div[class*='chatbot'], div[class*='chat'], "
                    "div[class*='bot-'], div[class*='apply-message'], div[class*='chatLayer'], "
                    "[role='dialog'], .styles_modal__gNq3p"
                )
                search_roots = [d for d in drawers if d.is_displayed()]
            except Exception:
                pass
        if not search_roots:
            search_roots = [self.driver]

        skip_phrases = [
            "thank you", "noted", "got it", "hi ", "hello",
            "start your interview", "all interview questions",
            "kindly answer all the recruiter's questions", "kindly answer all",
            "share your background", "companies appreciate",
            "type message here", "type message", "save", "submit", "cancel",
        ]
        skip_answers = {
            "currently serving", "previously served", "never served",
            "army", "navy", "air force", "yes", "no", "none", "agree", "disagree",
            "2.0", "1.0", "3.0", "delhi", "noida", "bengaluru"
        }

        for root in search_roots:
            try:
                # 1. Primary: Query dedicated bot message wrappers in Naukri's chatbot
                # In Naukri chatbot DOM, all recruiter prompts are inside:
                # <li class="botItem ..."><div class="botMsg msg"><div><span>...</span></div></div></li>
                bot_nodes = root.find_elements(
                    By.CSS_SELECTOR,
                    "li.botItem div.botMsg, li[class*='botItem'] [class*='botMsg'], "
                    "div.botMsg, [class*='botMsg'], li.botItem div.msg, div.chat-bubble"
                )
                for node in reversed(bot_nodes):
                    try:
                        txt = (node.text or node.get_attribute("innerText") or "").strip()
                    except Exception:
                        continue
                    if not txt or len(txt) < 3:
                        continue
                    txt_lower = txt.lower()
                    if any(sp in txt_lower for sp in skip_phrases):
                        continue
                    if txt_lower in skip_answers:
                        continue
                    if all(c in "•.  " for c in txt):
                        continue
                    return self._clean_label(txt)
            except Exception:
                pass

            # 2. Fallback: Search all text nodes in reverse order
            try:
                nodes = root.find_elements(
                    By.XPATH,
                    ".//*[self::p or self::span or self::div or self::h4 or self::h5][string-length(normalize-space(text())) > 2]"
                )
                for node in reversed(nodes):
                    try:
                        txt = (node.text or "").strip()
                    except Exception:
                        continue
                    if not txt or len(txt) < 3:
                        continue
                    txt_lower = txt.lower()

                    # Exclude candidate response bubbles on the right / containing pencil edit icon
                    try:
                        classes = (node.get_attribute("class") or "").lower()
                        parent_classes = (node.find_element(By.XPATH, "..").get_attribute("class") or "").lower()
                        all_cls = f"{classes} {parent_classes}"
                        if any(u in all_cls for u in ["user", "msg-right", "msgright", "sender", "right", "applicant", "candidate"]):
                            continue
                    except Exception:
                        pass

                    try:
                        has_pencil = len(node.find_elements(By.XPATH, ".//*[contains(@class, 'edit') or contains(@class, 'pencil') or self::svg]")) > 0
                        if has_pencil and len(txt) < 30:
                            continue
                    except Exception:
                        pass

                    if txt_lower in skip_answers:
                        continue
                    if any(skip in txt_lower for skip in skip_phrases):
                        continue
                    if all(c in "•.  " for c in txt):
                        continue

                    # If it's a valid bot prompt, return it directly
                    return self._clean_label(txt)
            except Exception:
                pass

        return None

    def identify_question(
        self,
        element: Any,
        parent_block: Optional[Any] = None,
    ) -> str:
        """Extracts the question prompt/label associated with a form input element."""
        if not element:
            return "Question"

        # 1. Primary: If inside a chatbot or drawer, extract the latest active bot question bubble
        if self.is_chatbot():
            q = self._get_latest_chatbot_question()
            if q and q != "Question":
                return q

        # Also check container from element ancestor
        try:
            bot_container = element.find_element(
                By.XPATH,
                "./ancestor::*[contains(@class, 'chatbot') or contains(@class, 'drawer') or contains(@class, 'bot-') or contains(@class, 'apply') or contains(@class, 'chat')][1]"
            )
            if bot_container:
                q = self._get_latest_chatbot_question(container=bot_container)
                if q and q != "Question":
                    return q
        except Exception:
            pass

        # 2. Check label[for="id"]
        try:
            elem_id = element.get_attribute("id")
            if elem_id and self.driver:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{elem_id}']")
                for lbl in labels:
                    txt = (lbl.text or "").strip()
                    if txt:
                        return self._clean_label(txt)
        except Exception:
            pass

        # 3. Check parent block or ancestor containers for question labels
        blocks = [parent_block] if parent_block else []
        if not parent_block:
            try:
                parent = element.find_element(
                    By.XPATH,
                    "./ancestor::*[contains(@class, 'question') or contains(@class, 'form-group') or contains(@class, 'bot-msg') or contains(@class, 'field') or contains(@class, 'msg-wrap')][1]"
                )
                if parent:
                    blocks.append(parent)
            except Exception:
                pass

        for block in blocks:
            if not block:
                continue
            for sel in QUESTION_LABEL_SELECTORS:
                try:
                    candidates = block.find_elements(By.CSS_SELECTOR, sel)
                    for cand in candidates:
                        txt = (cand.text or "").strip()
                        if txt and len(txt) > 1 and not txt.startswith("Hi "):
                            return self._clean_label(txt)
                except Exception:
                    continue

        # 4. Check element attributes (aria-label, placeholder, title, name)
        for attr in ["aria-label", "placeholder", "title", "name"]:
            try:
                val = element.get_attribute(attr)
                if val and val.strip():
                    cleaned_val = val.strip().lower()
                    # Skip generic chat input placeholders
                    if any(p in cleaned_val for p in ["type message", "type your message", "type here", "write a message"]):
                        continue
                    return self._clean_label(val.strip())
            except Exception:
                pass

        # 5. Fallback: Preceding sibling text or label
        try:
            prev = element.find_element(By.XPATH, "preceding-sibling::*[1]")
            if prev and prev.text and prev.text.strip():
                return self._clean_label(prev.text.strip())
        except Exception:
            pass

        return "Question"

    def _clean_label(self, label: str) -> str:
        """Cleans asterisks, colons, extra whitespaces from question labels."""
        cleaned = re.sub(r'[\*\:\?]+$', '', label.strip())
        cleaned = re.sub(r'^\*+\s*', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned or "Question"

    def discover_fields(self, container: Optional[Any] = None) -> List[FormField]:
        """Scans active modal/container and discovers all interactable fields."""
        if not self.driver:
            return []

        ctx = container or self.get_container() or self.driver

        # If inside a chatbot drawer, wait for question loading/typing dots to resolve
        if self.is_chatbot(ctx):
            self.wait_for_chatbot_ready(container=ctx, timeout=6.0)

        for attempt in range(2):
            try:
                return self._discover_fields_internal(container)
            except StaleElementReferenceException:
                time.sleep(0.5)
            except Exception as e:
                print_lg(f"[NaukriForm] Field discovery notice: {e}")
                break
        return []

    def _discover_fields_internal(self, container: Optional[Any] = None) -> List[FormField]:
        """Internal field discovery logic."""
        if not self.driver:
            return []

        ctx = container or self.get_container() or self.driver

        # =========================================================================
        # CHATBOT DRAWER SPECIALIZED FIELD DISCOVERY
        # =========================================================================
        if self.is_chatbot(ctx):
            # 1. First, check if active quick-reply chips/buttons or radio options are present in the chatbot container.
            active_chips = []
            seen_texts = set()
            candidate_elements = []

            search_roots = [ctx] if ctx else []
            if not search_roots and self.driver:
                search_roots.append(self.driver)

            for root in search_roots:
                for sel in FORM_RADIO_SELECTORS:
                    try:
                        elems = root.find_elements(By.CSS_SELECTOR, sel)
                        candidate_elements.extend(elems)
                    except Exception:
                        pass

                # Only use fallback xpath choices if no standard radio/chip elements were found
                if not candidate_elements:
                    try:
                        xpath_choices = root.find_elements(
                            By.XPATH,
                            ".//*[self::div or self::label or self::button or self::li or self::span or self::p]"
                            "[translate(normalize-space(.), 'YES', 'yes')='yes' or translate(normalize-space(.), 'NO', 'no')='no' or "
                            "translate(normalize-space(.), 'CURRENTLY SERVING', 'currently serving')='currently serving' or "
                            "translate(normalize-space(.), 'NEVER SERVED', 'never served')='never served' or "
                            "translate(normalize-space(.), 'PREVIOUSLY SERVED', 'previously served')='previously served']"
                        )
                        candidate_elements.extend(xpath_choices)
                    except Exception:
                        pass

            for el in candidate_elements:
                is_disp = False
                try:
                    is_disp = el.is_displayed()
                except Exception:
                    pass

                target_click_elem = el
                if not is_disp:
                    try:
                        parent = el.find_element(
                            By.XPATH,
                            "./ancestor::*[self::label or contains(@class, 'radio') or contains(@class, 'option') or contains(@class, 'choice') or contains(@class, 'pill') or contains(@class, 'mcc')][1]"
                        )
                        if parent and parent.is_displayed():
                            target_click_elem = parent
                            is_disp = True
                    except Exception:
                        pass

                if not is_disp:
                    continue

                # Exclude past user answer bubbles (bubbles containing pencil edit icons or userMsg/userItem class)
                try:
                    user_bubbles = target_click_elem.find_elements(
                        By.XPATH,
                        "./ancestor-or-self::*[contains(@class, 'userMsg') or contains(@class, 'userItem') or contains(@class, 'editable-listItem') or contains(@class, 'user-msg') or contains(@class, 'usermsg') or contains(@class, 'msg-user') or contains(@class, 'user_item')]"
                    )
                    if user_bubbles:
                        continue
                    has_pencil = len(target_click_elem.find_elements(
                        By.XPATH,
                        "./ancestor-or-self::*[contains(@class, 'chatbot_ListItem') or contains(@class, 'userItem') or contains(@class, 'userMsg')]//*[contains(@class, 'pencil') or contains(@class, 'editMsg') or contains(@class, 'chatBot-edit_pencil')]"
                    )) > 0
                    if has_pencil:
                        continue
                except Exception:
                    pass

                raw_text = (target_click_elem.text or target_click_elem.get_attribute("innerText") or target_click_elem.get_attribute("value") or "").strip()
                lines = [l.strip() for l in raw_text.splitlines() if l.strip() and not l.strip().startswith("•")]
                choice_txt = None
                if lines:
                    for l in lines:
                        if l.lower() in ["yes", "no", "never served", "currently serving", "previously served", "none", "agree", "disagree", "true", "false"]:
                            choice_txt = l
                            break
                    if not choice_txt:
                        choice_txt = lines[-1] if len(lines[-1]) < 50 else lines[0]
                else:
                    try:
                        eid = target_click_elem.get_attribute("id")
                        if eid and self.driver:
                            lbls = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{eid}']")
                            if lbls and lbls[0].is_displayed():
                                choice_txt = (lbls[0].text or "").strip()
                    except Exception:
                        pass

                if not choice_txt:
                    continue

                choice_lower = choice_txt.lower()
                if any(skip in choice_lower for skip in ["save", "submit", "type message", "cancel", "thank you", "noted", "hi "]):
                    continue
                if len(choice_txt) > 60:
                    continue

                if choice_lower not in seen_texts:
                    seen_texts.add(choice_lower)
                    active_chips.append((target_click_elem, choice_txt))

            if active_chips:
                first_elem = active_chips[0][0]
                lbl = self._get_latest_chatbot_question(ctx) or self.identify_question(first_elem)
                lbl_clean = self._clean_label(lbl).lower() if lbl else ""

                # Filter out chips that match question text or question fragments
                filtered_chips = []
                for elem, c_txt in active_chips:
                    c_clean = self._clean_label(c_txt).lower()
                    if lbl_clean and (c_clean == lbl_clean or (len(c_clean) > 20 and c_clean in lbl_clean) or (len(lbl_clean) > 20 and lbl_clean in c_clean)):
                        continue
                    filtered_chips.append((elem, c_txt))
                if filtered_chips:
                    active_chips = filtered_chips

                # Check whether these chips are checkboxes or radio buttons
                is_checkbox = False
                try:
                    cb_elems = ctx.find_elements(By.CSS_SELECTOR, "input[type='checkbox'], input.mcc__checkbox, div.multiselectcheckboxes, div.multicheckboxes-container")
                    if cb_elems:
                        is_checkbox = True
                except Exception:
                    pass

                field_type = "checkbox" if is_checkbox else "radio"
                if len(active_chips) >= 2 or any(c[1].lower() in ["yes", "no", "never served", "currently serving", "none"] for c in active_chips):
                    return [FormField(
                        field_type=field_type,
                        label=lbl,
                        element=active_chips[0][0],
                        options=[c[1] for c in active_chips],
                        raw_elements=[c[0] for c in active_chips],
                        required=True,
                    )]

            # 2. Second, if no active chips, check contenteditable chat inputs
            for sel in CONTENTEDITABLE_SELECTORS:
                try:
                    ceds = ctx.find_elements(By.CSS_SELECTOR, sel)
                    for ce in ceds:
                        if ce.is_displayed():
                            lbl = self._get_latest_chatbot_question(ctx) or self.identify_question(ce)
                            val = ce.get_attribute("textContent") or ce.text or ""
                            lbl_lower = lbl.lower() if lbl else ""
                            field_type = "number" if any(kw in lbl_lower for kw in ["year", "experience", "exp", "ctc", "salary", "notice", "month", "how many"]) else "contenteditable"
                            return [FormField(
                                field_type=field_type,
                                label=lbl,
                                element=ce,
                                required=True,
                                current_value=val,
                            )]
                except Exception:
                    pass

            # 3. Third, look for the standard chatbot text input
            for sel in [
                "input[placeholder*='Type message']", "textarea[placeholder*='Type message']",
                "input[placeholder*='type message']", "textarea[placeholder*='type message']",
                "input[placeholder*='answer']", "textarea[placeholder*='answer']",
                "input[class*='chat-input']", "input[class*='bot-input']",
                "input[type='text']", "input[type='number']", "input:not([type])", "textarea"
            ]:
                try:
                    inputs = ctx.find_elements(By.CSS_SELECTOR, sel)
                    for inp in inputs:
                        if inp.is_displayed():
                            lbl = self._get_latest_chatbot_question(ctx) or self.identify_question(inp)
                            inp_type = (inp.get_attribute("type") or "text").lower()
                            lbl_lower = lbl.lower() if lbl else ""
                            field_type = "number" if inp_type == "number" or any(kw in lbl_lower for kw in ["year", "experience", "exp", "ctc", "salary", "notice", "month", "how many"]) else "text"
                            val = inp.get_attribute("value") or ""
                            return [FormField(
                                field_type=field_type,
                                label=lbl,
                                element=inp,
                                required=True,
                                current_value=val,
                            )]
                except Exception:
                    pass

            # In chatbot drawer, do not fall back to generic page forms!
            return []

        # GUARD: If ctx is None (container=None and get_container() returned None),
        # there is no active form on the page. Return empty immediately.
        if ctx is None:
            print_lg("[NaukriForm] No container found for field discovery, skipping.")
            return []

        fields: List[FormField] = []
        seen_elements: Set[Any] = set()

        # 1. File Uploads (often hidden input[type='file'])
        for sel in FORM_FILE_SELECTORS:
            try:
                file_inputs = ctx.find_elements(By.CSS_SELECTOR, sel)
                for fi in file_inputs:
                    if fi in seen_elements:
                        continue
                    lbl = self.identify_question(fi)
                    is_displayed = False
                    try:
                        is_displayed = fi.is_displayed()
                    except Exception:
                        pass
                    # If hidden, only treat as file input if active prompt explicitly asks for a resume/document
                    is_file_prompt = any(w in lbl.lower() for w in ["resume", "cv", "upload", "attach", "document", "file"])
                    if not is_displayed and not is_file_prompt:
                        continue

                    seen_elements.add(fi)
                    if lbl == "Question":
                        lbl = "Resume / CV Upload"
                    fields.append(FormField(
                        field_type="file",
                        label=lbl,
                        element=fi,
                        required=bool(fi.get_attribute("required")),
                    ))
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering file fields: {e}")

        # 2. Textarea Inputs
        for sel in FORM_TEXTAREA_SELECTORS:
            try:
                areas = ctx.find_elements(By.CSS_SELECTOR, sel)
                for ta in areas:
                    if ta in seen_elements or not ta.is_displayed():
                        continue
                    # In chatbot drawer, handle message input in step 6 after evaluating chips
                    if self.is_chatbot(ctx):
                        continue
                    seen_elements.add(ta)
                    lbl = self.identify_question(ta)
                    val = ta.get_attribute("value") or ""
                    fields.append(FormField(
                        field_type="textarea",
                        label=lbl,
                        element=ta,
                        required=bool(ta.get_attribute("required")),
                        current_value=val,
                    ))
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering textarea fields: {e}")

        # 3. Radio Buttons & Quick Reply Chips
        radio_groups: Dict[str, List[Any]] = {}
        for sel in FORM_RADIO_SELECTORS:
            try:
                radios = ctx.find_elements(By.CSS_SELECTOR, sel)
                for r in radios:
                    if r in seen_elements or not r.is_displayed():
                        continue
                    seen_elements.add(r)
                    if self.is_chatbot(ctx):
                        group_key = "chatbot_active_chips"
                    else:
                        group_key = r.get_attribute("name") or "default_radio_group"
                        if "chip" in sel:
                            try:
                                parent = r.find_element(By.XPATH, "..")
                                group_key = f"chip_group_{id(parent)}"
                            except Exception:
                                pass
                    if group_key not in radio_groups:
                        radio_groups[group_key] = []
                    radio_groups[group_key].append(r)
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering radio fields: {e}")

        # In chatbot drawer: if active chips are found, return ONLY the active chip group as a single FormField
        if self.is_chatbot(ctx) and "chatbot_active_chips" in radio_groups and radio_groups["chatbot_active_chips"]:
            group_elems = radio_groups["chatbot_active_chips"]
            first_elem = group_elems[0]
            lbl = self.identify_question(first_elem)
            options: List[str] = []
            for elem in group_elems:
                opt_text = (elem.text or elem.get_attribute("value") or "").strip()
                if not opt_text:
                    try:
                        opt_text = elem.find_element(By.XPATH, "./following-sibling::*[1]").text.strip()
                    except Exception:
                        try:
                            opt_text = elem.find_element(By.XPATH, "..").text.strip()
                        except Exception:
                            opt_text = ""
                options.append(opt_text or "Option")

            return [FormField(
                field_type="radio",
                label=lbl,
                element=first_elem,
                options=options,
                raw_elements=group_elems,
                required=True,
            )]

        for grp_name, group_elems in radio_groups.items():
            if not group_elems:
                continue
            first_elem = group_elems[0]
            lbl = self.identify_question(first_elem)
            options: List[str] = []
            for elem in group_elems:
                opt_text = (elem.text or elem.get_attribute("value") or "").strip()
                if not opt_text:
                    try:
                        opt_text = elem.find_element(By.XPATH, "./following-sibling::*[1]").text.strip()
                    except Exception:
                        try:
                            opt_text = elem.find_element(By.XPATH, "..").text.strip()
                        except Exception:
                            opt_text = ""
                options.append(opt_text or "Option")

            fields.append(FormField(
                field_type="radio",
                label=lbl,
                element=first_elem,
                options=options,
                raw_elements=group_elems,
                required=any(bool(e.get_attribute("required")) for e in group_elems),
            ))

        # 4. Checkboxes
        for sel in FORM_CHECKBOX_SELECTORS:
            try:
                cb_inputs = ctx.find_elements(By.CSS_SELECTOR, sel)
                for cb in cb_inputs:
                    if cb in seen_elements or not cb.is_displayed():
                        continue
                    seen_elements.add(cb)
                    lbl = self.identify_question(cb)
                    opt_text = (cb.text or cb.get_attribute("value") or "").strip()
                    if not opt_text:
                        try:
                            opt_text = cb.find_element(By.XPATH, "..").text.strip()
                        except Exception:
                            pass
                    fields.append(FormField(
                        field_type="checkbox",
                        label=lbl,
                        element=cb,
                        options=[opt_text] if opt_text else ["Yes"],
                        raw_elements=[cb],
                        required=bool(cb.get_attribute("required")),
                    ))
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering checkboxes: {e}")

        # 5. Dropdown / Select
        for sel in FORM_SELECT_SELECTORS:
            try:
                select_elems = ctx.find_elements(By.CSS_SELECTOR, sel)
                for se in select_elems:
                    if se in seen_elements or not se.is_displayed():
                        continue
                    seen_elements.add(se)
                    lbl = self.identify_question(se)
                    options = []
                    raw_options = []
                    try:
                        opts = se.find_elements(By.TAG_NAME, "option")
                        for o in opts:
                            txt = (o.text or o.get_attribute("value") or "").strip()
                            if txt and not any(p in txt.lower() for p in ["select an option", "--select--", "choose", "select"]):
                                options.append(txt)
                                raw_options.append(o)
                    except Exception:
                        pass
                    fields.append(FormField(
                        field_type="select",
                        label=lbl,
                        element=se,
                        options=options,
                        raw_elements=raw_options,
                        required=bool(se.get_attribute("required")),
                    ))
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering selects: {e}")

        # 6. Text & Number Inputs
        # In chatbot drawer, if choice options (chips/radios/selects) are already detected,
        # skip discovering text inputs (the bottom 'Type message here...' input bar must not be used).
        if self.is_chatbot(ctx) and any(f.field_type in ("radio", "select", "checkbox") for f in fields):
            return fields

        for sel in FORM_TEXT_INPUT_SELECTORS:
            try:
                inputs = ctx.find_elements(By.CSS_SELECTOR, sel)
                for inp in inputs:
                    if inp in seen_elements or not inp.is_displayed():
                        continue
                    seen_elements.add(inp)
                    lbl = self.identify_question(inp)
                    inp_type = inp.get_attribute("type") or "text"
                    lbl_lower = lbl.lower()
                    field_type = "number" if inp_type == "number" or any(kw in lbl_lower for kw in ["year", "experience", "exp", "ctc", "salary", "notice"]) else "text"
                    val = inp.get_attribute("value") or ""
                    fields.append(FormField(
                        field_type=field_type,
                        label=lbl,
                        element=inp,
                        required=bool(inp.get_attribute("required")),
                        current_value=val,
                    ))
                    # In chatbot drawer, only ONE active text input exists at any time
                    if self.is_chatbot(ctx):
                        return fields
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering text inputs: {e}")

        # 7. Contenteditable Elements in regular forms
        for sel in CONTENTEDITABLE_SELECTORS:
            try:
                ceds = ctx.find_elements(By.CSS_SELECTOR, sel)
                for ce in ceds:
                    if ce in seen_elements or not ce.is_displayed():
                        continue
                    seen_elements.add(ce)
                    lbl = self.identify_question(ce)
                    val = ce.get_attribute("textContent") or ce.text or ""
                    fields.append(FormField(
                        field_type="contenteditable",
                        label=lbl,
                        element=ce,
                        required=True,
                        current_value=val,
                    ))
            except Exception as e:
                print_lg(f"[NaukriForm] Notice discovering contenteditable controls: {e}")

        return fields

    def answer(
        self,
        field: FormField,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None,
    ) -> Answer:
        """Determines the appropriate answer for a form field using QnAEngine."""
        if field.field_type == "file":
            path = self.resume_path or get_resume()
            ans = Answer(value=path, source="profile", confidence=1.0, field_type="file")
            return validate_answer(ans, field.label)

        if field.field_type in ("text", "number", "textarea", "contenteditable"):
            ans = self.qna_engine.resolve_text_answer(
                field.label,
                job_description=job_description,
                work_location=work_location,
            )
            ans.field_type = field.field_type
            return ans

        if field.field_type in ("radio", "select", "checkbox"):
            ans, _ = self.qna_engine.resolve_choice_answer(
                field.label,
                field.options,
                work_location=work_location,
            )
            ans.field_type = field.field_type
            return ans

        # Default fallback
        ans = Answer(value="Yes", source="rule", confidence=0.5, field_type="unknown")
        return validate_answer(ans, field.label)

    def _enter_and_verify_input(self, elem: Any, str_val: str, max_attempts: int = 2) -> bool:
        """Enters text into an input/textarea with verification and retry (Section 8 & 9)."""
        for attempt in range(1, max_attempts + 1):
            try:
                if self.driver:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", elem)
                elem.click()
            except Exception:
                pass

            try:
                human_type(elem, str_val, clear_first=True, driver=self.driver)
            except Exception:
                try:
                    elem.send_keys(str_val)
                except Exception:
                    pass

            try:
                if self.driver:
                    self.driver.execute_script(
                        "if (arguments[0].value !== arguments[1]) { arguments[0].value = arguments[1]; }"
                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true})); "
                        "arguments[0].dispatchEvent(new Event('change', {bubbles: true})); "
                        "arguments[0].dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));",
                        elem,
                        str_val,
                    )
            except Exception:
                pass

            # Verification (Section 9)
            actual_val = ""
            try:
                actual_val = elem.get_attribute("value") or ""
            except Exception:
                pass

            if str_val.strip().lower() in actual_val.strip().lower() or (actual_val.strip() and str_val.strip()):
                return True

            time.sleep(0.3)

        return False

    def _enter_and_verify_contenteditable(self, elem: Any, str_val: str, max_attempts: int = 2) -> bool:
        """Enters text into contenteditable elements with verification and retry (Section 8 & 9)."""
        for attempt in range(1, max_attempts + 1):
            try:
                if self.driver:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", elem)
                elem.click()
            except Exception:
                pass

            try:
                elem.send_keys(Keys.CONTROL + "a")
                elem.send_keys(Keys.BACKSPACE)
            except Exception:
                pass

            try:
                elem.send_keys(str_val)
            except Exception:
                pass

            try:
                if self.driver:
                    self.driver.execute_script(
                        "arguments[0].focus();"
                        "try { document.execCommand('selectAll', false, null); } catch(e){}"
                        "try { document.execCommand('delete', false, null); } catch(e){}"
                        "try { document.execCommand('insertText', false, arguments[1]); } catch(e){}"
                        "if (arguments[0].textContent !== arguments[1]) { arguments[0].textContent = arguments[1]; }"
                        "arguments[0].dispatchEvent(new InputEvent('input', {bubbles: true, cancelable: true, inputType: 'insertText', data: arguments[1]}));"
                        "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));"
                        "arguments[0].dispatchEvent(new KeyboardEvent('keyup', {bubbles: true}));",
                        elem,
                        str_val,
                    )
            except Exception:
                pass

            # Verification (Section 9)
            actual_val = ""
            try:
                actual_val = elem.get_attribute("textContent") or getattr(elem, "text", "") or ""
            except Exception:
                pass

            if str_val.strip().lower() in actual_val.strip().lower() or (actual_val.strip() and str_val.strip()):
                return True

            time.sleep(0.3)

        return False

    def _click_chatbot_save_button(self) -> bool:
        """
        In a chatbot drawer, clicking a choice option (e.g. Yes/No radio, checkbox) or entering text
        enables the bottom 'Save' button. This helper finds and clicks the 'Save' button
        to submit the selected answer and advance the conversation.
        """
        if not self.driver:
            return False
        ctx = self.get_container()
        roots = [ctx] if ctx else []
        if not roots and self.driver:
            roots.append(self.driver)

        from selenium.webdriver.common.action_chains import ActionChains

        for attempt in range(8):
            for root in roots:
                try:
                    # 1. Primary: Locate explicit Naukri chatbot sendMsg button/container
                    cb_btns = root.find_elements(
                        By.CSS_SELECTOR,
                        "div.sendMsg, div[class*='sendMsg'], div.sendMsgbtn_container div.send, div.sendMsgbtn_container"
                    )
                    for btn in cb_btns:
                        if not btn.is_displayed():
                            continue
                        cls = (btn.get_attribute("class") or "").lower()
                        parent_cls = ""
                        try:
                            parent = btn.find_element(By.XPATH, "..")
                            parent_cls = (parent.get_attribute("class") or "").lower()
                        except Exception:
                            pass
                        is_dis = "disabled" in cls or "disabled" in parent_cls or (btn.get_attribute("aria-disabled") or "").lower() == "true"
                        if is_dis and attempt < 3:
                            continue
                        if is_dis and attempt >= 3:
                            try:
                                self.driver.execute_script(
                                    "arguments[0].classList.remove('disabled');"
                                    "if (arguments[0].parentElement) { arguments[0].parentElement.classList.remove('disabled'); }"
                                    "arguments[0].removeAttribute('disabled');"
                                    "arguments[0].removeAttribute('aria-disabled');",
                                    btn
                                )
                            except Exception:
                                pass
                        try:
                            ActionChains(self.driver).move_to_element(btn).click().perform()
                            time.sleep(0.8)
                            return True
                        except Exception:
                            try:
                                self.driver.execute_script("arguments[0].click();", btn)
                                time.sleep(0.8)
                                return True
                            except Exception:
                                pass

                    # 2. General save button fallback inside drawer
                    save_candidates = root.find_elements(
                        By.XPATH,
                        ".//*[self::button or self::div or self::a or self::span]"
                        "[normalize-space(translate(text(), 'SAVE', 'save'))='save' or "
                        "contains(translate(text(), 'SAVE', 'save'), 'save') or "
                        "contains(@class, 'save') or @type='submit']"
                    )
                    for btn in save_candidates:
                        if not btn.is_displayed():
                            continue
                        btn_cls = (btn.get_attribute("class") or "").lower()
                        btn_id = (btn.get_attribute("id") or "").lower()
                        if "save-job" in btn_cls or "save-job" in btn_id or "bookmark" in btn_cls or "styles_save" in btn_cls:
                            continue
                        txt = (btn.text or "").strip().lower()
                        if txt and len(txt) > 25:
                            continue

                        # Check whether button is enabled or disabled
                        aria_dis = (btn.get_attribute("aria-disabled") or "").lower() == "true"
                        attr_dis = btn.get_attribute("disabled") is not None
                        cls_dis = "disabled" in btn_cls

                        if not (aria_dis or attr_dis or cls_dis) or btn.is_enabled():
                            try:
                                ActionChains(self.driver).move_to_element(btn).click().perform()
                                time.sleep(0.8)
                                return True
                            except Exception:
                                try:
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    time.sleep(0.8)
                                    return True
                                except Exception:
                                    pass
                        elif attempt >= 4:
                            # If React is holding a static class or property after options were clicked
                            try:
                                self.driver.execute_script(
                                    "arguments[0].removeAttribute('disabled');"
                                    "arguments[0].classList.remove('disabled');"
                                    "arguments[0].removeAttribute('aria-disabled');"
                                    "arguments[0].click();",
                                    btn
                                )
                                time.sleep(0.8)
                                return True
                            except Exception:
                                pass
                except Exception:
                    pass
            time.sleep(0.3)
        return False

    def _submit_chat_input_if_needed(self, elem: Any) -> None:
        """Sends Enter or clicks Save/Send button if inside chatbot context."""
        try:
            placeholder = (elem.get_attribute("placeholder") or "").lower()
            elem_cls = (elem.get_attribute("class") or "").lower()
            is_chat = (
                any(w in placeholder for w in ["message", "reply", "type", "chat"])
                or any(w in elem_cls for w in ["chat", "msg", "bot"])
                or self.is_chatbot()
            )
            if is_chat:
                try:
                    elem.send_keys(Keys.ENTER)
                except Exception:
                    pass
                time.sleep(0.4)
                self._click_chatbot_save_button()
        except Exception:
            pass

    def wait_for_question_transition(
        self,
        previous_label: Optional[str] = None,
        timeout: float = 6.0,
        check_interval: float = 0.3,
    ) -> bool:
        """
        Waits for the DOM state to transition to the next question, confirmation screen,
        or final submit button. Uses DOM state changes instead of fixed sleeps (Section 13).
        """
        if not self.driver:
            return True

        start = time.time()
        clean_prev = self._clean_label(previous_label) if previous_label else ""

        while time.time() - start < timeout:
            # 1. Check if submission confirmation appeared
            if self._check_submission_confirmed():
                return True

            # 2. Check if final submit button is now present
            btn_info = self.find_action_button()
            if btn_info and btn_info[1]:
                return True

            # 3. Check if new fields are visible with a different question prompt
            new_fields = self.discover_fields()
            if new_fields:
                current_label = self._clean_label(new_fields[0].label)
                if not clean_prev or current_label != clean_prev:
                    return True

            time.sleep(check_interval)

        return False

    def fill_field(self, field: FormField, answer: Answer) -> bool:
        """Fills the resolved answer into the target DOM element with mandatory verification."""
        if not field.element or not self.driver:
            return False

        try:
            elem = field.element
            str_val = str(answer.value)
            is_ce = False
            try:
                if field.field_type == "contenteditable":
                    is_ce = True
                elif elem is not None and hasattr(elem, "get_attribute"):
                    attr = elem.get_attribute("contenteditable")
                    if isinstance(attr, str) and attr.lower() in ("true", "plaintext-only"):
                        is_ce = True
            except Exception:
                is_ce = False

            # 1a. Contenteditable Elements
            if is_ce:
                verified = self._enter_and_verify_contenteditable(elem, str_val)
                if not verified:
                    ctrl_cls = ""
                    try:
                        ctrl_cls = elem.get_attribute("class") or ""
                    except Exception:
                        pass
                    log_input_debug(
                        question=field.label,
                        detected_controls=["contenteditable"],
                        selected_control=ctrl_cls,
                        interaction="send_keys_contenteditable",
                        verification="FAILED",
                        reason="textContent remained empty after retries",
                    )
                    return False

                self._submit_chat_input_if_needed(elem)
                return True

            # 1b. Text / Number / Textarea
            elif field.field_type in ("text", "number", "textarea"):
                verified = self._enter_and_verify_input(elem, str_val)
                if not verified:
                    ctrl_name = ""
                    try:
                        ctrl_name = elem.get_attribute("name") or elem.get_attribute("id") or ""
                    except Exception:
                        pass
                    log_input_debug(
                        question=field.label,
                        detected_controls=[field.field_type],
                        selected_control=ctrl_name,
                        interaction="send_keys",
                        verification="FAILED",
                        reason="value remained empty after retries",
                    )
                    return False

                self._submit_chat_input_if_needed(elem)
                return True

            # 2. Radio button / Chip
            elif field.field_type == "radio":
                target_val = str(answer.value).lower().strip()
                target_elem = None

                for i, opt in enumerate(field.options):
                    if opt.lower().strip() == target_val or target_val in opt.lower().strip():
                        if i < len(field.raw_elements):
                            target_elem = field.raw_elements[i]
                            break

                if not target_elem:
                    if any(w in target_val for w in ["never", "no", "none", "neither"]):
                        for i, opt in enumerate(field.options):
                            if any(w in opt.lower() for w in ["never served", "never", "no", "none", "neither", "n/a", "not applicable"]):
                                if i < len(field.raw_elements):
                                    target_elem = field.raw_elements[i]
                                    break
                    elif "yes" in target_val:
                        for i, opt in enumerate(field.options):
                            if any(w in opt.lower() for w in ["yes", "agree", "have", "authorized"]):
                                if i < len(field.raw_elements):
                                    target_elem = field.raw_elements[i]
                                    break

                # CRITICAL SAFETY GUARD:
                # If target_val was negative ("never", "no", "none"), DO NOT fall back to raw_elements[0]
                # if raw_elements[0] is positive ("yes", "currently", "previously")!
                is_negative_intent = any(w in target_val for w in ["never", "no", "none", "neither"])
                if not target_elem and field.raw_elements:
                    first_opt_lower = field.options[0].lower() if field.options else ""
                    if is_negative_intent and any(pos in first_opt_lower for pos in ["yes", "currently", "previously"]):
                        print_lg(f"[NaukriForm] Refusing fallback to positive option '{field.options[0]}' for negative intent '{target_val}'")
                    else:
                        target_elem = field.raw_elements[0]

                if target_elem:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", target_elem)
                    except Exception:
                        pass
                    time.sleep(0.2)

                    try:
                        target_elem.click()
                    except Exception:
                        pass

                    try:
                        self.driver.execute_script("""
                            var el = arguments[0];
                            
                            // Find outermost clickable option container
                            var container = el;
                            var p = el.parentElement;
                            while (p && p !== document.body) {
                                var cls = (p.className || '').toString().toLowerCase();
                                var role = (p.getAttribute('role') || '').toLowerCase();
                                var tag = p.tagName.toLowerCase();
                                if (tag === 'label' || role === 'radio' || cls.includes('option') || cls.includes('radio') || cls.includes('choice') || cls.includes('pill') || cls.includes('chip')) {
                                    container = p;
                                }
                                p = p.parentElement;
                            }
                            
                            // Dispatch mouse events on container
                            container.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: window }));
                            container.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                            container.focus();
                            container.click();
                            container.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                            
                            if (container !== el) {
                                el.dispatchEvent(new MouseEvent('mouseover', { bubbles: true, cancelable: true, view: window }));
                                el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                                el.focus();
                                el.click();
                                el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                            }
                            
                            // Find and check any radio input
                            var radio = container.querySelector("input[type='radio']") || 
                                        el.querySelector("input[type='radio']") || 
                                        (container.tagName === 'INPUT' && container.type === 'radio' ? container : null) || 
                                        (el.tagName === 'INPUT' && el.type === 'radio' ? el : null);
                            if (!radio && container.getAttribute('for')) {
                                radio = document.getElementById(container.getAttribute('for'));
                            }
                            if (!radio && el.previousElementSibling && el.previousElementSibling.type === 'radio') {
                                radio = el.previousElementSibling;
                            }
                            if (radio) {
                                radio.checked = true;
                                radio.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                radio.dispatchEvent(new Event('change', { bubbles: true }));
                                radio.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        """, target_elem)
                    except Exception as e:
                        print_lg(f"[NaukriForm] Script click notice: {e}")

                    time.sleep(0.5)

                    # In chatbot drawer, clicking a radio option requires clicking the bottom 'Save' button!
                    if self.is_chatbot():
                        self._click_chatbot_save_button()

                    return True
                return False

            # 3. Checkbox
            elif field.field_type == "checkbox":
                target_val = str(answer.value).lower().strip()
                target_elem = None

                # Find matched option in field.options / raw_elements
                for i, opt in enumerate(field.options):
                    opt_clean = opt.lower().strip()
                    if opt_clean == target_val or target_val in opt_clean or opt_clean in target_val:
                        if i < len(field.raw_elements):
                            target_elem = field.raw_elements[i]
                            break

                if not target_elem:
                    if any(w in target_val for w in ["yes", "agree", "true", "1"]):
                        for i, opt in enumerate(field.options):
                            if any(w in opt.lower() for w in ["yes", "agree", "true"]):
                                if i < len(field.raw_elements):
                                    target_elem = field.raw_elements[i]
                                    break
                    if not target_elem and field.raw_elements:
                        target_elem = field.raw_elements[0]
                    elif not target_elem:
                        target_elem = field.element

                if target_elem:
                    try:
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", target_elem)
                    except Exception:
                        pass
                    time.sleep(0.2)

                    try:
                        target_elem.click()
                    except Exception:
                        try:
                            self.driver.execute_script("arguments[0].click();", target_elem)
                        except Exception:
                            pass

                    # Also ensure input checkbox is checked
                    try:
                        self.driver.execute_script("""
                            var el = arguments[0];
                            var cb = el.querySelector("input[type='checkbox']") || 
                                     (el.tagName === 'INPUT' && el.type === 'checkbox' ? el : null);
                            if (!cb && el.getAttribute('for')) {
                                cb = document.getElementById(el.getAttribute('for'));
                            }
                            if (cb && !cb.checked) {
                                cb.checked = true;
                                cb.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                cb.dispatchEvent(new Event('change', { bubbles: true }));
                            }
                        """, target_elem)
                    except Exception:
                        pass

                    time.sleep(0.4)
                    if self.is_chatbot():
                        self._click_chatbot_save_button()
                    return True
                return False

            # 4. Select / Dropdown
            elif field.field_type == "select":
                elem = field.element
                str_val = str(answer.value).strip()
                tag_name = elem.tag_name.lower() if hasattr(elem, "tag_name") else ""
                if tag_name == "select":
                    sel = Select(elem)
                    try:
                        sel.select_by_visible_text(str_val)
                        return True
                    except Exception:
                        for opt in field.options:
                            if str_val.lower() in opt.lower():
                                sel.select_by_visible_text(opt)
                                return True
                        if field.options:
                            sel.select_by_visible_text(field.options[0])
                            return True
                else:
                    try:
                        elem.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", elem)
                    for i, opt in enumerate(field.options):
                        if str_val.lower() in opt.lower():
                            if i < len(field.raw_elements):
                                try:
                                    field.raw_elements[i].click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", field.raw_elements[i])
                                return True
                    return True

            # 5. File upload
            elif field.field_type == "file":
                elem = field.element
                file_path = str(answer.value).strip()
                if file_path and os.path.exists(file_path):
                    elem.send_keys(os.path.abspath(file_path))
                    return True
                elif file_path:
                    print_lg(f"[NaukriForm] File upload skipped; file not found on disk: {file_path}")
                    return True

        except Exception as e:
            print_lg(f"[NaukriForm] Error filling field '{field.label}': {e}")
            return False

        return False

    def validate(self, field: FormField, answer: Answer) -> bool:
        """Validates that the answer satisfies domain rules and required field constraints."""
        if not answer.validated:
            print_lg(f"[NaukriForm] Validation failed for '{field.label}': {answer.validation_error}")
            return False
        if field.required and (answer.value is None or str(answer.value).strip() == ""):
            print_lg(f"[NaukriForm] Required field '{field.label}' has empty answer")
            return False
        return True

    def is_final_submit(self, button_elem: Any) -> bool:
        """Determines whether a button represents the final submission action."""
        if not button_elem:
            return False

        text = (button_elem.text or "").strip().lower()
        title = (button_elem.get_attribute("title") or "").strip().lower()
        btn_type = (button_elem.get_attribute("type") or "").strip().lower()
        classes = (button_elem.get_attribute("class") or "").strip().lower()
        btn_id = (button_elem.get_attribute("id") or "").strip().lower()
        combined = f"{text} {title} {classes} {btn_id}"

        # If it explicitly says "next", "continue", or "save", it's an intermediate step
        if any(w in text for w in ["next", "continue", "save and next", "save & next", "save"]):
            return False

        # If it matches final submission keywords
        if any(w in text for w in ["submit", "apply", "finish", "done"]):
            return True

        if btn_type == "submit" and "save" not in text:
            return True

        for sel_kw in ["submit", "apply"]:
            if sel_kw in combined and "save" not in combined:
                return True

        return False

    def find_action_button(self, container: Optional[Any] = None) -> Optional[Tuple[Any, bool]]:
        """Locates the primary action button (Next, Save, or Submit) and determines if it is final submit."""
        if not self.driver:
            return None

        ctx = container or self.get_container() or self.driver

        # First check intermediate navigation buttons (including 'Save' in chatbot)
        for sel in FORM_NEXT_BUTTON_SELECTORS:
            try:
                btns = ctx.find_elements(By.CSS_SELECTOR, sel)
                for b in btns:
                    if b.is_displayed():
                        text = (b.text or "").strip().lower()
                        if any(w in text for w in ["save", "next", "continue"]):
                            return (b, False)
            except Exception:
                continue

        # Check XPath for text-based "Save" or "Next" button
        try:
            save_btns = ctx.find_elements(
                By.XPATH,
                ".//button[normalize-space(translate(text(), 'SAVE', 'save'))='save'] | "
                ".//button[contains(translate(text(), 'NEXT', 'next'), 'next')] | "
                ".//*[contains(@class, 'save') and (self::button or self::div or @role='button')]"
            )
            for b in save_btns:
                if b.is_displayed():
                    return (b, False)
        except Exception:
            pass

        # Then check explicit submit buttons
        for sel in FORM_SUBMIT_BUTTON_SELECTORS:
            try:
                btns = ctx.find_elements(By.CSS_SELECTOR, sel)
                for b in btns:
                    if b.is_displayed():
                        is_final = self.is_final_submit(b)
                        return (b, is_final)
            except Exception:
                continue

        return None

    def next(self) -> Tuple[bool, str]:
        """
        Advances to the next form step if an intermediate navigation button is present.

        CRITICAL SAFETY RULE (Phase 10 & 11):
        If the action button is a final submit button, it STOPS immediately without clicking!
        """
        btn_info = self.find_action_button()
        if not btn_info:
            return (False, "NO_BUTTON")

        btn, is_final = btn_info
        if is_final:
            print_lg("[NaukriForm] Safety Gate: Final submit button detected. STOPPING before submission.")
            return (False, "STOPPED_AT_SUBMIT")

        # Intermediate Next/Continue/Save button
        try:
            btn.click()
        except Exception:
            try:
                self.driver.execute_script("arguments[0].removeAttribute('disabled'); arguments[0].click();", btn)
            except Exception as e:
                print_lg(f"[NaukriForm] Failed clicking action button: {e}")
                return (False, f"CLICK_FAILED: {e}")

        import time
        time.sleep(1.5)  # Allow chatbot or form animation to render the next question
        return (True, "NAVIGATED_NEXT")

    def _check_submission_error(self) -> Optional[str]:
        """Checks if active DOM or modal shows application rejection or error."""
        if not self.driver:
            return None
        container = self.get_container()
        combined_txt = ""
        try:
            body_elem = self.driver.find_element(By.TAG_NAME, "body")
            body_txt = str(body_elem.text or "").lower() if hasattr(body_elem, "text") and isinstance(body_elem.text, str) else ""
            cont_txt = str(container.text or "").lower() if container and hasattr(container, "text") and isinstance(container.text, str) else ""
            combined_txt = f"{cont_txt} {body_txt}".strip()
            for err in SUBMISSION_ERROR_TEXTS:
                if err in combined_txt:
                    return err
        except Exception:
            pass
        return None

    def _check_submission_confirmed(self) -> bool:
        """Checks if active DOM or modal shows application submission confirmation.
        
        CRITICAL TWO-STAGE CHATBOT CONFIRMATION INVARIANT:
        1. When a chatbot is active (drawer is open):
           ONLY returns True if the chatbot drawer contains a genuine completion text
           (e.g., 'Thank you for your response' / 'Thank you for your responses').
           Sets self._chatbot_thank_you_detected = True.
           NEVER checks main-page background text or buttons while the drawer is open.
        2. When a chatbot flow was used and the drawer has closed:
           ONLY returns True if self._chatbot_thank_you_detected is True AND
           the main page displays unambiguous post-submission confirmation
           (e.g., button is 'Applied' or confirmation message).
           If the drawer closed WITHOUT self._chatbot_thank_you_detected, returns False!
        3. For non-chatbot forms:
           Checks genuine confirmation elements or unambiguous post-submission banners.
        """
        if not self.driver:
            return False
        container = self.get_container()
        in_chatbot = bool(container and self.is_chatbot(container)) or (self._chatbot_mode and container is not None)

        # 0. Check for rejection or error indicators first
        combined_txt = ""
        try:
            body_elem = self.driver.find_element(By.TAG_NAME, "body")
            body_txt = str(body_elem.text or "").lower() if hasattr(body_elem, "text") and isinstance(body_elem.text, str) else ""
            cont_txt = str(container.text or "").lower() if container and hasattr(container, "text") and isinstance(container.text, str) else ""
            combined_txt = f"{cont_txt} {body_txt}".strip()
            for err in SUBMISSION_ERROR_TEXTS:
                if err in combined_txt:
                    return False
        except Exception:
            pass

        # Case 1: Inside an active drawer or container
        if container:
            try:
                drawer_txt = str(container.text or "").lower()
                for phrase in CHATBOT_CONFIRMATION_TEXTS:
                    if phrase in drawer_txt:
                        self._chatbot_thank_you_detected = True
                        return True
            except Exception:
                pass
            if in_chatbot:
                # Inside the open chatbot drawer, do NOT match against background main-page text or buttons
                return False

        # Case 2: Chatbot mode was active and drawer has now closed (Stage 2 check)
        if self._chatbot_mode:
            # Stage 1 MUST have been observed in the drawer!
            if not self._chatbot_thank_you_detected:
                return False

            # Verify post-application confirmation on the main page after drawer closed
            for sel in APPLIED_BUTTON_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed():
                            txt = (e.text or "").strip().lower()
                            if "applied" in txt:
                                return True
                except Exception:
                    pass

            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_txt = str(body_elem.text or "").lower()
                for phrase in SUBMISSION_CONFIRMATION_TEXTS:
                    if phrase in body_txt:
                        return True
            except Exception:
                pass

            return False

        # Case 3: Regular modal / non-chatbot flow
        if container:
            for sel in SUBMISSION_SUCCESS_SELECTORS:
                try:
                    elems = container.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed():
                            txt = (e.text or "").strip().lower()
                            if not any(err in txt for err in SUBMISSION_ERROR_TEXTS):
                                return True
                except Exception:
                    pass

        # Case 4: Main page check for direct/non-chatbot apply
        if not container:
            for sel in APPLIED_BUTTON_SELECTORS:
                try:
                    elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for e in elems:
                        if e.is_displayed():
                            txt = (e.text or "").strip().lower()
                            if "applied" in txt:
                                return True
                except Exception:
                    pass

            try:
                body_elem = self.driver.find_element(By.TAG_NAME, "body")
                body_txt = str(body_elem.text or "").lower()
                for phrase in SUBMISSION_CONFIRMATION_TEXTS:
                    if phrase in body_txt:
                        return True
            except Exception:
                pass

        return False

    def wait_for_chatbot_turn_transition(
        self,
        previous_question: Optional[str] = None,
        timeout: float = 8.0,
        check_interval: float = 0.3,
    ) -> Tuple[str, str]:
        """
        In Naukri's chatbot questionnaire, after answering a question and clicking Save:
        Actively polls for server response and DOM transition over timeout.
        Returns one of:
        - ("CONFIRMED", reason): all questions answered ("Thank you for your response", "Applied to", etc.)
        - ("ERROR", reason): application rejected or error message appeared ("incomplete information", etc.)
        - ("NEXT_QUESTION", label): new question bubble and interactive options appeared
        - ("TIMEOUT", reason): no transition detected within timeout
        """
        if not self.driver:
            return ("TIMEOUT", "Driver unavailable")

        start = time.time()
        clean_prev = self._clean_label(previous_question) if previous_question else ""

        # Brief settle time to allow Naukri client to register the Save click
        time.sleep(0.6)

        while time.time() - start < timeout:
            # 1. Check for hard error or rejection first
            err = self._check_submission_error()
            if err:
                return ("ERROR", err)

            # 2. Check for confirmation in drawer or main page
            ctx = self.get_container()
            if ctx:
                try:
                    drawer_txt = (ctx.text or "").lower()
                    for phrase in CHATBOT_CONFIRMATION_TEXTS:
                        if phrase in drawer_txt:
                            phrase_display = phrase.capitalize()
                            return ("CONFIRMED", f"Chatbot showed '{phrase_display}'")
                except Exception:
                    pass

            if self._check_submission_confirmed():
                return ("CONFIRMED", "Submission confirmed")

            # 3. Check if typing indicator or spinner is animating
            typing_active = False
            search_ctx = ctx or self.driver
            try:
                dots = search_ctx.find_elements(
                    By.XPATH,
                    ".//*[contains(@class, 'typing') or contains(@class, 'dot') or contains(@class, 'loader') or contains(@class, 'spinner')] | "
                    ".//*[contains(text(), '•') or contains(text(), '...')]"
                )
                for d in dots:
                    try:
                        if d.is_displayed():
                            typing_active = True
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            if typing_active:
                time.sleep(check_interval)
                continue

            # 4. Check if a NEW question and its fields have appeared
            current_q = self._get_latest_chatbot_question(ctx)
            clean_curr = self._clean_label(current_q) if current_q else ""

            fields = self.discover_fields(container=ctx)
            if fields:
                # If label changed, or if interactive elements are visible in drawer
                if (clean_curr and clean_curr != clean_prev) or (fields[0].label and self._clean_label(fields[0].label) != clean_prev):
                    return ("NEXT_QUESTION", fields[0].label or clean_curr)
                # If label is generic/same but interactive input controls are present
                for f in fields:
                    if f.field_type in ("radio", "checkbox") and f.raw_elements:
                        return ("NEXT_QUESTION", f.label or clean_curr or "Question")
                    elif f.field_type in ("text", "textarea", "contenteditable") and f.element:
                        return ("NEXT_QUESTION", f.label or clean_curr or "Question")

            # 5. Check if drawer closed and main page shows success
            if not ctx or not self.is_chatbot(ctx):
                time.sleep(1.0)
                if self._check_submission_confirmed():
                    return ("CONFIRMED", "Chatbot drawer closed and application confirmed")
                for _ in range(3):
                    time.sleep(1.0)
                    if self._check_submission_confirmed():
                        return ("CONFIRMED", "Chatbot drawer closed and application confirmed")

            time.sleep(check_interval)

        # Timeout reached: final check
        err = self._check_submission_error()
        if err:
            return ("ERROR", err)
        if self._check_submission_confirmed():
            return ("CONFIRMED", "Submission confirmed at transition timeout")

        ctx = self.get_container()
        if not ctx or not self.is_chatbot(ctx):
            for _ in range(3):
                time.sleep(1.0)
                if self._check_submission_confirmed():
                    return ("CONFIRMED", "Chatbot drawer closed and application confirmed")

        fields = self.discover_fields(container=ctx)
        if fields:
            return ("NEXT_QUESTION", fields[0].label or "Question")

        return ("TIMEOUT", "Transition timed out")

    def _handle_chatbot_completion(self, max_wait: float = 4.0) -> bool:
        """
        When the chatbot displays 'Thank you for your response', Naukri automatically
        closes the drawer and reveals the confirmation banner on the main page (Applied to "...").
        This helper waits for auto-close, or cleanly clicks the close button if it lingers.
        """
        if not self.driver:
            return False

        start = time.time()
        while time.time() - start < max_wait:
            ctx = self.get_container()
            if not ctx or not self.is_chatbot(ctx):
                time.sleep(0.5)
                return True
            time.sleep(0.4)

        # If drawer is still open, click the close button ('X')
        ctx = self.get_container()
        if ctx:
            for sel in MODAL_CLOSE_BUTTONS:
                try:
                    btns = ctx.find_elements(By.CSS_SELECTOR, sel)
                    for b in btns:
                        if b.is_displayed():
                            try:
                                b.click()
                            except Exception:
                                self.driver.execute_script("arguments[0].click();", b)
                            time.sleep(0.8)
                            return True
                except Exception:
                    pass
        return False

    def correct_military_preset(self, container: Optional[Any] = None) -> bool:
        """
        If Naukri's chatbot pre-filled 'Currently serving' from a prior session,
        clicks the edit pencil icon next to it and corrects the answer to 'Never served'.
        """
        if not self.driver:
            return False
        ctx = container or self.get_container()
        if not ctx:
            return False
        try:
            # Look for bubbles or elements containing "Currently serving"
            serving_nodes = ctx.find_elements(
                By.XPATH,
                ".//*[contains(translate(text(), 'CURRENTLY SERVING', 'currently serving'), 'currently serving')]"
            )
            for node in serving_nodes:
                if not node.is_displayed():
                    continue
                # Find pencil or edit icon near this response
                edit_candidates = node.find_elements(
                    By.XPATH,
                    "./preceding-sibling::*[contains(@class, 'edit') or contains(@class, 'icon') or self::button or self::span] | "
                    "./following-sibling::*[contains(@class, 'edit') or contains(@class, 'icon') or self::button or self::span] | "
                    "..//*[contains(@class, 'edit') or contains(@class, 'pencil') or contains(@class, 'icon-edit')] | "
                    "./ancestor::*[contains(@class, 'user') or contains(@class, 'right')][1]//*[contains(@class, 'edit') or contains(@class, 'pencil') or self::button]"
                )
                for edit_btn in edit_candidates:
                    if edit_btn.is_displayed():
                        try:
                            edit_btn.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", edit_btn)
                        time.sleep(1.0)
                        # Now find and click the 'Never served' chip
                        never_chips = ctx.find_elements(
                            By.XPATH,
                            ".//*[normalize-space(translate(text(), 'NEVER SERVED', 'never served'))='never served' or contains(translate(text(), 'NEVER SERVED', 'never served'), 'never served')]"
                        )
                        for nc in never_chips:
                            if nc.is_displayed():
                                try:
                                    nc.click()
                                except Exception:
                                    self.driver.execute_script("arguments[0].click();", nc)
                                time.sleep(1.0)
                                print_lg("[NaukriForm] Successfully corrected pre-filled military preset to 'Never served'.")
                                return True
        except Exception as e:
            print_lg(f"[NaukriForm] Notice during military preset check: {e}")
        return False

    def fill_form(
        self,
        job_description: Optional[str] = None,
        work_location: Optional[str] = None,
        max_steps: int = 15,
    ) -> Dict[str, Any]:
        """
        Orchestrates full form interaction:
        Discovers fields, answers, validates, fills, and advances step-by-step
        until reaching the final submit button, detecting confirmation, or exhausting form steps.

        Guaranteed to STOP before final submission.
        """
        filled_records = []
        is_chat = self.is_chatbot()
        self._chatbot_mode = bool(is_chat)
        self._chatbot_thank_you_detected = False
        if is_chat:
            self.correct_military_preset()
            self.wait_for_chatbot_ready(timeout=6.0)

        consecutive_same_question_count = 0
        last_question_label = None

        for step in range(max_steps):
            # Dynamic chatbot check at each step
            if not is_chat and self.is_chatbot():
                is_chat = True
                self._chatbot_mode = True
                self.wait_for_chatbot_ready(timeout=4.0)

            # 0. Check for application error / rejection first
            err_msg = self._check_submission_error()
            if err_msg:
                print_lg(f"[NaukriForm] Application rejection/error detected at step {step}: '{err_msg}'")
                return {
                    "status": "FAILED",
                    "reason": f"Application rejected by Naukri: {err_msg}",
                    "steps": step,
                    "filled_fields": filled_records,
                }

            # 1. Check if submission is already confirmed before discovering fields
            if self._check_submission_confirmed():
                if is_chat or self.is_chatbot():
                    self._handle_chatbot_completion()
                return {
                    "status": "SUBMITTED",
                    "reason": "Chatbot confirmed submission",
                    "steps": step,
                    "filled_fields": filled_records,
                }

            fields = self.discover_fields()
            if not fields:
                if is_chat:
                    # Active wait for chatbot to render next question or end message
                    self.wait_for_chatbot_ready(timeout=5.0)
                    if self._check_submission_confirmed():
                        self._handle_chatbot_completion()
                        return {
                            "status": "SUBMITTED",
                            "reason": "Chatbot confirmed submission",
                            "steps": step,
                            "filled_fields": filled_records,
                        }
                    err_msg = self._check_submission_error()
                    if err_msg:
                        return {
                            "status": "FAILED",
                            "reason": f"Application rejected by Naukri: {err_msg}",
                            "steps": step,
                            "filled_fields": filled_records,
                        }
                    fields = self.discover_fields()

                if not fields:
                    if is_chat:
                        if self._check_submission_confirmed():
                            self._handle_chatbot_completion()
                            return {
                                "status": "SUBMITTED",
                                "reason": "Chatbot confirmed submission",
                                "steps": step,
                                "filled_fields": filled_records,
                            }
                        err_msg = self._check_submission_error()
                        if err_msg:
                            return {
                                "status": "FAILED",
                                "reason": f"Application rejected by Naukri: {err_msg}",
                                "steps": step,
                                "filled_fields": filled_records,
                            }
                        btn_info = self.find_action_button()
                        if btn_info and btn_info[1]:  # final submit
                            return {
                                "status": "READY_TO_SUBMIT",
                                "steps": step,
                                "filled_fields": filled_records,
                            }
                        break
                    else:
                        btn_info = self.find_action_button()
                        if btn_info:
                            btn, is_final = btn_info
                            if is_final:
                                return {
                                    "status": "READY_TO_SUBMIT",
                                    "steps": step,
                                    "filled_fields": filled_records,
                                }
                            else:
                                # Intermediate Next/Save button
                                advanced, _ = self.next()
                                if advanced:
                                    self.wait_for_question_transition(previous_label=last_question_label, timeout=6.0)
                                    continue

                    # Double check if confirmation arrived
                    if self._check_submission_confirmed():
                        if is_chat:
                            self._handle_chatbot_completion()
                        return {
                            "status": "SUBMITTED",
                            "reason": "Chatbot confirmed submission",
                            "steps": step,
                            "filled_fields": filled_records,
                        }
                    # No fields and no buttons and no confirmation -> finished form
                    break

            # Loop protection: detect if stuck on the exact same question
            current_q_label = self._clean_label(fields[0].label) if fields else ""
            if current_q_label and current_q_label == last_question_label:
                consecutive_same_question_count += 1
                if consecutive_same_question_count >= 3:
                    print_lg(f"[NaukriForm] Loop guard triggered: stuck on '{current_q_label}' for 3 steps.")
                    return {
                        "status": "INPUT_FAILED",
                        "field": current_q_label,
                        "error": f"Stuck on same question '{current_q_label}' for 3 steps without DOM transition",
                        "filled_fields": filled_records,
                    }
            else:
                consecutive_same_question_count = 1
                last_question_label = current_q_label

            for f in fields:
                ans = self.answer(f, job_description=job_description, work_location=work_location)
                if not self.validate(f, ans):
                    return {
                        "status": "VALIDATION_FAILED",
                        "field": f.label,
                        "error": ans.validation_error or "Validation failed",
                        "filled_fields": filled_records,
                    }
                success = self.fill_field(f, ans)
                if not success:
                    print_lg(f"[NaukriForm] Input entry / verification failed for field '{f.label}'")
                    return {
                        "status": "INPUT_FAILED",
                        "field": f.label,
                        "error": f"Failed verifying input for question '{f.label}'",
                        "filled_fields": filled_records,
                    }

                print_lg(f"[NaukriForm] Step {step+1}: Filled field '{f.label}' ({f.field_type}) with '{ans.value}' [source: {ans.source}]")
                if success and f.label and hasattr(self.qna_engine, "save_learned_answer"):
                    try:
                        self.qna_engine.save_learned_answer(f.label, str(ans.value), answer_type=f.field_type, source=ans.source)
                    except Exception:
                        pass
                filled_records.append({
                    "field": f.label,
                    "type": f.field_type,
                    "value": ans.value,
                    "source": ans.source,
                    "confidence": ans.confidence,
                    "success": success,
                })

            # Check if submission was confirmed right after answering
            if self._check_submission_confirmed():
                if is_chat:
                    self._handle_chatbot_completion()
                return {
                    "status": "SUBMITTED",
                    "reason": "Chatbot confirmed submission after answering",
                    "steps": step + 1,
                    "filled_fields": filled_records,
                }

            if is_chat or self.is_chatbot():
                is_chat = True
                # In chatbot, the current question was answered and Save was clicked.
                # DO NOT call self.next() (which re-clicks Save prematurely)!
                # Actively wait for turn transition (Question 2, confirmation, or rejection):
                trans_status, trans_detail = self.wait_for_chatbot_turn_transition(
                    previous_question=last_question_label,
                    timeout=10.0
                )
                print_lg(f"[NaukriForm] Chatbot step {step+1} transition: {trans_status} ({trans_detail})")

                if trans_status == "CONFIRMED":
                    self._chatbot_thank_you_detected = True
                    self._handle_chatbot_completion(max_wait=6.0)
                    # Verify Stage 2: main page post-application confirmation after drawer closes
                    confirmed_stage2 = False
                    for _ in range(4):
                        time.sleep(1.0)
                        if self._check_submission_confirmed():
                            confirmed_stage2 = True
                            break
                    if confirmed_stage2 or not self.get_container():
                        return {
                            "status": "SUBMITTED",
                            "reason": f"Chatbot confirmed submission: {trans_detail}",
                            "steps": step + 1,
                            "filled_fields": filled_records,
                        }
                    else:
                        return {
                            "status": "FAILED",
                            "reason": "Chatbot confirmed submission but drawer did not close cleanly",
                            "steps": step + 1,
                            "filled_fields": filled_records,
                        }

                if trans_status == "ERROR":
                    print_lg(f"[NaukriForm] Chatbot application rejected: {trans_detail}")
                    return {
                        "status": "FAILED",
                        "reason": f"Application rejected by Naukri: {trans_detail}",
                        "steps": step + 1,
                        "filled_fields": filled_records,
                    }

                if trans_status == "NEXT_QUESTION":
                    # Transitioned to next question bubble & choices!
                    # Continue loop to let step + 1 discover, answer, and save it.
                    continue

                # Check if drawer has closed
                ctx = self.get_container()
                if not ctx or not self.is_chatbot(ctx):
                    if self._chatbot_thank_you_detected:
                        for _ in range(3):
                            time.sleep(1.0)
                            if self._check_submission_confirmed():
                                return {
                                    "status": "SUBMITTED",
                                    "reason": "Chatbot drawer closed and application confirmed",
                                    "steps": step + 1,
                                    "filled_fields": filled_records,
                                }
                    else:
                        return {
                            "status": "FAILED",
                            "reason": "Chatbot drawer closed without receiving 'Thank you for your response' confirmation",
                            "steps": step + 1,
                            "filled_fields": filled_records,
                        }

                # Fallback check if confirmation arrived
                if self._check_submission_confirmed():
                    self._handle_chatbot_completion()
                    return {
                        "status": "SUBMITTED",
                        "reason": "Chatbot confirmed submission",
                        "steps": step + 1,
                        "filled_fields": filled_records,
                    }
                continue
            else:
                advanced, reason = self.next()
                if reason == "STOPPED_AT_SUBMIT":
                    return {
                        "status": "READY_TO_SUBMIT",
                        "steps": step + 1,
                        "filled_fields": filled_records,
                    }
                if advanced:
                    self.wait_for_question_transition(previous_label=last_question_label, timeout=6.0)
                else:
                    if self._check_submission_confirmed():
                        return {
                            "status": "SUBMITTED",
                            "reason": "Chatbot confirmed submission",
                            "steps": step + 1,
                            "filled_fields": filled_records,
                        }
                    new_fields = self.discover_fields()
                    if new_fields:
                        continue

                    btn_info = self.find_action_button()
                    if btn_info and btn_info[1]:  # final submit button appeared
                        return {
                            "status": "READY_TO_SUBMIT",
                            "steps": step + 1,
                            "filled_fields": filled_records,
                        }
                    break

        # Final check if confirmation appeared after loop
        if self._check_submission_confirmed():
            if is_chat:
                self._handle_chatbot_completion()
            return {
                "status": "SUBMITTED",
                "reason": "Chatbot confirmed submission",
                "steps": max_steps,
                "filled_fields": filled_records,
            }

        return {
            "status": "READY_TO_SUBMIT",
            "steps": len(filled_records),
            "filled_fields": filled_records,
        }
