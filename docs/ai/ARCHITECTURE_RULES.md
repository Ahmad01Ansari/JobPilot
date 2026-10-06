# JobPilot — Architecture & Engineering Rules
**Specialized Architectural Guidelines and Layer Boundaries**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §2 & §5*

---

## 1. Architectural Philosophy

JobPilot is engineered as a clean, multi-tier desktop and web automation system. The architecture is intentionally decoupled into distinct layers to guarantee testability, maintainability, thread safety, and crash isolation.

Every AI agent and software engineer working on this repository **MUST** respect the established architectural layers. **Never invent parallel architectures or bypass layers.**

---

## 2. Directory Structure & Layer Mapping

```
Apply-and-Pray/
├── app/
│   ├── db/                 # Database Layer: SQLAlchemy models, engine, session factory
│   │   ├── models/         # Declarative SQLAlchemy 2.0 ORM models
│   │   └── session.py      # Session management, engine initialization, session_scope
│   ├── repositories/       # Repository Layer: Data access objects, raw queries, CRUD
│   │   ├── base.py         # Base repository abstraction
│   │   ├── job_repo.py     # Job persistence operations
│   │   └── ...
│   ├── services/           # Service Layer: Business logic, domain rules, orchestrators
│   │   ├── job_service.py  # High-level job coordination
│   │   ├── automation/     # Automation orchestration, bridge, workers, TaskRunner
│   │   └── ...
│   └── ui/                 # Presentation Layer: PySide6 Desktop GUI
│       ├── views/          # 13 Stacked views (Dashboard, Jobs, Settings, etc.)
│       ├── components/     # Reusable UI widgets (cards, tables, badges, headers)
│       ├── state.py        # AppState reactive signal manager
│       ├── theme.py        # ThemeManager (Dark/Light tokens, QSS styling)
│       └── main_window.py  # PySide6 Single Window Shell
├── platforms/              # Platform Automation Engines (Selenium / Undetected-Chromedriver)
│   ├── linkedin/           # LinkedIn Easy Apply & Search Engine
│   ├── naukri/             # Naukri.com Search & Apply Engine
│   ├── indeed/             # Indeed Search & Apply Engine
│   ├── glassdoor/          # Glassdoor Search & Apply Engine
│   └── foundit/            # Foundit (Monster) Engine
├── modules/                # Core Shared Modules & Intelligence
│   ├── qna_engine.py       # Multi-tier QnA answering engine (Rules -> Resume -> LLM)
│   ├── browser_lock.py     # Stale Chrome profile lock resolution
│   ├── config_loader.py    # Master config loader and JSON schema validation
│   └── tracker.py          # Legacy DB / CSV application tracking & dual-sync
├── config/                 # Static & Dynamic Configuration
│   ├── profile.json        # User profile, skills, compensation, personal facts
│   ├── secrets.py          # Gitignored credentials & LLM API keys
│   └── ...
└── tests/                  # Test Suites (Unit, Integration, Mocks, Harvesters)
```

---

## 3. Layer Contracts & Strict Boundaries

### 3.1. Layer Interaction Rules

```
┌────────────────────────────────────────────────────────┐
│                   PRESENTATION (UI)                    │
└───────────────────────────┬────────────────────────────┘
                            │ Calls Service Methods (Non-blocking)
                            │ Subscribes to Qt Signals / AppState
┌───────────────────────────▼────────────────────────────┐
│                     SERVICE LAYER                      │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       Invokes Repositories      Spawns Background Worker
                │                        │
┌───────────────▼────────┐      ┌────────▼───────────────┐
│    REPOSITORY LAYER    │      │   AUTOMATION WORKER    │
└───────────────┬────────┘      └────────┬───────────────┘
                │                        │
        Commits / Queries         Executes Engine
                │                        │
┌───────────────▼────────┐      ┌────────▼───────────────┐
│     DATABASE LAYER     │      │   AUTOMATION ENGINE    │
└────────────────────────┘      └────────────────────────┘
```

1. **Presentation Layer (`app/ui/` & `app.py`):**
   - **Allowed:** Call methods on `Service` classes; read/bind to `AppState`; emit and receive Qt signals; format data for display.
   - **Forbidden:** Direct imports from `app.db`, direct queries via SQLAlchemy, instantiating `selenium.webdriver`, creating Playwright instances, importing platform engines directly, making blocking network calls on the Qt main thread.

2. **Service Layer (`app/services/`):**
   - **Allowed:** Perform business logic, validation, and domain coordination; call `Repository` methods; dispatch tasks to `AutomationBridge` or `TaskRunner`; call AI intelligence engines; transform ORM entities to DTOs.
   - **Forbidden:** Directly manipulating PySide6 UI widgets; running infinite synchronous loops; executing raw SQL outside repositories; swallowing exceptions without structured logging.

3. **Repository Layer (`app/repositories/`):**
   - **Allowed:** Perform CRUD operations using SQLAlchemy sessions; encapsulate complex filters, joins, and aggregates; manage transaction rollbacks on failure; return DTOs or detached model objects.
   - **Forbidden:** Triggering UI updates; initiating browser automation; performing business decisions (e.g. determining if an application should be skipped); relying on UI state.

4. **Automation Worker Layer (`app/services/automation/`):**
   - **Allowed:** Run in background threads (`QThread`, `concurrent.futures`); manage automation lifecycle; report progress and state transitions via Qt signals (`AutomationBridge`); handle cancellation tokens.
   - **Forbidden:** Directly touching Qt UI widgets; blocking the main event loop; suppressing crash diagnostics.

5. **Automation Engine Layer (`platforms/` & `modules/`):**
   - **Allowed:** Control browser drivers (`undetected_chromedriver`, Selenium, Stagehand); inspect and manipulate DOM elements; extract job postings; report step-by-step progress via callbacks or bridge hooks; record audit screenshots.
   - **Forbidden:** Direct coupling to PySide6 UI; committing directly to SQLAlchemy sessions; hardcoding user personal data.

---

## 4. Forbidden Architectural Anti-Patterns

| Anti-Pattern | Description | Correct Alternative |
|---|---|---|
| **UI-to-DB Bypass** | UI view creates an SQLAlchemy session or imports `app.db.models`. | UI calls a `Service`, which delegates to a `Repository`. |
| **UI-to-Driver Bypass** | A button click in a PySide6 view launches Chrome directly. | UI calls `AutomationService.start_job()`, which launches a `TaskRunner`/`QThread` worker. |
| **Worker UI Access** | A background worker thread updates a `QLabel` or `QTableWidget` directly. | Worker emits a Qt signal (`bridge.status_updated.emit(...)`), and the UI slot handles the widget update on the main thread. |
| **Service Duplication** | Creating `JobService2`, `ModernApplierService`, or `HelperService` instead of extending `JobService`. | Inspect existing service methods and extend or refactor with backward compatibility. |
| **Entity Leakage** | Returning live, attached SQLAlchemy ORM instances directly into UI models. | Use Data Transfer Objects (DTOs), dataclasses, or plain dictionaries to prevent detached instance session errors. |
| **Hidden Global State** | Storing application states in module-level global variables. | Use `AppState` or dedicated state machines with explicit transitions. |

---

## 5. Threading & Concurrency Boundaries

JobPilot is a desktop application powered by PySide6 (Qt). Qt enforces strict thread affinity rules:
1. **Qt Main Thread (GUI Thread):**
   - Handles all user events, rendering, paint events, and window resizing.
   - **Rule:** Never execute operations taking > 50ms on the main thread (no disk I/O, no network HTTP calls, no WebDriver commands, no LLM calls).
2. **Background Automation Threads (`QThread` / `TaskRunner`):**
   - All WebDriver lifecycle tasks, browser navigations, scraping routines, and long-running AI inferences must execute here.
   - Communication from background threads to GUI must occur exclusively through **Qt Signals** or thread-safe callback bridges (`AutomationBridge`).
3. **Cancellation & Shutdown:**
   - Every background worker must regularly poll `should_cancel()` or check a `threading.Event`.
   - On application exit, all active workers must be gracefully requested to terminate before tearing down WebDriver instances.

---

## 6. Service & Repository Extension Rules

Before adding or modifying any service:
1. **Grep Search:** Search `app/services/` and `app/repositories/` to verify if similar domain logic exists.
2. **Preserve Signatures:** Maintain existing public method signatures. If new parameters are needed, provide sensible default values.
3. **Repository Invariant:** Every repository method must use `session_scope()` or manage transaction rollbacks cleanly on failure.
4. **DTO Return Pattern:** Repositories querying data for display should return dataclasses, Pydantic models, or detached objects to isolate the database layer.

---

## 7. Architecture Compliance Checklist

Before committing any architectural change, verify:
- [ ] No direct imports of `app.db` or `app.repositories` in `app/ui/`.
- [ ] No UI widget access inside background threads or automation engines.
- [ ] All cross-layer communications use defined Service interfaces or Qt signals.
- [ ] No new duplicate services or repositories were created.
- [ ] All database queries are encapsulated inside `app/repositories/`.
- [ ] Background tasks implement clean cooperative cancellation.

---

## 8. Job Qualification Subsystem Architecture

The **Job Qualification Engine** operates as an isolated, local-first ranking engine evaluating discovered jobs against candidate profile facts:

1. **Context Extraction:** `CandidateContextProvider` builds canonical, immutable `CandidateQualificationContext` from `ProfileService`, `ResumeService`, and configuration facts without detached ORM leakages.
2. **Deterministic Evaluation:** `QualificationEngine` performs hard filtering (negative keywords, company blacklist), role title matching, skill keyword/synonym matching (`SkillMatcher`), experience requirement parsing (`ExperienceStrength`), and location alignment. Missing attributes dynamically renormalize scoring weights without penalty.
3. **Semantic AI Enhancement:** `SemanticAIAdvisor` provides optional semantic enhancement via local Ollama LLMs with deterministic fallback on network or model unavailability.
4. **Service & Persistence:** `JobQualificationService` coordinates the workflow and persists results to the evolved `JobEvaluation` model via `JobEvaluationRepository`.
5. **UI & Asynchronous Execution:** `JobQualificationWorker` (`QThread`) executes evaluations in the background, updating `JobsTable` match badges, `JobsDetailPanel` qualification summaries, and handling bulk evaluations from `JobsBulkBar`. No UI widget is ever touched from worker threads.
