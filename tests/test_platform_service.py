"""Unit and UI test suite for PlatformService, SettingsService, and Phase 9 views."""

import os
import shutil
import tempfile
import unittest

from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.services.platform_service import PlatformService
from app.services.settings_service import SettingsService


class TestPlatformAndSettingsServices(unittest.TestCase):
    """Unit tests for PlatformService and SettingsService business logic."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase9_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.platform_service = PlatformService(session_factory=self.Session)
        self.settings_service = SettingsService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_seed_default_platforms(self):
        """Verifies seeding creates 6 platforms idempotently."""
        platforms = self.platform_service.seed_default_platforms()
        self.assertEqual(len(platforms), 6)

        names = {p.name for p in platforms}
        self.assertEqual(names, {"linkedin", "naukri", "indeed", "foundit", "glassdoor", "email"})

        # Verify enabled state
        p_li = self.platform_service.get_platform_by_name("linkedin")
        self.assertTrue(p_li.is_enabled)
        p_in = self.platform_service.get_platform_by_name("indeed")
        self.assertFalse(p_in.is_enabled)
        p_fo = self.platform_service.get_platform_by_name("foundit")
        self.assertTrue(p_fo.is_enabled)
        p_em = self.platform_service.get_platform_by_name("email")
        self.assertTrue(p_em.is_enabled)

        # Idempotent re-seed
        re_seeded = self.platform_service.seed_default_platforms()
        self.assertEqual(len(re_seeded), 6)

    def test_toggle_platform(self):
        """Verifies platform enable/disable toggling."""
        self.platform_service.seed_default_platforms()

        # LinkedIn starts enabled
        new_state, err = self.platform_service.toggle_platform("linkedin")
        self.assertIsNone(err)
        self.assertFalse(new_state)

        # Toggle back
        new_state, err = self.platform_service.toggle_platform("linkedin")
        self.assertIsNone(err)
        self.assertTrue(new_state)

        # Toggle non-existent platform
        fail_state, fail_err = self.platform_service.toggle_platform("unknown")
        self.assertFalse(fail_state)
        self.assertIn("not found", fail_err)

    def test_save_and_get_platform_config(self):
        """Verifies updating platform account runtime parameters."""
        self.platform_service.seed_default_platforms()

        success, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            default_location="Bengaluru, India",
            experience_years=6,
            max_applications=45,
            apply_mode="ALL",
            pause_before_submit=True,
            stealth_mode=True,
            safe_mode=False,
            max_pages_per_search=7,
            consecutive_skips_limit=18,
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        cfg = self.platform_service.get_platform_config("linkedin")
        self.assertEqual(cfg["default_location"], "Bengaluru, India")
        self.assertEqual(cfg["experience_years"], 6)
        self.assertEqual(cfg["max_applications"], 45)
        self.assertEqual(cfg["apply_mode"], "ALL")
        self.assertTrue(cfg["pause_before_submit"])
        self.assertFalse(cfg["safe_mode"])
        self.assertEqual(cfg["max_pages_per_search"], 7)
        self.assertEqual(cfg["consecutive_skips_limit"], 18)

    def test_save_platform_config_validations(self):
        """Verifies invalid parameters are rejected."""
        self.platform_service.seed_default_platforms()

        # Negative experience (not -1)
        ok, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            experience_years=-5,
        )
        self.assertFalse(ok)
        self.assertIn("cannot be negative", err)

        # Zero max applications
        ok, err = self.platform_service.save_platform_config(
            platform_name="linkedin",
            max_applications=0,
        )
        self.assertFalse(ok)
        self.assertIn("greater than 0", err)

    def test_save_and_get_search_config(self):
        """Verifies saving and retrieving search criteria keywords and filters."""
        self.platform_service.seed_default_platforms()

        success, err = self.platform_service.save_search_config(
            platform_name="linkedin",
            search_terms=["AI Engineer", "MLOps Engineer"],
            search_location="Hyderabad",
            experience_years=4,
            date_posted="Past 24 hours",
            easy_apply_only=True,
            max_pages_per_search=5,
            switch_number=25,
            consecutive_skips_limit=8,
            bad_words=["Polygraph", "US Only"],
            negative_title_words=["intern", "manager"],
        )
        self.assertTrue(success)
        self.assertIsNone(err)

        res = self.platform_service.get_search_config("linkedin")
        self.assertEqual(res["search_terms"], ["AI Engineer", "MLOps Engineer"])
        self.assertEqual(res["search_location"], "Hyderabad")
        self.assertEqual(res["experience_years"], 4)
        self.assertEqual(res["date_posted"], "Past 24 hours")
        self.assertEqual(res["max_pages_per_search"], 5)
        self.assertEqual(res["switch_number"], 25)
        self.assertEqual(res["consecutive_skips_limit"], 8)
        self.assertEqual(res["bad_words"], ["Polygraph", "US Only"])
        self.assertEqual(res["negative_title_words"], ["intern", "manager"])

    def test_save_search_config_requires_terms(self):
        """Verifies saving with empty search terms is rejected."""
        self.platform_service.seed_default_platforms()

        ok, err = self.platform_service.save_search_config(
            platform_name="linkedin",
            search_terms=[],
            search_location="India",
        )
        self.assertFalse(ok)
        self.assertIn("At least one search keyword is required", err)

    def test_settings_service_seed_and_get(self):
        """Verifies settings defaults seeding and typed retrieval."""
        self.settings_service.seed_defaults_if_empty()

        click_gap = self.settings_service.get_setting("click_gap")
        self.assertEqual(click_gap, 1)

        safe_mode = self.settings_service.get_setting("safe_mode")
        self.assertTrue(safe_mode)

        run_bg = self.settings_service.get_setting("run_in_background")
        self.assertFalse(run_bg)

    def test_settings_save_and_batch_update(self):
        """Verifies saving individual and batch settings."""
        self.settings_service.seed_defaults_if_empty()

        # Single save
        ok, err = self.settings_service.save_setting("click_gap", 3)
        self.assertTrue(ok)
        self.assertIsNone(err)
        self.assertEqual(self.settings_service.get_setting("click_gap"), 3)

        # Batch save
        batch_payload = {
            "click_gap": 2,
            "smooth_scroll": True,
            "run_in_background": True,
        }
        ok_batch, err_batch = self.settings_service.save_batch(batch_payload)
        self.assertTrue(ok_batch)
        self.assertIsNone(err_batch)

        self.assertEqual(self.settings_service.get_setting("click_gap"), 2)
        self.assertTrue(self.settings_service.get_setting("smooth_scroll"))
        self.assertTrue(self.settings_service.get_setting("run_in_background"))

    def test_settings_reset_category(self):
        """Verifies resetting a category restores its original default values."""
        self.settings_service.seed_defaults_if_empty()

        # Alter browser settings
        self.settings_service.save_setting("run_in_background", True)
        self.settings_service.save_setting("safe_mode", False)

        self.assertTrue(self.settings_service.get_setting("run_in_background"))
        self.assertFalse(self.settings_service.get_setting("safe_mode"))

        # Reset category
        ok, err = self.settings_service.reset_category_to_defaults("browser")
        self.assertTrue(ok)
        self.assertIsNone(err)

        # Should be back to defaults
        self.assertFalse(self.settings_service.get_setting("run_in_background"))
        self.assertTrue(self.settings_service.get_setting("safe_mode"))

    def test_save_search_config_with_cycle_options(self):
        """Verifies cycle controls and automation options are saved and retrieved."""
        self.platform_service.seed_default_platforms()

        ok, err = self.platform_service.save_search_config(
            platform_name="linkedin",
            search_terms=["RPA Developer"],
            search_location="Noida",
            run_non_stop=True,
            cycle_date_posted=True,
            alternate_sortby=True,
            stop_date_cycle_at_24hr=True,
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

        cfg = self.platform_service.get_search_config("linkedin")
        self.assertTrue(cfg.get("run_non_stop"))
        self.assertTrue(cfg.get("cycle_date_posted"))
        self.assertTrue(cfg.get("alternate_sortby"))
        self.assertTrue(cfg.get("stop_date_cycle_at_24hr"))

    def test_sync_search_config_to_all_platforms(self):
        """Verifies sync_to_all_platforms atomically applies search criteria across all 4 platforms."""
        self.platform_service.seed_default_platforms()

        ok, err = self.platform_service.save_search_config(
            platform_name="linkedin",
            search_terms=["Lead AI Engineer"],
            search_location="Bangalore",
            experience_years=5,
            run_non_stop=True,
            sync_to_all_platforms=True,
        )
        self.assertTrue(ok)
        self.assertIsNone(err)

        for plat_name in ["linkedin", "naukri", "indeed", "glassdoor"]:
            cfg = self.platform_service.get_search_config(plat_name)
            self.assertEqual(cfg.get("search_terms"), ["Lead AI Engineer"])
            self.assertEqual(cfg.get("search_location"), "Bangalore")
            self.assertEqual(cfg.get("experience_years"), 5)
            self.assertTrue(cfg.get("run_non_stop"))

    def test_keyword_extractor_service(self):
        """Verifies KeywordExtractorService provides positive keywords and domain exclusions."""
        from app.services.keyword_extractor_service import KeywordExtractorService

        extractor = KeywordExtractorService()
        result = extractor.extract_from_profile(
            title="Senior RPA Developer",
            skills=["Automation Anywhere", "Python", "SAP Automation", "OCR"],
            summary="Enterprise RPA bot developer",
        )

        # Check positive keywords
        self.assertIn("RPA Developer", result["search_terms"])
        self.assertIn("Automation Anywhere Developer", result["search_terms"])

        # Check negative domain exclusions (should exclude android, react, flutter etc.)
        negatives = [k.lower() for k in result["negative_title_words"]]
        self.assertIn("android", negatives)
        self.assertIn("full stack", negatives)
        self.assertIn("react", negatives)
        self.assertIn("php", negatives)
        self.assertIn("flutter", negatives)

        # Check bad words
        self.assertTrue(any("unpaid" in w.lower() for w in result["bad_words"]))



class TestPhase9Views(unittest.TestCase):
    """Headless UI tests for PlatformsView, SearchView, and SettingsView."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "phase9_view_test.db")
        self.db_url = f"sqlite:///{self.db_path}"

        self.engine = create_engine(self.db_url, future=True)
        event.listen(self.engine, "connect", configure_sqlite_pragmas)
        Base.metadata.create_all(bind=self.engine)

        self.Session = sessionmaker(
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            bind=self.engine,
            future=True,
        )
        self.platform_service = PlatformService(session_factory=self.Session)
        self.settings_service = SettingsService(session_factory=self.Session)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_platforms_view_rendering(self):
        """Verifies PlatformsView renders 4 cards and handles refresh."""
        from app.ui.views.platforms_view import PlatformsView

        view = PlatformsView(service=self.platform_service)
        view.show()

        # Grid should contain 6 platform cards + 1 Coming Soon card
        self.assertEqual(view.grid.count(), 7)
        self.assertIn("Platform Connections", view.header.title_label.text())

    def test_search_view_rendering_and_interaction(self):
        """Verifies SearchView populates keywords and handles save."""
        from app.ui.views.search_view import SearchView

        # Seed defaults
        self.platform_service.seed_default_platforms()

        view = SearchView(service=self.platform_service)
        view.show()

        # Check default loaded search terms
        tags = view.tag_search_terms.get_tags()
        self.assertGreater(len(tags), 0)

        # Add a keyword
        view.tag_search_terms.txt_input.setText("Cloud Architect")
        view.tag_search_terms._add_tag()
        self.assertIn("Cloud Architect", view.tag_search_terms.get_tags())

        # Click save
        view.btn_save.click()
        self.assertTrue(view.notification_bar.isVisible())
        self.assertIn("updated successfully", view.notification_bar.message_label.text())

    def test_settings_view_rendering_and_save(self):
        """Verifies SettingsView renders tabs, saves batch changes, and resets category."""
        from app.ui.views.settings_view import SettingsView

        view = SettingsView(service=self.settings_service)
        view.show()

        # Check at least 4 tabs present (Phase 14 expands to 6 tabs)
        self.assertGreaterEqual(view.tabs.count(), 4)


        # Change setting
        view.spn_click_gap.setValue(4)
        view.btn_save.click()
        self.assertTrue(view.notification_bar.isVisible())
        self.assertIn("saved successfully", view.notification_bar.message_label.text())

        # Verify persisted
        val = self.settings_service.get_setting("click_gap")
        self.assertEqual(val, 4)

        # Reset category
        view.btn_reset.click()
        self.assertIn("Reset", view.notification_bar.message_label.text())

    def test_naukri_config_dialog_and_card_customization(self):
        """Verifies Naukri removes unsupported Easy Apply/Hybrid mode and shows Freshness chip."""
        from app.ui.views.platforms_view import PlatformCard, PlatformConfigDialog

        self.platform_service.seed_default_platforms()

        # 1. Dialog check
        dlg = PlatformConfigDialog("naukri", service=self.platform_service)
        self.assertFalse(hasattr(dlg, "cmb_apply_mode"))
        self.assertTrue(hasattr(dlg, "cmb_freshness"))
        self.assertEqual(dlg.cmb_freshness.count(), 5)

        # 2. Card check
        card = PlatformCard("naukri", service=self.platform_service, on_changed_callback=None)
        self.assertIn("freshness", card.chip_val_labels)
        self.assertNotIn("mode", card.chip_val_labels)
        self.assertIn("Days", card.chip_val_labels["freshness"].text())

    def test_linkedin_config_dialog_customization(self):
        """Verifies LinkedIn preserves Easy Apply / Hybrid mode selector."""
        from app.ui.views.platforms_view import PlatformCard, PlatformConfigDialog

        self.platform_service.seed_default_platforms()

        dlg = PlatformConfigDialog("linkedin", service=self.platform_service)
        self.assertTrue(hasattr(dlg, "cmb_apply_mode"))
        self.assertTrue(hasattr(dlg, "cmb_freshness"))

        card = PlatformCard("linkedin", service=self.platform_service, on_changed_callback=None)
        self.assertIn("mode", card.chip_val_labels)


if __name__ == "__main__":
    unittest.main()
