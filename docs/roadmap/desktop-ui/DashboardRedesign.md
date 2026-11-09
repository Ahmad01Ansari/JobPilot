# JOBPILOT — DASHBOARD REDESIGN + TODAY'S JOB HUNT
# MASTER IMPLEMENTATION PROMPT

You are working on the JobPilot local-first PySide6 desktop application.

Your task is to redesign the existing Dashboard into a modern, production-grade
"Job Search Command Center" and integrate "Today's Job Hunt" directly into the
Dashboard experience.

IMPORTANT:
Do NOT treat this as a cosmetic UI redesign.

This is an operational redesign of the user's daily job-search workflow.

The new Dashboard must answer:

    "What should I do today to maximize my chances of getting my next job?"

It must use REAL JobPilot data and existing services.

============================================================
1. REQUIRED INPUTS — STUDY BEFORE CODING
============================================================

Before changing code, inspect:

1. The attached JobPilot feature/page specification.
2. The current Dashboard implementation.
3. Existing Dashboard services/repositories.
4. JobRepository / JobService.
5. Qualification Engine / QualificationService.
6. ApplicationService.
7. RecruitmentService.
8. FollowUpService.
9. InterviewService.
10. OutreachService.
11. ProfileService.
12. ResumeService.
13. QnAService.
14. AutomationManager / AutomationWorker.
15. LogService.
16. Platform/session services.
17. Existing JobsView and JobsDetailPanel.
18. Existing theme system.
19. Existing navigation system.
20. Existing tests.

The attached specification is a reference blueprint, not permission to blindly
implement every item inside it.

The current repository is authoritative for actual architecture.

DO NOT invent services, models, database fields, APIs, or fake metrics merely
because they appear in the specification.

============================================================
2. CORE ARCHITECTURE RULE
============================================================

Maintain:

    PySide6 UI
        ↓
    Presentation/ViewModel layer where appropriate
        ↓
    Service layer
        ↓
    Repository layer
        ↓
    SQLAlchemy
        ↓
    SQLite/PostgreSQL

The Dashboard must NOT:

- query SQLAlchemy directly
- query SQLite directly
- access ORM models directly for business logic
- run Selenium/Playwright/Stagehand
- contain qualification algorithms
- contain application-transition logic
- contain outreach logic
- contain AI decision logic
- duplicate existing service logic

The Dashboard is an orchestration/presentation layer.

Reuse existing services.

Do NOT create:

    DashboardService2
    JobQualificationService2
    ApplicationService2
    OutreachService2

If an existing service is missing a required read/query method, extend the
existing service cleanly instead of bypassing the architecture.

============================================================
3. VERY IMPORTANT — QUALIFICATION ENGINE DEPENDENCY
============================================================

Today's Job Hunt depends heavily on the Qualification Engine.

The Dashboard must consume qualification results.

DO NOT implement a second qualification algorithm inside Dashboard.

Expected flow:

    JobRepository
          ↓
    QualificationService
          ↓
    persisted qualification result
          ↓
    Dashboard Today's Job Hunt
          ↓
    user action

Use:

- qualification score
- qualification decision
- matched skills
- missing skills
- hard-filter failures
- explanation/reasons
- evaluation status

where those fields actually exist.

If Qualification Engine is not fully implemented or tested yet:

STOP Dashboard implementation at the integration boundary and report the
missing dependency.

DO NOT fake qualification scores.

DO NOT generate random match percentages.

DO NOT hard-code "high match" jobs.

============================================================
4. PRODUCT PRINCIPLE
============================================================

The Dashboard is NOT primarily:

    analytics dashboard
    system log viewer
    bot launcher
    database statistics page

It is:

    JOB SEARCH COMMAND CENTER

The user's main loop should become:

    Discover
       ↓
    Qualify
       ↓
    Review best opportunities
       ↓
    Apply / manually review
       ↓
    Follow up
       ↓
    Respond to recruiters
       ↓
    Attend interviews
       ↓
    Improve strategy

The Dashboard should surface the next useful action in this loop.

============================================================
5. TODAY'S JOB HUNT — PRIMARY FEATURE
============================================================

Integrate "Today's Job Hunt" directly into Dashboard.

Do NOT create another top-level navigation page unless the existing navigation
architecture absolutely requires it.

Dashboard should become the home of Today's Job Hunt.

Create a clear primary section:

    TODAY'S JOB HUNT

This section should answer:

    "What are the best actions available to me right now?"

============================================================
6. TODAY'S JOB HUNT DATA MODEL
============================================================

Do not create a fake temporary data model.

Build a presentation-level aggregation from existing domains.

Possible inputs:

Jobs:
- discovered jobs
- qualification result
- application status
- platform
- application method
- discovered date

Applications:
- current recruitment status
- automation status
- submitted date
- latest activity

Outreach:
- conversations requiring action
- recruiter replies
- drafts
- follow-ups

FollowUps:
- overdue
- due today
- upcoming

Interviews:
- today
- upcoming
- preparation required

Profile/Resume/QnA:
- readiness
- missing critical information

Automation:
- current state
- platform state
- active run
- paused/manual intervention state

Use only data that actually exists.

============================================================
7. TODAY'S JOB HUNT — PRIORITY ORDER
============================================================

The system should prioritize work approximately in this order:

1. OVERDUE / URGENT
2. INTERVIEW TODAY
3. RECRUITER REPLY / INBOUND MESSAGE REQUIRING RESPONSE
4. APPLICATION/FOLLOW-UP DUE TODAY
5. HIGH-QUALITY QUALIFIED JOBS NOT YET APPLIED
6. APPLICATIONS REQUIRING MANUAL REVIEW
7. UPCOMING INTERVIEWS
8. OTHER JOB SEARCH ACTIVITIES

This is prioritization for presentation.

Do not silently perform consequential actions.

============================================================
8. PRIMARY "TODAY" WORK QUEUE
============================================================

Create a prominent action-oriented work queue.

Example:

    TODAY'S JOB HUNT

    ┌─────────────────────────────────────────────┐
    │ 12 actions need your attention              │
    │                                             │
    │ 🔴 2 overdue follow-ups                    │
    │ 🟠 1 recruiter reply                       │
    │ 🟣 1 interview tomorrow                    │
    │ 🟢 8 strong-match jobs to review           │
    └─────────────────────────────────────────────┘

Do NOT necessarily use exactly these numbers.

All values must be real.

Each row/card must provide:

- action type
- company
- job title/context
- urgency
- reason
- recommended next action
- direct navigation/action button

Examples:

    Backend Developer
    Gamma Labs
    Match 87%
    Strong match — 8/10 required skills
    [Review Job]

    Recruiter replied
    Acme Corp
    "Can you share your availability..."
    [Open Conversation]

    Follow-up due
    XYZ Technologies
    Application submitted 5 days ago
    [Compose Follow-up]

    Interview tomorrow
    ABC Ltd
    Technical Round — 11:00 AM
    [Prepare]

============================================================
9. TOP JOB OPPORTUNITIES
============================================================

Create a "Top Opportunities" section.

Default behavior:

    unapplied + active + qualified jobs
    sorted by qualification score / decision / freshness

Do NOT blindly use:

    score >= 70

unless the qualification engine defines that threshold.

Use the Qualification Engine's decision model.

Recommended display:

    TOP OPPORTUNITIES

    Job Title
    Company
    Location
    Platform
    Match
    Method
    Status
    Action

Example:

    Senior Python Developer
    ABC Technologies
    Bangalore / Remote
    LinkedIn
    91% Strong Match
    Easy Apply
    Not Applied
    [Review]

    AI Engineer
    XYZ Labs
    Hyderabad
    Company Portal
    84% Good Match
    External
    Not Applied
    [Review]

============================================================
10. IMPORTANT — NO BLIND "APPLY NOW"
============================================================

Do not make Dashboard automatically submit applications simply because a job
has a high qualification score.

Qualification means:

    "This job looks relevant."

It does NOT mean:

    "Submit my application automatically."

Actions should respect:

- application method
- platform
- automation availability
- login state
- qualification
- user safety settings
- manual-review requirements

Possible actions:

    Review Job
    Open Job
    Apply
    Start Application
    Manual Review
    Open Company Portal

The exact action must come from actual job/application capabilities.

============================================================
11. TODAY'S PROGRESS
============================================================

Create a compact daily progress section.

Example:

    TODAY

    Jobs discovered       42
    Qualified             18
    Reviewed               9
    Applications           5
    Outreach                3
    Follow-ups              2

These values must be calculated from real data.

Do not use fabricated values.

Where a metric is unavailable, show:

    —

or an honest empty state.

Do not display fake 0/50 quotas unless such quota actually exists.

============================================================
12. PIPELINE SUMMARY
============================================================

Keep a compact recruitment pipeline summary.

Do NOT let the pipeline funnel dominate the screen.

Possible:

    Applications
    ─────────────────────────────
    Submitted        234
    Under Review       2
    Interview         51
    Offer              2
    Rejected           4

Include a:

    View Pipeline →

action.

Clicking a stage should navigate to ApplicationsView with the correct filter.

Do not duplicate the complete Analytics page here.

============================================================
13. UPCOMING / DEADLINES
============================================================

Create a compact "Upcoming" section.

Include:

- interviews
- follow-ups
- application deadlines if available
- scheduled outreach
- other real time-sensitive events

Prioritize:

    Today
    Tomorrow
    Next 7 days

Example:

    UPCOMING

    Today
    3:00 PM — Recruiter Follow-up
    [Open]

    Tomorrow
    11:00 AM — Technical Interview
    [Prepare]

    Oct 8
    Follow-up — ABC Corp
    [Open]

Do not show a huge empty panel.

If empty:

    No upcoming actions.
    Your schedule is clear.

Provide useful secondary action:

    View Follow-ups
    View Interviews

============================================================
14. RECRUITER / OUTREACH ATTENTION
============================================================

Add a compact "Communication" section.

Show only conversations that need attention.

Priority:

1. unread recruiter reply
2. response requiring user action
3. follow-up due
4. draft waiting
5. waiting-for-recruiter state

Do not show every email.

The purpose is:

    "Who needs me?"

not:

    "Show me my entire inbox."

Actions:

    Open Conversation
    Reply
    Follow Up
    View Application

Use existing OutreachService.

Do not implement email discovery/scraping here.

============================================================
15. INTERVIEW CARD
============================================================

If an interview exists, show the nearest upcoming interview.

Display:

- company
- role
- round
- date/time
- timezone
- meeting link if available
- interviewer if available
- preparation status if available

Actions:

    Join / Open Meeting
    Prepare
    View Interview

If no interview exists:

    No upcoming interviews

with:

    View Interviews →

Do not create fake interview information.

============================================================
16. PROFILE / APPLICATION READINESS
============================================================

Create a small readiness indicator.

Possible dimensions:

- Profile complete
- Resume available
- Default resume configured
- QnA readiness
- Platform readiness

Do not invent a single "94%" score unless a real readiness calculation exists.

Prefer:

    PROFILE READY
    Resume ✓
    Profile ✓
    QnA 82%
    Platforms 3/5 ready

If readiness scoring does not exist:

show the actual underlying statuses rather than inventing a percentage.

Actions:

    Complete Profile
    Manage Resume
    Review QnA
    Platforms

============================================================
17. AUTOMATION STATUS — SECONDARY
============================================================

Automation should remain visible, but it should NOT dominate the Dashboard.

Replace the current large Platform Automation Launch Deck with a compact
"Automation" status strip.

Example:

    AUTOMATION

    LinkedIn   Ready
    Naukri     Ready
    Indeed     Manual / Restricted
    Glassdoor  Ready
    Foundit    Not configured

And:

    Idle

Actions:

    Open Mission Control
    Run Search
    Resume

Do not make "Launch All" the primary Dashboard CTA.

Do not introduce blind sequential multi-platform execution.

============================================================
18. SAFETY / ANTI-BOT REQUIREMENTS
============================================================

Do NOT implement or expose:

- CAPTCHA solving
- CAPTCHA bypass
- stealth fingerprint spoofing
- browser fingerprint manipulation
- proxy rotation for evasion
- rate-limit bypass
- security bypass
- "humanizer" designed to evade detection

If a platform requires human verification:

    MANUAL VERIFICATION REQUIRED

The Dashboard should expose this as a state requiring user intervention.

============================================================
19. RECENT ACTIVITY
============================================================

Keep Recent Activity, but move it below the operational content.

Show concise events:

    19:48  Job discovered
    19:47  Recruiter reply received
    19:42  Application submitted
    19:30  12 jobs qualified

Use LogService / existing activity source.

Do not expose raw engineering logs here.

Provide:

    View Activity →

which opens Logs/System Activity.

============================================================
20. SYSTEM LOGS ARE NOT DASHBOARD CONTENT
============================================================

The existing "System Activity Log" popup should remain available through the
Logs/Diagnostics area.

Do not make the Dashboard a debugging console.

Dashboard events should be human-readable.

Examples:

GOOD:

    "5 new jobs qualified"

BAD:

    "QualificationWorker.process_batch() completed successfully"

============================================================
21. HEADER REDESIGN
============================================================

Redesign the current top header.

Keep:

- JobPilot / Dashboard identity
- global search Ctrl+K
- platform status
- user/profile indicator

Remove unnecessary duplication.

Recommended:

    Dashboard

    [Search jobs, companies, contacts... Ctrl+K]

    LinkedIn ●
    Naukri ●
    Indeed ●
    Profile

Avoid filling the header with technical information.

============================================================
22. PRIMARY ACTIONS
============================================================

Dashboard primary actions should be limited.

Recommended:

    + Add Job
    Search Jobs
    Review Today's Hunt

Automation should be secondary:

    Automation →

Do NOT have five competing orange CTA buttons.

There should be one clear primary action at a time.

============================================================
23. VISUAL DESIGN
============================================================

Use the existing JobPilot design system where possible.

Target:

    modern ATS / SaaS / productivity application

NOT:

    cyber-security dashboard
    trading terminal
    gaming UI
    overly colorful admin dashboard

Use:

- strong typography hierarchy
- subtle borders
- restrained surfaces
- compact status chips
- consistent spacing
- clean tables
- subtle separators
- orange only as accent/action color
- semantic status colors
- dark theme
- light theme
- responsive split layouts

Do not turn every section into a giant bordered card.

"Modern" does NOT mean:

    more cards
    more gradients
    more icons
    more colors
    more KPI boxes

Prefer hierarchy and whitespace.

============================================================
24. DARK THEME
============================================================

Preserve the existing dark visual direction but improve hierarchy.

Do not blindly copy:

    #0F1117 + orange everywhere

from the old specification.

Use the existing semantic theme tokens.

Orange should mean:

    primary action / attention

not:

    every border
    every icon
    every badge

============================================================
25. LIGHT THEME
============================================================

The redesign must work properly in light mode.

Check:

- text contrast
- border visibility
- status chips
- table rows
- selected states
- hover states
- disabled states
- empty states
- dialogs

Do not implement light theme as simply "dark theme with white background."

============================================================
26. PAGE STRUCTURE
============================================================

Recommended Dashboard layout:

------------------------------------------------------------
HEADER
------------------------------------------------------------

Dashboard                         Search...        Platform status

------------------------------------------------------------
TODAY'S JOB HUNT
------------------------------------------------------------

[12 actions need attention]

[Urgent] [Recruiter Reply] [Follow-up] [Top Jobs]

------------------------------------------------------------
MAIN WORKSPACE
------------------------------------------------------------

LEFT ~65%

    Top Opportunities
    ┌───────────────────────────────────────────┐
    │ Job | Company | Match | Method | Action   │
    │ ...                                       │
    └───────────────────────────────────────────┘

    Today's Progress
    [Discovered] [Qualified] [Reviewed] [Applied]

RIGHT ~35%

    Needs Attention
    - Recruiter reply
    - Follow-up
    - Manual application review

    Upcoming
    - Interview
    - Follow-up

------------------------------------------------------------
PIPELINE
------------------------------------------------------------

Compact application funnel / stage summary

------------------------------------------------------------
LOWER AREA
------------------------------------------------------------

Communication        Automation Status
Recent Activity      Profile / Resume readiness

------------------------------------------------------------

This is a reference layout, not a rigid pixel specification.

Use responsive behavior based on available window size.

============================================================
27. DO NOT DUPLICATE OTHER PAGES
============================================================

Dashboard should provide summaries and entry points.

JobsView:
    detailed job repository

ApplicationsView:
    complete application pipeline

OutreachWorkspace:
    complete conversations

InterviewsView:
    complete interview management

FollowupsView:
    complete follow-up management

AnalyticsView:
    complete analytics

AutomationView:
    complete automation mission control

LogsView:
    complete diagnostics

Dashboard:
    prioritized overview + action center

Never duplicate complete page functionality inside Dashboard.

============================================================
28. GLOBAL SEARCH
============================================================

Preserve Ctrl+K.

Search should eventually support:

- jobs
- companies
- applications
- contacts
- conversations
- interviews
- follow-ups

Use existing search infrastructure if available.

Do not create another independent search engine.

============================================================
29. EMPTY STATES
============================================================

Every Dashboard section must have meaningful empty states.

Examples:

No qualified jobs:

    No qualified opportunities yet.
    Run a job search to discover new roles.

    [Search Jobs]

No recruiter replies:

    No recruiter messages need your attention.

No interviews:

    No upcoming interviews.

No follow-ups:

    You're caught up on follow-ups.

No automation:

    Automation is idle.

Do not leave giant blank rectangles.

============================================================
30. LOADING STATES
============================================================

Do not freeze the Qt UI.

Dashboard data loading must be asynchronous where required.

Use existing worker/task infrastructure.

Show:

    loading skeleton/spinner
    section-level loading
    refresh state

Do not block the Qt main thread.

============================================================
31. REFRESH BEHAVIOR
============================================================

Use one coherent refresh mechanism.

Avoid having:

    Refresh Stats
    Refresh
    Refresh Activity
    Refresh Jobs

all competing visually.

Dashboard should have a single refresh action where possible.

Individual sections may refresh internally if architecture requires it, but
this should not clutter the UI.

============================================================
32. DATA CONSISTENCY
============================================================

Dashboard metrics must come from authoritative domain services.

Do not calculate:

    applications
    interviews
    offers
    qualification

using independent duplicated SQL queries inside the UI.

Use service-level aggregations.

If an aggregation is missing:

    extend the appropriate service.

============================================================
33. PERFORMANCE
============================================================

Dashboard must remain responsive with:

- thousands of jobs
- hundreds/thousands of applications
- long communication histories
- large activity logs

Do not load entire tables just to calculate Dashboard metrics.

Use:

- aggregate queries
- pagination
- limited result sets
- indexed filters
- service-level summary methods

Examples:

    top 5/10 qualified jobs
    top 5 attention items
    latest 5 activities
    next 3 schedules

Do not load 5,000 jobs into the Dashboard.

============================================================
34. TODAY'S HUNT ALGORITHM
============================================================

Do NOT create arbitrary hard-coded priorities.

Create a clear presentation-level prioritization model.

Example conceptual categories:

    URGENT
    HIGH
    NORMAL
    INFORMATIONAL

Possible signals:

- overdue
- due today
- interview proximity
- recruiter inbound
- qualification decision
- qualification score
- unapplied
- application status
- follow-up status
- freshness

Document the prioritization rules.

Do not silently perform actions based on this priority.

Priority determines:

    what appears first

not:

    what JobPilot automatically executes.

============================================================
35. QUALIFICATION INTEGRATION
============================================================

Dashboard should expose:

    Match
    Decision
    Confidence
    Matched Skills
    Missing Skills
    Explanation

where available.

Example:

    87%
    STRONG MATCH

    + Python
    + FastAPI
    + PostgreSQL
    + Docker

    Missing:
    - Kubernetes

    Why:
    Strong role and skill alignment.

Click:

    View Qualification

should open the job detail / qualification explanation.

Do not repeat qualification logic.

============================================================
36. ACTION ROUTING
============================================================

Every Dashboard action must route to an existing workflow.

Examples:

[Review Job]
    → JobsView / Job Detail

[Apply]
    → appropriate application workflow

[Open Conversation]
    → OutreachWorkspace

[Follow Up]
    → FollowupsView / Outreach Composer

[Prepare]
    → InterviewsView

[Complete Profile]
    → ProfileView

[Manage Resume]
    → ResumesView

[Automation]
    → AutomationView

[View Activity]
    → LogsView

Do not create isolated duplicate dialogs unless necessary.

============================================================
37. NO FAKE DATA
============================================================

This is mandatory.

Do not use:

- mock jobs
- fake recruiters
- fake interviews
- fake application counts
- random match scores
- placeholder 94% readiness
- fake platform health
- hardcoded activity events

If real data does not exist:

    show empty state

or:

    —

or:

    Not configured

This is a production desktop application.

============================================================
38. EXISTING DASHBOARD MIGRATION
============================================================

Before deleting anything from the current Dashboard:

Audit:

- current widgets
- current service calls
- current signals
- current refresh behavior
- current navigation callbacks
- current automation triggers
- current activity stream
- current platform status
- existing tests

Reuse working functionality.

Do not rewrite working backend logic merely to redesign UI.

============================================================
39. CURRENT SCREEN-SPECIFIC ISSUES TO FIX
============================================================

Based on the current Dashboard screenshots, specifically address:

1. The page is vertically overloaded.
2. Six KPI cards consume too much first-screen space.
3. Platform Automation Launch Deck is too large.
4. "All Platforms / Launch All" is too prominent.
5. Pipeline funnel is too large relative to actionable work.
6. Upcoming Schedules wastes space when empty.
7. Recent System Activity is too prominent.
8. System Activity popup feels like a developer/debug tool.
9. Multiple orange CTAs compete with each other.
10. Dashboard currently communicates system state better than user priorities.
11. There is no strong "what should I do next?" area.
12. Qualification results are not the center of job discovery.
13. There is no cohesive daily workflow.
14. Empty sections consume too much visual space.
15. Dashboard should feel like an ATS/job-search product rather than an
    automation control console.

Do not simply rearrange the existing cards.

Redesign the information hierarchy.

============================================================
40. TODAY'S JOB HUNT SHOULD FEEL LIKE A WORK QUEUE
============================================================

The user should be able to open JobPilot in the morning and immediately see:

    TODAY'S JOB HUNT

    1. Review 8 strong-match jobs
    2. Reply to recruiter from ABC
    3. Follow up with XYZ
    4. Prepare for tomorrow's interview
    5. Review 2 applications requiring manual intervention

This should be the emotional/product experience.

Not:

    "Here are 1,407 jobs and 234 applications."

Counts are secondary.

Actions are primary.

============================================================
41. AUTOMATION SAFETY
============================================================

Automation controls must remain explicit.

Never automatically:

- submit an application
- send recruiter email
- send follow-up
- answer unknown application questions
- solve CAPTCHA
- bypass platform restrictions

unless an existing explicit user-approved workflow already defines that action
and the action is within its supported/safe boundary.

Dashboard recommendations are recommendations.

The user remains in control of consequential actions.

============================================================
42. TESTING
============================================================

Before implementation:

    record baseline test count

After implementation:

    run existing tests
    run Dashboard tests
    run relevant service tests
    run qualification tests
    run application tests
    run outreach/follow-up tests
    run UI/self-test if available

Add tests for:

1. Dashboard loads with empty database.
2. Dashboard loads with real jobs.
3. Dashboard loads with no qualification results.
4. Dashboard loads with qualification results.
5. Top opportunities are correctly selected.
6. Unapplied jobs only appear in opportunity queue.
7. Recruiter reply appears in attention queue.
8. Overdue follow-up appears correctly.
9. Interview ordering works.
10. Dashboard handles missing profile.
11. Dashboard handles missing resume.
12. Dashboard handles unavailable automation platform.
13. Navigation actions route correctly.
14. Refresh does not duplicate data.
15. Large datasets remain performant.
16. Dark theme.
17. Light theme.
18. Empty states.
19. Loading states.
20. Qualification explanation navigation.
21. No fake data is generated.

Never claim tests passed without actually running them.

============================================================
43. DOCUMENTATION
============================================================

Update relevant documentation.

Document:

- Dashboard architecture
- Today's Job Hunt aggregation
- prioritization rules
- data sources
- service dependencies
- UI states
- empty states
- action routing
- testing strategy

Do not create unnecessary documentation duplicates.

============================================================
44. IMPLEMENTATION ORDER
============================================================

Follow this exact sequence.

PHASE 0 — Understand

Read the repository and attached specification.

Do not code.

PHASE 1 — Audit

Identify:

- existing Dashboard
- existing services
- qualification integration
- existing Today/Action concepts
- current theme system
- current navigation
- current tests

Do not code yet.

PHASE 2 — Architecture Plan

Produce:

1. Current architecture
2. Proposed Dashboard architecture
3. Today’s Job Hunt data flow
4. Required service changes
5. UI component hierarchy
6. database queries/aggregations required
7. test plan
8. migration/deprecation plan

STOP and report the plan.

PHASE 3 — Service Integration

Only after architecture is clear:

Implement missing service-level aggregation/query methods.

Do not put business logic into widgets.

PHASE 4 — Dashboard Presentation Model

Create a clean presentation model / DTO layer if appropriate.

Example conceptual structure:

DashboardSnapshot
Today'sHuntSummary
DashboardActionItem
TopOpportunity
UpcomingItem
PipelineSummary
CommunicationSummary
AutomationSummary
ReadinessSummary
RecentActivityItem

Use actual project naming conventions.

PHASE 5 — Dashboard UI

Implement the redesigned Dashboard.

PHASE 6 — Today’s Job Hunt

Implement the action-oriented queue.

PHASE 7 — Navigation

Connect every action to existing workflows.

PHASE 8 — Theme

Validate dark and light modes.

PHASE 9 — Tests

Run all relevant tests.

PHASE 10 — Visual QA

Launch the application and inspect the real Dashboard.

Check:

- first viewport
- scrolling
- responsive layout
- empty states
- populated states
- long titles
- long company names
- many action items
- dark theme
- light theme

PHASE 11 — Regression

Verify:

- Jobs
- Applications
- Outreach
- Interviews
- Follow-ups
- Analytics
- Automation
- Logs
- Profile
- Resume
- QnA
- Settings

still work.

============================================================
45. IMPORTANT — DO NOT EXPAND SCOPE
============================================================

This task is:

    Dashboard redesign
    +
    Today's Job Hunt integration

Do NOT start implementing:

- email discovery engine
- recruiter discovery engine
- new scraper
- new platform
- Glassdoor automation rewrite
- universal application agent
- Stagehand integration
- new outreach engine
- new qualification algorithm
- CAPTCHA solving
- stealth system
- analytics redesign
- database migration unrelated to Dashboard

If one of these is required as a dependency, report it.

Do not silently expand scope.

============================================================
46. ACCEPTANCE CRITERIA
============================================================

The implementation is successful only if:

[ ] Dashboard opens without errors.

[ ] Dashboard uses real JobPilot data.

[ ] No fake metrics exist.

[ ] Today's Job Hunt is the primary operational area.

[ ] User can immediately understand what requires attention.

[ ] Qualified jobs are surfaced using the Qualification Engine.

[ ] Qualification logic is NOT duplicated in Dashboard.

[ ] Recruiter replies requiring attention are surfaced.

[ ] Follow-ups due/overdue are surfaced.

[ ] Upcoming interviews are surfaced.

[ ] Today's progress is visible.

[ ] Application pipeline remains visible but compact.

[ ] Automation status remains available but secondary.

[ ] Recent activity is secondary.

[ ] System logs remain in Logs/Diagnostics.

[ ] Dashboard actions route to existing workflows.

[ ] No blind "Launch All" behavior is introduced.

[ ] No CAPTCHA bypass or stealth/security evasion is introduced.

[ ] No UI blocking occurs.

[ ] Dark theme works.

[ ] Light theme works.

[ ] Empty states are useful.

[ ] Large datasets do not freeze the UI.

[ ] Existing navigation remains intact.

[ ] Existing automation is not rewritten.

[ ] Existing tests continue passing.

[ ] New Dashboard tests pass.

[ ] Documentation is updated.

============================================================
47. FINAL PRODUCT TEST
============================================================

After implementation, do NOT just tell me:

    "Dashboard redesigned successfully."

Instead perform this real-world test:

Pretend I opened JobPilot at 9:00 AM.

Ask:

    "Can I understand within 10 seconds what I should do today?"

Then verify:

    1. What jobs should I review?
    2. Which applications need attention?
    3. Who replied?
    4. Who should I follow up with?
    5. Do I have an interview?
    6. Is my profile/resume ready?
    7. Is automation ready?
    8. What progress have I made today?

If the Dashboard cannot answer these questions quickly,
the redesign is not complete.

============================================================
48. FINAL REPORT
============================================================

At the end report:

1. Files changed
2. Services changed
3. Components added/removed
4. Dashboard data flow
5. Today's Job Hunt logic
6. Qualification integration
7. Tests added
8. Tests executed
9. Test results
10. Visual QA results
11. Any known limitations
12. Any dependencies intentionally left untouched

Do not claim anything was implemented if it was not.

============================================================
FINAL RULE
============================================================

The goal is NOT to make the Dashboard contain everything.

The goal is to make the Dashboard tell the user:

    "Here is where you stand.
     Here is what matters.
     Here is what you should do next."

Build the Dashboard as the operational home of JobPilot.