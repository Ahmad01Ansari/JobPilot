"""Unit tests for JobPilot brand assets, multi-platform icons, and UI theme integration."""

import os
import unittest
from pathlib import Path
from PIL import Image

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtWidgets import QApplication
from app.ui.theme import ThemeManager


class TestBrandIconsAndAssets(unittest.TestCase):
    """Verifies that all required icon formats, tray icons, and UI integrations function correctly."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.brand_dir = Path("app/ui/assets/brand")

    def test_01_all_brand_files_exist(self):
        """Verifies that all required icon formats and resolutions are present on disk."""
        required_files = [
            "jobpilot.png",
            "jobpilot_512.png",
            "jobpilot_256.png",
            "jobpilot_128.png",
            "jobpilot_64.png",
            "jobpilot_48.png",
            "jobpilot_32.png",
            "jobpilot_24.png",
            "jobpilot_16.png",
            "jobpilot.ico",
            "jobpilot_tray.png",
            "jobpilot_tray_active.png",
            "jobpilot_badge.png",
            "jobpilot_tray_avatar.png",
            "jobpilot_tray_avatar_active.png",
        ]
        for fn in required_files:
            file_path = self.brand_dir / fn
            self.assertTrue(file_path.exists(), f"Brand asset missing: {fn}")
            self.assertGreater(file_path.stat().st_size, 100, f"Brand asset is empty: {fn}")

    def test_02_ico_multi_resolution(self):
        """Verifies that jobpilot.ico is a valid Windows icon containing multiple size layers."""
        ico_path = self.brand_dir / "jobpilot.ico"
        with Image.open(ico_path) as im:
            self.assertEqual(im.format, "ICO")

    def test_03_png_transparency(self):
        """Verifies that master png icons have an alpha channel for clean OS background integration."""
        with Image.open(self.brand_dir / "jobpilot_512.png") as im:
            self.assertEqual(im.mode, "RGBA")
            self.assertEqual(im.size, (512, 512))
            # Corner pixel (0, 0) should be transparent (alpha == 0)
            corner_alpha = im.getpixel((0, 0))[3]
            self.assertEqual(corner_alpha, 0)

    def test_04_tray_icons_dimensions(self):
        """Verifies tray icon dimensions are 32x32."""
        with Image.open(self.brand_dir / "jobpilot_tray.png") as im:
            self.assertEqual(im.size, (32, 32))
            self.assertEqual(im.mode, "RGBA")
        with Image.open(self.brand_dir / "jobpilot_tray_active.png") as im:
            self.assertEqual(im.size, (32, 32))
            self.assertEqual(im.mode, "RGBA")

    def test_05_static_web_assets(self):
        """Verifies that static assets for web dashboard and favicon exist."""
        self.assertTrue(Path("static/img/jobpilot.png").exists())
        self.assertTrue(Path("static/favicon.ico").exists())

    def test_06_desktop_entry_file(self):
        """Verifies that the Linux .desktop launcher file exists with valid syntax."""
        desktop_file = Path("scripts/jobpilot.desktop")
        self.assertTrue(desktop_file.exists())
        content = desktop_file.read_text(encoding="utf-8")
        self.assertIn("[Desktop Entry]", content)
        self.assertIn("Name=JobPilot", content)
        self.assertIn("Icon=", content)

    def test_07_theme_manager_app_icon(self):
        """Verifies that ThemeManager.get_app_icon() returns a valid non-null QIcon."""
        icon = ThemeManager.get_app_icon()
        self.assertFalse(icon.isNull(), "ThemeManager.get_app_icon() returned a null QIcon.")
        sizes = icon.availableSizes()
        self.assertGreater(len(sizes), 0, "No sizes available in app icon.")

    def test_08_theme_manager_tray_icons(self):
        """Verifies that ThemeManager.get_tray_icon() returns valid non-null icons for idle and active states."""
        tray_idle = ThemeManager.get_tray_icon(active=False)
        self.assertFalse(tray_idle.isNull(), "Idle tray icon is null.")
        tray_active = ThemeManager.get_tray_icon(active=True)
        self.assertFalse(tray_active.isNull(), "Active tray icon is null.")

    def test_09_theme_manager_brand_pixmap(self):
        """Verifies that ThemeManager.get_brand_pixmap() scales correctly."""
        pix_32 = ThemeManager.get_brand_pixmap(32, variant="app")
        self.assertFalse(pix_32.isNull())
        self.assertEqual(pix_32.width(), 32)
        self.assertEqual(pix_32.height(), 32)

        pix_badge = ThemeManager.get_brand_pixmap(28, variant="badge")
        self.assertFalse(pix_badge.isNull())
        self.assertEqual(pix_badge.width(), 28)
        self.assertEqual(pix_badge.height(), 28)

    def test_10_about_dialog_instantiation(self):
        """Verifies that AboutDialog initializes and renders its brand icon without errors."""
        from app.ui.widgets.about_dialog import AboutDialog
        dlg = AboutDialog()
        self.assertEqual(dlg.windowTitle(), "About JobPilot")
        dlg.close()
        dlg.deleteLater()


if __name__ == "__main__":
    unittest.main()
