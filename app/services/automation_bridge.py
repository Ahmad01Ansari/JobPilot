"""Automation bridge connecting execution domain events with SQLite domain services."""

import logging
from typing import Optional, Tuple
from sqlalchemy.orm import sessionmaker

from app.db.session import SessionLocal
from app.repositories.dto import JobCreateDTO
from app.services.application_service import ApplicationService
from app.services.automation_events import (
    ApplicationSubmittedEvent,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
    AutomationInterventionEvent,
)
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class AutomationBridge:
    """Translates real-time automation engine domain events into persistent database records.
    
    Provides strict isolation, idempotency, and database fault tolerance.
    """

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal
        self.job_service = JobService(session_factory=self._session_factory)
        self.app_service = ApplicationService(session_factory=self._session_factory)
        self._captcha_resolved = False
        self.on_intervention = None

    def mark_captcha_resolved(self) -> None:
        """Signals that the user has manually resolved a CAPTCHA challenge via UI."""
        logger.info("[AutomationBridge] CAPTCHA marked as resolved by user.")
        self._captcha_resolved = True

    def reset_captcha_status(self) -> None:
        """Resets manual CAPTCHA resolution flag for subsequent challenges."""
        logger.info("[AutomationBridge] CAPTCHA resolution flag reset.")
        self._captcha_resolved = False

    def is_captcha_resolved_by_user(self) -> bool:
        """Checks if user has clicked 'I have resolved the CAPTCHA' in the UI."""
        return bool(self._captcha_resolved)

    def handle_job_discovered(self, event: JobDiscoveredEvent) -> Optional[int]:
        """Upserts a discovered job listing idempotently based on SHA-256 fingerprint."""
        try:
            app_method = getattr(event, "application_method", "EASY_APPLY") or "EASY_APPLY"
            app_url = getattr(event, "application_url", None)
            desc = getattr(event, "description", None)
            exp_text = getattr(event, "experience_text", None)
            sal_text = getattr(event, "salary_text", None)
            sal_min = getattr(event, "salary_min", None)
            sal_max = getattr(event, "salary_max", None)
            req_exp_min = getattr(event, "required_experience_min", None)
            req_exp_max = getattr(event, "required_experience_max", None)
            work_style = getattr(event, "work_style", None)

            dto = JobCreateDTO(
                platform=event.platform,
                company_raw=event.company,
                title=event.title,
                location=event.location,
                source_url=event.url or f"https://{event.platform}.com/jobs/{event.external_job_id or 'unknown'}",
                external_job_id=event.external_job_id,
                application_method=app_method,
                application_url=app_url,
                description=desc,
                experience_text=exp_text,
                salary_text=sal_text,
                salary_min=sal_min,
                salary_max=sal_max,
                required_experience_min=req_exp_min,
                required_experience_max=req_exp_max,
                work_style=work_style,
                apply_type="EXTERNAL" if app_method == "COMPANY_PORTAL" else "DIRECT",
            )
            job, _ = self.job_service.upsert_job(dto)
            # Link listing to canonical JobOpportunity via multi-signal deduplication
            try:
                from app.services.dedup.job_dedup_service import JobDeduplicationService
                dedup_svc = JobDeduplicationService(session_factory=self._session_factory)
                dedup_svc.process_incoming_job(job.id)
            except Exception as dedup_err:
                logger.debug("Notice during job deduplication: %s", dedup_err)
            return job.id
        except Exception as exc:
            logger.error("DATABASE_PERSISTENCE_ERROR in handle_job_discovered: %s", exc)
            return None


    def handle_application_submitted(self, event: ApplicationSubmittedEvent) -> Optional[int]:
        """Ensures job existence and records application idempotently."""
        try:
            job_id = event.job_id
            job = None
            if not job_id:
                # Upsert job if id not directly provided
                dto = JobCreateDTO(
                    platform=event.platform,
                    company_raw=event.company,
                    title=event.title,
                    source_url=event.source_url or f"https://{event.platform}.com/jobs/{event.external_job_id or 'unknown'}",
                    external_job_id=event.external_job_id,
                )
                job, _ = self.job_service.upsert_job(dto)
                job_id = job.id
            else:
                job = self.job_service.get_job_by_id(job_id)

            if not job_id:
                logger.error("DATABASE_PERSISTENCE_ERROR: Could not resolve job_id for submitted application.")
                return None

            app_res_id = None
            # Check if an application record already exists for this job
            existing_app = self.app_service.get_by_job_id(job_id)
            if existing_app:
                updated_app, err = self.app_service.transition_status(
                    application_id=existing_app.id,
                    new_status="SUBMITTED",
                    source="automation",
                    notes=f"Applied automatically via {event.platform.capitalize()} (Run: {event.run_id})",
                    allow_override=True,
                )
                if err:
                    logger.warning("Application status transition notice: %s", err)
                app_res_id = updated_app.id if updated_app else existing_app.id
            else:
                app, err = self.app_service.create_application(
                    job_id=job_id,
                    status="SUBMITTED",
                    application_type="EASY_APPLY",
                    notes=f"Applied automatically via {event.platform.capitalize()} (Run: {event.run_id})",
                    external_job_link=event.source_url,
                )
                if err:
                    logger.warning("Application record notice: %s", err)
                app_res_id = app.id if app else None

            # Mark canonical opportunity as APPLIED in deduplication service
            try:
                opp_id = getattr(job, "opportunity_id", None) if job else None
                if opp_id:
                    from app.services.dedup.job_dedup_service import JobDeduplicationService
                    dedup_svc = JobDeduplicationService(session_factory=self._session_factory)
                    dedup_svc.mark_opportunity_applied(opp_id, job_id, event.platform)
            except Exception as dedup_err:
                logger.debug("Notice marking opportunity applied: %s", dedup_err)

            return app_res_id
        except Exception as exc:
            logger.error("DATABASE_PERSISTENCE_ERROR in handle_application_submitted: %s", exc)
            return None

    def handle_intervention(self, event: AutomationInterventionEvent) -> None:
        """Logs and relays intervention request to any registered listeners."""
        try:
            logger.warning(
                "INTERVENTION_REQUIRED [%s]: %s (Platform: %s)",
                getattr(event, "intervention_type", "UNKNOWN"),
                getattr(event, "message", ""),
                getattr(event, "platform", "unknown"),
            )
            listener = getattr(self, "on_intervention", None)
            if callable(listener):
                listener(event)
        except Exception as exc:
            logger.error("Error in handle_intervention: %s", exc)
