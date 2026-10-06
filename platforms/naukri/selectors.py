'''
Naukri DOM Selectors
Isolates all HTML classes, IDs, XPaths, and CSS selectors for Naukri.com.
Makes platform DOM updates easy to maintain without altering core platform logic.
'''

# --- URLs ---
LOGIN_URL = "https://www.naukri.com/nlogin/login"
HOME_URL = "https://www.naukri.com/"
LOGGED_IN_HOMEPAGE_URL = "https://www.naukri.com/mnjuser/homepage"

# --- Authentication & Session Indicators ---
# Elements present only when a session is authenticated
LOGGED_IN_SELECTORS = [
    ".nI-gNb-drawer__bars",
    ".view-profile-wrapper",
    "a[href*='mnjuser/profile']",
    "a[href*='myprofile']",
    ".nI-gNb-header__wrapper .user-name",
    ".user-name",
    "div.nI-gNb-drawer",
    "a.nI-gNb-header__logo[href*='mnjuser']",
    ".logged-in",
]

# Elements present when login is required
# IMPORTANT: These must be specific to the header/login-page context.
# Broad selectors like a[href*='login'] cause false positives on authenticated pages
# because footer/menu links also contain 'login' in their href.
LOGIN_REQUIRED_SELECTORS = [
    "#usernameField",
    "input[placeholder*='Username']",
    "input[placeholder*='Email']",
    "#passwordField",
    "a#login_Layer",
    "a[title='Jobseeker Login']",
    "a[href*='nlogin/login']",
    ".nI-gNb-header__login",
    "a[title='Jobseeker Register']",
    ".nI-gNb-header__register",
]

# Elements indicating login submission failure or invalid credentials
LOGIN_ERROR_SELECTORS = [
    ".server-err",
    ".err-container",
    ".error-message",
    "div.server-err",
    ".err",
    "span[class*='error']",
]

# Indicators of anti-bot challenge or CAPTCHA
CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='challenge']",
    ".captcha-container",
    ".geetest_holder",
    "#bot-detector",
    "div[class*='captcha']",
    "div[id*='captcha']",
]

# Indicators of Two-Factor Authentication / OTP checkpoint
OTP_SELECTORS = [
    "input[placeholder*='OTP']",
    "input[name*='otp']",
    "#otpField",
    ".otp-container",
]

# Login form fields
LOGIN_USERNAME_INPUT = "#usernameField"
LOGIN_PASSWORD_INPUT = "#passwordField"
LOGIN_SUBMIT_BUTTON = "button[type='submit'].btn-primary, button[type='submit']"

# --- Search & Results Selectors ---
SEARCH_BASE_URL = "https://www.naukri.com"

# Job Card Container / Tuples across Naukri UI iterations
JOB_CARD_SELECTORS = [
    "div.srp-jobtuple-wrapper",
    "article.jobTuple",
    "div[data-job-id]",
    "div.cust-job-tuple",
    ".srp-tuple-card",
]

# Card Details Selectors (Relative to Job Card)
CARD_TITLE_SELECTORS = ["a.title", "a[class*='title']"]
CARD_COMPANY_SELECTORS = ["a.subTitle", "a[class*='comp-name']", "span.comp-name", ".company-name"]
CARD_LOCATION_SELECTORS = ["span.loc-wrap", "span[class*='locWdth']", "span[class*='location']", "li[class*='location']"]
CARD_EXPERIENCE_SELECTORS = ["span.exp-wrap", "span[class*='expwdth']", "span[class*='experience']", "li[class*='experience']"]
CARD_SALARY_SELECTORS = ["span.sal-wrap", "span[class*='sal']", "li[class*='salary']", "span[class*='ni-job-tuple-icon-salary']"]
CARD_DESCRIPTION_SNIPPET = [

    "span.job-desc",
    "div.job-desc",
    "div[class*='job-desc']",
    "span[class*='ni-job-tuple-icon-srp-description']",
    "div.row4",
    "div[class*='srp-description']",
    "div[class*='job-description']",
    "span.styles_jpt__desc__"
]
JOB_DETAILS_DESCRIPTION_SELECTORS = [
    "section.job-desc-details",
    "div.styles_JDC__dang-inner-html__h0K4t",
    "div.dang-inner-html",
    "div[class*='dang-inner-html']",
    "div[class*='job-desc']",
    "div[class*='job-description']",
    "section[class*='job-desc']",
    "article[class*='job-desc']",
]
CARD_POSTED_DATE = ["span.date", "span[class*='posted-date']", ".job-post-day", "span[class*='fleft']"]


# Results Indicators
NO_JOBS_SELECTORS = [
    ".no-jobs-found",
    "div[class*='no-result']",
    ".zero-results",
    "div.no-data",
]

# Pagination
PAGINATION_NEXT_BUTTONS = [
    "a[class*='next']",
    "a[class*='styles_btn-secondary']",
    "a.styles_btn-secondary__2Sm-s",
    ".pagination a.next",
]

# Already Applied Status Indicators
ALREADY_APPLIED_SELECTORS = [
    "button[class*='already-applied']",
    "span[class*='already-applied']",
    ".already-applied",
    "span[class*='applied-txt']",
    "div[class*='applied-msg']",
    "button[class*='applied']",
    ".drawer-applied",
    "div[class*='chatbot_applied']",
]

ALREADY_APPLIED_XPATHS = [
    "//button[normalize-space(translate(text(), 'APPLIED', 'applied'))='applied']",
    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')]",
    "//span[normalize-space(translate(text(), 'APPLIED', 'applied'))='applied']",
    "//span[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')]",
    "//div[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')]",
    "//p[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'you have applied')]",
    "//p[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')]",
    "//*[starts-with(normalize-space(translate(text(), 'APPLIED TO', 'applied to')), 'applied to')]",
    "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start your interview preparation')]",
]

# --- Application Flow & Modal Selectors ---
# Apply Buttons on Job Details page or Card
APPLY_BUTTON_SELECTORS = [
    # Company Portal / External Apply Buttons (most specific)
    "button#company-site-button",
    "#company-site-button",
    "button.company-site-button",
    "button[class*='company-site-button']",
    "button[class*='styles_company-site-button']",
    "a#company-site-button",
    "a[class*='company-site-button']",
    # ID-based (most stable)
    "button#apply-button",
    "#apply-button",
    "button#applyButton",
    # Class-based with partial matches
    "button.apply-button",
    "button[class*='apply-button']",
    "button[class*='apply-btn']",
    "button[class*='applyBtn']",
    "button[class*='styles_apply-button']",
    "button[class*='styles_apply']",
    "button[class*='styles_btn']",
    "button[class*='apply_CTA']",
    "button[class*='applyCTA']",
    # Container-based
    "div[class*='apply-button-container'] button[id*='apply']",
    "div[class*='apply-button-container'] button[id*='company']",
    "div[class*='apply-button-container'] button[class*='apply']",
    "div[class*='apply-button-container'] button[class*='company']",
    "div[class*='apply-button-container'] button",
    "div[class*='apply-container'] button",
    "div[class*='top-card'] button",
    "div[class*='job-header'] button",
    "div[class*='job-actions'] button",
    # Naukri chatbot / drawer apply buttons
    ".apply-message button",
    "button[class*='chatbot_applyBtn']",
    "button[class*='chatbot-apply']",
    # Aria / data attribute based
    "button[aria-label*='Apply']",
    "button[data-ga-track*='apply']",
    "button[data-id='apply']",
    # Broader tag + text content matches (used as CSS last resort)
    "a[class*='apply-button']",
    "a[class*='apply-btn']",
    "a#apply-button",
    "a[class*='apply_CTA']",
    # Generic visible apply/quick-apply buttons
    "button[title*='Apply']",
    "button[title*='apply']",
    "input[type='button'][value*='Apply']",
]

# XPath selectors for Apply button - more reliable than CSS for Naukri's dynamic DOM
APPLY_BUTTON_XPATH_SELECTORS = [
    "//button[@id='company-site-button' or contains(@class, 'company-site-button')]",
    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company site') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company website')]",
    "//button[@id='apply-button' or @id='applyButton']",
    "//button[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') and not(contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')) and not(normalize-space(translate(text(), 'APPLIED', 'applied'))='applied')]",
    "//a[@id='company-site-button' or contains(@class, 'company-site-button')]",
    "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company site') or contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company website')]",
    "//a[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply') and not(contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'already applied')) and not(normalize-space(translate(text(), 'APPLIED', 'applied'))='applied')]",
    "//div[contains(@class, 'apply')]//button",
    "//div[contains(@class, 'apply')]//a",
    "//button[.//span[contains(translate(normalize-space(.), 'APPLY', 'apply'), 'apply')]]",
]

# Indicator text for External application
EXTERNAL_APPLY_TEXTS = [
    "apply on company site",
    "apply on company website",
    "company site",
    "company website",
    "apply externally",
    "apply on employer site",
    "apply on employer website",
    "employer website",
    "employer site",
    "redirect to",
]

EXTERNAL_APPLY_XPATHS = [
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company site')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company website')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employer site')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employer website')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply externally')]",
    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company site')]",
    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'company website')]",
    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employer site')]",
    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'employer website')]",
    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply externally')]",
]

# Questionnaire Form / Chatbot Modal Indicators
QUESTIONNAIRE_MODAL_SELECTORS = [
    "div._chatBotContainer",
    "div[class*='_chatBotContainer']",
    "div.chatbot_Drawer",
    "div[class*='chatbot_Drawer']",
    "div.chatbot_MessageContainer",
    "div[class*='chatbot_MessageContainer']",
    "div.apply-message-container",
    "div[class*='apply-message-container']",
    "div[class*='apply-message-wrapper']",
    "div[class*='chatbot-container']",
    "div[class*='chatbot_container']",
    "div[class*='chatbot-wrapper']",
    ".chatbot_DrawerContent",
    "div[class*='DrawerContent']",
    "div[class*='chat-container']",
    "div[class*='chatContainer']",
    "div[class*='bot-form']",
    "div[class*='bot-container']",
    "div[class*='botContainer']",
    "form[name*='applyForm']",
    "div.qna-container",
    "div[class*='qna']",
    ".questions-wrapper",
    "div[class*='drawer-wrapper']",
    "div[class*='apply-drawer']",
    "div[class*='apply-modal']",
    "div.modal-body",
    "div[class*='drawer']:not([class*='nI-gNb']):not([class*='gnb'])",
]

# Direct / 1-Click Confirmation Indicators
DIRECT_APPLY_SUCCESS_SELECTORS = [
    "div[class*='apply-success']",
    "div[class*='applied-to']",
    "div[class*='applied_to']",
    "span[class*='applied-txt']",
    ".already-applied",
    "span[class*='already-applied']",
    "button[class*='already-applied']",
    ".success-msg",
    "div.toaster-content",
    "div[class*='toast-message']",
    "div[class*='success-container']",
    "div[class*='success-card']",
    ".drawer-applied",
    "div[class*='chatbot_applied']",
    "div[class*='apply-button-container']",
    "div[class*='styles_jhc__apply-button-container']",
    "div[class*='styles_applied']",
    "span[class*='styles_applied']",
    "div[class*='interview-prep']",
    "div[class*='prep']",
]

# Incomplete Profile / Missing Information Modal (Requires MANUAL_REQUIRED)
PROFILE_INCOMPLETE_SELECTORS = [
    ".profile-incomplete",
    "div[class*='incomplete-profile']",
    "div[class*='profile-update-modal']",
    "a[href*='update-profile']",
]

# Modal Discard / Close Buttons
MODAL_CLOSE_BUTTONS = [
    "button[class*='cross']",
    "span[class*='cross']",
    "span[class*='crossIcon']",
    "i[class*='crossIcon']",
    "div[class*='crossIcon']",
    "#crossIcon",
    ".crossIcon",
    "button[class*='close']",
    "span[class*='close']",
    "i[class*='close']",
    "span.ni-icon-cross",
    "i.ni-icon-cross",
    ".drawer-close",
    "[aria-label='Close' i]",
    "[aria-label='Dismiss' i]",
]

# Unexpected Marketing / Notification / Location / Cookie Popup Dismiss Controls
POPUP_DISMISS_SELECTORS = [
    "button[class*='cross']",
    "span[class*='cross']",
    "span[class*='crossIcon']",
    "i[class*='crossIcon']",
    "div[class*='crossIcon']",
    "#crossIcon",
    ".crossIcon",
    "button[class*='close']",
    "span[class*='close']",
    "i[class*='close']",
    "span.ni-icon-cross",
    "i.ni-icon-cross",
    "button#block-notifications",
    "button[id*='block']",
    "button[class*='later']",
    "a[class*='later']",
    "span[class*='later']",
    "button[class*='skip']",
    "a[class*='skip']",
    "span[class*='skip']",
    "div[class*='nudge'] span[class*='cross']",
    "div[class*='nudge'] button[class*='close']",
    "div[class*='feedback'] span[class*='cross']",
    "div[class*='survey'] button[class*='close']",
    "div[class*='chatbot'] button[class*='close']",
    "div[class*='chatbot'] span[class*='cross']",
    ".chatbot_DrawerControl span.crossIcon",
    "div[class*='location'] button[class*='close']",
    "div[class*='location'] span[class*='cross']",
    "div[class*='location-popup'] button",
    "div[class*='location-popup'] span[class*='cross']",
    "div[class*='loc-popup'] button",
    "div[class*='loc-popup'] span[class*='cross']",
    "[aria-label='Close' i]",
    "[aria-label='Dismiss' i]",
]


# --- Form Field & Question Selectors ---
# Question Containers / Form Groups / Chatbot Message Wrappers
QUESTION_BLOCK_SELECTORS = [
    "div.question-item",
    "div[class*='question-wrap']",
    "div[class*='bot-msg']",
    "div[class*='botMsg']",
    "div.form-group",
    "div[class*='field-wrapper']",
    "div[class*='q-item']",
    "div.msg-wrap",
    "li[class*='question']",
]

# Question Text / Prompt Selectors
QUESTION_LABEL_SELECTORS = [
    "label",
    "span.question-text",
    "span[class*='question-title']",
    "div[class*='question-title']",
    "p.msg-text",
    "div.msg-text",
    "span.msg-text",
    "span.label",
    "div.label",
    "div[class*='bot-msg']",
    "div[class*='botMsg']",
    "div[class*='msg-wrapper']",
    "div[class*='chat-bubble']",
    "div[class*='content']",
]

# Inputs & Controls
FORM_TEXT_INPUT_SELECTORS = [
    "input[placeholder*='Type message']",
    "input[placeholder*='type message']",
    "input[placeholder*='Type your answer']",
    "input[placeholder*='type your answer']",
    "textarea[placeholder*='Type message']",
    "textarea[placeholder*='type message']",
    "textarea[placeholder*='Type your answer']",
    "textarea[placeholder*='type your answer']",
    "input[class*='chat-input']",
    "input[class*='bot-input']",
    "input[type='text']",
    "input[type='number']",
    "input[type='tel']",
    "input[type='email']",
    "input:not([type])",
]

FORM_TEXTAREA_SELECTORS = [
    "textarea",
]

# Rich Text / Contenteditable Controls
CONTENTEDITABLE_SELECTORS = [
    "div[contenteditable='true']",
    "div[contenteditable='']",
    "p[contenteditable='true']",
    "span[contenteditable='true']",
    "[role='textbox'][contenteditable='true']",
    "div[class*='chat-input'][contenteditable]",
    "div[class*='editor'][contenteditable]",
    "div.textArea",
    "div[class*='textArea']",
    "div[class*='chatbot_InputContainer'] div",
    "div[class*='chatbot_InputContainer'] [contenteditable]",
]

FORM_RADIO_SELECTORS = [
    "input[type='radio']",
    "div[class*='radio']",
    "label[class*='radio']",
    "span[class*='radio']",
    "li[class*='radio']",
    "[role='radio']",
    "div[class*='option']",
    "li[class*='option']",
    "div[class*='choice']",
    "button[class*='choice']",
    "div[class*='pill']",
    "div[class*='bot-option']",
    "div[class*='bot-chip']",
    "button[class*='bot-chip']",
    "div.bot-chips button",
    "div.bot-chips .chip",
    "div[class*='chips'] button",
    "div[class*='chip-wrapper'] button",
    "button[class*='chip']",
    "div[class*='quick-reply']",
    "div[class*='quickReply']",
    "button[class*='quick-reply']",
    "button[class*='quickReply']",
    "ul.chips li button",
    "ul.chips li",
    "span[class*='radio-label']",
    "label.radio",
    "div[class*='radio-wrap']",
    "div[class*='radioOpt']",
    "label.mcc__label",
    "label[class*='mcc__label']",
    "label[class*='mcc']",
]

FORM_CHECKBOX_SELECTORS = [
    "input[type='checkbox']",
    "label[class*='checkbox']",
    "input.mcc__checkbox",
    "input[class*='mcc__checkbox']",
    "label.mcc__label",
    "label[class*='mcc__label']",
    "div[class*='multiselectcheckboxes'] label",
    "div[class*='multicheckboxes'] label",
]

FORM_SELECT_SELECTORS = [
    "select",
    "div.dropdown",
    "div[class*='select-dropdown']",
    "div[class*='custom-select']",
]

FORM_FILE_SELECTORS = [
    "input[type='file']",
]

# Form Navigation / Action Buttons
FORM_NEXT_BUTTON_SELECTORS = [
    "button[class*='next']",
    "button[class*='continue']",
    "button[class*='save']",
    "button[class*='btn-next']",
    "button[class*='save-btn']",
    "button[class*='saveBtn']",
    "button.styles_btn",
    "a[class*='next']",
]

FORM_SUBMIT_BUTTON_SELECTORS = [
    "button[class*='submit']",
    "button#submit-button",
    "button[class*='btn-primary'][type='submit']",
    "button[type='submit']",
    "button[class*='save'][type='submit']",
    "button[class*='save-btn']",
    "button[class*='saveBtn']",
    "button[class*='save']",
    "button[id*='submit']",
    "button[id*='save']",
]

# --- Submission Confirmation & Verification Selectors ---
SUBMISSION_SUCCESS_SELECTORS = [
    "div[class*='applied-to']",
    "div[class*='apply-success']",
    "div[class*='applied-message']",
    "div[class*='chatbot_applied']",
    "div[class*='bot-success']",
    ".success-msg",
    "div[class*='success-container']",
    "div[class*='success-card']",
    "div[class*='confirm-apply']",
    ".drawer-applied",
    "div[class*='applied-banner']",
    # NOTE: Removed overly broad selectors that cause false positives:
    #   div[class*='applied']  - matches random divs on job pages
    #   div[class*='power-up'] - matches promo banners
    #   div[class*='pro-apply'] - matches promo banners
    #   p[class*='success']     - too broad
    #   div[class*='interview-prep'] - matches non-confirmation sections
    #   div[class*='applyMessage']   - matches chatbot drawer body before completion
]

SUBMISSION_ERROR_TEXTS = [
    "not accepted",
    "incomplete information",
    "not accepted due to incomplete information",
    "mandatory questions",
    "reapplying",
    "oops",
    "application was not accepted",
    "application not accepted",
    "something went wrong",
    "could not be submitted",
    "error occurred",
    "please answer all",
    "failed to submit",
    "unable to submit",
]

SUBMISSION_CONFIRMATION_TEXTS = [
    "applied successfully",
    "application submitted",
    "application sent",
    "you have applied",
    "successfully applied",
    "application has been sent",
    "thank you for applying",
    "application is received",
    "application status: applied",
    "applied to",
    "start your interview preparation",
    "all interview questions for this job",
    "thank you for your responses",
    "thank you for your response",
]

# Chatbot-specific confirmation texts (only checked within drawer context or verify_submission)
CHATBOT_CONFIRMATION_TEXTS = [
    "thank you for your response",
    "thank you for your responses",
    "response has been recorded",
    "responses have been recorded",
    "your response has been submitted",
    "answers have been submitted",
]

APPLIED_BUTTON_SELECTORS = [
    "button[class*='applied']",
    "span[class*='applied']",
    ".already-applied",
    "button[disabled]",
    "span[class*='applied-txt']",
]

# Rate limit and access error indicators (Section 15 Case G)
RATE_LIMIT_SELECTORS = [
    "div[class*='rate-limit']",
    "div[class*='block-msg']",
    "div[class*='access-denied']",
    "div.error-429",
]

RATE_LIMIT_TEXTS = [
    "too many requests",
    "daily application limit",
    "maximum applications reached",
    "rate limit",
    "temporarily blocked",
    "access denied",
    "limit reached for today",
    "you have exceeded",
]

# Apply disabled indicators (Section 15 Case H)
APPLY_DISABLED_SELECTORS = [
    "button[disabled]",
    "button.disabled",
    "button[aria-disabled='true']",
    "div[class*='disabled-apply']",
]

# --- Section 18 Semantic Grouping Aliases ---
APPLY_BUTTON = APPLY_BUTTON_SELECTORS
APPLIED_INDICATOR = APPLIED_BUTTON_SELECTORS + ALREADY_APPLIED_SELECTORS
QUESTION_CONTAINER = QUESTION_BLOCK_SELECTORS
QUESTION_TEXT = QUESTION_LABEL_SELECTORS
TEXT_INPUT = FORM_TEXT_INPUT_SELECTORS
TEXTAREA = FORM_TEXTAREA_SELECTORS
CONTENTEDITABLE = CONTENTEDITABLE_SELECTORS
RADIO_OPTION = FORM_RADIO_SELECTORS
CHECKBOX = FORM_CHECKBOX_SELECTORS
DROPDOWN = FORM_SELECT_SELECTORS
NEXT_BUTTON = FORM_NEXT_BUTTON_SELECTORS
SUBMIT_BUTTON = FORM_SUBMIT_BUTTON_SELECTORS
SUCCESS_INDICATOR = SUBMISSION_SUCCESS_SELECTORS
LOGIN_INDICATOR = LOGIN_REQUIRED_SELECTORS
CAPTCHA_INDICATOR = CAPTCHA_SELECTORS
ERROR_INDICATOR = LOGIN_ERROR_SELECTORS + RATE_LIMIT_SELECTORS



