"""Deterministic Qualification Engine.

Evaluates a Job against a CandidateQualificationContext using pure, explainable,
and extensible rule components. Decoupled from ORM models and UI frameworks.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.dto.qualification_dto import (
    CandidateQualificationContext,
    ExperienceEvaluationResult,
    JobQualificationInput,
    QualificationResultDTO,
    ScoringWeights,
    SkillMatchResult,
)
from app.services.dto.qualification_enums import (
    AIStatus,
    EvaluationStatus,
    ExperienceStrength,
    QualificationDecision,
)
from app.services.qualification.experience_parser import ExperienceParser
from app.services.qualification.hard_filter_evaluator import HardFilterEvaluator
from app.services.qualification.skill_matcher import BaseSkillMatcher, SynonymSkillMatcher


class QualificationEngine:
    """Pure deterministic evaluation engine for candidate-job qualification."""

    def __init__(
        self,
        skill_matcher: Optional[BaseSkillMatcher] = None,
        weights: Optional[ScoringWeights] = None,
    ):
        self.skill_matcher = skill_matcher or SynonymSkillMatcher()
        self.weights = weights or ScoringWeights()

    def qualify(
        self,
        job: JobQualificationInput,
        context: CandidateQualificationContext,
    ) -> QualificationResultDTO:
        """Executes the full deterministic qualification pipeline for a single job."""
        now = datetime.now(timezone.utc)

        # ---------------------------------------------------------------------
        # STEP 1: Input Validation
        # ---------------------------------------------------------------------
        title = (job.title or "").strip()
        comp = (job.company_name or "").strip()
        desc = (job.description or "").strip()

        if not title or not comp:
            return QualificationResultDTO(
                job_id=job.job_id,
                score=0,
                decision=QualificationDecision.REJECTED,
                confidence=None,
                evaluation_status=EvaluationStatus.INSUFFICIENT_DATA,
                ai_status=AIStatus.NOT_REQUESTED,
                recommendation="Job is missing title or company information.",
                evaluated_at=now,
            )

        if len(desc) < 20:
            # Minimal data available
            return QualificationResultDTO(
                job_id=job.job_id,
                score=0,
                decision=QualificationDecision.REVIEW_REQUIRED,
                confidence=0.2,
                evaluation_status=EvaluationStatus.INSUFFICIENT_DATA,
                ai_status=AIStatus.NOT_REQUESTED,
                negative_reasons=["Job posting lacks detailed description or requirements."],
                recommendation="Insufficient description data to reliably qualify.",
                evaluated_at=now,
            )

        # ---------------------------------------------------------------------
        # STEP 2: Hard Exclusion Filters
        # ---------------------------------------------------------------------
        hard_failures = HardFilterEvaluator.evaluate(job=job, context=context)
        if hard_failures:
            reasons = [f["reason"] for f in hard_failures]
            return QualificationResultDTO(
                job_id=job.job_id,
                score=0,
                decision=QualificationDecision.REJECTED,
                confidence=0.95,
                evaluation_status=EvaluationStatus.SUCCESS,
                ai_status=AIStatus.NOT_REQUESTED,
                hard_filter_failures=hard_failures,
                negative_reasons=reasons,
                recommendation="Job disqualified due to hard exclusion constraints.",
                evaluated_at=now,
            )

        # ---------------------------------------------------------------------
        # STEP 3: Structured Component Matching
        # ---------------------------------------------------------------------
        positive_reasons: List[str] = []
        negative_reasons: List[str] = []
        component_scores: Dict[str, Any] = {}
        known_attributes_count = 0
        total_attributes_count = 4

        # 3a. Role / Title Match
        role_score, role_reason = self._evaluate_role_match(job.title, context)
        component_scores["role_match"] = role_score
        known_attributes_count += 1
        if role_score >= 70:
            positive_reasons.append(role_reason)
        elif role_score < 40:
            negative_reasons.append(role_reason)

        # 3b. Skills Match
        skill_res: SkillMatchResult = self.skill_matcher.match_skills(
            candidate_skills=context.all_skills,
            job_text=desc,
            job_title=title,
        )
        component_scores["skill_match"] = skill_res.score
        known_attributes_count += 1
        if skill_res.matched_skills:
            top_matched = skill_res.matched_skills[:5]
            positive_reasons.append(f"Matched {len(skill_res.matched_skills)} relevant skills: {', '.join(top_matched)}.")
        if skill_res.missing_skills:
            top_missing = skill_res.missing_skills[:5]
            if skill_res.score < 60:
                negative_reasons.append(f"Candidate lacks some mentioned skills: {', '.join(top_missing)}.")

        # 3c. Experience Fit
        exp_res: ExperienceEvaluationResult = ExperienceParser.evaluate_experience(
            candidate_years=context.years_of_experience,
            text=f"{job.experience_text or ''}\n{desc}",
            pre_parsed_min=job.required_experience_min,
            pre_parsed_max=job.required_experience_max,
        )
        component_scores["experience_match"] = exp_res.score if not exp_res.is_unknown else "UNKNOWN"
        component_scores["experience_strength"] = exp_res.requirement_strength.value
        if not exp_res.is_unknown:
            known_attributes_count += 1
            if exp_res.score >= 80:
                positive_reasons.append(exp_res.reason)
            else:
                negative_reasons.append(exp_res.reason)

        # 3d. Location / Work Style Match
        loc_score, loc_status, loc_reason = self._evaluate_location(job, context)
        component_scores["location_match"] = loc_score if loc_status != "UNKNOWN" else "UNKNOWN"
        if loc_status != "UNKNOWN":
            known_attributes_count += 1
            if loc_score >= 80:
                positive_reasons.append(loc_reason)
            else:
                negative_reasons.append(loc_reason)

        # 3e. Salary Evaluation (Informational / Non-penalizing unknown)
        salary_status, salary_reason = self._evaluate_salary(job, context)
        component_scores["salary_match"] = salary_status
        if salary_status == "SATISFIED":
            positive_reasons.append(salary_reason)
        elif salary_status == "BELOW_EXPECTATION":
            negative_reasons.append(salary_reason)

        # ---------------------------------------------------------------------
        # STEP 4: Scoring Synthesis with Dynamic Unknown Renormalization
        # ---------------------------------------------------------------------
        # Base weights: role (0.35), skill (0.35), exp (0.20), loc (0.10)
        active_weights: Dict[str, float] = {}
        active_scores: Dict[str, float] = {}

        active_weights["role"] = self.weights.role_weight
        active_scores["role"] = role_score

        active_weights["skill"] = self.weights.skill_weight
        active_scores["skill"] = skill_res.score

        if not exp_res.is_unknown:
            active_weights["exp"] = self.weights.experience_weight
            active_scores["exp"] = exp_res.score

        if loc_status != "UNKNOWN" and loc_score is not None:
            active_weights["loc"] = self.weights.location_weight
            active_scores["loc"] = loc_score

        # Renormalize sum of active weights to 1.0
        total_active_weight = sum(active_weights.values())
        if total_active_weight > 0:
            weighted_score = sum(
                active_scores[k] * (active_weights[k] / total_active_weight)
                for k in active_weights
            )
        else:
            weighted_score = 0.0

        final_score = int(round(max(0.0, min(100.0, weighted_score))))

        # Evidence completeness confidence (0.0 to 1.0)
        confidence = round(known_attributes_count / total_attributes_count, 2)

        # ---------------------------------------------------------------------
        # STEP 5: Explicit Decision Mapping (No auto-apply)
        # ---------------------------------------------------------------------
        if exp_res.requirement_strength == ExperienceStrength.REQUIRED and exp_res.score < 35:
            # Significant required experience deficit
            decision = QualificationDecision.REVIEW_REQUIRED
            recommendation = "Candidate experience is notably below mandatory job requirement. Manual review recommended."
        elif final_score >= 80:
            decision = QualificationDecision.STRONG_MATCH
            recommendation = "Strong candidate alignment across core technologies and role requirements."
        elif final_score >= 65:
            decision = QualificationDecision.GOOD_MATCH
            recommendation = "Solid match for candidate profile with minor skill or experience gaps."
        elif final_score >= 50:
            decision = QualificationDecision.POSSIBLE_MATCH
            recommendation = "Moderate profile overlap; candidate meets partial requirements."
        elif final_score >= 35:
            decision = QualificationDecision.WEAK_MATCH
            recommendation = "Weak alignment with candidate skills and targeted job roles."
        else:
            decision = QualificationDecision.REJECTED
            recommendation = "Job role and requirements do not align with candidate qualifications."

        return QualificationResultDTO(
            job_id=job.job_id,
            score=final_score,
            decision=decision,
            confidence=confidence,
            evaluation_status=EvaluationStatus.SUCCESS,
            ai_status=AIStatus.NOT_REQUESTED,
            matched_skills=skill_res.matched_skills,
            missing_skills=skill_res.missing_skills,
            hard_filter_failures=[],
            positive_reasons=positive_reasons,
            negative_reasons=negative_reasons,
            recommendation=recommendation,
            component_scores=component_scores,
            engine_version="1.0.0",
            ai_model_version=None,
            evaluated_at=now,
        )

    # -------------------------------------------------------------------------
    # Helper Evaluators
    # -------------------------------------------------------------------------
    def _evaluate_role_match(
        self,
        job_title: str,
        context: CandidateQualificationContext,
    ) -> Tuple[float, str]:
        """Calculates role alignment between job title and candidate target titles."""
        clean_jt = job_title.lower()
        targets = [t.lower() for t in context.target_titles if t]

        if not targets:
            return (50.0, "Candidate has no target titles specified.")

        best_score = 0.0
        best_target = targets[0]

        for target in targets:
            # Exact or substring match
            if target == clean_jt or target in clean_jt:
                best_score = max(best_score, 100.0)
                best_target = target
            else:
                # Token overlap calculation
                jt_tokens = set(re.findall(r"\w+", clean_jt))
                tgt_tokens = set(re.findall(r"\w+", target))
                overlap = len(jt_tokens & tgt_tokens)
                if tgt_tokens:
                    token_ratio = (overlap / len(tgt_tokens)) * 100.0
                    if token_ratio > best_score:
                        best_score = token_ratio
                        best_target = target

        if best_score >= 90:
            reason = f"Job title aligns directly with target role '{best_target}'."
        elif best_score >= 60:
            reason = f"Job title shares significant domain keywords with target role '{best_target}'."
        else:
            reason = f"Job title diverges from candidate's primary target roles."

        return (round(best_score, 1), reason)

    def _evaluate_location(
        self,
        job: JobQualificationInput,
        context: CandidateQualificationContext,
    ) -> Tuple[Optional[float], str, str]:
        """Evaluates location and remote compatibility."""
        ws = (job.work_style or "").lower()
        if "remote" in ws or (job.location and "remote" in job.location.lower()):
            return (100.0, "MATCHED", "Position is remote, matching candidate flexibility.")

        if context.willing_to_relocate:
            return (100.0, "MATCHED", "Candidate is willing to relocate for this position.")

        loc = (job.location or "").strip().lower()
        if not loc:
            return (None, "UNKNOWN", "Location is not specified in job posting.")

        city = (context.current_city or "").strip().lower()
        if city and (city in loc or loc in city):
            return (100.0, "MATCHED", f"Job is located in candidate's current city ({context.current_city}).")

        for pref in context.preferred_locations:
            clean_pref = pref.strip().lower()
            if clean_pref and (clean_pref in loc or loc in clean_pref):
                return (100.0, "MATCHED", f"Job location matches preferred location '{pref}'.")

        return (30.0, "MISMATCH", f"Job location '{job.location}' does not match candidate preferences.")

    def _evaluate_salary(
        self,
        job: JobQualificationInput,
        context: CandidateQualificationContext,
    ) -> Tuple[str, str]:
        """Evaluates compensation requirements when available."""
        if job.salary_max is None or context.expected_ctc is None:
            return ("UNKNOWN", "Salary not specified or candidate has no minimum expectation set.")

        if job.salary_max >= context.expected_ctc:
            return ("SATISFIED", f"Listed compensation meets or exceeds candidate expectation.")
        else:
            return ("BELOW_EXPECTATION", f"Listed compensation is below candidate expectation.")
