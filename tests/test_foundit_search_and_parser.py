"""
tests/test_foundit_search_and_parser.py

Unit tests for Foundit URL construction, card extraction, experience/salary
parsing, and job description extraction.
"""

import unittest
from unittest.mock import MagicMock

from platforms.foundit.search import (
    build_search_url,
    get_pagination_offset,
    slugify_query,
    slugify,
)
from platforms.foundit.parser import (
    parse_experience_string,
    parse_salary_string,
    is_valid_job_description,
    FounditJobParser,
)


class TestFounditSearch(unittest.TestCase):
    """Tests for search URL generation and query slugification."""

    def test_slugify_query(self):
        self.assertEqual(slugify("Python Developer"), "python-developer")
        self.assertEqual(slugify_query("Data  Scientist / ML!"), "data-scientist-ml")
        self.assertEqual(slugify("C++ Engineer"), "c-engineer")
        self.assertEqual(slugify(""), "")

    def test_build_search_url_basic(self):
        url = build_search_url(keyword="Python Developer", location="Bengaluru")
        self.assertIn("https://www.foundit.in/search/python-developer-jobs-in-bengaluru", url)
        self.assertIn("query=Python+Developer", url)
        self.assertIn("location=Bengaluru", url)

    def test_build_search_url_with_experience_and_sort(self):
        url = build_search_url(
            keyword="Software Engineer",
            location="Delhi",
            experience_years=3,
            page=2,
        )
        self.assertIn("https://www.foundit.in/search/software-engineer-jobs-in-delhi", url)
        self.assertIn("experience=3", url)
        self.assertIn("query=Software+Engineer", url)

    def test_pagination_offset(self):
        self.assertEqual(get_pagination_offset(1), 0)
        self.assertEqual(get_pagination_offset(2), 15)
        self.assertEqual(get_pagination_offset(3), 30)
        self.assertEqual(get_pagination_offset(0), 0)


class TestFounditParser(unittest.TestCase):
    """Tests for experience, salary, and JD parsing."""

    def test_parse_experience_string(self):
        self.assertEqual(parse_experience_string("3 - 5 Years"), (3, 5))
        self.assertEqual(parse_experience_string("2 to 4 Yrs"), (2, 4))
        self.assertEqual(parse_experience_string("5+ Years"), (5, None))
        self.assertEqual(parse_experience_string("Fresher"), (0, 0))
        self.assertEqual(parse_experience_string("0-1 Years"), (0, 1))
        self.assertEqual(parse_experience_string("Not specified"), (None, None))
        self.assertEqual(parse_experience_string(None), (None, None))

    def test_parse_salary_string(self):
        min_sal, max_sal = parse_salary_string("6 - 12 LPA")
        self.assertEqual(min_sal, 600000)
        self.assertEqual(max_sal, 1200000)

        min_sal, max_sal = parse_salary_string("3.5 - 5.5 Lacs PA")
        self.assertEqual(min_sal, 350000)
        self.assertEqual(max_sal, 550000)

        min_sal, max_sal = parse_salary_string("Not disclosed")
        self.assertIsNone(min_sal)
        self.assertIsNone(max_sal)

        min_sal, max_sal = parse_salary_string(None)
        self.assertIsNone(min_sal)
        self.assertIsNone(max_sal)

    def test_is_valid_job_description(self):
        self.assertFalse(is_valid_job_description(""))
        self.assertFalse(is_valid_job_description("Short"))
        self.assertFalse(is_valid_job_description("Please login to view full details"))
        self.assertTrue(is_valid_job_description(
            "We are looking for an experienced Senior Python Developer with strong Django, "
            "FastAPI, and AWS skills to join our growing engineering team in Bengaluru."
        ))

    def test_extract_job_description_from_browser(self):
        """Tests that extract_job_description uses the fallback hierarchy."""
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        mock_elem = MagicMock()
        mock_elem.text = "A" * 150  # Satisfies >= 60 chars and valid
        mock_elem.is_displayed.return_value = True

        mock_driver.find_elements.side_effect = lambda by, sel: [mock_elem] if "jobDescription" in sel else []

        parser = FounditJobParser(mock_browser)
        jd = parser.extract_job_description()
        self.assertEqual(jd, "A" * 150)

    def test_extract_job_description_returns_empty_when_too_short(self):
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver

        mock_elem = MagicMock()
        mock_elem.text = "Too short"
        mock_elem.is_displayed.return_value = True
        mock_driver.find_elements.return_value = [mock_elem]

        parser = FounditJobParser(mock_browser)
        jd = parser.extract_job_description()
        self.assertEqual(jd, "")

    def test_parse_card(self):
        """Tests extracting job card details into a Job object."""
        mock_browser = MagicMock()
        parser = FounditJobParser(mock_browser)

        mock_card = MagicMock()
        mock_card.get_attribute.side_effect = lambda attr: "68631630" if attr == "id" else ""

        title_mock = MagicMock()
        title_mock.text = "Senior Python Developer"

        comp_mock = MagicMock()
        comp_mock.text = "Tech Solutions Ltd"

        loc_mock = MagicMock()
        loc_mock.text = "Bengaluru, Karnataka"

        exp_mock = MagicMock()
        exp_mock.text = "3-5 Yrs"

        sal_mock = MagicMock()
        sal_mock.text = "10 - 15 LPA"

        def find_elements_mock(by, sel):
            if "jobTitle" in sel:
                return [title_mock]
            if "companyName" in sel:
                return [comp_mock]
            if "location" in sel:
                return [loc_mock]
            if "experienceSalary" in sel or "details" in sel:
                return [exp_mock]
            if "salary" in sel:
                return [sal_mock]
            return []

        mock_card.find_elements.side_effect = find_elements_mock

        job = parser.parse_card(mock_card)
        self.assertEqual(job.job_id, "68631630")
        self.assertEqual(job.platform, "foundit")
        self.assertEqual(job.title, "Senior Python Developer")
        self.assertEqual(job.company, "Tech Solutions Ltd")
        self.assertEqual(job.location, "Bengaluru, Karnataka")
        self.assertEqual(job.required_experience_min, 3)
        self.assertEqual(job.required_experience_max, 5)
        self.assertEqual(job.salary_min, 1000000)
        self.assertEqual(job.salary_max, 1500000)

    def test_parse_full_job_page_already_applied(self):
        """Tests parsing a job page that was already applied to (e.g. Link 1 - Flex RPA Developer)."""
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver
        parser = FounditJobParser(browser=mock_browser)

        # Title h1
        h1_mock = MagicMock()
        h1_mock.text = "RPA Developer-IT"

        # Company
        comp_mock = MagicMock()
        comp_mock.text = "Flex"

        # Applied status badge
        applied_badge = MagicMock()
        applied_badge.is_displayed.return_value = True
        applied_badge.text = "Applied 35 minutes ago"

        # Meta elements (experience, location)
        exp_mock = MagicMock()
        exp_mock.text = "3-5 Years"
        loc_mock = MagicMock()
        loc_mock.text = "Chennai, India"

        # JD container
        jd_mock = MagicMock()
        jd_mock.is_displayed.return_value = True
        jd_mock.text = (
            "Job Description\n"
            "Flex is the diversified manufacturing partner of choice that helps market-leading brands design, build and deliver innovative products that improve the world."
        )

        mock_driver.find_elements.side_effect = lambda by, sel: (
            [h1_mock] if sel == "h1"
            else [comp_mock] if "company" in sel.lower()
            else [applied_badge] if "applied" in sel.lower() or "application status" in sel.lower()
            else [exp_mock, loc_mock] if "span or self::div" in sel
            else [jd_mock] if "job description" in sel.lower() or "detailscontainer" in sel.lower()
            else []
        )
        mock_driver.find_element.return_value = MagicMock(text="Your application status: Applied (26 Sept 2026)")

        res = parser.parse_full_job_page()
        self.assertTrue(res["is_applied"])
        self.assertIn("Applied", res["applied_status_text"])
        self.assertEqual(res["title"], "RPA Developer-IT")
        self.assertEqual(res["company"], "Flex")
        self.assertEqual(res["required_experience_min"], 3)
        self.assertEqual(res["required_experience_max"], 5)
        self.assertEqual(res["location"], "Chennai, India")
        self.assertIn("Flex is the diversified manufacturing partner", res["description"])

    def test_parse_full_job_page_non_applied_with_view_more(self):
        """Tests parsing a fresh non-applied job page with package and View More (e.g. Link 2 - Ishttaa Techcraft Automation Engineer)."""
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver
        parser = FounditJobParser(browser=mock_browser)

        h1_mock = MagicMock()
        h1_mock.text = "Automation Engineer"

        comp_mock = MagicMock()
        comp_mock.text = "Ishttaa Techcraft Private Limited"

        exp_mock = MagicMock()
        exp_mock.text = "2-5 Years"

        sal_mock = MagicMock()
        sal_mock.text = "₹ 0.5 - 5 LPA"

        loc_mock = MagicMock()
        loc_mock.text = "Hosur"

        # View more button
        view_more_btn = MagicMock()
        view_more_btn.is_displayed.return_value = True

        jd_mock = MagicMock()
        jd_mock.is_displayed.return_value = True
        jd_mock.text = (
            "Job Description\n"
            "Hands-on experience in PLC programming, debugging, and troubleshooting. "
            "Good understanding of machine sequencing and automation logic. "
            "Experience in electrical panel troubleshooting and fault diagnosis."
        )

        mock_driver.find_elements.side_effect = lambda by, sel: (
            [h1_mock] if sel == "h1"
            else [comp_mock] if "company" in sel.lower()
            else [] if "applied" in sel.lower() or "application status" in sel.lower()
            else [exp_mock, sal_mock, loc_mock] if "span or self::div" in sel
            else [view_more_btn] if "view more" in sel.lower()
            else [jd_mock] if "job description" in sel.lower() or "detailscontainer" in sel.lower()
            else []
        )
        mock_driver.find_element.return_value = MagicMock(text="Job Description")

        res = parser.parse_full_job_page()
        self.assertFalse(res["is_applied"])
        self.assertEqual(res["title"], "Automation Engineer")
        self.assertEqual(res["company"], "Ishttaa Techcraft Private Limited")
        self.assertEqual(res["required_experience_min"], 2)
        self.assertEqual(res["required_experience_max"], 5)
        self.assertEqual(res["salary_min"], 50000)
        self.assertEqual(res["salary_max"], 500000)
        self.assertEqual(res["location"], "Hosur")
        self.assertIn("PLC programming", res["description"])

    def test_parse_card_easy_apply_vs_external_portal(self):
        """Verifies that cards with 'Quick Apply' are EASY_APPLY/DIRECT, while cards without are COMPANY_PORTAL/EXTERNAL."""
        mock_browser = MagicMock()
        parser = FounditJobParser(mock_browser)

        # 1. Quick Apply card (e.g. Vinovaai)
        qa_card = MagicMock()
        qa_card.text = "UI Path RPA Developer\nVinovaai Private Limited\nQuick Apply\nPosted 30 days ago"
        qa_card.get_attribute.side_effect = lambda a: "cardContainer" if a == "class" else "vinovaai-1" if a == "id" else ""
        qa_title = MagicMock(text="UI Path RPA Developer")
        qa_comp = MagicMock(text="Vinovaai Private Limited")
        qa_card.find_elements.side_effect = lambda by, sel: (
            [qa_title] if "jobTitle" in sel
            else [qa_comp] if "companyName" in sel
            else []
        )
        qa_job = parser.parse_card(qa_card)
        self.assertEqual(qa_job.application_method, "EASY_APPLY")
        self.assertEqual(qa_job.apply_type, "DIRECT")

        # 2. External card without Quick Apply (e.g. Infosys Limited)
        ext_card = MagicMock()
        ext_card.text = "RPA Developer Automation Anywhere\nInfosys Limited\n3 - 5 Years\nBengaluru, India\nEarly Applicant\nPosted 2 months ago"
        ext_card.get_attribute.side_effect = lambda a: "cardContainer" if a == "class" else "infosys-1" if a == "id" else ""
        ext_title = MagicMock(text="RPA Developer Automation Anywhere")
        ext_comp = MagicMock(text="Infosys Limited")
        ext_card.find_elements.side_effect = lambda by, sel: (
            [ext_title] if "jobTitle" in sel
            else [ext_comp] if "companyName" in sel
            else []
        )
        ext_job = parser.parse_card(ext_card)
        self.assertEqual(ext_job.application_method, "COMPANY_PORTAL")
        self.assertEqual(ext_job.apply_type, "EXTERNAL")

    def test_search_canonical_url_and_sidebar_filters(self):
        """Verifies that search() navigates to canonical SEO search URL and applies filters via sidebar."""
        from platforms.foundit.search import FounditSearch
        mock_browser = MagicMock()
        mock_driver = MagicMock()
        mock_browser.driver = mock_driver
        search_engine = FounditSearch(mock_browser)
        search_engine.apply_sidebar_experience_filter = MagicMock(return_value=True)

        dummy_card = MagicMock()
        dummy_card.is_displayed.return_value = True
        dummy_card.get_attribute.side_effect = lambda a: "cardContainer" if a == "class" else "job-1" if a == "id" else ""
        dummy_card.text = "RPA Developer\nInfosys\n3-5 Yrs\nPosted 2 days ago"

        search_engine.find_job_cards = MagicMock(return_value=[dummy_card])

        cards = search_engine.search(
            keyword="rpa-developer",
            location="India",
            experience_years=3,
            freshness_days=7,
            quick_apply=False,
            page=1,
        )
        self.assertEqual(len(cards), 1)
        mock_browser.navigate.assert_called_once()
        nav_url = mock_browser.navigate.call_args[0][0]
        # Must use canonical search route, avoiding /srp/results split-pane mode
        self.assertIn("https://www.foundit.in/search/rpa-developer-jobs-in-india", nav_url)
        self.assertIn("query=rpa-developer", nav_url)
        self.assertIn("location=India", nav_url)
        # Filters are applied through the UI sidebar, not jammed into the URL query
        self.assertNotIn("experienceRanges=", nav_url)
        self.assertNotIn("jobAge=", nav_url)
        search_engine.apply_sidebar_experience_filter.assert_called_once_with(3)


if __name__ == "__main__":
    unittest.main()
