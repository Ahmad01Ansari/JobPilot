You are redesigning the existing JobPilot Jobs page into a production-ready,
modern ATS-style Job Management workspace.

IMPORTANT:
This is an existing PySide6 desktop application.

The current Jobs page already has working:
- JobsService / JobService
- ApplicationService
- database/repository layer
- job loading
- job selection
- job detail panel
- All Jobs / Easy Apply / Company Portal views
- search
- platform filtering
- status information
- job description rendering
- Open Listing URL
- pipeline actions

DO NOT rewrite or replace the existing backend architecture.

DO NOT rewrite the database models unless absolutely required for an existing
functionality that cannot be implemented otherwise.

DO NOT modify LinkedIn or Naukri automation.

DO NOT create fake data.

The goal is to transform the EXISTING Jobs page into a polished,
production-ready ATS-style interface while preserving all existing behavior.

========================================================
1. PRIMARY UX GOAL
========================================================

The Jobs page should feel like:

"Professional ATS Job Repository + Intelligent Job Workspace"

It should resemble a modern recruitment/productivity application rather than
a traditional desktop CRUD table.

The user should be able to:

1. Quickly find jobs.
2. Filter jobs precisely.
3. Sort jobs.
4. Compare jobs.
5. Select a job.
6. Inspect its details without losing table context.
7. Understand application status immediately.
8. Open the original listing.
9. Add the job to the recruitment pipeline.
10. Track whether it was applied, skipped, failed, external, etc.
11. Perform bulk operations when appropriate.

Prioritize information hierarchy and productivity over decoration.

========================================================
2. PAGE STRUCTURE
========================================================

Redesign the page into:

PAGE HEADER
    ↓
VIEW / FILTER TOOLBAR
    ↓
ACTIVE FILTER CHIPS
    ↓
JOB DATA GRID + DETAIL PANEL
    ↓
PAGINATION / RESULT SUMMARY

Recommended layout:

┌───────────────────────────────────────────────────────────────┐
│ Jobs                                  + Add Job   Refresh     │
│ Browse and manage your job opportunities                     │
├───────────────────────────────────────────────────────────────┤
│ All Jobs | Easy Apply | Company Portal                        │
├───────────────────────────────────────────────────────────────┤
│ Search │ Platform │ Status │ Method │ Location │ More Filters │
├───────────────────────────────────────────────────────────────┤
│ Active filters: LinkedIn ×  Easy Apply ×  ...                 │
├───────────────────────────────────────────────┬───────────────┤
│                                               │               │
│                  JOB DATA GRID                │ JOB DETAILS   │
│                                               │               │
│                                               │               │
│                                               │               │
├───────────────────────────────────────────────┴───────────────┤
│ 124 jobs    1–50 of 124                < 1 2 3 ... >          │
└───────────────────────────────────────────────────────────────┘

Do not create excessive nested cards.

========================================================
3. PAGE HEADER
========================================================

Create a clean ATS-style header.

Left:

Jobs

"Browse, filter, and manage opportunities across your job sources."

Right:

[ + Add Job ]
[ Refresh ]

Optional:

[ Export ]

Only expose Export if the existing application already supports or can safely
support it without changing the backend architecture.

Do not use huge title typography.

========================================================
4. JOB CATEGORY NAVIGATION
========================================================

Keep the current three categories:

All Jobs
Easy Apply
Company Portal

But redesign them as modern segmented tabs.

Example:

[ All Jobs 124 ] [ Easy Apply 86 ] [ Company Portal 38 ]

The active tab should use the application's primary accent.

Do not use large orange-filled blocks everywhere.

The primary accent should be reserved for:
- active navigation
- primary CTA
- important selected state

========================================================
5. GLOBAL SEARCH
========================================================

Improve the current search field.

Support searching across relevant existing fields:

- job title
- company
- location
- platform

Use:

[ 🔍 Search jobs, companies, locations... ]

Do not execute a database query on every keystroke if the current repository
architecture does not support it efficiently.

Use a small debounce.

Display:

"124 jobs"

or:

"Showing 1–50 of 124 jobs"

========================================================
6. FILTER SYSTEM
========================================================

This is one of the biggest improvements required.

The current page needs proper filtering.

Implement a modern filter toolbar.

Primary filters:

Platform
Status
Application Method
Location
Experience
Date Discovered

Example:

[ Platform ▾ ]
[ Status ▾ ]
[ Method ▾ ]
[ Location ▾ ]
[ Experience ▾ ]
[ Date ▾ ]
[ More Filters ]

Each filter should support appropriate multi-selection where useful.

Example:

Platform:
☐ LinkedIn
☐ Naukri
☐ Indeed
☐ Manual

Status:
☐ Not Applied
☐ Applying
☐ Submitted
☐ Skipped
☐ Failed
☐ External
☐ Already Applied

Only expose statuses that actually exist in the current application.

========================================================
7. COLUMN FILTERS
========================================================

The table must support per-column filtering where practical.

For example:

Job Title
Company
Platform
Location
Experience
Method
Status

Each column header should have a small filter/sort affordance.

Example:

JOB TITLE   ↕ 🔍
COMPANY     ↕ 🔍
PLATFORM    ↕
LOCATION    ↕ 🔍
EXPERIENCE  ↕
METHOD      ↕
STATUS      ↕

Do not make every filter permanently visible.

Use a small popup/filter menu.

========================================================
8. TABLE / DATA GRID
========================================================

This is the most important UI improvement.

The existing table should become a proper ATS-style data grid.

Required capabilities:

- sortable columns
- resizable columns
- sensible automatic column widths
- minimum/maximum column widths
- horizontal scrolling when necessary
- sticky header
- alternating/subtle row treatment
- row hover state
- selected row state
- keyboard navigation
- double-click / Enter to open job details
- column visibility
- column reordering where practical
- persistent column sizing if the existing settings architecture supports it
- pagination or efficient virtualization
- no unnecessary full-table redraws

DO NOT hardcode fixed widths that break at different window sizes.

The grid must adapt to:

1920 × 1080
1600 × 900
1366 × 768

========================================================
9. RECOMMENDED DEFAULT COLUMNS
========================================================

Use a better ATS-oriented column order:

1. Job
2. Company
3. Platform
4. Location
5. Experience
6. Method
7. Status
8. Discovered
9. Actions

But do not display every possible field by default.

The most important information should have the most width.

Recommended approximate priority:

Job             HIGH
Company         MEDIUM
Platform        SMALL
Location        MEDIUM
Experience      SMALL
Method          SMALL
Status          MEDIUM
Discovered      SMALL
Actions         SMALL

The Job column should be the most flexible column.

Company should not be allowed to consume half of the table.

========================================================
10. JOB CELL DESIGN
========================================================

Instead of plain text:

Senior Software Engineer

use a richer but compact job cell:

Senior Software Engineer
Blue Yonder

Optional secondary metadata:

LinkedIn · Easy Apply

Do not make every row look like a card.

The table should remain dense enough for scanning.

========================================================
11. COMPANY CELL
========================================================

Company names should wrap gracefully.

Do not show broken values such as:

"LMENDATA
SOLUTIONS ..."

unless truncation is necessary.

Use:

LUMENDATA SOLUTIONS...

with tooltip on hover containing the complete value.

Same rule applies to:

- Job title
- Company
- Location
- Method

Never corrupt/truncate the underlying data.

========================================================
12. STATUS SYSTEM
========================================================

Create a consistent semantic status system.

Examples:

NOT APPLIED
neutral gray

APPLYING
blue/info

SUBMITTED
green/success

SKIPPED
muted gray

FAILED
red/danger

EXTERNAL
purple/info

ALREADY APPLIED
green/neutral

Only use statuses that actually exist in the backend.

Important:

Do not use the primary orange color for statuses.

Orange should remain the product/action accent.

Status colors should communicate meaning.

Do not rely only on color:
include text + icon/state shape where appropriate.

========================================================
13. METHOD DISPLAY
========================================================

Use compact semantic badges:

Easy Apply
Company Portal
External

Do not make the Method column visually dominant.

For Naukri Company Portal jobs, do not show:

"Open on LinkedIn"

The action must be derived from the selected job's actual platform/source.

Examples:

LinkedIn job:
[ Open on LinkedIn ↗ ]

Naukri job:
[ Open on Naukri ↗ ]

External application:
[ Open Application ↗ ]

Never hardcode LinkedIn actions for Naukri jobs.

========================================================
14. PLATFORM DISPLAY
========================================================

Use compact platform badges/chips:

LinkedIn
Naukri
Indeed
Manual

Use consistent iconography.

Do not use four unrelated colors.

Platform colors should be subtle and secondary.

The platform should not overpower job title/status.

========================================================
15. ROW SELECTION
========================================================

Selected job should be clearly visible.

Use:

- subtle accent border
OR
- subtle background tint
OR
- left accent indicator

Do not use an extremely bright full-row background.

The selected row should remain visible while the detail panel updates.

========================================================
16. DETAIL PANEL
========================================================

The current right-side detail panel is useful but should be redesigned.

It should behave like a modern ATS job workspace.

Header:

Senior Software Engineer (GENAI)

Blue Yonder
LinkedIn

Then compact metadata:

📍 Location
💼 Experience
💰 Salary
⚡ Method

Only display fields that actually exist.

Then:

JOB DESCRIPTION

Scrollable content.

Do not put the entire description inside multiple nested cards.

Use clear typography:

Section heading
Body content

Preserve line breaks and readability.

========================================================
17. DETAIL PANEL ACTIONS
========================================================

Primary action should be contextual.

Examples:

LinkedIn Easy Apply:

[ Open on LinkedIn ↗ ]

Naukri:

[ Open on Naukri ↗ ]

External:

[ Open Application ↗ ]

Then secondary actions:

[ Full JD ]
[ Add to Pipeline ]

If the job is already submitted:

[ View Application ]

If already in pipeline:

[ View Application ]

Do not show contradictory actions.

For example, don't show:

"In Pipeline"

when the job has no associated application.

========================================================
18. JOB DETAILS MODAL
========================================================

The existing Job Details modal should also be redesigned.

Current modal is functional but visually dated.

Improve:

- title hierarchy
- metadata layout
- description typography
- spacing
- modal width
- button hierarchy
- scrolling
- close behavior

Use:

JOB TITLE

Company · Platform

Location · Experience · Salary

────────────────────────

Job Description

...

────────────────────────

[ Open Listing ↗ ]                 [ Close ]

Do not use heavy black bars behind every heading.

========================================================
19. COLUMN VISIBILITY
========================================================

Add:

[ Columns ▾ ]

Menu:

☑ Job
☑ Company
☑ Platform
☑ Location
☑ Experience
☑ Method
☑ Status
☐ Discovered
☐ Last Seen

Only include fields that actually exist.

This allows the user to customize the table without overcrowding it.

========================================================
20. SORTING
========================================================

Support:

- Job title
- Company
- Platform
- Location
- Experience
- Status
- First seen
- Last seen

Where backend sorting exists.

Use clear sort indicators:

↑
↓

Do not implement fake client-side sorting for fields that would require
incorrect/incomplete data.

========================================================
21. RESULT PAGINATION
========================================================

The current "100 jobs" indicator should become a proper result footer.

Example:

124 jobs

Showing 1–50 of 124

[ Previous ] 1 2 3 [ Next ]

Use server-side pagination if the repository/service layer already supports it.

Do not load thousands of jobs into the UI unnecessarily.

If pagination already exists in JobService, use it.

========================================================
22. BULK SELECTION
========================================================

Add a checkbox column if the existing service layer can support safe bulk
operations.

Example:

☐

Selecting rows produces:

3 selected

[ Mark Skipped ]
[ Add to Pipeline ]
[ Open URLs ]

Do NOT implement destructive bulk operations without explicit confirmation.

Do NOT add bulk Apply automation from this page unless the existing
automation architecture already supports that operation safely.

========================================================
23. ACTIVE FILTER CHIPS
========================================================

When filters are active, show:

Filters:

LinkedIn ×
Easy Apply ×
India ×

[ Clear All ]

This provides immediate visibility into why the table is showing its current
results.

========================================================
24. EMPTY STATES
========================================================

Never display a giant empty table.

Examples:

No jobs found

Try changing your filters or search query.

[ Clear Filters ]

For Easy Apply:

No Easy Apply jobs available.

For Company Portal:

No company portal jobs found.

Make empty states useful and visually clean.

========================================================
25. LOADING STATE
========================================================

Use skeleton rows or a lightweight loading state.

Do not freeze the UI while loading jobs.

Example:

Job title     Company       Platform       Location
────────      ───────       ────────       ────────
Loading...    Loading...    Loading...     Loading...

Only use skeleton animations if they fit the existing PySide6 architecture.

========================================================
26. ERROR STATE
========================================================

If jobs fail to load:

Unable to load jobs

[ Retry ]

Show a concise error.

Do not expose Python tracebacks in the main UI.

Detailed information belongs in Logs.

========================================================
27. COLOR SYSTEM
========================================================

The current orange accent is useful but currently overused.

Create semantic design tokens.

Primary accent:
orange

Use orange for:
- primary CTA
- active tab
- important selected state
- key interactive focus

Do NOT use orange for:
- every badge
- every section
- every button
- normal table rows

Recommended semantic system:

Primary:
brand orange

Success:
green

Warning:
amber

Danger:
red

Info:
blue

Neutral:
slate/gray

Platform colors should be subtle.

The overall UI should remain dark and sophisticated.

Also ensure the same semantic tokens work in light theme.

========================================================
28. LIGHT + DARK THEME
========================================================

The Jobs page must work correctly in both themes.

Dark theme:
- near-black application background
- elevated dark surfaces
- subtle slate borders
- white primary text
- muted gray secondary text

Light theme:
- soft gray application background
- white surfaces
- subtle gray borders
- dark primary text
- muted slate secondary text

Do not simply invert colors.

Every component must use the central theme/design-token system.

========================================================
29. TABLE DENSITY
========================================================

Provide a professional data-grid density.

Default:

Comfortable

Optional:

Compact
Comfortable

Avoid oversized rows.

The user should be able to scan many jobs at once.

========================================================
30. TOOLBAR UX
========================================================

Recommended toolbar:

┌──────────────────────────────────────────────────────────────┐
│ 🔍 Search jobs...   Platform ▾ Status ▾ Method ▾ More ▾      │
│                                                              │
│ LinkedIn ×  Easy Apply ×                    Clear filters    │
└──────────────────────────────────────────────────────────────┘

Right-side:

[ Columns ▾ ]

Do not fill the toolbar with too many buttons.

Advanced filters should go into a popup/drawer.

========================================================
31. RESPONSIVE SPLIT VIEW
========================================================

The table/detail layout should adapt to window width.

Large desktop:

~70% table
~30% detail

At narrower widths:

~65% table
~35% detail

If the window becomes too narrow:

allow the detail panel to collapse or open as a drawer/modal.

Do not allow table columns to become unreadable.

========================================================
32. KEYBOARD UX
========================================================

Implement standard productivity interactions where supported:

↑ / ↓
navigate rows

Enter
open selected job

Esc
close detail/modal

Ctrl/Cmd + K
global search

Ctrl/Cmd + F
focus job search

Do not break existing application shortcuts.

========================================================
33. RIGHT DETAIL PANEL SHOULD REMEMBER SELECTION
========================================================

When the user:

- changes page
- applies a filter
- sorts

the selected job should be handled safely.

Never display details from an old job while the table shows a different selection.

If the selected job disappears after filtering:

clear the detail panel and show:

Select a job to view details.

========================================================
34. DATA QUALITY
========================================================

The screenshots show malformed/truncated values such as:

"ue Yonde"

instead of the expected location/company value.

DO NOT silently fix source data in the UI.

Instead:

1. Preserve the actual stored value.
2. Render it safely.
3. Show full value via tooltip/detail panel.
4. If the source data itself is malformed, optionally mark it as such
   without mutating the database.

The UI layer must not silently modify job records.

========================================================
35. PERFORMANCE
========================================================

The Jobs page may eventually contain thousands of jobs.

Design for:

10
100
1,000
10,000+

jobs.

Avoid rebuilding the entire UI for every selection/filter update.

Prefer:

- efficient model/view architecture
- pagination
- lazy detail loading
- virtualized rendering where supported
- debounced search
- minimal database queries
- cached selected-job details where appropriate

Do not sacrifice correctness for premature optimization.

========================================================
36. COMPONENT ARCHITECTURE
========================================================

Do not keep everything inside one large JobsView class.

Prefer components such as:

app/ui/views/jobs_view.py

app/ui/widgets/jobs/
    jobs_header.py
    jobs_toolbar.py
    jobs_tabs.py
    jobs_filter_bar.py
    jobs_table.py
    jobs_detail_panel.py
    jobs_status_badge.py
    jobs_empty_state.py
    jobs_pagination.py
    job_details_dialog.py

Only create components where they provide real reuse/value.

Do not over-fragment tiny widgets.

========================================================
37. EXISTING SERVICE CONTRACT
========================================================

Before implementation, inspect the existing:

JobService
ApplicationService
JobRepository
ApplicationRepository
Job model
Application model

Reuse existing methods.

If a required capability already exists, use it.

If a required UI feature cannot be implemented with the existing service
contract, first determine whether a small read-only/service-layer extension
is appropriate.

DO NOT create a new database model simply to improve the UI.

DO NOT change the automation engine for UI convenience.

========================================================
38. IMPORTANT STATUS SEMANTICS
========================================================

Keep job state and application state conceptually separate.

A job can be:

Active
Inactive

An application can be:

Not Applied
Applying
Submitted
Skipped
Failed
Rejected
etc.

Do not turn job status into application status.

Display them in the appropriate places.

========================================================
39. PLATFORM-SPECIFIC ACTIONS
========================================================

Never hardcode actions based only on the current selected tab.

Actions must use the selected job's actual platform + method + URLs.

Example:

LinkedIn + Easy Apply
→ Open LinkedIn

Naukri + Company Portal
→ Open Naukri / external application URL

Manual
→ Open source URL

This is critical for the current All Jobs / Easy Apply / Company Portal views.

========================================================
40. VISUAL DESIGN RULE
========================================================

The final page should NOT look like:

"dark table + orange buttons."

It should look like:

"modern professional ATS data workspace."

Use:

- generous but efficient spacing
- clear hierarchy
- subtle surfaces
- professional typography
- restrained color
- compact badges
- clean table
- excellent filtering
- strong selected state
- polished detail panel

Avoid:
- excessive cards
- excessive borders
- huge blank spaces
- giant buttons
- neon colors
- excessive rounded containers
- unnecessary gradients
- decorative elements without function

========================================================
41. TESTING REQUIREMENTS
========================================================

Add/update tests for:

1. JobsView rendering
2. All Jobs tab
3. Easy Apply tab
4. Company Portal tab
5. global search
6. platform filter
7. status filter
8. method filter
9. multiple filters
10. clear filters
11. column sorting
12. column resizing
13. column visibility
14. row selection
15. detail panel updates
16. empty state
17. loading state
18. error state
19. pagination
20. platform-specific action URL
21. correct LinkedIn/Naukri action
22. light theme
23. dark theme
24. keyboard navigation
25. malformed/long text rendering
26. large dataset rendering

Do not modify existing tests simply to make them pass.

Existing functionality must remain passing.

========================================================
42. VISUAL QA
========================================================

Generate screenshots for:

1. All Jobs — dark
2. Easy Apply — dark
3. Company Portal — dark
4. All Jobs — light
5. Filters opened
6. Multiple active filters
7. Selected job
8. Empty state
9. Loading state
10. Job detail modal
11. Narrow desktop width
12. Wide desktop width

Recommended test sizes:

1920 × 1080
1600 × 900
1366 × 768

The page must remain usable at all three sizes.

========================================================
43. FINAL ACCEPTANCE CRITERIA
========================================================

The transformation is complete only when:

✓ Existing Jobs functionality still works
✓ Existing services remain the source of truth
✓ No LinkedIn/Naukri automation logic changed
✓ All Jobs / Easy Apply / Company Portal remain functional
✓ Search works
✓ Multiple filters work
✓ Column sorting works
✓ Columns resize correctly
✓ Columns can be shown/hidden
✓ Table adapts to window size
✓ Detail panel follows selected job
✓ Platform-specific actions are correct
✓ Status colors are semantic
✓ Dark theme works
✓ Light theme works
✓ Empty/loading/error states exist
✓ Pagination is usable
✓ Long job/company names remain readable
✓ No fake data
✓ No hardcoded job values
✓ No contradictory actions
✓ No UI freezing during data loading
✓ Existing regression suite passes

========================================================
FINAL DESIGN OBJECTIVE
========================================================

Transform the current Jobs page from:

"database table with a detail panel"

into:

"production-grade ATS Job Workspace."

The user should be able to sit on this screen for hours while reviewing
hundreds of jobs.

The most important UX principles are:

FIND FAST
FILTER PRECISELY
SCAN QUICKLY
SELECT EASILY
UNDERSTAND STATUS
INSPECT DETAILS
TAKE ACTION

Do not redesign the backend merely to make the UI look better.

Make the existing JobPilot functionality feel like a polished commercial ATS.
