"""Repository for Application lifecycle management and status transitions."""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy import desc, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.base import utc_now
from app.db.models import Application, ApplicationStatusHistory, Company, Contact, Interview, Job, Offer
from app.repositories.base import BaseRepository
from app.repositories.dto import ApplicationCreateDTO
from app.repositories.validators import validate_status_transition


BLOCKING_APPLICATION_STATES = {
    "SUBMITTED",
    "APPLYING",
    "UNKNOWN",
    "MANUAL_REQUIRED",
}


class ApplicationRepository(BaseRepository):
    """Data access and lifecycle management for job applications."""

    def get_by_id(self, application_id: int) -> Optional[Application]:
        """Fetches an application by internal primary key."""
        return self.session.execute(
            select(Application).where(Application.id == application_id)
        ).scalar_one_or_none()

    def get_by_job_id(self, job_id: int) -> Optional[Application]:
        """Fetches the application record associated with an internal job ID."""
        return self.session.execute(
            select(Application).where(Application.job_id == job_id)
        ).scalar_one_or_none()

    def is_job_blocking(self, job_id: int) -> bool:
        """Determines if a job has an active application that blocks retrying."""
        app = self.get_by_job_id(job_id)
        if not app:
            return False
        return app.status in BLOCKING_APPLICATION_STATES

    def create_application(self, dto: ApplicationCreateDTO) -> Application:
        """Creates an application and records its initial status history in a single transaction."""
        now = utc_now()
        status_clean = dto.status.strip().upper()
        auto_status = dto.automation_status
        if not auto_status:
            if status_clean == "SUBMITTED":
                auto_status = "SUCCESS"
            elif status_clean == "APPLYING":
                auto_status = "RUNNING"
            elif status_clean in ("FAILED", "UNKNOWN", "MANUAL_REQUIRED"):
                auto_status = status_clean
            else:
                auto_status = "NOT_STARTED"

        app = Application(
            job_id=dto.job_id,
            user_id=dto.user_id,
            resume_id=dto.resume_id,
            contact_id=dto.contact_id,
            status=status_clean,
            automation_status=auto_status,
            application_type=dto.application_type,
            applied_at=now if status_clean == "SUBMITTED" else None,
            external_job_link=dto.external_job_link,
            notes=dto.notes,
        )
        self.session.add(app)
        self.session.flush()

        # Record initial status in history
        history = ApplicationStatusHistory(
            application_id=app.id,
            old_status=None,
            new_status=app.status,
            changed_at=now,
            source="creation",
            notes=dto.notes,
        )
        self.session.add(history)

        # Auto-provision Interview record if created directly in INTERVIEW status
        if status_clean == "INTERVIEW":
            from app.db.models.interview import Interview
            init_iv = Interview(
                application_id=app.id,
                round_number=1,
                round_name="Interview Round 1",
                scheduled_at=now + timedelta(days=1),
                mode="VIRTUAL",
                status="SCHEDULED",
                notes=dto.notes or "Auto-provisioned upon entering Interview stage",
            )
            self.session.add(init_iv)
        elif status_clean == "OFFER":
            from app.db.models.offer import Offer
            init_off = Offer(
                application_id=app.id,
                status="RECEIVED",
                notes=dto.notes or "Auto-provisioned upon entering Offer stage",
            )
            self.session.add(init_off)

        self.session.flush()
        return app

    def transition_status(
        self,
        application_id: int,
        new_status: str,
        source: str = "automation",
        notes: Optional[str] = None,
        failure_reason: Optional[str] = None,
        allow_override: bool = False,
    ) -> Application:
        """Validates and applies a status transition, appending an audit record atomically.

        Raises:
            ValueError: If the status transition violates the state machine rules.
        """
        app = self.get_by_id(application_id)
        if not app:
            raise ValueError(f"Application with ID {application_id} not found.")

        target = new_status.strip().upper()
        is_valid, err_msg = validate_status_transition(
            current_status=app.status,
            new_status=target,
            allow_override=allow_override,
        )
        if not is_valid:
            raise ValueError(err_msg)

        now = utc_now()
        old_status = app.status
        app.status = target

        # Keep automation_status in sync with automation events
        if target == "SUBMITTED":
            app.automation_status = "SUCCESS"
        elif target == "APPLYING":
            app.automation_status = "RUNNING"
        elif target in ("FAILED", "UNKNOWN", "MANUAL_REQUIRED"):
            app.automation_status = target

        if target == "SUBMITTED" and not app.applied_at:
            app.applied_at = now

        if failure_reason:
            app.failure_reason = failure_reason

        if notes:
            app.notes = notes

        history = ApplicationStatusHistory(
            application_id=app.id,
            old_status=old_status,
            new_status=target,
            changed_at=now,
            source=source,
            notes=notes or failure_reason,
        )
        self.session.add(history)

        # Auto-provision next SCHEDULED Interview round when entering or re-entering INTERVIEW
        # unless an active SCHEDULED round already exists for this application.
        if target == "INTERVIEW":
            from app.db.models.interview import Interview
            has_scheduled_iv = (
                self.session.execute(
                    select(Interview.id).where(
                        Interview.application_id == app.id,
                        Interview.status == "SCHEDULED",
                    )
                ).first()
                is not None
            )
            if not has_scheduled_iv:
                max_round = (
                    self.session.scalar(
                        select(func.max(Interview.round_number)).where(
                            Interview.application_id == app.id
                        )
                    )
                    or 0
                )
                next_round = int(max_round) + 1
                init_iv = Interview(
                    application_id=app.id,
                    round_number=next_round,
                    round_name=f"Interview Round {next_round}",
                    scheduled_at=now + timedelta(days=1),
                    mode="VIRTUAL",
                    status="SCHEDULED",
                    notes=notes or "Auto-provisioned upon entering Interview stage",
                )
                self.session.add(init_iv)

        # Auto-provision Offer record if transitioning to OFFER and none exists
        elif target == "OFFER":
            from app.db.models.offer import Offer
            from app.db.models.interview import Interview
            has_offer = (
                self.session.execute(
                    select(Offer).where(Offer.application_id == app.id)
                ).first()
                is not None
            )
            if not has_offer:
                init_off = Offer(
                    application_id=app.id,
                    status="RECEIVED",
                    notes=notes or "Auto-provisioned upon entering Offer stage",
                )
                self.session.add(init_off)

            pending_ivs = self.session.execute(
                select(Interview).where(
                    Interview.application_id == app.id,
                    Interview.status == "SCHEDULED",
                )
            ).scalars().all()
            for iv in pending_ivs:
                iv.status = "COMPLETED"
                if not iv.completed_at:
                    iv.completed_at = now
                iv.notes = (iv.notes or "") + " [Auto-completed: application reached Offer]"

        # Cancel pending interviews if application is rejected, withdrawn, junked, or reset
        elif target in ("REJECTED", "WITHDRAWN", "JUNK", "NOT_APPLIED"):
            from app.db.models.interview import Interview
            pending_ivs = self.session.execute(
                select(Interview).where(
                    Interview.application_id == app.id,
                    Interview.status == "SCHEDULED",
                )
            ).scalars().all()
            for iv in pending_ivs:
                iv.status = "CANCELLED"
                iv.notes = (iv.notes or "") + f" [Auto-cancelled: application {target}]"

        self.session.flush()
        return app

    def update_automation_status(
        self,
        application_id: int,
        automation_status: str,
        notes: Optional[str] = None,
    ) -> Optional[Application]:
        """Directly updates the automation status of an application."""
        app = self.get_by_id(application_id)
        if not app:
            return None
        app.automation_status = automation_status.strip().upper()
        if notes:
            app.notes = notes
        self.session.flush()
        return app

    def list_applications(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Application]:
        """Lists applications with optional status filter and pagination."""
        stmt = select(Application)
        if status:
            stmt = stmt.where(Application.status == status.strip().upper())
        stmt = stmt.order_by(Application.created_at.desc())
        stmt = self.apply_pagination(stmt, limit=limit, offset=offset)
        return list(self.session.execute(stmt).scalars().all())

    def get_pipeline_grouped(self) -> Dict[str, List[Application]]:
        """Returns applications grouped by pipeline status for data consumption."""
        stmt = select(Application).order_by(Application.updated_at.desc())
        all_apps = list(self.session.execute(stmt).scalars().all())

        pipeline: Dict[str, List[Application]] = {
            "APPLYING": [],
            "SUBMITTED": [],
            "UNDER_REVIEW": [],
            "SHORTLISTED": [],
            "INTERVIEW": [],
            "OFFER": [],
            "REJECTED": [],
            "UNKNOWN": [],
        }

        for app in all_apps:
            if app.status in pipeline:
                pipeline[app.status].append(app)
            else:
                pipeline.setdefault(app.status, []).append(app)

        return pipeline

    def check_duplicate_outreach_application(
        self,
        job_id: Optional[int] = None,
        company_name: Optional[str] = None,
        job_title: Optional[str] = None,
        contact_email: Optional[str] = None,
        source_url: Optional[str] = None,
    ):
        """Lifecycle-aware 4-tier duplicate application detection across active recruitment states.

        Returns:
            DuplicateMatchResultDTO detailing whether a duplicate exists, which tier matched,
            and the existing application metadata.
        """
        from app.db.models.contact import Contact
        from app.db.models.job import Job
        from app.repositories.validators import normalize_company_name
        from app.services.dto.outreach_dto import DuplicateMatchResultDTO

        non_duplicate_states = {"WITHDRAWN", "ARCHIVED", "CANCELLED"}

        # -------------------------------------------------------------
        # Tier 1: Exact Job ID match
        # -------------------------------------------------------------
        if job_id:
            stmt = (
                select(Application)
                .where(Application.job_id == job_id)
                .where(Application.status.notin_(non_duplicate_states))
                .order_by(Application.created_at.desc())
            )
            existing = self.session.execute(stmt).scalars().first()
            if existing:
                comp_name = existing.job.company.name if (existing.job and existing.job.company) else company_name
                j_title = existing.job.title if existing.job else job_title
                return DuplicateMatchResultDTO(
                    is_duplicate=True,
                    match_tier="EXACT_JOB_ID",
                    existing_application_id=existing.id,
                    existing_status=existing.status,
                    company_name=comp_name,
                    job_title=j_title,
                    applied_at=existing.applied_at or existing.created_at,
                    can_override=True,
                )

        # -------------------------------------------------------------
        # Tier 2: Normalized Company Name + Normalized Job Title
        # -------------------------------------------------------------
        if company_name and job_title:
            norm_comp = normalize_company_name(company_name).lower()
            norm_title = job_title.strip().lower()

            stmt = (
                select(Application)
                .join(Application.job)
                .where(Application.status.notin_(non_duplicate_states))
            )
            for app in self.session.execute(stmt).scalars().all():
                if not app.job:
                    continue
                app_comp = normalize_company_name(app.job.company.name if app.job.company else "").lower()
                app_title = (app.job.title or "").strip().lower()
                if (norm_comp and app_comp == norm_comp) and (norm_title and (norm_title in app_title or app_title in norm_title)):
                    return DuplicateMatchResultDTO(
                        is_duplicate=True,
                        match_tier="NORMALIZED_COMPANY_TITLE",
                        existing_application_id=app.id,
                        existing_status=app.status,
                        company_name=app.job.company.name if app.job.company else company_name,
                        job_title=app.job.title or job_title,
                        applied_at=app.applied_at or app.created_at,
                        can_override=True,
                    )

        # -------------------------------------------------------------
        # Tier 3: Contact Email + Job Title
        # -------------------------------------------------------------
        if contact_email and job_title:
            c_email = contact_email.strip().lower()
            norm_title = job_title.strip().lower()

            stmt = (
                select(Application)
                .join(Application.contact)
                .join(Application.job)
                .where(Contact.email == c_email)
                .where(Application.status.notin_(non_duplicate_states))
            )
            for app in self.session.execute(stmt).scalars().all():
                app_title = (app.job.title if app.job else "").strip().lower()
                if norm_title in app_title or app_title in norm_title:
                    return DuplicateMatchResultDTO(
                        is_duplicate=True,
                        match_tier="CONTACT_TITLE",
                        existing_application_id=app.id,
                        existing_status=app.status,
                        company_name=app.job.company.name if (app.job and app.job.company) else company_name,
                        job_title=app.job.title if app.job else job_title,
                        applied_at=app.applied_at or app.created_at,
                        can_override=True,
                    )

        # -------------------------------------------------------------
        # Tier 4: Source URL
        # -------------------------------------------------------------
        if source_url:
            clean_url = source_url.strip().lower()
            stmt = (
                select(Application)
                .join(Application.job)
                .where(Application.status.notin_(non_duplicate_states))
            )
            for app in self.session.execute(stmt).scalars().all():
                job_app_url = (getattr(app.job, "application_url", None) or "").strip().lower()
                job_src_url = (getattr(app.job, "source_url", None) or "").strip().lower()
                app_ext_url = (getattr(app, "external_job_link", None) or "").strip().lower()
                if clean_url and (clean_url in (job_app_url, job_src_url, app_ext_url)):
                    return DuplicateMatchResultDTO(
                        is_duplicate=True,
                        match_tier="SOURCE_URL",
                        existing_application_id=app.id,
                        existing_status=app.status,
                        company_name=app.job.company.name if (app.job and app.job.company) else company_name,
                        job_title=app.job.title if app.job else job_title,
                        applied_at=app.applied_at or app.created_at,
                        can_override=True,
                    )

        return DuplicateMatchResultDTO(is_duplicate=False)

    def get_outreach_applications_projected(
        self,
        search_query: Optional[str] = None,
        is_priority: Optional[bool] = None,
        is_unread: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Application]:
        """Fetches outreach applications with all necessary relationships eager-loaded, avoiding N+1 queries."""
        stmt = (
            select(Application)
            .where(Application.application_type == "EMAIL")
            .options(
                selectinload(Application.job).selectinload(Job.company),
                selectinload(Application.contact),
                selectinload(Application.resume),
                selectinload(Application.communications),
                selectinload(Application.follow_ups),
            )
            .order_by(desc(Application.created_at))
        )

        if is_priority is not None:
            stmt = stmt.where(Application.is_priority == is_priority)

        if is_unread is not None:
            stmt = stmt.where(Application.is_unread == is_unread)

        if search_query:
            like = f"%{search_query.strip()}%"
            stmt = (
                stmt.join(Application.job, isouter=True)
                .join(Job.company, isouter=True)
                .join(Application.contact, isouter=True)
                .where(
                    or_(
                        Company.name.ilike(like),
                        Job.title.ilike(like),
                        Contact.name.ilike(like),
                        Contact.email.ilike(like),
                        Application.notes.ilike(like),
                    )
                )
            )

        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars().all())

    def count_submitted_between(self, start_dt: datetime, end_dt: datetime) -> int:
        """Counts applications submitted within the specified UTC timestamp interval."""
        stmt = select(func.count(Application.id)).where(
            Application.applied_at >= start_dt,
            Application.applied_at <= end_dt,
        )
        return self.session.scalar(stmt) or 0

    def get_canonical_kpi_counts(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Single source of truth for Dashboard and Applications KPI card counts."""
        q_jobs = select(func.count(Job.id))
        if start_date:
            q_jobs = q_jobs.where(Job.created_at >= start_date)
        if end_date:
            q_jobs = q_jobs.where(Job.created_at <= end_date)
        total_jobs = self.session.scalar(q_jobs) or 0

        q_submitted = select(func.count(Application.id)).where(
            Application.status == "SUBMITTED"
        )
        if start_date:
            q_submitted = q_submitted.where(Application.created_at >= start_date)
        if end_date:
            q_submitted = q_submitted.where(Application.created_at <= end_date)
        submitted_apps = self.session.scalar(q_submitted) or 0

        q_review = select(func.count(Application.id)).where(
            Application.status == "UNDER_REVIEW"
        )
        if start_date:
            q_review = q_review.where(Application.created_at >= start_date)
        if end_date:
            q_review = q_review.where(Application.created_at <= end_date)
        under_review_count = self.session.scalar(q_review) or 0

        has_scheduled_iv = exists(
            select(Interview.id).where(
                Interview.application_id == Application.id,
                Interview.status == "SCHEDULED",
            )
        )
        has_any_iv = exists(
            select(Interview.id).where(Interview.application_id == Application.id)
        )
        q_interviews = select(func.count(func.distinct(Application.id))).where(
            (
                Application.status.notin_(("OFFER", "REJECTED", "WITHDRAWN", "JUNK"))
                & has_scheduled_iv
            )
            | ((Application.status == "INTERVIEW") & (~has_any_iv))
        )
        if start_date:
            q_interviews = q_interviews.where(Application.created_at >= start_date)
        if end_date:
            q_interviews = q_interviews.where(Application.created_at <= end_date)
        interviews_count = self.session.scalar(q_interviews) or 0

        q_offers = (
            select(func.count(func.distinct(Application.id)))
            .outerjoin(Offer, Offer.application_id == Application.id)
            .where((Application.status == "OFFER") | (Offer.id.is_not(None)))
        )
        if start_date:
            q_offers = q_offers.where(Application.created_at >= start_date)
        if end_date:
            q_offers = q_offers.where(Application.created_at <= end_date)
        offers_count = self.session.scalar(q_offers) or 0

        q_withdrawn = select(func.count(Application.id)).where(
            Application.status == "WITHDRAWN"
        )
        if start_date:
            q_withdrawn = q_withdrawn.where(Application.created_at >= start_date)
        if end_date:
            q_withdrawn = q_withdrawn.where(Application.created_at <= end_date)
        withdrawn_count = self.session.scalar(q_withdrawn) or 0

        q_rejected = select(func.count(Application.id)).where(
            Application.status == "REJECTED"
        )
        if start_date:
            q_rejected = q_rejected.where(Application.created_at >= start_date)
        if end_date:
            q_rejected = q_rejected.where(Application.created_at <= end_date)
        rejections_count = self.session.scalar(q_rejected) or 0

        in_pipeline = submitted_apps + under_review_count + interviews_count

        return {
            "total_jobs": total_jobs,
            "applications_submitted": submitted_apps,
            "submitted": submitted_apps,
            "under_review": under_review_count,
            "in_pipeline": in_pipeline,
            "interviews": interviews_count,
            "offers": offers_count,
            "withdrawn": withdrawn_count,
            "rejections": rejections_count,
            "rejected": rejections_count,
        }



