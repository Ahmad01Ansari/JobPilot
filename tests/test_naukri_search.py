import unittest
from unittest.mock import MagicMock
from platforms.naukri.search import build_search_url, slugify, NaukriSearch
from platforms.naukri.selectors import (
    JOB_CARD_SELECTORS,
    NO_JOBS_SELECTORS,
    PAGINATION_NEXT_BUTTONS,
)


class TestNaukriSearch(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("RPA Developer"), "rpa-developer")
        self.assertEqual(slugify("Python Automation Engineer"), "python-automation-engineer")
        self.assertEqual(slugify("Delhi / NCR"), "delhi-ncr")
        self.assertEqual(slugify("AI & Automation"), "ai-automation")
        self.assertEqual(slugify("  Automation Anywhere  "), "automation-anywhere")

    def test_build_search_url_basic(self):
        url = build_search_url(keyword="RPA Developer", location="India")
        self.assertTrue(url.startswith("https://www.naukri.com/rpa-developer-jobs-in-india?"))
        self.assertIn("k=RPA+Developer", url)
        self.assertIn("l=India", url)

    def test_build_search_url_with_experience_and_freshness(self):
        url = build_search_url(
            keyword="RPA Developer",
            location="India",
            experience_years=2,
            freshness_days=7,
        )
        self.assertTrue(url.startswith("https://www.naukri.com/rpa-developer-jobs-in-india?"))
        self.assertIn("experience=2", url)
        self.assertIn("nignrpmexp=Y", url)
        self.assertIn("jobAge=7", url)

    def test_build_search_url_pagination(self):
        url = build_search_url(
            keyword="RPA Developer",
            location="India",
            experience_years=2,
            page=3,
        )
        self.assertTrue(url.startswith("https://www.naukri.com/rpa-developer-jobs-in-india-3?"))

    def test_build_search_url_keyword_only(self):
        url = build_search_url(keyword="Python Automation")
        self.assertTrue(url.startswith("https://www.naukri.com/python-automation-jobs?"))
        self.assertIn("k=Python+Automation", url)

    def test_search_discovers_cards(self):
        mock_browser = MagicMock()
        mock_browser.navigate.return_value = True

        mock_driver = MagicMock()
        mock_card1 = MagicMock()
        mock_card2 = MagicMock()

        def find_elements(by, selector):
            if selector in NO_JOBS_SELECTORS:
                return []
            if selector == JOB_CARD_SELECTORS[0]:
                return [mock_card1, mock_card2]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_driver.execute_script.return_value = 1000
        mock_browser.driver = mock_driver

        search_engine = NaukriSearch(mock_browser)
        cards = search_engine.search(
            keyword="RPA Developer",
            location="India",
            experience_years=2,
            scroll_to_hydrate=False,
        )

        self.assertEqual(len(cards), 2)
        mock_browser.navigate.assert_called_once()

    def test_search_zero_results(self):
        mock_browser = MagicMock()
        mock_browser.navigate.return_value = True

        mock_driver = MagicMock()
        mock_zero_elem = MagicMock()
        mock_zero_elem.is_displayed.return_value = True

        def find_elements(by, selector):
            if selector in NO_JOBS_SELECTORS:
                return [mock_zero_elem]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_browser.driver = mock_driver

        search_engine = NaukriSearch(mock_browser)
        cards = search_engine.search(keyword="NonexistentSkill123", scroll_to_hydrate=False)
        self.assertEqual(len(cards), 0)

    def test_has_next_page(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_btn = MagicMock()
        mock_btn.is_displayed.return_value = True
        mock_btn.is_enabled.return_value = True

        def find_elements(by, selector):
            if selector == PAGINATION_NEXT_BUTTONS[0]:
                return [mock_btn]
            return []

        mock_driver.find_elements.side_effect = find_elements
        mock_browser.driver = mock_driver

        search_engine = NaukriSearch(mock_browser)
        self.assertTrue(search_engine.has_next_page())


if __name__ == "__main__":
    unittest.main()
