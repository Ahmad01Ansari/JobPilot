"""Comprehensive unit test suite for the redesigned ATS Jobs View and Widgets."""

import os
import shutil
import tempfile
import unittest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models import Job
from app.services.application_service import ApplicationService
from app.services.job_service import JobFilter, JobService
from app.ui.views.jobs_view import JobsView
from app.ui.widgets.jobs import (
    JobDetailsDialog,
    JobsCategoryTabs,
    JobsDetailPanel,
    JobsEmptyState,
    JobsErrorState,
    JobsLoadingState,
    JobsPagination,
    JobsTable,
    JobsToolbar,
)

# Shared QApplication instance for headless Qt tests
app = QApplication.instance() or QApplication(["--platform", "offscreen"])


class TestJobsUIATS(unittest.TestCase):
    """Test suite covering ATS data grid, filters, sorting, bulk actions, and detail panel."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_jobs_ats.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
            future=True,
        )

        self.job_service = JobService(session_factory=self.Session)
        self.app_service = ApplicationService(session_factory=self.Session)

        # Seed realistic test data
        self.job1, _ = self.job_service.create_manual_job(
            title="Senior Python Developer",
            company="Spotify",
            platform="linkedin",
            location="Bengaluru, India",
            source_url="https://linkedin.com/jobs/view/101",
        )
        self.job2, _ = self.job_service.create_manual_job(
            title="RPA Automation Lead",
            company="Infozzle Software",
            platform="naukri",
            location="Noida, India",
            source_url="https://naukri.com/job/202",
        )
        self.job3, _ = self.job_service.create_manual_job(
            title="Machine Learning Engineer",
            company="Global AI Corp",
            platform="linkedin",
            location="Remote",
            source_url="https://linkedin.com/jobs/view/303",
            salary_text="25-35 LPA",
            experience_text="4-6 Years",
            description="Develop LLM workflows and AI pipelines.",
        )
        with self.Session() as s:
            j = s.query(Job).filter_by(id=self.job3.id).one()
            j.application_method = "COMPANY_PORTAL"
            j.application_url = "https://careers.globalai.com/jobs/apply/303"
            s.commit()
            self.job3 = self.job_service.get_job(self.job3.id)

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_jobs_view_initialization_and_counts(self):
        """Verifies JobsView initializes, loads records, and category counts."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.rowCount(), 3)
        counts = self.job_service.get_category_counts()
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["easy"], 2)
        self.assertEqual(counts["portal"], 1)

    def test_category_tab_filtering(self):
        """Verifies clicking category tabs filters results properly."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Switch to Easy Apply
        view.category_tabs.btn_easy.click()
        self.assertEqual(view.table.rowCount(), 2)

        # Switch to Company Portal
        view.category_tabs.btn_portal.click()
        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 1).text(), "Machine Learning Engineer")

        # Switch back to All
        view.category_tabs.btn_all.click()
        self.assertEqual(view.table.rowCount(), 3)

    def test_search_and_location_filtering(self):
        """Verifies search and location filters narrow results dynamically."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Search title
        view.txt_search.setText("Python")
        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 1).text(), "Senior Python Developer")

        # Clear search
        view.txt_search.clear()
        self.assertEqual(view.table.rowCount(), 3)

        # Filter by location
        view.toolbar.txt_location.setText("Noida")
        view.refresh()
        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 2).text(), "Infozzle Software")

    def test_platform_and_status_filtering(self):
        """Verifies platform dropdown and status dropdown filter correctly."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Platform filter -> Naukri
        view.toolbar.cmb_platform.setCurrentText("Naukri")
        view.refresh()
        self.assertEqual(view.table.rowCount(), 1)
        self.assertEqual(view.table.item(0, 3).text(), "Naukri")

        # Reset platform
        view.toolbar.cmb_platform.setCurrentIndex(0)
        view.refresh()
        self.assertEqual(view.table.rowCount(), 3)

    def test_column_visibility_toggle(self):
        """Verifies columns can be hidden and shown via the toolbar menu."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Company column is col 2 in 9-column grid
        self.assertFalse(view.table.isColumnHidden(2))
        view.toolbar.column_actions[2].trigger()
        self.assertTrue(view.table.isColumnHidden(2))

        # Restore
        view.toolbar.column_actions[2].trigger()
        self.assertFalse(view.table.isColumnHidden(2))

    def test_density_toggle(self):
        """Verifies row height changes between comfortable and compact modes."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        self.assertEqual(view.table.verticalHeader().defaultSectionSize(), 46)
        view.table.set_density("compact")
        self.assertEqual(view.table.verticalHeader().defaultSectionSize(), 34)
        view.table.set_density("comfortable")
        self.assertEqual(view.table.verticalHeader().defaultSectionSize(), 46)

    def test_bulk_selection_and_pipeline_tracking(self):
        """Verifies multi-job checkbox selection and bulk pipeline addition."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Initially 0 selected, bulk bar hidden
        self.assertFalse(view.bulk_bar.isVisible())

        # Select all via header click
        view.table._on_header_clicked(0)
        self.assertTrue(view.bulk_bar.isVisible())
        self.assertEqual(len(view.table.get_checked_jobs()), 3)

        # Trigger bulk add to pipeline
        view.bulk_bar.btn_pipeline.click()
        self.assertFalse(view.bulk_bar.isVisible())

        # Verify application records created
        apps = self.app_service.list_applications()
        self.assertEqual(len(apps), 3)

    def test_contextual_detail_panel_actions(self):
        """Verifies detail panel provides correct platform/portal links."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Select Python Developer on LinkedIn (Easy Apply)
        py_row = -1
        for r in range(view.table.rowCount()):
            if view.table.item(r, 1).text() == "Senior Python Developer":
                py_row = r
                break
        self.assertGreaterEqual(py_row, 0)
        view.table.selectRow(py_row)
        job = view.table.get_selected_job()
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertIn("LinkedIn", view.detail_panel.btn_primary_visit.text())

        # Find row for Company Portal job
        portal_row = -1
        for r in range(view.table.rowCount()):
            if view.table.item(r, 1).text() == "Machine Learning Engineer":
                portal_row = r
                break
        self.assertGreaterEqual(portal_row, 0)
        view.table.selectRow(portal_row)
        self.assertIn("Visit Company Portal", view.detail_panel.btn_primary_visit.text())
        self.assertTrue(view.detail_panel.lbl_portal_banner.isVisible())

    def test_empty_state_and_clear_filters(self):
        """Verifies empty state shows when no jobs match and clear button resets filters."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        view.txt_search.setText("NonexistentJobXYZ123")
        self.assertEqual(view.table.rowCount(), 0)
        self.assertEqual(view.left_stack.currentIndex(), 1)  # Empty State

        # Click Clear All Filters on empty state
        view.empty_state.clear_filters_clicked.emit()
        self.assertEqual(view.table.rowCount(), 3)
        self.assertEqual(view.left_stack.currentIndex(), 0)  # Table

    def test_job_details_dialog_rendering(self):
        """Verifies JobDetailsDialog instantiates properly with job metadata."""
        dlg = JobDetailsDialog(self.job3)
        self.assertIn("Machine Learning Engineer", dlg.windowTitle())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
