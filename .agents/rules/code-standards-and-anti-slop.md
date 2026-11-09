# Code Standards & Anti-AI Slop Policy

> **MANDATORY PRODUCTION CODE HYGIENE DIRECTIVE:**
> All code authored or edited by AI agents in this repository must meet senior, enterprise-grade production standards.
> "AI slop" — conversational filler, performative comments, childish syntax-restating commentary, emojis/icons in
> code or logs, incomplete mock stubs, and sloppy coding habits — is strictly forbidden across JobPilot.

---

## 1. Zero-Tolerance Prohibitions (Anti-AI Slop)

### ❌ 1. No Emojis or Icons in Source Code & Logging
- **Forbidden in Code & Comments:** Never use emojis in code, variable names, function names, docstrings, or inline comments (e.g. `# 🚀 initialize engine`, `# ⚠️ handle error`, `# ✅ success`).
- **Forbidden in Logs & Prints:** Never use emojis in log statements or stdout/stderr (e.g. `logger.info("🚀 Launching worker...")`, `print("✅ Done!")`).
  - *Why:* Emojis break non-UTF-8 terminals, corrupt syslog/ELK parsers, fail headless pipe redirection, and look unprofessional.
  - *Correct Pattern:* Use standard structured logging:
    ```python
    # ❌ FORBIDDEN
    logger.info("🚀 Starting worker for %s...", platform)
    logger.warning("⚠️ Failed to parse job card: %s", job_id)

    # ✅ PRODUCTION STANDARD
    logger.info("Starting automation worker [platform=%s]", platform)
    logger.warning("Failed to parse job card [job_id=%s, error=%s]", job_id, err)
    ```
- **Forbidden in UI String Literals:** Never use raw Unicode emoji characters as buttons, headers, or status labels in PySide6 code (e.g. `QPushButton("🚀 Run")`, `QLabel("❌ Failed")`). Use the application's design system: `ThemeManager`, `qtawesome`, or registered SVG vector assets.

---

### ❌ 2. No Performative, Chatty, or Childish Comments
- Never write comments that merely restate what the code obviously does:
  ```python
  # ❌ FORBIDDEN (AI Slop)
  # Create a variable to hold user name
  user_name = get_user()
  # Loop through all jobs in list
  for job in jobs:
      # Check if job is valid
      if job.is_valid:
          # Call apply function
          apply(job)
  # Voila! Everything is done
  ```
- Never write conversational, chatty, or self-narrating comments:
  - ❌ `# Now we need to carefully check if the session is alive...`
  - ❌ `# Let's go ahead and parse the HTML response here`
  - ❌ `# This little helper will make magic happen`
  - ❌ `# Hopefully this doesn't crash on Windows!`
- **The Rule for Comments:** Only write comments that explain **WHY** non-obvious code exists — such as platform-specific quirks, concurrency invariants, rate limit trade-offs, or upstream ATS edge cases. If the code is clear, let the code speak for itself.

---

### ❌ 3. No Incomplete Stubs or Placeholder Code
- Never leave lazy placeholders in submitted code:
  - ❌ `# TODO: implement this later`
  - ❌ `# Add logic here`
  - ❌ `pass  # placeholder`
  - ❌ `return None  # mock response`
- Never hallucinate fallback values or introduce fake mock data in production paths. Every code path must be fully implemented, typed, and testable.

---

### ❌ 4. No Trivial Helper Bloat
- Do not create tiny one-line wrapper functions that wrap standard Python calls without adding value (e.g. `def check_if_empty(lst): return len(lst) == 0`).
- Do not invent custom utilities when standard library modules (`collections`, `itertools`, `pathlib`, `typing`, `functools`, `dataclasses`) or existing project services (`app/services/`) already provide robust solutions.

---

## 2. Enterprise Production Standards

### ✅ 1. Robust Type Annotations
Every function, method, and class attribute must include complete Python type hints:
```python
# ✅ PRODUCTION STANDARD
def resolve_credential(
    self,
    tenant: str,
    platform: str,
    user_id: Optional[int] = None,
) -> Optional[WorkdayCredentialDTO]:
    ...
```

### ✅ 2. Clean, Professional Docstrings (PEP 257 / Google Style)
Docstrings must be concise and informative, focusing on parameters, return values, exceptions, and lifecycle contracts:
```python
class WorkdayAccountService:
    """Manages multi-tenant Workday candidate account credentials and lifecycle.

    Handles secure storage via SecretsService, session isolation, and tenant-level
    credential retrieval across multi-step universal automation runs.
    """

    def record_account(
        self,
        tenant: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
    ) -> WorkdayAccount:
        """Persist or update account credentials for a Workday tenant.

        Args:
            tenant: Domain tenant identifier (e.g. 'myworkdayjobs.com/company').
            email: Account login username/email.
            password: Plaintext password (encrypted immediately upon receipt).
            display_name: Human-readable company or brand name.

        Returns:
            WorkdayAccount model instance representing the saved record.

        Raises:
            ValidationError: If tenant or email formatting is invalid.
            DatabaseError: If database persistence fails.
        """
```

### ✅ 3. Parameterized Structured Logging
- Always use parameterized logging instead of f-strings in logger calls to allow log aggregation tools to group error signatures:
  ```python
  # ❌ INCONSISTENT / WASTEFUL
  logger.info(f"Processing job {job_id} at {company}")

  # ✅ STRUCTURED & EFFICIENT
  logger.info("Processing job card [job_id=%s, company=%s]", job_id, company)
  ```

### ✅ 4. Explicit Exception Hierarchy
- Catch specific exceptions, never bare `except:`.
- Log the exception with traceback where appropriate (`logger.exception(...)` or `exc_info=True`).
- Propagate or translate to domain-level exceptions with actionable diagnostic context.

