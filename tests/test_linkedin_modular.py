import unittest
from unittest.mock import MagicMock, patch

from platforms.linkedin.selectors import (
    HOME_URL,
    LOGIN_URL,
    EASY_APPLY_BUTTON_XPATHS,
    JOB_RESULTS_CONTAINER,
)
from platforms.linkedin.parser import LinkedInJobParser
from platforms.linkedin.browser import LinkedInBrowser
from platforms.linkedin.applier import LinkedInApplier
from platforms.linkedin.rotator import LinkedInRotator
from modules.tracker import ApplicationTracker


class TestLinkedInModular(unittest.TestCase):
    def test_parser_extract_job_id(self):
        # 1. From data-job-id attribute
        card_mock = MagicMock()
        card_mock.get_attribute.side_effect = lambda attr: "12345678" if attr == "data-job-id" else None
        job_id = LinkedInJobParser.extract_job_id_from_card(card_mock)
        self.assertEqual(job_id, "12345678")

        # 2. From data-occludable-job-id attribute
        card_mock = MagicMock()
        card_mock.get_attribute.side_effect = lambda attr: "87654321" if attr == "data-occludable-job-id" else None
        job_id = LinkedInJobParser.extract_job_id_from_card(card_mock)
        self.assertEqual(job_id, "87654321")

        # 3. From child anchor href
        card_mock = MagicMock()
        card_mock.get_attribute.return_value = None
        anchor_mock = MagicMock()
        anchor_mock.get_attribute.return_value = "https://www.linkedin.com/jobs/view/99887766/?eBP=CwEAAAGW..."
        card_mock.find_elements.return_value = [anchor_mock]
        job_id = LinkedInJobParser.extract_job_id_from_card(card_mock)
        self.assertEqual(job_id, "99887766")

    def test_rotator_search_url_construction(self):
        rotator = LinkedInRotator(browser=MagicMock())
        url = rotator.build_search_url("Senior Python Developer", start=50)
        self.assertIn("keywords=Senior+Python+Developer", url)
        self.assertIn("f_AL=true", url)
        self.assertIn("start=50", url)

    def test_applier_skips_already_handled(self):
        tracker_mock = MagicMock(spec=ApplicationTracker)
        tracker_mock.is_already_handled.return_value = (True, "Already submitted")

        browser_mock = MagicMock()
        browser_mock.driver = MagicMock()

        applier = LinkedInApplier(browser=browser_mock, tracker=tracker_mock)
        res = applier.apply_to_job(
            job_id="112233",
            title="Software Engineer",
            company="Google",
            location="Mountain View",
            source_url="https://linkedin.com/jobs/view/112233",
        )

        self.assertEqual(res["status"], "SKIPPED")
        self.assertIn("Already submitted", res["reason"])
        # Should NOT click anything in the browser
        browser_mock.driver.find_elements.assert_not_called()

    def test_rotator_pre_filters_handled_jobs(self):
        tracker_mock = MagicMock(spec=ApplicationTracker)
        # First job is already handled, second is fresh
        tracker_mock.is_already_handled.side_effect = lambda jid, **kwargs: (True, "Already handled") if jid == "101" else (False, None)

        card1 = MagicMock()
        card1.get_attribute.side_effect = lambda attr: "101" if attr == "data-job-id" else None

        card2 = MagicMock()
        card2.get_attribute.side_effect = lambda attr: "102" if attr == "data-job-id" else None

        browser_mock = MagicMock()
        browser_mock.driver = MagicMock()
        browser_mock.driver.find_elements.return_value = [card1, card2]

        applier_mock = MagicMock(spec=LinkedInApplier)
        applier_mock.apply_to_job.return_value = {"status": "SUBMITTED"}

        rotator = LinkedInRotator(
            browser=browser_mock,
            tracker=tracker_mock,
            applier=applier_mock,
            search_terms=["Python"],
            max_pages_per_term=1,
        )

        stats = rotator.run()
        self.assertEqual(stats["jobs_evaluated"], 2)
        self.assertEqual(stats["jobs_skipped"], 1)
        self.assertEqual(stats["jobs_applied"], 1)
        # Card 1 should NEVER have been clicked because it was pre-filtered
        card1.click.assert_not_called()


if __name__ == "__main__":
    unittest.main()
