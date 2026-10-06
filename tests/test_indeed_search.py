'''
Unit Tests for Indeed Search and URL Builder
Validates URL formatting, parameters, pagination, and job card extraction.
'''

import unittest
from unittest.mock import MagicMock, patch
from selenium.webdriver.common.by import By

from platforms.indeed.search import build_search_url, IndeedSearch, IndeedJobItem


class TestIndeedSearch(unittest.TestCase):
    def test_build_search_url_basic(self):
        url = build_search_url(keyword="RPA Developer", location="India")
        self.assertIn("q=RPA+Developer", url)
        self.assertIn("l=India", url)
        self.assertIn("sc=0kf%3Aattr%28DS3S6%29%3B", url)  # Easy Apply filter URL-encoded

    def test_build_search_url_freshness(self):
        url_1d = build_search_url(keyword="Python", location="Delhi", freshness_days=1)
        self.assertIn("fromage=1", url_1d)

        url_7d = build_search_url(keyword="Python", location="Delhi", freshness_days=7)
        self.assertIn("fromage=7", url_7d)

    def test_build_search_url_pagination(self):
        url_p1 = build_search_url(keyword="AI", page=1)
        self.assertNotIn("start=", url_p1)

        url_p2 = build_search_url(keyword="AI", page=2)
        self.assertIn("start=10", url_p2)

        url_p3 = build_search_url(keyword="AI", page=3)
        self.assertIn("start=20", url_p3)

    def test_build_search_url_without_easy_apply(self):
        url = build_search_url(keyword="QA", easy_apply_only=False)
        self.assertNotIn("DS3S6", url)

    def test_parse_job_card(self):
        mock_browser = MagicMock()
        search_engine = IndeedSearch(browser=mock_browser)

        mock_card = MagicMock()
        mock_title_el = MagicMock()
        mock_title_el.text = "Senior RPA Developer"
        def mock_get_attr(attr):
            if attr == "id":
                return "job_xyz123"
            elif attr == "href":
                return "https://in.indeed.com/viewjob?jk=xyz123"
            return ""
        mock_title_el.get_attribute.side_effect = mock_get_attr

        mock_company_el = MagicMock()
        mock_company_el.text = "Acme Automations"

        mock_loc_el = MagicMock()
        mock_loc_el.text = "Bengaluru, Karnataka"

        def find_elements_mock(by, sel):
            if "jcs-JobTitle" in sel:
                return [mock_title_el]
            elif "company-name" in sel or "company" in sel:
                return [mock_company_el]
            elif "location" in sel:
                return [mock_loc_el]
            elif "job-snippet" in sel:
                mock_snip = MagicMock()
                mock_snip.text = "3+ years of experience in UiPath development and process automation."
                return [mock_snip]
            return []

        mock_card.find_elements.side_effect = find_elements_mock
        mock_card.text = "Senior RPA Developer\nAcme Automations\nBengaluru, Karnataka\nEasily apply\n3+ years of experience"
        mock_card.get_attribute.return_value = ""

        item = search_engine._parse_job_card(mock_card)
        self.assertIsNotNone(item)
        self.assertEqual(item.title, "Senior RPA Developer")
        self.assertEqual(item.company, "Acme Automations")
        self.assertEqual(item.location, "Bengaluru, Karnataka")
        self.assertEqual(item.job_id, "xyz123")
        self.assertEqual(item.experience_text, "3+ Years")
        self.assertEqual(item.required_experience_min, 3)
        self.assertIn("UiPath development", item.description)

    def test_parse_indeed_salary(self):
        from platforms.indeed.search import parse_indeed_salary
        # Range in annual INR
        low, high = parse_indeed_salary("₹4,00,000 - ₹8,00,000 a year")
        self.assertEqual(low, 400000)
        self.assertEqual(high, 800000)

        # Monthly range
        low_m, high_m = parse_indeed_salary("₹25,000 - ₹35,000 a month")
        self.assertEqual(low_m, 300000)
        self.assertEqual(high_m, 420000)

        # Single salary
        low_s, high_s = parse_indeed_salary("₹50,000 a month")
        self.assertEqual(low_s, 600000)
        self.assertEqual(high_s, 600000)

        # Empty
        self.assertEqual(parse_indeed_salary(""), (None, None))

    def test_parse_indeed_experience(self):
        from platforms.indeed.search import parse_indeed_experience
        # User screenshot example: 'Experience: 1–4 Years' (en-dash)
        low, high, txt = parse_indeed_experience("Experience: 1–4 Years")
        self.assertEqual(low, 1)
        self.assertEqual(high, 4)
        self.assertEqual(txt, "1-4 Years")

        # Isolated range as on tags / badges
        low_iso, high_iso, txt_iso = parse_indeed_experience("5-6 Years")
        self.assertEqual(low_iso, 5)
        self.assertEqual(high_iso, 6)
        self.assertEqual(txt_iso, "5-6 Years")

        # 4-6 Years
        low_46, high_46, txt_46 = parse_indeed_experience("4-6 Years")
        self.assertEqual(low_46, 4)
        self.assertEqual(high_46, 6)
        self.assertEqual(txt_46, "4-6 Years")

        # Minimum pattern
        low_min, high_min, txt_min = parse_indeed_experience("min 3 years of hands-on experience")
        self.assertEqual(low_min, 3)
        self.assertIsNone(high_min)
        self.assertEqual(txt_min, "3+ Years")

        # Plus pattern
        low_p, high_p, txt_p = parse_indeed_experience("Experience: 3+ years")
        self.assertEqual(low_p, 3)
        self.assertIsNone(high_p)
        self.assertEqual(txt_p, "3+ Years")

        # In sentence
        low_s, high_s, txt_s = parse_indeed_experience("Candidate must have 2-5 years of experience in React")
        self.assertEqual(low_s, 2)
        self.assertEqual(high_s, 5)
        self.assertEqual(txt_s, "2-5 Years")

    def test_parse_indeed_work_style(self):
        from platforms.indeed.search import parse_indeed_work_style
        ws_office = parse_indeed_work_style("Mumbai", "Developer", "Work from Office Mandatory")
        self.assertEqual(ws_office, "On-site")

        ws_remote = parse_indeed_work_style("Remote", "Frontend Dev", "Flexible work from home")
        self.assertEqual(ws_remote, "Remote")

        ws_hybrid = parse_indeed_work_style("Pune", "Engineer", "Hybrid 3 days in office")
        self.assertEqual(ws_hybrid, "Hybrid")

    def test_indeed_job_item_to_job(self):
        item = IndeedJobItem(
            job_id="test_jk_123",
            title="RPA Developer",
            company="Step One Step Ahead LLP",
            location="Mumbai, Maharashtra",
            salary="₹4,00,000 - ₹8,00,000 a year",
            salary_min=400000,
            salary_max=800000,
            experience_text="1-4 Years",
            required_experience_min=1,
            required_experience_max=4,
            work_style="On-site",
            description="Full Job Description for UiPath Developer",
        )
        job = item.to_job()
        self.assertEqual(job.platform, "indeed")
        self.assertEqual(job.title, "RPA Developer")
        self.assertEqual(job.company, "Step One Step Ahead LLP")
        self.assertEqual(job.salary_min, 400000)
        self.assertEqual(job.salary_max, 800000)
        self.assertEqual(job.required_experience_min, 1)
        self.assertEqual(job.required_experience_max, 4)
        self.assertEqual(job.work_style, "On-site")
        self.assertEqual(job.description, "Full Job Description for UiPath Developer")
        self.assertEqual(job.raw_metadata.get("salary_text"), "₹4,00,000 - ₹8,00,000 a year")
        self.assertEqual(job.raw_metadata.get("experience_text"), "1-4 Years")

    def test_search_via_ui_flow(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://in.indeed.com/jobs?q=RPA+Developer&l=India"
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)
        # Mock execute_script to simulate successful input fill and submit
        mock_driver.execute_script.return_value = {"what": True, "where": True}

        with patch.object(search_engine, "apply_date_posted_filter", return_value=True) as mock_filter:
            with patch.object(search_engine, "parse_job_cards", return_value=[MagicMock()]) as mock_parse:
                with patch("time.sleep"):
                    results = search_engine.search_via_ui(
                        keyword="RPA Developer",
                        location="India",
                        freshness_days=3,
                        scroll_to_hydrate=False,
                    )
                    self.assertEqual(len(results), 1)
                    mock_filter.assert_called_once_with(3)
                    mock_parse.assert_called_once()

    def test_search_via_ui_fallback_when_empty_query(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        # Simulates Indeed UI dropping query and landing on empty q=
        mock_driver.current_url = "https://in.indeed.com/jobs?q=&l=India"
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)

        with patch.object(search_engine, "apply_date_posted_filter") as mock_filter:
            with patch.object(search_engine, "parse_job_cards", return_value=[MagicMock()]) as mock_parse:
                with patch("time.sleep"):
                    results = search_engine.search_via_ui(
                        keyword="RPA Developer",
                        location="India",
                        freshness_days=3,
                        scroll_to_hydrate=False,
                    )
                    self.assertEqual(len(results), 1)
                    # Verify direct URL fallback was triggered
                    mock_browser.navigate.assert_called()
                    self.assertIn("q=RPA+Developer", mock_browser.navigate.call_args[0][0])

    def test_apply_date_posted_filter_script(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)
        # 1st call opens popover (returns True), 2nd call selects option & clicks Update (returns success=True)
        mock_driver.execute_script.side_effect = [True, {"success": True, "updateClicked": True}]

        with patch("time.sleep"):
            success = search_engine.apply_date_posted_filter(freshness_days=3)
            self.assertTrue(success)

    def test_search_uses_ui_on_page_1_by_default(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)
        mock_item = MagicMock()

        with patch.object(search_engine, "search_via_ui", return_value=[mock_item]) as mock_ui:
            results = search_engine.search(
                keyword="RPA Developer",
                location="India",
                freshness_days=7,
                easy_apply_only=True,
                page=1,
            )
            self.assertEqual(results, [mock_item])
            mock_ui.assert_called_once_with(
                keyword="RPA Developer",
                location="India",
                freshness_days=7,
                scroll_to_hydrate=True,
            )

    def test_search_uses_direct_url_when_ui_disabled(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)
        mock_item = MagicMock()

        with patch.object(search_engine, "search_via_ui") as mock_ui:
            with patch.object(search_engine, "parse_job_cards", return_value=[mock_item]):
                with patch("time.sleep"):
                    results = search_engine.search(
                        keyword="RPA Developer",
                        location="India",
                        freshness_days=7,
                        easy_apply_only=True,
                        page=1,
                        use_ui_filters=False,
                    )
                    self.assertEqual(results, [mock_item])
                    mock_ui.assert_not_called()
                    mock_browser.navigate.assert_called_once()
                    called_url = mock_browser.navigate.call_args[0][0]
                    self.assertIn("fromage=7", called_url)
                    self.assertIn("sc=0kf%3Aattr%28DS3S6%29%3B", called_url)

    def test_search_uses_url_on_page_2(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        search_engine = IndeedSearch(browser=mock_browser)
        mock_item = MagicMock()

        with patch.object(search_engine, "search_via_ui") as mock_ui:
            with patch.object(search_engine, "parse_job_cards", return_value=[mock_item]):
                with patch("time.sleep"):
                    results = search_engine.search(
                        keyword="RPA Developer",
                        location="India",
                        page=2,
                    )
                    self.assertEqual(results, [mock_item])
                    mock_ui.assert_not_called()
                    mock_browser.navigate.assert_called_once()


if __name__ == "__main__":
    unittest.main()


