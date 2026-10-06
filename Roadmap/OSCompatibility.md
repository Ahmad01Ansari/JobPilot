You are working on JobPilot, a production-oriented desktop application built primarily with Python/PySide6, SQLAlchemy, SQLite/PostgreSQL, browser automation, AI providers, background workers, and long-running automation processes.

JobPilot currently targets:

PRIMARY:
- Windows 10/11
- Ubuntu/Linux desktop

FUTURE:
- macOS

NOT A CURRENT TARGET:
- Android
- iOS

The goal of this task is NOT to redesign JobPilot.

The goal is to perform a complete DESKTOP OS COMPATIBILITY, RESOURCE, CONCURRENCY, CRASH, DEADLOCK, SHUTDOWN, AND LONG-RUN RELIABILITY AUDIT and fix the issues found.

Do not begin by changing code.

FIRST inspect and understand the existing repository.

============================================================
0. NON-NEGOTIABLE RULES
============================================================

1. DO NOT rewrite working business logic unnecessarily.

2. DO NOT rewrite LinkedIn or Naukri automation.

3. DO NOT replace the existing PySide6 architecture.

4. DO NOT introduce fake compatibility layers.

5. DO NOT claim Windows/Linux compatibility without actually testing or creating reproducible test coverage.

6. DO NOT silently change application behavior while fixing OS compatibility.

7. Preserve existing database schema and migrations unless a change is genuinely required.

8. Do not introduce OS-specific logic into domain/business services.

9. Do not use:
   - hardcoded Windows paths
   - hardcoded Linux paths
   - hardcoded separators
   - shell-specific commands without abstraction
   - OS-specific assumptions inside core services

10. Never block the Qt GUI thread with:
   - network requests
   - AI requests
   - browser automation
   - database-heavy operations
   - filesystem-heavy operations
   - subprocess execution
   - large file processing
   - model loading
   - backup/restore
   - resume parsing

11. Never solve a deadlock by adding arbitrary sleeps.

12. Never solve a race condition with arbitrary delays.

13. Never hide exceptions with broad:
       except Exception:
           pass

14. Never terminate worker processes/threads blindly if graceful cancellation is possible.

15. Every background worker must have a defined lifecycle:
   START → RUNNING → STOP REQUESTED → CLEANUP → FINISHED

16. Application shutdown must be deterministic and safe.

17. All OS-specific functionality must be isolated behind infrastructure/service abstractions.

18. Do not add security bypasses, stealth automation, CAPTCHA bypasses, fingerprint spoofing, proxy rotation, or rate-limit evasion.

19. No fake health metrics.

20. No fake performance measurements.

21. No "works on my machine" acceptance.

============================================================
1. REPOSITORY DISCOVERY — BEFORE CODING
============================================================

Audit the actual repository.

Identify:

- application entry point
- PySide6 application bootstrap
- main window
- navigation
- services
- repositories
- database layer
- SQLAlchemy setup
- workers
- QThread usage
- QRunnable/QThreadPool usage
- asyncio usage
- subprocess usage
- Selenium usage
- Playwright usage
- Stagehand integration
- browser profiles
- AI provider integrations
- filesystem/storage services
- backup/restore
- logging
- settings/configuration
- secrets handling
- notification system
- timers
- event buses/signals
- singleton managers
- shutdown handlers
- crash handling
- packaging/build configuration
- tests
- CI configuration

Create:

docs/OS_COMPATIBILITY_AUDIT.md

Before modifying code, document the discovered architecture.

Do not assume that previously documented architecture is still accurate.

============================================================
2. CREATE AN OS COMPATIBILITY MATRIX
============================================================

Create an explicit matrix:

                    Windows 10/11     Ubuntu Linux
----------------------------------------------------
Application startup       ?                ?
PySide6 UI                ?                ?
High DPI                  ?                ?
SQLite                    ?                ?
SQLAlchemy                ?                ?
Filesystem                ?                ?
Settings                  ?                ?
Secrets                   ?                ?
Browser automation        ?                ?
Chrome/Chromium            ?                ?
Selenium                   ?                ?
Playwright                 ?                ?
Stagehand                  ?                ?
Ollama                     ?                ?
Network                    ?                ?
Subprocess                 ?                ?
Workers                    ?                ?
Thread shutdown            ?                ?
App shutdown               ?                ?
Backup/restore             ?                ?
Logging                    ?                ?
Notifications              ?                ?
Resume parsing              ?                ?
Long-running automation    ?                ?

For every unknown item:

- determine whether it is actually supported
- test it where possible
- document limitations
- do not mark it "compatible" based only on theoretical support

============================================================
3. MEMORY LEAK AUDIT
============================================================

Investigate memory growth during:

A. Application startup
B. Navigation between views
C. Opening/closing dialogs repeatedly
D. Global search
E. Logs/mission-control page
F. Dashboard/analytics
G. Resume upload/parsing
H. AI requests
I. Browser automation
J. Long-running automation
K. Repeated start/stop cycles
L. Application restart

Look specifically for:

- Qt widgets never being released
- signal connections accumulating
- lambdas retaining objects
- circular references
- QThread references retained forever
- QTimer instances accumulating
- QNetwork objects not released
- browser drivers not closed
- Playwright contexts not closed
- subprocesses not terminated
- large log buffers
- unbounded event history
- unbounded Python lists/dicts
- cached screenshots
- cached DOM/page data
- DataFrame retention
- image/PDF memory retention
- database sessions retained
- ORM objects unnecessarily retained
- global singleton state growing indefinitely

Use actual profiling where possible.

Do not simply increase garbage collection frequency.

Document:

- suspected leak
- reproduction steps
- evidence
- fix
- verification

============================================================
4. CPU / RESOURCE USAGE
============================================================

Audit CPU and resource consumption.

Check:

- idle CPU usage
- navigation CPU usage
- dashboard refresh
- log streaming
- global search
- browser automation
- AI requests
- database queries
- polling loops
- timers
- filesystem watchers
- retry loops

Look for:

- busy loops
- while True loops
- excessive polling
- timers firing too frequently
- repeated database queries
- repeated UI repainting
- excessive signal emission
- duplicate workers
- duplicate automation runs
- uncontrolled retries

Prefer:

event-driven architecture
over
continuous polling

Where polling is required, use a bounded and documented interval.

Do not invent arbitrary delays just to reduce CPU.

============================================================
5. THREADING / QTHREAD AUDIT
============================================================

Audit every QThread, QRunnable, QThreadPool and worker.

For every worker determine:

- who creates it?
- who owns it?
- who starts it?
- who stops it?
- who waits for it?
- what happens if it throws?
- what happens if the UI closes?
- what happens if the user starts it twice?
- what happens if the user clicks Stop?
- what happens if the worker finishes naturally?
- what happens if the worker hangs?

Check for:

- QThread affinity errors
- QObject used from wrong thread
- UI updates from worker threads
- worker objects destroyed while running
- threads destroyed while still running
- double start
- double stop
- orphaned threads
- race conditions
- signals emitted after UI destruction

Qt UI objects MUST only be manipulated from the GUI thread.

Workers must communicate through signals/events or approved thread-safe services.

============================================================
6. DEADLOCK / RACE CONDITION AUDIT
============================================================

Search for potential deadlocks and race conditions.

Audit:

- Lock
- RLock
- mutexes
- condition variables
- threading.Event
- queues
- Qt signals
- blockingQueuedConnection
- synchronous signal handlers
- database locks
- SQLite transactions
- worker shutdown
- browser shutdown
- subprocess shutdown

Look specifically for:

Lock A → Lock B
and elsewhere:
Lock B → Lock A

Also identify:

worker waiting for UI
UI waiting for worker

worker waiting for another worker
another worker waiting for first worker

database transaction waiting on another transaction

browser shutdown waiting for a thread that is waiting for browser shutdown

Avoid nested locks where possible.

Prefer ownership and message passing over shared mutable state.

============================================================
7. SQLITE / DATABASE CONCURRENCY
============================================================

Audit SQLite usage specifically for:

- multiple threads
- multiple workers
- long-running transactions
- session lifetime
- connection reuse
- WAL
- busy timeout
- concurrent writes
- shutdown during transaction

Verify:

- SQLAlchemy engine configuration
- session creation
- session disposal
- thread safety
- transaction boundaries
- rollback behavior
- connection cleanup

No UI thread should hold an open database transaction while waiting for a worker/network/browser operation.

Check for:

database is locked

and reproduce if possible.

Implement proper retry/backoff only where appropriate.

Never hide database-lock errors.

============================================================
8. APPLICATION SHUTDOWN AUDIT
============================================================

This is CRITICAL.

When user closes JobPilot:

1. Stop accepting new work.
2. Signal workers to stop.
3. Stop automation gracefully.
4. Stop browser automation.
5. Close browser contexts/drivers.
6. Finish/rollback active DB transactions.
7. Flush important logs.
8. Stop timers/watchers.
9. Release resources.
10. Close database engine.
11. Save required application state.
12. Exit cleanly.

Verify behavior when:

- idle
- AI request running
- browser running
- LinkedIn automation running
- Naukri automation running
- universal agent running
- resume parsing running
- backup running
- database operation running
- log stream active
- multiple workers active

Do NOT use:

os._exit()
kill -9
TerminateProcess()
or equivalent forceful termination

as the normal shutdown mechanism.

Force termination may exist only as a documented last-resort recovery path.

============================================================
9. CRASH RESILIENCE
============================================================

Audit crash handling.

The application must not silently fail.

Handle:

- uncaught Python exceptions
- worker exceptions
- Qt exceptions
- browser crashes
- browser process disappearance
- AI provider failures
- network failures
- SQLite errors
- corrupted configuration
- corrupted cache
- missing files
- permission errors
- unavailable directories
- subprocess failures

Create a safe crash reporting mechanism.

Crash reports MUST NOT contain:

- API keys
- passwords
- cookies
- browser session data
- authentication headers
- access tokens
- full credential values

Sanitize crash information before persistence/export.

============================================================
10. FILESYSTEM / PATH COMPATIBILITY
============================================================

Audit every filesystem operation.

Use pathlib / platform-safe APIs.

Never assume:

C:\...
/home/...
~/...
/tmp/...

Use appropriate application data directories.

Support:

Windows user directories
Linux XDG directories
future macOS user directories

Separate:

- application data
- configuration
- secrets
- cache
- logs
- backups
- temporary files

Check:

- Unicode paths
- spaces in paths
- long paths
- permission denied
- missing directories
- read-only locations
- network-mounted locations
- relative paths
- symlinks where applicable

Never construct paths using string concatenation.

============================================================
11. SUBPROCESS AUDIT
============================================================

Find every subprocess/os.system/command execution.

For each command determine:

- why it exists
- whether it is OS-specific
- whether an equivalent Python API exists
- whether shell=True is used
- whether user-controlled input reaches it

Avoid:

shell=True

unless absolutely necessary and justified.

Never pass untrusted user input directly to a shell.

Create platform adapters where commands genuinely differ.

Example:

BrowserLauncher
ProcessManager
SystemNotificationService
FileOpener

instead of:

if windows:
    os.system(...)
else:
    os.system(...)

inside business logic.

============================================================
12. BROWSER PROCESS LIFECYCLE
============================================================

Audit:

Selenium
undetected-chromedriver
Playwright
Stagehand
Chrome/Chromium

Check:

- driver startup
- browser startup
- context creation
- profile locking
- multiple instances
- shutdown
- crash recovery
- orphan browser processes
- profile cleanup
- Windows process behavior
- Linux process behavior

Do not change existing LinkedIn/Naukri automation behavior unnecessarily.

The objective is lifecycle reliability, not automation redesign.

============================================================
13. BROWSER PROFILE / FILE LOCKING
============================================================

Persistent browser profiles are especially sensitive.

Check:

- two automation runs opening the same profile
- application restart while browser is active
- stale profile locks
- corrupted profile state
- browser process still running after JobPilot closes

Never delete browser profile data automatically as a generic fix.

If a profile is locked:

- detect it
- explain the condition
- offer safe recovery

============================================================
14. HIGH DPI / DISPLAY COMPATIBILITY
============================================================

Audit PySide6 UI on:

- 100% scaling
- 125%
- 150%
- 175%
- 200%

Check:

- clipped controls
- tiny text
- oversized controls
- dialogs exceeding screen size
- popup positioning
- table columns
- icons
- fonts
- screenshots
- browser windows

Do not hardcode pixel sizes where responsive sizing is appropriate.

Use Qt layout systems and DPI-aware sizing.

Test:

single monitor
multiple monitors
different resolutions
moving window between monitors

============================================================
15. WINDOW / DIALOG LIFECYCLE
============================================================

Audit every major dialog/view.

Check:

- repeated open/close
- modal dialogs
- non-modal dialogs
- parent ownership
- window references
- signal cleanup
- stale references

Repeatedly opening and closing a dialog should not continuously increase memory.

Avoid unnecessary:

self.dialog = Dialog()

patterns that retain closed dialogs forever.

============================================================
16. NETWORK / AI REQUEST RELIABILITY
============================================================

Audit network calls.

Every network operation must have:

- timeout
- cancellation strategy where supported
- error handling
- retry policy where appropriate
- bounded retries
- clear failure state

Never retry infinitely.

Never retry authentication failures endlessly.

Never block the GUI waiting for network responses.

AI providers may be:

- local Ollama
- OpenAI-compatible APIs
- cloud providers
- arbitrary user-configured endpoints

OS compatibility must not depend on one provider.

============================================================
17. TIMER / POLLING AUDIT
============================================================

Find all:

QTimer
threading.Timer
sleep()
polling loops
scheduled jobs

For each determine:

- why it exists
- expected frequency
- whether it can overlap with itself
- what happens during shutdown
- whether it continues after its page closes

Avoid:

while True:
    sleep(1)

when an event-driven solution is possible.

Timers must stop when their owner/service is stopped.

============================================================
18. LOGGING / LOG MEMORY
============================================================

Audit logging carefully.

The application must support long-running automation without unbounded memory growth.

Check:

- in-memory log buffers
- event timeline size
- raw log widgets
- log file rotation
- export
- copy operations

UI log views should use bounded models/windows.

Do not load millions of log lines into memory.

"Clear log view" must not necessarily delete forensic log files.

Separate:

Clear View
from
Delete/Archive Logs

============================================================
19. BACKUP / RESTORE RELIABILITY
============================================================

Audit backup/restore on Windows and Linux.

Check:

- file locking
- SQLite WAL
- browser profile exclusion/inclusion
- temporary files
- interrupted backup
- interrupted restore
- insufficient disk space
- permissions
- corrupted archives
- path traversal inside archives

Restore must not leave the application in a partially restored state.

Use:

backup → validate → restore staging → verify → activate

where practical.

============================================================
20. TEMP FILE / RESOURCE CLEANUP
============================================================

Find all temporary files/directories.

Verify cleanup when:

- success
- failure
- exception
- cancellation
- application crash
- restart

Use Python tempfile mechanisms where appropriate.

Never create predictable shared temporary filenames.

============================================================
21. OS SIGNAL / INTERRUPTION HANDLING
============================================================

Audit application behavior for:

Windows close
Linux SIGTERM
SIGINT
terminal close where applicable
system shutdown/logoff

The application should attempt graceful cleanup.

Do not assume Unix signals exist identically on Windows.

Platform-specific signal behavior must be isolated.

============================================================
22. CONFIGURATION COMPATIBILITY
============================================================

Audit configuration loading.

Test:

- missing config
- malformed config
- old config version
- new config
- missing settings
- unknown settings
- invalid values

Application must fail safely.

Never destroy a user's existing configuration because one field is invalid.

Use migration/defaulting logic.

Do not silently change existing default semantics.

============================================================
23. ENVIRONMENT / USER DIRECTORY COMPATIBILITY
============================================================

Audit use of:

HOME
USERPROFILE
APPDATA
LOCALAPPDATA
XDG_CONFIG_HOME
XDG_DATA_HOME
TEMP
TMP

Do not directly rely on one OS environment variable.

Use appropriate platform-aware APIs.

============================================================
24. PACKAGING / DEPLOYMENT AUDIT
============================================================

Inspect how JobPilot is intended to be distributed.

Evaluate:

Windows:
- executable packaging
- DLL dependencies
- WebDriver/browser dependencies
- VC runtime requirements
- writable directories
- antivirus false positives

Linux:
- Python/runtime dependencies
- shared libraries
- browser dependencies
- permissions
- desktop launcher
- X11/Wayland compatibility

Do not require the user to manually modify source code after installation.

Document known system dependencies.

============================================================
25. WAYLAND / X11 LINUX COMPATIBILITY
============================================================

Because Ubuntu may use Wayland or X11, test/inspect:

- PySide6 rendering
- window positioning
- clipboard
- screenshots
- browser windows
- global shortcuts if used
- system notifications

Do not assume X11-only behavior.

If a feature requires X11:

- isolate it
- detect availability
- provide graceful fallback

============================================================
26. WINDOWS-SPECIFIC AUDIT
============================================================

Check Windows-specific issues:

- path length
- file locks
- antivirus interaction
- process termination
- startup behavior
- browser profile locks
- subprocess behavior
- UTF-16/Unicode paths
- permissions
- UAC
- AppData locations
- executable discovery

Do not require administrator privileges unless absolutely necessary.

JobPilot should run with normal user privileges.

============================================================
27. LINUX-SPECIFIC AUDIT
============================================================

Check:

- permissions
- XDG directories
- Wayland/X11
- executable permissions
- symlinks
- case sensitivity
- missing shared libraries
- browser dependencies
- process lifecycle
- user services

Do not assume Ubuntu-specific paths for all Linux systems.

The target is:

Ubuntu first

while avoiding unnecessary Ubuntu-only assumptions.

============================================================
28. RESOURCE LIMITS
============================================================

Define reasonable resource expectations.

Measure where practical:

- startup time
- idle RAM
- idle CPU
- dashboard RAM
- log page RAM
- automation RAM
- automation CPU
- repeated navigation memory
- repeated worker lifecycle memory

Do not create arbitrary performance targets without measurement.

Record actual baseline values.

Then fix measurable regressions.

============================================================
29. LONG-RUN SOAK TEST
============================================================

Create a reliability test scenario.

Run JobPilot for an extended period while performing:

- navigation
- search
- dashboard refresh
- opening/closing dialogs
- AI requests
- database operations
- log streaming
- starting/stopping workers
- browser automation where safe

Measure:

- memory growth
- CPU growth
- thread count
- subprocess count
- browser process count
- database connections
- event count
- log size

The objective is to detect resource accumulation.

============================================================
30. START / STOP STRESS TEST
============================================================

Repeatedly:

START
STOP
START
STOP

workers and automation.

Test:

- 10 cycles
- 50 cycles where practical
- concurrent operations

Look for:

- duplicate workers
- orphan processes
- memory growth
- stale signals
- deadlocks
- UI freezes

============================================================
31. AUTOMATION SAFETY
============================================================

Do NOT modify existing automation to bypass:

- CAPTCHA
- anti-bot systems
- security controls
- rate limits
- authentication protections

If the automation encounters a verification/security checkpoint:

transition to the existing/manual intervention mechanism.

This task is about OS reliability, not bypassing platform controls.

============================================================
32. TEST STRATEGY
============================================================

Do not only add unit tests.

Add appropriate:

UNIT TESTS
INTEGRATION TESTS
THREAD LIFECYCLE TESTS
DATABASE CONCURRENCY TESTS
RESOURCE TESTS
SHUTDOWN TESTS
FILESYSTEM TESTS
OS-SPECIFIC TESTS
UI LIFECYCLE TESTS

Where OS-specific execution is unavailable in the current environment:

- create tests that can run in CI
- clearly mark environment-dependent tests
- document required Windows/Linux validation

Never mark an untested OS as fully verified.

============================================================
33. CI / CROSS-PLATFORM VALIDATION
============================================================

If CI exists, inspect it.

If practical, add:

Windows test job
Linux test job

Do not add macOS CI yet unless required.

The CI should at minimum validate:

- import/startup
- tests
- database initialization
- filesystem operations
- worker lifecycle
- shutdown
- packaging smoke test where practical

============================================================
34. ARCHITECTURE RULE
============================================================

Maintain:

UI
↓
Presentation / ViewModel
↓
Service Layer
↓
Repository / Domain
↓
Infrastructure

OS-specific functionality belongs in Infrastructure.

Examples:

Filesystem:
StorageService

Browser:
BrowserAgent

Process:
ProcessManager

Notifications:
NotificationService

Paths:
AppPaths

System integration:
PlatformService

Do NOT write:

if Windows:
    ...
else:
    ...

throughout the application.

Centralize platform differences.

============================================================
35. CREATE AN OS ABSTRACTION LAYER ONLY WHERE NEEDED
============================================================

Do not create abstractions for everything.

Introduce abstractions only where actual OS differences exist.

Potential examples:

AppPaths
ProcessManager
BrowserLauncher
NotificationService
SystemInfoService
FileAssociationService

Keep them small and testable.

============================================================
36. DOCUMENT ALL FINDINGS
============================================================

Create:

docs/OS_COMPATIBILITY_AUDIT.md

For every issue record:

ID
Severity
OS
Component
Problem
Reproduction
Evidence
Root Cause
Fix
Regression Test
Validation Status

Severity:

CRITICAL
HIGH
MEDIUM
LOW
INFO

Examples:

OS-001
HIGH
Windows
Worker lifecycle
QThread remains alive after application shutdown

OS-002
HIGH
Linux
Filesystem
Hardcoded Windows path

OS-003
MEDIUM
Both
Logs
Unbounded in-memory log buffer

============================================================
37. FIX ORDER
============================================================

Fix in this order:

1. crashes
2. deadlocks
3. data corruption
4. unsafe shutdown
5. orphan processes
6. memory leaks
7. thread lifecycle bugs
8. database concurrency
9. filesystem incompatibilities
10. CPU/resource issues
11. UI/DPI issues
12. packaging/deployment issues
13. minor compatibility issues

Do not spend time polishing UI while critical lifecycle bugs remain.

============================================================
38. REGRESSION PROTECTION
============================================================

After each major fix:

- run relevant tests
- run full test suite
- verify existing automation remains intact
- verify database behavior
- verify application startup
- verify application shutdown

Do not change behavior unrelated to the issue.

============================================================
39. UPDATE AGENT DEVELOPMENT RULES
============================================================

After the audit is complete, update the repository's agent rules file.

Locate the existing:

AGENTS.md
or equivalent AI/developer rules file.

Do NOT blindly create a duplicate rules file.

Add a permanent section:

## Desktop OS Compatibility & Reliability Rules

Include rules equivalent to:

1. JobPilot supports Windows and Linux desktop first.
2. macOS is a future target.
3. Do not introduce mobile-specific assumptions into desktop core architecture.
4. OS-specific behavior must be isolated behind infrastructure abstractions.
5. Never hardcode OS-specific filesystem paths.
6. Use pathlib/platform-aware APIs.
7. Never block the Qt GUI thread.
8. All network, AI, browser, subprocess, filesystem-heavy and database-heavy operations must run outside the GUI thread where appropriate.
9. Every worker must have an explicit lifecycle and graceful cancellation.
10. Application shutdown must stop workers, browsers, timers and subprocesses safely.
11. Never use arbitrary sleeps to fix synchronization.
12. Avoid shared mutable state across threads.
13. Never update Qt widgets from worker threads.
14. Database sessions must have clear ownership and transaction boundaries.
15. SQLite concurrency must be explicitly handled.
16. Never leave browser processes orphaned.
17. Never assume X11; support Wayland where practical.
18. Never require administrator/root privileges unless explicitly justified.
19. Never hide exceptions.
20. Never silently change configuration defaults.
21. Never introduce unbounded in-memory buffers.
22. Long-running operations must be cancellable where practical.
23. Resource cleanup must happen on success, failure and cancellation.
24. Do not claim OS compatibility without validation.
25. Do not rewrite working automation merely to solve an OS issue.
26. No platform security bypasses.
27. No fake health/performance metrics.
28. Every OS-specific bug fix requires regression coverage where practical.
29. Test repeated start/stop and application shutdown.
30. Prefer event-driven architecture over polling.
31. Keep OS-specific infrastructure separate from domain logic.
32. Future macOS compatibility must not be broken by unnecessary Windows/Linux assumptions.

Preserve all existing agent rules.

Do not delete or weaken existing security, architecture, testing, or automation rules.

============================================================
40. FINAL VALIDATION
============================================================

Before declaring the task complete, verify:

[ ] Application starts cleanly
[ ] Application closes cleanly
[ ] No worker remains after shutdown
[ ] No orphan browser process remains
[ ] No obvious memory growth
[ ] No deadlock found in tested flows
[ ] No GUI blocking in audited operations
[ ] SQLite concurrency is safe
[ ] Filesystem paths are portable
[ ] Windows-specific issues documented
[ ] Linux-specific issues documented
[ ] DPI behavior reviewed
[ ] Wayland/X11 behavior reviewed
[ ] Subprocess lifecycle reviewed
[ ] AI/network timeouts reviewed
[ ] Timer/polling reviewed
[ ] Logging memory bounded
[ ] Backup/restore reviewed
[ ] Configuration migration reviewed
[ ] Existing LinkedIn automation preserved
[ ] Existing Naukri automation preserved
[ ] Existing tests still pass
[ ] New regression tests pass
[ ] OS audit document created
[ ] Agent rules updated
[ ] No secrets exposed
[ ] No security bypass introduced

============================================================
41. FINAL REPORT
============================================================

At the end provide:

1. Repository architecture discovered
2. Number of issues found
3. Number fixed
4. Number deferred
5. Critical/high-risk issues
6. Memory findings
7. Thread/deadlock findings
8. Database findings
9. Filesystem findings
10. Windows findings
11. Linux findings
12. Browser/process findings
13. Shutdown findings
14. Performance findings
15. Tests added
16. Tests executed
17. OS environments actually validated
18. Remaining limitations
19. Files changed
20. Agent rules changed

IMPORTANT:

Do not claim:

"Windows and Linux fully supported"

unless those environments were actually validated.

Instead use:

VALIDATED
PARTIALLY VALIDATED
NOT VALIDATED
KNOWN LIMITATION

============================================================
EXECUTION ORDER
============================================================

Follow this exact order:

PHASE 1 — Repository discovery
PHASE 2 — OS compatibility matrix
PHASE 3 — Thread/worker audit
PHASE 4 — Shutdown/lifecycle audit
PHASE 5 — Memory/resource audit
PHASE 6 — Database/filesystem audit
PHASE 7 — Browser/subprocess audit
PHASE 8 — UI/DPI/display audit
PHASE 9 — Network/AI/timer audit
PHASE 10 — Packaging/deployment audit
PHASE 11 — Implement fixes
PHASE 12 — Add regression tests
PHASE 13 — Cross-platform validation
PHASE 14 — Update AGENTS.md
PHASE 15 — Final audit report

IMPORTANT:

Do not jump directly into implementation.

First inspect the repository and produce the audit findings and implementation plan.

After the audit, fix issues systematically.

Preserve existing architecture and automation.

The final goal is:

A stable, resource-conscious, crash-resistant, thread-safe,
cleanly-shutting-down JobPilot desktop application that behaves
consistently across Windows and Ubuntu/Linux without introducing
OS-specific coupling into the core architecture.