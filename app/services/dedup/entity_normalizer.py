"""Entity and title normalization preserving domain identity for job deduplication."""

import re
from typing import List, Optional, Set, Tuple


class EntityNormalizer:
    """Normalizes company names, job titles, and locations while strictly preserving domain identity."""

    # Pure corporate structure legal suffixes (never functional domain names)
    LEGAL_CORPORATE_SUFFIXES: Set[str] = {
        "pvt ltd", "pvt. ltd.", "private limited", "ltd.", "ltd",
        "inc.", "inc", "llc", "corp.", "corp", "corporation",
        "co.", "co", "company", "gmbh", "b.v.", "s.a.",
    }

    # Standardized seniority mapping
    SENIORITY_EXPANSIONS = {
        r"\bsr(?:\.|\b)": "senior",
        r"\bjr(?:\.|\b)": "junior",
        r"\bmid-level\b": "mid",
        r"\bpr(?:\.|\b)": "principal",
    }

    # Standardized functional abbreviations
    DISCIPLINE_ABBREVIATIONS = {
        r"\bdev\b": "developer",
        r"\beng(?:\.|\b)": "engineer",
        r"\bengr(?:\.|\b)": "engineer",
        r"\bsw\b": "software",
        r"\bswe\b": "software engineer",
        r"\bsde\b": "software development engineer",
        r"\bqa\b": "quality assurance",
        r"\bml\b": "machine learning",
        r"\bai\b": "ai",
        r"\bbackend\b": "backend",
        r"\bback-end\b": "backend",
        r"\bfrontend\b": "frontend",
        r"\bfront-end\b": "frontend",
        r"\bfullstack\b": "fullstack",
        r"\bfull-stack\b": "fullstack",
    }

    # Clutter patterns to clean from titles (urgent hiring noise, experience brackets)
    TITLE_CLUTTER_PATTERNS = [
        r"\b(immediate\s+joiner|urgent\s+hiring|urgently\s+hiring|actively\s+hiring)\b",
        r"\b(\d+\s*[-–+to]+\s*\d*\s*(?:yrs|years?|yoe))\b",
        r"\b(?:\(|\[|\{)\s*(?:m/f/d|immediate|urgent|hiring|fresher|\d+\+?\s*years?)\s*(?:\)|\]|\})",
    ]

    # Common city aliases for location matching
    CITY_ALIASES = {
        "bangalore": "bengaluru",
        "bengaluru": "bengaluru",
        "bombay": "mumbai",
        "mumbai": "mumbai",
        "madras": "chennai",
        "chennai": "chennai",
        "calcutta": "kolkata",
        "kolkata": "kolkata",
        "nyc": "new york",
        "new york city": "new york",
        "sf": "san francisco",
        "bay area": "san francisco",
    }

    @classmethod
    def normalize_company(cls, raw_company: Optional[str]) -> str:
        """Normalizes company name by removing purely legal corporate suffixes.

        Strictly preserves brand identity and technical division names (e.g. 'AWS', 'Google Cloud').
        """
        if not raw_company or not isinstance(raw_company, str):
            return ""

        text = raw_company.strip().lower()
        # Remove punctuation except letters and digits
        text = re.sub(r"[,;:\'\"\(\)\[\]]", " ", text)

        # Remove legal entity suffixes
        for suffix in sorted(cls.LEGAL_CORPORATE_SUFFIXES, key=len, reverse=True):
            text = re.sub(rf"\b{re.escape(suffix)}\b", " ", text)

        # Collapse whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def normalize_title(cls, raw_title: Optional[str]) -> str:
        """Normalizes a job title while strictly preserving functional stack and specialization.

        Standardizes seniority (Sr. -> Senior) and abbreviations (Dev -> Developer),
        while preserving 'Backend', 'AI', 'Payments', 'Platform', 'Security', etc.
        """
        if not raw_title or not isinstance(raw_title, str):
            return ""

        text = raw_title.strip().lower()

        # Remove procedural clutter like (Immediate Joiner) or (3-5 Yrs)
        for pattern in cls.TITLE_CLUTTER_PATTERNS:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

        # Remove bracketed artifacts
        text = re.sub(r"[\(\[\{].*?[\)\]\}]", " ", text)

        # Expand seniority
        for pat, rep in cls.SENIORITY_EXPANSIONS.items():
            text = re.sub(pat, rep, text)

        # Expand abbreviations
        for pat, rep in cls.DISCIPLINE_ABBREVIATIONS.items():
            text = re.sub(pat, rep, text)

        # Clean punctuation to space
        text = re.sub(r"[,\-_/|•:;!\.]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @classmethod
    def compute_title_similarity(cls, title_a: str, title_b: str) -> float:
        """Calculates token-based Jaccard and containment similarity between two normalized titles.

        Returns:
            Float between 0.0 (completely distinct) and 1.0 (identical functional role).
        """
        norm_a = cls.normalize_title(title_a)
        norm_b = cls.normalize_title(title_b)

        if not norm_a or not norm_b:
            return 0.0

        if norm_a == norm_b:
            return 1.0

        tokens_a = set(norm_a.split())
        tokens_b = set(norm_b.split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a.intersection(tokens_b)
        union = tokens_a.union(tokens_b)

        jaccard = len(intersection) / len(union)

        # If one title is fully contained in another (e.g. "python developer" in "senior python developer")
        containment = len(intersection) / min(len(tokens_a), len(tokens_b))
        combined = (jaccard * 0.6) + (containment * 0.4)

        # If the only difference between titles is seniority qualifiers (e.g. "DevOps Engineer" vs "Senior DevOps Engineer")
        diff = tokens_a.symmetric_difference(tokens_b)
        seniority_qualifiers = {"senior", "junior", "lead", "principal", "staff", "associate", "entry", "intern", "sr", "jr", "ii", "iii", "iv"}
        if diff and diff.issubset(seniority_qualifiers) and len(intersection) >= 2:
            combined = max(combined, 0.88)

        return round(min(1.0, combined), 3)

    @classmethod
    def are_locations_compatible(
        cls,
        loc_a: Optional[str],
        loc_b: Optional[str],
        work_style_a: Optional[str] = None,
        work_style_b: Optional[str] = None,
    ) -> bool:
        """Determines if two locations/work styles represent compatible candidate locations.

        - If either listing specifies 'Remote' or work_style is 'Remote', locations are compatible.
        - If both have distinct cities, checks known city aliases (e.g. Bangalore vs Bengaluru).
        """
        la = (loc_a or "").strip().lower()
        lb = (loc_b or "").strip().lower()
        wa = (work_style_a or "").strip().lower()
        wb = (work_style_b or "").strip().lower()

        # Remote work style is universally compatible
        if "remote" in la or "remote" in lb or wa == "remote" or wb == "remote":
            return True

        # If neither provided location, assume compatible
        if not la or not lb:
            return True

        # Canonicalize aliases
        for alias, canon in cls.CITY_ALIASES.items():
            if alias in la:
                la = la.replace(alias, canon)
            if alias in lb:
                lb = lb.replace(alias, canon)

        # Check token intersection
        toks_a = set(re.findall(r"\b\w{3,}\b", la))
        toks_b = set(re.findall(r"\b\w{3,}\b", lb))

        if not toks_a or not toks_b:
            return True

        return len(toks_a.intersection(toks_b)) > 0
