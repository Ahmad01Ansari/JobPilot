"""Repository for automated JobEvaluation / Qualification records."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import JobEvaluation
from app.repositories.base import BaseRepository
from app.services.dto.qualification_dto import QualificationResultDTO


class JobEvaluationRepository(BaseRepository):
    """Data access operations for automated job qualification and evaluation outcomes."""

    def record_qualification(self, dto: QualificationResultDTO) -> JobEvaluation:
        """Records a structured qualification outcome adhering to the evolved schema."""
        # Map decision to legacy status for analytics backward compatibility
        legacy_status = "QUALIFIED" if dto.score >= 50 and dto.decision not in ("REJECTED",) else "NOT_QUALIFIED"

        evaluation = JobEvaluation(
            job_id=dto.job_id,
            status=legacy_status,
            score=dto.score,
            decision=str(dto.decision.value if hasattr(dto.decision, "value") else dto.decision),
            confidence=dto.confidence,
            evaluation_status=str(dto.evaluation_status.value if hasattr(dto.evaluation_status, "value") else dto.evaluation_status),
            ai_status=str(dto.ai_status.value if hasattr(dto.ai_status, "value") else dto.ai_status),
            matched_skills=dto.matched_skills,
            missing_skills=dto.missing_skills,
            hard_filter_failures=dto.hard_filter_failures,
            positive_reasons=dto.positive_reasons,
            negative_reasons=dto.negative_reasons,
            component_scores=dto.component_scores,
            recommendation=dto.recommendation,
            decision_reason=dto.recommendation,
            engine_version=dto.engine_version,
            ai_model_version=dto.ai_model_version,
            evaluated_at=dto.evaluated_at or utc_now(),
        )
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

    def record_evaluation(
        self,
        job_id: int,
        status: str,
        decision_reason: Optional[str] = None,
        candidate_experience: Optional[int] = None,
        rules_matched: Optional[Dict[str, Any]] = None,
    ) -> JobEvaluation:
        """Legacy helper for recording automated qualification outcome."""
        evaluation = JobEvaluation(
            job_id=job_id,
            status=status.strip().upper(),
            decision_reason=decision_reason,
            candidate_experience=candidate_experience,
            evaluated_at=utc_now(),
            rules_matched=rules_matched,
            recommendation=decision_reason or "",
            decision="GOOD_MATCH" if status.upper() == "QUALIFIED" else "REJECTED",
            score=80 if status.upper() == "QUALIFIED" else 0,
        )
        self.session.add(evaluation)
        self.session.flush()
        return evaluation

    def get_latest_evaluation(self, job_id: int) -> Optional[JobEvaluation]:
        """Fetches the most recent evaluation record for a job."""
        stmt = (
            select(JobEvaluation)
            .where(JobEvaluation.job_id == job_id)
            .order_by(JobEvaluation.evaluated_at.desc())
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_bulk_latest_evaluations(self, job_ids: List[int]) -> Dict[int, JobEvaluation]:
        """Fetches the latest evaluation for a batch of jobs in a single efficient query."""
        if not job_ids:
            return {}

        # Subquery finding max evaluated_at per job_id
        subq = (
            select(
                JobEvaluation.job_id,
                func.max(JobEvaluation.evaluated_at).label("max_eval_at")
            )
            .where(JobEvaluation.job_id.in_(job_ids))
            .group_by(JobEvaluation.job_id)
            .subquery()
        )

        stmt = (
            select(JobEvaluation)
            .join(
                subq,
                (JobEvaluation.job_id == subq.c.job_id) &
                (JobEvaluation.evaluated_at == subq.c.max_eval_at)
            )
        )
        results = self.session.execute(stmt).scalars().all()
        return {e.job_id: e for e in results}

    def list_by_job(self, job_id: int) -> List[JobEvaluation]:
        """Lists all historical evaluation records for a specific job."""
        stmt = (
            select(JobEvaluation)
            .where(JobEvaluation.job_id == job_id)
            .order_by(JobEvaluation.evaluated_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def list_qualified_jobs(
        self,
        min_score: int = 0,
        decision: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[JobEvaluation]:
        """Queries latest qualifications meeting score and decision thresholds."""
        stmt = (
            select(JobEvaluation)
            .where(JobEvaluation.score >= min_score)
        )
        if decision:
            stmt = stmt.where(JobEvaluation.decision == decision.strip().upper())
        stmt = stmt.order_by(JobEvaluation.score.desc(), JobEvaluation.evaluated_at.desc())
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())

    def count_qualified_between(self, start_dt: datetime, end_dt: datetime) -> int:
        """Counts distinct jobs evaluated and qualified within the specified UTC timestamp interval."""
        stmt = select(func.count(func.distinct(JobEvaluation.job_id))).where(
            JobEvaluation.created_at >= start_dt,
            JobEvaluation.created_at <= end_dt,
            (
                JobEvaluation.decision.in_(["STRONG_MATCH", "GOOD_MATCH", "POSSIBLE_MATCH"])
                | (JobEvaluation.status == "QUALIFIED")
            ),
            JobEvaluation.decision != "REJECTED",
            JobEvaluation.score >= 50,
            JobEvaluation.evaluation_status == "SUCCESS",
        )
        return self.session.scalar(stmt) or 0


# Domain Alias
JobQualificationRepository = JobEvaluationRepository

