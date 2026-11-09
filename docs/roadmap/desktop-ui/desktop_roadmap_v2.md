# JobPilot — Desktop UI Roadmap v2 (Consolidated)

## Revision History

| Version | Date | Notes |
|---|---|---|
| v1 | Original | 42 granular phases |
| **v2** | 21 Sep 2026 | Consolidated to 15 phases (8 done + 7 remaining), 7 deferred |

---

## Architecture (Unchanged)

```text
                         ┌─────────────────────┐
                         │    PySide6 Desktop   │
                         │         UI           │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   Service Layer      │
                         └──────────┬───────────┘
                                    │
             ┌──────────────────────┼──────────────────────┐
             │                      │                      │
             ▼                      ▼                      ▼
      Profile Service       Automation Service      Tracking Service
             │                      │                      │
             │             ┌────────┼────────┐             │
             │             ▼        ▼        ▼             │
             │         LinkedIn   Naukri   Indeed           │
             │                                              │
             └──────────────────┬───────────────────────────┘
                                ▼
                        ┌─────────────────┐
                        │    Database      │
                        │ SQLite/Postgres  │
                        └─────────────────┘
```

**Critical rule:** Do not rewrite existing LinkedIn or Naukri automation. Build around them.

---

## Completed Phases (1–8) ✅

| Phase | Original Phases | Deliverable | Tests |
|---|---|---|---|
| 1 | 0 | Project audit, architecture documentation | — |
| 2 | 1 | PySide6 desktop app, sidebar, theme, 13 nav views | 203 |
| 3 | 2–3 + 6 | SQLAlchemy DB: 15 models, 12 repositories, session mgmt | 203 |
| 4 | 4 | Resume service & UI (upload, SHA-256 dedup, set-default) | 214 |
| 5 | 5 | Config → DB migration engine (profile.json, questions.py, CSV) | 223 |
| 6 | — | (Absorbed into Phase 3) | — |
| 7 | 7 | Profile management UI (4 form cards, readiness scoring) | 230 |
| 8 | 8 | Q&A knowledge base UI (CRUD, matcher tester, profile tab) | 247 |

**Current state:** 247 passing tests. 3 functional views + 10 placeholder views.

### Pre-Built Infrastructure (from Phase 3)

Models, repositories, and DTOs already exist for ALL major entities:

| Component | Model File | Repository File |
|---|---|---|
| Platform config | `app/db/models/platform.py` | `app/repositories/platform_repository.py` |
| Jobs | `app/db/models/job.py` | `app/repositories/job_repository.py` |
| Job evaluations | `app/db/models/job_evaluation.py` | `app/repositories/job_evaluation_repo.py` |
| Applications | `app/db/models/application.py` | `app/repositories/application_repository.py` |
| Status history | `app/db/models/status_history.py` | (in application_repository) |
| Interviews | `app/db/models/interview.py` | `app/repositories/recruitment_repository.py` |
| Communications | `app/db/models/communication.py` | `app/repositories/recruitment_repository.py` |
| Follow-ups | `app/db/models/follow_up.py` | `app/repositories/recruitment_repository.py` |
| Contacts | `app/db/models/contact.py` | `app/repositories/contact_repository.py` |
| Companies | `app/db/models/company.py` | `app/repositories/company_repository.py` |
| Settings | `app/db/models/setting.py` | `app/repositories/settings_repository.py` |
| Offers | `app/db/models/offer.py` | `app/repositories/recruitment_repository.py` |

This means remaining phases focus on **service + UI** work, not schema design.

---

## Phase 9 — Platform Management & Search Config

**Merges original:** Phases 9 + 10 + parts of 29

### Goal
Build platform status cards, per-platform search configuration, and application-wide settings editor.

### Deliverables

1. **`PlatformService`** — CRUD for platform config (LinkedIn, Naukri, Indeed, Glassdoor), enable/disable toggle, search parameters per platform, last-run stats
2. **`SettingsService`** — application-wide settings (bot speed, stealth, delays, logging, max applications)
3. **`PlatformsView`** — platform status cards: enabled state, last run date, application count, "Configure" per platform
4. **`SearchView`** — search configuration editor: keywords, location, experience level, remote/hybrid/onsite, date posted, per-platform
5. **`SettingsView`** — grouped settings editor: General, Browser, Automation, Logging, AI/QnA

### Uses existing
`Platform` model, `platform_repository.py`, `Setting` model, `settings_repository.py`

### Size: Medium (3 services, 3 views)

---

## Phase 10 — Jobs & Applications Core

**Merges original:** Phases 13 + 14 + 15 + 16 + 32 + 34

### Goal
Build the central job database viewer and full application lifecycle tracker.

### Deliverables

1. **`JobService`** — job listing with multi-filter (platform, company, title, location, salary, date), pagination, deduplication, manual job entry
2. **`ApplicationService`** — full lifecycle tracking (DISCOVERED → QUALIFIED → APPLYING → SUBMITTED → UNDER_REVIEW → SHORTLISTED → INTERVIEW → OFFER/REJECTED/WITHDRAWN), status transitions with history logging
3. **`JobsView`** — searchable/filterable job table, detail panel, "Open URL", "Mark Interested", "Add Note", manual "Add Job"
4. **`ApplicationsView`** — application table with status badges, category filters, timeline, status transition buttons
5. CSV history import into new schema (extend existing migration engine)

### Uses existing
`Job`, `Application`, `StatusHistory`, `JobEvaluation` models; `job_repository.py`, `application_repository.py`, `job_evaluation_repo.py`

### Size: Large

---

## Phase 11 — Recruitment Pipeline

**Merges original:** Phases 17 + 18 + 19 + 20 + 24 + 35

### Goal
Build interview scheduling, communication logging, follow-up tracking, and contact management.

### Deliverables

1. **`RecruitmentService`** — interview CRUD (rounds, scheduling, status), communication logging (email, call, message), follow-up due tracking, contact management
2. **`InterviewsView`** — interview list with round types (HR, Technical, Coding, Final), status tracking, meeting links, notes
3. **`FollowupsView`** — follow-up due dates, status tracking (DUE/SENT/WAITING/NO_RESPONSE), linked to applications
4. Contact management embedded in interviews/communications (recruiter name, email, phone, company)

### Uses existing
`Interview`, `Communication`, `FollowUp`, `Contact`, `Offer` models; `recruitment_repository.py`, `contact_repository.py`

### Size: Medium-Large

---

## Phase 12 — Dashboard & Analytics

**Merges original:** Phases 21 + 22

### Goal
Build the main dashboard with live stats and the analytics metrics page.

### Deliverables

1. **`DashboardService`** — aggregation: total jobs/applications/interviews/offers, per-platform breakdown, current pipeline counts, recent activity feed
2. **`AnalyticsService`** — application rate, response rate, interview rate, offer rate, platform comparison, time-to-response analysis
3. **`DashboardView`** — stat cards, pipeline summary bar, recent activity timeline
4. **`AnalyticsView`** — metrics tables, rate calculations, platform comparison

### Uses existing
All job/application/interview models already in DB

### Size: Medium
### Depends on: Phase 10 (needs job/application data to be meaningful)

---

## Phase 13 — Automation Engine Integration

**Merges original:** Phases 11 + 12 + 26 + 27 + 33

### Goal
Wire existing LinkedIn/Naukri automation into the desktop app with background workers and live console.

### Deliverables

1. **`AutomationManager`** — `run(platform)`, `stop(platform)`, `pause(platform)`, `get_status(platform)` wrapping existing engines
2. **`AutomationWorker` (QThread)** — runs Selenium off UI thread, emits Qt signals: `job_found`, `application_submitted`, `error`, `login_required`, `captcha_detected`
3. Wire `runAiBot.py` / `platforms/` to write jobs + applications to DB in real time
4. **`AutomationView`** — start/stop controls, live status display, current keyword/page, counters
5. **`LogsView`** — real-time log console with level filter, copy, export

### Uses existing
All `platforms/` automation code (LinkedIn + Naukri), `runAiBot.py` entry points

### Size: Large
### Risk: Highest — bridges existing automation with new desktop UI. Rule: wrap, don't rewrite.

---

## Phase 14 — Settings, Security & Backup

**Merges original:** Phases 29 + 30 + 31

### Goal
Complete settings management, add secrets protection, and build backup/restore.

### Deliverables

1. Complete `SettingsView` with all sections (General, Browser, Automation, Logging, AI/QnA, Appearance)
2. Secrets management — OS keyring or encrypted storage for passwords/API keys
3. Backup/Restore — SQLite export/import, profile JSON export, resume file backup
4. Log sanitization — ensure no passwords/tokens/cookies in logs

### Uses existing
`settings_repository.py`, `Setting` model

### Size: Small-Medium

---

## Phase 15 — Notifications & Smart Search

**Merges original:** Phases 25 + 36

### Goal
Desktop notifications and cross-entity global search.

### Deliverables

1. Desktop notifications — interview reminders, follow-up due, automation alerts
2. Global search — unified search across jobs, companies, applications, recruiters, interviews

### Size: Small

---

## Deferred Features (Build After Core Is Stable)

| Original Phase | Feature | Reason |
|---|---|---|
| 23 | Email integration (Gmail parsing) | Complex external integration |
| 37 | Company management (standalone entity) | Already tracked as fields on jobs; standalone is nice-to-have |
| 38 | AI Assistant (natural language queries) | Luxury; needs full data first |
| 39 | Resume/Job matching (skill scoring) | Enhancement; needs stable job DB |
| 40 | Comprehensive test suite | Already building tests per phase |
| 41 | PyInstaller packaging | Distribution only |
| 42 | Production readiness checklist | Final checklist, not a build phase |

---

## Execution Timeline

```text
DONE ──────────────────────────────────────────────────────
 Phases 1–8     Foundation, DB, Profile, Resume, Q&A         247 tests ✅

NEXT ──────────────────────────────────────────────────────
 Phase 9        Platform Management & Search Config           Medium
 Phase 10       Jobs & Applications Core                      Large
 Phase 11       Recruitment Pipeline                          Medium-Large
 Phase 12       Dashboard & Analytics                         Medium
 Phase 13       Automation Engine Integration                 Large ⚠️
 Phase 14       Settings, Security & Backup                   Small-Medium
 Phase 15       Notifications & Smart Search                  Small

DEFERRED ──────────────────────────────────────────────────
                Email, AI Assistant, Resume Matching, Packaging
```

---

## Invariants (All Phases)

1. **13 NAV_ITEMS** — navigation registry must stay at exactly 13 items
2. **Zero automation breakage** — existing LinkedIn/Naukri code is read-only until Phase 13
3. **Architecture:** `UI → Service → Repository → SQLAlchemy → Database`
4. **Testing:** every phase adds tests, full regression must pass before proceeding
5. **No secrets in code/logs** — passwords, tokens, cookies, API keys never committed or logged
