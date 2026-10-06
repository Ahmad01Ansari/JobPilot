# JobPilot — Private Beta Readiness & Audit

## CURRENT IMPLEMENTATION STATE

### 1. Application Architecture & Entry Points
- **Primary Desktop Shell:** [`run_desktop.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/run_desktop.py) boots [`app/main.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/main.py), initializing `QApplication`, DPI pass-through scaling, high-contrast dark theme, and single-instance window icon (`JobPilot.JobAutomation.Desktop.1` on Windows, `jobpilot` on Linux).
- **Core Orchestrator:** [`app/ui/main_window.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/main_window.py) houses the sidebar navigation, dynamic breadcrumbs, top-bar candidate pill, global command palette (`Ctrl+K`), and view switching.
- **Onboarding Wizard Launcher:** [`run_wizard.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/run_wizard.py) launches the 10-step [`OnboardingWizardDialog`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/onboarding_wizard.py).
- **Headless Worker Runner:** [`runAiBot.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/runAiBot.py) provides headless CLI execution for platform rotators.

### 2. Versioning
- **Authoritative Version:** `0.1.0-beta.1` defined in [`app/version.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/version.py) and re-exported in [`app/__init__.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/__init__.py).
- **Surface Presence:** Displayed in About Dialog, Settings, and System Diagnostics.

### 3. Desktop UI Views (13 Core Views + Logs Mission Control)
1. **DashboardView:** KPI summary cards, quick action trigger bar, active application pipeline, weekly application velocity chart, recent application stream.
2. **JobsView:** Live job table, search/filter bar, detail drawer, status badge filtering, match score chips.
3. **ApplicationsView:** Application lifecycle ledger, kanban/table view modes, stage transition modal, timeline audit view.
4. **ProfileView:** Personal data, contact information, compensation preferences, notice period, 26+ technical skills tags, live 100% readiness gauge.
5. **ResumesView:** Multi-role resume manager, default flag, PDF preview trigger, AI extraction status indicators.
6. **QnAView:** 398 screening question-answer bank, live search, add/edit modals, interactive test-match diagnostics.
7. **PlatformsView:** Multi-platform grid (LinkedIn, Naukri, Indeed, Foundit, Glassdoor, Email Outreach), runtime config modals, platform-tailored options (Naukri freshness without invalid Easy Apply switch, LinkedIn `f_AL` hybrid toggles).
8. **SearchView:** Search term rotation tags, positive/negative exclusion lists, global sync across platforms.
9. **OutreachView:** Direct email sequence builder, recruiter thread manager, follow-up scheduler, template catalog.
10. **InterviewsView:** Recruiter interview tracker, stage logs, question prep cards, offer evaluation.
11. **FollowUpsView:** Automated and manual recruiter outreach follow-up cadence monitor.
12. **AnalyticsView:** Application conversion rates, platform response rates, time-to-first-response metrics.
13. **SettingsView:** System settings, encrypted credentials manager, AI provider configuration, backup/restore center, and diagnostic report exporter.
14. **LogsMissionControl (Dialog):** Bounded real-time event timeline, log stream filtering, sanitization status.

### 4. Service & Domain Architecture
- **Layer Boundary:** Strict separation: `UI` (`app/ui/`) → `Service` (`app/services/`) → `Repository` (`app/repositories/`) → `Database` (`app/db/`).
- **Profile & Resume:** `ProfileService`, `ResumeService`, `CandidateContextProvider`.
- **Screening Knowledge:** `QnAService`, `QnASeedService`, `QnAEngine` (multi-tier answer resolution: Profile Fact → Canonical Rule → Calculation → AI).
- **Deduplication:** `JobDeduplicationService` (URL normalization with query allowlist, fuzzy title/company similarity, cross-platform opportunity clustering).
- **Security & Secrets:** `SecretsService` (Fernet-based AES-128 encryption with OS-isolated key storage), `LogSanitizer` (redaction of tokens, keys, passwords, bearer headers), `URLSecurityValidator` (SSRF and loopback protection).
- **Database & Persistence:** SQLite WAL mode with 30s busy timeout, SQLAlchemy 2.0 ORM, idempotent migration and seeding routines in `MigrationService`.

### 5. Automation Engines
- **LinkedIn:** Search query rotation, `f_AL` Easy Apply, multi-step application form filler, safety gate review.
- **Naukri:** Search query rotation with `jobAge` freshness filter, 1-click in-app submission, external listing capture.
- **Foundit:** Multi-keyword rotation, quick-apply filter toggle, application tracking.
- **Glassdoor:** Multi-term search rotation, easy-apply switch handling, evaluation pipeline.
- **Indeed:** Multi-term rotation, "Easily apply" vs company portal identification.
- **Universal Agent:** State machine orchestrator for external ATS portals (Workday, Greenhouse, Lever, Ashby, BambooHR) with human-in-the-loop fallback.

---

## BETA ACCEPTANCE CRITERIA (The Beta Contract)

JobPilot Private Beta is targeted at **4–5 real users** running **Windows 10/11** and **Ubuntu/Linux**.
To be approved for Beta Distribution, the application must satisfy:

1. **Zero Data Loss:** All user-entered profile fields, resumes, Q&A entries, and platform settings must survive application restart, upgrade, and backup/restore cycles.
2. **Deterministic State Transitions:** An application is never marked `SUBMITTED` without confirmed success evidence from the browser engine.
3. **No Thread Deadlocks or UI Freezes:** All network requests, LLM generation, resume parsing, and browser automation must execute off the Qt main thread. Bounded timeouts (15–30s) must protect against network stalls.
4. **No Orphaned Processes:** Chrome, ChromeDriver, and background worker threads must cleanly terminate on application exit, stop request, or crash.
5. **Safe Interruption & Recovery:** Force-closing the application or experiencing a network drop during automation or AI requests must restore cleanly to a known state on next launch.
6. **No Secret Leaks:** API keys, passwords, and session tokens must never appear in raw logs, UI error dialogs, crash reports, or diagnostic exports.
7. **Actionable Recovery UX:** Recoverable errors must present what happened, why, and clear user actions (Retry, Configure, Skip).
8. **Sanitized Diagnostics:** Users must be able to export a complete, sanitized `JobPilot_Diagnostic_Report.json` / `.md` without exposing sensitive credentials.
