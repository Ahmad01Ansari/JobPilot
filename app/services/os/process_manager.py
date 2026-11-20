"""Cross-platform subprocess lifecycle and process tree management."""

import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

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
                elif sys.platform == "darwin":
                    try:
                        res = subprocess.run(
                            ["ps", "-p", str(pid), "-o", "state="],
                            capture_output=True,
                            text=True,
                            timeout=1,
                        )
                        if res.returncode == 0 and "Z" in res.stdout:
                            return False
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
            if pid == os.getpid():
                logger.warning("Refusing to kill own process PID %s", pid)
                return False

            descendant_pids = cls._get_descendant_pids_posix(pid)

            current_pgrp = os.getpgrp() if hasattr(os, "getpgrp") else None
            pgid = None
            try:
                pgid = os.getpgid(pid)
            except Exception:
                pass

            # CRITICAL: Only use killpg if target is its own process group leader
            # AND the group is NOT our own process group. Calling killpg on our own
            # process group terminates the application itself!
            is_own_pgrp = (current_pgrp is not None and pgid == current_pgrp)
            is_group_leader = (pgid == pid)
            use_killpg = (is_group_leader and not is_own_pgrp and hasattr(os, "killpg"))

            if use_killpg:
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except Exception:
                    os.kill(pid, signal.SIGTERM)
            else:
                for cpid in reversed(descendant_pids):
                    if cpid != os.getpid() and cls.is_pid_alive(cpid):
                        try:
                            os.kill(cpid, signal.SIGTERM)
                        except Exception:
                            pass
                if cls.is_pid_alive(pid):
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except Exception:
                        pass

            # Wait briefly for cooperative exit
            deadline = time.time() + timeout_seconds
            while time.time() < deadline:
                if not cls.is_pid_alive(pid):
                    return True
                time.sleep(0.1)

            # Force kill lingering process and descendants
            if cls.is_pid_alive(pid):
                if use_killpg:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except Exception:
                        os.kill(pid, signal.SIGKILL)
                else:
                    for cpid in reversed(descendant_pids):
                        if cpid != os.getpid() and cls.is_pid_alive(cpid):
                            try:
                                os.kill(cpid, signal.SIGKILL)
                            except Exception:
                                pass
                    if cls.is_pid_alive(pid):
                        try:
                            os.kill(pid, signal.SIGKILL)
                        except Exception:
                            pass
                time.sleep(0.1)

            return not cls.is_pid_alive(pid)
        except ProcessLookupError:
            return True
        except Exception as exc:
            logger.warning("Failed killing process tree for PID %s: %s", pid, exc)
            return False

    @classmethod
    def _get_descendant_pids_posix(cls, parent_pid: int) -> List[int]:
        """Finds all child and descendant PIDs of a process on Linux and macOS."""
        descendants: List[int] = []
        try:
            task_dir = Path(f"/proc/{parent_pid}/task")
            if task_dir.is_dir():
                for tid_dir in task_dir.iterdir():
                    children_file = tid_dir / "children"
                    if children_file.is_file():
                        with open(children_file, "r") as f:
                            for cpid_str in f.read().split():
                                if cpid_str.isdigit():
                                    cpid = int(cpid_str)
                                    descendants.append(cpid)
                                    descendants.extend(cls._get_descendant_pids_posix(cpid))
        except Exception:
            pass

        if not descendants:
            try:
                res = subprocess.run(
                    ["pgrep", "-P", str(parent_pid)],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if res.returncode == 0:
                    for line in res.stdout.strip().splitlines():
                        if line.strip().isdigit():
                            cpid = int(line.strip())
                            descendants.append(cpid)
                            descendants.extend(cls._get_descendant_pids_posix(cpid))
            except Exception:
                pass

        return list(dict.fromkeys(descendants))

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

    @classmethod
    def suspend_process(cls, pid: int) -> bool:
        """Suspends/pauses process execution cooperatively across platforms.

        On POSIX: Uses signal.SIGSTOP.
        On Windows: Uses kernel32 DebugActiveProcess or silently fails gracefully if unsupported.
        """
        if not cls.is_pid_alive(pid):
            return False

        if sys.platform == "win32" or os.name == "nt":
            try:
                import ctypes
                return bool(ctypes.windll.kernel32.DebugActiveProcess(pid))
            except Exception as exc:
                logger.debug("Windows process suspension not available for PID %s: %s", pid, exc)
                return False

        # POSIX (Linux / macOS)
        try:
            if hasattr(signal, "SIGSTOP") and hasattr(os, "kill"):
                os.kill(pid, signal.SIGSTOP)
                return True
        except Exception as exc:
            logger.debug("Failed sending SIGSTOP to PID %s: %s", pid, exc)
        return False

    @classmethod
    def resume_process(cls, pid: int) -> bool:
        """Resumes a suspended process across platforms.

        On POSIX: Uses signal.SIGCONT.
        On Windows: Uses kernel32 DebugActiveProcessStop.
        """
        if not cls.is_pid_alive(pid):
            return False

        if sys.platform == "win32" or os.name == "nt":
            try:
                import ctypes
                return bool(ctypes.windll.kernel32.DebugActiveProcessStop(pid))
            except Exception as exc:
                logger.debug("Windows process resume not available for PID %s: %s", pid, exc)
                return False

        # POSIX (Linux / macOS)
        try:
            if hasattr(signal, "SIGCONT") and hasattr(os, "kill"):
                os.kill(pid, signal.SIGCONT)
                return True
        except Exception as exc:
            logger.debug("Failed sending SIGCONT to PID %s: %s", pid, exc)
        return False
