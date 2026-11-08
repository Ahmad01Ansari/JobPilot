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

# Login form input & submit selectors
LOGIN_USERNAME_SELECTORS = [
    "#username",
    "#session_key",
    "input[name='session_key']",
    "input[autocomplete='username']",
    "input[type='email']",
    "input[name='username']",
]

LOGIN_PASSWORD_SELECTORS = [
    "#password",
    "#session_password",
    "input[name='session_password']",
    "input[autocomplete='current-password']",
    "input[type='password']",
]

LOGIN_SUBMIT_SELECTORS = [
    "button[type='submit']",
    "button[data-litms-control-urn*='login-submit']",
    ".btn__primary--large",
    "button.btn__primary--large",
]

# Job Search & Listings
JOB_RESULTS_CONTAINER = ".jobs-search-results-list"
JOB_RESULTS_CONTAINERS = [
    "div[data-display-contents='true']",
    ".jobs-search-results-list",
    ".scaffold-layout__list",
    ".jobs-search-results",
    "div[data-view-name='job-search-results-list']",
    "div.scaffold-layout__list-detail-inner",
    "div.scaffold-layout__list-container",
    "ul.scaffold-layout__list-container",
    ".scaffold-layout__list-detail",
    "main.scaffold-layout__main",
    "main",
]
JOB_CARD_ITEMS = [
    # Modern Genesis SDUI layout (late 2024 - 2026+)
    "div[role='button'][componentkey^='job-card-component-ref-']",
    "div[role='button'][componentkey*='job-card']",
    "div[componentkey^='job-card-component-ref-']",
    "[componentkey^='job-card-component-ref-']",
    "[componentkey*='job-card-']",
    # Classic & Scaffold layouts
    "li[data-occludable-job-id]",
    "li.jobs-search-results__list-item",
    "li.scaffold-layout__list-item",
    "ul.scaffold-layout__list-container > li",
    "div.job-card-container",
    "div[data-job-id]",
    "div.job-card-job-posting-card-wrapper",
    "div[data-view-name='job-card']",
    "div[data-view-name='job-card-component']",
    "div[data-view-name='job-card-item']",
    "div.jobs-search-results-list__list-item",
    "li.jobs-search-results-list__list-item",
    "div[data-entity-urn*='urn:li:jobPosting:']",
    "li[data-entity-urn*='urn:li:jobPosting:']",
    "div.job-card-list__entity-lockup",
    "div.job-card-list",
    "div.base-card",
    "li.base-card",
    "//div[@role='button' and contains(@componentkey, 'job-card-component-ref-')]",
    "//div[contains(@componentkey, 'job-card')]",
    "//li[contains(@class, 'scaffold-layout__list-item') or contains(@class, 'jobs-search-results__list-item') or @data-occludable-job-id]",
    "//div[@data-job-id or contains(@class, 'job-card-container') or @data-view-name='job-card']",
]

JOB_CARD_CLICKABLE_SELECTORS = [
    "a.job-card-list__title",
    "a.job-card-container__link",
    "a[href*='/jobs/view/']",
    "a[href*='currentJobId=']",
    "a[data-control-name='job_card_click']",
    "div.job-card-list__entity-lockup",
    ".artdeco-entity-lockup__title",
    "h2 a",
    "h3 a",
    "p",
    "span",
]

NO_RESULTS_INDICATORS = [
    "div.jobs-search-no-results-banner",
    ".jobs-search-two-pane__no-results-banner",
    "//h1[contains(normalize-space(.), 'No matching jobs')]",
    "//div[contains(normalize-space(.), 'No matching jobs')]",
]

# Job Details & Description
JOB_DETAILS_CONTAINER = ".jobs-search__job-details"
JOB_DESCRIPTION_SELECTORS = [
    "[data-testid='expandable-text-box']",
    "div#job-details",
    "div.dang-inner-html",
    "article.jobs-description__container",
    "div.jobs-description-content__text",
    "div.jobs-box__html-content",
    "div.jobs-description__content",
]

JOB_TITLE_SELECTORS = [
    "h1.t-24",
    "h1.job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title",
    "h2.job-card-list__title",
    "a.job-card-list__title",
    "div.job-details-jobs-unified-top-card__title-container h1",
    ".job-details-jobs-unified-top-card__job-title a",
]

JOB_COMPANY_SELECTORS = [
    ".job-card-container__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".job-card-container__primary-description",
    ".artdeco-entity-lockup__subtitle",
]

JOB_LOCATION_SELECTORS = [
    ".job-card-container__metadata-item",
    ".jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__workplace-type",
    ".job-details-jobs-unified-top-card__bullet",
    ".job-details-jobs-unified-top-card__workplace-type",
    ".artdeco-entity-lockup__caption",
]

# Application buttons
EASY_APPLY_BUTTON_XPATHS = [
    ".//button[contains(@aria-label, 'Easy Apply') or contains(., 'Easy Apply')]",
    ".//a[contains(@aria-label, 'Easy Apply') or contains(., 'Easy Apply')]",
    ".//button[contains(@class,'jobs-apply-button') and contains(@class, 'artdeco-button--3') and contains(@aria-label, 'Easy')]",
    ".//button[contains(@class,'jobs-apply-button') and contains(., 'Easy Apply')]",
    ".//a[contains(@href, 'openSDUIApplyFlow=true')]",
    ".//button[contains(@class,'jobs-apply-button')]",
    ".//button[contains(., 'Apply') and not(contains(., 'Applied'))]",
    ".//a[contains(., 'Apply') and not(contains(., 'Applied'))]",
]

# Easy Apply Modal & Flow
EASY_APPLY_MODAL_CLASS = "jobs-easy-apply-modal"
EASY_APPLY_MODAL_SELECTORS = [
    "dialog[open]",
    "dialog[data-testid='dialog']",
    "div.jobs-easy-apply-modal",
    "div[role='dialog'][aria-labelledby*='dialog-header']",
    "div[role='dialog']",
    "dialog",
]
EASY_APPLY_MODAL_XPATHS = [
    "//dialog[@open or @data-testid='dialog']",
    "//div[contains(@class, 'jobs-easy-apply-modal')]",
    "//div[@role='dialog' and (contains(@aria-labelledby, 'dialog-header') or .//button[contains(@aria-label, 'Dismiss') or contains(., 'Next') or contains(., 'Submit')])]",
    "//div[@role='dialog']",
    "//dialog",
]
MODAL_NEXT_BUTTON_XPATH = ".//button[contains(@aria-label, 'Continue to next step') or contains(@aria-label, 'next step') or normalize-space(.)='Next' or contains(normalize-space(.), 'Next')]"
MODAL_REVIEW_BUTTON_XPATH = ".//button[contains(@aria-label, 'Review your application') or normalize-space(.)='Review' or contains(normalize-space(.), 'Review')]"
MODAL_SUBMIT_BUTTON_XPATH = ".//button[contains(@aria-label, 'Submit application') or normalize-space(.)='Submit application' or contains(normalize-space(.), 'Submit application') or (contains(normalize-space(.), 'Submit') and not(contains(normalize-space(.), 'Submitting')))]"
MODAL_DISMISS_BUTTON_XPATH = ".//button[contains(@aria-label, 'Dismiss') or contains(@aria-label, 'Close') or normalize-space(.)='✕' or contains(@class, 'artdeco-modal__dismiss')]"
CONFIRM_DISCARD_BUTTON_XPATH = ".//button[contains(@data-control-name, 'discard_application_confirm_btn') or normalize-space(.)='Discard' or contains(normalize-space(.), 'Discard')]"
MODAL_BACK_BUTTON_XPATH = ".//button[contains(@aria-label, 'Back') or normalize-space(.)='Back' or contains(normalize-space(.), 'Back')]"
MODAL_UPLOAD_RESUME_XPATH = ".//button[contains(., 'Upload resume') or contains(@aria-label, 'Upload resume')] | .//input[@type='file']"

