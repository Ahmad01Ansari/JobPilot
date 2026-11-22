# Changelog

All notable changes to the JobPilot Desktop Application will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.9-beta] — 2026-11-22

### Cross-Platform Auto-Update System, Foundit Redirect & URL Extraction, and Telemetry Real-Time Sync

This release introduces an in-app cross-platform auto-updater and release notification engine (`UpdateService` and `UpdateDialog`), resolves Foundit modern green redirect toast confirmation and external portal destination extraction, fixes Automation View tab and hero card synchronization during automation execution, and expands regression test suites.

#### Added
- **Cross-Platform Auto-Update & In-App Release Notification Architecture (`UpdateService` & `UpdateDialog`)**:
  - Implemented asynchronous background update checker with GitHub Releases API integration (`Ahmad01Ansari/JobPilot`).
  - Added robust Semantic Versioning comparison supporting pre-release tags (`0.4.9-beta` > `0.4.8-beta`).
  - Added platform-specific release asset auto-discovery for Windows (`.zip`/`.exe`), Linux (`.AppImage`), and macOS (`.dmg`).
  - Implemented chunked background download engine with SHA256 cryptographic checksum verification and real-time progress callbacks.
  - Implemented detached atomic self-updating scripts (`update_helper.bat` for Windows and atomic replacement for Linux AppImages).
  - Built PySide6 `UpdateDialog` modal featuring release notes markdown viewer, version badges, live progress bar, and 1-click update action.
  - Integrated non-blocking startup update notification banner (`NotificationBar`) in `MainWindow` with safety suppression during active automation.
  - Added manual "Check for Updates" trigger in `AboutDialog`.
- **Foundit External Portal URL Extraction & Submission Tracking**:
  - Enhanced `FounditApplier` to click `Apply Now` on external employer postings, detect and extract the target portal URL from child browser tabs, cleanly close extra tabs, and record the application as `SUBMITTED`.
  - Added full telemetry recording for external portal destinations in application notes.

#### Fixed & Enhanced
- **Foundit Green Redirect Toast Confirmation**:
  - Updated `FounditSubmitter.verify_submission` to recognize modern Foundit's green redirect notification toast (`Redirecting you to apply on company site.`) and button state transformation to `Applied` as successful submission.
- **Foundit Job Model Experience Property Fix**:
  - Added setter for `Job.experience_text` in `modules/models.py` to prevent `AttributeError: property 'experience_text' of 'Job' object has no setter` during search result parsing.
- **Foundit Real-Time Qualification & Submissions Telemetry**:
  - Linked Stage 2 experience validation in `FounditRotator` directly to `tracker.record_qualified(job)` to update live qualified counters in `PilotService` and `AutomationWorker`.
- **Automation View Platform Tab Synchronization**:
  - Upgraded `AutomationView` to automatically synchronize active platform tabs and hero cards on progress, discovery, evaluation, and submission events, switching from `LinkedIn` to `Foundit` dynamically when Foundit automation executes.
  - Fixed `AutomationUIState` in `app/ui/widgets/automation/state.py` to ensure discovered, evaluated, qualified, skipped, and submitted KPI counters synchronize accurately.
- **Regression Test Coverage Expansion**:
  - Added `tests/test_update_service.py` verifying SemVer parsing, asset selection, GitHub API payload handling, and update workflows.
  - Added `tests/test_auto_close_stale.py`, `tests/test_outreach_lifecycle_management.py`, and `tests/test_setup_data_transfer.py`.

---

## [0.4.8-beta] — 2026-11-20

### Multi-Platform Analytics Dashboard, ATS Archetype Tracking, and Outreach Attachment Pipeline

This release delivers the unified multi-platform automation dashboard (`index.html` + `app.py`) tracking 1,800+ applications across all 7 supported platforms, automated ATS archetype and reference code extraction, grounded email outreach resume attachment dispatch, and cross-platform GUI/thread lifecycle hardening.

#### Added
- **Multi-Platform Analytics & Automation Dashboard (`templates/index.html` + `app.py`)**: Upgraded web dashboard to automatically aggregate and display applications across all 7 engines (`naukri`, `linkedin`, `indeed`, `universal`, `glassdoor`, `foundit`, `email`/`direct_outreach`) with dynamic platform-aware metric cards.
- **ATS Archetype Detection & Confirmation Tracking**: Integrated live detection for Workday, Greenhouse, Lever, Taleo, iCIMS, SuccessFactors, CatsOne, Google Forms, FreshTeam, Zoho Recruit, and Ashby, rendering styled archetype pills and confirmation reference numbers.
- **Email Outreach Attachment Pipeline**: Grounded Copilot email application flow with automatic discovery and resolution of candidate's default resume PDF (`AppPaths.get_resumes_dir() / default_resume_filename`), attaching physical files to direct outreach emails.
- **AI Career Copilot & Grounded RAG Knowledge Base**: Implemented `PlatformKnowledgeBase` providing grounded UI navigation flows and feature explanations across JobPilot's desktop views.
- **Interactive Simulation & Reasoning Stream**: Implemented real-time interactive thought stream cards (`PilotMessageCard` with animated milestones, pulsing execution steps, and live console logging for automation workers).
- **Semantic Intent Routing & Human Behavior Test Suite**: Built semantic intent router handling complex human inquiries (application status checks, skip keyword additions/removals, compensation queries, and offer audits) with 60 comprehensive unit tests.
- **Single-Instance Application Lock**: Added `SingleInstanceLock` in `app/services/os/single_instance.py` to prevent duplicate concurrent processes from locking SQLite databases or Chrome profiles.
- **Smooth UI Wheel Event Filtering**: Added `app/ui/wheel_filter.py` to prevent accidental value changes on spinboxes and combo boxes during view scrolling.

#### Fixed & Enhanced
- **Dashboard JS Syntax & Header Deduplication**: Corrected unclosed brace syntax in `templates/index.html` preventing dashboard script execution, and eliminated duplicate title rendering in header.
- **Test Worker Thread Safety**: Fixed cooperative thread wait handling during test fixture teardowns in `test_automation_integration.py` and `test_universal_worker_lifecycle.py`, eliminating `QThread: Destroyed while thread is still running` aborts.
- **LogsView Compatibility**: Restored backward-compatible `console` and `txt_search` properties on `LogsView` to satisfy existing test harnesses and legacy callers.
- **Cross-Platform Chrome Lock & Process Recovery**: Added `find_pids_for_profile` using Windows PowerShell (`Get-CimInstance Win32_Process`) and POSIX (`pgrep`) to reliably locate and terminate lingering Chrome instances. Added `lockfile` cleanup to `cleanup_stale_profile_locks`.
- **ChromeOptions Reusability Across All Platforms**: Refactored `FounditBrowser`, `GlassdoorBrowser`, `IndeedBrowser`, `LinkedInBrowser`, and `NaukriBrowser` to use `_build_options()` and `_get_launch_kwargs()`, eliminating the undetected-chromedriver crash (`cannot reuse the ChromeOptions object`) on retry attempts.
- **LinkedIn Seniority Mismatch Gate**: Added `_is_senior_title_mismatch` in `LinkedInRotator` to pre-filter and skip senior, principal, lead, and director roles when candidate experience is below required thresholds.
- **Automatic Experience Level Search Filtering**: Configured `LinkedInRotator` to automatically append `f_E=2%2C3` (Entry level & Associate) for candidates with $\le 2$ years experience.
- **Dynamic Candidate Skill Provenance in QnA**: Updated `QnAEngine` to dynamically draw verified skills from candidate profile records rather than hardcoded domain lists.

## [0.4.7-beta] — 2026-11-17

### Universal ATS Loop Prevention, Mission Control Live Streaming, and Indeed Numeric Normalization

This release stabilizes Universal ATS questionnaire automation, connects real-time thread-safe log streaming to the Mission Control Cockpit, normalizes Indeed phone/numeric field validation, and integrates upstream platform configuration hardening.

#### Fixed
- **Universal ATS Loop Prevention & Dynamic Overview Handling**: Broadened overview apply button regex to recognize multi-language/portal variations, added loop prevention to stop repetitive clicking of entry buttons on identical URLs, expanded embedded ATS iframe detection (Zoho Recruit, NiyukHR, Workable, Breezy, Recruitee, BambooHR, Ashby), and suppressed illegal state transitions from terminal `COMPLETED`.
- **Mission Control Cockpit Real-Time Log Streaming**: Resolved blank logs tab by pointing canonical log path to runtime logs (`AppPaths.get_logs_dir() / "log.txt"`), registered cross-thread `realtime_line_received` Qt Signal with `helpers.add_log_listener`, wired `AutomationManager` typed event bus, and added `refresh()` tab synchronization.
- **Indeed Phone & Number Validation**: Added pure-digit normalization (`_clean_phone_number`) stripping non-digit symbols (`+`, spaces, dashes) to satisfy Indeed's strict integer format (`Answer must be a valid number (no decimals)`), fixed dial code matching to prevent selecting British Indian Ocean Territory (`+246`) over India (`+91`), added explicit standalone checkbox handling, and added self-healing error correction in `advance_to_next_step()`.
- **Platform Configuration Validation & Boolean Normalization**: Normalized `is_enabled` and `enabled` boolean flags in `config/search.py` and `modules/config_loader.py` to prevent `ValueError` crashes on platform initialization.

## [0.4.6-beta] — 2026-11-12

### Native macOS Packaging, Unified Pipeline KPIs & Upstream Enhancements

This release introduces native macOS distribution packages (.dmg & .zip), synchronizes real-time pipeline KPIs across all desktop tabs, and integrates launcher resilience enhancements.

#### Added
- **Native macOS Application Bundle & DMG Packaging**: Added `scripts/build_macos.sh` and PyInstaller `BUNDLE` rule in `JobPilot.spec` creating standalone `JobPilot.app` with Retina display scaling (`NSHighResolutionCapable`), dark mode integration, ad-hoc code signing, and a styled drag-to-Applications `.dmg` installer.
- **Apple Icon Asset Generation**: Extended `scripts/generate_icons.py` with multi-resolution `.icns` support, generating `app/ui/assets/brand/jobpilot.icns`.
- **macOS GitHub Actions Release Workflow**: Added `build-macos` job to `.github/workflows/release.yml` running on `macos-latest` (Apple Silicon M-series) and added `macos-latest` to `.github/workflows/ci.yml`.
- **Website Multi-Platform Download Matrix**: Updated landing page (`DownloadsSection.tsx`, `robot-hero.tsx`, `ArchitectureSection.tsx`, `Footer.tsx`) with a 3-column distribution card grid for Windows, macOS, and Linux.
- **Automatic Virtual Environment Bootstrapping**: Integrated `.venv` auto-detection in `run_desktop.py` to seamlessly re-execute inside the local virtual environment when invoked via unconfigured system Python.

#### Fixed
- **Platform Configuration Validation & Boolean Normalization**: Fixed `ValueError: 'enabled' in platforms.naukri must be a boolean` during platform engine initialization (Naukri, Foundit, and Glassdoor). Updated `config/search.py` (`_read_platform_from_db`) to read `p.is_enabled` and populate `enabled`/`is_enabled`, hardened `modules/config_loader.py` to default `enabled` to `True` when omitted from profile JSON or DB overlays, normalized case-insensitive `apply_mode` strings (`ALL`/`all`), and added `stop_check` parameter to `NaukriRotator.iter_qualified_jobs`.
- **Stagehand Universal Agent Initialization on Windows (Python 3.15+)**: Resolved a critical timeout where Stagehand CDP readiness checks stalled for 60,000ms due to Python 3.15 PEP 690 `lazy from .thread import ThreadPoolExecutor` resolution failure during `asyncio.to_thread(_read_chrome_version)`. Implemented eager runtime normalization in `app/services/os/compatibility.py`, `run_desktop.py`, and `stagehand_agent.py` to pre-bind concrete executor classes.
- **Search Strategy Floating Window Artifacts**: Eliminated orphaned top-level blank windows spawned on Windows when saving job search strategy criteria. Replaced unsafe `w.setParent(None)` calls in `SearchKeywordInput._render_tags` and related layout clearing loops with `w.hide()` and `w.deleteLater()`.
- **Windows Frozen GUI Stream Safeguards**: Implemented `_SafeStream` for `sys.stdout` and `sys.stderr` in `run_desktop.py` to prevent `NoneType` attribute errors in windowed PyInstaller executable builds on Windows.
- **Browser Fallback Discovery on Windows**: Extended browser automation to detect and launch Microsoft Edge, Brave, or Chromium when Google Chrome is not installed on Windows hosts or virtual machines.
- **Automation & QnA Synchronization**: Resolved Windows browser initialization parameters, job link extraction nuances, and candidate question-and-answer persistence in the AI QnA engine.
- **Unified Pipeline KPI Cards**: Replaced fragmented queries with a single canonical repository query `ApplicationRepository.get_canonical_kpi_counts()` across Dashboard, Applications, and Interviews views, ensuring accurate real-time metrics across all tabs.
- **Dynamic Interview Auto-Provisioning**: Moving an application to `INTERVIEW` automatically ensures an active interview round is provisioned with `max_round + 1` scheduling.
- **Resilient Package Initialization (`app/__init__.py`)**: Guarded legacy Flask web dashboard imports with `try...except (ImportError, ModuleNotFoundError)` to prevent desktop startup crashes when optional web modules are absent.
- **Design System Visual Polish**: Refined ThemeManager selection contrast, active focus rings, vector TopBar navigation icons, and `AllActionsDialog` horizontal scrolling lock.
## [0.4.5-beta] — 2026-11-02

### Workday Automation, Profile Repeaters, and Foundit Engine Stabilization

This release brings end-to-end Workday ATS automation, dynamic experience and education repeaters to the desktop GUI, and runtime stabilization for Foundit job search automation.

#### Added
- **Workday Multi-Step Application Pipeline**: Complete end-to-end automation for Workday portals (Candidate contact info, Work Experience repeaters, Education with School Not Found & Degree selection, Skills tags pills, Resume PDF upload, Social URLs, and Disclosures) with a mandatory human Pre-Submission Review gate.
- **Desktop Dynamic Repeater Cards**: Added `ExperienceItemWidget`, `EducationItemWidget`, and `RepeaterCard` to `ProfileView`, allowing full CRUD for work experiences, education history, and skills synchronized with SQLite and `config/profile.json`.
- **Workday Account Management**: Added dedicated credentials and status management dialog for Workday portals in desktop Settings.
- **SSL Certificate Auto-Configuration**: Added `ensure_ssl_certificates()` configuring trusted CA certificates from `certifi` without bypassing TLS verification, resolving ChromeDriver patcher `SSLCertVerificationError` on Linux.
- **Foundit Manual Resolution Gate**: Added `ensure_authenticated()` and `_recover_from_access_denied()` in `FounditBrowser` to recover from poisoned Akamai cookies and provide an interactive 180s window for candidate OTP/CAPTCHA completion.
- **HTML-Escaped Activity Log Stream**: Escaped log messages in `LiveActivityStream` so errors containing angle brackets (e.g. `<urlopen error ...>`) render legibly without being swallowed by Qt rich text formatting.

---

## [0.1.0-beta.4] — 2026-10-30

### Cross-Platform Reliability, High-DPI Scaling & Process Safety Release (Windows & Linux)

This release delivers multi-platform parity across Windows and Ubuntu/Linux, eliminates database startup collision errors, hardens process tree lifecycle and suspension, and enhances UI modals for Windows fractional display scaling (125%/150%).

#### Added
- **Multi-OS CI Verification Pipeline**: Added `.github/workflows/ci.yml` running compilation, unit tests, and headless PySide6 desktop GUI validation on Windows and Ubuntu matrix.
- **Cross-Platform Developer Governance**: Added `.gitattributes` line ending normalizations, comprehensive contributor workflow in `CONTRIBUTING.md`, PR validation template, and contributor rules in `.agents/rules/cross-platform-rules.md`.
- **Cross-Platform Process Suspension**: Added `ProcessManager.suspend_process` and `ProcessManager.resume_process` providing safe suspension on POSIX (`SIGSTOP`/`SIGCONT`) and Windows Win32 API without throwing `AttributeError`.

#### Fixed
- **Platform Repository Duplicate Row Resolution**: Replaced fragile `scalar_one_or_none()` with ordered first retrieval in `PlatformRepository.get_account` and enforced unique indexing and auto-deduplication on startup to prevent `sqlalchemy.exc.MultipleResultsFound` on Windows.
- **High-DPI Modal Layouts**: Replaced fixed geometry (`setFixedSize`) with responsive bounding (`setMinimumSize` + `resize`) in Captcha, About, Intervention, and Job Picker dialogs to prevent clipping under 125%/150% Windows display scaling.
- **Cross-Platform Profile Directory Resolution**: Standardized browser profile discovery using `AppPaths.get_user_data_dir()` for Windows `%APPDATA%` and Linux fallbacks, and replaced raw POSIX `os.chmod` with `AppPaths.safe_set_permissions()`.
- **Settings Import Guard**: Restored missing `failed_file_name` export in `config/settings.py` and imported `Optional` in `modules/open_chrome.py`.

---

## [0.1.0-beta.3] — 2026-10-14

### Windows Polish & Feedback Release (Windows & Linux)

This update resolves UI focus outline styling, Windows scrollbar dithering, canonical Q&A hydration on clean installs, product tour overlay visibility, and onboarding candidate profile synchronization.

#### Fixed
- **Windows Button Outline & Scrollbar Stippling**: Eliminated Windows native dotted focus outlines on action buttons with `outline: none;` and `NoFocus` policies. Configured transparent `add-page` and `sub-page` scrollbar track rules across the application to permanently eliminate Windows 1-bit dithered checkerboard patterns.
- **100+ Canonical Screening Q&A Catalog on Fresh Installs**: Updated `MigrationService` and `SetupService` to automatically seed the full 100+ canonical question catalog into SQLite on initial setup and fresh installs. Added dynamic PyInstaller `sys._MEIPASS` path resolution so frozen Windows executables reliably locate `canonical_qna_catalog.json`.
- **Product Tour Overlay Ergonomics & Transparency**: Prevented duplicate tour guide overlays on onboarding completion. Changed the overlay scrim from an opaque 75% dark tint to a subtle `rgba(15, 17, 23, 0.28)` backdrop and re-anchored the card to the bottom center so users can clearly see and relate to underlying views.
- **Candidate Profile Onboarding Synchronization**: Added `refresh()` capability to `ProfileView` and connected it to onboarding completion signals. Fixed `ProfileService.apply_onboarding_data` and `SetupService.get_existing_profile` to preserve all candidate fields (`current_employer`, `middle_name`, `zipcode`, `address`, `linkedin_url`), immediately reflecting verified resume details in the profile view.

---

## [0.1.0-beta.2] — 2026-10-14

### Private Beta Maintenance & Compatibility Release (Windows & Linux)

This update addresses Windows VM display scaling, setup wizard ergonomics, AI provider validation, and table status lifecycle consistency.

#### Fixed
- **Setup Wizard Window Sizing & Visibility**: Added responsive geometry based on screen `availableGeometry()`, centering above taskbars, and wrapped onboarding step pages in responsive scroll areas so action buttons ("Next", "Continue", "Finish Setup") remain accessible across any display resolution or Windows display scaling (125%/150%).
- **AI Provider Connection Validation**: Fixed false-positive connection check in setup wizard. Connections now pass the active API key, endpoint, and model into `test_connection()` and correctly surface error responses instead of falsely indicating success.
- **Resume Parsing & Profile Pre-population**: Integrated raw text extraction and heuristic parsing fallback (`ResumeParserService` pattern catalog) into the setup wizard, automatically pre-filling candidate details (name, email, phone, title, skills) into the profile review step.
- **Status Badge & Pipeline Consistency**: Standardized `StatusDropdownButton` geometry (112x22px) and removed cell margin clipping across `JobsTable` and `InterviewsView`. Standardized stage lifecycle transitions across Home, Jobs Repository, and Interview Tracking views.
- **Packaging & CI Release Automation**: Automated dynamic version resolution in `scripts/build_windows.bat` and `scripts/build_linux.sh` from `app.version`, and upgraded GitHub Actions release pipeline for flexible Windows artifact bundling (`JobPilot-*-windows-x64.zip`).

---

## [0.1.0-beta.1] — 2026-10-06

### Private Beta Initial Release (Windows 10/11 & Ubuntu/Linux)

This is the initial controlled private beta release targeted at 4–5 active users.

#### Added
- **Cross-Platform Desktop UI**: Full 13-view PySide6 desktop suite featuring dark/light adaptive design tokens, system tray integration, and offscreen headless verification capabilities.
- **Authoritative Versioning**: Unified version string `0.1.0-beta.1` across application runtime, About modal, and Settings views.
- **Sanitized Diagnostic Telemetry**: One-click "Export Diagnostic Report" in Settings and About dialogs, scrubbed through `LogSanitizer` (redacts API keys, cookies, tokens, and passwords).
- **Cross-Platform Deduplication Architecture**: Conservative application deduplication preserving raw portal listings while deduplicating applications across LinkedIn, Naukri, Indeed, Glassdoor, and Foundit based on normalized URLs and ATS requisition IDs.
- **Naukri Search Freshness**: Search filter refinement supporting 1, 3, 7, 15, and 30-day freshness cycles, eliminating misleading Easy Apply toggles for portals without boolean quick-apply flags.
- **Robust Q&A Knowledge Base**: Verified profile facts and deterministic rule cache storing candidate answers with source provenance tracking.
- **Packaging & Distribution Scripts**: PyInstaller build specs (`JobPilot.spec`), automated Linux packaging (`scripts/build_linux.sh`), desktop launcher installer (`scripts/install_linux.sh`), and Windows batch builds (`scripts/build_windows.bat`).

#### Fixed
- **Platform Modal Configuration**: Fixed Naukri card chips and search modals to reflect freshness rather than unsupported `f_AL=true` Easy Apply parameters.
- **SQLite Concurrency & WAL Stability**: SQLite connections enforce `PRAGMA journal_mode = WAL;`, `PRAGMA busy_timeout = 30000;`, and `PRAGMA synchronous = NORMAL;` to prevent database locks during multi-threaded operation.
- **Log Sanitation**: Automated regex scrubber filtering OpenAI, Groq, NVIDIA, Gemini, Anthropic keys, AWS credentials, JWTs, and platform session cookies before disk writes.

#### Known Limitations (Private Beta)
- **Target OS**: Officially validated on Windows 10/11 and Ubuntu 22.04/24.04 LTS. macOS is architecturally supported but deferred for beta distribution.
- **Human Checkpoints**: CAPTCHA and multi-factor authentication (OTP) require manual user interaction via the visible browser window (anti-evasion policy).
