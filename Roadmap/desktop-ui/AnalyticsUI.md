You are working on the JobPilot desktop application.

The current Analytics page is shown in the attached reference screenshot.

The current page contains:

- Application Analytics header
- Refresh Analytics button
- Application Rate
- Response Rate
- Interview Rate
- Offer Rate
- Platform Performance Comparison table
- Recruitment Stage Breakdown

The current implementation is functional but visually and analytically too simple.

Your task is to redesign this page into a MODERN, PRODUCTION-QUALITY RECRUITMENT ANALYTICS WORKSPACE.

IMPORTANT:

This is NOT the Dashboard.

Do not duplicate Dashboard functionality.

The Dashboard should remain a high-level operational overview.

The Analytics page should answer:

    "What is happening in my job search,
     why is it happening,
     where is the funnel leaking,
     and how is performance changing over time?"

============================================================
1. FIRST — AUDIT THE EXISTING IMPLEMENTATION
============================================================

Before changing code, inspect:

    AnalyticsView
    AnalyticsService
    DashboardService
    JobService
    ApplicationService
    RecruitmentService
    Interview models
    Offer models
    Communication models
    FollowUp models
    ApplicationStatusHistory
    Platform model
    Job model
    Application model
    existing theme system
    existing chart/visualization components
    existing UI components

Determine:

1. Which analytics already exist.
2. Which metrics are currently calculated.
3. Which metrics are actually supported by database data.
4. Which metrics can be calculated reliably.
5. Which metrics would require schema changes.
6. Which existing components can be reused.
7. How dark/light theme is currently implemented.
8. How date filtering is implemented elsewhere.
9. How navigation and page layouts are structured.

DO NOT invent metrics that cannot be calculated from real data.

DO NOT insert fake/demo values.

If a metric cannot currently be calculated reliably:

    either do not show it

or:

    implement the required backend calculation first.

============================================================
2. DESIGN DIRECTION
============================================================

Use the current JobPilot UI theme as the visual foundation.

The screenshot currently uses:

    dark background
    subtle borders
    orange accent
    compact typography
    dark table surfaces

Keep that visual language but modernize it substantially.

Design target:

    Modern ATS / SaaS analytics
    + Data-dense
    + Clean
    + Professional
    + Minimal chrome
    + Strong visual hierarchy
    + Dark + Light theme
    + Responsive desktop layout

DO NOT interpret "modern" as:

    more cards
    more borders
    more gradients
    giant empty containers
    oversized headings
    excessive rounded rectangles
    decorative charts

The page should feel like a serious analytics product.

Think:

    Linear
    Vercel
    modern ATS software
    modern SaaS BI workspace

but adapted to JobPilot's existing visual identity.

============================================================
3. CORE PRINCIPLE — ANALYTICS, NOT DASHBOARD
============================================================

Dashboard answers:

    "What needs my attention?"

Analytics answers:

    "What does my historical application data tell me?"

Therefore Analytics should emphasize:

    trends
    conversion
    funnel leakage
    platform comparison
    response behavior
    application velocity
    time-to-response
    recruitment stages
    outcomes
    historical comparisons
    drill-down

Avoid duplicating:

    recent activity
    simple today's counts
    basic quick actions
    automation controls

============================================================
4. PAGE STRUCTURE
============================================================

Redesign the page approximately as:

---------------------------------------------------------
HEADER
---------------------------------------------------------

Application Analytics

Understand application volume, conversion, response behavior,
and recruitment funnel performance.

[Date Range] [Platform] [Method] [Status] [Refresh]

---------------------------------------------------------
ANALYTICS SUMMARY
---------------------------------------------------------

Applications      Response Rate      Interview Rate
     171               3.8%               0.5%

Offers            Avg Response Time    Application Velocity
     1               X days              X / week

These should NOT all be giant cards.

Use compact metric tiles with:

    value
    label
    comparison
    small trend indicator where data exists

Example:

    171
    Applications
    ↑ 18% vs previous period

If previous-period comparison cannot be calculated,
do not display a fake comparison.

---------------------------------------------------------
SECTION 1 — APPLICATION FUNNEL
---------------------------------------------------------

Application Funnel

    Discovered
        ↓
    Qualified
        ↓
    Applied
        ↓
    Response
        ↓
    Interview
        ↓
    Offer

Create a visually clear horizontal or vertical funnel.

Each stage should show:

    count
    conversion %
    drop-off %

Example:

    1,240 Discovered
          ↓ 31.4%
      389 Qualified
          ↓ 44.0%
      171 Applied
          ↓ 3.8%
        7 Responses
          ↓ 14.3%
        1 Interview
          ↓ 0%
        0 Offers

DO NOT hard-code these values.

Use actual database values.

Allow clicking a stage to filter/drill into the underlying jobs/applications.

============================================================
5. SECTION 2 — APPLICATION TREND
============================================================

Create a proper time-series visualization.

Title:

    Application Activity

Controls:

    [7D] [30D] [90D] [6M] [1Y] [Custom]

Chart:

    Applications over time

Optional series:

    Discovered
    Qualified
    Submitted
    Responses
    Interviews
    Offers

Use a clean line/area visualization.

Do not put every series on screen by default if it becomes cluttered.

Allow toggling individual series.

Tooltip should show:

    Date
    Applications
    Responses
    Interviews
    Offers

The graph should respond to global filters.

============================================================
6. SECTION 3 — CONVERSION ANALYSIS
============================================================

Create a dedicated conversion analysis section.

Possible metrics:

    Discovery → Qualification
    Qualification → Application
    Application → Response
    Response → Interview
    Interview → Offer

Show:

    Conversion %
    Absolute count
    Change vs previous period where supported

Use compact visual bars rather than large cards.

Example:

    Application → Response

    ███████░░░░░░░░   3.8%

And:

    7 responses / 184 submitted

The user should immediately understand where the funnel loses candidates.

============================================================
7. SECTION 4 — PLATFORM ANALYTICS
============================================================

Replace the current basic platform table with a richer platform analytics view.

Platforms may include:

    LinkedIn
    Naukri
    Indeed
    Foundit
    Manual

For every platform show:

    Jobs discovered
    Qualified
    Applications
    Responses
    Interviews
    Offers
    Application rate
    Response rate
    Interview rate
    Offer rate

Also show:

    application volume trend
    response trend

IMPORTANT:

Do NOT rank platforms as:

    BEST
    WORST
    #1
    #2

unless the user explicitly chooses a sorting order.

This is an analytics interface, not a recommendation system.

Allow sorting by any metric.

Allow clicking a platform row to filter the rest of the analytics page.

============================================================
8. SECTION 5 — APPLICATION METHOD ANALYSIS
============================================================

Add analysis by application method.

Possible methods:

    Easy Apply
    Direct Apply
    Questionnaire
    External Portal
    Manual

Show:

    Applications
    Responses
    Interviews
    Offers
    Response Rate

This is especially important because JobPilot supports multiple
application flows.

Use a compact comparison visualization/table.

Do not assume every platform has the same application methods.

Only display methods that exist in actual data.

============================================================
9. SECTION 6 — RESPONSE TIME ANALYTICS
============================================================

Add a dedicated response timing section if the underlying data
supports timestamps.

Metrics:

    Average time to response
    Median time to response
    Fastest response
    Slowest response

Visualize response distribution.

For example:

    < 1 day
    1–3 days
    4–7 days
    8–14 days
    15–30 days
    30+ days

Use actual timestamps from:

    application submitted
    recruiter response / communication

Do NOT calculate response time from unrelated timestamps.

If response timestamps are incomplete:

    clearly show "Insufficient data"

rather than inventing a value.

============================================================
10. SECTION 7 — APPLICATION VELOCITY
============================================================

Add:

    Applications per day
    Applications per week
    Applications per month

Show a trend.

Example:

    This week
    42 applications

    Last week
    31 applications

    Weekly velocity
    +35.5%

Only display comparison if previous-period data exists.

Also support:

    average applications/day
    active application days
    highest-volume day

============================================================
11. SECTION 8 — RECRUITMENT STAGE ANALYTICS
============================================================

The current "Recruitment Stage Breakdown" is too simplistic.

Replace it with a stage distribution visualization.

Stages:

    Applying
    Submitted
    Under Review
    Shortlisted
    Interview
    Offer
    Closed

Show:

    Count
    Percentage of active applications

Use:

    horizontal bars
    compact stage pipeline
    or segmented distribution

Do not use seven giant boxes.

Allow clicking a stage to filter applications.

============================================================
12. SECTION 9 — APPLICATION AGING
============================================================

Add:

    Application Aging

Group active applications into:

    < 3 days
    3–7 days
    8–14 days
    15–30 days
    30–60 days
    60+ days

This helps identify applications that have been sitting without
movement.

Only include relevant active/recruitment states.

Do not mix:

    rejected
    withdrawn
    closed

into active aging unless explicitly selected.

============================================================
13. SECTION 10 — COMPANY / JOB ANALYTICS
============================================================

If enough real data exists, add a compact section for:

    Applications by company
    Applications by job title
    Applications by experience level
    Applications by location

Do not create huge tables.

Use:

    top categories
    searchable breakdown
    expandable rows
    drill-down

For example:

    Job Role Distribution

    RPA Developer             42
    Automation Engineer       31
    Python Developer          24
    AI Automation Engineer    18

Clicking a role should allow filtering the analytics dataset.

Do not label one role "best".

============================================================
14. SECTION 11 — SOURCE QUALITY / FUNNEL LEAKAGE
============================================================

Add an analytical section:

    Funnel Leakage

Identify where volume drops between stages.

Example:

    Discovered → Qualified      31%
    Qualified → Applied         44%
    Applied → Response           3.8%
    Response → Interview        14%

Visually highlight the magnitude of each drop-off.

Use neutral language:

    "Conversion"
    "Drop-off"
    "Volume"

Do not generate subjective conclusions such as:

    "Bad platform"
    "Poor jobs"
    "Best source"

The analytics should present evidence, not decisions.

============================================================
15. SECTION 12 — FILTER BAR
============================================================

Create one global analytics filter bar near the top.

Filters:

    Date Range
    Platform
    Application Method
    Recruitment Status
    Job Type if supported
    Location if supported
    Experience if supported

Controls:

    [Apply]
    [Clear]

Prefer compact controls.

Show active filters as small removable chips.

Example:

    Last 30 days   ×
    Platform: LinkedIn   ×
    Method: Easy Apply   ×

Do NOT create giant filter cards.

============================================================
16. DATE RANGE SYSTEM
============================================================

Support:

    Today
    7 days
    30 days
    90 days
    6 months
    12 months
    Custom

When a date range is selected, ALL analytics must update.

Do not update only the top KPI cards.

The entire page must use the same analytics query/filter context.

============================================================
17. PERIOD COMPARISON
============================================================

Where sufficient data exists, allow:

    Current Period
    Previous Period

Example:

    Applications
    171

    Previous period
    143

    Change
    +19.6%

Use subtle trend indicators.

Do not fabricate percentage changes.

If there is insufficient previous-period data:

    hide the comparison.

============================================================
18. DRILL-DOWN EXPERIENCE
============================================================

This is one of the most important features.

Every major analytics visualization should be interactive.

Examples:

Click:

    LinkedIn

→ filter analytics to LinkedIn.

Click:

    Submitted = 144

→ open filtered Applications view.

Click:

    Interview = 1

→ show the corresponding application/interview records.

Click:

    RPA Developer = 42

→ filter Jobs/Applications to that role.

Do not create duplicate analytics data views.

Reuse the existing Jobs and Applications views where possible.

============================================================
19. EXPORT
============================================================

Add:

    Export Analytics

Options:

    CSV
    Excel if existing export infrastructure supports it

Export the CURRENT filtered dataset.

Do not export the entire database when filters are active.

Include:

    date range
    filters
    platform
    job
    company
    application
    status
    timestamps
    relevant calculated metrics

Use existing export utilities if available.

============================================================
20. EMPTY / INSUFFICIENT DATA STATES
============================================================

Analytics must handle:

    no applications
    no responses
    no interviews
    no offers
    incomplete timestamps
    platform with zero applications
    filtered dataset with no results

Do not show:

    0.0%

everywhere without context.

For example:

    No interview data yet

is more useful than:

    Interview Rate: 0.0%

when there are zero interviews.

For response-time metrics:

    Not enough response timestamps

instead of a misleading zero.

============================================================
21. TOOLTIP / DATA EXPLANATION
============================================================

Every non-obvious metric should have a small tooltip/info indicator.

Examples:

    Response Rate
    "Responses received ÷ submitted applications"

    Interview Rate
    "Applications with at least one interview ÷ submitted applications"

    Offer Rate
    "Applications with at least one offer ÷ submitted applications"

Do not make users guess how metrics are calculated.

============================================================
22. VISUAL HIERARCHY
============================================================

Use this hierarchy:

LEVEL 1
    Page title + global filters

LEVEL 2
    Compact key metrics

LEVEL 3
    Main analytical visualizations

LEVEL 4
    Detailed comparison tables / drilldowns

Avoid:

    card inside card
    panel inside panel
    bordered section inside bordered section

Use whitespace and subtle surface differences instead.

============================================================
23. MODERN DARK THEME
============================================================

Preserve JobPilot's current dark theme concept.

Use:

    near-black page background
    slightly elevated surfaces
    subtle borders
    white/near-white primary text
    muted gray secondary text
    orange as primary accent

Orange should be used for:

    primary actions
    selected states
    important highlights
    interactive focus

Do NOT make every chart orange.

Use restrained semantic colors for:

    positive/confirmed
    warning
    neutral
    closed/rejected

Avoid neon colors.

============================================================
24. LIGHT THEME
============================================================

The exact same analytics layout must work in light mode.

Use:

    white/off-white background
    subtle gray borders
    dark text
    muted secondary text
    orange accent

Do not simply invert the dark theme.

Ensure:

    charts
    grid lines
    tooltips
    labels
    badges
    tables
    dropdowns

remain readable.

============================================================
25. RESPONSIVE DESKTOP LAYOUT
============================================================

The application is desktop-first.

Use:

    wide layout for charts
    two-column sections where useful
    full-width charts for time series
    compact tables

Avoid fixed heights that create huge empty areas.

The current screenshot has a large empty area beneath
Platform Performance Comparison.

Eliminate this.

Every section should size according to its content.

============================================================
26. CHART DESIGN
============================================================

Charts should be:

    clean
    compact
    readable
    interactive

Avoid:

    3D charts
    excessive gradients
    unnecessary legends
    decorative animations
    pie charts for everything

Preferred:

    line charts
    area charts
    horizontal bars
    funnel visualization
    compact stacked bars

Animations should be subtle and fast.

============================================================
27. TABLE DESIGN
============================================================

For detailed analytics tables:

    sticky header
    compact rows
    sortable columns
    subtle hover
    right-aligned numeric columns
    percentage formatting
    consistent number formatting

Example:

    Platform      Apps    Responses    Response Rate
    LinkedIn      145       7              4.8%
    Naukri         23       1              4.3%
    Indeed         30       0              0.0%
    Foundit        11       0              0.0%

Allow sorting by:

    applications
    responses
    interviews
    offers
    conversion rates

Do not visually declare a winner.

============================================================
28. PERFORMANCE
============================================================

Do not execute one database query per table row.

Prefer:

    aggregated SQL queries
    grouped queries
    date-bucket queries
    service-level analytics aggregation

Analytics should remain responsive with thousands of jobs/applications.

Avoid loading every Application object into Python just to calculate
simple counts that SQL can calculate.

============================================================
29. BACKEND ARCHITECTURE
============================================================

Keep analytics calculations OUT of the UI.

Use:

    AnalyticsService

as the authoritative analytics layer.

Conceptual API:

    get_summary(filters)
    get_funnel(filters)
    get_application_trend(filters)
    get_platform_breakdown(filters)
    get_method_breakdown(filters)
    get_response_time_metrics(filters)
    get_velocity(filters)
    get_stage_breakdown(filters)
    get_aging_breakdown(filters)
    get_role_breakdown(filters)
    get_location_breakdown(filters)
    get_period_comparison(filters)

Do not create random SQL queries directly inside AnalyticsView.

============================================================
30. ANALYTICS FILTER OBJECT
============================================================

If the current implementation has many individual parameters,
introduce a structured filter object.

Example concept:

    AnalyticsFilter

containing:

    start_date
    end_date
    platform
    application_method
    status
    location
    experience
    job_type

Use the project's existing conventions if an equivalent filter object
already exists.

Do not duplicate an existing filtering abstraction.

============================================================
31. DATA DEFINITIONS
============================================================

Define every metric clearly.

For example:

Application Rate:

    submitted applications / discovered jobs

Response Rate:

    applications with recruiter response /
    submitted applications

Interview Rate:

    applications with at least one interview /
    submitted applications

Offer Rate:

    applications with at least one offer /
    submitted applications

If the current system uses a different definition, inspect the
existing AnalyticsService and preserve established semantics unless
there is a documented bug.

Do not silently change metric definitions during UI redesign.

============================================================
32. CURRENT DATA MUST REMAIN CONSISTENT
============================================================

The screenshot currently shows values such as:

    Application Rate: 24.2%
    Response Rate: 3.8%
    Interview Rate: 0.5%
    Offer Rate: 0.0%

Platform rows:

    LinkedIn
    Naukri
    Indeed
    Foundit
    Manual

These are examples of CURRENT DATA displayed by the application.

Do not hard-code them.

After redesign, the same underlying data should produce consistent
results.

If the UI changes metric definitions, explicitly document the change
and update tests.

============================================================
33. NO FAKE DATA
============================================================

This is a strict requirement.

Do not add:

    sample applications
    fake response times
    fake trends
    fake percentages
    fake companies
    fake charts

If there is insufficient data:

    show an intentional empty state.

Example:

    No response-time data yet
    Start tracking recruiter responses to see this analysis.

============================================================
34. ACCESSIBILITY
============================================================

Ensure:

    keyboard navigation
    readable contrast
    visible focus states
    meaningful button labels
    tooltips for icon-only controls
    accessible chart summaries where practical

Do not make charts the only way to understand a metric.

Important values should also exist as text.

============================================================
35. MICRO-INTERACTIONS
============================================================

Use subtle interactions:

    hover row
    tooltip
    filter chip removal
    chart series toggle
    drill-down
    refresh loading state
    smooth filter update

Avoid:

    excessive animations
    bouncing cards
    distracting transitions

============================================================
36. REFRESH BEHAVIOR
============================================================

Replace the current large:

    Refresh Analytics

button with a compact refresh control.

Show:

    refreshing state
    last updated time

Example:

    Updated 2 min ago   ↻

When refreshing:

    disable duplicate refresh requests
    show subtle loading indicator
    preserve current filters

============================================================
37. LOADING STATES
============================================================

Do not render an empty page while analytics load.

Use:

    skeleton rows
    skeleton chart areas
    compact loading indicators

Avoid giant spinners.

============================================================
38. ERROR STATES
============================================================

If analytics loading fails:

    show a compact inline error state.

Example:

    Unable to load analytics

    [Retry]

Do not crash the entire application.

============================================================
39. DO NOT OVERBUILD
============================================================

Do NOT add every possible chart just because it is technically possible.

Prioritize:

    1. Funnel
    2. Application trend
    3. Conversion analysis
    4. Platform analysis
    5. Application method analysis
    6. Response timing
    7. Aging
    8. Drill-down
    9. Export

Only add additional visualizations if the underlying data supports them
and they provide meaningful analytical value.

============================================================
40. FINAL TARGET LAYOUT
============================================================

Target the following overall structure:

┌──────────────────────────────────────────────────────────────┐
│ Application Analytics                         Updated 2m ago │
│ Understand your recruitment funnel and trends                │
│                                                              │
│ [30 Days] [All Platforms] [All Methods] [All Status] [↻]    │
└──────────────────────────────────────────────────────────────┘

┌────────────┬────────────┬────────────┬────────────┬──────────┐
│ Applications│ Response  │ Interview  │ Offers     │ Velocity │
│ 171         │ 3.8%      │ 0.5%       │ 0.0%       │ 42/week  │
└────────────┴────────────┴────────────┴────────────┴──────────┘

┌─────────────────────────────────────┬────────────────────────┐
│ Application Activity                │ Funnel                 │
│                                     │                        │
│        ╱╲                           │ Discovered   1240      │
│   ╱╲  ╱  ╲                          │     ↓                  │
│  ╱  ╲╱    ╲                         │ Qualified     389      │
│                                     │     ↓                  │
│ Applications over time              │ Applied       171      │
│                                     │     ↓                  │
└─────────────────────────────────────┴────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Conversion Analysis                                          │
│                                                              │
│ Qualified → Applied        ███████████░░░░ 44.0%             │
│ Applied → Response         █░░░░░░░░░░░░░  3.8%             │
│ Response → Interview       ██░░░░░░░░░░░░ 14.3%             │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Platform Performance                                         │
│                                                              │
│ Platform    Jobs    Apps    Responses   Interviews   Offers │
│ LinkedIn    300     145        7            1           0   │
│ Naukri      352      23        1            0           0   │
│ Indeed       76      30        0            0           0   │
│ Foundit     136      11        0            0           0   │
└──────────────────────────────────────────────────────────────┘

┌───────────────────────────────┬──────────────────────────────┐
│ Application Method            │ Application Aging            │
│                               │                              │
│ Direct Apply      54         │ < 3 days          31         │
│ Questionnaire     42         │ 3–7 days           44         │
│ Easy Apply        63         │ 8–14 days          28         │
│ External          12         │ 15–30 days         19         │
└───────────────────────────────┴──────────────────────────────┘

============================================================
41. IMPORTANT UX RULE
============================================================

The page must NOT feel like:

    "Dashboard with more charts."

It must feel like:

    "A recruitment analytics workspace."

The user should be able to answer:

    How many applications am I sending?

    Is my application volume increasing?

    What percentage reaches each recruitment stage?

    Where is the funnel dropping?

    How do platforms differ?

    How do application methods differ?

    How quickly do recruiters respond?

    How many applications are aging without movement?

    Which roles/locations generate most application volume?

    What changed compared with the previous period?

    Which exact applications are behind a metric?

============================================================
42. TESTING
============================================================

Add/update tests for:

    summary metrics
    date filters
    platform filters
    method filters
    status filters
    funnel calculations
    trend aggregation
    period comparison
    response time
    aging buckets
    platform aggregation
    method aggregation
    zero-data states
    insufficient-data states
    drill-down filters
    export filters

Verify that:

    Dashboard remains unchanged
    Jobs remains unchanged
    Applications remains unchanged
    Automation remains unchanged

Run the complete existing test suite.

============================================================
43. FINAL ACCEPTANCE CRITERIA
============================================================

The implementation is complete only when:

[ ] Analytics is visually distinct from Dashboard
[ ] Dark theme is modernized
[ ] Light theme works correctly
[ ] No giant empty containers
[ ] No fake metrics
[ ] Global filters work
[ ] Date ranges work
[ ] Funnel exists
[ ] Trend chart exists
[ ] Conversion analysis exists
[ ] Platform analysis exists
[ ] Application method analysis exists
[ ] Response timing exists if data supports it
[ ] Application aging exists
[ ] Drill-down works
[ ] Export works
[ ] Loading states exist
[ ] Empty states exist
[ ] Error states exist
[ ] Refresh state exists
[ ] Tooltips explain important metrics
[ ] Analytics calculations remain in AnalyticsService
[ ] UI does not contain business logic
[ ] Existing dashboard is not duplicated
[ ] Existing functionality is not broken
[ ] Existing tests pass

============================================================
44. FINAL IMPLEMENTATION REPORT
============================================================

After implementation report:

1. Files modified
2. Files created
3. Backend analytics added
4. UI components added
5. Metrics implemented
6. Metrics intentionally NOT implemented because data is insufficient
7. Filters implemented
8. Drill-down behavior
9. Export behavior
10. Tests added
11. Full test result
12. Any remaining limitations

Do not claim a feature is implemented unless it actually exists.

Start by auditing the current AnalyticsView and AnalyticsService.
Do not start coding immediately.