"""
Single-Instance Application Enforcer for JobPilot Desktop.

Ensures only one instance of the JobPilot desktop application runs at a time
per user session. If a second instance is launched (e.g. by double-clicking
JobPilot.app again on macOS or running the executable on Windows/Linux),
the secondary instance notifies the primary instance to raise and focus its
existing window, and then exits cleanly with exit code 0.
"""

import os
import sys
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def _get_server_name() -> str:
    """Generate a deterministic, user-scoped socket name for single instance locking."""
    user_identifier = "default"
    try:
        if hasattr(os, "getuid"):
            user_identifier = str(os.getuid())
        else:
            user_identifier = os.environ.get("USERNAME", "default")
    except Exception:
        pass
    return f"jobpilot_desktop_single_instance_{user_identifier}"


class SingleInstanceManager:
    """Manages cross-platform single instance locking via QLocalServer and QLocalSocket."""

    def __init__(self, server_name: Optional[str] = None) -> None:
        self.server_name = server_name or _get_server_name()
        self._server: Optional[object] = None
        self._main_window: Optional[object] = None

    def register_main_window(self, window: object) -> None:
        """Register the primary MainWindow to be focused on duplicate launch attempts."""
        self._main_window = window

    def _handle_new_connection(self) -> None:
        """Handle incoming connection from a secondary instance attempting to launch."""
        if not self._server:
            return

        socket = self._server.nextPendingConnection()
        if not socket:
            return

        def _on_ready_read():
            try:
                data = bytes(socket.readAll()).decode("utf-8", errors="ignore").strip()
                if "ACTIVATE" in data:
                    self._activate_existing_window()
            except Exception as exc:
                logger.debug("Error reading activation signal: %s", exc)
            finally:
                socket.disconnectFromServer()
                socket.deleteLater()

        socket.readyRead.connect(_on_ready_read)

    def _activate_existing_window(self) -> None:
        """Restore, raise, and activate the registered MainWindow."""
        if not self._main_window:
            return

        try:
            # Unminimize if minimized
            if hasattr(self._main_window, "isMinimized") and self._main_window.isMinimized():
                if hasattr(self._main_window, "showNormal"):
                    self._main_window.showNormal()
                else:
                    self._main_window.show()
            else:
                self._main_window.show()

            self._main_window.raise_()
            self._main_window.activateWindow()
            logger.info("Activated existing JobPilot primary window in response to launch request.")
        except Exception as exc:
            logger.warning("Failed to bring primary window to front: %s", exc)

    def release(self) -> None:
        """Cleanly close and unregister the local server."""
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass
            self._server = None

    @classmethod
    def acquire_lock(cls) -> Tuple[bool, Optional["SingleInstanceManager"]]:
        """
        Attempts to acquire the single-instance lock.

        Returns:
            Tuple[bool, Optional[SingleInstanceManager]]:
                (True, manager) if this process is the primary instance.
                (False, None) if another instance is already running (activation requested).
        """
        # Bypass single-instance lock for test runs or explicit multi-instance flag
        if (
            "--test-run" in sys.argv
            or "--allow-multiple" in sys.argv
            or os.environ.get("JOBPILOT_ALLOW_MULTIPLE") == "1"
        ):
            return True, None

        server_name = _get_server_name()

        try:
            from PySide6.QtNetwork import QLocalServer, QLocalSocket
        except ImportError:
            # If QtNetwork is unavailable, allow execution to proceed
            logger.warning("PySide6.QtNetwork unavailable; skipping single instance enforcement.")
            return True, None

        # Check if an existing primary instance is running by attempting to connect
        socket = QLocalSocket()
        socket.connectToServer(server_name)

        if socket.waitForConnected(500):
            # Another instance responded; send activate command and exit
            try:
                socket.write(b"ACTIVATE\n")
                socket.waitForBytesWritten(500)
                socket.disconnectFromServer()
            except Exception as exc:
                logger.debug("Failed sending ACTIVATE message to primary instance: %s", exc)

            logger.info(
                "JobPilot is already running. Activated existing instance and terminating duplicate."
            )
            return False, None

        # No running instance responded; take ownership of the server lock
        manager = cls(server_name=server_name)
        server = QLocalServer()

        # Remove any stale socket file left behind by a previous unclean crash
        QLocalServer.removeServer(server_name)

        if not server.listen(server_name):
            # If listening failed even after removeServer, remove once more and retry
            QLocalServer.removeServer(server_name)
            if not server.listen(server_name):
                logger.warning(
                    "Could not create single instance server '%s': %s. Continuing anyway.",
                    server_name,
                    server.errorString(),
                )
                return True, None

        server.newConnection.connect(manager._handle_new_connection)
        manager._server = server
        return True, manager
