"""Cross-platform subprocess lifecycle and process tree management."""

import logging
import os
import signal
import subprocess
import sys
import time
from typing import Optional

logger = logging.getLogger(__name__)


class ProcessManager:
    """Provides resilient process status checks and process tree termination."""

    @classmethod
    def is_pid_alive(cls, pid: int) -> bool:
        """Determines whether a process with the specified PID is currently running."""
        if not isinstance(pid, int) or pid <= 0 or pid > 4_194_304:
            return False

        try:
            if sys.platform == "win32" or os.name == "nt":
                import ctypes
                kernel32 = ctypes.windll.kernel32
                SYNCHRONIZE = 0x00100000
                process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
                if process:
                    kernel32.CloseHandle(process)
                    return True
                return False
            else:
                # Unix signal 0 performs error checking without sending a real signal
                os.kill(pid, 0)
                if sys.platform.startswith("linux"):
                    try:
                        with open(f"/proc/{pid}/status", "r", encoding="utf-8", errors="ignore") as f:
                            for line in f:
                                if line.startswith("State:"):
                                    if "Z" in line or "zombie" in line.lower():
                                        return False
                                    break
                    except Exception:
                        pass
                return True
        except (ProcessLookupError, OverflowError):
            return False
        except PermissionError:
            # Process exists but belongs to a different user account
            return True
        except OSError:
            return False

    @classmethod
    def kill_process_tree(cls, pid: int, timeout_seconds: float = 2.0) -> bool:
        """Terminates a process and all of its spawned child processes across platforms.

        On Windows: Uses 'taskkill /F /T /PID <pid>' to cleanly wipe out the entire process tree.
        On POSIX: Uses process groups (os.killpg) sending SIGTERM, followed by SIGKILL if still alive.

        Args:
            pid: Root process ID to terminate.
            timeout_seconds: Time to wait for SIGTERM before sending SIGKILL.

        Returns:
            True if process was terminated or already dead; False on error.
        """
        if not cls.is_pid_alive(pid):
            return True

        if sys.platform == "win32" or os.name == "nt":
            try:
                # Windows taskkill with /T (tree) and /F (force)
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                time.sleep(0.2)
                return not cls.is_pid_alive(pid)
            except Exception as exc:
                logger.warning("Windows taskkill failed for PID %s: %s", pid, exc)
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
                return not cls.is_pid_alive(pid)

        # POSIX (Linux & macOS)
        try:
            pgid = None
            try:
                pgid = os.getpgid(pid)
            except Exception:
                pass

            if pgid is not None and hasattr(os, "killpg"):
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
            else:
                os.kill(pid, signal.SIGTERM)

            # Wait briefly for cooperative exit
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if not cls.is_pid_alive(pid):
                    return True
                time.sleep(0.1)

            # Force kill lingering process and group
            if cls.is_pid_alive(pid):
                if pgid is not None and hasattr(os, "killpg"):
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        os.kill(pid, signal.SIGKILL)
                else:
                    os.kill(pid, signal.SIGKILL)
                time.sleep(0.1)

            return not cls.is_pid_alive(pid)
        except ProcessLookupError:
            return True
        except Exception as exc:
            logger.warning("Failed killing process tree for PID %s: %s", pid, exc)
            return False

    @classmethod
    def safe_terminate_process(cls, proc: Optional[subprocess.Popen], timeout_seconds: float = 2.0) -> None:
        """Safely stops a Popen subprocess instance and all child processes."""
        if proc is None:
            return

        try:
            if proc.poll() is not None:
                return  # Process already exited

            proc.terminate()
            try:
                proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                cls.kill_process_tree(proc.pid, timeout_seconds=1.0)
                try:
                    proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("Notice during safe_terminate_process: %s", exc)
