'''
Platforms Registry
Entry point for multi-platform job automation (LinkedIn, Indeed, Naukri).
'''

from platforms.base_platform import BasePlatformApplier, list_supported_platforms, SUPPORTED_PLATFORMS
from platforms.router import PlatformRouter, LinkedInPlatform, NaukriPlatform

__all__ = [
    "BasePlatformApplier",
    "list_supported_platforms",
    "SUPPORTED_PLATFORMS",
    "PlatformRouter",
    "LinkedInPlatform",
    "NaukriPlatform",
]

