'''
Indeed Platform Automation Package
'''

from platforms.indeed.browser import IndeedBrowser, DEFAULT_INDEED_PROFILE_DIR
from platforms.indeed.selectors import (
    HOME_URL,
    LOGIN_URL,
    SEARCH_BASE_URL,
    LOGGED_IN_SELECTORS,
    LOGIN_REQUIRED_SELECTORS,
)
from platforms.indeed.search import IndeedSearch, IndeedJobItem, build_search_url
from platforms.indeed.form import IndeedForm
from platforms.indeed.safety_gate import IndeedSafetyGate, SafetyGateResult
from platforms.indeed.captcha_handler import IndeedCaptchaHandler
from platforms.indeed.submitter import IndeedSubmitter
from platforms.indeed.applier import IndeedApplier, IndeedFlowDetector
from platforms.indeed.rotator import (
    IndeedRotator,
    IndeedRotationConfig,
    IndeedRotationStats,
)

__all__ = [
    "IndeedBrowser",
    "DEFAULT_INDEED_PROFILE_DIR",
    "HOME_URL",
    "LOGIN_URL",
    "SEARCH_BASE_URL",
    "LOGGED_IN_SELECTORS",
    "LOGIN_REQUIRED_SELECTORS",
    "IndeedSearch",
    "IndeedJobItem",
    "build_search_url",
    "IndeedForm",
    "IndeedSafetyGate",
    "SafetyGateResult",
    "IndeedCaptchaHandler",
    "IndeedSubmitter",
    "IndeedApplier",
    "IndeedFlowDetector",
    "IndeedRotator",
    "IndeedRotationConfig",
    "IndeedRotationStats",
]
