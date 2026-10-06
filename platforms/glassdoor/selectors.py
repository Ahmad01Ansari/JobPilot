'''
Glassdoor Platform DOM Selectors
Isolates all HTML classes, IDs, XPaths, and CSS selectors for Glassdoor (glassdoor.com and glassdoor.co.in).
Provides multi-tier selector fallbacks for authentication, search filters, job cards,
Easy Apply modals, screening forms, confirmation signals, and anti-bot challenges.
'''

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
HOME_URL = "https://www.glassdoor.com/"
LOGIN_URL = "https://www.glassdoor.com/profile/login_input.htm"
SEARCH_BASE_URL = "https://www.glassdoor.com/Job/jobs.htm"

JOBS_SECTION_URL = "https://www.glassdoor.com/Job/index.htm"
JOBS_NAV_SELECTORS = [
    "//a[@data-test='site-header-jobs']",
    "//nav//a[contains(@href, '/Job') and (contains(., 'Jobs') or normalize-space()='Jobs')]",
    "//a[contains(@href, '/Job/index.htm')]",
    "//a[contains(@href, '/Job/jobs.htm')]",
    "//a[contains(@href, '/Job') and (normalize-space()='Jobs' or contains(text(), 'Jobs'))]",
    "a[data-test='nav-jobs']",
    "a[href*='/Job/index']",
]

INDIA_HOME_URL = "https://www.glassdoor.co.in/"
INDIA_SEARCH_BASE_URL = "https://www.glassdoor.co.in/Job/jobs.htm"

# ---------------------------------------------------------------------------
# Authentication & Session Verification Selectors
# ---------------------------------------------------------------------------
LOGGED_IN_SELECTORS = [
    "//button[@data-test='user-avatar']",
    "//button[contains(@aria-label, 'Account')]",
    "//button[contains(@aria-label, 'Profile')]",
    "//button[contains(@aria-label, 'user menu')]",
    "//a[contains(@href, '/member/home')]",
    "//a[contains(@href, '/profile')]",
    "//div[contains(@class, 'UserAvatar')]",
    "//span[contains(@class, 'profile-name') or contains(@class, 'user-menu')]",
    "//button[contains(@class, 'profile') or contains(@class, 'avatar')]",
    "//div[@data-test='avatar']",
]

LOGIN_REQUIRED_SELECTORS = [
    "//button[normalize-space()='Sign In' or normalize-space()='Sign in']",
    "//a[normalize-space()='Sign In' or normalize-space()='Sign in']",
    "input#inlineUserEmail",
    "input#modalUserEmail",
    "input[name='username']",
    "input[name='email']",
    "input[type='email']",
    "//div[contains(@class, 'ContentWall')]",
]

# Login form inputs
LOGIN_EMAIL_INPUTS = [
    "input#inlineUserEmail",
    "input#modalUserEmail",
    "input[name='username']",
    "input[name='email']",
    "input[type='email']",
]

LOGIN_PASSWORD_INPUTS = [
    "input#inlineUserPassword",
    "input#modalUserPassword",
    "input[name='password']",
    "input[type='password']",
]

LOGIN_SUBMIT_BUTTONS = [
    "button[type='submit']",
    "//button[contains(., 'Continue with email')]",
    "//button[contains(., 'Sign In') or contains(., 'Sign in')]",
    "//button[contains(., 'Log In') or contains(., 'Log in')]",
]

# ---------------------------------------------------------------------------
# Modal & Overlay Dismissal Selectors (Glassdoor Wall / Alerts)
# ---------------------------------------------------------------------------
MODAL_CLOSE_BUTTONS = [
    "button[data-test='job-alert-modal-close']",
    "button[aria-label='Cancel']",
    ".modal_CloseButton__faPZA button",
    "button[data-test='modal-close']",
    "button[aria-label='Close']",
    "button[aria-label='close']",
    "button.CloseButton",
    "//button[contains(@class, 'modal_close') or contains(@class, 'CloseButton') or contains(@class, 'ModalClose')]",
    "//button[contains(@aria-label, 'Close') or contains(@aria-label, 'close') or contains(@aria-label, 'Cancel')]",
    "//div[contains(@id, 'HdrModal')]//button",
    "//div[contains(@class, 'ContentWall')]//button[contains(@aria-label, 'Close') or contains(., '×')]",
    "//div[contains(., 'Create job alert') or contains(., 'job alert')]//button[contains(@aria-label, 'Close') or contains(@aria-label, 'Cancel') or contains(@class, 'close') or contains(., '×') or @data-test='job-alert-modal-close' or @data-test='modal-close']",
    "//div[@role='dialog']//button[contains(@aria-label, 'Close') or contains(@aria-label, 'Cancel') or @data-test='modal-close' or contains(., '×') or normalize-space()='✕' or normalize-space()='X']",
    "//button[contains(text(), 'No thanks') or contains(text(), 'Not now') or contains(text(), 'Dismiss') or contains(text(), 'Cancel')]",
    "[data-test='job-alert-modal-close']",
]

COOKIE_ACCEPT_BUTTONS = [
    "button#onetrust-accept-btn-handler",
    "//button[contains(text(), 'Accept all') or contains(text(), 'Accept All') or contains(text(), 'Accept Cookies')]",
]

# ---------------------------------------------------------------------------
# Search Form & Header Inputs
# ---------------------------------------------------------------------------
SEARCH_KEYWORD_INPUTS = [
    "#searchBar-jobTitle",
    "input#searchBar-jobTitle",
    "input[data-test='search-bar-keyword-input']",
    "main input#searchBar-jobTitle",
    "input#sc\\.keyword",
    "input[name='sc.keyword']",
    "form:not(header *) input[placeholder*='Job Title' i]",
    "form:not(header *) input[placeholder*='Job title' i]",
    "form:not(header *) input[placeholder*='keywords' i]",
]

SEARCH_LOCATION_INPUTS = [
    "#searchBar-location",
    "input#searchBar-location",
    "input[data-test='search-bar-location-input']",
    "main input#searchBar-location",
    "input#sc\\.location",
    "input[name='sc.location']",
    "form:not(header *) input[placeholder*='Location' i]",
    "form:not(header *) input[placeholder*='City' i]",
    "input[placeholder*='City, county' i]",
    "input[placeholder*='region or remote' i]",
    "//input[contains(@placeholder, 'City, county') or contains(@placeholder, 'region or remote')]",
]

SEARCH_SUBMIT_BUTTONS = [
    "button[data-test='search-bar-submit']",
    "button.SearchStyles__searchButton",
    "form:not(header *) button[type='submit']",
    "form:not(header *) button[data-test='search-bar-submit']",
]

# ---------------------------------------------------------------------------
# Search Results Page (SRP) Filters
# ---------------------------------------------------------------------------
EASY_APPLY_FILTER_BUTTONS = [
    "//button[contains(., 'Easy Apply only')]",
    "//span[contains(text(), 'Easy Apply only')]/ancestor::button",
    "//div[@role='button' and contains(., 'Easy Apply only')]",
    "//span[contains(text(), 'Easy Apply only')]/ancestor::div[@role='button']",
    "//button[@data-test='easy-apply-filter']",
    "//button[contains(@data-test, 'easy-apply') or contains(., 'Easy Apply')]",
    "//span[contains(text(), 'Easy Apply')]/ancestor::button",
    "//div[contains(@class, 'filter') and (contains(., 'Easy Apply only') or contains(., 'Easy Apply'))]",
    "//button[contains(@id, 'filter_easyApply')]",
    "//button[contains(@aria-label, 'Easy Apply')]",
    "button[data-test='filter-easy-apply']",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'easy apply')]",
]

DATE_POSTED_FILTER_BUTTONS = [
    "button[data-test='date-posted-filter']",
    "//button[contains(., 'Date Posted') or contains(., 'Date posted')]",
    "//button[contains(@aria-label, 'Date Posted')]",
]

DATE_POSTED_OPTIONS = {
    "last_24_hours": [
        "//li[contains(., 'Last 24 Hours') or contains(., 'Last 24 hours') or contains(., 'Past 24 hours')]",
        "//span[contains(., 'Last 24 Hours') or contains(., 'Last 24 hours')]",
    ],
    "last_3_days": [
        "//li[contains(., 'Last 3 Days') or contains(., 'Last 3 days') or contains(., 'Past 3 days')]",
        "//span[contains(., 'Last 3 Days') or contains(., 'Last 3 days')]",
    ],
    "last_week": [
        "//li[contains(., 'Last 7 Days') or contains(., 'Last week') or contains(., 'Past week')]",
        "//span[contains(., 'Last 7 Days') or contains(., 'Last week')]",
    ],
    "last_month": [
        "//li[contains(., 'Last 30 Days') or contains(., 'Last month') or contains(., 'Past month')]",
        "//span[contains(., 'Last 30 Days') or contains(., 'Last month')]",
    ],
}

# ---------------------------------------------------------------------------
# Job Listing Cards (Left Pane SRP List)
# ---------------------------------------------------------------------------
JOB_LIST_CONTAINERS = [
    "ul[data-test='job-listing-list']",
    "div[data-test='job-listings']",
    "div.JobsList_wrapper__*",
    "ul.JobsList_jobsList__*",
]

JOB_CARD_ELEMENTS = [
    "ul[data-test='job-listing-list'] > li",
    "li[data-test='jobListing']",
    "li[class*='JobsList_jobListItem']",
    "li[class*='jobListing']",
    "div.jobCard",
    "div[data-test='job-card']",
    "div[class*='JobCard_jobCard']",
    "article[data-test='job-listing-wrapper']",
    "//li[.//a[contains(@href, '/job-listing/') or @data-test='job-title']]",
    "//article[.//a[contains(@href, '/job-listing/') or @data-test='job-title']]",
]
JOB_CARD_CONTAINERS = JOB_CARD_ELEMENTS

CARD_TITLE_SELECTORS = [
    "[data-test='job-title']",
    "a[data-test='job-title']",
    "a[class*='JobCard_jobTitle']",
    "div[class*='jobTitle']",
    "a[class*='jobTitle']",
]

CARD_COMPANY_SELECTORS = [
    "[data-test='employer-name']",
    "span[class*='EmployerProfile_employerName']",
    "div[class*='employerName']",
    "span[class*='employerName']",
]

CARD_LOCATION_SELECTORS = [
    "[data-test='job-location']",
    "div[class*='JobCard_location']",
    "span[class*='JobCard_location']",
    "span[class*='location']",
]

CARD_SALARY_SELECTORS = [
    "[data-test='detailSalary']",
    "span[class*='JobCard_salaryEstimate']",
    "div[class*='salary-estimate']",
    "span[class*='salary']",
]

CARD_RATING_SELECTORS = [
    "[data-test='rating-headline']",
    "span[class*='EmployerProfile_rating']",
    "span.rating-headline",
]

CARD_EASY_APPLY_INDICATORS = [
    ".//span[contains(text(), 'Easy Apply')]",
    ".//*[@data-test='easy-apply-tag']",
    ".//*[@data-test='easyApply']",
    ".//*[@data-test='easy-apply']",
    ".//span[contains(@class, 'easyApply')]",
    ".//*[contains(@class, 'EasyApply')]",
    ".//*[contains(@aria-label, 'Easy Apply')]",
    ".//svg[contains(@class, 'easyApply')]",
]

CARD_ALREADY_APPLIED_INDICATORS = [
    ".//span[contains(text(), 'Applied') or contains(text(), 'You applied')]",
    ".//*[@data-test='job-applied-tag']",
    ".//span[contains(@class, 'applied')]",
]

# ---------------------------------------------------------------------------
# Job Details Pane (Right Pane / Detail Container)
# ---------------------------------------------------------------------------
DETAILS_PANE_SELECTORS = [
    "div[data-test='job-details']",
    "div[class*='JobDetails_jobDetailsContainer']",
    "div#JobDescriptionContainer",
    "div[class*='jobDescriptionContent']",
    "main[class*='JobDetails']",
]

DETAIL_TITLE_SELECTORS = [
    "h1[data-test='job-title']",
    "h2[data-test='job-title']",
    "div[class*='JobDetails_jobTitle']",
    "h1[class*='jobTitle']",
]

DETAIL_COMPANY_SELECTORS = [
    "a[data-test='employer-name']",
    "span[data-test='employer-name']",
    "h4[class*='EmployerProfile_employerName']",
    "div[class*='EmployerProfile_employerName']",
]

DETAIL_LOCATION_SELECTORS = [
    "div[data-test='location']",
    "span[data-test='location']",
    "div[class*='JobDetails_location']",
]

JOB_DESCRIPTION_SELECTORS = [
    "#jobDescriptionText",
    "div[data-test='jobDescriptionContent']",
    "div[class*='JobDetails_jobDescription']",
    "div#JobDescriptionContainer",
    "div[class*='jobDescription']",
    "div[class*='desc']",
    "div[data-test='job-description']",
    "div[class*='JobDetails_jobDetailsContainer']",
    "section[class*='JobDetails']",
    "main[class*='JobDetails']",
    "div#JobDescContainer",
    "div.jobDescriptionContent",
]

JD_SHOW_MORE_BUTTONS = [
    "//button[contains(., 'Show More') or contains(., 'Read More') or contains(., 'Show more')]",
    "button[data-test='show-more-button']",
    "button[class*='JobDetails_showMore']",
]

# ---------------------------------------------------------------------------
# Application Triggers (Apply Buttons in Details Pane)
# ---------------------------------------------------------------------------
APPLY_EASY_TRIGGERS = [
    "button[data-test='easyApply']",
    "//button[@data-test='easyApply']",
    "//button[@data-easy-apply='true']",
    "//button[contains(@class, 'easyApply') or contains(., 'Easy Apply')]",
    "//button[contains(., 'Easy Apply') or contains(., 'Easy apply')]",
    "//button[@data-test='easy-apply-button']",
    "//button[@data-test='apply-button' and contains(., 'Easy')]",
    "//button[contains(@aria-label, 'Easy Apply')]",
    "//span[contains(text(), 'Easy Apply')]/ancestor::button",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'easy apply')]",
]

APPLY_EXTERNAL_TRIGGERS = [
    "//button[@data-test='apply-button']",
    "//button[contains(., 'Apply on company site') or contains(., 'Apply on employer site') or contains(., 'Apply on Employer Site')]",
    "//a[contains(., 'Apply on company site') or contains(., 'Apply on employer site')]",
    "//button[contains(@aria-label, 'Apply on company site')]",
]

APPLY_ALREADY_BADGES = [
    "//span[contains(text(), 'Applied') or contains(text(), 'You applied')]",
    "//div[contains(@class, 'appliedBadge')]",
    "//button[contains(., 'Applied') and @disabled]",
]

# ---------------------------------------------------------------------------
# Multi-Step Easy Apply Form Selectors
# ---------------------------------------------------------------------------
EASY_APPLY_MODAL_CONTAINERS = [
    "div[data-test='easy-apply-modal']",
    "div[class*='EasyApplyModal']",
    "div[role='dialog'][aria-label*='Apply' i]",
    "div[class*='modal-content']",
]

FORM_FIRST_NAME_INPUTS = [
    "input[name*='firstName' i]",
    "input#firstName",
    "input[autocomplete*='given-name']",
    "input[placeholder*='First name' i]",
]

FORM_LAST_NAME_INPUTS = [
    "input[name*='lastName' i]",
    "input#lastName",
    "input[autocomplete*='family-name']",
    "input[placeholder*='Last name' i]",
]

FORM_EMAIL_INPUTS = [
    "input[type='email']",
    "input[name*='email' i]",
    "input#email",
    "input[placeholder*='Email' i]",
]

FORM_PHONE_INPUTS = [
    "input[type='tel']",
    "input[name*='phone' i]",
    "input#phone",
    "input[placeholder*='Phone' i]",
]

FORM_LOCATION_INPUTS = [
    "input[name*='city' i]",
    "input[name*='location' i]",
    "input#location",
    "input[placeholder*='City' i]",
]

FORM_RESUME_FILE_INPUTS = [
    "input[type='file'][accept*='pdf' i]",
    "input[type='file']",
]

FORM_CONTINUE_BUTTONS = [
    "//button[contains(., 'Continue') or contains(., 'Next') or contains(., 'Review your application')]",
    "button[data-test='continue-button']",
    "button[data-test='next-button']",
]

FORM_SUBMIT_BUTTONS = [
    "button[data-testid='submit-application-button']",
    "button[data-test='submit-application-button']",
    "//button[contains(., 'Submit your application') or contains(., 'Send application') or contains(., 'Submit Application')]",
    "//button[contains(., 'Submit') and @type='submit']",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit your application')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit application')]",
    "//button[contains(@class, 'ia-continueButton')]",
]

# ---------------------------------------------------------------------------
# Submission Confirmation Selectors
# ---------------------------------------------------------------------------
SUBMIT_SUCCESS_CONTAINERS = [
    "div[data-test='application-success']",
    "//h3[contains(., 'Application submitted') or contains(., 'Application Submitted') or contains(., 'Your application has been sent')]",
    "//div[contains(text(), 'You have successfully applied')]",
    "//span[contains(text(), 'Application sent')]",
    "//*[contains(text(), 'Your application was submitted')]",
    "//*[contains(text(), 'Application submitted')]",
    "//*[contains(text(), 'Your application has been submitted')]",
    "//h1[contains(., 'submitted')]",
    "//h2[contains(., 'submitted')]",
]

# ---------------------------------------------------------------------------
# CAPTCHA & Security Challenge Selectors
# ---------------------------------------------------------------------------
CAPTCHA_IFRAME_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='turnstile']",
    "iframe[src*='recaptcha/api2/bframe']",
    "iframe[src*='recaptcha/enterprise/bframe']",
    "iframe[src*='bframe']",
    "iframe[src*='arkoselabs']",
    "iframe[src*='datadome']",
    "iframe[src*='hcaptcha.com']",
]

CAPTCHA_CONTAINER_SELECTORS = [
    "#challenge-stage",
    "#challenge-running",
    ".cf-turnstile",
]

# ---------------------------------------------------------------------------
# Pagination Selectors
# ---------------------------------------------------------------------------
PAGINATION_NEXT_BUTTONS = [
    "button[data-test='pagination-next']",
    "button[data-test='load-more']",
    "//button[contains(@aria-label, 'Next') and not(@disabled)]",
    "//button[(contains(., 'Next') or contains(., 'Show more jobs') or contains(., 'Load more')) and not(@disabled)]",
    "//a[contains(@aria-label, 'Next') and not(contains(@class, 'disabled'))]",
]

PAGINATION_CURRENT_PAGE = [
    "//button[@data-test='pagination-current']",
    "//li[contains(@class, 'current') or contains(@class, 'active')]",
]
