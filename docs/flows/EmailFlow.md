You are working inside the existing JobPilot desktop application.

TASK:
Implement a new first-class feature called:

    OUTREACH CENTER

The purpose is to manage job-application emails, recruiter contacts,
email conversations, follow-ups, response tracking, and eventually
AI-assisted email intelligence.

This is NOT simply an "email sender".

The goal is to turn:

    Find Job
    → Send Email
    → Attach Resume
    → Forget

into:

    Find Job
    → Create Outreach
    → Select Contact
    → Select Resume
    → Generate/Select Email
    → Send
    → Track Application
    → Track Conversation
    → Schedule Follow-up
    → Detect Response
    → Pause Follow-ups
    → Track Interview / Offer
    → Analytics

============================================================
0. MOST IMPORTANT RULE
============================================================

DO NOT start coding immediately.

First audit the existing JobPilot architecture.

The project already contains concepts/services for:

    Job
    Application
    Company
    Contact
    Communication
    FollowUp
    Interview
    Offer
    Resume
    RecruitmentService
    ApplicationService
    JobService
    AnalyticsService
    ResumeService / ResumeManager
    AutomationBridge
    Notification system if available
    existing configuration/secrets infrastructure

Do NOT create duplicate versions of these concepts.

The Outreach Center must become a layer on top of the existing
recruitment/application architecture.

============================================================
1. REPOSITORY AUDIT
============================================================

Inspect:

    models
    repositories
    services
    views
    dialogs
    theme system
    AutomationManager
    RecruitmentService
    ApplicationService
    JobService
    ResumeService
    Contact model/service
    Communication model/service
    FollowUp model/service
    Interview model/service
    Offer model/service
    AnalyticsService
    Notification system
    existing settings/security
    existing email integrations/connectors
    existing plugin/integration architecture

Determine:

1. How Contact is represented.
2. How Communication is represented.
3. How FollowUp is represented.
4. How Application is linked to Job.
5. How Application is linked to Contact.
6. How Application is linked to Resume.
7. Whether emails are already represented as Communications.
8. Whether email threads/message IDs are supported.
9. How timestamps are stored.
10. How application status transitions work.
11. How notifications are implemented.
12. How secrets/credentials are stored.
13. Whether Gmail/Outlook/email integration already exists.
14. How existing views communicate with services.
15. How navigation is registered.

Produce an internal architecture map before modifying files.

============================================================
2. ARCHITECTURAL PRINCIPLE
============================================================

The desired architecture is:

    Job
      ↓
    Application
      ↓
    Outreach
      ↓
    Communication
      ↓
    FollowUp
      ↓
    Response
      ↓
    Recruitment Status
      ↓
    Interview / Offer
      ↓
    Analytics

Do NOT create:

    EmailApplication
    EmailContact
    EmailConversation
    EmailFollowUp

if existing domain entities can represent these concepts.

Instead extend existing models/services only where necessary.

============================================================
3. IMPORTANT DOMAIN SEPARATION
============================================================

Do NOT confuse:

    Email state

with:

    Recruitment state

Email state could be:

    DRAFT
    SCHEDULED
    SENT
    DELIVERED
    REPLIED
    FAILED

Recruitment state could be:

    SUBMITTED
    UNDER_REVIEW
    SHORTLISTED
    INTERVIEW
    OFFER
    REJECTED
    WITHDRAWN

These are different dimensions.

An email being SENT does not mean:

    Application = SUBMITTED

unless the email represents the actual job application.

An incoming recruiter email does not automatically mean:

    Application = INTERVIEW

unless the content is actually an interview request and the user
confirms or the existing automation rules explicitly support it.

============================================================
4. NEW PAGE
============================================================

Add a new navigation item:

    Outreach

or:

    Outreach Center

Preferred display:

    Outreach

Subtitle:

    Applications, recruiter conversations and follow-ups.

Do not call the page simply:

    Email Automation

because the feature is broader than email sending.

Keep the existing 13 navigation items unchanged unless the current
architecture explicitly allows adding a new item.

If navigation is centrally defined, add Outreach without changing
existing item identifiers.

============================================================
5. OUTREACH CENTER UI
============================================================

Build a modern ATS/SaaS-style workspace consistent with the redesigned
JobPilot UI.

The page should contain:

HEADER

    Outreach

    Applications, recruiter conversations and follow-ups.

    [+ New Outreach]

SUMMARY

    Email Applications
    Responses
    Follow-ups Due
    Needs Action

Do NOT show fake values.

All numbers must come from real database queries.

============================================================
6. MAIN OUTREACH WORKSPACE
============================================================

Use a split workspace.

LEFT:

    outreach/application list

RIGHT:

    selected application conversation/detail panel

Concept:

    ┌────────────────────────────┬─────────────────────────────┐
    │ OUTREACH                   │ CONVERSATION                │
    │                            │                             │
    │ ABC Technologies          │ ABC Technologies            │
    │ RPA Developer              │ RPA Developer               │
    │ Sent 4 days ago            │                             │
    │ Follow-up due tomorrow     │ YOU                         │
    │                            │ Application sent            │
    │ XYZ Corp                   │ 28 Sep                      │
    │ Python Developer           │                             │
    │ Recruiter replied          │ RECRUITER                   │
    │                            │ We'd like to schedule...    │
    │ Acme                       │ 03 Oct                       │
    │ Automation Engineer        │                             │
    │ Follow-up due today        │ [Reply] [View Application]  │
    └────────────────────────────┴─────────────────────────────┘

Do not create giant empty panels.

The workspace must resize according to content.

============================================================
7. OUTREACH LIST FILTERS
============================================================

Add compact filters:

    All
    Needs Action
    Follow-ups
    Responses
    Scheduled
    Waiting
    Completed

Optional:

    Platform
    Application Method
    Status
    Date

Show active filters as removable chips.

Do not create huge filter cards.

============================================================
8. SEARCH
============================================================

Add:

    Search outreach...

Search:

    company
    job title
    contact name
    contact email
    subject
    application ID if supported

Do not perform expensive full database scans on every keystroke.

Use debounced search or repository-level filtering.

============================================================
9. NEW OUTREACH WORKFLOW
============================================================

Add:

    [+ New Outreach]

Opening it should launch a proper workflow.

STEP 1 — Select Job

Allow:

    existing Job

or:

    manual job/company details

Prefer existing Job.

Search:

    Job title
    Company
    Platform

Once selected:

    populate company
    title
    URL
    platform

============================================================
10. CONTACT SELECTION
============================================================

STEP 2:

    Select Contact

Fields:

    Recruiter name
    Email
    Company
    Role/title

Reuse existing Contact.

Allow:

    Existing Contact
    Create Contact

If contact already exists:

    prefill it.

Do not create duplicate Contact records.

Use normalized email as a primary duplicate signal where appropriate.

============================================================
11. RESUME SELECTION
============================================================

STEP 3:

    Select Resume

Reuse Resume Management.

Show:

    Recommended resume
    Target role
    Version
    Integrity
    Last updated

Prefer role-matched resume.

Example:

    Job:
    RPA Developer

    Recommended:
    ★ RPA Developer Resume v2.1

Allow:

    change resume

Do not automatically attach a resume without showing the user which
resume will be sent.

============================================================
12. ATTACHMENT VALIDATION
============================================================

Before sending:

    ✓ File exists
    ✓ PDF readable
    ✓ Resume verified
    ✓ Target role assigned
    ✓ Version valid

Show the selected attachment.

If the resume is invalid:

    block send

and explain why.

Do not silently substitute another resume.

============================================================
13. EMAIL TEMPLATE SYSTEM
============================================================

Create/reuse a template service.

Templates should support:

    name
    subject
    body
    category
    variables
    attachments if supported
    active/inactive

Initial categories:

    JOB_APPLICATION
    FOLLOW_UP
    RECRUITER_INTRODUCTION
    REFERRAL_REQUEST
    INTERVIEW_FOLLOW_UP
    THANK_YOU

Do not hard-code email bodies into the UI.

============================================================
14. TEMPLATE VARIABLES
============================================================

Support variables such as:

    {{candidate_name}}
    {{recruiter_name}}
    {{company_name}}
    {{job_title}}
    {{job_url}}
    {{target_role}}
    {{resume_name}}
    {{resume_version}}

Only resolve variables for which actual data exists.

If:

    recruiter_name

is unavailable:

    do not produce:

    "Hi undefined"

Use an appropriate fallback or require the user to fill it.

============================================================
15. EMAIL COMPOSER
============================================================

Build a modern email composer.

Example:

    New Outreach

    To:
    hr@company.com

    Subject:
    Application for RPA Developer — Ahmad Raza

    Resume:
    RPA Developer Resume v2.1

    Template:
    RPA Application

    ──────────────────────────────────────

    Email body...

    ──────────────────────────────────────

    📎 RPA_Developer_Resume_v2.1.pdf

    [Save Draft] [Schedule] [Send]

Features:

    rich/simple text editing according to existing UI architecture
    template insertion
    variable preview
    attachment management
    send/schedule
    discard

============================================================
16. AI EMAIL PERSONALIZATION
============================================================

Add optional:

    [Personalize with AI]

AI should receive only the necessary context:

    Job title
    Job description
    Company
    Candidate profile
    Selected resume content/summary

Do NOT send secrets.

Do NOT send unrelated database information.

AI output must remain editable before sending.

Show:

    AI-generated draft

not:

    automatically sent email.

============================================================
17. AI FACTUALITY RULE
============================================================

AI-generated email must NOT invent:

    skills
    years of experience
    certifications
    company experience
    education
    salary
    notice period
    achievements

Only use information supported by:

    candidate profile
    selected resume
    existing QnA/profile knowledge

If information is unavailable:

    omit it

rather than inventing it.

============================================================
18. EMAIL PROVIDER / INTEGRATION
============================================================

IMPORTANT:

Do not implement raw SMTP credentials directly inside the UI.

First inspect whether JobPilot already has:

    Gmail integration
    Outlook/Microsoft integration
    email connector
    plugin
    OAuth integration

Use the existing integration architecture if available.

If an email provider integration does not exist:

    create an EmailProvider interface

such as:

    EmailProvider
        send()
        save_draft()
        schedule()
        fetch_messages()
        get_thread()

Then implement the provider adapter using the project's supported
integration mechanism.

DO NOT store email passwords in source code.

Prefer OAuth/token-based authorization where the existing integration
supports it.

============================================================
19. SEND FLOW
============================================================

When user clicks Send:

    validate recipient
    validate subject
    validate body
    validate selected resume
    validate attachment
    validate provider
    check duplicate application
    confirm if necessary
    send
    persist communication
    update application if applicable
    create follow-up schedule if configured

The database should only record SENT after the provider confirms
successful sending.

If provider fails:

    record FAILED
    preserve draft
    show actionable error

Do not mark an email as sent merely because the user clicked Send.

============================================================
20. APPLICATION CREATION / LINKING
============================================================

When an email is explicitly being used as a job application:

    create or update Application

Set:

    platform/source = EMAIL or MANUAL_EMAIL
    application_method = EMAIL
    job_id
    contact_id
    resume_id
    submitted_at
    status = SUBMITTED

BUT:

Only do this if the email actually represents an application.

A recruiter conversation should not automatically create a new
application.

Use existing ApplicationService.

Do not directly manipulate the database from the UI.

============================================================
21. DUPLICATE APPLICATION PROTECTION
============================================================

Before sending a job application email:

Check for an existing relevant application.

Possible matching hierarchy:

    exact job_id
    same normalized company + job title
    same contact + job title
    same source URL

If an existing application is found:

    show:

    Possible duplicate application

    Existing:
        ABC Technologies
        RPA Developer
        Sent 28 Sep
        Status: Awaiting Response

    [View Existing]
    [Send Anyway]
    [Cancel]

Do not silently create duplicate applications.

Do not make duplicate detection impossible to override.

============================================================
22. COMMUNICATION RECORD
============================================================

Every sent email should create a Communication record.

Store, where supported:

    application_id
    contact_id
    company_id
    direction = OUTBOUND
    channel = EMAIL
    subject
    occurred_at
    provider_message_id
    provider_thread_id
    status

Do NOT store full email body in logs.

If the existing Communication model supports body/content storage,
follow its privacy/security conventions.

============================================================
23. THREAD SUPPORT
============================================================

If the provider supports conversation/thread IDs:

    persist provider_thread_id

This enables:

    application
       ↓
    email thread
       ↓
    recruiter response

Do not assume every email provider has the same thread semantics.

Use an adapter.

============================================================
24. FOLLOW-UP SYSTEM
============================================================

Reuse the existing FollowUp entity/service.

A follow-up should contain:

    application_id
    communication_id if applicable
    due_at
    type
    status
    notes

Possible states:

    SCHEDULED
    DUE
    COMPLETED
    SKIPPED
    CANCELLED

Do not create a second follow-up database.

============================================================
25. FOLLOW-UP SEQUENCE
============================================================

Implement a simple sequence model.

Example:

    Initial Application
        Day 0

    Follow-up #1
        Day 4

    Follow-up #2
        Day 10

    Final Follow-up
        Day 17

However:

DEFAULT BEHAVIOR:

    require user approval before sending follow-ups.

Do not automatically send a large sequence without explicit user
configuration.

============================================================
26. FOLLOW-UP ACTIONS
============================================================

When follow-up becomes due:

Show:

    Follow-up due

    ABC Technologies
    RPA Developer

    No response for 4 days.

    Suggested message:
    ...

Actions:

    [Review & Send]
    [Reschedule]
    [Skip]
    [Stop Sequence]

Do not send automatically unless the user has explicitly enabled
automatic follow-ups for that sequence.

============================================================
27. CRITICAL AUTOMATION RULE
============================================================

If an inbound recruiter response is detected:

    PAUSE all pending follow-ups for that application.

Example:

    Follow-up #2 scheduled tomorrow

    Recruiter replies today

    ↓

    Follow-up #2
    automatically becomes:

    PAUSED / CANCELLED

depending on the domain model.

This prevents JobPilot from sending:

    "Just following up..."

after the recruiter has already responded.

This rule must have automated tests.

============================================================
28. INBOUND EMAIL SYNC
============================================================

If an authorized email integration is available:

Implement:

    fetch new relevant messages

Match messages to existing applications using:

    provider_thread_id
    provider_message_id
    participants
    normalized subject
    known contact email

Do not match purely by subject if stronger identifiers exist.

If no reliable match:

    put the email into:

    Unmatched / Needs Review

Do not attach an email to the wrong application.

============================================================
29. RESPONSE CLASSIFICATION
============================================================

Add optional AI-assisted response classification.

Possible categories:

    ACKNOWLEDGEMENT
    RECRUITER_RESPONSE
    INTERVIEW_REQUEST
    INFORMATION_REQUEST
    ASSESSMENT_REQUEST
    REJECTION
    OFFER
    OTHER
    UNKNOWN

The classifier should return:

    category
    confidence
    evidence/summary

Do not silently make major state changes based solely on uncertain AI
classification.

============================================================
30. HUMAN CONFIRMATION FOR IMPORTANT STATE CHANGES
============================================================

For potentially important changes:

    INTERVIEW
    OFFER
    REJECTION

show:

    Response detected

    Suggested classification:
    Interview Request

    Confidence:
    High

    Suggested application status:
    INTERVIEW

    [Apply]
    [Ignore]

For low confidence:

    Manual review required.

Do not silently change the application state.

============================================================
31. ACTION REQUIRED
============================================================

Create an "Action Required" concept using existing notifications
if possible.

Examples:

    Recruiter replied
    Follow-up due
    Interview request
    Recruiter asked a question
    Application needs attention

Show count in Outreach.

Example:

    Needs Action: 4

============================================================
32. CONVERSATION TIMELINE
============================================================

Selected application should show a chronological timeline.

Example:

    28 Sep
    YOU
    Application sent
    📎 Resume attached

    02 Oct
    YOU
    Follow-up #1 sent

    05 Oct
    RECRUITER
    Response received

    05 Oct
    JOBPILOT
    Suggested: Interview Request

    07 Oct
    INTERVIEW
    Technical interview

Use existing Communication, FollowUp, Interview and Offer records.

Do not create another timeline database.

============================================================
33. REPLY ACTION
============================================================

When recruiter responds:

    [Reply]

should open the composer with:

    recipient
    thread
    subject
    context

pre-filled.

Preserve the email thread where the provider supports it.

Do not create a new unrelated conversation.

============================================================
34. EMAIL TEMPLATES + FOLLOW-UP TEMPLATES
============================================================

Templates should support categories.

Example:

    RPA Application
    Follow-up #1
    Follow-up #2
    Recruiter Reply
    Interview Confirmation
    Thank You

Templates can be manually edited.

AI personalization can generate a draft from a template.

Do not require AI to use the system.

============================================================
35. OUTREACH ANALYTICS
============================================================

Integrate with AnalyticsService.

Possible metrics:

    Email Applications
    Email Responses
    Email Response Rate
    Interviews
    Offers
    Follow-ups Sent
    Follow-ups Due
    Average Response Time

Only implement metrics supported by real data.

Do NOT create a separate OutreachAnalyticsService if AnalyticsService
already owns cross-channel analytics.

Add email as:

    application_method = EMAIL

where appropriate.

============================================================
36. ANALYTICS SEMANTICS
============================================================

Clearly define:

    Email Applications
        = applications where method == EMAIL

    Email Responses
        = distinct applications with qualifying inbound response

    Response Rate
        = responded email applications /
          submitted email applications

    Interviews
        = distinct email applications linked to >= 1 Interview

    Offers
        = distinct email applications linked to >= 1 Offer

Do not count:

    multiple emails
    multiple replies
    multiple interview rounds

as multiple applications.

============================================================
37. OUTREACH ANALYTICS SHOULD FEED MAIN ANALYTICS
============================================================

Do not make Outreach analytics isolated.

Main Analytics should eventually be able to show:

    LinkedIn
    Naukri
    Indeed
    Foundit
    Email
    Manual

and:

    Easy Apply
    Direct Apply
    Questionnaire
    External
    Email
    Manual

Use existing AnalyticsFilter infrastructure.

============================================================
38. OUTREACH NAVIGATION
============================================================

From Outreach:

    Click Job
        → JobsView

    Click Application
        → ApplicationsView

    Click Resume
        → Resume Management

    Click Interview
        → Recruitment / Interview view

    Click Company
        → Company/Contact details

Reuse existing navigation mechanisms.

Do not duplicate existing pages.

============================================================
39. SECURITY / PRIVACY
============================================================

Email and resume content is sensitive.

Never log:

    passwords
    OAuth tokens
    access tokens
    refresh tokens
    full email bodies
    resume content

Use existing SecretsService.

Do not store email credentials in:

    config.py
    JSON files
    source code
    logs

If provider OAuth is available, use OAuth.

============================================================
40. RATE LIMITING / SEND SAFETY
============================================================

Do not implement high-volume uncontrolled sending.

For V1:

    manual send

or:

    explicit scheduled sends with reasonable limits.

Add safeguards:

    duplicate detection
    recipient validation
    attachment validation
    provider failure handling
    send confirmation where appropriate

Do not create a bulk email blasting system.

This is a recruitment outreach tool, not a mass-mailing platform.

============================================================
41. SCHEDULED EMAILS
============================================================

If scheduling is implemented:

    store scheduled_at

and use the existing JobPilot scheduler/automation infrastructure
if available.

Do not create a second scheduler.

States:

    DRAFT
    SCHEDULED
    SENT
    FAILED
    CANCELLED

Scheduled sends must survive application restart.

============================================================
42. UI STATES
============================================================

Implement:

    loading
    empty
    error
    sending
    scheduled
    sent
    failed
    needs action
    unmatched response

Empty state:

    No outreach yet

    Start tracking job application emails and recruiter follow-ups.

    [+ New Outreach]

============================================================
43. MODERN UI DESIGN
============================================================

Follow the existing redesigned JobPilot UI.

Dark:

    Obsidian background
    subtle elevated surfaces
    muted borders
    orange accent
    semantic status colors

Light:

    clean white/off-white surfaces
    subtle borders
    dark typography
    orange accent

Avoid:

    giant cards
    excessive borders
    gradients
    oversized buttons
    giant empty panels

The page should feel like:

    recruitment CRM
    + ATS
    + email workspace

not:

    generic email client.

============================================================
44. RESPONSIVE SPLIT VIEW
============================================================

Desktop:

    list 35–40%
    detail 60–65%

Allow resizing if existing UI architecture supports it.

When no item is selected:

    show a useful empty state in the detail panel.

Do not permanently show an empty giant panel.

============================================================
45. IMPLEMENTATION PHASES
============================================================

Implement in this order.

PHASE 0 — Architecture audit

    inspect existing models/services/integrations

PHASE 1 — Domain contract

Define:

    email state
    communication relationship
    application relationship
    follow-up relationship
    thread identity
    response semantics

PHASE 2 — Backend

    OutreachService
    EmailProvider interface if required
    template service if required
    follow-up integration
    communication integration

PHASE 3 — Basic UI

    OutreachView
    list
    filters
    detail panel

PHASE 4 — New Outreach

    job
    contact
    resume
    template
    composer
    attachment
    send

PHASE 5 — Tracking

    communication timeline
    follow-ups
    application linking

PHASE 6 — Scheduled Follow-ups

    due states
    approval flow
    pause on response

PHASE 7 — Inbound Sync

    provider messages
    thread matching
    unmatched messages

PHASE 8 — AI

    response classification
    email personalization
    suggested replies

PHASE 9 — Analytics

    email method
    response metrics
    follow-up metrics

PHASE 10 — Tests

    complete regression suite

============================================================
46. TESTING
============================================================

Add tests for:

DOMAIN:

    communication creation
    application linking
    contact linking
    resume linking

EMAIL:

    valid send
    provider failure
    invalid recipient
    missing attachment
    missing credentials

DUPLICATES:

    duplicate job application
    duplicate contact
    override duplicate warning

TEMPLATES:

    variable substitution
    missing variable
    template rendering

FOLLOW-UP:

    create
    schedule
    due
    complete
    skip
    cancel
    reschedule

CRITICAL:

    recruiter response pauses follow-up

THREADS:

    match by thread ID
    match by message ID
    fallback matching
    unmatched message

CLASSIFICATION:

    interview request
    rejection
    information request
    acknowledgement
    unknown
    low confidence

APPLICATION:

    email application creates Application
    recruiter email does not create duplicate Application

ANALYTICS:

    email application count
    response count
    response rate
    interview count
    offer count

UI:

    new outreach
    search
    filters
    select application
    composer
    detail panel
    empty state
    error state

============================================================
47. REGRESSION REQUIREMENT
============================================================

After implementation:

    LinkedIn automation must still work.
    Naukri automation must still work.
    Indeed automation must still work.
    Foundit automation must still work.
    Resume selection must still work.
    Application tracking must still work.
    Recruitment pipeline must still work.
    Analytics must still work.

Do not change existing platform automation unless required.

If shared models/services are changed:

    add migration
    add backward compatibility
    add regression tests

============================================================
48. NO FAKE DATA
============================================================

Strict requirement.

Never create fake:

    email counts
    response rates
    conversations
    contacts
    response times
    recruiter messages
    follow-ups

All UI values must come from real persisted data.

If no data exists:

    show an intentional empty state.

============================================================
49. NO SILENT AI ACTIONS
============================================================

AI may:

    classify
    summarize
    draft
    suggest

AI should not silently:

    send email
    reject application
    accept offer
    schedule interview
    change important application status

without an explicit configured rule and/or human confirmation.

============================================================
50. FINAL UX TARGET
============================================================

The final experience should feel like:

    "JobPilot is my recruitment command center."

Example daily workflow:

    Morning
       ↓
    Open Outreach
       ↓
    3 follow-ups due
       ↓
    Review and send
       ↓
    Recruiter replied
       ↓
    Follow-up automatically paused
       ↓
    AI identifies interview request
       ↓
    User confirms
       ↓
    Application → INTERVIEW
       ↓
    Interview appears in Recruitment
       ↓
    Analytics updated

============================================================
51. FINAL ACCEPTANCE CRITERIA
============================================================

[ ] Outreach page exists
[ ] Existing navigation remains stable
[ ] New outreach workflow works
[ ] Existing Job can be selected
[ ] Existing Contact can be selected/created
[ ] Existing Resume can be selected
[ ] Email template system works
[ ] Variables resolve correctly
[ ] Email composer works
[ ] Attachment validation works
[ ] Provider abstraction works
[ ] Email sends only after provider confirmation
[ ] Communication record is created
[ ] Application is linked correctly
[ ] Duplicate application detection works
[ ] Follow-up system uses existing FollowUp architecture
[ ] Scheduled follow-ups work
[ ] Follow-up approval works
[ ] Recruiter response pauses follow-ups
[ ] Conversation timeline works
[ ] Thread matching works where provider supports it
[ ] Unmatched emails are not attached incorrectly
[ ] AI personalization is optional
[ ] AI response classification is optional
[ ] Important state changes require confirmation
[ ] Outreach analytics integrate with AnalyticsService
[ ] No duplicate CRM architecture
[ ] No duplicate email database
[ ] No duplicate scheduler
[ ] No secrets in source/logs
[ ] No mass-mailing behavior
[ ] No fake data
[ ] Dark theme works
[ ] Light theme works
[ ] Loading/empty/error states work
[ ] Existing automation remains functional
[ ] Full test suite passes

============================================================
52. FINAL IMPLEMENTATION REPORT
============================================================

After implementation report:

1. Files created
2. Files modified
3. Existing models/services reused
4. Database changes
5. Migration changes
6. Email provider integration
7. Outreach workflow
8. Communication integration
9. Follow-up integration
10. Thread/inbox integration
11. AI features
12. Analytics integration
13. Tests added
14. Test results
15. Features intentionally deferred
16. Known limitations

IMPORTANT:

Do not claim email integration is working unless an actual supported
provider was connected and tested.

Do not claim inbound synchronization works unless it was actually
tested.

START WITH THE ARCHITECTURE AUDIT.
DO NOT START BY BUILDING THE UI.

============================================================
53. OUTREACH CENTER V2 OVERHAUL STATUS: COMPLETED
============================================================

The Outreach Center V2 overhaul specified in `WorkingFlow/OutreachV2.md` is fully implemented:
1. Work Queue: Operational categorization into TODAY, WAITING, UPCOMING, and CLOSED.
2. Next Action Engine: Every case answers "What do I need to do right now?" with explicit headline, owner, and CTA.
3. Safe Bulk Outreach: Dedicated BulkOutreachDialog and BulkOutreachWorker with pre-send validation, individual recipient removal, template preview, resume selection, and sequential throttled dispatch.
4. Selection Action Bar: Batch operations (Bulk Email, Pause/Resume Cadence, Mark Read, Toggle Priority).
5. High Performance: get_outreach_applications_projected() single-query projection eliminating N+1 overhead.
6. Database Schema: Added indexed `is_unread` and `is_priority` to applications and `ai_classification` to communications.
7. Verification: 41 automated tests in `test_outreach*.py` + headless desktop GUI self-test fully passing.