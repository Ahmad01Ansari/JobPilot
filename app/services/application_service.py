"""Application lifecycle and recruitment pipeline service.

Provides business logic for tracking job applications through state transitions,
recording audit history, enforcing state machine validation, and calculating pipeline metrics.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.db.base import utc_now
from app.db.models import Application, ApplicationStatusHistory, Job
from app.db.session import SessionLocal, get_db_session
from app.repositories.application_repository import ApplicationRepository
from app.repositories.dto import ApplicationCreateDTO
from app.repositories.validators import ALLOWED_TRANSITIONS, validate_status_transition


@dataclass
class ApplicationFilter:
    """Structured criteria for searching and filtering applications."""

    status_list: Optional[List[str]] = None
    platform: Optional[str] = None
    search: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class ApplicationService:
    """Service layer for job applications tracking and lifecycle state machine transitions."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def create_application(
        self,
        job_id: int,
        status: str = "APPLYING",
        automation_status: Optional[str] = None,
        application_type: str = "EASY_APPLY",
        notes: Optional[str] = None,
        external_job_link: Optional[str] = None,
        user_id: Optional[int] = None,
        resume_id: Optional[int] = None,
    ) -> Tuple[Optional[Application], Optional[str]]:
        """Creates a new application record for a specific job."""
        st_clean = status.strip().upper()
        dto = ApplicationCreateDTO(
            job_id=job_id,
            user_id=user_id,
            resume_id=resume_id,
            status=st_clean,
            automation_status=automation_status,
            application_type=application_type,
            notes=notes,
            external_job_link=external_job_link,
        )

        try:
            with get_db_session(self._session_factory) as session:
                repo = ApplicationRepository(session)
                existing = repo.get_by_job_id(job_id)
                if existing:
                    return existing, None

                app = repo.create_application(dto)
                session.commit()
                return app, None
        except Exception as e:
            return None, f"Database error creating application: {e}"

    def get_application(self, application_id: int) -> Optional[Application]:
        """Fetches an application with eagerly loaded job and status history."""
        with get_db_session(self._session_factory) as session:
            stmt = (
                select(Application)
                .where(Application.id == application_id)
                .options(
                    joinedload(Application.job),
                    joinedload(Application.status_history),
                )
            )
            return session.execute(stmt).unique().scalar_one_or_none()

    def get_by_job_id(self, job_id: int) -> Optional[Application]:
        """Fetches an application record for a given internal job ID."""
        with get_db_session(self._session_factory) as session:
            repo = ApplicationRepository(session)
            return repo.get_by_job_id(job_id)

    def transition_status(
        self,
        application_id: int,
        new_status: str,
        source: str = "manual",
        notes: Optional[str] = None,
        failure_reason: Optional[str] = None,
        allow_override: bool = False,
    ) -> Tuple[Optional[Application], Optional[str]]:
        """Transitions application status with state-machine validation and idempotency."""
        target_status = new_status.strip().upper()

        try:
            with get_db_session(self._session_factory) as session:
                repo = ApplicationRepository(session)
                app = repo.get_by_id(application_id)
                if not app:
                    return None, f"Application {application_id} not found."

                # Idempotency Check: if identical, return without duplicate history
                if app.status == target_status:
                    return app, None

                # Validation against domain state machine
                is_valid, err_msg = validate_status_transition(
                    current_status=app.status,
                    new_status=target_status,
                    allow_override=allow_override,
                )
                if not is_valid:
                    return None, err_msg

                updated = repo.transition_status(
                    application_id=application_id,
                    new_status=target_status,
                    source=source,
                    notes=notes,
                    failure_reason=failure_reason,
                    allow_override=allow_override,
                )
                session.commit()
                return updated, None
        except Exception as e:
            return None, f"Error transitioning application status: {e}"

    def list_applications(
        self,
        filters: Optional[ApplicationFilter] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Application]:
        """Lists applications with eager-loaded Job records matching filter criteria."""
        with get_db_session(self._session_factory) as session:
            stmt = select(Application).options(joinedload(Application.job)).join(Job)

            if filters:
                if filters.status_list:
                    cleaned_statuses = [s.strip().upper() for s in filters.status_list if s.strip()]
                    if cleaned_statuses:
                        stmt = stmt.where(Application.status.in_(cleaned_statuses))

                if filters.platform and filters.platform.strip().lower() not in ["all", ""]:
                    stmt = stmt.where(Job.platform == filters.platform.strip().lower())

                if filters.date_from:
                    stmt = stmt.where(Application.updated_at >= filters.date_from)

                if filters.date_to:
                    stmt = stmt.where(Application.updated_at <= filters.date_to)

                if filters.search and filters.search.strip():
                    term = f"%{filters.search.strip()}%"
                    stmt = stmt.where(
                        or_(
                            Job.title.ilike(term),
                            Job.company_raw.ilike(term),
                            Application.status.ilike(term),
                            Application.notes.ilike(term),
                        )
                    )

            stmt = stmt.order_by(Application.updated_at.desc())
            if limit > 0:
                stmt = stmt.limit(limit).offset(offset)
            return list(session.execute(stmt).unique().scalars().all())

    def count_applications(self, filters: Optional[ApplicationFilter] = None) -> int:
        """Counts total applications matching the given filter criteria."""
        with get_db_session(self._session_factory) as session:
            stmt = select(func.count(Application.id)).join(Job)

            if filters:
                if filters.status_list:
                    cleaned_statuses = [s.strip().upper() for s in filters.status_list if s.strip()]
                    if cleaned_statuses:
                        stmt = stmt.where(Application.status.in_(cleaned_statuses))

                if filters.platform and filters.platform.strip().lower() not in ["all", ""]:
                    stmt = stmt.where(Job.platform == filters.platform.strip().lower())

                if filters.date_from:
                    stmt = stmt.where(Application.updated_at >= filters.date_from)

                if filters.date_to:
                    stmt = stmt.where(Application.updated_at <= filters.date_to)

                if filters.search and filters.search.strip():
                    term = f"%{filters.search.strip()}%"
                    stmt = stmt.where(
                        or_(
                            Job.title.ilike(term),
                            Job.company_raw.ilike(term),
                            Application.status.ilike(term),
                            Application.notes.ilike(term),
                        )
                    )

            return session.execute(stmt).scalar() or 0

    def get_status_history(self, application_id: int) -> List[ApplicationStatusHistory]:
        """Returns ordered chronological status transition records for an application."""
        with get_db_session(self._session_factory) as session:
            stmt = (
                select(ApplicationStatusHistory)
                .where(ApplicationStatusHistory.application_id == application_id)
                .order_by(ApplicationStatusHistory.changed_at.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def get_pipeline_summary(self) -> Dict[str, int]:
        """Calculates aggregate counts per domain application status."""
        with get_db_session(self._session_factory) as session:
            repo = ApplicationRepository(session)
            grouped = repo.get_pipeline_grouped()
            return {status: len(apps) for status, apps in grouped.items()}

    def get_allowed_transitions(self, current_status: str) -> List[str]:
        """Returns the list of valid target states reachable from current status."""
        cur = current_status.strip().upper()
        allowed = set(ALLOWED_TRANSITIONS.get(cur, set()))
        standard = {
            "SUBMITTED",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "RECRUITER_CONTACTED",
            "ASSESSMENT",
            "INTERVIEW",
            "OFFER",
            "REJECTED",
            "WITHDRAWN",
            "JUNK",
        }
        allowed.update(standard)
        allowed.discard(cur)
        return sorted(list(allowed))

    def mark_as_junk(self, job_id: int, notes: str = "Marked as junk by user") -> Tuple[Optional[Application], Optional[str]]:
        """Marks a job listing with JUNK status."""
        from app.repositories.job_repository import JobRepository
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            ok = repo.mark_as_junk(job_id=job_id, reason=notes)
            if ok:
                session.commit()
                app = session.execute(
                    select(Application).where(Application.job_id == job_id)
                ).scalar_one_or_none()
                return app, None
            return None, "Job not found"

    def restore_from_junk(self, job_id: int, new_status: str = "NOT_APPLIED") -> Tuple[Optional[Application], Optional[str]]:
        """Restores a job from JUNK status back to an active state (or NOT_APPLIED)."""
        from app.repositories.job_repository import JobRepository
        with get_db_session(self._session_factory) as session:
            repo = JobRepository(session)
            ok = repo.restore_from_junk(job_id=job_id, new_status=new_status)
            if ok:
                session.commit()
                app = session.execute(
                    select(Application).where(Application.job_id == job_id)
                ).scalar_one_or_none()
                return app or True, None
            return None, "Job not found or not in junk status"
