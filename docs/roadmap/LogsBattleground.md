# JobPilot — Automation Battle Ground / Mission Control
# Complete Logs Page Redesign

The current Logs page is functional but visually and operationally weak.

It currently behaves like:

    GUI
      ↓
    terminal output
      ↓
    huge text area
      ↓
    user manually searches logs

This is NOT the desired production experience.

Redesign the Logs page into an interactive:

    AUTOMATION BATTLE GROUND
    / MISSION CONTROL

where the user can visually understand:

    What is running?
    What jobs were discovered?
    What jobs were skipped?
    What applications succeeded?
    What failed?
    Why did something fail?
    Where does the automation currently stand?
    Does the user need to intervene?
    Which platform/keyword/job caused the event?

The raw logs must remain available as a detailed forensic/debug view.

IMPORTANT:

DO NOT rewrite the existing logging backend just for UI purposes.

First audit the existing:

    LogService
    AutomationService
    AutomationWorker
    AutomationBridge
    platform automation engines
    application events
    existing log storage
    existing log signals
    existing database records

Then build the new UI on top of the existing event/log infrastructure.

============================================================
1. CORE DESIGN PRINCIPLE
============================================================

The page should have TWO layers:

    OPERATIONAL VIEW
        ↓
    human-friendly automation battlefield

    FORENSIC VIEW
        ↓
    complete raw technical logs

The user should NOT need to read:

    [NaukriRotator] Starting search...
    [NaukriRotator] Finished...
    [NaukriRotator] Max jobs evaluated...

to understand what happened.

Instead show:

    Naukri
    ● Search rotation active

    Keyword
    "RPA Developer"

    Jobs discovered
    12

    Qualified
    8

    Applied
    6

    Skipped
    2

    Failed
    0

Then allow:

    [View Raw Logs]

============================================================
2. VISUAL CONCEPT — AUTOMATION BATTLE GROUND
============================================================

The visual language should feel like:

    Linear
    Raycast
    GitHub Actions
    modern DevOps monitoring
    ATS operations dashboard

NOT:

    terminal emulator
    old desktop log viewer
    giant bordered text box

Use JobPilot's existing theme.

Dark theme:
    subtle dark surfaces
    orange JobPilot accent
    semantic green/yellow/red/blue

Light theme must also work.

Do NOT use excessive cards.

Use a hierarchy of:

    header
    mission status
    live activity
    execution timeline
    events
    details

============================================================
3. TOP HEADER — MISSION CONTROL
============================================================

Replace:

    "System & Execution Logs"

with a stronger operational header:

    Automation Mission Control

Subtitle:

    Monitor every automation run, application, intervention and failure.

Example:

┌──────────────────────────────────────────────────────────────┐
│ Automation Mission Control                  ● LIVE           │
│ Monitor automation activity and execution health             │
│                                                              │
│ [All] [LinkedIn] [Naukri] [Indeed] [Foundit] [Universal]   │
└──────────────────────────────────────────────────────────────┘

If automation is idle:

    ○ IDLE

If running:

    ● LIVE

If waiting for user:

    ⚠ ACTION REQUIRED

If failed:

    ✕ FAILED

Do not fake these states.
Derive them from actual backend state.

============================================================
4. LIVE MISSION STATUS BAR
============================================================

Immediately below the header, show a compact operational strip.

Example:

    ENGINE
    ● Running

    PLATFORM
    Naukri

    SEARCH
    RPA Developer

    JOBS
    24 discovered

    QUALIFIED
    13

    APPLIED
    8

    SKIPPED
    5

    FAILED
    0

    INTERVENTIONS
    1

Use real events/data.

Clicking a metric should filter the activity stream.

Example:

    Click "Failed: 2"

→ activity stream automatically becomes:

    Filter: Failed

============================================================
5. LIVE AUTOMATION TIMELINE
============================================================

This should be the heart of the page.

Instead of one giant text area:

show an interactive vertical timeline.

Example:

    ● 10:42:18
      Search started
      Naukri · "RPA Developer"

    │

    ● 10:42:21
      14 jobs discovered

    │

    ✓ 10:42:23
      9 jobs qualified

    │

    ● 10:42:25
      Applying to:
      Senior RPA Developer
      ABC Technologies

    │

    ✓ 10:42:31
      Application submitted

    │

    ⚠ 10:42:38
      Manual verification required

This gives the user a visual story of the run.

============================================================
6. EVENT TYPES
============================================================

Normalize existing log/events into semantic event types where possible.

Examples:

    RUN_STARTED
    RUN_STOPPED
    SEARCH_STARTED
    SEARCH_COMPLETED
    PAGE_OPENED
    JOB_DISCOVERED
    JOB_QUALIFIED
    JOB_SKIPPED
    APPLICATION_STARTED
    APPLICATION_SUBMITTED
    APPLICATION_FAILED
    QUESTION_DETECTED
    QUESTION_ANSWERED
    RESUME_UPLOADED
    CAPTCHA_REQUIRED
    LOGIN_REQUIRED
    MANUAL_INTERVENTION
    RETRY
    RATE_LIMITED
    ERROR
    RUN_COMPLETED

Do NOT force existing log messages into fake events.

If an event cannot be reliably inferred:

    RAW_LOG

Preserve the original message.

============================================================
7. EVENT CARDS SHOULD BE INTERACTIVE
============================================================

Clicking:

    Application failed

should expand:

┌───────────────────────────────────────────────┐
│ ✕ Application Failed                          │
│                                               │
│ Senior RPA Developer                          │
│ ABC Technologies                              │
│                                               │
│ Platform                                      │
│ Naukri                                        │
│                                               │
│ Reason                                        │
│ Required question could not be answered       │
│                                               │
│ Application ID                                │
│ #1842                                         │
│                                               │
│ [Open Application] [View Question]            │
│ [View Raw Logs]                               │
└───────────────────────────────────────────────┘

The UI should connect logs back to actual JobPilot entities.

============================================================
8. JOB / APPLICATION CORRELATION
============================================================

This is extremely important.

If an event is related to:

    Job
    Application
    Company
    Platform
    Automation Run

store/display its identifier.

Example:

    Application #1842
    Job #4821
    Company: ABC Technologies

Clicking:

    [Open Job]

should navigate to JobsView and open the exact job.

Clicking:

    [Open Application]

should navigate to ApplicationsView and open the exact application.

Reuse the Universal Search / Exact Record Navigation architecture.

Do NOT create duplicate navigation logic.

============================================================
9. "WHAT IS THE BOT DOING RIGHT NOW?"
============================================================

Add a prominent current-action area.

Example:

┌───────────────────────────────────────────────┐
│ CURRENT ACTION                                │
│                                               │
│ ● Applying to job                             │
│                                               │
│ Senior RPA Developer                          │
│ ABC Technologies                              │
│                                               │
│ Step 4 / 7                                    │
│ Filling screening questions                   │
│                                               │
│ [View Application] [Stop Automation]          │
└───────────────────────────────────────────────┘

If searching:

    ● Searching Naukri

If waiting:

    ⚠ Waiting for manual verification

If idle:

    Automation is currently idle.

This should come from the current worker/state.

============================================================
10. HUMAN INTERVENTION CENTER
============================================================

This should be one of the most useful features.

When automation needs the user:

    CAPTCHA
    LOGIN
    UNKNOWN QUESTION
    MANUAL REVIEW
    APPLICATION CONFIRMATION
    UNSUPPORTED UI

show:

┌────────────────────────────────────────────────┐
│ ⚠ ACTION REQUIRED                              │
│                                                │
│ Naukri needs your attention.                   │
│                                                │
│ Job: RPA Developer                             │
│ Company: ABC Technologies                      │
│                                                │
│ Reason: Manual verification required           │
│                                                │
│ [Open Browser]       [Skip Job]                │
│ [Resume After Completion]                      │
└────────────────────────────────────────────────┘

Clicking this should open the appropriate browser/application flow.

Never attempt to bypass security challenges.

============================================================
11. RUN HISTORY
============================================================

Add a Run History section.

Example:

    Automation Runs

    Today

    ✓ Naukri · RPA Developer
      42 jobs · 12 applications
      10:42 AM · 8m 21s

    ⚠ LinkedIn · Python Automation
      31 jobs · 7 applications
      09:12 AM · 6m 04s

    ✕ Universal Application Agent
      4 jobs · 2 applications
      Yesterday · 11m 32s

Click a run:

    → load that run's timeline

This is much more useful than one endless log buffer.

Use existing persisted run information if available.

If historical runs are not currently persisted, design a compatible
RunSummary model/service only if necessary.

Do NOT invent historical data.

============================================================
12. RUN DETAIL VIEW
============================================================

Clicking a run should open:

    Run #20261005-104218

    Status
    ✓ Completed

    Platform
    Naukri

    Duration
    8m 21s

    Search Terms
    RPA Developer
    Automation Engineer

    Results
    42 discovered
    18 qualified
    12 skipped
    10 applied
    0 failed
    1 intervention

Then:

    Execution Timeline

with all events.

============================================================
13. AUTOMATION FUNNEL
============================================================

For a completed run show a compact funnel:

    Discovered        42
         ↓
    Evaluated         36
         ↓
    Qualified         18
         ↓
    Application       12
         ↓
    Submitted         10
         ↓
    Failed             0

Make each stage clickable.

Example:

    click Qualified

→ filter timeline to qualified jobs.

Do not create fake metrics.
Use actual automation events/database records.

============================================================
14. "BATTLEFIELD MAP" / EXECUTION FLOW
============================================================

Add an optional visual flow at the top of a selected run:

    SEARCH
      ↓
    DISCOVER
      ↓
    QUALIFY
      ↓
    APPLY
      ↓
    QUESTIONS
      ↓
    SUBMIT
      ↓
    VERIFY

Each node gets live status:

    ✓ completed
    ● active
    ○ pending
    ⚠ intervention
    ✕ failed

Example:

    SEARCH ✓
       ↓
    DISCOVER ✓
       ↓
    QUALIFY ✓
       ↓
    APPLY ●
       ↓
    QUESTIONS ○
       ↓
    SUBMIT ○

This should be especially useful while automation is running.

============================================================
15. PLATFORM HEALTH
============================================================

Add a compact Platform Health panel.

Example:

    PLATFORM HEALTH

    LinkedIn       ● Ready
    Naukri         ● Running
    Indeed         ⚠ Manual verification
    Foundit        ● Ready
    Glassdoor      ○ Idle
    Universal      ● Ready

Click a platform:

    → filter current activity to that platform.

Do not claim "Ready" unless backend state supports it.

============================================================
16. SMART FILTER BAR
============================================================

Replace the current basic:

    Search logs
    Level
    Auto-scroll

with:

    🔎 Search activity...

    [All]
    [Errors]
    [Warnings]
    [Applications]
    [Jobs]
    [Interventions]
    [Platforms]
    [Runs]

and:

    Platform ▼
    Run ▼
    Time ▼
    Status ▼

Example:

    Platform: Naukri
    Status: Failed
    Event: Application

Show active filter chips:

    Naukri ×
    Failed ×

============================================================
17. LIVE SEARCH
============================================================

Search should filter the operational events.

Support:

    job title
    company
    platform
    application ID
    job ID
    error message
    event type
    run ID

Examples:

    "ABC Technologies"

    "captcha"

    "RPA Developer"

    "1842"

Do not use an LLM for basic log search.

============================================================
18. RAW LOG VIEW
============================================================

The current giant text log must NOT disappear.

Move it into:

    [Raw Logs]

or:

    [Technical View]

Provide:

    Raw stream
    Timestamp
    Level
    Logger
    Message

Features:

    search
    copy
    select all
    auto-scroll
    pause stream
    clear
    export
    wrap/nowrap
    timestamps toggle

Keep it optimized for developers/debugging.

============================================================
19. RAW LOG → EVENT NAVIGATION
============================================================

Every semantic event should have:

    View Raw Log

Clicking it should:

    open raw log
    scroll to the corresponding source message
    highlight it

This creates a direct bridge between:

    human-readable event

and:

    technical evidence

============================================================
20. ERROR CENTER
============================================================

Create a dedicated error view/filter.

Example:

    ERROR CENTER

    3 unresolved issues

    ✕ Application failed
      ABC Technologies
      Naukri
      10:43:21

    ⚠ Unknown question
      XYZ Technologies
      Universal Agent
      10:44:10

    ⚠ CAPTCHA required
      Indeed
      10:45:03

Each error should support:

    [Open]
    [View Context]
    [Open Raw Logs]
    [Open Application]
    [Mark Resolved]

Do not create fake resolution state if the backend does not support it.

If persistence is required, add it through the existing service layer.

============================================================
21. FAILURE CLUSTERING
============================================================

If the same failure occurs repeatedly:

    Required question unanswered
    Required question unanswered
    Required question unanswered
    Required question unanswered

do not show four visually identical alerts.

Show:

    ⚠ Required question unanswered ×4

Expand:

    Job A
    Job B
    Job C
    Job D

This makes repeated automation failures immediately visible.

============================================================
22. RETRY / RECOVERY VISIBILITY
============================================================

Show recovery attempts:

    ⚠ Application failed

    Retry 1
    ✓ Page reloaded

    Retry 2
    ✓ Form detected

    ✓ Application submitted

This is much better than hiding retries inside raw logs.

============================================================
23. AUTOMATION "HEARTBEAT"
============================================================

When an automation is running, show a subtle live heartbeat:

    ● Automation active
      Last event: 1.2s ago

If no event arrives for an unusual amount of time:

    ⚠ No activity detected

Do NOT assume the bot is stuck immediately.

Use actual worker state/timeouts where available.

============================================================
24. SESSION / ENGINE STATUS
============================================================

The bottom status bar can become a compact system strip:

    Engine ● Ready
    Database ● Connected
    Automation ● Running
    AI ● Connected
    Browser ● Active

Clicking a status opens the relevant configuration/status page.

Again, derive from actual services.

============================================================
25. REAL-TIME UPDATE ARCHITECTURE
============================================================

Do NOT poll the database every 100ms.

Reuse existing Qt signals/event infrastructure where possible.

Preferred:

    AutomationWorker
          ↓
    AutomationBridge / LogService
          ↓
    structured event
          ↓
    Logs/Mission Control UI

For persisted historical logs:

    service/repository query

For live events:

    Qt signal/event stream

Use QThread correctly.

Never perform expensive database operations on the Qt main thread.

============================================================
26. STRUCTURED LOG EVENT MODEL
============================================================

If the current logs are plain strings, introduce a normalized internal
event DTO without breaking existing logging.

Example:

@dataclass
class AutomationEvent:
    event_id: str
    timestamp: datetime
    level: str
    event_type: str
    message: str

    platform: Optional[str]
    run_id: Optional[str]

    job_id: Optional[int]
    application_id: Optional[int]
    company_id: Optional[int]

    action: Optional[str]
    status: Optional[str]

    metadata: dict

    raw_log_reference: Optional[str]

Existing raw logging must continue to work.

Do NOT force every old log message into a fake structured event.

============================================================
27. SENSITIVE DATA PROTECTION
============================================================

This is critical.

Logs must NEVER expose:

    passwords
    API keys
    cookies
    session tokens
    authentication headers
    full credentials
    secret values

Reuse the existing LogSanitizer.

Before displaying structured events:

    sanitize()

Before exporting:

    sanitize()

Before copying:

    sanitize()

Never add a "show secrets" debugging option.

============================================================
28. EXPORT / INCIDENT REPORT
============================================================

Add:

    [Export Run]

Options:

    Summary
    Events
    Raw Logs
    Errors

Generate a sanitized diagnostic report.

Example:

    JobPilot Automation Report

    Run:
    Naukri · RPA Developer

    Duration:
    8m 21s

    Jobs:
    42

    Applications:
    12

    Successful:
    10

    Failed:
    0

    Interventions:
    1

    Errors:
    0

Then detailed event timeline.

Do not export credentials or secrets.

============================================================
29. LIVE / PAUSED STREAM CONTROL
============================================================

Provide:

    ● LIVE

button.

When clicked:

    ⏸ PAUSED

The UI stops auto-scrolling but continues collecting events.

Then:

    [Jump to Latest]

This is important when debugging.

Do NOT stop the actual automation when the user pauses the log view.

Log-view pause ≠ automation pause.

============================================================
30. "FOLLOW AUTOMATION" MODE
============================================================

Add a small toggle:

    [✓ Follow Automation]

When enabled:

    automatically scroll to the latest event.

When disabled:

    user can investigate older events without being dragged to bottom.

This is better than a simple Auto-scroll checkbox.

============================================================
31. KEYBOARD SHORTCUTS
============================================================

Support:

    Ctrl+K       Global Search
    Ctrl+F       Search logs
    Esc          Clear/close search
    Space        Pause/follow stream
    Enter        Open selected event
    ↑ ↓          Navigate events
    R            Refresh
    Ctrl+C       Copy selected log
    Ctrl+E       Export run

Do not trigger global shortcuts while the user is typing in a text field
unless intentionally designed.

Reuse existing JobPilot shortcut infrastructure.

============================================================
32. "DRILL DOWN" INTERACTION
============================================================

The user should be able to drill down:

    Run
      ↓
    Platform
      ↓
    Job
      ↓
    Application
      ↓
    Event
      ↓
    Raw Log

Example:

    Run #123
       ↓
    Naukri
       ↓
    RPA Developer
       ↓
    ABC Technologies
       ↓
    Application #1842
       ↓
    QUESTIONNAIRE
       ↓
    Unknown Question
       ↓
    Raw log

This should make debugging extremely fast.

============================================================
33. MINI LIVE JOB ACTIVITY FEED
============================================================

While automation is running, show a compact activity feed:

    10:42:18  🔎 Found job
    10:42:19  ✓ Qualified
    10:42:21  ▶ Applying
    10:42:26  ✓ Submitted
    10:42:28  🔎 Found job
    10:42:29  ⊘ Skipped
    10:42:31  ⚠ Manual review

This can become the "battlefield feed".

============================================================
34. EMPTY / IDLE STATE
============================================================

When no automation is running:

Do NOT show a huge empty black console.

Show:

    Automation Mission Control

    ○ No active automation

    Start an automation from the Automation workspace.

    Recent Runs

    [Recent run history]

    System

    Engine      ✓ Ready
    Database    ✓ Connected
    AI          ✓ Connected

This makes the page useful even when idle.

============================================================
35. NO FAKE DATA
============================================================

Absolutely no fake:

    jobs
    applications
    runs
    metrics
    platform health
    failures

Everything must come from actual JobPilot state.

If no historical run exists:

    No runs recorded yet.

============================================================
36. PERFORMANCE
============================================================

The current raw log area can become extremely large.

Do NOT keep unlimited log widgets in memory.

Use:

    bounded live buffer
    virtualization where appropriate
    lazy loading for historical runs
    pagination/chunk loading
    event aggregation

Example:

    Latest 500 live events

Older events:

    [Load older events]

Do not freeze the UI with thousands of QTextEdit lines.

============================================================
37. PAGE STRUCTURE
============================================================

Recommended final layout:

    ┌─────────────────────────────────────────────────────────┐
    │ Automation Mission Control               ● LIVE          │
    │                                                         │
    │ [All] [LinkedIn] [Naukri] [Indeed] [Foundit] [Universal]│
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │ CURRENT ACTION                                           │
    │ ● Applying to RPA Developer — ABC Technologies          │
    │                                                         │
    ├──────────────┬──────────────┬──────────────┬────────────┤
    │ Discovered   │ Qualified    │ Applied      │ Failed     │
    │ 42           │ 18           │ 12           │ 0          │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │ EXECUTION FLOW                                          │
    │ Search ✓ → Discover ✓ → Qualify ✓ → Apply ● → Submit ○ │
    │                                                         │
    ├──────────────────────────────┬──────────────────────────┤
    │                              │                          │
    │ LIVE ACTIVITY                │ DETAILS                  │
    │                              │                          │
    │ ✓ Job found                  │ Application #1842       │
    │ ✓ Qualified                 │ ABC Technologies        │
    │ ▶ Applying                  │ RPA Developer            │
    │ ⚠ Manual intervention       │ Naukri                   │
    │                              │                          │
    ├──────────────────────────────┴──────────────────────────┤
    │ FILTERS                                                 │
    │ 🔎 Search  [Level] [Event] [Platform] [Run]             │
    ├─────────────────────────────────────────────────────────┤
    │                                                         │
    │ [Timeline] [Errors] [Raw Logs] [Run History]            │
    │                                                         │
    └─────────────────────────────────────────────────────────┘

Adapt this layout to the actual available screen size.

Do NOT create a fixed layout that breaks at smaller resolutions.

============================================================
38. TABS
============================================================

Use four primary modes:

    LIVE
    RUN HISTORY
    ERRORS
    RAW LOGS

### LIVE

Current automation activity.

### RUN HISTORY

Past execution runs.

### ERRORS

Failures and interventions.

### RAW LOGS

Technical forensic stream.

This is much cleaner than putting everything on one page.

============================================================
39. INTEGRATE WITH UNIVERSAL SEARCH
============================================================

Universal Search should be able to find:

    Run ID
    Job ID
    Application ID
    error text
    company
    platform

Example:

    Ctrl+K
    "ABC Technologies"

Search result:

    Jobs
    Applications
    Automation Events

Clicking:

    Automation Event

must open Logs Mission Control and focus the exact event.

Use the existing NavigationRequest / AppNavigator architecture.

============================================================
40. AI FEATURES — OPTIONAL, NOT REQUIRED
============================================================

Do NOT make AI mandatory for basic logs.

But design an optional:

    "Explain this failure"

button.

Example:

    ✕ Application failed

    [Explain Failure]

AI receives only sanitized relevant context:

    event
    surrounding events
    sanitized error
    platform
    application state

AI response:

    "The application failed because the required question
     'Are you willing to relocate?' did not have a verified
     candidate answer."

Then:

    [Open Q&A]
    [Open Application]

Do NOT send credentials, cookies, passwords or raw secrets to AI.

Do not automatically execute AI recommendations.

============================================================
41. "WHY DID THIS JOB FAIL?"
============================================================

For a job/application event, provide a contextual explanation panel.

Example:

    Application Failed

    Job
    Senior RPA Developer

    Company
    ABC Technologies

    Platform
    Naukri

    Stage
    Questionnaire

    Reason
    Unknown question

    Recovery
    Manual intervention required

    Related Q&A
    12 possible answers

    [Open Q&A Knowledge Base]
    [Retry]
    [Skip]

Only show actions that the existing backend actually supports.

============================================================
42. DO NOT REWRITE AUTOMATION ENGINES
============================================================

This page is an observability layer.

DO NOT modify:

    LinkedIn automation
    Naukri automation
    Indeed automation
    Foundit automation
    Glassdoor automation
    Universal Application Agent

just to generate prettier logs.

Use existing signals/events where possible.

If an engine currently emits insufficient structured information:

    add a minimal event bridge

rather than rewriting its application logic.

============================================================
43. IMPLEMENTATION PHASES
============================================================

Implement in this order.

PHASE 0
Audit current logging/event architecture.

PHASE 1
Create normalized AutomationEvent DTO.

PHASE 2
Map existing logs/events into semantic event types.

PHASE 3
Build Mission Control shell.

PHASE 4
Build live event stream.

PHASE 5
Build current-action panel.

PHASE 6
Build execution metrics/funnel.

PHASE 7
Build event detail/drill-down.

PHASE 8
Build human intervention center.

PHASE 9
Build run history.

PHASE 10
Build error center.

PHASE 11
Build raw technical logs.

PHASE 12
Connect exact Job/Application navigation.

PHASE 13
Add export/diagnostic report.

PHASE 14
Add optional AI failure explanation.

PHASE 15
Performance optimization.

PHASE 16
Theme/light-mode refinement.

PHASE 17
Tests + regression.

Do not implement all UI components at once before verifying the data
pipeline.

============================================================
44. TESTING
============================================================

Add tests for:

### EVENT NORMALIZATION

Raw log → correct event type.

### LIVE STREAM

Automation event appears without UI freeze.

### CURRENT ACTION

Correct running state displayed.

### METRICS

Discovered/qualified/applied/failed derived from actual events.

### NAVIGATION

Event → exact Job.

Event → exact Application.

### INTERVENTION

CAPTCHA/manual intervention creates correct UI state.

### ERROR

Application failure appears in Error Center.

### RUN HISTORY

Completed run can be opened and timeline restored.

### RAW LOG

Event → corresponding raw log.

### SANITIZATION

Passwords/API keys/tokens/cookies never appear.

### EXPORT

Exported report contains no secrets.

### PERFORMANCE

10,000 historical events must not freeze the UI.

============================================================
45. ACCEPTANCE CRITERIA
============================================================

The redesign is complete only when:

1. The page no longer looks like a terminal.

2. User can immediately understand the current automation state.

3. User can see what the bot is doing right now.

4. User can visually follow an automation run.

5. User can filter activity by:
   platform
   event
   status
   run
   search term

6. User can click a job/application event and open the exact record.

7. User can identify failures without reading raw logs.

8. User can see why an application failed.

9. User can see when manual intervention is required.

10. User can inspect complete technical logs when needed.

11. Raw logs remain available.

12. Historical runs can be inspected if supported by backend persistence.

13. No fake data is introduced.

14. No credentials/secrets appear in logs.

15. Live automation never runs on the Qt main thread.

16. Logs UI never blocks automation.

17. Existing automation engines remain functional.

18. Light and dark themes work.

19. Existing tests continue to pass.

20. The UI is useful when automation is both:
       RUNNING
       and
       IDLE.

============================================================
46. FINAL PRODUCT VISION
============================================================

The final Logs page should feel like:

    "Mission Control for my entire job search automation"

not:

    "A terminal window with a dark theme."

The user should be able to look at the page for 3 seconds and know:

    ┌───────────────────────────────────────┐
    │ ● AUTOMATION RUNNING                 │
    │                                       │
    │ Naukri                               │
    │ RPA Developer                         │
    │                                       │
    │ 42 discovered                         │
    │ 18 qualified                          │
    │ 12 applications                       │
    │ 10 submitted                          │
    │ 0 failed                              │
    │                                       │
    │ CURRENT                               │
    │ Applying → ABC Technologies          │
    │                                       │
    │ NEXT                                 │
    │ Screening Questions                   │
    └───────────────────────────────────────┘

And when something goes wrong:

    ┌───────────────────────────────────────┐
    │ ⚠ ACTION REQUIRED                    │
    │                                       │
    │ Unknown screening question            │
    │                                       │
    │ RPA Developer                         │
    │ ABC Technologies                     │
    │                                       │
    │ [Open Application]                    │
    │ [Open Q&A]                            │
    │ [View Logs]                           │
    └───────────────────────────────────────┘

That is the target experience.

Do not just redesign the screenshot.

Build a real operational observability layer on top of the existing
JobPilot automation architecture.