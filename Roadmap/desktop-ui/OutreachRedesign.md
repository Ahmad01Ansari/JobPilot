You are continuing development of the existing JobPilot desktop application.

The Outreach Center functionality already exists and includes:

    - Direct recruiter outreach
    - Email sending
    - Resume attachment
    - Email templates
    - AI pitch generation
    - Follow-up cadence
    - Inbound email synchronization
    - Recruiter response tracking
    - Threaded replies
    - Communication timeline
    - Follow-up pause/resume
    - AI response classification
    - Application linking
    - Email analytics

DO NOT rebuild these backend capabilities.

The current problem is primarily UX/UI.

The current Outreach Center looks like a basic PySide6 form rather than
a modern ATS + Gmail-style communication workspace.

Redesign the UI so the feature feels like:

    Gmail
    +
    modern ATS
    +
    recruitment CRM
    +
    AI copilot
    +
    desktop productivity application

Do NOT literally clone Gmail.

The goal is a JobPilot-native recruitment communication workspace.

============================================================
0. CRITICAL RULE — AUDIT BEFORE CHANGING
============================================================

Before modifying UI code:

Inspect the existing implementation and identify:

    OutreachView
    NewOutreachDialog
    OutreachService
    OutreachDispatcher
    FollowUpScheduler
    InboundSyncService
    EmailProvider
    Communication model
    Application model
    Contact model
    Resume model
    EmailTemplate model
    NotificationService
    existing theme system
    existing navigation system
    existing AI service
    existing worker/QThread architecture

Determine which functionality already works.

DO NOT recreate existing backend functionality just to support the
new UI.

The UI must consume the existing service layer.

Architecture remains:

    UI
      ↓
    Service
      ↓
    Repository
      ↓
    Database

Never:

    UI
      ↓
    direct SQL

============================================================
1. CURRENT UI PROBLEMS TO FIX
============================================================

The current UI has several problems.

PROBLEM 1:

The main page is too rigid.

Current layout resembles:

    KPI cards
    ↓
    left list
    right giant bordered panel

Make the hierarchy more fluid.

PROBLEM 2:

The Direct Outreach modal is too form-heavy.

Current:

    Company
    Position
    Recruiter
    Email
    Resume
    Template
    Subject
    Body
    Cadence

This feels like an old enterprise form.

Replace it with a modern email composer.

PROBLEM 3:

Too many nested borders.

Reduce:

    cards
    rectangular containers
    unnecessary outlines
    heavy separators

Use:

    whitespace
    typography
    subtle surfaces
    restrained borders

PROBLEM 4:

The conversation area does not feel like a conversation.

It should visually resemble an actual professional communication thread.

PROBLEM 5:

AI is treated as a single "Generate Pitch" button.

AI should become a contextual assistant inside the composer and
conversation workspace.

PROBLEM 6:

Important recruitment context is hidden.

The user should immediately understand:

    Company
    Job
    Recruiter
    Application status
    Resume used
    Last contact
    Next follow-up
    Response status

without opening multiple pages.

============================================================
2. NEW OUTREACH CENTER INFORMATION ARCHITECTURE
============================================================

Redesign the page around three logical areas:

    TOP
    global controls / summary

    LEFT
    conversation/application inbox

    CENTER
    conversation timeline / email workspace

    RIGHT
    recruitment context / AI / follow-up intelligence

Concept:

┌─────────────────────────────────────────────────────────────────┐
│ Outreach                         Search       Sync     + New     │
├─────────────────────────────────────────────────────────────────┤
│ 12 Outreach   5 Waiting   3 Replies   2 Actions   4 Followups │
├───────────────┬───────────────────────────────┬─────────────────┤
│ CONVERSATIONS │ CONVERSATION                  │ CONTEXT         │
│               │                               │                 │
│ ABC Corp      │ Recruiter conversation        │ RPA Developer   │
│ RPA Developer │                               │ ABC Corp        │
│ Replied       │ Recruiter                    │                 │
│               │ Hi Ahmad,...                  │ Application     │
│ XYZ Ltd       │                               │ Submitted       │
│ Waiting       │ You                           │                 │
│               │ Thank you...                  │                 │
│ Acme          │                               │ Resume          │
│ Follow-up     │ ─────────────────────────     │ RPA v2.1        │
│ due           │ Reply composer                │                 │
│               │                               │ Next follow-up  │
│               │                               │ Oct 2           │
└───────────────┴───────────────────────────────┴─────────────────┘

Do not force the exact three-column width.

Allow the center conversation area to dominate the screen.

The right panel can collapse.

============================================================
3. TOP HEADER
============================================================

Replace the current large static header with a compact command header.

LEFT:

    Outreach

    Recruiter communication and application follow-up

CENTER/RIGHT:

    Search
    Sync
    Filters
    [+ New Outreach]

Optional:

    ⋮ More

Do not make every action a large button.

Primary action:

    + New Outreach

Secondary actions:

    Sync
    Search
    Filter

Use icons + tooltips where appropriate.

============================================================
4. KPI STRIP — MAKE IT SUBTLE
============================================================

Keep useful metrics but reduce the "four giant cards" appearance.

Show compact metrics:

    12
    Outreached

    5
    Waiting

    3
    Replied

    2
    Needs Action

    4
    Follow-ups

These should feel like an analytics strip, not dashboard cards.

Clicking a metric should filter the conversation list.

Example:

    Click "Needs Action"
        ↓
    automatically activates Action filter.

============================================================
5. LEFT CONVERSATION INBOX
============================================================

The left side should feel like a modern email/recruitment inbox.

Each conversation row should show:

    Company
    Job title
    Recruiter name
    Last activity
    Status
    Next action

Example:

    ABC Technologies
    RPA Developer

    Sarah Jenkins
    Recruiter replied 2h ago

    [INTERVIEW REQUEST]

Another:

    Infosys
    Automation Developer

    Waiting for response
    Follow-up due tomorrow

Do NOT display unnecessary information.

Use typography hierarchy rather than multiple boxes.

============================================================
6. CONVERSATION ROW STATES
============================================================

Support visual states:

    Waiting
    Replied
    Needs Action
    Follow-up Due
    Scheduled
    Completed
    Paused

Semantic colors should be subtle.

Do not use bright saturated backgrounds everywhere.

Use:

    colored dot
    small badge
    accent border
    icon

instead of giant colored boxes.

============================================================
7. SEARCH
============================================================

Create a proper global Outreach search.

Search:

    company
    job title
    recruiter
    email
    subject
    message content if supported
    application ID

Debounce search.

Add keyboard shortcut:

    Ctrl/Cmd + K

if the existing application supports command shortcuts.

============================================================
8. FILTER SYSTEM
============================================================

Replace the current basic:

    All
    Waiting
    Replied
    Action

with:

    All
    Needs Action
    Waiting
    Replied
    Follow-up Due
    Scheduled
    Paused
    Completed

Additional filter menu:

    Company
    Platform
    Application Method
    Date Range
    Recruiter
    Resume
    Recruitment Status

Do not permanently display all filters.

Use:

    Filters ▾

with active filter chips below.

============================================================
9. CONVERSATION VIEW
============================================================

The center should become the primary workspace.

Header:

    ABC Technologies
    RPA Developer

    Sarah Jenkins
    Senior Technical Recruiter

Actions:

    Reply
    Schedule Follow-up
    Pause Follow-ups
    Open Application
    Open Job
    More

Show current recruitment status:

    SUBMITTED
    UNDER REVIEW
    INTERVIEW
    OFFER

etc.

============================================================
10. EMAIL THREAD DESIGN
============================================================

Do not render messages as giant bordered cards.

Use a clean email-thread design.

Example:

    Sarah Jenkins
    Senior Recruiter
    Sep 28, 12:44 PM

    Hi Ahmad,

    We'd like to discuss your experience...

    [Read more]

    ─────────────────────────────

    Ahmad Raza
    Sep 28, 1:02 PM

    Thank you for reaching out...

Use:

    sender
    timestamp
    subject when relevant
    collapsed/expanded body

Collapsed messages:

    one or two preview lines

Expanded:

    full content

Newest message should be visually obvious.

============================================================
11. MESSAGE ACTIONS
============================================================

Hover/context actions:

    Reply
    Forward if supported
    Copy
    Open attachment
    View sent resume
    More

Do not overload the visible interface.

============================================================
12. RECRUITER ATTACHMENTS
============================================================

Incoming attachments should appear as modern file chips.

Example:

    📄 Interview_Invitation.pdf
    245 KB

    [Open]

or:

    📄 Technical_Assignment.docx
    18 KB

Do NOT expose raw filesystem paths.

Use existing attachment storage.

============================================================
13. SENT RESUME
============================================================

When an email was sent with a resume:

show:

    📎 RPA Developer Resume
    v2.1

    [View Sent Resume]

This must refer to the exact resume snapshot used for the send.

Do not simply open the user's current resume if it has since changed.

============================================================
14. INLINE REPLY COMPOSER
============================================================

The current:

    "Reply to Recruiter (Threaded)"

box should become much more polished.

Design:

    Reply to Sarah Jenkins

    ┌──────────────────────────────────────┐
    │                                      │
    │ Write your response...               │
    │                                      │
    │                                      │
    └──────────────────────────────────────┘

    📎 Attach
    ✨ AI
    📝 Template

    [Discard]                       [Send Reply]

Do not use an oversized modal.

Keep reply composition inside the conversation.

============================================================
15. RICHER COMPOSER
============================================================

Support where technically appropriate:

    Bold
    Italic
    Bullets
    Links
    Attach
    Template
    AI

Do not turn this into a full Word processor.

Keep it email-focused.

============================================================
16. AUTOSAVE DRAFTS
============================================================

Implement draft behavior if backend architecture supports it.

While typing:

    Saving...

then:

    Saved

If the user closes the composer accidentally:

    preserve draft

On reopening:

    Resume draft

Do not lose typed recruiter replies.

This is a high-value productivity feature.

============================================================
17. AI COPILOT
============================================================

Do NOT keep AI as only:

    "Generate Tailored Pitch"

Create an AI assistant inside the composer.

Click:

    ✨ AI

opens a compact contextual assistant.

Actions:

    Generate draft
    Make shorter
    Make more professional
    Make warmer
    Highlight relevant experience
    Answer recruiter question
    Suggest reply
    Improve grammar

AI output always goes into the editable composer.

Never auto-send AI output.

============================================================
18. AI CONTEXT AWARENESS
============================================================

AI should understand the current context:

    Job
    Company
    Recruiter
    Job description
    Candidate profile
    Selected resume
    Current conversation

For reply generation, also include relevant recent conversation
context.

Do not send unnecessary unrelated user data.

============================================================
19. AI RESPONSE INSIGHT
============================================================

When a recruiter replies, show a compact AI insight above the composer.

Example:

    ✨ Recruiter Insight

    Interview invitation detected.

    They appear to be asking for:
    • Availability
    • Notice period

    Suggested action:
    Schedule interview

    [Apply Status]
    [Draft Reply]

This should be a suggestion.

Do not silently change recruitment state.

============================================================
20. AI QUESTION EXTRACTION
============================================================

This is an important missing feature.

If recruiter asks:

    "Can you share your notice period and expected salary?"

show:

    Recruiter Questions

    Notice period       [45 days]
    Expected salary     [Not provided]

Then:

    [Draft Answer]

The answer should use verified candidate/profile data.

Never invent answers.

============================================================
21. AI REPLY DRAFTING
============================================================

If recruiter asks multiple questions:

    detect questions
    ↓
    map to known profile/Q&A data
    ↓
    show proposed answers
    ↓
    generate draft
    ↓
    user reviews
    ↓
    send

This connects Outreach with the existing Q&A knowledge system.

Do not create a second candidate knowledge base.

============================================================
22. RIGHT CONTEXT PANEL
============================================================

Add a collapsible recruitment context panel.

Sections:

    APPLICATION
    Company
    Job title
    Platform
    Application method
    Submitted date
    Current status

    CONTACT
    Recruiter
    Email
    Designation

    RESUME
    Resume name
    Version
    Target role

    FOLLOW-UP
    Next follow-up
    Sequence status

    QUICK ACTIONS
    Open Application
    Open Job
    View Resume
    View Company
    View Contact

============================================================
23. APPLICATION STATUS
============================================================

Make application state visible without dominating the UI.

Example:

    Submitted
       ↓
    Under Review
       ↓
    Recruiter Replied
       ↓
    Interview

But do NOT imply that every recruiter reply means interview.

Communication state and recruitment state remain separate.

============================================================
24. FOLLOW-UP TIMELINE
============================================================

Replace the current simple:

    Step 1
    Step 2
    Step 3

block with a compact visual timeline.

Example:

    ● Application Sent
    │ Sep 28
    │
    ├── ● Follow-up #1
    │      Oct 2
    │      Waiting
    │
    ├── ○ Follow-up #2
    │      Oct 8
    │      Scheduled
    │
    └── ○ Follow-up #3
           Oct 15
           Scheduled

If recruiter replies:

    Follow-up #1
    PAUSED
    "Recruiter replied"

Make this visually obvious.

============================================================
25. FOLLOW-UP ACTIONS
============================================================

Provide:

    Pause
    Resume
    Reschedule
    Execute Now
    Skip
    Stop Sequence

These should appear contextually.

Do not display every action permanently.

============================================================
26. SMART FOLLOW-UP INSIGHT
============================================================

Add:

    Next action

Example:

    Recruiter replied 2 hours ago.
    No follow-up required.

or:

    No response for 4 days.
    Follow-up #1 is due tomorrow.

or:

    Interview invitation detected.
    Follow-up sequence paused.

This is much more useful than simply displaying:

    Follow-up due.

============================================================
27. NEW OUTREACH — REPLACE CURRENT RIGID MODAL
============================================================

The current Direct Recruiter Outreach dialog is too rigid.

Do NOT use a long vertical form.

Replace it with a modern composer workspace.

Suggested layout:

┌──────────────────────────────────────────────────────────────┐
│ New Outreach                                      ×          │
│ Start a recruiter conversation                               │
├──────────────────────────────────────────────────────────────┤
│ JOB CONTEXT                                                  │
│                                                              │
│ Search job...                                                │
│                                                              │
│ ABC Technologies · RPA Developer                             │
│                                                              │
│ CONTACT                                                      │
│ Sarah Jenkins                             sarah@abc.com      │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ MESSAGE                                                      │
│                                                              │
│ To: Sarah Jenkins <...>                                     │
│ Subject: Application — RPA Developer                         │
│                                                              │
│ Hi Sarah,                                                    │
│                                                              │
│ ...                                                          │
│                                                              │
│ ✨ AI Assist   📝 Template   📎 Resume                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ FOLLOW-UP                                                    │
│                                                              │
│ ○ No follow-up                                               │
│ ● Suggested cadence                                          │
│                                                              │
│ +4 days      +10 days       +17 days                         │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Resume: RPA Developer v2.1                                   │
│                                                              │
│                         Save Draft    Schedule    Send        │
└──────────────────────────────────────────────────────────────┘

The user should feel like composing an email, not completing a
database form.

============================================================
28. JOB PICKER
============================================================

Instead of:

    Target Company *
    Position Title *

provide:

    Search JobPilot jobs...

When selected:

    Company
    Job title
    platform
    URL
    description
    target role

are automatically populated.

Allow:

    + Create New Job

only when necessary.

============================================================
29. CONTACT PICKER
============================================================

Instead of always requiring:

    Recruiter Name
    Recruiter Email

show:

    Search contacts...

Existing contact:

    Sarah Jenkins
    Senior Recruiter
    sarah@abc.com

Allow:

    + New Contact

Prevent duplicate contacts.

============================================================
30. RESUME PICKER
============================================================

Replace plain dropdown with a modern resume selector.

Example:

    Recommended

    RPA Developer Resume
    v2.1
    Updated Sep 11
    ✓ Verified

    [Change]

Show why it was recommended:

    Target role match

Do not display raw filesystem paths.

============================================================
31. TEMPLATE PICKER
============================================================

Instead of a simple dropdown:

    Custom Pitch

show a small template library.

Categories:

    Applications
    Follow-ups
    Recruiter Intro
    Referral
    Interview
    Thank You

Each template:

    name
    short preview
    category

Click to insert.

============================================================
32. SUBJECT LINE INTELLIGENCE
============================================================

When a job/contact is selected, suggest:

    Application — RPA Developer — Ahmad Raza

Allow editing.

Do not lock the subject.

============================================================
33. ATTACHMENT EXPERIENCE
============================================================

Show selected resume as:

    📎 Ahmad_Raza_RPA_Resume_v2.1.pdf
    248 KB · Verified

Actions:

    View
    Replace
    Remove

Never show only a dropdown value.

============================================================
34. SEND ACTIONS
============================================================

Bottom action bar:

    Save Draft
    Schedule
    Send

Send should be the primary action.

Schedule opens:

    Later today
    Tomorrow morning
    Custom date/time

Use existing scheduler.

Do not create a second scheduler.

============================================================
35. SEND CONFIRMATION
============================================================

Before sending a NEW OUTREACH email, show a compact final review
only if needed.

Display:

    To
    Subject
    Resume
    Follow-up cadence

Then:

    Send Outreach

Avoid a giant confirmation dialog.

============================================================
36. SMART DUPLICATE WARNING
============================================================

If an existing application is found:

    Possible duplicate

    ABC Technologies
    RPA Developer
    Last contacted Sep 24

Actions:

    View existing
    Continue anyway
    Cancel

Do not block legitimate follow-up/contact scenarios.

============================================================
37. INBOUND SYNC UX
============================================================

Current:

    Sync Inbound

should become:

    Sync

with status feedback.

States:

    Sync
    Syncing...
    Synced just now
    3 new messages
    Needs review

Do not make the user wonder whether synchronization worked.

============================================================
38. UNMATCHED EMAILS
============================================================

Add a dedicated:

    Needs Review

state.

Example:

    2 emails could not be matched.

    Recruiter:
    recruiter@company.com

    Subject:
    Interview Opportunity

    [Assign to Application]

Do not silently attach uncertain emails.

============================================================
39. NOTIFICATION CENTER
============================================================

Integrate with existing NotificationService.

Examples:

    🔵 Recruiter replied
    🟠 Follow-up due
    🟣 Interview invitation detected
    🔴 Email send failed

Click notification:

    open corresponding Outreach conversation.

Do not build another notification system.

============================================================
40. EMAIL SEND STATUS
============================================================

Show precise status.

Example:

    Sending...
    Sent just now
    Failed
    Scheduled for Oct 2

Do not claim:

    Delivered

unless the provider actually confirms delivery.

============================================================
41. DRAFTS
============================================================

Add a:

    Drafts

filter/state.

Example:

    Drafts 3

Each row:

    Company
    Job
    Last edited
    Attachment
    Status

This is a very useful missing feature.

============================================================
42. SCHEDULED
============================================================

Add:

    Scheduled

filter.

Show:

    ABC Corp
    Follow-up #1
    Oct 2 · 9:00 AM

Actions:

    Edit
    Reschedule
    Cancel

============================================================
43. SENT HISTORY
============================================================

Add:

    Sent

view/filter.

This should not be a generic email inbox.

Show recruitment context:

    Company
    Job
    Contact
    Application
    Resume used
    Date sent

============================================================
44. QUICK ACTIONS
============================================================

Contextual quick actions:

    Reply
    Follow-up
    Pause
    Open Application
    Open Job
    View Resume
    View Contact
    Copy Email
    Open Original Thread

Keep these contextual.

Do not turn the screen into a toolbar full of buttons.

============================================================
45. KEYBOARD SHORTCUTS
============================================================

Where technically appropriate:

    Ctrl/Cmd + K
        Search

    Ctrl/Cmd + N
        New Outreach

    R
        Reply

    F
        Follow-up

    Esc
        Close composer

    Ctrl/Cmd + Enter
        Send

Do not trigger destructive actions accidentally.

============================================================
46. MODAL / DRAWER BEHAVIOR
============================================================

Avoid giant blocking dialogs.

Prefer:

    side drawer
    expandable composer
    centered lightweight composer

for most actions.

The user should maintain context while composing.

If the existing PySide6 architecture makes a modal necessary,
style it as a modern workspace rather than a traditional form.

============================================================
47. RESPONSIVE BEHAVIOR
============================================================

When window width decreases:

    hide/collapse right context panel

then:

    reduce left inbox width

then:

    show conversation full-width

Do not allow horizontal clipping.

============================================================
48. DARK THEME
============================================================

Follow the existing JobPilot dark theme.

Use:

    deep near-black background
    subtle elevated surfaces
    muted borders
    white/near-white typography
    orange primary accent

Avoid:

    excessive orange
    bright colored cards
    gradients
    glowing effects
    neon UI

Orange should indicate:

    primary action
    selected state
    important interaction

not every component.

============================================================
49. LIGHT THEME
============================================================

The same UI must work properly in light mode.

Do not simply invert colors.

Use:

    white/off-white surfaces
    subtle gray borders
    dark text
    restrained orange accents

Check:

    badges
    disabled controls
    placeholders
    hover states
    selected rows
    timeline
    composer
    AI panels

for proper contrast.

============================================================
50. VISUAL HIERARCHY
============================================================

Reduce the number of visible rectangles.

Use hierarchy:

    typography
    whitespace
    alignment
    subtle dividers
    small status indicators

instead of:

    box
    inside box
    inside another box.

The current UI looks "compact" because everything is compressed into
containers.

Modernize by improving hierarchy, not merely reducing font sizes.

============================================================
51. DO NOT MAKE IT LOOK LIKE A DASHBOARD
============================================================

Outreach is a workspace.

It should feel closer to:

    Gmail
    Linear
    Notion
    modern ATS CRM

than:

    analytics dashboard.

KPI metrics should remain secondary.

The conversation should be the main visual focus.

============================================================
52. AI + HUMAN WORKFLOW
============================================================

AI should assist at three moments:

    BEFORE SEND
        Draft / personalize / improve

    AFTER RESPONSE
        classify / extract questions / summarize

    BEFORE REPLY
        suggest answer / draft response

The user remains in control of:

    send
    status change
    interview confirmation
    offer classification
    rejection classification

============================================================
53. CONVERSATION SUMMARY
============================================================

For long threads, show:

    ✨ AI Summary

Example:

    Recruiter requested:
    • Notice period
    • Interview availability

    Candidate previously replied:
    • Notice period: 45 days

    Next action:
    Provide interview availability.

This summary should be generated on demand or cached.

Do not call AI on every UI repaint.

============================================================
54. RESPONSE INTELLIGENCE
============================================================

Add a compact insight panel:

    Recruiter Intent
    ─────────────────────
    Interview Request

    Confidence
    High

    Questions detected
    2

    Suggested action
    Schedule interview

    [Draft Reply]
    [Apply Status]

Do not automatically change application state.

============================================================
55. FOLLOW-UP INTELLIGENCE
============================================================

Instead of blindly showing:

    Step 1
    Step 2
    Step 3

show:

    Outreach Health

    ✓ Application sent
    ✓ Recruiter replied
    ⏸ Follow-up sequence paused

or:

    Outreach Health

    ✓ Application sent
    ○ No response
    🟠 Follow-up due tomorrow

This is much more understandable.

============================================================
56. APPLICATION CONTEXT LINKING
============================================================

Every outreach conversation should provide direct navigation:

    View Application
    View Job
    View Resume
    View Contact

Do not duplicate those entities inside Outreach.

============================================================
57. REAL DATA ONLY
============================================================

No fake:

    recruiter names
    email addresses
    company names
    response counts
    follow-ups
    AI classifications

Demo/test data may only appear through an explicit test fixture.

The screenshot currently contains placeholder/test-looking data such as
"JobPilot" and a recruiter email. Do not hard-code such values into
production UI.

============================================================
58. PERFORMANCE
============================================================

Do not load the entire mailbox into memory.

Use:

    pagination
    lazy loading
    limited timeline fetches
    debounced search

Do not block Qt main thread with:

    SMTP
    IMAP
    AI
    attachment processing

Use existing QThread/worker architecture.

============================================================
59. ACCESSIBILITY
============================================================

Ensure:

    keyboard navigation
    visible focus
    readable text
    adequate contrast
    tooltips for icon-only actions

Do not rely solely on color to communicate:

    replied
    failed
    waiting
    paused

Use:

    text
    icons
    status labels

============================================================
60. MICRO-INTERACTIONS
============================================================

Add subtle feedback:

    Send → Sent ✓
    Sync → Synced
    Save draft → Saved
    AI generation → streaming/progress state
    Follow-up paused → Paused
    Resume → Resumed

Keep animations subtle.

No flashy animations.

============================================================
61. EMPTY STATES
============================================================

When no outreach exists:

    No recruiter conversations yet.

    Start tracking direct applications,
    recruiter replies and follow-ups in one place.

    [+ New Outreach]

When no response:

    No recruiter responses yet.

When no follow-ups:

    No follow-ups due.

Do not leave giant empty black areas.

============================================================
62. ERROR STATES
============================================================

Errors should be actionable.

Example:

    Unable to send email

    SMTP authentication failed.

    [Test Connection]
    [Open Email Settings]
    [Retry]

Not:

    Error: SMTPException

============================================================
63. DO NOT BREAK BACKEND ARCHITECTURE
============================================================

Reuse:

    OutreachService
    OutreachDispatcher
    FollowUpScheduler
    InboundSyncService
    EmailProvider
    Communication
    Application
    Contact
    Resume
    EmailTemplate
    NotificationService
    UniversalAIService

Do not create:

    GmailService2
    OutreachDatabase
    EmailCRM
    EmailApplication
    EmailContact
    EmailFollowUp

unless architecture audit proves an entirely new abstraction is
actually necessary.

============================================================
64. DO NOT CREATE A SECOND SCHEDULER
============================================================

All:

    scheduled emails
    follow-ups
    notifications

must use the existing scheduling infrastructure.

============================================================
65. DO NOT CREATE A SECOND AI KNOWLEDGE BASE
============================================================

For candidate questions:

    reuse ProfileService
    reuse ResumeService
    reuse existing Q&A knowledge

For job context:

    reuse Job

For application context:

    reuse Application

============================================================
66. IMPLEMENTATION ORDER
============================================================

PHASE 1

Audit current UI and backend.

Do not change anything yet.

PHASE 2

Redesign Outreach page information architecture.

Implement:

    header
    KPI strip
    inbox
    conversation
    context panel

PHASE 3

Redesign New Outreach composer.

Implement:

    job picker
    contact picker
    resume picker
    template picker
    modern email editor
    attachment chips
    cadence configuration

PHASE 4

Implement:

    draft state
    autosave
    schedule
    send UX

using existing backend.

PHASE 5

Implement:

    conversation timeline
    expandable messages
    attachments
    sent resume viewer
    threaded reply

PHASE 6

Implement:

    AI Copilot
    AI reply generation
    question extraction
    response summary
    response classification

PHASE 7

Implement:

    follow-up intelligence
    smart next action
    action-required state

PHASE 8

Implement:

    filters
    search
    keyboard shortcuts
    responsive behavior

PHASE 9

Dark/light theme refinement.

PHASE 10

Testing and regression.

============================================================
67. TESTING
============================================================

Add UI tests for:

    new outreach
    job selection
    contact selection
    resume selection
    template selection
    AI draft
    draft autosave
    send
    schedule
    reply
    attachment viewing
    pause follow-ups
    resume follow-ups
    filters
    search
    context navigation
    empty state
    error state
    dark theme
    light theme

Backend regression:

    send flow
    duplicate detection
    thread matching
    follow-up pause
    inbound sync
    AI classification
    application linking

============================================================
68. VISUAL ACCEPTANCE CRITERIA
============================================================

The redesigned page must NOT look like:

    a collection of bordered forms
    an old desktop CRUD application
    a dashboard with giant cards
    a generic email client
    a web page copied into PySide6

It should feel like:

    a professional desktop recruitment workspace.

The user should be able to glance at the page and immediately answer:

    Who replied?
    Who needs action?
    What did I send?
    Which resume did I send?
    What happens next?
    When is my next follow-up?
    What does the recruiter want?
    What should I reply?

============================================================
69. FINAL ACCEPTANCE TEST
============================================================

Create one realistic end-to-end test scenario:

    Job:
        RPA Developer

    Company:
        Example Technologies

    Recruiter:
        Sarah Jenkins

    Candidate:
        Current user profile

Workflow:

    1. Create outreach
    2. Select existing Job
    3. Select Contact
    4. Select role-matched Resume
    5. Generate AI draft
    6. Edit draft
    7. Attach resume
    8. Send
    9. Application appears in Outreach
    10. Follow-up sequence appears
    11. Simulate recruiter reply
    12. Follow-ups pause
    13. AI detects interview request
    14. User confirms suggested status
    15. Draft reply
    16. Send threaded reply
    17. Timeline updates
    18. Application/Recruitment/Analytics reflect the events

No fake production data.

============================================================
70. FINAL DELIVERABLE
============================================================

After implementation report:

1. UI files changed
2. Backend files reused
3. Backend files changed
4. New UI components
5. New UX features
6. AI features
7. Draft/scheduling features
8. Thread/reply features
9. Follow-up features
10. Tests added
11. Test results
12. Screenshots or visual verification
13. Known limitations

IMPORTANT:

DO NOT simply make the existing UI more colorful.

DO NOT solve the problem by adding more cards.

DO NOT reduce everything into smaller controls.

The goal is a genuine information-architecture redesign.

The current feature set is already strong.

Now make the UI feel equally strong.