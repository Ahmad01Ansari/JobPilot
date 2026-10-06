"""Comprehensive unit test suite for the redesigned Job Search Strategy workspace."""

import os
import shutil
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.platform_service import PlatformService
from app.ui.views.search_view import SearchView
from app.ui.widgets.search import (
    SearchAutomationCard,
    SearchKeywordInput,
    SearchLocationCard,
    SearchPlatformsCard,
    SearchPreferencesCard,
    SearchPreviewDialog,
    SearchSkipRulesCard,
    SearchStickyBar,
    SearchSummaryCard,
)

app = QApplication.instance() or QApplication(["--platform", "offscreen"])


class TestSearchUIStrategy(unittest.TestCase):
    """Test suite covering the ATS-style Search Strategy workspace and modular cards."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_search_strategy.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

        self.platform_service = PlatformService(session_factory=self.Session)
        self.platform_service.seed_default_platforms()

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_search_view_initialization_and_summary(self):
        """Verifies SearchView initializes with seeded platform config and summary card."""
        view = SearchView(service=self.platform_service)
        view.show()

        # Check search terms loaded
        tags = view.tag_search_terms.get_tags()
        self.assertGreater(len(tags), 0)

        # Summary card shows ready health
        self.assertIn("Strategy Ready", view.summary_card.lbl_health.text())
        self.assertFalse(view.sticky_bar._is_dirty)

    def test_target_roles_tag_input_operations(self):
        """Verifies adding, comma-separated pasting, deduplication, and tag removal."""
        tag_input = SearchKeywordInput(badge_prefix="roles")

        # Comma paste
        tag_input.txt_input.setText("AI Automation Engineer, RPA Lead, AI Automation Engineer")
        tag_input._add_tag()

        tags = tag_input.get_tags()
        self.assertEqual(len(tags), 2)
        self.assertIn("AI Automation Engineer", tags)
        self.assertIn("RPA Lead", tags)
        self.assertEqual(tag_input.lbl_count.text(), "2 roles")

        # Remove a tag
        tag_input._remove_tag("RPA Lead")
        self.assertEqual(tag_input.get_tags(), ["AI Automation Engineer"])
        self.assertEqual(tag_input.lbl_count.text(), "1 roles")

    def test_summary_card_health_transitions(self):
        """Verifies health badge updates when keywords or location are cleared."""
        view = SearchView(service=self.platform_service)
        view.show()

        # Clear keywords -> Expect No Target Keywords
        view.tag_search_terms.clear()
        view._update_summary_card()
        self.assertIn("No Target Keywords", view.summary_card.lbl_health.text())

        # Add keyword back -> Expect Strategy Ready
        view.tag_search_terms.txt_input.setText("Python Automation")
        view.tag_search_terms._add_tag()
        view._update_summary_card()
        self.assertIn("Strategy Ready", view.summary_card.lbl_health.text())

        # Clear location -> Expect Location Unstated
        view.txt_location.clear()
        view._update_summary_card()
        self.assertIn("Location Unstated", view.summary_card.lbl_health.text())

    def test_quick_location_suggestions(self):
        """Verifies clicking quick location pills updates the location text field."""
        view = SearchView(service=self.platform_service)
        view.show()

        view.location_card._apply_location("Bangalore")
        self.assertEqual(view.txt_location.text(), "Bangalore")
        self.assertTrue(view.sticky_bar._is_dirty)

    def test_platform_switching_and_loading(self):
        """Verifies changing platform combo reloads that platform's search criteria."""
        view = SearchView(service=self.platform_service)
        view.show()

        # Switch to Naukri
        view.cmb_platform.setCurrentText("Naukri")
        self.assertFalse(view.sticky_bar._is_dirty)

        # Switch to LinkedIn
        view.cmb_platform.setCurrentText("LinkedIn")
        self.assertFalse(view.sticky_bar._is_dirty)

    def test_preset_loaders(self):
        """Verifies RPA domain exclusions and standard blacklists can be loaded."""
        view = SearchView(service=self.platform_service)
        view.show()

        # Load RPA exclusions
        init_neg_count = len(view.tag_negative_titles.get_tags())
        view._load_rpa_exclusions()
        new_neg_count = len(view.tag_negative_titles.get_tags())
        self.assertGreater(new_neg_count, init_neg_count)
        self.assertTrue(view.sticky_bar._is_dirty)

        # Load standard blacklist
        init_bad_count = len(view.tag_bad_words.get_tags())
        view._load_standard_bad_words()
        new_bad_count = len(view.tag_bad_words.get_tags())
        self.assertGreater(new_bad_count, init_bad_count)

    def test_search_preview_dialog(self):
        """Verifies SearchPreviewDialog instantiates and generates search queue rows."""
        keywords = ["RPA Developer", "Python Engineer"]
        platforms = ["LinkedIn", "Naukri"]
        dlg = SearchPreviewDialog(
            keywords=keywords,
            location="Bangalore",
            platforms=platforms,
            date_posted="Past week",
            easy_apply=True,
            experience=5,
        )
        self.assertIn("Search Queue Preview", dlg.windowTitle())
        dlg.close()

    def test_saving_and_dirty_state_clearing(self):
        """Verifies modifying a field marks dirty, and saving commits to DB and clears dirty state."""
        view = SearchView(service=self.platform_service)
        view.show()

        self.assertFalse(view.sticky_bar._is_dirty)

        # Modify a setting
        view.spn_switch_number.setValue(45)
        self.assertTrue(view.sticky_bar._is_dirty)

        # Click save
        view.btn_save.click()
        self.assertFalse(view.sticky_bar._is_dirty)

        # Verify DB value
        cfg = self.platform_service.get_search_config("linkedin")
        self.assertEqual(cfg["switch_number"], 45)


if __name__ == "__main__":
    unittest.main()
