"""Cross-platform auto-update and release notification service for JobPilot AI."""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QThread, Signal

from app.services.os.app_paths import AppPaths
from app.services.os.system_service import SystemService
from app.version import __version__ as CURRENT_VERSION

logger = logging.getLogger(__name__)

DEFAULT_REPO = "Ahmad01Ansari/JobPilot"
GITHUB_API_URL = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_ALL_RELEASES_URL = "https://api.github.com/repos/{repo}/releases"


@dataclass
class ReleaseAsset:
    """Represents a downloadable binary or installer asset from a GitHub Release."""
    name: str
    download_url: str
    size_bytes: int
    content_type: str
    created_at: str


@dataclass
class UpdateInfo:
    """Represents release metadata for an available application update."""
    version: str
    tag_name: str
    release_name: str
    release_notes: str
    html_url: str
    published_at: str
    is_prerelease: bool
    asset: Optional[ReleaseAsset] = None


def normalize_version(version_str: str) -> str:
    """Strips leading 'v' or 'V' and extra whitespace from version string."""
    clean = (version_str or "").strip()
    if clean.lower().startswith("v"):
        clean = clean[1:].strip()
    return clean


def is_newer_version(remote_version: str, local_version: str) -> bool:
    """Compares two version strings semantically.

    Returns True if remote_version is strictly newer than local_version.
    Supports standard semver and beta/rc identifiers (e.g. 0.5.0 > 0.4.8-beta).
    """
    v_remote = normalize_version(remote_version)
    v_local = normalize_version(local_version)

    if not v_remote or not v_local:
        return False

    try:
        from packaging import version
        return version.parse(v_remote) > version.parse(v_local)
    except Exception:
        pass

    # Defensive fallback parser: split numbers and pre-release suffix
    def parse_simple(v: str) -> Tuple[int, int, int, str]:
        parts = v.split("-", 1)
        nums = parts[0].split(".")
        major = int(nums[0]) if len(nums) > 0 and nums[0].isdigit() else 0
        minor = int(nums[1]) if len(nums) > 1 and nums[1].isdigit() else 0
        patch = int(nums[2]) if len(nums) > 2 and nums[2].isdigit() else 0
        suffix = parts[1] if len(parts) > 1 else ""
        return (major, minor, patch, suffix)

    try:
        r_maj, r_min, r_pat, r_suf = parse_simple(v_remote)
        l_maj, l_min, l_pat, l_suf = parse_simple(v_local)

        if (r_maj, r_min, r_pat) > (l_maj, l_min, l_pat):
            return True
        if (r_maj, r_min, r_pat) == (l_maj, l_min, l_pat):
            # A version without suffix (final) is newer than a version with suffix (beta)
            if not r_suf and l_suf:
                return True
            if r_suf and l_suf:
                return r_suf > l_suf
        return False
    except Exception:
        return False


class UpdateService:
    """Manages update discovery, asset resolution, background downloads, and installation."""

    def __init__(self, repo: str = DEFAULT_REPO, current_version: str = CURRENT_VERSION):
        self.repo = repo
        self.current_version = current_version
        self._last_checked_time: Optional[float] = None
        self._cached_update: Optional[UpdateInfo] = None

    def get_updates_directory(self) -> Path:
        """Resolves and ensures the updates staging directory in user data storage."""
        updates_dir = AppPaths.get_user_data_dir() / "updates"
        updates_dir.mkdir(parents=True, exist_ok=True)
        return updates_dir

    def check_for_updates(
        self,
        include_prereleases: bool = False,
        timeout: int = 10,
    ) -> Optional[UpdateInfo]:
        """Queries GitHub Releases API to detect available updates for the current platform.

        Returns an UpdateInfo instance if a newer version is available, or None otherwise.
        """
        api_url = (
            GITHUB_ALL_RELEASES_URL.format(repo=self.repo)
            if include_prereleases
            else GITHUB_API_URL.format(repo=self.repo)
        )

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"JobPilot-Desktop/{self.current_version} ({sys.platform})",
        }

        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status != 200:
                    logger.warning("[UpdateService] GitHub API responded with status %s", response.status)
                    return None
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404:
                logger.info("[UpdateService] No published releases found for %s", self.repo)
            elif http_err.code == 403:
                logger.warning("[UpdateService] GitHub API rate limit reached.")
            else:
                logger.warning("[UpdateService] HTTP error checking updates: %s", http_err)
            return None
        except Exception as exc:
            logger.debug("[UpdateService] Network check failed: %s", exc)
            return None

        self._last_checked_time = time.time()

        # Handle list response vs single release object
        release_data = data[0] if isinstance(data, list) and data else data
        if not isinstance(release_data, dict):
            return None

        tag_name = release_data.get("tag_name", "")
        remote_version = normalize_version(tag_name)
        if not remote_version:
            return None

        if not is_newer_version(remote_version, self.current_version):
            logger.info(
                "[UpdateService] JobPilot is up to date (current: %s, latest: %s)",
                self.current_version,
                remote_version,
            )
            return None

        # Resolve asset matching the current client operating system
        raw_assets = release_data.get("assets", [])
        best_asset = self.get_best_asset_for_platform(raw_assets)

        info = UpdateInfo(
            version=remote_version,
            tag_name=tag_name,
            release_name=release_data.get("name") or f"JobPilot v{remote_version}",
            release_notes=release_data.get("body") or "Bug fixes and improvements.",
            html_url=release_data.get("html_url", f"https://github.com/{self.repo}/releases/tag/{tag_name}"),
            published_at=release_data.get("published_at", ""),
            is_prerelease=bool(release_data.get("prerelease", False)),
            asset=best_asset,
        )

        self._cached_update = info
        logger.info("[UpdateService] Update detected: %s (Asset: %s)", info.version, best_asset.name if best_asset else "None")
        return info

    def get_best_asset_for_platform(self, raw_assets: List[Dict[str, Any]]) -> Optional[ReleaseAsset]:
        """Maps raw GitHub release assets to the best match for the current operating system."""
        if not raw_assets:
            return None

        platform_matchers = []
        if AppPaths.is_windows():
            platform_matchers = [
                lambda name: name.endswith("-windows-x64.zip") or name.endswith("-win64.zip"),
                lambda name: name.endswith(".exe") and "setup" in name.lower(),
                lambda name: name.endswith(".zip") and "windows" in name.lower(),
                lambda name: name.endswith(".zip"),
            ]
        elif AppPaths.is_linux():
            platform_matchers = [
                lambda name: name.endswith(".AppImage"),
                lambda name: name.endswith(".deb"),
                lambda name: name.endswith(".tar.gz") and "linux" in name.lower(),
            ]
        elif AppPaths.is_macos():
            platform_matchers = [
                lambda name: name.endswith(".dmg"),
                lambda name: name.endswith(".zip") and "macos" in name.lower(),
                lambda name: name.endswith(".zip"),
            ]

        for matcher in platform_matchers:
            for item in raw_assets:
                name = item.get("name", "")
                if matcher(name):
                    return ReleaseAsset(
                        name=name,
                        download_url=item.get("browser_download_url", ""),
                        size_bytes=int(item.get("size", 0)),
                        content_type=item.get("content_type", "application/octet-stream"),
                        created_at=item.get("created_at", ""),
                    )

        # Fallback to first non-source asset
        for item in raw_assets:
            name = item.get("name", "")
            if not name.endswith(".txt") and not name.endswith(".sha256") and not name.endswith(".sig"):
                return ReleaseAsset(
                    name=name,
                    download_url=item.get("browser_download_url", ""),
                    size_bytes=int(item.get("size", 0)),
                    content_type=item.get("content_type", "application/octet-stream"),
                    created_at=item.get("created_at", ""),
                )
        return None

    def download_asset(
        self,
        asset: ReleaseAsset,
        destination_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Optional[Path]:
        """Streams asset download with real-time chunked progress reporting."""
        if not asset or not asset.download_url:
            return None

        target_dir = self.get_updates_directory()
        target_file = destination_path or (target_dir / asset.name)

        headers = {
            "User-Agent": f"JobPilot-Desktop/{self.current_version}",
        }
        req = urllib.request.Request(asset.download_url, headers=headers)

        total_bytes = asset.size_bytes
        downloaded_bytes = 0
        chunk_size = 64 * 1024  # 64 KB

        try:
            with urllib.request.urlopen(req, timeout=30) as response, open(target_file, "wb") as out_f:
                if total_bytes <= 0:
                    content_len = response.headers.get("Content-Length")
                    if content_len and content_len.isdigit():
                        total_bytes = int(content_len)

                while True:
                    if cancel_check and cancel_check():
                        logger.info("[UpdateService] Download cancelled by caller.")
                        out_f.close()
                        if target_file.exists():
                            target_file.unlink(missing_ok=True)
                        return None

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    out_f.write(chunk)
                    downloaded_bytes += len(chunk)

                    if progress_callback:
                        pct = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
                        progress_callback(downloaded_bytes, total_bytes, pct)

            logger.info("[UpdateService] Successfully downloaded asset: %s (%d bytes)", target_file, downloaded_bytes)
            return target_file
        except Exception as exc:
            logger.error("[UpdateService] Error downloading update asset: %s", exc)
            if target_file.exists():
                target_file.unlink(missing_ok=True)
            return None

    def apply_update(self, downloaded_asset_path: Path) -> Tuple[bool, str]:
        """Dispatches OS-specific non-destructive installation and prepares restart.

        Returns (success, message_or_instruction).
        """
        if not downloaded_asset_path.exists():
            return False, "Downloaded update package not found."

        file_name = downloaded_asset_path.name.lower()

        # ---------------------------------------------------------------------
        # Linux AppImage Direct Replacement
        # ---------------------------------------------------------------------
        if AppPaths.is_linux() and file_name.endswith(".appimage"):
            try:
                # Ensure execution permission
                AppPaths.safe_set_permissions(downloaded_asset_path, 0o755)

                current_appimage = os.environ.get("APPIMAGE")
                if current_appimage and os.path.exists(current_appimage):
                    # Prepare atomic swap script
                    swap_sh = self.get_updates_directory() / "swap_appimage.sh"
                    with open(swap_sh, "w") as f:
                        f.write(f"""#!/bin/sh
sleep 1
cp "{downloaded_asset_path}" "{current_appimage}"
chmod +x "{current_appimage}"
exec "{current_appimage}" &
""")
                    AppPaths.safe_set_permissions(swap_sh, 0o755)
                    subprocess.Popen(["/bin/sh", str(swap_sh)], close_fds=True)
                    return True, "AppImage updated. Restarting application..."

                # Standalone run
                subprocess.Popen([str(downloaded_asset_path)], close_fds=True)
                return True, "Launched new AppImage."
            except Exception as e:
                return False, f"Failed to apply AppImage update: {e}"

        # ---------------------------------------------------------------------
        # Windows Zip / Installer Detached Replacement
        # ---------------------------------------------------------------------
        if AppPaths.is_windows() and (file_name.endswith(".zip") or file_name.endswith(".exe")):
            try:
                current_exe = sys.executable
                app_dir = Path(current_exe).parent

                if file_name.endswith(".exe"):
                    # Launch installer
                    subprocess.Popen([str(downloaded_asset_path)], shell=True)
                    return True, "Launched installer. Please follow instructions."

                # Batch script to wait for process exit, extract zip, and relaunch
                helper_bat = self.get_updates_directory() / "update_helper.bat"
                with open(helper_bat, "w") as f:
                    f.write(f"""@echo off
timeout /t 2 /nobreak > nul
tar -xf "{downloaded_asset_path}" -C "{app_dir}"
start "" "{current_exe}"
del "%~f0"
""")
                subprocess.Popen([str(helper_bat)], shell=True, close_fds=True)
                return True, "Update scheduled. Restarting JobPilot..."
            except Exception as e:
                return False, f"Failed to prepare Windows update: {e}"

        # ---------------------------------------------------------------------
        # Default: Open downloaded file / directory in OS file manager
        # ---------------------------------------------------------------------
        success, err = SystemService.open_file_or_dir(downloaded_asset_path)
        if success:
            return True, f"Opened {downloaded_asset_path.name} in file manager. Please install and restart."
        return False, err or "Failed to open update file."


class UpdateCheckWorker(QThread):
    """Background worker that queries GitHub Releases without freezing UI."""

    update_found = Signal(object)      # UpdateInfo
    update_not_found = Signal()
    check_error = Signal(str)

    def __init__(self, service: UpdateService, include_prereleases: bool = False, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.service = service
        self.include_prereleases = include_prereleases

    def run(self) -> None:
        try:
            info = self.service.check_for_updates(include_prereleases=self.include_prereleases)
            if info:
                self.update_found.emit(info)
            else:
                self.update_not_found.emit()
        except Exception as exc:
            self.check_error.emit(str(exc))


class UpdateDownloadWorker(QThread):
    """Background worker that streams update binary downloads with progress signals."""

    download_progress = Signal(int, int, float)   # (downloaded_bytes, total_bytes, percent)
    download_finished = Signal(object)           # Path
    download_error = Signal(str)

    def __init__(self, service: UpdateService, asset: ReleaseAsset, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.service = service
        self.asset = asset
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        def on_prog(down, total, pct):
            self.download_progress.emit(down, total, pct)

        try:
            path = self.service.download_asset(
                asset=self.asset,
                progress_callback=on_prog,
                cancel_check=lambda: self._cancelled,
            )
            if path and not self._cancelled:
                self.download_finished.emit(path)
            elif not self._cancelled:
                self.download_error.emit("Download failed or timed out.")
        except Exception as exc:
            self.download_error.emit(str(exc))

