"""Keyword and Domain Exclusion Extraction Service for JobPilot.

Analyzes candidate profile or resume attributes to determine:
1. High-precision positive search keywords for job portals.
2. Cross-domain negative exclusion keywords to filter out non-target domains
   (e.g., if candidate is RPA / Automation, exclude Android, Full Stack, Java, Mechanical).
3. Universal job description blacklists (security clearance, polygraph, citizen requirements).
"""

from typing import Any, Dict, List, Optional, Set
import re


DOMAIN_KEYWORD_PRESETS = {
    "rpa": {
        "search_terms": [
            "RPA Developer",
            "Automation Anywhere Developer",
            "Python Automation Engineer",
            "AI Automation Engineer",
            "Automation Engineer",
            "UiPath Developer",
        ],
        "negative_title_words": [
            "android",
            "ios",
            "full stack",
            "frontend",
            "react",
            "angular",
            "vue",
            "java developer",
            "dot net",
            "c++",
            "php",
            "flutter",
            "salesforce",
            "devops",
            "cloud architect",
            "mechanical",
            "civil",
            "chemical",
            "hardware",
            "electrical",
            "technician",
            "machinist",
            "maintenance",
            "site engineer",
            "eplan",
            "plc programmer",
        ],
        "bad_words": [
            "US Citizen Only",
            "Active Security Clearance",
            "Polygraph",
            "CNC Operator",
            "No C2C",
            "Unpaid Internship",
        ],
    },
    "python": {
        "search_terms": [
            "Python Automation Engineer",
            "Python Developer",
            "Backend Developer Python",
            "Python Software Engineer",
            "SDET Python",
        ],
        "negative_title_words": [
            "android",
            "ios",
            "swift",
            "flutter",
            "frontend",
            "ui designer",
            "mechanical",
            "civil",
            "hardware",
            "technician",
            "machinist",
            "site engineer",
        ],
        "bad_words": [
            "US Citizen Only",
            "Security Clearance",
            "Polygraph",
        ],
    },
    "ai": {
        "search_terms": [
            "AI Automation Engineer",
            "AI Engineer",
            "LLM Application Engineer",
            "Generative AI Developer",
            "Machine Learning Engineer",
        ],
        "negative_title_words": [
            "mechanical",
            "civil",
            "technician",
            "machinist",
            "hardware engineer",
            "helpdesk",
            "desktop support",
        ],
        "bad_words": [
            "US Citizen Only",
            "Security Clearance",
            "Polygraph",
        ],
    },
}

COMMON_PHYSICAL_DISQUALIFIERS = [
    "electrical",
    "mechanical",
    "civil",
    "hardware",
    "chemical",
    "structural",
    "technician",
    "machinist",
    "maintenance",
    "site engineer",
    "eplan",
    "plc programmer",
]


class KeywordExtractorService:
    """Provides automated keyword generation and domain exclusion recommendations."""

    @staticmethod
    def infer_domain(role_or_title: str, skills: Optional[List[str]] = None) -> str:
        """Infers primary domain category from role title and skills."""
        text = (role_or_title or "").lower()
        if skills:
            text += " " + " ".join(s.lower() for s in skills)

        if any(k in text for k in ["rpa", "automation anywhere", "uipath", "blue prism", "sap gui"]):
            return "rpa"
        if any(k in text for k in ["llm", "generative ai", "genai", "machine learning", "deep learning", "nlp"]):
            return "ai"
        if "python" in text or "automation" in text:
            return "python"
        return "rpa"  # Default to primary candidate focus

    @classmethod
    def get_recommendations_for_role(
        cls,
        role_or_title: str,
        skills: Optional[List[str]] = None,
        custom_search_terms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Generates positive search keywords, domain exclusion negative keywords, and bad words."""
        domain = cls.infer_domain(role_or_title, skills)
        preset = DOMAIN_KEYWORD_PRESETS.get(domain, DOMAIN_KEYWORD_PRESETS["rpa"])

        search_terms = list(preset["search_terms"])
        if custom_search_terms:
            for term in custom_search_terms:
                if term and term not in search_terms:
                    search_terms.insert(0, term)

        # Include role target if specified
        clean_role = (role_or_title or "").strip()
        if clean_role and clean_role not in search_terms:
            search_terms.insert(0, clean_role)

        negative_words = list(preset["negative_title_words"])
        bad_words = list(preset["bad_words"])

        return {
            "domain": domain,
            "search_terms": search_terms,
            "negative_title_words": negative_words,
            "bad_words": bad_words,
        }

    @classmethod
    def get_rpa_domain_exclusions(cls) -> List[str]:
        """Convenience method returning comprehensive exclusions for software automation engineers."""
        return list(DOMAIN_KEYWORD_PRESETS["rpa"]["negative_title_words"])

    @classmethod
    def get_common_blacklists(cls) -> List[str]:
        """Returns standard job description red flags."""
        return list(DOMAIN_KEYWORD_PRESETS["rpa"]["bad_words"])

    @classmethod
    def extract_from_profile(
        cls,
        title: str,
        skills: Optional[List[str]] = None,
        summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extracts search keywords and exclusions from candidate profile title and skills."""
        return cls.get_recommendations_for_role(role_or_title=title, skills=skills)

