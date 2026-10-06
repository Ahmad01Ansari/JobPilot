"""
Unit Tests for Phase 1: PySide6 Desktop Application Foundation.
Tests application startup, navigation registry consistency, view switching,
window constraints, theme application, and UI state signals in offscreen mode.
"""

import os
import sys
import unittest

# Ensure offscreen platform is set before QApplication is imported
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from app.ui.theme import ThemeManager, COLORS
from app.ui.state import AppState
from app.ui.navigation import NAV_ITEMS, get_nav_item_by_id
from app.ui.main_window import MainWindow
from app.ui.views.dashboard_view import DashboardView
from app.ui.views.profile_view import ProfileView


class TestDesktopFoundation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initializes offscreen QApplication once for all test methods."""
        app = QApplication.instance()
        if app is None:
            cls.app = QApplication(["jobpilot_test", "-platform", "offscreen"])
        else:
            cls.app = app
        ThemeManager.apply_dark_theme(cls.app)

    def setUp(self):
        self.state = AppState()
        self.window = MainWindow(state=self.state)

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()

    def test_window_constraints(self):
        """Validates that MainWindow enforces minimum dimensions."""
        min_size = self.window.minimumSize()
        self.assertGreaterEqual(min_size.width(), 1024, "Minimum width must be at least 1024px")
        self.assertGreaterEqual(min_size.height(), 680, "Minimum height must be at least 680px")

    def test_navigation_registry_consistency(self):
        """Validates that registered navigation items exist with matching stacked widgets."""
        self.assertEqual(len(NAV_ITEMS), 14, "Must have exactly 14 registered navigation items")
        self.assertEqual(self.window.stacked_widget.count(), 14, "Stacked widget must contain exactly 14 pages")
        self.assertEqual(len(self.window.sidebar.buttons), 14, "Sidebar must have exactly 14 buttons")

        # Verify every registered item has a valid view class
        for item in NAV_ITEMS:
            self.assertIn(item.id, self.window.page_index_map)
            self.assertIn(item.id, self.window.view_instances)
            view = self.window.view_instances[item.id]
            self.assertIsInstance(view, item.view_class)

    def test_navigation_page_switching(self):
        """Verifies that navigating to every page ID correctly updates the active widget."""
        for item in NAV_ITEMS:
            self.window.navigate_to(item.id)
            current_widget = self.window.get_current_view()
            self.assertIsInstance(current_widget, item.view_class, f"Active widget for {item.id} must be {item.view_class.__name__}")
            self.assertEqual(self.state.current_page_id, item.id)

    def test_top_bar_updates_on_navigation(self):
        """Verifies that TopBar updates its header title on page change."""
        self.window.navigate_to("profile")
        self.assertEqual(self.window.top_bar.title_label.text(), "Profile")

        self.window.navigate_to("analytics")
        self.assertEqual(self.window.top_bar.title_label.text(), "Analytics")

    def test_notification_bar_display(self):
        """Verifies that notification banner shows message when signal emitted."""
        self.window.notification_bar.hide()
        self.assertTrue(self.window.notification_bar.isHidden())
        self.state.notify("success", "Application submitted successfully!")
        self.assertFalse(self.window.notification_bar.isHidden())
        self.assertIn("Application submitted successfully!", self.window.notification_bar.message_label.text())

    def test_status_bar_updates(self):
        """Verifies StatusBar indicator setters."""
        status_bar = self.window.status_bar
        self.assertIn("Ready", status_bar.engine_label.text())
        self.assertIn("Not Connected", status_bar.db_label.text())

        status_bar.set_engine_status("Active", is_ready=True)
        self.assertIn("Active", status_bar.engine_label.text())

        status_bar.set_database_status("Connected (SQLite)")
        self.assertIn("Connected", status_bar.db_label.text())

    def test_theme_stylesheet_compilation(self):
        """Verifies that the centralized theme stylesheet compiles and applies without error."""
        css = ThemeManager.get_stylesheet(COLORS)
        self.assertIsInstance(css, str)
        self.assertIn(COLORS["background"], css)
        self.assertIn(COLORS["surface"], css)
        self.assertIn(COLORS["accent"], css)

    def test_refined_dark_canvas_tokens_and_styling(self):
        """Verifies Refined Dark Canvas (#0F1117) and Safety Orange (#FF5F15) design tokens."""
        ThemeManager.apply_dark_theme(self.app)
        self.assertEqual(COLORS["background"], "#0F1117")
        self.assertEqual(COLORS["surface"], "#161B22")
        self.assertEqual(COLORS["primary"], "#FF5F15")
        self.assertEqual(COLORS["text"], "#F0F6FC")
        self.assertEqual(COLORS["border"], "#262C36")
        self.assertIsNotNone(self.window.top_bar)
        self.assertIsNotNone(self.window.sidebar)

    def test_dashboard_platform_trigger_deck_integration(self):
        """Validates that DashboardView integrates the weighted PlatformTriggerDeck command center."""
        dashboard_view = self.window.view_instances.get("dashboard")
        self.assertIsNotNone(dashboard_view)
        self.assertTrue(hasattr(dashboard_view, "trigger_deck"))

        deck = dashboard_view.trigger_deck
        self.assertIsNotNone(deck.tile_linkedin)
        self.assertIsNotNone(deck.tile_naukri)
        self.assertIsNotNone(deck.tile_all)

        # Initial state check
        self.assertIn("Ready to Launch", deck.lbl_status_pill.text())
        self.assertTrue(deck.live_tray.isHidden())
        self.assertTrue(deck.tile_linkedin.btn_trigger.isEnabled())
        self.assertTrue(deck.tile_naukri.btn_trigger.isEnabled())
        self.assertTrue(deck.tile_all.btn_trigger.isEnabled())

        # Test state transition to running
        deck.set_state("running", active_platform="linkedin")
        self.assertIn("Running: Linkedin", deck.lbl_status_pill.text())
        self.assertFalse(deck.live_tray.isHidden())
        self.assertFalse(deck.tile_linkedin.btn_trigger.isEnabled())

        # Test state transition to stopping
        deck.set_state("stopping")
        self.assertIn("Stopping", deck.lbl_status_pill.text())
        self.assertFalse(deck.live_tray.isHidden())

        # Test return to idle
        deck.set_state("idle")
        self.assertIn("Ready to Launch", deck.lbl_status_pill.text())
        self.assertTrue(deck.live_tray.isHidden())
        self.assertTrue(deck.tile_linkedin.btn_trigger.isEnabled())


if __name__ == "__main__":
    unittest.main()

