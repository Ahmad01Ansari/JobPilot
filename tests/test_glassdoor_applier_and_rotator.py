'''
Unit Tests for Glassdoor Applier and Rotator (Phases K, L)
Validates end-to-end application lifecycle, 2-stage qualification, tracker logging,
and multi-keyword rotation orchestration.
'''

import unittest
from unittest.mock import MagicMock, patch

from platforms.glassdoor.search import GlassdoorJobItem
from platforms.glassdoor.applier import GlassdoorApplier
from platforms.glassdoor.rotator import GlassdoorRotator
from modules.qualification_engine import QualificationResult


class TestGlassdoorApplierAndRotator(unittest.TestCase):
    def test_applier_stage1_title_skip(self):
        mock_browser = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.is_already_applied.return_value = False

        mock_qual_engine = MagicMock()
        mock_qual_engine.qualify_title.return_value = QualificationResult(
            accepted=False, reason="Disqualified title"
        )

        applier = GlassdoorApplier(
            browser=mock_browser,
            tracker=mock_tracker,
            qualification_engine=mock_qual_engine,
        )

        job_item = GlassdoorJobItem(
            job_id="gd_101",
            title="Senior Mechanical Engineer",
            company="Tech Corp",
            location="India",
            job_url="https://glassdoor.com/job/101",
        )

        status = applier.apply(job_item)
        self.assertEqual(status, "skipped")
        mock_tracker.record_application.assert_called_once()
        self.assertEqual(mock_tracker.record_application.call_args[1]["status"], "SKIPPED")

    def test_applier_stage2_description_skip(self):
        mock_browser = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.is_already_applied.return_value = False

        mock_qual_engine = MagicMock()
        mock_qual_engine.qualify_title.return_value = QualificationResult(accepted=True)
        mock_qual_engine.qualify_description.return_value = QualificationResult(
            accepted=False, reason="Requires 10+ years experience"
        )

        applier = GlassdoorApplier(
            browser=mock_browser,
            tracker=mock_tracker,
            qualification_engine=mock_qual_engine,
        )

        job_item = GlassdoorJobItem(
            job_id="gd_102",
            title="RPA Developer",
            company="Tech Corp",
            location="India",
            job_url="https://glassdoor.com/job/102",
        )

        with patch("platforms.glassdoor.parser.GlassdoorParser.extract_job_description", return_value="Detailed JD"):
            status = applier.apply(job_item)

        self.assertEqual(status, "skipped")
        self.assertEqual(mock_tracker.record_application.call_args[1]["status"], "SKIPPED")

    def test_applier_external_flow(self):
        mock_browser = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.is_already_applied.return_value = False

        mock_qual_engine = MagicMock()
        mock_qual_engine.qualify_title.return_value = QualificationResult(accepted=True)
        mock_qual_engine.qualify_description.return_value = QualificationResult(accepted=True)

        applier = GlassdoorApplier(
            browser=mock_browser,
            tracker=mock_tracker,
            qualification_engine=mock_qual_engine,
        )

        job_item = GlassdoorJobItem(
            job_id="gd_103",
            title="RPA Developer",
            company="External Corp",
            location="India",
            job_url="https://glassdoor.com/job/103",
        )

        with patch("platforms.glassdoor.parser.GlassdoorParser.extract_job_description", return_value="Detailed JD"), \
             patch("platforms.glassdoor.applier.GlassdoorFlowDetector.detect_flow", return_value=("EXTERNAL", MagicMock())):
            status = applier.apply(job_item)

        self.assertEqual(status, "external")
        self.assertEqual(mock_tracker.record_application.call_args[1]["status"], "EXTERNAL")

    def test_applier_easy_apply_submitted(self):
        mock_browser = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.is_already_applied.return_value = False

        mock_qual_engine = MagicMock()
        mock_qual_engine.qualify_title.return_value = QualificationResult(accepted=True)
        mock_qual_engine.qualify_description.return_value = QualificationResult(accepted=True)

        applier = GlassdoorApplier(
            browser=mock_browser,
            tracker=mock_tracker,
            qualification_engine=mock_qual_engine,
            pause_before_submit=False,
        )

        mock_trigger = MagicMock()
        applier.form.is_review_step = MagicMock(side_effect=[False, True])
        applier.form.click_continue = MagicMock(return_value=True)
        applier.submitter.submit_application = MagicMock(return_value=True)

        job_item = GlassdoorJobItem(
            job_id="gd_104",
            title="RPA Developer",
            company="Quick Corp",
            location="India",
            job_url="https://glassdoor.com/job/104",
        )

        with patch("platforms.glassdoor.parser.GlassdoorParser.extract_job_description", return_value="Detailed JD"), \
             patch("platforms.glassdoor.applier.GlassdoorFlowDetector.detect_flow", return_value=("EASY_APPLY", mock_trigger)):
            status = applier.apply(job_item)

        self.assertEqual(status, "submitted")
        self.assertEqual(mock_tracker.record_application.call_args[1]["status"], "SUBMITTED")

    @patch("platforms.glassdoor.rotator.get_platform")
    def test_rotator_run(self, mock_get_platform):
        mock_get_platform.return_value = {
            "enabled": True,
            "search_terms": ["RPA Developer"],
            "search_location": "India",
            "max_pages_per_search": 1,
            "switch_number": 5,
            "daily_application_goal": 10,
        }

        mock_browser = MagicMock()
        mock_tracker = MagicMock()
        mock_applier = MagicMock()
        mock_applier.apply.return_value = "submitted"

        rotator = GlassdoorRotator(
            browser=mock_browser,
            tracker=mock_tracker,
            applier=mock_applier,
        )

        mock_card = MagicMock()
        rotator.search.get_job_card_elements = MagicMock(return_value=[mock_card])

        mock_item = GlassdoorJobItem(
            job_id="gd_201",
            title="RPA Engineer",
            company="Test Company",
            location="India",
            job_url="https://glassdoor.com/job/201",
            is_easy_apply=True,
        )

        rotator.search.parse_job_cards = MagicMock(return_value=[mock_item])

        stats = rotator.run()

        self.assertEqual(stats["discovered"], 1)
        self.assertEqual(stats["submitted"], 1)
        mock_applier.apply.assert_called_once()


if __name__ == "__main__":
    unittest.main()
