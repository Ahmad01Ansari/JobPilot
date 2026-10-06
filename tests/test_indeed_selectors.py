'''
Unit Tests for Indeed Selectors & Triggers
Validates XPath and CSS selector definitions and ensures fallback coverage.
'''

import unittest
from platforms.indeed.selectors import (
    HOME_URL,
    LOGIN_URL,
    SEARCH_BASE_URL,
    JOB_CARD_SELECTORS,
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    APPLY_NOW_TRIGGERS,
    APPLY_EXTERNAL_TRIGGERS,
    FORM_CONTINUE_BUTTONS,
    FINAL_SUBMIT_BUTTONS,
    REVIEW_CONTAINER,
    CONFIRMATION_HEADINGS,
)


class TestIndeedSelectors(unittest.TestCase):
    def test_urls(self):
        self.assertTrue(HOME_URL.startswith("https://in.indeed.com"))
        self.assertTrue(SEARCH_BASE_URL.startswith("https://in.indeed.com/jobs"))
        self.assertIn("secure.indeed.com", LOGIN_URL)

    def test_job_card_selectors_non_empty(self):
        self.assertGreater(len(JOB_CARD_SELECTORS), 0)
        self.assertIn("div.job_seen_beacon", JOB_CARD_SELECTORS)

    def test_job_title_selectors_non_empty(self):
        self.assertGreater(len(CARD_TITLE_SELECTORS), 0)
        self.assertIn("a.jcs-JobTitle", CARD_TITLE_SELECTORS)

    def test_company_name_selectors_non_empty(self):
        self.assertGreater(len(CARD_COMPANY_SELECTORS), 0)
        self.assertTrue(any("company-name" in sel for sel in CARD_COMPANY_SELECTORS))

    def test_apply_now_triggers(self):
        self.assertGreater(len(APPLY_NOW_TRIGGERS), 0)
        self.assertTrue(any("Apply now" in sel for sel in APPLY_NOW_TRIGGERS))

    def test_apply_external_triggers(self):
        self.assertGreater(len(APPLY_EXTERNAL_TRIGGERS), 0)
        self.assertTrue(any("company site" in sel for sel in APPLY_EXTERNAL_TRIGGERS))

    def test_continue_buttons(self):
        self.assertGreater(len(FORM_CONTINUE_BUTTONS), 0)
        self.assertTrue(any("Continue" in sel for sel in FORM_CONTINUE_BUTTONS))

    def test_submit_buttons(self):
        self.assertGreater(len(FINAL_SUBMIT_BUTTONS), 0)
        self.assertTrue(any("Submit your application" in sel for sel in FINAL_SUBMIT_BUTTONS))

    def test_review_indicators(self):
        self.assertGreater(len(REVIEW_CONTAINER), 0)

    def test_confirmation_patterns(self):
        self.assertGreater(len(CONFIRMATION_HEADINGS), 0)


if __name__ == "__main__":
    unittest.main()
