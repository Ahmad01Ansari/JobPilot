# JOBPILOT — UNIVERSAL GLOBAL SEARCH ENGINE
# CROSS-ENTITY SEARCH + EXACT RECORD NAVIGATION

Build a production-grade Universal Search Engine for JobPilot.

This is NOT just a search box.

The goal is:

USER SEARCHES
    ↓
GLOBAL SEARCH POPUP
    ↓
SEARCH ACROSS ALL SUPPORTED JOBPILOT ENTITIES
    ↓
GROUP RESULTS BY CATEGORY
    ↓
USER CLICKS A RESULT
    ↓
NAVIGATE TO THE CORRECT PAGE
    ↓
APPLY AN EXACT RECORD FILTER / SELECTION
    ↓
SHOW ONLY THAT SPECIFIC RECORD
    ↓
HIGHLIGHT / FOCUS THE SELECTED RECORD

The user must never have to manually search for the record again.

============================================================
1. FIRST — AUDIT THE EXISTING APPLICATION
============================================================

DO NOT immediately create a new search system.

First inspect the existing JobPilot architecture.

Inspect:

- PySide6 application shell
- sidebar/navigation
- all NAV_ITEMS
- JobsView
- ApplicationsView
- CompaniesView
- ContactsView
- Outreach Center
- ResumesView
- InterviewsView
- FollowupsView
- OffersView
- Q&A / Knowledge Base
- PlatformsView
- AutomationView
- AnalyticsView
- DashboardView
- SettingsView
- relevant Services
- Repositories
- SQLAlchemy models
- database schema
- existing filters
- existing search implementations
- existing IDs/primary keys
- existing navigation mechanism
- current global shortcuts
- current Ctrl+K behavior if any

Determine which entities actually exist.

DO NOT invent entities that are not present.

Create:

UNIVERSAL SEARCH AUDIT

with:

Entity
Service
Repository
Primary ID
Searchable fields
Existing filters
Existing detail view
Existing navigation route
Existing exact-record selection mechanism

============================================================
2. CORE SEARCH ARCHITECTURE
============================================================

Create a dedicated:

GlobalSearchService

or equivalent service-layer component.

Architecture:

PySide6 Search UI
        ↓
GlobalSearchController
        ↓
GlobalSearchService
        ↓
Search Providers
        ↓
Existing Services / Repositories
        ↓
Database

IMPORTANT:

UI MUST NOT directly query SQLAlchemy models.

Do NOT create:

SearchPopup → Session.query(...)

Instead:

SearchPopup
→ GlobalSearchController
→ GlobalSearchService
→ entity search providers
→ existing repositories/services

============================================================
3. SEARCH PROVIDER ARCHITECTURE
============================================================

Do not put every entity's search logic into one giant method.

Create a provider interface similar to:

SearchProvider

Each provider handles one logical entity.

Examples:

JobSearchProvider
ApplicationSearchProvider
CompanySearchProvider
ContactSearchProvider
ResumeSearchProvider
InterviewSearchProvider
FollowUpSearchProvider
OutreachSearchProvider
PlatformSearchProvider
KnowledgeSearchProvider

Only implement providers for entities that actually exist.

Each provider should return normalized:

SearchResult

Example:

SearchResult(
    category="Jobs",
    entity_type="job",
    entity_id=123,
    title="RPA Developer",
    subtitle="ABC Technologies · Bangalore",
    description="...",
    metadata={...},
    route="jobs",
    action="open_record"
)

The UI must NOT need to understand database models.

============================================================
4. SEARCH RESULT CONTRACT
============================================================

Create a stable normalized search result.

Minimum fields:

- entity_type
- entity_id
- category
- title
- subtitle
- description
- metadata
- route
- action
- score
- matched_fields

Optional:

- icon
- status
- platform
- location
- timestamp

Example:

{
    "entity_type": "job",
    "entity_id": 4821,
    "category": "Jobs",
    "title": "RPA Developer",
    "subtitle": "ABC Technologies · Bangalore",
    "route": "jobs",
    "action": "open_record",
    "score": 0.94,
    "matched_fields": [
        "title",
        "company",
        "location"
    ]
}

Do NOT expose ORM objects to the UI.

============================================================
5. SEARCHABLE CATEGORIES
============================================================

Support the entities that actually exist in the application.

At minimum investigate:

1. Jobs
2. Applications
3. Companies
4. Contacts
5. Outreach / Conversations
6. Resumes
7. Interviews
8. Follow-ups
9. Offers
10. Platforms
11. Q&A / Knowledge Base

If an entity does not exist:

DO NOT fabricate it.

The search architecture must allow additional providers to be added later.

============================================================
6. WHAT SHOULD MATCH?
============================================================

Search must not only match the entity title.

For JOBS:

- title
- company
- location
- platform
- job ID
- source URL
- application URL
- description
- skills
- experience
- employment type
- status

For APPLICATIONS:

- job title
- company
- application ID
- platform
- status
- application method
- URL

For COMPANIES:

- company name
- domain
- industry
- location
- notes

For CONTACTS:

- name
- email
- company
- position
- phone if appropriate
- notes

For OUTREACH:

- contact
- company
- subject
- message content
- conversation status

For RESUMES:

- filename
- target role
- version
- skills
- status

For INTERVIEWS:

- company
- job
- candidate/contact
- status
- interview type

For FOLLOW-UPS:

- company
- job
- contact
- title
- status

For OFFERS:

- company
- job
- status

For Q&A:

- question
- answer
- category
- tags

============================================================
7. SEARCH BEHAVIOR
============================================================

Search should support:

- exact match
- partial match
- prefix match
- token match
- case-insensitive search
- multiple words
- whitespace normalization

Example:

"rpa developer"

should find:

"RPA Developer"

"Senior RPA Developer"

"RPA Developer — Automation"

Also:

"abc rpa"

should find records where:

company = ABC
AND
title contains RPA

where appropriate.

============================================================
8. SEARCH RANKING
============================================================

Implement deterministic relevance ranking.

Suggested priority:

1. Exact title/name match
2. Prefix title/name match
3. Exact identifier match
4. Multiple token match
5. Company match
6. Location match
7. Status/platform match
8. Description/content match

Example:

Search:

"RPA Developer"

Ranking:

RPA Developer
★★★★★

Senior RPA Developer
★★★★

Python Developer
★★

Do not use an LLM merely to rank ordinary database search results.

Use deterministic ranking first.

============================================================
9. SEARCH POPUP UI
============================================================

Create a modern global search popup.

It should feel like:

Linear / Raycast / modern ATS command center

NOT:

an old desktop dialog with a giant table.

Structure:

┌──────────────────────────────────────────────┐
│ 🔎 Search JobPilot...                     ⌘K │
├──────────────────────────────────────────────┤
│                                              │
│ Jobs                                      12 │
│ ─────────────────────────────────────────── │
│  RPA Developer                               │
│  ABC Technologies · Bangalore               │
│                                              │
│  Automation Engineer                         │
│  XYZ Ltd · Noida                             │
│                                              │
│ Applications                               3 │
│ ─────────────────────────────────────────── │
│  RPA Developer · ABC Technologies            │
│  Submitted · LinkedIn                        │
│                                              │
│ Companies                                   2 │
│ ─────────────────────────────────────────── │
│  ABC Technologies                            │
│                                              │
├──────────────────────────────────────────────┤
│ ↑↓ Navigate     Enter Open     Esc Close     │
└──────────────────────────────────────────────┘

============================================================
10. SEARCH POPUP BEHAVIOR
============================================================

When popup opens:

- focus search input automatically
- preserve previous query if appropriate
- show recent searches only when query is empty
- show useful categories
- start searching after short debounce

Do NOT execute a database query for every keystroke without debounce.

Recommended debounce:

150–250ms

Cancel previous search when a new query arrives.

Never allow stale search responses to overwrite newer results.

============================================================
11. GLOBAL KEYBOARD SHORTCUT
============================================================

Support:

Ctrl+K

or the application's existing global search shortcut.

IMPORTANT:

Inspect the existing shortcut system first.

Do not create a conflicting second Ctrl+K implementation.

Shortcut must NOT trigger while the user is actively typing inside:

- text editor
- QTextEdit
- QLineEdit
- search field
- message composer

unless intentionally designed.

============================================================
12. CATEGORY GROUPING
============================================================

Results must be grouped:

Jobs
Applications
Companies
Contacts
Outreach
Resumes
Interviews
Follow-ups
Offers
Platforms
Q&A

Only show categories containing matches.

Example:

Search: "Infosys"

Jobs (8)
Applications (3)
Company (1)
Contacts (4)
Outreach (2)

Do not show:

Resumes (0)
Interviews (0)

============================================================
13. CATEGORY RESULT LIMIT
============================================================

Do not show 500 results inside the popup.

Initially show a small number per category.

Example:

Jobs
5 results

Applications
5 results

Companies
3 results

Then:

"View all 42 Jobs"

The exact limit should be configurable.

============================================================
14. RESULT HIGHLIGHTING
============================================================

Highlight the matching part of the result.

Example:

Search:

rpa

Result:

**RPA** Developer

ABC Technologies

Do not alter stored data.

Use presentation-level highlighting.

============================================================
15. RESULT ICONS
============================================================

Each entity should have a consistent icon.

Example:

Jobs → briefcase
Applications → document/check
Companies → building
Contacts → person
Outreach → message
Resume → file
Interview → calendar
Follow-up → clock
Offer → trophy/document
Platform → globe
Q&A → question mark

Use the existing icon system/theme.

Do NOT introduce random icon libraries unless the project already uses one.

============================================================
16. RESULT STATUS
============================================================

Where useful, show compact status information.

Examples:

RPA Developer
ABC Technologies
● Submitted

Python Automation Engineer
XYZ Ltd
● Interview

Do not overload every result with badges.

Only display useful metadata.

============================================================
17. MOST IMPORTANT FEATURE:
# EXACT RECORD NAVIGATION
============================================================

Clicking a result must NOT simply open the destination page.

It must open the page AND identify the exact record.

Example:

Search:

"RPA Developer ABC Technologies"

User clicks:

RPA Developer
ABC Technologies · Bangalore

Correct behavior:

1. Close search popup.
2. Navigate to Jobs.
3. Pass exact entity ID = 4821.
4. JobsView receives navigation request.
5. JobsView loads/selects job 4821.
6. Apply exact-record filter/focus.
7. Show ONLY job 4821.
8. Highlight selected row.
9. Open its detail panel.

The user should immediately see:

RPA Developer
ABC Technologies
ID 4821

NOT:

the entire Jobs table with 100 jobs.

============================================================
18. NAVIGATION CONTRACT
============================================================

Create a centralized navigation request.

Example:

NavigationRequest(
    route="jobs",
    entity_type="job",
    entity_id=4821,
    filter_mode="exact",
    focus=True
)

or equivalent architecture.

Do NOT pass arbitrary UI instructions between views.

Example:

BAD:

open_jobs()
find_text("RPA Developer")
click_row()

GOOD:

navigate(
    route="jobs",
    entity_type="job",
    entity_id=4821,
    mode="exact"
)

============================================================
19. EXACT FILTER VS SELECTED RECORD
============================================================

There are two separate concepts:

EXACT FILTER

Only one record should appear in the list.

SELECTED RECORD

The record is highlighted/opened in the detail panel.

For global search result navigation, default to:

EXACT FILTER + SELECT

So:

Search result
↓
Jobs
↓
exact filter = job_id 4821
↓
one visible record
↓
selected
↓
detail panel open

Do not rely only on row selection.

============================================================
20. PAGE-SPECIFIC NAVIGATION ADAPTER
============================================================

Each major view should implement a predictable navigation contract.

Example:

JobsView.open_record(entity_id, exact=True)

ApplicationsView.open_record(entity_id, exact=True)

CompaniesView.open_record(entity_id, exact=True)

ContactsView.open_record(entity_id, exact=True)

OutreachView.open_conversation(entity_id)

ResumesView.open_record(entity_id)

InterviewsView.open_record(entity_id)

FollowupsView.open_record(entity_id)

OffersView.open_record(entity_id)

Do not make GlobalSearchService know how each UI works.

============================================================
21. DEEP-LINK ROUTING
============================================================

Create a central:

AppNavigator

or use the existing navigation architecture.

It should understand:

route
entity_type
entity_id
mode
optional filter parameters

Example:

AppNavigator.open(
    route="jobs",
    entity_id=4821,
    mode="exact"
)

Then:

AppNavigator
→ activate JobsView
→ JobsView.open_record(4821, exact=True)

============================================================
22. RECORD NOT FOUND
============================================================

If a search result refers to a record that was deleted between:

SEARCH
and
CLICK

do not crash.

Show:

"Record no longer exists."

Offer:

[Search Again]

If record exists but cannot be loaded:

show a proper error state.

============================================================
23. EXACT FILTER MUST BE DATABASE-BACKED
============================================================

Do NOT implement exact filtering by:

loading all records
+
filtering in Python/UI

Use existing service/repository filters.

Example:

JobService.get(job_id)

or:

JobService.list(JobFilter(job_id=4821))

depending on the actual architecture.

For large datasets:

database-side filtering is mandatory.

============================================================
24. CLEAR EXACT SEARCH STATE
============================================================

When the user navigates to a record via global search:

show a compact filter chip:

┌──────────────────────────────┐
│ Exact record: RPA Developer ×│
└──────────────────────────────┘

User can click × to return to the normal list.

Example:

Jobs

[Exact: RPA Developer — ABC Technologies ×]

1 result

This makes it obvious why only one record is visible.

============================================================
25. BACK NAVIGATION
============================================================

If user:

Ctrl+K
→ searches
→ opens Job

then pressing Back / navigation should behave naturally.

Do not leave the user trapped in exact-filter mode.

Preserve previous page/filter state where practical.

Example:

Jobs page had:

Status = Submitted
Platform = LinkedIn

Then global search opened another job.

When user exits exact mode:

restore previous Jobs filters if architecture supports it.

============================================================
26. SEARCH RESULT → SPECIFIC RECORD EXAMPLES
============================================================

Example 1:

Search:

"RPA Developer"

Click job.

Result:

Jobs
Exact filter:
job_id=123

1 record.

------------------------------------------------

Example 2:

Search:

"ABC Technologies"

Click company.

Result:

Companies
Exact filter:
company_id=45

1 record.

------------------------------------------------

Example 3:

Search:

"RPA Developer ABC"

Click application.

Result:

Applications
Exact filter:
application_id=789

1 record.

------------------------------------------------

Example 4:

Search:

"Rahul Sharma"

Click contact.

Result:

Outreach / Contacts
Exact record:
contact_id=22

1 record.

------------------------------------------------

Example 5:

Search:

"resume v3"

Click resume.

Result:

Resumes
Exact record:
resume_id=15

============================================================
27. CROSS-ENTITY AMBIGUITY
============================================================

Suppose:

"ABC Technologies"

matches:

Company
Job
Application
Contact
Outreach

Do NOT merge them into one ambiguous result.

Show categories.

Example:

ABC Technologies

Companies
  ABC Technologies

Jobs
  RPA Developer — ABC Technologies
  Python Developer — ABC Technologies

Applications
  RPA Developer — ABC Technologies

Contacts
  Rahul Sharma — ABC Technologies

============================================================
28. EXACT IDENTIFIER SEARCH
============================================================

If user enters:

application ID
job ID
resume ID
database ID
platform job ID

prioritize exact identifier match.

Example:

"JOB-4821"

should immediately surface:

Jobs
RPA Developer — ABC Technologies

with very high ranking.

============================================================
29. SEARCH EMPTY STATE
============================================================

When query has no results:

┌──────────────────────────────────────────┐
│ 🔎 xyzabc                                │
│                                          │
│ No results found                         │
│                                          │
│ Try searching for a job title, company, │
│ contact, application, resume or ID.      │
└──────────────────────────────────────────┘

Do not show fake recommendations.

============================================================
30. SEARCH EMPTY QUERY
============================================================

When popup opens with no query:

Show useful content such as:

Recent searches

or:

Quick navigation:

Jobs
Applications
Companies
Contacts
Outreach
Resumes

Use actual application state.

Do not fabricate recent searches.

Persist recent searches only if useful.

============================================================
31. PERFORMANCE
============================================================

Search must remain responsive.

Do NOT:

- load the entire database
- instantiate every ORM record
- run every provider sequentially on the UI thread
- execute expensive AI calls for every query

Use:

- indexed fields
- bounded result limits
- debouncing
- service/repository queries
- asynchronous/background work where appropriate

PySide6 main thread must remain responsive.

============================================================
32. SEARCH INDEX
============================================================

First determine whether current dataset size requires an index.

For a local SQLite database, start with optimized SQL queries and indexes.

Potential indexes:

jobs.title
jobs.company_id
jobs.platform_id
applications.status
companies.name
contacts.name
contacts.email
resumes.name

Only add indexes that are supported by the actual schema.

Do not create a complex external search engine unnecessarily.

Build a pluggable SearchProvider architecture so full-text search can
be added later if needed.

============================================================
33. NO LLM REQUIRED FOR BASIC SEARCH
============================================================

Do NOT use an LLM for:

- normal keyword search
- result ranking
- exact record identification
- navigation

The universal search engine must work offline/local.

AI-powered semantic search can be a future enhancement.

For V1:

deterministic search first.

============================================================
34. SEARCH RESULT ACTIONS
============================================================

Each result may support:

Enter
Click
Double-click

Primary action:

OPEN

Optional secondary actions:

- Open external URL
- View details
- Copy ID

But keep the popup clean.

============================================================
35. KEYBOARD NAVIGATION
============================================================

Support:

↑
↓
Enter
Esc

Optional:

Tab
Shift+Tab

Enter opens highlighted result.

Esc closes popup.

Do not trigger unrelated application shortcuts while search popup is active.

============================================================
36. SEARCH POPUP MUST NOT DESTROY EXISTING UI STATE
============================================================

Opening search should be non-destructive.

When closed without selecting:

previous page remains exactly as it was.

Do not reload the entire application.

============================================================
37. THEME
============================================================

Use the existing JobPilot semantic theme system.

Support:

Dark
Light

Do NOT hardcode a second independent color system.

Search popup should match the existing modern ATS/SaaS visual language.

Avoid:

- excessive borders
- giant cards
- old desktop-dialog appearance
- oversized category headers

Use:

- compact spacing
- subtle surface
- strong typography
- keyboard-first interaction
- clear selected state

============================================================
38. ACCESSIBILITY
============================================================

Search results must expose:

- category
- title
- subtitle
- selected state

Keyboard navigation must work without mouse.

Search field must have accessible label.

============================================================
39. TESTING
============================================================

Create unit tests for:

- exact match
- partial match
- multi-token search
- case-insensitive search
- ranking
- category grouping
- result limits
- entity IDs
- duplicate results
- exact identifier match
- empty results
- stale/deleted records

Create navigation tests for:

Search Job
→ JobsView
→ exact job ID
→ one record visible
→ selected

Search Application
→ ApplicationsView
→ exact application ID

Search Company
→ CompaniesView
→ exact company ID

Search Contact
→ ContactsView
→ exact contact ID

Search Resume
→ ResumesView
→ exact resume ID

============================================================
40. CRITICAL NAVIGATION TEST
============================================================

This exact scenario MUST be tested:

1. Open Jobs page.
2. Have 100 jobs in database.
3. Press Ctrl+K.
4. Search "RPA Developer".
5. Select a specific ABC Technologies result.
6. Popup closes.
7. Jobs page opens.
8. Exact job ID is passed.
9. Jobs page applies exact filter.
10. Only ONE job is visible.
11. Correct row is selected.
12. Detail panel shows ABC Technologies.
13. No LinkedIn/Naukri/other unrelated record is shown.
14. Clearing exact filter returns to normal Jobs list.

============================================================
41. IMPORTANT — DO NOT CONFUSE TEXT SEARCH WITH EXACT NAVIGATION
============================================================

The search result must carry the actual database entity ID.

BAD:

Search result:
"RPA Developer"

Click:
JobsView.search("RPA Developer")

This can show 30 jobs.

GOOD:

Search result:
entity_type = "job"
entity_id = 4821

Click:
AppNavigator.open(
    route="jobs",
    entity_id=4821,
    mode="exact"
)

Result:

1 exact record.

============================================================
42. SEARCH PROVIDER RESULT IDs ARE MANDATORY
============================================================

Every result MUST contain a stable entity ID.

Never create a result with only:

title
subtitle

because that makes exact navigation unreliable.

Required:

entity_type
entity_id
route

============================================================
43. HANDLE DUPLICATE TITLES
============================================================

There may be:

RPA Developer — ABC
RPA Developer — XYZ
RPA Developer — ABC

Never identify a result by title alone.

Use:

entity_id

for identity.

Display enough metadata to distinguish them.

============================================================
44. SEARCH RESULT → EXTERNAL LINK
============================================================

If a result represents a platform/job external page:

keep the internal record identity AND external URL.

Example:

entity_id = 4821
external_url = ...

Clicking the result should normally open the JobPilot record first.

Provide external-open as a secondary action where appropriate.

Do not lose the internal record context.

============================================================
45. GLOBAL SEARCH SHOULD BE EXTENSIBLE
============================================================

Adding a new entity later should require:

1. SearchProvider
2. registration
3. navigation adapter

NOT rewriting:

GlobalSearchService
SearchPopup
AppNavigator

============================================================
46. IMPLEMENTATION ORDER
============================================================

PHASE 0
Audit current navigation and entity architecture.

PHASE 1
Define SearchResult and SearchProvider contracts.

PHASE 2
Implement GlobalSearchService.

PHASE 3
Implement entity search providers.

PHASE 4
Implement ranking/grouping.

PHASE 5
Implement SearchPopup UI.

PHASE 6
Implement Ctrl+K/global shortcut.

PHASE 7
Implement AppNavigator integration.

PHASE 8
Implement exact-record navigation for Jobs.

PHASE 9
Implement exact-record navigation for Applications.

PHASE 10
Implement remaining entity navigation.

PHASE 11
Implement exact-filter chips + state restoration.

PHASE 12
Performance optimization/indexing.

PHASE 13
Testing/regression.

============================================================
47. IMPORTANT — DO NOT BREAK EXISTING SEARCH/FILTERS
============================================================

Global Search is an additional entry point.

Do NOT replace:

- Jobs filters
- Applications filters
- Outreach search
- Resume filters
- Analytics filters

unless explicitly required.

Global Search should navigate INTO existing views.

Do not create duplicate versions of existing page logic.

============================================================
48. ACCEPTANCE CRITERIA
============================================================

The feature is complete only when:

[ ] Ctrl+K opens global search.
[ ] Search is responsive.
[ ] Results come from real database data.
[ ] Results are grouped by entity.
[ ] Search supports multiple words.
[ ] Search ranking is deterministic.
[ ] Every result has entity_type + entity_id.
[ ] Every result has a valid navigation route.
[ ] Clicking a Job result opens Jobs.
[ ] The exact Job ID is selected.
[ ] Only that Job is shown.
[ ] Detail panel opens for that Job.
[ ] Clicking Application result opens exact Application.
[ ] Clicking Company opens exact Company.
[ ] Clicking Contact opens exact Contact.
[ ] Clicking Resume opens exact Resume.
[ ] Exact filter state is visible.
[ ] User can clear exact filter.
[ ] Previous page state is preserved where appropriate.
[ ] Deleted records are handled gracefully.
[ ] No fake results.
[ ] No direct UI → database queries.
[ ] Search does not block Qt main thread.
[ ] Existing filters continue working.
[ ] Existing navigation continues working.
[ ] Existing tests pass.
[ ] New search/navigation tests pass.
[ ] Dark theme works.
[ ] Light theme works.

============================================================
49. FINAL IMPLEMENTATION PRINCIPLE
============================================================

The Universal Search Engine has TWO responsibilities:

RESPONSIBILITY 1
FIND THE RIGHT RECORD.

RESPONSIBILITY 2
TAKE THE USER DIRECTLY TO THAT EXACT RECORD.

Do not consider the feature complete if only responsibility #1 works.

The defining behavior is:

SEARCH
→ RESULT
→ CLICK
→ CORRECT PAGE
→ EXACT ENTITY ID
→ EXACT FILTER
→ EXACT RECORD
→ DETAIL VIEW

NOT:

SEARCH
→ RESULT
→ OPEN PAGE
→ USER SEARCHES AGAIN

That second behavior is NOT acceptable.

============================================================
50. FINAL INSTRUCTION TO THE AI AGENT
============================================================

First perform the repository audit.

Then produce:

1. Existing entity/search architecture
2. Existing navigation architecture
3. Missing capabilities
4. SearchProvider design
5. GlobalSearchService design
6. SearchResult contract
7. AppNavigator integration
8. Exact-record filtering strategy for each view
9. UI design
10. Performance strategy
11. Test plan
12. Files to modify
13. Files to add

STOP after the plan.

Wait for explicit approval before implementation.

After approval, implement incrementally and run the regression suite
after every major phase.

Do not rewrite unrelated features.
Do not invent database fields.
Do not fabricate search results.
Do not use an LLM for basic search.
Do not break existing page filters.

The final user experience must feel like:

"Search anything in JobPilot → click it → I'm immediately looking at
that exact record."