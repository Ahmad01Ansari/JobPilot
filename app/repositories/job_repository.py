"""Repository for Job entity operations with fingerprint deduplication and filtering."""

from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import func, nulls_first, nulls_last, or_, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import Application, Job, JobEvaluation, generate_job_fingerprint
from app.repositories.base import BaseRepository
from app.repositories.dto import JobCreateDTO


class JobRepository(BaseRepository):
    """Data access operations for job listings."""

    def get_by_id(self, job_id: int) -> Optional[Job]:
        """Fetches a job by internal database primary key."""
        from sqlalchemy.orm import selectinload
        return self.session.execute(
            select(Job).options(selectinload(Job.applications), selectinload(Job.evaluations)).where(Job.id == job_id)
        ).scalar_one_or_none()

    def get_by_external_id(self, platform: str, external_job_id: str) -> Optional[Job]:
        """Fetches a job by platform name and external job listing ID."""
        if not external_job_id:
            return None
        return self.session.execute(
            select(Job).where(
                Job.platform == platform.strip().lower(),
                Job.external_job_id == str(external_job_id).strip(),
            )
        ).scalar_one_or_none()

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Job]:
        """Fetches a job by its deterministic SHA-256 fingerprint."""
        return self.session.execute(
            select(Job).where(Job.job_fingerprint == fingerprint)
        ).scalar_one_or_none()

    def upsert_job(self, dto: JobCreateDTO) -> Tuple[Job, bool]:
        """Upserts a job based on its deterministic fingerprint.

        Returns:
            Tuple of (Job, created: bool)
        """
        fingerprint = generate_job_fingerprint(
            platform=dto.platform,
            company=dto.company_raw,
            title=dto.title,
            location=dto.location,
            source_url=dto.source_url,
            external_job_id=dto.external_job_id,
        )

        existing = None
        if dto.external_job_id:
            existing = self.get_by_external_id(dto.platform, dto.external_job_id)
        if not existing:
            existing = self.get_by_fingerprint(fingerprint)

        now = utc_now()
        if existing:
            # Update activity timestamp and reactivate if previously closed
            existing.last_seen_at = now
            existing.is_active = True
            if dto.company_id and not existing.company_id:
                existing.company_id = dto.company_id
            if dto.company_raw and (not existing.company_raw or existing.company_raw in ("Unknown Company", "Unknown Role", "Unknown")):
                existing.company_raw = dto.company_raw
            if dto.title and (not existing.title or existing.title in ("Unknown Title", "Unknown Role", "Unknown")):
                existing.title = dto.title
            if dto.description and (not existing.description or len(dto.description) > len(existing.description or "")):
                existing.description = dto.description
            if dto.raw_metadata:
                if not existing.raw_metadata:
                    existing.raw_metadata = dto.raw_metadata
                elif isinstance(existing.raw_metadata, dict):
                    merged = dict(existing.raw_metadata)
                    merged.update(dto.raw_metadata)
                    existing.raw_metadata = merged
            if dto.application_method and dto.application_method != "EASY_APPLY":
                existing.application_method = dto.application_method
            if dto.application_url:
                clean_url = dto.application_url.strip()
                if not any(d in clean_url.lower() for d in ["naukri.com", "linkedin.com"]):
                    existing.application_url = clean_url
            if dto.apply_type and dto.apply_type != "DIRECT":
                existing.apply_type = dto.apply_type
            if dto.experience_text and (not existing.experience_text or existing.experience_text in ("N/A", "Not specified") or len(dto.experience_text) > len(existing.experience_text or "")):
                existing.experience_text = dto.experience_text
            if dto.required_experience_min is not None:
                existing.required_experience_min = dto.required_experience_min
            if dto.required_experience_max is not None:
                existing.required_experience_max = dto.required_experience_max
            if dto.salary_text and (not existing.salary_text or existing.salary_text in ("N/A", "Not specified") or len(dto.salary_text) > len(existing.salary_text or "")):
                existing.salary_text = dto.salary_text
            if dto.salary_min is not None:
                existing.salary_min = dto.salary_min
            if dto.salary_max is not None:
                existing.salary_max = dto.salary_max
            if dto.work_style and not existing.work_style:
                existing.work_style = dto.work_style
            if dto.location and (not existing.location or existing.location in ("India", "Unknown", "")):
                existing.location = dto.location
            self.session.flush()
            return existing, False


        clean_app_url = (
            dto.application_url.strip()
            if (dto.application_url and not any(d in dto.application_url.lower() for d in ["naukri.com", "linkedin.com"]))
            else None
        )

        job = Job(
            company_id=dto.company_id,
            platform=dto.platform.strip().lower(),
            external_job_id=str(dto.external_job_id).strip() if dto.external_job_id else None,
            job_fingerprint=fingerprint,
            title=dto.title.strip(),
            company_raw=dto.company_raw.strip(),
            location=dto.location.strip() if dto.location else None,
            work_style=dto.work_style.strip() if dto.work_style else None,
            experience_text=dto.experience_text.strip() if dto.experience_text else None,
            required_experience_min=dto.required_experience_min,
            required_experience_max=dto.required_experience_max,
            salary_text=dto.salary_text.strip() if dto.salary_text else None,
            salary_min=dto.salary_min,
            salary_max=dto.salary_max,
            salary_period=dto.salary_period,
            salary_currency=dto.salary_currency,
            source_url=dto.source_url.strip(),
            apply_type=dto.apply_type,
            application_method=dto.application_method or "EASY_APPLY",
            application_url=clean_app_url,
            description=dto.description,
            raw_metadata=dto.raw_metadata,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
        )
        self.session.add(job)
        self.session.flush()
        return job, True

    def _get_latest_eval_subquery(self):
        """Constructs subquery for the most recent JobEvaluation per job."""
        latest_eval_id_sub = (
            select(
                JobEvaluation.job_id,
                func.max(JobEvaluation.id).label("max_eval_id"),
            )
            .group_by(JobEvaluation.job_id)
            .subquery()
        )
        return (
            select(
                JobEvaluation.job_id,
                JobEvaluation.score,
                JobEvaluation.decision,
            )
            .join(latest_eval_id_sub, JobEvaluation.id == latest_eval_id_sub.c.max_eval_id)
            .subquery()
        )

    def _build_filtered_stmt(
        self,
        base_stmt,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        location: Optional[str] = None,
        application_method: Optional[str] = None,
        status: Optional[str] = None,
        match_score_min: Optional[int] = None,
        match_score_max: Optional[int] = None,
        match_not_evaluated: bool = False,
        include_junk: bool = False,
        latest_eval_subquery=None,
    ):
        stmt = base_stmt

        if status:
            st = status.strip().upper()
            if st == "NOT_APPLIED":
                stmt = stmt.outerjoin(Job.applications).where(Application.id == None)
            elif st == "JUNK":
                stmt = stmt.join(Job.applications).where(Application.status == "JUNK")
            else:
                stmt = stmt.join(Job.applications).where(Application.status == st)
                if not include_junk and st != "JUNK":
                    stmt = stmt.where(~Job.applications.any(Application.status == "JUNK"))
        elif not include_junk:
            # Hide junk jobs from default repository listing
            stmt = stmt.where(~Job.applications.any(Application.status == "JUNK"))

        if platform:
            stmt = stmt.where(Job.platform == platform.strip().lower())
        if is_active is not None:
            stmt = stmt.where(Job.is_active == is_active)
        if application_method:
            stmt = stmt.where(Job.application_method == application_method.strip().upper())
        if location:
            loc = f"%{location.strip()}%"
            stmt = stmt.where(Job.location.ilike(loc))
        if search:
            q = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(q),
                    Job.company_raw.ilike(q),
                    Job.location.ilike(q),
                )
            )

        if latest_eval_subquery is not None:
            if match_not_evaluated:
                stmt = stmt.outerjoin(latest_eval_subquery, Job.id == latest_eval_subquery.c.job_id).where(
                    latest_eval_subquery.c.score.is_(None)
                )
            elif match_score_min is not None or match_score_max is not None:
                stmt = stmt.join(latest_eval_subquery, Job.id == latest_eval_subquery.c.job_id)
                if match_score_min is not None:
                    stmt = stmt.where(latest_eval_subquery.c.score >= match_score_min)
                if match_score_max is not None:
                    stmt = stmt.where(latest_eval_subquery.c.score <= match_score_max)

        return stmt

    def list_jobs(
        self,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        search: Optional[str] = None,
        location: Optional[str] = None,
        application_method: Optional[str] = None,
        status: Optional[str] = None,
        match_score_min: Optional[int] = None,
        match_score_max: Optional[int] = None,
        match_not_evaluated: bool = False,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: int = 50,
        offset: int = 0,
        include_junk: bool = False,
    ) -> List[Job]:
        """Lists jobs with optional filtering by platform, activity, search term, location, method, status, match score, and sorting."""
        from sqlalchemy.orm import joinedload, selectinload
        stmt = select(Job).options(joinedload(Job.applications), selectinload(Job.evaluations))

        needs_eval = match_not_evaluated or match_score_min is not None or match_score_max is not None or sort_by == "match"
        latest_eval = self._get_latest_eval_subquery() if needs_eval else None

        stmt = self._build_filtered_stmt(
            stmt,
            platform=platform,
            is_active=is_active,
            search=search,
            location=location,
            application_method=application_method,
            status=status,
            match_score_min=match_score_min,
            match_score_max=match_score_max,
            match_not_evaluated=match_not_evaluated,
            include_junk=include_junk,
            latest_eval_subquery=latest_eval,
        )

        # Sorting logic
        is_desc = sort_order.lower() == "desc"
        if sort_by == "match":
            if not (match_score_min is not None or match_score_max is not None):
                if not match_not_evaluated:
                    stmt = stmt.outerjoin(latest_eval, Job.id == latest_eval.c.job_id)
            if is_desc:
                stmt = stmt.order_by(nulls_last(latest_eval.c.score.desc()))
            else:
                stmt = stmt.order_by(nulls_first(latest_eval.c.score.asc()))
        elif sort_by == "title":
            stmt = stmt.order_by(Job.title.desc() if is_desc else Job.title.asc())
        elif sort_by == "company":
            stmt = stmt.order_by(Job.company_raw.desc() if is_desc else Job.company_raw.asc())
        elif sort_by == "platform":
            stmt = stmt.order_by(Job.platform.desc() if is_desc else Job.platform.asc())
        elif sort_by == "location":
            stmt = stmt.order_by(Job.location.desc() if is_desc else Job.location.asc())
        elif sort_by == "created_at" or sort_by == "first_seen_at":
            stmt = stmt.order_by(Job.first_seen_at.desc() if is_desc else Job.first_seen_at.asc())
        else:
            stmt = stmt.order_by(Job.last_seen_at.desc() if is_desc else Job.last_seen_at.asc())

        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).unique().scalars().all())

    def count_jobs(
        self,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        application_method: Optional[str] = None,
        search: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
        match_score_min: Optional[int] = None,
        match_score_max: Optional[int] = None,
        match_not_evaluated: bool = False,
        include_junk: bool = False,
    ) -> int:
        """Returns the total number of jobs matching filter criteria."""
        stmt = select(func.count(func.distinct(Job.id)))
        needs_eval = match_not_evaluated or match_score_min is not None or match_score_max is not None
        latest_eval = self._get_latest_eval_subquery() if needs_eval else None

        stmt = self._build_filtered_stmt(
            stmt,
            platform=platform,
            is_active=is_active,
            search=search,
            location=location,
            application_method=application_method,
            status=status,
            match_score_min=match_score_min,
            match_score_max=match_score_max,
            match_not_evaluated=match_not_evaluated,
            include_junk=include_junk,
            latest_eval_subquery=latest_eval,
        )
        return self.session.scalar(stmt) or 0

    def get_job_ids(
        self,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        application_method: Optional[str] = None,
        search: Optional[str] = None,
        location: Optional[str] = None,
        status: Optional[str] = None,
        match_score_min: Optional[int] = None,
        match_score_max: Optional[int] = None,
        match_not_evaluated: bool = False,
        include_junk: bool = False,
        limit: int = 10000,
    ) -> List[int]:
        """Returns all Job IDs matching filter criteria (useful for bulk processing/qualifying)."""
        stmt = select(Job.id).distinct()
        needs_eval = match_not_evaluated or match_score_min is not None or match_score_max is not None
        latest_eval = self._get_latest_eval_subquery() if needs_eval else None

        stmt = self._build_filtered_stmt(
            stmt,
            platform=platform,
            is_active=is_active,
            search=search,
            location=location,
            application_method=application_method,
            status=status,
            match_score_min=match_score_min,
            match_score_max=match_score_max,
            match_not_evaluated=match_not_evaluated,
            include_junk=include_junk,
            latest_eval_subquery=latest_eval,
        )
        stmt = stmt.limit(limit)
        return list(self.session.execute(stmt).scalars().all())

    def get_top_opportunity_jobs(
        self,
        limit: int = 5,
        decisions: Optional[List[str]] = None,
    ) -> List[Tuple[Job, JobEvaluation]]:
        """Returns top unapplied jobs matching qualification decisions, ordered by score and recency."""
        allowed_decisions = decisions or ["STRONG_MATCH", "GOOD_MATCH", "POSSIBLE_MATCH"]

        ACTIVE_APPLIED_STATUSES = [
            "SUBMITTED",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "RECRUITER_CONTACTED",
            "ASSESSMENT",
            "INTERVIEW",
            "OFFER",
        ]

        latest_eval_id_sub = (
            select(
                JobEvaluation.job_id,
                func.max(JobEvaluation.id).label("max_eval_id"),
            )
            .group_by(JobEvaluation.job_id)
            .subquery()
        )

        stmt = (
            select(Job, JobEvaluation)
            .join(latest_eval_id_sub, Job.id == latest_eval_id_sub.c.job_id)
            .join(JobEvaluation, JobEvaluation.id == latest_eval_id_sub.c.max_eval_id)
            .where(~Job.applications.any(Application.status.in_(ACTIVE_APPLIED_STATUSES)))
            .where(~Job.applications.any(Application.status == "JUNK"))
            .where(
                (JobEvaluation.decision.in_(allowed_decisions))
                | (JobEvaluation.status == "QUALIFIED")
            )
            .where(JobEvaluation.decision != "REJECTED")
            .where(JobEvaluation.score >= 50)
            .where(JobEvaluation.evaluation_status == "SUCCESS")
            .order_by(JobEvaluation.score.desc(), JobEvaluation.evaluated_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).all())


    def mark_as_junk(self, job_id: int, reason: str = "Marked as Junk by user") -> bool:
        """Marks a job listing with JUNK status."""
        job = self.get_by_id(job_id)
        if not job:
            return False
        app = self.session.execute(
            select(Application).where(Application.job_id == job_id)
        ).scalar_one_or_none()
        if app:
            app.status = "JUNK"
            app.skip_reason = reason
        else:
            app = Application(
                job_id=job_id,
                status="JUNK",
                application_type="MANUAL",
                skip_reason=reason,
            )
            self.session.add(app)
        self.session.flush()
        return True

    def restore_from_junk(self, job_id: int, new_status: str = "NOT_APPLIED") -> bool:
        """Restores a job from JUNK status back to an active state (or NOT_APPLIED)."""
        job = self.get_by_id(job_id)
        if not job:
            return False
        app = self.session.execute(
            select(Application).where(Application.job_id == job_id)
        ).scalar_one_or_none()
        if app:
            st = new_status.strip().upper()
            if st == "NOT_APPLIED":
                self.session.delete(app)
            else:
                app.status = st
                app.skip_reason = None
            self.session.flush()
            return True
        return False

    def mark_as_closed(self, job_id: int) -> bool:
        """Marks a job listing as closed/inactive."""
        job = self.get_by_id(job_id)
        if not job:
            return False
        job.is_active = False
        job.closed_at = utc_now()
        self.session.flush()
        return True

    def get_eligible_portal_jobs(self, limit: int = 50, offset: int = 0) -> List[Job]:
        """Query Company Portal jobs eligible for application (active, COMPANY_PORTAL, has application_url, no submitted application)."""
        stmt = (
            select(Job)
            .where(Job.application_method == "COMPANY_PORTAL")
            .where(Job.is_active == True)
            .where(Job.application_url.is_not(None))
            .where(~Job.applications.any(Application.status == "SUBMITTED"))
            .order_by(Job.last_seen_at.desc())
        )
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())

    def count_discovered_between(self, start_dt: datetime, end_dt: datetime) -> int:
        """Counts jobs created/discovered within the specified UTC timestamp interval."""
        stmt = select(func.count(Job.id)).where(
            Job.created_at >= start_dt,
            Job.created_at <= end_dt,
        )
        return self.session.scalar(stmt) or 0

