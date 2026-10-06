# JobPilot — Master AI Development Constitution
**Primary Source of Truth for Autonomous AI Agents and Engineers**
*Version: 1.0.0 | Status: Active & Mandatory | Scope: Repository-Wide*

---

## 1. Prime Directive

This document is the **immutable constitution** of the JobPilot codebase. Every AI coding agent, pair programmer, and engineer interacting with this repository **MUST** adhere strictly to the rules, architectural boundaries, security constraints, and development workflows set forth herein.

### The Five Inviolable Laws:
1. **Inspect Before Modifying:** Never alter code based solely on prompts or assumptions. Always read the active implementation, call graph, and existing tests first.
2. **Preserve Architectural Boundaries:** UI never talks directly to databases or browser drivers; automation runs in worker threads; business logic lives in services; persistence lives in repositories.
3. **Protect Working Automation:** Working LinkedIn, Naukri, Indeed, Glassdoor, Foundit, and Universal automation engines are protected production assets. Never rewrite working engines just to make them look cleaner.
4. **Zero Fake Implementations & Zero Hallucination:** Never fabricate metrics, mock production statuses, hallucinate candidate facts, or swallow errors with `except: pass`.
5. **Verify Before Declaring Complete:** Code is not complete until it compiles, runs targeted and regression tests, respects edge cases, and satisfies the Mandatory Completion Checklist.

---

## 2. System Architecture & Layer Boundaries

JobPilot follows a strict multi-tier layered architecture:

```
┌────────────────────────────────────────────────────────┐
│                   PRESENTATION LAYER                   │
│   Desktop GUI (PySide6)   │   Local Web API (Flask)    │
│       app/ui/views/       │           app.py           │
└───────────────────────────┬────────────────────────────┘
                            │ Calls Service Methods / Receives Qt Signals
┌───────────────────────────▼────────────────────────────┐
│                      SERVICE LAYER                     │
│                   app/services/                        │
│   JobService, ApplicationService, ProfileService,      │
│   AutomationService, AutomationBridge, QnAService,     │
│   ResumeService, OutreachService, PlatformService      │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       Uses Repositories         Dispatches Events & Orchestrates
                │                        │
┌───────────────▼────────┐      ┌────────▼───────────────┐
│    REPOSITORY LAYER    │      │    AUTOMATION WORKER   │
│   app/repositories/    │      │   QThread / TaskRunner │
└───────────────┬────────┘      └────────┬───────────────┘
                │                        │
       Queries / Persists         Executes Platform Engine
                │                        │
┌───────────────▼────────┐      ┌────────▼───────────────┐
│     DATABASE LAYER     │      │   AUTOMATION ENGINES   │
│   SQLAlchemy 2.0 Models│      │   platforms/ & modules/│
│   SQLite (jobpilot.db) │      │   LinkedIn, Naukri,    │
│   Tracker (legacy DB)  │      │   Indeed, Glassdoor    │
└────────────────────────┘      └────────────────────────┘
```

### 2.1. Strict Layer Isolation Rules

| From Layer | Permitted Destinations | Forbidden Destinations |
|---|---|---|
| **UI (`app/ui/`)** | Service Layer (`app/services/`), UI State (`AppState`), UI Models/Tokens | Repositories, SQLAlchemy Sessions, Database Files, Selenium/Playwright WebDrivers, Network HTTP Endpoints |
| **Service (`app/services/`)** | Repositories (`app/repositories/`), Other Services, Automation Bridge, Intelligence Engines | UI Widgets/Views, Direct raw SQL queries (bypassing repositories) |
| **Repository (`app/repositories/`)** | Database Sessions (`app/db/session.py`), SQLAlchemy Models (`app/db/models/`), DTOs | UI Layer, Automation Engines, Browser Drivers |
| **Automation (`platforms/`)** | Automation Bridge (`AutomationBridge`), Intelligence Engines (`modules/qna_engine.py`), Tracker (`modules/tracker.py`), Browser Controllers | Direct UI widget manipulation, Direct database session commits |

---

## 3. Standard AI Agent Workflow (8-Phase Lifecycle)

No agent may jump directly from `User Request → Code Edits`. All work must execute through this 8-phase workflow:

```
PHASE 0: UNDERSTAND  ──► Read rules, verify intent, check constraints
        │
PHASE 1: AUDIT       ──► Inspect live files, call paths, active models & tests
        │
PHASE 2: PLAN        ──► Define smallest safe change, identify risks & test plan
        │
PHASE 3: IMPLEMENT   ──► Write minimal, robust code preserving existing behavior
        │
PHASE 4: TEST        ──► Execute baseline, targeted, and full regression tests
        │
PHASE 5: VERIFY      ──► Validate live behavior, edge cases, and layer compliance
        │
PHASE 6: DOCUMENT    ──► Update relevant architecture docs & working flows
        │
PHASE 7: REPORT      ──► Structured report: what changed, tested, risks, limits
```

### Phase Details:
- **Phase 0 — Understand:** Identify requirements, constraints, and platform scope. Never make assumptions; ask clarifying questions if requirements are ambiguous.
- **Phase 1 — Audit:** Locate existing implementations. Check `app/services/`, `app/repositories/`, `platforms/`, and `modules/` before writing new classes. If functionality exists, reuse or extend it.
- **Phase 2 — Plan:** Document the step-by-step diff plan. Identify regression risks, affected components, and exact test suites to execute.
- **Phase 3 — Implement:** Apply the **Smallest Safe Change**. Preserve existing comments, interfaces, and backward-compatible parameters.
- **Phase 4 — Test:** Compile Python files (`py_compile`), execute targeted unit tests, affected platform test suites, and regression gates.
- **Phase 5 — Verify:** Check error states, timeouts, cancellation paths, and GUI responsiveness.
- **Phase 6 — Document:** Keep documentation aligned with reality. If a data structure or flow changed, update the relevant file in `docs/` or `WorkingFlow/`.
- **Phase 7 — Report:** Present results using the mandatory response format (§16).

---

## 4. Codebase Organization & Inventory

```
apply-and-pray/
├── AGENTS.md                          # Quick agent entrypoint & essential runbook
├── docs/                              # Architecture audits & specialized guidelines
│   ├── ai/                            # AI Agent Rule System & Templates
│   │   ├── AI_DEVELOPMENT_RULES.md    # [THIS FILE] Master Constitution
│   │   ├── ARCHITECTURE_RULES.md      # Detailed layer & dependency contracts
│   │   ├── UI_RULES.md                # PySide6 desktop design system & threading
│   │   ├── AUTOMATION_RULES.md        # Automation worker & lifecycle rules
│   │   ├── BROWSER_AUTOMATION_RULES.md# Selenium/Stagehand browser rules
│   │   ├── AI_AGENT_RULES.md          # Multi-tier QnA & LLM truth boundaries
│   │   ├── SECURITY_RULES.md          # Credential hygiene & anti-bypass rules
│   │   ├── DATABASE_RULES.md          # SQLAlchemy 2.0 & migration policies
│   │   ├── TESTING_RULES.md           # Test requirements & baseline reporting
│   │   ├── FEATURE_DEVELOPMENT_TEMPLATE.md
│   │   ├── BUG_FIX_TEMPLATE.md
│   │   └── AUTOMATION_DEVELOPMENT_TEMPLATE.md
│   └── current_architecture.md        # Complete component inventory & call graphs
├── app/                               # PySide6 Application & Enterprise Services
│   ├── db/                            # SQLAlchemy models, sessions, migrations
│   ├── repositories/                  # Data access layer (CRUD, DTOs, queries)
│   ├── services/                      # Domain logic, automation orchestrators, AI
│   └── ui/                            # PySide6 views, state, navigation, theme
├── platforms/                         # Modular platform automation subsystems
│   ├── linkedin/                      # LinkedIn Easy Apply & search engine
│   ├── naukri/                        # Naukri 12-phase automation pipeline
│   ├── indeed/                        # Indeed search rotator & smart apply engine
│   ├── glassdoor/                     # Glassdoor search, extractor & applier
│   ├── foundit/                       # Foundit (Monster) automation subsystem
│   ├── router.py                      # Multi-platform unified router
│   └── base_platform.py               # BasePlatformApplier abstract contract
├── modules/                           # Shared utilities, QnA engine, qualification
├── config/                            # Master JSON configuration & secrets
├── tests/                             # Comprehensive automated test suites
├── WorkingFlow/                       # End-to-end execution flow diagrams
└── run_desktop.py                     # Desktop GUI launch entrypoint
```

---

## 5. Coding & Style Conventions

1. **Python Runtime:** Python 3.11.x inside `.venv` (`/home/ahmad10raza/anaconda3/envs/apply-and-pray`).
2. **Type Annotations:** All new functions, methods, and classes must include Python type hints (`from typing import Optional, List, Dict, Any, Tuple, Callable`).
3. **No Duplicate Services/Helpers:** Never create `NewService2`, `HelperUtils`, or parallel managers. Always search and extend existing services.
4. **Change Minimization:** Prefer the smallest safe change. Do not refactor unrelated files when implementing a specific feature or bug fix.
5. **Documentation Integrity:** Preserve existing docstrings and comments. Never delete explanatory commentary without explicit rationale.
6. **No Zombie Code:** Do not commit commented-out blocks of dead code. Use version control for history.

---

## 6. Error Handling & Recovery Standard

1. **No Silent Exceptions:**
   ```python
   # STRICTLY FORBIDDEN
   try:
       do_something()
   except:
       pass
   ```
   Every `try ... except` must catch specific exception types, log context via `print_lg` or `logger`, and transition to a known, recoverable, or terminal state.
2. **Distinguish Failure States:**
   - `FAILED`: Action definitively attempted and failed (e.g. invalid password, button disabled, HTTP 500).
   - `UNKNOWN`: Action initiated, but outcome could not be verified (e.g. submit button clicked, but confirmation banner did not appear before timeout). Never mark `UNKNOWN` as `SUBMITTED` or `FAILED`.
   - `MANUAL_REQUIRED`: Execution cannot proceed autonomously without human intervention (e.g. CAPTCHA detected, OTP challenge, ambiguous screening question, review gate).
3. **Cooperative Cancellation:** All long-running loops must periodically inspect a `stop_check` callable or `threading.Event` and exit gracefully without leaving orphan browser profiles or lingering locks.

---

## 7. Security & Privacy Invariants

1. **Zero Credential Leakage:** Never log or display plain-text passwords, session cookies, auth tokens, or private API keys in logs, activity feeds, UI text, or LLM prompts.
2. **Strict Githygiene:** Sensitive files (`config/profile.json`, `config/secrets.py`, `jobpilot.db`, session profiles) are strictly gitignored. Never hardcode credentials in committed files.
3. **No Anti-Bot Bypass:** Do not implement CAPTCHA bypasses, Cloudflare circumvention exploits, or fingerprint spoofing hacks. When a security challenge appears:
   - Immediately pause execution (`MANUAL_REQUIRED`).
   - Emit an `AutomationInterventionEvent` with `InterventionType.CAPTCHA_DETECTED`.
   - Allow the user to solve the challenge cooperatively in the browser.

---

## 8. Browser Automation Standards

1. **The Automation Loop:**
   $$\text{OBSERVE} \longrightarrow \text{CLASSIFY} \longrightarrow \text{ACT} \longrightarrow \text{VERIFY}$$
   Never `FIND -> CLICK -> ASSUME`. Always verify DOM changes following any interaction.
2. **Window & Search Integrity Guard:**
   - Splitting views: When selecting cards in split-pane search pages (e.g. Glassdoor, Indeed), click card container elements rather than stripping `target="_blank"` from anchors.
   - Never allow the main search results tab to navigate away. If a click navigates the main window, immediately isolate the job into a new tab and restore the search results URL.
3. **Profile Isolation & Lock Cleanup:**
   - Every platform uses a dedicated Chrome profile directory (`~/.jobpilot-<platform>-profile`).
   - Clean up stale lock files (`SingletonLock`, `SingletonCookie`, `SingletonSocket`) using `modules/browser_lock.py` prior to launching Chrome.
4. **Page Load Strategy:**
   - Chrome runs with `options.page_load_strategy = 'eager'`.
   - Use `safe_driver_get(driver, url, timeout)` to avoid hanging on background websockets or analytics trackers.

---

## 9. AI & LLM Truth Boundaries

1. **Zero Hallucination Policy:** Form field answers, cover letter content, and candidate facts must originate from validated candidate truth:
   - `PROFILE_FACT`: Extracted directly from `config/profile.json` or `ProfileService`.
   - `RESUME_FACT`: Parsed directly from the active candidate resume via `ResumeService`.
   - `QNA_RULE`: Pre-configured user rule from `config/questions.py` or `QnAService`.
2. **Deterministic-First Hierarchy:**
   1. **Tier 1:** Exact / regex rule matching from QnA database.
   2. **Tier 2:** Structured factual extraction from resume text.
   3. **Tier 3:** Bounded LLM semantic resolution (Ollama, OpenAI, Gemini).
   4. **Fallback:** If confidence is below threshold or info is absent, mark as `UNKNOWN` and request human input (`MANUAL_REQUIRED`). Never guess.

---

## 10. Database & Migration Invariants

1. **ORM Standard:** Use SQLAlchemy 2.0 syntax with type-annotated mapped columns (`Mapped[int] = mapped_column(...)`).
2. **Session Scoping:** Never leave open database sessions. Use `DatabaseService.session_scope()` or repository context managers to ensure automatic commit on success and rollback on exception.
3. **No Destructive Schema Modifications:** Never casually drop or rename existing database columns without an explicit backward-compatible migration plan and data conversion step.
4. **Dual-Persistence Synchronization:** When updating application status, ensure synchronization between `jobpilot.db` (via `ApplicationService`) and legacy tracking files (`modules/tracker.py`).

---

## 11. UI Development & Threading Rules

1. **Responsive Main Thread:** The Qt main event loop must never be blocked by network calls, database transactions, file I/O, or browser automation.
2. **Worker Pattern:** Offload background tasks to `QThread` or `TaskRunner`. Use Qt Signals (`pyqtSignal` / `Signal`) to communicate progress, logs, and state updates back to the UI.
3. **Design System Consistency:** All UI elements must adhere to `ThemeManager` (`app/ui/theme.py`) tokens. Do not hardcode arbitrary hex colors, ad-hoc font families, or non-standard padding. Support both Dark and Light themes.
4. **State Reactive Updates:** Use `AppState.get_instance().notify_data_updated("<domain>")` to trigger view refreshes cleanly without tight component coupling.

---

## 12. Testing & Verification Standards

1. **Baseline Testing Requirement:** Run relevant existing tests **before** touching code to establish a verified baseline.
2. **Test Isolation:** Automated unit and integration tests must never connect to live external job portals (LinkedIn, Naukri, Glassdoor). Use local mock servers, fixtures, or DOM dumps.
3. **Mandatory Verification Suite:**
   - Syntax validation: `.venv/bin/python -m py_compile ...`
   - Unit test suite: `.venv/bin/python -m unittest discover -s tests -p "test_<module>*.py"`
   - Full regression suite: `.venv/bin/python -m unittest discover -s tests`
   - Desktop headless preflight: `.venv/bin/python run_desktop.py --offscreen --test-run`

---

## 13. Specialized Rule Documents Directory

For deep-dive technical requirements in specific subsystems, refer to the specialized documentation:

| Document | Purpose |
|---|---|
| [`docs/ai/ARCHITECTURE_RULES.md`](ARCHITECTURE_RULES.md) | Architectural invariants, layer boundaries, dependency contracts |
| [`docs/ai/UI_RULES.md`](UI_RULES.md) | PySide6 design system, theme tokens, thread safety, view models |
| [`docs/ai/AUTOMATION_RULES.md`](AUTOMATION_RULES.md) | Multi-platform automation lifecycle, workers, safety gates, events |
| [`docs/ai/BROWSER_AUTOMATION_RULES.md`](BROWSER_AUTOMATION_RULES.md) | WebDriver resilience, profiles, DOM waits, split-view handling |
| [`docs/ai/AI_AGENT_RULES.md`](AI_AGENT_RULES.md) | Multi-tier QnA engine, zero hallucination, LLM truth boundaries |
| [`docs/ai/SECURITY_RULES.md`](SECURITY_RULES.md) | Secret storage, credential masking, anti-bypass principles |
| [`docs/ai/DATABASE_RULES.md`](DATABASE_RULES.md) | SQLAlchemy 2.0 models, migrations, repositories, dual-sync |
| [`docs/ai/TESTING_RULES.md`](TESTING_RULES.md) | Test suites, mock harnesses, headless execution, test baselines |

---

## 14. Standard Reusable Templates

Every future feature, bug fix, or automation enhancement must follow the corresponding standardized template:

| Template | Purpose |
|---|---|
| [`docs/ai/FEATURE_DEVELOPMENT_TEMPLATE.md`](FEATURE_DEVELOPMENT_TEMPLATE.md) | New feature specification, data flow, state machine, and test plan |
| [`docs/ai/BUG_FIX_TEMPLATE.md`](BUG_FIX_TEMPLATE.md) | Root cause analysis, reproduction, fix design, and regression guard |
| [`docs/ai/AUTOMATION_DEVELOPMENT_TEMPLATE.md`](AUTOMATION_DEVELOPMENT_TEMPLATE.md) | Platform automation engine structure, DOM selectors, recovery logic |

---

## 15. Mandatory Completion Checklist

Before declaring any coding task finished, the AI agent must verify every item:

- [ ] **Requirements Understood:** Fully verified user intent and constraints.
- [ ] **Existing Implementation Inspected:** Active code read; no parallel duplicate services created.
- [ ] **Architecture Compliant:** Layer boundaries respected (UI -> Service -> Repository -> DB).
- [ ] **Change Minimized:** Only necessary lines modified; no unrelated refactoring.
- [ ] **Error Handling Robust:** No silent `except: pass`; proper failure/unknown states defined.
- [ ] **Security Verified:** No secrets logged, exposed in prompts, or un-gitignored.
- [ ] **Python Syntax Verified:** `py_compile` succeeds on all touched and dependent files.
- [ ] **Targeted Tests Passed:** Specific unit/integration tests pass.
- [ ] **Regression Suite Passed:** Full test suite passes without breaking existing features.
- [ ] **Desktop Preflight Verified:** `run_desktop.py --offscreen --test-run` succeeds.
- [ ] **Documentation Updated:** Relevant documentation reflects new/changed behavior.
- [ ] **Report Provided:** Final output adheres strictly to the Agent Response Format.

---

## 16. Agent Response Format

Every AI agent completing a task in JobPilot must format its response with these exact sections:

```markdown
## Understanding
[Clear, concise summary of the task and requirements addressed]

## Existing Architecture
[Existing components, layers, and call paths inspected]

## Plan
[Step-by-step summary of changes made]

## Implementation
[Specific modifications made, highlighting non-obvious design decisions]

## Testing
- Baseline Tests: [X tests run, Y passed]
- Post-Change Tests: [X tests run, Y passed]
- Commands Executed: [Exact command lines run]

## Verification
[Confirmation of behavior, error paths, and headless preflight verification]

## Files Changed
- [file_path_1](file:///absolute/path/to/file1)
- [file_path_2](file:///absolute/path/to/file2)

## Risks / Limitations
[Any assumptions, known edge cases, or follow-up requirements]
```
