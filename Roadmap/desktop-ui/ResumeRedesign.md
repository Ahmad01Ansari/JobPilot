You are working on the JobPilot desktop application.

The current Resume Management page is functional but extremely
minimal. It currently displays uploaded resume files in a table with:

    Name
    Target Role
    Version
    Status
    Integrity
    Actions

It also shows:

    Total Resumes
    Default Resume
    Storage Location
    Upload Resume

The current page behaves mostly like a PDF/file manager.

Your task is to redesign it into a modern, production-quality
RESUME MANAGEMENT + RESUME INTELLIGENCE workspace.

IMPORTANT:

Do NOT turn this into a generic document manager.

The purpose of this page is to help JobPilot answer:

    Which resume should I use?

    Which role is this resume targeting?

    Is this resume complete and usable?

    Which platforms/applications use this resume?

    Which resume is the default?

    What versions exist?

    Is the PDF valid?

    What skills/experience does this resume contain?

    Which jobs/roles does this resume match?

    Can I preview, compare, duplicate, archive, or assign it?

The page must remain integrated with the existing JobPilot
ResumeManager and automation architecture.

Do not rewrite existing automation.

============================================================
1. FIRST — AUDIT THE EXISTING RESUME SYSTEM
============================================================

Before changing UI, inspect the repository.

Inspect:

    ResumeService
    ResumeManager
    resume models
    resume repository
    managed_resumes/
    profile configuration
    Application model
    Job model
    platform configuration
    QnA Engine
    qualification engine
    existing resume upload logic
    existing PDF validation
    existing role matching logic
    existing theme system
    existing design system
    existing dialogs/modals

Determine:

1. What resume metadata already exists.
2. How resumes are stored.
3. How default resume is determined.
4. How target role is stored.
5. How version is stored.
6. How integrity is calculated.
7. How resume files are validated.
8. Whether text extraction already exists.
9. Whether resume parsing already exists.
10. Whether resume usage is tracked.
11. Whether applications reference a resume.
12. Whether multiple resumes can exist for one role.
13. Whether archive/delete is already supported.
14. Which features require backend changes.

DO NOT invent a second ResumeManager.

Reuse existing services and repositories.

============================================================
2. CORE PRODUCT DIRECTION
============================================================

The redesigned page should feel like:

    Modern ATS Resume Workspace

not:

    File Explorer
    PDF folder
    Basic CRUD table

Visual inspiration:

    modern SaaS
    ATS platforms
    Linear/Vercel-style information density
    professional recruitment software

Keep the existing JobPilot design language:

    dark Obsidian canvas
    subtle borders
    restrained orange accent
    compact typography
    clear hierarchy
    dark + light theme

Do NOT solve "modern UI" by adding:

    huge cards
    gradients everywhere
    excessive borders
    giant empty containers
    unnecessary decorative elements

============================================================
3. TARGET PAGE STRUCTURE
============================================================

Use this general structure:

------------------------------------------------------------
HEADER
------------------------------------------------------------

Resume Management

Manage targeted resumes, versions, resume health, and
application assignments.

                         [ + Upload Resume ]

------------------------------------------------------------
SUMMARY / RESUME HEALTH
------------------------------------------------------------

    3 Resumes       1 Default       2 Role-targeted
    100% Verified   12 Applications  Last updated 2h ago

Do NOT show metrics that cannot be calculated from real data.

------------------------------------------------------------
TOOLBAR
------------------------------------------------------------

[ Search resumes... ]

[ All Roles ▾ ]
[ All Status ▾ ]
[ All Versions ▾ ]

[ Grid ] [ List ]

[ Sort ▾ ]

------------------------------------------------------------
RESUME WORKSPACE
------------------------------------------------------------

Prefer a rich resume list/grid rather than the current huge
empty table.

Each resume should expose useful information immediately.

------------------------------------------------------------
DETAIL / PREVIEW
------------------------------------------------------------

Selecting a resume opens a contextual preview/detail panel.

Do not require opening an external PDF viewer for every action.

============================================================
4. RESUME CARD / ROW DESIGN
============================================================

Each resume item should show:

    Resume name
    Target role
    Version
    Status
    Default indicator
    Integrity
    Last modified
    File type / size
    Optional page count
    Optional extracted skill count

Example:

    ┌───────────────────────────────────────────────┐
    │  RPA Developer Resume                     ⋮  │
    │                                               │
    │  RPA Developer                                │
    │  v2.1   PDF   2 pages                         │
    │                                               │
    │  ● Verified      ★ Default                    │
    │                                               │
    │  Updated 2 days ago                           │
    │                                               │
    │  Python · SQL · Automation Anywhere · UiPath  │
    │                                               │
    │  [Preview] [Use for Applications]             │
    └───────────────────────────────────────────────┘

Do NOT display every possible metadata field if it makes the
card cluttered.

Prioritize:

    Role
    Version
    Status
    Default
    Updated
    Key skills

============================================================
5. RESUME PREVIEW
============================================================

This is a major missing feature.

Selecting a resume should open a detail/preview workspace.

Layout:

    LEFT:
        Resume information

    CENTER:
        PDF/document preview

    RIGHT:
        Resume intelligence

Example:

    Resume
    RPA Developer Resume

    Target Role
    RPA Developer

    Version
    2.1

    Status
    Verified

    Default
    Yes

    File
    PDF · 2 pages

Then:

    [ Open PDF ]
    [ Set as Default ]
    [ Duplicate ]
    [ Edit Metadata ]
    [ Archive ]

Do not automatically open an external browser/application.

If native PDF rendering already exists, reuse it.

If it does not exist, first determine whether an appropriate
existing dependency can be reused before introducing a new
dependency.

============================================================
6. RESUME INTELLIGENCE PANEL
============================================================

If resume text extraction is available or can be implemented
reliably, add a Resume Intelligence panel.

Show:

    Skills detected
    Experience
    Education
    Certifications
    Tools / technologies
    Target roles
    Contact completeness

Example:

    Resume Intelligence

    Skills
    ─────────────────────────────
    Python
    SQL
    Automation Anywhere
    UiPath
    Selenium
    RPA
    LLM / RAG

    Certifications
    ─────────────────────────────
    Automation Anywhere
    Google Cloud

Do NOT invent extracted information.

Only show information actually extracted from the resume.

If parsing is unavailable:

    "Resume intelligence unavailable"

rather than fake data.

============================================================
7. RESUME HEALTH / VALIDATION
============================================================

Expand the current Integrity concept.

Current:

    Verified

should become a useful Resume Health indicator.

Potential checks:

    PDF readable
    File exists
    File not corrupted
    Text extractable
    Contact information present
    Resume has meaningful content
    Target role assigned
    Version metadata valid
    File size valid
    No duplicate file detected

Example:

    Resume Health
    ──────────────────────
    ✓ PDF valid
    ✓ Text readable
    ✓ Target role assigned
    ✓ Version defined
    ⚠ No target platform assigned

Do not create an "ATS score" unless the backend has a real,
well-defined scoring algorithm.

Do not show arbitrary:

    87/100 ATS Score

without an actual explainable calculation.

============================================================
8. TARGET ROLE MANAGEMENT
============================================================

Target Role should become a first-class concept.

A resume can be:

    General
    RPA Developer
    Automation Engineer
    Python Developer
    AI Automation Engineer
    Data Scientist

Use the actual configured roles if JobPilot already has a role
configuration system.

Allow:

    assign role
    change role
    remove role
    create role if existing architecture supports it

Do not create a separate incompatible role system.

============================================================
9. ROLE-TO-RESUME MATCHING
============================================================

Add an optional:

    "Role Fit"

feature.

When a resume is selected, allow:

    Check Role Fit

Input:

    selected target role

Output:

    Matching skills
    Missing skills
    Relevant experience
    Potential gaps

Example:

    RPA Developer Fit

    Strong matches
        Python
        SQL
        Automation Anywhere
        Selenium

    Missing / not detected
        UiPath

Important:

This must be based on actual resume content and the existing
qualification/profile data.

Do not make unsupported claims.

Do not use an opaque AI score unless clearly labelled and
explainable.

============================================================
10. RESUME VERSIONING
============================================================

The current page has:

    Version 1.0

but version management is not actually useful yet.

Add proper version behavior.

Support:

    Create new version
    Duplicate resume
    Rename version
    Compare versions
    Set version as active
    Archive old version

Example:

    RPA Developer Resume

        v2.1   Active
        v2.0   Archived
        v1.0   Archived

Show:

    Created
    Modified
    Status

Do not overwrite an existing resume silently.

============================================================
11. VERSION COMPARISON
============================================================

Add:

    Compare Versions

When two versions are selected:

    Version 2.1        Version 2.0

Show:

    file metadata
    page count
    detected skills
    certifications
    target role
    modification date

If text diff is technically supported, optionally show:

    Added
    Removed
    Changed

Do not implement complex document diffing unless the underlying
resume text extraction supports it reliably.

============================================================
12. RESUME ASSIGNMENT
============================================================

This is especially important for JobPilot automation.

A resume should be assignable to:

    target role
    platform
    application strategy

For example:

    RPA Developer Resume
        ↓
    RPA Developer
        ↓
    LinkedIn
    Naukri
    Indeed
    Foundit

Potential configuration:

    Default for Role
    Default for Platform
    Default Global Resume

BUT:

Do not create conflicting defaults.

Define precedence clearly:

    Job-specific assignment
        ↓
    Role-specific resume
        ↓
    Platform-specific resume
        ↓
    Global default resume

Only implement levels that the existing backend can support
without destabilizing automation.

============================================================
13. APPLICATION USAGE
============================================================

Add a useful:

    Usage

section.

For selected resume:

    Applications using this resume
    Submitted
    In Progress
    Failed
    Last Used

If application-to-resume relationship is not currently stored,
DO NOT fake these values.

Instead:

    either add the relationship properly

or:

    mark the feature as unavailable until tracking exists.

This relationship can become very valuable later for analytics.

============================================================
14. RESUME-TO-JOB MATCH
============================================================

If existing JobPilot qualification/AI infrastructure supports it,
allow:

    "Find Matching Jobs"

for the selected resume.

Flow:

    Resume
      ↓
    Target role / skills
      ↓
    Existing Job database
      ↓
    Matching Jobs

This should reuse the existing:

    QualificationEngine

rather than creating another job matching engine.

Initially this can simply filter by:

    target role
    skills
    experience

Do not introduce an entirely new AI matching subsystem inside
ResumeView.

============================================================
15. UPLOAD EXPERIENCE
============================================================

Improve:

    Upload Resume

into a proper upload workflow.

Support:

    drag & drop
    file picker
    PDF validation
    duplicate detection
    metadata extraction
    target role assignment
    version selection
    default selection

Flow:

    Select PDF
        ↓
    Validate
        ↓
    Extract metadata
        ↓
    Detect duplicate
        ↓
    Assign target role
        ↓
    Set version
        ↓
    Preview
        ↓
    Save

Show validation errors before saving.

============================================================
16. DUPLICATE DETECTION
============================================================

Detect duplicate files using a reliable file hash.

Example:

    SHA-256

If the same PDF already exists:

    "This resume already exists."

Options:

    View existing
    Create new version
    Cancel

Do not silently create duplicates.

============================================================
17. SEARCH
============================================================

Add resume search.

Search should cover:

    name
    target role
    skills
    version
    status

Example:

    Search: RPA

returns:

    RPA Developer Resume
    RPA + AI Resume
    Automation Engineer Resume

If skills are extracted, allow skill search.

============================================================
18. FILTERS
============================================================

Useful filters:

    Target Role
    Status
    Version
    Default
    Integrity
    Recently Updated

Do not create excessive filters.

Show active filters as compact removable chips.

============================================================
19. SORTING
============================================================

Support:

    Recently updated
    Name
    Role
    Version
    Last used
    Status

Default:

    Recently updated

if consistent with the existing UX.

============================================================
20. ACTION MENU
============================================================

Replace the tiny "..." button with a meaningful contextual menu.

Actions:

    Preview
    Edit Metadata
    Set as Default
    Duplicate
    Create Version
    Compare
    Assign Role
    Find Matching Jobs
    Archive
    Delete

Only display actions that are actually supported.

Dangerous actions:

    Delete

must require confirmation.

============================================================
21. ARCHIVE VS DELETE
============================================================

Do not immediately delete resumes that may be referenced by
applications or automation.

Prefer:

    Active
    Archived

If a resume is referenced by historical applications:

    prevent destructive deletion

or:

    warn that historical references will remain.

Do not break historical application records.

============================================================
22. DEFAULT RESUME UX
============================================================

The current top bar says:

    Default: Mohd Ahmad Raza Ansari Resume...

Improve this.

Use a clear:

    Default Resume

indicator.

When changing default:

    confirm or immediately update with clear feedback.

Ensure only one global default exists if the current model requires
that invariant.

============================================================
23. RESUME STATUS MODEL
============================================================

Inspect the existing status enum.

If necessary, support states such as:

    ACTIVE
    DEFAULT
    STANDBY
    ARCHIVED
    INVALID

Do not create duplicate status systems.

Default should ideally be represented as a property/assignment,
not necessarily as a completely separate lifecycle state.

Avoid ambiguous combinations such as:

    DEFAULT + ARCHIVED

============================================================
24. STORAGE INFORMATION
============================================================

The current page displays:

    Storage: managed_resumes/

Do not expose raw filesystem implementation details as the primary
user-facing experience.

Instead show:

    Managed Resume Storage
    2 resumes · 8.4 MB

Optionally provide:

    Open Storage Location

inside an advanced/details menu.

============================================================
25. RESUME METADATA EDITOR
============================================================

Add an Edit Metadata dialog.

Fields:

    Resume Name
    Target Role
    Version
    Description
    Tags
    Default
    Status

Optional:

    Platform assignment

Do not allow editing extracted resume text directly unless a proper
resume editor is being implemented.

This page is a management layer, not necessarily a Word processor.

============================================================
26. TAGS
============================================================

Optional useful tags:

    RPA
    Python
    AI
    Automation Anywhere
    UiPath
    Data Science

Tags should support:

    filtering
    search
    organization

Do not force tags on every resume.

============================================================
27. RESUME PREVIEW + DETAIL LAYOUT
============================================================

Preferred desktop layout:

┌──────────────────────────────────────────────────────────────┐
│ Resume Management                              [+ Upload]    │
│ Manage targeted resumes and versions                         │
├──────────────────────────────────────────────────────────────┤
│ 3 Resumes   1 Default   2 Targeted   100% Verified           │
├──────────────────────────────────────────────────────────────┤
│ [ Search... ] [ Role ▾ ] [ Status ▾ ] [ Sort ▾ ] [Grid/List] │
├──────────────────────────────┬───────────────────────────────┤
│ RESUME LIBRARY               │ SELECTED RESUME              │
│                              │                               │
│ ┌──────────────────────────┐ │ RPA Developer Resume         │
│ │ RPA Developer Resume  ⋮ │ │                               │
│ │ RPA Developer            │ │ [PDF Preview]                │
│ │ v2.1  ● Verified ★       │ │                               │
│ │ Python · SQL · UiPath    │ │                               │
│ │ Updated 2 days ago       │ │                               │
│ └──────────────────────────┘ │                               │
│                              │ Target Role: RPA Developer    │
│ ┌──────────────────────────┐ │ Version: 2.1                 │
│ │ General Resume        ⋮  │ │ Status: Active               │
│ │ General                  │ │ Integrity: Verified           │
│ │ v1.0                     │ │                               │
│ └──────────────────────────┘ │ Skills                       │
│                              │ Python · SQL · RPA            │
│                              │                               │
│                              │ [Edit] [Duplicate] [Archive] │
└──────────────────────────────┴───────────────────────────────┘

Do not make the preview panel permanently consume half the screen
if no resume is selected.

Use:

    list/grid → detail panel

and responsive resizing.

============================================================
28. EMPTY STATE
============================================================

If no resumes exist:

    No resumes yet

    Upload your first resume to use it for automated applications.

    [ Upload Resume ]

Do not show an empty giant table.

============================================================
29. LOADING STATE
============================================================

Use compact skeleton/loading states.

Do not freeze the UI while:

    parsing PDF
    calculating integrity
    extracting metadata

Long-running processing must not run on the Qt main thread.

============================================================
30. BACKGROUND PROCESSING
============================================================

PDF parsing, text extraction, hashing, and AI-based resume analysis
must not block the UI.

Use the existing worker/thread/service architecture.

UI:

    Uploading...
    Parsing...
    Verifying...
    Ready

Do not create a new threading architecture if an existing worker
system already exists.

============================================================
31. SECURITY
============================================================

Resume files contain sensitive personal information.

Do not:

    log resume text
    log extracted personal information
    send resume content to an external AI provider without explicit
    configuration/consent
    expose resume filesystem paths unnecessarily

When using AI resume analysis:

    respect existing AI provider configuration
    sanitize logs
    clearly identify when external processing occurs

============================================================
32. AI FEATURES — OPTIONAL AND CONTROLLED
============================================================

Potential advanced features:

    Resume summary
    Skill extraction
    Role fit analysis
    Missing skill analysis
    Resume improvement suggestions
    Job-to-resume matching

BUT:

Do not implement these as fake AI features.

Use the existing AI infrastructure if available.

Do not call an LLM for simple deterministic tasks.

Use:

    PDF/text extraction
        ↓
    deterministic parsing
        ↓
    AI only when useful

Any AI-generated result must be labelled accordingly.

============================================================
33. ATS SCORE WARNING
============================================================

Do NOT add a generic:

    ATS Score: 92%

unless there is an actual transparent scoring system.

An arbitrary AI-generated score is not useful.

If implementing resume health, prefer explainable signals:

    ✓ Contact information
    ✓ Skills detected
    ✓ Experience detected
    ✓ Target role assigned
    ✓ PDF readable

This is more trustworthy.

============================================================
34. ANALYTICS INTEGRATION
============================================================

Prepare the architecture for future resume analytics.

Potential metrics:

    Applications using resume
    Response rate by resume
    Interview rate by resume
    Last used
    Most used resume
    Role-specific performance

BUT:

Only show these if application records actually reference the resume.

Do not retrofit fake relationships.

If resume_id is not currently stored on Application:

    assess whether adding this relationship is appropriate

before implementing resume performance analytics.

============================================================
35. DESIGN SYSTEM
============================================================

Use existing JobPilot ThemeManager.

Do NOT hard-code colors.

Dark theme:

    Obsidian background
    elevated surfaces
    subtle borders
    white primary text
    muted gray secondary text
    orange accent

Light theme:

    light canvas
    subtle gray borders
    dark text
    same orange accent

All components must support both themes.

Avoid:

    excessive orange
    gradients
    glowing cards
    oversized pills
    thick borders

============================================================
36. TABLE / LIST MODE
============================================================

If keeping a list/table mode, improve columns.

Recommended:

    Resume
    Target Role
    Version
    Status
    Integrity
    Last Modified
    Last Used
    Applications
    Actions

Only show:

    Last Used
    Applications

if backed by real data.

Keep rows compact.

Allow sorting.

============================================================
37. GRID MODE
============================================================

Grid mode should be useful for visual resume management.

Each card:

    filename/name
    role
    version
    status
    health
    key skills
    updated date
    actions

Do not create huge cards.

Use 2–3 columns depending on available width.

============================================================
38. KEYBOARD / ACCESSIBILITY
============================================================

Support:

    keyboard navigation
    Enter → preview selected resume
    Delete → confirmation
    Escape → close detail panel/dialog
    visible focus state
    accessible action labels

Do not make icon-only buttons without tooltips.

============================================================
39. PERFORMANCE
============================================================

Do not parse every PDF every time the page opens.

Store reusable metadata where appropriate.

Use:

    file hash
    modification timestamp
    cached metadata

to determine whether reparsing is required.

The page should load quickly even with many resumes.

============================================================
40. TESTING
============================================================

Add/update tests for:

UPLOAD:

    valid PDF
    invalid PDF
    duplicate PDF
    missing file
    large file

METADATA:

    create
    edit
    rename
    target role
    version

DEFAULT:

    set default
    replace default
    only one default

VERSIONING:

    duplicate
    create version
    archive old version

INTEGRITY:

    valid
    corrupted
    missing file

SEARCH/FILTER:

    name
    role
    status
    tags

PREVIEW:

    selected resume
    no selection
    missing file

DELETE/ARCHIVE:

    confirmation
    referenced resume protection

THEME:

    dark
    light

PERFORMANCE:

    multiple resumes
    cached metadata
    no repeated parsing

If resume-to-application tracking is implemented:

    usage count
    last used
    application association

============================================================
41. DO NOT BREAK EXISTING RESUME AUTOMATION
============================================================

This is critical.

Existing automation expects the ResumeManager to continue working.

Do NOT change:

    resume file paths
    resume selection behavior
    automation resume resolution

unless absolutely necessary.

If backend changes are required:

    preserve backward compatibility.

The UI redesign must sit on top of the existing resume architecture.

============================================================
42. IMPLEMENTATION PHASES
============================================================

Implement in this order:

PHASE 1 — Audit
    inspect current resume architecture

PHASE 2 — Resume library redesign
    search
    filter
    list/grid
    improved metadata

PHASE 3 — Detail / Preview
    PDF preview
    metadata panel
    actions

PHASE 4 — Resume health
    validation
    integrity
    metadata extraction

PHASE 5 — Version management
    duplicate
    version
    archive
    compare

PHASE 6 — Role targeting
    target role
    assignment

PHASE 7 — Upload workflow
    validation
    duplicate detection
    metadata
    preview

PHASE 8 — Optional Resume Intelligence
    only if existing extraction/AI infrastructure supports it

PHASE 9 — Application integration
    usage tracking
    resume-to-application association
    only if backend supports it

PHASE 10 — Testing
    complete regression suite

============================================================
43. IMPORTANT: DON'T OVERBUILD
============================================================

The first version must prioritize:

    1. Better resume library
    2. Preview
    3. Metadata
    4. Role targeting
    5. Version management
    6. Integrity/health
    7. Search/filter
    8. Better upload workflow

Then add:

    Resume Intelligence
    Role Fit
    Job Matching
    Application Usage Analytics

only after the foundation is stable.

Do not build a full resume editor.

============================================================
44. FINAL ACCEPTANCE CRITERIA
============================================================

[ ] Resume page no longer feels like a PDF file list
[ ] Modern ATS/SaaS visual design
[ ] Dark theme
[ ] Light theme
[ ] Search
[ ] Filters
[ ] Sorting
[ ] List/Grid
[ ] Resume preview
[ ] Detail panel
[ ] Metadata editing
[ ] Target role management
[ ] Default resume management
[ ] Version management
[ ] Duplicate detection
[ ] Archive support
[ ] Resume health/integrity
[ ] Improved upload workflow
[ ] Empty state
[ ] Loading state
[ ] Error state
[ ] Background PDF processing
[ ] No UI blocking
[ ] No fake ATS score
[ ] No fake AI data
[ ] Existing ResumeManager remains compatible
[ ] Existing automation remains functional
[ ] Dark/light themes verified
[ ] Tests pass

============================================================
45. FINAL IMPLEMENTATION REPORT
============================================================

After implementation report:

1. Files created
2. Files modified
3. Existing services reused
4. Backend changes
5. UI changes
6. Resume metadata changes
7. Versioning implementation
8. Preview implementation
9. Health/integrity implementation
10. AI features implemented, if any
11. Features intentionally deferred
12. Tests added
13. Full test result
14. Any limitations

Do not claim features are implemented unless they actually work.

START BY AUDITING THE EXISTING RESUME ARCHITECTURE.

Do not start coding immediately.