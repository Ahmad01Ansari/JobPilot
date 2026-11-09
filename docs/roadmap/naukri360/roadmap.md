Absolutely. Let's lock the **Naukri implementation roadmap** first, and then work through it **one phase at a time** without jumping ahead.

# JobPilot — Naukri Automation Roadmap

## Target Architecture

```text
                         runAiBot.py
                              │
                              ▼
                      ┌───────────────┐
                      │ PlatformRouter│
                      └───────┬───────┘
                              │
                       ┌──────┴──────┐
                       ▼             ▼
                  LinkedIn        Naukri
                  Platform        Platform
                       │             │
                       └──────┬──────┘
                              ▼
                       Normalized Job
                              │
                              ▼
                    Qualification Engine
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
               SKIP                      ACCEPT
                                           │
                                           ▼
                                  Application Engine
                                           │
                       ┌───────────────────┼──────────────────┐
                       ▼                   ▼                  ▼
                    DIRECT            QUESTIONNAIRE       EXTERNAL
                       │                   │                  │
                       │                   ▼                  │
                       │              QnA Engine              │
                       │                   │                  │
                       │            Answer Validator          │
                       │                   │                  │
                       └───────────────────┴──────────────────┘
                                           │
                                           ▼
                                      Submit/Manual
                                           │
                                           ▼
                                  Application Tracker
```

---

# Phase 0 — Repository & Existing Architecture Audit

### Goal

Understand your existing LinkedIn implementation before writing Naukri code.

### Inspect

```text
base_platform.py
runAiBot.py
qna_engine.py
config_loader.py
profile.json
open_chrome.py
clickers_and_finders.py
logging
application tracking
LinkedIn implementation
```

### Questions we answer

* What functionality already exists?
* What can be reused?
* What should become common?
* Where is LinkedIn-specific logic mixed into generic logic?
* What interface should `NaukriPlatform` implement?

### Deliverable

A concrete architecture such as:

```python
class BasePlatform:
    def login(self): ...
    def search_jobs(self): ...
    def get_job_details(self): ...
    def apply(self): ...
```

We **do not implement Naukri yet**.

---

# Phase 1 — Configuration Architecture

### Goal

Add Naukri configuration without breaking LinkedIn.

Target:

```json
{
  "platforms": {
    "linkedin": {},
    "naukri": {}
  }
}
```

Naukri configuration:

```json
{
  "enabled": true,
  "search_terms": [
    "RPA Developer",
    "Automation Anywhere Developer",
    "Python Automation Engineer",
    "AI Automation Engineer"
  ],
  "search_location": "India",
  "experience_years": 2,
  "max_pages_per_search": 3,
  "freshness_days": 7,
  "apply_mode": "direct_only",
  "pause_before_submit": true
}
```

### Also establish

```text
candidate experience
search experience
salary preferences
notice period
location preference
resume
```

as separate concepts.

### Deliverable

Validated Naukri configuration loader.

---

# Phase 2 — Platform Abstraction / Normalized Job Model

### Goal

Prevent Naukri from duplicating LinkedIn logic.

Create a normalized object:

```python
Job
```

Example:

```python
Job(
    platform="naukri",
    job_id="...",
    title="RPA Developer",
    company="ABC",
    location="Noida",
    experience_min=1,
    experience_max=3,
    salary_min=400000,
    salary_max=700000,
    description="...",
    source_url="..."
)
```

### Deliverable

Both:

```text
LinkedIn → Job
Naukri   → Job
```

produce the same internal structure.

---

# Phase 3 — Common Qualification Engine

### Goal

Move job qualification out of LinkedIn/Naukri-specific code.

Pipeline:

```text
Job
 │
 ├── Already applied?
 ├── Company blacklist?
 ├── Title blacklist?
 ├── Experience?
 ├── Location?
 ├── Work mode?
 ├── Description?
 └── Bad words?
```

Return:

```python
QualificationResult(
    accepted=True,
    reason=None
)
```

or:

```python
QualificationResult(
    accepted=False,
    reason="Experience exceeds candidate experience"
)
```

### Deliverable

One qualification engine shared by both platforms.

---

# Phase 4 — Naukri Browser & Authentication

### Goal

Create the isolated Naukri browser session.

```text
~/.apply-and-pray-naukri-profile
```

Implement:

```python
NaukriBrowser
```

Responsibilities:

* Chrome startup
* persistent profile
* page-load strategy
* timeout handling
* navigation
* login-state detection
* manual login
* session recovery

### Important

Initially:

```text
Manual login
      ↓
Save session
      ↓
Reuse session
```

No automatic password handling.

### Deliverable

We can launch Naukri and reliably determine:

```text
LOGGED_IN
LOGIN_REQUIRED
UNKNOWN
```

---

# Phase 5 — Naukri Search Engine

### Goal

Search Naukri reliably.

Implement:

```python
NaukriSearch
```

Responsibilities:

```text
keyword
location
experience
freshness
pagination
```

Pipeline:

```text
SearchCriteria
      ↓
build_search_url()
      ↓
navigate
      ↓
validate search results
      ↓
extract cards
```

### Deliverable

Given:

```text
RPA Developer
India
0–5 years
7 days
```

the bot returns a list of job cards.

**No applications yet.**

---

# Phase 6 — Job Card & Detail Extraction

### Goal

Convert Naukri DOM → normalized `Job`.

Extract:

```text
Job ID
Title
Company
Location
Experience
Salary
Description
Posted date
Source URL
```

Architecture:

```text
Naukri DOM
    ↓
NaukriJobParser
    ↓
Job
```

### Deliverable

A reliable job extraction layer independent of the application flow.

---

# Phase 7 — Deduplication & Application Tracking

### Goal

Never blindly apply twice.

Implement:

```python
ApplicationTracker
```

States:

```text
DISCOVERED
QUALIFIED
SKIPPED
APPLYING
SUBMITTED
FAILED
MANUAL_REQUIRED
EXTERNAL
UNKNOWN
```

Critical state:

```text
UNKNOWN
```

Example:

```text
Clicked Apply
     ↓
Browser timeout
     ↓
Was application submitted?
     ↓
UNKNOWN
```

The bot must **not automatically retry** an UNKNOWN application.

### Deliverable

Reliable application history and idempotency.

---

# Phase 8 — Naukri Application Flow Detection

### Goal

Determine what happens after clicking Apply.

Possible states:

```text
DIRECT
QUESTIONNAIRE
EXTERNAL
LOGIN_REQUIRED
CAPTCHA
PROFILE_INCOMPLETE
UNKNOWN
```

Architecture:

```text
Click Apply
     ↓
Detect application state
     │
 ┌───┼────┬──────┬─────────┐
 ▼   ▼    ▼      ▼         ▼
Direct QnA External Login  Unknown
```

### Deliverable

Naukri can correctly identify the application type.

Still **don't enable fully automatic submission**.

---

# Phase 9 — Naukri Questionnaire Engine

### Goal

Handle Naukri-specific forms while reusing your existing QnA engine.

Pipeline:

```text
Question
   ↓
Normalize
   ↓
Known profile field?
   ├── YES → deterministic answer
   │
   └── NO
        ↓
     Rule engine
        ↓
     LLM fallback
        ↓
     Answer validation
```

Answer object:

```python
Answer(
    value="30 days",
    source="profile",
    confidence=1.0
)
```

Possible sources:

```text
profile
rule
calculation
llm
manual
```

### Deliverable

Naukri questions can be answered consistently without blindly trusting the LLM.

---

# Phase 10 — Form Interaction Engine

### Goal

Actually interact with Naukri forms.

Support:

```text
text
number
dropdown
radio
checkbox
textarea
file upload
```

Architecture:

```text
NaukriForm
    │
    ├── discover_fields()
    ├── identify_question()
    ├── answer()
    ├── validate()
    └── next()
```

### Deliverable

Bot can fill an application but initially stops before final submission.

---

# Phase 11 — Human Review / Safety Gate

Initially:

```json
"pause_before_submit": true
```

Workflow:

```text
Application
     ↓
Fill everything
     ↓
Final screen
     ↓
PAUSE
     ↓
Human reviews
     ↓
Submit
```

This phase lets us verify that:

* questions are answered correctly
* CTC is correct
* notice period is correct
* resume is correct
* no unexpected question was mishandled

### Deliverable

First **real-world controlled application**.

---

# Phase 12 — Submission & Confirmation

Only after Phase 11 is stable.

Implement:

```python
submit_application()
```

Then verify actual submission.

Don't consider:

```text
click() succeeded
```

as submission success.

Require something like:

```text
confirmation detected
```

or:

```text
application status confirmed
```

### Deliverable

Reliable:

```text
SUBMITTED
```

state.

---

# Phase 13 — Error Recovery

Test deliberately:

### Browser

```text
timeout
page crash
stale element
network delay
unexpected popup
```

### Authentication

```text
session expired
login required
OTP
CAPTCHA
```

### Application

```text
unknown question
missing field
unexpected form
external redirect
submission failure
```

Every failure should result in a controlled state:

```text
FAILED
MANUAL_REQUIRED
UNKNOWN
```

—not a crash of the entire run.

---

# Phase 14 — Pagination & Search Rotation

Implement:

```text
Search Term 1
    ↓
Page 1
Page 2
Page 3
    ↓
Search Term 2
    ↓
Page 1
...
```

Configuration:

```json
{
  "max_pages_per_search": 3,
  "max_jobs_evaluated_per_search": 100
}
```

Only after this works should we add sophisticated stopping rules such as consecutive skips.

---

# Phase 15 — Unified Application History

I'd eventually move toward:

```text
applications.csv
```

rather than making each platform's CSV the primary source.

Example:

```text
platform
job_id
title
company
location
source_url
status
application_type
discovered_at
applied_at
failure_reason
skip_reason
```

Then:

```text
LinkedIn
Naukri
Indeed
```

can all use the same tracker.

---

# Phase 16 — CLI Integration

Then implement:

```bash
python runAiBot.py --platform linkedin
```

```bash
python runAiBot.py --platform naukri
```

```bash
python runAiBot.py --platform all
```

Architecture:

```text
runAiBot
    ↓
PlatformRouter
    ├── LinkedInPlatform
    └── NaukriPlatform
```

---

# Phase 17 — Dashboard Integration

Only after CLI is stable.

Add:

```text
Naukri
Applications
Skipped
Failed
Manual Required
External
Success
```

to your existing Flask dashboard.

---

# Phase 18 — Automated Regression Tests

Create tests for:

```text
URL generation
experience parsing
salary parsing
job normalization
deduplication
QnA
answer validation
application states
```

Example:

```text
"1-5 years" → min=1, max=5
"3 to 5 years" → min=3, max=5
"5+ years" → min=5
"2 yrs" → min=2
```

This prevents future Naukri changes from breaking the qualification engine.

---

# Phase 19 — Production Run

Only after everything above:

```text
pause_before_submit = false
```

Then:

```text
Search
 ↓
Qualify
 ↓
Apply
 ↓
Answer
 ↓
Validate
 ↓
Submit
 ↓
Verify
 ↓
Log
```

---

# Final Development Order

This is the exact order I'd recommend:

| Phase | Component                        | Automatic Submit? |
| ----: | -------------------------------- | :---------------: |
|     0 | Existing repo audit              |         ❌         |
|     1 | Configuration                    |         ❌         |
|     2 | Platform abstraction + Job model |         ❌         |
|     3 | Qualification engine             |         ❌         |
|     4 | Naukri browser/login             |         ❌         |
|     5 | Search engine                    |         ❌         |
|     6 | Job extraction                   |         ❌         |
|     7 | Deduplication/tracking           |         ❌         |
|     8 | Application-flow detection       |         ❌         |
|     9 | QnA engine integration           |         ❌         |
|    10 | Form automation                  |         ❌         |
|    11 | Human review                     |         ❌         |
|    12 | Submission + verification        |   **Controlled**  |
|    13 | Error recovery                   |     Controlled    |
|    14 | Pagination/search rotation       |     Controlled    |
|    15 | Unified history                  |     Controlled    |
|    16 | CLI                              |     Controlled    |
|    17 | Dashboard                        |     Controlled    |
|    18 | Regression tests                 |     Controlled    |
|    19 | Production automation            |         ✅         |

## How we'll work

We'll **not jump from Phase 0 to Phase 10**.

We'll do:

> **Phase 0 → inspect your existing code → make a concrete change → test → confirm → Phase 1.**

### So our immediate task is Phase 0.

Upload the **`Apply-and-Pray` project ZIP** (with secrets/cookies/passwords removed). I want to inspect the actual:

```text
base_platform.py
runAiBot.py
LinkedIn implementation
qna_engine.py
config_loader.py
open_chrome.py
clickers_and_finders.py
profile.json
```

and any Naukri code you've already started.

Then I'll give you the **exact Phase 0 findings and the first code changes**, rather than making assumptions about your existing architecture.
