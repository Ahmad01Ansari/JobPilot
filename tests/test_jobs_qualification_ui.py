"""Unit tests for Job Qualification UI components and integration."""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.db.models import Job, JobEvaluation
from app.services.dto.qualification_dto import QualificationResultDTO
from app.services.dto.qualification_enums import AIStatus, EvaluationStatus, QualificationDecision
from app.ui.widgets.jobs.jobs_detail_panel import JobsDetailPanel
from app.ui.widgets.jobs.jobs_table import JobsTable, create_match_badge
from app.ui.workers.job_qualification_worker import JobQualificationWorker

# Ensure headless Qt
os.environ["QT_QPA_PLATFORM"] = "offscreen"
app = QApplication.instance() or QApplication([])


class TestJobQualificationUI(unittest.TestCase):
    """Test suite verifying Jobs table, detail panel, and background qualification worker."""

    def setUp(self):
        self.table = JobsTable()
        self.detail_panel = JobsDetailPanel()

    def tearDown(self):
        self.table.deleteLater()
        self.detail_panel.deleteLater()

    def test_table_columns_include_match(self):
        """Verifies Match column exists at index 7 and header labels match."""
        col_labels = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        self.assertIn("Match", col_labels)
        self.assertEqual(col_labels[7], "Match")
        self.assertEqual(col_labels[8], "Status")

    def test_create_match_badge_formatting(self):
        """Verifies match badge styles and texts across decisions."""
        # Un-evaluated
        w_none = create_match_badge(None, None)
        lbl_none = w_none.findChild(w_none.layout().itemAt(0).widget().__class__)
        self.assertEqual(lbl_none.text(), "—")

        # Strong match
        w_strong = create_match_badge(92, "STRONG_MATCH")
        lbl_strong = w_strong.findChild(lbl_none.__class__)
        self.assertIn("92% Strong", lbl_strong.text())

        # Review required
        w_rev = create_match_badge(35, "REVIEW_REQUIRED")
        lbl_rev = w_rev.findChild(lbl_none.__class__)
        self.assertIn("Review", lbl_rev.text())

    def test_table_update_job_evaluation(self):
        """Verifies dynamic row badge update via update_job_evaluation."""
        job = MagicMock(spec=Job)
        job.id = 999
        job.title = "Lead Automation Engineer"
        job.company_raw = "Global Tech"
        job.platform = "linkedin"
        job.location = "Pune"
        job.experience_text = "5+ Years"
        job.application_method = "EASY_APPLY"
        job.first_seen_at = None
        job.evaluations = []
        job.applications = []

        self.table.set_jobs([job])
        self.assertEqual(self.table.rowCount(), 1)

        # Update evaluation
        self.table.update_job_evaluation(999, 88, "STRONG_MATCH")
        cell_widget = self.table.cellWidget(0, 7)
        self.assertIsNotNone(cell_widget)

    def test_detail_panel_qualification_lifecycle(self):
        """Verifies detail panel renders qualification fit and responds to set_qualification."""
        job = MagicMock(spec=Job)
        job.id = 101
        job.title = "RPA Architect"
        job.company_raw = "RoboSystems"
        job.platform = "naukri"
        job.location = "Bengaluru"
        job.salary_text = "20-25 LPA"
        job.experience_text = "6-10 Years"
        job.application_method = "EASY_APPLY"
        job.description = "Design enterprise bot architecture."
        job.evaluations = []
        job.applications = []

        self.detail_panel.set_job(job)
        self.assertEqual(self.detail_panel.lbl_qual_badge.text(), "Not Evaluated")

        # Update with result DTO
        dto = QualificationResultDTO(
            job_id=101,
            score=78,
            decision=QualificationDecision.GOOD_MATCH,
            confidence=0.9,
            component_scores={"role_match": 85, "skill_match": 75, "experience_match": 80, "location_match": 100},
            positive_reasons=["Matched 3 core skills: UiPath, Python, SQL."],
            negative_reasons=[],
            recommendation="Solid match for candidate profile.",
        )
        self.detail_panel.set_qualification(dto)
        self.assertIn("78% Good Match", self.detail_panel.lbl_qual_badge.text())
        self.assertIn("Role: 85%", self.detail_panel.lbl_qual_metrics.text())
        self.assertIn("Matched 3 core skills", self.detail_panel.lbl_qual_reasons.text())

    def test_detail_panel_qualify_button_signal(self):
        """Verifies clicking Qualify Fit emits qualify_job_requested signal."""
        job = MagicMock(spec=Job)
        job.id = 202
        job.title = "Python Automation Dev"
        job.company_raw = "AutoFlow"
        job.platform = "linkedin"
        job.location = "Remote"
        job.experience_text = "3 Years"
        job.salary_text = None
        job.application_method = "EASY_APPLY"
        job.description = "Python scripts for data automation."
        job.evaluations = []
        job.applications = []

        self.detail_panel.set_job(job)
        emitted_jobs = []
        self.detail_panel.qualify_job_requested.connect(lambda j: emitted_jobs.append(j))

        self.detail_panel.btn_qualify.click()
        self.assertEqual(len(emitted_jobs), 1)
        self.assertEqual(emitted_jobs[0].id, 202)


if __name__ == "__main__":
    unittest.main()
