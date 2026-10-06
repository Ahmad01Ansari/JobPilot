"""Unit and integration test suite for Exact Record Navigation and AppNavigator lifecycle."""

import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QWidget
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Application, Job, User
from app.db.session import configure_sqlite_pragmas
from app.services.application_service import ApplicationService
from app.services.job_service import JobService
from app.services.navigation_service import AppNavigator
from app.services.search.search_result import NavigationAction, NavigationRequest, ViewStateSnapshot
from app.ui.views.applications_view import ApplicationsView
from app.ui.views.jobs_view import JobsView

# Ensure single headless QApplication instance
app = QApplication.instance() or QApplication(["-platform", "offscreen"])


class TestAppNavigator(unittest.TestCase):
    """Verifies AppNavigator lifecycle, arming, and view routing."""

    def setUp(self):
        self.mock_main_window = MagicMock()
        self.mock_main_window.state = MagicMock()
        self.mock_main_window.state.current_page = "dashboard"
        self.mock_jobs_view = MagicMock()
        self.mock_main_window.view_instances = {
            "jobs": self.mock_jobs_view,
        }
        self.navigator = AppNavigator(self.mock_main_window)

    def test_navigate_to_inactive_view_arms_request_before_switching(self):
        req = NavigationRequest(
            route="jobs",
            entity_type="job",
            entity_id=10,
            action=NavigationAction.FILTER,
            focus=True,
        )

        success = self.navigator.navigate(req)
        self.assertTrue(success)

        # Verified: arm_navigation_request was called BEFORE navigate_to
        self.mock_jobs_view.arm_navigation_request.assert_called_once_with(req)
        self.mock_main_window.navigate_to.assert_called_once_with("jobs")

    def test_navigate_to_already_active_view_dispatches_directly(self):
        self.mock_main_window.state.current_page = "jobs"
        req = NavigationRequest(
            route="jobs",
            entity_type="job",
            entity_id=25,
            action=NavigationAction.OPEN,
            focus=False,
        )

        success = self.navigator.navigate(req)
        self.assertTrue(success)

        # Directly dispatched to active view
        self.mock_jobs_view.handle_navigation_request.assert_called_once_with(req)
        self.mock_jobs_view.arm_navigation_request.assert_not_called()

    def test_navigate_invalid_route_returns_false(self):
        req = NavigationRequest(
            route="nonexistent_view",
            entity_type="unknown",
            entity_id=1,
        )
        success = self.navigator.navigate(req)
        self.assertFalse(success)


class TestJobsViewExactNavigation(unittest.TestCase):
    """Verifies exact filter, snapshot capture, and restoration in JobsView."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "nav_test.db")
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
        self._seed_data()
        self.job_service = JobService(session_factory=self.Session)
        self.view = JobsView(job_service=self.job_service)
        self.view.show()

    def tearDown(self):
        self.view.deleteLater()
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_data(self):
        with self.Session() as session:
            for i in range(1, 6):
                job = Job(
                    title=f"Engineer #{i}",
                    company_raw="Acme Inc",
                    platform="linkedin",
                    source_url=f"https://linkedin.com/jobs/{i}",
                    job_fingerprint=f"fp_{i}",
                )
                session.add(job)
            session.commit()

    def test_apply_exact_filter_isolates_single_row(self):
        # Initial refresh loads all 5 jobs
        self.view.refresh()
        self.assertEqual(self.view.table.rowCount(), 5)
        self.assertFalse(self.view.exact_filter_chip.isVisible())

        # Apply exact filter to job #3
        req = NavigationRequest(
            route="jobs",
            entity_type="job",
            entity_id=3,
            action=NavigationAction.FILTER,
            focus=True,
        )
        self.view.handle_navigation_request(req)

        # Verified: Table contains exactly 1 row matching job #3
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertTrue(self.view.exact_filter_chip.isVisible())
        self.assertIn("Engineer #3", self.view.exact_filter_chip.lbl_text.text())

        # Clear exact filter
        self.view.clear_exact_filter()

        # Verified: Snapshot restored all 5 jobs and hid the chip
        self.assertFalse(self.view.exact_filter_chip.isVisible())
        self.assertEqual(self.view.table.rowCount(), 5)


class TestApplicationsViewExactNavigation(unittest.TestCase):
    """Verifies exact filter, snapshot capture, and restoration in ApplicationsView."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "app_nav_test.db")
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
        self._seed_data()
        self.app_service = ApplicationService(session_factory=self.Session)
        self.view = ApplicationsView(service=self.app_service)
        self.view.show()

    def tearDown(self):
        self.view.deleteLater()
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_data(self):
        with self.Session() as session:
            for i in range(1, 4):
                job = Job(
                    title=f"Role #{i}",
                    company_raw="Tech Corp",
                    platform="naukri",
                    source_url=f"https://naukri.com/jobs/{i}",
                    job_fingerprint=f"app_fp_{i}",
                )
                session.add(job)
                session.flush()

                app = Application(
                    job_id=job.id,
                    status="APPLIED",
                )
                session.add(app)
            session.commit()

    def test_apply_exact_filter_isolates_application_row(self):
        self.view.refresh()
        self.assertEqual(self.view.table.rowCount(), 3)
        self.assertFalse(self.view.exact_filter_chip.isVisible())

        # Exact filter to application #2
        req = NavigationRequest(
            route="applications",
            entity_type="application",
            entity_id=2,
            action=NavigationAction.FILTER,
            focus=True,
        )
        self.view.handle_navigation_request(req)

        # Verified: Table contains exactly 1 row
        self.assertEqual(self.view.table.rowCount(), 1)
        self.assertTrue(self.view.exact_filter_chip.isVisible())

        # Clear exact filter restores original 3 rows
        self.view.clear_exact_filter()
        self.assertFalse(self.view.exact_filter_chip.isVisible())
        self.assertEqual(self.view.table.rowCount(), 3)


if __name__ == "__main__":
    unittest.main()
