"""Unit tests for ApplicationsView filter features, metric cards, and interactions."""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.session import configure_sqlite_pragmas
from app.services.application_service import ApplicationFilter, ApplicationService
from app.services.job_service import JobService
from app.ui.views.applications_view import ApplicationsView


class TestApplicationsViewFeatures(unittest.TestCase):
    """Test suite for ApplicationsView filters, metric card interactions, and state sync."""

    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "app_ui_test.db")
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
        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)

        # Seed test jobs and applications
        self.j1, _ = self.job_service.create_manual_job(title="RPA Architect", company="Hitachi", platform="linkedin")
        self.j2, _ = self.job_service.create_manual_job(title="Python Engineer", company="Uber", platform="naukri")
        self.j3, _ = self.job_service.create_manual_job(title="Automation Lead", company="Spotify", platform="linkedin")

        self.a1, _ = self.app_service.create_application(job_id=self.j1.id, status="OFFER")
        self.a2, _ = self.app_service.create_application(job_id=self.j2.id, status="SUBMITTED")
        self.a3, _ = self.app_service.create_application(job_id=self.j3.id, status="REJECTED")

        self.view = ApplicationsView(service=self.app_service)
        self.view.show()
        QApplication.processEvents()

    def tearDown(self):
        self.view.close()
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initial_rendering(self):
        """Verifies initial row count and tab counts."""
        self.assertEqual(self.view.table.rowCount(), 3)
        self.assertEqual(self.view.tabs.count(), 6)
        self.assertIn("3 applications", self.view.lbl_count_pill.text())

    def test_tab_filtering(self):
        """Verifies switching tabs filters applications appropriately."""
        # Tab 2: Submitted (contains SUBMITTED, UNDER_REVIEW)
        self.view.tabs.setCurrentIndex(2)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Uber")

        # Tab 4: Offers
        self.view.tabs.setCurrentIndex(4)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Hitachi")

        # Tab 5: Closed / Rejected
        self.view.tabs.setCurrentIndex(5)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Spotify")

        # Back to Tab 0: All
        self.view.tabs.setCurrentIndex(0)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 3)

    def test_metric_card_clicking(self):
        """Verifies clicking on metric cards toggles filtering."""
        # Click Submitted card -> switches to Submitted tab (index 2)
        self.view._on_metric_card_clicked(target_tab=2, target_status="SUBMITTED")
        QApplication.processEvents()
        self.assertEqual(self.view.tabs.currentIndex(), 2)
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Uber")

        # Click again -> toggles back to All Applications (index 0)
        self.view._on_metric_card_clicked(target_tab=2, target_status="SUBMITTED")
        QApplication.processEvents()
        self.assertEqual(self.view.tabs.currentIndex(), 0)
        self.assertEqual(self.view.table.rowCount(), 3)

        # Click Offers card -> switches to Offers tab (index 4)
        self.view._on_metric_card_clicked(target_tab=4, target_status="OFFER")
        QApplication.processEvents()
        self.assertEqual(self.view.tabs.currentIndex(), 4)
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Hitachi")

    def test_search_and_clear_filters(self):
        """Verifies text search and Reset button."""
        self.view.txt_search.setText("Hitachi")
        self.view.refresh()
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Hitachi")

        # Reset button
        self.view._clear_all_filters()
        QApplication.processEvents()
        self.assertEqual(self.view.txt_search.text(), "")
        self.assertEqual(self.view.tabs.currentIndex(), 0)
        self.assertEqual(self.view.cmb_platform.currentIndex(), 0)
        self.assertEqual(self.view.cmb_status_filter.currentIndex(), 0)
        self.assertEqual(self.view.table.rowCount(), 3)

    def test_platform_filter(self):
        """Verifies filtering by platform dropdown."""
        # Select LinkedIn
        idx = self.view.cmb_platform.findText("LinkedIn")
        self.view.cmb_platform.setCurrentIndex(idx)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 2)

        # Select Naukri
        idx = self.view.cmb_platform.findText("Naukri")
        self.view.cmb_platform.setCurrentIndex(idx)
        QApplication.processEvents()
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertEqual(self.view.table.item(0, 0).text(), "Uber")


if __name__ == "__main__":
    unittest.main()
