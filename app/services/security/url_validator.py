"""Centralized URL Security and SSRF Prevention Validator for JobPilot."""

import enum
import ipaddress
import re
import socket
from typing import Optional, Set, Tuple
from urllib.parse import urlsplit


class URLClassification(enum.Enum):
    """Categorization of URLs according to security trust boundaries."""
    EXPECTED_PLATFORM = "EXPECTED_PLATFORM"
    LOCAL_AI = "LOCAL_AI"
    ALLOWED_EXTERNAL = "ALLOWED_EXTERNAL"
    BLOCKED = "BLOCKED"


class URLSecurityValidator:
    """Validates URLs to defend against SSRF, dangerous schemes, and host escapes."""

    # Explicitly permitted web navigation schemes
    ALLOWED_SCHEMES: Set[str] = {"http", "https"}

    # Known trusted platform root domains
    PLATFORM_DOMAINS: Set[str] = {
        "linkedin.com",
        "naukri.com",
        "indeed.com",
        "foundit.in",
        "foundit.com",
        "glassdoor.com",
        "glassdoor.co.in",
    }

    # Cloud metadata hostnames and known IPs
    BLOCKED_HOSTNAMES: Set[str] = {
        "metadata.google.internal",
        "metadata",
        "instance-data",
    }

    # Common local AI ports
    DEFAULT_LOCAL_AI_PORTS: Set[int] = {11434, 1234, 8000, 8080, 5000}

    @classmethod
    def classify_url(cls, url: str, allow_local_ai: bool = False, allow_loopback: bool = False) -> Tuple[URLClassification, str]:
        """Classifies a URL into a trust tier and returns (classification, reason)."""
        if not url or not isinstance(url, str):
            return URLClassification.BLOCKED, "Empty or non-string URL."

        url_str = url.strip()

        # Reject dangerous inline scheme prefixes
        dangerous_prefix = re.match(r"^(javascript|data|file|vbscript|about|blob):", url_str, flags=re.IGNORECASE)
        if dangerous_prefix:
            return URLClassification.BLOCKED, f"Dangerous URL scheme '{dangerous_prefix.group(1)}:' is prohibited."

        try:
            parsed = urlsplit(url_str)
        except Exception as e:
            return URLClassification.BLOCKED, f"Malformed URL structure: {e}"

        scheme = (parsed.scheme or "").lower()
        if scheme not in cls.ALLOWED_SCHEMES:
            return URLClassification.BLOCKED, f"Unsupported URL scheme '{scheme}'. Only http and https are allowed."

        hostname = (parsed.hostname or "").lower().rstrip(".")
        if not hostname:
            return URLClassification.BLOCKED, "URL lacks a valid hostname."

        port = parsed.port

        # Check blocked cloud metadata hostnames
        if hostname in cls.BLOCKED_HOSTNAMES or hostname.endswith(".internal"):
            return URLClassification.BLOCKED, f"Blocked cloud metadata hostname: {hostname}"

        # Check for loopback / local hosts
        is_loopback = hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0")

        # Parse IP literal if provided
        ip_addr = None
        try:
            ip_addr = ipaddress.ip_address(hostname)
        except ValueError:
            pass

        if ip_addr:
            # Check for cloud metadata IP (169.254.169.254, 100.100.100.200)
            if str(ip_addr) in ("169.254.169.254", "100.100.100.200"):
                return URLClassification.BLOCKED, "Blocked cloud metadata address (169.254.169.254)."

            if ip_addr.is_link_local:
                return URLClassification.BLOCKED, f"Link-local address '{ip_addr}' is prohibited."

            if ip_addr.is_loopback or ip_addr.is_unspecified:
                is_loopback = True

            if ip_addr.is_private and not is_loopback:
                return URLClassification.BLOCKED, f"Private network address '{ip_addr}' is prohibited for web navigation."

        # Handle loopback / local AI
        if is_loopback:
            if allow_local_ai:
                return URLClassification.LOCAL_AI, "Permitted local AI provider endpoint."
            import os
            if allow_loopback or os.environ.get("JOBPILOT_ALLOW_LOCAL_TESTING") == "1":
                return URLClassification.ALLOWED_EXTERNAL, "Permitted local test server endpoint during testing."
            return URLClassification.BLOCKED, "Localhost and loopback access blocked for external web navigation."

        # Check if hostname matches an expected platform
        for plat_dom in cls.PLATFORM_DOMAINS:
            if hostname == plat_dom or hostname.endswith("." + plat_dom):
                return URLClassification.EXPECTED_PLATFORM, f"Recognized job platform: {plat_dom}"

        # External destination (e.g. ATS portals: workday, greenhouse, etc.)
        return URLClassification.ALLOWED_EXTERNAL, f"External web destination: {hostname}"

    @classmethod
    def is_safe_url(cls, url: str, allow_local_ai: bool = False, allow_loopback: bool = False) -> Tuple[bool, str]:
        """Convenience method returning (is_safe, reason)."""
        cls_type, reason = cls.classify_url(url, allow_local_ai=allow_local_ai, allow_loopback=allow_loopback)
        if cls_type in (URLClassification.EXPECTED_PLATFORM, URLClassification.ALLOWED_EXTERNAL):
            return True, reason
        elif cls_type == URLClassification.LOCAL_AI and allow_local_ai:
            return True, reason
        return False, reason


def is_safe_url(url: str, allow_local_ai: bool = False, allow_loopback: bool = False) -> Tuple[bool, str]:
    """Module-level helper to check if a URL is safe for navigation or requests."""
    return URLSecurityValidator.is_safe_url(url, allow_local_ai=allow_local_ai, allow_loopback=allow_loopback)


def validate_url(url: str, allow_local_ai: bool = False, allow_loopback: bool = False) -> str:
    """Validates URL and returns cleaned string, or raises ValueError if unsafe."""
    safe, reason = is_safe_url(url, allow_local_ai=allow_local_ai, allow_loopback=allow_loopback)
    if not safe:
        raise ValueError(f"Navigation blocked by security policy for URL '{url}': {reason}")
    return url.strip()

