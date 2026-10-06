"""Optional AI Semantic Enhancement Layer for Job Qualification.

Calls UniversalAIService to evaluate deep semantic nuance between candidate experience
and complex job descriptions, with guaranteed fallback to deterministic scoring.
"""

import json
import logging
from typing import Any, Dict, Optional, Tuple

from app.services.ai_service import UniversalAIService
from app.services.dto.qualification_dto import (
    CandidateQualificationContext,
    JobQualificationInput,
    QualificationResultDTO,
)
from app.services.dto.qualification_enums import AIStatus

logger = logging.getLogger("JobPilot.SemanticAIAdvisor")


class SemanticAIAdvisor:
    """Enhances deterministic qualification outcomes with deep semantic LLM analysis."""

    def __init__(self, ai_service: Optional[UniversalAIService] = None):
        self.ai_service = ai_service or UniversalAIService()

    def enhance(
        self,
        base_result: QualificationResultDTO,
        job: JobQualificationInput,
        context: CandidateQualificationContext,
    ) -> QualificationResultDTO:
        """Attempts to augment base deterministic qualification result with semantic reasoning."""
        cfg = self.ai_service.get_config()
        if not cfg.get("enabled"):
            return base_result

        desc = (job.description or "").strip()
        if len(desc) < 50:
            return base_result

        schema = json.dumps({
            "semantic_score": "integer 0-100 indicating semantic skill and domain fit",
            "additional_positive_reasons": ["list of 1-3 short strings"],
            "additional_negative_reasons": ["list of 1-3 short strings"],
            "semantic_summary": "one clear summary sentence",
        })

        prompt = (
            f"Candidate Current Role: {context.current_title}\n"
            f"Candidate Target Roles: {', '.join(context.target_titles)}\n"
            f"Candidate Verified Skills: {', '.join(context.all_skills[:20])}\n"
            f"Candidate Years of Experience: {context.years_of_experience}\n\n"
            f"Job Title: {job.title}\n"
            f"Company: {job.company_name}\n"
            f"Job Description Excerpt:\n{desc[:1500]}\n\n"
            "Analyze the conceptual alignment between this candidate's background and the job requirements."
        )

        try:
            res = self.ai_service.extract_structured_json(
                prompt=prompt,
                schema_description=schema,
                system_prompt="You are an expert ATS qualification analyst. Output strictly RFC-compliant JSON without markdown.",
            )

            sem_score = res.get("semantic_score")
            pos_extra = res.get("additional_positive_reasons", [])
            neg_extra = res.get("additional_negative_reasons", [])
            summary = res.get("semantic_summary", "")

            # Merge reasons without duplicate clutter
            new_pos = list(base_result.positive_reasons)
            for p in pos_extra:
                if p and p not in new_pos:
                    new_pos.append(str(p).strip())

            new_neg = list(base_result.negative_reasons)
            for n in neg_extra:
                if n and n not in new_neg:
                    new_neg.append(str(n).strip())

            # Blend score: 85% deterministic + 15% semantic nuance
            blended_score = base_result.score
            if isinstance(sem_score, (int, float)):
                blended_score = int(round(0.85 * base_result.score + 0.15 * float(sem_score)))
                base_result.component_scores["ai_semantic_score"] = int(sem_score)

            base_result.score = max(0, min(100, blended_score))
            base_result.positive_reasons = new_pos
            base_result.negative_reasons = new_neg
            if summary:
                base_result.recommendation = f"{base_result.recommendation} AI Insight: {summary}"
            base_result.ai_status = AIStatus.APPLIED
            base_result.ai_model_version = cfg.get("model", "unknown")
            return base_result

        except Exception as e:
            logger.warning("AI semantic enhancement failed; retaining deterministic score: %s", e)
            base_result.ai_status = AIStatus.UNAVAILABLE
            return base_result
