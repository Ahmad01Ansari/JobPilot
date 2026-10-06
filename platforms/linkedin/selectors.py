"""LinkedIn DOM Selectors and URLs.

Centralizes all HTML classes, IDs, XPaths, and CSS selectors for LinkedIn.com.
Allows UI changes to be maintained without modifying core automation logic.
"""

# URLs
HOME_URL = "https://www.linkedin.com/feed/"
LOGIN_URL = "https://www.linkedin.com/login"
JOBS_HOME_URL = "https://www.linkedin.com/jobs/"

# Session / Authentication indicators
LOGGED_IN_INDICATORS = [
    '//button[contains(normalize-space(.), "Start a post")]',
    '//nav[contains(@class, "global-nav")]',
    './/img[contains(@class, "global-nav__me-photo")]',
    '//button[contains(@class, "global-nav__primary-link-me-menu-trigger")]',
    '//div[contains(@class, "feed-identity-module")]',
    '//a[contains(@href, "/feed/")]',
]

GUEST_INDICATORS = [
    '//a[contains(@href, "/login") or contains(@href, "/signin")]',
    '//a[contains(normalize-space(.), "Sign in") or contains(normalize-space(.), "Join now")]',
    '//button[contains(normalize-space(.), "Sign in") or contains(normalize-space(.), "Join now")]',
    '//button[@data-tracking-control-name="public_jobs_nav-header-signin"]',
    '//div[contains(@class, "sign-in-modal")]',
    '//div[contains(@class, "authwall")]',
    '//section[contains(@class, "guest-homepage")]',
]

TWO_FA_KEYWORDS = [
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

POST_LOGIN_DISMISS_XPATHS = [
    '//button[contains(normalize-space(.), "Remember this device") or contains(normalize-space(.), "Remember this computer")]',
    '//button[contains(normalize-space(.), "Trust this browser") or contains(normalize-space(.), "Trust device")]',
    '//button[contains(normalize-space(.), "Continue") or contains(normalize-space(.), "Done")]',
    '//button[contains(normalize-space(.), "Skip for now") or contains(normalize-space(.), "Not now")]',
    '//button[contains(normalize-space(.), "Remind me later")]',
    '//a[contains(normalize-space(.), "Skip for now") or contains(normalize-space(.), "Not now")]',
]

# Job Search & Listings
JOB_RESULTS_CONTAINER = ".jobs-search-results-list"
JOB_CARD_ITEMS = [
    "li[data-occludable-job-id]",
    ".jobs-search-results__list-item",
    "div.job-card-container",
]

# Job Details & Description
JOB_DETAILS_CONTAINER = ".jobs-search__job-details"
JOB_DESCRIPTION_SELECTORS = [
    "div#job-details",
    "div.dang-inner-html",
    "article.jobs-description__container",
    "div.jobs-description-content__text",
    "div.jobs-box__html-content",
    "div.jobs-description__content",
]

JOB_TITLE_SELECTORS = [
    "h1.t-24",
    "h2.job-card-list__title",
    ".jobs-unified-top-card__job-title",
    "a.job-card-list__title",
]

JOB_COMPANY_SELECTORS = [
    ".job-card-container__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".job-card-container__primary-description",
]

JOB_LOCATION_SELECTORS = [
    ".job-card-container__metadata-item",
    ".jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__workplace-type",
]

# Application buttons
EASY_APPLY_BUTTON_XPATHS = [
    ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]",
    ".//button[contains(@class,'jobs-apply-button') and contains(., 'Easy Apply')]",
    ".//a[contains(@href, 'openSDUIApplyFlow=true')]",
    ".//button[contains(@class,'jobs-apply-button')]",
]

# Easy Apply Modal & Flow
EASY_APPLY_MODAL_CLASS = "jobs-easy-apply-modal"
MODAL_NEXT_BUTTON_XPATH = ".//button[contains(@aria-label, 'Continue to next step') or contains(., 'Next')]"
MODAL_REVIEW_BUTTON_XPATH = ".//button[contains(@aria-label, 'Review your application') or contains(., 'Review')]"
MODAL_SUBMIT_BUTTON_XPATH = ".//button[contains(@aria-label, 'Submit application') or contains(., 'Submit application')]"
MODAL_DISMISS_BUTTON_XPATH = ".//button[contains(@aria-label, 'Dismiss') or contains(@class, 'artdeco-modal__dismiss')]"
CONFIRM_DISCARD_BUTTON_XPATH = ".//button[contains(@data-control-name, 'discard_application_confirm_btn') or contains(., 'Discard')]"
