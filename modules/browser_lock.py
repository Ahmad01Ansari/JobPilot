"""Browser Profile Lock & Isolation Management.

Provides stale Chrome lock file detection, PID liveness verification,
and deterministic multi-user profile isolation for LinkedIn and Naukri.
"""

import os
import sys
import re
from typing import Optional
from modules.helpers import print_lg, make_directories


def extract_pid_from_lock(lock_path: str) -> Optional[int]:
    """Extracts process ID from a Chrome SingletonLock symlink or file content."""
    try:
        # Only SingletonLock contains a process ID in Chromium; SingletonCookie and
        # SingletonSocket contain random session cookies or socket descriptors.
        base_name = os.path.basename(lock_path)
        if base_name != "SingletonLock":
            return None

        if os.path.islink(lock_path):
            target = os.readlink(lock_path)
            # Linux Chrome creates symlinks like 'hostname-12345'
            match = re.search(r"-(\d+)$", target)
            if match:
                pid = int(match.group(1))
                if 0 < pid <= 4_194_304:
                    return pid
            # Fallback regex for any number in target
            match = re.search(r"(\d+)", target)
            if match:
                pid = int(match.group(1))
                if 0 < pid <= 4_194_304:
                    return pid
        elif os.path.isfile(lock_path):
            with open(lock_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                match = re.search(r"-?(\d+)$", content) or re.search(r"(\d+)", content)
                if match:
                    pid = int(match.group(1))
                    if 0 < pid <= 4_194_304:
                        return pid
    except Exception:
        pass
    return None


def is_pid_alive(pid: int) -> bool:
    """Checks whether a process with the specified PID is currently running."""
    if not isinstance(pid, int) or pid <= 0 or pid > 4_194_304:
        return False
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            process = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if process:
                kernel32.CloseHandle(process)
                return True
            return False
        else:
            # On Unix, signal 0 does not kill process but performs error checking
            os.kill(pid, 0)
            if sys.platform.startswith("linux"):
                try:
                    with open(f"/proc/{pid}/status", "r") as f:
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
        # Process exists but belongs to another user
        return True
    except OSError:
        return False


def cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Safely cleans up orphaned SingletonLock, SingletonCookie, and SingletonSocket files.
    
    If a lock points to a dead PID or is broken, it unlinks the lock to prevent
    undetected-chromedriver startup crashes.
    """
    if not profile_dir or not os.path.exists(profile_dir):
        return

    # If primary SingletonLock is active, do not touch any singleton files
    primary_lock = os.path.join(profile_dir, "SingletonLock")
    if os.path.islink(primary_lock) or os.path.exists(primary_lock):
        active_pid = extract_pid_from_lock(primary_lock)
        if active_pid is not None and is_pid_alive(active_pid):
            print_lg(f"[BrowserLock] Chrome process {active_pid} is actively using profile at {profile_dir}.")
            return

    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket"]
    for item in lock_files:
        path = os.path.join(profile_dir, item)
        if os.path.islink(path) or os.path.exists(path):
            pid = extract_pid_from_lock(path)
            # If PID is detected and confirmed alive, do not touch (another active browser session)
            if pid is not None and is_pid_alive(pid):
                print_lg(f"[BrowserLock] Chrome process {pid} is actively using profile at {profile_dir}.")
                continue

            try:
                if os.path.islink(path) or os.path.isfile(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)
                print_lg(f"[BrowserLock] Cleared stale lock file: {path} (stale pid: {pid})")
            except Exception as e:
                print_lg(f"[BrowserLock] Could not remove stale lock {path}: {e}")

    # Check for bloated/corrupted Preferences file (> 10MB indicates autocomplete/history corruption causing Chrome core dump)
    pref_file = os.path.join(profile_dir, "Default", "Preferences")
    if os.path.isfile(pref_file):
        try:
            size_mb = os.path.getsize(pref_file) / (1024 * 1024)
            if size_mb > 10.0:
                print_lg(f"[BrowserLock] Detected bloated Preferences file ({size_mb:.1f} MB). Backing up and resetting to prevent Chrome crash...")
                bak_path = pref_file + ".corrupt.bak"
                if os.path.exists(bak_path):
                    os.unlink(bak_path)
                os.rename(pref_file, bak_path)
                with open(pref_file, "w", encoding="utf-8") as f:
                    f.write("{}")
                print_lg("[BrowserLock] Preferences reset cleanly.")
        except Exception as e:
            print_lg(f"[BrowserLock] Warning checking Preferences file size: {e}")


def kill_profile_processes(profile_dir: str) -> None:
    """Terminates any Chrome processes actively using the specified user data directory and frees locks."""
    if not profile_dir or not os.path.exists(profile_dir):
        return

    primary_lock = os.path.join(profile_dir, "SingletonLock")
    if os.path.islink(primary_lock) or os.path.exists(primary_lock):
        pid = extract_pid_from_lock(primary_lock)
        if pid is not None and is_pid_alive(pid):
            try:
                print_lg(f"[BrowserLock] Terminating lingering Chrome process {pid} using {profile_dir}...")
                from app.services.os.process_manager import ProcessManager
                ProcessManager.kill_process_tree(pid, timeout_seconds=1.5)
            except Exception as e:
                print_lg(f"[BrowserLock] Notice terminating process {pid}: {e}")

    # Remove all lock files now that process is cleared
    for item in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        path = os.path.join(profile_dir, item)
        if os.path.islink(path) or os.path.exists(path):
            try:
                if os.path.islink(path) or os.path.isfile(path):
                    os.unlink(path)
                elif os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path, ignore_errors=True)
                print_lg(f"[BrowserLock] Cleared lock file after process termination: {path}")
            except Exception:
                pass


def get_profile_dir(platform: str, user_id: Optional[int] = None) -> str:
    """Returns deterministic profile directory for a platform and user.
    
    For multi-user (user_id > 1), creates an isolated profile path:
    ~/.jobpilot/profiles/user_{user_id}_{platform}
    
    For default user (user_id is None or 1), maintains full backwards
    compatibility with legacy profile locations:
    - LinkedIn: ~/.jobpilot-chrome-profile (or fallback ~/.apply-and-pray-chrome-profile)
    - Naukri: ~/.jobpilot-naukri-profile (or fallback ~/.apply-and-pray-naukri-profile)
    """
    plat = platform.strip().lower()
    
    if user_id is not None and user_id > 1:
        base_dir = os.path.expanduser(f"~/.jobpilot/profiles/user_{user_id}_{plat}")
        make_directories([base_dir])
        return base_dir

    if plat == "naukri":
        primary = os.path.expanduser("~/.jobpilot-naukri-profile")
        fallback = os.path.expanduser("~/.apply-and-pray-naukri-profile")
        if not os.path.exists(primary) and os.path.exists(fallback):
            return fallback
        return primary
    elif plat == "indeed":
        return os.path.expanduser("~/.jobpilot-indeed-profile")
    elif plat == "foundit":
        return os.path.expanduser("~/.jobpilot-foundit-profile")
    elif plat == "glassdoor":
        return os.path.expanduser("~/.jobpilot-glassdoor-profile")
    else:
        # Default: LinkedIn / General
        primary = os.path.expanduser("~/.jobpilot-chrome-profile")
        fallback = os.path.expanduser("~/.apply-and-pray-chrome-profile")
        if not os.path.exists(primary) and os.path.exists(fallback):
            return fallback
        return primary
