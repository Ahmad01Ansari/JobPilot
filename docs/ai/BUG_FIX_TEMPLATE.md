# Bug Fix Template — JobPilot
*Copy and fill out this document for every bug fix or issue resolution.*
*Reference: [Master Constitution](AI_DEVELOPMENT_RULES.md) §3, §15*

---

# Bug: [Short Descriptive Bug Title]

## 1. Symptoms & Observed Failure
- **Error Message / Traceback:**
  ```
  [Paste exact error log / stacktrace here]
  ```
- **Observed Behavior:** [Describe what actually happened during runtime]
- **Environment:** [OS, Chrome version, Python environment, platform (LinkedIn/Naukri/Indeed/Glassdoor/UI)]

## 2. Reproduction Steps
1. Navigate to: [...]
2. Run command / Action: [...]
3. Input data: [...]
4. Observed failure occurs at: [exact line or step]

## 3. Root Cause Analysis
- **Why did it happen?** [Detailed technical explanation of the flaw, race condition, stale element, or unhandled exception]
- **Faulty Code Location:** `path/to/file.py:L123-L145`
- **Call Chain:** [Trace leading to the failure]

## 4. Existing vs Expected Behavior
- **Existing Behavior:** [What the system currently does (e.g. crashes, swallows error, loops indefinitely)]
- **Expected Behavior:** [What the system should do according to architecture rules and user expectations]

## 5. Proposed Fix (Smallest Safe Change)
- **Target Files:**
  - `path/to/file.py`: [Explanation of exact change]
- **Design Rationale:** [Why this is the minimal and safest resolution]
- **Preserved Interfaces:** [Confirmation that caller contracts remain unchanged]

## 6. Regression Risks & Side Effects
- **Potential Callers Affected:** [Other modules calling the modified function]
- **Mitigation Strategy:** [How we ensure other platforms or views are not broken]

## 7. Test Strategy & Baseline
- **Baseline Test Run:**
  - Command: `.venv/bin/python -m unittest tests/test_relevant.py`
  - Baseline Result: [X passed, 1 failed (reproduced)]
- **Regression Suite:**
  - Command: `.venv/bin/python -m unittest discover -s tests`

## 8. Verification & Proof of Fix
- **Post-Fix Test Result:** [All tests passed]
- **Compilation Check:** `.venv/bin/python -m py_compile ...`
- **Manual / Headless Run Output:** [Paste relevant log snippet showing successful execution]

## 9. Remaining Limitations & Edge Cases
- [Document any known edge cases not covered by this specific fix]
