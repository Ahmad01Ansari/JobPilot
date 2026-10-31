You are working on JobPilot, a PySide6 desktop application for managing the complete job-search lifecycle.

I want you to build a production-quality FIRST-RUN SETUP WIZARD that turns a fresh JobPilot installation into a fully configured, application-ready workspace.

IMPORTANT:
Do NOT start coding immediately.

First inspect the existing repository, architecture, services, models, views, settings, profile system, Q&A system, AI service, resume management, platform management, navigation, and existing onboarding/setup functionality.

The current application already contains functionality for:

- Candidate Profile
- Resume Management
- Screening Q&A Knowledge Base
- AI / Universal AI Service
- Job Search Strategy / Preferences
- Platform Management
- Automation Settings
- Credentials & Security
- Backup & Restore
- Dashboard
- Jobs
- Applications
- Outreach
- Analytics
- Automation

The Setup Wizard must ORCHESTRATE these existing capabilities.

DO NOT duplicate their business logic.

--------------------------------------------------
# PRIMARY PRODUCT GOAL
--------------------------------------------------

The first time a user launches JobPilot, they should experience:

    Install JobPilot
          ↓
    Welcome
          ↓
    Understand JobPilot
          ↓
    Import Resume
          ↓
    AI extracts candidate profile
          ↓
    User reviews profile
          ↓
    Build verified Screening Q&A
          ↓
    Select / configure AI provider
          ↓
    Configure job-search preferences
          ↓
    Configure supported platforms
          ↓
    Configure automation safety
          ↓
    Readiness Check
          ↓
    Product Tour
          ↓
    JobPilot Ready
          ↓
    Dashboard

The user should feel:

"JobPilot is configured and ready for my job search."

NOT:

"I just filled out another huge settings form."

--------------------------------------------------
# NON-NEGOTIABLE ARCHITECTURE RULE
--------------------------------------------------

Use:

UI
 ↓
SetupService / SetupOrchestrator
 ↓
Existing Services
 ↓
Repositories / DB / Secrets / Storage

The Setup Wizard MUST NOT:

- directly manipulate database tables
- directly write SQL
- duplicate ProfileService logic
- duplicate QnAService logic
- duplicate ResumeService logic
- duplicate AIService logic
- duplicate PlatformService logic
- duplicate SettingsService logic
- directly access Selenium/browser automation
- directly access credentials/secrets
- create parallel configuration stores

The wizard is an ORCHESTRATOR.

Existing services remain the source of truth.

--------------------------------------------------
# PHASE 0 — FULL REPOSITORY AUDIT
--------------------------------------------------

Before implementation, inspect the actual repository.

Identify and document:

1. Existing ProfileService
2. Candidate profile model/schema
3. Existing ResumeService
4. Resume parsing/extraction functionality
5. Existing QnAService/ProfileService Q&A functionality
6. Existing UniversalAIService / AI service
7. Current provider configuration
8. SecretsService
9. SettingsService
10. PlatformService
11. Job Search Strategy service/model
12. Readiness logic if any
13. MainWindow/navigation architecture
14. Existing dialogs/wizards
15. Theme system
16. Existing first-run detection
17. Existing application settings
18. Existing database settings
19. Existing tests
20. Existing setup wizard references

Do NOT assume filenames or APIs.

Create a repository verification matrix:

| Capability | Existing implementation | Service | Model | Reusable API | Changes needed |
|------------|-------------------------|---------|-------|--------------|----------------|

If something does not exist, explicitly mark it as missing.

Do not invent APIs.

--------------------------------------------------
# PHASE 1 — DEFINE THE SETUP DOMAIN
--------------------------------------------------

Create a lightweight Setup domain/orchestration layer.

Suggested architecture:

app/services/setup/
    setup_service.py
    setup_state.py
    setup_steps.py
    setup_progress.py
    setup_persistence.py
    setup_readiness.py

Adapt names to the existing project architecture if equivalent abstractions already exist.

Create:

SetupState

with information such as:

- current_step
- completed_steps
- skipped_steps
- started_at
- updated_at
- completed_at
- is_first_run
- setup_version
- resume_id
- profile_reviewed
- qna_reviewed
- ai_configured
- preferences_configured
- platforms_configured
- safety_configured
- tour_completed

Do NOT store secrets in SetupState.

Do NOT store API keys/passwords in wizard state.

--------------------------------------------------
# PHASE 2 — SETUP PROGRESS & RESUMABILITY
--------------------------------------------------

The wizard must be resumable.

If the user:

- closes the application
- crashes
- exits midway
- skips a step
- restarts JobPilot

the wizard must know where they stopped.

Example:

    Step 4 of 8
    AI Provider

    "You stopped setup here last time."

    [Continue Setup]

Never lose setup progress.

The wizard should also support:

    Start Over

but this MUST NOT delete existing profile/resume/Q&A data.

Starting over means rerunning configuration steps, not wiping the database.

--------------------------------------------------
# PHASE 3 — WELCOME SCREEN
--------------------------------------------------

Create a polished modern welcome screen.

Title:

    Welcome to JobPilot

Subtitle:

    Your personal AI-powered job search workspace.

Explain briefly:

- Discover jobs
- Manage resumes
- Track applications
- Answer screening questions
- Automate supported application workflows
- Manage recruiter outreach
- Track interviews and follow-ups
- Analyze job-search performance

Show:

    "Let's configure your workspace in a few minutes."

Buttons:

    [Get Started]

    [I'll configure this later]

If the user skips:

- do not mark setup complete
- allow dashboard access
- show setup readiness warning
- allow reopening Setup Wizard later

--------------------------------------------------
# PHASE 4 — RESUME IMPORT
--------------------------------------------------

The preferred onboarding path should be:

    Resume → AI extraction → Profile review

Screen:

    Build your profile from your resume

Allow:

- PDF
- DOCX

Use the existing ResumeService.

Do not implement a second resume parser if one already exists.

Show:

    Drop your resume here

    [Browse Files]

After selection:

    ✓ Resume loaded
    → Reading document
    → Extracting candidate information
    → Extracting experience
    → Extracting education
    → Extracting skills
    → Preparing profile

Use the existing AI service architecture.

If AI is not configured yet, support:

    Configure AI first

OR

    Continue with manual profile setup

Do not make AI configuration a hidden dependency.

--------------------------------------------------
# PHASE 5 — AI PROFILE EXTRACTION
--------------------------------------------------

Create a structured extraction result.

Example:

CandidateProfileExtraction:

    field
    extracted_value
    source
    confidence
    requires_review

Possible sources:

    RESUME
    EXISTING_PROFILE
    USER
    AI_INFERENCE

IMPORTANT:

AI_INFERENCE MUST NEVER automatically become a verified candidate fact.

For example:

If resume says:

    RPA Developer at ABC

AI can extract:

    Current Role = RPA Developer
    Employer = ABC

But if the resume does NOT mention:

    Expected CTC
    Notice Period
    Relocation
    Gender
    Disability
    Veteran status

then value must be:

    Unknown / Not provided

NEVER invent values.

--------------------------------------------------
# PHASE 6 — PROFILE REVIEW
--------------------------------------------------

After extraction show a review screen.

Example:

    AI PROFILE EXTRACTION

    We found 27 pieces of information.

    Personal Information
    --------------------
    First Name       Mohd Ahmad Raza     ✓
    Last Name        Ansari              ✓
    Email            example@gmail.com   ✓
    Phone            +91...              ✓

    Professional
    --------------------
    Current Role     RPA Developer       ✓
    Employer         AventIQ AI          ✓
    Experience       2 years             ✓

    Needs Your Input
    --------------------
    Expected CTC     Not found           ⚠
    Notice Period    Not found           ⚠
    Relocation       Not found           ⚠

Every extracted field should indicate its source.

Example:

    Source: Resume

For inferred/AI-generated information:

    Source: AI inference
    Review required

The user must explicitly confirm before profile data becomes verified.

Buttons:

    [Back]

    [Edit]

    [Save & Continue]

Do not silently overwrite existing profile data.

If profile data already exists:

show:

    Existing value
    New extracted value

Example:

    Current Role

    Existing:
    RPA Developer

    Resume:
    RPA Developer / AI Automation Engineer

    [Keep Existing]
    [Use Resume]
    [Edit]

--------------------------------------------------
# PHASE 7 — SCREENING Q&A KNOWLEDGE BASE
--------------------------------------------------

After profile confirmation:

    Build your Screening Knowledge Base

Explain:

    JobPilot uses verified candidate information
    to answer screening questions consistently.

Use the existing QnAService / ProfileService.

Do NOT create a second Q&A database.

Create candidate facts from verified information.

IMPORTANT ARCHITECTURE:

Candidate Fact
      ↓
Question Variations
      ↓
Answer

Example:

Fact:

    years_of_experience = 2

Possible questions:

    "How many years of experience do you have?"
    "Years of experience?"
    "How long have you worked in automation?"

Answer:

    2 years

This should improve the existing Q&A engine rather than replace it.

--------------------------------------------------
# PHASE 8 — Q&A REVIEW
--------------------------------------------------

Show generated/derived Q&A entries before activation.

Example:

    Screening Knowledge

    34 candidate facts available

    Personal       8
    Experience    12
    Skills         7
    Education      3
    Availability   2
    Preferences    2

Each entry should show:

    Question
    Answer
    Source
    Verification status
    Active status

Example:

    How many years of experience do you have?

    Answer:
    2 years

    Source:
    Candidate Profile

    Status:
    ✓ Verified

AI-generated answers should NOT automatically become verified.

Use states such as:

    VERIFIED
    NEEDS_REVIEW
    AI_GENERATED
    UNKNOWN

Allow:

    [Edit]
    [Verify]
    [Disable]

Do not generate hundreds of useless Q&A entries.

Prioritize reusable candidate facts.

--------------------------------------------------
# PHASE 9 — RESUME SELECTION
--------------------------------------------------

If multiple resumes exist, allow the user to choose a default resume.

Example:

    Choose your primary resume

    ○ RPA_Developer.pdf
       RPA Developer / Automation

    ○ AI_Automation.pdf
       AI Automation Engineer

    ○ Python_Developer.pdf
       Python / Backend

Use existing ResumeService.

Do not duplicate resume state.

--------------------------------------------------
# PHASE 10 — AI PROVIDER SETUP
--------------------------------------------------

This is an important part of onboarding.

The AI service must support configurable providers.

Do NOT assume users have OpenAI.

Potential provider categories:

    Ollama
    OpenAI
    Groq
    NVIDIA
    Hugging Face
    Gemini
    DeepSeek
    OpenAI-compatible endpoint
    Custom provider

The actual list MUST come from the existing AI architecture and supported integrations.

The UI should explain:

    "Choose the AI provider you already use."

For each provider show:

    Provider
    Endpoint
    Model
    API Key
    Connection Status
    Documentation
    Setup Guide

Example:

    Ollama

    Local inference

    Endpoint:
    http://localhost:11434/v1

    Model:
    llama3.1:8b

    [Discover Models]
    [Test Connection]

    Need help?
    [How to install Ollama]
    [View documentation]

For cloud providers:

    API Key:
    ••••••••••••

    [Test Connection]

    Need an API key?
    [How to get one]

IMPORTANT:

Never display secrets in plaintext unless explicitly requested by the user.

Use existing SecretsService.

Never put secrets into:

- logs
- SetupState
- debug artifacts
- AI prompts
- screenshots
- generic presentation models

--------------------------------------------------
# PHASE 11 — AI PROVIDER HELP SYSTEM
--------------------------------------------------

Build provider-specific help.

The user should be able to click:

    How do I get this API key?

and see:

    1. Where to create an account
    2. Where API keys are generated
    3. What permissions are required
    4. Where to paste the key
    5. How to test the connection

Also include:

    Official Documentation
    Setup Guide
    Pricing / free-tier information if known
    Model recommendations

Do NOT hardcode outdated claims.

Store provider help as structured metadata so it can be updated independently.

Example conceptual structure:

ProviderHelp:

    provider
    display_name
    api_key_url
    documentation_url
    setup_url
    instructions
    supported_models
    notes

Use official provider documentation URLs where possible.

If a provider changes its UI, do not make the entire AI service depend on a scraped page.

--------------------------------------------------
# PHASE 12 — AI CONNECTION TEST
--------------------------------------------------

The test must verify actual functionality.

Do not say:

    ✓ AI Connected

just because the endpoint URL exists.

Perform a real safe test request.

Show:

    ✓ Endpoint reachable
    ✓ Authentication valid
    ✓ Model available
    ✓ Chat request successful

or:

    ✕ Endpoint unreachable
    ✕ Invalid API key
    ✕ Model unavailable
    ⚠ Provider returned an error

Show actionable troubleshooting.

Example:

    Model not found.

    Try:

    1. Discover available models
    2. Select another model
    3. Check provider documentation

Do this asynchronously.

Never block the Qt main thread.

--------------------------------------------------
# PHASE 13 — JOB SEARCH PREFERENCES
--------------------------------------------------

Configure the user's job-search strategy.

Reuse existing Job Search Strategy architecture.

Ask for:

Target roles
    RPA Developer
    Automation Engineer
    AI Automation Engineer
    Python Automation Engineer

Locations

Remote preference

Experience level

Employment type

Target industries if supported

Preferred platforms

Application methods:

    Easy Apply
    Company Career Portal
    External ATS
    Manual

Do not invent fields that the existing backend does not support.

The wizard should call the existing service.

--------------------------------------------------
# PHASE 14 — PLATFORM SETUP
--------------------------------------------------

Show platform readiness.

Example:

    LinkedIn
    ──────────────
    Session: Ready
    Search: Available
    Application: Configured

    Naukri
    ──────────────
    Session: Ready

    Indeed
    ──────────────
    Search: Available
    Application: Manual verification may be required

    Foundit
    ──────────────
    Not configured

Use actual backend state.

Do NOT show fake "Connected" statuses.

Possible states:

    READY
    CONFIGURED
    SEARCH_READY
    MANUAL_VERIFICATION
    NEEDS_CONFIGURATION
    CONNECTION_FAILED
    UNKNOWN

The wizard must not bypass platform security controls.

CAPTCHA/login challenges remain human-intervention events.

--------------------------------------------------
# PHASE 15 — AUTOMATION SAFETY
--------------------------------------------------

Before enabling automation, explain the safety model.

Show:

    Application Safety

    ☑ Require review before final submission
    ☑ Pause when CAPTCHA appears
    ☑ Pause when unknown questions are detected
    ☑ Pause when required information is missing
    ☑ Pause when application flow is unfamiliar

For the initial production implementation:

    Final submission:
    ALWAYS REQUIRE USER CONFIRMATION

Do not implement:

- CAPTCHA bypass
- stealth mode
- fingerprint spoofing
- proxy rotation for evasion
- rate-limit bypass
- security-control bypass

--------------------------------------------------
# PHASE 16 — READINESS CENTER
--------------------------------------------------

Create a reusable SetupReadinessService.

This should work both:

1. Inside Setup Wizard
2. Outside setup from Profile/Settings/Dashboard

Example:

    JOBPILOT READINESS

    ████████████████░░░░ 82%

    Candidate Profile        ✓
    Primary Resume           ✓
    Screening Q&A            ✓
    AI Provider              ✓
    Job Preferences          ✓
    LinkedIn                 ✓
    Naukri                   ⚠
    Universal Agent          ⚠

    2 items need attention

    [Fix Setup]

Readiness must be based on actual system state.

No fake percentages.

Prefer:

    READY
    NEEDS_ATTENTION
    BLOCKED
    NOT_CONFIGURED

If possible, calculate the score from actual required capabilities.

Example:

    Profile complete
    Resume available
    AI verified
    Q&A verified
    At least one platform ready

These are real readiness requirements.

--------------------------------------------------
# PHASE 17 — EXACT FIX NAVIGATION
--------------------------------------------------

When the user clicks:

    Fix Setup

take them directly to the relevant setting.

Examples:

    Missing AI provider
        → Settings → AI & Screening

    Missing resume
        → Resume Management

    Missing profile field
        → Candidate Profile → exact field

    Missing job preferences
        → Job Search Strategy

    Platform not configured
        → Platform Management

Do not simply open the dashboard and make the user search manually.

Reuse the application's existing navigation system.

--------------------------------------------------
# PHASE 18 — PRODUCT TOUR
--------------------------------------------------

The product tour happens AFTER configuration.

Do not make the tour mandatory.

Tour steps:

1. Dashboard
2. Jobs
3. Applications
4. Resume Management
5. Screening Q&A
6. Outreach
7. Analytics
8. Automation
9. Settings / Readiness

Each tooltip should explain:

    What this page does
    Why it matters
    What the user can do here

Allow:

    [Next]
    [Back]
    [Skip Tour]

Remember tour completion.

Allow:

    Settings → Restart Product Tour

Do not create a second unrelated onboarding state system.

--------------------------------------------------
# PHASE 19 — FINAL SETUP COMPLETION
--------------------------------------------------

Show a polished completion screen.

Example:

    🎉 JobPilot is Ready

    Your workspace is configured.

    Candidate Profile        ✓
    Resume                    ✓
    Screening Knowledge       ✓
    AI Engine                 ✓
    Job Preferences           ✓
    Platforms                 3 Ready

    You can now:

    🔎 Search for jobs
    📄 Manage resumes
    🤖 Run supported automation
    📬 Manage recruiter outreach
    📊 Track your applications

    [Go to Dashboard]

If some optional features are incomplete:

    JobPilot is ready for core usage.

    2 optional features still need configuration.

    [Review Setup]

Do not prevent the user from using the application merely because an optional feature is incomplete.

--------------------------------------------------
# PHASE 20 — SETTINGS → SETUP WIZARD
--------------------------------------------------

The same wizard must be available after first launch.

Settings:

    Setup & Readiness

Actions:

    [Run Setup Wizard]
    [Check Readiness]
    [Restart Product Tour]

When rerunning setup:

show:

    What would you like to update?

    ☑ Candidate Profile
    ☐ Screening Q&A
    ☐ AI Provider
    ☐ Job Preferences
    ☐ Platform Configuration
    ☐ Automation Safety

Do not reset unrelated configuration.

--------------------------------------------------
# PHASE 21 — FIRST-RUN DETECTION
--------------------------------------------------

Determine first-run status using the existing settings/configuration mechanism.

Do not introduce multiple competing flags such as:

    first_run
    onboarding_complete
    setup_complete
    wizard_complete

unless there is a clear reason.

Prefer one authoritative setup state/version.

Support future migrations:

    setup_version = 1

If a future version adds a new required setup step:

    setup_version < current_version

then show:

    "JobPilot has a new setup step."

Do not force users to repeat the entire wizard.

--------------------------------------------------
# PHASE 22 — UI/UX REQUIREMENTS
--------------------------------------------------

The existing JobPilot UI uses a dark professional desktop style with orange accent.

Maintain the existing design system.

Support:

    Dark Theme
    Light Theme

Do NOT create a completely separate visual system for the wizard.

Design principles:

- modern ATS/SaaS
- professional
- clean
- compact
- minimal unnecessary cards
- strong typography hierarchy
- clear progress
- generous spacing
- accessible controls
- keyboard navigation
- clear validation
- no giant empty panels
- no fake statistics

Wizard should feel like a premium desktop product.

--------------------------------------------------
# PHASE 23 — WIZARD LAYOUT
--------------------------------------------------

Recommended layout:

┌──────────────────────────────────────────────────────┐
│ JobPilot Setup                         Step 4 of 8   │
│                                                      │
│  ① Profile   ② Resume   ③ Q&A   ④ AI   ⑤ ...       │
├──────────────────────────────────────────────────────┤
│                                                      │
│                  CURRENT STEP                         │
│                                                      │
│              Configure your AI                       │
│                                                      │
│       Choose the provider you want to use.            │
│                                                      │
│                 [Provider UI]                         │
│                                                      │
├──────────────────────────────────────────────────────┤
│                                                      │
│ [Back]                            [Continue →]        │
└──────────────────────────────────────────────────────┘

Avoid making the wizard look like a normal Settings page.

--------------------------------------------------
# PHASE 24 — ERROR HANDLING
--------------------------------------------------

Every step must have:

Loading
Success
Warning
Error
Empty
Retry
Skip where appropriate

Example:

    AI connection failed.

    Reason:
    Connection refused at localhost:11434

    [Retry]
    [Configure Manually]
    [Continue Without AI]

Never leave the user stuck.

--------------------------------------------------
# PHASE 25 — DATA SAFETY
--------------------------------------------------

Profile and Q&A information can contain sensitive personal information.

Therefore:

- Never log full profile objects
- Never log resume contents
- Never log API keys
- Never log passwords
- Never log full Q&A answers if they may contain sensitive data
- Sanitize diagnostics
- Use SecretsService for credentials
- Do not send unnecessary profile fields to cloud AI providers
- Explain cloud AI data handling during AI setup

When extracting a resume:

Only send the minimum necessary information to the configured provider.

If local AI is available, make that clear.

--------------------------------------------------
# PHASE 26 — AI EXTRACTION UX
--------------------------------------------------

AI operations should never freeze the UI.

Use appropriate worker/thread architecture.

For PySide6:

Main Qt Thread
    ↓
Worker
    ↓
Existing AI Service
    ↓
Result DTO
    ↓
UI

Do not perform blocking API calls directly inside UI event handlers.

Do not create a new asyncio architecture if the project already has an established worker pattern.

Reuse the existing architecture.

--------------------------------------------------
# PHASE 27 — NO BUSINESS LOGIC IN WIDGETS
--------------------------------------------------

Widgets should only handle:

- presentation
- user interaction
- validation display
- emitting actions

Business operations belong in:

SetupService
ProfileService
ResumeService
QnAService
AIService
SettingsService
PlatformService
ReadinessService

--------------------------------------------------
# PHASE 28 — TESTING
--------------------------------------------------

Add tests for:

### Setup state

- first launch detected
- setup progress saved
- setup resumes
- setup completion
- setup version migration

### Resume extraction

- valid extraction
- missing fields
- malformed resume
- AI unavailable
- extraction failure

### Profile review

- existing values preserved
- user can choose existing vs extracted
- AI inference cannot become verified automatically

### Q&A

- facts converted to Q&A
- duplicates avoided
- verified vs AI-generated state preserved
- inactive Q&A preserved

### AI provider

- local provider
- OpenAI-compatible endpoint
- invalid endpoint
- invalid API key
- model unavailable
- timeout
- connection retry

### Readiness

- correct score/state
- missing profile detected
- missing resume detected
- missing AI detected
- platform state reflected correctly

### Navigation

- Fix Setup opens correct page
- exact setting/field where supported
- wizard can be launched from Settings

### Persistence

- close wizard
- reopen
- resume same step
- complete wizard
- restart application

### UI

- dark theme
- light theme
- keyboard navigation
- Back/Next
- Skip
- cancellation
- error recovery

--------------------------------------------------
# PHASE 29 — DO NOT BREAK EXISTING FEATURES
--------------------------------------------------

This feature must not break:

- Candidate Profile
- Resume Management
- Q&A
- AI configuration
- Settings
- Platform management
- Jobs
- Applications
- Outreach
- Analytics
- Automation
- LinkedIn automation
- Naukri automation
- Universal Application Agent
- existing navigation
- existing theme system

Run the full existing test suite before and after implementation.

Do not rewrite working automation engines.

--------------------------------------------------
# PHASE 30 — IMPLEMENTATION ORDER
--------------------------------------------------

Implement in this order:

Phase 0
Repository audit

Phase 1
Setup state/persistence

Phase 2
Setup service/orchestrator

Phase 3
Wizard shell/progress/navigation

Phase 4
Welcome

Phase 5
Resume import

Phase 6
AI profile extraction

Phase 7
Profile review

Phase 8
Q&A generation/review

Phase 9
Resume selection

Phase 10
AI provider configuration

Phase 11
AI provider help/documentation

Phase 12
Job preferences

Phase 13
Platform readiness/configuration

Phase 14
Automation safety

Phase 15
Readiness Center

Phase 16
Product Tour

Phase 17
Settings integration

Phase 18
Error handling/recovery

Phase 19
Testing/regression

Phase 20
Final UX polish

--------------------------------------------------
# PHASE 31 — ACCEPTANCE CRITERIA
--------------------------------------------------

The implementation is successful only if a fresh JobPilot installation can do this:

1. Launch JobPilot.

2. Automatically detect that setup has not been completed.

3. Display Welcome screen.

4. Explain what JobPilot does.

5. User uploads resume.

6. Resume is processed.

7. AI extracts profile information.

8. User reviews extracted information.

9. Missing information is clearly identified.

10. AI does not invent missing candidate facts.

11. User confirms profile.

12. Screening knowledge is generated from verified facts.

13. User reviews Q&A.

14. User selects/configures an AI provider.

15. Connection test actually verifies the provider.

16. User can access provider-specific setup documentation.

17. User configures job-search preferences.

18. User sees real platform readiness.

19. User configures automation safety.

20. Readiness Center reports actual readiness.

21. User can fix missing configuration directly.

22. Product tour explains the major JobPilot areas.

23. Setup completes.

24. Dashboard opens.

25. Restarting JobPilot does NOT show the first-run wizard again.

26. Settings can reopen the wizard.

27. Rerunning setup does not destroy existing data.

28. Closing JobPilot halfway through setup allows resuming later.

29. No credentials/secrets appear in logs.

30. Existing application functionality remains intact.

--------------------------------------------------
# IMPORTANT PRODUCT PRINCIPLES
--------------------------------------------------

1. Setup Wizard = orchestration, not duplicate business logic.

2. Resume = source for extraction, NOT permission to invent candidate facts.

3. Verified candidate facts are the foundation of the Q&A engine.

4. AI-generated information must have explicit provenance.

5. User confirmation is required before AI-derived profile data becomes verified.

6. AI provider configuration must be provider-agnostic.

7. Users must not be forced to use OpenAI.

8. Local and cloud AI providers should be treated consistently through an abstraction.

9. Provider documentation/help must be built into the UX.

10. Readiness must use real backend state.

11. Product tour is separate from configuration.

12. Setup must be resumable.

13. Setup must be rerunnable.

14. Setup must be versionable.

15. Secrets must never enter generic UI state.

16. No fake statuses or fake readiness percentages.

17. No platform security bypass functionality.

18. Existing automation must remain untouched.

19. The wizard should make JobPilot feel like a professional product, not a developer tool.

20. The ultimate goal is:

    INSTALL
      ↓
    CONFIGURE
      ↓
    VERIFY
      ↓
    LEARN
      ↓
    READY
      ↓
    JOB SEARCH

--------------------------------------------------
# FINAL INSTRUCTION
--------------------------------------------------

First perform the repository audit.

Then produce a concise implementation report containing:

1. Existing architecture discovered
2. Existing services that can be reused
3. Existing onboarding/setup functionality
4. Missing pieces
5. Proposed files
6. Proposed architecture
7. Data flow
8. Setup state model
9. AI extraction flow
10. Q&A flow
11. AI provider flow
12. Readiness model
13. Product tour architecture
14. Test plan
15. Risks
16. Any conflicts with existing JobPilot architecture

DO NOT blindly follow the proposed filenames if equivalent architecture already exists.

If the repository already contains functionality that solves part of this problem, reuse it.

After the audit, STOP and present the implementation plan for approval.

DO NOT implement code until the plan has been reviewed and approved.

# One important addition
I strongly recommend making ReadinessService a reusable system, not something that exists only inside the wizard.