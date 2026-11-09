

# JobPilot — Desktop Job Automation & Tracking Platform

## Master Implementation Roadmap

### Core objective

Transform the existing `Apply-and-Pray` project into a **PySide6 desktop application** that combines:

* User profile management
* Resume management
* Job-search configuration
* LinkedIn automation
* Naukri automation
* Future Indeed automation
* Future Glassdoor automation
* Centralized job database
* Application tracking
* Interview tracking
* Recruiter communication tracking
* Email/call status tracking
* Follow-up management
* Analytics/dashboard
* Automation controls
* Logs and error monitoring
* Configuration management
* Future multi-user support

The existing LinkedIn and Naukri automation must remain functional throughout the migration.

---

# Architecture

The target architecture should become:

```text
                         ┌─────────────────────┐
                         │    PySide6 Desktop  │
                         │         UI          │
                         └──────────┬──────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Application       │
                         │   / Service Layer   │
                         └──────────┬──────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
      Profile Service       Automation Service      Tracking Service
             │                      │                      │
             │             ┌────────┼────────┐            │
             │             ▼        ▼        ▼            │
             │         LinkedIn   Naukri   Indeed          │
             │                                             │
             └──────────────────┬──────────────────────────┘
                                ▼
                        ┌─────────────────┐
                        │    Database     │
                        │ SQLite/Postgres │
                        └─────────────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
        User/Profile       Jobs/Applications   Communication
        Resume/Data        Interviews/Status   Email/Calls
```

---

# Important architectural rule

The AI agent must **not rewrite the existing automation blindly**.

The existing:

```text
LinkedIn automation
Naukri automation
QnA engine
browser infrastructure
```

should initially be treated as working systems.

The desktop application should be built **around them** and then gradually integrate them.

---

# Phase 0 — Existing Project Freeze & Audit

### Goal

Understand the completed LinkedIn + Naukri implementation before changing architecture.

### Tasks

Inspect:

```text
runAiBot.py
platforms/
modules/
config/
all excels/
logs/
```

Identify:

* LinkedIn entry point
* Naukri entry point
* browser manager
* QnA engine
* profile configuration
* search configuration
* secrets
* application history
* logging
* resume handling
* job parsing
* application result handling

### Deliverable

Create:

```text
docs/current_architecture.md
```

containing:

```text
Existing component
Purpose
Input
Output
Reusable?
Desktop integration required?
```

### Gate

**Do not modify automation code yet.**

---

# Phase 1 — Desktop Application Foundation

Create the PySide6 application.

Recommended structure:

```text
app/
├── main.py
├── ui/
│   ├── main_window.py
│   ├── dashboard/
│   ├── profile/
│   ├── jobs/
│   ├── applications/
│   ├── interviews/
│   ├── platforms/
│   ├── automation/
│   ├── analytics/
│   ├── settings/
│   └── logs/
│
├── services/
├── models/
├── repositories/
├── workers/
└── resources/
```

Create:

* Main window
* Sidebar
* Top bar
* Central content area
* Status bar
* Theme system

Initial navigation:

```text
Dashboard
Profile
Resumes
Platforms
Job Search
Jobs
Applications
Interviews
Follow-ups
Analytics
Automation
Logs
Settings
```

### Gate

Desktop application launches successfully.

---

# Phase 2 — Database Architecture

This is the most important phase.

Move persistent application data from scattered configuration/CSV files into a database.

For desktop-first development:

```text
SQLite
```

is appropriate initially.

Use SQLAlchemy so that PostgreSQL can be introduced later without redesigning the entire application.

---

# Phase 3 — Database Schema

Design proper relational models.

## User

```text
users
```

Fields:

```text
id
name
email
phone
created_at
updated_at
```

---

## Personal Profile

```text
profiles
```

Fields such as:

```text
user_id
date_of_birth
gender
current_location
preferred_location
address
linkedin_url
github_url
portfolio_url
```

---

## Professional Profile

```text
professional_profiles
```

Fields:

```text
user_id
current_title
current_company
total_experience
skills
primary_skills
secondary_skills
education
notice_period
current_ctc
expected_ctc
availability
```

---

# Phase 4 — Resume Management

Create:

```text
resumes
```

Store:

```text
id
user_id
name
file_path
file_hash
version
is_default
created_at
updated_at
```

Features:

* Add resume
* Delete resume
* Rename resume
* Set default resume
* Open resume
* Track which resume was used for an application

Do not store large PDF binaries in SQLite initially unless there is a strong reason.

Store paths and metadata.

---

# Phase 5 — Migrate Config → Database

Current config:

```text
profile.json
personals.py
search.py
questions.py
settings.py
```

should become the **initial seed source**.

Migration flow:

```text
Existing Config
      ↓
Migration Script
      ↓
Database
      ↓
Desktop UI
      ↓
Database becomes source of truth
```

Example:

```bash
python migrate_config_to_db.py
```

### Critical rule

Do not delete the old configuration immediately.

First:

```text
Config → DB
```

Then validate:

```text
DB values == existing config values
```

Only after successful validation should automation read from DB.

---

# Phase 6 — Repository/Data Access Layer

Do not allow UI code to directly execute SQL everywhere.

Create:

```text
repositories/
├── user_repository.py
├── profile_repository.py
├── resume_repository.py
├── platform_repository.py
├── job_repository.py
├── application_repository.py
├── interview_repository.py
├── communication_repository.py
└── settings_repository.py
```

Architecture:

```text
UI
 ↓
Service
 ↓
Repository
 ↓
Database
```

This will keep the project maintainable.

---

# Phase 7 — Profile Management UI

Build a complete profile editor.

Sections:

### Personal

```text
Name
Email
Phone
Location
```

### Professional

```text
Current designation
Company
Experience
Skills
Notice period
Current CTC
Expected CTC
```

### Links

```text
LinkedIn
GitHub
Portfolio
```

### Education

```text
Degree
College
University
Year
CGPA
```

### Additional information

```text
Relocation
Work mode
Preferred locations
```

Buttons:

```text
Save
Reset
Validate
```

Every update writes to DB.

---

# Phase 8 — QnA Knowledge Base UI

Instead of keeping all answers hidden inside configuration files, create a UI for managing answers.

Example:

| Question                | Answer  | Type    | Source  |
| ----------------------- | ------- | ------- | ------- |
| Notice period?          | 45 days | Text    | Profile |
| Expected CTC?           | 8 LPA   | Number  | Profile |
| Willing to relocate?    | Yes     | Boolean | User    |
| Experience with Python? | 2 years | Number  | Profile |

Allow:

```text
Add
Edit
Delete
Test
Enable/Disable
```

This becomes the knowledge base used by the QnA engine.

---

# Phase 9 — Platform Management

Create a **Platforms** page.

Cards:

```text
LinkedIn
Naukri
Indeed
Glassdoor
```

Each platform should show:

```text
Enabled
Login status
Last run
Jobs discovered
Applications submitted
Failures
```

Example:

```text
LinkedIn
────────────────────
● Enabled

Last Run: 20 Sep 2026
Applications: 18
Status: Ready

[Configure] [Run]
```

---

# Phase 10 — Platform Configuration

Each platform gets its own settings.

## LinkedIn

```text
Enabled
Search terms
Location
Experience
Remote/Hybrid/Onsite
Easy Apply
Date posted
Maximum applications
Pause before submit
```

## Naukri

Same concept.

## Indeed

Prepare architecture but don't implement automation yet.

## Glassdoor

Same.

---

# Phase 11 — Automation Engine Abstraction

Create:

```text
AutomationManager
```

with:

```python
run(platform)
stop(platform)
pause(platform)
resume(platform)
get_status(platform)
```

Platform interface:

```python
class BasePlatform:
    initialize()
    login()
    search()
    extract_jobs()
    qualify()
    apply()
    close()
```

Existing LinkedIn and Naukri implementations should adapt to this interface rather than being rewritten unnecessarily.

---

# Phase 12 — Background Worker Architecture

This is essential for PySide6.

**Never run Selenium directly on the UI thread.**

Use:

```text
QThread
QRunnable
QThreadPool
```

or an equivalent worker architecture.

Flow:

```text
UI
 ↓
Automation Worker
 ↓
LinkedIn/Naukri
 ↓
Signals
 ↓
UI
```

Signals:

```text
job_found
job_qualified
application_started
application_submitted
application_failed
login_required
captcha_detected
automation_finished
error
```

This keeps the UI responsive.

---

# Phase 13 — Central Job Database

Create:

```text
jobs
```

Important fields:

```text
id
platform
external_job_id
title
company
location
work_mode
description
experience_min
experience_max
salary_min
salary_max
source_url
posted_date
discovered_at
```

Unique constraint:

```text
(platform, external_job_id)
```

This becomes the central job database.

---

# Phase 14 — Job Management UI

Create **Jobs** page.

Features:

```text
Search
Filter
Sort
Pagination
```

Filters:

```text
Platform
Company
Title
Location
Experience
Salary
Posted date
Application status
```

Job details:

```text
Title
Company
Location
Salary
Experience
Description
Source
Application status
```

Buttons:

```text
Apply
Skip
Open
Mark Interested
Add Note
```

---

# Phase 15 — Application Tracking Database

Create:

```text
applications
```

Important fields:

```text
id
job_id
platform
application_status
application_type
applied_at
resume_id
failure_reason
notes
created_at
updated_at
```

---

# Phase 16 — Application Lifecycle

Do not limit status to:

```text
Applied
Rejected
Selected
```

Use a richer lifecycle.

### Discovery

```text
DISCOVERED
QUALIFIED
SKIPPED
```

### Application

```text
APPLYING
SUBMITTED
FAILED
UNKNOWN
EXTERNAL
MANUAL_REQUIRED
```

### Recruitment

```text
UNDER_REVIEW
SHORTLISTED
RECRUITER_CONTACTED
ASSESSMENT
INTERVIEW_SCHEDULED
INTERVIEWING
```

### Outcome

```text
OFFER
ACCEPTED
REJECTED
WITHDRAWN
POSITION_CLOSED
NO_RESPONSE
```

---

# Phase 17 — Recruitment Pipeline / Kanban

Build a Kanban-style application tracker.

```text
┌───────────┬─────────────┬──────────────┬───────────────┐
│ Applied   │ Shortlisted │ Interview    │ Offer         │
├───────────┼─────────────┼──────────────┼───────────────┤
│ Company A │ Company B   │ Company C    │ Company D     │
│ Company E │ Company F   │ Company G    │               │
└───────────┴─────────────┴──────────────┴───────────────┘
```

Drag/drop status changes should update the database.

---

# Phase 18 — Communication Tracking

Create:

```text
communications
```

Track:

```text
application_id
type
direction
date
subject
summary
contact_name
contact_email
contact_phone
notes
```

Types:

```text
EMAIL
PHONE_CALL
LINKEDIN_MESSAGE
WHATSAPP
RECRUITER_MESSAGE
OTHER
```

Direction:

```text
INBOUND
OUTBOUND
```

Example:

```text
20 Sep
📧 Recruiter Email
"Interview invitation received"

21 Sep
📞 Phone Call
"Recruiter discussed salary expectations"
```

---

# Phase 19 — Interview Management

Create:

```text
interviews
```

Fields:

```text
application_id
round_number
round_name
scheduled_at
interviewer
mode
meeting_link
status
notes
feedback
```

Round types:

```text
HR
Technical
Coding
Managerial
Final
Assessment
Client
```

Statuses:

```text
SCHEDULED
COMPLETED
RESCHEDULED
CANCELLED
PASSED
FAILED
```

---

# Phase 20 — Follow-up System

Create a follow-up manager.

Example:

```text
Company: ABC
Applied: 15 Sep
Last communication: 17 Sep
Next follow-up: 22 Sep
```

Statuses:

```text
FOLLOW_UP_DUE
FOLLOW_UP_SENT
WAITING
NO_RESPONSE
```

Later you can integrate email to automatically detect replies.

---

# Phase 21 — Dashboard

Now build the main dashboard.

Show:

### Overall

```text
Jobs Found
Qualified Jobs
Applications
Interviews
Offers
Rejections
```

### Platform breakdown

```text
LinkedIn
Naukri
Indeed
Glassdoor
```

### Current pipeline

```text
Applied        124
Under Review    28
Shortlisted    12
Interviews      7
Offers          2
Rejected       42
No Response    35
```

### Recent activity

```text
10:32  Naukri     Applied → ABC
10:29  LinkedIn   Applied → XYZ
09:55  Email      Interview received → DEF
09:40  LinkedIn   Job discovered → PQR
```

---

# Phase 22 — Analytics

Create an analytics page.

Metrics:

### Application rate

```text
Applications / Qualified Jobs
```

### Response rate

```text
Responses / Applications
```

### Interview rate

```text
Interviews / Applications
```

### Offer rate

```text
Offers / Applications
```

### Platform comparison

Not a ranking, but factual statistics:

```text
Platform | Applications | Responses | Interviews | Offers
```

### Time analysis

```text
Average days:
Application → Response
Response → Interview
Interview → Offer
```

---

# Phase 23 — Email Integration

Later integrate email.

Potential workflow:

```text
Gmail
 ↓
Email Parser
 ↓
Identify company
 ↓
Identify application
 ↓
Classify email
 ↓
Update application
```

Classifications:

```text
APPLICATION_RECEIVED
SHORTLISTED
INTERVIEW_INVITATION
REJECTION
ASSESSMENT
OFFER
RECRUITER_CONTACT
OTHER
```

Important:

**Do not automatically change application status based solely on an uncertain LLM classification.**

Use confidence + matching evidence.

---

# Phase 24 — Call Tracking

Allow manual call logging first.

```text
+ Add Call
```

Fields:

```text
Company
Recruiter
Phone
Date
Duration
Summary
Next action
```

Later, if desired, integrate supported call/contact data.

---

# Phase 25 — Notifications & Follow-up Reminders

Desktop notifications:

```text
Interview tomorrow at 11:00
Follow-up due today
Recruiter email received
Application needs manual review
Automation stopped
Login required
```

---

# Phase 26 — Automation Control Center

Create an automation page.

Example:

```text
Automation Control
────────────────────────────

LinkedIn    ● Running
Naukri      ● Idle
Indeed      ○ Disabled
Glassdoor   ○ Disabled

[Start LinkedIn]
[Start Naukri]
[Stop All]
```

Show live:

```text
Current keyword
Current page
Jobs evaluated
Qualified
Skipped
Applications
Errors
```

---

# Phase 27 — Live Automation Console

Add a terminal-like log window inside PySide6.

Example:

```text
22:14:03 INFO  Starting Naukri
22:14:08 INFO  Search: RPA Developer
22:14:11 INFO  Found 20 jobs
22:14:13 INFO  Qualified: ABC Technologies
22:14:18 INFO  Opening application
22:14:22 INFO  Questionnaire detected
22:14:24 INFO  Answered: Notice Period = 45 days
22:14:27 WARN  Manual review required
```

Allow:

```text
Clear
Export
Copy
Filter by level
```

---

# Phase 28 — Error & Exception Center

Create an error database/log viewer.

Categories:

```text
LOGIN
NETWORK
SELENIUM
CAPTCHA
QUESTION
FORM
SUBMISSION
DATABASE
UNKNOWN
```

Each error:

```text
timestamp
platform
job
error_type
message
stack_trace
resolved
```

This will make debugging much easier than searching raw log files.

---

# Phase 29 — Settings

Create application-wide settings:

```text
General
Database
Browser
Automation
Notifications
Logging
AI/QnA
Security
Appearance
```

Automation settings:

```text
Pause before submit
Maximum applications/session
Delay between applications
Maximum pages
Stop on CAPTCHA
Stop on unknown question
```

---

# Phase 30 — Security

Before production, implement:

### Secrets

Never put:

```text
password
API key
session cookie
token
```

inside normal configuration/database fields in plaintext.

Use:

```text
OS keyring
environment variables
encrypted secrets
```

where appropriate.

### Database

Ensure:

```text
backups
permissions
safe writes
transaction handling
```

### Logs

Never log:

```text
passwords
OTP
tokens
cookies
API keys
```

---

# Phase 31 — Backup & Restore

Create:

```text
Backup Database
Restore Database
Export Data
Import Data
```

Backup:

```text
database
profile
applications
jobs
interviews
communications
settings
```

Do **not** blindly copy browser session profiles into backups.

---

# Phase 32 — Import Existing History

You already have historical CSV/application data.

Build:

```text
CSV → Database importer
```

Import:

```text
all_applied_jobs.csv
all_applied_naukri_jobs.csv
```

Map old fields into the new schema.

Run duplicate detection during migration.

---

# Phase 33 — Existing LinkedIn/Naukri Integration

Now connect the completed automation engines to the database.

Flow:

```text
Desktop
   ↓
AutomationManager
   ↓
Naukri
   ↓
Job discovered
   ↓
DB
   ↓
Qualification
   ↓
Application
   ↓
DB status update
   ↓
Dashboard refresh
```

Same for LinkedIn.

**Do not duplicate jobs or application records merely because automation runs again.**

---

# Phase 34 — Manual Job Entry

Allow the user to manually add jobs.

Useful when a recruiter sends a job directly.

```text
+ Add Job
```

Source:

```text
MANUAL
EMAIL
REFERRAL
RECRUITER
LINKEDIN
NAUKRI
```

---

# Phase 35 — Recruiter & Contact Management

Create:

```text
contacts
```

Store:

```text
name
company
designation
email
phone
LinkedIn
notes
```

Associate contacts with applications.

This lets you see:

```text
Company
 ├── Application
 ├── Recruiter
 ├── Emails
 ├── Calls
 └── Interviews
```

---

# Phase 36 — Search & Smart Filters

Global search across:

```text
Jobs
Companies
Applications
Recruiters
Interviews
Communications
```

Example:

```text
"Automation Anywhere"
```

could return:

```text
Jobs
Applications
Recruiters
Emails
Interviews
```

---

# Phase 37 — Company Management

Create company-level records.

```text
companies
```

Track:

```text
company
website
industry
location
applications
responses
interviews
offers
notes
```

This avoids repeating company information across tables.

---

# Phase 38 — AI Assistant

Only after the core application system is stable.

Potential assistant:

```text
"How many RPA jobs did I apply for this month?"

"Which applications need follow-up?"

"Show applications where recruiter contacted me."

"Which interviews are scheduled this week?"

"Summarize my job search this month."

"Find unanswered recruiter messages."
```

The assistant should query your database rather than inventing information.

---

# Phase 39 — Resume/Job Matching

Later add:

```text
Job Description
       ↓
Resume
       ↓
Skill matching
       ↓
Match score
       ↓
Missing skills
```

Example:

```text
Python       ✓
SQL          ✓
Automation   ✓
Power BI     ✗
Azure        ✓
```

Use this as informational matching rather than automatically deciding whether a job should be applied to unless the existing qualification rules explicitly say so.

---

# Phase 40 — Testing

Build tests for:

### Database

```text
CRUD
relationships
constraints
transactions
```

### Automation

```text
job extraction
deduplication
status transitions
```

### QnA

```text
question normalization
answer retrieval
validation
```

### UI

```text
profile update
job status update
application creation
interview creation
```

### Migration

```text
config → DB
CSV → DB
```

---

# Phase 41 — Packaging

Package the application as a desktop application.

Possible:

```text
PyInstaller
```

Output:

```text
JobPilot.exe
```

for Windows and an appropriate Linux package/build for Ubuntu.

Application startup:

```text
JobPilot
      ↓
Database check
      ↓
Load user
      ↓
Dashboard
```

---

# Phase 42 — Production Readiness

Final checks:

```text
✓ LinkedIn works
✓ Naukri works
✓ DB works
✓ Profile works
✓ Resume management works
✓ Job tracking works
✓ Application tracking works
✓ Interview tracking works
✓ Communication tracking works
✓ Backup works
✓ Restore works
✓ Error handling works
✓ Secrets protected
✓ UI doesn't freeze
✓ Automation can be stopped
✓ Unknown application state handled safely
```

---

# Final Target Application

The finished application should look conceptually like:

```text
┌───────────────────────────────────────────────────────────────┐
│ JobPilot                                          ⚙ Settings │
├───────────────┬───────────────────────────────────────────────┤
│               │                                               │
│ Dashboard     │               Dashboard                       │
│               │                                               │
│ Profile       │   Jobs       Applications    Interviews       │
│ Resumes       │   1,248      184             17              │
│ Platforms     │                                               │
│ Jobs          │   ─────────────────────────────────────────   │
│ Applications  │                                               │
│ Interviews    │   Application Pipeline                        │
│ Follow-ups    │                                               │
│ Contacts      │   Applied → Shortlisted → Interview → Offer  │
│ Companies     │                                               │
│ Analytics     │   ─────────────────────────────────────────   │
│ Automation    │                                               │
│ Logs          │   Recent Activity                             │
│ Settings      │                                               │
│               │   Naukri    Applied      ABC                  │
│               │   LinkedIn  Interview    XYZ                  │
│               │   Email     Recruiter    DEF                  │
│               │                                               │
└───────────────┴───────────────────────────────────────────────┘
```

## Recommended execution order

Despite the roadmap having many phases, I would organize the actual development into these major milestones:

| Milestone | Phases | Objective                             |
| --------- | -----: | ------------------------------------- |
| **A**     |    0–5 | Desktop + DB foundation               |
| **B**     |   6–10 | Profile, resume, QnA, platforms       |
| **C**     |  11–16 | Automation + jobs + applications      |
| **D**     |  17–20 | Recruitment pipeline                  |
| **E**     |  21–25 | Dashboard + analytics + communication |
| **F**     |  26–30 | Automation control + security         |
| **G**     |  31–35 | Migration + contacts + companies      |
| **H**     |  36–39 | Search + AI features                  |
| **I**     |  40–42 | Testing + packaging + production      |

### One critical rule for the AI agent

Give it this instruction:

> **Work strictly one phase at a time. Before each phase, inspect the existing implementation. Do not rewrite working LinkedIn or Naukri automation unless the current architecture requires a specific adapter/interface change. For every phase: inspect → propose changes → implement → test → report changed files → report test results → wait for approval before starting the next phase. The database must eventually become the source of truth, while the existing config files should initially be treated as migration/seed data. Never expose or commit credentials, passwords, cookies, tokens, or API keys. Never bypass CAPTCHA or authentication controls.**

This approach will turn `JobPilot` from a collection of automation scripts into a **proper desktop job-search operating system**, while preserving the LinkedIn and Naukri code you already finished.
