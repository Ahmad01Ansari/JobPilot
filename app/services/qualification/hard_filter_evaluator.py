"""Deterministic Hard Filter Evaluator for Job Qualification.

Enforces absolute constraints: company blacklists, negative title words, and irrelevant disciplines.
"""

from typing import Any, Dict, List, Optional, Set
import re

from app.services.dto.qualification_dto import CandidateQualificationContext, JobQualificationInput


class HardFilterEvaluator:
    """Evaluates hard deterministic exclusion constraints."""

    @classmethod
    def evaluate(
        cls,
        job: JobQualificationInput,
        context: CandidateQualificationContext,
    ) -> List[Dict[str, Any]]:
        """Evaluates all hard filters and returns a list of failures (if any)."""
        failures: List[Dict[str, Any]] = []

        # 1. Company Blacklist Check
        comp_clean = (job.company_name or "").strip().lower()
        if comp_clean:
            for bl_comp in context.blacklisted_companies:
                bl_clean = bl_comp.strip().lower()
                if bl_clean and (bl_clean == comp_clean or bl_clean in comp_clean):
                    failures.append({
                        "rule": "COMPANY_BLACKLIST",
                        "passed": False,
                        "reason": f"Company '{job.company_name}' is in candidate exclusion blacklist ('{bl_comp}').",
                    })
                    break

        # 2. Negative Title Keywords Check
        title_clean = (job.title or "").strip().lower()
        if title_clean:
            for neg_kw in context.negative_title_keywords:
                neg_kw_clean = neg_kw.strip().lower()
                if not neg_kw_clean:
                    continue
                # Match word boundary
                pattern = rf"(?<!\w){re.escape(neg_kw_clean)}(?!\w)"
                if re.search(pattern, title_clean):
                    failures.append({
                        "rule": "NEGATIVE_TITLE_KEYWORD",
                        "passed": False,
                        "reason": f"Job title '{job.title}' contains excluded keyword '{neg_kw}'.",
                    })
                    break

        return failures
