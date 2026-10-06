"""Unit tests for Job Status Change functionality in Jobs Repository and ATS widgets."""

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
from app.services.job_service import JobService
from app.ui.views.jobs_view import JobsView
from app.ui.widgets.jobs import JobsDetailPanel, JobsTable
from app.ui.widgets.jobs.jobs_table import StatusDropdownButton

# Shared QApplication instance for headless Qt tests
app = QApplication.instance() or QApplication(["--platform", "offscreen"])


class TestJobsStatusChange(unittest.TestCase):
    """Test suite covering manual status transitions from table dropdown and detail panel."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_status_change.db")
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

        # Create test jobs
        self.job1, _ = self.job_service.create_manual_job(
            title="AI Developer - Agentic Workflow Automation",
            company="Jewelex India",
            platform="naukri",
            location="Mumbai",
            source_url="https://naukri.com/job/101",
        )
        self.job2, _ = self.job_service.create_manual_job(
            title="Backend Engineer",
            company="Google",
            platform="linkedin",
            location="Hyderabad",
            source_url="https://linkedin.com/job/102",
        )

        # Create an application in FAILED status for job1 (as shown in user screenshot)
        self.app1, _ = self.app_service.create_application(
            job_id=self.job1.id,
            status="FAILED",
            application_type="AUTO",
            notes="Initial automation failed",
        )

    def tearDown(self):
        self.engine.dispose()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_status_dropdown_button_rendering(self):
        """Verifies StatusDropdownButton displays correctly for failed status."""
        btn = StatusDropdownButton("FAILED")
        self.assertEqual(btn.text(), "Failed ▾")
        self.assertEqual(btn.current_status, "FAILED")

        # Test options exist
        codes = [c for c, _, _ in btn.STATUS_OPTIONS]
        self.assertIn("SUBMITTED", codes)
        self.assertIn("FAILED", codes)
        self.assertIn("UNDER_REVIEW", codes)
        self.assertIn("INTERVIEW", codes)

    def test_change_status_from_failed_to_submitted(self):
        """Verifies changing status of a Failed job to Submitted via JobsView."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Check initial status is FAILED
        app = self.app_service.get_by_job_id(self.job1.id)
        self.assertEqual(app.status, "FAILED")

        # Request status change from FAILED to SUBMITTED
        view._on_status_change_requested(self.job1, "SUBMITTED")

        # Verify application transitioned to SUBMITTED
        updated_app = self.app_service.get_by_job_id(self.job1.id)
        self.assertEqual(updated_app.status, "SUBMITTED")
        self.assertEqual(updated_app.automation_status, "SUCCESS")

        # Check detail panel updates
        view._on_job_selected(self.job1)
        self.assertIn("Submitted", view.detail_panel.btn_track_app.text())

    def test_change_status_for_unapplied_job(self):
        """Verifies changing status for a job that has no application creates an application."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Job2 initially has no application
        app = self.app_service.get_by_job_id(self.job2.id)
        self.assertIsNone(app)

        # User requests status change to SUBMITTED directly
        view._on_status_change_requested(self.job2, "SUBMITTED")

        # Verify application created with SUBMITTED status
        created_app = self.app_service.get_by_job_id(self.job2.id)
        self.assertIsNotNone(created_app)
        self.assertEqual(created_app.status, "SUBMITTED")

    def test_bulk_status_change(self):
        """Verifies changing status for multiple jobs in bulk."""
        view = JobsView(job_service=self.job_service, app_service=self.app_service)
        view.show()

        # Change both job1 and job2 to INTERVIEW
        view._on_status_change_requested([self.job1, self.job2], "INTERVIEW")

        app1 = self.app_service.get_by_job_id(self.job1.id)
        app2 = self.app_service.get_by_job_id(self.job2.id)

        self.assertEqual(app1.status, "INTERVIEW")
        self.assertEqual(app2.status, "INTERVIEW")

    def test_detail_panel_status_button(self):
        """Verifies detail panel button displays current status and triggers change."""
        panel = JobsDetailPanel()
        panel.show()

        panel.set_job(self.job1, in_pipeline=True, app_status="FAILED")
        self.assertIn("Failed", panel.btn_track_app.text())
        self.assertTrue(panel.btn_track_app.isEnabled())


if __name__ == "__main__":
    unittest.main()
