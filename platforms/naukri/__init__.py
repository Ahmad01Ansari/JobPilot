'''
Naukri Platform Automation Package
'''

from platforms.naukri.browser import NaukriBrowser, DEFAULT_NAUKRI_PROFILE_DIR
from platforms.naukri.search import NaukriSearch, build_search_url, slugify
from platforms.naukri.parser import (
    NaukriJobParser,
    parse_experience_string,
    parse_salary_string,
    parse_work_style,
    extract_job_id,
)
from platforms.naukri.applier import NaukriFlowDetector, NaukriApplier
from platforms.naukri.form import NaukriForm, FormField
from platforms.naukri.safety_gate import (
    NaukriSafetyGate,
    ApplicationReviewSummary,
    SafetyGateResult,
    ReviewDecision,
)
from platforms.naukri.submitter import NaukriSubmitter
from platforms.naukri.recovery import (
    classify_error,
    dismiss_unexpected_popups,
    retry_on_transient_error,
    safe_apply_job,
)
from platforms.naukri.selectors import (
    LOGIN_URL,
    HOME_URL,
    LOGGED_IN_HOMEPAGE_URL,
)
from platforms.naukri.rotator import (
    SearchRotationConfig,
    SearchRotationEngine,
    RotationStats,
    TermStats,
    RotationJobItem,
)

__all__ = [
    "NaukriBrowser",
    "NaukriSearch",
    "NaukriJobParser",
    "NaukriFlowDetector",
    "NaukriApplier",
    "NaukriForm",
    "FormField",
    "NaukriSafetyGate",
    "ApplicationReviewSummary",
    "SafetyGateResult",
    "ReviewDecision",
    "NaukriSubmitter",
    "classify_error",
    "dismiss_unexpected_popups",
    "retry_on_transient_error",
    "safe_apply_job",
    "build_search_url",
    "slugify",
    "parse_experience_string",
    "parse_salary_string",
    "parse_work_style",
    "extract_job_id",
    "DEFAULT_NAUKRI_PROFILE_DIR",
    "LOGIN_URL",
    "HOME_URL",
    "LOGGED_IN_HOMEPAGE_URL",
    "SearchRotationConfig",
    "SearchRotationEngine",
    "RotationStats",
    "TermStats",
    "RotationJobItem",
]




