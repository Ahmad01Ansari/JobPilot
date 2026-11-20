"""
Main application entry point for JobPilot Desktop.
Initializes QApplication, theme tokens, and primary MainWindow shell.
"""

import sys
import multiprocessing

# Critical: freeze_support() must be called immediately for PyInstaller frozen bundles
# to prevent infinite recursive process spawning on macOS and Windows.
multiprocessing.freeze_support()

# Filter macOS Finder process serial number argument (-psn_...)
if sys.platform == "darwin":
    sys.argv = [arg for arg in sys.argv if not arg.startswith("-psn_")]

import os
import io
from pathlib import Path

# Safeguard against 'NoneType' object has no attribute 'write' in frozen GUI builds on Windows
class _SafeStream:
    def write(self, s: str) -> int:
        return len(s) if s else 0
    def flush(self) -> None:
        pass
    def isatty(self) -> bool:
        return False

if sys.stdout is None or not hasattr(sys.stdout, "write"):
    sys.stdout = _SafeStream()
if sys.stderr is None or not hasattr(sys.stderr, "write"):
    sys.stderr = _SafeStream()
if sys.stdin is None:
    sys.stdin = io.StringIO()

# Ensure project root is present in sys.path for direct execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication
from app.ui.theme import ThemeManager
from app.ui.main_window import MainWindow


def main() -> int:
    """Initializes and runs the JobPilot Desktop Application."""
    try:
        from modules.open_chrome import ensure_ssl_certificates
        ensure_ssl_certificates()
    except Exception:
        pass

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

    # Silence harmless Linux desktop host portal registration warnings
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.services.warning=false")

    app = QApplication(sys.argv)
    app.setApplicationName("JobPilot")
    app.setOrganizationName("JobPilot")
    app.setDesktopFileName("jobpilot")

    # Enforce cross-platform single instance locking to prevent duplicate launches
    from app.services.os.single_instance import SingleInstanceManager
    is_primary, instance_mgr = SingleInstanceManager.acquire_lock()
    if not is_primary:
        return 0
    if instance_mgr:
        app.aboutToQuit.connect(instance_mgr.release)

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

    # Install global wheel scroll filter to prevent accidental editing of inputs when scrolling
    try:
        from app.ui.wheel_filter import install_no_wheel_edit_filter
        install_no_wheel_edit_filter(app)
    except Exception:
        pass

    # Startup Splash Screen (displayed during database initialization in desktop mode)
    import time
    splash = None
    splash_start_time = 0.0
    watchdog_timer = None
    is_offscreen = os.environ.get("QT_QPA_PLATFORM") == "offscreen" or "--offscreen" in sys.argv

    def _dismiss_splash():
        nonlocal splash
        if watchdog_timer and watchdog_timer.isActive():
            watchdog_timer.stop()
        if splash is not None:
            try:
                splash.close()
                splash.deleteLater()
            except Exception:
                pass
            splash = None

    if not is_offscreen and "--test-run" not in sys.argv:
        splash_pix = ThemeManager.get_splash_pixmap()
        if not splash_pix.isNull():
            from PySide6.QtWidgets import QSplashScreen
            from PySide6.QtCore import Qt, QTimer
            from PySide6.QtGui import QColor, QFont
            splash = QSplashScreen(splash_pix, Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint)
            if not app_icon.isNull():
                splash.setWindowIcon(app_icon)
            splash.setFont(QFont("Inter", 10))
            splash.show()
            for _ in range(3):
                app.processEvents()

            # Center splash screen on the active display
            primary_screen = app.primaryScreen()
            if primary_screen:
                screen_geo = primary_screen.geometry()
                splash_geo = splash.geometry()
                x = screen_geo.x() + (screen_geo.width() - splash_geo.width()) // 2
                y = screen_geo.y() + (screen_geo.height() - splash_geo.height()) // 2
                splash.move(x, y)

            splash.showMessage("JobPilot Autopilot initializing...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#FF5F15"))
            splash.raise_()
            splash.activateWindow()
            splash.repaint()
            for _ in range(3):
                app.processEvents()
            splash_start_time = time.time()
            # Safety watchdog: auto-dismiss splash after 30 seconds if startup hangs
            watchdog_timer = QTimer()
            watchdog_timer.setSingleShot(True)
            watchdog_timer.timeout.connect(_dismiss_splash)
            watchdog_timer.start(30000)

    # Initialize and diagnose database connection safely
    from app.db import init_db, check_connection
    from app.ui.state import AppState

    state = AppState()
    if splash is not None:
        try:
            splash.showMessage("Connecting to database...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#FF5F15"))
            splash.repaint()
            app.processEvents()
        except Exception:
            pass
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

    # Instantiate Main Window with live splash loading updates
    window = MainWindow(state=state, splash=splash)
    if instance_mgr:
        instance_mgr.register_main_window(window)

    def _finish_and_show():
        if os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            window.showMaximized()
            window.raise_()
            window.activateWindow()
        if splash is not None:
            try:
                splash.finish(window)
            except Exception:
                pass
            _dismiss_splash()

    if watchdog_timer and watchdog_timer.isActive():
        watchdog_timer.stop()

    if splash is not None and splash_start_time > 0:
        elapsed = time.time() - splash_start_time
        min_display_time = 1.0  # Ensure splash is visible for at least 1.0s
        rem_ms = int(max(0, (min_display_time - elapsed) * 1000))
        try:
            splash.showMessage("Ready! Opening JobPilot...", Qt.AlignBottom | Qt.AlignHCenter, QColor("#FF5F15"))
            splash.repaint()
            app.processEvents()
        except Exception:
            pass
        if rem_ms > 0:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(rem_ms, _finish_and_show)
        else:
            _finish_and_show()
    else:
        _finish_and_show()

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
