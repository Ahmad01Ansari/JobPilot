You are continuing development of the existing JobPilot desktop application.

We are now redesigning:

    System Settings & Security

The current Settings UI works functionally but visually feels like an
old enterprise configuration form.

The goal is NOT to simply change colors, fonts, or add more cards.

The goal is to redesign Settings into a modern desktop control center
for:

    configuration
    automation behavior
    AI providers
    platform credentials
    recruiter email
    security
    backups
    system health

The application is PySide6 desktop software.

============================================================
0. SOURCE OF TRUTH
============================================================

Use the existing SettingFlow.md architecture as the functional source
of truth.

Existing service layer:

    SettingsService
    SecretsService
    BackupService
    UniversalAIService

Existing settings tabs:

    General
    Browser
    Automation Safeguards
    AI & Screening
    Credentials & Security
    Backup & Restore

Existing database:

    SQLite
    app_settings

Existing security mechanism:

    SecretsService
    Fernet encryption
    machine-local key:
        ~/.jobpilot/.key

Existing workers:

    EmailTestWorker
    AI connection/test workers
    backup/restore workers where applicable

Do NOT replace the existing backend architecture simply to redesign
the UI.

Do NOT create a second SettingsService.

Do NOT create a second SecretsService.

Do NOT create another credential store.

Do NOT create another backup system.

============================================================
1. FIRST STEP — AUDIT
============================================================

Before modifying anything:

Inspect:

    app/ui/views/settings_view.py

and:

    SettingsService
    SecretsService
    BackupService
    UniversalAIService

Inspect:

    Settings model/storage
    app_settings keys
    existing theme system
    notification system
    worker/QThread architecture
    DesignUI.md

Map every existing UI control to:

    service
    setting key
    default
    save operation
    reset operation

Create a short implementation audit before coding.

Do not invent settings that don't exist unless explicitly listed below
as optional enhancements.

============================================================
2. PRIMARY DESIGN DIRECTION
============================================================

The new Settings page should feel like:

    Linear Settings
    + modern desktop application preferences
    + security center
    + AI control panel
    + automation control center

NOT:

    HTML form
    old Windows settings dialog
    giant collection of cards
    dashboard

The user should understand the system state immediately.

The page should answer:

    Is my system configured correctly?
    Are my credentials configured?
    Is AI available?
    Is email connected?
    Are backups healthy?
    Are automation safeguards enabled?

without opening every tab.

============================================================
3. NEW PAGE INFORMATION ARCHITECTURE
============================================================

Use this overall structure:

┌──────────────────────────────────────────────────────────────┐
│ Settings & Security                                          │
│ Control JobPilot's automation, AI, accounts and backups.     │
│                                                              │
│                         Reset       Unsaved • Save Changes   │
├──────────────────────────────────────────────────────────────┤
│ SYSTEM STATUS                                                │
│                                                              │
│ ● Automation Ready   ● AI Connected   ● Email Connected      │
│ ● Credentials 2/2   ● Backup Healthy                        │
├───────────────┬──────────────────────────────────────────────┤
│ SETTINGS NAV  │ ACTIVE SETTINGS                              │
│               │                                              │
│ General       │ Section                                      │
│ Browser       │ Description                                  │
│ Automation    │                                              │
│ AI & Screening│ configuration                                │
│ Credentials   │                                              │
│ Backup        │                                              │
│               │                                              │
│               │                                              │
└───────────────┴──────────────────────────────────────────────┘

The left navigation should be compact.

The active settings area should be the dominant region.

Do NOT use the current horizontal row of large tab buttons.

============================================================
4. SETTINGS SIDEBAR
============================================================

Replace the current horizontal tabs:

    General
    Browser
    Automation
    AI & Screening
    Credentials
    Backup & Restore

with a vertical settings navigation.

Example:

    ⚙ General
    ◉ Browser
    🛡 Automation
    ✦ AI & Screening
    🔐 Credentials
    💾 Backup & Restore

Each item should support:

    icon
    title
    short description or status
    active indicator

Example:

    🔐 Credentials
       2 accounts configured

    ✦ AI & Screening
       Ollama · Connected

    💾 Backup & Restore
       Last backup 2 days ago

This makes the sidebar useful rather than decorative.

============================================================
5. SETTINGS STATUS INDICATORS
============================================================

Add contextual status indicators.

Examples:

    General
        Configured

    Browser
        Ready

    Automation
        Safe

    AI & Screening
        ● Connected

    Credentials
        4 configured

    Backup
        ● Healthy

Do NOT use red/yellow/green everywhere.

Use status color only where meaningful.

============================================================
6. GLOBAL HEADER
============================================================

Header:

    Settings & Security

    Configure JobPilot's automation, AI, credentials and backups.

Right side:

    Reset Section
    Save Changes

Replace:

    "Save Settings"

with:

    "Save Changes"

The Save button should become disabled when there are no changes.

When there are changes:

    ● Unsaved changes

and:

    Save Changes

When saved:

    ✓ All changes saved

============================================================
7. UNSAVED CHANGES SYSTEM
============================================================

Implement a proper dirty-state system.

When user changes a setting:

    Unsaved changes

appears.

Save:

    saving...
    saved ✓

If the user attempts to switch sections with unsaved changes:

show:

    Unsaved changes

    Save changes before leaving?

    [Save Changes]
    [Discard]
    [Cancel]

Do not silently lose configuration.

============================================================
8. RESET BEHAVIOR
============================================================

"Reset Section" should reset only the active section.

Never reset the entire Settings page accidentally.

Confirmation:

    Reset Browser settings?

    This will restore the default values for this section.

    [Reset Section]
    [Cancel]

After reset:

    Unsaved changes

Do not immediately persist the reset unless the user saves.

============================================================
9. SYSTEM STATUS HEADER
============================================================

Add a compact status area near the top.

Example:

    SYSTEM STATUS

    ● Automation Ready
    ● AI Connected
    ● Email Connected
    ● Credentials Configured
    ● Backup Healthy

Each status item should be clickable and navigate to the relevant
section.

Do not turn these into giant KPI cards.

Use compact status chips / rows.

============================================================
10. GENERAL SETTINGS REDESIGN
============================================================

Existing functionality includes:

    general.click_gap
    general.smooth_scroll
    general.run_non_stop
    general.alternate_sortby
    general.cycle_date_posted

Do not change the underlying keys.

Organize into semantic sections:

------------------------------------------------------------
Execution Timing
------------------------------------------------------------

    Action delay

    [ 1 sec ]

    Delay between automated UI interactions.

------------------------------------------------------------
Search Discovery
------------------------------------------------------------

    Smooth scrolling                         [ ON/OFF ]

    Alternate Recent / Relevant             [ ON/OFF ]

    Cycle posted-date filters                [ ON/OFF ]

------------------------------------------------------------
Continuous Execution
------------------------------------------------------------

    Run continuously                         [ ON/OFF ]

    Warning:

    Continuous execution may run until manually stopped.

Use modern toggle rows rather than old checkbox + label layouts.

============================================================
11. NUMBER INPUT DESIGN
============================================================

For:

    Action Click Delay

Use:

    −   1 sec   +

or a compact modern spin control.

Show allowed range:

    1–10 seconds

Do not make the control enormous.

============================================================
12. BROWSER SETTINGS REDESIGN
============================================================

Existing settings:

    browser.run_in_background
    browser.stealth_mode
    browser.safe_mode
    browser.disable_extensions
    browser.keep_screen_awake

Group them into:

    Browser Execution
    Session & Profiles
    System Power

Example:

------------------------------------------------------------
Browser Execution
------------------------------------------------------------

    Run in background
    Launch browser without visible window.

    [ OFF ]

------------------------------------------------------------
Session
------------------------------------------------------------

    Persistent isolated profile
    Keep platform sessions separated.

    [ ON ]

------------------------------------------------------------
System
------------------------------------------------------------

    Prevent system sleep during automation

    [ ON ]

------------------------------------------------------------

Do not expose raw Chrome command-line flags in the primary UI.

============================================================
13. BROWSER PROFILE INFORMATION
============================================================

If available from the existing architecture, show:

    LinkedIn Profile
    ● Ready

    Naukri Profile
    ● Ready

    Foundit Profile
    ○ Not configured

Do NOT expose filesystem internals by default.

Optional:

    View Profile Location

can be inside an advanced section.

============================================================
14. BROWSER ADVANCED SETTINGS
============================================================

Use progressive disclosure.

Primary screen:

    simple safe controls

Advanced:

    background/headless behavior
    extension behavior
    profile paths
    advanced browser options

Do not overwhelm normal users.

============================================================
15. AUTOMATION SAFEGUARDS REDESIGN
============================================================

Existing settings:

    automation.pause_before_submit
    automation.pause_at_failed_question
    automation.follow_companies
    automation.close_tabs

Create a clearly recognizable:

    AUTOMATION SAFETY

section.

Top status:

    Automation Safety
    ● Protected

Then:

    Pause before final submission              [ ON/OFF ]

    Pause when screening answer is unresolved  [ ON/OFF ]

    Follow companies automatically             [ ON/OFF ]

    Close external job tabs after capture     [ ON/OFF ]

Each row needs:

    title
    short explanation
    toggle

============================================================
16. SAFETY PROFILE
============================================================

Add a small summary:

    Current Safety Profile

    ✓ Manual review on uncertain questions
    ✓ Final submission review disabled/enabled
    ✓ External tabs retained
    ✓ Company follows disabled

Provide:

    Review Safety Settings

Do not create a separate safety configuration backend.

This is a presentation layer over existing settings.

============================================================
17. IMPORTANT — NO SECURITY BYPASS FEATURES
============================================================

Do not add UI controls intended to bypass:

    CAPTCHA
    security challenges
    platform access restrictions
    rate limits
    authentication controls

The Settings UI should configure legitimate browser/session behavior
and human-review safeguards.

Do not add:

    CAPTCHA solver
    proxy rotation for evasion
    fingerprint spoofing
    challenge bypass

as Settings features.

============================================================
18. AI & SCREENING REDESIGN
============================================================

This should become one of the most polished settings sections.

Current functionality:

    ai.use_AI
    ai.provider
    ai.model
    ai.api_url
    secret.llm_api_key

Design:

------------------------------------------------------------
AI ENGINE
------------------------------------------------------------

    AI Screening & QnA

    ● Ollama Connected

    Provider
    [ Ollama ▾ ]

    Model
    [ llama3.1:8b ▾ ]

    Endpoint
    [ http://localhost:11434/v1/ ]

    API Key
    [ ••••••••••• ]   Show

    [ Test Connection ]

------------------------------------------------------------

Do not expose all fields at equal visual weight.

============================================================
19. AI PROVIDER CARDS
============================================================

Instead of a generic provider dropdown alone, show provider state.

Example:

    LOCAL

    Ollama
    ● Connected

    llama3.1:8b
    Local inference

    [Use]

and:

    CLOUD

    OpenAI
    ○ Not configured

    [Configure]

Similarly:

    Gemini
    DeepSeek

Only show detailed credentials after selecting/configuring a provider.

============================================================
20. MODEL DISCOVERY
============================================================

For Ollama:

    Refresh Models

should display:

    llama3.1:8b
    4.7 GB
    Installed

    qwen...
    5.1 GB
    Installed

If refresh is running:

    Discovering models...

Never freeze the UI.

Use the existing background worker.

============================================================
21. AI CONNECTION HEALTH
============================================================

After testing:

    ✓ Connected
    Ollama
    llama3.1:8b
    184 ms

or:

    ✕ Connection failed

    Unable to reach Ollama.

    [Retry]
    [Open Endpoint]

Do not display raw stack traces.

Provide detailed technical information through:

    View Details

if needed.

============================================================
22. AI USAGE SUMMARY
============================================================

If existing service data supports it, optionally show:

    AI Provider
    Ollama

    Model
    llama3.1:8b

    Status
    Connected

    Last Test
    2 minutes ago

Do NOT invent token usage or cost metrics if the backend doesn't
already track them.

============================================================
23. AI PROVIDER FALLBACK
============================================================

If the existing architecture supports multiple providers, expose a
clear fallback configuration only if actually implemented.

Example:

    Primary
        Ollama

    Fallback
        OpenAI

But DO NOT add a fake fallback system just for UI.

Only expose capabilities that exist in UniversalAIService.

============================================================
24. ONBOARDING / PROFILE SETUP
============================================================

The existing:

    Launch Setup Wizard

should become:

    Candidate Profile Setup

Show:

    Profile completeness

    86% complete

ONLY if the backend can calculate this accurately.

Otherwise show:

    Candidate profile configured

Button:

    Open Setup Wizard

Explain:

    Re-run profile extraction and screening defaults.

============================================================
25. CREDENTIALS & SECURITY — MAJOR REDESIGN
============================================================

This is the most important redesign because the current screenshot
looks like a giant form.

Do NOT display all credentials in one giant rectangular container.

Create a Security Center.

Top:

    SECURITY CENTER

    ● Protected

    Credentials are encrypted locally and never displayed in logs.

Then:

    Platform Accounts
    Email & Outreach
    Encryption
    Security Activity

============================================================
26. PLATFORM ACCOUNT CARDS
============================================================

Instead of:

    LinkedIn Email:
    [field]

    LinkedIn Password:
    [field]

    Naukri Username:
    [field]

use account cards.

Example:

    LinkedIn
    ─────────────────────────────

    ● Credentials configured

    Account
    ah***@gmail.com

    Last verified
    2 days ago

    [Test Login]   [Edit]

Similarly:

    Naukri
    ● Credentials configured

    Account
    ah***@gmail.com

    [Test Login] [Edit]

NEVER display the full email address in the security overview if
masking is appropriate.

NEVER display the password.

============================================================
27. CREDENTIAL EDITOR
============================================================

Clicking:

    Edit

opens a focused credential editor.

Example:

    LinkedIn Credentials

    Email / Phone
    [ah***@gmail.com]

    Password
    [••••••••••••] [Show]

    [Test Credential]
    [Save]

Password reveal should be temporary.

Never write revealed credentials to logs.

============================================================
28. CREDENTIAL TESTING
============================================================

Where supported, add:

    Test Login

or:

    Verify Credentials

But this must use existing platform/service capabilities.

Do not implement a fake login test.

States:

    Testing...
    Verified
    Failed
    Needs attention

Do not expose password or session cookies.

============================================================
29. EMAIL OUTREACH REDESIGN
============================================================

The current SMTP/IMAP section is too technical.

Primary UI:

    Recruiter Email

    ● Connected

    Gmail
    ah***@gmail.com

    SMTP    ✓
    IMAP    ✓

    Last verified
    Today, 11:42 PM

    [Test Connection]
    [Edit]

This should be the first visual layer.

============================================================
30. EMAIL PROVIDER SETUP
============================================================

When Edit is clicked:

    Email Provider

    Gmail
    Outlook / Microsoft 365
    Custom SMTP / IMAP

After provider selection:

    Sender Email
    App Password / Secret

    SMTP
    Host
    Port

    IMAP
    Host
    Port

Hide advanced server configuration for preset providers.

For Gmail:

    smtp.gmail.com
    587

    imap.gmail.com
    993

can be auto-populated from existing defaults.

============================================================
31. EMAIL CONNECTION HEALTH
============================================================

Show separate statuses:

    SMTP
    ✓ Connected

    IMAP
    ✓ Connected

This is better than one generic:

    Email connected

because inbound and outbound communication can fail independently.

============================================================
32. EMAIL CONNECTION TEST
============================================================

Use existing:

    EmailTestWorker

Run asynchronously.

Show progress:

    Connecting to SMTP...
    ✓ SMTP authenticated

    Connecting to IMAP...
    ✓ IMAP authenticated

    Connection verified

Do not block the UI.

============================================================
33. ENCRYPTION STATUS
============================================================

Add a compact Security Health section:

    Credential encryption
    ✓ Enabled

    Key file
    ✓ Available

    File permissions
    ✓ Restricted

Do not expose the actual encryption key.

If the key cannot be loaded:

    ✕ Credential store unavailable

    Credential updates are disabled until the encryption key is
    restored.

Use existing fail-secure behavior.

============================================================
34. IMPORTANT SECURITY ARCHITECTURE RULE
============================================================

Do not claim that the key is truly "hardware-bound" or impossible to
copy unless the implementation actually provides that.

The existing architecture uses:

    ~/.jobpilot/.key

with restricted permissions.

Describe it accurately as:

    Machine-local encryption key

not:

    hardware-secured key

Do not modify cryptography merely for UI redesign.

============================================================
35. SECRET DISPLAY RULES
============================================================

Never show:

    plaintext password
    API key
    app password
    encryption key
    cookies
    authentication tokens

except for deliberate temporary reveal of the specific credential
field.

Use:

    ••••••••

For API keys optionally show:

    sk-••••••••1234

ONLY if the backend already supports safe masked display.

============================================================
36. SECURITY ACTIVITY
============================================================

If existing logging/audit infrastructure supports it, show:

    Credential updated
    AI connection tested
    Email connection tested
    Backup created
    Restore completed

with:

    date/time

Do NOT create a full security audit subsystem solely for UI unless
there is already an appropriate service.

If no audit data exists:

    do not fabricate it.

============================================================
37. BACKUP & RESTORE REDESIGN
============================================================

Do not make Backup & Restore another giant form.

Create:

    BACKUP CENTER

Top status:

    ● Backup Healthy

Then:

    Last backup
    Sep 28, 2026 · 10:32 PM

    Backup size
    18.4 MB

    Integrity
    ✓ Verified

Only display these values if available from BackupService.

============================================================
38. BACKUP ACTION
============================================================

Primary button:

    Create Backup

Secondary:

    Restore Backup

Additional:

    Export Profile
    Import Profile

Use clear separation because Restore is destructive.

============================================================
39. BACKUP HISTORY
============================================================

If BackupService can provide history, show:

    Backup History

    Sep 28    18.4 MB    ✓ Verified
    Sep 21    17.9 MB    ✓ Verified
    Sep 14    17.5 MB    ✓ Verified

Actions:

    Restore
    Verify
    Open Location

If history does not exist in the backend:

    do not create fake entries.

Instead show:

    Last backup

and the latest known archive.

============================================================
40. RESTORE SAFETY UX
============================================================

Restore must be visually distinct from backup.

Before restore:

    Restore JobPilot

    This will replace the current database, profile and resumes.

    A pre-restore safety snapshot will be created automatically.

    Backup:
    jobpilot_backup_20260928.zip

    [Cancel]
    [Review Backup]
    [Restore]

Do not use a generic confirmation like:

    "Are you sure?"

============================================================
41. BACKUP INTEGRITY DISPLAY
============================================================

After verification:

    ✓ Archive valid

    Database
    ✓

    Profile
    ✓

    Resumes
    ✓

    Manifest
    ✓

    SHA-256
    ✓

This maps directly to the existing BackupService architecture.

============================================================
42. PROFILE IMPORT / EXPORT
============================================================

Keep:

    Export Profile
    Import Profile

but place them under:

    Data Management

rather than making them look like backup operations.

Explain:

    Profile export contains candidate profile configuration.

    It is not a complete system backup.

============================================================
43. ADVANCED SETTINGS
============================================================

Introduce progressive disclosure.

Most users see:

    common settings

Advanced sections can contain:

    raw endpoints
    advanced browser behavior
    server host/ports
    profile paths
    diagnostic controls

Do not hide security-critical warnings.

============================================================
44. SETTINGS SEARCH
============================================================

Add:

    Search settings...

at the top.

Examples:

    "SMTP"
    "headless"
    "Ollama"
    "password"
    "follow companies"
    "backup"

Search should navigate directly to the matching setting.

If implementing this requires indexing all settings metadata, keep it
UI/service-level. Do not create a second configuration system.

============================================================
45. COMMAND PALETTE INTEGRATION
============================================================

If JobPilot already has global command/search infrastructure, allow:

    Ctrl + K

to find settings.

Examples:

    > Open AI settings
    > Open Credentials
    > Test email connection
    > Create backup

Only expose actions that are actually safe and implemented.

Do not make destructive actions executable without confirmation.

============================================================
46. CONNECTION STATUS PERSISTENCE
============================================================

When a connection test succeeds, show:

    Connected
    Last verified: 2 minutes ago

Do not claim "Connected" merely because credentials exist.

Differentiate:

    Configured
    Verified
    Failed
    Unknown

This distinction is important.

============================================================
47. SETTINGS STATUS MODEL
============================================================

Use presentation states such as:

    CONFIGURED
    VERIFIED
    NEEDS_ATTENTION
    NOT_CONFIGURED
    UNKNOWN

Do not conflate:

    credentials exist

with:

    credentials work.

============================================================
48. NOTIFICATION SYSTEM
============================================================

Reuse the existing NotificationBar / notification system.

Examples:

    ✓ Settings saved

    ✓ AI connection verified

    ✓ Email connection verified

    ⚠ Some settings require attention

    ✕ Backup restore failed

Do not create another toast/notification framework.

============================================================
49. ERROR UX
============================================================

Never show raw Python errors as the primary message.

Bad:

    ConnectionError: [Errno 111] Connection refused

Good:

    Could not connect to Ollama.

    Endpoint:
    localhost:11434

    Check that Ollama is running.

    [Retry]
    [Open AI Settings]

Advanced details can be available through:

    View technical details

============================================================
50. LOADING STATES
============================================================

Every asynchronous action must have a clear state.

Examples:

    Test AI
        Testing...

    Refresh Models
        Discovering models...

    Test Email
        Testing SMTP...
        Testing IMAP...

    Create Backup
        Preparing database...
        Creating archive...
        Verifying integrity...

Never freeze the main Qt thread.

============================================================
51. THEME SYSTEM
============================================================

Use the existing DesignUI.md design tokens.

Do NOT scatter hardcoded colors across widgets.

Use semantic tokens:

    surface
    surface_elevated
    surface_hover
    border
    text_primary
    text_secondary
    text_muted
    accent
    success
    warning
    error
    info

Dark mode:

    deep neutral background
    subtle elevated surfaces
    restrained borders
    orange accent

Light mode:

    white/off-white surfaces
    dark typography
    subtle borders
    same orange accent

Do not simply invert dark colors.

============================================================
52. VISUAL DESIGN RULE
============================================================

Do NOT solve the current UI problem by adding more cards.

Avoid:

    giant cards
    nested cards
    excessive borders
    giant empty containers
    huge form controls

Use:

    section headers
    spacing
    dividers
    compact rows
    status indicators
    typography

Settings should feel calm and professional.

============================================================
53. SETTINGS ROW DESIGN
============================================================

Standard setting row:

    TITLE
    Short explanation

                                      [Control]

Example:

    Pause before final submission
    Review the application before clicking Submit.

                                      [ OFF ]

For destructive/important options:

    ⚠ Run continuously
    Automation continues until manually stopped.

                                      [ OFF ]

This is much better than:

    Label: [checkbox]

============================================================
54. SECTION DESIGN
============================================================

Each section should follow:

    Section title
    Section description

    setting row
    setting row
    setting row

Do not put every setting inside a giant bordered rectangle.

Use subtle separators between rows.

============================================================
55. MOBILE-STYLE TOGGLE DESIGN IS NOT REQUIRED
============================================================

This is a desktop application.

Do not blindly copy mobile settings UI.

Controls should take advantage of desktop width:

    title + description on left
    control on right

For advanced configurations:

    two-column layout

============================================================
56. CREDENTIALS SHOULD USE PROGRESSIVE DISCLOSURE
============================================================

The current screenshot shows:

    LinkedIn username
    LinkedIn password
    Naukri username
    Naukri password
    email
    app password
    SMTP
    IMAP

all at once.

Do not do this.

First show:

    LinkedIn       ● Configured
    Naukri         ● Configured
    Recruiter Email ● Connected

Then click:

    Edit

to open the specific credential configuration.

This dramatically improves readability and reduces accidental
exposure of sensitive information.

============================================================
57. "SHOW PASSWORD" UX
============================================================

Do not keep:

    Show

permanently visible next to every credential.

Use an eye icon:

    👁

with tooltip:

    Show password temporarily

Automatically re-mask after a short inactivity period if technically
appropriate.

Never log the value.

============================================================
58. CREDENTIAL COPY ACTIONS
============================================================

Do NOT add convenient:

    Copy Password

or:

    Copy API Key

buttons by default.

Avoid increasing secret exposure through clipboard.

============================================================
59. SAVE MODEL
============================================================

Support:

    Save Changes

globally.

But preserve section-level atomic updates.

Do not make changing one AI field accidentally overwrite credentials.

Each category should persist only its own changed settings.

============================================================
60. AUTO-SAVE
============================================================

Do NOT automatically persist every keystroke for sensitive settings.

Especially:

    password
    API key
    SMTP credential

Use:

    edit
    validate
    save

For normal non-sensitive settings, autosave may be considered only if
the existing SettingsService architecture safely supports it.

Default behavior:

    explicit Save Changes.

============================================================
61. DANGEROUS ACTIONS
============================================================

Actions requiring confirmation:

    Reset settings
    Restore backup
    Delete credential
    Remove provider configuration

Use explicit confirmation dialogs.

Never require confirmation for:

    changing a checkbox
    changing a model
    testing connection

============================================================
62. SETTINGS RESET
============================================================

Add:

    Reset Section

and optionally:

    Reset All Settings

ONLY if existing backend supports it safely.

If implementing Reset All:

    clearly warn that credentials may also be affected.

Never make this the default action.

============================================================
63. DATA PRIVACY
============================================================

Add a small:

    Privacy & Data

section if supported by existing architecture.

Show:

    Credentials stored encrypted locally
    AI provider used for screening
    Local Ollama vs cloud provider

Do not make unsupported claims about provider data retention.

Only describe what JobPilot actually knows/configures.

============================================================
64. AI LOCAL VS CLOUD INDICATOR
============================================================

When provider is Ollama:

    ● Local
    Requests remain on this machine unless another service is
    configured.

When cloud provider:

    ● Cloud

    Requests may be sent to the configured provider.

Do not claim specific provider retention policies unless documented
by the provider.

============================================================
65. SYSTEM HEALTH SUMMARY
============================================================

Add a compact Settings landing summary if practical:

    SYSTEM HEALTH

    Automation
    ✓ Ready

    AI
    ✓ Ollama connected

    Email
    ✓ SMTP / IMAP connected

    Credentials
    ✓ 2 platforms configured

    Backup
    ✓ Last backup verified

This should not duplicate Dashboard analytics.

It is specifically:

    configuration health.

============================================================
66. NO FAKE DATA
============================================================

Critical.

Do not hard-code:

    Last verified
    backup size
    connection latency
    account names
    model sizes
    connection status

All values must come from the real backend.

If information is unavailable:

    Not checked
    Unknown
    Not configured

Do not invent values.

============================================================
67. DO NOT MODIFY AUTOMATION ENGINES
============================================================

This is a Settings redesign.

Do NOT change:

    LinkedIn automation
    Naukri automation
    Indeed automation
    Foundit automation
    Outreach engine

unless a settings integration is genuinely broken.

The Settings UI must consume the existing configuration.

============================================================
68. DO NOT CHANGE DATABASE KEYS
============================================================

Preserve all existing keys.

General:

    general.click_gap
    general.smooth_scroll
    general.run_non_stop
    general.alternate_sortby
    general.cycle_date_posted

Browser:

    browser.run_in_background
    browser.stealth_mode
    browser.safe_mode
    browser.disable_extensions
    browser.keep_screen_awake

Automation:

    automation.pause_before_submit
    automation.pause_at_failed_question
    automation.follow_companies
    automation.close_tabs

AI:

    ai.use_AI
    ai.provider
    ai.model
    ai.api_url

Secrets:

    secret.llm_api_key
    secret.linkedin_username
    secret.linkedin_password
    secret.naukri_username
    secret.naukri_password

Email:

    email.default.provider
    email.default.user
    email.default.password
    email.default.smtp_host
    email.default.smtp_port
    email.default.imap_host
    email.default.imap_port

Do not rename existing keys.

============================================================
69. ARCHITECTURE
============================================================

Maintain:

    UI
      ↓
    Service
      ↓
    Repository
      ↓
    DB

Never:

    UI
      ↓
    SQL

Never allow individual UI components to directly manipulate the
database.

============================================================
70. COMPONENT ARCHITECTURE
============================================================

Refactor settings_view.py only where useful.

Suggested:

    app/ui/views/settings/
        settings_view.py
        settings_sidebar.py
        settings_header.py
        system_status.py

        sections/
            general_section.py
            browser_section.py
            automation_section.py
            ai_section.py
            credentials_section.py
            backup_section.py

        components/
            setting_row.py
            status_indicator.py
            credential_card.py
            connection_status.py
            section_header.py
            danger_action.py

Do not create dozens of tiny components.

============================================================
71. PRESENTATION MODEL
============================================================

If necessary, create a lightweight SettingsViewModel /
SettingsPresentationModel.

It can aggregate:

    current values
    dirty state
    connection state
    verification state
    display labels

Do not create a second configuration database.

============================================================
72. TESTING
============================================================

Add tests for:

    section navigation
    dirty state
    save
    discard
    reset section
    unsaved changes warning
    password masking
    password reveal
    AI connection
    model refresh
    SMTP connection
    IMAP connection
    credential save
    backup creation
    backup verification
    restore confirmation
    light theme
    dark theme

============================================================
73. SECURITY TESTS
============================================================

Verify:

    credentials never appear in logs
    API keys never appear in logs
    passwords remain masked
    encryption failure prevents secret persistence
    invalid encryption key fails safely
    clipboard is not used for secrets
    backup restore does not bypass safety checks

Do not weaken existing SecretsService behavior.

============================================================
74. ASYNC TESTS
============================================================

Verify the UI remains responsive during:

    AI test
    model discovery
    SMTP test
    IMAP test
    backup
    restore

All network/file-heavy work must remain off the Qt main thread.

============================================================
75. VISUAL ACCEPTANCE CRITERIA
============================================================

The redesigned page must NOT look like:

    ❌ old enterprise settings form
    ❌ giant form with 20 input fields
    ❌ collection of bordered cards
    ❌ dashboard
    ❌ mobile settings page
    ❌ browser webpage embedded in desktop

It SHOULD feel like:

    ✓ modern desktop application
    ✓ professional ATS product
    ✓ security control center
    ✓ clean
    ✓ calm
    ✓ information-dense
    ✓ easy to scan
    ✓ safe around credentials
    ✓ technically powerful without exposing complexity

============================================================
76. FINAL SETTINGS STRUCTURE
============================================================

Recommended final navigation:

    SETTINGS

    Overview
    ─────────────────
    General
    Browser
    Automation
    AI & Screening
    Credentials
    Backup & Restore

The optional Overview should show:

    System Health
    AI
    Email
    Credentials
    Backup

If implementing Overview creates too much duplication,
keep the status summary at the top of the first section instead.

============================================================
77. IMPLEMENTATION PHASES
============================================================

PHASE 1

Audit existing SettingsView and services.

Deliver:

    settings → service mapping
    existing UI controls
    existing workers
    existing tests

Do not modify anything yet.

PHASE 2

Build new Settings shell:

    header
    sidebar
    active section
    dirty state
    save/reset

PHASE 3

Implement:

    General
    Browser
    Automation

using modern setting rows.

PHASE 4

Implement:

    AI & Screening

with provider/model/connection states.

PHASE 5

Implement:

    Credentials & Security

with account cards
credential editor
security health
email connection UX.

PHASE 6

Implement:

    Backup & Restore

with verification and safe restore UX.

PHASE 7

Implement:

    search
    status summary
    advanced sections
    keyboard navigation

PHASE 8

Dark/light theme refinement.

PHASE 9

Testing and regression.

============================================================
78. FINAL REGRESSION GATE
============================================================

Before declaring complete:

    Existing Settings tests pass.

    Existing SecretsService tests pass.

    Existing BackupService tests pass.

    Existing AI tests pass.

    Existing Outreach tests pass.

    Existing LinkedIn automation remains unchanged.

    Existing Naukri automation remains unchanged.

    Existing Indeed automation remains unchanged.

    Existing Foundit automation remains unchanged.

No credentials are exposed in logs.

No secrets are stored in plaintext.

No UI freezes during connection tests or backups.

============================================================
79. FINAL DELIVERABLE
============================================================

Report:

    1. Files changed
    2. Services reused
    3. New UI components
    4. Settings architecture changes
    5. Security improvements
    6. AI UX improvements
    7. Credential UX improvements
    8. Backup UX improvements
    9. Tests added
    10. Existing tests passed
    11. Dark/light theme verification
    12. Known limitations

Also provide screenshots of:

    General
    Browser
    Automation
    AI & Screening
    Credentials & Security
    Backup & Restore

============================================================
FINAL PRODUCT PRINCIPLE
============================================================

JobPilot Settings should not feel like:

    "Here are 30 fields you need to configure."

It should feel like:

    "Here is the current health of my JobPilot system,
     and here is exactly what I can configure."

The complexity belongs in the architecture.

The UI should make that complexity understandable.