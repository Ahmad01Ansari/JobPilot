# JobPilot — Threat Model & Security Architecture

**Document Version:** 1.0.0  
**Target:** Local-First Desktop Automation & Application Platform

---

## 1. High-Value Assets

JobPilot manages high-value assets across its application lifecycle:

1. **Candidate Authentication Credentials:**
   - LinkedIn, Naukri, Indeed, Foundit, and Glassdoor session passwords and usernames.
   - Platform session cookies (`li_at`, `JSESSIONID`, `remember_token`).
2. **AI Provider Secrets:**
   - API keys for OpenAI, Google Gemini, Groq, NVIDIA NIM, DeepSeek, and custom OpenAI-compatible endpoints.
3. **Outreach & Communication Credentials:**
   - SMTP and IMAP passwords, Gmail App Passwords, custom mail server endpoints.
4. **Candidate Personally Identifiable Information (PII):**
   - Full legal name, email, phone numbers, home address, city, postal code.
   - Current and expected compensation (CTC), notice period.
   - Professional resumes (PDF and DOCX formats) stored in managed directories.
5. **Screening Knowledge Base & History:**
   - Pre-configured screening Q&A answers, customized work history, job search criteria.
   - Application submissions log and tracking database (`jobpilot.db`).
6. **Local Encryption Keys:**
   - Fernet master key (`~/.jobpilot/.key`) protecting the SQLite encrypted secrets store.

---

## 2. Trust Boundaries & Data Flow

### Boundary 1: User & Desktop GUI (Trusted Input)
```
[ User Action / Form Input ]
             ↓ (PySide6 Event Loop)
[ UI Layer: app/ui/views/ ]
             ↓ (Strict Layer Isolation)
[ Service Layer: app/services/ ]
```
- **Rule:** UI components never directly read raw secrets or query databases directly.
- **Masking:** Secrets rendered in the UI must display as masked bullets (`••••••••`).

### Boundary 2: Service Layer & Database (Encrypted Persistence)
```
[ Service Layer ]
  ↓ (SecretsService / AES-128-CBC + HMAC-SHA256)
[ SQLite Database: app_settings ]
```
- **Rule:** All credentials (platform passwords, AI keys, SMTP passwords) are stored encrypted. Cleartext passwords must never be persisted in SQLite tables or configuration JSON files.

### Boundary 3: Browser Automation & Untrusted External Web Content
```
[ Browser Automation Engine ]
        ↓
[ External Job Portals / ATS Forms / Recruiter Sites ]
        ↓ (UNTRUSTED DATA)
[ Page DOM / Form Questions / Job Descriptions ]
```
- **Rule:** External webpage content is strictly **PASSIVE DATA**, never trusted instructions.
- **URL Security:** Navigation must pass through `URLSecurityValidator` (`app/services/security/url_validator.py`). Dangerous schemes (`file:`, `javascript:`, `data:`) and cloud metadata endpoints (`169.254.169.254`) are blocked.
- **CAPTCHA & Auth Gates:** If a CAPTCHA or multi-factor prompt is detected, automation halts safely and yields control to the human user via `MANUAL_REQUIRED`. Evasion or bypass is strictly forbidden.

### Boundary 4: AI Gateway & External Model Providers
```
[ Untrusted Web Content ]
        ↓
[ PromptSecurityGuard: <untrusted_content> tags ]
        ↓
[ AIGateway: Protocol Adapters ]
        ↓ (HTTPS with TLS Verification)
[ External AI Providers / Local Ollama ]
```
- **Data Classification:**
  - `SECRET`: **NEVER** sent to any LLM prompt.
  - `SENSITIVE_CANDIDATE_DATA`: Only sent to verified providers when explicitly required for resume parsing or application question answering.
  - `JOB_DATA`: Extracted and analyzed as passive input.
- **SSRF Isolation:** Localhost endpoints (`http://localhost:11434`) are permitted only for local AI providers configured by the user, while loopback access is blocked for browser navigation.

---

## 3. Defensive Security Controls

| Domain | Control Mechanism | Location |
| :--- | :--- | :--- |
| **Secrets Management** | Fernet authenticated encryption with `0o700` directory and `0o600` file permissions. | `app/services/secrets_service.py` |
| **Filesystem & Backups** | Zip Slip path traversal rejection, symlink blocking, and archive size limits. | `app/services/backup_service.py` |
| **URL Navigation** | Strict scheme checking (`http`/`https`), cloud metadata blocking, SSRF loopback isolation. | `app/services/security/url_validator.py` |
| **Observability** | Pre-persistence log redacting regex filter scrubbing API keys, tokens, cookies, passwords. | `app/services/sanitizer_service.py` |
| **Prompt Injection** | Untrusted content encapsulation tags `<untrusted_content>` and breakout neutralization. | `app/services/ai/prompt_guard.py` |
| **Email Outreach** | CRLF header injection stripping and strict TLS context verification. | `app/services/email/smtp_imap_provider.py` |
| **VCS Cleanliness** | Comprehensive `.gitignore` excluding SQLite databases, CSV dumps, and resumes. | `.gitignore` |

---

## 4. Human-in-the-Loop Security Invariants

JobPilot prioritizes user control and safety above autonomous execution:

1. **Safety Gate Review:** The application supports `pause_before_submit` mode, allowing the user to review filled form fields and CTC parameters before any application is dispatched.
2. **Consequential Action Confirmation:** Critical actions such as restoring a backup, deleting resumes, resetting credentials, or dispatching email outreach require explicit user confirmation.
3. **Fail-Closed Design:** In the event of network disruption, parsing failure, or unknown form fields, the bot defaults to `MANUAL_REQUIRED` rather than guessing or fabricating answers.

---

## 5. Incident Response & Recovery Guidance

If credentials or keys are suspected to have been compromised:
1. **Rotate Secrets:** Navigate to `Settings -> Credentials` and update the relevant platform and AI API keys immediately.
2. **Rotate Fernet Key:** Delete `~/.jobpilot/.key` and restart JobPilot to generate a fresh encryption key, then re-enter credentials in Settings.
3. **Inspect Logs:** Review `logs/log.txt` to confirm no plain credentials were leaked (all lines are processed via `LogSanitizer`).
4. **Database Rollback:** If database corruption occurs, utilize the pre-restore backup created automatically at `jobpilot.db.pre_restore.bak`.
