# JobPilot — Private Beta Release Gate Checklist

Use this pre-flight gate before cutting and distributing a release build (`v0.1.0-beta.1`) to private beta users.

---

## 1. Test Suite & Static Verification
- [ ] Automated test suite discovery passes (`.venv/bin/python -m unittest discover -s tests`)
- [ ] Headless GUI self-test passes (`.venv/bin/python run_desktop.py --offscreen --test-run`)
- [ ] Syntax compilation clean across all modules (`.venv/bin/python -m py_compile runAiBot.py app.py config/*.py modules/*.py platforms/*.py tests/*.py`)
- [ ] No critical open bugs in issue tracker or backlog
- [ ] No high or critical security vulnerabilities detected

---

## 2. Packaging & Binaries
- [ ] Windows distribution build created via `scripts/build_windows.bat`
- [ ] Ubuntu distribution tarball created via `scripts/build_linux.sh`
- [ ] Linux launcher installer script verified (`scripts/install_linux.sh`)
- [ ] Official brand icon present in executable, window titlebar, and system tray (`jobpilot.ico`, `jobpilot.png`)
- [ ] PyInstaller spec (`JobPilot.spec`) includes all hidden imports and asset paths

---

## 3. User Experience & Critical Workflows
- [ ] Fresh installation launches into First-Run Setup Wizard
- [ ] Setup Wizard dependency order verified: AI Setup → Resume Import → Profile Review → Q&A Review → Platform Setup → Readiness
- [ ] AI provider connection tests successfully (Ollama or cloud endpoint)
- [ ] Resume parsing functions asynchronously off-thread without freezing UI
- [ ] Candidate Profile Facts persist edits without silent data corruption
- [ ] Q&A Bank loads 300+ canonical questions and reflects custom edits
- [ ] Platform configurations load correctly; Naukri shows Freshness days rather than invalid Easy Apply toggle
- [ ] Cross-platform deduplication distinguishes listing vs logical opportunity and marks existing submissions as `ALREADY_APPLIED`
- [ ] Job discovery and evaluation score calculation function without error
- [ ] Application tracking correctly displays status transitions and prevents phantom `SUBMITTED` states

---

## 4. Automation & Process Lifecycle
- [ ] Automation engines (LinkedIn, Naukri, Indeed, Glassdoor, Foundit, Universal ATS) launch in visible browser
- [ ] Manual intervention cleanly triggers on OTP, CAPTCHA, or unknown questions
- [ ] Resume/Pause operations respond promptly to user inputs
- [ ] Browser and worker processes cleanly terminate on automation stop and application exit (0 orphan processes)
- [ ] Database transactions are short-lived; WAL mode enabled (`PRAGMA journal_mode = WAL`)

---

## 5. Security & Secret Hygiene
- [ ] Credentials encrypted via `SecretsService` (AES-128 Fernet) in OS-isolated directories
- [ ] Plaintext passwords, tokens, cookies, and secret keys absent from source code
- [ ] Diagnostic report export tested and verified free of secrets via `LogSanitizer`
- [ ] No debug credentials or test cookies committed to production settings
- [ ] No hardcoded development paths in production runtime configuration

---

## 6. Versioning & Documentation
- [ ] Single authoritative version `0.1.0-beta.1` verified in `app/version.py`, `AboutDialog`, and `SettingsView`
- [ ] `CHANGELOG.md` updated with release notes
- [ ] `docs/PRIVATE_BETA_NOTES.md` prepared with system requirements and support contact info
- [ ] `docs/BETA_BACKLOG.md` updated with all deferred post-beta suggestions
- [ ] `AGENTS.md` verified with permanent Feature Freeze rules (§10)
