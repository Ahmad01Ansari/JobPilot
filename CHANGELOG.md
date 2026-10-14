# Changelog

All notable changes to the JobPilot Desktop Application will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
