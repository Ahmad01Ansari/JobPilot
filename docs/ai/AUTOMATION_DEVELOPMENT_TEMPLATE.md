# Automation Development Template — JobPilot
*Copy and fill out this document when developing or updating any platform automation engine.*
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §8, §9 & [Browser Rules](BROWSER_AUTOMATION_RULES.md)*

---

# Automation Engine: [Platform Name (e.g. Glassdoor / Indeed / ATS)]

## 1. Automation Workflow & Execution Cycle
Every automation engine must execute through this 8-stage cycle:

```
[1. DISCOVER] ──► Find job cards, application buttons, or modal entry points
      │
[2. OBSERVE]  ──► Wait for DOM stability; verify URL, handle, and container presence
      │
[3. CLASSIFY] ──► Categorize widget types (text input, radio, dropdown, file upload)
      │
[4. EXTRACT]  ──► Parse question text, constraints (required, max length), and options
      │
[5. VALIDATE] ──► Resolve candidate answers against Profile/Resume/QnA with provenance
      │
[6. ACT]      ──► Scroll into view, apply safe human click / keystrokes with delay
      │
[7. VERIFY]   ──► Confirm DOM mutation, next-step transition, or submit confirmation
      │
[8. RECOVER]  ──► On failure/timeout: retry, dump audit artifacts, or route to MANUAL_REQUIRED
```

---

## 2. Browser & Profile Lifecycle
- **Persistent Profile Directory:** `~/.jobpilot-[platform]-profile`
- **Lock Cleanup:** Call `modules.browser_lock.clean_stale_locks(profile_dir)` prior to browser launch.
- **Page Load Strategy:** `options.page_load_strategy = 'eager'`
- **Window Preservation Plan:**
  - Search Tab (Handle 0): Kept open continuously; never navigated away.
  - Job Processing Tab (Handle 1): Opened for each job, processed, closed, focus returned to Handle 0.

---

## 3. Explicit State Machine Mapping
| Workflow Step | ExecutionState | InterventionReason | TerminalResult (if final) |
|---|---|---|---|
| Launch Browser | `INITIALIZING` | `NONE` | - |
| Check Login | `AUTHENTICATING` | `LOGIN_WALL` (if logged out) | - |
| Search Page Load | `NAVIGATING` | `NONE` | - |
| Extracting Cards | `EXTRACTING` | `NONE` | - |
| Form Filling | `FILLING_FORM` | `UNKNOWN_QUESTION` (if missing fact) | - |
| Human Review Gate | `PAUSED_FOR_INTERVENTION` | `PENDING_HUMAN_REVIEW` | - |
| Verification Success| `FINALIZING` | `NONE` | `SUBMITTED` |
| Verification Missing| `FINALIZING` | `NONE` | `STATUS_UNKNOWN` |

---

## 4. Timeouts & Retry Policy
- **Navigation Timeout:** 30 seconds (`safe_driver_get`).
- **Element Visibility Timeout:** 5–10 seconds (`WebDriverWait`).
- **Action Retry Limit:** Maximum 2 retries for transient `StaleElementReferenceException`.
- **Session Max Applications:** 25–30 applications before mandatory cooldown to prevent platform rate-limits.

---

## 5. Overlay, Popup, & Modal Handlers
- **Known Modals:** [List known popups, e.g. "Save alert", "Experience rating"]
- **Dismissal Routine:** [How popups are detected and cleanly closed without failing]
- **Escape Fallback:** Send `Keys.ESCAPE` if backdrop overlay blocks target element.

---

## 6. CAPTCHA, 2FA, & Security Boundaries
- **Detection Selectors:** [CSS selectors or text identifying Cloudflare / reCAPTCHA]
- **Action on Detection:** Immediately transition to `PAUSED_FOR_INTERVENTION` with reason `CAPTCHA_DETECTED`.
- **Resumption Condition:** Wait for user to complete challenge manually; poll DOM until challenge container disappears.
- **Strict Prohibition:** NEVER integrate automatic bypasses or third-party CAPTCHA solvers.

---

## 7. Field Mapping & QnA Provenance
| DOM Field Pattern | Candidate Fact Source | Fallback Strategy | Provenance Tag |
|---|---|---|---|
| First/Last Name | `profile.json:personal` | Fail fast | `PROFILE_FACT` |
| Phone Number | `profile.json:personal` | Fail fast | `PROFILE_FACT` |
| Years of Experience | `ResumeService` / `QnAService` | Compute from work history | `RESUME_FACT` |
| Visa / Work Auth | `config/questions.py` | Prompt user | `QNA_RULE` |
| Unknown screening | LLM (Tier 3) | `PAUSED_FOR_INTERVENTION` | `USER_MANUAL_INPUT` |

---

## 8. Result Verification & Audit Dumps
- **Verification Selector:** [DOM selector or text indicating successful submission]
- **Handling Ambiguity:** If submit button clicked but confirmation not found, record `STATUS_UNKNOWN`.
- **Audit Snapshot:** Save full-page screenshot to `app/snapshots/<platform>_<job_id>_<timestamp>.png`.
- **DOM Dump:** Save outerHTML and SHA-256 hash if verification is uncertain or failed.

---

## 9. Test & Verification Plan
- **Offline / Mock Test:** Unit tests with mock DOM and fake server fixtures.
- **Offscreen GUI Integration:** Validate that worker status signals update UI elements cleanly.
- **Syntax Check:** `.venv/bin/python -m py_compile platforms/[platform]/*.py`
