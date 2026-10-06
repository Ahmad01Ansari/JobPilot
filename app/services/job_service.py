"""Job repository operations service.

Encapsulates business logic for querying, filtering, manual entry,
and deterministic upserting of discovered and applied jobs.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Application, Job, generate_job_fingerprint
from app.db.session import SessionLocal, get_db_session
from app.repositories.dto import JobCreateDTO
from app.repositories.job_repository import JobRepository


@dataclass
class JobFilter:
    """Structured criteria for searching and filtering job listings."""

    platform: Optional[str] = None
    is_active: Optional[bool] = None
    application_method: Optional[str] = None
    search: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    match_score_min: Optional[int] = None
    match_score_max: Optional[int] = None
    match_not_evaluated: bool = False
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    include_junk: bool = False


class JobService:
    """Service layer for job search, retrieval, deduplication, and lifecycle management."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def get_job_by_id(self, job_id: int) -> Optional[Job]:
        """Fetches a single job by internal database primary key."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            return repo.get_by_id(job_id)


    def upsert_job(self, dto: JobCreateDTO) -> Tuple[Job, bool]:
        """Creates or updates a job posting based on deterministic fingerprint deduplication.

        Returns:
            Tuple of (Job, created: bool)
        """
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            job, created = repo.upsert_job(dto)
            session.commit()
            return job, created

    def get_job(self, job_id: int) -> Optional[Job]:
        """Fetches a job record by primary key with applications and status history eagerly loaded."""
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload, selectinload
        with get_db_session(self._session_factory) as session:
            stmt = (
                select(Job)
                .where(Job.id == job_id)
                .options(
                    joinedload(Job.applications).joinedload(Application.status_history),
                    selectinload(Job.evaluations),
                )
            )
            return session.execute(stmt).unique().scalar_one_or_none()

    def list_jobs(
        self,
        filters: Optional[JobFilter] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
    ) -> List[Job]:
        """Retrieves paginated job listings according to specified filters."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            f = filters or JobFilter()

            search_query = f.search
            if f.company and not search_query:
                search_query = f.company

            active_sort_by = sort_by or f.sort_by
            active_sort_order = sort_order or f.sort_order

            plat = f.platform.strip().lower() if f.platform and f.platform.strip().lower() not in ["all platforms", "all", ""] else None
            return repo.list_jobs(
                platform=plat,
                is_active=f.is_active,
                search=search_query,
                location=f.location,
                application_method=f.application_method,
                status=f.status,
                match_score_min=f.match_score_min,
                match_score_max=f.match_score_max,
                match_not_evaluated=f.match_not_evaluated,
                sort_by=active_sort_by,
                sort_order=active_sort_order,
                limit=limit,
                offset=offset,
                include_junk=f.include_junk,
            )

    def count_jobs(self, filters: Optional[JobFilter] = None) -> int:
        """Returns total count of matching job records."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            f = filters or JobFilter()
            plat = f.platform.strip().lower() if f.platform and f.platform.strip().lower() not in ["all platforms", "all", ""] else None
            search_query = f.search
            if f.company and not search_query:
                search_query = f.company
            return repo.count_jobs(
                platform=plat,
                is_active=f.is_active,
                application_method=f.application_method,
                search=search_query,
                location=f.location,
                status=f.status,
                match_score_min=f.match_score_min,
                match_score_max=f.match_score_max,
                match_not_evaluated=f.match_not_evaluated,
                include_junk=f.include_junk,
            )

    def get_job_ids(self, filters: Optional[JobFilter] = None, limit: int = 10000) -> List[int]:
        """Returns list of Job IDs matching filter criteria (useful for bulk operations)."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            f = filters or JobFilter()
            plat = f.platform.strip().lower() if f.platform and f.platform.strip().lower() not in ["all platforms", "all", ""] else None
            search_query = f.search
            if f.company and not search_query:
                search_query = f.company
            return repo.get_job_ids(
                platform=plat,
                is_active=f.is_active,
                application_method=f.application_method,
                search=search_query,
                location=f.location,
                status=f.status,
                match_score_min=f.match_score_min,
                match_score_max=f.match_score_max,
                match_not_evaluated=f.match_not_evaluated,
                include_junk=f.include_junk,
                limit=limit,
            )

    def get_category_counts(self) -> Dict[str, int]:
        """Returns live counts for the primary category tabs plus junk."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            easy_cnt = repo.count_jobs(application_method="EASY_APPLY")
            portal_cnt = repo.count_jobs(application_method="COMPANY_PORTAL")
            junk_cnt = repo.count_jobs(status="JUNK")
            return {
                "all": repo.count_jobs(),
                "easy_apply": easy_cnt,
                "easy": easy_cnt,
                "company_portal": portal_cnt,
                "portal": portal_cnt,
                "junk": junk_cnt,
            }

    def mark_job_as_junk(self, job_id: int, reason: str = "Marked as Junk by user") -> bool:
        """Marks a job listing as JUNK in repository and updates application tracker."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            success = repo.mark_as_junk(job_id, reason=reason)
            if success:
                session.commit()
                try:
                    from modules.tracker import ApplicationTracker
                    job = repo.get_by_id(job_id)
                    if job:
                        tracker = ApplicationTracker()
                        tracker.record_state(
                            job=job,
                            state="JUNK",
                            skip_reason=reason,
                        )
                except Exception:
                    pass
            return success

    def restore_job_from_junk(self, job_id: int, new_status: str = "NOT_APPLIED") -> bool:
        """Restores a job from JUNK status back to active state or NOT_APPLIED."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            success = repo.restore_from_junk(job_id, new_status=new_status)
            if success:
                session.commit()
                try:
                    from modules.tracker import ApplicationTracker
                    job = repo.get_by_id(job_id)
                    if job:
                        tracker = ApplicationTracker()
                        st = new_status.strip().upper()
                        if st == "NOT_APPLIED":
                            key = (job.platform.lower(), str(job.external_job_id or job.id).strip())
                            if key in tracker._records:
                                tracker._records.pop(key, None)
                        else:
                            tracker.record_state(job=job, state=st)
                except Exception:
                    pass
            return success

    def create_manual_job(
        self,
        title: str,
        company: str,
        platform: str = "manual",
        location: Optional[str] = None,
        source_url: Optional[str] = None,
        description: Optional[str] = None,
        salary_text: Optional[str] = None,
        experience_text: Optional[str] = None,
        external_job_id: Optional[str] = None,
    ) -> Tuple[Optional[Job], Optional[str]]:
        """Creates a manually sourced or referral job listing."""
        t_clean = str(title or "").strip()
        c_clean = str(company or "").strip()

        if not t_clean:
            return None, "Job title cannot be empty."
        if not c_clean:
            return None, "Company name cannot be empty."

        p_clean = str(platform or "manual").strip().lower()
        url = str(source_url or "").strip() or f"https://jobpilot.local/{p_clean}/{t_clean.replace(' ', '-').lower()}"

        dto = JobCreateDTO(
            platform=p_clean,
            company_raw=c_clean,
            title=t_clean,
            source_url=url,
            external_job_id=external_job_id.strip() if external_job_id else None,
            location=location.strip() if location else None,
            salary_text=salary_text.strip() if salary_text else None,
            experience_text=experience_text.strip() if experience_text else None,
            description=description.strip() if description else None,
            apply_type="MANUAL",
        )

        try:
            job, created = self.upsert_job(dto)
            return job, None
        except Exception as e:
            return None, f"Database error adding manual job: {e}"

    def mark_job_inactive(self, job_id: int) -> bool:
        """Marks a job listing as closed or inactive."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            success = repo.mark_as_closed(job_id)
            if success:
                session.commit()
            return success

    def get_stats(self) -> Dict[str, Any]:
        """Computes summary statistics for jobs repository."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            total = repo.count_jobs()
            active = repo.count_jobs(is_active=True)
            inactive = repo.count_jobs(is_active=False)

            linkedin_count = repo.count_jobs(platform="linkedin")
            naukri_count = repo.count_jobs(platform="naukri")
            manual_count = repo.count_jobs(platform="manual")

            return {
                "total_jobs": total,
                "active_jobs": active,
                "inactive_jobs": inactive,
                "platforms": {
                    "linkedin": linkedin_count,
                    "naukri": naukri_count,
                    "manual": manual_count,
                },
            }

    def get_eligible_portal_jobs(self, limit: int = 50, offset: int = 0) -> List[Job]:
        """Returns active Company Portal jobs that have not been applied to."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            return repo.get_eligible_portal_jobs(limit=limit, offset=offset)

    def mark_as_junk(self, job_id: int, reason: str = "Marked as Junk by user") -> bool:
        """Marks a job listing with JUNK status."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            ok = repo.mark_as_junk(job_id=job_id, reason=reason)
            session.commit()
            return ok

    def restore_from_junk(self, job_id: int, new_status: str = "NOT_APPLIED") -> bool:
        """Restores a job from JUNK status back to an active state (or NOT_APPLIED)."""
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            ok = repo.restore_from_junk(job_id=job_id, new_status=new_status)
            session.commit()
            return ok

    def get_top_opportunities(
        self,
        limit: int = 5,
        decisions: Optional[List[str]] = None,
    ) -> List["TopOpportunityDTO"]:
        """Returns top unapplied jobs matching qualification decisions with explainability."""
        from app.services.dto.dashboard_dto import TopOpportunityDTO

        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            pairs = repo.get_top_opportunity_jobs(limit=limit, decisions=decisions)
            opportunities: List[TopOpportunityDTO] = []
            for rank_idx, (job, eval_record) in enumerate(pairs, start=1):
                # Compute freshness status
                freshness = "QUALIFIED"
                if eval_record.evaluation_status == "FAILED":
                    freshness = "FAILED"
                elif eval_record.updated_at and job.updated_at and eval_record.updated_at < job.updated_at:
                    freshness = "STALE"

                # Extract explainability reasons
                reasons = list(eval_record.positive_reasons or [])
                if not reasons and eval_record.decision_reason:
                    reasons = [eval_record.decision_reason]

                opportunities.append(
                    TopOpportunityDTO(
                        job_id=job.id,
                        title=job.title,
                        company=job.company_raw,
                        location=job.location,
                        platform=job.platform,
                        application_method=job.application_method or "EASY_APPLY",
                        score=eval_record.score,
                        decision=eval_record.decision,
                        evaluation_status=eval_record.evaluation_status,
                        confidence=eval_record.confidence,
                        rank=rank_idx,
                        freshness_status=freshness,
                        matched_skills=eval_record.matched_skills or [],
                        missing_skills=eval_record.missing_skills or [],
                        reasons=reasons,
                        application_url=job.application_url or job.source_url,
                        discovered_at=job.created_at,
                        recommended_action="REVIEW_JOB",
                    )
                )
            return opportunities


