'''
Foundit Platform Automation Package
'''

from platforms.foundit.browser import FounditBrowser, DEFAULT_FOUNDIT_PROFILE_DIR
from platforms.foundit.auth import FounditAuth
from platforms.foundit.search import FounditSearch, build_search_url, slugify
from platforms.foundit.parser import (
    FounditJobParser,
    parse_experience_string,
    parse_salary_string,
    is_valid_job_description,
)
from platforms.foundit.rotator import (
    FounditRotator,
    FounditRotationConfig,
    RotationStats,
    TermStats,
)
from platforms.foundit.submitter import FounditSubmitter
from platforms.foundit.form import FounditForm
from platforms.foundit.applier import FounditApplier, FounditFlowDetector
from platforms.foundit.exceptions import (
    FounditError,
    FounditLoginError,
    FounditCaptchaError,
    FounditSessionError,
    FounditElementNotFoundError,
    FounditSubmissionError,
)
from platforms.foundit.selectors import (
    HOME_URL,
    LOGIN_URL,
    SEARCH_BASE_URL,
)

__all__ = [
    "FounditBrowser",
    "FounditAuth",
    "FounditSearch",
    "FounditJobParser",
    "FounditRotator",
    "FounditRotationConfig",
    "FounditSubmitter",
    "FounditForm",
    "FounditApplier",
    "FounditFlowDetector",
    "DEFAULT_FOUNDIT_PROFILE_DIR",
    "FounditError",
    "FounditLoginError",
    "FounditCaptchaError",
    "FounditSessionError",
    "FounditElementNotFoundError",
    "FounditSubmissionError",
    "build_search_url",
    "slugify",
    "parse_experience_string",
    "parse_salary_string",
    "is_valid_job_description",
    "RotationStats",
    "TermStats",
    "HOME_URL",
    "LOGIN_URL",
    "SEARCH_BASE_URL",
]
