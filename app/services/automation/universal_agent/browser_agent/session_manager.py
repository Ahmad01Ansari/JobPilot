"""Universal browser profile and session persistence manager."""

import os
from pathlib import Path
from typing import Any, Dict, Optional


class UniversalSessionManager:
    """Manages isolated browser user profile directories, viewports, and launch configs."""

    DEFAULT_PROFILE_DIR = os.path.expanduser("~/.jobpilot-universal-profile")
    DEFAULT_VIEWPORT = {"width": 1280, "height": 800}

    def __init__(self, profile_dir: Optional[str] = None) -> None:
        self.profile_dir = profile_dir or self.DEFAULT_PROFILE_DIR
        self._ensure_profile_dir()

    def _ensure_profile_dir(self) -> None:
        """Ensures the profile directory exists with safe directory permissions."""
        os.makedirs(self.profile_dir, mode=0o700, exist_ok=True)
        try:
            from modules.browser_lock import extract_pid_from_lock, is_pid_alive, cleanup_stale_profile_locks
            import signal, time
            lock_path = os.path.join(self.profile_dir, "SingletonLock")
            pid = extract_pid_from_lock(lock_path)
            if pid and is_pid_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.5)
                except Exception:
                    pass
            cleanup_stale_profile_locks(self.profile_dir)
        except Exception:
            pass

        # Pre-seed Chrome preferences to automatically deny geolocation and notification prompts
        try:
            import json
            default_dir = os.path.join(self.profile_dir, "Default")
            os.makedirs(default_dir, exist_ok=True)
            pref_file = os.path.join(default_dir, "Preferences")
            prefs = {}
            if os.path.exists(pref_file):
                try:
                    with open(pref_file, "r", encoding="utf-8") as f:
                        prefs = json.load(f)
                except Exception:
                    prefs = {}
            if not isinstance(prefs, dict):
                prefs = {}
            profile = prefs.setdefault("profile", {})
            cd_settings = profile.setdefault("default_content_setting_values", {})
            cd_settings["geolocation"] = 2  # Block geolocation
            cd_settings["notifications"] = 2  # Block notifications
            with open(pref_file, "w", encoding="utf-8") as f:
                json.dump(prefs, f)
        except Exception:
            pass

    def get_user_data_dir(self) -> str:
        """Returns the absolute path to the persistent user data directory."""
        return self.profile_dir

    def get_launch_options(self, headless: bool = False, **overrides: Any) -> Dict[str, Any]:
        """Constructs standardized launch options for local_browser.launch."""
        downloads_dir = os.path.join(self.profile_dir, "downloads")
        os.makedirs(downloads_dir, exist_ok=True)
        options: Dict[str, Any] = {
            "user_data_dir": self.profile_dir,
            "headless": headless,
            "viewport_width": self.DEFAULT_VIEWPORT["width"] if headless else None,
            "viewport_height": self.DEFAULT_VIEWPORT["height"] if headless else None,
            "preserve_user_data_dir": True,
            "accept_downloads": True,
            "downloads_path": downloads_dir,
            "args": [
                "--start-maximized",
                "--no-default-browser-check",
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--deny-permission-prompts",
                "--disable-geolocation",
            ],
        }
        options.update(overrides)
        return options

    def clear_cookies(self) -> None:
        """Removes cookie files from profile directory to reset sessions if requested."""
        cookie_path = Path(self.profile_dir) / "Default" / "Cookies"
        if cookie_path.exists():
            try:
                cookie_path.unlink()
            except OSError:
                pass
