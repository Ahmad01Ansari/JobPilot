# JobPilot — First-Run Setup Wizard & Readiness Engine
## Comprehensive Implementation Plan & Technical Specification (Revised v2.0)

> **Status:** Draft / Awaiting User Approval  
> **Target Release:** First-Run Experience, Setup Orchestrator & Multi-Tier Readiness Engine  
> **Source Documents:** [`Roadmap/onboardingServices.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/Roadmap/onboardingServices.md) & [`DesignUI.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/DesignUI.md)  
> **Architectural Law:** Layer Isolation (UI → Setup Domain Orchestrator → Existing Domain Services → Repositories / DB / Secrets). Zero code duplication. Zero secret storage in setup state. Adaptive Discovery over Rigid Sequential Checklists.

---

## 1. Revised Architecture & Responsibilities

The setup system is an **adaptive orchestrator**, not a rigid sequence. It discovers what already exists in the local database and settings, identifies what is genuinely missing, and guides the candidate through only what is needed.

```
                  ┌─────────────────────────────────────────┐
                  │             Setup Wizard UI             │
                  │   Adaptive Navigator · DesignUI.md      │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                  ┌─────────────────────────────────────────┐
                  │        SetupService (Orchestrator)      │
                  │  Coordinates Discovery, State & Actions │
                  └────────────────────┬────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
 ┌──────────────────────┐   ┌──────────────────────┐   ┌──────────────────────┐
 │   ReadinessService   │   │   Existing Domain    │   │      SetupState      │
 │  Source of Truth on  │   │       Services       │   │  Progress & History  │
 │  Requirements & Gate │   │ (Profile, Resume...) │   │ (No Secrets / State) │
 └──────────┬───────────┘   └──────────┬───────────┘   └──────────────────────┘
            │                          │
            ▼                          ▼
 ┌──────────────────────┐   ┌─────────────────────────────────────────────────┐
 │ SetupRequirement     │   │ Repositories / SQLite DB / SecretsStore         │
 │ Checklist Registry   │   │ (profile.json, jobpilot.db, OS Keyring, Config) │
 └──────────────────────┘   └─────────────────────────────────────────────────┘
```

### Core Separation of Concerns:
- **`Setup Wizard UI`**: Pure presentation. Renders state, adapts navigation dynamically, displays field provenance, captures user confirmations, and triggers actions.
- **`SetupService` (Orchestrator)**: Manages setup flow, coordinates calls between domain services, handles partial failure/recovery, records audit events, and checks for conflicting data.
- **`ReadinessService` (Ground Truth)**: Evaluates the system requirements independently of the wizard. Available universally to the Wizard, Dashboard, Settings, and Automation Pre-flight.
- **`Existing Services`**: Source of domain data (`ProfileService`, `ResumeService`, `QnAService`, `PlatformService`, `SettingsService`). Their internal business logic remains untouched.
- **`SecretsService`**: Authoritative store for API keys and platform credentials. Never stores secrets in `SetupState`, JSON logs, or UI state models.
- **`UniversalAIService`**: Generic provider abstraction for LLM inference with capability discovery and data minimization.

---

## 2. Revised Setup State & Requirement Models

### 2.1 Requirement Status Enum & `SetupRequirement` Model
Instead of treating every setup item as a mandatory blocker, every capability is declared as a `SetupRequirement` with explicit criticality (`CORE` vs `RECOMMENDED` vs `OPTIONAL`):

```python
# app/services/setup/setup_requirements.py
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

class RequirementCriticality(str, Enum):
    CORE = "CORE"                    # Must have to use basic JobPilot (Profile, Resume, Prefs)
    RECOMMENDED = "RECOMMENDED"      # Greatly improves experience (AI, Q&A facts)
    OPTIONAL = "OPTIONAL"            # Feature-specific (Platform credentials, Automation safety)

class RequirementStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"

@dataclass
class SetupRequirement:
    key: str                         # e.g., "candidate_profile", "primary_resume", "ai_provider"
    title: str                       # e.g., "Candidate Profile"
    description: str                 # e.g., "Basic personal info, target role, and key skills"
    criticality: RequirementCriticality
    status: RequirementStatus = RequirementStatus.NOT_STARTED
    blocking: bool = False           # True only if required for the current target capability
    route: str = "profile"           # Associated UI navigation route (Ctrl+1..9, Ctrl+0)
    fix_action: str = "edit_profile" # Wizard step or settings handler
    details: Dict[str, Any] = field(default_factory=dict) # e.g. {"name": "Ahmad", "missing_fields": []}
```

### 2.2 Non-Secret `SetupState` Model
`SetupState` tracks navigation progress, session timestamps, and audit history. It is serialized to `config/setup.json`.

```python
# app/services/setup/setup_state.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime

SETUP_SCHEMA_VERSION = "2.0.0"   # Independent of application software version

@dataclass
class SetupEvent:
    timestamp: str               # ISO-8601 string
    event_type: str              # e.g., "SETUP_STARTED", "RESUME_IMPORTED", "AI_TEST_SUCCESS"
    step_key: str                # e.g., "resume", "ai_provider"
    summary: str                 # Human-readable event description (NO SECRETS)

@dataclass
class SetupState:
    setup_schema_version: str = SETUP_SCHEMA_VERSION
    is_completed: bool = False
    setup_mode: str = "QUICK"    # "QUICK" (2-5 min) or "ADVANCED" (Full)
    current_step: str = "welcome"
    completed_steps: List[str] = field(default_factory=list)
    skipped_steps: List[str] = field(default_factory=list)
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    active_resume_id: Optional[str] = None
    tour_completed: bool = False
    events: List[SetupEvent] = field(default_factory=list)

    def log_event(self, event_type: str, step_key: str, summary: str):
        self.events.append(SetupEvent(
            timestamp=datetime.utcnow().isoformat(),
            event_type=event_type,
            step_key=step_key,
            summary=summary
        ))
        self.updated_at = datetime.utcnow().isoformat()
```

---

## 3. Two Meaningful Readiness Levels (Zero Arbitrary Percentages)

Instead of vague numbers like "Readiness: 73%", JobPilot establishes two explicit, transparent product milestones:

```
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: CORE READY (Manual Job Search & Tracking Ready)              │
│ Criteria:                                                              │
│  ✓ Candidate Profile: Full Name, Email, Phone, at least 3 skills       │
│  ✓ Primary Resume: At least 1 active PDF/DOCX file uploaded            │
│  ✓ Basic Job Preferences: At least 1 target role title & location      │
│ Outcome:                                                               │
│  User can immediately browse jobs, manage resumes, track               │
│  applications manually, and organize interviews without blockers.      │
├────────────────────────────────────────────────────────────────────────┤
│ LEVEL 2: AUTOMATION READY (Autonomous Agent & Easy Apply Ready)       │
│ Criteria:                                                              │
│  ✓ Core Ready criteria satisfied                                       │
│  ✓ AI Provider: Verified connectivity + text generation test passed    │
│  ✓ Screening Q&A: 6 core facts verified (authorization, notice, etc.) │
│  ✓ Target Platform: Valid session/credentials for target portal        │
│  ✓ Safety Guardrails: Daily application caps & delay ranges confirmed │
│ Outcome:                                                               │
│  Universal Agent & Platform bots unlocked for safe autonomous actions. │
└────────────────────────────────────────────────────────────────────────┘
```

```python
# app/services/setup/setup_readiness.py
@dataclass
class ReadinessEvaluation:
    is_core_ready: bool
    is_automation_ready: bool
    core_completed_count: int
    core_total_count: int
    recommended_completed_count: int
    recommended_total_count: int
    requirements: Dict[str, SetupRequirement]
    blockers: List[str]              # e.g., ["Missing primary resume"]
    warnings: List[str]              # e.g., ["AI Provider not configured (Manual Q&A will be used)"]
    change_summary: List[str]        # Audit summary of changes made in this session
```

---

## 4. Adaptive Setup Flows: First-Run vs. Returning User

### 4.1 First-Run Flow (Adaptive & Non-Trapping)
The wizard offers **Quick Setup** (~2–5 minutes) or **Advanced Setup**:

```
                  Launch JobPilot (Brand-New Install)
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 1: Welcome & Setup Choice   │
                 │  [Quick Setup (Recommended)]     │
                 │  [Advanced Setup]  ·  [Skip]     │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 2: Resume Ingestion         │
                 │  Drag & drop PDF / Word doc      │
                 └────────────────┬─────────────────┘
                                  │
               AI Available? ─────┴───── AI Unavailable?
                     │                         │
                     ▼                         ▼
         [AI Extract Profile]        [Manual Profile Entry]
                     │                         │
                     └────────────┬────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 3: Profile Review & Edit    │
                 │  Field-level provenance badges   │
                 │  Demographics: User-controlled   │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 4: Job Search Strategy      │
                 │  Target titles, locations, types │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 5: AI Engine (Optional)     │
                 │  [Configure AI]  or  [Skip AI]   │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
                 ┌──────────────────────────────────┐
                 │ Step 6: Readiness & Change Log   │
                 │  Core Ready Badge (3/3 Core Met) │
                 │  Summary of changes applied      │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼
               ┌──────────────────────────────────────┐
               │ Optional Product Tour (Quick/Skip)   │
               └──────────────────┬───────────────────┘
                                  │
                                  ▼
                           DASHBOARD VIEW
```

### 4.2 Returning / Partially-Configured User Flow
When re-launched or opened via **Settings → Setup & Readiness**:
1. `SetupService.discover_current_state()` inspects existing database tables and configuration files.
2. Already-configured requirements are marked as **`READY`** with a green checkmark and summarized details.
3. The wizard highlights only **`MISSING`** or **`NEEDS_REVIEW`** steps.
4. The user can jump directly to any step via the left navigation rail or click `Continue with Missing Steps`.
5. **Start Over Safety:** Clicking "Start Over" resets the wizard navigation cursor; it **NEVER deletes** existing resumes, candidate profiles, Q&A entries, or credentials.

---

## 5. Resume Ingestion, AI Extraction & Field-Level Provenance

### 5.1 Extraction Pipeline with Graceful Fallback
AI is **never** a hard requirement for profile setup. If AI is unconfigured or unavailable, the user can review text extracted by the local PDF parser or enter details manually.

```
       Upload Resume (PDF / DOCX)
                  │
                  ▼
       ResumeParserService (Local pypdf / pdfminer)
                  │
          Text Extracted?
           ├── No  ──► "Unable to read document text. [Retry] [Enter Profile Manually]"
           └── Yes ──► Check AI Provider Connectivity
                         │
        AI Available? ───┴─── AI Not Configured?
             │                        │
             ▼                        ▼
  Extract with UniversalAI      Parse Basic Regex / Text
  (Structured JSON Adapter)     (Email, Phone, Name Heuristics)
             │                        │
             └───────────┬────────────┘
                         ▼
             Profile Review Screen
             (Field-Level Provenance)
```

### 5.2 Field-Level Provenance & Candidate Fact Status
Every profile field maintains clear metadata regarding its source and confidence:
- `Source`: `RESUME`, `USER_INPUT`, `EXISTING_PROFILE`, or `NOT_FOUND`.
- `Status`: `EXTRACTED`, `NORMALIZED`, `INFERRED`, or `USER_CONFIRMED`.
- **Golden Rule:** AI models must **never** invent missing values. If an item is not found in the resume, it remains empty (`Unknown / Not provided`).
- **Demographic Fields Protection:** Sensitive demographic fields (*Ethnicity, Gender, Disability, Veteran Status*) are **NEVER** auto-extracted, auto-inferred, or populated by AI. They appear solely as optional, explicit candidate-controlled inputs with an explanatory note.

---

## 6. Profile → Canonical Candidate Facts → Q&A Conflict Resolution

### 6.1 Canonical Candidate Fact Architecture
To prevent the knowledge base from accumulating redundant questions (e.g., "Date of Birth", "DOB", "What is your date of birth?"), JobPilot separates **Canonical Facts** from **Question Variations**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CANONICAL CANDIDATE FACT LAYER                       │
│                                                                        │
│   Fact Key:       candidate.total_experience_years                     │
│   Canonical Value: 5                                                   │
│   Data Type:      integer                                              │
│   Source:         RESUME (Verified by Candidate)                       │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Referenced by matcher
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   QUESTION MATCHER & VARIATIONS                        │
│                                                                        │
│   Pattern 1: "How many years of total work experience do you have?"   │
│   Pattern 2: "Total professional experience (years):"                  │
│   Pattern 3: "Years of experience"                                     │
│   ──► ALL RESOLVE TO: candidate.total_experience_years (Answer: 5)     │
└────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Conflict Detection & Resolution UI
When the wizard discovers that resume data contradicts existing Q&A or profile entries, it displays an interactive conflict resolution dialog rather than silently overwriting data:

```
┌────────────────────────────────────────────────────────────────────────┐
│ ⚠ Conflicting Information Detected: Total Experience                   │
├────────────────────────────────────────────────────────────────────────┤
│ Existing Knowledge Base:    3 Years                                    │
│ Parsed Resume Document:     5 Years (Found at Acme Corp 2021-2026)     │
├────────────────────────────────────────────────────────────────────────┤
│ Choose authoritative answer:                                           │
│  ( ) Keep Existing Value (3 Years)                                     │
│  (•) Update with Resume Value (5 Years)                                │
│  ( ) Enter Custom Value: [     ] Years                                 │
│                                                                        │
│                                           [Confirm Selection]          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Generic AI Provider Architecture & Model Registry

### 7.1 Unified AI Architecture (OpenAI-Compatible First)
Rather than writing vendor-specific code (`if provider == "Groq": ... elif provider == "OpenAI": ...`), JobPilot standardizes on a generic provider contract centered around standard OpenAI-compatible endpoints:

```
                          ┌────────────────────────┐
                          │   UniversalAIService   │
                          └───────────┬────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │     AIProviderBase     │
                          │ (Generic Specification)│
                          └───────────┬────────────┘
                                      │
      ┌───────────────────────────────┼───────────────────────────────┐
      ▼                               ▼                               ▼
┌────────────────────────┐ ┌────────────────────────┐ ┌────────────────────────┐
│ OpenAICompatibleAdapter│ │     OllamaAdapter      │ │ NativeProviderAdapter  │
│ (Groq, NVIDIA, OpenAI, │ │ (Local model discovery │ │ (Anthropic, Gemini     │
│ Together, OpenRouter,  │ │  & offline execution)  │ │  direct SDK/REST APIs) │
│ Custom Local Endpoints)│ │                        │ │                        │
└────────────────────────┘ └────────────────────────┘ └────────────────────────┘
```

### 7.2 Capability-Based Connection Testing
A simple "Connected" status is insufficient. The AI setup test executes a progressive 5-stage diagnostic and displays detailed status badges:
1. **Endpoint Reachability:** DNS resolution and HTTP/HTTPS socket connect.
2. **Authentication Validation:** API key accepted by endpoint (HTTP 200 vs 401/403).
3. **Model Availability:** Selected model ID is accessible under the account quota.
4. **Chat Generation Test:** Lightweight ping (`"Reply 'OK'"`).
5. **Structured JSON Validation:** Tests adherence to schema/JSON mode output.

### 7.3 Model Capability Registry
JobPilot inspects or registers capabilities per model:
- `text_generation` (Standard prompt response)
- `structured_output` (JSON mode / schema adherence)
- `vision` (Image/screenshot analysis)
- `context_window` (e.g. 8k, 32k, 128k tokens)

---

## 8. Provider Documentation Architecture & Maintainable Metadata

To prevent outdated links or hardcoded pricing/free-tier claims, provider configurations use clean, externalized metadata definitions:

```python
# app/services/ai/provider_definitions.py
@dataclass
class ProviderMetadata:
    id: str                          # e.g., "groq"
    name: str                        # e.g., "Groq Cloud"
    adapter_type: str                # "openai_compatible"
    default_endpoint: str            # "https://api.groq.com/openai/v1"
    default_model: str               # "llama-3.3-70b-versatile"
    available_models: List[str]
    api_key_url: str                 # "https://console.groq.com/keys"
    documentation_url: str           # "https://console.groq.com/docs"
    privacy_policy_url: str          # "https://groq.com/privacy-policy"
    supports_model_discovery: bool
    requires_api_key: bool
    notice: str = "Provider terms and availability may change over time."
```

---

## 9. Privacy, Data Minimization & Cloud AI Transparency

### 9.1 Data Minimization Rules by Task
JobPilot enforces strict contextual boundaries on data sent to LLM providers:

| Task | Payload Transmitted to AI | Data Strictly Excluded / Redacted |
|---|---|---|
| **Resume Extraction** | Clean resume body text only | Unrelated candidate system paths, credentials, auth tokens |
| **Screening Question**| Target question + matched candidate facts only | Candidate full home address, phone number, email, unrelated jobs |
| **Job Description Match**| Job requirements + candidate skills & titles | Contact details, salary history, demographic details |

### 9.2 Clear Cloud AI Privacy Notice
In Step 5 of the wizard, a dedicated informational card clearly discloses:
> **Cloud AI Processing Disclosure:**  
> When using cloud providers (*Groq, NVIDIA, OpenAI, Anthropic, Gemini*), application data relevant to the task is transmitted to their servers according to their respective privacy terms.  
> **Prefer 100% Local Privacy?** Use **Ollama** with local open models (*llama3, mistral*); zero candidate data ever leaves your computer.

---

## 10. Automation Pre-Flight Strategy

Readiness is never assumed based on historical wizard completions. Before any automation engine runs (e.g. LinkedIn Easy Apply or Universal ATS), an instant pre-flight audit executes:

```python
# Conceptual Pre-Flight Dispatch
report = readiness_service.evaluate_for_platform(platform_name="linkedin")
if not report.can_run_automation:
    show_preflight_blocker_dialog(
        reasons=report.blockers,
        fix_action=report.recommended_fix_route
    )
    return
```

### Pre-Flight Checks:
1. Active primary resume exists on disk.
2. Verified candidate facts exist for common ATS screening prompts.
3. AI provider is responsive (if AI answering is enabled).
4. Platform session/cookies are valid (or credentials provided).
5. Daily application limit has not been exhausted.

---

## 11. Contextual Product Tour Architecture

- **No Forced 9-Step Tours:** The candidate is offered a 30-second **Quick Tour**, a comprehensive **Full Tour**, or **Skip to Dashboard**.
- **Contextual First-Use Tooltips:** Instead of an overwhelming walkthrough on first launch, subtle highlight tooltips trigger when a user visits a section for the first time (e.g., first visit to `Applications` or `Universal Agent`).
- **Restart Tour Anytime:** Accessible via `Settings → Setup & Readiness → Restart Tour`.

---

## 12. Failure Handling & Recovery Paths

The wizard is engineered to never crash or trap the user:
- **Resume Parse Failure:** Displays raw text preview or opens manual entry mode.
- **AI Connectivity Failure:** Preserves resume and profile data. Offers `[Retry]`, `[Fix API Key]`, or `[Continue Without AI]`.
- **Database / Disk Full:** Alerts the user cleanly; does not corrupt `config/setup.json`.
- **App Termination During Setup:** Resumes from the last completed requirement upon relaunch.

---

## 13. Proposed File Changes & Modular Additions

```
app/
├── services/
│   ├── setup/                                  # Setup & Readiness Domain Layer
│   │   ├── __init__.py
│   │   ├── setup_requirements.py               # SetupRequirement & Status Models
│   │   ├── setup_state.py                      # SetupState & SetupEvent (NO SECRETS)
│   │   ├── setup_service.py                    # Adaptive Orchestrator Service
│   │   ├── setup_readiness.py                  # Standalone Reusable Readiness Engine
│   │   └── provider_definitions.py             # Data-driven AI Provider Metadata
│   │
│   └── ai/
│       ├── provider_registry.py                # Generic AI Provider Registry
│       └── model_capabilities.py               # Model capability validator
│
├── ui/
│   ├── widgets/
│   │   ├── onboarding_wizard.py                # Adaptive Shell Dialog (DesignUI.md)
│   │   ├── onboarding_steps/                   # Individual step views
│   │   │   ├── step_welcome.py
│   │   │   ├── step_resume.py
│   │   │   ├── step_profile.py                 # Field provenance & demographics
│   │   │   ├── step_preferences.py
│   │   │   ├── step_ai_provider.py             # Capability test & privacy card
│   │   │   ├── step_qna_review.py              # Canonical facts & conflict resolver
│   │   │   └── step_readiness_summary.py       # Dual-tier status & change audit
│   │   │
│   │   └── tour_overlay.py                     # Contextual Spotlight Tour
│   │
│   └── views/
│       ├── dashboard_view.py                   # Setup Later banner & Readiness card
│       └── settings_view.py                    # "Setup & Readiness" tab
│
tests/
├── test_setup_requirements.py                  # Checklist model tests
├── test_setup_state.py                         # JSON persistence & non-secret audits
├── test_setup_service.py                       # Orchestrator & conflict resolution tests
├── test_setup_readiness.py                     # Core Ready vs Automation Ready tests
├── test_ai_capabilities.py                     # Multi-tier connection & capability tests
└── test_setup_wizard_ui.py                     # Headless PySide6 workflow tests
```

---

## 14. Comprehensive Test Matrix

| Test Suite | Scenario | Expected Behavior |
|---|---|---|
| **Empty Database** | Launch with fresh `jobpilot.db` and empty config | Wizard opens in Quick Setup mode, guides user through Core requirements without error. |
| **Pre-Configured DB** | Launch with completed profile, resume, and preferences | Wizard detects `CORE_READY`, shows green checkmarks, skips already-verified steps. |
| **Partially Configured** | Profile exists, but AI and resume missing | Wizard highlights only Resume and AI steps. |
| **Interrupted Setup** | User exits wizard at Step 3 and restarts app | Relaunch resumes at Step 3; previously entered profile data is intact. |
| **AI Unavailable** | Invalid API key or network disconnect | Text generation fails with helpful error; user clicks "Continue Without AI" and finishes setup. |
| **Malformed Resume** | Corrupted or image-only PDF | Parser reports warning; user enters profile details manually. |
| **Q&A Data Conflict** | Resume says 5 yrs experience; Q&A says 3 yrs | Conflict dialog prompts user to pick authoritative answer. |
| **Cloud AI Setup** | User inputs Groq or OpenAI key | Executes 5-point capability check; displays live latency pill. |
| **Local Ollama Setup** | User chooses Ollama local endpoint | Queries `/api/tags`, auto-populates installed models, passes test. |
| **Pre-Flight Block** | User starts LinkedIn bot without resume | Bot launch halted; exact missing requirement dialog shown with one-click fix route. |
| **Start Over Safety** | User clicks "Start Over" in wizard | Wizard navigation resets; database records and credentials remain intact. |

---

## 15. Migration & Backward Compatibility Plan

1. **Settings Backward Compatibility:** Existing `general.onboarding_completed: true` in `config/settings.json` is respected. Existing users will not be forced through the wizard.
2. **Setup Schema Versioning:** `setup_schema_version: "2.0.0"` is saved in `config/setup.json`. Schema upgrades are handled safely without resetting candidate databases.
3. **Preserving Automation Assets:** All existing platform automations in `platforms/` continue to call existing services unchanged.

---

## 16. Acceptance Criteria (Scenarios A through J)

- [ ] **Scenario A (Brand-New User):** Completes Quick Setup in under 4 minutes; achieves `CORE READY`; Dashboard displays welcome state.
- [ ] **Scenario B (Existing User):** App launches directly to Dashboard; Setup Wizard does not trigger.
- [ ] **Scenario C (Partially Configured):** Wizard presents only unconfigured items with clear "Recommended" labels.
- [ ] **Scenario D (Interrupted Setup):** Closing the app midway preserves completed steps; relaunch prompts resume.
- [ ] **Scenario E (AI Unavailable):** Candidate finishes profile setup manually without being blocked by AI.
- [ ] **Scenario F (Data Conflict):** Contradictory experience years triggers conflict choice dialog.
- [ ] **Scenario G (Cloud AI):** 5-point test verifies connectivity, model availability, and structured JSON output.
- [ ] **Scenario H (Local AI):** Ollama endpoint connects and populates local models.
- [ ] **Scenario I (Automation Pre-Flight):** Automation blocked if critical readiness requirements are missing, providing direct fix link.
- [ ] **Scenario J (Rerun Wizard):** Re-running setup audits existing state without duplicating Q&A entries or wiping credentials.
