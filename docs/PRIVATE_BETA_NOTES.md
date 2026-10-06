# JobPilot — Private Beta Notes (`v0.1.0-beta.1`)

Welcome to the **JobPilot Private Beta**.

JobPilot is an autonomous desktop application for job discovery, multi-platform application management, candidate profile intelligence, and outreach tracking.

This private beta is designed for **4–5 active users** under controlled evaluation conditions.

---

## 1. Supported Operating Systems

| Operating System | Support Status | Notes |
| :--- | :--- | :--- |
| **Windows 10 / 11 (x64)** | **Fully Supported** | Tested on desktop display scalings (100%, 125%, 150%). Chrome browser required. |
| **Ubuntu / Debian Linux (x64)** | **Fully Supported** | Tested on Ubuntu 22.04 LTS and 24.04 LTS (X11 and Wayland). Google Chrome or Chromium required. |
| **macOS** | *Deferred* | Architecturally compatible; official packaging deferred to post-beta release. |
| **Android / iOS** | *Not Targeted* | Desktop-only application. |

---

## 2. Supported Platforms & Automation Capabilities

| Platform | Discovery Mode | Application Automation | Notes |
| :--- | :--- | :--- | :--- |
| **LinkedIn** | Live Search & Feed | Easy Apply Automation | Filters on `f_AL=true` when Easy Apply is selected. Manual intervention on phone/OTP verification. |
| **Naukri** | Portal Search & Feeds | In-App Direct Apply | Configured via Search Freshness cycles (Past 1, 3, 7, 15, 30 days). External listings tracked in ledger. |
| **Indeed** | Search & Discovery | Easily Apply Mode | Automated navigation through multi-step qualification questions. |
| **Foundit** | Portal Discovery | Quick Apply Flow | Automated submission on supported Quick Apply listings. |
| **Glassdoor** | Discovery & Ledger | Easy Apply Flow | Supported with human checkpoint handoff on security challenges. |
| **Universal ATS Agent** | Portal Ingestion | Multi-Page Form Automation | Supported on Workday, Greenhouse, and Lever archetypes. |

---

## 3. Important Beta Principles

1. **Anti-Evasion & Security Policy**:
   - JobPilot **never** attempts automated CAPTCHA bypass or fingerprint spoofing.
   - When a platform issues an OTP, puzzle, or Cloudflare challenge, JobPilot pauses execution and requests manual intervention. You complete the check in the browser window, then click Resume.
2. **Safe Deduplication**:
   - JobPilot distinguishes between *raw listings* and *logical applications*.
   - A listing discovered on Naukri that represents an opportunity you already applied to on LinkedIn will be marked as `ALREADY_APPLIED` and blocked from duplicate submission according to policy.
3. **Database Integrity**:
   - All state is stored in a local SQLite database running in Write-Ahead Log (WAL) mode.
   - Credentials and API keys are AES-128 encrypted via `SecretsService` and stored in isolated OS directories.

---

## 4. Known Limitations & Issues

- **Headless Mode**: Automation runs visibly in standard browser windows to allow human verification of critical application steps. Headless background automation is intentionally disabled for anti-bot compliance.
- **Provider Rate Limits**: When using cloud AI providers (OpenAI, Groq, Gemini), ensure your account has adequate rate limits. For offline use, local Ollama is fully supported.
- **High-DPI Multi-Monitor Setups**: When dragging windows across monitors with different DPI factors (e.g., 4K 150% to 1080p 100%), some minor Qt font readjustment may occur until the window is resized.

---

## 5. Backup & Upgrade Recommendations

> [!IMPORTANT]
> Always take a database backup before performing application updates or running extensive automated batches.

- Go to **Settings → Backup & Recovery**.
- Click **"Create Database Backup"**.
- Backups are stored in `~/.jobpilot/backups/` (Linux) or `%APPDATA%\JobPilot\backups\` (Windows) and can be restored with one click.

---

## 6. How to Report Bugs & Provide Feedback

If you encounter an unexpected error, freeze, or broken workflow:

1. Open **Settings → General Preferences** (or click **About JobPilot**).
2. Click **"📋 Export Diagnostic Report"**.
3. Choose a destination file (e.g., `jobpilot_diagnostics.md`).
4. Share the generated report along with:
   - What you were doing immediately before the issue occurred.
   - What platform or page was active.
   - Any screenshots of the application or browser window.

> [!NOTE]
> All diagnostic reports are automatically scrubbed by `LogSanitizer`. No API keys, passwords, cookies, or session tokens are contained in exported diagnostic files.
