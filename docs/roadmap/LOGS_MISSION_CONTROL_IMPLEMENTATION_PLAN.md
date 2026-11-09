# JobPilot — Automation Mission Control & Logs Battleground
## Architectural Implementation Plan (Revised v2.0)

> **Document Version:** 2.0.0 (Post-Review Architecture Alignment)  
> **Status:** Pending Final Review & Explicit User Sign-Off  
> **Reference Document:** [`Roadmap/LogsBattleground.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/Roadmap/LogsBattleground.md)  
> **Design Tokens & Theme Guide:** [`DesignUI.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/DesignUI.md)  
> **Architectural Constitution:** [`docs/ai/AI_DEVELOPMENT_RULES.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/docs/ai/AI_DEVELOPMENT_RULES.md)

---

## 1. Architectural Philosophy & Invariants

The revised architecture establishes **Automation Mission Control** as a non-invasive, high-fidelity observability and incident command layer sitting directly on top of JobPilot's existing automation infrastructure.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       AUTOMATION LAYER (PROTECTED)                          │
│   LinkedIn · Naukri · Indeed · Foundit · Glassdoor · Universal ATS          │
│   (Zero modifications to engine rotator logic or browser automation)        │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ (Emits typed signals & log traces)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    OBSERVABILITY BOUNDARY & EVENT BRIDGE                     │
│                                                                             │
│   PRIMARY: Typed Signals (AutomationWorker / AutomationBridge)              │
│   SECONDARY: Structured Events (JobDiscoveredEvent, etc.)                   │
│   FALLBACK: Deterministic Raw Log Parser (Regex rules on log tags)          │
│   RAW_LOG: Raw text stream preserved for forensic inspection                │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │ Event Correlator & Deduplicator (Fingerprint + Windowed LRU Cache) │   │
│   └──────────────────────────────────┬──────────────────────────────────┘   │
└──────────────────────────────────────┼──────────────────────────────────────┘
                                       │ (Deduplicated AutomationEvent DTOs)
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
┌──────────────────────────────────────┐┌─────────────────────────────────────┐
│          LIVE EVENT STREAM           ││        PERSISTENCE & RUNS           │
│   In-memory Ring Buffer (1,000 evt)  ││   SQLite automation_runs table      │
│   Multi-Run Active Context Map       ││   AutomationRunRepository           │
└──────────────────┬───────────────────┘└──────────────────┬──────────────────┘
                   │                                       │
                   └───────────────────┬───────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MISSION CONTROL COCKPIT (PySide6)                        │
│                                                                             │
│   1. Top Bar & Multi-Run Selector (LinkedIn ● / Naukri ● / Universal ⚠)     │
│   2. Scoped Metric Strip ([CURRENT RUN] Discovered, Applied, Skipped, etc.) │
│   3. Truthful Current Action Hero (From worker state, never regex inferred) │
│   4. Normalized Pipeline Stages (SEARCH → DISCOVER → APPLY → VERIFY)       │
│                                                                             │
│   4 Integrated Workspace Modes:                                             │
│   [ ⚔ LIVE BATTLEFIELD ]  [ ⏱ RUN HISTORY ]  [ ⚠ ERROR CENTER ]  [ 💻 RAW ] │
│                                                                             │
│   Central Navigation: AppNavigator.navigate(NavigationRequest(...))         │
│   Security: Whitelisted Diagnostic Export, Zero Credential Exposure         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Phase 0: Existing System Audit & Verification Matrix

In strict accordance with Phase 0 directives, every underlying model, repository, and service has been verified against live repository code:

| Component / File | Verified Method / Field | Actual Behavior / Schema in Codebase | Reusable As-Is? | Action / Adapter Required |
| :--- | :--- | :--- | :---: | :--- |
| **`AutomationRun` Model**<br>[`app/db/models/automation_run.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/db/models/automation_run.py) | `run_id`, `platform`, `status`, `started_at`, `finished_at`, `current_keyword`, `jobs_discovered`, `jobs_evaluated`, `jobs_qualified`, `jobs_skipped`, `applications_submitted`, `errors_count`, `stop_reason`, `meta_data` | Fully implemented SQLite table with UUID string `run_id`, integer counters, and JSON `meta_data`. | **YES** | Reusable directly without schema migrations. |
| **`AutomationRunRepository`**<br>[`app/repositories/automation_run_repository.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/repositories/automation_run_repository.py) | `create_run(...)`<br>`get_by_run_id(...)`<br>`update_progress(...)`<br>`finalize_run(...)`<br>`list_recent(limit=20)` | Persists and queries runs ordered by `desc(started_at)`. | **YES** | Reusable directly for **Run History** tab and historical funnel metrics. |
| **`AutomationWorker`**<br>[`app/services/automation_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/automation_service.py#L29) | `state_changed(str, str)`<br>`progress_updated(object)`<br>`job_discovered(object)`<br>`job_evaluated(object)`<br>`application_submitted(object)`<br>`intervention_required(object)`<br>`activity_logged(str, str)`<br>`finished_result(object)` | Runs in a background `QThread`. Emits typed domain events and activity messages. | **YES** | Serves as the **PRIMARY** event source for live execution. |
| **`AutomationManager`**<br>[`app/services/automation_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/automation_service.py#L814) | `get_state()`, `get_current_run()`, `is_running()`, `is_paused()`, `request_stop()`, `get_recent_runs()` | Manages single primary active worker lifecycle. | **YES** | Multi-run tracking will maintain a registry of active run contexts in Mission Control. |
| **`AutomationBridge`**<br>[`app/services/automation_bridge.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/automation_bridge.py) | `mark_captcha_resolved()`<br>`reset_captcha_status()`<br>`is_captcha_resolved_by_user()`<br>`handle_job_discovered()`<br>`handle_application_submitted()` | Idempotently connects engine execution with `JobService` and `ApplicationService`. | **YES** | Powers human intervention resolution and entity persistence. |
| **`LogService`**<br>[`app/services/log_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/log_service.py) | `tail(n_lines=500)`<br>`filter_logs(lines, level, search)`<br>`safe_clear(confirm=True)` | Reads `logs/log.txt` with `LogSanitizer`. | **ADAPT** | Add byte-offset incremental tailing to avoid scanning the entire 30MB file on every tick. |
| **`LogSanitizer`**<br>[`app/services/sanitizer_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/sanitizer_service.py) | `sanitize_text(text)`<br>`sanitize_record(dict)` | Regex scrubber for passwords, tokens, cookies, auth headers. | **YES** | Applied to display text, while preserving numeric IDs for correlation. |
| **`AppNavigator`**<br>[`app/services/navigation_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/navigation_service.py) | `navigate(request: NavigationRequest)` | Routes `NavigationRequest(route, entity_type, entity_id, exact=True)` to target view with state persistence. | **YES** | Authoritative deep-link mechanism for opening exact Job and Application records. |
| **`QnAService`**<br>[`app/services/qna_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/qna_service.py) | `add_entry(question, answer, category, answer_type, platform, source, confidence)` | Validates and persists screening Q&A into SQLite `qna_entries`. | **YES** | Used by the Intervention Center to save answers with explicit candidate confirmation. |

---

## 3. Strict Event Source Hierarchy & Deduplication Strategy

To guarantee that duplicate events are never produced when both a typed worker signal and a raw log message fire for the same logical action, we establish a deterministic 4-tier event hierarchy:

```
Tier 1: SIGNAL (PRIMARY)
  ▲ Emitted directly by AutomationWorker / AutomationBridge. Highest precedence.
  │
Tier 2: STRUCTURED_LOG (SECONDARY)
  ▲ Structured JSON or domain objects logged by modern engines.
  │
Tier 3: PARSED_LOG (FALLBACK)
  ▲ Regex extraction on known log tags ([NaukriSearch], [APPLICATION_CONFIRMED]).
  │ Only ingested if no matching SIGNAL event was recorded within the deduplication window.
  │
Tier 4: RAW
    Preserved strictly for forensic text viewing. Never promotes to semantic business events.
```

### 3.1 EventSource Enum & Normalized `AutomationEvent` DTO
Located at `app/services/logs/automation_event.py`:

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

class EventSource(str, Enum):
    SIGNAL = "SIGNAL"                     # Typed Qt Signal from AutomationWorker
    STRUCTURED_LOG = "STRUCTURED_LOG"     # Structured payload from engine
    PARSED_LOG = "PARSED_LOG"             # Deterministic regex parse from log tag
    RAW = "RAW"                           # Unstructured forensic line

class AutomationEventType(str, Enum):
    # Lifecycle
    RUN_STARTED = "RUN_STARTED"
    RUN_COMPLETED = "RUN_COMPLETED"
    RUN_STOPPED = "RUN_STOPPED"
    RUN_PAUSED = "RUN_PAUSED"
    # Search & Discovery
    SEARCH_STARTED = "SEARCH_STARTED"
    SEARCH_COMPLETED = "SEARCH_COMPLETED"
    JOB_DISCOVERED = "JOB_DISCOVERED"
    JOB_QUALIFIED = "JOB_QUALIFIED"
    JOB_SKIPPED = "JOB_SKIPPED"
    # Application & Execution
    APPLICATION_STARTED = "APPLICATION_STARTED"
    STAGE_TRANSITION = "STAGE_TRANSITION"
    QUESTION_DETECTED = "QUESTION_DETECTED"
    QUESTION_ANSWERED = "QUESTION_ANSWERED"
    RESUME_ATTACHED = "RESUME_ATTACHED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_FAILED = "APPLICATION_FAILED"
    # Interventions & Recovery
    CAPTCHA_DETECTED = "CAPTCHA_DETECTED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    MANUAL_INTERVENTION = "MANUAL_INTERVENTION"
    RETRY_ATTEMPT = "RETRY_ATTEMPT"
    RATE_LIMITED = "RATE_LIMITED"
    ERROR = "ERROR"
    RAW_LOG = "RAW_LOG"

@dataclass
class LogFileReference:
    """Stable pointer to a line in logs/log.txt without assuming immutable line numbers."""
    log_file: str                       # e.g., "logs/log.txt"
    file_mtime: float                   # File modification timestamp at recording
    line_number: int                    # 1-indexed line number at recording time
    byte_offset: int                    # Byte seek offset
    line_fingerprint: str               # sha256 prefix of raw line for validation
    is_valid: bool = True               # Flagged False if file was truncated/rotated

@dataclass
class AutomationEvent:
    """Normalized domain event for automation observability and diagnostics."""
    event_id: str                       # Deterministic UUID or content hash
    run_id: str                         # Correlation ID of the automation session
    timestamp: datetime                 # UTC timestamp
    sequence: int                       # Strictly monotonic sequence number per run
    source: EventSource                 # SIGNAL, STRUCTURED_LOG, PARSED_LOG, RAW
    level: str                          # INFO, WARNING, ERROR, CRITICAL
    event_type: AutomationEventType     # Semantic event type

    # Execution Context
    platform: str                       # linkedin, naukri, indeed, universal, etc.
    engine: Optional[str] = None        # e.g., "NaukriRotator", "StagehandUniversal"
    stage: Optional[str] = None         # SEARCH, DISCOVER, QUALIFY, APPLICATION, etc.

    # Entity Identity (Non-secret correlation IDs)
    job_id: Optional[int] = None
    application_id: Optional[int] = None
    company: Optional[str] = None
    job_title: Optional[str] = None

    # Step & Progress
    action: Optional[str] = None        # e.g., "Answering screening questions"
    status: Optional[str] = None        # SUCCESS, FAILED, PENDING, INTERVENTION
    duration_ms: Optional[int] = None
    attempt_number: int = 1

    # Forensic & Diagnostic Payload
    message: str = ""                   # Sanitized human-readable text
    metadata: Dict[str, Any] = field(default_factory=dict) # Sanitized key-values
    raw_reference: Optional[LogFileReference] = None
```

### 3.2 Deterministic Deduplication Strategy
Located at `app/services/logs/event_correlator.py`:
- **Fingerprint Formula:**
  $$\text{Fingerprint} = \text{SHA256}(\text{run\_id} + \text{event\_type} + \text{str(job\_id or '')} + \text{str(application\_id or '')} + \text{action or ''})$$
- **Time-Windowed Deduplication Cache:**
  - Maintains an LRU cache of fingerprints emitted within a sliding window of **5,000 ms**.
  - When a `SIGNAL` event arrives, its fingerprint is cached immediately.
  - If a subsequent `PARSED_LOG` event from the log file arrives with the same fingerprint inside the window, it is **discarded as a duplicate**; its `raw_reference` is simply attached to the existing `SIGNAL` event.
  - This ensures exactly **one semantic event** per operational occurrence.

---

## 4. Source of Truth Matrix by Feature

To eliminate confusion between database, worker, and file state, each UI feature is bound to exactly one authoritative source:

| Feature / Widget | Authoritative Source of Truth | Secondary / Fallback Source | Prohibited Pattern |
| :--- | :--- | :--- | :--- |
| **Live Automation State**<br>(Running / Idle / Action Required) | `AutomationManager.get_state()` & active `AutomationWorker.state_changed` | None (Worker is ground truth) | **NEVER** parse `log.txt` to guess if bot is running. |
| **"What is the Bot Doing Right Now?"**<br>(Active Job, Current Step) | `AutomationProgressEvent` (`current_job`, `current_term`, `stage`) from active worker | Display: *"Current action unavailable"* | **NEVER** regex-scrape log strings to invent the active job. |
| **Active Run KPIs**<br>(Discovered, Applied, Skipped, etc.) | `AutomationProgressEvent` on active `AutomationWorker` | None | **NEVER** mix current run metrics with lifetime DB totals. |
| **Historical Run Table & Funnels** | SQLite `AutomationRunRepository.list_recent()` | None | **NEVER** calculate past run totals from log file text. |
| **Live Event Timeline** | `EventCorrelator` in-memory ring buffer (per run) | None | **NEVER** reload the timeline by rescanning entire `log.txt`. |
| **Human Interventions**<br>(CAPTCHA, Review Holds, Q&A) | `AutomationInterventionEvent` from `AutomationWorker.intervention_required` | None | **NEVER** fake intervention state without active worker signal. |
| **Forensic Raw Logs** | `LogService` reading `logs/log.txt` incrementally via byte offsets | None | **NEVER** truncate or delete the log file from normal view. |

---

## 5. Multi-Run Handling Architecture

JobPilot supports multi-platform automation runs (e.g. Naukri crawler running alongside a paused Universal ATS session). The UI must never force a single global run state.

### 5.1 `RunObservabilityContext` Model
Located at `app/services/logs/run_context.py`:
- `active_contexts: Dict[str, RunObservabilityContext]` indexed by `run_id`.
- Each context tracks:
  - `platform`: `naukri`, `linkedin`, etc.
  - `status`: `RUNNING`, `PAUSED`, `ACTION_REQUIRED`, `IDLE`.
  - `current_progress`: `AutomationProgressEvent`.
  - `event_buffer`: Bounded circular buffer of latest 1,000 `AutomationEvent` instances for that specific run.
  - `interventions`: List of unresolved `AutomationInterventionEvent` instances.

### 5.2 Multi-Run Selector in Top Bar
At the top of Mission Control, an interactive segmented control displays all active/recent runs:
```
[ ● Naukri · RPA Dev (Running) ]  [ ⚠ Universal ATS (Action Required) ]  [ ○ LinkedIn (Idle) ]
```
- Clicking a chip sets `selected_run_id` in Mission Control.
- All timeline nodes, metric cards, and current action panels instantly scope to the selected run.

---

## 6. Metric Scope Guarantees

Every counter rendered in the interface displays an unambiguous scope badge to prevent mixing session data with lifetime metrics:

| Metric Card | Explicit Scope Label | Calculation Source |
| :--- | :--- | :--- |
| **Session Discovered** | `[CURRENT RUN]` | `AutomationProgressEvent.jobs_discovered` |
| **Session Qualified** | `[CURRENT RUN]` | `AutomationProgressEvent.jobs_qualified` |
| **Session Applied** | `[CURRENT RUN]` | `AutomationProgressEvent.applications_submitted` |
| **Session Skipped** | `[CURRENT RUN]` | `AutomationProgressEvent.jobs_skipped` |
| **Session Interventions** | `[CURRENT RUN]` | Count of active `AutomationInterventionEvent`s for this run |
| **Daily Application Funnel** | `[TODAY]` | Query to `ApplicationRepository` filtered by `DATE(created_at) = CURRENT_DATE` |
| **Historical Run Metrics** | `[RUN #<ID>]` | Read directly from selected `AutomationRun` record in SQLite |

---

## 7. Normalized Execution Pipeline Stages

Rather than assuming every engine follows an identical hardcoded step sequence, Mission Control normalizes execution into **8 canonical pipeline stages**:

$$\text{SEARCH} \longrightarrow \text{DISCOVER} \longrightarrow \text{QUALIFY} \longrightarrow \text{APPLICATION} \longrightarrow \text{REVIEW} \longrightarrow \text{SUBMISSION} \longrightarrow \text{VERIFICATION} \longrightarrow \text{COMPLETED}$$

- **Platform-Specific Sub-Steps:** Each platform renders its internal progress *within* the active canonical stage:
  - *Naukri:* Inside `APPLICATION`, renders: `"Applying via Naukri 1-Click Apply"`.
  - *Universal ATS:* Inside `APPLICATION`, renders: `"Step 3/5: Filling Custom Questionnaire"`.
  - *LinkedIn:* Inside `REVIEW`, renders: `"NaukriSafetyGate / EasyApply Review Step"`.
- If an engine skips a stage (e.g. Direct URL apply skips `SEARCH`), the node is marked as `SKIPPED (N/A)` rather than failing.

---

## 8. Real Human Intervention Action Contracts

All intervention actions in Tab 3 are backed by real service and worker contracts:

| Action Button | Underlying Service Call | Expected Behavior & Verification |
| :--- | :--- | :--- |
| **[I Have Solved The Challenge ✓]** | `AutomationBridge.mark_captcha_resolved()` | Updates internal flag in bridge, allowing waiting worker thread loop to resume browser navigation. |
| **[Confirm & Submit Application]** | `AutomationWorker.confirm_review(notes=...)` | Calls `_active_orchestrator.confirm_submission()` on Universal Agent or unlocks Safety Gate. |
| **[Skip This Job]** | `ApplicationService.transition_status(app_id, "SKIPPED")` + worker resume | Marks application record as `SKIPPED` in SQLite and signals worker to advance to next listing. |
| **[Add Answer to Q&A Bank]** | `QnAService.add_entry(question, answer, source="MANUAL", confidence=1.0)` | Validates inputs, saves to `qna_entries` table with full candidate provenance, and resumes worker. |
| **[Open Browser Session]** | Truthful driver inspection | If browser is running in non-headless mode, brings OS window to foreground. If headless, displays clear advisory: *"Automation is running in headless mode; browser window cannot be brought to foreground."* |

---

## 9. Failure Clustering via Deterministic Fingerprinting

To prevent visual alert fatigue from identical repeated errors (e.g. 10 consecutive timeouts locating a submit button), errors are clustered using normalized error signatures:

1. **Message Normalization:**
   - Strips dynamic substrings using regex:
     - Job IDs: `r"job[_\s-]?\d+"` $\longrightarrow$ `"<JOB_ID>"`
     - URLs: `r"https?://\S+"` $\longrightarrow$ `"<URL>"`
     - Timestamps: `r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}"` $\longrightarrow$ `"<TIMESTAMP>"`
2. **Cluster Key:**
   $$\text{ClusterKey} = \text{SHA256}(\text{platform} + \text{stage} + \text{normalized\_error\_message})$$
3. **UI Presentation:**
   - Groups matching errors into a single high-priority card:
     `⚠ Timeout locating submit button × 6 (Naukri · Last 12m)`
   - Expanding the card reveals the exact job listings, applications, and timestamps affected.

---

## 10. Central Navigation Bridge via `AppNavigator`

Eliminates tight coupling to `MainWindow` internals by using the established [`AppNavigator`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/navigation_service.py) and [`NavigationRequest`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/search/search_result.py):

```python
# app/ui/views/logs/logs_navigation_bridge.py
from app.services.navigation_service import AppNavigator
from app.services.search.search_result import NavigationRequest, NavigationAction

class LogsNavigationBridge:
    """Dispatches exact-record deep links using central AppNavigator."""
    def __init__(self, navigator: AppNavigator):
        self._navigator = navigator

    def open_job(self, job_id: int) -> bool:
        """Navigates to JobsView (Ctrl+3) and opens the exact job inspection drawer."""
        request = NavigationRequest(
            route="jobs",
            entity_type="job",
            entity_id=job_id,
            action=NavigationAction.OPEN_DETAILS,
            query=str(job_id),
            exact=True,
        )
        return self._navigator.navigate(request)

    def open_application(self, application_id: int) -> bool:
        """Navigates to ApplicationsView (Ctrl+5) and focuses the exact application row."""
        request = NavigationRequest(
            route="applications",
            entity_type="application",
            entity_id=application_id,
            action=NavigationAction.SELECT_ROW,
            query=str(application_id),
            exact=True,
        )
        return self._navigator.navigate(request)
```

---

## 11. Security Model & Whitelisted Diagnostic Export

### 11.1 Secret Hygiene Rules
1. **Never Capture Secrets:** Passwords, API keys, session tokens, authorization headers, and raw credential payloads are scrubbed at the source.
2. **Correlation ID Preservation:** Sanitization rules are strictly configured so that numeric database IDs (`job_id`, `application_id`, `run_id`) are never destroyed.

### 11.2 Whitelisted Diagnostic Export
The `[Export Diagnostic Report]` feature **NEVER** inspects `os.environ` or dumps system environment variables. It exports strictly whitelisted diagnostic metadata:

```markdown
# JobPilot Diagnostic Report
**Export Timestamp:** 2026-10-05T23:15:00Z
**JobPilot Version:** 1.0.0 | **Python:** 3.11.13 | **OS:** Linux (x86_64)

## System Health
- Database: Connected (SQLite)
- Active Automation Worker: Running (Naukri)
- AI Service: Configured (Universal Gateway)

## Selected Run Summary
- Run ID: 604b33ed-896a-4203-9839-cb6b0f8343d6
- Platform: Naukri
- Search Terms: "RPA Developer"
- Duration: 8m 21s
- Discovered: 42 | Qualified: 18 | Applied: 12 | Failed: 0 | Interventions: 1

## Sanitized Event Timeline (Last 50 Events)
[10:42:18] [SEARCH_STARTED] Started search rotation for 'RPA Developer'
[10:42:21] [JOB_DISCOVERED] Discovered job 'Senior RPA Developer' (ID: #4821)
...

## Sanitized Raw Log Excerpt
(Scrubbed of user directory paths, tokens, and cookies)
```

---

## 12. Performance Model & Memory Protection

To ensure that 30MB+ log files or 10,000+ line automation runs never cause UI freezing:

1. **Incremental Byte-Offset Log Reader:**
   - `LogService` tracks file byte offset `self._last_byte_offset`.
   - On refresh, seeks directly to `_last_byte_offset` and reads only newly appended bytes. Never rereads the entire file!
2. **Bounded UI Document Limits:**
   - Raw terminal `QPlainTextEdit` enforces:
     ```python
     self.txt_terminal.setMaximumBlockCount(2000)
     ```
   - Automatically drops oldest lines when buffer exceeds 2,000 blocks, keeping memory strictly bounded.
3. **In-Memory Event Ring Buffer:**
   - Live timeline maintains a `collections.deque(maxlen=1000)` per active run.
4. **Decoupled Stream Pause:**
   - Clicking `[⏸ Pause Stream]` sets `self._ui_stream_paused = True`. Incoming Qt signals continue updating backend buffers and SQLite metrics, but UI widget re-rendering is suspended until user clicks `[▶ Resume Stream]`.
   - **Pause Stream $\neq$ Stop Automation.** The background Selenium worker runs unaffected.
5. **Safe "Clear View" Action:**
   - Replaced destructive `[Clear Log File]` with `[Clear View]`.
   - `[Clear View]` clears only the local widget buffer. The underlying `logs/log.txt` file and database run records are **never deleted**.

---

## 13. UI Architecture & Theme Alignment ([`DesignUI.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/DesignUI.md))

### 13.1 SaaS/ATS Aesthetic (Zero Gaming Gimmicks)
- **Visual Tone:** Modern ATS Operations & DevOps Observability (Linear, Raycast, GitHub Actions).
- **Surfaces:** Obsidian canvas (`#0F1117`), card surfaces (`#161B22`), border lines (`#262C36`), Safety Orange (`#FF5F15`) active accents.
- **Light Theme:** Fully supported via `ThemeManager` (`#F6F8FA` canvas, `#FFFFFF` surfaces, `#D0D7DE` borders).
- **Reduced Chrome:** Flat nested hierarchy; cards are used only for top-level operational containers. No card-inside-card clutter.

### 13.2 View Structure & Layout
```
app/ui/views/
├── logs_view.py                          # Replaced with AutomationMissionControlView
└── logs/
    ├── mission_header.py                 # Top bar, platform chips, active run selector
    ├── mission_status_strip.py           # Scoped KPI cards ([CURRENT RUN], [TODAY])
    ├── current_action_card.py            # "What is the Bot Doing Right Now?" hero
    ├── pipeline_flow_map.py              # Canonical 8-stage visual pipeline
    ├── tabs/
    │   ├── live_battlefield_tab.py       # Interactive vertical timeline & event cards
    │   ├── run_history_tab.py            # SQLite run list, duration, conversion funnel
    │   ├── error_center_tab.py           # Human interventions & failure clusters
    │   └── raw_logs_tab.py               # Bounded incremental terminal with search & pause
    ├── widgets/
    │   ├── event_detail_drawer.py        # Slide-out drill down inspector for selected event
    │   ├── intervention_action_dialog.py # CAPTCHA solver, Q&A adder, review approval
    │   └── log_filter_bar.py             # Search, level combo, event type filter, pause toggle
    └── logs_navigation_bridge.py         # AppNavigator wrapper for Jobs/Applications links
```

---

## 14. Revised 14-Phase Implementation Sequence

```
┌───────────────────────────────────────────────────────────────────────────────┐
│ PHASE 0: Existing System Audit                                    [COMPLETED] │
│   • Verified AutomationRun model, repository, worker signals, AppNavigator.  │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 1: Event Contract & Correlation Model                                   │
│   • Implement AutomationEvent DTO, EventSource, and AutomationEventType.     │
│   • Implement LogFileReference model with byte-offset validation.             │
│   • Implement EventCorrelator with 5,000ms windowed deduplication cache.      │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 2: Live Event Bridge & Log Normalizer                                   │
│   • Implement AutomationLogBridge connecting typed signals to EventCorrelator.│
│   • Implement LogNormalizer fallback regex rules for engine rotator tags.     │
│   • Unit test event deduplication: verify signal + log produce 1 event.       │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 3: Multi-Run Context & Persistence                                      │
│   • Implement RunObservabilityContext and active run registry.                │
│   • Connect SQLite AutomationRunRepository for run creation & progress sync.  │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 4: Mission Control Shell & Scoped Top Bar                               │
│   • Build AutomationMissionControlView container with DesignUI.md tokens.     │
│   • Implement MissionHeader with multi-run selector and status pills.         │
│   • Implement MissionStatusStrip with clearly scoped metric counters.         │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 5: Current Action Hero & Canonical Pipeline Map                         │
│   • Implement CurrentActionCard (truthfully sourced from worker state).       │
│   • Implement PipelineFlowMap rendering canonical 8 stages with live status.  │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 6: Tab 1 — Live Battlefield Timeline & Detail Drawer                    │
│   • Implement vertical timeline with semantic event node rendering.           │
│   • Build EventDetailDrawer side panel with step timing and failure context.  │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 7: Tab 2 — Run History & Conversion Funnel                              │
│   • Build RunHistoryTab querying AutomationRunRepository asynchronously.      │
│   • Implement conversion funnel: Discovered → Qualified → Applied → Verified. │
│   • Add historical run replay mode (inspect past events without running bot). │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 8: Tab 3 — Error & Human Intervention Center                            │
│   • Build ErrorCenterTab with top-priority active intervention cards.         │
│   • Implement deterministic failure clustering with normalized error keys.    │
│   • Wire real intervention action handlers (CAPTCHA, skip, Q&A save).         │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 9: Tab 4 — Forensic Raw Logs Terminal                                   │
│   • Implement RawLogsTab using QPlainTextEdit with setMaximumBlockCount(2000).│
│   • Implement incremental byte-offset file reader in LogService.              │
│   • Add search query highlighter, severity filter, pause stream toggle.       │
│   • Replace clear file with non-destructive [Clear View].                     │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 10: Central Navigation Bridge Integration                               │
│   • Implement LogsNavigationBridge utilizing AppNavigator.navigate().         │
│   • Connect [Open Job] and [Open Application] to exact-record focus.          │
│   • Connect [View in Raw Logs] to auto-scroll and highlight matching line.    │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 11: Whitelisted Diagnostic Export                                       │
│   • Implement export generator without arbitrary environment variable dumps.  │
│   • Scrub local paths and sanitize all messages before file write.            │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 12: Theme Polish & Micro-Interactions                                   │
│   • Integrate ThemeManager listener for dynamic Dark/Light mode switching.    │
│   • Verify keyboard shortcuts: Space (pause stream), Ctrl+F (search logs).    │
├───────────────────────────────────────────────────────────────────────────────┤
│ PHASE 13: Comprehensive Verification & Regression Suite                       │
│   • Unit test event pipeline end-to-end across LinkedIn, Naukri, Universal.   │
│   • Verify full test suite passes with zero regressions in automation engines.│
│   • Headless PySide6 desktop verification (`run_desktop.py --offscreen`).     │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 15. Comprehensive Test & Acceptance Gate

The feature will be declared production-ready only when all acceptance criteria pass:

- [ ] **No Duplicate Semantic Events:** Ingesting a worker signal and its corresponding log tag produces exactly 1 semantic event.
- [ ] **Truthful Current Action:** Hero card reflects active `AutomationProgressEvent` or displays *"Automation is currently idle"*. Zero regex scraping for active state.
- [ ] **Multi-Run Support:** Multiple concurrent runs (e.g. Naukri running + Universal ATS paused) maintain distinct, non-overlapping contexts.
- [ ] **Scoped Metrics:** All UI metric cards display explicit scope labels (`[CURRENT RUN]`, `[TODAY]`).
- [ ] **Decoupled Stream Pause:** `[Pause Stream]` suspends UI timeline rendering without pausing or interrupting `AutomationWorker`.
- [ ] **Safe View Clear:** `[Clear View]` clears displayed lines; log files on disk and SQLite runs are preserved.
- [ ] **Restart Resiliency:** Historical runs and conversion funnels survive application restart via `AutomationRunRepository`.
- [ ] **Exact Navigation:** `[Open Job]` and `[Open Application]` navigate via `AppNavigator` and focus the exact record.
- [ ] **Real Intervention Contracts:** Resolving CAPTCHA or saving Q&A executes the actual service method with candidate confirmation.
- [ ] **Deterministic Error Clustering:** Repeated errors group cleanly using normalized error signatures.
- [ ] **Whitelisted Export:** Diagnostic export scrubs secrets and never dumps `os.environ`.
- [ ] **Bounded Memory Performance:** Raw terminal limits document blocks to 2,000; incremental reader seeks to byte offsets without full-file rescans.
- [ ] **Theme Adherence:** Verified with Dark Obsidian (`#0F1117`) and Light Canvas (`#F6F8FA`).
- [ ] **Zero Engine Interference:** Full regression suite passes across all protected platform engines (`LinkedIn`, `Naukri`, `Indeed`, `Universal ATS`).

---

## 16. Recommendation & Sign-Off Request

> [!IMPORTANT]
> **This revised plan addresses all 40 architectural review points.**
> In strict accordance with `AGENTS.md` and Constitution Phase 2:
> **No implementation code will be written until this revised plan receives your explicit sign-off.**
> 
> Please review and approve this document. Once approved, we will proceed immediately with **Phase 1: Event Contract & Correlation Model**.
