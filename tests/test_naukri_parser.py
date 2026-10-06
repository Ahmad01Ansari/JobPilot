import unittest
from unittest.mock import MagicMock
from platforms.naukri.parser import (
    parse_experience_string,
    parse_salary_string,
    parse_work_style,
    extract_job_id,
    NaukriJobParser,
)
from platforms.naukri.selectors import (
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_EXPERIENCE_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_DESCRIPTION_SNIPPET,
    CARD_POSTED_DATE,
)
from modules.models import Job


class TestNaukriParser(unittest.TestCase):
    def test_parse_experience_string(self):
        # Ranges
        self.assertEqual(parse_experience_string("1-5 Yrs"), (1, 5))
        self.assertEqual(parse_experience_string("0-2 Yrs"), (0, 2))
        self.assertEqual(parse_experience_string("3 - 6 Yrs"), (3, 6))
        self.assertEqual(parse_experience_string("2 to 4 years"), (2, 4))

        # Plus pattern
        self.assertEqual(parse_experience_string("2+ Yrs"), (2, None))
        self.assertEqual(parse_experience_string("5+ years"), (5, None))

        # Freshers
        self.assertEqual(parse_experience_string("Fresher"), (0, 0))
        self.assertEqual(parse_experience_string("Freshers can apply"), (0, 0))

        # Empty / Undisclosed
        self.assertEqual(parse_experience_string("Not Disclosed"), (None, None))
        self.assertEqual(parse_experience_string(""), (None, None))

    def test_parse_salary_string(self):
        # Lacs PA
        self.assertEqual(parse_salary_string("3-6 Lacs PA"), (300000, 600000))
        self.assertEqual(parse_salary_string("3.5 - 5.5 Lacs PA"), (350000, 550000))
        self.assertEqual(parse_salary_string("6.0 Lacs PA"), (600000, None))

        # Raw commas
        self.assertEqual(parse_salary_string("50,000 - 1,00,000 PA"), (50000, 100000))

        # Not Disclosed / Unspecified
        self.assertEqual(parse_salary_string("Not Disclosed"), (None, None))
        self.assertEqual(parse_salary_string("Unspecified"), (None, None))
        self.assertEqual(parse_salary_string(""), (None, None))

    def test_parse_work_style(self):
        self.assertEqual(parse_work_style("Remote", "RPA Dev"), "Remote")
        self.assertEqual(parse_work_style("Delhi", "RPA Dev (Work from Home)"), "Remote")
        self.assertEqual(parse_work_style("Bengaluru", "Automation Engineer", "Hybrid working model"), "Hybrid")
        self.assertEqual(parse_work_style("Noida", "Python Dev"), "On-site")
        self.assertIsNone(parse_work_style("", "Dev"))

    def test_extract_job_id(self):
        # 1. From element attribute
        mock_elem = MagicMock()
        mock_elem.get_attribute.side_effect = lambda attr: "9876543210" if attr == "data-job-id" else None
        self.assertEqual(extract_job_id(card=mock_elem), "9876543210")

        # 2. From URL
        url1 = "https://www.naukri.com/job-listings-rpa-developer-avent-iq-noida-123456789012?src=seo"
        self.assertEqual(extract_job_id(source_url=url1), "123456789012")

    def test_parse_card_to_normalized_job(self):
        mock_card = MagicMock()
        mock_card.get_attribute.side_effect = lambda attr: "naukri_job_1122" if attr == "data-job-id" else None

        # Mock sub elements
        def make_elem(text="", href=None):
            e = MagicMock()
            e.text = text
            e.get_attribute.side_effect = lambda a: href if a == "href" else None
            return e

        title_elem = make_elem("Senior RPA Developer", "https://www.naukri.com/job-listings-rpa-1122?src=search")
        comp_elem = make_elem("AventIQ AI")
        loc_elem = make_elem("Delhi / NCR, Remote")
        exp_elem = make_elem("2-4 Yrs")
        sal_elem = make_elem("4.5 - 6.5 Lacs PA")
        desc_elem = make_elem("Experience with Automation Anywhere 360 and Python.")
        date_elem = make_elem("2 Days Ago")

        def find_elements(by, selector):
            if selector in CARD_TITLE_SELECTORS:
                return [title_elem]
            if selector in CARD_COMPANY_SELECTORS:
                return [comp_elem]
            if selector in CARD_LOCATION_SELECTORS:
                return [loc_elem]
            if selector in CARD_EXPERIENCE_SELECTORS:
                return [exp_elem]
            if selector in CARD_SALARY_SELECTORS:
                return [sal_elem]
            if selector in CARD_DESCRIPTION_SNIPPET:
                return [desc_elem]
            if selector in CARD_POSTED_DATE:
                return [date_elem]
            return []

        mock_card.find_elements.side_effect = find_elements

        job = NaukriJobParser.parse_card(mock_card)
        self.assertIsNotNone(job)
        self.assertIsInstance(job, Job)
        self.assertEqual(job.platform, "naukri")
        self.assertEqual(job.job_id, "naukri_job_1122")
        self.assertEqual(job.title, "Senior RPA Developer")
        self.assertEqual(job.company, "AventIQ AI")
        self.assertEqual(job.location, "Delhi / NCR, Remote")
        self.assertEqual(job.work_style, "Remote")
        self.assertEqual(job.required_experience_min, 2)
        self.assertEqual(job.required_experience_max, 4)
        self.assertEqual(job.salary_min, 450000)
        self.assertEqual(job.salary_max, 650000)
        self.assertEqual(job.posted_date, "2 Days Ago")
        self.assertEqual(job.source_url, "https://www.naukri.com/job-listings-rpa-1122")


if __name__ == "__main__":
    unittest.main()
