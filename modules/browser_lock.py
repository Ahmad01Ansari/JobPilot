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


def find_pids_for_profile(profile_dir: str) -> list[int]:
    """Finds process IDs of Chrome instances using the given profile directory."""
    if not profile_dir or not os.path.exists(profile_dir):
        return []
    pids = []
    norm_target = os.path.normpath(profile_dir).lower()

    if sys.platform == "win32" or os.name == "nt":
        try:
            import subprocess
            import json
            ps_script = (
                "Get-CimInstance Win32_Process -Filter \"name = 'chrome.exe'\" "
                "| Select-Object ProcessId, CommandLine "
                "| ConvertTo-Json -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                items = data if isinstance(data, list) else [data]
                for item in items:
                    cmd = (item.get("CommandLine") or "").lower().replace("/", "\\")
                    pid = item.get("ProcessId")
                    if pid and norm_target in cmd:
                        pids.append(int(pid))
        except Exception:
            pass
    else:
        try:
            import subprocess
            res = subprocess.run(
                ["pgrep", "-f", f"user-data-dir=.*{re.escape(os.path.basename(profile_dir))}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0:
                for line in res.stdout.strip().splitlines():
                    if line.strip().isdigit():
                        pids.append(int(line.strip()))
        except Exception:
            pass

    return pids


def cleanup_stale_profile_locks(profile_dir: str) -> None:
    """Safely cleans up orphaned SingletonLock, SingletonCookie, SingletonSocket, and lockfile files.
    
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

    lock_files = ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]
    for item in lock_files:
        path = os.path.join(profile_dir, item)
        if os.path.islink(path) or os.path.exists(path):
            pid = extract_pid_from_lock(path)
            # If PID is detected and confirmed alive, do not touch (another active browser session)
            if pid is not None and is_pid_alive(pid):
                print_lg(f"[BrowserLock] Chrome process {pid} is actively using profile at {profile_dir}.")
                continue

            # On Windows, lockfile may exist with active Chrome processes lacking SingletonLock
            if item == "lockfile" and (sys.platform == "win32" or os.name == "nt"):
                active_pids = find_pids_for_profile(profile_dir)
                if active_pids:
                    print_lg(f"[BrowserLock] Active Chrome process(es) {active_pids} using profile at {profile_dir}.")
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

    # 1. Check primary SingletonLock PID (POSIX)
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

    # 2. Comprehensive check for any Chrome processes using this profile directory (Windows & POSIX)
    active_pids = find_pids_for_profile(profile_dir)
    if active_pids:
        from app.services.os.process_manager import ProcessManager
        for pid in active_pids:
            if is_pid_alive(pid):
                try:
                    print_lg(f"[BrowserLock] Terminating lingering Chrome process {pid} using profile {profile_dir}...")
                    ProcessManager.kill_process_tree(pid, timeout_seconds=1.5)
                except Exception as e:
                    print_lg(f"[BrowserLock] Notice terminating process {pid}: {e}")

    # 3. Remove all lock files now that processes are cleared
    for item in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
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
    <user_data_dir>/profiles/user_{user_id}_{platform}
    
    For default user (user_id is None or 1), maintains full backwards
    compatibility with legacy profile locations:
    - LinkedIn: ~/.jobpilot-chrome-profile (or fallback ~/.apply-and-pray-chrome-profile)
    - Naukri: ~/.jobpilot-naukri-profile (or fallback ~/.apply-and-pray-naukri-profile)
    - Windows AppData fallback if legacy does not exist.
    """
    from app.services.os.app_paths import AppPaths
    plat = platform.strip().lower()
    user_data = AppPaths.get_user_data_dir()
    
    if user_id is not None and user_id > 1:
        base_dir = str(user_data / "profiles" / f"user_{user_id}_{plat}")
        make_directories([base_dir])
        return base_dir

    if plat == "naukri":
        primary = os.path.expanduser("~/.jobpilot-naukri-profile")
        fallback = os.path.expanduser("~/.apply-and-pray-naukri-profile")
        if not os.path.exists(primary) and os.path.exists(fallback):
            return fallback
        if not os.path.exists(primary) and AppPaths.is_windows():
            win_prof = str(user_data / "profiles" / "naukri")
            make_directories([win_prof])
            return win_prof
        return primary
    elif plat == "indeed":
        primary = os.path.expanduser("~/.jobpilot-indeed-profile")
        if not os.path.exists(primary) and AppPaths.is_windows():
            win_prof = str(user_data / "profiles" / "indeed")
            make_directories([win_prof])
            return win_prof
        return primary
    elif plat == "foundit":
        primary = os.path.expanduser("~/.jobpilot-foundit-profile")
        if not os.path.exists(primary) and AppPaths.is_windows():
            win_prof = str(user_data / "profiles" / "foundit")
            make_directories([win_prof])
            return win_prof
        return primary
    elif plat == "glassdoor":
        primary = os.path.expanduser("~/.jobpilot-glassdoor-profile")
        if not os.path.exists(primary) and AppPaths.is_windows():
            win_prof = str(user_data / "profiles" / "glassdoor")
            make_directories([win_prof])
            return win_prof
        return primary
    else:
        # Default: LinkedIn / General
        primary = os.path.expanduser("~/.jobpilot-chrome-profile")
        fallback = os.path.expanduser("~/.apply-and-pray-chrome-profile")
        if not os.path.exists(primary) and os.path.exists(fallback):
            return fallback
        if not os.path.exists(primary) and AppPaths.is_windows():
            win_prof = str(user_data / "profiles" / "linkedin")
            make_directories([win_prof])
            return win_prof
        return primary
