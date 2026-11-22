"""Unit and regression tests for JobPilot UpdateService and auto-update architecture."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import urllib.error

from app.services.update_service import (
    ReleaseAsset,
    UpdateInfo,
    UpdateService,
    is_newer_version,
    normalize_version,
)


class TestUpdateVersioning(unittest.TestCase):
    """Tests for version normalization and semantic version comparisons."""

    def test_normalize_version(self):
        self.assertEqual(normalize_version("v1.2.3"), "1.2.3")
        self.assertEqual(normalize_version("V0.5.0-beta"), "0.5.0-beta")
        self.assertEqual(normalize_version("  0.4.8  "), "0.4.8")
        self.assertEqual(normalize_version(""), "")

    def test_newer_version_detection(self):
        self.assertTrue(is_newer_version("0.5.0", "0.4.8"))
        self.assertTrue(is_newer_version("v0.5.0", "0.4.8-beta"))
        self.assertTrue(is_newer_version("1.0.0", "0.9.9"))
        self.assertTrue(is_newer_version("0.4.9", "0.4.8"))
        # Final release is newer than beta of same version
        self.assertTrue(is_newer_version("0.4.8", "0.4.8-beta"))

    def test_same_or_older_version_ignored(self):
        self.assertFalse(is_newer_version("0.4.8", "0.4.8"))
        self.assertFalse(is_newer_version("v0.4.8", "0.4.8"))
        self.assertFalse(is_newer_version("0.4.7", "0.4.8"))
        self.assertFalse(is_newer_version("0.3.0", "0.4.8-beta"))

    def test_invalid_versions_handled_safely(self):
        self.assertFalse(is_newer_version("", "0.4.8"))
        self.assertFalse(is_newer_version("invalid", "0.4.8"))
        self.assertFalse(is_newer_version("0.5.0", ""))


class TestUpdateAssetResolution(unittest.TestCase):
    """Tests for mapping GitHub release assets to client operating systems."""

    def setUp(self):
        self.service = UpdateService(current_version="0.4.8-beta")
        self.mock_assets = [
            {
                "name": "JobPilot-0.5.0-windows-x64.zip",
                "browser_download_url": "https://github.com/test/download/win.zip",
                "size": 75000000,
                "content_type": "application/zip",
                "created_at": "2026-11-22T10:00:00Z",
            },
            {
                "name": "JobPilot-0.5.0-x86_64.AppImage",
                "browser_download_url": "https://github.com/test/download/appimage",
                "size": 82000000,
                "content_type": "application/x-executable",
                "created_at": "2026-11-22T10:00:00Z",
            },
            {
                "name": "JobPilot-0.5.0.dmg",
                "browser_download_url": "https://github.com/test/download/mac.dmg",
                "size": 90000000,
                "content_type": "application/octet-stream",
                "created_at": "2026-11-22T10:00:00Z",
            },
        ]

    @patch("app.services.os.app_paths.AppPaths.is_windows", return_value=True)
    @patch("app.services.os.app_paths.AppPaths.is_linux", return_value=False)
    @patch("app.services.os.app_paths.AppPaths.is_macos", return_value=False)
    def test_windows_asset_resolution(self, *mocks):
        asset = self.service.get_best_asset_for_platform(self.mock_assets)
        self.assertIsNotNone(asset)
        self.assertTrue(asset.name.endswith(".zip"))
        self.assertIn("win", asset.name.lower())

    @patch("app.services.os.app_paths.AppPaths.is_windows", return_value=False)
    @patch("app.services.os.app_paths.AppPaths.is_linux", return_value=True)
    @patch("app.services.os.app_paths.AppPaths.is_macos", return_value=False)
    def test_linux_asset_resolution(self, *mocks):
        asset = self.service.get_best_asset_for_platform(self.mock_assets)
        self.assertIsNotNone(asset)
        self.assertTrue(asset.name.endswith(".AppImage"))

    @patch("app.services.os.app_paths.AppPaths.is_windows", return_value=False)
    @patch("app.services.os.app_paths.AppPaths.is_linux", return_value=False)
    @patch("app.services.os.app_paths.AppPaths.is_macos", return_value=True)
    def test_macos_asset_resolution(self, *mocks):
        asset = self.service.get_best_asset_for_platform(self.mock_assets)
        self.assertIsNotNone(asset)
        self.assertTrue(asset.name.endswith(".dmg"))


class TestUpdateServiceExecution(unittest.TestCase):
    """Tests for GitHub API querying, rate limit handling, and failure modes."""

    def setUp(self):
        self.service = UpdateService(repo="Ahmad01Ansari/JobPilot", current_version="0.4.8-beta")

    @patch("urllib.request.urlopen")
    def test_check_for_updates_available(self, mock_urlopen):
        payload = {
            "tag_name": "v0.5.0",
            "name": "JobPilot Release v0.5.0",
            "body": "- Enhanced Foundit apply\n- Real-time KPI update",
            "html_url": "https://github.com/Ahmad01Ansari/JobPilot/releases/tag/v0.5.0",
            "published_at": "2026-11-22T12:00:00Z",
            "prerelease": False,
            "assets": [
                {
                    "name": "JobPilot-0.5.0-x86_64.AppImage",
                    "browser_download_url": "https://github.com/Ahmad01Ansari/JobPilot/releases/download/v0.5.0/JobPilot-0.5.0-x86_64.AppImage",
                    "size": 85000000,
                    "content_type": "application/x-executable",
                }
            ],
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        update = self.service.check_for_updates()
        self.assertIsNotNone(update)
        self.assertEqual(update.version, "0.5.0")
        self.assertEqual(update.tag_name, "v0.5.0")
        self.assertIn("Foundit", update.release_notes)
        self.assertIsNotNone(update.asset)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_already_up_to_date(self, mock_urlopen):
        payload = {
            "tag_name": "v0.4.8-beta",
            "name": "JobPilot v0.4.8-beta",
            "body": "Existing release notes",
            "html_url": "https://github.com/Ahmad01Ansari/JobPilot/releases/tag/v0.4.8-beta",
            "published_at": "2026-11-20T12:00:00Z",
            "prerelease": True,
            "assets": [],
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        update = self.service.check_for_updates()
        self.assertIsNone(update)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_handles_rate_limit_or_http_errors(self, mock_urlopen):
        mock_urlopen.side_effect = urllib.error.HTTPError("url", 403, "Rate Limited", {}, None)
        update = self.service.check_for_updates()
        self.assertIsNone(update)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_handles_network_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = TimeoutError("Connection timed out")
        update = self.service.check_for_updates()
        self.assertIsNone(update)


if __name__ == "__main__":
    unittest.main()

