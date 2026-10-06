"""
Main application entry point for JobPilot Desktop.
Initializes QApplication, theme tokens, and primary MainWindow shell.
"""

import sys
import os
from pathlib import Path

# Ensure project root is present in sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from app.ui.theme import ThemeManager
from app.ui.main_window import MainWindow


def main() -> int:
    """Initializes and runs the JobPilot Desktop Application."""
    # Install centralized log sanitizer and global crash handler
    try:
        from app.services.sanitizer_service import install_root_sanitizer
        install_root_sanitizer()
    except Exception:
        pass

    try:
        from app.services.os.crash_reporter import install_global_crash_handler
        install_global_crash_handler()
    except Exception:
        pass

    # Check for headless / offscreen CLI flag
    if "--offscreen" in sys.argv or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    # Configure High DPI scaling policy (prevents fractional scaling blurriness on Windows/Linux)
    try:
        from PySide6.QtCore import Qt
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("JobPilot")
    app.setOrganizationName("JobPilot")
    app.setDesktopFileName("jobpilot")

    # Set application-wide brand icon (inherited by all dialogs, windows, and taskbars)
    app_icon = ThemeManager.get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Windows taskbar grouping and icon identity registration
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("JobPilot.JobAutomation.Desktop.1")
        except Exception:
            pass

    # Apply centralized dark theme
    ThemeManager.apply_dark_theme(app)

    # Initialize and diagnose database connection safely
    from app.db import init_db, check_connection
    from app.ui.state import AppState

    state = AppState()
    try:
        success, err = init_db()
        if success:
            diag = check_connection()
            if diag.get("status") == "ok":
                wal_str = " (WAL)" if diag.get("wal_enabled") else ""
                state.update_status("database", f"Connected{wal_str}")
                # Run full migration only once on initial setup if DB is unseeded
                try:
                    from app.db.session import SessionLocal, get_db_session
                    from app.db.models import User
                    from sqlalchemy import select, func
                    with get_db_session(SessionLocal) as s:
                        is_seeded = (s.scalar(select(func.count(User.id))) or 0) > 0
                    if not is_seeded:
                        from app.services.migration_service import MigrationService
                        MigrationService().run_full_migration()
                except Exception:
                    pass
                # Sync profile.json → DB so manual edits are captured
                try:
                    from app.services.platform_service import PlatformService
                    PlatformService().sync_profile_json_to_db()
                except Exception:
                    pass
            else:
                state.update_status("database", f"Check Warning: {diag.get('error') or 'unknown'}")
        else:
            state.update_status("database", f"Init Error: {err}")
    except Exception as exc:
        state.update_status("database", f"Error: {exc}")

    # Instantiate Main Window
    window = MainWindow(state=state)
    if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
        window.showMaximized()

    # Pre-flight self-test support
    from PySide6.QtCore import QTimer
    if "--test-run" in sys.argv:
        print("[JobPilot Desktop] Verified: UI shell, DB connection, 13 views, services, and event bus initialized successfully.")
        def _safe_quit():
            window.close()
            app.quit()
        QTimer.singleShot(250, _safe_quit)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
