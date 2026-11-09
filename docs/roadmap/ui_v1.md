# Walkthrough — Profile Restoration & Modern Data-Sheet UI/UX Redesign

We have resolved both user requests:
1. **Restored Ahmad's Profile**: Fully restored candidate profile data across SQLite (`User`, `Profile`, `ProfessionalProfile`) and `config/profile.json` (Mohd Ahmad Raza Ansari, `candidate@example.com`, AventIQ AI, 2.0 yrs experience, 3.5 LPA / 5.5 LPA, 30 days notice). Fortified test suite isolation with `is_test = True` so running tests will never overwrite real user profile configs.
2. **Modern CRM / Donor Spec-Sheet Redesign**: Transformed Candidate Profile view ([`app/ui/views/profile_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/profile_view.py)) into the symmetrical 2-column data-sheet architecture shown in the reference design (`media_1789979448985.png`). Features:
   - **Candidate Profile Banner**: Initials avatar badge (`MA`), bold candidate name, category badge (`RPA & AI AUTOMATION`), contact info, and quick highlight metrics (`CURRENT CTC`, `TARGET CTC`).
   - **Symmetrical 2-Column Cards**: Equal 50/50 split with fixed 125px uppercase muted labels (`FIRST NAME`, `MOBILE`, `ADDRESS`, `CURRENT ROLE`, etc.), aligned values, and subtle 1px dividers.
   - **Dual View / Edit Modes**: Clean data presentation in View Mode with instant `[Edit Profile ✏️]` toggle to uniform 34px inputs in Edit Mode.
   - **Interactive Skills & Profiles**: Core skill pills, summary typography, and direct action links.

---

## 1. Key Accomplishments & Technical Changes

### 1. Modern Web UI/UX for Detail & History Dialogs ([`app/ui/widgets/activity_dialogs.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/activity_dialogs.py))
- **Eliminated Nested Box-in-Box Look**:
  - Previously, `QLabel` inherited from `QFrame` in Qt, and a catch-all `QFrame { border: 1px solid #262C36; border-radius: 12px; }` in `theme.py` caused every single text label inside popups to render inside its own rounded border box.
  - Refined `app/ui/theme.py` so that `QLabel` has `border: none; background: transparent;`, and default `QFrame` has `border: none;`.
  - Rebuilt [`ActivityDetailDialog`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/activity_dialogs.py) into a clean, modern web modal:
    - Header: Icon pill with dark accent background, event title (`15px 700`), humanized timestamp, and platform pill badge.
    - Body: Clean key-value specification list where each row has a muted label (`#8B949E`), high-contrast value (`#F0F6FC`), and an ultra-subtle bottom divider line (`border-bottom: 1px solid #21262D`).
    - Status value renders as a crisp, pill-shaped badge (`#238636` background tint, `#3FB950` text).
    - Job listing URL renders as an accessible `Open Job Link ↗` hyperlink.
  - Rebuilt [`AllActivityDialog`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/activity_dialogs.py) into a sleek timeline feed:
    - Clean platform tags (`#FF5F15` tint), bold job titles, muted descriptions, relative timestamps, and hover state transitions.

### 2. Real-Time Profile Persistence & App Boot Guard ([`app/services/profile_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/profile_service.py), [`app/services/migration_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/migration_service.py))
- **`github_url` and Blanked Values**:
  - `_sync_to_profile_json` now explicitly tests `"github_url" in professional_data` and `"portfolio_url" in professional_data`, properly writing empty strings `""` when a user clears a URL, rather than ignoring empty strings.
  - Added `github_url=prof.get("github_url")` to `ProfessionalProfileUpdateDTO` in `MigrationService.migrate_user_and_profiles()`.
- **Database Boot Protection**:
  - `MigrationService.migrate_user_and_profiles()` now checks if `user_repo.get_profile(user.id)` and `user_repo.get_professional_profile(user.id)` already exist in the SQLite database. If both exist, it skips overwriting them from static JSON files on boot.
- **Immediate UI Refresh**:
  - `ProfileView._on_save_clicked()` now invokes `self.load_profile()` immediately upon successful save, reloading all inputs and recalculating readiness directly from the database in realtime.
- **Unit Test Isolation**:
  - `ProfileService.is_test` flag ensures that test runs with custom/temporary session factories never mutate `config/profile.json` or dirty live application configs.

### 3. Profile Page UI/UX Polish ([`app/ui/views/profile_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/profile_view.py), [`app/ui/theme.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/theme.py))
- **Card Containers**: Replaced old `QGroupBox` border-cutout titles with modern card `QFrame` containers with an internal header label, eliminating border clipping and text collisions.
- **`QDoubleSpinBox` Styling**: Added `QDoubleSpinBox` to the global dark stylesheet in `app/ui/theme.py`, setting 36px height, dark charcoal background, `#262C36` border, and 20px padding to prevent spin arrows from overlapping numerical text.
- **Standardized Field Heights**: All `QLineEdit`, `QSpinBox`, `QDoubleSpinBox` inputs are now standardized at minimum `36px` height with clean 12px muted field labels and 10px grid spacing.

### 4. Screening Q&A Knowledge Base Layout Fixes ([`app/ui/views/qna_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/qna_view.py))
- **Column Header Modes**:
  - Column 0 (`Question Prompt`): `Stretch` mode so prompts have ample horizontal room.
  - Column 1 (`Answer`): `Stretch` mode with text truncated to 55 characters + `...` for preview, with the full answer available on hover via `item.setToolTip()`.
  - Column 2 (`Type`): Fixed at 90px (displays `BOOLEAN` and `TEXT` without truncation).
  - Column 3 (`Category`): Fixed at 115px.
  - Column 4 (`Platform`): Fixed at 95px.
  - Column 5 (`Status`): Fixed at 120px (no more `'ERIFIED` badge clipping).
  - Column 6 (`Actions`): Fixed at 160px (spacious `[Active]`, `[Edit]`, `[✕]` buttons).
- **Row Sizing**: Standardized vertical section size at 44px for clean, breathable table rows.

---

## 2. Test Verification & Results

1. **Compilation Check**:
   ```bash
   .venv/bin/python -m py_compile runAiBot.py app.py config/*.py modules/*.py platforms/*.py app/ui/widgets/*.py app/ui/views/*.py app/services/*.py tests/*.py
   ```
   *Result:* Clean compilation, 0 syntax or import errors.

2. **Persistence E2E Verification**:
   - Simulated saving `github_url` and blanking `portfolio_url` via `ProfileService.save_profile()`.
   - Verified database records updated correctly (`github_url: 'https://github.com/Ahmad10Raza'`, `portfolio_url: None`).
   - Verified `config/profile.json` updated correctly.
   - Executed `MigrationService.run_full_migration()` (simulating app restart) and confirmed database values were preserved.

3. **Full Automated Test Suite**:
   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```
   *Result:* **378 tests passed, 0 failures, 0 errors in 134.9s!**

4. **Desktop UI Pre-Flight Test**:
   ```bash
   .venv/bin/python run_desktop.py --offscreen --test-run
   ```
   *Result:* Clean startup with all 13 views and services initialized successfully.

---

## 3. Previous Phase Accomplishments (Phase 15 & Roadmap)

### 1. Unified Cross-Entity Global Search Engine
- **Service ([`app/services/search_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/search_service.py)):**
  - High-performance, multi-token search querying across 5 core entities:
    1. **Jobs**: Searches title, company name, location, experience text, and description.
    2. **Applications**: Joins Job, matches title, company, application status, notes, and failure reasons.
    3. **Companies**: Matches name, location, industry, notes, and website.
    4. **Contacts / Recruiters**: Joins Company, matches recruiter name, email, phone, designation, and notes.
    5. **Interviews**: Joins Application and Job, matches round name, interviewer, mode, notes, meeting links, and company.
  - **Category Filtering**: Supports filtering by entity type (`All`, `Jobs`, `Applications`, `Companies`, `Contacts`, `Interviews`).
  - **Structured Results**: Returns dataclasses `SearchResultItem` and `GlobalSearchResult` with color-coded status badges, formatted subtitles, and routing targets (`target_page`).

### 2. Desktop Notifications & Follow-Up Reminders
- **Service ([`app/services/notification_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/notification_service.py)):**
  - **System Tray Integration**: Native `QSystemTrayIcon` notifications on supported desktop environments, with graceful fallback to in-app banners (`NotificationBar` / `AppState.notify`).
  - **Automated Reminder Scans**:
    - Scans for **upcoming interviews** within a 24-hour window (`status == 'SCHEDULED'`).
    - Scans for **due and overdue follow-ups** (`status == 'PENDING'`, `due_at <= now + 12h`).
    - **Deduplication Engine**: Tracks alerted interview and follow-up IDs to prevent repetitive alert fatigue across periodic check intervals.
  - **Automation Alert Hooks**:
    - Connects to [`AutomationManager`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/automation_service.py) signals.
    - Dispatches instant warnings on `intervention_required` (`LOGIN_REQUIRED`, `CAPTCHA_DETECTED`).
    - Dispatches notifications on `run_finished` (`COMPLETED`, `FAILED`).
    - Dispatches notifications on `application_submitted`.
  - **Periodic Polling**: Integrates a `QTimer` background poller running at configurable intervals (default: 15 minutes).

### 3. Command Palette & Quick Search UI
- **Modal Search Dialog ([`app/ui/widgets/search_dialog.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/search_dialog.py)):**
  - Fast search-as-you-type command palette with 150ms keystroke debouncing.
  - Category pill filter chips (`All`, `Jobs`, `Applications`, `Companies`, `Contacts`, `Interviews`).
  - Arrow key navigation (`↑`/`↓`), Enter to select, and Esc to dismiss.
  - One-click routing: selecting any item navigates directly to its target view (`jobs`, `applications`, `interviews`, `followups`).
- **TopBar Search Trigger ([`app/ui/top_bar.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/top_bar.py)):**
  - Integrated `🔍 Search jobs, companies... Ctrl+K` button in the header.
  - Binds the global `Ctrl+K` shortcut anywhere in the application window.
- **Main Window Assembly ([`app/ui/main_window.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/main_window.py)):**
  - Connects `TopBar` search and `Ctrl+K` to `GlobalSearchDialog`.
  - Instantiates `NotificationService`, runs startup reminder scans, and wires automation manager events.

---

## 2. Test Verification & Results

### Automated Test Suite Execution
1. **Compilation Check**:
   ```bash
   .venv/bin/python -m py_compile runAiBot.py app.py config/*.py modules/*.py platforms/*.py platforms/naukri/*.py tests/*.py
   ```
   *Result:* Clean compilation, 0 syntax or import errors.

2. **Phase 15 Dedicated Tests ([`tests/test_notifications_and_search.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/tests/test_notifications_and_search.py))**:
   - 17 comprehensive unit & integration tests:
     - `TestSearchService`: multi-entity queries, token matching, category filters, empty/whitespace queries.
     - `TestNotificationService`: interview reminders, due/overdue follow-up alerts, deduplication cache, intervention alerts, run completions, settings suppression.
     - `TestUIIntegration`: dialog rendering, live search execution, item selection signal, TopBar search button, `Ctrl+K` shortcut, navigation routing.
   *Result:* 17/17 passed in 0.938s.

3. **Full System Regression Suite**:
   ```bash
   .venv/bin/python -m unittest discover -s tests
   ```
   *Result:* **344 tests passed, 0 failures, 0 errors in 92.8s!**

---

## 3. Master Desktop Roadmap Summary

With Phase 15 complete, the consolidated desktop roadmap has been fully implemented:

| Phase | Description | Status |
|---|---|---|
| **Phases 1–8** | Foundation, DB models, Profile, Resume, Q&A | ✅ Complete (247 tests) |
| **Phase 9** | Platform Management, Search Config & Settings | ✅ Complete (259 tests) |
| **Phase 10** | Jobs & Applications Core, SHA-256 Deduplication | ✅ Complete (275 tests) |
| **Phase 11** | Recruitment Pipeline, Interviews, Contacts, Follow-ups | ✅ Complete (289 tests) |
| **Phase 12** | Dashboard & Analytics, Conversion Rates | ✅ Complete (298 tests) |
| **Phase 13** | Automation Engine Integration (LinkedIn & Naukri wrapped) | ✅ Complete (311 tests) |
| **Phase 14** | Settings, Fernet Security & Staging-Isolated Backup | ✅ Complete (327 tests) |
| **Phase 15** | Desktop Notifications & Cross-Entity Smart Search | ✅ Complete (344 tests) |
| **UI/UX Polish**| Modern ATS Transformation (SmartHR Aesthetic, 349 tests) | ✅ Complete (349 tests) |

---

## 4. Modern ATS UI/UX Transformation (SmartHR / Ashby Aesthetic)

In accordance with [`Roadmap/desktop-ui/template-example/`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/Roadmap/desktop-ui/template-example/) and [`Roadmap/desktop-ui/ui_transoform.md`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/Roadmap/desktop-ui/ui_transoform.md), the desktop application was transformed from an administrative utility look into a spacious, modern, card-based Applicant Tracking System (ATS) & Career CRM:

1. **Design Tokens & Theme ([`app/ui/theme.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/theme.py)):**
   - **Refined Dark Canvas (`#0F1117`)**: Clean pitch-dark obsidian neutral canvas replacing the previous deep navy tint. High-contrast charcoal card surfaces (`#161B22`), elevated headers (`#1C2128`), and soft non-intrusive borders (`#262C36`).
   - **Crisp Light Canvas (`#F6F8FA`)**: Minimalist light canvas with pure white card surfaces (`#FFFFFF`), subtle borders (`#D0D7DE`), and deep text (`#1F2328`).
   - **Vibrant Safety Orange (`#FF5F15`)**: High-energy primary accent color (hover: `#E04F0B`, subtle tint: `#FF5F1518`), applied to active navigation pills, primary action buttons, key metrics, and focus rings.
   - **Theme Switching**: Introduced `ThemeManager.apply_dark_theme()`, `ThemeManager.apply_light_theme()`, and `ThemeManager.toggle_theme()` with on-the-fly toggling via the `TopBar` quick toggle button (`🌙` / `☀️`).
   - Fixed unclosed QScrollBar CSS syntax in Qt stylesheet engine.

2. **Component Library ([`app/ui/widgets/`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/)):**
   - **[`ModernMetricCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/metric_card.py):** Circular tinted icon badge, large high-contrast metric values (26px bold), uppercase category label, and trend indicator pill.
   - **[`WelcomeBanner`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/welcome_banner.py):** Candidate greeting banner displaying current pipeline status summary and quick action triggers (`[🔄 Refresh]`, `[+ Add Job]`, `[▶ Run Automation]`).
   - **[`PipelineFunnelCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/pipeline_funnel.py):** Visual horizontal progress bars for recruitment stages (Discovered, Submitted, Under Review, Interview, Offer) with live percentage fills and stage counts.
   - **[`UpcomingSchedulesCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/upcoming_schedules.py):** Upcoming interview cards with round badges, formatted date/time chips, and direct "Join Meeting ↗" web links.

3. **Smooth Card-Based Scrollable Settings ([`app/ui/views/settings_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/settings_view.py)):**
   - Each configuration tab (General, Browser, Automation, AI & Screening, Credentials & Security, Backup & Restore) is now a smooth, card-based scrollable container (`QScrollArea` wrapping dedicated section `QFrame` cards).
   - Balanced typography with bold headings, informative subtitles, and generous 16–20px card padding.
   - Safety Orange primary action buttons with clear reset/save operations.

4. **Testing & Verification:**
   - Pre-flight headless verification passed: `.venv/bin/python run_desktop.py --offscreen --test-run`.
   - Full automated test suite: **349 tests passed, 0 failures, 0 errors in 99.3s!**

---

## 5. Refined Dark Canvas Resolution & Border Restoration

### Decision & User Directive
As requested by the user (*"home page border gone? and apart from home all page white theme not working somehwre dark somwhere white. try in one time if not possible let drop white theme will proceed dark theme only"*), we dropped the inconsistent multi-theme toggle and unified the entire application on the **Refined Dark Canvas (`#0F1117`)** with **Safety Orange (`#FF5F15`)** accents and crystal-clear card borders.

### Key Fixes Applied:
1. **Full Border & Surface Restoration on Dashboard:**
   - **[`WelcomeBanner`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/welcome_banner.py):** Restored `#161B22` background, `#262C36` border, `#F0F6FC` heading, and Safety Orange `#FF5F15` CTA button.
   - **[`ModernMetricCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/metric_card.py):** Restored `#161B22` card background, `#262C36` card borders, 26px `#F0F6FC` bold metric text, uppercase labels, and hover borders (`{accent}80`).
   - **[`PipelineFunnelCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/pipeline_funnel.py):** Restored `#161B22` card background, `#262C36` border, `#1C2128` progress track bars, and stage counts.
   - **[`UpcomingSchedulesCard`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/upcoming_schedules.py):** Restored `#161B22` card background, `#262C36` card border, and `#1C2128` schedule item cards.
   - **[`DashboardView`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/dashboard_view.py):** Restored `#161B22` backgrounds and `#262C36` borders for `platform_frame` and `activity_frame`, with `#1C2128` breakdown rows.
   - **[`PageHeader`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/page_header.py):** Restored `#F0F6FC` bold title and `#8B949E` subtitle.

2. **TopBar & Sidebar Cleanup:**
   - **[`TopBar`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/top_bar.py):** Removed the theme toggle button. Styled with `#161B22` surface, `#262C36` bottom border, `#1C2128` search bar with `#333A46` border and `#FF5F15` hover state, and `#1C2128` candidate pill.
   - **[`Sidebar`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/sidebar.py):** Styled with `#161B22` surface, `#262C36` right border, Safety Orange `#FF5F15` "JP" logo badge, and `#FF5F1522` active pill.

3. **Visual Verification:**
   - Saved visual captures:
     - Dashboard: ![Dashboard Dark Canvas](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_dark_verified.png)
     - Applications: ![Applications Dark Canvas](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/applications_dark_verified.png)

4. **Testing & Regression Suite:**
   - Pre-flight headless verification passed: `[JobPilot Desktop] Verified: UI shell, DB connection, 13 views, services, and event bus initialized successfully.`
   - Full automated test suite: **350 tests passed, 0 failures, 0 errors in 104.5s!**

---

## 6. Dashboard Platform Automation Trigger Deck & Dark Theme Standardization

We standardized the JobPilot Desktop UI exclusively on the **Refined Dark Canvas (`#0F1117`)** with **Safety Orange (`#FF5F15`)** accents, and built a prominent, high-visual-weight **Platform Automation Trigger Deck** right on the ATS Dashboard.

### A. Dashboard Platform Automation Trigger Deck (`PlatformTriggerDeck`)
- **Outer Command Surface:** `#161B22` background, `#262C36` border, 14px radius, placed right below the KPI metric cards.
- **Deck Header:**
  - `⚡` Safety orange icon badge.
  - Title: **Platform Automation Launch Deck** with subtext.
  - Live Status Pill: transitions between `● Ready to Launch` (green), `⚡ Running: [Platform]` (Safety Orange), and `⏳ Stopping...` (Amber).
  - `Console ↗` button to jump straight to the live automation monitor.
- **3 Weighted Platform Action Cards (`PlatformCardTile`):**
  - **LinkedIn:** Azure branding (`#0A66C2`), "Easy Apply" tag, "Stealth Profile Active" badge, `[▶ Run LinkedIn]` action button.
  - **Naukri.com:** Cyan branding (`#0284C7`), "FastForward" tag, "Safety Review Gate" badge, `[▶ Run Naukri]` action button.
  - **All Platforms:** Safety Orange highlight border (`#FF5F15`), "Sequential" tag, "Multi-Platform Batch" badge, and `[🚀 Launch All]` primary CTA button.
- **Live Telemetry & Cooperative Stop Tray:**
  - Automatically slides out during execution.
  - Shows active engine name, current search keyword (`🔍 Term: "..."`), real-time job counters (`Discovered`, `Qualified`, `Submitted`, `Errors`), an orange progress bar, and a live log line.
  - Includes a prominent `[⏹ Emergency Stop]` button to request graceful engine shutdown.

### B. Visual Verification

#### Dashboard Overview with Ready Launch Deck
![Dashboard Trigger Deck Idle](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_trigger_deck_idle.png)

#### Dashboard Overview with Active Telemetry & Stop Tray
![Dashboard Trigger Deck Running](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_trigger_deck_running.png)

---

## 7. Full User Data, API & Backend Connectivity Audit & Synchronization

We conducted an exhaustive audit of all user data, APIs, and backend services to ensure 100% two-way connectivity with the desktop UI:

### A. Real User Data & Primary Candidate Resolution
- **Issue Resolved:** The SQLite database previously held an unseeded placeholder (`Candidate`, `candidate@jobpilot.local`) with no profiles, which was masking the real candidate.
- **Action Taken:** Cleaned up the orphaned placeholder and ran full idempotent migration. The system now loads the real candidate: **Mohd Ahmad Raza Ansari** (`candidate@example.com`, `+1 555-0199`, Delhi, 2.0 yrs experience, 3.5 LPA / 5.5 LPA, 30 days notice).
- **Auto-Migration on Launch:** Updated `app/main.py` so that whenever the application launches, `MigrationService().run_full_migration()` ensures all data, resumes, QnA entries, and historical applications are automatically synchronized into the relational database.

### B. Two-Way Synchronization (UI ⇄ Database ⇄ `config/profile.json`)
- **Profile Updates:** Added `_sync_to_profile_json()` in `ProfileService.save_profile()`. Whenever the user edits personal or professional details, compensation, notice period, or skills in `ProfileView`, changes are committed to SQLite AND written back to `config/profile.json` (with cache invalidation), ensuring that automation engines (`runAiBot.py`) immediately pick up the latest candidate information.
- **Search & Platform Updates:** Added `_sync_search_to_profile_json()` in `PlatformService.save_search_config()` and `update_platform_config()`. Changes made to search keywords, locations, experience filters, and max applications in `SearchView` or `PlatformsView` immediately synchronize back into `config/profile.json` and `config/search.py`.
- **Secrets & Credentials:** Verified that `config/secrets.py` reads directly from `SecretsService.get_secret()`. Credentials saved in `SettingsView` (LinkedIn, Naukri, AI API Keys) are encrypted with Fernet in the DB and decrypted on-the-fly for the bot engines.

### C. Live Backend Data Verification Across Core Views
- **Dashboard (`DashboardView`):** Displays real candidate greeting "Welcome Back, Mohd Ahmad Ansari", 144 discovered jobs, 144 submitted applications, 36 in active pipeline, and platform breakdown (36 LinkedIn, 108 Naukri).
- **TopBar (`TopBar`):** Candidate profile pill displays `👤 Mohd Ahmad Ansari` dynamically, and clicking it navigates straight to the Candidate Profile page.
- **Resumes (`ResumesView`):** Resolved return unpacking in `migration_service.py` to register the candidate's PDF resume (`Mohd Ahmad Raza Ansari Resume 11 09 2026.pdf`) as the default active resume.
- **Jobs & Applications (`JobsView` & `ApplicationsView`):** Fully populated with all 144 real historical jobs and applications with state machine transitions and audit trails.
- **QnA Knowledge Base (`QnAView`):** 110 screening questions and answers loaded from `config/profile.json` & `config/questions.py` ready for automated answering and test matching.
- **Search (`GlobalSearchDialog` via `Ctrl+K`):** Unified multi-entity search searches across all jobs, companies, applications, and contacts.

### D. Visual Verification of Live Connected Data

#### Dashboard with Real Candidate Data & 144 Applications
![Dashboard Live Data](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_live_data.png)

#### Profile View with 95% Readiness & Verified Candidate Details
![Profile Live Data](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/profile_live_data.png)

#### Jobs Repository with Migrated Opportunities
![Jobs Live Data](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/jobs_live_data.png)

---

## 8. Switchable Platform Distribution Charts & Balanced Activity Stream

### A. Switchable Interactive Platform Distribution Widget (`PlatformChartCard`)
- **Widget Implementation ([`app/ui/widgets/platform_chart_card.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/platform_chart_card.py)):**
  - Designed an interactive segmented chart switcher widget (`[ 📊 Bars | 🍩 Donut | 📋 Cards ]`) featuring dark obsidian styling (`#161B22` background, `#262C36` border) and active Safety Orange highlights (`#FF5F15`).
  - **View 0 — Volume Share Bars (`📊 Bars`):** Comparative horizontal progress tracks color-coded per platform (`#0284C7` for Naukri, `#0A66C2` for LinkedIn, etc.) with rounded corners, percentage badge pills, and job/application count summaries.
  - **View 1 — High-DPI Vector Donut Chart (`🍩 Donut`):** Custom `QPainter` vector donut canvas with anti-aliased arcs, central summary cutout (`144 Total Jobs`), and an aligned legend with colored bullet indicators, percentage shares, and counts.
  - **View 2 — Platform Metric Cards (`📋 Cards`):** Detailed breakdown cards displaying Jobs, Applications, Interviews, and Offers per platform.

### B. Recent System Activity Sizing & Height Alignment
- **Activity Stream Optimization ([`app/ui/views/dashboard_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/dashboard_view.py)):**
  - Restricted the recent activity list to the **top 5 most recent events** (down from 8) to maintain vertical harmony with the chart card.
  - Synchronized minimum card heights to `320px` across both `platform_chart_card` and `activity_frame`.
  - Added bottom container stretching to eliminate dead space and prevent vertical misalignment across different window sizes.

### C. Visual Comparison of the Switchable Views

#### 1. Volume Share Bars View (`📊 Bars`)
![Dashboard Chart Bars](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_chart_bars.png)

#### 2. Vector Donut Chart View (`🍩 Donut`)
![Dashboard Chart Donut](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_chart_donut.png)

#### 3. Platform Metric Cards View (`📋 Cards`)
![Dashboard Chart Cards](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_chart_cards.png)

---

## 9. Onboarding Wizard & Universal AI Engine

### A. Universal AI Service ([`ai_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/ai_service.py))
- Multi-provider AI engine supporting **Ollama** (local), **OpenAI**, **Gemini**, and **DeepSeek**
- `test_connection()` validates provider endpoints with latency measurement
- `generate_text()` and `extract_structured_json()` for resume parsing and Q&A
- Configuration persisted via `SettingsRepository` + `SecretsService` (encrypted API keys)
- Used universally across the application — onboarding, resume extraction, screening Q&A

### B. Resume Parser Service ([`resume_parser.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/resume_parser.py))
- Extracts raw text from **PDF** (pypdf), **DOCX** (python-docx), and plain text files
- Two extraction tiers:
  1. **AI Extraction**: Sends resume text to Universal AI Service for structured JSON extraction
  2. **Heuristic Fallback**: Regex-based extraction of email, phone, LinkedIn/GitHub URLs, name, 30+ tech skills, experience years
- Returns structured `(data_dict, raw_text, method_used)` tuple

### C. Onboarding Wizard Dialog ([`onboarding_wizard.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/onboarding_wizard.py))
6-step guided setup wizard that launches on first run:

#### Step 1: Welcome & Feature Tour
![Welcome Step](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/onboarding_welcome.png)

#### Step 2: Universal AI Provider Setup
![AI Setup Step](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/onboarding_ai_setup.png)

#### Step 3: Resume Upload
![Upload Step](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/onboarding_upload.png)

#### Step 5: Review & Edit Extracted Profile (4-tab editor)
![Review Step](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/onboarding_review.png)

#### Step 6: Setup Complete
![Complete Step](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/onboarding_complete.png)

### D. Profile Sync Pipeline ([`profile_service.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/services/profile_service.py))
- `apply_onboarding_data()` maps wizard output to `save_profile()` Dict-based API
- Syncs Q&A screening defaults (work authorization, relocation, remote) to `QnAEntry` table
- Triggers `_sync_to_profile_json()` → `config/profile.json` for automation engine pickup

### E. MainWindow Integration ([`main_window.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/main_window.py))
- `_check_onboarding()` checks `general.onboarding_completed` flag on startup
- Deferred launch via `QTimer.singleShot(500ms)` to ensure window is visible first
- Skipped in offscreen/test-run mode to avoid blocking CI

### F. Settings View Enhancements ([`settings_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/settings_view.py))
- `_on_ai_provider_changed()` updates placeholder hints per provider
- `_launch_setup_wizard()` opens onboarding wizard from Settings → AI tab

### G. Test Results
- **27/27 onboarding & AI tests** passed (AI Service, Resume Parser, Wizard UI, Profile Sync, Universal AI Engine Bridge)
- **9/9 foundation tests** passed (no regressions)
- **Desktop preflight**: 13 views verified, exit code 0
- **Full syntax compilation**: All source files clean

---

## 10. Header Badges Redesign, Activity Popups & Profile Restoration

### A. Square Status Badges Proportional to Font Size ([`status_badge.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/status_badge.py) & [`top_bar.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/top_bar.py))
- **Problem**: Status badges in the top bar were stretching vertically to fill the layout height, appearing as oversized 40px tall chunky blobs.
- **Solution**:
  - Replaced bulky pill radius with sharp, square corners (`border-radius: 4px`).
  - Added fixed height constraints (`setFixedHeight(20)`) and proportional padding (`1px 7px`, `font-size: 11px`, `font-weight: 600`).
  - Set `plat_layout.setAlignment(Qt.AlignVCenter)` in `TopBar` so badges align cleanly with the label text without vertical stretching.

![TopBar Square Badges](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/topbar_square_badges.png)

### B. Recent System Activity "View All" & Focused Record Popups ([`activity_dialogs.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/widgets/activity_dialogs.py) & [`dashboard_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/dashboard_view.py))
- **Card Header Action**: Added an interactive **`View All →`** button in the Recent System Activity card header (`#1C2128` background, `#FF5F15` Safety Orange accent).
- **Row Interactivity**: Every activity item now features an interactive **`Details →`** button, pointing hand cursor, and hover highlight.
- **`ActivityDetailDialog`**: A focused modal popup displaying only the essential information for that specific record:
  - Event type badge & timestamp
  - Job Title, Company Name, and Location
  - Application/Job Status highlighted in Safety Orange
  - Direct listing link and supplementary metadata (experience/salary or interview details)
- **`AllActivityDialog`**: A modal log listing all system events with a platform filter dropdown (`All Platforms`, `LinkedIn`, `Naukri`). Clicking any record opens its `ActivityDetailDialog`.

#### Recent System Activity Card with View All Button:
![Dashboard Recent Activity](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_recent_activity_card.png)

#### Focused Record Detail Popup (`ActivityDetailDialog`):
![Activity Detail Popup](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/activity_detail_popup.png)

#### Full System Activity Log (`AllActivityDialog`):
![Activity All Popup](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/activity_all_popup.png)

### C. Candidate Profile Restoration & Test Profile Isolation ([`test_onboarding_and_ai.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/tests/test_onboarding_and_ai.py))
- **Restoration**: Restored the candidate profile in SQLite `jobpilot.db` and `config/profile.json` back to **Mohd Ahmad Raza Ansari** (`candidate@example.com`, `+1 555-0199`, RPA & AI Automation Engineer).
- **Test Isolation**: Updated `test_apply_onboarding_data_succeeds` with a `try...finally` snapshot/restore block so automated unit tests can run without ever overwriting the real candidate profile.

---

## 11. Real-Time Profile Persistence & Spacious Bio / Cover Letter

### A. Real-Time Profile Data Persistence ([`profile_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/profile_view.py))
- **Live Persistence & UI Refresh**: Fixed the issue where editing or blanking URLs (e.g. GitHub, Website) would revert when closing and reopening the app. Added `_update_link_widget()` helper so links and status chips refresh immediately on `load_profile()`.
- **Card-Level Quick Save**: In addition to the top-right "Save Profile" action, clicking the section-level `[Done ✓]` toggle button now automatically invokes `self._on_save_clicked()`, writing all changes to both the SQLite database (`Profile`, `ProfessionalProfile`, `User`) and `config/profile.json` in real time.

### B. Spacious Multi-line Bio & Cover Letter Editing ([`profile_view.py`](file:///home/ahmad10raza/Documents/Mastering/Apply-and-Pray/app/ui/views/profile_view.py))
- **Problem**: Multi-line fields like "Summary / Bio" and "Cover Letter Template" were constrained inside 42px row cells, clipping long text in View mode and feeling cramped during editing.
- **Solution**:
  - Enhanced `DataSheetRow` with configurable `min_height` and `max_height` properties.
  - Set `col_span=2` for Bio (min 100px, max 140px) and Cover Letter (min 240px, max 340px).
  - In View Mode, content displays with comfortable line height, subtle background, and smooth scrolling.
  - In Edit Mode, a full-sized `QTextEdit` provides an expansive, code-editor style typing area with clear font contrast.

#### Spacious Profile — View Mode:
![Spacious Profile View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/spacious_profile_view.png)

#### Spacious Profile — Edit Mode:
![Spacious Profile Edit](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/spacious_profile_edit.png)

---

## 12. Systematic UI/UX Harmonization Across All Pages

Every view in the JobPilot application was systematically audited and aligned with modern web & desktop design guidelines:
- Dark canvas (`#0F1117`), card surface (`#161B22`), elevated surface (`#1C2128`), subtle border (`#262C36`), and Safety Orange (`#FF5F15`) primary accent.
- Standardized 44px table row height, clean uppercase headers with removed `letter-spacing` (preventing font clipping on Linux).
- Explicit `alternate-background-color: {COLORS['surface_alt']};` across all `QTableWidget` stylesheets to eliminate Qt's default white alternating rows.
- Elimination of redundant nested frames and box-in-box styling.
- Fixed Qt mnemonic accelerator character leaks (`&&` for literal `&`).

### Visual Gallery of All Harmonized Application Pages

#### 1. Dashboard View
Unified KPI metrics, responsive platform distribution charts, and streamlined recent activity feed with single-click modal inspections.
![Dashboard View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/dashboard_view.png)

#### 2. Applications View
Top KPI metric cards, fixed-width non-clipping action buttons (`Update`, `Audit`), alternating row dark styling, and tab mnemonic fix (`Shortlisted && Interview`).
![Applications View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/applications_view.png)

#### 3. Jobs View
Streamlined 6-column layout (Job Title stretch, Company 130px, Platform 85px, Location 110px, Experience 95px, Status 120px) with responsive right-hand detail drawer. Selecting any row automatically previews job details without redundant buttons.
![Jobs View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/jobs_view.png)

#### 4. Interviews View
Added top KPI metric cards (`Scheduled Rounds`, `Completed Rounds`, `Cancelled / Rescheduled`), 44px table row height, alternating row palette, and non-clipping action buttons.
![Interviews View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/interviews_view.png)

#### 5. Follow-ups View
Modernized 3 top KPI cards (`Pending Follow-ups`, `Due Today`, `Completed`), simplified Recruiter column, and dark alternating row styling.
![Follow-ups View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/followups_view.png)

#### 6. Resumes View
Multi-variant resume registry with standardized table rows, integrity badge styling, and action triggers.
![Resumes View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/resumes_view.png)

#### 7. Q&A View
Modernized 12px rounded cards, dark alternating row table styling, comfortable input padding, and uppercase section headers.
![QnA View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/qna_view.png)

#### 8. Platforms View
Direct integration cards for LinkedIn and Naukri with real-time connection status indicators and credential management.
![Platforms View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/platforms_view.png)

#### 9. Search View
Search query preferences and skip filters with cleaned groupbox headers and standardized form fields.
![Search View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/search_view.png)

#### 10. Analytics View
Standalone KPI cards for Conversion Funnel metrics and a full Platform Performance breakdown table with dark alternating rows.
![Analytics View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/analytics_view.png)

#### 11. Settings View
Clean tab bar navigation with fixed mnemonic strings (`AI && Screening`, `Credentials && Security`, `Backup && Restore`), provider-adaptive placeholders, and direct wizard launch.
![Settings View](/home/ahmad10raza/.gemini/antigravity/brain/e6aaac13-3c50-4889-8fb8-3d7f1d17740d/settings_view.png)

---

## 13. Verification and Test Results

### A. Full Automated Test Suite Execution
Executed Python 3.11 test discovery across all unit, service, UI, and integration test modules:
```bash
.venv/bin/python -m unittest discover -s tests
```
**Result**:
- **Ran 378 tests in 134.184s**
- **Status: OK (100% Passing, 0 Failures, 0 Errors)**

### B. Pre-flight Desktop Smoke Test
```bash
.venv/bin/python run_desktop.py --offscreen --test-run
```
**Result**:
- **13 UI Views initialized and validated**
- **Exit Code: 0**



