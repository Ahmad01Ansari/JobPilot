You are working inside the existing JobPilot repository.

Your task is to add a NEW platform automation driver for:

    Foundit
    https://www.foundit.in/

The goal is to implement Foundit automation using the EXISTING JobPilot architecture and coding patterns.

IMPORTANT:
Do NOT redesign JobPilot.
Do NOT rewrite LinkedIn, Naukri, or Indeed automation.
Do NOT duplicate shared business logic unnecessarily.

Foundit must become another platform driver plugged into the existing automation architecture.

============================================================
1. CANONICAL ARCHITECTURE — MUST FOLLOW
============================================================

JobPilot already follows this architecture:

    UI / CLI
       ↓
    AutomationBridge
       ↓
    Platform Driver
       ↓
    Shared Engines
       ├── QualificationEngine
       ├── QnA Engine
       ├── Resume Manager
       ├── ApplicationTracker
       └── AI/LLM Hub
       ↓
    Database

The canonical document defines platform drivers as separate from shared intelligence engines.

Follow the same architecture used by:

    platforms/naukri/
    platforms/indeed/

The existing architecture defines:

    Job
    Application
    Application lifecycle
    Qualification filters
    QnA resolution
    Resume handling
    ApplicationTracker

Do not create another Job model, Application model, QnA engine,
qualification engine, or tracker for Foundit.

Reuse the existing ones.

============================================================
2. FIRST TASK — REPOSITORY AUDIT
============================================================

Before writing code, inspect the existing repository.

Specifically inspect:

    platforms/
    platforms/naukri/
    platforms/indeed/
    platforms/linkedin/
    modules/qna_engine.py
    modules/qualification_engine.py
    modules/tracker.py
    modules/config_loader.py
    modules/models.py
    modules/
    config/
    automation bridge / signal code
    existing platform registration/router code

Also inspect existing tests.

Do NOT assume filenames or class names.

Determine:

1. How Naukri authentication is implemented.
2. How Naukri search is implemented.
3. How Naukri job cards are parsed.
4. How Naukri applications are tracked.
5. How Indeed authentication/profile persistence works.
6. How Indeed form handling is separated from the platform driver.
7. How QnA Engine is called.
8. How Resume Manager is called.
9. How QualificationEngine is called.
10. How ApplicationTracker records states.
11. How platforms are registered/discovered by the AutomationManager.
12. How AutomationBridge emits events.
13. How stop_check / cooperative interruption works.
14. How platform settings are loaded from DB/profile.
15. How existing platform credentials are represented.

Create an internal implementation map before modifying files.

DO NOT change architecture simply because Foundit behaves differently.

============================================================
3. FOUNDIt DIRECTORY ARCHITECTURE
============================================================

Create a dedicated platform package following the closest existing
platform architecture.

Preferred structure:

    platforms/
        foundit/
            __init__.py
            auth.py
            search.py
            parser.py
            applier.py
            selectors.py
            models.py        # only if platform-specific DTOs are required
            rotator.py       # only if existing architecture requires it
            form.py          # only if multi-step application form exists
            submitter.py    # only if separation is useful
            flow.py          # application flow detection
            exceptions.py
            README.md

Do NOT create every file automatically.

Only create modules that are actually required after inspecting
the existing codebase.

Mirror the coding conventions of Naukri/Indeed.

============================================================
4. AUTHENTICATION — EMAIL + PASSWORD
============================================================

Implement Foundit login using the existing browser/session architecture.

Required behavior:

    Foundit Login
        ↓
    Open Foundit
        ↓
    Detect authenticated session
        ↓
    If already logged in:
        continue
    Else:
        open login page
        ↓
        email/username field
        ↓
        password field
        ↓
        login/submit
        ↓
        wait for authenticated state
        ↓
        verify login success

Use the existing JobPilot persistent Chrome profile architecture.

Do NOT store plaintext credentials inside source code.

Credentials must come from the existing JobPilot configuration/
credential system.

Use the existing configuration abstraction if available.

If the repository already has a SecretsService or credential abstraction,
reuse it.

Do not introduce a second credential storage mechanism.

============================================================
5. PERSISTENT BROWSER PROFILE
============================================================

Foundit must have an isolated persistent profile.

Preferred:

    ~/.jobpilot-foundit-profile

Before choosing the exact path, inspect how existing platforms define
their profile paths and follow the established convention.

Important:

Never run two driver instances concurrently against the same profile.

Follow the existing browser initialization abstraction if one exists.

Do not create a completely separate browser framework for Foundit.

============================================================
6. LOGIN STATE DETECTION
============================================================

Implement robust authentication detection.

Do NOT rely only on:

    time.sleep(5)

Use DOM/state-based detection.

Possible states:

    AUTHENTICATED
    LOGIN_REQUIRED
    CAPTCHA_REQUIRED
    LOGIN_FAILED
    UNKNOWN

Authentication verification should use multiple signals where possible:

    - authenticated navigation
    - presence of account/profile element
    - absence of login form
    - known logged-in URL/state
    - user/account menu

Avoid fragile selectors whenever possible.

Selectors should be isolated in:

    platforms/foundit/selectors.py

============================================================
7. CAPTCHA / HUMAN VERIFICATION
============================================================

Do NOT implement CAPTCHA bypass.

Do NOT use:

    CAPTCHA-solving services
    proxy rotation to evade CAPTCHA
    fingerprint spoofing
    stealth patches specifically intended to defeat CAPTCHA
    automated challenge solving

If Foundit presents CAPTCHA or human verification:

    CAPTCHA_REQUIRED
        ↓
    pause automation
        ↓
    notify UI
        ↓
    user completes verification
        ↓
    verify authenticated/application state
        ↓
    resume

Expose a state such as:

    MANUAL_REQUIRED

The automation must not enter an infinite retry loop.

If repeated CAPTCHA/human verification occurs,
pause the Foundit run and allow the user to skip/stop.

============================================================
8. SEARCH ENGINE
============================================================

Implement Foundit job search using the same conceptual architecture
as the other platforms.

The search layer should handle:

    keyword
    location
    experience
    freshness/date posted if supported
    page number
    pagination
    relevant Foundit filters

Do not hard-code user search preferences.

Read them from JobPilot's existing configuration/search settings.

Search should return normalized job records.

Preferred conceptual interface:

    search_jobs(...)
        -> list[NormalizedJob]

Do not make the rest of JobPilot dependent on Foundit's raw DOM.

============================================================
9. JOB CARD EXTRACTION
============================================================

Implement a dedicated Foundit parser.

Extract, where available:

    job_id
    title
    company
    location
    experience
    salary
    posted_date
    job_url
    application_url
    source/platform
    description summary
    raw metadata

Normalize the result into JobPilot's existing Job representation.

Do NOT create a second incompatible job representation unless the
existing architecture requires a temporary platform DTO.

The parser must tolerate:

    missing salary
    missing experience
    missing location
    missing posted date
    dynamic cards
    duplicated cards
    partially loaded cards

Never crash the complete run because one job card is malformed.

Log the problematic job and continue.

============================================================
10. JOB DEDUPLICATION
============================================================

Use the existing Job/Application deduplication strategy if available.

Preferred fingerprint priority:

    1. Foundit native job ID
    2. normalized job URL
    3. normalized combination of:
       platform + title + company + location + source URL

Do NOT create duplicate applications for the same Foundit job.

Before applying:

    check existing application state.

If already submitted:

    SKIP

If previously failed:

    follow existing retry policy.

If manually required:

    do not automatically restart unless explicitly requested.

============================================================
11. QUALIFICATION PIPELINE
============================================================

Follow the existing two-stage filtering architecture.

Stage 1:

    title + company + already-handled checks

before opening expensive job details whenever possible.

Stage 2:

    description + experience + company + blacklist checks

after description extraction.

Use:

    QualificationEngine

Do NOT copy qualification logic into Foundit.

The canonical architecture explicitly requires fast title exclusion
and description filtering before expensive AI calls.
Follow that rule.

Expected flow:

    Foundit Search
        ↓
    Parse Job Card
        ↓
    qualify_title()
        ↓
    SKIP or continue
        ↓
    Open Job
        ↓
    Extract Description
        ↓
    qualify_description()
        ↓
    SKIP or continue
        ↓
    Detect application flow

============================================================
12. JOB DESCRIPTION EXTRACTION
============================================================

Implement Foundit-specific JD extraction.

First inspect the actual Foundit DOM and determine the most reliable
description source.

Build an extraction pipeline rather than relying on one selector.

Conceptually:

    Level 1:
        main job-description container

    Level 2:
        semantic/container fallback

    Level 3:
        structured data / JSON-LD if available

    Level 4:
        secondary page representation if required

    Level 5:
        card/summary fallback

Every extraction result must pass validation.

Create something equivalent to:

    is_valid_job_description(text)

Validation should reject:

    empty text
    loading text
    error text
    login/cookie notices
    obviously incomplete content

Do not send invalid JD content to the QnA/AI systems.

============================================================
13. APPLICATION FLOW DETECTION
============================================================

Foundit may expose different application flows.

Do NOT assume every Apply button behaves identically.

Detect the application flow before executing it.

Suggested normalized states:

    DIRECT_APPLY
    QUESTIONNAIRE
    EXTERNAL_PORTAL
    LOGIN_REQUIRED
    CAPTCHA_REQUIRED
    MANUAL_REQUIRED
    UNKNOWN

Example:

    Click Apply
        ↓
    inspect resulting UI
        ↓
    DIRECT_APPLY
        OR
    QUESTIONNAIRE
        OR
    EXTERNAL
        OR
    LOGIN_REQUIRED
        OR
    CAPTCHA
        OR
    UNKNOWN

The detection must be deterministic where possible.

============================================================
14. DIRECT APPLY FLOW
============================================================

For a simple Foundit application:

    Open job
        ↓
    Click Apply
        ↓
    detect confirmation/result
        ↓
    verify application submitted
        ↓
    record SUBMITTED

Do NOT treat a successful button click alone as proof of submission.

Require a confirmation signal such as:

    confirmation message
    application state
    applied indicator
    known post-submit state
    URL/state transition

Use DOM polling rather than arbitrary long sleeps.

============================================================
15. QUESTIONNAIRE / MULTI-STEP FORM
============================================================

If Foundit presents a questionnaire:

    detect current step
        ↓
    inspect fields
        ↓
    classify field
        ↓
    resolve answer
        ↓
    validate answer
        ↓
    fill
        ↓
    continue
        ↓
    detect next step
        ↓
    repeat

Support, where present:

    text
    textarea
    radio
    checkbox
    select
    date
    numeric
    file upload

Do not assume every field is a question.

Use labels, name attributes, aria-labels, nearby text,
fieldset legends, and semantic relationships to identify fields.

============================================================
16. QnA ENGINE INTEGRATION
============================================================

DO NOT implement a Foundit-specific AI answering system.

Use the existing JobPilot QnA pipeline.

Expected resolution:

    Foundit Question
        ↓
    QnA Engine
        ↓
    Tier 1: profile/catalog
        ↓
    Tier 2: resume/context
        ↓
    Tier 3: configured LLM
        ↓
    answer
        ↓
    validate
        ↓
    fill

The canonical QnA architecture has three tiers:
catalog/profile → resume semantic context → LLM fallback.

Reuse that exact concept.

AI answers must only use factual candidate profile information.

Never invent:

    employment history
    education
    certifications
    years of experience
    salary
    visa/citizenship information
    notice period
    skills

If confidence is insufficient:

    MANUAL_REQUIRED

============================================================
17. RESUME HANDLING
============================================================

Reuse JobPilot's existing Resume Manager.

Do NOT create:

    foundit_resume_manager.py

unless the existing architecture genuinely requires a platform adapter.

Use the configured default resume or role-matched resume according
to the existing system.

Handle:

    existing resume selection
    PDF upload
    resume validation
    missing resume

If upload fails:

    record meaningful error
    do not falsely mark application as submitted.

============================================================
18. EXTERNAL APPLICATIONS
============================================================

If Foundit redirects to an employer/third-party portal:

    capture destination URL
    verify it is external
    record:

        EXTERNAL

Do not pretend the application was submitted.

Persist:

    source URL
    external application URL
    company
    title
    timestamp
    reason/state

The UI should allow the user to open the external application.

============================================================
19. APPLICATION STATE MACHINE
============================================================

Use the existing JobPilot lifecycle.

Expected states:

    DISCOVERED
    QUALIFIED
    APPLYING
    EXTERNAL
    SKIPPED
    MANUAL_REQUIRED
    FAILED
    SUBMITTED

Example:

    DISCOVERED
        ↓
    QUALIFIED
        ↓
    APPLYING
        ├──→ SUBMITTED
        ├──→ EXTERNAL
        ├──→ MANUAL_REQUIRED
        ├──→ SKIPPED
        └──→ FAILED

Do not invent a Foundit-specific lifecycle.

Persist all meaningful transitions through the existing
ApplicationTracker/service layer.

============================================================
20. APPLICATION FAILURE CLASSIFICATION
============================================================

Do not classify every failure as FAILED.

Distinguish:

    LOGIN_REQUIRED
    CAPTCHA_REQUIRED
    MANUAL_REQUIRED
    FORM_VALIDATION_ERROR
    ELEMENT_NOT_FOUND
    TIMEOUT
    NETWORK_ERROR
    UNKNOWN

Map them to JobPilot's existing application state model appropriately.

Store the detailed failure reason separately if the existing model
supports it.

============================================================
21. STOP / PAUSE SUPPORT
============================================================

Every search iteration and application step must support cooperative
stopping.

Follow the existing pattern:

    if stop_check and stop_check():
        break

Also support pause/manual intervention if the existing AutomationWorker
provides it.

Never leave the browser in an uncontrolled infinite loop.

============================================================
22. BROWSER NAVIGATION SAFETY
============================================================

Use the existing browser abstraction.

Do not create a second Chrome manager unless necessary.

Avoid fixed sleeps wherever possible.

Instead poll for:

    URL change
    DOM element appearance
    spinner disappearance
    form transition
    button state
    application confirmation

Use short bounded waits.

Every wait must have a timeout.

Never:

    while True:
        wait()

without timeout or stop_check.

============================================================
23. SELECTOR ARCHITECTURE
============================================================

All Foundit-specific selectors must live in:

    platforms/foundit/selectors.py

Avoid scattering selectors across:

    applier.py
    search.py
    parser.py
    auth.py

Prefer semantic selectors:

    data attributes
    aria labels
    stable IDs
    accessible roles
    form labels
    semantic HTML

Avoid brittle selectors such as:

    div:nth-child(7) > div:nth-child(2)

unless absolutely necessary.

Where multiple selectors are required, create selector fallbacks.

============================================================
24. PLATFORM ADAPTER / COMMON INTERFACE
============================================================

Inspect the existing BasePlatformApplier or equivalent interface.

Foundit should conform to the same interface.

Expected conceptual methods may include:

    login()
    is_logged_in()
    search_jobs()
    parse_job()
    apply_to_job()
    get_job_description()
    detect_application_flow()
    stop()

BUT:

Do not blindly create these names.

Use the actual interfaces found in the repository.

Foundit must be usable by the existing AutomationManager/router
without platform-specific special cases scattered throughout the app.

============================================================
25. AUTOMATION MANAGER INTEGRATION
============================================================

Register Foundit with the existing platform router/manager.

Expected conceptual configuration:

    linkedin
    naukri
    indeed
    foundit

The AutomationManager should be able to start:

    Foundit only

or:

    all configured platforms

without breaking existing platforms.

Do not modify existing platform behavior.

============================================================
26. DESKTOP GUI INTEGRATION
============================================================

If platform selection exists in the GUI:

    add Foundit

Do not redesign the AutomationView.

Reuse existing:

    started
    progress
    job_found
    app_submitted
    log_emitted
    error
    finished

signals.

Foundit should emit the same normalized events as other platforms.

Example:

    PLATFORM=Foundit
    EVENT=JOB_FOUND
    EVENT=JOB_SKIPPED
    EVENT=APPLICATION_STARTED
    EVENT=MANUAL_REQUIRED
    EVENT=APPLICATION_SUBMITTED
    EVENT=APPLICATION_FAILED

============================================================
27. LOGGING
============================================================

Use the existing LogService / logging abstraction.

Every application should have useful structured logs.

Example:

    [FOUNDIt] Login successful
    [FOUNDIt] Search: RPA Developer | India
    [FOUNDIt] Found 20 job cards
    [FOUNDIt] SKIP: Senior RPA Architect | 8+ years
    [FOUNDIt] QUALIFIED: RPA Developer | ABC Technologies
    [FOUNDIt] Applying: job_id=...
    [FOUNDIt] Flow: QUESTIONNAIRE
    [FOUNDIt] QnA: 4 fields resolved
    [FOUNDIt] Application submitted
    [FOUNDIt] Recorded SUBMITTED

Never log:

    passwords
    cookies
    session tokens
    API keys
    secrets

============================================================
28. ERROR RECOVERY
============================================================

A single bad job must NOT terminate the entire Foundit run.

Per-job exception boundary:

    try:
        process_job(job)
    except RecoverableJobError:
        log
        record failure
        continue
    except ManualRequired:
        pause/manual state
    except StopRequested:
        exit gracefully

Only fatal browser/session failures should terminate the platform run.

============================================================
29. TESTING
============================================================

Before declaring implementation complete, add tests.

Minimum tests:

AUTH:

    test_login_success
    test_already_logged_in
    test_login_required
    test_login_failure
    test_captcha_requires_manual

SEARCH:

    test_search_url
    test_parse_job_cards
    test_empty_results
    test_pagination

PARSER:

    test_parse_title
    test_parse_company
    test_parse_location
    test_parse_experience
    test_parse_salary
    test_parse_job_url
    test_missing_optional_fields

DESCRIPTION:

    test_valid_description
    test_invalid_description
    test_loading_stub_rejected

QUALIFICATION:

    test_title_skip
    test_company_skip
    test_description_skip
    test_qualified_job

APPLICATION:

    test_direct_apply
    test_questionnaire_flow
    test_external_flow
    test_manual_required
    test_submit_confirmation
    test_failed_application

QNA:

    test_existing_qna_engine_called
    test_unknown_question_escalates

TRACKING:

    test_discovered
    test_qualified
    test_applying
    test_submitted
    test_external
    test_manual_required
    test_failed

INTEGRATION:

    test_foundit_registered
    test_automation_manager_can_start_foundit
    test_stop_check
    test_event_emission

Do not require a live Foundit account for unit tests.

Use mocks/fakes for Selenium wherever possible.

============================================================
30. LIVE BROWSER TEST
============================================================

After unit tests pass, create a controlled manual/live smoke test.

Do NOT immediately automate hundreds of applications.

First validate:

    1. Browser starts
    2. Foundit opens
    3. Login page detected
    4. Email/password can be supplied from configured credentials
    5. Login success detected
    6. Search works
    7. Job cards are extracted
    8. Job details open
    9. JD extraction works
    10. Qualification filters work
    11. Apply flow is detected
    12. Form fields are identified
    13. QnA Engine is called
    14. Resume handling works
    15. Confirmation is detected
    16. ApplicationTracker receives correct state

Initially use:

    pause_before_submit = true

so submission can be manually reviewed.

============================================================
31. IMPORTANT: DO NOT FAKE SUCCESS
============================================================

Never mark:

    SUBMITTED

merely because:

    Apply button clicked
    form opened
    final page loaded

Require an actual confirmation signal.

Similarly:

    EXTERNAL

only when an external destination is actually detected.

============================================================
32. NO DUPLICATION OF SHARED LOGIC
============================================================

Do NOT copy/paste:

    QualificationEngine
    QnA Engine
    Resume Manager
    ApplicationTracker
    ConfigLoader
    SecretsService
    Browser Manager
    AutomationWorker
    AutomationBridge

Foundit should be a thin platform-specific adapter around the
existing JobPilot infrastructure.

============================================================
33. IMPLEMENTATION ORDER
============================================================

Implement in this exact order:

PHASE A — Audit
    inspect repository
    inspect Naukri
    inspect Indeed
    identify shared interfaces

PHASE B — Platform skeleton
    platforms/foundit/
    selectors
    exceptions
    platform registration

PHASE C — Authentication
    persistent profile
    login
    session detection
    manual verification handling

PHASE D — Search
    search URL/form
    pagination
    job card extraction

PHASE E — Job parser
    normalize job
    JD extraction
    validation

PHASE F — Qualification
    integrate existing QualificationEngine

PHASE G — Application flow detection
    direct
    questionnaire
    external
    manual
    unknown

PHASE H — Application
    form detection
    QnA Engine
    resume
    submit confirmation

PHASE I — Tracking
    ApplicationTracker
    logs
    AutomationBridge events

PHASE J — GUI/router
    platform registration
    Foundit selection
    status/event integration

PHASE K — Tests
    unit tests
    integration mocks
    regression tests

PHASE L — Controlled live smoke test

============================================================
34. CRITICAL REGRESSION RULE
============================================================

After implementation:

    Existing LinkedIn tests must still pass.
    Existing Naukri tests must still pass.
    Existing Indeed tests must still pass.

Do not alter their behavior to make Foundit work.

If a shared abstraction must be changed:

    1. make it backward compatible
    2. add regression tests
    3. explain exactly why the change is necessary

============================================================
35. FINAL DELIVERABLE
============================================================

At the end, provide a concise implementation report:

1. Files created
2. Files modified
3. Existing files reused
4. Authentication flow
5. Search flow
6. JD extraction levels
7. Application flows supported
8. QnA integration
9. Resume integration
10. Application states
11. CAPTCHA/manual intervention behavior
12. Tests added
13. Test results
14. Known limitations
15. Any Foundit behavior that could not be verified

Do not claim live functionality unless it was actually tested.

============================================================
MOST IMPORTANT RULE
============================================================

COPY THE ARCHITECTURE, NOT THE CODE.

Use Naukri/Indeed as architectural references.

Foundit must have:

    Platform Driver
        ↓
    Foundit Search
        ↓
    Foundit Parser
        ↓
    QualificationEngine
        ↓
    Foundit Application Flow
        ↓
    QnA Engine
        ↓
    Resume Manager
        ↓
    ApplicationTracker
        ↓
    AutomationBridge / UI

while preserving the existing JobPilot architecture.

Do not rewrite existing automation.
Do not create duplicate shared engines.
Do not hard-code credentials.
Do not bypass CAPTCHA/security controls.
Do not mark applications successful without confirmation.
Do not use infinite retry loops.

Start by auditing the repository and existing Naukri/Indeed
implementations before making any code changes.

============================================================
PHASE 2 IMPLEMENTATION SUMMARY & PRODUCTION FINDINGS
============================================================

### 1. Authentication & Cookie Persistence
- Profile directory: `~/.jobpilot-foundit-profile`
- Persistent session cookies: `IS_LOGGED_IN == "true"` and `MSSOAT` (JWT session token).
- `check_session_state()` inspects persistent cookies and profile DOM elements (`Hi, <Candidate>`, `profile_avatar`, `/home/user`) first.
- If session is valid, `FounditAuth.login()` immediately skips credential entry and avoids unnecessary login loops.

### 2. UI Search Fields & Quick Apply Toggle
- Avoid direct parameterized URLs (`/srp/results?query=...`) which trigger Cloudflare/Akamai bot detection.
- `search_via_ui()` navigates to `https://www.foundit.in/` and interacts with:
  - Skills Input: `#heroSectionDesktop-skillsAutoComplete--input`
  - Location Input: `#heroSectionDesktop-locationAutoComplete--input`
  - Experience Input / Dropdown: `#heroSectionDesktop-expAutoComplete--input`
  - Search Button: `button.search_submit_btn`
- On the Search Results Page (SRP):
  - Automatically activates the `Quick Apply` toggle switch (`input#toggle` / `//span[contains(text(), 'Quick Apply')]`) to filter for 1-click apply jobs.
  - Applies sidebar experience and location filters as required.

### 3. Multi-Tab Apply & Qualification Workflow
- Foundit job cards open applications in a new tab (`target="_blank"`).
- `FounditApplier.apply()`:
  1. Captures `main_window` handle and initial window handles.
  2. Clicks `Apply Now` / `Quick Apply`.
  3. Detects the new tab and switches window context.
  4. Extracts full Job Description (JD), experience, and salary from the new tab.
  5. Evaluates Stage 2 qualification (`qualification_engine.qualify_job_post_click(job)`). If disqualified, marks `SKIPPED` in `ApplicationTracker`, closes the new tab, and returns focus to `main_window`.
  6. If qualified and external employer site (e.g. LinkedIn, Workday, company portal): captures redirect URL, marks `EXTERNAL` in `ApplicationTracker`, closes the new tab, and refocuses `main_window`.
  7. If native Foundit apply: fills screening questions via `FounditForm`, clicks submit, confirms submission status, records `SUBMITTED`, closes the new tab, and cleanly returns to `main_window`.