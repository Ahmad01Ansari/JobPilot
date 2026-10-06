You are working on the existing JobPilot desktop application.

Your task is to redesign ONLY the Automation Control Center UI/UX into a
modern, production-grade automation command center.

The current page already has working automation functionality for:

    LinkedIn
    Naukri
    Indeed
    Foundit

The backend automation engine, workers, signals, platform drivers,
ApplicationTracker, AutomationBridge, logging, and database integration
already exist.

============================================================
CRITICAL RULE
============================================================

THIS IS A UI/UX REDESIGN.

Do NOT rewrite the automation engines.

Do NOT change:

    LinkedIn automation logic
    Naukri automation logic
    Indeed automation logic
    Foundit automation logic
    AutomationWorker behavior
    AutomationManager behavior
    AutomationBridge contracts
    ApplicationTracker
    database models
    platform APIs
    QnA engine
    qualification engine

The existing backend is the source of truth.

Build a substantially better UI around the existing functionality.

The page must remain fully functional after the redesign.

============================================================
1. FIRST — AUDIT THE EXISTING AUTOMATION PAGE
============================================================

Before modifying anything, inspect:

    current AutomationView
    AutomationWorker
    AutomationManager
    AutomationBridge
    AppState
    platform router
    platform status implementation
    logging implementation
    ApplicationTracker
    automation event/signals
    run history implementation
    existing theme.py
    existing widgets
    PageHeader
    StatusBadge
    MetricCard
    NotificationBar
    sidebar/topbar/statusbar

Also inspect:

    LinkedIn automation
    Naukri automation
    Indeed automation
    Foundit automation

Determine the actual signals/events currently available.

DO NOT invent backend events if equivalent information already exists.

If a useful UI feature requires a new event, first determine whether
the information can be derived from existing signals/state.

Only add a minimal backend adapter/event if genuinely necessary.

============================================================
2. DESIGN SYSTEM — ABSOLUTELY PRESERVE
============================================================

The Automation page MUST use the existing JobPilot design system.

Do NOT introduce a new color palette.

Do NOT invent random hex colors.

Use:

    app.ui.theme.COLORS
    ThemeManager

Dark theme:

    background       #0F1117
    surface          #161B22
    surface_alt      #1C2128
    surface_elevated #22272E
    surface_hover    #262C36
    border           #262C36
    border_light     #333A46

Primary:

    primary          #FF5F15
    primary_hover    #E04F0B
    primary_subtle   #FF5F1518
    accent           #FF7A3D

Typography:

    text             #F0F6FC
    text_muted       #8B949E
    text_dark        #6E7681

Semantic colors:

    success          #2EA043
    warning          #D29922
    danger           #F85149
    info             #388BFD
    purple           #A371F7
    cyan             #39C5CF

Light theme must automatically use the existing light tokens.

The application already defines dynamic runtime theme switching.
Use it instead of duplicating theme logic.

============================================================
3. CORE UX DIRECTION
============================================================

The new page should feel like:

    "Mission Control for Job Automation"

NOT:

    "A page containing many cards and a giant terminal."

The visual hierarchy should be:

    RUN CONTROL
        ↓
    LIVE RUN STATE
        ↓
    REAL-TIME PIPELINE
        ↓
    CURRENT JOB / CURRENT ACTION
        ↓
    ACTIVITY
        ↓
    RUN HISTORY

Prioritize information density and scannability.

Avoid:

    excessive nested cards
    huge empty areas
    oversized headers
    giant terminal boxes
    unnecessary borders
    duplicate information
    decorative gradients
    excessive orange
    fake metrics
    fake animations

Use subtle surfaces and spacing.

============================================================
4. NEW PAGE STRUCTURE
============================================================

Redesign the page into approximately this structure:

┌─────────────────────────────────────────────────────────────┐
│ AUTOMATION                                      [Run controls]│
│ Live execution across LinkedIn · Naukri · Indeed · Foundit   │
├─────────────────────────────────────────────────────────────┤
│ PLATFORM STRIP                                               │
│ ● LinkedIn Ready  ● Naukri Ready  ● Indeed Ready  ● Foundit │
├─────────────────────────────────────────────────────────────┤
│ ACTIVE RUN                                                    │
│                                                               │
│  LinkedIn       RUNNING             00:04:21       34%        │
│  ███████████████████░░░░░░░░░░░░░░                         │
│                                                               │
│  18 discovered   11 evaluated   6 qualified   2 submitted    │
│                                                               │
│                  [Pause] [Stop]                               │
├─────────────────────────────────────────────────────────────┤
│ PIPELINE                                                      │
│                                                               │
│  DISCOVERED → EVALUATING → QUALIFIED → APPLYING → SUBMITTED  │
│      18           11            6           3          2      │
├──────────────────────────────┬────────────────────────────────┤
│ CURRENT JOB                  │ LIVE ACTIVITY                  │
│                              │                                │
│ Company                      │ ● 22:51:08 Job discovered     │
│ Job title                    │ ● 22:51:09 Qualification      │
│ Platform                     │ ● 22:51:11 JD extracted       │
│ Location                     │ ● 22:51:13 QnA resolved        │
│ Status                       │ ● 22:51:15 Applying            │
│                              │ ● 22:51:18 Submitted           │
│ Current action               │                                │
│                              │ [All] [Jobs] [Applications]    │
├──────────────────────────────┴────────────────────────────────┤
│ RUN HISTORY                                                   │
│ Recent runs · duration · platform · discovered · submitted   │
└─────────────────────────────────────────────────────────────┘

This is a conceptual structure.

Adapt it to the existing application geometry and components.

============================================================
5. PAGE HEADER
============================================================

Replace the oversized current title treatment with a compact PageHeader.

Title:

    Automation

Subtitle:

    Monitor and control live job application runs across all platforms.

Right-side actions:

    [Start Automation]
    [Pause]
    [Stop]

Primary Start button:

    Safety Orange #FF5F15

Do not make all three buttons visually equal.

Hierarchy:

    Start Automation = primary
    Pause = secondary
    Stop = danger/secondary

When no run exists:

    Start Automation enabled
    Pause disabled
    Stop disabled

When running:

    Start disabled
    Pause enabled
    Stop enabled

When paused:

    Resume becomes primary
    Stop remains enabled

Use existing button tokens.

============================================================
6. PLATFORM HEALTH STRIP
============================================================

Create a compact platform status strip.

Platforms:

    LinkedIn
    Naukri
    Indeed
    Foundit

Each item should show:

    platform icon
    platform name
    status dot
    state

Example:

    ● LinkedIn  Ready
    ● Naukri   Ready
    ● Indeed   Ready
    ● Foundit  Ready

Possible states:

    READY
    RUNNING
    PAUSED
    LOGIN_REQUIRED
    CAPTCHA
    ERROR
    DISCONNECTED
    DISABLED

Use the existing semantic status colors.

Do NOT hard-code:

    "Ready"

Read actual platform state.

Clicking a platform should optionally open a compact platform detail
popover/drawer showing:

    Login state
    Last run
    Last successful run
    Current run
    Jobs processed
    Applications submitted
    Error count

============================================================
7. ACTIVE RUN HERO
============================================================

Create a single high-value "Active Run" area.

This should be the visual centerpiece.

Show:

    Platform
    Run state
    elapsed time
    current phase
    progress
    discovered
    evaluated
    qualified
    submitted
    skipped
    errors

Example:

    LinkedIn                         RUNNING
    Easy Apply · Keyword Rotation    04:21

    Processing: RPA Developer
    ABC Technologies

    ████████████████░░░░░░░░░  64%

    18 discovered   11 evaluated   6 qualified   2 submitted

Do not fabricate percentage.

If true percentage is unavailable:

    show indeterminate progress

or

    show current stage instead.

============================================================
8. CURRENT ACTION INDICATOR
============================================================

Add a highly useful live automation indicator.

Example:

    CURRENT ACTION

    ● Extracting job description

    ABC Technologies
    RPA Developer

    Stage 3 of 5
    Description → Qualification

The current action should change based on actual automation events.

Possible states:

    Initializing
    Logging in
    Searching
    Discovering jobs
    Evaluating job
    Extracting description
    Checking qualification
    Opening application
    Resolving questions
    Uploading resume
    Waiting for verification
    Submitting
    Confirming application
    Completed
    Paused
    Failed

This makes the UI feel like an actual automation control center
instead of a static dashboard.

============================================================
9. PIPELINE VISUALIZATION
============================================================

Replace the current giant pipeline card with a compact horizontal
execution pipeline.

Stages:

    DISCOVERED
       ↓
    EVALUATED
       ↓
    QUALIFIED
       ↓
    APPLYING
       ↓
    SUBMITTED

Each stage displays:

    count
    status
    subtle progress indication

Example:

    18              11             6             3             2
    DISCOVERED → EVALUATED → QUALIFIED → APPLYING → SUBMITTED

Current stage should use:

    cyan / orange emphasis

Completed stages:

    success

Inactive stages:

    muted

Failed stage:

    danger

Do not make the pipeline look like a decorative infographic.

It should remain compact and information-dense.

============================================================
10. KPI STRIP
============================================================

Replace six large cards with a compact metric rail.

Metrics:

    Discovered
    Evaluated
    Qualified
    Submitted
    Skipped
    Errors

Each metric:

    small icon
    11px uppercase label
    22–26px number
    optional delta/trend

Use MetricCard or an equivalent compact component.

Do not create huge cards.

All metrics must come from actual run state.

============================================================
11. CURRENT JOB WORKSPACE
============================================================

Create a compact "Current Job" panel.

When a job is active:

    RPA Developer
    ABC Technologies

    LinkedIn · India
    2–5 years

    Current stage:
    Qualification

    Current action:
    Checking job description

Actions:

    [View Job]
    [Open in Browser]

Only display actions that are valid for the actual platform/job.

Do NOT show:

    "Open on LinkedIn"

for a Naukri / Indeed / Foundit job.

Use the actual source platform.

When there is no active job:

    No active job

    Start an automation run to see live processing here.

Do not leave a giant empty panel.

============================================================
12. LIVE ACTIVITY STREAM
============================================================

The current terminal-style log box is too dominant.

Redesign it into a modern structured activity stream.

Instead of only:

    [22:50:38] [INFO] ...

render structured rows:

    ● 22:51:08   JOB FOUND
      RPA Developer · ABC Technologies

    ● 22:51:09   EVALUATING
      Checking title and company filters

    ● 22:51:11   JD EXTRACTED
      1,284 characters

    ● 22:51:13   QUALIFIED
      Passed experience and keyword filters

    ● 22:51:15   APPLYING
      Foundit questionnaire

    ● 22:51:18   SUBMITTED
      Application confirmed

Use semantic colors.

The raw log must still be accessible.

Add:

    [Activity] [Raw Logs]

Activity = structured modern feed.

Raw Logs = existing technical log output.

This preserves debugging capability without making the entire UI
look like a terminal.

============================================================
13. ACTIVITY FILTERS
============================================================

Add compact filters:

    All
    Jobs
    Qualification
    Applications
    System
    Errors

Also add:

    Search activity...

And a toggle:

    Auto-scroll

Default:

    ON

When the user manually scrolls upward:

    automatically pause auto-scroll

Show:

    "Jump to latest"

button.

============================================================
14. LIVE EVENT ROW DESIGN
============================================================

Each event should have:

    event icon
    timestamp
    event type
    short description
    optional platform badge

Example:

    ✓ 22:51:18  SUBMITTED
      RPA Developer · ABC Technologies        LinkedIn

Event colors:

    submitted      success
    qualified      success/info
    discovered     info
    applying       cyan
    manual         warning
    skipped        neutral
    error          danger

Do not use orange for every event.

Orange is the primary action accent, not the universal status color.

============================================================
15. MANUAL INTERVENTION CENTER
============================================================

Add a dedicated "Needs Attention" mechanism.

If automation encounters:

    CAPTCHA
    login required
    unknown questionnaire
    manual verification
    unexpected form
    resume issue

show a compact attention banner:

    ⚠ Action required

    Foundit requires manual verification.

    [Open Browser]
    [Resume]
    [Skip Job]

This should be connected to the existing MANUAL_REQUIRED state.

Do NOT bypass CAPTCHA or verification.

The user should be able to intervene without losing the run context.

============================================================
16. PAUSE / RESUME EXPERIENCE
============================================================

Make pause state visually obvious but not disruptive.

When paused:

    PAUSED

    Automation is safely paused.
    Current job: RPA Developer

    [Resume Automation]
    [Stop Run]

Preserve:

    current platform
    current job
    current stage
    counters
    elapsed time

Do not reset the dashboard when paused.

============================================================
17. STOP EXPERIENCE
============================================================

Do not immediately kill the automation on Stop.

Use a compact confirmation:

    Stop automation?

    Current run:
    LinkedIn · 18 discovered · 2 submitted

    [Continue Run] [Stop Automation]

If backend already provides graceful stop behavior,
use that mechanism.

============================================================
18. RUN HISTORY
============================================================

The current "Run Summary" area should become a compact Run History.

Display:

    Platform
    Date/time
    Duration
    Discovered
    Qualified
    Submitted
    Skipped
    Errors
    Final state

Example:

    LinkedIn     Sep 26, 22:50    00:08
    0 discovered · 0 submitted
    COMPLETED

    Foundit       Sep 26, 22:28    04:31
    18 discovered · 3 submitted
    COMPLETED

Use a compact table/list.

Allow clicking a run to open a Run Details drawer.

============================================================
19. RUN DETAILS DRAWER
============================================================

Add a modern right-side drawer when a historical run is selected.

Show:

    Run ID
    Platform
    Start time
    End time
    Duration
    Final state

    Pipeline:
        Discovered
        Evaluated
        Qualified
        Submitted
        Skipped
        Errors

    Activity timeline

    Errors / warnings

Actions:

    [View Jobs]
    [View Logs]
    [Close]

Do not navigate away from Automation page.

============================================================
20. AUTOMATION QUEUE
============================================================

If the existing backend exposes queued jobs, add a small queue indicator.

Example:

    QUEUE

    12 jobs remaining

    Next:
    Python Automation Engineer
    ABC Technologies

If no queue data exists, do not fake it.

============================================================
21. THROUGHPUT / PERFORMANCE
============================================================

Add optional live performance information.

Example:

    4.2 jobs/min
    2 applications/min
    00:04:21 elapsed

Only show these metrics if they can be calculated from real events.

Do not invent ETA or throughput.

If enough data exists, calculate:

    jobs/min
    applications/min
    average processing time

Do not show misleading precision.

For example:

    4.2 jobs/min

rather than:

    4.238742 jobs/min

============================================================
22. PLATFORM-SPECIFIC RUN HEADER
============================================================

When running a single platform:

    LinkedIn
    Easy Apply · Keyword Rotation

When running:

    Foundit
    Quick Apply · Split-Pane Search

When running All Platforms:

    Multi-Platform Automation

Show platform icon + platform name.

Do not hard-code a LinkedIn-specific interface.

============================================================
23. ALL PLATFORMS MODE
============================================================

When "All Platforms" is selected, the page should visually communicate
that multiple engines are running.

Example:

    MULTI-PLATFORM RUNNING

    LinkedIn   ● Running
    Naukri     ● Running
    Indeed     ● Idle
    Foundit    ● Running

Aggregate:

    Total discovered
    Total evaluated
    Total qualified
    Total submitted

Allow the user to inspect each platform individually.

============================================================
24. SMART PLATFORM CONTROL
============================================================

Keep the existing platform selector:

    LinkedIn
    Naukri.com
    Indeed
    Foundit
    All Platforms

But redesign it as a compact segmented control / platform switcher.

Selected platform:

    Safety Orange accent

Inactive:

    surface_alt

Hover:

    surface_hover

Do not use huge five-card tiles.

The selector should occupy minimal vertical space.

============================================================
25. REAL-TIME ANIMATION
============================================================

Add restrained motion.

Allowed:

    live status pulse
    progress transitions
    event insertion
    subtle counter animation
    drawer slide
    hover transitions

Do NOT add:

    bouncing elements
    excessive glowing
    neon effects
    continuous gradients
    flashy animations

Follow the existing motion standards:

    150ms–180ms for UI transitions
    OutCubic / InOutQuad where appropriate

Animation must communicate state, not decoration.

============================================================
26. RESPONSIVE LAYOUT
============================================================

The page must work at:

    1024x680
    1280x800
    1440x900
    1920x1080

At smaller width:

    Current Job + Activity
    should intelligently resize.

Do not allow:

    horizontal overflow
    clipped buttons
    overlapping controls
    giant fixed-width terminal panels

Use stretch factors intelligently.

============================================================
27. SCROLLING
============================================================

The page should have ONE primary vertical scroll context.

Avoid nested scrollbars everywhere.

Activity stream may have its own internal scrolling.

Run History may have internal scrolling if necessary.

Do not make every card independently scrollable.

============================================================
28. EMPTY STATES
============================================================

Design meaningful empty states.

No active run:

    Automation is idle

    Select a platform and start a run to begin processing jobs.

    [Start Automation]

No activity:

    No activity yet.

No run history:

    No automation runs yet.

No current job:

    Waiting for the first job...

Avoid giant blank rectangles.

============================================================
29. ERROR STATE
============================================================

Errors should be visible but controlled.

Example:

    ⚠ Automation stopped

    LinkedIn session expired.

    [Open Platform]
    [Retry]

Do not show stack traces directly in the main UI.

Detailed stack traces belong in Raw Logs.

============================================================
30. ACCESSIBILITY
============================================================

Every icon-only control must have:

    tooltip
    accessible label

Buttons must have:

    hover
    pressed
    focused
    disabled

Keyboard support:

    Space = Pause/Resume
    Esc = Stop confirmation / close drawer
    Ctrl+K = Global search
    Enter = activate focused action

Do not break existing global shortcuts.

============================================================
31. DATA INTEGRITY
============================================================

The UI must NEVER fabricate:

    discovered count
    submitted count
    progress
    ETA
    throughput
    current job
    platform state

All displayed values must originate from:

    AppState
    AutomationWorker
    AutomationManager
    AutomationBridge
    ApplicationTracker
    database
    existing signals

If data is unavailable:

    show "—"
    or
    hide the metric

Do not display false zeroes when the value is actually unknown.

============================================================
32. KEEP RAW LOGGING
============================================================

Do not remove the existing logging system.

The user still needs technical debugging.

Provide:

    Activity
    Raw Logs

Activity = modern structured UX.

Raw Logs = developer/debugging view.

Raw Logs should retain:

    timestamps
    INFO
    WARNING
    ERROR
    DEBUG

Add:

    copy
    clear
    search
    level filter

Use the existing LogService.

============================================================
33. THEME SUPPORT
============================================================

The page MUST support both:

    Dark
    Light

Dark:

    #0F1117
    #161B22
    #1C2128
    #22272E
    #262C36
    #FF5F15

Light:

    #F6F8FA
    #FFFFFF
    #F0F2F5
    #EAEEF2
    #D0D7DE
    #FF5F15

Do not create separate hardcoded dark/light styles scattered across
the view.

Use:

    COLORS
    ThemeManager

and refresh styles when the theme changes.

============================================================
34. TYPOGRAPHY
============================================================

Use existing JobPilot typography.

Page title:

    22px / 700

Section title:

    14–16px / 700

Body:

    13px

Metadata:

    12px

KPI:

    24–26px / 800

Table headers:

    11px / 700 / uppercase

Do not use oversized typography.

============================================================
35. STATUS BADGES
============================================================

Use the existing StatusBadge component.

Do not create custom status pill implementations.

Use existing semantic mappings:

    Success
    Warning
    Primary
    Purple
    Danger
    Info
    Neutral

Automation-specific:

    RUNNING → cyan
    READY → success
    PAUSED → warning
    MANUAL_REQUIRED → warning
    FAILED → danger
    COMPLETED → success
    IDLE → neutral

Follow existing theme tokens.

============================================================
36. ICONS
============================================================

Use JobPilot's existing vector icon system.

Do not introduce random emoji as the primary visual language.

Use the existing SidebarIconPainter/icon registry or existing icon
components where appropriate.

Automation-related visuals may use:

    automation
    lightning
    terminal
    search
    check
    warning
    play
    pause
    stop
    clock

If an icon does not exist, create it consistently using the existing
vector icon system.

============================================================
37. REMOVE VISUAL REDUNDANCY
============================================================

The current page repeats:

    Completed
    0 applied
    0 discovered
    status
    pipeline counts
    metric cards

Reduce duplication.

One piece of information should have one primary visual location.

Example:

Do NOT display:

    "0 submitted"

in 4 different places unless one is a deliberately summarized KPI.

============================================================
38. IMPORTANT VISUAL IMPROVEMENT
============================================================

The current Live Activity Stream visually dominates the page.

Fix this.

The activity feed should be important but not look like a terminal window.

Target visual hierarchy:

    1. Active Run
    2. Current Job / Current Action
    3. Pipeline
    4. Activity
    5. History

The user should be able to understand the entire automation state
within approximately 2–3 seconds.

============================================================
39. DO NOT TURN THIS INTO A DASHBOARD
============================================================

This page is an EXECUTION CONTROL CENTER.

It is not:

    Analytics
    Dashboard
    Reports

Do not add:

    pie charts
    donut charts
    decorative graphs
    large trend charts

The page should answer:

    What is running?
    What is it doing?
    Which job is being processed?
    How many jobs have been discovered?
    How many qualified?
    How many submitted?
    Is anything blocked?
    Does the user need to intervene?
    What happened recently?
    What happened in previous runs?

============================================================
40. PRESERVE EXISTING FUNCTIONALITY
============================================================

All existing controls must continue to work:

    Start Automation
    Stop
    Pause
    Resume
    Platform selection
    View Job
    Auto-scroll
    Clear logs
    Run history
    Automation events

If a current button does not have a backend implementation,
do not fake the behavior.

Disable it or clearly indicate unavailable state.

============================================================
41. IMPLEMENTATION STRATEGY
============================================================

Phase 1:
    Audit existing AutomationView and backend signals.

Phase 2:
    Extract reusable UI components if needed.

Potential components:

    AutomationHeader
    PlatformHealthStrip
    ActiveRunPanel
    PipelineStrip
    AutomationMetricRail
    CurrentJobPanel
    CurrentActionPanel
    ActivityStream
    ActivityFilterBar
    AttentionBanner
    RunHistory
    RunDetailsDrawer

Do not create unnecessary components.

Phase 3:
    Rebuild layout.

Phase 4:
    Connect all existing live signals.

Phase 5:
    Add activity/event normalization only if needed.

Phase 6:
    Add run details drawer.

Phase 7:
    Add manual intervention UX.

Phase 8:
    Add dark/light theme validation.

Phase 9:
    Regression testing.

============================================================
42. TESTING
============================================================

Test:

    Start automation
    Stop automation
    Pause automation
    Resume automation
    Platform selection
    LinkedIn state
    Naukri state
    Indeed state
    Foundit state
    All Platforms
    Job discovered event
    Job evaluated event
    Job qualified event
    Application submitted event
    Error event
    Manual required event
    Run completion
    Run history
    Run details
    Activity filters
    Auto-scroll
    Jump to latest
    Theme switching
    Window resize
    Empty state
    No active job state

Most importantly:

    Existing automation tests must continue to pass.

============================================================
43. VISUAL QA
============================================================

After implementation, inspect the page at:

    1024x680
    1280x800
    1440x900

Verify:

    no clipping
    no excessive whitespace
    no nested card explosion
    no horizontal scrollbar
    no giant terminal
    no overlapping controls
    no inconsistent orange usage
    no hardcoded colors
    no unreadable text
    no duplicated metrics

The final page should feel like:

    Linear
    Raycast
    modern ATS
    enterprise automation console

but MUST remain visually consistent with JobPilot.

Do not copy another product's UI literally.

============================================================
44. FINAL ACCEPTANCE CRITERIA
============================================================

The redesign is complete only when:

[ ] Existing automation still works.
[ ] No platform automation logic was rewritten.
[ ] LinkedIn works.
[ ] Naukri works.
[ ] Indeed works.
[ ] Foundit works.
[ ] Start/Pause/Resume/Stop work.
[ ] Real-time counters remain accurate.
[ ] Current job updates live.
[ ] Current action updates live where backend data exists.
[ ] Activity stream updates live.
[ ] Raw logs remain available.
[ ] Manual intervention state is visible.
[ ] Run history remains functional.
[ ] Run details can be inspected.
[ ] Dark theme works.
[ ] Light theme works.
[ ] Existing theme tokens are respected.
[ ] No random colors were introduced.
[ ] No fake metrics were introduced.
[ ] No excessive nested cards.
[ ] Page works at 1024x680.
[ ] Existing tests pass.

============================================================
FINAL PRINCIPLE
============================================================

Do not interpret "modern UI" as:

    more cards
    more gradients
    more colors
    bigger typography
    more empty space

Interpret "modern UI" as:

    better hierarchy
    less visual noise
    compact information density
    clear execution state
    strong live feedback
    purposeful motion
    structured activity
    excellent controls
    consistent design tokens
    fast scanning
    minimal cognitive load

The result should feel like a professional automation cockpit,
not a collection of dashboard widgets.

START BY AUDITING THE EXISTING CODE.
DO NOT MODIFY CODE UNTIL YOU UNDERSTAND THE CURRENT SIGNAL FLOW.