'''
Foundit Platform Selectors
Comprehensive semantic CSS & XPath selector catalog for Foundit India (foundit.in).
Mapped and verified during Phase 2 live DOM reconnaissance.
'''

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------
HOME_URL = "https://www.foundit.in/"
LOGIN_URL = "https://www.foundit.in/auth/login"
SEARCH_BASE_URL = "https://www.foundit.in/search"
SRP_BASE_URL = "https://www.foundit.in/srp/results"

# ---------------------------------------------------------------------------
# Authentication & Header Selectors
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Authentication & Header Selectors
# ---------------------------------------------------------------------------
HEADER_LOGIN_BUTTONS = [
    "//button[normalize-space()='Login' or contains(normalize-space(), 'Log In') or contains(normalize-space(), 'Sign In')]",
    "//a[normalize-space()='Login' or contains(normalize-space(), 'Log In') or contains(normalize-space(), 'Sign In')]",
    "//button[contains(@class, 'text-[#6E00BE]') and contains(normalize-space(), 'Login')]",
]

HEADER_REGISTER_BUTTONS = [
    "//button[normalize-space()='Register' or contains(normalize-space(), 'Sign Up')]",
    "//a[normalize-space()='Register' or contains(normalize-space(), 'Sign Up')]",
    "//button[contains(@class, 'bg-[#FC5912]') and contains(normalize-space(), 'Register')]",
]

LOGIN_USERNAME_INPUT = "input#userName, input[name='userName'], input[placeholder*='Email ID / Phone Number']"
LOGIN_PASSWORD_SWITCH_LINKS = [
    "//*[contains(text(), 'Login via Password')]",
    "span.text-brand-primary.cursor-pointer",
    "//span[contains(normalize-space(), 'Login via Password')]",
]

LOGIN_PASSWORD_INPUT = "input#password, input[name='password'], input[type='password']"
LOGIN_SUBMIT_BUTTON = "button#loginSubmit[type='submit'], button#loginSubmit, button[aria-label='submit']"

# ---------------------------------------------------------------------------
# Session State Verification Selectors
# ---------------------------------------------------------------------------
LOGGED_IN_SELECTORS = [
    "//*[starts-with(normalize-space(), 'Hi,') or contains(normalize-space(), 'Hi, ')]",
    "div.profile_avatar, div[class*='profile_avatar']",
    "div[class*='userProfile']",
    "div[class*='user-avatar']",
    "div[class*='profileSection']",
    "div[class*='userAvatar']",
    "a[href*='/seeker/profile']",
    "a[href*='/home/user']",
    "a[href*='/dashboard']",
    "div[class*='profile-container']",
    "div.avatar",
]

LOGIN_REQUIRED_SELECTORS = [
    "input#userName",
    "input#password",
    "button#loginSubmit",
]

# ---------------------------------------------------------------------------
# UI Search & Filter Selectors
# ---------------------------------------------------------------------------
HOME_SKILLS_INPUT = "input#heroSectionDesktop-skillsAutoComplete--input, input[placeholder*='Search by Skills'], input[placeholder*='Skills']"
HOME_LOCATION_INPUT = "input#heroSectionDesktop-locationAutoComplete--input, input[placeholder*='Location']"
HOME_EXPERIENCE_INPUT = "input#heroSectionDesktop-expAutoComplete--input, input[placeholder*='Experience']"
HOME_SEARCH_BUTTON = "button.search_submit_btn, button[class*='search_submit_btn'], button[aria-label='search']"

SRP_SKILLS_INPUT = "input#heroSectionDesktop-skillsAutoComplete--input, input[class*='input-box'], input[placeholder*='Skills']"
SRP_LOCATION_INPUT = "input#heroSectionDesktop-locationAutoComplete--input, input[placeholder*='Location']"
SRP_EXPERIENCE_INPUT = "input#heroSectionDesktop-expAutoComplete--input, input[placeholder*='Experience']"
SRP_SEARCH_BUTTON = "button.search_submit_btn, button[class*='search_submit_btn'], button[aria-label='search']"

QUICK_APPLY_TOGGLE = "input#toggle"
QUICK_APPLY_TOGGLE_LABEL = "//span[contains(normalize-space(), 'Quick Apply')] | //label[.//input[@id='toggle']] | //label[@for='toggle'] | //div[contains(@class, 'peer')]"

# Left Sidebar Filter Selectors (Canonical Search UI)
SIDEBAR_FILTER_CONTAINER = "aside, div.allFilters, div[class*='filters-container'], div[class*='filterContainer']"
SIDEBAR_EXPERIENCE_SECTION = "//div[contains(@class, 'filter') or contains(@class, 'accordion')][.//span[contains(text(), 'Experience')] or .//div[contains(text(), 'Experience')] or .//h3[contains(text(), 'Experience')]]"
SIDEBAR_APPLIED_CHIPS = "//div[contains(text(), 'filters applied') or contains(@class, 'applied')]//span[contains(@class, 'chip') or contains(@class, 'tag') or contains(text(), 'yr') or contains(text(), 'Fresher')]"


CAPTCHA_SELECTORS = [
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='recaptcha']",
    "iframe[src*='arkoselabs']",
    "div[id*='turnstile']",
    "div.cf-turnstile",
    "div[class*='captcha']",
    "#challenge-running",
]

OTP_SELECTORS = [
    "input[class*='otp']",
    "input[name*='otp']",
    "input[placeholder*='OTP']",
    "div[class*='otpContainer']",
    "button#verifyOtp",
]

# ---------------------------------------------------------------------------
# Search Results Page (SRP) Job Card Selectors
# ---------------------------------------------------------------------------
CARD_CONTAINER_SELECTOR = "div.cardContainer, div.cardContainer.activeCard, div.srpResultCard, div[class~='cardContainer']"
ACTIVE_CARD_SELECTOR = "div.cardContainer.activeCard, div[class*='cardContainer activeCard']"

CARD_TITLE_SELECTORS = [
    "div#jobCardTitle.jobTitle",
    "div.jobTitle",
    "div[id*='jobCardTitle']",
    "div[class*='jobTitle']",
    "h3.jobTitle",
    "a.jobTitle",
    "div.cardHead div.infoSection div",
    "div.headerContent div.infoSection div",
]

CARD_COMPANY_SELECTORS = [
    "div.companyName p",
    "div.companyName",
    "div[class*='companyName'] p",
    "div[class*='companyName']",
    "div.cardHead div.companyName",
    "div.infoSection div.companyName",
]

CARD_LOCATION_SELECTORS = [
    "div.bodyRow div.details.location",
    "div.bodyRow div.location",
    "div[class*='location']",
    "div.details.location",
]

CARD_EXPERIENCE_SELECTORS = [
    "div.experienceSalary span.details",
    "div.bodyRow i.mqfisrp-briefcase-job + span.details",
    "span.details",
    "div.experienceSalary",
]

CARD_SALARY_SELECTORS = [
    "div.experienceSalary .salary",
    "div.salaryText",
    "span[class*='salary']",
    "div[class*='salary']",
]

CARD_POSTED_DATE_SELECTORS = [
    "div.jobAddedTime p.timeText",
    "p.timeText",
    "div[class*='jobAddedTime']",
]

CARD_TAGS_SELECTORS = [
    "div.jobTags div.cardApplyLabel",
    "div.cardApplyLabel",
    "div[class*='jobTags']",
]

# ---------------------------------------------------------------------------
# Split-Pane & Job Description Container Selectors
# ---------------------------------------------------------------------------
DETAILS_CONTAINER_SELECTORS = [
    "div.detailsContainer",
    "div[class*='detailsContainer']",
    "div[class*='srpRightContainer']",
    "div[class*='rightSection']",
]

JD_CONTAINER_SELECTORS = [
    "div.jobDescription",
    "div[class*='jobDescription']",
    "div[class*='jobDetails']",
    "div[class*='description']",
    "section[class*='description']",
    "div.detailsContainer",
]

DETAILS_TITLE_SELECTORS = [
    "div.detailsContainer div.jobTitle",
    "div.detailsContainer h1",
    "div.srpRightContainer div.jobTitle",
    "div.srpRightContainer h1",
    "div#jobCardTitle",
    "div.jobTitle",
    "h1",
]

DETAILS_COMPANY_SELECTORS = [
    "div.detailsContainer div.companyName p",
    "div.detailsContainer div.companyName",
    "div.srpRightContainer div.companyName p",
    "div.srpRightContainer div.companyName",
    "div.companyName p",
    "div.companyName",
]

DETAILS_LOCATION_SELECTORS = [
    "div.detailsContainer div.location",
    "div.srpRightContainer div.location",
    "div.detailsContainer .location",
    "div.location",
]

DETAILS_EXPERIENCE_SELECTORS = [
    "div.detailsContainer div.experienceSalary span",
    "div.srpRightContainer div.experienceSalary span",
    "div.detailsContainer span.details",
    "div.experienceSalary span.details",
]

DETAILS_SALARY_SELECTORS = [
    "div.detailsContainer .salary",
    "div.srpRightContainer .salary",
    "div.detailsContainer div.salaryText",
    "div.srpRightContainer div.salaryText",
    "span[class*='salary']",
]

PRIMARY_APPLY_BUTTON_SELECTORS = [
    "button#applyNowBtn",
    "button[class*='applyNowBtn']",
    "div.applyBtnCont button",
    "//button[contains(normalize-space(), 'Apply Now')]",
    "//button[contains(normalize-space(), 'Quick Apply')]",
    "//button[contains(normalize-space(), 'Apply')]",
]

EXTERNAL_APPLY_INDICATORS = [
    "apply on company site",
    "apply on company website",
    "company website",
    "company site",
    "external apply",
    "external",
    "apply now",
    "redirect",
]

# ---------------------------------------------------------------------------
# Submission & Confirmation Selectors
# ---------------------------------------------------------------------------
SUBMISSION_SUCCESS_TEXTS = [
    "you have applied successfully",
    "applied successfully",
    "application submitted",
    "application sent",
    "applied just now",
    "your application status",
    "recruiter response",
    "thank you for applying",
    "your application has been sent",
    "you have successfully applied",
]

APPLIED_BUTTON_TEXTS = [
    "applied",
    "already applied",
]

MODAL_CLOSE_BUTTONS = [
    "//button[contains(@class, 'popupClose') or contains(@class, 'close') or @aria-label='Close' or normalize-space()='×' or normalize-space()='X']",
    "//div[contains(@class, 'modal') or contains(@class, 'popup') or contains(@class, 'drawer')]//button[contains(@class, 'close') or @aria-label='Close' or normalize-space()='×' or normalize-space()='X']",
    "button.popupClose",
    "button.close",
    "i.mqfisrp-close",
    "button[aria-label='Close']",
    "div[class*='close']",
]

# ---------------------------------------------------------------------------
# Pagination Selectors
# ---------------------------------------------------------------------------
PAGINATION_CONTAINER = "div.pagination, nav[class*='pagination']"
PAGINATION_NEXT_BUTTONS = [
    "//div[contains(@class, 'pagination')]//button[contains(normalize-space(), 'Next')]",
    "//div[contains(@class, 'pagination')]//a[contains(normalize-space(), 'Next')]",
]
