'''
Foundit Search Engine
Constructs search query URLs with filters and extracts job card DOM elements on Foundit India (foundit.in).
'''

import re
import time
import random
from urllib.parse import urlencode
from typing import Optional, List, Dict, Any
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, TimeoutException

from platforms.foundit.selectors import (
    HOME_URL,
    SEARCH_BASE_URL,
    CARD_CONTAINER_SELECTOR,
    ACTIVE_CARD_SELECTOR,
    PAGINATION_CONTAINER,
    PAGINATION_NEXT_BUTTONS,
    DETAILS_CONTAINER_SELECTORS,
    HOME_SKILLS_INPUT,
    HOME_LOCATION_INPUT,
    HOME_EXPERIENCE_INPUT,
    HOME_SEARCH_BUTTON,
    SRP_SKILLS_INPUT,
    SRP_LOCATION_INPUT,
    SRP_EXPERIENCE_INPUT,
    SRP_SEARCH_BUTTON,
    QUICK_APPLY_TOGGLE,
    QUICK_APPLY_TOGGLE_LABEL,
    SIDEBAR_FILTER_CONTAINER,
    SIDEBAR_EXPERIENCE_SECTION,
    SIDEBAR_APPLIED_CHIPS,
)
from modules.helpers import print_lg


def slugify(text: str) -> str:
    """Converts a phrase into a clean URL-friendly slug."""
    cleaned = re.sub(r'[/\\_]+', ' ', text)
    cleaned = re.sub(r'[^a-zA-Z0-9\s-]', '', cleaned)
    slug = re.sub(r'[\s-]+', '-', cleaned).strip('-').lower()
    return slug


slugify_query = slugify


def get_pagination_offset(page: int) -> int:
    """Returns the Foundit 15-card offset for a 1-based page number."""
    if page <= 1:
        return 0
    return (page - 1) * 15


def build_search_url(
    keyword: str,
    location: Optional[str] = None,
    experience_years: Optional[int] = None,
    freshness_days: Optional[int] = None,
    page: int = 1,
) -> str:
    """Builds a verified, canonical search URL for Foundit (Screenshot 2).
    Generates standard search view with the left filter sidebar and Quick Apply toggle:
    e.g. https://www.foundit.in/search/rpa-developer-jobs-in-india?query=rpa+developer&location=india
    Filters such as Experience are applied through the left sidebar UI, avoiding the split-screen /srp/results mode.
    """
    kw_slug = slugify(keyword) if keyword else ""
    loc_slug = slugify(location) if location and location.strip() else ""

    if kw_slug and loc_slug:
        slug_path = f"{kw_slug}-jobs-in-{loc_slug}"
    elif kw_slug:
        slug_path = f"{kw_slug}-jobs"
    elif loc_slug:
        slug_path = f"jobs-in-{loc_slug}"
    else:
        slug_path = "jobs"

    base_url = f"{SEARCH_BASE_URL}/{slug_path}"

    params: Dict[str, Any] = {}
    if keyword and keyword.strip():
        params["query"] = keyword.strip()
    if location and location.strip():
        params["location"] = location.strip()

    if experience_years is not None and experience_years >= 0:
        params["experience"] = str(experience_years)

    query_string = urlencode(params)
    return f"{base_url}?{query_string}" if query_string else base_url


def is_valid_job_card(card_elem: WebElement) -> bool:
    """Validates that a DOM element is an actual job listing card, rejecting headers, banners, and filters."""
    if not card_elem:
        return False
    try:
        if not card_elem.is_displayed():
            return False

        cls = (card_elem.get_attribute("class") or "").lower()
        if any(ign in cls for ign in ["filter", "header", "srprightcontainer", "cardscontainer", "notification"]):
            return False

        text = (card_elem.get_attribute("innerText") or card_elem.text or "").strip()
        if not text or len(text) < 20:
            return False

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return False

        first_line = lines[0].lower()
        reject_starters = [
            "showing",
            "results for",
            "select all",
            "all filter",
            "real-time notification",
            "scan to download",
            "location",
        ]
        if any(first_line.startswith(rej) or rej in first_line for rej in reject_starters):
            return False

        if re.search(r'showing\s+\d+\s+results', text, re.I):
            return False

        # Must contain typical job card elements or indicators
        lower_full = text.lower()
        has_job_indicator = any(
            ind in lower_full
            for ind in ["yrs", "year", "skills:", "quick apply", "save", "fresher", "posted"]
        )
        if not has_job_indicator:
            return False

        return True
    except Exception:
        return False


class FounditSearch:
    """Executes searches and discovers job listing elements on Foundit via UI inputs."""

    def __init__(self, browser: Any):
        self.browser = browser

    @property
    def driver(self):
        return getattr(self.browser, "driver", None)

    def close_open_modals(self) -> None:
        """Closes any transient popups, dropdowns, or location modals."""
        if not self.driver:
            return
        try:
            from selenium.webdriver.common.keys import Keys
            active = self.driver.switch_to.active_element
            if active:
                active.send_keys(Keys.ESCAPE)
                time.sleep(0.2)
        except Exception:
            pass

        from platforms.foundit.selectors import MODAL_CLOSE_BUTTONS
        for sel in MODAL_CLOSE_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            self.driver.execute_script("arguments[0].click();", el)
                        time.sleep(0.2)
            except Exception:
                continue

    def search_via_ui(
        self,
        keyword: str,
        location: Optional[str] = "India",
        experience_years: Optional[int] = None,
        freshness_days: Optional[int] = None,
        quick_apply: bool = True,
    ) -> bool:
        """Applies search filters directly through Foundit UI input fields and buttons."""
        if not self.driver:
            return False

        current_url = (self.driver.current_url or "").lower()
        if "foundit.in" not in current_url:
            self.browser.navigate(HOME_URL)
            time.sleep(2)

        # 1. Locate Skills input (Home or SRP)
        skills_input = None
        for sel in [
            HOME_SKILLS_INPUT,
            SRP_SKILLS_INPUT,
            "input#heroSectionDesktop-skillsAutoComplete--input",
            "input[placeholder*='Skills']",
            "input[placeholder*='Search by Skills']",
        ]:
            try:
                for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if el.is_displayed():
                        skills_input = el
                        break
                if skills_input:
                    break
            except Exception:
                continue

        if not skills_input:
            # If not on home or SRP with inputs, navigate to home
            self.browser.navigate(HOME_URL)
            time.sleep(2)
            try:
                skills_input = self.driver.find_element(By.ID, "heroSectionDesktop-skillsAutoComplete--input")
            except Exception:
                pass

        if not skills_input:
            print_lg("[FounditSearch] Notice: Skills input not found for UI search.")
            return False

        print_lg(f"[FounditSearch] Entering search keyword in UI: '{keyword}'...")
        try:
            skills_input.click()
            time.sleep(0.3)
            skills_input.clear()
            skills_input.send_keys(keyword)
            time.sleep(1)

            # Check for autocomplete suggestion dropdown
            try:
                suggestions = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "div.autocomplete-results li, div[class*='suggestion'] div, div[id*='react-autowhatever'] li"
                )
                if suggestions:
                    self.driver.execute_script("arguments[0].click();", suggestions[0])
            except Exception:
                pass
        except Exception as e:
            print_lg(f"[FounditSearch] Notice setting keyword: {e}")

        # 2. Enter Location in UI (only if not already applied)
        if location and location.strip():
            location_already_applied = False
            try:
                # Check entire search section / header text
                containers = self.driver.find_elements(
                    By.XPATH,
                    "//div[contains(@id, 'heroSection') or contains(@class, 'heroSection') or contains(@class, 'search') or ancestor::header]"
                )
                for c in containers:
                    if location.lower() in (c.text or "").lower():
                        location_already_applied = True
                        break

                if not location_already_applied:
                    # Check any visible chips / elements containing location name in header
                    chips = self.driver.find_elements(
                        By.XPATH,
                        f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{location.lower()}') and (ancestor::header or ancestor::div[contains(@class, 'search') or contains(@id, 'heroSection')])]"
                    )
                    if any(ch.is_displayed() for ch in chips):
                        location_already_applied = True
            except Exception:
                pass

            if location_already_applied:
                print_lg(f"[FounditSearch] Location '{location}' is already applied in search box. Skipping.")
            else:
                loc_input = None
                for sel in [
                    HOME_LOCATION_INPUT,
                    SRP_LOCATION_INPUT,
                    "input#heroSectionDesktop-locationAutoComplete--input",
                    "input[placeholder*='Location']",
                ]:
                    try:
                        for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                            if el.is_displayed():
                                loc_input = el
                                break
                        if loc_input:
                            break
                    except Exception:
                        continue

                if loc_input:
                    try:
                        current_val = (loc_input.get_attribute("value") or "").strip().lower()
                        parent_text = ""
                        try:
                            parent_text = (loc_input.find_element(By.XPATH, "./..").text or "").lower()
                        except Exception:
                            pass

                        if (location.lower() in current_val) or (location.lower() in parent_text):
                            print_lg(f"[FounditSearch] Location '{location}' is already in input. Skipping.")
                        else:
                            loc_input.click()
                            time.sleep(0.2)
                            loc_input.clear()
                            loc_input.send_keys(location)
                            time.sleep(0.8)
                            suggestions = self.driver.find_elements(
                                By.CSS_SELECTOR,
                                "div.autocomplete-results li, div[class*='suggestion'] div"
                            )
                            if suggestions:
                                self.driver.execute_script("arguments[0].click();", suggestions[0])
                    except Exception as e:
                        print_lg(f"[FounditSearch] Notice setting location: {e}")

        # Ensure any open location dropdown/modal is dismissed before clicking search
        self.close_open_modals()

        # 3. Select Experience in UI
        if experience_years is not None:
            exp_input = None
            for sel in [
                HOME_EXPERIENCE_INPUT,
                SRP_EXPERIENCE_INPUT,
                "input#heroSectionDesktop-expAutoComplete--input",
                "input[placeholder*='Experience']",
            ]:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if el.is_displayed():
                            exp_input = el
                            break
                    if exp_input:
                        break
                except Exception:
                    continue

            if exp_input:
                try:
                    exp_input.click()
                    time.sleep(0.5)
                    opts = self.driver.find_elements(
                        By.CSS_SELECTOR,
                        "div[class*='experience'] li, div[class*='exp'] li, div[class*='dropdown'] div, li"
                    )
                    target_txt = "fresher" if experience_years <= 0 else f"{experience_years} year"
                    target_opt = None
                    for o in opts:
                        txt = (o.text or "").strip().lower()
                        if target_txt in txt or (experience_years > 0 and f"{experience_years} yr" in txt):
                            target_opt = o
                            break
                    if target_opt:
                        self.driver.execute_script("arguments[0].click();", target_opt)
                        time.sleep(0.3)
                except Exception as e:
                    print_lg(f"[FounditSearch] Notice setting experience: {e}")

        # Ensure any dropdown modal is closed before clicking search
        self.close_open_modals()

        # 4. Click Search Button
        search_btn = None
        for sel in [
            HOME_SEARCH_BUTTON,
            SRP_SEARCH_BUTTON,
            "button.search_submit_btn",
            "button[class*='search_submit_btn']",
            "button[aria-label='search']",
            "//button[contains(@class, 'search') or .//*[name()='svg']]",
        ]:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for b in elems:
                    if b.is_displayed():
                        search_btn = b
                        break
                if search_btn:
                    break
            except Exception:
                continue

        if search_btn:
            print_lg("[FounditSearch] Clicking Search button...")
            try:
                search_btn.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(5)
        else:
            print_lg("[FounditSearch] Notice: Search button not found.")
            return False

        # Close any lingering popups after search
        self.close_open_modals()

        # 5. Apply or deactivate Quick Apply toggle on SRP based on configuration
        if quick_apply:
            self.apply_quick_apply_filter()
        else:
            self.ensure_quick_apply_filter_off()

        return True

    def apply_sidebar_experience_filter(self, experience_years: Optional[int]) -> bool:
        """Applies the experience filter in the left sidebar UI as shown in Screenshot 2."""
        if not self.driver or experience_years is None:
            return False

        try:
            target_str = "fresher" if experience_years <= 0 else f"{experience_years} yr"
            target_str_plural = "fresher" if experience_years <= 0 else f"{experience_years} yrs"

            # 1. Check if filter is already applied (e.g. "1 filters applied: [ 2 yrs x ]")
            applied_elements = self.driver.find_elements(
                By.XPATH,
                "//div[contains(., 'filters applied') or contains(@class, 'applied')]//span | "
                "//div[contains(@class, 'filter')]//div[contains(@class, 'chip') or contains(@class, 'tag')] | "
                "//div[contains(@class, 'filter')]//span[contains(text(), 'yr') or contains(text(), 'Fresher')]"
            )
            for el in applied_elements:
                if el.is_displayed():
                    txt = (el.text or "").strip().lower()
                    if target_str in txt or target_str_plural in txt:
                        print_lg(f"[FounditSearch] Experience filter '{target_str_plural}' is already applied in sidebar.")
                        return True

            # 2. Check if radio input exists directly (e.g. input with value or id)
            target_elem = None
            radio_inputs = self.driver.find_elements(
                By.XPATH,
                f"//input[@type='radio'][@value='{experience_years}'] | "
                f"//input[@type='radio'][contains(@id, '{experience_years}')]"
            )
            for r in radio_inputs:
                target_elem = r
                break

            # 2b. If not direct radio input, search via text across all elements using '.'
            if not target_elem:
                sidebar_elements = self.driver.find_elements(
                    By.XPATH,
                    f"//label[contains(translate(., 'YRS', 'yrs'), '{target_str}')] | "
                    f"//*[contains(@class, 'filter') or contains(@class, 'sidebar') or contains(@class, 'Filters') or ancestor::*[contains(., 'All Filters')]]"
                    f"//*[self::span or self::p or self::div or self::li][contains(translate(., 'YRS', 'yrs'), '{target_str}')]"
                )
                for el in sidebar_elements:
                    try:
                        if not el.is_displayed():
                            continue
                        txt = (el.text or "").strip().lower()
                        if experience_years <= 0:
                            if "fresher" in txt:
                                target_elem = el
                                break
                        else:
                            if re.search(r'(?<!\d)' + str(experience_years) + r'\s*yrs?\b', txt):
                                target_elem = el
                                break
                    except Exception:
                        continue

            # If not found directly and exp > 4, try clicking 'View more' under Experience
            if not target_elem and experience_years > 4:
                try:
                    view_mores = self.driver.find_elements(
                        By.XPATH,
                        "//div[contains(., 'Experience')]//following::span[contains(text(), 'View more') or contains(text(), 'view more')]"
                    )
                    for vm in view_mores:
                        if vm.is_displayed():
                            self.driver.execute_script("arguments[0].click();", vm)
                            time.sleep(0.8)
                            break
                    # Re-scan
                    sidebar_elements = self.driver.find_elements(
                        By.XPATH,
                        "//aside//*[self::label or self::div or self::span or self::p] | //div[contains(@class, 'filter') or contains(@class, 'sidebar')]//*[self::label or self::div or self::span or self::p]"
                    )
                    for el in sidebar_elements:
                        txt = (el.text or "").strip().lower()
                        if re.search(r'(?<!\d)' + str(experience_years) + r'\s*yrs?\b', txt):
                            target_elem = el
                            break
                except Exception:
                    pass

            if target_elem:
                print_lg(f"[FounditSearch] Clicking sidebar experience filter: '{target_str_plural}'...")
                # If target element is an inner span/div, prefer clicking its parent label or input
                click_target = target_elem
                try:
                    if target_elem.tag_name.lower() != "label":
                        parent_label = target_elem.find_element(By.XPATH, "./ancestor::label[1]")
                        if parent_label:
                            click_target = parent_label
                except Exception:
                    pass

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", click_target)
                time.sleep(0.3)
                try:
                    click_target.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", click_target)

                # Ensure radio input state is updated and React change event is dispatched
                try:
                    radio_elem = click_target if click_target.tag_name.lower() == "input" else None
                    if not radio_elem:
                        radios = click_target.find_elements(By.XPATH, ".//input[@type='radio'] | ./preceding-sibling::input[@type='radio'] | ./following-sibling::input[@type='radio']")
                        if radios:
                            radio_elem = radios[0]
                    if radio_elem:
                        self.driver.execute_script("if (!arguments[0].checked) { arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles: true})); }", radio_elem)
                except Exception:
                    pass

                time.sleep(2.5)
                self.close_open_modals()
                return True
            else:
                print_lg(f"[FounditSearch] Notice: Sidebar experience option for '{target_str_plural}' not found.")
        except Exception as e:
            print_lg(f"[FounditSearch] Notice applying sidebar experience filter: {e}")
        return False

    def apply_quick_apply_filter(self) -> bool:
        """Toggles the 'Quick Apply' switch on Foundit search results page if not already active."""
        if not self.driver:
            return False
        try:
            toggle = None
            for sel in [
                QUICK_APPLY_TOGGLE,
                "input#toggle",
                "//div[contains(., 'Quick Apply')]//input[@type='checkbox']",
                "//label[contains(., 'Quick Apply') and .//input]",
            ]:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                    for e in elems:
                        toggle = e
                        break
                    if toggle:
                        break
                except Exception:
                    continue

            is_active = False
            if toggle:
                try:
                    is_active = toggle.is_selected() or bool(self.driver.execute_script("return arguments[0].checked === true;", toggle))
                except Exception:
                    pass

            if toggle and not is_active:
                print_lg("[FounditSearch] Activating 'Quick Apply' toggle filter...")
                try:
                    toggle.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", toggle)
                time.sleep(1)

                # Verify if checkbox state flipped; if not, click parent label or peer switch
                now_active = toggle.is_selected() or bool(self.driver.execute_script("return arguments[0].checked === true;", toggle))
                if not now_active:
                    lbls = self.driver.find_elements(
                        By.XPATH,
                        "//label[@for='toggle'] | //label[.//input[@id='toggle']] | //div[contains(@class, 'peer')] | //span[contains(text(), 'Quick Apply')]"
                    )
                    for l in lbls:
                        if l.is_displayed():
                            self.driver.execute_script("arguments[0].click();", l)
                            time.sleep(1)
                            break

                time.sleep(2.5)
                return True
            elif is_active:
                print_lg("[FounditSearch] 'Quick Apply' filter is already active.")
                return True
            else:
                # Try clicking toggle label or peer container directly if input was not found
                lbls = self.driver.find_elements(
                    By.XPATH,
                    "//label[@for='toggle'] | //label[contains(., 'Quick Apply')] | //div[contains(@class, 'peer')] | //div[contains(text(), 'Quick Apply') or .//span[contains(text(), 'Quick Apply')]]"
                )
                for l in lbls:
                    if l.is_displayed():
                        self.driver.execute_script("arguments[0].click();", l)
                        time.sleep(2.5)
                        return True
        except Exception as e:
            print_lg(f"[FounditSearch] Notice toggling quick apply: {e}")
        return False

    def ensure_quick_apply_filter_off(self) -> bool:
        """Ensures the 'Quick Apply' switch on Foundit search results page is turned OFF for hybrid mode."""
        if not self.driver:
            return False
        try:
            toggle = None
            for sel in [
                QUICK_APPLY_TOGGLE,
                "input#toggle",
                "//div[contains(., 'Quick Apply')]//input[@type='checkbox']",
            ]:
                try:
                    elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                    for e in elems:
                        toggle = e
                        break
                    if toggle:
                        break
                except Exception:
                    continue

            is_active = False
            if toggle:
                try:
                    is_active = toggle.is_selected()
                except Exception:
                    pass

            if is_active and toggle:
                print_lg("[FounditSearch] Hybrid Mode: Deactivating 'Quick Apply' filter toggle to discover both Easy Apply and External jobs...")
                try:
                    toggle.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", toggle)
                time.sleep(2.5)
                return True
            elif not is_active:
                print_lg("[FounditSearch] Hybrid Mode: 'Quick Apply' toggle filter is OFF.")
                return True
        except Exception as e:
            print_lg(f"[FounditSearch] Notice turning off quick apply: {e}")
        return False

    def search(
        self,
        keyword: str,
        location: Optional[str] = "India",
        experience_years: Optional[int] = None,
        freshness_days: Optional[int] = None,
        quick_apply: bool = True,
        page: int = 1,
    ) -> List[WebElement]:
        """Performs search via canonical URL navigation with left sidebar filter application (Screenshot 2).
        Avoids split-pane /srp/results mode by applying filters through the UI sidebar.
        """
        print_lg(f"[FounditSearch] Searching: '{keyword}' in '{location}' (page {page})...")

        # 1. If page > 1 and already on a search results page, advance via dynamic pagination
        if page > 1 and self.driver and "/search" in (self.driver.current_url or ""):
            print_lg(f"[FounditSearch] Advancing to page {page} on existing search page...")
            next_btn = self.get_next_page_element()
            if next_btn:
                print_lg(f"[FounditSearch] Clicking Next page button for page {page}...")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_btn)
                time.sleep(random.uniform(0.4, 0.8))
                try:
                    next_btn.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", next_btn)
                time.sleep(random.uniform(2.5, 4.0))
                self.close_open_modals()
                cards = self.find_job_cards()
                if cards:
                    return cards

            # Try page number button in pagination
            try:
                page_buttons = self.driver.find_elements(
                    By.XPATH,
                    f"//div[contains(@class, 'pagination')]//button[normalize-space()='{page}'] | "
                    f"//div[contains(@class, 'pagination')]//a[normalize-space()='{page}']"
                )
                for pb in page_buttons:
                    if pb.is_displayed():
                        print_lg(f"[FounditSearch] Clicking page {page} button...")
                        self.driver.execute_script("arguments[0].click();", pb)
                        time.sleep(random.uniform(2.5, 4.0))
                        self.close_open_modals()
                        cards = self.find_job_cards()
                        if cards:
                            return cards
            except Exception:
                pass

            # Fallback: Scroll to bottom to trigger dynamic loading / infinite scroll
            print_lg(f"[FounditSearch] Scrolling to bottom to load more jobs for page {page}...")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(2.0, 3.5))
            cards = self.find_job_cards()
            if cards:
                return cards

        # Primary: Canonical Search URL (opens standard search layout with left sidebar)
        url = build_search_url(
            keyword=keyword,
            location=location,
            experience_years=experience_years,
            freshness_days=freshness_days,
            page=page,
        )
        print_lg(f"[FounditSearch] Navigating to canonical search URL: {url}")
        self.browser.navigate(url)
        time.sleep(random.uniform(3.0, 4.5))
        self.close_open_modals()

        # 2. Apply experience filter via UI sidebar if specified (Screenshot 2)
        if experience_years is not None and experience_years >= 0:
            self.apply_sidebar_experience_filter(experience_years)

        # 3. Handle Quick Apply toggle if configured (Screenshot 2 center toggle)
        if quick_apply:
            self.apply_quick_apply_filter()
        else:
            self.ensure_quick_apply_filter_off()

        cards = self.find_job_cards()
        if cards:
            return cards

        # 4. Resilient fallback: Try UI search only if initial navigation returned 0 cards on page 1
        if page == 1:
            print_lg("[FounditSearch] Canonical navigation returned 0 cards. Attempting UI search fallback...")
            ui_success = self.search_via_ui(
                keyword=keyword,
                location=location,
                experience_years=experience_years,
                freshness_days=freshness_days,
                quick_apply=quick_apply,
            )
            if ui_success:
                cards = self.find_job_cards()
                if cards:
                    return cards

        return cards
    def find_job_cards(self) -> List[WebElement]:
        """Returns all visible, validated job cards currently present on the page."""
        if not self.driver:
            return []
        cards_found = []
        seen_ids = set()

        # 1. Primary card container selectors
        for sel in [
            CARD_CONTAINER_SELECTOR,
            "div.cardContainer",
            "div.srpResultCard",
            "div[class~='cardContainer']",
            "div[class*='jobCard']",
        ]:
            try:
                for c in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    try:
                        if not is_valid_job_card(c):
                            continue
                        c_cls = c.get_attribute("class") or ""
                        # Guard against outer wrappers and right pane
                        if any(w in c_cls for w in ["cardsContainer", "srpRightContainer", "detailsContainer"]):
                            continue
                        cid = c.get_attribute("id") or c.get_attribute("data-job-id") or ""
                        if not cid:
                            for a in c.find_elements(By.TAG_NAME, "a"):
                                h = a.get_attribute("href") or ""
                                m = re.search(r'/job/([a-zA-Z0-9_-]+)', h)
                                if m:
                                    cid = m.group(1)
                                    break
                        if not cid:
                            first_text = (c.text or "")[:40].strip()
                            cid = f"card_{hash(first_text)}" if first_text else f"card_{len(cards_found) + 1}"

                        if c.is_displayed() and cid not in seen_ids:
                            seen_ids.add(cid)
                            cards_found.append(c)
                    except Exception:
                        continue
                if cards_found:
                    return cards_found
            except Exception:
                pass

        # 2. Resilient fallback: discover card containers via job titles
        try:
            title_elems = self.driver.find_elements(By.CSS_SELECTOR, "div.jobTitle, div#jobCardTitle, h3.jobTitle")
            for te in title_elems:
                try:
                    if not te.is_displayed():
                        continue
                    card = te.find_element(
                        By.XPATH,
                        "./ancestor::div[contains(@class, 'cardContainer') or contains(@class, 'srpResultCard') or contains(@class, 'card')][1]"
                    )
                    if not is_valid_job_card(card):
                        continue
                    c_cls = card.get_attribute("class") or ""
                    if any(w in c_cls for w in ["srpRightContainer", "detailsContainer"]):
                        continue
                    cid = card.get_attribute("id") or card.get_attribute("data-job-id")
                    if not cid:
                        first_text = (card.text or "")[:40].strip()
                        cid = f"card_{hash(first_text)}" if first_text else f"card_{len(cards_found) + 1}"

                    if card and cid not in seen_ids:
                        seen_ids.add(cid)
                        cards_found.append(card)
                except Exception:
                    continue
        except Exception:
            pass

        return cards_found

    def select_card(self, card_elem: WebElement, timeout: int = 5) -> bool:
        """Clicks a card to trigger the split-pane job details view on the right."""
        if not self.driver or not card_elem:
            return False
        try:
            # Scroll element into view safely
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", card_elem)
            time.sleep(0.3)
            try:
                card_elem.click()
            except Exception:
                self.driver.execute_script("arguments[0].click();", card_elem)

            # Wait briefly for details pane to update
            start_t = time.time()
            while time.time() - start_t < timeout:
                for sel in DETAILS_CONTAINER_SELECTORS:
                    try:
                        elems = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        if any(e.is_displayed() and len(e.text or "") > 50 for e in elems):
                            return True
                    except Exception:
                        pass
                time.sleep(0.5)
            return True
        except Exception as e:
            print_lg(f"[FounditSearch] Failed to select job card: {e}")
            return False

    def get_next_page_element(self) -> Optional[WebElement]:
        """Locates the next page navigation element if present."""
        if not self.driver:
            return None
        for sel in PAGINATION_NEXT_BUTTONS:
            try:
                elems = self.driver.find_elements(By.XPATH if sel.startswith("//") else By.CSS_SELECTOR, sel)
                for e in elems:
                    if e.is_displayed() and "disabled" not in (e.get_attribute("class") or "").lower():
                        return e
            except Exception:
                continue
        return None
