"""Unit and integration tests for OS compatibility, concurrency, process management, and lifecycle shutdown."""

import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.db.session import configure_sqlite_pragmas, create_db_engine, dispose_engine
from app.services.os.app_paths import AppPaths
from app.services.os.crash_reporter import _write_sanitized_crash_dump, install_global_crash_handler
from app.services.os.lifecycle_manager import ApplicationLifecycleManager
from app.services.os.process_manager import ProcessManager
from app.services.os.system_service import SystemService
from app.services.automation_service import AutomationManager, AutomationWorker
from app.services.task_runner import JobRunnerPool


class TestAppPaths(unittest.TestCase):
    """Verifies cross-platform path resolution and permission handling."""

    def test_os_detection_predicates(self):
        """Tests OS detection helper flags."""
        self.assertIsInstance(AppPaths.is_windows(), bool)
        self.assertIsInstance(AppPaths.is_linux(), bool)
        self.assertIsInstance(AppPaths.is_macos(), bool)

    def test_user_data_dir_resolution(self):
        """Verifies canonical data directory resolution."""
        data_dir = AppPaths.get_user_data_dir()
        self.assertIsInstance(data_dir, Path)
        self.assertTrue(str(data_dir))

    @patch("app.services.os.app_paths.Path.home")
    def test_windows_appdata_resolution(self, mock_home):
        """Verifies %APPDATA% resolution on Windows when no legacy directory exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            mock_home.return_value = Path(tmp_dir) / "fake_home"
            with patch("sys.platform", "win32"), patch.dict(os.environ, {"APPDATA": tmp_dir}):
                resolved = AppPaths.get_user_data_dir()
                self.assertEqual(resolved, Path(tmp_dir) / "JobPilot")

    def test_safe_set_permissions(self):
        """Verifies permissions setting succeeds safely across all platforms."""
        with tempfile.NamedTemporaryFile() as tf:
            p = Path(tf.name)
            success = AppPaths.safe_set_permissions(p, mode=0o600)
            self.assertTrue(success)


class TestSystemService(unittest.TestCase):
    """Verifies system diagnostics and cross-platform file opening."""

    def test_system_diagnostics_structure(self):
        """Verifies diagnostic dictionary schema."""
        diag = SystemService.get_system_diagnostics()
        self.assertIn("os_name", diag)
        self.assertIn("platform", diag)
        self.assertIn("architecture", diag)
        self.assertIn("python_version", diag)
        self.assertIn("is_64bit", diag)

    def test_open_nonexistent_file(self):
        """Verifies open_file_or_dir fails cleanly on non-existent path."""
        success, err = SystemService.open_file_or_dir("/nonexistent/file/path/xyz.txt")
        self.assertFalse(success)
        self.assertIn("does not exist", err.lower())

    @patch("PySide6.QtGui.QDesktopServices.openUrl", return_value=True)
    def test_open_valid_file_via_desktop_services(self, mock_open_url):
        """Verifies open_file_or_dir uses QDesktopServices when available."""
        with tempfile.NamedTemporaryFile() as tf:
            success, err = SystemService.open_file_or_dir(tf.name)
            self.assertTrue(success)
            self.assertIsNone(err)


class TestProcessManager(unittest.TestCase):
    """Verifies process tree termination and liveness checks."""

    def test_is_pid_alive_current_process(self):
        """Verifies current process PID is detected as alive."""
        self.assertTrue(ProcessManager.is_pid_alive(os.getpid()))

    def test_is_pid_alive_invalid_pid(self):
        """Verifies non-existent or negative PID is detected as not alive."""
        self.assertFalse(ProcessManager.is_pid_alive(-1))
        self.assertFalse(ProcessManager.is_pid_alive(9999999))

    def test_safe_terminate_process(self):
        """Verifies safe_terminate_process cleanly stops a spawned subprocess."""
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        self.assertTrue(ProcessManager.is_pid_alive(proc.pid))

        ProcessManager.safe_terminate_process(proc, timeout_seconds=1.0)
        self.assertFalse(ProcessManager.is_pid_alive(proc.pid))


class TestCrashReporter(unittest.TestCase):
    """Verifies crash telemetry sanitization and dump generation."""

    def test_write_sanitized_crash_dump(self):
        """Verifies that sensitive data is masked in written crash dumps."""
        try:
            # Raise exception containing sensitive token
            raise ValueError("Authentication failed with token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret123")
        except ValueError as err:
            exc_type, exc_val, exc_tb = sys.exc_info()
            dump_path = _write_sanitized_crash_dump(exc_type, exc_val, exc_tb, thread_name="TestThread")
            self.assertIsNotNone(dump_path)
            self.assertTrue(dump_path.exists())

            # Read back and verify secret is masked
            content = dump_path.read_text(encoding="utf-8")
            self.assertNotIn("Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret123", content)
            self.assertIn("[REDACTED_TOKEN]", content)

            # Cleanup
            try:
                dump_path.unlink()
            except Exception:
                pass


class TestSqliteConcurrencyPragmas(unittest.TestCase):
    """Verifies SQLite WAL mode and 30-second busy timeout configuration."""

    def test_sqlite_pragmas_applied(self):
        """Verifies SQLite connection events apply WAL and 30000ms busy timeout."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tf:
            db_url = f"sqlite:///{tf.name}"
            eng = create_db_engine(url=db_url)
            with eng.connect() as conn:
                from sqlalchemy import text
                timeout_res = conn.execute(text("PRAGMA busy_timeout;")).scalar()
                wal_res = conn.execute(text("PRAGMA journal_mode;")).scalar()
                sync_res = conn.execute(text("PRAGMA synchronous;")).scalar()

                self.assertEqual(timeout_res, 30000)
                self.assertEqual(wal_res.upper(), "WAL")
                # PRAGMA synchronous = NORMAL is integer 1 in SQLite
                self.assertIn(sync_res, (1, "NORMAL", "normal"))
            eng.dispose()


class TestApplicationLifecycleManager(unittest.TestCase):
    """Verifies coordinated application graceful shutdown."""

    def setUp(self):
        ApplicationLifecycleManager._is_shutting_down = False

    def tearDown(self):
        ApplicationLifecycleManager._is_shutting_down = False

    def test_shutdown_application_orchestration(self):
        """Tests that lifecycle shutdown executes without throwing exceptions."""
        with patch.object(JobRunnerPool.get_instance(), "shutdown") as mock_pool_shutdown:
            ApplicationLifecycleManager.shutdown_application(timeout_ms=500)
            self.assertTrue(ApplicationLifecycleManager.is_shutting_down())
            mock_pool_shutdown.assert_called()


if __name__ == "__main__":
    unittest.main()
