'''
Glassdoor Platform Exceptions
Standard exception hierarchy for Glassdoor automation driver.
'''


class GlassdoorError(Exception):
    """Base exception for all Glassdoor automation errors."""
    pass


class GlassdoorLoginError(GlassdoorError):
    """Raised when authentication fails due to bad credentials, disabled account, or unexpected flow."""
    pass


class GlassdoorCaptchaError(GlassdoorError):
    """Raised when human verification, Cloudflare Turnstile, or anti-bot challenge is encountered."""
    pass


class GlassdoorSessionError(GlassdoorError):
    """Raised when browser session crashes, window closes, or socket times out."""
    pass


class GlassdoorElementNotFoundError(GlassdoorError):
    """Raised when an essential DOM element (card, button, input) cannot be located."""
    pass


class GlassdoorSubmissionError(GlassdoorError):
    """Raised when application submission cannot be completed or verified."""
    pass
