"""
Glassdoor Semantic Job & Description Extractor
Implements multi-level observation and extraction for Glassdoor job cards and descriptions:
LEVEL 1: Semantic DOM analysis & structural relationships.
LEVEL 2: Accessibility attributes (aria-label, role, heading tags).
LEVEL 3: Validated data attributes and test IDs.
LEVEL 4: Structured Data (JSON-LD JobPosting schema).
LEVEL 5: Safe Detail Navigation fallback.
Enforces strict rejection of generic UI text ('Apply', 'Jobs', 'Search') and fake placeholder strings.
"""

from __future__ import annotations
import re
import json
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from modules.models import Job
from modules.helpers import print_lg

logger = logging.getLogger(__name__)

GENERIC_TITLES_BLACKLIST = {
    "search", "jobs", "apply", "sign in", "login", "glassdoor", "save", "easy apply",
    "close", "cancel", "next", "previous", "view job", "review", "ratings", "filter",
}

GENERIC_COMPANIES_BLACKLIST = {
    "save", "apply", "reviews", "jobs", "glassdoor", "overview", "salary", "interviews",
    "benefits", "photos",
}


class JDValidationStatus(Enum):
    VALID_DESCRIPTION = "VALID_DESCRIPTION"
    PARTIAL_DESCRIPTION = "PARTIAL_DESCRIPTION"
    MISSING_DESCRIPTION = "MISSING_DESCRIPTION"
    INVALID_CONTENT = "INVALID_CONTENT"


@dataclass
class JDExtractionResult:
    description: str
    status: JDValidationStatus
    character_count: int
    confidence: float
    source: str
    extraction_method: str
    failure_reason: Optional[str] = None

    @property
    def is_usable(self) -> bool:
        return self.status in (JDValidationStatus.VALID_DESCRIPTION, JDValidationStatus.PARTIAL_DESCRIPTION)


def clean_text(text: Optional[str]) -> str:
    """Removes irregular whitespace, non-breaking spaces, and excess line breaks."""
    if not text:
        return ""
    cleaned = text.replace('\xa0', ' ').replace('\u200b', '')
    return re.sub(r'[ \t]+', ' ', cleaned).strip()


def validate_title(title: str) -> bool:
    """Verifies that the extracted title is a genuine job title and not generic chrome/UI text."""
    if not title:
        return False
    cleaned = clean_text(title).lower()
    if len(cleaned) < 2 or len(cleaned) > 150:
        return False
    if cleaned in GENERIC_TITLES_BLACKLIST:
        return False
    if any(cleaned == bl for bl in GENERIC_TITLES_BLACKLIST):
        return False
    return True


def validate_company(company: str) -> bool:
    """Verifies that the extracted company name is genuine and not button or tab text."""
    if not company:
        return False
    cleaned = clean_text(company).lower()
    if len(cleaned) < 2 or len(cleaned) > 120:
        return False
    if cleaned in GENERIC_COMPANIES_BLACKLIST:
        return False
    return True


class GlassdoorJobDescriptionExtractor:
    """Multi-tiered job description extractor and validator."""

    # Disqualification markers indicating page errors or login gates
    ERROR_MARKERS = [
        "sign in to view", "please log in to continue", "404 not found",
        "job is no longer available", "session expired", "access denied",
        "create a free account to view",
    ]

    @classmethod
    def validate_jd_content(cls, raw_text: str) -> Tuple[JDValidationStatus, Optional[str]]:
        """Categorizes raw description text into strict validation states."""
        cleaned = clean_text(raw_text)
        if not cleaned:
            return (JDValidationStatus.MISSING_DESCRIPTION, "Description is empty")

        char_len = len(cleaned)
        lower = cleaned.lower()

        for marker in cls.ERROR_MARKERS:
            if marker in lower:
                return (JDValidationStatus.INVALID_CONTENT, f"Contained rejection marker: '{marker}'")

        # Reject pure navigation or copyright boilerplate
        if "glassdoor" in lower and char_len < 100 and ("all rights reserved" in lower or "cookie policy" in lower):
            return (JDValidationStatus.INVALID_CONTENT, "Boilerplate/cookie text detected")

        if char_len < 80:
            return (JDValidationStatus.PARTIAL_DESCRIPTION, f"Short description ({char_len} chars)")

        return (JDValidationStatus.VALID_DESCRIPTION, None)

    @classmethod
    def extract_from_dom(cls, driver: Any) -> JDExtractionResult:
        """Executes layered JD extraction from the active browser window/pane."""
        if not driver:
            return JDExtractionResult(
                description="",
                status=JDValidationStatus.MISSING_DESCRIPTION,
                character_count=0,
                confidence=0.0,
                source="NONE",
                extraction_method="NULL_DRIVER",
                failure_reason="Driver unavailable",
            )

        # LEVEL 1: Visible Job Details Content & Container
        try:
            l1_data = driver.execute_script('''
                // Try clicking "Show More" if present
                var moreBtns = document.querySelectorAll(
                    "[data-test='show-more-button'], button[class*='showMore'], button[class*='ShowMore'], " +
                    "button[aria-label*='Show more' i], button[aria-label*='Read more' i]"
                );
                for (var b of moreBtns) {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0) {
                        try { b.click(); } catch(e) {}
                        break;
                    }
                }

                var selectors = [
                    "#jobDescriptionText",
                    "[data-test='jobDescriptionContent']",
                    "div[class*='JobDetails_jobDescription']",
                    "#JobDescriptionContainer",
                    "div[class*='jobDescription']",
                    "div[data-test='job-description']",
                    "div[class*='JobDetails_jobDetailsContainer']",
                    "section[class*='JobDetails']",
                    "main[class*='JobDetails']"
                ];

                for (var sel of selectors) {
                    var el = document.querySelector(sel);
                    if (el) {
                        var t = (el.innerText || el.textContent || '').trim();
                        if (t.length > 50) {
                            return { text: t, selector: sel, method: "VISIBLE_DETAIL_DOM" };
                        }
                    }
                }
                return null;
            ''')
            if l1_data and l1_data.get("text"):
                raw = l1_data["text"]
                status, reason = cls.validate_jd_content(raw)
                if status in (JDValidationStatus.VALID_DESCRIPTION, JDValidationStatus.PARTIAL_DESCRIPTION):
                    return JDExtractionResult(
                        description=clean_text(raw),
                        status=status,
                        character_count=len(raw),
                        confidence=0.95 if status == JDValidationStatus.VALID_DESCRIPTION else 0.7,
                        source=l1_data.get("selector", "DOM"),
                        extraction_method="LEVEL_1_VISIBLE_DETAIL_DOM",
                        failure_reason=reason,
                    )
        except Exception as e:
            logger.debug(f"[JDExtractor] Level 1 error: {e}")

        # LEVEL 2: Semantic Heading & Paragraph Containers
        try:
            l2_text = driver.execute_script('''
                var headings = Array.from(document.querySelectorAll("h2, h3, h4"))
                    .filter(h => /description|about the job|responsibilities|qualifications/i.test(h.innerText || ''));
                if (headings.length > 0) {
                    var parent = headings[0].parentElement;
                    if (parent) {
                        var t = (parent.innerText || parent.textContent || '').trim();
                        if (t.length > 80) return t;
                    }
                }
                return null;
            ''')
            if l2_text:
                status, reason = cls.validate_jd_content(l2_text)
                if status in (JDValidationStatus.VALID_DESCRIPTION, JDValidationStatus.PARTIAL_DESCRIPTION):
                    return JDExtractionResult(
                        description=clean_text(l2_text),
                        status=status,
                        character_count=len(l2_text),
                        confidence=0.85,
                        source="SEMANTIC_HEADINGS",
                        extraction_method="LEVEL_2_SEMANTIC_HEADINGS",
                        failure_reason=reason,
                    )
        except Exception as e:
            logger.debug(f"[JDExtractor] Level 2 error: {e}")

        # LEVEL 3: Structured Data (JSON-LD)
        try:
            json_ld_list = driver.execute_script('''
                var scripts = document.querySelectorAll("script[type='application/ld+json']");
                var res = [];
                for (var s of scripts) {
                    try {
                        var data = JSON.parse(s.innerHTML || s.textContent);
                        res.push(data);
                    } catch(e) {}
                }
                return res;
            ''')
            if json_ld_list:
                for entry in json_ld_list:
                    items = entry if isinstance(entry, list) else [entry]
                    for item in items:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            desc = item.get("description", "")
                            # Strip HTML tags from JSON-LD description
                            desc_clean = re.sub(r'<[^>]+>', ' ', desc)
                            status, reason = cls.validate_jd_content(desc_clean)
                            if status in (JDValidationStatus.VALID_DESCRIPTION, JDValidationStatus.PARTIAL_DESCRIPTION):
                                return JDExtractionResult(
                                    description=clean_text(desc_clean),
                                    status=status,
                                    character_count=len(desc_clean),
                                    confidence=0.9,
                                    source="JSON_LD",
                                    extraction_method="LEVEL_3_JSON_LD_STRUCTURED_DATA",
                                    failure_reason=reason,
                                )
        except Exception as e:
            logger.debug(f"[JDExtractor] Level 3 error: {e}")

        # Extraction completely failed
        return JDExtractionResult(
            description="",
            status=JDValidationStatus.MISSING_DESCRIPTION,
            character_count=0,
            confidence=0.0,
            source="NONE",
            extraction_method="ALL_LEVELS_EXHAUSTED",
            failure_reason="No valid description container or structured data found in current DOM",
        )


class GlassdoorJobExtractor:
    """Extracts, normalizes, and validates job items into standard Job models."""

    @classmethod
    def extract_from_card_dom(cls, card_data: Dict[str, Any], search_keyword: str = "") -> Optional[Job]:
        """Converts raw card candidate dictionary into a strictly validated unified Job model."""
        raw_title = clean_text(card_data.get("title", ""))
        raw_company = clean_text(card_data.get("company", ""))
        raw_loc = clean_text(card_data.get("location", ""))
        job_id = str(card_data.get("jobId") or card_data.get("job_id") or "").strip()
        url = card_data.get("link") or card_data.get("job_url") or ""
        salary = clean_text(card_data.get("salary"))
        is_easy_apply = bool(card_data.get("isEasyApply") or card_data.get("is_easy_apply"))

        # Validation: Reject generic title / company
        if not validate_title(raw_title):
            logger.debug(f"[JobExtractor] Rejected invalid title: '{raw_title}'")
            return None

        if not validate_company(raw_company):
            logger.debug(f"[JobExtractor] Rejected invalid company: '{raw_company}'")
            return None

        # Stable ID resolution
        if not job_id:
            if url:
                m = re.search(r'jobListingId=(\d+)|jl=(\d+)', url)
                if m:
                    job_id = m.group(1) or m.group(2)
            if not job_id:
                # Deterministic hash fallback
                job_id = f"gd_{abs(hash(raw_title + raw_company + raw_loc))}"

        # Raw metadata preservation
        raw_meta = {}
        if salary:
            raw_meta["salary_text"] = salary
        if card_data.get("rating"):
            raw_meta["rating"] = str(card_data.get("rating"))
        if search_keyword:
            raw_meta["search_keyword"] = search_keyword

        # Normalize remote / work style
        loc_lower = raw_loc.lower()
        work_style = "ON_SITE"
        if "remote" in loc_lower:
            work_style = "REMOTE"
        elif "hybrid" in loc_lower:
            work_style = "HYBRID"

        return Job(
            platform="glassdoor",
            job_id=job_id,
            title=raw_title,
            company=raw_company,
            location=raw_loc or "India",
            source_url=url,
            apply_type="DIRECT" if is_easy_apply else "EXTERNAL",
            application_method="EASY_APPLY" if is_easy_apply else "COMPANY_PORTAL",
            application_url=url,
            description="",  # Explicitly empty until JD extraction succeeds; NO fake placeholder string!
            work_style=work_style,
            raw_metadata=raw_meta,
        )
