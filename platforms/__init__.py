'''
Platforms Registry
Entry point for multi-platform job automation (LinkedIn, Indeed, Naukri).
'''

from platforms.base_platform import BasePlatformApplier, list_supported_platforms, SUPPORTED_PLATFORMS

__all__ = ["BasePlatformApplier", "list_supported_platforms", "SUPPORTED_PLATFORMS"]

