# JobPilot — Job Lifecycle & Application Architecture

You are working on the existing JobPilot desktop ATS/job-automation application.

The goal of this task is to establish a clean, scalable lifecycle architecture for:

- Job discovery across multiple platforms
- Easy Apply jobs
- Company Portal / External Application jobs
- Applications
- Recruitment status tracking
- Interviews
- Offers
- Follow-ups
- Future company-portal automation

IMPORTANT:

This is an ARCHITECTURE AND DATA-FLOW TASK.

Do not blindly implement new UI or rewrite the existing automation.

First inspect the current:
- Job model
- Application model
- repositories
- JobService
- ApplicationService
- recruitment service
- LinkedIn automation
- Naukri automation
- platform router
- existing JobsView
- ApplicationsView
- InterviewsView
- FollowupsView

Then adapt the existing architecture where necessary.

Do not duplicate existing models/services if the required capability already exists.

==================================================
1. CORE ARCHITECTURAL PRINCIPLE
==================================================

The most important rule:

A JOB and an APPLICATION are different entities.

A Job represents an opportunity discovered from a platform.

An Application represents the user's attempt/application against that job.

Do NOT create separate Job records simply because the job has:

- Easy Apply
- Company Portal / External Application

Instead:

ONE JOB
    +
APPLICATION METHOD
    +
APPLICATION STATE

should describe the lifecycle.

Example:

Job:
RPA Developer
ABC Technologies
LinkedIn
Bangalore

Application Method:
EASY_APPLY

Application:
SUBMITTED

Another example:

Job:
Python Automation Engineer
XYZ Technologies
Naukri
Delhi

Application Method:
COMPANY_PORTAL

Application:
NOT_STARTED / NEW

==================================================
2. JOB ENTITY
==================================================

Every discovered opportunity should create or update ONE Job record.

A Job should contain information such as:

- id
- platform
- external_job_id if available
- title
- company
- location
- experience
- salary
- description / JD
- source_url
- application_url
- application_method
- contact information
- first_seen_at
- last_seen_at
- is_active
- fingerprint / deduplication identity
- metadata if required

Use the existing Job model where possible.

Do not create a second Job record merely because:

application_method = EASY_APPLY

versus:

application_method = COMPANY_PORTAL

==================================================
3. APPLICATION METHOD
==================================================

Introduce or reuse a semantic application method.

Supported values should be:

EASY_APPLY
COMPANY_PORTAL
MANUAL
UNKNOWN

The exact enum/value names can follow the existing project's conventions.

IMPORTANT:

Application method describes HOW the job can be applied to.

It does NOT describe whether the application has been submitted.

For example:

EASY_APPLY + NEW

means:

"This job can be applied through the platform's Easy Apply mechanism and has not yet been submitted."

Whereas:

EASY_APPLY + SUBMITTED

means:

"The Easy Apply application was successfully submitted."

Similarly:

COMPANY_PORTAL + NEW

means:

"This job requires an external/company website application and has not yet been submitted."

==================================================
4. JOB DISCOVERY FLOW
==================================================

All supported platforms should follow the same high-level discovery pipeline:

Platform
    ↓
Search
    ↓
Discover Job
    ↓
Extract Job Data
    ↓
Detect Application Method
    ↓
Normalize Job
    ↓
Deduplicate
    ↓
Upsert Job
    ↓
Evaluate Eligibility
    ↓
Determine next action

Platforms may include:

- LinkedIn
- Naukri
- Indeed
- Glassdoor
- Manual
- Future platforms

Do not create platform-specific lifecycle logic in the UI.

The platform automation should normalize its result into the common Job model/service.

==================================================
5. APPLICATION METHOD DETECTION
==================================================

When the bot encounters a job, determine:

A. EASY_APPLY

Example:

Job page
    ↓
Easy Apply / Quick Apply
    ↓
application can be completed inside platform

Store:

application_method = EASY_APPLY

B. COMPANY_PORTAL

Example:

Job page
    ↓
Apply
    ↓
external company/recruiter website

Store:

application_method = COMPANY_PORTAL

Also preserve:

application_url

This URL is important because future Company Portal automation will use it.

C. UNKNOWN

If the application mechanism cannot be reliably identified:

application_method = UNKNOWN

Do not guess.

==================================================
6. JOB TAB ARCHITECTURE
==================================================

The main Jobs section should contain filtered views.

Primary navigation:

Jobs

Inside Jobs:

[ All Jobs ]
[ Easy Apply ]
[ Company Portal ]

These are NOT three separate databases.

They are views over the same Job table.

Conceptually:

ALL JOBS
    ↓
    ├── EASY APPLY
    │      application_method = EASY_APPLY
    │
    └── COMPANY PORTAL
           application_method = COMPANY_PORTAL

The All Jobs view shows every discovered job.

Easy Apply shows:

application_method = EASY_APPLY

Company Portal shows:

application_method = COMPANY_PORTAL

==================================================
7. DO NOT DUPLICATE JOBS ACROSS TABS
==================================================

If the same job appears in All Jobs and Easy Apply:

that is ONE Job record.

The UI is simply showing the same record through two different filters.

Do not create:

Job #101 → All Jobs
Job #102 → Easy Apply

That would be incorrect.

==================================================
8. JOB STATUS VS APPLICATION STATUS
==================================================

This is critical.

Do NOT use one generic "status" field for everything.

Separate:

A. JOB STATUS

Examples:

ACTIVE
INACTIVE
EXPIRED
CLOSED

This describes the job opportunity.

B. APPLICATION STATUS

Examples:

NOT_STARTED
SUBMITTED
UNDER_REVIEW
SHORTLISTED
INTERVIEW
OFFER
REJECTED
WITHDRAWN

This describes the candidate's recruitment lifecycle.

C. AUTOMATION STATUS

This describes what the automation engine is doing.

Examples:

NOT_STARTED
RUNNING
SUCCESS
FAILED
MANUAL_REQUIRED
UNKNOWN

Do not mix these three concepts.

==================================================
9. JOB TAB STATUS
==================================================

The Jobs tab is primarily about discovered opportunities.

For each job, show information such as:

Title
Company
Platform
Location
Application Method
Experience
Salary
First Seen
Last Seen
Application Status
Actions

Example:

RPA Developer
ABC Technologies

LinkedIn
Bangalore
Easy Apply

Application:
Not Started

[View Job]

Another:

Python Automation Engineer
XYZ Technologies

Naukri
Delhi
Company Portal

Application:
Not Started

[View Job]
[Open Company Portal]

==================================================
10. JOB DESCRIPTION / JD
==================================================

Every discovered job should preserve the job description when available.

Do not put the entire JD directly into the table.

The Jobs UI should provide:

[View JD]

which opens a modal/dialog/drawer.

The JD viewer should show:

- Job title
- Company
- Location
- Experience
- Salary
- Application method
- Platform
- Full job description
- Source URL
- Application URL
- Contact information if available

Use a scrollable detail dialog.

==================================================
11. CONTACT INFORMATION
==================================================

If recruiter/contact information is discovered, associate it with the appropriate:

Contact

and/or:

Company

record using the existing models.

Do not duplicate contact information into every application record unnecessarily.

Example:

Contact:
John Smith
Recruiter
john@example.com
LinkedIn profile

Then associate:

Job
Application
Follow-up

with that contact where appropriate.

==================================================
12. APPLICATION CREATION
==================================================

A Job should NOT automatically become an Application merely because it was discovered.

Discovery:

Job exists.

Application:

created when the candidate actually starts/initiates an application workflow or when the system explicitly queues the job for application according to existing business rules.

Example:

Job discovered:

Job exists
Application = none

When Easy Apply automation successfully submits:

Job
    ↓
Application created
    ↓
status = SUBMITTED

When Company Portal automation later successfully submits:

Job
    ↓
Application created
    ↓
status = SUBMITTED

==================================================
13. IMPORTANT: AUTOMATION FAILURE DOES NOT EQUAL REJECTION
==================================================

This must never happen:

Automation failed
    ↓
Application status = REJECTED

That is incorrect.

For example:

Naukri chatbot failed to enter an answer.

This means:

Automation execution failed/manual intervention required.

It does NOT mean:

Recruiter rejected the candidate.

Keep automation execution state separate from recruitment status.

==================================================
14. EASY APPLY LIFECYCLE
==================================================

Current working Easy Apply automation should follow:

JOB DISCOVERED
    ↓
application_method = EASY_APPLY
    ↓
eligibility evaluation
    ↓
automation starts
    ↓
application submitted
    ↓
APPLICATION CREATED
    ↓
application.status = SUBMITTED

If questionnaire fails:

JOB remains active
    ↓
automation status = FAILED / MANUAL_REQUIRED
    ↓
application is NOT marked REJECTED

If the application was already submitted:

ALREADY_APPLIED
    ↓
application.status = SUBMITTED
or existing application remains unchanged

Do not duplicate the Application record.

==================================================
15. COMPANY PORTAL LIFECYCLE
==================================================

Company Portal jobs are discovered now.

Full Company Portal automation will be implemented later.

Therefore:

Job discovered
    ↓
application_method = COMPANY_PORTAL
    ↓
Job appears under:
Jobs → Company Portal
    ↓
candidate can inspect JD
    ↓
candidate can inspect application URL
    ↓
future automation can select eligible jobs
    ↓
Company Portal automation starts
    ↓
Application submitted
    ↓
Application.status = SUBMITTED

The Company Portal queue should eventually be selectable using criteria such as:

application_method = COMPANY_PORTAL
AND
no submitted application exists
AND
job is active
AND
job is eligible

Do not implement the Company Portal bot in this task unless explicitly requested.

==================================================
16. COMPANY PORTAL QUEUE
==================================================

Design the architecture so future automation can query:

"Give me Company Portal jobs that are eligible for application."

Conceptually:

WHERE
    application_method = COMPANY_PORTAL
    AND job.is_active = true
    AND no successful application exists
    AND job has application_url
    AND job has not been manually excluded

The exact query should use the existing repository/service architecture.

Do not put SQL directly inside the UI.

==================================================
17. APPLICATION TAB
==================================================

Applications is the candidate's recruitment pipeline.

The Applications page should show only actual Application records.

It should include:

- Job title
- Company
- Platform
- Application method
- Submitted date
- Current recruitment status
- Last status change
- Next follow-up
- Interview status if applicable
- Offer status if applicable

Example:

RPA Developer
ABC Technologies

LinkedIn · Easy Apply

Submitted:
23 Sep 2026

Status:
Under Review

Next:
Follow up in 3 days

==================================================
18. APPLICATION STATUS OWNERSHIP
==================================================

The Applications tab is the primary place where the user manages recruitment lifecycle status.

Example lifecycle:

SUBMITTED
    ↓
UNDER_REVIEW
    ↓
SHORTLISTED
    ↓
INTERVIEW
    ↓
OFFER

Possible terminal/alternative states:

REJECTED
WITHDRAWN

The system should maintain a status history/audit trail.

Every status transition should record:

- application_id
- previous status
- new status
- source
- timestamp
- notes
- optional failure/reason

==================================================
19. AUTOMATION VS HUMAN STATUS UPDATE
==================================================

Automation may create:

SUBMITTED

when submission is actually confirmed.

Automation should NOT arbitrarily set:

SHORTLISTED
INTERVIEW
OFFER
REJECTED

unless a future verified integration explicitly provides such information.

Those recruitment lifecycle changes should normally be user-driven/manual or come from a future communication integration.

==================================================
20. APPLICATION DETAIL PAGE
==================================================

Clicking an application should open a detailed recruitment workspace.

Example:

RPA Developer
ABC Technologies

LinkedIn · Easy Apply

────────────────────────

Current Status:
UNDER REVIEW

────────────────────────

Timeline

23 Sep
Application submitted

25 Sep
Recruiter contacted candidate

27 Sep
Technical interview scheduled

────────────────────────

Tabs/sections:

Overview
Timeline
Interviews
Communications
Follow-ups
Notes
Offer

The same Job information should be accessible from the application.

Do not duplicate the entire Job object into Application.

==================================================
21. STATUS UPDATE RESTRICTION
==================================================

The user specifically wants recruitment status updates to be managed from Applications.

Implement that rule.

Job status:

managed from Jobs.

Recruitment/application status:

managed from Applications.

Follow-up task status:

managed from Follow-ups.

Interview status:

managed from Interviews.

Do not create multiple UI locations that can independently change the same lifecycle state without coordination.

==================================================
22. FOLLOW-UP PAGE
==================================================

Follow-ups are TASKS.

They are not another application status.

A Follow-up should represent an action the candidate needs to perform.

Examples:

CALL recruiter
EMAIL recruiter
LINKEDIN_MESSAGE
FOLLOW_UP_APPLICATION
SEND_THANK_YOU
CHECK_APPLICATION_STATUS
OTHER

Each follow-up should contain:

- id
- application_id
- contact_id if applicable
- task type
- due_at
- notes
- status
- completed_at

Statuses:

PENDING
COMPLETED
CANCELLED

Optionally:

OVERDUE

can be derived from:

PENDING + due_at < now

rather than necessarily storing another database status.

==================================================
23. FOLLOW-UP RELATIONSHIP
==================================================

A follow-up should normally belong to an Application.

Example:

Application:
RPA Developer — ABC Technologies

Follow-up:

Type:
EMAIL_RECRUITER

Due:
25 Sep

Contact:
John Smith

Notes:
"Ask for update on application."

The Follow-up page is therefore a task management view over recruitment activities.

==================================================
24. INTERVIEW RELATIONSHIP
==================================================

Interview belongs to an Application.

Example:

Application
    ↓
Interview #1
    HR
    ↓
Interview #2
    Technical
    ↓
Interview #3
    Managerial

Interview status:

SCHEDULED
COMPLETED
RESCHEDULED
CANCELLED
NO_SHOW

Do not convert interview status directly into application status automatically unless an explicit business rule exists.

Example:

Interview COMPLETED

does not necessarily mean:

Application = OFFER

==================================================
25. OFFER RELATIONSHIP
==================================================

Offer belongs to an Application.

Application:

INTERVIEW
    ↓
Offer received
    ↓
Offer record

Offer should contain:

- offered CTC
- currency
- joining date
- status
- notes

Application status can then become:

OFFER

through the controlled application lifecycle transition.

==================================================
26. ALL JOBS AS THE MASTER DISCOVERY VIEW
==================================================

The Jobs section should conceptually look like:

Jobs

[ All Jobs ] [ Easy Apply ] [ Company Portal ]

All Jobs:
--------------------------------
Every discovered job

Easy Apply:
--------------------------------
Only jobs where:
application_method = EASY_APPLY

Company Portal:
--------------------------------
Only jobs where:
application_method = COMPANY_PORTAL

These are FILTERED VIEWS, not separate entities.

==================================================
27. APPLICATIONS AS THE MASTER RECRUITMENT VIEW
==================================================

The Applications section should conceptually look like:

Applications

[ All ] [ Submitted ] [ Under Review ] [ Interview ] [ Offer ] [ Rejected ]

Every item represents an actual Application.

Do not populate Applications merely because a Job was discovered.

==================================================
28. DUPLICATE PROTECTION
==================================================

The architecture must prevent duplicate Jobs and duplicate Applications.

Job deduplication preference:

1. platform-native external job ID
2. normalized platform + external ID
3. normalized source URL
4. carefully designed fallback fingerprint

Application uniqueness:

A Job should not normally have multiple successful Applications for the same candidate unless the platform/business rules explicitly permit it.

Before creating a new application:

check for an existing application.

If already submitted:

do not create another Application.

==================================================
29. PLATFORM-SPECIFIC DETAILS MUST NOT LEAK INTO CORE DOMAIN LOGIC
==================================================

LinkedIn/Naukri/Indeed/Glassdoor may have different UI behavior.

The normalized result should become:

Job
+
application_method
+
source/application URL
+
platform metadata

The core JobService/ApplicationService should not contain:

if platform == "naukri":
    click this selector

That belongs inside the platform automation layer.

==================================================
30. DATA FLOW
==================================================

The final architecture should look like:

                    PLATFORM AUTOMATION
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
       LinkedIn         Naukri           Indeed
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                    NORMALIZED JOB
                           │
                           ▼
                       JobService
                           │
                           ▼
                        Job DB
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
       Easy Apply View           Company Portal View
              │                         │
              ▼                         ▼
       Easy Apply Bot          Future Portal Bot
              │                         │
              └────────────┬────────────┘
                           ▼
                      Application
                           │
                           ▼
                  ApplicationService
                           │
                           ▼
                 Recruitment Lifecycle
                           │
          ┌────────────────┼─────────────────┐
          ▼                ▼                 ▼
      Interviews     Communications      Follow-ups
          │                │                 │
          └────────────────┼─────────────────┘
                           ▼
                         Offer