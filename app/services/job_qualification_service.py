"""Framework-Agnostic Job Qualification Service.

Orchestrates deterministic matching, context extraction, optional AI enhancement,
and persistence. Strictly decoupled from PySide6 and GUI threads.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import sessionmaker

from app.db.models import Job, JobEvaluation
from app.db.session import SessionLocal, get_db_session
from app.repositories.job_evaluation_repo import JobEvaluationRepository
from app.repositories.job_repository import JobRepository
from app.services.dto.qualification_dto import (
    CandidateQualificationContext,
    JobQualificationInput,
    QualificationResultDTO,
    ScoringWeights,
)
from app.services.dto.qualification_enums import (
    AIStatus,
    EvaluationStatus,
    QualificationDecision,
)
from app.services.qualification.candidate_context_provider import CandidateContextProvider
from app.services.qualification.qualification_engine import QualificationEngine
from app.services.qualification.semantic_ai_advisor import SemanticAIAdvisor

logger = logging.getLogger("JobPilot.JobQualificationService")


class JobQualificationService:
    """Core domain service for job qualification, ranking, and explainable evaluation."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        engine: Optional[QualificationEngine] = None,
        context_provider: Optional[CandidateContextProvider] = None,
        ai_advisor: Optional[SemanticAIAdvisor] = None,
        weights: Optional[ScoringWeights] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self.weights = weights or ScoringWeights()
        self.engine = engine or QualificationEngine(weights=self.weights)
        self.context_provider = context_provider or CandidateContextProvider(session_factory=self._session_factory)
        self.ai_advisor = ai_advisor or SemanticAIAdvisor()

    def get_qualification(self, job_id: int) -> Optional[QualificationResultDTO]:
        """Fetches the latest qualification record for a job, if evaluated."""
        with get_db_session(self._session_factory) as s:
            repo = JobEvaluationRepository(s)
            eval_record = repo.get_latest_evaluation(job_id)
            if not eval_record:
                return None
            return self._record_to_dto(eval_record)

    def qualify_job(
        self,
        job_id: int,
        user_id: Optional[int] = None,
        force_reevaluate: bool = False,
        use_ai: bool = False,
    ) -> QualificationResultDTO:
        """Evaluates a job against the candidate profile and records the outcome."""
        with get_db_session(self._session_factory) as s:
            repo = JobEvaluationRepository(s)
            job_repo = JobRepository(s)

            if not force_reevaluate:
                existing = repo.get_latest_evaluation(job_id)
                if existing:
                    return self._record_to_dto(existing)

            job = job_repo.get_by_id(job_id)
            if not job:
                return QualificationResultDTO(
                    job_id=job_id,
                    score=0,
                    decision=QualificationDecision.REJECTED,
                    confidence=None,
                    evaluation_status=EvaluationStatus.FAILED,
                    ai_status=AIStatus.NOT_REQUESTED,
                    recommendation=f"Job record with id {job_id} not found in database.",
                )

            # Build input DTO
            comp_name = job.company.name if (job.company and job.company.name) else job.company_raw
            job_input = JobQualificationInput(
                job_id=job.id,
                title=job.title,
                company_name=comp_name,
                location=job.location,
                work_style=job.work_style,
                experience_text=job.experience_text,
                required_experience_min=job.required_experience_min,
                required_experience_max=job.required_experience_max,
                salary_text=job.salary_text,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_period=job.salary_period,
                salary_currency=job.salary_currency,
                description=job.description,
            )

        # Build candidate context outside the database session
        context = self.context_provider.build_context(user_id=user_id)

        # 1. Deterministic evaluation
        result = self.engine.qualify(job=job_input, context=context)

        # 2. Optional semantic AI enhancement
        if use_ai and result.evaluation_status == EvaluationStatus.SUCCESS:
            result = self.ai_advisor.enhance(base_result=result, job=job_input, context=context)

        # 3. Persist evaluation history in database
        with get_db_session(self._session_factory) as s:
            repo = JobEvaluationRepository(s)
            saved_record = repo.record_qualification(result)
            s.commit()
            return self._record_to_dto(saved_record)

    def requalify_job(
        self,
        job_id: int,
        user_id: Optional[int] = None,
        use_ai: bool = False,
    ) -> QualificationResultDTO:
        """Forces re-evaluation of a job and appends a new qualification record."""
        return self.qualify_job(
            job_id=job_id,
            user_id=user_id,
            force_reevaluate=True,
            use_ai=use_ai,
        )

    def qualify_jobs_bulk(
        self,
        job_ids: List[int],
        user_id: Optional[int] = None,
        force_reevaluate: bool = False,
        use_ai: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[str, Any]:
        """Bulk qualifies multiple jobs sequentially with progress reporting."""
        total = len(job_ids)
        results: List[QualificationResultDTO] = []
        qualified_count = 0
        rejected_count = 0

        logger.info("Starting bulk qualification for %d jobs (force=%s, ai=%s)", total, force_reevaluate, use_ai)

        for idx, jid in enumerate(job_ids):
            try:
                res = self.qualify_job(
                    job_id=jid,
                    user_id=user_id,
                    force_reevaluate=force_reevaluate,
                    use_ai=use_ai,
                )
                results.append(res)
                if res.decision in (QualificationDecision.STRONG_MATCH, QualificationDecision.GOOD_MATCH, QualificationDecision.POSSIBLE_MATCH):
                    qualified_count += 1
                elif res.decision == QualificationDecision.REJECTED:
                    rejected_count += 1

                if progress_callback:
                    progress_callback(idx + 1, total, f"Job {jid}")
            except Exception as e:
                logger.error("Error qualifying job_id %d during bulk: %s", jid, e)

        return {
            "total": total,
            "processed": len(results),
            "qualified": qualified_count,
            "rejected": rejected_count,
            "results": results,
        }

    def list_qualified_jobs(
        self,
        min_score: int = 50,
        decision: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[QualificationResultDTO]:
        """Queries qualifications meeting criteria."""
        with get_db_session(self._session_factory) as s:
            repo = JobEvaluationRepository(s)
            records = repo.list_qualified_jobs(min_score=min_score, decision=decision, limit=limit, offset=offset)
            return [self._record_to_dto(r) for r in records]

    def _record_to_dto(self, record: JobEvaluation) -> QualificationResultDTO:
        """Maps an ORM JobEvaluation record into a QualificationResultDTO."""
        try:
            dec = QualificationDecision(record.decision)
        except Exception:
            dec = QualificationDecision.REVIEW_REQUIRED

        try:
            eval_st = EvaluationStatus(record.evaluation_status)
        except Exception:
            eval_st = EvaluationStatus.SUCCESS

        try:
            ai_st = AIStatus(record.ai_status)
        except Exception:
            ai_st = AIStatus.NOT_REQUESTED

        return QualificationResultDTO(
            job_id=record.job_id,
            score=record.score,
            decision=dec,
            confidence=record.confidence,
            evaluation_status=eval_st,
            ai_status=ai_st,
            matched_skills=record.matched_skills or [],
            missing_skills=record.missing_skills or [],
            hard_filter_failures=record.hard_filter_failures or [],
            positive_reasons=record.positive_reasons or [],
            negative_reasons=record.negative_reasons or [],
            recommendation=record.recommendation or record.decision_reason or "",
            component_scores=record.component_scores or {},
            engine_version=record.engine_version or "1.0.0",
            ai_model_version=record.ai_model_version,
            evaluated_at=record.evaluated_at,
        )
