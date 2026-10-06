'''
Glassdoor Platform Automation Package
Provides modular platform automation for Glassdoor job applications.
'''

from platforms.glassdoor.selectors import *  # noqa: F401, F403
from platforms.glassdoor.exceptions import (
    GlassdoorError,
    GlassdoorLoginError,
    GlassdoorCaptchaError,
    GlassdoorSessionError,
    GlassdoorElementNotFoundError,
    GlassdoorSubmissionError,
)
from platforms.glassdoor.browser import GlassdoorBrowser, get_default_glassdoor_profile_dir
from platforms.glassdoor.auth import GlassdoorAuth
from platforms.glassdoor.search import GlassdoorSearch, GlassdoorJobItem, build_search_url
from platforms.glassdoor.parser import GlassdoorParser, is_valid_job_description
from platforms.glassdoor.form import GlassdoorForm
from platforms.glassdoor.submitter import GlassdoorSubmitter
from platforms.glassdoor.captcha_handler import GlassdoorCaptchaHandler
from platforms.glassdoor.applier import GlassdoorApplier, GlassdoorFlowDetector
from platforms.glassdoor.rotator import GlassdoorRotator

__all__ = [
    "GlassdoorError",
    "GlassdoorLoginError",
    "GlassdoorCaptchaError",
    "GlassdoorSessionError",
    "GlassdoorElementNotFoundError",
    "GlassdoorSubmissionError",
    "GlassdoorBrowser",
    "get_default_glassdoor_profile_dir",
    "GlassdoorAuth",
    "GlassdoorSearch",
    "GlassdoorJobItem",
    "build_search_url",
    "GlassdoorParser",
    "is_valid_job_description",
    "GlassdoorForm",
    "GlassdoorSubmitter",
    "GlassdoorCaptchaHandler",
    "GlassdoorApplier",
    "GlassdoorFlowDetector",
    "GlassdoorRotator",
]
