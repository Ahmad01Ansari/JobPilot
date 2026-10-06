"""LinkedIn Automation Platform Package.

Provides modular browser session management, job parsing, Easy Apply execution,
and search rotation for LinkedIn.com.
"""

from platforms.linkedin.selectors import (
    HOME_URL,
    LOGIN_URL,
    JOBS_HOME_URL,
)
from platforms.linkedin.browser import LinkedInBrowser
from platforms.linkedin.parser import LinkedInJobParser
from platforms.linkedin.applier import LinkedInApplier
from platforms.linkedin.rotator import LinkedInRotator

__all__ = [
    "HOME_URL",
    "LOGIN_URL",
    "JOBS_HOME_URL",
    "LinkedInBrowser",
    "LinkedInJobParser",
    "LinkedInApplier",
    "LinkedInRotator",
]
