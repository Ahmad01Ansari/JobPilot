'''
Unit Tests for Glassdoor Selectors & Triggers
Validates XPath and CSS selector definitions and ensures fallback coverage.
Fulfills Phase A deliverable: Validated selector inventory.
'''

import unittest
from platforms.glassdoor.selectors import (
    HOME_URL,
    LOGIN_URL,
    SEARCH_BASE_URL,
    INDIA_HOME_URL,
    INDIA_SEARCH_BASE_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
    LOGIN_EMAIL_INPUTS,
    LOGIN_PASSWORD_INPUTS,
    LOGIN_SUBMIT_BUTTONS,
    MODAL_CLOSE_BUTTONS,
    COOKIE_ACCEPT_BUTTONS,
    SEARCH_KEYWORD_INPUTS,
    SEARCH_LOCATION_INPUTS,
    SEARCH_SUBMIT_BUTTONS,
    EASY_APPLY_FILTER_BUTTONS,
    DATE_POSTED_FILTER_BUTTONS,
    DATE_POSTED_OPTIONS,
    JOB_CARD_ELEMENTS,
    CARD_TITLE_SELECTORS,
    CARD_COMPANY_SELECTORS,
    CARD_LOCATION_SELECTORS,
    CARD_SALARY_SELECTORS,
    CARD_RATING_SELECTORS,
    CARD_EASY_APPLY_INDICATORS,
    CARD_ALREADY_APPLIED_INDICATORS,
    DETAILS_PANE_SELECTORS,
    DETAIL_TITLE_SELECTORS,
    DETAIL_COMPANY_SELECTORS,
    DETAIL_LOCATION_SELECTORS,
    JOB_DESCRIPTION_SELECTORS,
    JD_SHOW_MORE_BUTTONS,
    APPLY_EASY_TRIGGERS,
    APPLY_EXTERNAL_TRIGGERS,
    APPLY_ALREADY_BADGES,
    EASY_APPLY_MODAL_CONTAINERS,
    FORM_FIRST_NAME_INPUTS,
    FORM_LAST_NAME_INPUTS,
    FORM_EMAIL_INPUTS,
    FORM_PHONE_INPUTS,
    FORM_LOCATION_INPUTS,
    FORM_RESUME_FILE_INPUTS,
    FORM_CONTINUE_BUTTONS,
    FORM_SUBMIT_BUTTONS,
    SUBMIT_SUCCESS_CONTAINERS,
    CAPTCHA_IFRAME_SELECTORS,
    CAPTCHA_CONTAINER_SELECTORS,
    PAGINATION_NEXT_BUTTONS,
    PAGINATION_CURRENT_PAGE,
)


class TestGlassdoorSelectors(unittest.TestCase):
    def test_urls(self):
        self.assertTrue(HOME_URL.startswith("https://www.glassdoor.com"))
        self.assertTrue(SEARCH_BASE_URL.startswith("https://www.glassdoor.com/Job/jobs.htm"))
        self.assertTrue(INDIA_HOME_URL.startswith("https://www.glassdoor.co.in"))
        self.assertTrue(INDIA_SEARCH_BASE_URL.startswith("https://www.glassdoor.co.in/Job/jobs.htm"))
        self.assertIn("login", LOGIN_URL.lower())

    def test_auth_selectors_non_empty(self):
        self.assertGreater(len(LOGGED_IN_SELECTORS), 0)
        self.assertGreater(len(LOGIN_REQUIRED_SELECTORS), 0)
        self.assertGreater(len(LOGIN_EMAIL_INPUTS), 0)
        self.assertGreater(len(LOGIN_PASSWORD_INPUTS), 0)
        self.assertGreater(len(LOGIN_SUBMIT_BUTTONS), 0)

    def test_overlay_dismissal_selectors_non_empty(self):
        self.assertGreater(len(MODAL_CLOSE_BUTTONS), 0)
        self.assertGreater(len(COOKIE_ACCEPT_BUTTONS), 0)

    def test_search_inputs_and_filters_non_empty(self):
        self.assertGreater(len(SEARCH_KEYWORD_INPUTS), 0)
        self.assertGreater(len(SEARCH_LOCATION_INPUTS), 0)
        self.assertGreater(len(SEARCH_SUBMIT_BUTTONS), 0)
        self.assertGreater(len(EASY_APPLY_FILTER_BUTTONS), 0)
        self.assertGreater(len(DATE_POSTED_FILTER_BUTTONS), 0)
        for key in ["last_24_hours", "last_3_days", "last_week", "last_month"]:
            self.assertIn(key, DATE_POSTED_OPTIONS)
            self.assertGreater(len(DATE_POSTED_OPTIONS[key]), 0)

    def test_job_card_selectors_non_empty(self):
        self.assertGreater(len(JOB_CARD_ELEMENTS), 0)
        self.assertGreater(len(CARD_TITLE_SELECTORS), 0)
        self.assertGreater(len(CARD_COMPANY_SELECTORS), 0)
        self.assertGreater(len(CARD_LOCATION_SELECTORS), 0)
        self.assertGreater(len(CARD_SALARY_SELECTORS), 0)
        self.assertGreater(len(CARD_RATING_SELECTORS), 0)
        self.assertGreater(len(CARD_EASY_APPLY_INDICATORS), 0)
        self.assertGreater(len(CARD_ALREADY_APPLIED_INDICATORS), 0)

    def test_job_details_and_jd_selectors_non_empty(self):
        self.assertGreater(len(DETAILS_PANE_SELECTORS), 0)
        self.assertGreater(len(DETAIL_TITLE_SELECTORS), 0)
        self.assertGreater(len(DETAIL_COMPANY_SELECTORS), 0)
        self.assertGreater(len(DETAIL_LOCATION_SELECTORS), 0)
        self.assertGreater(len(JOB_DESCRIPTION_SELECTORS), 0)
        self.assertGreater(len(JD_SHOW_MORE_BUTTONS), 0)

    def test_application_triggers_non_empty(self):
        self.assertGreater(len(APPLY_EASY_TRIGGERS), 0)
        self.assertTrue(any("Easy Apply" in sel for sel in APPLY_EASY_TRIGGERS))
        self.assertGreater(len(APPLY_EXTERNAL_TRIGGERS), 0)
        self.assertTrue(any("company site" in sel.lower() or "employer site" in sel.lower() for sel in APPLY_EXTERNAL_TRIGGERS))
        self.assertGreater(len(APPLY_ALREADY_BADGES), 0)

    def test_form_selectors_non_empty(self):
        self.assertGreater(len(EASY_APPLY_MODAL_CONTAINERS), 0)
        self.assertGreater(len(FORM_FIRST_NAME_INPUTS), 0)
        self.assertGreater(len(FORM_LAST_NAME_INPUTS), 0)
        self.assertGreater(len(FORM_EMAIL_INPUTS), 0)
        self.assertGreater(len(FORM_PHONE_INPUTS), 0)
        self.assertGreater(len(FORM_LOCATION_INPUTS), 0)
        self.assertGreater(len(FORM_RESUME_FILE_INPUTS), 0)
        self.assertGreater(len(FORM_CONTINUE_BUTTONS), 0)
        self.assertGreater(len(FORM_SUBMIT_BUTTONS), 0)

    def test_submit_confirmation_and_captcha_non_empty(self):
        self.assertGreater(len(SUBMIT_SUCCESS_CONTAINERS), 0)
        self.assertGreater(len(CAPTCHA_IFRAME_SELECTORS), 0)
        self.assertGreater(len(CAPTCHA_CONTAINER_SELECTORS), 0)

    def test_pagination_selectors_non_empty(self):
        self.assertGreater(len(PAGINATION_NEXT_BUTTONS), 0)
        self.assertGreater(len(PAGINATION_CURRENT_PAGE), 0)


if __name__ == "__main__":
    unittest.main()
