"""Follow-up cadence evaluation and automated reminder/dispatch scheduler."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models import Application, Communication, FollowUp, User
from app.db.session import SessionLocal, get_db_session
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_enums import (
    FollowUpStatus,
    MessageStatus,
)
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)

STEP_TEMPLATE_KEYS = {
    1: "followup_step_1_checkin",
    2: "followup_step_2_value_add",
    3: "followup_step_3_graceful_closeout",
}


class FollowUpScheduler:
    """Evaluates due follow-ups and supports manual queueing or guarded automatic execution."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        dispatcher: Optional[OutreachDispatcher] = None,
        outreach_service: Optional[Any] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._dispatcher = dispatcher or OutreachDispatcher(session_factory=self._session_factory)
        self._outreach_service = outreach_service

    def refresh_due_statuses(self) -> int:
        """Transitions any PENDING follow-ups whose due_at has arrived into DUE status."""
        now = datetime.now(timezone.utc)
        count = 0
        with get_db_session(self._session_factory) as s:
            due_records = s.execute(
                select(FollowUp).where(
                    FollowUp.status == FollowUpStatus.PENDING.value,
                    FollowUp.due_at <= now,
                )
            ).scalars().all()

            for fu in due_records:
                fu.status = FollowUpStatus.DUE.value
                count += 1
            s.commit()
        return count

    def prepare_followup_draft(self, followup_id: int) -> Dict[str, Any]:
        """Pre-populates subject and body for a due follow-up using canonical step templates."""
        with get_db_session(self._session_factory) as s:
            fu = s.get(FollowUp, followup_id)
            if not fu or not fu.application:
                return {"error": "Follow-up record not found"}

            app = fu.application
            from app.repositories.user_repository import UserRepository
            user = s.get(User, app.user_id) if app.user_id else UserRepository(s).get_primary_user()
            tmpl_repo = EmailTemplateRepository(s)
            tmpl_repo.seed_defaults_if_empty()

            tmpl_key = STEP_TEMPLATE_KEYS.get(fu.step_number, "followup_step_1_checkin")
            tmpl = tmpl_repo.get_by_key(tmpl_key)
            if not tmpl:
                tmpl = tmpl_repo.get_by_key("followup_step_1_checkin")

            candidate_name = user.name if user else "Candidate"
            candidate_email = user.email if user else "candidate@jobpilot.local"
            recruiter_name = app.contact.name if app.contact else "Hiring Team"
            comp_name = app.job.company.name if (app.job and app.job.company) else (app.job.company_raw if app.job else "")
            job_title = app.job.title if app.job else ""

            ctx = {
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "recruiter_name": recruiter_name,
                "company_name": comp_name,
                "job_title": job_title,
                "skills": "Python, RPA, System Architecture",
                "portfolio_url": "https://github.com",
            }

            subj, _ = TemplateRenderer.render(tmpl.subject_template, ctx, strict=False)
            body, _ = TemplateRenderer.render(tmpl.body_template, ctx, strict=False)

            return {
                "followup_id": fu.id,
                "step_number": fu.step_number,
                "application_id": app.id,
                "company_name": comp_name,
                "job_title": job_title,
                "contact_name": recruiter_name,
                "contact_email": app.contact.email if app.contact else "",
                "subject": subj,
                "body_text": body,
                "template_id": tmpl.id,
            }

    def execute_followup(
        self,
        followup_id: int,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches the follow-up email and marks the follow-up as COMPLETED."""
        with get_db_session(self._session_factory) as s:
            fu = s.get(FollowUp, followup_id)
            if not fu or not fu.application:
                return {"success": False, "error": "Follow-up record not found"}

            if fu.status == FollowUpStatus.PAUSED.value:
                return {
                    "success": False,
                    "error": f"Cannot execute follow-up: paused due to '{fu.paused_reason}'",
                }

            app = fu.application
            contact = app.contact
            if not contact or not contact.email:
                return {"success": False, "error": "Application has no recruiter contact email"}

            # Prepare body text
            if not custom_body:
                draft = self.prepare_followup_draft(followup_id)
                body = draft.get("body_text", "Following up on my previous note.")
            else:
                body = custom_body

            if not self._outreach_service:
                from app.services.outreach_service import OutreachService
                self._outreach_service = OutreachService(
                    session_factory=self._session_factory,
                    dispatcher=self._dispatcher,
                )

            reply_res = self._outreach_service.send_reply(
                application_id=app.id,
                body_text=body,
                subject=custom_subject or None,
            )

            if reply_res.get("success"):
                fu.status = FollowUpStatus.COMPLETED.value
                fu.completed_at = utc_now()
                fu.notes = f"Executed follow-up step {fu.step_number}"
                s.commit()
                return {
                    "success": True,
                    "followup_id": fu.id,
                    "status": "COMPLETED",
                    "communication_id": reply_res.get("communication_id"),
                }
            else:
                return {
                    "success": False,
                    "error": reply_res.get("error", "Failed to dispatch follow-up email"),
                }
