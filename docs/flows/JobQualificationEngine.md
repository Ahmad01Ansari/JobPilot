You are working on JobPilot, a local-first PySide6 desktop AI job-search application.

TASK:
Implement the Job Qualification Engine as the next isolated product capability.

IMPORTANT:
Do NOT redesign the Dashboard yet.
Do NOT implement Today's Job Hunt yet.
Do NOT add new job platforms.
Do NOT modify LinkedIn/Naukri automation.
Do NOT work on Glassdoor.
Do NOT work on the Universal Application Agent.

The goal of this phase is ONLY:

Existing Jobs
    ↓
JobQualificationService
    ↓
QualificationResult
    ↓
persist qualification result
    ↓
expose results to existing Jobs domain/UI

==================================================
1. FIRST: AUDIT THE REPOSITORY
==================================================

Before writing code, inspect the existing repository.

Understand:

- current project structure
- architecture
- Job model
- JobRepository
- JobService
- Application model/service
- ProfileService
- ResumeService
- QnAService
- database/session setup
- migrations/schema strategy
- existing enums
- existing settings/configuration
- existing AI/LLM abstraction
- existing UI architecture
- existing tests
- existing logging
- existing theme/design system

Search for all existing references to:

- Job
- JobRepository
- JobService
- Application
- Profile
- Resume
- QnA
- qualification
- match
- score
- ranking
- recommendation
- AI service
- LLM
- settings

Do not assume the architecture.
Use the existing implementation as the source of truth.

Before implementation, produce:

1. Current architecture summary
2. Relevant files/classes
3. Existing Job schema
4. Existing repository/service interfaces
5. Existing AI abstraction
6. Existing profile/resume/Q&A sources
7. Existing tests
8. Proposed minimal changes
9. Potential compatibility risks

Do not code until this audit is complete.

==================================================
2. ARCHITECTURAL RULE
==================================================

Follow:

UI
 ↓
Service
 ↓
Repository
 ↓
SQLAlchemy
 ↓
Database

The UI must NOT:

- query SQLAlchemy directly
- calculate qualification scores
- call the LLM directly
- contain qualification business rules
- access database sessions directly

Qualification logic belongs in the service/domain layer.

Recommended structure:

JobQualificationService
    ↓
QualificationEngine
    ↓
Rule/Scoring components
    ↓
AI semantic analysis when required
    ↓
QualificationRepository
    ↓
JobQualification table

Reuse existing services instead of creating duplicates.

Do not create:

JobService2
ProfileService2
AIService2
ResumeService2

==================================================
3. CORE DESIGN
==================================================

The existing Job entity remains the source job record.

Do NOT turn Job into a giant qualification object.

Create a separate persisted qualification result associated with Job.

Conceptually:

Job
 |
 └── JobQualification
       ├── score
       ├── decision
       ├── confidence
       ├── matched_skills
       ├── missing_skills
       ├── hard_filter_results
       ├── positive_reasons
       ├── negative_reasons
       ├── recommendation
       ├── evaluated_at
       └── engine/model version

Use the repository's existing naming conventions.

The exact schema must follow the existing project's conventions.

==================================================
4. QUALIFICATION RESULT
==================================================

Create a structured qualification result.

Minimum conceptual fields:

- job_id
- score
- decision
- confidence
- matched_skills
- missing_skills
- hard_filter_failures
- positive_reasons
- negative_reasons
- recommendation
- evaluated_at
- rules_version
- model_version if AI is used
- evaluation_status
- error information where appropriate

Decisions should be explicit.

Recommended values:

STRONG_MATCH
GOOD_MATCH
POSSIBLE_MATCH
WEAK_MATCH
REJECTED
REVIEW_REQUIRED

Do not introduce a decision that silently means multiple things.

The exact enum naming should follow existing project conventions if an enum system already exists.

==================================================
5. SEPARATE SCORE FROM DECISION
==================================================

Do NOT use:

score >= 80 => automatically apply

The score and recommendation are different concepts.

Example:

Score: 72
Decision: POSSIBLE_MATCH

Reason:

- Strong technical skill alignment
- Experience requirement slightly above candidate experience
- Salary information unavailable

The system should help the user decide.

It must not silently decide consequential actions such as applying.

==================================================
6. QUALIFICATION PIPELINE
==================================================

Implement the qualification pipeline in this order:

STEP 1 — INPUT VALIDATION

Validate that the Job contains enough information.

At minimum consider:

- title
- company
- description
- location where available

If the job lacks sufficient information:

evaluation_status = INSUFFICIENT_DATA

Do not manufacture missing information.

Do not ask the LLM to invent missing job requirements.

--------------------------------------------------

STEP 2 — HARD FILTERS

Evaluate deterministic constraints first.

Possible filters:

- target role
- excluded role/title
- experience
- location
- remote preference
- employment type
- salary minimum
- excluded company

Only implement filters supported by the existing Profile/settings schema.

DO NOT invent configuration fields just to complete the feature.

Hard filters must be explainable.

Example:

{
  "passed": false,
  "rule": "experience",
  "reason": "Job requires 5+ years; profile target is 1–3 years"
}

A hard-filter failure should be visible to the user.

Do not automatically reject every mismatch unless the existing user preference explicitly defines it as a hard exclusion.

--------------------------------------------------

STEP 3 — STRUCTURED MATCHING

Calculate meaningful components where sufficient data exists.

Possible components:

- role match
- skill match
- experience match
- location match
- salary match
- employment-type match

Do not score unavailable information as a false negative.

For example:

Salary unavailable

must NOT automatically mean:

salary_match = 0

Instead represent:

salary_match = UNKNOWN

or equivalent project convention.

--------------------------------------------------

STEP 4 — SEMANTIC MATCHING

Use AI only where semantic reasoning provides real value.

Example:

Job:

"Build enterprise workflow automation solutions."

Candidate skills:

- Automation Anywhere
- UiPath
- Python
- REST APIs
- SQL

A pure keyword matcher may miss the relationship.

The semantic layer may determine:

strong conceptual alignment.

AI should produce structured output.

Do NOT accept arbitrary free-form AI output as trusted application logic.

Use a strict schema.

Conceptually:

{
  "matched_skills": [],
  "missing_skills": [],
  "positive_reasons": [],
  "negative_reasons": [],
  "semantic_score": 0,
  "confidence": 0
}

Validate the response.

If AI fails:

- do not crash the qualification pipeline
- preserve deterministic scoring where possible
- mark AI component unavailable
- expose the limitation

Do NOT fabricate an AI result.

==================================================
7. SOURCE OF TRUTH
==================================================

Candidate facts must come from trusted JobPilot sources.

Possible sources:

ProfileService
ResumeService
QnAService
user-provided data

Do not allow AI to invent candidate facts.

Never infer unsupported facts such as:

- years of experience
- salary
- degree
- employer
- certification
- skill
- location
- notice period

If information is unknown:

UNKNOWN

not:

probably true.

==================================================
8. SCORING
==================================================

Design a transparent scoring system.

Do NOT create an arbitrary black-box score.

The scoring system must be explainable.

For example, conceptually:

Role Match
Skill Match
Experience Match
Location Match
Salary Match
Employment Match

combined into an overall score.

However:

DO NOT blindly use these exact weights.

First inspect existing project requirements/settings.

If no scoring strategy exists, implement a simple documented baseline with configurable constants rather than scattering magic numbers throughout the code.

Example:

ROLE_WEIGHT
SKILL_WEIGHT
EXPERIENCE_WEIGHT
LOCATION_WEIGHT
SALARY_WEIGHT

Keep weights centralized.

Document the formula.

==================================================
9. UNKNOWN DATA
==================================================

Unknown is NOT the same as failure.

Examples:

Salary not listed
→ UNKNOWN

Remote policy not stated
→ UNKNOWN

Experience requirement not found
→ UNKNOWN

Do not punish every unknown value.

The engine should distinguish:

PASS
FAIL
UNKNOWN

This distinction must survive into the qualification result where useful.

==================================================
10. AI COST CONTROL
==================================================

Do not call an LLM for every possible operation.

Use:

deterministic filtering
        ↓
structured matching
        ↓
AI semantic analysis only when useful

Avoid unnecessary repeated AI calls.

Qualification should support:

- deterministic-only evaluation
- AI-assisted evaluation

according to existing project capabilities/configuration.

If AI is unavailable locally:

the deterministic engine must still function.

The feature must not become completely unusable because Ollama/API credentials are unavailable.

==================================================
11. RE-EVALUATION
==================================================

Qualification results become stale.

Support explicit re-evaluation.

Conceptually:

qualify_job(job_id)
requalify_job(job_id)
get_qualification(job_id)

Avoid blindly recalculating every job whenever the Jobs page opens.

Store:

evaluated_at
rules_version
model_version

when supported by the architecture.

This allows future re-evaluation when:

- profile changes
- resume changes
- qualification rules change
- AI model changes

==================================================
12. BULK QUALIFICATION
==================================================

Support qualifying multiple existing jobs.

Conceptually:

qualify_jobs(job_ids)

and, if appropriate:

qualify_unqualified_jobs()

Do not block the Qt main thread.

If qualification is computationally expensive or calls an LLM:

use the project's worker/background-task pattern.

The UI must remain responsive.

==================================================
13. JOB REPOSITORY INTEGRATION
==================================================

Integrate with the EXISTING JobRepository.

Do not replace it.

Do not rewrite it unless the audit proves a minimal extension is necessary.

The QualificationRepository should handle qualification persistence.

JobService remains responsible for Jobs.

JobQualificationService is responsible for qualification.

Conceptually:

JobService
    → JobRepository

JobQualificationService
    → JobRepository/read access
    → QualificationRepository/write/read qualification

Do not duplicate Job records.

==================================================
14. JOBS UI INTEGRATION
==================================================

Make only the minimum Jobs UI changes necessary to expose qualification.

Do NOT redesign the Jobs page.

Do NOT redesign the Dashboard.

Add only useful qualification information such as:

- Match score
- Decision
- qualification status

Potentially allow:

[View Qualification]

which shows:

Score
Decision
Matched skills
Missing skills
Hard filter issues
Positive reasons
Negative reasons
Recommendation
Evaluation timestamp

Use the existing design system.

Do not introduce a new visual language.

==================================================
15. EXPLAINABILITY
==================================================

A user must be able to answer:

"Why did JobPilot give this job 84%?"

Example:

84% — GOOD MATCH

Strengths:
✓ RPA development
✓ Python
✓ Automation Anywhere
✓ SQL
✓ REST APIs

Potential gaps:
△ Workday experience not found

Experience:
✓ Within target range

Location:
✓ Matches preference

Recommendation:
Good candidate for review.

Do not produce meaningless generic explanations.

==================================================
16. DO NOT AUTO-APPLY
==================================================

Qualification Engine must NOT:

- submit applications
- open browsers
- send recruiter emails
- send outreach
- modify application status
- skip jobs automatically based solely on AI
- make consequential decisions

This phase is analysis/ranking only.

==================================================
17. DATABASE
==================================================

Before modifying the database:

inspect:

- current SQLAlchemy models
- migration mechanism
- naming conventions
- relationship conventions
- indexes
- timestamps
- enum patterns

Create the minimum schema necessary.

Important indexes should be considered for:

- job_id
- decision
- score
- evaluated_at

Do not invent a migration system if one already exists.

Follow existing migration conventions.

==================================================
18. TESTING
==================================================

Before implementation:

record the existing test count.

After implementation:

run the full relevant test suite.

Add tests for:

1. Job with strong match
2. Job with weak match
3. Job with missing description
4. Job with missing salary
5. Job with missing experience
6. Role mismatch
7. Skill match
8. Skill mismatch
9. Location match
10. Location mismatch
11. Unknown values
12. Hard filter failure
13. Multiple hard filter failures
14. AI available
15. AI unavailable
16. AI malformed response
17. AI timeout/error
18. Deterministic fallback
19. Requalification
20. Existing qualification replacement/versioning
21. Bulk qualification
22. Job not found
23. Duplicate qualification request
24. Persistence/retrieval
25. UI display
26. Regression of existing JobService/JobRepository behavior

Do not claim tests pass unless they actually pass.

==================================================
19. PERFORMANCE
==================================================

Qualification must not make the Jobs screen slow.

Avoid:

for job in jobs:
    call expensive AI synchronously

Instead:

- deterministic filtering first
- batch where appropriate
- background workers for expensive work
- caching/persisted results
- explicit requalification

Do not introduce unnecessary AI calls.

==================================================
20. LOGGING
==================================================

Use the existing LogService/logging conventions.

Log useful operational information:

- qualification started
- qualification completed
- qualification failed
- AI unavailable
- evaluation duration
- number of jobs processed

Never log:

- API keys
- passwords
- cookies
- tokens
- credentials
- sensitive personal data unnecessarily

==================================================
21. ERROR STATES
==================================================

Clearly distinguish:

SUCCESS
INSUFFICIENT_DATA
AI_UNAVAILABLE
FAILED
UNKNOWN

Do not convert failures into:

score = 0

A failed evaluation is not the same thing as a bad job.

==================================================
22. DOCUMENTATION
==================================================

Add/update documentation describing:

- qualification architecture
- scoring formula
- hard filters
- unknown handling
- AI role
- result states
- re-evaluation
- data model
- extension points

Do not create duplicate architecture documentation if an existing document already covers it.

Update the relevant existing documentation instead.

==================================================
23. FUTURE COMPATIBILITY
==================================================

Design this so the future architecture can become:

Job Discovery
      ↓
Jobs
      ↓
Qualification
      ↓
Ranking
      ↓
Action Engine
      ↓
Today's Job Hunt
      ↓
Applications / Outreach / Follow-ups

Today's Job Hunt is NOT part of this implementation.

However, QualificationResult must be easy for a future ActionService to consume.

For example:

ActionService can later ask:

get_top_qualified_jobs_for_today()

without rewriting the qualification engine.

==================================================
24. DO NOT OVERENGINEER
==================================================

This is an important first version.

Do NOT build:

- ML training pipeline
- custom fine-tuned model
- vector database
- autonomous AI agent
- scraping system
- new job discovery system
- recruiter discovery
- new platform integration
- dashboard redesign
- notification system
- Today's Job Hunt
- automatic application decisions

Use the simplest architecture that can evolve cleanly.

==================================================
25. IMPLEMENTATION ORDER
==================================================

Follow this exact sequence:

PHASE 0
Repository audit.

PHASE 1
Design qualification domain/model.

PHASE 2
Database model + migration.

PHASE 3
QualificationRepository.

PHASE 4
Deterministic QualificationEngine.

PHASE 5
Scoring + decision logic.

PHASE 6
Profile/Resume/QnA integration.

PHASE 7
AI semantic matching through existing AI abstraction.

PHASE 8
JobQualificationService.

PHASE 9
Bulk qualification/background worker if required.

PHASE 10
Minimal Jobs UI integration.

PHASE 11
Tests.

PHASE 12
Full regression tests.

PHASE 13
Documentation.

PHASE 14
Final architecture audit.

==================================================
26. ACCEPTANCE CRITERIA
==================================================

The feature is complete only when:

[ ] Existing JobRepository still works
[ ] Existing JobService still works
[ ] Existing automation is untouched
[ ] Jobs can be qualified individually
[ ] Existing jobs can be bulk-qualified
[ ] Results persist in the database
[ ] Score is explainable
[ ] Decision is explicit
[ ] Unknown data is handled correctly
[ ] Hard filters are explainable
[ ] AI is optional/failure-safe
[ ] No candidate facts are invented
[ ] Qualification failures are not treated as bad jobs
[ ] Results can be re-evaluated
[ ] Jobs UI can display qualification
[ ] Qt UI remains responsive
[ ] No Dashboard redesign occurred
[ ] No Today's Job Hunt implementation occurred
[ ] No new platform automation occurred
[ ] Tests pass
[ ] Existing regression tests pass
[ ] Documentation is updated

==================================================
27. FINAL REPORT
==================================================

At the end, report:

1. What was found during audit
2. Files changed
3. Database changes
4. New services/repositories/models
5. Scoring formula
6. Decision rules
7. AI integration
8. UI changes
9. Tests before implementation
10. Tests after implementation
11. Any failures
12. Any known limitations
13. What should be done in the next phase

IMPORTANT:

Do not start the next phase automatically.

Stop after completing the Qualification Engine.

The next planned feature after successful verification is:

ACTION ENGINE → TODAY'S JOB HUNT

But that must be handled as a separate implementation phase.