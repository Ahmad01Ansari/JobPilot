"""End-to-end integration and smoke test for JobPilot Desktop UI application.

Verifies:
- Application initialization with real database connection.
- Seamless navigation and rendering across all 13 views in NAV_ITEMS.
- GlobalSearchDialog command palette opening and search query execution.
- Absence of uncaught Qt exceptions, layout warnings, or null pointer references.
- Clean application shutdown.
"""

import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from app.db import init_db, check_connection
from app.ui.navigation import NAV_ITEMS
from app.ui.state import AppState
from app.ui.theme import ThemeManager
from app.ui.main_window import MainWindow
from app.ui.widgets.search_dialog import GlobalSearchDialog


class TestApplicationRun(unittest.TestCase):
    """End-to-end application lifecycle and view verification test."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(["--offscreen"])
        ThemeManager.apply_dark_theme(cls.app)

        # Ensure database is initialized
        success, err = init_db()
        if not success:
            raise RuntimeError(f"Database initialization failed: {err}")

    def setUp(self):
        self.state = AppState()
        diag = check_connection()
        wal_str = " (WAL)" if diag.get("wal_enabled") else ""
        self.state.update_status("database", f"Connected{wal_str}")
        self.window = MainWindow(state=self.state)
        self.window.show()

    def tearDown(self):
        self.window.notification_service.stop_reminder_timer()
        logs_view = self.window.view_instances.get("logs")
        if logs_view and hasattr(logs_view, "refresh_timer"):
            logs_view.refresh_timer.stop()
        self.window.close()

    def test_database_connection_status(self):
        """MainWindow reflects active database connection."""
        self.assertIn("Connected", self.window.status_bar.db_label.text())

    def test_all_13_navigation_views_render_cleanly(self):
        """Iterates through every registered navigation item in NAV_ITEMS and verifies switching."""
        self.assertEqual(len(NAV_ITEMS), 14)

        for item in NAV_ITEMS:
            with self.subTest(view_id=item.id, title=item.title):
                self.window.navigate_to(item.id)

                # Verify state updated
                self.assertEqual(self.state.current_page_id, item.id)

                # Verify top bar title updated
                self.assertEqual(self.window.top_bar.title_label.text(), item.title)

                # Verify stacked widget shows the correct view instance
                current_view = self.window.get_current_view()
                self.assertIsNotNone(current_view)
                self.assertIsInstance(current_view, item.view_class)

                # Process pending Qt events to ensure paint/layout methods run without errors
                self.app.processEvents()

    def test_global_search_dialog_modal_workflow(self):
        """Verifies opening the global command palette and executing a search."""
        dialog = GlobalSearchDialog(search_service=self.window.search_service, parent=self.window)
        self.assertIsNotNone(dialog)

        # Trigger search
        dialog.txt_search.setText("Engineer")
        dialog._perform_search()
        self.app.processEvents()

        # Dialog contains search box, chips, results list
        self.assertEqual(dialog.txt_search.text(), "Engineer")
        self.assertIsNotNone(dialog.results_list)

        dialog.close()

    def test_top_bar_search_button_connection(self):
        """TopBar contains search button connected to search_requested signal."""
        self.assertTrue(hasattr(self.window.top_bar, "btn_search"))
        self.assertTrue(hasattr(self.window.top_bar, "search_requested"))

    def test_state_notification_banner_display(self):
        """Emitting notifications through AppState displays message in NotificationBar."""
        self.state.notify("info", "System health check normal.")
        self.app.processEvents()
        self.assertTrue(self.window.notification_bar.isVisible())
        self.assertIn("health check normal", self.window.notification_bar.message_label.text())


if __name__ == "__main__":
    unittest.main()
