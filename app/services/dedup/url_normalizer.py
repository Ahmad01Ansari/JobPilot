"""Safe external application URL canonicalization and ATS identifier extraction."""

import hashlib
import re
from typing import Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Known marketing, attribution, and analytics query parameters to safely strip
TRACKING_QUERY_PARAMS: Set[str] = {
    # Standard analytics & UTM
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_reader", "utm_referrer", "utm_name",
    # Platform attribution
    "ref", "refid", "reference", "source", "src", "origin", "lever-origin",
    "gh_src", "gh_jid", "linkedin_origin", "naukri_src", "indeed_src",
    # Ad and click trackers
    "fbclid", "gclid", "dclid", "msclkid", "twclid", "yclid",
    # Session / display noise
    "mode", "iis", "iisn", "trk", "trkcampaign", "tracking",
}

# Parameters that must NEVER be stripped because they identify the specific job opening
PROTECTED_JOB_PARAMS: Set[str] = {
    "jobid", "job_id", "jid", "id", "requisitionid", "reqid", "req_id",
    "postingid", "positionid", "openingid", "p",
}


class URLNormalizer:
    """Canonicalizes external job application URLs and extracts ATS identities."""

    @classmethod
    def extract_ats_metadata(cls, url: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        """Extracts (ats_provider, ats_job_id) from well-known ATS portal URLs.

        Returns:
            Tuple of (provider_name, requisition_identifier) or (None, None).
        """
        if not url or not isinstance(url, str):
            return None, None

        clean = url.strip()

        # 1. Greenhouse: boards.greenhouse.io/{company}/jobs/{job_id}
        gh_match = re.search(r"boards\.greenhouse\.io/[^/]+/jobs/([0-9a-zA-Z_-]+)", clean, re.IGNORECASE)
        if gh_match:
            return "greenhouse", gh_match.group(1)

        # 2. Lever: jobs.lever.co/{company}/{job_uuid}
        lever_match = re.search(r"jobs\.lever\.co/[^/]+/([0-9a-fA-F-]{20,})", clean, re.IGNORECASE)
        if lever_match:
            return "lever", lever_match.group(1)

        # 3. Workday: {tenant}.wd{N}.myworkdayjobs.com/.../job/.../{job_id} or _R{digits}
        wd_match = re.search(r"myworkdayjobs\.com/.*?/job/.*?_([0-9a-zA-Z_-]+)", clean, re.IGNORECASE)
        if wd_match:
            return "workday", wd_match.group(1)
        wd_req_match = re.search(r"myworkdayjobs\.com/.*?/(R-?[0-9]{4,}[0-9a-zA-Z_-]*)", clean, re.IGNORECASE)
        if wd_req_match:
            return "workday", wd_req_match.group(1)

        # 4. Ashby: jobs.ashbyhq.com/{company}/{job_id}
        ashby_match = re.search(r"jobs\.ashbyhq\.com/[^/]+/([0-9a-fA-F-]{20,})", clean, re.IGNORECASE)
        if ashby_match:
            return "ashby", ashby_match.group(1)

        # 5. SmartRecruiters: jobs.smartrecruiters.com/{company}/{job_id}
        sr_match = re.search(r"jobs\.smartrecruiters\.com/[^/]+/([0-9a-zA-Z_-]+)", clean, re.IGNORECASE)
        if sr_match:
            return "smartrecruiters", sr_match.group(1)

        # 6. Taleo: ...taleo.net/...jobdetail.ftl?job={job_id}
        taleo_match = re.search(r"taleo\.net/.*?[?&]job=([0-9a-zA-Z_-]+)", clean, re.IGNORECASE)
        if taleo_match:
            return "taleo", taleo_match.group(1)

        # 7. iCIMS: ...icims.com/jobs/([0-9]+)/...
        icims_match = re.search(r"icims\.com/jobs/([0-9]+)", clean, re.IGNORECASE)
        if icims_match:
            return "icims", icims_match.group(1)

        return None, None

    @classmethod
    def normalize_application_url(cls, url: Optional[str]) -> Optional[str]:
        """Normalizes an external application URL using safe allowlist parameter stripping.

        - Converts scheme and hostname to lowercase.
        - Strips trailing slash on path (unless root path).
        - Strips known marketing/tracking query parameters (allowlist).
        - Preserves protected routing and requisition query parameters.
        - Sorts remaining query parameters deterministically.
        - Strips URL fragment (#...).
        """
        if not url or not isinstance(url, str):
            return None

        clean = url.strip()
        if not clean:
            return None

        try:
            parsed = urlsplit(clean)
        except Exception:
            return clean

        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()
        path = parsed.path or ""

        # Normalize path trailing slashes
        if len(path) > 1 and path.endswith("/"):
            path = path[:-1]

        # Parse query params safely
        query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
        kept_pairs = []
        for k, v in query_pairs:
            k_lower = k.lower()
            # If it's a known tracking parameter and not a protected job ID parameter, strip it
            if k_lower in TRACKING_QUERY_PARAMS and k_lower not in PROTECTED_JOB_PARAMS:
                continue
            kept_pairs.append((k, v))

        # Sort query keys for canonical deterministic hashing
        kept_pairs.sort(key=lambda item: item[0])
        clean_query = urlencode(kept_pairs) if kept_pairs else ""

        # Rebuild without fragment
        canonical = urlunsplit((scheme, netloc, path, clean_query, ""))
        return canonical

    @classmethod
    def compute_canonical_url_hash(cls, normalized_url: Optional[str]) -> Optional[str]:
        """Computes SHA-256 fingerprint of a normalized external application URL."""
        if not normalized_url:
            return None
        return hashlib.sha256(normalized_url.strip().encode("utf-8")).hexdigest()
