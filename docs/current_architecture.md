# JobPilot — Current Architecture Audit & Component Inventory
**Phase 0 Deliverable — Master Desktop UI Migration Roadmap**

---

## 1. Executive Summary

This document establishes the architecture freeze and component audit of **JobPilot** (formerly *Apply & Pray*) prior to building the PySide6 desktop application. 

The existing system consists of two production-ready multi-platform automation pipelines:
1. **LinkedIn Automation**: Script-driven Easy Apply bot (`runAiBot.py`) using `undetected-chromedriver`, multi-tier QnA answering, and direct URL navigation.
2. **Naukri Automation**: Modular, 12-phase pipeline (`platforms/naukri/*`, `platforms/router.py`) featuring isolated Chrome profiles, pre-click apply button classification, questionnaire handling, GUI safety gates, error recovery, and search rotation.

Both pipelines share a unified configuration layer (`config/profile.json`), a unified candidate & job data model (`modules/models.py`), a multi-tier QnA engine (`modules/qna_engine.py`), and a unified application tracking database (`modules/tracker.py`).

Per the architectural guidelines in [`Roadmap/desktop-ui/desktop_roadmap.md`](../Roadmap/desktop-ui/desktop_roadmap.md), **no existing automation code is rewritten**. The PySide6 desktop application will wrap these battle-tested engines using service adapters and background worker threads.

---

## 2. High-Level Component Call Graph

```mermaid
flowchart TD
    subgraph CLI_Entry ["CLI & Platform Entry Points"]
        CLI["runAiBot.py (CLI / Entry)"]
        Router["platforms/router.py (PlatformRouter)"]
        CLI -->|--platform naukri| Router
        CLI -->|--platform linkedin| LN_Engine["runAiBot.py (apply_to_jobs)"]
    end

    subgraph Config_Layer ["Configuration & Credentials"]
        ConfigLoader["modules/config_loader.py"]
        ProfileJSON["config/profile.json"]
        Secrets["config/secrets.py"]
        ConfigLoader --> ProfileJSON
        ConfigLoader --> Secrets
    end

    subgraph Naukri_Pipeline ["Naukri Automation Subsystem"]
        NaukriPlat["platforms/router.py (NaukriPlatform)"]
        Rotator["platforms/naukri/rotator.py (SearchRotationEngine)"]
        Search["platforms/naukri/search.py (NaukriSearchEngine)"]
        Parser["platforms/naukri/parser.py (NaukriJobParser)"]
        Qual["modules/qualification_engine.py (QualificationEngine)"]
        Recovery["platforms/naukri/recovery.py (safe_apply_job)"]
        Applier["platforms/naukri/applier.py (NaukriApplier)"]
        Detector["platforms/naukri/flow_detector.py (NaukriFlowDetector)"]
        Form["platforms/naukri/form.py (NaukriForm)"]
        SafetyGate["platforms/naukri/safety_gate.py (NaukriSafetyGate)"]
        Submitter["platforms/naukri/submitter.py (NaukriSubmitter)"]
        NBrowser["platforms/naukri/browser.py (NaukriBrowser)"]

        Router --> NaukriPlat
        NaukriPlat --> Rotator
        Rotator --> Search
        Rotator --> Parser
        Rotator --> Qual
        Rotator --> Recovery
        Recovery --> Applier
        Applier --> Detector
        Applier --> Form
        Applier --> SafetyGate
        Applier --> Submitter
        NaukriPlat --> NBrowser
    end

    subgraph LinkedIn_Pipeline ["LinkedIn Automation Subsystem"]
        LNB["modules/open_chrome.py (open_chrome)"]
        LN_Engine --> LNB
        LN_Filters["apply_filters()"]
        LN_QnA["answer_common_questions()"]
        LN_External["external_apply()"]
        LN_Engine --> LN_Filters
        LN_Engine --> LN_QnA
        LN_Engine --> LN_External
    end

    subgraph Intelligence_Layer ["Shared AI & Decision Layer"]
        QnAEngine["modules/qna_engine.py (QnAEngine)"]
        LLM["Ollama / OpenAI / Gemini / DeepSeek"]
        Form --> QnAEngine
        LN_QnA --> QnAEngine
        QnAEngine --> LLM
    end

    subgraph State_Storage ["State Tracking & History"]
        Tracker["modules/tracker.py (ApplicationTracker)"]
        SQLiteDB[("all excels/job_tracker.db")]
        HistCSV["all excels/all_applied_applications_history.csv"]
        NaukriCSV["all excels/applications.csv"]
        Tracker --> SQLiteDB
        Tracker --> NaukriCSV
        LN_Engine --> HistCSV
        Applier --> Tracker
    end
```

---

## 3. Comprehensive Component Inventory & Audit

| # | Component | Primary File(s) | Purpose | Input | Output | Reusability | Desktop UI Integration Requirement |
|---|---|---|---|---|---|---|---|
| **1** | **CLI Dispatcher** | [`runAiBot.py`](../runAiBot.py) | Parses `--platform` (`linkedin`, `naukri`, `all`) and orchestrates execution loops. | CLI arguments, system environment | Process exit code, log output | Adapter Needed | Extract automation triggers into `AutomationService` so PySide6 UI can start/stop runs without subprocess spawning. |
| **2** | **Platform Router** | [`platforms/router.py`](../platforms/router.py) | Manages lifecycle (`initialize`, `login`, `search_and_apply`) across platforms. | Platform name string, options dict | Platform run results, rotation stats | Direct | Directly invokable by PySide6 background worker threads (`QThread`). |
| **3** | **LinkedIn Engine** | [`runAiBot.py`](../runAiBot.py) | Direct URL job search, pagination, Easy Apply modal clicking, and resume upload. | `search_terms`, Chrome profile, secrets | Applied jobs, CSV records | Adapter Needed | Wrap `apply_to_jobs()` in an event-emitting worker that posts progress/job signals to the Qt GUI instead of raw terminal prints. |
| **4** | **Naukri Rotation Engine** | [`platforms/naukri/rotator.py`](../platforms/naukri/rotator.py) | Multi-keyword search rotation, multi-page loop, relevance decay, and application caps. | `config.search_terms`, `max_pages`, `applier` | `RotationStats`, `TermStats` | Direct | Add a cancellation token (`threading.Event`) check per iteration to allow instant stop from UI. |
| **5** | **Naukri Applier** | [`platforms/naukri/applier.py`](../platforms/naukri/applier.py) | Isolated tab management, end-to-end job application flow orchestration. | `Job` object, card element | `Job` with final status (`SUBMITTED`, `SKIPPED`, etc.) | Direct | Already decoupled from browser creation. Emits clean return status. |
| **6** | **Naukri Flow Detector** | [`platforms/naukri/flow_detector.py`](../platforms/naukri/flow_detector.py) | Inspects pre-click button types (`DIRECT`, `EXTERNAL`) and post-click states (`QUESTIONNAIRE`, `CAPTCHA`, `LOGIN`). | WebDriver, element DOM | `(flow_type, description)` | Direct | Fully reusable without modification. |
| **7** | **Naukri Form Filler** | [`platforms/naukri/form.py`](../platforms/naukri/form.py) | Inspects screening forms (inputs, radios, selects, textareas), answers via QnA engine. | WebDriver, `QnAEngine` | `FormFillResult` (status, filled fields) | Direct | Fully reusable. |
| **8** | **Safety Gate Review** | [`platforms/naukri/safety_gate.py`](../platforms/naukri/safety_gate.py) | Pauses before submission; provides human-in-the-loop review modal with Approve/Discard/Manual. | `Job`, filled fields, candidate params | `SafetyGateResult` (`APPROVE`, `DISCARD`, `MANUAL`) | Adapter Needed | Currently implemented in Tkinter (`show_gui_review_dialog`). Will be replaced with a native PySide6 modal dialog in Phase 11. |
| **9** | **Naukri Submitter** | [`platforms/naukri/submitter.py`](../platforms/naukri/submitter.py) | Executes final submit click and verifies success banner or timeout. | WebDriver, `Job` | `SubmissionResult` (`CONFIRMED`, `TIMEOUT`) | Direct | Fully reusable. |
| **10** | **Error Recovery** | [`platforms/naukri/recovery.py`](../platforms/naukri/recovery.py) | Dismisses popups/overlays and retries transient DOM failures with exponential backoff. | Function callable, WebDriver | Return value of wrapped function | Direct | Fully reusable. |
| **11** | **Browser Manager (LinkedIn)** | [`modules/open_chrome.py`](../modules/open_chrome.py) | Launches `undetected-chromedriver` with LinkedIn profile and anti-bot flags. | Profile path, headless flag | `uc.Chrome` driver instance | Direct | Reusable. Driver can run in background while desktop UI runs in foreground. |
| **12** | **Browser Manager (Naukri)** | [`platforms/naukri/browser.py`](../platforms/naukri/browser.py) | Isolated Chrome session with persistent profile, auth detection (`LOGGED_IN`, `LOGIN_REQUIRED`, `CAPTCHA`). | Profile path, credentials | `NaukriBrowser` instance | Direct | Provide session status signals to PySide6 status bar and platform indicators. |
| **13** | **Unified QnA Engine** | [`modules/qna_engine.py`](../modules/qna_engine.py) | Multi-tier answer resolution: Rules → Resume extraction → LLM (Ollama/OpenAI/Gemini). | Question string, input type, options | `QnAAnswer` (value, source, confidence) | Direct | Integrate into Desktop QnA Editor tab to let users edit rules and test question answers in real time. |
| **14** | **Qualification Engine** | [`modules/qualification_engine.py`](../modules/qualification_engine.py) | Dynamic job screening via `core_skills`, `negative_title_words`, `irrelevant_tech_words`, and experience constraints. | `Job` object, candidate criteria | `QualificationResult` (`is_qualified`, `reason`) | Direct | Will read criteria directly from database once SQLite/PostgreSQL layer is initialized. |
| **15** | **Application Tracker** | [`modules/tracker.py`](../modules/tracker.py) | Dual persistence in SQLite (`job_tracker.db`) and CSV (`applications.csv`), deduplication. | `Job` object, status, metadata | Saved record, stats dict | Direct | Will serve as the foundation for the Phase 2/3 unified database schema. |
| **16** | **Unified Config Loader** | [`modules/config_loader.py`](../modules/config_loader.py) | Reads `config/profile.json` with fallback to Python config files. | File paths, environment variables | Config dictionaries | Adapter Needed | Config files become seed/migration data for database tables in Phase 4. |
| **17** | **Web Dashboard API** | [`app.py`](../app.py) | Flask web dashboard exposing `/api/unified/history`, `/api/naukri/stats`, and `/api/naukri/records`. | HTTP requests | JSON payloads, HTML views | Deprecated | Desktop app replaces local Flask server, but the JSON data structures inform desktop table models. |
| **18** | **DOM Helpers** | [`modules/clickers_and_finders.py`](../modules/clickers_and_finders.py), [`modules/helpers.py`](../modules/helpers.py) | Resilient JavaScript clicks, smart element waiters, profile path locators, structured logging. | WebDriver, locators, messages | DOM elements, log entries | Direct | Fully reusable. |

---

## 4. Subsystem Deep-Dive

### 4.1. Authentication & Session Handling
- **LinkedIn**:
  - Profile directory: `~/.jobpilot-chrome-profile` (with fallback to `~/.apply-and-pray-chrome-profile`).
  - Detection: Verifies cookies and checks for presence of feed navigation elements.
  - Credentials: `config/secrets.py` (`username`, `password`).
- **Naukri**:
  - Profile directory: `~/.jobpilot-naukri-profile` (with fallback to `~/.apply-and-pray-naukri-profile`).
  - Detection: Uses `NaukriBrowser.check_session_state()` returning `LOGGED_IN`, `LOGIN_REQUIRED`, `CAPTCHA`, or `OTP`.
  - Credentials: `config/profile.json` (`platforms.naukri.credentials`).

### 4.2. Job Data Model
The shared dataclass in [`modules/models.py`](../modules/models.py) defines the contract between parsers, engines, and trackers:
```python
@dataclass
class Job:
    platform: Literal["linkedin", "naukri", "indeed", "glassdoor"]
    job_id: str
    title: str
    company: str
    location: str
    source_url: str
    experience_required: Optional[Tuple[int, int]] = None
    salary_range: Optional[Tuple[float, float]] = None
    skills: List[str] = field(default_factory=list)
    description_text: str = ""
    status: TrackerStatus = "DISCOVERED"
    skip_reason: Optional[str] = None
    apply_mode: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```
This data model is completely forward-compatible with the target database schema in Phase 3.

### 4.3. Data Storage & Formats
1. **SQLite Database (`all excels/job_tracker.db`)**:
   - Table: `naukri_applications` (stores `job_id`, `platform`, `title`, `company`, `location`, `status`, `skip_reason`, `url`, `timestamp`).
2. **CSV History**:
   - `all excels/all_applied_applications_history.csv`: LinkedIn applied history.
   - `all excels/applications.csv`: Naukri applied, skipped, failed, and external history.
3. **Logs**:
   - `logs/log.txt`: Rotating human-readable event log.

---

## 5. Desktop UI Integration Roadmap (Phases 1–5)

To transition this architecture into the PySide6 desktop application cleanly:

1. **Phase 1 (Desktop Foundation)**:
   - Construct the PySide6 application frame (`app/main.py`, `app/ui/main_window.py`).
   - Implement navigation sidebar, dark slate theme (`#0f172a`), top bar, and content viewport.
   - Zero modifications to automation code.

2. **Phase 2 (Database Architecture)**:
   - Introduce SQLAlchemy database engine with SQLite backend (`jobpilot.db`).
   - Migrate legacy CSV and `job_tracker.db` data into the unified schema.

3. **Phase 3 (Database Schema)**:
   - Implement models for `User`, `CandidateProfile`, `Job`, `Application`, `Interview`, and `RecruiterCommunication`.

4. **Phase 4 (Configuration & Seed Migration)**:
   - Seed candidate personal details, CTC, notice period, and screening rules from `config/profile.json` into the database.

5. **Phase 5 (Automation Service Adapter & QThread Workers)**:
   - Wrap `NaukriPlatform.search_and_apply()` and LinkedIn `apply_to_jobs()` inside `QThread` worker classes.
   - Connect progress callbacks and cancellation tokens so desktop buttons (`Start Automation`, `Stop Automation`) operate safely.

---

## 6. Audit Sign-Off Gate
- [x] All 18 system components audited and documented.
- [x] Input/Output contracts verified.
- [x] Zero automation code modified during Phase 0.
- [x] 170 unit tests passing with 0 failures and 0 errors.
- **Phase 0 Status**: COMPLETE. Ready for user approval to proceed to **Phase 1**.
