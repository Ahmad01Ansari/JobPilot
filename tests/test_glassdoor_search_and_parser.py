'''
Unit Tests for Glassdoor Search, Parser, and Flow Detection (Phases D, E, F, G)
Validates URL construction, card parsing, JD extraction with fallbacks, and application flow detection.
'''

import unittest
from unittest.mock import MagicMock

from platforms.glassdoor.search import build_search_url, GlassdoorJobItem
from platforms.glassdoor.parser import GlassdoorParser, is_valid_job_description
from platforms.glassdoor.applier import GlassdoorFlowDetector


class TestGlassdoorSearchAndParser(unittest.TestCase):
    def test_build_search_url_basic(self):
        url = build_search_url("RPA Developer", "India")
        self.assertIn("sc.keyword=RPA+Developer", url)
        self.assertIn("locKeyword=India", url)
        self.assertTrue(url.startswith("https://www.glassdoor.com/Job/jobs.htm"))

    def test_build_search_url_with_filters(self):
        url = build_search_url("Python Developer", "Delhi", from_age=3, page=2)
        self.assertIn("sc.keyword=Python+Developer", url)
        self.assertIn("locKeyword=Delhi", url)
        self.assertIn("fromAge=3", url)
        self.assertIn("p=2", url)

    def test_is_valid_job_description(self):
        self.assertFalse(is_valid_job_description(None))
        self.assertFalse(is_valid_job_description(""))
        self.assertFalse(is_valid_job_description("Short text"))
        self.assertFalse(is_valid_job_description("Please sign in to view the complete job description."))

        valid_jd = (
            "We are seeking an experienced RPA Developer proficient in Automation Anywhere 360, "
            "Python, SQL, and enterprise process automation. You will design, build, and deploy "
            "mission-critical automation workflows across global finance and operations teams."
        )
        self.assertTrue(is_valid_job_description(valid_jd))

    def test_parse_job_card(self):
        mock_card = MagicMock()
        mock_card.get_attribute.side_effect = lambda attr: "12345" if attr in ["data-jobid", "data-id"] else None

        title_el = MagicMock()
        title_el.text = "Lead RPA Developer"

        comp_el = MagicMock()
        comp_el.text = "Acme Corp"

        loc_el = MagicMock()
        loc_el.text = "Bengaluru, India"

        sal_el = MagicMock()
        sal_el.text = "₹12L - ₹18L"

        rating_el = MagicMock()
        rating_el.text = "4.2"

        def find_element_side_effect(by, sel):
            if "title" in sel:
                return title_el
            elif "employer" in sel:
                return comp_el
            elif "location" in sel:
                return loc_el
            elif "Salary" in sel or "salary" in sel:
                return sal_el
            elif "rating" in sel:
                return rating_el
            return MagicMock()

        mock_card.find_element.side_effect = find_element_side_effect

        mock_easy_apply_el = MagicMock()
        mock_easy_apply_el.is_displayed.return_value = True
        mock_card.find_elements.side_effect = lambda by, sel: [mock_easy_apply_el] if "Easy Apply" in sel else []

        item = GlassdoorParser.parse_job_card(mock_card)
        self.assertIsNotNone(item)
        self.assertEqual(item.title, "Lead RPA Developer")
        self.assertEqual(item.company, "Acme Corp")
        self.assertEqual(item.location, "Bengaluru, India")
        self.assertEqual(item.salary, "₹12L - ₹18L")
        self.assertEqual(item.rating, "4.2")
        self.assertTrue(item.is_easy_apply)
        self.assertEqual(item.job_id, "12345")

    def test_flow_detector_easy_apply(self):
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True
        mock_btn.is_enabled.return_value = True

        mock_driver.find_elements.side_effect = lambda by, sel: [mock_btn] if "easy-apply" in sel or "Easy Apply" in sel else []

        flow, btn = GlassdoorFlowDetector.detect_flow(mock_driver)
        self.assertEqual(flow, "EASY_APPLY")
        self.assertEqual(btn, mock_btn)

    def test_flow_detector_external(self):
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True

        # Return empty for easy apply, return mock_btn for external apply
        def find_side_effect(by, sel):
            if "easy" in sel.lower():
                return []
            if "company site" in sel or "employer site" in sel or "@data-test='apply-button'" in sel:
                return [mock_btn]
            return []

        mock_driver.find_elements.side_effect = find_side_effect

        flow, btn = GlassdoorFlowDetector.detect_flow(mock_driver)
        self.assertEqual(flow, "EXTERNAL")
        self.assertEqual(btn, mock_btn)

    def test_flow_detector_already_applied(self):
        mock_driver = MagicMock()
        mock_badge = MagicMock()
        mock_badge.is_displayed.return_value = True

        def find_side_effect(by, sel):
            if "Applied" in sel or "applied" in sel:
                return [mock_badge]
            return []

        mock_driver.find_elements.side_effect = find_side_effect

        flow, btn = GlassdoorFlowDetector.detect_flow(mock_driver)
        self.assertEqual(flow, "ALREADY_APPLIED")
    def test_search_via_ui_automation(self):
        from platforms.glassdoor.search import GlassdoorSearch

        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver
        mock_driver.current_url = "https://www.glassdoor.com/Job/index.htm"

        mock_kw_input = MagicMock()
        mock_kw_input.is_displayed.return_value = True

        mock_loc_input = MagicMock()
        mock_loc_input.is_displayed.return_value = True

        mock_submit_btn = MagicMock()
        mock_submit_btn.is_displayed.return_value = True
        mock_submit_btn.is_enabled.return_value = True

        def find_elements_mock(by, sel):
            if "keyword" in sel or "jobTitle" in sel:
                return [mock_kw_input]
            if "location" in sel:
                return [mock_loc_input]
            if "search" in sel or "submit" in sel:
                return [mock_submit_btn]
            return []

        mock_driver.find_elements.side_effect = find_elements_mock

        search_engine = GlassdoorSearch(mock_browser)
        success = search_engine.search_via_ui("RPA Developer", "Bengaluru", easy_apply_only=False)

        self.assertTrue(success)
        mock_kw_input.click.assert_called()
        mock_loc_input.click.assert_called()
        mock_submit_btn.click.assert_called()


if __name__ == "__main__":
    unittest.main()
