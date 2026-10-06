'''
Unit Tests for Indeed Rotator
Validates multi-keyword cycling, quota enforcement, tracker skipping, and stop signal checks.
'''

import unittest
from unittest.mock import MagicMock

from platforms.indeed.rotator import (
    IndeedRotationConfig,
    IndeedRotationStats,
    IndeedRotator,
)
from platforms.indeed.search import IndeedJobItem


class TestIndeedRotator(unittest.TestCase):
    def test_config_from_profile_fallback(self):
        cfg = IndeedRotationConfig(
            search_terms=["RPA Developer"],
            location="India",
            freshness_days=7,
            switch_number=10,
            daily_application_goal=20,
        )
        self.assertEqual(cfg.search_terms, ["RPA Developer"])
        self.assertEqual(cfg.switch_number, 10)
        self.assertEqual(cfg.daily_application_goal, 20)

    def test_rotator_skips_already_applied(self):
        mock_browser = MagicMock()
        mock_browser.driver.current_window_handle = "main_window"

        mock_tracker = MagicMock()
        # job1 is already applied, job2 is not
        mock_tracker.is_applied.side_effect = lambda jid: jid == "job1"

        config = IndeedRotationConfig(
            search_terms=["Developer"],
            max_pages_per_search=1,
            switch_number=10,
            daily_application_goal=5,
        )

        rotator = IndeedRotator(browser=mock_browser, tracker=mock_tracker, config=config)

        # Mock search returning 2 jobs
        job1 = IndeedJobItem(job_id="job1", title="Dev 1", company="Corp 1")
        job2 = IndeedJobItem(job_id="job2", title="Dev 2", company="Corp 2")
        rotator.search.search = MagicMock(return_value=[job1, job2])

        # Mock applier
        mock_applier = MagicMock()
        mock_applier.apply_to_job.return_value = (True, "Submitted successfully.")

        stats = rotator.run(applier=mock_applier)

        self.assertEqual(stats.jobs_evaluated, 2)
        self.assertEqual(stats.jobs_skipped, 1)  # job1 skipped
        self.assertEqual(stats.jobs_applied, 1)  # job2 applied
        mock_applier.apply_to_job.assert_called_once_with(job2, main_window="main_window")

    def test_rotator_respects_stop_check(self):
        mock_browser = MagicMock()
        mock_browser.driver.current_window_handle = "main_window"
        mock_tracker = MagicMock()
        mock_tracker.is_applied.return_value = False

        config = IndeedRotationConfig(
            search_terms=["Term 1", "Term 2"],
            max_pages_per_search=2,
            switch_number=10,
            daily_application_goal=5,
        )

        rotator = IndeedRotator(browser=mock_browser, tracker=mock_tracker, config=config)
        rotator.search.search = MagicMock(return_value=[IndeedJobItem(job_id="j1", title="T", company="C")])

        # Immediate stop check
        stats = rotator.run(stop_check=lambda: True)
        self.assertEqual(stats.terms_searched, 0)
        self.assertEqual(stats.jobs_applied, 0)

    def test_rotator_auto_relaxes_date_filter_when_zero_results(self):
        mock_browser = MagicMock()
        mock_browser.driver.current_window_handle = "main_window"
        mock_tracker = MagicMock()
        mock_tracker.is_applied.return_value = False

        config = IndeedRotationConfig(
            search_terms=["AI Engineer"],
            max_pages_per_search=1,
            freshness_days=7,
            auto_relax_date_filter=True,
            switch_number=10,
            daily_application_goal=5,
        )

        rotator = IndeedRotator(browser=mock_browser, tracker=mock_tracker, config=config)

        # First call (freshness=7) returns [] (zero results)
        # Second call (freshness=30) returns [job1]
        job1 = IndeedJobItem(job_id="ai_1", title="AI Engineer", company="AI Labs", is_easy_apply=True)

        def mock_search(keyword, location, freshness_days, easy_apply_only, page):
            if freshness_days == 7:
                return []
            if freshness_days == 30:
                return [job1]
            return []

        rotator.search.search = MagicMock(side_effect=mock_search)

        mock_applier = MagicMock()
        mock_applier.apply_to_job.return_value = (True, "Applied.")

        stats = rotator.run(applier=mock_applier)

        self.assertEqual(stats.jobs_evaluated, 1)
        self.assertEqual(stats.jobs_applied, 1)
        mock_applier.apply_to_job.assert_called_once_with(job1, main_window="main_window")

    def test_rotator_skips_negative_keywords(self):
        mock_browser = MagicMock()
        mock_browser.driver.current_window_handle = "main_window"
        mock_tracker = MagicMock()
        mock_tracker.is_applied.return_value = False

        config = IndeedRotationConfig(
            search_terms=["Developer"],
            max_pages_per_search=1,
            switch_number=10,
            daily_application_goal=5,
            negative_title_words=["UiPath", "Intern"],
        )

        rotator = IndeedRotator(browser=mock_browser, tracker=mock_tracker, config=config)

        # job_neg has "UiPath" in title, job_ok does not
        job_neg = IndeedJobItem(job_id="neg_1", title="RPA UiPath Developer", company="Corp 1")
        job_ok = IndeedJobItem(job_id="ok_1", title="RPA Python Developer", company="Corp 2")
        rotator.search.search = MagicMock(return_value=[job_neg, job_ok])

        mock_applier = MagicMock()
        mock_applier.apply_to_job.return_value = (True, "Applied.")

        stats = rotator.run(applier=mock_applier)

        self.assertEqual(stats.jobs_evaluated, 2)
        self.assertEqual(stats.jobs_skipped, 1)  # job_neg skipped for UiPath
        self.assertEqual(stats.jobs_applied, 1)  # job_ok applied
        mock_applier.apply_to_job.assert_called_once_with(job_ok, main_window="main_window")
        mock_tracker.record_evaluation.assert_called_with(
            mock_tracker.record_evaluation.call_args[0][0],
            "SKIPPED",
            skip_reason="Title contains negative keyword 'uipath'",
        )


if __name__ == "__main__":
    unittest.main()
