# JobPilot Desktop OS Compatibility, Concurrency & Lifecycle Audit

**Audit Date:** October 2026  
**Target Environments:**
- Primary 1: Ubuntu / Linux Desktop (X11 / Wayland, Ubuntu 22.04 / 24.04 LTS, Python 3.11)
- Primary 2: Windows 10 & 11 (64-bit, NTFS, Python 3.11)
- Future Target: macOS 13+ (Ventura / Sonoma / Sequoia, Apple Silicon & Intel)
- Out of Scope: Mobile (iOS / Android)

---

## 1. Executive Summary

JobPilot is a PySide6 desktop automation application combining local SQLite data storage, multi-threaded worker pools, multi-platform Selenium/Playwright browser automation (LinkedIn, Naukri, Indeed, Glassdoor, Foundit), and local/cloud AI pipelines.

This audit evaluates the application against real-world multi-OS operational risks:
1. **Uncoordinated Process Exit:** Window close events (`closeEvent`) previously did not coordinate graceful shutdown across `AutomationManager`, `JobRunnerPool`, active browser sessions, or database connection pools, risking orphaned Chrome/ChromeDriver background processes and SQLite lock starvation.
2. **Path & Filesystem Assumptions:** POSIX-centric paths (`Path.home() / ".jobpilot"`, hardcoded forward slashes, `os.chmod` permission bits without Windows guards) and hardcoded `xdg-open` calls.
3. **Database Concurrency & Locking:** Multi-threaded workers querying or updating SQLite without sufficient busy timeouts (previously 10,000ms) during intensive evaluation loops.
4. **Subprocess Hierarchy Management:** Process tree termination on Windows lacking `taskkill /F /T` or job object containment, leading to lingering zombie Chrome instances.
5. **High DPI & Scaling Gaps:** Fractional display scaling (125%, 150%) on Windows laptops needing explicit Qt PassThrough rounding policies.
6. **Crash Resilience:** Absence of global exception hooks for background QThreads and thread pools resulting in silent failures without sanitized diagnostic crash dumps.

---

## 2. Operating System Compatibility Matrix

| Category | Linux Desktop (Ubuntu 22.04/24.04) | Windows 10/11 (NTFS) | macOS (Future Target) |
| :--- | :--- | :--- | :--- |
| **GUI Framework** | PySide6 (Qt6) via XCB/Wayland | PySide6 (Qt6) via Windows platform plugin | PySide6 (Qt6) via Cocoa |
| **High DPI Scaling** | System scale factors supported | PassThrough rounding policy required for 125%/150% scaling | Native Retina scaling |
| **User Data Path** | `~/.config/jobpilot` or `~/.jobpilot` | `%APPDATA%\JobPilot` or `~/.jobpilot` | `~/Library/Application Support/JobPilot` |
| **Process Termination** | `os.killpg(pgid, SIGTERM)` | `taskkill /F /T /PID` or ProcessGroup | `os.killpg(pgid, SIGTERM)` |
| **Browser Lock Files** | Chromium symlinks (`hostname-pid`) | Chromium text files (`pid`) | Symlinks / lock files |
| **External File Launch** | `QDesktopServices` / `xdg-open` | `QDesktopServices` / `os.startfile` | `QDesktopServices` / `open` |
| **DB Engine** | SQLite3 with WAL mode | SQLite3 with WAL mode + 30s busy timeout | SQLite3 with WAL mode |
| **File Permissions** | `os.chmod(0o600 / 0o700)` enforced | ACLs via OS / no-op `os.chmod` fallback | `os.chmod(0o600 / 0o700)` |

---

## 3. Discovered Vulnerabilities & Architecture Gaps (Inventory)

### OS-001 (CRITICAL): Uncoordinated Graceful Shutdown
- **Component:** `app/ui/main_window.py` (`closeEvent`)
- **Impact:** Closing the desktop window while automation or background tasks were running terminated the GUI thread while leaving child processes (`chrome.exe`, `chromedriver.exe`, `runAiBot.py` subprocesses) running in the background. Database connection pools were dropped without `engine.dispose()`.
- **Resolution:** Introduced `ApplicationLifecycleManager` (`app/services/os/lifecycle_manager.py`) wired into `MainWindow.closeEvent`. Coordinates:
  1. Setting cooperative stop requests on `AutomationManager`.
  2. Shutting down `JobRunnerPool` task execution.
  3. Closing active Selenium/Playwright browser instances.
  4. Waiting boundedly (up to 3000ms) for workers to unwind.
  5. Cleanly disposing SQLAlchemy engine pool via `engine.dispose()`.

### OS-002 (HIGH): Cross-Platform File and Path Infrastructure
- **Component:** `app/services/resume_service.py`, `modules/browser_lock.py`
- **Impact:** Hardcoded `xdg-open` subprocess execution failed on Windows systems where `xdg-open` is not a recognized command. Hardcoded POSIX paths and unhandled permissions created cross-platform friction.
- **Resolution:** Created `app/services/os/app_paths.py` and `app/services/os/system_service.py`:
  - `system_service.open_file_or_dir(path)` prioritizes `QDesktopServices.openUrl`, falling back to `os.startfile` on Windows, `xdg-open` on Linux, and `open` on macOS.
  - `app_paths.get_user_data_dir()` resolves standard user storage locations across Windows, Linux, and macOS.

### OS-003 (HIGH): SQLite Concurrency & Busy Timeout Starvation
- **Component:** `app/db/session.py` (`configure_sqlite_pragmas`)
- **Impact:** Under simultaneous multi-threaded evaluation (e.g. background job qualification worker running while automation updates runs), SQLite transactions could trigger `sqlite3.OperationalError: database is locked` if locks took longer than 10 seconds.
- **Resolution:** Increased `PRAGMA busy_timeout` to 30,000ms (30 seconds) and set `PRAGMA synchronous = NORMAL` alongside `PRAGMA journal_mode = WAL`. Created explicit `dispose_engine()` for clean shutdown.

### OS-004 (HIGH): Subprocess Process Tree Termination on Windows
- **Component:** `platforms/router.py`, `modules/browser_lock.py`
- **Impact:** On Windows, calling `proc.terminate()` or `os.kill(pid, signal.SIGTERM)` on the parent Python runner failed to terminate spawned Chrome browser instances, leaving orphaned `chrome.exe` processes consuming system memory.
- **Resolution:** Created `app/services/os/process_manager.py` with `kill_process_tree(pid)`:
  - On Windows: Uses `taskkill /F /T /PID <pid>` to terminate entire process hierarchy.
  - On Linux/POSIX: Uses `os.killpg` with `SIGTERM` followed by `SIGKILL` fallback.

### OS-005 (MEDIUM): Memory & Buffer Bounding for 24h+ Long Runs
- **Component:** `app/services/logs/run_context.py`, `app/ui/views/logs/tabs/live_battlefield_tab.py`
- **Analysis:** `RunObservabilityContext` uses bounded `deque(maxlen=1000)`. `LiveBattlefieldTab` enforces `MAX_TIMELINE_CARDS = 80` with explicit `widget.deleteLater()`. Verified bounded memory footprint for 24/7 background operation.

### OS-006 (MEDIUM): High DPI Fractional Scaling Support
- **Component:** `app/main.py`
- **Impact:** On Windows devices with 125% or 150% display scaling, default Qt rounding policies could result in micro-blurriness or misaligned borders.
- **Resolution:** Explicitly configured `QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)` before `QApplication` instantiation.

### OS-007 (LOW): Crash Resilience & Global Exception Telemetry
- **Component:** `app/services/os/crash_reporter.py`, `app/main.py`
- **Impact:** Uncaught thread or event loop exceptions could cause unexpected termination without diagnostic telemetry.
- **Resolution:** Implemented `install_global_crash_handler()` hooking `sys.excepthook` and `threading.excepthook`. Sanitizes stack traces using `LogSanitizer` and saves crash dumps to `logs/crash_dumps/crash_<timestamp>.json`.
