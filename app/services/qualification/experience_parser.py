"""Experience Requirement Parser and Evaluator.

Extracts experience bounds and distinguishes requirement strength:
REQUIRED, PREFERRED, FLEXIBLE, or UNKNOWN.
"""

import re
from typing import Optional, Tuple

from app.services.dto.qualification_dto import ExperienceEvaluationResult
from app.services.dto.qualification_enums import ExperienceStrength


class ExperienceParser:
    """Parses experience statements from text and scores candidate experience fit."""

    # Patterns indicating flexible / entry level criteria
    FLEXIBLE_PATTERNS = [
        re.compile(r"\b(?:freshers?|fresher|entry[\s-]level|fresh graduates?)\b", re.IGNORECASE),
        re.compile(r"\b0\s*(?:[-–—/]|to)\s*[1-2]\s*(?:years?|yrs?)\b", re.IGNORECASE),
        re.compile(r"\b0\+?\s*(?:years?|yrs?)\b", re.IGNORECASE),
    ]

    # Patterns indicating preferred / soft requirements
    PREFERRED_PATTERNS = [
        re.compile(r"(\d+)\+?\s*(?:years?|yrs?)[^\.\n]*(?:preferred|plus|ideal|nice to have|advantage)", re.IGNORECASE),
        re.compile(r"(?:preferred|desired|plus|advantage)[^\.\n]*(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE),
    ]

    # Patterns indicating strict requirements
    REQUIRED_PATTERNS = [
        re.compile(r"(\d+)\+?\s*(?:years?|yrs?)[^\.\n]*(?:required|mandatory|must have|minimum|min)", re.IGNORECASE),
        re.compile(r"(?:minimum|min|at least|mandatory|must have)[^\.\n]*(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE),
    ]

    # Range pattern: '2-5 years', '3 to 6 yrs', '1/3 years'
    RANGE_PATTERN = re.compile(r"(\d+)\s*(?:[-–—/]|to)\s*(\d+)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
    # Single pattern: '5+ years', '3 years'
    SINGLE_PATTERN = re.compile(r"(\d+)\+?\s*(?:years?|yrs?)", re.IGNORECASE)

    @classmethod
    def parse_bounds_and_strength(
        cls,
        text: Optional[str],
        pre_parsed_min: Optional[int] = None,
        pre_parsed_max: Optional[int] = None,
    ) -> Tuple[Optional[int], Optional[int], ExperienceStrength]:
        """Extracts (min_years, max_years, strength) from job description or experience text."""
        raw_text = (text or "").strip()

        # Check for flexible / fresher keywords
        for p in cls.FLEXIBLE_PATTERNS:
            if p.search(raw_text):
                return (0, 1, ExperienceStrength.FLEXIBLE)

        # Use pre-parsed values if available from the job model
        min_y = pre_parsed_min
        max_y = pre_parsed_max

        # Fallback to regex extraction if bounds not stored
        if min_y is None and raw_text:
            range_matches = cls.RANGE_PATTERN.findall(raw_text)
            valid_ranges = [(int(m[0]), int(m[1])) for m in range_matches if int(m[0]) <= 25 and int(m[1]) <= 30]
            if valid_ranges:
                min_y = min(r[0] for r in valid_ranges)
                max_y = max(r[1] for r in valid_ranges)
            else:
                single_matches = cls.SINGLE_PATTERN.findall(raw_text)
                single_vals = [int(m) for m in single_matches if int(m) <= 25]
                if single_vals:
                    min_y = min(single_vals)

        if min_y is None and max_y is None:
            return (None, None, ExperienceStrength.UNKNOWN)

        # Detect strength
        strength = ExperienceStrength.REQUIRED
        for p in cls.PREFERRED_PATTERNS:
            if p.search(raw_text):
                strength = ExperienceStrength.PREFERRED
                break

        return (min_y, max_y, strength)

    @classmethod
    def evaluate_experience(
        cls,
        candidate_years: float,
        text: Optional[str],
        pre_parsed_min: Optional[int] = None,
        pre_parsed_max: Optional[int] = None,
    ) -> ExperienceEvaluationResult:
        """Evaluates candidate years against experience requirement strength."""
        min_y, max_y, strength = cls.parse_bounds_and_strength(
            text=text,
            pre_parsed_min=pre_parsed_min,
            pre_parsed_max=pre_parsed_max,
        )

        if strength == ExperienceStrength.UNKNOWN or min_y is None:
            return ExperienceEvaluationResult(
                score=100.0,
                requirement_strength=ExperienceStrength.UNKNOWN,
                parsed_min_years=None,
                parsed_max_years=None,
                is_unknown=True,
                reason="Experience requirement not explicitly specified in listing.",
            )

        if strength == ExperienceStrength.FLEXIBLE:
            return ExperienceEvaluationResult(
                score=100.0,
                requirement_strength=ExperienceStrength.FLEXIBLE,
                parsed_min_years=min_y,
                parsed_max_years=max_y,
                is_unknown=False,
                reason="Position welcomes entry-level or flexible experience candidates.",
            )

        # Numeric comparison
        if candidate_years >= min_y:
            # Candidate qualifies comfortably
            reason = f"Candidate experience ({candidate_years:g} yrs) satisfies requirement ({min_y}+ yrs)."
            return ExperienceEvaluationResult(
                score=100.0,
                requirement_strength=strength,
                parsed_min_years=min_y,
                parsed_max_years=max_y,
                is_unknown=False,
                reason=reason,
            )

        # Candidate is below minimum years
        deficit = min_y - candidate_years

        if strength == ExperienceStrength.PREFERRED:
            # Soft penalty for preferred experience
            if deficit <= 1.0:
                score = 80.0
            elif deficit <= 2.0:
                score = 65.0
            else:
                score = 40.0
            reason = f"Candidate ({candidate_years:g} yrs) is slightly below preferred experience ({min_y}+ yrs)."
        else:
            # Strict penalty for required experience
            if deficit <= 0.5:
                score = 85.0
                reason = f"Candidate ({candidate_years:g} yrs) narrowly borders required experience ({min_y}+ yrs)."
            elif deficit <= 1.5:
                score = 55.0
                reason = f"Candidate ({candidate_years:g} yrs) is under required experience ({min_y}+ yrs)."
            elif deficit <= 3.0:
                score = 30.0
                reason = f"Candidate ({candidate_years:g} yrs) has significant deficit from required experience ({min_y}+ yrs)."
            else:
                score = 10.0
                reason = f"Candidate ({candidate_years:g} yrs) does not meet required experience ({min_y}+ yrs)."

        return ExperienceEvaluationResult(
            score=round(score, 1),
            requirement_strength=strength,
            parsed_min_years=min_y,
            parsed_max_years=max_y,
            is_unknown=False,
            reason=reason,
        )
