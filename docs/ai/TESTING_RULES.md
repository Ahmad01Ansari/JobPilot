# JobPilot — Testing & Verification Rules
**Specialized Guidelines for Automated Testing, Mocks, and Pre-Flight Validation**
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §15, §16*

---

## 1. Testing Philosophy

JobPilot controls mission-critical job applications. A bug in field extraction, form filling, or submission verification can cause misrepresentations to employers or break user workflows.

### Core Testing Mandates:
1. **Never Test on Live Platforms in Automated Suites:** Automated CI/unit tests must NEVER hit live LinkedIn, Naukri, Indeed, or Glassdoor endpoints. Use local HTML fixtures, mocked WebDrivers, and fake ATS servers (`tests/test_fake_ats_server.py`).
2. **Test Before and After (Baseline Verification):** Run existing relevant tests before modifying code to establish a baseline. Run them again after modifications to prove zero regressions.
3. **No Unverified Success Claims:** Never claim a test passed without running the command and inspecting the actual return code and stdout.

---

## 2. Essential Test Commands

All commands must be executed using the project's Python 3.11 virtual environment (`.venv`):

### 2.1. Syntax & Compilation Check
```bash
.venv/bin/python -m py_compile runAiBot.py app.py config/*.py modules/*.py platforms/*.py platforms/naukri/*.py platforms/indeed/*.py tests/*.py
```

### 2.2. Full Test Suite Discovery
```bash
.venv/bin/python -m unittest discover -s tests
```

### 2.3. Desktop UI Headless Offscreen Test
Validates PySide6 views, ThemeManager, and signal connections without opening a physical window:
```bash
.venv/bin/python run_desktop.py --offscreen --test-run
```

### 2.4. Production Pre-Flight Diagnostics
Verifies configuration schemas, driver paths, and profile permissions:
```bash
.venv/bin/python runAiBot.py --platform naukri --check-config
.venv/bin/python runAiBot.py --platform indeed --check-config
```

### 2.5. Universal Agent ATS Harness Tests
```bash
.venv/bin/python -m unittest tests/test_fake_ats_server.py tests/test_universal_state_machine.py tests/test_universal_orchestrator.py tests/test_universal_worker_lifecycle.py tests/test_universal_ui_dialogs.py tests/test_ats_archetypes.py tests/test_universal_alpha_acceptance.py tests/test_universal_hardening_release_gate.py
```

---

## 3. Required Test Coverage Matrix

Every new feature or bug fix must provide tests covering:
1. **Happy Path:** Expected data flows, successful element interactions, valid state transitions.
2. **Invalid Input:** Malformed configurations, missing profile fields, unsupported URLs.
3. **Failure Path:** WebDriver timeouts, NoSuchElementException, stale element recovery.
4. **Boundary & Edge Cases:** 0 search results found, multi-tab window switches, modal popups obscuring buttons.
5. **State Machine Verification:** Verify that the worker enters expected `ExecutionState`, correctly sets `InterventionReason`, and halts at review gates.

---

## 4. Test Reporting Format

In your final agent response, always report test metrics using this exact format:

```
### Test Verification Report:
- Baseline (Before Changes):
  - Ran: 42 tests
  - Result: 42 passed, 0 failed
- Post-Implementation (After Changes):
  - Ran: 45 tests (+3 new tests added)
  - Result: 45 passed, 0 failed
- Syntax Compilation: PASSED (0 errors)
- Desktop Offscreen Test: PASSED (Exit code 0)
```
