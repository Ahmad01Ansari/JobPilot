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

    def test_parser_ignores_ember_ids(self):
        # Ember component ID like id="ember912384" should NOT be extracted as a job ID
        card_ember = MagicMock()
        card_ember.get_attribute.side_effect = lambda attr: "ember912384" if attr == "id" else None
        card_ember.find_elements.return_value = []
        job_id = LinkedInJobParser.extract_job_id_from_card(card_ember)
        self.assertIsNone(job_id)

    def test_wait_for_job_cards_prioritizes_cards_over_banner(self):
        # Even if a banner element is in DOM, real cards should be found and returned
        card = MagicMock()
        card.is_displayed.return_value = True

        banner = MagicMock()
        banner.is_displayed.return_value = True
        banner.text = "No matching jobs found"

        driver_mock = MagicMock()
        # When querying for card selectors, return [card]
        # When querying for banner, return [banner]
        def mock_find_elements(by, selector):
            if "job" in selector or "scaffold" in selector or "data-occludable" in selector:
                return [card]
            if "no-results" in selector or "No matching" in selector:
                return [banner]
            return []

        driver_mock.find_elements.side_effect = mock_find_elements

        rotator = LinkedInRotator(browser=MagicMock())
        cards = rotator.wait_for_job_cards(driver_mock, max_wait=3.0)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0], card)

    def test_rotator_card_click_handles_interception(self):
        # When card.click() throws ElementClickInterceptedException, it should fallback to inner clickable or JS click
        card = MagicMock()
        card.get_attribute.side_effect = lambda attr: "4199887766" if attr == "data-job-id" else None
        card.click.side_effect = Exception("element click intercepted: Element is not clickable")

        inner_title = MagicMock()
        inner_title.is_displayed.return_value = True
        inner_title.click.return_value = None

        card.find_elements.side_effect = lambda by, sel: [inner_title] if "title" in sel or "link" in sel else []

        driver_mock = MagicMock()
        driver_mock.find_elements.return_value = [card]

        applier_mock = MagicMock(spec=LinkedInApplier)
        applier_mock.apply_to_job.return_value = {"status": "SUBMITTED"}

        tracker_mock = MagicMock(spec=ApplicationTracker)
        tracker_mock.is_already_handled.return_value = (False, None)

        browser_mock = MagicMock()
        browser_mock.driver = driver_mock

        rotator = LinkedInRotator(
            browser=browser_mock,
            tracker=tracker_mock,
            applier=applier_mock,
            search_terms=["Developer"],
            max_pages_per_term=1,
        )

        stats = rotator.run()
        self.assertEqual(stats["jobs_applied"], 1)
        self.assertEqual(stats["jobs_skipped"], 0)
        # Verify the inner title was clicked as a fallback
        inner_title.click.assert_called_once()

    def test_parser_extracts_job_id_from_genesis_componentkey(self):
        # Genesis SDUI layout uses componentkey="job-card-component-ref-4459126215"
        card_genesis = MagicMock()
        card_genesis.get_attribute.side_effect = lambda attr: "job-card-component-ref-4459126215" if attr == "componentkey" else None
        card_genesis.find_elements.return_value = []
        job_id = LinkedInJobParser.extract_job_id_from_card(card_genesis)
        self.assertEqual(job_id, "4459126215")

    def test_parser_extracts_genesis_card_text_metadata(self):
        # Genesis SDUI card text parsing
        card_genesis = MagicMock()
        card_genesis.text = """Selected, RPA Developer II (Verified job)
RPA Developer II
Hollister Incorporated
Gurugram
3 school alumni work here
Saved"""
        card_genesis.find_elements.return_value = []

        driver_mock = MagicMock()
        driver_mock.find_elements.return_value = []

        title = LinkedInJobParser.extract_title(driver_mock, card_element=card_genesis)
        company = LinkedInJobParser.extract_company(driver_mock, card_element=card_genesis)
        location = LinkedInJobParser.extract_location(driver_mock, card_element=card_genesis)

        self.assertEqual(title, "RPA Developer II")
        self.assertEqual(company, "Hollister Incorporated")
        self.assertEqual(location, "Gurugram")

    def test_applier_finds_genesis_dialog_modal(self):
        # Genesis SDUI modal uses <dialog data-testid="dialog" open="">
        dialog_mock = MagicMock()
        dialog_mock.is_displayed.return_value = True

        driver_mock = MagicMock()
        driver_mock.find_elements.side_effect = lambda by, sel: [dialog_mock] if "dialog" in sel else []

        browser_mock = MagicMock()
        browser_mock.driver = driver_mock

        applier = LinkedInApplier(browser=browser_mock)
        found = applier._find_modal(driver_mock)
        self.assertIsNotNone(found)
        self.assertEqual(found, dialog_mock)

    def test_applier_answers_genesis_field_questions(self):
        # Genesis input with aria-label and empty value
        input_mock = MagicMock()
        input_mock.is_displayed.return_value = True
        input_mock.get_attribute.side_effect = lambda attr: (
            "" if attr == "value" else ("How many years of work experience do you have with Microsoft Power Automate?" if attr == "aria-label" else None)
        )

        modal_mock = MagicMock()
        modal_mock.find_elements.side_effect = lambda by, sel: [input_mock] if "input" in sel else []

        driver_mock = MagicMock()
        browser_mock = MagicMock()
        browser_mock.driver = driver_mock

        qna_mock = MagicMock()
        qna_mock.answer_text_question.return_value = "4"

        applier = LinkedInApplier(browser=browser_mock, qna_engine=qna_mock)
        applier._answer_step_questions(driver_mock, modal_mock)

        input_mock.send_keys.assert_called_with("4")
        qna_mock.answer_text_question.assert_called_once()

    def test_clickers_find_easy_apply_modal(self):
        from modules.clickers_and_finders import find_easy_apply_modal
        modal_el = MagicMock()
        modal_el.is_displayed.return_value = True

        driver_mock = MagicMock()
        driver_mock.find_elements.side_effect = lambda by, sel: [modal_el] if "dialog" in sel else []

        result = find_easy_apply_modal(driver_mock, timeout=1.0)
        self.assertEqual(result, modal_el)

    def test_applier_answers_radio_group_hybrid(self):
        # Two radio inputs: Yes and No for "Are you comfortable working in a hybrid setting?*"
        r_yes = MagicMock()
        r_yes.is_displayed.return_value = True
        r_yes.is_selected.return_value = False
        r_yes.get_attribute.side_effect = lambda attr: "hybrid_group" if attr == "name" else ("yes_id" if attr == "id" else ("Yes" if attr == "value" else None))

        r_no = MagicMock()
        r_no.is_displayed.return_value = True
        r_no.is_selected.return_value = False
        r_no.get_attribute.side_effect = lambda attr: "hybrid_group" if attr == "name" else ("no_id" if attr == "id" else ("No" if attr == "value" else None))

        lbl_yes = MagicMock()
        lbl_yes.text = "Yes"
        lbl_yes.is_displayed.return_value = True

        lbl_no = MagicMock()
        lbl_no.text = "No"
        lbl_no.is_displayed.return_value = True

        title_p = MagicMock()
        title_p.text = "Are you comfortable working in a hybrid setting?*"
        title_p.is_displayed.return_value = True

        ancestor_mock = MagicMock()
        ancestor_mock.find_elements.side_effect = lambda by, sel: [title_p]

        r_yes.find_element.side_effect = lambda by, sel: ancestor_mock

        modal_mock = MagicMock()
        modal_mock.find_elements.side_effect = lambda by, sel: (
            [r_yes, r_no] if "radio" in sel else ([lbl_yes] if "yes_id" in sel else ([lbl_no] if "no_id" in sel else []))
        )

        driver_mock = MagicMock()
        browser_mock = MagicMock()
        browser_mock.driver = driver_mock

        applier = LinkedInApplier(browser=browser_mock)
        applier._answer_radio_groups(driver_mock, modal_mock)

        # Verify JS was executed to set checked=true and dispatch change event
        driver_mock.execute_script.assert_called()
        call_args = driver_mock.execute_script.call_args[0]
        self.assertIn("checked = true", call_args[0])
        self.assertEqual(call_args[1], r_yes)


if __name__ == "__main__":
    unittest.main()
