'''
JobPilot - Multi-Platform Job Search & Application Automation
'''



# Imports
import os
import csv
import re
try:
    import pyautogui
except Exception:
    pyautogui = None

# Set CSV field size limit to prevent field size errors
csv.field_size_limit(1000000)  # Set to 1MB instead of default 131KB

from random import choice, shuffle, randint
from datetime import datetime
from urllib.parse import urlencode

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.select import Select
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import NoSuchElementException, ElementClickInterceptedException, NoSuchWindowException, ElementNotInteractableException, WebDriverException, TimeoutException

from config.personals import *
from config.questions import *
from config.search import *
from config.secrets import use_AI, username, password, ai_provider
from config.settings import *

from modules.open_chrome import *
from modules.helpers import *
from modules.clickers_and_finders import *
from modules.validator import validate_config
from modules.qna_engine import QnAEngine

try:
    from app.services.sanitizer_service import install_root_sanitizer
    install_root_sanitizer()
except Exception:
    pass

if use_AI:
    from modules.ai.openaiConnections import ai_create_openai_client, ai_extract_skills, ai_answer_question, ai_close_openai_client
    from modules.ai.deepseekConnections import deepseek_create_client, deepseek_extract_skills, deepseek_answer_question
    from modules.ai.geminiConnections import gemini_create_client, gemini_extract_skills, gemini_answer_question

from typing import Literal


if pyautogui is not None:
    pyautogui.FAILSAFE = False
# if use_resume_generator:    from resume_generator import is_logged_in_GPT, login_GPT, open_resume_chat, create_custom_resume


#< Global Variables and logics

if run_in_background == True:
    pause_at_failed_question = False
    pause_before_submit = False
    run_non_stop = False

first_name = first_name.strip()
middle_name = middle_name.strip()
last_name = last_name.strip()
full_name = first_name + " " + middle_name + " " + last_name if middle_name else first_name + " " + last_name

useNewResume = True
randomly_answered_questions = set()

tabs_count = 1
easy_applied_count = 0
external_jobs_count = 0
failed_count = 0
skip_count = 0
dailyEasyApplyLimitReached = False

re_experience = re.compile(r'[(]?\s*(\d+)\s*[)]?\s*[-to]*\s*\d*[+]*\s*year[s]?', re.IGNORECASE)

desired_salary_lakhs = str(round(desired_salary / 100000, 2))
desired_salary_monthly = str(round(desired_salary/12, 2))
desired_salary = str(desired_salary)

current_ctc_lakhs = str(round(current_ctc / 100000, 2))
current_ctc_monthly = str(round(current_ctc/12, 2))
current_ctc = str(current_ctc)

notice_period_months = str(notice_period//30)
notice_period_weeks = str(notice_period//7)
notice_period = str(notice_period)

aiClient = None
qna_engine = QnAEngine(ai_client=None)
about_company_for_ai = None # TODO extract about company for AI

#>


#< Login Functions
def is_logged_in_LN() -> bool:
    '''
    Function to check if user is logged-in in LinkedIn
    * Returns: `True` if user is logged-in or `False` if not
    '''
    try:
        url = driver.current_url.lower()
    except Exception:
        return False

    # Checkpoint, Challenge, Login, Signup, or Authwall URLs mean definitely NOT logged in
    if any(k in url for k in ["/checkpoint/", "/challenge/", "/login", "/signup", "/uas/", "/authwall"]):
        return False

    # Check for unauthenticated / guest sign-in indicators FIRST
    guest_indicators = [
        '//a[contains(@href, "/login") or contains(@href, "/signin")]',
        '//a[contains(normalize-space(.), "Sign in") or contains(normalize-space(.), "Join now")]',
        '//button[contains(normalize-space(.), "Sign in") or contains(normalize-space(.), "Join now")]',
        '//button[@data-tracking-control-name="public_jobs_nav-header-signin"]',
        '//div[contains(@class, "sign-in-modal")]',
        '//div[contains(@class, "authwall")]',
        '//section[contains(@class, "guest-homepage")]',
    ]
    is_guest = any(try_xp(driver, xp, False) for xp in guest_indicators)
    if is_guest:
        # Verify if an authenticated global-nav me-photo exists to override
        if not try_xp(driver, '//img[contains(@class, "global-nav__me-photo")] | //button[contains(@class, "global-nav__primary-link-me-menu-trigger")]', False):
            return False

    # Check for positive authenticated DOM elements (navigation, profile, feed widgets)
    logged_in_indicators = [
        '//button[contains(normalize-space(.), "Start a post")]',
        '//nav[contains(@class, "global-nav")]',
        './/img[contains(@class, "global-nav__me-photo")]',
        '//button[contains(@class, "global-nav__primary-link-me-menu-trigger")]',
        '//div[contains(@class, "feed-identity-module")]',
        '//a[contains(@href, "/feed/")]',
    ]
    for xpath in logged_in_indicators:
        if try_xp(driver, xpath, False):
            return True

    # If explicitly on feed and no guest sign-in modal
    if "linkedin.com/feed" in url:
        return True

    return False


def is_linkedin_2fa_or_challenge() -> bool:
    '''
    Checks if LinkedIn is currently presenting a 2FA prompt, mobile app confirmation,
    SMS code verification, or security challenge.
    '''
    try:
        url = driver.current_url.lower()
        if any(k in url for k in ["/checkpoint/", "/challenge/", "consumer-captcha", "/two-step", "security-check"]):
            return True
        page_source = driver.page_source.lower()
        indicators = [
            "check your linkedin app",
            "verify your identity",
            "we sent a notification",
            "two-step verification",
            "two-factor",
            "enter the code",
            "enter the 6-digit code",
            "enter 6-digit code",
            "verification code",
            "authenticator app",
            "verify using sms",
            "security verification",
            "confirm your sign-in attempt",
            "recognize this device in the future",
            "did you just try to sign in",
            "open the linkedin app",
            "pin-input",
        ]
        return any(ind in page_source for ind in indicators)
    except Exception:
        return False


def dismiss_linkedin_post_login_prompts(drv) -> bool:
    '''
    Dismisses post-login interstitials such as 'Remember this device', 'Trust this browser',
    'Add phone number', or 'Skip' that LinkedIn displays after 2FA.
    '''
    try:
        post_login_xpaths = [
            '//button[contains(normalize-space(.), "Remember this device") or contains(normalize-space(.), "Remember this computer")]',
            '//button[contains(normalize-space(.), "Trust this browser") or contains(normalize-space(.), "Trust device")]',
            '//button[contains(normalize-space(.), "Continue") or contains(normalize-space(.), "Done")]',
            '//button[contains(normalize-space(.), "Skip for now") or contains(normalize-space(.), "Not now")]',
            '//button[contains(normalize-space(.), "Remind me later")]',
            '//a[contains(normalize-space(.), "Skip for now") or contains(normalize-space(.), "Not now")]',
        ]
        clicked = False
        for xp in post_login_xpaths:
            try:
                elems = drv.find_elements(By.XPATH, xp)
                for el in elems:
                    if el.is_displayed():
                        drv.execute_script("arguments[0].click();", el)
                        print_lg(f"Dismissed post-login prompt: '{el.text.strip()}'")
                        clicked = True
                        sleep(1)
                        break
            except Exception:
                continue
        return clicked
    except Exception:
        return False


def check_linkedin_auth_complete() -> bool:
    '''
    Evaluates whether LinkedIn authentication is finalized after credentials/2FA submission.
    Dismisses post-login prompts and verifies authenticated state.
    '''
    try:
        # 1. Dismiss any post-login / device trust interstitials
        dismiss_linkedin_post_login_prompts(driver)

        # 2. Check standard login indicators
        if is_logged_in_LN():
            return True

        url = ""
        try:
            url = driver.current_url.lower()
        except Exception:
            pass

        # 3. If on feed, mynetwork, or jobs, verify again
        if any(p in url for p in ["/feed", "/mynetwork", "/jobs", "/in/"]):
            return is_logged_in_LN()
    except Exception:
        pass
    return False


def safe_driver_get(drv, url: str, timeout: int = 30) -> None:
    '''
    Navigates to URL safely. If network requests or trackers hang past timeout,
    stops window loading and proceeds with available DOM.
    '''
    try:
        drv.set_page_load_timeout(timeout)
        drv.get(url)
    except TimeoutException:
        print_lg(f"Notice: Page load exceeded {timeout}s for URL, halting network requests and proceeding with DOM.")
        try:
            drv.execute_script("window.stop();")
        except Exception:
            pass
    except Exception as e:
        err_msg = str(e).lower()
        if "timeout" in err_msg or "timed out" in err_msg:
            print_lg(f"Warning: Navigation timed out ({e}). Halting background requests and proceeding.")
            try:
                drv.execute_script("window.stop();")
            except Exception:
                pass
        else:
            raise e


def dismiss_linkedin_overlays(drv) -> None:
    """Dismisses cookie banners, Google One Tap, or auth popups that block interaction."""
    try:
        for xp in [
            '//button[contains(@action-type, "ACCEPT") or contains(normalize-space(.), "Accept cookies") or contains(normalize-space(.), "Accept")]',
            '//button[@aria-label="Dismiss" or @aria-label="Close"]',
            '//button[contains(@class, "artdeco-global-alert__action")]',
        ]:
            btns = drv.find_elements(By.XPATH, xp)
            for b in btns:
                if b.is_displayed():
                    drv.execute_script("arguments[0].click();", b)
    except Exception:
        pass
    try:
        drv.execute_script("""
            const gsi = document.getElementById('credential_picker_container') || document.querySelector('iframe[src*="google.com/gsi"]');
            if (gsi) gsi.remove();
        """)
    except Exception:
        pass


def find_visible_input_element(drv, selectors, timeout: float = 6.0):
    """Finds an interactable, visible input element across multiple CSS and XPath selectors."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        for sel in selectors:
            try:
                if sel.startswith("//"):
                    elems = drv.find_elements(By.XPATH, sel)
                else:
                    elems = drv.find_elements(By.CSS_SELECTOR, sel)
                for el in elems:
                    if el.is_displayed() and el.get_attribute("type") != "hidden":
                        return el
            except Exception:
                pass
        sleep(0.3)

    for sel in selectors:
        try:
            if sel.startswith("//"):
                el = drv.find_element(By.XPATH, sel)
            else:
                el = drv.find_element(By.CSS_SELECTOR, sel)
            if el:
                return el
        except Exception:
            pass
    return None


def fill_react_input(drv, element, value: str) -> None:
    """Fills an input field reliably handling React controlled inputs and non-interactable overlays."""
    from selenium.webdriver.common.action_chains import ActionChains
    try:
        drv.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        sleep(0.15)
        drv.execute_script("arguments[0].focus();", element)
    except Exception:
        pass

    # 1. Native HTMLInputElement prototype setter (required for React / Redux / SDUI to detect value change)
    try:
        drv.execute_script("""
            const el = arguments[0];
            const val = arguments[1];
            el.focus();
            const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            setter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """, element, value)
    except Exception:
        pass

    # 2. Try native clear and send_keys with ActionChains fallback
    try:
        element.clear()
        element.send_keys(Keys.CONTROL + "a")
        element.send_keys(Keys.BACKSPACE)
        element.send_keys(value)
    except Exception:
        try:
            actions = ActionChains(drv)
            actions.click(element).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).send_keys(value).perform()
        except Exception:
            try:
                drv.execute_script("""
                    const el = arguments[0];
                    const val = arguments[1];
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    setter.call(el, val);
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                """, element, value)
            except Exception:
                pass


def login_LN() -> bool:
    '''
    Function to login to LinkedIn:
    * Resolves credentials from secrets / settings (supports email, username, phone)
    * Checks if already logged in first
    * Fills credentials and submits
    * If 2FA occurs, WAITS for user to approve on app/device with automatic detection
    * If no 2FA occurs, proceeds immediately without dialogs!
    * Uses modern dark theme dialogs everywhere
    * Returns True if logged in, False otherwise
    '''
    # Resolve authoritative credentials dynamically
    try:
        from config.secrets import get_linkedin_credentials
        eff_username, eff_password = get_linkedin_credentials()
    except Exception:
        eff_username, eff_password = username, password

    if not eff_username or eff_username == "username@example.com" or eff_password == "CHANGE_ME_TO_YOUR_LINKEDIN_PASSWORD":
        print_lg("User did not configure username/password in settings, asking manual login...")
        show_modern_alert(
            "LinkedIn credentials are not configured in Settings.\n\nPlease log in manually in the browser, or save your credentials in Settings view.",
            "Login Required",
            "OK",
        )
        manual_login_retry(is_logged_in_LN, 2)
        return is_logged_in_LN()

    # Check if persistent profile is already logged in before loading /login
    if is_logged_in_LN():
        print_lg("Already logged in to LinkedIn via active session!")
        return True

    safe_driver_get(driver, "https://www.linkedin.com/feed", 30)
    sleep(2)
    dismiss_linkedin_overlays(driver)

    if is_logged_in_LN():
        print_lg("Already logged in to LinkedIn via persistent profile cookies!")
        return True

    # Navigate to login page only when not authenticated
    safe_driver_get(driver, "https://www.linkedin.com/login", 30)
    sleep(2)
    dismiss_linkedin_overlays(driver)

    # 1. Attempt to enter credentials
    try:
        # Check for saved profile / choose account card first
        for card_xp in [
            '//div[contains(@class, "profile__details")]',
            '//button[contains(@class, "profile__details")]',
            '//a[contains(normalize-space(.), "Sign in with another account")]',
            '//button[contains(normalize-space(.), "Sign in as")]',
        ]:
            card = try_xp(driver, card_xp, False)
            if card and card.is_displayed():
                try:
                    driver.execute_script("arguments[0].click();", card)
                    sleep(1)
                    break
                except Exception:
                    pass

        # Find username/email input with multi-selector fallback
        username_selectors = [
            "#username",
            "#session_key",
            "input[name='session_key']",
            "input[autocomplete='username']",
            "input[type='email']",
            "//input[@id='username' or @name='session_key' or @id='session_key']",
            "//input[@type='email' or @type='text'][not(@type='hidden')]",
        ]
        username_field = find_visible_input_element(driver, username_selectors, timeout=6.0)

        if username_field:
            fill_react_input(driver, username_field, eff_username)
            print_lg(f"Entered username/email for {eff_username}.")
            buffer(0.5)

            # Find password input
            password_selectors = [
                "#password",
                "#session_password",
                "input[name='session_password']",
                "input[autocomplete='current-password']",
                "input[type='password']",
                "//input[@id='password' or @name='session_password' or @id='session_password']",
                "//input[@type='password'][not(@type='hidden')]",
            ]
            password_field = find_visible_input_element(driver, password_selectors, timeout=6.0)

            if password_field:
                fill_react_input(driver, password_field, eff_password)
                print_lg("Entered password.")
                buffer(0.5)

            # Check "Keep me signed in" checkbox if present and unchecked
            try:
                keep_signed_in = driver.find_element(By.CSS_SELECTOR, "input[type='checkbox']#remember-me-checkbox, input[name='rememberMeShown']")
                if keep_signed_in and not keep_signed_in.is_selected():
                    driver.execute_script("arguments[0].click();", keep_signed_in)
            except Exception:
                pass

            # Submit login form
            submit_selectors = [
                '//button[@type="submit" and (contains(normalize-space(.), "Sign in") or contains(normalize-space(.), "Sign In") or contains(normalize-space(.), "Log in") or contains(normalize-space(.), "Log In"))]',
                '//button[@data-litms-control-urn="login-submit"]',
                '//button[@type="submit"]',
                '//button[contains(@class, "btn__primary")]',
                '//button[contains(@class, "signin-form__submit-button")]',
            ]
            submit_btn = None
            for xp in submit_selectors:
                try:
                    candidates = driver.find_elements(By.XPATH, xp)
                    for c in candidates:
                        if c.is_displayed():
                            submit_btn = c
                            break
                    if submit_btn:
                        break
                except Exception:
                    pass

            if submit_btn:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", submit_btn)
                    sleep(0.2)
                    driver.execute_script("arguments[0].click();", submit_btn)
                except Exception:
                    submit_btn.click()
                print_lg(f"Submitted login credentials for {eff_username}.")
            else:
                submitted = False
                try:
                    submitted = driver.execute_script("""
                        const el = arguments[0];
                        const form = (el && el.closest) ? el.closest('form') : document.querySelector('form');
                        if (form) {
                            if (form.requestSubmit) { form.requestSubmit(); return true; }
                            form.submit(); return true;
                        }
                        return false;
                    """, password_field or username_field)
                except Exception:
                    pass

                if submitted:
                    print_lg("Submitted login form via form.requestSubmit().")
                else:
                    print_lg("Pressing ENTER via ActionChains to submit login credentials.")
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(driver).send_keys(Keys.ENTER).perform()
                    except Exception as ent_err:
                        print_lg(f"ActionChains ENTER failed: {ent_err}")
        else:
            # Check for saved profile button
            try:
                profile_button = find_by_class(driver, "profile__details")
                profile_button.click()
                print_lg("Clicked saved profile card.")
            except Exception:
                print_lg("Couldn't find login fields or profile card.")
    except Exception as e:
        print_lg(f"Error while entering credentials: {e}")

    # 2. Wait and evaluate post-login state
    print_lg("Evaluating LinkedIn authentication response...")
    is_2fa = False
    for _ in range(15):
        sleep(1)
        dismiss_linkedin_post_login_prompts(driver)
        if is_logged_in_LN():
            print_lg("LinkedIn login successful! Proceeding with automation.")
            return True
        if is_linkedin_2fa_or_challenge():
            is_2fa = True
            break

    # 3. Handle 2FA ONLY if 2FA occurred!
    if is_2fa:
        print_lg("=================================================================")
        print_lg("[2FA DETECTED] LinkedIn Security Verification / 2FA Challenge!")
        print_lg("LinkedIn sent a verification prompt to your mobile device or requested a code.")
        print_lg(">> Please open your LinkedIn mobile app and tap 'Yes', or enter code in Chrome.")
        print_lg("JobPilot is actively waiting up to 180 seconds and will auto-detect your login...")
        print_lg("=================================================================")

        def _check_2fa_auth() -> bool:
            try:
                dismiss_linkedin_post_login_prompts(driver)
                if is_logged_in_LN() or check_linkedin_auth_complete():
                    return True
                cur_url = driver.current_url.lower()
                if any(p in cur_url for p in ["/feed", "/mynetwork", "/jobs", "/in/"]):
                    if not is_linkedin_2fa_or_challenge():
                        return True
            except Exception:
                pass
            return False

        msg_text = (
            "LinkedIn Two-Factor Authentication (2FA) Required\n\n"
            "LinkedIn requires security verification to sign in:\n\n"
            "📱 Option 1: Open your LinkedIn mobile app and tap 'Yes'.\n"
            "🔑 Option 2: Enter the SMS or authenticator code in the Chrome window.\n\n"
            "JobPilot is actively waiting up to 180 seconds and will automatically\n"
            "proceed to job applications as soon as you authenticate."
        )

        auth_res = show_modern_confirm(
            text=msg_text,
            title="LinkedIn 2FA Verification",
            buttons=["I Have Authenticated", "Cancel"],
            poll_condition=_check_2fa_auth,
            timeout_seconds=180,
        )

        dismiss_linkedin_post_login_prompts(driver)
        if auth_res == "I Have Authenticated":
            for _ in range(6):
                if is_logged_in_LN() or check_linkedin_auth_complete():
                    print_lg("[2FA SUCCESS] LinkedIn authentication verified! Proceeding with automation.")
                    try:
                        if "feed" not in driver.current_url.lower():
                            safe_driver_get(driver, "https://www.linkedin.com/feed/", 15)
                    except Exception:
                        pass
                    return True
                sleep(1)
                dismiss_linkedin_post_login_prompts(driver)

            if is_logged_in_LN():
                return True
            else:
                print_lg("[2FA NOTICE] 'I Have Authenticated' clicked, but LinkedIn session is not logged in yet.")

        if auth_res == "Cancel":
            print_lg("[2FA CANCELLED] User cancelled 2FA verification prompt.")
            return False

        print_lg("[ERROR] LinkedIn 2FA verification timed out after 180 seconds.")
        show_modern_alert(
            "LinkedIn 2FA verification timed out after 3 minutes.\n\nPlease authenticate in Chrome, then restart automation.",
            "2FA Verification Timeout",
            "OK",
        )
        return False

    # 4. If NOT 2FA and not logged in, check for login errors (e.g. wrong password)
    if not is_2fa and not is_logged_in_LN():
        err_msg = ""
        try:
            err_elem = try_xp(driver, "//div[contains(@class, 'alert') or contains(@id, 'error') or @role='alert']", False)
            if err_elem and err_elem.text.strip():
                err_msg = err_elem.text.strip()
        except Exception:
            pass

        if err_msg:
            print_lg(f"LinkedIn login failed with message: {err_msg}")
            show_modern_alert(
                f"LinkedIn login failed:\n{err_msg}\n\nPlease check your credentials in the Settings page.",
                "Login Failed",
                "OK",
            )
        else:
            print_lg("Login did not reach feed. Starting manual login retry...")

        manual_login_retry(is_logged_in_LN, 3)

    return is_logged_in_LN()
#>



def get_applied_job_ids() -> set[str]:
    '''
    Function to get a `set` of applied job's Job IDs
    * Returns a set of Job IDs from existing applied jobs history csv file
    '''
    job_ids: set[str] = set()
    try:
        with open(file_name, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            for row in reader:
                job_ids.add(row[0])
    except FileNotFoundError:
        print_lg(f"The CSV file '{file_name}' does not exist.")
    return job_ids



def set_search_location() -> None:
    '''
    Function to set search location
    '''
    if search_location.strip():
        try:
            print_lg(f'Setting search location as: "{search_location.strip()}"')
            search_location_ele = try_xp(driver, ".//input[@aria-label='City, state, or zip code'and not(@disabled)]", False) #  and not(@aria-hidden='true')]")
            text_input(actions, search_location_ele, search_location, "Search Location")
        except ElementNotInteractableException:
            try_xp(driver, ".//label[@class='jobs-search-box__input-icon jobs-search-box__keywords-label']")
            actions.send_keys(Keys.TAB, Keys.TAB).perform()
            actions.key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            actions.send_keys(search_location.strip()).perform()
            sleep(2)
            actions.send_keys(Keys.ENTER).perform()
            try_xp(driver, ".//button[@aria-label='Cancel']")
        except Exception as e:
            try_xp(driver, ".//button[@aria-label='Cancel']")
            print_lg("Failed to update search location, continuing with default location!", e)


def build_search_url(search_term: str) -> str:
    '''
    Build LinkedIn jobs search URL pre-encoded with filters to prevent flaky UI clicks.
    '''
    params = {"keywords": search_term}
    if search_location and search_location.strip():
        params["location"] = search_location.strip()
    if "distance" in globals() and distance is not None:
        params["distance"] = str(distance)
    if easy_apply_only:
        params["f_AL"] = "true"
    if date_posted:
        tpr_map = {
            "Past 24 hours": "r86400",
            "Past week": "r604800",
            "Past month": "r2592000"
        }
        if date_posted in tpr_map:
            params["f_TPR"] = tpr_map[date_posted]
    if sort_by:
        sort_map = {
            "Most recent": "DD",
            "Most relevant": "R"
        }
        if sort_by in sort_map:
            params["sortBy"] = sort_map[sort_by]
    if experience_level:
        exp_map = {
            "Internship": "1",
            "Entry level": "2",
            "Associate": "3",
            "Mid-Senior level": "4",
            "Director": "5",
            "Executive": "6"
        }
        exp_vals = [exp_map[e] for e in experience_level if e in exp_map]
        if exp_vals:
            params["f_E"] = ",".join(exp_vals)
    if on_site:
        wt_map = {
            "On-site": "1",
            "Remote": "2",
            "Hybrid": "3"
        }
        wt_vals = [wt_map[w] for w in on_site if w in wt_map]
        if wt_vals:
            params["f_WT"] = ",".join(wt_vals)

    return f"https://www.linkedin.com/jobs/search/?{urlencode(params)}"


def apply_filters() -> None:
    '''
    Function to apply job search filters
    '''
    global pause_after_filters

    # Check if any complex filters were configured that require the 'All filters' modal:
    has_modal_filters = bool(
        companies or location or industry or job_function or job_titles or
        salary or benefits or commitments or under_10_applicants or
        in_your_network or fair_chance_employer or job_type
    )

    if not has_modal_filters:
        print_lg("Core search filters (Location, Easy Apply, Date Posted) applied directly via search URL.")
        return

    set_search_location()

    try:
        recommended_wait = 1 if click_gap < 1 else 0

        wait.until(EC.presence_of_element_located((By.XPATH, '//button[normalize-space()="All filters"]'))).click()
        buffer(recommended_wait)

        wait_span_click(driver, sort_by)
        wait_span_click(driver, date_posted)
        buffer(recommended_wait)

        multi_sel_noWait(driver, experience_level) 
        multi_sel_noWait(driver, companies, actions)
        if experience_level or companies: buffer(recommended_wait)

        multi_sel_noWait(driver, job_type)
        multi_sel_noWait(driver, on_site)
        if job_type or on_site: buffer(recommended_wait)

        if easy_apply_only: boolean_button_click(driver, actions, "Easy Apply")
        
        multi_sel_noWait(driver, location)
        multi_sel_noWait(driver, industry)
        if location or industry: buffer(recommended_wait)

        multi_sel_noWait(driver, job_function)
        multi_sel_noWait(driver, job_titles)
        if job_function or job_titles: buffer(recommended_wait)

        if under_10_applicants: boolean_button_click(driver, actions, "Under 10 applicants")
        if in_your_network: boolean_button_click(driver, actions, "In your network")
        if fair_chance_employer: boolean_button_click(driver, actions, "Fair Chance Employer")

        wait_span_click(driver, salary)
        buffer(recommended_wait)
        
        multi_sel_noWait(driver, benefits)
        multi_sel_noWait(driver, commitments)
        if benefits or commitments: buffer(recommended_wait)

        try:
            show_results_button: WebElement = driver.find_element(By.XPATH, '//button[contains(translate(@aria-label, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "apply current filters to show")]')
            try:
                show_results_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", show_results_button)
        except Exception as btn_err:
            print_lg(f"Notice: 'Show results' button not clicked: {btn_err}")

        if pause_after_filters and "Turn off Pause after search" == show_modern_confirm("These are your configured search results and filter. It is safe to change them while this dialog is open, any changes later could result in errors and skipping this search run.", "Please check your results", ["Turn off Pause after search", "Look's good, Continue"]):
            pause_after_filters = False

    except Exception as e:
        print_lg(f"Setting the preferences failed: {e}")
        if pause_after_filters:
            show_modern_confirm(f"Faced error while applying filters. Please make sure correct filters are selected, click on show results and click on any button of this dialog: {e}", "Filter Notice", ["Doesn't look good, but Continue XD", "Look's good, Continue"])



def is_browser_alive(drv: WebDriver) -> bool:
    '''
    Checks whether the browser session and at least one window are still alive.
    '''
    try:
        if drv is None:
            return False
        handles = drv.window_handles
        return len(handles) > 0
    except Exception:
        return False


def scroll_job_list(driver: WebDriver) -> None:
    '''
    Progressively scrolls the left job listings container to load all occludable
    job items (typically ~25 items) and render the pagination controls at the bottom.
    '''
    try:
        container = None
        for cls in ["jobs-search-results-list", "scaffold-layout__list", "jobs-search-results"]:
            try:
                container = driver.find_element(By.CLASS_NAME, cls)
                if container:
                    break
            except Exception:
                continue

        if container:
            for i in range(1, 6):
                driver.execute_script("arguments[0].scrollTop = (arguments[0].scrollHeight * arguments[1]) / 5;", container, i)
                buffer(0.3)
            driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", container)
            buffer(0.5)
        else:
            for i in range(1, 4):
                driver.execute_script(f"window.scrollTo(0, (document.body.scrollHeight * {i}) / 3);")
                buffer(0.3)
    except Exception as e:
        print_lg(f"Notice: Scrolling job list encountered an issue: {e}")


def get_page_info() -> tuple[WebElement | None, int | None]:
    '''
    Function to get pagination element and current page number
    '''
    try:
        pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
        if pagination_element:
            scroll_to_view(driver, pagination_element)
            current_page = int(pagination_element.find_element(By.XPATH, ".//button[contains(@class, 'active')]").text)
        else:
            current_page = None
    except Exception:
        try:
            scroll_job_list(driver)
            pagination_element = try_find_by_classes(driver, ["jobs-search-pagination__pages", "artdeco-pagination", "artdeco-pagination__pages"])
            if pagination_element:
                scroll_to_view(driver, pagination_element)
                current_page = int(pagination_element.find_element(By.XPATH, ".//button[contains(@class, 'active')]").text)
            else:
                current_page = None
        except Exception:
            pagination_element = None
            current_page = None
    return pagination_element, current_page



def get_job_main_details(job: WebElement, blacklisted_companies: set, rejected_jobs: set, applied_jobs: set = None) -> tuple[str, str, str, str, str, bool, bool]:
    '''
    # Function to get job main details.
    Returns a tuple of (job_id, title, company, work_location, work_style, skip, is_already_applied)
    * job_id: Job ID
    * title: Job title
    * company: Company name
    * work_location: Work location of this job
    * work_style: Work style of this job (Remote, On-site, Hybrid)
    * skip: A boolean flag to skip this job
    * is_already_applied: A boolean flag indicating the job was already applied to in previous runs
    '''
    skip = False
    is_already_applied = False
    job_details_button = job.find_element(By.TAG_NAME, 'a')  # job.find_element(By.CLASS_NAME, "job-card-list__title")  # Problem in India
    scroll_to_view(driver, job_details_button, True)
    job_id = job.get_dom_attribute('data-occludable-job-id')
    title = job_details_button.text
    title = title[:title.find("\n")]
    # company = job.find_element(By.CLASS_NAME, "job-card-container__primary-description").text
    # work_location = job.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
    other_details = job.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
    index = other_details.find(' · ')
    company = other_details[:index]
    work_location = other_details[index+3:]
    work_style = work_location[work_location.rfind('(')+1:work_location.rfind(')')]
    work_location = work_location[:work_location.rfind('(')].strip()

    # Emit DISCOVERED telemetry for live desktop playground
    try:
        import json
        print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': job_id, 'title': title, 'company': company, 'location': work_location, 'status': 'DISCOVERED'})}", flush=True)
    except Exception:
        pass
    
    # Skip if previously rejected due to blacklist or already applied
    if company in blacklisted_companies:
        print_lg(f'Skipping "{title} | {company}" job (Blacklisted Company). Job ID: {job_id}!')
        skip = True
    elif job_id in rejected_jobs: 
        print_lg(f'Skipping previously rejected "{title} | {company}" job. Job ID: {job_id}!')
        skip = True
    elif applied_jobs and (str(job_id) in applied_jobs or job_id in applied_jobs):
        print_lg(f'Pre-filter skip: Already applied to "{title} | {company}" job (in history). Job ID: {job_id}!')
        skip = True
        is_already_applied = True

    try:
        footer_state = job.find_element(By.CLASS_NAME, "job-card-container__footer-job-state")
        if footer_state.text.strip().lower() == "applied":
            skip = True
            is_already_applied = True
            if applied_jobs is not None and job_id:
                applied_jobs.add(job_id)
            print_lg(f'Pre-filter skip: Already applied to "{title} | {company}" job (card badge). Job ID: {job_id}!')
    except: pass

    # Fast Title Pre-Filter: check negative_title_words to skip irrelevant domains immediately
    if not skip and negative_title_words:
        lower_title = title.lower()
        for neg_word in negative_title_words:
            if re.search(r'\b' + re.escape(neg_word.lower()) + r'\b', lower_title):
                print_lg(f'Skipping "{title} | {company}" job (Irrelevant title keyword "{neg_word}"). Job ID: {job_id}!')
                skip = True
                break

    if skip:
        try:
            import json
            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': job_id, 'title': title, 'company': company, 'location': work_location, 'status': 'SKIPPED', 'reason': 'Skipped by filter/blacklist'})}", flush=True)
        except Exception:
            pass

    try: 
        if not skip:
            try:
                job_details_button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", job_details_button)
    except Exception as e:
        print_lg(f'Notice: Failed to click "{title} | {company}" job details button ({e}). Skipping this job card.') 
        discard_job()
        skip = True
        try:
            import json
            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': job_id, 'title': title, 'company': company, 'location': work_location, 'status': 'SKIPPED', 'reason': 'Details click failed'})}", flush=True)
        except Exception:
            pass
    buffer(click_gap)
    return (job_id,title,company,work_location,work_style,skip,is_already_applied)


# Function to check for Blacklisted words in About Company
def check_blacklist(rejected_jobs: set, job_id: str, company: str, blacklisted_companies: set) -> tuple[set, set, WebElement] | ValueError:
    jobs_top_card = try_find_by_classes(driver, ["job-details-jobs-unified-top-card__primary-description-container","job-details-jobs-unified-top-card__primary-description","jobs-unified-top-card__primary-description","jobs-details__main-content"])
    about_company_org = find_by_class(driver, "jobs-company__box")
    scroll_to_view(driver, about_company_org)
    about_company_org = about_company_org.text
    about_company = about_company_org.lower()
    skip_checking = False
    for word in about_company_good_words:
        if word.lower() in about_company:
            print_lg(f'Found the word "{word}". So, skipped checking for blacklist words.')
            skip_checking = True
            break
    if not skip_checking:
        for word in about_company_bad_words: 
            if word.lower() in about_company: 
                rejected_jobs.add(job_id)
                blacklisted_companies.add(company)
                raise ValueError(f'\n"{about_company_org}"\n\nContains "{word}".')
    buffer(click_gap)
    scroll_to_view(driver, jobs_top_card)
    return rejected_jobs, blacklisted_companies, jobs_top_card



# Function to extract years of experience required from About Job
def extract_years_of_experience(text: str) -> int:
    # 1. Match range patterns like '1-5 years', '1–5 Years', '3 to 5 years'
    # The baseline minimum required experience is the lower bound of the range
    range_pattern = re.compile(r'(\d+)\s*(?:[-–—/]|to)\s*(\d+)\s*\+?\s*year[s]?', re.IGNORECASE)
    range_matches = range_pattern.findall(text)
    range_mins = [int(m[0]) for m in range_matches if int(m[0]) <= 15]

    # 2. Match single patterns like '5+ years', '3 years'
    single_pattern = re.compile(r'(\d+)\s*\+?\s*year[s]?', re.IGNORECASE)
    single_matches = single_pattern.findall(text)
    single_vals = [int(m) for m in single_matches if int(m) <= 15]

    if range_mins:
        return min(range_mins)
    if single_vals:
        return min(single_vals)
    return 0



def get_job_description(
) -> tuple[
    str | Literal['Unknown'],
    int | Literal['Unknown'],
    bool,
    str | None,
    str | None
    ]:
    '''
    # Job Description
    Function to extract job description from About the Job.
    ### Returns:
    - `jobDescription: str | 'Unknown'`
    - `experience_required: int | 'Unknown'`
    - `skip: bool`
    - `skipReason: str | None`
    - `skipMessage: str | None`
    '''
    try:
        jobDescription = "Unknown"
        experience_required = "Unknown"
        found_masters = 0
        jd_class_selectors = [
            "jobs-box__html-content",
            "jobs-description__content",
            "jobs-description-content__text",
            "jobs-box__html-content--fade",
            "jobs-description",
        ]
        for sel in jd_class_selectors:
            try:
                el = find_by_class(driver, sel)
                if el and el.text and el.text.strip():
                    jobDescription = el.text.strip()
                    break
            except Exception:
                continue

        if jobDescription == "Unknown":
            for css in ["div#job-details", "article.jobs-description__container", "div.jobs-description__content", "div[class*='jobs-description']", "section.job-details"]:
                try:
                    el = driver.find_element(By.CSS_SELECTOR, css)
                    if el and el.text and el.text.strip():
                        jobDescription = el.text.strip()
                        break
                except Exception:
                    continue

        if jobDescription == "Unknown":
            try:
                el = driver.find_element(By.XPATH, "//div[contains(@class, 'jobs-description') or @id='job-details']")
                if el and el.text and el.text.strip():
                    jobDescription = el.text.strip()
            except Exception:
                pass

        jobDescriptionLow = jobDescription.lower()

        skip = False
        skipReason = None
        skipMessage = None
        for word in bad_words:
            if word.lower() in jobDescriptionLow:
                skipMessage = f'\n{jobDescription}\n\nContains bad word "{word}". Skipping this job!\n'
                skipReason = "Found a Bad Word in About Job"
                skip = True
                break
        if not skip and security_clearance == False and ('polygraph' in jobDescriptionLow or 'clearance' in jobDescriptionLow or 'secret' in jobDescriptionLow):
            skipMessage = f'\n{jobDescription}\n\nFound "Clearance" or "Polygraph". Skipping this job!\n'
            skipReason = "Asking for Security clearance"
            skip = True
        if not skip:
            if did_masters and 'master' in jobDescriptionLow:
                print_lg(f'Found the word "master" in \n{jobDescription}')
                found_masters = 2
            experience_required = extract_years_of_experience(jobDescription)
            if current_experience > -1 and experience_required > current_experience + found_masters:
                skipMessage = f'\n{jobDescription}\n\nExperience required {experience_required} > Current Experience {current_experience + found_masters}. Skipping this job!\n'
                skipReason = "Required experience is high"
                skip = True
    except Exception as e:
        if jobDescription == "Unknown":    print_lg("Unable to extract job description!")
        else:
            experience_required = "Error in extraction"
            print_lg("Unable to extract years of experience required!")
            # print_lg(e)
    return jobDescription, experience_required, skip, skipReason, skipMessage


# Function to upload resume
def upload_resume(modal: WebElement, resume: str) -> tuple[bool, str]:
    try:
        modal.find_element(By.NAME, "file").send_keys(os.path.abspath(resume))
        return True, os.path.basename(default_resume_path)
    except: return False, "Previous resume"

# Function to answer common questions for Easy Apply
def answer_common_questions(label: str, answer: str) -> str:
    if 'sponsorship' in label or 'visa' in label: answer = require_visa
    return answer


# Function to answer the questions for Easy Apply
def answer_questions(modal: WebElement, questions_list: set, work_location: str, job_description: str | None = None ) -> set:
    # Get all questions from the page
     
    all_questions = modal.find_elements(
        By.XPATH,
        ".//div[@data-test-form-element] | "
        ".//div[contains(@class, 'jobs-easy-apply-form-element')] | "
        ".//div[contains(@class, 'fb-dash-form-element')] | "
        ".//div[contains(@data-test-form-builder, 'form-component')]"
    )
    if not all_questions:
        all_questions = modal.find_elements(By.XPATH, ".//div[contains(@class, 'jobs-easy-apply-form-section__grouping')]")

    for Question in all_questions:
        # Check if it's a select Question
        select = try_xp(Question, ".//select", False)
        if select:
            label_org = "Unknown"
            try:
                label = Question.find_element(By.TAG_NAME, "label")
                label_org = label.find_element(By.TAG_NAME, "span").text
            except: pass
            answer = 'Yes'
            label = label_org.lower()
            select = Select(select)
            selected_option = select.first_selected_option.text
            optionsText = []
            options = '"List of phone country codes"'
            optionsText = [option.text for option in select.options]
            options = "".join([f' "{option}",' for option in optionsText])
            prev_answer = selected_option
            if overwrite_previous_answers or selected_option == "Select an option":
                if any(w in label for w in ['phone country code', 'country code', 'dial code']):
                    matched_cc = None
                    cand_country = country.lower() if 'country' in globals() and country else "india"
                    for opt in optionsText:
                        opt_l = opt.lower()
                        if cand_country in opt_l and "+91" in opt:
                            matched_cc = opt
                            break
                        elif "+91" in opt or (cand_country in opt_l and "(+" in opt):
                            matched_cc = opt
                            break
                    if not matched_cc:
                        for opt in optionsText:
                            if cand_country in opt.lower():
                                matched_cc = opt
                                break
                    answer = matched_cc if matched_cc else "India (+91)"
                elif 'email' in label: 
                    answer = prev_answer if prev_answer and prev_answer != "Select an option" else email
                elif 'phone' in label: 
                    answer = prev_answer
                elif 'gender' in label or 'sex' in label: 
                    answer = gender
                elif 'disability' in label: 
                    answer = disability_status
                elif 'proficiency' in label: 
                    answer = 'Professional'
                # Add location handling
                elif any(loc_word in label for loc_word in ['location', 'city', 'state', 'country']):
                    if 'country' in label:
                        answer = country 
                    elif 'state' in label:
                        answer = state
                    elif 'city' in label:
                        answer = current_city if current_city else work_location
                    else:
                        answer = work_location
                else: 
                    answer = answer_common_questions(label,answer)
                try: 
                    select.select_by_visible_text(answer)
                except NoSuchElementException as e:
                    # Define similar phrases for common answers
                    possible_answer_phrases = []
                    if answer == 'Decline':
                        possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"]
                    elif 'yes' in answer.lower():
                        possible_answer_phrases = ["Yes", "Agree", "I do", "I have"]
                    elif 'no' in answer.lower():
                        possible_answer_phrases = ["No", "Disagree", "I don't", "I do not"]
                    else:
                        # Try partial matching for any answer
                        possible_answer_phrases = [answer]
                        # Add lowercase and uppercase variants
                        possible_answer_phrases.append(answer.lower())
                        possible_answer_phrases.append(answer.upper())
                        # Try without special characters
                        possible_answer_phrases.append(''.join(c for c in answer if c.isalnum()))
                    foundOption = False
                    for phrase in possible_answer_phrases:
                        for option in optionsText:
                            # Check if phrase is in option or option is in phrase (bidirectional matching)
                            if phrase.lower() in option.lower() or option.lower() in phrase.lower():
                                select.select_by_visible_text(option)
                                answer = option
                                foundOption = True
                                break
                    if not foundOption and 'qna_engine' in globals():
                        _, ai_matched = qna_engine.answer_select_or_radio(label_org, optionsText, work_location)
                        if ai_matched:
                            try:
                                select.select_by_visible_text(ai_matched)
                                answer = ai_matched
                                foundOption = True
                                print_lg(f'QnAEngine/AI selected "{ai_matched}" for "{label_org}"')
                            except Exception:
                                pass
                    if not foundOption:
                        # Fallback: random selection
                        print_lg(f'Failed to find an option with text "{answer}" for question labelled "{label_org}", answering randomly!')
                        select.select_by_index(randint(1, len(select.options)-1))
                        answer = select.first_selected_option.text
                        randomly_answered_questions.add((f'{label_org} [ {options} ]',"select"))
            questions_list.add((f'{label_org} [ {options} ]', answer, "select", prev_answer))
            continue
        
        # Check if it's a radio Question
        radio = try_xp(Question, './/fieldset[@data-test-form-builder-radio-button-form-component="true"]', False)
        if radio:
            prev_answer = None
            label = try_xp(radio, './/span[@data-test-form-builder-radio-button-form-component__title]', False)
            try: label = find_by_class(label, "visually-hidden", 2.0)
            except: pass
            label_org = label.text if label else "Unknown"
            answer = 'Yes'
            label = label_org.lower()

            label_org += ' [ '
            options = radio.find_elements(By.TAG_NAME, 'input')
            options_labels = []
            
            for option in options:
                id = option.get_attribute("id")
                option_label = try_xp(radio, f'.//label[@for="{id}"]', False)
                options_labels.append( f'"{option_label.text if option_label else "Unknown"}"<{option.get_attribute("value")}>' ) # Saving option as "label <value>"
                if option.is_selected(): prev_answer = options_labels[-1]
                label_org += f' {options_labels[-1]},'

            if overwrite_previous_answers or prev_answer is None:
                if 'citizenship' in label or 'employment eligibility' in label: answer = us_citizenship
                elif 'veteran' in label or 'protected' in label: answer = veteran_status
                elif 'disability' in label or 'handicapped' in label: 
                    answer = disability_status
                else: answer = answer_common_questions(label,answer)

                # Check QnAEngine if answer is still default 'Yes' to check for custom Q&A matches
                if 'qna_engine' in globals() and answer == 'Yes':
                    clean_opts = [lbl.split('"<')[0].strip('"') for lbl in options_labels]
                    q_target, _ = qna_engine.answer_select_or_radio(label_org, clean_opts, work_location)
                    if q_target:
                        answer = q_target

                foundOption = try_xp(radio, f".//label[normalize-space()='{answer}']", False)
                if foundOption: 
                    actions.move_to_element(foundOption).click().perform()
                else:    
                    possible_answer_phrases = ["Decline", "not wish", "don't wish", "Prefer not", "not want"] if answer == 'Decline' else [answer]
                    ele = options[0]
                    answer = options_labels[0]
                    for phrase in possible_answer_phrases:
                        for i, option_label in enumerate(options_labels):
                            if phrase in option_label:
                                foundOption = options[i]
                                ele = foundOption
                                answer = f'Decline ({option_label})' if len(possible_answer_phrases) > 1 else option_label
                                break
                        if foundOption: break
                    if not foundOption and 'qna_engine' in globals():
                        clean_opts = [lbl.split('"<')[0].strip('"') for lbl in options_labels]
                        _, ai_choice = qna_engine.answer_select_or_radio(label_org, clean_opts, work_location)
                        if ai_choice:
                            for i, c_opt in enumerate(clean_opts):
                                if c_opt.lower() == ai_choice.lower():
                                    ele = options[i]
                                    foundOption = ele
                                    answer = options_labels[i]
                                    break
                    actions.move_to_element(ele).click().perform()
                    if not foundOption: randomly_answered_questions.add((f'{label_org} ]',"radio"))
            else: answer = prev_answer
            questions_list.add((label_org+" ]", answer, "radio", prev_answer))
            continue
        
        # Check if it's a text question (including number, email, tel, or unspecified type)
        text = try_xp(Question, ".//input[not(@type) or @type='text' or @type='number' or @type='tel' or @type='email']", False)
        if text: 
            do_actions = False
            label = try_xp(Question, ".//label[@for]", False)
            try: label = label.find_element(By.CLASS_NAME,'visually-hidden')
            except: pass
            label_org = label.text if label else "Unknown"
            answer = "" # years_of_experience
            label = label_org.lower()

            # Inspect input attributes and question wrapper for numeric constraints
            inp_type = (text.get_attribute("type") or "").lower()
            inp_mode = (text.get_attribute("inputmode") or "").lower()
            inp_id = (text.get_attribute("id") or "").lower()
            inp_name = (text.get_attribute("name") or "").lower()
            step_attr = text.get_attribute("step")
            min_attr = text.get_attribute("min")
            q_html = (Question.get_attribute("outerHTML") or "")[:600].lower()

            feedback_text = ""
            try:
                fb_el = Question.find_elements(By.XPATH, ".//*[contains(@class, 'artdeco-inline-feedback') or contains(@class, 'fb-form-element-label__sub-title') or contains(@class, 'form-element__sub-title') or @role='alert']")
                displayed_texts = [f.text.strip() for f in fb_el if f.is_displayed() and f.text.strip()]
                if displayed_texts:
                    feedback_text = " ".join(displayed_texts).lower()
            except Exception:
                pass

            has_error = False
            try:
                err_el = Question.find_elements(By.XPATH, ".//*[contains(@class, 'artdeco-inline-feedback--error') or contains(@class, 'error') or @role='alert']")
                displayed_errs = [e.text.strip() for e in err_el if e.is_displayed() and e.text.strip()]
                if displayed_errs:
                    has_error = True
                    feedback_text += " " + " ".join(displayed_errs).lower()
            except Exception:
                pass

            requires_decimal_gt_zero = ("decimal number larger than 0" in feedback_text or "larger than 0.0" in feedback_text)

            is_contact_or_text_identity = any(w in label for w in [
                'city', 'location', 'address', 'street', 'state', 'zip', 'postal', 'country',
                'phone', 'mobile', 'email', 'name', 'linkedin', 'website', 'portfolio', 'headline'
            ])

            is_numeric_input = (
                not is_contact_or_text_identity
                and (
                    inp_type == "number"
                    or inp_mode in ["numeric", "decimal"]
                    or "numeric-input" in inp_id
                    or ":numeric" in inp_id
                    or inp_id.endswith("-numeric")
                    or inp_name.endswith("-numeric")
                    or step_attr is not None
                    or min_attr is not None
                    or requires_decimal_gt_zero
                    or any(w in feedback_text for w in ["decimal number", "whole number", "enter a number"])
                    or any(w in label for w in ["how many", "years of", "years experience", "rating", "scale of", "scale (", "between 0", "whole number", "gpa", "cgpa", "rate your"])
                    or (("?" in label or "*" in label) and any(kw in label for kw in ["engineering", "developer", "development", "project", "team", "backend", "frontend", "full stack", "qa", "testing", "python", "java", "sql", "aws", "automation", "rpa"]))
                )
            )

            prev_answer = text.get_attribute("value")
            if not prev_answer or overwrite_previous_answers or has_error:
                # 1. Primary candidate contact and identity fields (always string text)
                if 'city' in label or 'location' in label or 'address' in label:
                    answer = current_city if current_city else work_location
                    do_actions = True
                elif 'phone' in label or 'mobile' in label:
                    raw_phone = str(phone_number).strip()
                    digits = "".join(c for c in raw_phone if c.isdigit())
                    if digits.startswith("91") and len(digits) == 12:
                        answer = digits[2:]
                    elif digits.startswith("1") and len(digits) == 11:
                        answer = digits[1:]
                    else:
                        answer = digits if digits else raw_phone
                elif 'street' in label: answer = street
                elif 'signature' in label or 'legal name' in label: answer = full_name
                elif 'first name' in label or ('first' in label and 'name' in label and 'last' not in label): answer = first_name
                elif 'middle name' in label or ('middle' in label and 'name' in label and 'last' not in label): answer = middle_name
                elif 'last name' in label or ('last' in label and 'name' in label and 'first' not in label): answer = last_name
                elif 'name' in label:
                    if 'employer' in label or 'company' in label: answer = recent_employer
                    else: answer = full_name
                elif 'linkedin' in label: answer = linkedIn
                elif 'website' in label or 'blog' in label or 'portfolio' in label or 'link' in label: answer = website
                elif 'headline' in label: answer = linkedin_headline
                elif 'state' in label or 'province' in label: answer = state
                elif 'zip' in label or 'postal' in label or 'code' in label: answer = zipcode
                elif 'country' in label: answer = country
                # 2. Strict numeric inputs (years of experience, ratings, scale, gpa)
                elif is_numeric_input:
                    if requires_decimal_gt_zero:
                        try:
                            f_exp = float(years_of_experience)
                            ans_num = f_exp if f_exp > 0.0 else 2.0
                        except Exception:
                            ans_num = 2.0
                        answer = f"{ans_num:.1f}"
                    elif "scale" in label or "rating" in label or "rate your" in label:
                        if "1-5" in label or "1 to 5" in label:
                            answer = "4"
                        elif "1-10" in label or "1 to 10" in label:
                            answer = str(confidence_level) if 'confidence_level' in globals() else "9"
                        else:
                            answer = "4"
                    elif any(w in label for w in ['cgpa', 'gpa']):
                        answer = "8.0"
                    elif 'notice' in label:
                        answer = str(notice_period_months if 'month' in label else (notice_period_weeks if 'week' in label else 30))
                    elif any(w in label for w in ['salary', 'compensation', 'ctc', 'pay']):
                        answer = str(desired_salary if 'desired' in label else current_ctc)
                    else:
                        try:
                            f_val = float(years_of_experience)
                            if "decimal" in feedback_text:
                                answer = f"{f_val:.1f}"
                            else:
                                answer = str(int(f_val)) if f_val.is_integer() else str(f_val)
                        except Exception:
                            answer = str(years_of_experience)
                # 3. Other fields: notice period, compensation, AI/QnA engine
                elif 'notice' in label:
                    if 'month' in label:
                        answer = notice_period_months
                    elif 'week' in label:
                        answer = notice_period_weeks
                    else: answer = notice_period
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label: 
                    if 'current' in label or 'present' in label:
                        if 'month' in label:
                            answer = current_ctc_monthly
                        elif 'lakh' in label:
                            answer = current_ctc_lakhs
                        else:
                            answer = current_ctc
                    else:
                        if 'month' in label:
                            answer = desired_salary_monthly
                        elif 'lakh' in label:
                            answer = desired_salary_lakhs
                        else:
                            answer = desired_salary
                elif 'scale of 1-10' in label: answer = confidence_level
                elif ('hear' in label or 'come across' in label) and 'this' in label and ('job' in label or 'position' in label): answer = "LinkedIn"
                else: answer = answer_common_questions(label,answer)
                if answer == "" and 'qna_engine' in globals():
                    qna_ans = qna_engine.answer_text_question(label_org, job_description=job_description, work_location=work_location)
                    if qna_ans:
                        answer = qna_ans
                if answer == "":
                    if use_AI:
                        # 1. Primary path: UniversalAIService (Groq, NVIDIA, Ollama, DeepSeek, Gemini, etc.)
                        try:
                            from app.services.ai_service import UniversalAIService
                            _uai = UniversalAIService()
                            if _uai.get_config().get("enabled"):
                                from modules.ai.prompts import ai_answer_prompt
                                cand_ctx = user_information_all if 'user_information_all' in locals() else ""
                                prompt = ai_answer_prompt.format(cand_ctx, label_org)
                                if job_description and job_description != "Unknown":
                                    prompt += f"\nJob Description:\n{job_description}"
                                ans_txt = _uai.generate_text(prompt, temperature=0.0).strip()
                                if ans_txt:
                                    answer = ans_txt
                                    print_lg(f'AI Answered received via UniversalAIService for "{label_org}": "{answer}"')
                        except Exception as exc:
                            print_lg(f"UniversalAIService text answer notice: {exc}")

                    if (not answer or answer == "") and use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="text", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="text", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "text"))
                                answer = years_of_experience
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "text"))
                            answer = years_of_experience
                    elif not answer or answer == "":
                        randomly_answered_questions.add((label_org, "text"))
                        answer = years_of_experience

                final_ans = str(answer).strip()
                if is_numeric_input:
                    try:
                        f_val = float(final_ans)
                        if requires_decimal_gt_zero:
                            f_pos = f_val if f_val > 0.0 else 2.0
                            final_ans = f"{f_pos:.1f}"
                        elif "decimal" in feedback_text:
                            final_ans = f"{f_val:.1f}"
                        elif any(w in label for w in ["year", "experience", "month", "scale", "rating", "how many", "whole number", "between 0"]):
                            final_ans = str(int(round(f_val)))
                        elif f_val.is_integer():
                            final_ans = str(int(f_val))
                    except Exception:
                        final_ans = "2.0" if requires_decimal_gt_zero else str(years_of_experience)
                else:
                    max_len = text.get_attribute("maxlength")
                    if max_len:
                        try:
                            m_int = int(max_len)
                            if m_int > 0 and len(final_ans) > m_int:
                                trimmed = final_ans[:m_int]
                                last_space = trimmed.rfind(" ")
                                final_ans = trimmed[:last_space] if last_space > 20 else trimmed
                        except Exception:
                            pass

                try:
                    driver.execute_script("""
                        arguments[0].focus();
                        arguments[0].value = '';
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    """, text)
                except Exception:
                    pass
                text.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
                text.send_keys(final_ans)
                try:
                    driver.execute_script("""
                        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                        arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                    """, text)
                except Exception:
                    pass
                if do_actions:
                    sleep(1.5)
                    try:
                        actions.send_keys(Keys.ARROW_DOWN).perform()
                        sleep(0.3)
                        actions.send_keys(Keys.ENTER).perform()
                    except Exception:
                        pass
                    try:
                        suggestions = driver.find_elements(By.XPATH, "//div[contains(@class, 'basic-typeahead__selectable-list')]//li | //div[contains(@class, 'typeahead')]//li | //div[@role='listbox']//*[@role='option'] | //ul[contains(@class, 'typeahead')]//li")
                        if suggestions and any(s.is_displayed() for s in suggestions):
                            for s in suggestions:
                                if s.is_displayed():
                                    s.click()
                                    break
                    except Exception:
                        pass
            questions_list.add((label, text.get_attribute("value"), "text", prev_answer))
            continue

        # Check if it's a textarea question
        text_area = try_xp(Question, ".//textarea", False)
        if text_area:
            label = try_xp(Question, ".//label[@for]", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            prev_answer = text_area.get_attribute("value")
            has_error = False
            try:
                err_el = Question.find_elements(By.XPATH, ".//*[contains(@class, 'artdeco-inline-feedback--error') or contains(@class, 'error') or @role='alert']")
                if any(e.is_displayed() and e.text.strip() for e in err_el):
                    has_error = True
            except Exception:
                pass
            if not prev_answer or overwrite_previous_answers or has_error:
                if 'summary' in label: answer = linkedin_summary
                elif 'cover' in label: answer = cover_letter
                elif 'notice' in label:
                    if 'month' in label: answer = notice_period_months
                    elif 'week' in label: answer = notice_period_weeks
                    else: answer = notice_period
                elif 'salary' in label or 'compensation' in label or 'ctc' in label or 'pay' in label:
                    if 'current' in label or 'present' in label:
                        if 'month' in label: answer = current_ctc_monthly
                        elif 'lakh' in label: answer = current_ctc_lakhs
                        else: answer = current_ctc
                    else:
                        if 'month' in label: answer = desired_salary_monthly
                        elif 'lakh' in label: answer = desired_salary_lakhs
                        else: answer = desired_salary
                elif any(k in label for k in ['experience', 'years']):
                    answer = years_of_experience
                else:
                    answer = answer_common_questions(label, answer)
                if (not answer or answer == "") and 'qna_engine' in globals():
                    qna_ans = qna_engine.answer_text_question(label_org, job_description=job_description, work_location=work_location)
                    if qna_ans:
                        answer = qna_ans
                if answer == "":
                    if use_AI:
                        # 1. Primary path: UniversalAIService (Groq, NVIDIA, Ollama, DeepSeek, Gemini, etc.)
                        try:
                            from app.services.ai_service import UniversalAIService
                            _uai = UniversalAIService()
                            if _uai.get_config().get("enabled"):
                                from modules.ai.prompts import ai_answer_prompt
                                cand_ctx = user_information_all if 'user_information_all' in locals() else ""
                                prompt = ai_answer_prompt.format(cand_ctx, label_org)
                                if job_description and job_description != "Unknown":
                                    prompt += f"\nJob Description:\n{job_description}"
                                ans_txt = _uai.generate_text(prompt, temperature=0.0).strip()
                                if ans_txt:
                                    answer = ans_txt
                                    print_lg(f'AI Answered received via UniversalAIService for "{label_org}": "{answer}"')
                        except Exception as exc:
                            print_lg(f"UniversalAIService textarea answer notice: {exc}")

                    if (not answer or answer == "") and use_AI and aiClient:
                        try:
                            if ai_provider.lower() == "openai":
                                answer = ai_answer_question(aiClient, label_org, question_type="textarea", job_description=job_description, user_information_all=user_information_all)
                            elif ai_provider.lower() == "deepseek":
                                answer = deepseek_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            elif ai_provider.lower() == "gemini":
                                answer = gemini_answer_question(aiClient, label_org, options=None, question_type="textarea", job_description=job_description, about_company=None, user_information_all=user_information_all)
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                            if answer and isinstance(answer, str) and len(answer) > 0:
                                print_lg(f'AI Answered received for question "{label_org}" \nhere is answer: "{answer}"')
                            else:
                                randomly_answered_questions.add((label_org, "textarea"))
                                answer = ""
                        except Exception as e:
                            print_lg("Failed to get AI answer!", e)
                            randomly_answered_questions.add((label_org, "textarea"))
                            answer = ""
                    elif not answer or answer == "":
                        randomly_answered_questions.add((label_org, "textarea"))
            if not answer or answer == "":
                answer = str(qna_engine.prof.get("summary", "Experienced automation engineer with strong technical background.")) if 'qna_engine' in globals() else "Experienced automation engineer with strong technical background."
                randomly_answered_questions.add((label_org, "textarea"))
            try:
                driver.execute_script("""
                    arguments[0].focus();
                    arguments[0].value = '';
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                """, text_area)
            except Exception:
                pass
            text_area.send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            text_area.send_keys(str(answer).strip())
            try:
                driver.execute_script("""
                    arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
                    arguments[0].dispatchEvent(new Event('blur', { bubbles: true }));
                """, text_area)
            except Exception:
                pass
            questions_list.add((label, text_area.get_attribute("value"), "textarea", prev_answer))
            continue

        # Check if it's a checkbox question
        checkbox = try_xp(Question, ".//input[@type='checkbox']", False)
        if checkbox:
            label = try_xp(Question, ".//span[@class='visually-hidden']", False)
            label_org = label.text if label else "Unknown"
            label = label_org.lower()
            answer = try_xp(Question, ".//label[@for]", False)  # Sometimes multiple checkboxes are given for 1 question, Not accounted for that yet
            answer = answer.text if answer else "Unknown"
            prev_answer = checkbox.is_selected()
            checked = prev_answer
            if not prev_answer:
                try:
                    actions.move_to_element(checkbox).click().perform()
                    checked = True
                except Exception as e: 
                    print_lg("Checkbox click failed!", e)
                    pass
            questions_list.add((f'{label} ([X] {answer})', checked, "checkbox", prev_answer))
            continue


    # Select todays date
    try_xp(driver, "//button[contains(@aria-label, 'This is today')]")

    # Collect important skills
    # if 'do you have' in label and 'experience' in label and ' in ' in label -> Get word (skill) after ' in ' from label
    # if 'how many years of experience do you have in ' in label -> Get word (skill) after ' in '

    return questions_list




def external_apply(pagination_element: WebElement, job_id: str, job_link: str, resume: str, date_listed, application_link: str, screenshot_name: str, title: str = "", company: str = "", work_location: str = "", description: str = "") -> tuple[bool, str, int]:
    '''
    Function to extract and save external company portal job applications without navigating away.
    In Hybrid mode (ALL / easy_apply_only=False), harvests destination ATS link & full JD.
    In Easy Apply only mode, skips the external job.
    '''
    global tabs_count, dailyEasyApplyLimitReached, failed_count
    if easy_apply_only:
        try:
            if "exceeded the daily application limit" in driver.find_element(By.CLASS_NAME, "artdeco-inline-feedback__message").text:
                dailyEasyApplyLimitReached = True
        except:
            pass
        print_lg(f"Skipping external job {job_id} because Easy Apply Only mode is active.")
        return True, application_link, tabs_count

    try:
        ext_url = None

        def _unwrap_redirect(u: str) -> str:
            if not u:
                return u
            from urllib.parse import urlparse, parse_qs, unquote
            try:
                parsed = urlparse(u)
                qs = parse_qs(parsed.query)
                for k in ["url", "target", "dest", "redirect", "redirect_url", "destUrl"]:
                    if k in qs and qs[k]:
                        cand = unquote(qs[k][0]).strip()
                        if cand.startswith("http") and "linkedin.com" not in cand.lower():
                            return cand
            except Exception:
                pass
            return u

        # Locate the external apply button or link with all possible LinkedIn variations
        apply_btn = try_xp(
            driver,
            ".//button[contains(@class,'jobs-apply-button')] | "
            ".//a[contains(@class,'jobs-apply-button')] | "
            "//div[contains(@class, 'jobs-unified-top-card')]//button[contains(., 'Apply')] | "
            "//button[@id='topbar-apply'] | "
            "//button[contains(@aria-label, 'Apply to')]",
            False
        )
        
        # 1. Attempt static URL inspection from attributes
        if apply_btn:
            for attr in ["href", "data-apply-url", "data-url", "data-target-url", "data-session-redirect-url"]:
                try:
                    val = apply_btn.get_attribute(attr)
                    val = _unwrap_redirect(val)
                    if val and val.strip().startswith("http") and "linkedin.com" not in val.lower():
                        ext_url = val.strip()
                        break
                except Exception:
                    pass
            
            # Check child or ancestor anchors
            if not ext_url:
                try:
                    for a in apply_btn.find_elements(By.TAG_NAME, "a"):
                        h = _unwrap_redirect(a.get_attribute("href"))
                        if h and h.strip().startswith("http") and "linkedin.com" not in h.lower():
                            ext_url = h.strip()
                            break
                except Exception:
                    pass

        # 2. If static inspection didn't find direct external URL, click to resolve external redirect
        if not ext_url and apply_btn:
            initial_windows = list(driver.window_handles)
            try:
                apply_btn.click()
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", apply_btn)
                except Exception:
                    pass
            
            sleep(0.8)
            # Handle intermediate redirect confirmation if LinkedIn shows "Continue" modal
            continue_btn = try_xp(
                driver,
                "//button[contains(normalize-space(.), 'Continue')] | "
                "//a[contains(normalize-space(.), 'Continue')] | "
                "//button[contains(@aria-label, 'Continue')] | "
                "//button[contains(@class, 'artdeco-modal__confirm-dialog-btn')]",
                False
            )
            if continue_btn:
                try:
                    continue_btn.click()
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", continue_btn)
                    except Exception:
                        pass
            
            # Wait up to 3 seconds for new tab to appear
            tabs_after = list(driver.window_handles)
            if len(tabs_after) <= len(initial_windows):
                for _ in range(6):
                    sleep(0.5)
                    tabs_after = list(driver.window_handles)
                    if len(tabs_after) > len(initial_windows):
                        break

            if len(tabs_after) > len(initial_windows):
                new_tab = [w for w in tabs_after if w not in initial_windows][-1]
                driver.switch_to.window(new_tab)
                
                # Wait up to 4s for redirect to resolve away from about:blank or LinkedIn tracker
                for _ in range(8):
                    cur_u = driver.current_url or ""
                    if cur_u and "about:blank" not in cur_u and "linkedin.com/jobs/view/externalApply" not in cur_u and "linkedin.com/safety/go" not in cur_u:
                        ext_url = cur_u
                        break
                    sleep(0.5)
                else:
                    ext_url = _unwrap_redirect(driver.current_url or "")
                
                ext_url = _unwrap_redirect(ext_url)
                
                # Cleanly close the external tab and switch back to LinkedIn
                try:
                    if driver.current_window_handle != linkedIn_tab:
                        driver.close()
                except Exception:
                    pass

                # Guard against any lingering rogue popup tabs: keep ONLY linkedIn_tab open
                try:
                    for handle in list(driver.window_handles):
                        if handle != linkedIn_tab:
                            driver.switch_to.window(handle)
                            driver.close()
                except Exception:
                    pass
                driver.switch_to.window(linkedIn_tab)
            else:
                driver.switch_to.window(linkedIn_tab)

        if not ext_url:
            ext_url = job_link or f"https://www.linkedin.com/jobs/view/{job_id}/"

        application_link = ext_url
        print_lg(f'Harvested external company portal link: "{application_link}"')

        # Emit [TRACKER] event so the dashboard/desktop app records COMPANY_PORTAL
        try:
            import json
            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'EXTERNAL', 'application_method': 'COMPANY_PORTAL', 'application_url': application_link, 'description': (description if description != 'Unknown' else ''), 'reason': 'Direct apply on company website'})}", flush=True)
        except Exception:
            pass

        return False, application_link, tabs_count

    except Exception as e:
        print_lg("Failed to extract external apply link!", e)
        failed_job(job_id, job_link, resume, date_listed, "Probably didn't find Apply button or unable to switch tabs.", e, application_link, screenshot_name)
        failed_count += 1
        return True, application_link, tabs_count



def follow_company(modal: WebDriver = driver) -> None:
    '''
    Function to follow or un-follow easy applied companies based om `follow_companies`
    '''
    try:
        follow_checkbox_input = try_xp(modal, ".//input[@id='follow-company-checkbox' and @type='checkbox']", False)
        if follow_checkbox_input and follow_checkbox_input.is_selected() != follow_companies:
            try_xp(modal, ".//label[@for='follow-company-checkbox']")
    except Exception as e:
        print_lg("Failed to update follow companies checkbox!", e)
    


#< Failed attempts logging
def failed_job(job_id: str, job_link: str, resume: str, date_listed, error: str, exception: Exception, application_link: str, screenshot_name: str) -> None:
    '''
    Function to update failed jobs list in excel
    '''
    try:
        with open(failed_file_name, 'a', newline='', encoding='utf-8') as file:
            fieldnames = ['Job ID', 'Job Link', 'Resume Tried', 'Date listed', 'Date Tried', 'Assumed Reason', 'Stack Trace', 'External Job link', 'Screenshot Name']
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Job Link':truncate_for_csv(job_link), 'Resume Tried':truncate_for_csv(resume), 'Date listed':truncate_for_csv(date_listed), 'Date Tried':datetime.now(), 'Assumed Reason':truncate_for_csv(error), 'Stack Trace':truncate_for_csv(exception), 'External Job link':truncate_for_csv(application_link), 'Screenshot Name':truncate_for_csv(screenshot_name)})
            file.close()
    except Exception as e:
        print_lg("Failed to update failed jobs list!", e)
        show_modern_alert("Failed to update the excel of failed jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")


def screenshot(driver: WebDriver, job_id: str, failedAt: str) -> str:
    '''
    Function to to take screenshot for debugging
    - Returns screenshot name as String
    '''
    screenshot_name = "{} - {} - {}.png".format( job_id, failedAt, str(datetime.now()) )
    path = logs_folder_path+"/screenshots/"+screenshot_name.replace(":",".")
    # special_chars = {'*', '"', '\\', '<', '>', ':', '|', '?'}
    # for char in special_chars:  path = path.replace(char, '-')
    driver.save_screenshot(path.replace("//","/"))
    return screenshot_name
#>



def submitted_jobs(job_id: str, title: str, company: str, work_location: str, work_style: str, description: str, experience_required: int | Literal['Unknown', 'Error in extraction'], 
                   skills: list[str] | Literal['In Development'], hr_name: str | Literal['Unknown'], hr_link: str | Literal['Unknown'], resume: str, 
                   reposted: bool, date_listed: datetime | Literal['Unknown'], date_applied:  datetime | Literal['Pending'], job_link: str, application_link: str, 
                   questions_list: set | None, connect_request: Literal['In Development']) -> None:
    '''
    Function to create or update the Applied jobs CSV file, once the application is submitted successfully
    '''
    try:
        with open(file_name, mode='a', newline='', encoding='utf-8') as csv_file:
            fieldnames = ['Job ID', 'Title', 'Company', 'Work Location', 'Work Style', 'About Job', 'Experience required', 'Skills required', 'HR Name', 'HR Link', 'Resume', 'Re-posted', 'Date Posted', 'Date Applied', 'Job Link', 'External Job link', 'Questions Found', 'Connect Request']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            if csv_file.tell() == 0: writer.writeheader()
            writer.writerow({'Job ID':truncate_for_csv(job_id), 'Title':truncate_for_csv(title), 'Company':truncate_for_csv(company), 'Work Location':truncate_for_csv(work_location), 'Work Style':truncate_for_csv(work_style), 
                            'About Job':truncate_for_csv(description), 'Experience required': truncate_for_csv(experience_required), 'Skills required':truncate_for_csv(skills), 
                                'HR Name':truncate_for_csv(hr_name), 'HR Link':truncate_for_csv(hr_link), 'Resume':truncate_for_csv(resume), 'Re-posted':truncate_for_csv(reposted), 
                                'Date Posted':truncate_for_csv(date_listed), 'Date Applied':truncate_for_csv(date_applied), 'Job Link':truncate_for_csv(job_link), 
                                'External Job link':truncate_for_csv(application_link), 'Questions Found':truncate_for_csv(questions_list), 'Connect Request':truncate_for_csv(connect_request)})
        csv_file.close()
        try:
            import json
            is_ext = application_link != "Easy Applied" and application_link
            status_val = "EXTERNAL" if is_ext else "SUBMITTED"
            method_val = "COMPANY_PORTAL" if is_ext else "EASY_APPLY"
            tracker_payload = {
                'platform': 'linkedin',
                'job_id': str(job_id),
                'title': str(title),
                'company': str(company),
                'location': str(work_location),
                'status': status_val,
                'application_method': method_val,
            }
            if is_ext:
                tracker_payload['application_url'] = application_link
                tracker_payload['reason'] = 'Direct apply on company website'
            if description and description != 'Unknown':
                tracker_payload['description'] = description
            print(f"[TRACKER] {json.dumps(tracker_payload)}", flush=True)
        except Exception:
            pass
    except Exception as e:
        print_lg("Failed to update submitted jobs list!", e)
        show_modern_alert("Failed to update the excel of applied jobs!\nProbably because of 1 of the following reasons:\n1. The file is currently open or in use by another program\n2. Permission denied to write to the file\n3. Failed to find the file", "Failed Logging")



def dismiss_post_apply_modal(drv, timeout: float = 6.0) -> bool:
    '''
    Dismisses LinkedIn post-apply success modals (e.g. 'Your application was sent to...',
    'Turn your resume into a profile...', 'Not now', 'Done', or modal 'Dismiss' / 'Close').
    '''
    import time
    start = time.time()
    dismissed = False

    while time.time() - start < timeout:
        dismiss_xpaths = [
            # 1. "Not now" button on the post-apply upsell modal
            "//button[contains(normalize-space(.), 'Not now')]",
            ".//span[normalize-space(.)='Not now']/ancestor::button",
            # 2. "Done" button on post-apply dialogs
            "//button[contains(normalize-space(.), 'Done')]",
            ".//span[normalize-space(.)='Done']/ancestor::button",
            # 3. Modal close / dismiss 'X' button
            "//button[@aria-label='Dismiss']",
            "//button[@aria-label='Close']",
            "//button[contains(@class, 'artdeco-modal__dismiss')]",
            "//button[@data-test-modal-close-btn]",
            # 4. Any button inside post-apply modal container
            "//div[contains(@class, 'artdeco-modal')]//button[@aria-label='Dismiss']",
            "//div[contains(@role, 'dialog')]//button[@aria-label='Dismiss']",
        ]

        found = False
        for xp in dismiss_xpaths:
            try:
                elems = drv.find_elements(By.XPATH, xp)
                for el in elems:
                    if el.is_displayed():
                        try:
                            el.click()
                        except Exception:
                            drv.execute_script("arguments[0].click();", el)
                        print_lg(f"Successfully dismissed post-apply dialog via '{xp}'")
                        dismissed = True
                        found = True
                        sleep(0.5)
                        break
                if found:
                    break
            except Exception:
                continue

        # If dismissed, verify visible modals
        try:
            open_modals = drv.find_elements(By.XPATH, "//div[contains(@class, 'artdeco-modal') and @role='dialog']")
            visible_modals = [m for m in open_modals if m.is_displayed()]
            if not visible_modals:
                break
        except Exception:
            break

        # Fallback: send ESCAPE
        try:
            actions.send_keys(Keys.ESCAPE).perform()
        except Exception:
            pass

        sleep(0.5)

    # Final cleanup: if modal backdrop lingers in DOM, remove it via JS
    try:
        drv.execute_script("""
            const backdrops = document.querySelectorAll('.artdeco-modal-overlay, #artdeco-modal-outlet .artdeco-modal-overlay');
            backdrops.forEach(b => b.remove());
        """)
    except Exception:
        pass

    return dismissed


# Function to discard the job application and close any leftover modals
def discard_job() -> None:
    try:
        actions.send_keys(Keys.ESCAPE).perform()
    except Exception:
        pass
    buffer(0.5)

    # Click 'Discard' button on confirmation popups if visible
    discard_selectors = [
        "//button[@data-control-name='discard_application_confirm_btn']",
        "//button[contains(@class, 'artdeco-modal__confirm-dialog-btn') and contains(., 'Discard')]",
        "//button[contains(@data-test-dialog-secondary-action, '') and contains(., 'Discard')]",
        "//button[contains(@class, 'artdeco-button--secondary') and contains(., 'Discard')]",
        "//button[normalize-space(.)='Discard']",
        ".//span[normalize-space(.)='Discard']/ancestor::button",
        "//button[@aria-label='Discard']",
        "//button[contains(normalize-space(.), 'Not now')]",
    ]
    for sel in discard_selectors:
        try:
            btns = driver.find_elements(By.XPATH, sel)
            for btn in btns:
                if btn.is_displayed():
                    try:
                        btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", btn)
                    buffer(click_gap)
                    break
        except Exception:
            pass

    # Ensure any lingering modal backdrop is dismissed
    try:
        actions.send_keys(Keys.ESCAPE).perform()
    except Exception:
        pass
    buffer(0.3)






# Function to apply to jobs
def apply_to_jobs(search_terms: list[str]) -> None:
    applied_jobs = get_applied_job_ids()
    rejected_jobs = set()
    blacklisted_companies = set()
    global current_city, failed_count, skip_count, easy_applied_count, external_jobs_count, tabs_count, pause_before_submit, pause_at_failed_question, useNewResume, daily_application_goal, dailyEasyApplyLimitReached
    current_city = current_city.strip()

    if randomize_search_order:  shuffle(search_terms)
    for searchTerm in search_terms:
        search_url = build_search_url(searchTerm)
        safe_driver_get(driver, search_url, 30)
        print_lg("\n________________________________________________________________________________________________________________________\n")
        print_lg(f'\n>>>> Now searching for "{searchTerm}" <<<<\n\n')
        print_lg(f'Direct Search URL: {search_url}\n')

        apply_filters()

        current_count = 0
        consecutive_skips = 0
        should_switch_term = False
        try:
            while current_count < switch_number and not should_switch_term:
                # Wait until job listings are loaded
                wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-occludable-job-id]")))

                # Scroll container to hydrate all occludable job cards and pagination controls
                scroll_job_list(driver)

                pagination_element, current_page = get_page_info()
                if current_page is None:
                    current_page = 1

                page_applied_count = 0

                # Find all job listings in current page
                buffer(2)
                job_listings = driver.find_elements(By.XPATH, "//li[@data-occludable-job-id]")  

            
                for job in job_listings:
                    if keep_screen_awake and pyautogui is not None: pyautogui.press('shiftright')
                    if current_count >= switch_number:
                        should_switch_term = True
                        break
                    if consecutive_skips >= consecutive_skips_limit:
                        print_lg(f'\n>>>> Relevance decay: {consecutive_skips} consecutive jobs skipped for "{searchTerm}". Switching to next keyword! <<<<\n')
                        should_switch_term = True
                        break
                    print_lg("\n-@-\n")
                    try:
                        dismiss_post_apply_modal(driver, timeout=1.0)
                    except Exception:
                        pass

                    try:
                        job_id,title,company,work_location,work_style,skip,is_already_applied = get_job_main_details(job, blacklisted_companies, rejected_jobs, applied_jobs=applied_jobs)
                    except Exception as details_err:
                        print_lg(f"Error reading job details: {details_err}. Skipping this card.")
                        consecutive_skips += 1
                        continue
                    
                    if skip:
                        if not is_already_applied:
                            consecutive_skips += 1
                        continue
                    # Redundant fail safe check for applied jobs!
                    try:
                        if job_id in applied_jobs or find_by_class(driver, "jobs-s-apply__application-link", 2):
                            print_lg(f'Already applied to "{title} | {company}" job. Job ID: {job_id}!')
                            # Note: Already applied jobs do NOT increment consecutive_skips
                            try:
                                import json
                                print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'SKIPPED', 'reason': 'Already applied'})}", flush=True)
                            except Exception:
                                pass
                            continue
                    except Exception as e:
                        print_lg(f'Trying to Apply to "{title} | {company}" job. Job ID: {job_id}')

                    try:
                        import json
                        print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'QUALIFIED'})}", flush=True)
                    except Exception:
                        pass

                    job_link = "https://www.linkedin.com/jobs/view/"+job_id
                    application_link = "Easy Applied"
                    date_applied = "Pending"
                    hr_link = "Unknown"
                    hr_name = "Unknown"
                    connect_request = "In Development" # Still in development
                    date_listed = "Unknown"
                    skills = "Needs an AI" # Still in development
                    resume = "Pending"
                    reposted = False
                    questions_list = None
                    screenshot_name = "Not Available"

                    try:
                        rejected_jobs, blacklisted_companies, jobs_top_card = check_blacklist(rejected_jobs,job_id,company,blacklisted_companies)
                    except ValueError as e:
                        print_lg(e, 'Skipping this job!\n')
                        failed_job(job_id, job_link, resume, date_listed, "Found Blacklisted words in About Company", e, "Skipped", screenshot_name)
                        skip_count += 1
                        consecutive_skips += 1
                        try:
                            import json
                            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'SKIPPED', 'reason': 'Blacklisted company/words'})}", flush=True)
                        except Exception:
                            pass
                        continue
                    except Exception as e:
                        print_lg("Failed to scroll to About Company!")
                        # print_lg(e)



                    # Hiring Manager info
                    try:
                        hr_info_card = WebDriverWait(driver, 2).until(
                            EC.presence_of_element_located(
                                 (By.CLASS_NAME, "hirer-card__hirer-information")
                            )
                        )   
                            
                        hr_link = hr_info_card.find_element(By.TAG_NAME, "a").get_attribute("href")
                        hr_name = hr_info_card.find_element(By.TAG_NAME, "span").text
                        
                    except Exception as e:
                         print_lg(f"No recruiter card found for this job. Continuing... ({e})")
                         hr_link = ""
                         hr_name = ""

                    
                        # if connect_hr:
                        #     driver.switch_to.new_window('tab')
                        #     driver.get(hr_link)
                        #     wait_span_click("More")
                        #     wait_span_click("Connect")
                        #     wait_span_click("Add a note")
                        #     message_box = driver.find_element(By.XPATH, "//textarea")
                        #     message_box.send_keys(connect_request_message)
                        #     if close_tabs: driver.close()
                        #     driver.switch_to.window(linkedIn_tab) 
                        # def message_hr(hr_info_card):
                        #     if not hr_info_card: return False
                        #     hr_info_card.find_element(By.XPATH, ".//span[normalize-space()='Message']").click()
                        #     message_box = driver.find_element(By.XPATH, "//div[@aria-label='Write a message…']")
                        #     message_box.send_keys()
                        #     try_xp(driver, "//button[normalize-space()='Send']")        
                    except Exception as e:
                        print_lg(f'HR info was not given for "{title}" with Job ID: {job_id}!')
                        # print_lg(e)


                    # Calculation of date posted
                    try:
                        # try: time_posted_text = find_by_class(driver, "jobs-unified-top-card__posted-date", 2).text
                        # except: 
                        time_posted_text = jobs_top_card.find_element(By.XPATH, './/span[contains(normalize-space(), " ago")]').text
                        print("Time Posted: " + time_posted_text)
                        if time_posted_text.__contains__("Reposted"):
                            reposted = True
                            time_posted_text = time_posted_text.replace("Reposted", "")
                        date_listed = calculate_date_posted(time_posted_text.strip())
                    except Exception as e:
                        print_lg("Failed to calculate the date posted!",e)


                    description, experience_required, skip, reason, message = get_job_description()
                    if skip:
                        print_lg(message)
                        failed_job(job_id, job_link, resume, date_listed, reason, message, "Skipped", screenshot_name)
                        rejected_jobs.add(job_id)
                        skip_count += 1
                        consecutive_skips += 1
                        try:
                            import json
                            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'SKIPPED', 'reason': str(reason or 'Criteria mismatch')})}", flush=True)
                        except Exception:
                            pass
                        continue

                    
                    if use_AI and description != "Unknown":
                        try:
                            if ai_provider.lower() == "openai":
                                skills = ai_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "deepseek":
                                skills = deepseek_extract_skills(aiClient, description)
                            elif ai_provider.lower() == "gemini":
                                skills = gemini_extract_skills(aiClient, description)
                            else:
                                skills = "In Development"
                            print_lg(f"Extracted skills using {ai_provider} AI")
                        except Exception as e:
                            print_lg("Failed to extract skills:", e)
                            skills = "Error extracting skills"

                    uploaded = False
                    # Case 1: Easy Apply Button
                    # First try the classic button with "Easy" in aria-label
                    is_easy_apply = try_xp(driver, ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]")
                    # Fallback 1: check if apply link contains Easy Apply URL pattern
                    if not is_easy_apply:
                        try:
                            apply_link_el = driver.find_element(By.XPATH, ".//a[contains(@href, 'openSDUIApplyFlow=true')]")
                            if apply_link_el:
                                apply_link_el.click()
                                is_easy_apply = True
                                print_lg("Detected Easy Apply via URL pattern (openSDUIApplyFlow)")
                        except:
                            pass
                    # Fallback 2: check button text or aria-label for Easy Apply
                    if not is_easy_apply:
                        try:
                            apply_btn_el = try_xp(driver, ".//button[contains(@class,'jobs-apply-button')] | .//a[contains(@class,'jobs-apply-button')]", False)
                            if apply_btn_el:
                                btn_txt = (apply_btn_el.text or "").strip().lower()
                                btn_aria = (apply_btn_el.get_attribute("aria-label") or "").strip().lower()
                                if "easy" in btn_txt or "easy" in btn_aria:
                                    is_easy_apply = True
                                    print_lg("Detected Easy Apply via button text/aria inspection")
                        except Exception:
                            pass
                    if is_easy_apply:
                        try:
                            import json
                            print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'APPLYING', 'application_method': 'EASY_APPLY', 'description': (description if description != 'Unknown' else '')})}", flush=True)
                        except Exception:
                            pass

                        try: 
                            try:
                                errored = ""
                                modal = find_by_class(driver, "jobs-easy-apply-modal")
                                wait_span_click(modal, "Next", 1)
                                # if description != "Unknown":
                                #     resume = create_custom_resume(description)
                                resume = "Previous resume"
                                next_button = True
                                questions_list = set()
                                next_counter = 0
                                while next_button:
                                    next_counter += 1
                                    if next_counter >= 15: 
                                        if pause_at_failed_question:
                                            screenshot(driver, job_id, "Needed manual intervention for failed question")
                                            show_modern_alert("Couldn't answer one or more questions.\nPlease click \"Continue\" once done.\nDO NOT CLICK Back, Next or Review button in LinkedIn.\n\n\n\n\nYou can turn off \"Pause at failed question\" setting in config.py", "Help Needed", "Continue")
                                            next_counter = 1
                                            continue
                                        if questions_list: print_lg("Stuck for one or some of the following questions...", questions_list)
                                        screenshot_name = screenshot(driver, job_id, "Failed at questions")
                                        errored = "stuck"
                                        raise Exception("Seems like stuck in a continuous loop of next, probably because of new questions.")
                                    questions_list = answer_questions(modal, questions_list, work_location, job_description=description)
                                    if useNewResume and not uploaded: uploaded, resume = upload_resume(modal, default_resume_path)
                                    try: next_button = modal.find_element(By.XPATH, './/span[normalize-space(.)="Review"]') 
                                    except NoSuchElementException:  next_button = modal.find_element(By.XPATH, './/button[contains(span, "Next")]')
                                    try: next_button.click()
                                    except ElementClickInterceptedException: break    # Happens when it tries to click Next button in About Company photos section
                                    buffer(click_gap)

                            except NoSuchElementException: errored = "nose"
                            finally:
                                if questions_list and errored != "stuck": 
                                    print_lg("Answered the following questions...", questions_list)
                                    print("\n\n" + "\n".join(str(question) for question in questions_list) + "\n\n")
                                wait_span_click(driver, "Review", 1, scrollTop=True)
                                cur_pause_before_submit = pause_before_submit
                                if errored != "stuck" and cur_pause_before_submit:
                                    decision = show_modern_confirm('1. Please verify your information.\n2. If you edited something, please return to this final screen.\n3. DO NOT CLICK "Submit Application".\n\n\n\n\nYou can turn off "Pause before submit" setting in config.py\nTo TEMPORARILY disable pausing, click "Disable Pause"', "Confirm your information",["Disable Pause", "Discard Application", "Submit Application"])
                                    if decision == "Discard Application": raise Exception("Job application discarded by user!")
                                    pause_before_submit = False if "Disable Pause" == decision else True
                                    # try_xp(modal, ".//span[normalize-space(.)='Review']")
                                follow_company(modal)
                                if wait_span_click(driver, "Submit application", 2, scrollTop=True): 
                                    date_applied = datetime.now()
                                    sleep(1)
                                    dismiss_post_apply_modal(driver, timeout=6.0)
                                elif errored != "stuck" and cur_pause_before_submit and "Yes" in show_modern_confirm("You submitted the application, didn't you 😒?", "Failed to find Submit Application!", ["Yes", "No"]):
                                    date_applied = datetime.now()
                                    sleep(1)
                                    dismiss_post_apply_modal(driver, timeout=6.0)
                                else:
                                    print_lg("Since, Submit Application failed, discarding the job application...")
                                    # if screenshot_name == "Not Available":  screenshot_name = screenshot(driver, job_id, "Failed to click Submit application")
                                    # else:   screenshot_name = [screenshot_name, screenshot(driver, job_id, "Failed to click Submit application")]
                                    if errored == "nose": raise Exception("Failed to click Submit application 😑")


                        except Exception as e:
                            print_lg("Failed to Easy apply!")
                            # print_lg(e)
                            critical_error_log("Somewhere in Easy Apply process",e)
                            failed_job(job_id, job_link, resume, date_listed, "Problem in Easy Applying", e, application_link, screenshot_name)
                            failed_count += 1
                            consecutive_skips += 1
                            try:
                                import json
                                print(f"[TRACKER] {json.dumps({'platform': 'linkedin', 'job_id': str(job_id), 'title': str(title), 'company': str(company), 'location': str(work_location), 'status': 'FAILED', 'reason': str(e)})}", flush=True)
                            except Exception:
                                pass
                            discard_job()
                            continue
                    else:
                        # Case 2: Apply externally (Hybrid mode: extract company portal & JD without navigating away)
                        skip, application_link, tabs_count = external_apply(
                            pagination_element, job_id, job_link, resume, date_listed,
                            application_link, screenshot_name,
                            title=title, company=company, work_location=work_location, description=description
                        )
                        if dailyEasyApplyLimitReached:
                            print_lg("\n###############  Daily application limit for Easy Apply is reached!  ###############\n")
                            return
                        if skip:
                            consecutive_skips += 1
                            discard_job()
                            continue

                    submitted_jobs(job_id, title, company, work_location, work_style, description, experience_required, skills, hr_name, hr_link, resume, reposted, date_listed, date_applied, job_link, application_link, questions_list, connect_request)
                    if uploaded:   useNewResume = False

                    print_lg(f'Successfully saved "{title} | {company}" job. Job ID: {job_id} info')
                    current_count += 1
                    consecutive_skips = 0
                    page_applied_count += 1
                    if application_link == "Easy Applied": easy_applied_count += 1
                    else:   external_jobs_count += 1
                    applied_jobs.add(job_id)

                    total_applied_today = easy_applied_count + external_jobs_count
                    if total_applied_today >= daily_application_goal:
                        print_lg(f"\n🎯 [Daily Goal Reached] Reached daily goal of {daily_application_goal} applications on LinkedIn (Total applied: {total_applied_today}).")
                        should_cont, add_apps = show_modern_goal_dialog("LinkedIn", total_applied_today, daily_application_goal)
                        if should_cont and add_apps > 0:
                            daily_application_goal += add_apps
                            print_lg(f"🎯 [Daily Goal Extended] Extended daily goal by +{add_apps} applications. New goal: {daily_application_goal}. Resuming automation...\n")
                        else:
                            print_lg(f"🎯 [Daily Goal Completed] Finishing automation run cleanly at {total_applied_today} applications.\n")
                            dailyEasyApplyLimitReached = True
                            return



                if should_switch_term:
                    break

                # 1. Page Cap Check:
                if current_page >= max_pages_per_search:
                    print_lg(f"\n>>>> Reached page limit ({current_page}/{max_pages_per_search}) for '{searchTerm}'. Switching to next keyword! <<<<\n")
                    break

                # 2. Zero-Yield Page Check on Page 2+:
                if page_applied_count == 0 and current_page >= 2:
                    print_lg(f"\n>>>> Page {current_page} yielded 0 new applications for '{searchTerm}'. Switching to next keyword! <<<<\n")
                    break

                # Switching to next page
                if pagination_element is None or current_page is None:
                    print_lg(f"No pagination element found for '{searchTerm}'. Moving to next search term.")
                    break
                try:
                    next_page_btn = pagination_element.find_element(By.XPATH, f".//button[@aria-label='Page {current_page+1}']")
                    scroll_to_view(driver, next_page_btn)
                    try:
                        next_page_btn.click()
                    except Exception:
                        driver.execute_script("arguments[0].click();", next_page_btn)
                    print_lg(f"\n>-> Now on Page {current_page+1} \n")
                    buffer(3)
                except Exception as page_err:
                    print_lg(f"\n>-> Didn't find Page {current_page+1} ({page_err}). Completed search for '{searchTerm}'!\n")
                    break

        except Exception as e:
            if not is_browser_alive(driver):
                print_lg("Browser window closed or session is invalid. Ending application process.", e)
                raise e # Re-raise to be caught by main
            print_lg(f"Notice: Encountered issue during search for '{searchTerm}': {e}. Cleaning up and proceeding to next search term.")
            discard_job()
            critical_error_log("In Applier", e)

        
def interruptible_sleep(seconds: float, step: float = 1.0) -> None:
    elapsed = 0.0
    while elapsed < seconds:
        sleep(min(step, seconds - elapsed))
        elapsed += step


def run(total_runs: int) -> int:
    if dailyEasyApplyLimitReached:
        return total_runs
    print_lg("\n########################################################################################################################\n")
    print_lg(f"Date and Time: {datetime.now()}")
    print_lg(f"Cycle number: {total_runs}")
    print_lg(f"Currently looking for jobs posted within '{date_posted}' and sorting them by '{sort_by}'")
    apply_to_jobs(search_terms)
    print_lg("########################################################################################################################\n")
    if not dailyEasyApplyLimitReached and run_non_stop:
        from modules.human_behavior import cycle_sleep
        from modules.config_loader import get_platform
        ln_plat = get_platform("linkedin")
        sleep_mins = float(ln_plat.get("sleep_duration_minutes", 10))
        sleep_enabled = bool(ln_plat.get("sleep_mode_enabled", True))
        if sleep_enabled and sleep_mins > 0:
            cycle_sleep(duration_minutes=sleep_mins, platform_name="linkedin")
    buffer(3)
    return total_runs + 1



chatGPT_tab = False
linkedIn_tab = False

def main() -> None:
    total_runs = 1
    try:
        global linkedIn_tab, tabs_count, useNewResume, aiClient
        alert_title = "Error Occurred. Closing Browser!"
        validate_config()
        
        if not os.path.exists(default_resume_path):
            show_modern_alert(text='Your default resume "{}" is missing! Please update it\'s folder path "default_resume_path" in config.py\n\nOR\n\nAdd a resume with exact name and path (check for spelling mistakes including cases).\n\n\nFor now the bot will continue using your previous upload from LinkedIn!'.format(default_resume_path), title="Missing Resume", button="OK")
        if driver is None:
            print_lg("[CRITICAL] Chrome driver was not initialized. Aborting automation.")
            show_modern_alert(
                "Google Chrome failed to start.\n\nPlease check logs/errors.log or ensure Chrome is installed and closed before running.",
                "Browser Launch Failed",
                "OK",
            )
            sys.exit(1)

        # Check if already authenticated on LinkedIn via persistent session cookies
        tabs_count = len(driver.window_handles)
        safe_driver_get(driver, "https://www.linkedin.com/feed", 30)
        sleep(2)
        dismiss_linkedin_overlays(driver)
        if not is_logged_in_LN():
            print_lg("LinkedIn session not found on feed. Navigating to login...")
            login_LN()
        else:
            print_lg("Active LinkedIn session verified on feed! Skipping credential login.")

        if not is_logged_in_LN():
            print_lg("[CRITICAL] LinkedIn login could not be confirmed. Aborting automation immediately.")
            show_modern_alert(
                "Unable to confirm LinkedIn login.\n\nPlease check your credentials in Settings or sign in manually in Chrome before starting automation.",
                "Login Not Confirmed",
                "OK",
            )
            sys.exit(1)
        
        linkedIn_tab = driver.current_window_handle

        # # Login to ChatGPT in a new tab for resume customization
        # if use_resume_generator:
        #     try:
        #         driver.switch_to.new_window('tab')
        #         safe_driver_get(driver, "https://chat.openai.com/", 30)
        #         if not is_logged_in_GPT(): login_GPT()
        #         open_resume_chat()
        #         global chatGPT_tab
        #         chatGPT_tab = driver.current_window_handle
        #     except Exception as e:
        #         print_lg("Opening OpenAI chatGPT tab failed!")
        if use_AI:
            # Try Universal AI Service first (reads config from desktop Settings)
            try:
                from app.services.ai_service import UniversalAIService
                _universal_ai = UniversalAIService()
                _uni_client = _universal_ai.get_active_client()
                if _uni_client:
                    aiClient = _uni_client
                    print_lg("AI client created via Universal AI Service (desktop settings).")
                elif ai_provider == "gemini":
                    aiClient = gemini_create_client()
                else:
                    print_lg("Universal AI Service returned None; falling back to legacy client creation.")
                    raise ImportError("fallback")
            except Exception:
                # Legacy fallback: per-provider creation from config/secrets.py
                if ai_provider == "openai":
                    aiClient = ai_create_openai_client()
                elif ai_provider == "deepseek":
                    aiClient = deepseek_create_client()
                elif ai_provider == "gemini":
                    aiClient = gemini_create_client()
            if 'qna_engine' in globals() and aiClient:
                qna_engine.set_ai_client(aiClient)
                # Also wire Universal AI model config into QnA engine
                try:
                    from app.services.ai_service import UniversalAIService
                    qna_engine.set_universal_ai_service(UniversalAIService())
                except Exception:
                    pass

            try:
                about_company_for_ai = " ".join([word for word in (first_name+" "+last_name).split() if len(word) > 3])
                print_lg(f"Extracted about company info for AI: '{about_company_for_ai}'")
            except Exception as e:
                print_lg("Failed to extract about company info!", e)
        
        # Start applying to jobs
        driver.switch_to.window(linkedIn_tab)
        total_runs = run(total_runs)
        while(run_non_stop):
            if cycle_date_posted:
                date_options = ["Any time", "Past month", "Past week", "Past 24 hours"]
                global date_posted
                date_posted = date_options[date_options.index(date_posted)+1 if date_options.index(date_posted)+1 > len(date_options) else -1] if stop_date_cycle_at_24hr else date_options[0 if date_options.index(date_posted)+1 >= len(date_options) else date_options.index(date_posted)+1]
            if alternate_sortby:
                global sort_by
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
                total_runs = run(total_runs)
                sort_by = "Most recent" if sort_by == "Most relevant" else "Most relevant"
            total_runs = run(total_runs)
            if dailyEasyApplyLimitReached:
                break
        

    except (NoSuchWindowException, WebDriverException) as e:
        print_lg("Browser window closed or session is invalid. Exiting.", e)
    except Exception as e:
        critical_error_log("In Applier Main", e)
        if "read timed out" in str(e).lower() or "connectionpool" in str(e).lower():
            print_lg(f"Notice: Network/ChromeDriver socket timed out ({e}). Closing session cleanly.")
        else:
            show_modern_alert(e, alert_title)
    finally:
        summary = "Total runs: {}\nJobs Easy Applied: {}\nExternal job links collected: {}\nTotal applied or collected: {}\nFailed jobs: {}\nIrrelevant jobs skipped: {}\n".format(total_runs,easy_applied_count,external_jobs_count,easy_applied_count + external_jobs_count,failed_count,skip_count)
        print_lg(summary)
        print_lg("\n\nTotal runs:                     {}".format(total_runs))
        print_lg("Jobs Easy Applied:              {}".format(easy_applied_count))
        print_lg("External job links collected:   {}".format(external_jobs_count))
        print_lg("                              ----------")
        print_lg("Total applied or collected:     {}".format(easy_applied_count + external_jobs_count))
        print_lg("\nFailed jobs:                    {}".format(failed_count))
        print_lg("Irrelevant jobs skipped:        {}\n".format(skip_count))
        if randomly_answered_questions: print_lg("\n\nQuestions randomly answered:\n  {}  \n\n".format(";\n".join(str(question) for question in randomly_answered_questions)))
        timeSaved = (easy_applied_count * 80) + (external_jobs_count * 20) + (skip_count * 10)
        timeSavedMsg = ""
        if timeSaved > 0:
            timeSaved += 60
            timeSavedMsg = f"In this run, you saved approx {round(timeSaved/60)} mins ({timeSaved} secs)."
        msg = f"Summary:\n{summary}\n{timeSavedMsg}"
        print_lg(msg, "Closing the browser...")
        if tabs_count >= 10:
            msg = "NOTE: IF YOU HAVE MORE THAN 10 TABS OPENED, PLEASE CLOSE OR BOOKMARK THEM!\n\nOr it's highly likely that application will just open browser and not do anything next time!" 
            show_modern_alert(msg, "Info")
            print_lg("\n"+msg)
        if use_AI and aiClient:
            try:
                if ai_provider.lower() == "openai":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "deepseek":
                    ai_close_openai_client(aiClient)
                elif ai_provider.lower() == "gemini":
                    pass # Gemini client does not need to be closed
                print_lg(f"Closed {ai_provider} AI client.")
            except Exception as e:
                print_lg("Failed to close AI client:", e)
        try:
            if driver:
                driver.quit()
        except WebDriverException as e:
            print_lg("Browser already closed.", e)
        except Exception as e: 
            critical_error_log("When quitting...", e)


def parse_cli_args():
    """Parses command-line arguments for multi-platform routing."""
    import argparse
    parser = argparse.ArgumentParser(description="JobPilot Multi-Platform Automation")
    parser.add_argument(
        "--platform",
        choices=["linkedin", "naukri", "indeed", "foundit", "glassdoor", "universal", "all"],
        default="linkedin",
        help="Target platform to run automation on (default: linkedin)",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Target job/portal URL for universal application agent",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Runs production pre-flight readiness checks without launching browser or applying.",
    )
    args, _ = parser.parse_known_args()
    return args


if __name__ == "__main__":
    cli_args = parse_cli_args()
    if getattr(cli_args, "check_config", False):
        if cli_args.platform in ["naukri", "all"]:
            from platforms.naukri.preflight import run_preflight
            ready = run_preflight()
            if not ready:
                sys.exit(1)
        if cli_args.platform in ["linkedin", "all"]:
            from modules.validator import validate_config
            validate_config()
            print_lg("[Preflight] LinkedIn configuration valid.")
        if cli_args.platform in ["indeed", "all"]:
            print_lg("[Preflight] Indeed configuration valid.")
        if cli_args.platform in ["foundit", "all"]:
            from modules.config_loader import validate_foundit_config
            validate_foundit_config()
            print_lg("[Preflight] Foundit configuration valid.")
        if cli_args.platform in ["glassdoor", "all"]:
            from modules.config_loader import validate_glassdoor_config
            validate_glassdoor_config()
            print_lg("[Preflight] Glassdoor configuration valid.")
        if cli_args.platform in ["universal"]:
            print_lg("[Preflight] Universal AI application agent configuration valid.")
        sys.exit(0)

    if cli_args.platform == "naukri":
        from platforms.router import PlatformRouter
        router = PlatformRouter()
        router.run_naukri()
    elif cli_args.platform == "indeed":
        from platforms.router import PlatformRouter
        router = PlatformRouter()
        router.run_indeed()
    elif cli_args.platform == "foundit":
        from platforms.router import PlatformRouter
        router = PlatformRouter()
        router.run_foundit()
    elif cli_args.platform == "glassdoor":
        from platforms.router import PlatformRouter
        router = PlatformRouter()
        router.run_glassdoor()
    elif cli_args.platform == "universal":
        from platforms.router import PlatformRouter
        router = PlatformRouter()
        target_url = getattr(cli_args, "url", None)
        router.run_universal(target_url=target_url)
    elif cli_args.platform == "all":
        from platforms.router import PlatformRouter
        # Execute LinkedIn first
        main()
        # Execute Naukri sequentially
        router = PlatformRouter()
        router.run_naukri()
        # Execute Indeed sequentially
        router.run_indeed()
        # Execute Foundit sequentially
        router.run_foundit()
        # Execute Glassdoor sequentially
        router.run_glassdoor()
    else:
        # Default: LinkedIn
        main()

