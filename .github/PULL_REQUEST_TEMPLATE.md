## Description
<!-- Provide a brief description of what this PR does and why it is needed. -->

## Type of Change
- [ ] Bug fix (`fix:`)
- [ ] New feature (`feat:`)
- [ ] Code refactoring (`refactor:`)
- [ ] Test addition/improvement (`test:`)
- [ ] Documentation update (`docs:`)
- [ ] Build / packaging configuration

## Operating System Compatibility
- [ ] Tested on **Linux / Ubuntu**
- [ ] Tested on **Windows (10/11)**
- [ ] Verified that paths use `pathlib.Path` or `os.path.join()` (no hardcoded `/` or `\\`)
- [ ] Verified that subprocess termination uses `ProcessManager` (no raw `kill -9` or untracked processes)

## Pre-Flight Verification Checklist
- [ ] Gate 1: Code compiles cleanly (`python -m py_compile ...`)
- [ ] Gate 2: Automated unit tests pass (`python -m unittest discover -s tests`)
- [ ] Gate 3: Desktop UI headless self-test passes (`python run_desktop.py --offscreen --test-run`)
- [ ] No secrets, credentials, `.env`, or database files (`*.db`) committed
- [ ] No git tags created
