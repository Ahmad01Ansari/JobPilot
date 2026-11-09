Yes. Since you've chosen **Stagehand**, I would give your coding agent a prompt that makes it behave like an architect first and an implementer second.

One important point before the prompt: the current Stagehand Python SDK is now v4 and supports local browser execution with Playwright, plus `act()`, `observe()`, and `extract()`. The official examples also show autonomous `execute()` workflows. ([GitHub][1])

For JobPilot, however, **do not simply call `agent.execute("apply for this job")` and hand the whole process to Stagehand**. Use Stagehand as the browser-intelligence layer inside your controlled application state machine. Stagehand itself emphasizes mixing AI actions with deterministic Playwright-style control. ([GitHub][2])

Here is the prompt I would give your AI coding agent:

---

# AI AGENT PROMPT — JobPilot Universal AI Application Agent

```text
You are working on an existing production-oriented desktop application called JobPilot.

JobPilot is a PySide6 desktop application for managing a user's complete job search:

Jobs
→ Job Evaluation
→ Applications
→ Resumes
→ Q&A Knowledge Base
→ Recruitment Pipeline
→ Interviews
→ Outreach
→ Follow-ups
→ Analytics
→ Automation

The project already has working architecture and existing automation.

YOUR TASK:

Design and implement a new major capability:

========================================
UNIVERSAL AI APPLICATION AGENT
========================================

The goal is to allow JobPilot to intelligently handle unfamiliar company career pages, ATS application forms, and other legitimate application workflows using:

- Playwright
- Stagehand Python SDK
- existing JobPilot services
- existing Profile/Q&A/Resume infrastructure
- human-in-the-loop checkpoints
- a deterministic application state machine

IMPORTANT:

DO NOT rewrite the existing LinkedIn or Naukri automation.

DO NOT replace existing working automation.

DO NOT move existing Selenium automation to Playwright.

DO NOT modify the existing LinkedIn/Naukri implementation unless absolutely required for a clean integration boundary.

The new Universal Application Agent must be an additional automation backend.

========================================
1. FIRST: STUDY THE EXISTING PROJECT
========================================

Before changing any code, inspect the entire repository.

Specifically inspect:

- project structure
- services
- repositories
- SQLAlchemy models
- application models
- JobService
- ApplicationService
- ResumeService
- ProfileService
- QnAService
- AutomationManager
- AutomationWorker
- AutomationBridge
- LogService
- existing browser automation
- LinkedIn implementation
- Naukri implementation
- configuration system
- secrets system
- settings
- UI architecture
- tests
- existing automation state handling
- existing application status handling

Do NOT assume the architecture.

Read the actual implementation.

Create a short architecture map before proposing changes.

Identify:

1. Current application lifecycle
2. Current automation lifecycle
3. Current Job model
4. Current Application model
5. Current Q&A model/service
6. Current resume selection mechanism
7. Current profile data source
8. Current browser/session handling
9. Current human-intervention mechanism
10. Current logging/event system
11. Current UI → Service → Repository boundaries

========================================
2. STAGEHAND VERSION
========================================

Use the current Stagehand Python SDK.

Do not assume old Stagehand APIs.

Verify the installed/current API before implementation.

Prefer the modern Python architecture:

Stagehand
+
local browser / Playwright
+
Stagehand page
+
observe()
+
act()
+
extract()

Use deterministic Playwright locators wherever possible.

Use Stagehand AI capabilities only where they provide value.

Do not blindly use:

agent.execute("apply for this job")

as the entire application mechanism.

The application workflow must remain controlled by JobPilot.

========================================
3. CORE ARCHITECTURE
========================================

Implement this conceptual architecture:

JobPilot
    |
    v
ApplicationService
    |
    v
ApplicationOrchestrator
    |
    +-----------------------+
    |                       |
    v                       v
Platform Adapters      Universal Agent
    |                       |
    |                       v
LinkedIn               Stagehand
Naukri                    |
Existing automation     Playwright
                            |
                            v
                       Company / ATS
                       Application Page


The Universal Agent must implement a clean interface.

Example conceptual interface:

UniversalApplicationAgent

    start_application()
    inspect_page()
    detect_flow()
    map_fields()
    fill_fields()
    answer_questions()
    upload_documents()
    validate_form()
    request_human_intervention()
    resume_after_intervention()
    prepare_review()
    submit_application()
    verify_submission()
    collect_result()
    stop()
    cleanup()

Adapt names to the existing architecture.

Do not blindly create these exact methods if existing abstractions make a better design.

========================================
4. IMPORTANT: FRAMEWORK ABSTRACTION
========================================

Do NOT make the entire JobPilot application depend directly on Stagehand.

Create a browser-agent abstraction.

Conceptually:

BrowserAgent
    |
    +-- StagehandBrowserAgent
    |
    +-- FutureBrowserAgent

The rest of JobPilot should depend on the abstraction.

This protects the project from future Stagehand API changes or replacement.

Stagehand should be an implementation detail of the Universal Application Agent.

========================================
5. APPLICATION STATE MACHINE
========================================

Design a robust application state machine.

At minimum consider:

DISCOVERED
QUALIFIED
APPLICATION_STARTED
PAGE_ANALYSIS
FLOW_DETECTED
FORM_FILLING
QUESTIONNAIRE
DOCUMENT_UPLOAD
VALIDATING
REVIEW_REQUIRED
SUBMISSION_READY
SUBMITTING
SUBMISSION_VERIFICATION
SUBMITTED

Exceptional states:

LOGIN_REQUIRED
CAPTCHA_REQUIRED
HUMAN_INTERVENTION_REQUIRED
UNKNOWN_FLOW
FORM_ERROR
NETWORK_ERROR
TIMEOUT
FAILED
MANUAL_REQUIRED
CANCELLED

Do NOT mix recruitment lifecycle state with browser execution state.

For example:

Recruitment status:
SUBMITTED
UNDER_REVIEW
SHORTLISTED
INTERVIEW
OFFER
REJECTED
WITHDRAWN

Automation execution state:
NOT_STARTED
RUNNING
PAUSED
WAITING_FOR_USER
SUCCESS
FAILED
MANUAL_REQUIRED
UNKNOWN

Reuse existing domain models if they already provide equivalent concepts.

Do not create duplicate state systems unnecessarily.

========================================
6. UNIVERSAL APPLICATION FLOW
========================================

The generic flow should look approximately like:

Job URL
    ↓
Open browser
    ↓
Inspect page
    ↓
Identify application mechanism
    ↓
Detect:
    - direct form
    - multi-step form
    - ATS
    - external application
    - login
    - human verification
    - unknown flow
    ↓
Build page/application representation
    ↓
Map fields to candidate profile
    ↓
Fill deterministic fields
    ↓
Handle questions
    ↓
Upload resume
    ↓
Validate
    ↓
Human review when required
    ↓
Submit
    ↓
Verify result
    ↓
Persist Application
    ↓
Persist logs/events
```

Do not assume every site follows this exact sequence.

The state machine must support branching and recovery.

========================================
7. PAGE UNDERSTANDING
=====================

Create a page understanding layer.

It should collect useful information such as:

* URL
* page title
* visible text
* forms
* inputs
* labels
* placeholders
* aria-labels
* select elements
* radio buttons
* checkboxes
* buttons
* links
* iframe information
* current step
* validation errors
* required fields

Use DOM information first.

Use Stagehand observe/extract when semantic interpretation is required.

Avoid sending unnecessary page content to the LLM.

Minimize token usage.

Never send secrets to the model unnecessarily.

========================================
8. SEMANTIC FIELD MAPPING
=========================

This is one of the most important components.

Create:

SemanticFieldMapper

It should map website fields to JobPilot profile fields.

Example:

Website:

"First Name"

→ profile.first_name

Website:

"Given Name"

→ profile.first_name

Website:

"Mobile Number"

→ profile.phone

Website:

"Years of Automation Anywhere Experience"

→ profile.experience.automation_anywhere

Website:

"LinkedIn URL"

→ profile.links.linkedin

Website:

"Upload CV"

→ selected resume

The mapper should return structured information.

Conceptually:

{
field: "...",
semantic_key: "...",
confidence: 0.97,
source: "profile.phone",
requires_confirmation: false
}

Do NOT allow the LLM to invent candidate facts.

Every answer must have provenance.

Possible sources:

PROFILE
RESUME
QNA_KNOWLEDGE_BASE
APPLICATION_HISTORY
USER_INPUT
AI_GENERATED
UNKNOWN

AI_GENERATED or UNKNOWN information must be treated differently from verified candidate data.

========================================
9. CONFIDENCE SYSTEM
====================

Create confidence levels for AI interpretation.

HIGH
MEDIUM
LOW

Example:

Phone number:
HIGH

Email:
HIGH

Resume upload:
HIGH

Years of experience:
MEDIUM/HIGH

"Are you willing to relocate?"
Potentially MEDIUM

Legal/work authorization:
USER CONFIRMATION

Unknown personal fact:
DO NOT GUESS

Use confidence to determine whether human intervention is necessary.

========================================
10. Q&A INTEGRATION
===================

Do NOT build a second Q&A system.

Reuse the existing JobPilot Q&A service.

Flow:

Question detected
↓
Normalize question
↓
Search Q&A knowledge base
↓
If verified answer exists:
use answer
↓
Else:
analyze question
↓
Search profile/resume facts
↓
Generate candidate answer
↓
Validate
↓
If safe:
present/use answer
↓
If uncertain:
HUMAN_INTERVENTION_REQUIRED

Do not hallucinate candidate information.

Every AI-generated answer should be traceable.

========================================
11. RESUME SELECTION
====================

Reuse existing ResumeService.

Do not directly read files from random paths in the UI or agent.

The agent should request:

"Select resume for Job X"

from ResumeService.

Resume selection should consider:

* target role
* skills
* experience
* job requirements
* user-selected default
* existing JobPilot resume metadata

Do not automatically modify the original resume.

If resume tailoring exists, preserve the original resume and create a separate version.

========================================
12. FORM FILLING
================

Use a hybrid strategy.

Prefer:

1. deterministic Playwright locator
2. known semantic mapping
3. cached successful selector/action
4. Stagehand observe()
5. Stagehand act()
6. human intervention

Do NOT use AI for every click.

Example:

BAD:

LLM decides every click.

GOOD:

known field → Playwright locator

unknown field → Stagehand observe()

AI identifies target

JobPilot validates target

Playwright executes action

========================================
13. STAGEHAND USAGE
===================

Use Stagehand primarily for:

* unfamiliar field discovery
* semantic element identification
* page understanding
* extraction
* recovery from DOM variations
* unknown application layouts

Use deterministic Playwright for:

* navigation
* known selectors
* typing
* selecting
* uploading
* waiting
* reading deterministic states
* submission verification when possible

Use Stagehand observe() to discover candidate actions.

Use act() for atomic actions.

Use extract() for structured information.

Do not make huge multi-step AI instructions when deterministic smaller actions are possible.

========================================
14. ACTION SAFETY
=================

Every AI action must be validated before execution.

Conceptually:

AI
↓
Action
↓
ActionValidator
↓
Permission/Policy Check
↓
Browser Executor

Supported action types should be structured.

Examples:

NAVIGATE
CLICK
FILL
SELECT
CHECK
UNCHECK
UPLOAD
SCROLL
EXTRACT
WAIT
REQUEST_USER
STOP

Do not allow arbitrary code execution from the LLM.

Do not allow arbitrary shell commands from the LLM.

Do not allow the model to modify JobPilot files directly.

========================================
15. SUBMISSION SAFETY
=====================

Submitting an application is a consequential action.

Initially:

ALWAYS require explicit user confirmation before final submission.

Flow:

Application ready
↓
Review screen
↓
User sees:
- job
- company
- resume
- answers
- required fields
- external URL
- detected warnings
↓
User clicks:
"Submit Application"
↓
Agent performs submission
↓
Verify result

Do NOT automatically submit during the first implementation.

Build the architecture so automatic submission could be configurable later.

========================================
16. HUMAN-IN-THE-LOOP
=====================

This must be a first-class capability.

Create a HumanInterventionRequest model/event.

Examples:

LOGIN_REQUIRED
CAPTCHA_REQUIRED
UNKNOWN_QUESTION
AMBIGUOUS_FIELD
MISSING_INFORMATION
UNKNOWN_FLOW
LEGAL_ATTESTATION
SUBMISSION_CONFIRMATION
APPLICATION_ERROR

The UI should receive an event.

Example:

"Human verification required"

Actions:

[Open Browser]
[Continue]
[Skip Application]

The browser must remain alive while waiting for the user.

After the user completes the step:

RESUME

Do not restart the application unnecessarily.

========================================
17. SECURITY / CAPTCHA / BOT PROTECTION
=======================================

IMPORTANT:

Do NOT implement:

* CAPTCHA solving
* CAPTCHA bypass
* stealth plugins intended to evade detection
* fingerprint spoofing
* proxy rotation for evasion
* bot-detection bypass
* rate-limit bypass
* security-control bypass
* unauthorized scraping
* credential theft
* cookie extraction for unauthorized access

If a security or human-verification checkpoint appears:

pause the agent.

request human intervention.

This is a deliberate product feature.

For platforms whose terms prohibit unauthorized automation, do not design mechanisms intended to circumvent those restrictions.

========================================
18. DOMAIN / SITE POLICY
========================

Implement optional domain policy controls.

Examples:

allowed_domains
blocked_domains
manual_only_domains

The Universal Agent should never blindly navigate arbitrary domains.

Before application execution:

validate destination domain.

Log the decision.

Allow the user to configure domain behavior.

========================================
19. LOGIN HANDLING
==================

Do not automate credential discovery.

Credentials must come from JobPilot's existing SecretsService or user interaction.

Preferred flow:

LOGIN_REQUIRED
↓
Open browser
↓
User logs in
↓
Detect authenticated state
↓
Continue

Never expose passwords to Stagehand model context.

Never log passwords, session cookies, API keys, or authentication tokens.

========================================
20. BROWSER SESSION MANAGEMENT
==============================

Create a dedicated browser session manager.

Requirements:

* persistent profile support
* clean startup
* clean shutdown
* session recovery
* browser crash recovery
* page tracking
* multiple tabs
* active application tab
* timeout handling
* cancellation

Do not conflict with the existing LinkedIn/Naukri Chrome profiles.

Universal Agent should have its own browser profile/session configuration.

========================================
21. OBSERVABILITY
=================

Every agent action must be observable.

Create structured events such as:

AgentStarted
PageLoaded
PageAnalyzed
FlowDetected
FieldMapped
FieldFilled
QuestionDetected
AnswerSelected
ResumeSelected
ResumeUploaded
ValidationError
HumanInterventionRequested
HumanInterventionCompleted
ReviewReady
SubmissionStarted
SubmissionVerified
AgentPaused
AgentResumed
AgentFailed
AgentCompleted

Integrate with existing LogService and AutomationBridge where appropriate.

Do not duplicate existing event systems unnecessarily.

========================================
22. DEBUGGING / REPLAY
======================

The Universal Agent will be difficult to debug without evidence.

For each run, support optional debug artifacts:

* URL
* timestamp
* page title
* current state
* screenshots
* sanitized DOM snapshot
* action history
* Stagehand observations
* errors
* validation messages

Never store secrets.

Make debug capture configurable.

========================================
23. ACTION / OBSERVATION CACHE
==============================

Investigate Stagehand's observation caching capabilities.

Where safe, cache successful semantic mappings/actions.

Example:

"Find email field"

→ previously mapped selector

On next visit:

reuse selector if valid

If invalid:

observe again.

Do not blindly replay stale selectors.

Invalidate cache when DOM/page structure changes.

========================================
24. ATS / CAREER PORTAL STRATEGY
================================

Do NOT initially build separate adapters for every ATS.

First build:

Generic Application Agent

Then test against several real environments.

Potential categories:

* Greenhouse
* Lever
* Workday
* Ashby
* SmartRecruiters
* custom company career page

Only create specialized adapters when repeated patterns justify them.

Architecture should allow:

GenericAgent
GreenhouseAdapter
LeverAdapter
WorkdayAdapter
etc.

But do not prematurely build all adapters.

========================================
25. EXTERNAL APPLICATION DETECTION
==================================

Some job pages will redirect to:

* company careers page
* ATS
* external application portal
* another job board

Detect and classify this.

Example:

APPLICATION_TARGET_CHANGED

Store:

source_job_url
application_url
application_domain

Do NOT overwrite the original job URL.

This must integrate with the existing Job/Application model.

========================================
26. APPLICATION RESULT VERIFICATION
===================================

Never assume:

"Submit clicked = Application successful"

Verify using multiple signals where available:

* success message
* confirmation page
* application ID
* URL change
* submitted state
* confirmation email if later integrated

Return structured result:

SUCCESS
FAILED
UNKNOWN
MANUAL_REQUIRED

If uncertain:

UNKNOWN

Do not falsely mark the application as submitted.

========================================
27. FAILURE RECOVERY
====================

Build recovery strategies.

Example:

NETWORK_ERROR
↓
retry controlled number of times

DOM_CHANGED
↓
re-observe

FIELD_NOT_FOUND
↓
semantic search

VALIDATION_ERROR
↓
extract validation message
↓
repair

UNKNOWN_QUESTION
↓
human intervention

CAPTCHA
↓
human intervention

UNKNOWN_FLOW
↓
manual mode

Never create infinite retry loops.

========================================
28. COST CONTROL
================

LLM calls must be controlled.

Do not call an LLM for:

* every keystroke
* every field
* every click
* deterministic validation
* obvious DOM operations

Track:

LLM calls per application
tokens if available
latency
estimated cost
Stagehand action count

Expose useful metrics in debug logs.

========================================
29. LOCAL AI SUPPORT
====================

JobPilot already has local AI/Ollama-related infrastructure.

Investigate whether Stagehand can work with the existing OpenAI-compatible/local model endpoint.

Do not assume compatibility.

Test it.

Document:

SUPPORTED
PARTIALLY_SUPPORTED
NOT_SUPPORTED

If local models are not reliable enough for browser reasoning, allow a configurable cloud model provider.

Do not hard-code a provider.

Do not store API keys in source code.

========================================
30. PYTHON / THREADING
======================

JobPilot is a PySide6 desktop application.

Browser automation MUST NOT block the Qt main thread.

Reuse the existing worker architecture where appropriate.

Possible architecture:

Qt UI
↓
AutomationWorker
↓
ApplicationOrchestrator
↓
UniversalAgent
↓
Stagehand/Playwright

The UI must remain responsive during:

* page navigation
* Stagehand reasoning
* LLM calls
* file upload
* waits
* browser operations

Support cancellation.

========================================
31. UI INTEGRATION
==================

Do not create a separate ugly "AI agent console."

Integrate the agent into the existing modern JobPilot ATS UI.

Application details should show:

Application Mode:

Universal Agent

Current State:

FORM_FILLING

Current Website:

company.com

Progress:

Step 3 of 5

Human Action Required:

Yes/No

Current Action:

Mapping "Years of Experience"

Confidence:

High

Actions:

[Pause]
[Resume]
[Cancel]
[Open Browser]
[Review Application]

The UI should be modern, compact, and consistent with existing JobPilot design.

Support dark and light themes.

========================================
32. APPLICATION REVIEW UI
=========================

Before final submission, provide a review interface.

Show:

Job
Company
Application URL
Resume
Detected questions
Answers
Warnings
Unresolved fields
Confidence
Human-confirmation items

Example:

✓ First Name
✓ Email
✓ Phone
✓ Resume
✓ LinkedIn
⚠ Work Authorization — Confirm
⚠ Sponsorship — Confirm
✓ Experience

Final action:

[Submit Application]

========================================
33. DATABASE CHANGES
====================

Before creating new tables:

inspect existing schema.

Reuse existing Application and related models wherever possible.

Only add database fields/models where there is a genuine domain requirement.

Possible concepts:

ApplicationExecution
AgentRun
AgentEvent
HumanInterventionRequest

But do not automatically create all of these.

Determine whether existing Application/Automation events can support the feature.

If migrations are required:

create proper migration.

Do not destroy existing user data.

========================================
34. CONFIGURATION
=================

Integrate with existing SettingsService/configuration.

Potential settings:

Universal Agent enabled
Browser engine
Model provider
Model name
LLM timeout
Maximum agent steps
Human confirmation required
Automatic submission enabled/disabled
Debug screenshots
Domain policy
LLM cost limits
Application timeout

Do not change existing defaults unrelated to this feature.

Do not silently modify existing LinkedIn/Naukri settings.

========================================
35. TESTING STRATEGY
====================

Testing must happen at multiple levels.

Unit tests:

* field mapper
* semantic normalization
* confidence calculation
* action validator
* state transitions
* domain policy
* result verification
* recovery logic

Integration tests:

* fake application form
* multi-step form
* dropdowns
* radio buttons
* checkboxes
* resume upload
* validation errors
* unknown question
* human intervention
* login required
* external redirect
* submission confirmation

Browser tests:

Use controlled local test pages.

Do not use real job portals for automated CI.

Create local HTML fixtures representing different ATS patterns.

Regression tests:

Existing LinkedIn tests must continue passing.

Existing Naukri tests must continue passing.

Existing application tests must continue passing.

Existing UI tests must continue passing.

========================================
36. IMPLEMENTATION PHASES
=========================

DO NOT start coding immediately.

First produce a detailed implementation plan.

Break the work into phases.

Recommended structure:

PHASE 0
Repository and architecture audit

PHASE 1
Stagehand proof-of-concept

PHASE 2
BrowserAgent abstraction

PHASE 3
Universal Application Agent core

PHASE 4
Page understanding

PHASE 5
Semantic field mapping

PHASE 6
Profile/Q&A/Resume integration

PHASE 7
Application state machine

PHASE 8
Human-in-the-loop system

PHASE 9
Action validation and safety

PHASE 10
Submission verification and recovery

PHASE 11
Application review UI

PHASE 12
Automation worker integration

PHASE 13
Observability/debugging

PHASE 14
ATS compatibility testing

PHASE 15
Performance/cost optimization

PHASE 16
Production hardening

Adjust this list after auditing the real repository.

Do not blindly follow it.

========================================
37. EVERY PHASE MUST CONTAIN
============================

For every proposed phase provide:

1. Objective
2. Why it is needed
3. Existing files affected
4. New files
5. Modified files
6. Classes/functions
7. Database changes
8. UI changes
9. Service changes
10. Stagehand integration
11. Tests
12. Risks
13. Rollback strategy
14. Acceptance criteria
15. Dependencies
16. Estimated complexity
17. What must NOT change

========================================
38. IMPLEMENTATION RULE
=======================

After generating the plan:

STOP.

Do NOT implement anything yet.

Ask for approval.

Only after explicit approval:

Implement one phase at a time.

After each phase:

1. Run tests.
2. Report changed files.
3. Report tests.
4. Report failures.
5. Fix failures.
6. Confirm acceptance criteria.
7. Show what remains.
8. Ask for approval before moving to the next major phase if the change is architectural.

========================================
39. NO BIG-BANG REFACTOR
========================

Do NOT:

* rewrite JobPilot
* replace PySide6
* replace SQLAlchemy
* replace existing services
* replace existing automation
* rewrite LinkedIn
* rewrite Naukri
* replace Q&A
* replace ResumeService
* move everything into an AI agent

Build incrementally.

========================================
40. PRESERVE EXISTING AUTOMATION
================================

This is a hard requirement.

Existing:

LinkedIn automation
Naukri automation

must continue working.

The Universal Application Agent is additive.

Architecture:

Existing Automation
+
Universal Application Agent

NOT:

Existing Automation
→ replaced by Universal Agent

========================================
41. COMMERCIALIZATION CONSIDERATION
===================================

JobPilot may eventually become a commercial desktop application.

Therefore:

* review third-party licenses
* record Stagehand license
* record Playwright license
* review transitive dependency licenses where relevant
* avoid copyleft contamination where it creates commercial distribution concerns
* do not embed third-party credentials
* do not hard-code API providers
* keep provider integrations replaceable

Do not make commercial/legal conclusions yourself.

Flag anything requiring legal review.

========================================
42. PLATFORM POLICY BOUNDARY
============================

This feature is intended for legitimate application workflows.

Do not implement features intended to:

* bypass CAPTCHA
* bypass anti-bot systems
* evade rate limits
* evade security controls
* defeat access restrictions
* spoof fingerprints to evade detection
* rotate proxies to evade restrictions
* automate platforms in violation of their stated restrictions

Where human verification or platform restrictions occur:

pause and request user intervention.

========================================
43. FIRST DELIVERABLE
=====================

Your FIRST response must NOT contain implementation code.

Return:

# Universal AI Application Agent — Implementation Plan

## 1. Current JobPilot Architecture

Show what exists.

## 2. Integration Point

Show exactly where UniversalApplicationAgent fits.

## 3. Stagehand Integration Strategy

Explain how Stagehand v4 will be integrated with Python/Playwright.

## 4. Proposed Architecture

Provide a text architecture diagram.

## 5. State Machine

Provide the complete state transition design.

## 6. Phase-by-Phase Implementation

Provide detailed phases.

## 7. Files to Add

List exact proposed paths.

## 8. Files to Modify

List exact existing paths.

## 9. Database Changes

Only genuine required changes.

## 10. UI Changes

Explain how the existing UI will integrate with the agent.

## 11. Human-in-the-Loop

Explain every checkpoint.

## 12. Stagehand Usage

Clearly separate:

Stagehand AI
vs
deterministic Playwright
vs
JobPilot business logic.

## 13. Security

Explain credential handling, secrets, logs, browser profiles, domain policies.

## 14. Platform Safety

Explain how restricted/verification flows will be handled without bypassing security controls.

## 15. Testing Strategy

Unit + integration + browser fixture + regression.

## 16. Performance and LLM Cost

Explain how unnecessary model calls will be avoided.

## 17. Risks

List technical risks and mitigation.

## 18. Rollback Strategy

Explain how the feature can be disabled without affecting existing automation.

## 19. Acceptance Criteria

Define objective criteria for declaring the feature production-ready.

## 20. Recommended Implementation Order

Give the exact order you recommend.

STOP AFTER THE PLAN.

WAIT FOR MY APPROVAL.

========================================
FINAL RULE
==========

You are not building a generic browser bot.

You are extending JobPilot with a controlled, observable, recoverable AI application engine.

The architecture must remain:

PySide6
→ Services
→ Application Orchestrator
→ Universal Application Agent
→ Browser Agent abstraction
→ Stagehand + Playwright

while existing:

LinkedIn automation
Naukri automation

remain untouched and operational.

Do not code until I approve the detailed plan.

```

### Why I want this prompt structured this way

The key thing is that it **forces the coding agent to inspect your existing JobPilot before touching it**. That's important because you've already spent a lot of work on the service/database/automation architecture.

Also, the current Stagehand Python SDK specifically supports local browser use and exposes Playwright-style control plus `act`, `observe`, and `extract`, so this architecture can keep your application logic deterministic while using AI only where the website is unfamiliar. :contentReference[oaicite:2]{index=2}

I would also make the agent test Stagehand against **local fake application pages first**, rather than immediately pointing it at real company portals. That gives you a controlled environment for testing multi-step forms, dropdowns, validation errors, uploads, unknown questions, and recovery.

One particularly useful Stagehand feature for this architecture is that `observe()` can identify actionable elements and return selectors that can then be handled through Playwright, which fits your desired **AI discovers → JobPilot validates → deterministic browser executes** pattern. :contentReference[oaicite:3]{index=3}

**Do not let the coding agent skip directly to implementation.** Give it this prompt, let it inspect JobPilot and produce the phase plan, then bring that plan here. I can review the proposed architecture phase-by-phase before you approve the agent to start modifying the code.
```

[1]: https://github.com/browserbase/stagehand-python?utm_source=chatgpt.com "GitHub - browserbase/stagehand-python: The AI Browser Automation Framework · GitHub"
[2]: https://github.com/browserbase/stagehand/blob/main/packages/sdk-python/README.md?utm_source=chatgpt.com "stagehand/packages/sdk-python/README.md at main · browserbase/stagehand · GitHub"
