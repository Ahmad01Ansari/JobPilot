You are working on the JobPilot Outreach Center.

Your task is NOT to simply redesign the email UI.

Your task is to audit the existing Outreach architecture and redesign the workflow so it remains manageable when the user has hundreds of recruiters, applications, conversations, follow-ups and emails.

IMPORTANT:
Do not rewrite working email infrastructure unnecessarily.
Do not break SMTP/IMAP, threading, outbox, deduplication, follow-up scheduling or inbound synchronization.
Reuse existing services, models and repositories wherever possible.

READ FIRST:
- Existing AI development rules
- Architecture rules
- UI rules
- Automation rules
- Database rules
- Testing rules
- Existing Outreach specification
- Existing OutreachService
- Communication model
- Application model
- Contact model
- FollowUp model
- EmailTemplate model
- Outreach dispatcher
- Follow-up scheduler
- Inbound sync service
- Current Outreach UI

==================================================
1. FIRST AUDIT — DO NOT IMPLEMENT YET
==================================================

Inspect the current implementation and document:

1. How conversations are currently identified.
2. How applications are connected to contacts.
3. How communications are connected to applications.
4. How follow-ups are connected.
5. How conversation state is currently calculated.
6. How "needs action" is currently determined.
7. How pending follow-ups are queried.
8. How recruiter replies are detected.
9. How outbound messages are staged and sent.
10. How duplicate outreach is prevented.
11. How bulk operations could currently be performed.
12. Whether the UI requires opening conversations individually.
13. How search and filtering currently work.
14. Which parts are derived dynamically and which are persisted.

Create an architecture gap report before changing code.

==================================================
2. CORE PROBLEM TO SOLVE
==================================================

The Outreach Center must not behave like a simple email inbox.

The user may eventually have:

- hundreds of applications
- hundreds of recruiter contacts
- hundreds/thousands of emails
- many active follow-up cadences
- multiple recruiter replies
- multiple concurrent interview conversations

The user must NOT need to manually inspect every conversation to understand what needs attention.

The system must answer:

"WHAT DO I NEED TO DO RIGHT NOW?"

and:

"WHAT IS CURRENTLY WAITING FOR THE RECRUITER?"

and:

"WHICH APPLICATIONS/CONTACTS SHOULD I SEND THIS EMAIL TO?"

==================================================
3. INTRODUCE AN OUTREACH OPERATIONS MODEL
==================================================

Create a logical Outreach Case / Conversation Operations layer.

Do not automatically create a new database table if the existing schema can support this cleanly.

The logical object should combine:

Application
Contact
Conversation
Communications
FollowUps

and expose:

- conversation_state
- next_action
- next_action_owner
- next_action_due_at
- priority
- cadence_state
- last_contact_at
- last_inbound_at
- last_outbound_at
- unread/attention state
- application status
- recruiter/contact information

The important distinction is:

EMAIL != CONVERSATION != APPLICATION

An email belongs to a conversation.

A conversation belongs to an application/contact relationship.

==================================================
4. STANDARDIZE CONVERSATION STATE
==================================================

Define explicit conversation states.

At minimum evaluate:

NEEDS_ACTION
WAITING_FOR_RECRUITER
WAITING_FOR_USER
FOLLOW_UP_DUE
REPLIED
SCHEDULED
PAUSED
COMPLETED
CLOSED
UNKNOWN

Do not overload one status field with unrelated meanings.

Clearly separate:

1. Conversation State
2. Next Action
3. Next Action Owner
4. Follow-up State
5. Application Recruitment Status
6. Outbox/Send State

Do not use email delivery status as conversation state.

==================================================
5. NEXT ACTION IS A FIRST-CLASS CONCEPT
==================================================

Every active conversation must be able to answer:

What should happen next?

Examples:

REPLY_TO_RECRUITER
SEND_FOLLOW_UP
REVIEW_RECRUITER_REPLY
REVIEW_ATTACHMENT
CONFIRM_INTERVIEW
SCHEDULE_INTERVIEW
UPDATE_APPLICATION
WAIT_FOR_RECRUITER
PAUSE_CADENCE
RESUME_CADENCE
NONE

Every action should have:

- action type
- owner
- due_at
- source
- reason
- related application
- related conversation

If next_action_owner = USER:

surface it in "Needs Action".

If next_action_owner = RECRUITER:

surface it in "Waiting".

If next_action_owner = SYSTEM:

surface it in scheduled/automation state.

==================================================
6. BUILD A WORK QUEUE
==================================================

The primary Outreach view should have a work-oriented section.

Example:

TODAY

- Reply to recruiter
- Follow-up due
- Review recruiter reply
- Interview confirmation
- Attachment review

Then:

UPCOMING

Then:

WAITING FOR RECRUITER

Then:

COMPLETED/CLOSED

Do not require the user to open every conversation.

The work queue must be generated from real database state.

NO FAKE DATA.

==================================================
7. BULK TARGETING
==================================================

The user must be able to select multiple existing applications/conversations/contacts.

Example:

[ ] Company A — RPA Developer
[ ] Company B — Automation Engineer
[ ] Company C — RPA Developer

Selected: 3

Actions:

- Send Email
- Queue Follow-up
- Pause Cadence
- Resume Cadence
- Change/Select Resume
- Mark Reviewed

Bulk email must NOT bypass existing safety mechanisms.

Every selected recipient must individually pass:

- contact validation
- application validation
- duplicate detection
- conversation-state validation
- template rendering
- attachment validation
- send eligibility
- outbox staging
- dispatch
- result verification

Never blindly send one SMTP operation to a list.

==================================================
8. BULK EMAIL COMPOSER
==================================================

Create a bulk composer that shows:

Recipients
Template
Subject
Personalization
Resume/attachment
Scheduled send time

Before sending, display a recipient preview:

Company
Job
Recruiter
Email
Template
Resume
Existing conversation state
Last contact
Next action

Allow the user to remove individual recipients.

Require explicit final confirmation before queueing.

==================================================
9. GLOBAL OUTREACH SEARCH
==================================================

Support searching across:

- recruiter name
- recruiter email
- company
- job title
- application
- conversation
- email subject
- email body
- follow-up
- status

Integrate with the existing global Ctrl+K search if available.

Search should be service/repository driven.

Do not load thousands of records into the UI just to filter them locally.

Use pagination/query filtering.

==================================================
10. OPERATIONAL FILTERS
==================================================

Provide:

ALL
NEEDS ACTION
DUE TODAY
WAITING FOR RECRUITER
WAITING FOR ME
REPLIED
FOLLOW-UP ACTIVE
SCHEDULED
PAUSED
COMPLETED
CLOSED

Also support filters:

Company
Job
Recruiter
Application status
Conversation state
Follow-up state
Date
Priority
Resume version

==================================================
11. INBOUND REPLY HANDLING
==================================================

When an inbound recruiter email arrives:

1. Match it to the correct conversation.
2. Update conversation state.
3. Pause conflicting pending follow-ups.
4. Determine next action.
5. Assign action owner.
6. Run AI intent classification if configured.
7. Store AI result and evidence.
8. Surface the conversation in Needs Action when appropriate.

Example:

INTERVIEW_INVITATION

Next action:
CONFIRM_INTERVIEW

Owner:
USER

UI:

"Interview invitation detected"

[Review] [Draft Reply] [Update Application]

AI must recommend.

AI must not silently perform consequential actions.

==================================================
12. AI CLASSIFICATION
==================================================

AI may classify:

INTERVIEW_INVITATION
RECRUITER_QUESTION
SALARY_DISCUSSION
DOCUMENT_REQUEST
REJECTION
NEXT_ROUND
GENERAL_REPLY
FOLLOW_UP_RESPONSE
UNKNOWN

Every AI result must contain:

- classification
- confidence
- evidence
- source message
- recommended action

If confidence is insufficient:

UNKNOWN / MANUAL_REVIEW

Never invent recruiter intent.

==================================================
13. CADENCE MANAGEMENT
==================================================

The user must see cadence at a glance.

Example:

ABC Corp
Follow-up 2/3
Due tomorrow

XYZ Ltd
Follow-up 1/3
Due today

Microsoft
Paused
Reason: Recruiter replied

Do not make the user inspect each thread to determine cadence status.

Reuse the existing FollowUp scheduler.

Do not duplicate cadence logic inside the UI.

==================================================
14. SAFETY
==================================================

Bulk outreach must never bypass:

- duplicate detection
- user confirmation
- application state checks
- recruiter reply detection
- paused cadence
- invalid recipients
- outbox staging
- send verification

Never automatically send a message simply because AI generated it.

AI-generated emails require explicit user approval unless an already-existing, explicitly configured non-consequential workflow permits otherwise.

Do not send to closed/rejected applications unless the user explicitly chooses to override.

==================================================
15. DATA MODEL RULE
==================================================

Before creating new database models:

Determine whether the current:

Application
Contact
Communication
FollowUp

relationships can represent the required behavior.

Prefer derived operational state over unnecessary duplicated data.

If a new persisted entity is genuinely required, explain:

- why existing entities are insufficient
- fields
- relationships
- indexes
- migration
- backward compatibility

==================================================
16. UI DESIGN
==================================================

Use the existing JobPilot modern ATS/SaaS design system.

Do NOT create:

- giant cards
- excessive nested borders
- decorative dashboards
- fake statistics
- unnecessary modals
- WhatsApp-style email bubbles

Prioritize:

- information density
- hierarchy
- clear action states
- compact filters
- search
- bulk selection
- keyboard navigation
- responsive split view
- dark/light theme consistency

Suggested structure:

OUTREACH

Top:
[Needs Action] [Due Today] [Waiting] [Replied] [Scheduled]

Main:
Work Queue / Conversation List

Right:
Conversation Detail

Primary actions:
Reply
Send Follow-up
Pause
Resume
Schedule
Update Application

==================================================
17. PERFORMANCE
==================================================

Design for:

100+
500+
1,000+
10,000+

communications.

Do not load complete email bodies for every conversation.

Use:

- pagination
- indexed queries
- lazy loading
- summary projections
- conversation-level aggregation
- message-level loading only when opened

==================================================
18. TESTING
==================================================

Before implementation:

Record current test count.

After implementation test:

1. One conversation.
2. Multiple conversations.
3. Waiting recruiter.
4. Waiting user.
5. Follow-up due.
6. Recruiter reply.
7. Paused cadence.
8. Closed application.
9. Duplicate recipient.
10. Bulk selection.
11. Bulk send validation.
12. Remove one recipient from bulk send.
13. Wrong/invalid email.
14. Resume attachment mismatch.
15. AI classification.
16. Unknown AI intent.
17. Search.
18. Pagination.
19. Large dataset.
20. Restart/recovery.
21. Existing outbox reconciliation.
22. Existing threaded reply behavior.

Do not claim tests pass unless actually executed.

==================================================
19. IMPLEMENTATION ORDER
==================================================

Use this order:

PHASE 0
Audit existing implementation.

PHASE 1
Define conversation operational state and next-action model.

PHASE 2
Implement service/repository query layer.

PHASE 3
Implement work queue.

PHASE 4
Implement search/filtering.

PHASE 5
Implement bulk selection.

PHASE 6
Implement bulk composer and validation.

PHASE 7
Integrate inbound AI classification with next-action recommendations.

PHASE 8
Redesign Outreach UI around operational workflow.

PHASE 9
Performance optimization and indexing.

PHASE 10
Regression/integration testing.

PHASE 11
Final architecture and documentation update.

Do not start with UI.

==================================================
20. IMPORTANT ARCHITECTURAL RULE
==================================================

Do not turn Outreach into another independent subsystem.

Reuse:

ApplicationService
ContactService
OutreachService
FollowUp scheduler
Communication model
Application model
Contact model
Email provider
Outbox dispatcher
Inbound sync
ResumeService
QnAService
ProfileService

The Outreach Center is an orchestration/work-management layer over these systems.

==================================================
21. FINAL ACCEPTANCE CRITERIA
==================================================

The feature is complete only when the user can:

1. Open Outreach and immediately see what requires attention.
2. See what is waiting for recruiters.
3. See today's follow-ups.
4. Search a specific recruiter/company/job instantly.
5. Select multiple existing applications.
6. Compose one personalized email for the selected targets.
7. Preview every recipient before sending.
8. Remove individual recipients.
9. Prevent duplicate/invalid outreach.
10. Preserve existing threading.
11. Preserve existing follow-up scheduling.
12. Automatically surface recruiter replies.
13. Understand the next action for every active conversation.
14. Manage hundreds of conversations without manually opening each email.
15. Recover safely after restart or send failure.

==================================================
FINAL RULE

Do not mark the task complete merely because the UI looks better.

The real success criterion is:

"The user can manage a large and growing recruiter outreach workload without manually searching through individual emails to understand what is happening or what needs to be done."

Before finishing, provide:

1. Audit findings
2. Problems discovered
3. Architecture changes
4. Files changed
5. Database changes
6. Service changes
7. UI changes
8. Tests before/after
9. Remaining limitations
10. Manual validation steps

Do not hide unresolved problems.
Do not claim production-ready behavior without evidence.