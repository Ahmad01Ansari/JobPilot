'''
Foundit Platform Exceptions
Standard exception hierarchy for Foundit (Monster India) automation driver.
'''


class FounditError(Exception):
    """Base exception for all Foundit automation errors."""
    pass


class FounditLoginError(FounditError):
    """Raised when authentication fails due to bad credentials, disabled account, or unexpected flow."""
    pass


class FounditCaptchaError(FounditError):
    """Raised when human verification, Cloudflare Turnstile, or anti-bot challenge is encountered."""
    pass


class FounditSessionError(FounditError):
    """Raised when browser session crashes, window closes, or socket times out."""
    pass


class FounditElementNotFoundError(FounditError):
    """Raised when an essential DOM element (card, button, input) cannot be located."""
    pass


class FounditSubmissionError(FounditError):
    """Raised when application submission cannot be completed or verified."""
    pass
