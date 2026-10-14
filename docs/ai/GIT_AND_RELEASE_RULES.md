# Git, GitHub CI/CD & Software Release Standardization Rules — JobPilot

> **MANDATORY DIRECTIVE FOR ALL AI AGENTS:**
> Adhere strictly to these versioning, commit, and CI/CD standardization rules to prevent git conflicts, avoid GitHub Actions quota depletion, and ensure release integrity.

---

## 1. Core Principles

1. **Commit Often, Tag Sparingly:** Regular bug fixes, UI tweaks, and incremental refinements must be committed directly to `main` without generating release tags.
2. **Release Tags Are Expensive Milestones:** Pushing a release tag (`v*`) triggers cross-platform compilation matrix runners on GitHub Actions (Windows + Linux). Never tag a release for single-line changes or unverified fixes.
3. **Zero Untested Releases:** No release tag may ever be created or pushed without first executing the three mandatory verification gates (compilation, unit tests, and headless GUI self-test).

---

## 2. Commit vs. Release Workflow Separation

```
DEVELOPMENT CYCLE:
Fix Bug / Feature ──► Verify Locally ──► Commit to `main` ──► Push to `origin/main`
                                                                (NO Release Tag Created)
                                                                (Zero Actions Minutes Wasted)

RELEASE CYCLE (Explicit User Request / Milestone Batch):
Batch Verified ──► Bump app/version.py ──► Update CHANGELOG.md ──► Pass All Gates ──► Create Tag ──► Push Tag
```

### Rule A: When to Push Normal Commits
- User asks to fix a UI bug, style issue, or background automation bug.
- Agent verifies the fix locally.
- Agent stages files, commits with clean descriptive message, and pushes to `origin/main`.
- **Do NOT bump version. Do NOT create git tags.**

### Rule B: When to Create a Release Tag (`vX.Y.Z-beta.N`)
- **ONLY** when the user explicitly requests a new build or release ("push build", "release new version", "tag release").
- **OR** when a complete milestone batch (multiple related issues) has been thoroughly tested, confirmed, and approved for distribution to testers.

---

## 3. GitHub Actions & CI Quota Preservation

1. **Free Account Minute Discipline:** Free GitHub accounts receive 2,000 Actions minutes/month.
2. **Runner Weight Multipliers:** Windows virtual environments consume **2× minutes** per execution minute. A 5-minute Windows build consumes 10 quota minutes.
3. **Workflow Dispatch & Tag Triggering:**
   - `.github/workflows/release.yml` triggers **only** on tags matching `v*` or via manual `workflow_dispatch`.
   - Never push tags rapidly in succession. Consolidate fixes into batches.

---

## 4. Authoritative Versioning & Synchronization

When a release is explicitly authorized, the following three files **must** be updated simultaneously in the exact same commit:

1. **`app/version.py` (Single Source of Truth):**
   ```python
   __version__ = "0.1.0-beta.X"
   VERSION = __version__
   RELEASE_CHANNEL = "private-beta"
   ```
2. **`tests/test_beta_readiness_diagnostics.py`:**
   Update version assertions in `test_authoritative_version_string` and report metadata tests to match the new version.
3. **`CHANGELOG.md`:**
   Add a structured section following [Keep a Changelog](https://keepachangelog.com/) format:
   ```markdown
   ## [0.1.0-beta.X] — YYYY-MM-DD
   ### <Release Type Title>
   #### Added / Fixed / Changed
   - Bullet items explaining changes clearly
   ```

---

## 5. Mandatory Pre-Release Verification Gates

Before tagging any release, an AI agent **must execute and pass** all three gates in the `.venv` environment:

```bash
# Gate 1: Cross-Module Compilation
.venv/bin/python -m py_compile runAiBot.py run_desktop.py app.py config/*.py modules/*.py platforms/*.py tests/*.py

# Gate 2: Targeted Unit & Regression Test Suite
.venv/bin/python -m unittest tests/test_setup_service.py tests/test_onboarding_and_ai.py tests/test_beta_readiness_diagnostics.py tests/test_qna_canonical_seed.py tests/test_qna_service.py

# Gate 3: Headless Desktop GUI Verification
.venv/bin/python run_desktop.py --offscreen --test-run
```

If **any** gate fails, the release tag **must not be created**. Fix the issue first.

---

## 6. Git Identity & Commit Conventions

1. **Author Standard:** Every commit must preserve repository authorship:
   ```bash
   git commit --author="Ahmad Raza <rjaahmad60@gmail.com>" -m "type(scope): concise description"
   ```
2. **Conventional Commit Prefixes:**
   - `fix:` — Bug fixes, UI glitch fixes, layout adjustments.
   - `feat:` — New capabilities, new views, new provider adapters.
   - `refactor:` — Code restructuring without behavior changes.
   - `perf:` — Performance improvements, query optimizations.
   - `test:` — Adding or fixing unit/integration tests.
   - `release:` — Official version bump and release packaging.

---

## 7. Tagging & Publishing Invariants

1. **Annotated Tags Only:** Always use annotated tags with clear release summaries:
   ```bash
   git tag -a v0.1.0-beta.X -m "Release v0.1.0-beta.X"
   ```
2. **Atomic Push:**
   Push the commit to `main` first, then push the tag:
   ```bash
   git push origin main && git push origin v0.1.0-beta.X
   ```
3. **Packaging Script Parity:**
   `scripts/build_windows.bat` and `scripts/build_linux.sh` must dynamically resolve `$APP_VERSION` / `%APP_VERSION%` directly from `app.version` so executable naming never drifts.
