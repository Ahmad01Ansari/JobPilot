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

    def test_parser_extract_job_id_urn_and_query_param(self):
        # 4. From URN format (urn:li:fsd_jobPosting:4012345678)
        card_urn = MagicMock()
        card_urn.get_attribute.side_effect = lambda attr: "urn:li:fsd_jobPosting:4012345678" if attr == "data-entity-urn" else None
        job_id = LinkedInJobParser.extract_job_id_from_card(card_urn)
        self.assertEqual(job_id, "4012345678")

        # 5. From search query param currentJobId=55667788
        card_param = MagicMock()
        card_param.get_attribute.return_value = None
        anchor_mock = MagicMock()
        anchor_mock.get_attribute.return_value = "https://www.linkedin.com/jobs/search/?currentJobId=55667788&keywords=RPA"
        card_param.find_elements.return_value = [anchor_mock]
        job_id = LinkedInJobParser.extract_job_id_from_card(card_param)
        self.assertEqual(job_id, "55667788")

    def test_rotator_search_url_location_and_hybrid(self):
        # Hybrid mode (easy_apply_only=False) with location and date_posted
        rotator = LinkedInRotator(
            browser=MagicMock(),
            search_location="India",
            easy_apply_only=False,
            date_posted="Past week",
        )
        url = rotator.build_search_url("RPA Developer", start=25)
        self.assertIn("keywords=RPA+Developer", url)
        self.assertIn("location=India", url)
        self.assertNotIn("f_AL=true", url)
        self.assertIn("f_TPR=r604800", url)
        self.assertIn("start=25", url)

    def test_rotator_relevance_decay_switches_keyword(self):
        tracker_mock = MagicMock(spec=ApplicationTracker)
        # All jobs skipped as already handled to trigger relevance decay
        tracker_mock.is_already_handled.return_value = (True, "Already handled")

        card1 = MagicMock()
        card1.get_attribute.side_effect = lambda attr: "201" if attr == "data-job-id" else None
        card2 = MagicMock()
        card2.get_attribute.side_effect = lambda attr: "202" if attr == "data-job-id" else None

        browser_mock = MagicMock()
        browser_mock.driver = MagicMock()
        browser_mock.driver.find_elements.return_value = [card1, card2]

        rotator = LinkedInRotator(
            browser=browser_mock,
            tracker=tracker_mock,
            search_terms=["Term1", "Term2"],
            consecutive_skips_limit=2,
            max_pages_per_term=1,
        )

        stats = rotator.run()
        # Should have searched both terms because Term1 decayed after 2 skips
        self.assertEqual(stats["terms_searched"], 2)
        self.assertEqual(stats["jobs_skipped"], 4)


if __name__ == "__main__":
    unittest.main()
