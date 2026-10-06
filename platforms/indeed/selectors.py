'''
Indeed DOM Selectors
Isolates all HTML classes, IDs, XPaths, and CSS selectors for Indeed India (in.indeed.com).
Makes platform DOM updates easy to maintain without altering core platform logic.
'''

# --- URLs ---
HOME_URL = "https://in.indeed.com/"
LOGIN_URL = "https://secure.indeed.com/auth"
SEARCH_BASE_URL = "https://in.indeed.com/jobs"

# --- Authentication & Session Indicators ---
LOGGED_IN_SELECTORS = [
    "//button[contains(@aria-label, 'Account')]",
    "//button[contains(@aria-label, 'Profile')]",
    "//a[contains(@href, '/myjobs')]",
    "//a[contains(@href, 'profile.indeed.com')]",
    "//div[contains(@class, 'gnav-AccountMenu')]",
    "//span[contains(@class, 'nav-profile')]",
    "//div[@data-gnav-element-name='Profile']",
]

LOGIN_REQUIRED_SELECTORS = [
    "//a[contains(text(), 'Sign in')]",
    "//button[contains(text(), 'Sign in')]",
    "//input[@type='email' and @name='__email']",
    "//input[@id='passcode-input']",
    "//button[@id='auth-page-otp-send-new-code-button']",
]

# Login form fields
LOGIN_EMAIL_INPUT = [
    "//input[@type='email']",
    "//input[@name='__email']",
    "//input[contains(@id, 'email') or contains(@id, 'Email')]",
]

LOGIN_CONTINUE_BUTTON = [
    "//button[@type='submit']",
    "//button[contains(., 'Continue')]",
]

SIGN_IN_WITH_CODE_LINK = [
    "//a[contains(text(), 'Sign in with a code instead')]",
    "//button[contains(., 'Sign in with a code instead')]",
    "//*[contains(text(), 'Sign in with a code instead')]",
]

OTP_PASSCODE_INPUT = [
    "#passcode-input",
    "input[name='passcode']",
    "input[id='passcode-input']",
]

OTP_SUBMIT_BUTTON = [
    "//button[@type='submit' and contains(., 'Sign in')]",
    "//button[contains(., 'Sign in')]",
]

PASSKEY_NOT_NOW_BUTTON = [
    "//button[contains(text(), 'Not now')]",
    "//a[contains(text(), 'Not now')]",
    "//*[text()='Not now']",
]

COOKIE_ACCEPT_BUTTON = [
    "//button[contains(text(), 'Accept All Cookies')]",
    "//button[@id='onetrust-accept-btn-handler']",
]

# --- CAPTCHA & Security Challenge Selectors ---
CAPTCHA_IFRAME_SELECTORS = [
    "iframe[src*='recaptcha/api2/bframe']",
    "iframe[src*='recaptcha/enterprise/bframe']",
    "iframe[src*='bframe']",
    "iframe[title*='recaptcha challenge' i]",
    "iframe[src*='anchor']:not([src*='size=invisible'])",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[src*='turnstile']",
    "iframe[src*='hcaptcha.com']",
]

CAPTCHA_CONTAINER_SELECTORS = [
    "#challenge-stage",
    "#challenge-running",
    ".cf-turnstile",
]

CAPTCHA_RESPONSE_INPUTS = [
    "textarea[name='g-recaptcha-response']",
    "#g-recaptcha-response",
    "input[name='cf-turnstile-response']",
    "textarea[name='h-captcha-response']",
]

# --- Search Inputs & UI Filters ---
SEARCH_WHAT_INPUT = [
    "#text-input-what",
    "input[name='q']",
    "input[id*='what']",
    "input[aria-label*='job title' i]",
]

SEARCH_WHERE_INPUT = [
    "#text-input-where",
    "input[name='l']",
    "input[id*='where']",
    "input[aria-label*='location' i]",
]

SEARCH_SUBMIT_BUTTON = [
    "button[type='submit']",
    ".yosegi-InlineWhatWhere-primaryButton",
    "button.yosegi-InlineWhatWhere-primaryButton",
    "form button[type='submit']",
    "//button[contains(., 'Find jobs')]",
]

DATE_POSTED_FILTER_BUTTON = [
    "#filter-dateposted",
    "#fromAge_filter_button",
    "button[id*='fromAge']",
    "button[id*='dateposted']",
    "button[aria-label*='Date posted' i]",
    "//button[contains(., 'Date posted')]",
]

DATE_POSTED_OPTIONS = {
    1: ["li[data-testid='selection-pill-option-2']", "li[aria-label*='24 hours' i]"],
    3: ["li[data-testid='selection-pill-option-3']", "li[aria-label*='3 days' i]"],
    7: ["li[data-testid='selection-pill-option-4']", "li[aria-label*='7 days' i]"],
    14: ["li[data-testid='selection-pill-option-5']", "li[aria-label*='14 days' i]"],
}

FILTER_UPDATE_BUTTON = [
    "//button[contains(., 'Update') or contains(span, 'Update')]",
    "button[data-testid='filter-update-button']",
]

# --- Search & Results Selectors ---
JOB_CARD_SELECTORS = [
    "div.job_seen_beacon",
    "div.cardOutline",
    "div.slider_item",
]

CARD_TITLE_SELECTORS = [
    "a.jcs-JobTitle",
    "h2.jobTitle a",
    "a[class*='JobTitle']",
]

CARD_COMPANY_SELECTORS = [
    "span[data-testid='company-name']",
    "span.companyName",
    "div[data-testid='company-name']",
]

CARD_LOCATION_SELECTORS = [
    "div[data-testid='text-location']",
    "span.companyLocation",
]

CARD_SALARY_SELECTORS = [
    "div.metadata.salary-snippet-container",
    "div[data-testid='attribute_snippet_testid']",
    "div.salary-snippet",
]

EASILY_APPLY_BADGE_SELECTORS = [
    "//*[contains(text(), 'Easily apply') or contains(text(), 'Easy Apply')]",
    "div.ialHelp",
    "span.ialHelp",
]

CARD_SNIPPET_SELECTORS = [
    "div.job-snippet",
    "ul.job-snippet",
    "div.underCard_container",
    "table.jobCardShelfContainer",
    "div[data-testid='attribute_snippet_testid']",
    "div.heading6.tapItem-gutter",
    "div.metadataContainer",
    "div.jobMetaDataGroup",
]

# --- Right-Side Details Pane & Job Attributes ---
DETAILS_PANE_SELECTORS = [
    "#jobsearch-ViewJobPaneWrapper",
    "[data-testid='jobsearch-ViewjobPaneWrapper']",
    "div.jobsearch-RightPane",
    "div.jobsearch-ViewJobPane",
    "div.fastviewjob",
    "div.jobsearch-ViewJobBody",
]

JOB_DESCRIPTION_SELECTORS = [
    "div#jobDescriptionText",
    "#jobDescriptionText",
    "div[data-testid='jobsearch-JobDescriptionText']",
    "div.jobsearch-jobDescriptionText",
    "div.jobsearch-JobComponent-description",
    "div#jobDescriptionSection",
    "div.simple-job-description-html",
    "div.react-native-html-content",
    "div[data-testid='vj-job-description-heading'] ~ div",
    "div[data-testid='viewjob-job-content']",
    "div[data-testid='jobsearch-ViewJobContent']",
    "div[data-testid='job-description']",
    "div.jobsearch-ViewJobBody",
    "div[class*='JobDescription']",
    "div[class*='jobDescription']",
    "div#vjs-jobinfo",
    "div#vjs-desc",
]

JOB_DETAILS_SECTION_SELECTORS = [
    "#salaryInfoAndJobType",
    "#jobDetailsSection",
    "div[data-testid='jobDetailsSection']",
    "div[data-testid='jobsearch-JobDetailsSection-attribute']",
    "div[data-testid='attribute_snippet_testid']",
    "div.jobsearch-JobMetadataHeader-item",
    "div.jobsearch-JobInfoHeader-subtitle",
]

SALARY_DETAIL_SELECTORS = [
    "#salaryInfoAndJobType",
    "div[aria-label*='Pay']",
    "div[data-testid='attribute_snippet_testid']",
    "div[data-testid='jobsearch-JobDetailsSection-attribute']",
    "div.jobsearch-JobMetadataHeader-item",
    "span.css-19j1a75",
]

DETAIL_TITLE_SELECTORS = [
    "h5[data-testid='vj-job-title']",
    "[data-testid='vj-job-title']",
    "div[data-testid='company-info-title-row']",
    "h1.jobsearch-JobInfoHeader-title",
    "h1[data-testid='jobsearch-JobInfoHeader-title']",
    "h2.jobTitle",
    "h1",
]

DETAIL_COMPANY_SELECTORS = [
    "div[data-testid='inlineHeader-companyName'] a",
    "div[data-testid='inlineHeader-companyName']",
    "span[data-testid='company-name']",
    "div[data-testid='company-info-metadata']",
    "div.jobsearch-InlineCompanyRating div:first-child",
]

DETAIL_LOCATION_SELECTORS = [
    "div[data-testid='inlineHeader-companyLocation']",
    "div[data-testid='jobsearch-JobInfoHeader-companyLocation']",
    "div[data-testid='company-info-metadata']",
    "div.jobsearch-JobInfoHeader-companyLocation",
]

APPLY_NOW_TRIGGERS = [
    "//div[text()='Apply now']",
    "//*[text()='Apply now']",
    "//button[contains(., 'Apply now')]",
    "//button[@id='indeedApplyButton']",
    "//div[contains(@class, 'IndeedApplyButton')]//button",
]

APPLY_EXTERNAL_TRIGGERS = [
    "//*[contains(text(), 'Apply on company site')]",
    "//button[contains(., 'Apply on company site')]",
    "//a[contains(., 'Apply on company site')]",
    "//span[contains(text(), 'Apply on company site')]",
]

# --- Smart Apply Multi-Step Form Selectors ---
SPINNER_SELECTORS = [
    "//div[contains(@class, 'spinner') or contains(@class, 'Spinner')]",
    "//svg[contains(@class, 'spinner') or contains(@class, 'Spinner')]",
    "//circle[contains(@class, 'spinner') or contains(@class, 'Spinner')]",
    "//div[@role='status']",
    "//div[contains(@class, 'loading') or contains(@class, 'Loading')]",
    "//*[contains(@data-testid, 'spinner') or contains(@data-testid, 'loading')]",
    "//*[contains(@aria-label, 'loading') or contains(@aria-label, 'Loading')]",
    "//*[contains(text(), 'Preparing review')]",
    "//div[contains(@class, 'progress')]",
]

STEP_HEADING_SELECTORS = [
    "h1",
    "h2",
    "h3",
    "h4",
    "div[role='heading']",
    "[class*='heading' i]",
    "[class*='title' i]",
    "legend",
]

FORM_CONTINUE_BUTTONS = [
    "//button[contains(., 'Continue')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'review your application')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'review application')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save and continue')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save & continue')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'proceed')]",
    "//button[@data-testid='continue-button']",
    "//button[@data-testid='next-button']",
    "//button[@data-testid='review-button']",
    "//button[@data-testid='SmartApplyForm-continueButton']",
    "//button[contains(@class, 'ia-continueButton')]",
    "//button[contains(@class, 'ia-BasePage-footer')]",
    "//button[@type='submit']",
    "//input[@type='submit']",
    "//a[@role='button'][contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue')]",
]

# Step 1: Contact Information
CONTACT_FIRST_NAME = [
    "//input[contains(@name, 'first-name') or contains(@id, 'first-name')]",
    "//input[contains(@name, 'firstName') or contains(@id, 'firstName')]",
    "//input[contains(@id, 'input-firstName')]",
    "//input[contains(@autocomplete, 'given-name')]",
]

CONTACT_LAST_NAME = [
    "//input[contains(@name, 'last-name') or contains(@id, 'last-name')]",
    "//input[contains(@name, 'lastName') or contains(@id, 'lastName')]",
    "//input[contains(@id, 'input-lastName')]",
    "//input[contains(@autocomplete, 'family-name')]",
]

CONTACT_EMAIL = [
    "//input[@type='email']",
    "//input[contains(@name, 'email') or contains(@id, 'email')]",
    "//input[contains(@autocomplete, 'email')]",
]

CONTACT_PHONE = [
    "//input[contains(@type, 'tel')]",
    "//input[contains(@name, 'phone') or contains(@id, 'phone')]",
    "//input[contains(@name, 'phoneNumber') or contains(@id, 'phoneNumber')]",
    "//input[contains(@autocomplete, 'tel')]",
]

# Step 2: Location / Address
ADDRESS_POSTAL_CODE = [
    "//input[contains(@id, 'postal-code') or contains(@name, 'postal-code')]",
    "//input[contains(@id, 'zip') or contains(@name, 'zip')]",
]

ADDRESS_CITY = [
    "//input[contains(@id, 'locality') or contains(@name, 'locality')]",
    "//input[contains(@id, 'city') or contains(@name, 'city')]",
]

ADDRESS_STREET = [
    "//input[contains(@id, 'address') or contains(@name, 'address')]",
    "//textarea[contains(@id, 'address') or contains(@name, 'address')]",
]

# Step 3: Resume / CV
RESUME_SELECTION_CARD = [
    "//div[contains(@class, 'resume') and contains(@class, 'selected')]",
    "//input[@type='radio' and contains(@name, 'resume')]",
]

CV_OPTIONS_BUTTON = [
    "//button[contains(., 'CV options') or contains(., 'Resume options')]",
    "//button[contains(@aria-label, 'CV options') or contains(@aria-label, 'Resume options')]",
]

RESUME_FILE_INPUT = [
    "//input[@type='file']",
]

# Step 4: Employer Screening Questions
QUESTION_BLOCKS = [
    "//fieldset",
    "//div[contains(@class, 'ia-Questions')]//div[contains(@class, 'item')]",
    "//div[contains(@data-testid, 'question')]",
]

# Step 5: Review & Submission
REVIEW_CONTAINER = [
    "div[data-testid='review-module']",
    "div.ia-Review",
]

FINAL_SUBMIT_BUTTONS = [
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit your application')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit application')]",
    "//button[contains(., 'Submit your application')]",
    "//button[contains(., 'Submit application')]",
    "//button[contains(., 'Submit')]",
    "//button[@data-testid='submit-application-button']",
    "//button[@id='submit-application-button']",
    "//button[contains(@class, 'ia-ContinueButton')]",
    "//button[contains(., 'Apply now') and contains(@class, 'ia-')]",
    "//button[@type='submit' and contains(., 'Submit')]",
    "//div[@role='button' and contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit your application')]/ancestor-or-self::button",
]

# Final Confirmation Banner
CONFIRMATION_HEADINGS = [
    "//*[contains(text(), 'Your application was submitted')]",
    "//*[contains(text(), 'application was submitted')]",
    "//*[contains(text(), 'submitted to')]",
    "//*[contains(text(), 'Application submitted')]",
    "//*[contains(text(), 'Your application has been submitted')]",
    "//h1[contains(., 'submitted')]",
    "//h2[contains(., 'submitted')]",
]

RETURN_TO_SEARCH_BUTTON = [
    "//button[contains(., 'Return to job search')]",
    "//a[contains(., 'Return to job search')]",
    "//*[contains(text(), 'Return to job search')]",
    "//button[contains(., 'Done')]",
]
