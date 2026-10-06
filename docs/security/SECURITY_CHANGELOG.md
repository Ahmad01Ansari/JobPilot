# JobPilot — Security Changelog

All notable security enhancements, vulnerability fixes, and hardening measures are recorded in this file.

---

## [Security Release 1.1.0] — October 2026

### Critical Fixes
- **SEC-001 (Zip Slip Path Traversal Protection):**
  - **Component:** `app/services/backup_service.py`
  - **Issue:** `zipfile.ZipFile.extractall()` allowed relative path components (`../../`) within malicious archive entries to escape the staging isolation directory and overwrite arbitrary host files.
  - **Fix:** Implemented `_safe_extract()` verifying that every member resolves strictly within the target extraction root via `is_relative_to()`. Added checks disallowing symlinks, absolute paths, and compression bombs (100MB max per file, 500MB max total).
  - **Tests:** `tests/test_security_hardening.py:test_backup_zip_slip_rejection`, `test_backup_symlink_rejection`.

### High Severity Fixes
- **SEC-002 (Credential Redaction & Observability Protection):**
  - **Components:** `modules/helpers.py`, `app/services/sanitizer_service.py`, `run_desktop.py`, `runAiBot.py`
  - **Issue:** `print_lg()` wrote unredacted strings directly to `logs/log.txt`. Root Python loggers lacked an automatic sanitizing filter.
  - **Fix:** Filtered all strings through `LogSanitizer.sanitize_text()` inside `print_lg()` before disk persistence or listener notification. Expanded patterns to cover OpenAI, Groq, NVIDIA, Gemini, GitHub tokens, AWS keys, JWTs, and database URLs. Attached `SanitizingLogFilter` to root logging handlers at startup.
  - **Tests:** `tests/test_security_hardening.py:test_log_sanitizer_api_keys`, `test_print_lg_sanitizes_before_disk`.

- **SEC-003 & SEC-008 (SSRF Prevention & Centralized URL Validation):**
  - **Components:** `app/services/security/url_validator.py`, `StagehandAgent`, platform browser adapters
  - **Issue:** Web automation navigated blindly to URLs obtained from job listings without validating schemes or IP destinations.
  - **Fix:** Created `URLSecurityValidator` with classification tiers (`EXPECTED_PLATFORM`, `LOCAL_AI`, `ALLOWED_EXTERNAL`, `BLOCKED`). Restricts schemes to `http`/`https`, blocks cloud metadata IPs (`169.254.169.254`, `metadata.google.internal`), and blocks loopback access for external web navigation.
  - **Tests:** `tests/test_security_hardening.py:test_url_validator_prohibited_schemes`, `test_url_validator_cloud_metadata_blocked`, `test_url_validator_loopback_isolation`.

- **SEC-004 (VCS Secret & PII Hygiene):**
  - **Component:** `.gitignore`
  - **Issue:** SQLite databases (`jobpilot.db`, `app.db`), CSV exports with candidate application histories, and temporary debug directories were not ignored.
  - **Fix:** Hardened `.gitignore` to explicitly ignore all `*.db`, `*.sqlite*`, `*.csv`, `managed_resumes/`, `scratch/`, `debug/`, and `.key` files.

### Medium & Low Severity Hardening
- **SEC-005 (Prompt Injection Encapsulation):**
  - **Component:** `app/services/ai/prompt_guard.py`
  - **Issue:** External web content passed to LLMs was vulnerable to indirect prompt injection.
  - **Fix:** Implemented `PromptSecurityGuard` providing `<untrusted_content is_external_data="true">` boundary tags, closing tag breakout neutralization, and standard system directives.
  - **Tests:** `tests/test_security_hardening.py:test_prompt_guard_encapsulation`, `test_prompt_guard_system_directive`.

- **SEC-007 (Encryption Key Permissions):**
  - **Component:** `app/services/secrets_service.py`
  - **Issue:** The `~/.jobpilot/` directory lacked explicit POSIX `0o700` permissions.
  - **Fix:** Enforced `0o700` permissions on key directory and `0o600` on key file.
  - **Tests:** `tests/test_security_hardening.py:test_secrets_service_directory_permissions`.

- **SEC-009 (Email Header Injection Prevention & TLS Verification):**
  - **Component:** `app/services/email/smtp_imap_provider.py`
  - **Issue:** Header fields were not stripped of CRLF characters; implicit SSLContext was used.
  - **Fix:** Implemented `_sanitize_header()` to strip CRLF characters from subject, to, from, and cc fields. Configured explicit `ssl.create_default_context()` for all SMTP/TLS connections.
  - **Tests:** `tests/test_security_hardening.py:test_email_header_injection_stripping`.

- **SEC-010 (Dependency Declaration):**
  - **Component:** `requirements.txt`
  - **Fix:** Declared `cryptography>=42.0.0` explicitly in project requirements.
