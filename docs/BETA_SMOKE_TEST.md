# JobPilot — 19-Step Beta Smoke Test Protocol

This checklist must be executed before distributing any build (`v0.1.0-beta.1`) to private beta users on Windows or Linux.

---

## Pre-Flight Environment
- **Target OS**: Windows 10/11 or Ubuntu 22.04/24.04 LTS
- **Python**: 3.11.x virtual environment (`.venv`)
- **Browser**: Google Chrome / Chromium installed

---

## Verification Matrix

| Step | Action | Expected Behavior | Status |
| :---: | :--- | :--- | :---: |
| **1** | **Clean Installation** | Run `scripts/build_linux.sh` or `scripts/build_windows.bat`. Install launcher via `scripts/install_linux.sh`. | [ ] PASS |
| **2** | **First Launch** | Execute `run_desktop.py`. Desktop UI shell loads with 13 sidebar navigation items; no tracebacks in console. | [ ] PASS |
| **3** | **Setup Wizard** | If fresh install, Onboarding Wizard opens automatically. Progress indicator steps match dependency order. | [ ] PASS |
| **4** | **AI Connection** | Configure AI Provider (Ollama or cloud endpoint). Click "Test Connection"; returns success message. | [ ] PASS |
| **5** | **Resume Import** | Import a PDF or DOCX resume. Off-thread parsing parses contact, skills, and work experience. | [ ] PASS |
| **6** | **Profile Review** | Review Profile Facts in Profile view. Edit a field, click "Save Changes"; updates persist immediately. | [ ] PASS |
| **7** | **Q&A Knowledge Base** | Open Q&A view. Verify 300+ canonical questions load; edit a rule answer; verify provenance badge is displayed. | [ ] PASS |
| **8** | **Platform Configuration** | Open Platforms view. Configure search terms and freshness days for LinkedIn and Naukri. Ensure no invalid Easy Apply flags exist on Naukri. | [ ] PASS |
| **9** | **Job Discovery** | Trigger job discovery from Dashboard or Platforms view. Discovered jobs populate Jobs view with accurate titles and company names. | [ ] PASS |
| **10** | **Job Deduplication** | Ingest duplicate listing for the same opportunity across portals. Deduplication engine flags opportunity as `SAME_OPPORTUNITY` or `DUPLICATE_LISTING` with explainable reason. | [ ] PASS |
| **11** | **Job Qualification / Evaluation** | Trigger evaluation on discovered job. Match score and qualification reasoning compute without errors. | [ ] PASS |
| **12** | **Application Creation** | Create an application record for a qualified job. Record status initializes to `READY_TO_APPLY` or `DISCOVERED`. | [ ] PASS |
| **13** | **Automation & Manual Checkpoint** | Start an automation run. Browser window launches. If a verification challenge or unknown field occurs, automation triggers `MANUAL_REQUIRED` with audible/visual alert and pauses. Clicking "Resume" continues execution. | [ ] PASS |
| **14** | **Application Tracking** | Open Applications view. Verify card displays correct status (`APPLIED` / `MANUAL_REQUIRED`), applied timestamp, and platform tag. | [ ] PASS |
| **15** | **Global Search & Filter** | In Jobs and Applications views, search by keyword, company, and platform filter. Matching rows filter instantly. | [ ] PASS |
| **16** | **Analytics & Dashboard** | Open Analytics view. Funnel metrics, platform distribution, and response rate graphs render without errors. | [ ] PASS |
| **17** | **Database Backup** | Open Settings → Backup & Recovery. Click "Create Database Backup". Verify `.db` archive appears in backup list with valid size and timestamp. | [ ] PASS |
| **18** | **Application Restart** | Close JobPilot and relaunch. Verify all candidate profile data, Q&A entries, application statuses, and configurations remain intact. | [ ] PASS |
| **19** | **Graceful Teardown** | Close application during idle and active states. Browser instances terminate, worker threads exit gracefully, and SQLite database locks release without orphans. | [ ] PASS |

---

## Diagnostic Check
After running the smoke test, navigate to **Settings → General Preferences** and click **"📋 Export Diagnostics"**. Inspect the resulting markdown file to ensure:
1. Version is `0.1.0-beta.1`
2. No plain passwords, tokens, or cookies appear in `recent_diagnostic_logs`
3. Table row counts reflect completed smoke operations
