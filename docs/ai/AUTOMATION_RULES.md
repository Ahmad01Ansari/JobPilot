# JobPilot — Automation Rules & Worker Lifecycle
**Specialized Guidelines for Automation Workers, State Machines, and Observability**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §8, §13, §14*

---

## 1. Automation Subsystem Philosophy

JobPilot automates complex job discovery and multi-step application submissions across multiple platforms (LinkedIn, Naukri, Indeed, Glassdoor, Foundit, and Universal ATS portals).

Automation is inherently non-deterministic due to third-party website changes, dynamic rendering, network latency, and anti-bot measures. Therefore, automation logic must be:
1. **Isolated:** Run in dedicated worker threads, completely detached from the UI event loop.
2. **Explicitly State-Driven:** Governed by formal state machines separating execution phase from intervention reasons and terminal results.
3. **Observable:** Emit structured lifecycle events and maintain comprehensive audit trails.
4. **Verifiable:** Always verify that an action succeeded before advancing to the next step.

---

## 2. Automation Architecture & Flow

```
┌────────────────────────────────────────────────────────┐
│                   PRESENTATION (UI)                    │
│   User clicks "Start Automation" or "Apply All"        │
└───────────────────────────┬────────────────────────────┘
                            │ Calls start_automation(...)
┌───────────────────────────▼────────────────────────────┐
│              AUTOMATION ORCHESTRATOR / SERVICE         │
│   Validates prerequisites, acquires browser locks,     │
│   initializes session, configures task parameters      │
└───────────────────────────┬────────────────────────────┘
                            │ Spawns QThread / TaskRunner
┌───────────────────────────▼────────────────────────────┐
│                  AUTOMATION WORKER                     │
│   Controls task execution, polls cancellation token,   │
│   dispatches events via AutomationBridge               │
└───────────────────────────┬────────────────────────────┘
                            │ Invokes Platform Engine methods
┌───────────────────────────▼────────────────────────────┐
│                  AUTOMATION ENGINE                     │
│   (LinkedIn, Naukri, Indeed, Glassdoor, Universal)     │
│   OBSERVE ──► CLASSIFY ──► ACT ──► VERIFY              │
└────────────────────────────────────────────────────────┘
```

---

## 3. Explicit State Machine Standard

Never collapse all lifecycle states into a single ambiguous status string. Separate automation state into three orthogonal enums:

### 3.1. Execution State (`AutomationState`)
Tracks what the worker is actively doing:
- `IDLE`: Worker initialized, awaiting instructions.
- `INITIALIZING`: Launching browser driver, resolving profile locks.
- `AUTHENTICATING`: Verifying active session or logging in.
- `NAVIGATING`: Navigating to job search or application URL.
- `EXTRACTING`: Parsing job cards, requirements, and metadata.
- `FILLING_FORM`: Answering questions, attaching resume, filling fields.
- `PAUSED_FOR_INTERVENTION`: Temporarily paused awaiting human resolution.
- `FINALIZING`: Capturing audit snapshot, recording database entry.
- `TERMINATED`: Automation run completed.

### 3.2. Intervention Reason (`InterventionReason`)
Specifies *why* the automation paused for human assistance:
- `NONE`: Normal automated operation.
- `PENDING_HUMAN_REVIEW`: Mandatory review gate before final submission.
- `CAPTCHA_DETECTED`: Cloudflare, reCAPTCHA, or puzzle detected.
- `LOGIN_WALL`: Session expired, manual credential entry required.
- `TWO_FACTOR_REQUIRED`: SMS / Email 2FA verification prompt.
- `UNKNOWN_QUESTION`: Screening question cannot be answered safely from candidate facts.
- `EXTERNAL_REDIRECT`: Portal requires navigating off-platform to untrusted destination.

### 3.3. Terminal Result (`TerminalResult`)
Defines the final status of a single application attempt:
- `SUBMITTED`: Verified submission confirmation detected on page.
- `ALREADY_APPLIED`: Identified as previously submitted.
- `SKIPPED_CRITERIA`: Did not meet filter criteria (salary, location, blacklist).
- `FAILED_UNRECOVERABLE`: Critical unhandled error after retry exhaustion.
- `USER_CANCELLED`: Operator manually aborted the operation.
- `STATUS_UNKNOWN`: Form submitted but confirmation message could not be verified.

---

## 4. Worker Lifecycle & Cancellation Tokens

Every automation worker must implement cooperative cancellation:

```python
class AutomationWorker(QThread):
    def __init__(self, task_config, bridge: AutomationBridge):
        super().__init__()
        self.task_config = task_config
        self.bridge = bridge
        self._is_cancelled = False

    def request_cancellation(self):
        """Thread-safe cancellation request."""
        self._is_cancelled = True

    def should_cancel(self) -> bool:
        return self._is_cancelled

    def run(self):
        try:
            self.bridge.state_changed.emit(AutomationState.INITIALIZING)
            # Check cancellation at every major phase:
            if self.should_cancel():
                self.bridge.state_changed.emit(AutomationState.TERMINATED)
                return

            self._execute_workflow()
        except Exception as exc:
            logger.exception("Automation worker encountered fatal error: %s", exc)
            self.bridge.error_occurred.emit(str(exc))
        finally:
            self._cleanup_resources()
```

---

## 5. Result Verification Standard

Never assume an action succeeded because no exception was raised.

```
FIND ELEMENT ──► CLICK ──► ASSUME SUCCESS          ❌ FORBIDDEN
OBSERVE ──► ACT ──► VERIFY DOM STATE CHANGE        ✅ MANDATORY
```

### Verification Rules:
1. **Button Clicks:** After clicking "Submit" or "Next", wait for the DOM to change:
   - Verify the current step container disappears or advances to the next step index.
   - Or verify a confirmation message (`"Application submitted"`, `"Thank you for applying"`) appears.
2. **Text Input:** After sending keys, read back `.get_attribute("value")` or `.text` to verify the text was properly inserted and not cleared by JavaScript validation.
3. **Ambiguity Handling:** If a submit button is clicked, page navigates, but no explicit confirmation text is found:
   - **Never report `SUBMITTED`**.
   - Record status as `STATUS_UNKNOWN` and save an audit screenshot for manual inspection.

---

## 6. Observability & Structured Logging

Logs must be human-readable and structured. Avoid vague messages like `Error in loop`.

### The 4-W Logging Rule:
Every log message must answer:
1. **WHAT:** The operation being performed (`[LinkedInApplier] Answering screening question: 'Years of Python experience'`).
2. **WHERE:** URL, DOM selector, or page step (`Step 3 of 4: Compensation`).
3. **WHY:** Decision rationale (`Resolved value '5' using PROFILE_FACT:skills.python.years`).
4. **NEXT:** Next planned action (`Proceeding to Next button click`).

---

## 7. Audit Artifacts & Forensic Dumps

When an unrecoverable error occurs or when an application finishes:
1. **Audit Screenshot:** Save a PNG in `app/snapshots/` with naming format:
   `<platform>_<job_id>_<timestamp>_<status>.png`
2. **DOM Snapshot:** Save outerHTML dump if submission verification failed or an unexpected modal blocked progress.
3. **Audit Hash:** Compute SHA-256 digest of the DOM dump for verifiable provenance.
