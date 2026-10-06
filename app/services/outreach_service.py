"""Outreach Service providing the primary domain boundary for the Outreach Center."""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from app.db.base import utc_now
from app.db.models import (
    Application,
    Communication,
    Company,
    Contact,
    EmailTemplate,
    FollowUp,
    Job,
    Resume,
    User,
)
from app.db.session import SessionLocal, get_db_session
from app.repositories.application_repository import ApplicationRepository
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.dto.outreach_dto import (
    ConnectionStatusDTO,
    DuplicateMatchResultDTO,
    EmailMessageDTO,
    OutreachCreateDTO,
    SendResultDTO,
)
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    CadenceState,
    ConversationOpState,
    ConversationState,
    FollowUpStatus,
    InboundClassification,
    MessageStatus,
    NextActionOwner,
    NextActionType,
    PriorityLevel,
    WorkQueueSection,
)
from app.services.dto.outreach_viewmodels import (
    BulkTargetPreviewItemDTO,
    BulkTargetValidationResultDTO,
    ContactViewModel,
    ConversationDetailViewModel,
    FollowUpStepViewModel,
    NextActionRecommendation,
    OutreachCaseOperationViewModel,
    OutreachConversationViewModel,
    PresentationConversationState,
    ResumeSnapshotViewModel,
    TimelineMessageViewModel,
    WorkQueueGroupViewModel,
)
from app.services.email.factory import get_email_provider
from app.services.secrets_service import SecretsService
from app.services.email.provider import EmailProvider
from app.services.outreach_dispatcher import OutreachDispatcher
from app.services.template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)


class OutreachService:
    """Primary service coordinating templates, 2-phase outbox dispatch, and recruiter threads."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        dispatcher: Optional[OutreachDispatcher] = None,
        email_provider: Optional[EmailProvider] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._dispatcher = dispatcher or OutreachDispatcher(session_factory=self._session_factory)
        self._email_provider = email_provider

    def seed_templates_if_empty(self) -> int:
        with get_db_session(self._session_factory) as s:
            repo = EmailTemplateRepository(s)
            return repo.seed_defaults_if_empty()

    def list_templates(
        self,
        category: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[Dict[str, Any]]:
        """Returns list of active email templates with metadata."""
        with get_db_session(self._session_factory) as s:
            repo = EmailTemplateRepository(s)
            repo.seed_defaults_if_empty()
            templates = repo.list_all(include_inactive=include_inactive, category=category)
            return [
                {
                    "id": t.id,
                    "key": t.key,
                    "name": t.name,
                    "category": t.category,
                    "subject_template": t.subject_template,
                    "body_template": t.body_template,
                    "variables": json.loads(t.variables_json) if t.variables_json else [],
                    "is_active": t.is_active,
                }
                for t in templates
            ]

    def get_template(self, template_id: int) -> Optional[Dict[str, Any]]:
        with get_db_session(self._session_factory) as s:
            repo = EmailTemplateRepository(s)
            t = repo.get_by_id(template_id)
            if not t:
                return None
            return {
                "id": t.id,
                "key": t.key,
                "name": t.name,
                "category": t.category,
                "subject_template": t.subject_template,
                "body_template": t.body_template,
                "variables": json.loads(t.variables_json) if t.variables_json else [],
                "is_active": t.is_active,
            }

    def preview_template(
        self,
        template_id: int,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Interpolates context variables and generates safe preview representations."""
        with get_db_session(self._session_factory) as s:
            repo = EmailTemplateRepository(s)
            t = repo.get_by_id(template_id)
            if not t:
                return {"error": f"Template {template_id} not found", "preview": ""}

            subj_preview = TemplateRenderer.preview(t.subject_template, context)
            body_preview = TemplateRenderer.preview(t.body_template, context)

            all_missing = sorted(list(set(subj_preview["missing_variables"] + body_preview["missing_variables"])))
            return {
                "template_id": t.id,
                "template_name": t.name,
                "subject_preview": subj_preview["preview"],
                "body_preview": body_preview["preview"],
                "missing_variables": all_missing,
                "is_ready_to_send": len(all_missing) == 0,
            }

    def send_outreach(
        self,
        dto: OutreachCreateDTO,
        sender_name: Optional[str] = None,
        sender_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Dispatches an outbound outreach message through the 2-phase outbox engine."""
        with get_db_session(self._session_factory) as s:
            from app.repositories.user_repository import UserRepository
            from app.services.secrets_service import SecretsService

            user = UserRepository(s).get_primary_user()
            if not user:
                user = s.get(User, 1)

            creds = SecretsService().get_email_credentials(dto.account_id)
            auth_email = creds.get("user") if (creds and creds.get("user") and "@" in str(creds.get("user"))) else None

            resolved_name = sender_name or (user.name if user else "Candidate")
            resolved_email = sender_email or auth_email or (user.email if user else "candidate@example.com")

            # Interpolate template if requested and fields are blank
            if dto.template_id and (not dto.subject or not dto.body_text):
                tmpl_repo = EmailTemplateRepository(s)
                tmpl = tmpl_repo.get_by_id(dto.template_id)
                if tmpl:
                    ctx = {
                        "candidate_name": resolved_name,
                        "candidate_email": resolved_email,
                        "recruiter_name": dto.contact_name or "Hiring Team",
                        "company_name": dto.manual_company_name or "",
                        "job_title": dto.manual_job_title or "",
                        "platform": "JobPilot Direct Outreach",
                    }
                    if not dto.subject:
                        dto.subject, _ = TemplateRenderer.render(tmpl.subject_template, ctx, strict=False)
                    if not dto.body_text:
                        dto.body_text, _ = TemplateRenderer.render(tmpl.body_template, ctx, strict=False)

        send_res, app, comm, dup = self._dispatcher.dispatch_outreach(
            dto=dto,
            sender_name=resolved_name,
            sender_email=resolved_email,
            provider=self._email_provider,
        )

        if dup and dup.is_duplicate:
            return {
                "success": False,
                "is_duplicate": True,
                "error": f"Duplicate application detected under {dup.match_tier}",
                "duplicate_info": {
                    "tier": dup.match_tier,
                    "existing_application_id": dup.existing_application_id,
                    "existing_status": dup.existing_status,
                    "company_name": dup.company_name,
                    "job_title": dup.job_title,
                    "applied_at": dup.applied_at.isoformat() if dup.applied_at else None,
                },
            }

        return {
            "success": send_res.success,
            "status": send_res.status.value if send_res.status else MessageStatus.FAILED.value,
            "send_token": send_res.send_token,
            "provider_message_id": send_res.provider_message_id,
            "application_id": app.id if app else None,
            "communication_id": comm.id if comm else None,
            "error": send_res.error_message,
        }

    def send_reply(
        self,
        application_id: int,
        body_text: str,
        subject: Optional[str] = None,
        attachment_path: Optional[str] = None,
        resume_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Dispatches a direct, threaded reply email to an ongoing recruiter conversation."""
        try:
            application_id = int(application_id)
        except (ValueError, TypeError):
            return {"success": False, "error": f"Invalid application ID: {application_id}"}

        if not body_text or not body_text.strip():
            return {"success": False, "error": "Reply message body cannot be empty."}

        with get_db_session(self._session_factory) as s:
            from app.repositories.user_repository import UserRepository
            from app.services.secrets_service import SecretsService
            import uuid

            app = s.get(Application, application_id)
            if not app:
                return {"success": False, "error": f"Application {application_id} not found."}

            # Find latest non-draft communication to thread against
            comms = s.execute(
                select(Communication)
                .where(
                    Communication.application_id == application_id,
                    Communication.status != MessageStatus.DRAFT.value,
                )
                .order_by(Communication.occurred_at.desc())
            ).scalars().all()

            latest_comm = comms[0] if comms else None
            latest_inbound = next((c for c in comms if c.direction == "INBOUND"), None)

            # Determine recipient email
            recipient_email = None
            if latest_inbound and latest_inbound.sender_email and "@" in latest_inbound.sender_email:
                recipient_email = latest_inbound.sender_email
            elif app.contact and app.contact.email and "@" in app.contact.email:
                recipient_email = app.contact.email
            elif latest_comm and latest_comm.recipient_email:
                recipient_email = latest_comm.recipient_email

            if not recipient_email:
                return {"success": False, "error": "Could not determine recipient recruiter email address."}

            # Determine subject: preserve exact root subject to ensure Gmail threading
            if not subject:
                base_subj = ""
                for c in reversed(comms):
                    if c.subject and c.subject.strip():
                        base_subj = c.subject.strip()
                        break
                if not base_subj and latest_comm and latest_comm.subject:
                    base_subj = latest_comm.subject.strip()
                if not base_subj:
                    base_subj = f"Application: {app.job.title if app.job else 'Inquiry'}"

                clean_subj = base_subj
                while clean_subj.lower().startswith(("re:", "re :", "fwd:", "fwd :")):
                    clean_subj = clean_subj.split(":", 1)[1].strip()
                subject = f"Re: {clean_subj}"

            # Threading identifiers (RFC 2822 In-Reply-To and References)
            def _format_msg_id(mid: Optional[str]) -> Optional[str]:
                if not mid:
                    return None
                m = mid.strip()
                if not m:
                    return None
                if not m.startswith("<"):
                    m = f"<{m}"
                if not m.endswith(">"):
                    m = f"{m}>"
                return m

            in_reply_to = None
            references = None

            # Immediate parent is latest inbound if available, else latest outbound application
            target_parent = latest_inbound if (latest_inbound and latest_inbound.provider_message_id) else (latest_comm if (latest_comm and latest_comm.provider_message_id) else None)
            if target_parent and target_parent.provider_message_id:
                in_reply_to = _format_msg_id(target_parent.provider_message_id)

            # Accumulate full References thread chain
            ref_list = []
            for c in reversed(comms):
                if c.provider_message_id:
                    fmt = _format_msg_id(c.provider_message_id)
                    if fmt and fmt not in ref_list:
                        ref_list.append(fmt)

            if ref_list:
                references = " ".join(ref_list)
            elif in_reply_to:
                references = in_reply_to

            # Sender credentials
            user = UserRepository(s).get_primary_user() or s.get(User, 1)
            creds = SecretsService().get_email_credentials("default")
            auth_email = creds.get("user") if (creds and creds.get("user") and "@" in str(creds.get("user"))) else None
            resolved_email = auth_email or (creds.get("username") if creds else None) or (user.email if user else "candidate@example.com")
            resolved_name = (creds.get("sender_name") if creds else None) or (user.name if user else "Candidate")

            send_token = uuid.uuid4().hex

            # Stage attachment if provided
            snapshot_path = None
            if resume_id:
                res_obj = s.get(Resume, resume_id)
                if res_obj and res_obj.file_path and os.path.exists(res_obj.file_path):
                    snapshot_path = self._dispatcher.stage_attachment(res_obj.file_path, send_token)
            elif attachment_path and os.path.exists(attachment_path):
                snapshot_path = self._dispatcher.stage_attachment(attachment_path, send_token)

            msg_dto = EmailMessageDTO(
                account_id="default",
                send_token=send_token,
                from_address=resolved_email,
                from_name=resolved_name,
                to_address=recipient_email,
                subject=subject,
                body_text=body_text.strip(),
                in_reply_to=in_reply_to,
                references=references,
                attachment_snapshot_path=snapshot_path,
            )

            provider = self._email_provider or get_email_provider("default")
            res: SendResultDTO = provider.send_email(msg_dto)

            if not res.success:
                return {
                    "success": False,
                    "error": res.error_message or "Failed to send email via SMTP provider.",
                }

            # Record outgoing communication
            new_comm = Communication(
                application_id=app.id,
                contact_id=app.contact_id,
                type="EMAIL",
                direction="OUTBOUND",
                status=MessageStatus.SENT.value,
                subject=subject,
                sender_email=resolved_email,
                recipient_email=recipient_email,
                body_snippet=body_text.strip()[:160],
                summary=body_text.strip(),
                attachment_snapshot_path=snapshot_path,
                provider_message_id=res.provider_message_id or send_token,
                occurred_at=datetime.now(timezone.utc),
            )
            s.add(new_comm)

            # Update resume on application if provided
            if resume_id and not app.resume_id:
                app.resume_id = resume_id

            # Update application status
            if app.status in ("APPLIED", "RECRUITER_CONTACTED"):
                app.status = "RECRUITER_CONTACTED"

            s.commit()
            return {
                "success": True,
                "communication_id": new_comm.id,
                "message": "Reply dispatched successfully and recorded in conversation thread.",
            }

    def get_conversation_timeline(self, application_id: int) -> Dict[str, Any]:
        """Pulls complete communication history and scheduled follow-ups for an application."""
        with get_db_session(self._session_factory) as s:
            app = s.get(Application, application_id)
            if not app:
                return {"error": "Application not found"}

            communications = s.execute(
                select(Communication)
                .where(Communication.application_id == application_id)
                .order_by(Communication.occurred_at.asc())
            ).scalars().all()

            follow_ups = s.execute(
                select(FollowUp)
                .where(FollowUp.application_id == application_id)
                .order_by(FollowUp.step_number.asc())
            ).scalars().all()

            # Determine aggregate conversation state
            conv_state = ConversationState.WAITING.value
            has_recruiter_reply = any(c.direction == "INBOUND" for c in communications)
            if has_recruiter_reply:
                conv_state = ConversationState.REPLIED.value
            elif any(f.status == FollowUpStatus.PAUSED.value for f in follow_ups):
                conv_state = ConversationState.NEEDS_ACTION.value
            elif app.status in ("OFFER", "REJECTED", "WITHDRAWN"):
                conv_state = ConversationState.COMPLETED.value

            # Resolve resume information if attached to application
            resume_info = None
            if app.resume_id:
                r_obj = s.get(Resume, app.resume_id)
                if r_obj:
                    v_raw = getattr(r_obj, "version", "1.0") or "1.0"
                    v_tag = f"v{v_raw}" if not str(v_raw).startswith("v") else str(v_raw)
                    resume_info = {
                        "id": r_obj.id,
                        "name": r_obj.name,
                        "role_target": r_obj.role_target or "General",
                        "version": v_tag,
                        "file_path": r_obj.file_path,
                    }

            return {
                "application_id": app.id,
                "company_name": app.job.company.name if (app.job and app.job.company) else (app.job.company_raw if app.job else ""),
                "job_title": app.job.title if app.job else "",
                "status": app.status,
                "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                "resume_info": resume_info,
                "contact": {
                    "id": app.contact.id,
                    "name": app.contact.name,
                    "email": app.contact.email,
                    "designation": app.contact.designation,
                } if app.contact else None,
                "conversation_state": conv_state,
                "communications": [
                    {
                        "id": c.id,
                        "type": c.type,
                        "direction": c.direction,
                        "status": c.status,
                        "occurred_at": c.occurred_at.isoformat() if c.occurred_at else None,
                        "subject": c.subject,
                        "snippet": c.body_snippet or (c.summary[:150] if c.summary else ""),
                        "body_text": c.summary or c.body_snippet or "",
                        "attachment_path": c.attachment_snapshot_path,
                        "attachment_name": os.path.basename(c.attachment_snapshot_path) if c.attachment_snapshot_path else None,
                        "resume_info": resume_info if c.direction == "OUTBOUND" else None,
                        "sender_email": c.sender_email,
                        "recipient_email": c.recipient_email,
                        "error_message": c.error_message,
                    }
                    for c in communications
                ],
                "follow_ups": [
                    {
                        "id": f.id,
                        "step_number": f.step_number,
                        "due_at": f.due_at.isoformat() if f.due_at else None,
                        "status": f.status,
                        "paused_reason": f.paused_reason,
                        "notes": f.notes,
                    }
                    for f in follow_ups
                ],
            }

    def list_conversations(
        self,
        state_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Returns summarized active outreach conversations for the UI inbox/table."""
        results = []
        with get_db_session(self._session_factory) as s:
            stmt = (
                select(Application)
                .where(Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL)
                .order_by(desc(Application.created_at))
                .limit(limit)
            )
            apps = s.execute(stmt).scalars().all()

            for app in apps:
                timeline = self.get_conversation_timeline(app.id)
                if state_filter and timeline.get("conversation_state") != state_filter:
                    continue

                last_comm = timeline["communications"][-1] if timeline["communications"] else None
                next_fu = next((f for f in timeline["follow_ups"] if f["status"] == FollowUpStatus.PENDING.value), None)

                results.append({
                    "application_id": app.id,
                    "company_name": timeline["company_name"],
                    "job_title": timeline["job_title"],
                    "status": app.status,
                    "contact_name": timeline["contact"]["name"] if timeline["contact"] else "",
                    "contact_email": timeline["contact"]["email"] if timeline["contact"] else "",
                    "conversation_state": timeline["conversation_state"],
                    "last_activity_at": last_comm["occurred_at"] if last_comm else timeline["applied_at"],
                    "last_message_snippet": last_comm["snippet"] if last_comm else "",
                    "next_followup_due": next_fu["due_at"] if next_fu else None,
                })

        return results

    def list_due_followups(self) -> List[Dict[str, Any]]:
        """Finds all follow-ups that have become due for action."""
        now = datetime.now(timezone.utc)
        results = []
        with get_db_session(self._session_factory) as s:
            stmt = (
                select(FollowUp)
                .where(
                    FollowUp.status.in_([FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value]),
                    FollowUp.due_at <= now,
                )
                .order_by(FollowUp.due_at.asc())
            )
            for fu in s.execute(stmt).scalars().all():
                results.append({
                    "id": fu.id,
                    "application_id": fu.application_id,
                    "contact_id": fu.contact_id,
                    "step_number": fu.step_number,
                    "due_at": fu.due_at.isoformat(),
                    "status": fu.status,
                    "company_name": fu.application.job.company.name if (fu.application and fu.application.job and fu.application.job.company) else "",
                    "job_title": fu.application.job.title if (fu.application and fu.application.job) else "",
                    "contact_name": fu.contact.name if fu.contact else "",
                    "contact_email": fu.contact.email if fu.contact else "",
                })
        return results

    def pause_followups(self, application_id: int, reason: str = "Recruiter replied") -> int:
        """Pauses all pending and due followups for an application (critical safety invariant)."""
        count = 0
        with get_db_session(self._session_factory) as s:
            fus = s.execute(
                select(FollowUp).where(
                    FollowUp.application_id == application_id,
                    FollowUp.status.in_([
                        FollowUpStatus.PENDING.value,
                        FollowUpStatus.DUE.value,
                    ]),
                )
            ).scalars().all()

            for f in fus:
                f.status = FollowUpStatus.PAUSED.value
                f.paused_reason = reason
                count += 1
            s.commit()
        logger.info("Paused %d follow-ups on application %d (reason: %s)", count, application_id, reason)
        return count

    def resume_followups(self, application_id: int) -> int:
        """Resumes paused follow-ups for an application."""
        count = 0
        now = datetime.now(timezone.utc)
        with get_db_session(self._session_factory) as s:
            fus = s.execute(
                select(FollowUp).where(
                    FollowUp.application_id == application_id,
                    FollowUp.status == FollowUpStatus.PAUSED.value,
                )
            ).scalars().all()

            for f in fus:
                due_dt = f.due_at
                if due_dt and due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                if due_dt and due_dt <= now:
                    f.status = FollowUpStatus.DUE.value
                else:
                    f.status = FollowUpStatus.PENDING.value
                f.paused_reason = None
                count += 1
            s.commit()
        logger.info("Resumed %d follow-ups on application %d", count, application_id)
        return count

    def stop_followups(self, application_id: int, reason: str = "Sequence stopped") -> int:
        """Permanently cancels all active follow-ups for an application."""
        count = 0
        with get_db_session(self._session_factory) as s:
            fus = s.execute(
                select(FollowUp).where(
                    FollowUp.application_id == application_id,
                    FollowUp.status.in_([
                        FollowUpStatus.PENDING.value,
                        FollowUpStatus.DUE.value,
                        FollowUpStatus.PAUSED.value,
                    ]),
                )
            ).scalars().all()

            for f in fus:
                f.status = FollowUpStatus.CANCELLED.value
                f.paused_reason = reason
                count += 1
            s.commit()
        logger.info("Stopped %d follow-ups on application %d", count, application_id)
        return count

    def test_provider_connection(self, account_id: str = "default") -> ConnectionStatusDTO:
        provider = self._email_provider or get_email_provider(account_id)
        return provider.test_connection()

    def reconcile_startup_outreach(self) -> Dict[str, Any]:
        """Scans for in-flight SENDING messages and overdue scheduled messages on application boot."""
        provider = self._email_provider or get_email_provider("default")
        stuck_reconciled = self._dispatcher.reconcile_in_flight_communications(provider=provider, max_age_seconds=300)

        now = datetime.now(timezone.utc)
        overdue_scheduled = 0
        with get_db_session(self._session_factory) as s:
            scheduled_comms = s.execute(
                select(Communication).where(
                    Communication.status == MessageStatus.SCHEDULED.value
                )
            ).scalars().all()
            for comm in scheduled_comms:
                # If scheduled message was due in the past
                if comm.occurred_at and comm.occurred_at < now:
                    overdue_scheduled += 1

        logger.info(
            "Outreach startup reconciliation complete: %d stuck communications recovered, %d overdue scheduled messages detected.",
            stuck_reconciled,
            overdue_scheduled,
        )
        return {
            "stuck_reconciled": stuck_reconciled,
            "overdue_scheduled": overdue_scheduled,
        }

    def get_outreach_stats(self) -> Dict[str, Any]:
        """Returns high-level metric counts for the Outreach Center dashboard."""
        now = datetime.now(timezone.utc)
        with get_db_session(self._session_factory) as s:
            total_apps = s.execute(
                select(func.count(Application.id)).where(
                    Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL
                )
            ).scalar() or 0

            total_sent = s.execute(
                select(func.count(Communication.id)).where(
                    Communication.status == MessageStatus.SENT.value,
                    Communication.direction == "OUTBOUND",
                )
            ).scalar() or 0

            total_replied = s.execute(
                select(func.count(func.distinct(Communication.application_id))).where(
                    Communication.direction == "INBOUND"
                )
            ).scalar() or 0

            followups_due = s.execute(
                select(func.count(FollowUp.id)).where(
                    FollowUp.status.in_([FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value]),
                    FollowUp.due_at <= now,
                )
            ).scalar() or 0

            total_failed = s.execute(
                select(func.count(Communication.id)).where(
                    Communication.status == MessageStatus.FAILED.value
                )
            ).scalar() or 0

            awaiting_reply = max(0, total_sent - total_replied)

            delivery_rate = 100.0
            if (total_sent + total_failed) > 0:
                delivery_rate = round((total_sent / (total_sent + total_failed)) * 100, 1)

            return {
                "total_outreached": total_apps,
                "total_sent": total_sent,
                "awaiting_reply": awaiting_reply,
                "recruiter_replied": total_replied,
                "followups_due": followups_due,
                "total_failed": total_failed,
                "delivery_success_rate": delivery_rate,
            }

    # ===================================================================
    # Draft Persistence (Outreach Redesign §4)
    # ===================================================================

    def save_draft(
        self,
        application_id: int,
        body_text: str,
        subject: Optional[str] = None,
        recipient_email: Optional[str] = None,
    ) -> int:
        """Persists or updates a restart-safe draft for the given application.

        Uses Communication table with status=DRAFT. Upserts: if a DRAFT row
        already exists for the application, it is updated rather than creating
        a duplicate.

        Returns the communication.id of the draft row.
        """
        with get_db_session(self._session_factory) as s:
            existing = s.execute(
                select(Communication).where(
                    Communication.application_id == application_id,
                    Communication.status == MessageStatus.DRAFT.value,
                    Communication.direction == "OUTBOUND",
                )
            ).scalars().first()

            if existing:
                existing.summary = body_text
                existing.body_snippet = body_text[:160]
                if subject is not None:
                    existing.subject = subject
                if recipient_email is not None:
                    existing.recipient_email = recipient_email
                existing.occurred_at = datetime.now(timezone.utc)
                s.commit()
                logger.debug("Updated draft %d for application %d", existing.id, application_id)
                return existing.id

            app = s.get(Application, application_id)
            draft_subject = subject
            if not draft_subject and app:
                comms = s.execute(
                    select(Communication)
                    .where(
                        Communication.application_id == application_id,
                        Communication.status != MessageStatus.DRAFT.value,
                    )
                    .order_by(Communication.occurred_at.asc())
                ).scalars().all()
                for c in comms:
                    if c.subject and c.subject.strip():
                        clean_s = c.subject.strip()
                        while clean_s.lower().startswith(("re:", "re :", "fwd:", "fwd :")):
                            clean_s = clean_s.split(":", 1)[1].strip()
                        draft_subject = f"Re: {clean_s}"
                        break
                if not draft_subject and app.job and app.job.title:
                    draft_subject = f"Re: Application for {app.job.title}"

            draft = Communication(
                application_id=application_id,
                contact_id=app.contact_id if app else None,
                type="EMAIL",
                direction="OUTBOUND",
                status=MessageStatus.DRAFT.value,
                subject=draft_subject or "",
                body_snippet=body_text[:160],
                summary=body_text,
                recipient_email=recipient_email or "",
                occurred_at=datetime.now(timezone.utc),
            )
            s.add(draft)
            s.commit()
            logger.info("Created draft %d for application %d", draft.id, application_id)
            return draft.id

    def get_draft(self, application_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves the active draft for an application, if one exists."""
        with get_db_session(self._session_factory) as s:
            draft = s.execute(
                select(Communication).where(
                    Communication.application_id == application_id,
                    Communication.status == MessageStatus.DRAFT.value,
                    Communication.direction == "OUTBOUND",
                )
            ).scalars().first()

            if not draft:
                return None
            return {
                "id": draft.id,
                "subject": draft.subject,
                "body_text": draft.summary or draft.body_snippet or "",
                "recipient_email": draft.recipient_email,
                "updated_at": draft.occurred_at.isoformat() if draft.occurred_at else None,
            }

    def delete_draft(self, application_id: int) -> bool:
        """Deletes the active draft for an application. Returns True if a draft was removed."""
        with get_db_session(self._session_factory) as s:
            draft = s.execute(
                select(Communication).where(
                    Communication.application_id == application_id,
                    Communication.status == MessageStatus.DRAFT.value,
                    Communication.direction == "OUTBOUND",
                )
            ).scalars().first()

            if not draft:
                return False
            s.delete(draft)
            s.commit()
            logger.info("Deleted draft for application %d", application_id)
            return True

    # ===================================================================
    # Presentation ViewModel Factory Methods (Outreach Redesign §3)
    # ===================================================================

    @staticmethod
    def _compute_next_action(
        app_status: str,
        conv_state: PresentationConversationState,
        has_inbound: bool,
        latest_inbound_classification: Optional[str] = None,
        next_followup_due: Optional[datetime] = None,
    ) -> NextActionRecommendation:
        """Derives the best Next Action for the candidate based on conversation state."""
        now = datetime.now(timezone.utc)

        # Terminal states
        if app_status in ("OFFER", "REJECTED", "WITHDRAWN"):
            return NextActionRecommendation(
                action_type="WAIT",
                headline="Conversation Completed",
                rationale=f"Application status: {app_status}",
                cta_label="View Details",
            )

        # Recruiter replied — determine response type
        if conv_state in (PresentationConversationState.NEEDS_ACTION, PresentationConversationState.REPLIED):
            if latest_inbound_classification == InboundClassification.INTERVIEW_REQUEST.value:
                return NextActionRecommendation(
                    action_type="SCHEDULE_INTERVIEW",
                    headline="Confirm Interview Availability",
                    rationale="Recruiter requested an interview slot",
                    cta_label="Draft Reply",
                    suggested_status="INTERVIEWING",
                )
            if latest_inbound_classification == InboundClassification.INFORMATION_REQUEST.value:
                return NextActionRecommendation(
                    action_type="REPLY",
                    headline="Answer Recruiter Questions",
                    rationale="Recruiter asked screening questions",
                    cta_label="Draft Reply",
                )
            return NextActionRecommendation(
                action_type="REPLY",
                headline="Reply to Recruiter",
                rationale="Recruiter responded — reply to keep momentum",
                cta_label="Draft Reply",
            )

        # Follow-up due
        if conv_state == PresentationConversationState.FOLLOW_UP_DUE:
            return NextActionRecommendation(
                action_type="EXECUTE_FOLLOWUP",
                headline="Send Scheduled Follow-Up",
                rationale="Follow-up cadence step is due",
                cta_label="Execute Now",
                due_date=next_followup_due,
            )

        # Paused sequence
        if conv_state == PresentationConversationState.PAUSED:
            return NextActionRecommendation(
                action_type="RESUME_CADENCE",
                headline="Follow-Up Paused",
                rationale="Cadence paused — resume when ready",
                cta_label="Resume Cadence",
            )

        # Unmatched inbound
        if conv_state == PresentationConversationState.NEEDS_REVIEW:
            return NextActionRecommendation(
                action_type="REVIEW_ATTACHMENT",
                headline="Review Unmatched Email",
                rationale="Inbound email could not be auto-linked",
                cta_label="Link to Application",
            )

        # Default: waiting
        return NextActionRecommendation(
            action_type="WAIT",
            headline="Awaiting Recruiter Reply",
            rationale="Initial outreach sent — waiting for response",
            cta_label="View Latest Message",
        )

    def _resolve_presentation_state(
        self,
        app_status: str,
        has_inbound: bool,
        latest_inbound_classification: Optional[str],
        follow_ups: list,
        has_draft: bool,
    ) -> PresentationConversationState:
        """Maps raw DB state to the unified PresentationConversationState."""
        now = datetime.now(timezone.utc)

        if app_status in ("OFFER", "REJECTED", "WITHDRAWN"):
            return PresentationConversationState.COMPLETED

        if has_inbound and latest_inbound_classification in (
            InboundClassification.INTERVIEW_REQUEST.value,
            InboundClassification.INFORMATION_REQUEST.value,
            InboundClassification.ASSESSMENT_REQUEST.value,
        ):
            return PresentationConversationState.NEEDS_ACTION

        if has_inbound:
            return PresentationConversationState.REPLIED

        # Check for overdue follow-ups
        for fu in follow_ups:
            if fu.status == FollowUpStatus.PAUSED.value:
                return PresentationConversationState.PAUSED
            if fu.status in (FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value):
                if fu.due_at and fu.due_at <= now:
                    return PresentationConversationState.FOLLOW_UP_DUE

        return PresentationConversationState.WAITING

    def list_conversations_vm(
        self,
        state_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[OutreachConversationViewModel]:
        """Returns paginated, structured inbox ViewModels for the redesigned UI."""
        results: List[OutreachConversationViewModel] = []
        now = datetime.now(timezone.utc)

        with get_db_session(self._session_factory) as s:
            stmt = (
                select(Application)
                .where(Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL)
                .order_by(desc(Application.created_at))
            )

            # Server-side search
            if search_query:
                like_pattern = f"%{search_query}%"
                stmt = (
                    stmt
                    .join(Application.job, isouter=True)
                    .join(Job.company, isouter=True)
                    .join(Application.contact, isouter=True)
                    .where(
                        (Company.name.ilike(like_pattern)) |
                        (Job.company_raw.ilike(like_pattern)) |
                        (Job.title.ilike(like_pattern)) |
                        (Contact.name.ilike(like_pattern)) |
                        (Contact.email.ilike(like_pattern))
                    )
                )

            stmt = stmt.limit(limit).offset(offset)
            apps = s.execute(stmt).scalars().all()

            for app in apps:
                # Resolve company and job title
                company_name = ""
                job_title = ""
                if app.job:
                    job_title = app.job.title or ""
                    if app.job.company:
                        company_name = app.job.company.name or ""
                    elif app.job.company_raw:
                        company_name = app.job.company_raw

                # Contact info
                recruiter_name = app.contact.name if app.contact else ""
                recruiter_email = app.contact.email if app.contact else ""

                # Communications analysis
                comms = s.execute(
                    select(Communication)
                    .where(Communication.application_id == app.id)
                    .order_by(Communication.occurred_at.desc())
                ).scalars().all()

                has_inbound = any(c.direction == "INBOUND" for c in comms)
                latest_inbound = next((c for c in comms if c.direction == "INBOUND"), None)
                latest_inbound_class = getattr(latest_inbound, "ai_classification", None) if latest_inbound else None
                last_comm = comms[0] if comms else None

                # Follow-ups
                follow_ups = s.execute(
                    select(FollowUp)
                    .where(FollowUp.application_id == app.id)
                    .order_by(FollowUp.step_number.asc())
                ).scalars().all()

                next_fu_due = None
                for fu in follow_ups:
                    if fu.status in (FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value) and fu.due_at:
                        next_fu_due = fu.due_at
                        break

                # Draft check
                has_draft = any(c.status == MessageStatus.DRAFT.value and c.direction == "OUTBOUND" for c in comms)
                draft_preview = None
                if has_draft:
                    draft_comm = next((c for c in comms if c.status == MessageStatus.DRAFT.value and c.direction == "OUTBOUND"), None)
                    draft_preview = (draft_comm.body_snippet or "")[:80] if draft_comm else None

                # Resume
                resume_tag = None
                if app.resume_id:
                    r_obj = s.get(Resume, app.resume_id)
                    if r_obj:
                        v_raw = getattr(r_obj, "version", "1.0") or "1.0"
                        resume_tag = f"v{v_raw}" if not str(v_raw).startswith("v") else str(v_raw)

                # Compute state
                p_state = self._resolve_presentation_state(
                    app_status=app.status or "",
                    has_inbound=has_inbound,
                    latest_inbound_classification=latest_inbound_class,
                    follow_ups=follow_ups,
                    has_draft=has_draft,
                )

                # Filter by state or work queue section
                if state_filter:
                    if state_filter in ("NEEDS_ACTION", "TODAY"):
                        if p_state not in (
                            PresentationConversationState.NEEDS_ACTION,
                            PresentationConversationState.FOLLOW_UP_DUE,
                            PresentationConversationState.NEEDS_REVIEW,
                            PresentationConversationState.REPLIED,
                        ):
                            continue
                    elif state_filter == "WAITING":
                        if p_state not in (
                            PresentationConversationState.WAITING,
                            PresentationConversationState.REPLIED,
                        ):
                            continue
                    elif state_filter == "UPCOMING":
                        if p_state not in (
                            PresentationConversationState.SCHEDULED,
                            PresentationConversationState.FOLLOW_UP_DUE,
                        ):
                            continue
                    elif state_filter == "CLOSED":
                        if p_state not in (
                            PresentationConversationState.COMPLETED,
                            PresentationConversationState.PAUSED,
                        ):
                            continue
                    elif p_state.value != state_filter:
                        continue

                next_action = self._compute_next_action(
                    app_status=app.status or "",
                    conv_state=p_state,
                    has_inbound=has_inbound,
                    latest_inbound_classification=latest_inbound_class,
                    next_followup_due=next_fu_due,
                )

                snippet = ""
                last_activity = app.created_at
                if last_comm:
                    raw_s = last_comm.body_snippet or (last_comm.summary[:150] if last_comm.summary else "")
                    snippet = " ".join(raw_s.split())[:120]
                    last_activity = last_comm.occurred_at or app.created_at

                meta = self._get_app_meta(app.notes)
                is_prio = bool(meta.get("is_priority", False))
                is_rd = bool(meta.get("is_read", True))

                # Apply priority or unread filters if requested in state_filter
                if state_filter == "STARRED" and not is_prio:
                    continue
                if state_filter == "UNREAD" and is_rd:
                    continue

                results.append(OutreachConversationViewModel(
                    application_id=app.id,
                    company_name=company_name,
                    job_title=job_title,
                    recruiter_name=recruiter_name,
                    recruiter_email=recruiter_email,
                    recruitment_status=app.status or "",
                    state=p_state,
                    next_action=next_action,
                    last_activity_at=last_activity,
                    last_snippet=snippet,
                    has_unmatched_inbound=False,
                    active_draft_preview=draft_preview,
                    resume_version_tag=resume_tag,
                    unread_count=0 if is_rd else 1,
                    is_priority=is_prio,
                ))

        return results

    @staticmethod
    def _get_app_meta(notes: Optional[str]) -> dict:
        if not notes:
            return {}
        import re, json
        m = re.search(r'<!--meta:(\{.*?\})-->', notes)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return {}

    @staticmethod
    def _set_app_meta(notes: Optional[str], meta: dict) -> str:
        import re, json
        meta_str = f"<!--meta:{json.dumps(meta)}-->"
        current = notes or ""
        if re.search(r'<!--meta:(\{.*?\})-->', current):
            return re.sub(r'<!--meta:(\{.*?\})-->', meta_str, current)
        return (current + "\n" + meta_str).strip()

    def mark_conversation_read(self, application_id: int, is_read: bool = True) -> bool:
        """Marks a conversation as read or unread (persisting to indexed column and note fallback)."""
        with get_db_session(self._session_factory) as s:
            app = s.get(Application, application_id)
            if not app:
                return False
            app.is_unread = not is_read
            meta = self._get_app_meta(app.notes)
            meta["is_read"] = is_read
            app.notes = self._set_app_meta(app.notes, meta)
            s.commit()
            return True

    def toggle_conversation_priority(self, application_id: int) -> bool:
        """Toggles priority/starred state for a conversation (persisting to indexed column and note fallback)."""
        with get_db_session(self._session_factory) as s:
            app = s.get(Application, application_id)
            if not app:
                return False
            meta = self._get_app_meta(app.notes)
            new_prio = not (app.is_priority if app.is_priority is not None else meta.get("is_priority", False))
            app.is_priority = new_prio
            meta["is_priority"] = new_prio
            app.notes = self._set_app_meta(app.notes, meta)
            s.commit()
            return new_prio

    def _build_outreach_case(self, app: Application, now: Optional[datetime] = None) -> OutreachCaseOperationViewModel:
        """Transforms a fully loaded Application into an OutreachCaseOperationViewModel."""
        now = now or datetime.now(timezone.utc)

        # 1. Company and Job
        company_name = ""
        job_title = ""
        if app.job:
            job_title = app.job.title or ""
            if app.job.company:
                company_name = app.job.company.name or ""
            elif app.job.company_raw:
                company_name = app.job.company_raw

        # 2. Contact
        c_id = app.contact.id if app.contact else None
        c_name = app.contact.name if app.contact else ""
        c_email = app.contact.email if app.contact else ""
        c_desig = app.contact.designation if app.contact else None

        # 3. Communications breakdown
        comms = sorted(
            app.communications or [],
            key=lambda c: c.occurred_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        inbounds = [c for c in comms if c.direction == "INBOUND"]
        outbounds = [c for c in comms if c.direction == "OUTBOUND"]
        drafts = [c for c in outbounds if c.status == MessageStatus.DRAFT.value]

        last_comm = comms[0] if comms else None
        last_inbound = inbounds[0] if inbounds else None
        last_outbound = outbounds[0] if outbounds else None
        has_draft = len(drafts) > 0

        last_inbound_at = last_inbound.occurred_at if last_inbound else None
        last_outbound_at = last_outbound.occurred_at if last_outbound else None
        last_contact_at = last_comm.occurred_at if last_comm else app.applied_at or app.created_at

        last_snippet = ""
        if last_comm:
            raw_s = last_comm.body_snippet or (last_comm.summary[:150] if last_comm.summary else "")
            last_snippet = " ".join(raw_s.split())[:120]

        # 4. Cadence & Follow-ups
        follow_ups = sorted(app.follow_ups or [], key=lambda f: f.step_number)
        cadence_total = len(follow_ups)
        pending_or_due_fu = [
            f for f in follow_ups if f.status in (FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value)
        ]
        active_step = pending_or_due_fu[0].step_number if pending_or_due_fu else (cadence_total if cadence_total > 0 else 0)

        is_paused = any(f.status == FollowUpStatus.PAUSED.value for f in follow_ups)
        next_due_fu = pending_or_due_fu[0] if pending_or_due_fu else None
        next_fu_due_at = next_due_fu.due_at if next_due_fu else None

        if is_paused:
            cadence_state = CadenceState.PAUSED
        elif pending_or_due_fu:
            cadence_state = CadenceState.ACTIVE
        elif cadence_total > 0:
            cadence_state = CadenceState.COMPLETED
        else:
            cadence_state = CadenceState.NONE

        # 5. Metadata (Priority & Unread)
        meta = self._get_app_meta(app.notes)
        is_prio = bool(app.is_priority if app.is_priority is not None else meta.get("is_priority", False))
        is_unrd = bool(app.is_unread if app.is_unread is not None else not meta.get("is_read", True))

        # 6. Resume tag
        resume_tag = None
        if app.resume:
            v_raw = getattr(app.resume, "version", "1.0") or "1.0"
            resume_tag = f"v{v_raw}" if not str(v_raw).startswith("v") else str(v_raw)

        # 7. Operational State & Next Action Resolution
        app_status_upper = (app.status or "").upper()

        # Terminal state
        if app_status_upper in ("OFFER", "REJECTED", "WITHDRAWN"):
            conv_state = ConversationOpState.COMPLETED if app_status_upper == "OFFER" else ConversationOpState.CLOSED
            next_action_type = NextActionType.NONE
            next_action_owner = NextActionOwner.NONE
            next_action_headline = f"Application {app_status_upper.capitalize()}"
            next_action_rationale = f"Process concluded with status: {app_status_upper}"
            next_action_cta = "View History"
            section = WorkQueueSection.CLOSED
            prio = PriorityLevel.LOW

        # Recruiter replied and needs candidate response
        elif last_inbound and (not last_outbound_at or (last_inbound_at and last_inbound_at >= last_outbound_at)):
            conv_state = ConversationOpState.NEEDS_ACTION
            next_action_owner = NextActionOwner.USER
            section = WorkQueueSection.TODAY
            inbound_class = getattr(last_inbound, "ai_classification", None)

            if inbound_class == InboundClassification.INTERVIEW_REQUEST.value:
                next_action_type = NextActionType.CONFIRM_INTERVIEW
                next_action_headline = "Confirm Interview Availability"
                next_action_rationale = "Recruiter requested an interview slot"
                next_action_cta = "Confirm Interview"
                prio = PriorityLevel.HIGH
            elif inbound_class in (
                InboundClassification.INFORMATION_REQUEST.value,
                InboundClassification.ASSESSMENT_REQUEST.value,
            ):
                next_action_type = NextActionType.REPLY_TO_RECRUITER
                next_action_headline = "Answer Recruiter Questions"
                next_action_rationale = "Recruiter asked screening questions or requested assessment"
                next_action_cta = "Draft Reply"
                prio = PriorityLevel.HIGH
            elif inbound_class == InboundClassification.OFFER.value:
                next_action_type = NextActionType.UPDATE_APPLICATION
                next_action_headline = "Review Offer Details"
                next_action_rationale = "Candidate received an offer notification"
                next_action_cta = "Update Status"
                prio = PriorityLevel.HIGH
            elif inbound_class == InboundClassification.REJECTION.value:
                conv_state = ConversationOpState.CLOSED
                next_action_type = NextActionType.UPDATE_APPLICATION
                next_action_owner = NextActionOwner.USER
                next_action_headline = "Acknowledge Rejection"
                next_action_rationale = "Rejection detected — update recruitment stage"
                next_action_cta = "Close Application"
                section = WorkQueueSection.CLOSED
                prio = PriorityLevel.LOW
            else:
                next_action_type = NextActionType.REPLY_TO_RECRUITER
                next_action_headline = "Review Recruiter Reply"
                next_action_rationale = "Recruiter responded — follow up to maintain momentum"
                next_action_cta = "Draft Reply"
                prio = PriorityLevel.HIGH if is_prio else PriorityLevel.NORMAL

        # Follow-up due today or overdue
        elif next_due_fu and next_due_fu.due_at and next_due_fu.due_at <= now:
            conv_state = ConversationOpState.FOLLOW_UP_DUE
            next_action_owner = NextActionOwner.USER
            next_action_type = NextActionType.SEND_FOLLOW_UP
            next_action_headline = f"Send Follow-Up #{next_due_fu.step_number}"
            next_action_rationale = f"Cadence step #{next_due_fu.step_number} is due for outreach"
            next_action_cta = "Send Follow-Up"
            section = WorkQueueSection.TODAY
            prio = PriorityLevel.HIGH if is_prio else PriorityLevel.NORMAL

        # Active draft in progress
        elif has_draft:
            conv_state = ConversationOpState.WAITING_FOR_USER
            next_action_owner = NextActionOwner.USER
            next_action_type = NextActionType.REPLY_TO_RECRUITER
            next_action_headline = "Finish Draft Outreach"
            next_action_rationale = "Unfinished draft awaiting completion"
            next_action_cta = "Resume Draft"
            section = WorkQueueSection.TODAY
            prio = PriorityLevel.NORMAL

        # Upcoming scheduled follow-up
        elif next_due_fu and next_due_fu.due_at and next_due_fu.due_at > now:
            conv_state = ConversationOpState.SCHEDULED
            next_action_owner = NextActionOwner.SYSTEM
            next_action_type = NextActionType.WAIT_FOR_RECRUITER
            days_left = (next_due_fu.due_at - now).days
            next_action_headline = f"Follow-Up #{next_due_fu.step_number} in {max(1, days_left)} day(s)"
            next_action_rationale = f"Next cadence trigger scheduled for {next_due_fu.due_at.strftime('%b %d')}"
            next_action_cta = "View Cadence"
            section = WorkQueueSection.UPCOMING
            prio = PriorityLevel.NORMAL

        # Paused cadence
        elif is_paused:
            conv_state = ConversationOpState.PAUSED
            next_action_owner = NextActionOwner.USER
            next_action_type = NextActionType.RESUME_CADENCE
            next_action_headline = "Cadence Paused"
            next_action_rationale = "Automated outreach sequence is currently paused"
            next_action_cta = "Resume Cadence"
            section = WorkQueueSection.WAITING
            prio = PriorityLevel.LOW

        # Default: Waiting on recruiter
        else:
            conv_state = ConversationOpState.WAITING_FOR_RECRUITER
            next_action_owner = NextActionOwner.RECRUITER
            next_action_type = NextActionType.WAIT_FOR_RECRUITER
            next_action_headline = "Awaiting Recruiter Response"
            next_action_rationale = "Outbound pitch dispatched — ball is in recruiter's court"
            next_action_cta = "View Thread"
            section = WorkQueueSection.WAITING
            prio = PriorityLevel.NORMAL

        return OutreachCaseOperationViewModel(
            application_id=app.id,
            company_name=company_name,
            job_title=job_title,
            recruitment_status=app.status or "",
            contact_id=c_id,
            contact_name=c_name,
            contact_email=c_email,
            contact_designation=c_desig,
            conversation_state=conv_state,
            next_action_type=next_action_type,
            next_action_owner=next_action_owner,
            next_action_due_at=next_fu_due_at,
            next_action_headline=next_action_headline,
            next_action_rationale=next_action_rationale,
            next_action_cta=next_action_cta,
            priority=prio,
            cadence_state=cadence_state,
            cadence_active_step=active_step,
            cadence_total_steps=cadence_total,
            last_contact_at=last_contact_at,
            last_inbound_at=last_inbound_at,
            last_outbound_at=last_outbound_at,
            last_snippet=last_snippet,
            unread_attention=is_unrd,
            is_priority=is_prio,
            resume_version_tag=resume_tag,
            has_draft=has_draft,
            work_queue_section=section,
        )

    def list_outreach_cases(
        self,
        filter_mode: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OutreachCaseOperationViewModel]:
        """Returns projected, high-performance operational cases avoiding N+1 queries."""
        now = datetime.now(timezone.utc)
        with get_db_session(self._session_factory) as s:
            repo = ApplicationRepository(s)
            is_prio = True if filter_mode == "STARRED" else None
            is_unrd = True if filter_mode == "UNREAD" else None

            apps = repo.get_outreach_applications_projected(
                search_query=search_query,
                is_priority=is_prio,
                is_unread=is_unrd,
                limit=limit,
                offset=offset,
            )

            cases = [self._build_outreach_case(app, now=now) for app in apps]

            # Filter by operational filters if specified
            if filter_mode and filter_mode not in ("ALL", "STARRED", "UNREAD"):
                cases = [
                    c for c in cases
                    if c.conversation_state.value == filter_mode
                    or c.work_queue_section.value == filter_mode
                ]

            return cases

    def get_work_queue(self, search_query: Optional[str] = None) -> List[WorkQueueGroupViewModel]:
        """Categorizes all active outreach cases into a prioritized 4-section Work Queue."""
        cases = self.list_outreach_cases(filter_mode=None, search_query=search_query, limit=500)

        today_cases = [c for c in cases if c.work_queue_section == WorkQueueSection.TODAY]
        upcoming_cases = [c for c in cases if c.work_queue_section == WorkQueueSection.UPCOMING]
        waiting_cases = [c for c in cases if c.work_queue_section == WorkQueueSection.WAITING]
        closed_cases = [c for c in cases if c.work_queue_section == WorkQueueSection.CLOSED]

        return [
            WorkQueueGroupViewModel(
                section=WorkQueueSection.TODAY,
                headline="🚨 Needs Action Today",
                count=len(today_cases),
                cases=today_cases,
            ),
            WorkQueueGroupViewModel(
                section=WorkQueueSection.UPCOMING,
                headline="⏳ Upcoming Cadences",
                count=len(upcoming_cases),
                cases=upcoming_cases,
            ),
            WorkQueueGroupViewModel(
                section=WorkQueueSection.WAITING,
                headline="📨 Waiting on Recruiters",
                count=len(waiting_cases),
                cases=waiting_cases,
            ),
            WorkQueueGroupViewModel(
                section=WorkQueueSection.CLOSED,
                headline="📁 Completed & Closed",
                count=len(closed_cases),
                cases=closed_cases,
            ),
        ]

    def validate_bulk_targets(self, application_ids: Optional[List[int]] = None) -> BulkTargetValidationResultDTO:
        """Pre-validates a set of selected applications for bulk email dispatch."""
        with get_db_session(self._session_factory) as s:
            repo = ApplicationRepository(s)
            items: List[BulkTargetPreviewItemDTO] = []
            valid_count = 0
            dup_count = 0
            err_count = 0

            query = (
                select(Application)
                .options(
                    selectinload(Application.job).selectinload(Job.company),
                    selectinload(Application.contact),
                    selectinload(Application.resume),
                    selectinload(Application.communications),
                    selectinload(Application.follow_ups),
                )
            )
            if application_ids:
                query = query.where(Application.id.in_(application_ids))
            else:
                query = (
                    query
                    .join(Application.contact)
                    .where(Contact.email.isnot(None), Contact.email != "")
                    .order_by(Application.created_at.desc())
                    .limit(100)
                )

            apps = s.execute(query).scalars().all()

            for app in apps:
                comp_name = (
                    app.job.company.name
                    if (app.job and app.job.company)
                    else (app.job.company_raw if app.job else "Direct Opportunity")
                )
                job_title = app.job.title if app.job else "Opportunity"
                rec_name = app.contact.name if app.contact else "Recruiter"
                rec_email = (app.contact.email or "").strip().lower() if app.contact else ""
                r_id = app.resume_id
                r_name = app.resume.name if app.resume else "Default Resume"

                is_valid = True
                val_err = None
                is_dup = False
                dup_tier = None

                # Check 1: Recruiter email syntax
                if not rec_email or "@" not in rec_email or "." not in rec_email.split("@")[-1]:
                    is_valid = False
                    val_err = "Missing or invalid recruiter email"
                    err_count += 1

                # Check 2: Resume file exists on disk
                if is_valid and app.resume and app.resume.file_path:
                    if not os.path.exists(app.resume.file_path):
                        is_valid = False
                        val_err = f"Resume file not found at {app.resume.file_path}"
                        err_count += 1

                # Check 3: Duplicate check against OTHER active applications
                if is_valid:
                    dup_res = repo.check_duplicate_outreach_application(
                        contact_email=rec_email,
                        job_title=job_title,
                        company_name=comp_name,
                    )
                    if dup_res.is_duplicate and dup_res.existing_application_id != app.id:
                        is_dup = True
                        dup_tier = dup_res.match_tier
                        dup_count += 1

                if is_valid and not is_dup:
                    valid_count += 1
                elif is_dup:
                    is_valid = False
                    val_err = f"Duplicate ({dup_tier or 'active application'})"

                case = self._build_outreach_case(app)
                items.append(
                    BulkTargetPreviewItemDTO(
                        application_id=app.id,
                        company_name=comp_name,
                        job_title=job_title,
                        recruiter_name=rec_name,
                        recruiter_email=rec_email,
                        resume_id=r_id,
                        resume_name=r_name,
                        is_valid=is_valid,
                        validation_error=val_err,
                        is_duplicate=is_dup,
                        duplicate_tier=dup_tier,
                        current_state=case.conversation_state,
                        next_action_type=case.next_action_type,
                        is_selected=is_valid and not is_dup,
                    )
                )

            total_sel = len(application_ids) if application_ids is not None else len(items)
            return BulkTargetValidationResultDTO(
                total_selected=total_sel,
                valid_count=valid_count,
                duplicate_count=dup_count,
                error_count=err_count,
                items=items,
            )

    def dispatch_bulk_outreach_step(
        self,
        application_id: Optional[int],
        template_id: int,
        resume_id: Optional[int] = None,
        override_duplicate: bool = False,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None,
        target_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Dispatches an outreach email to a single target application or fresh recipient as part of a bulk batch."""
        try:
            with get_db_session(self._session_factory) as s:
                app = None
                if application_id:
                    app = s.get(Application, application_id)

                if app:
                    if not app.contact or not app.contact.email:
                        return {"success": False, "error": f"Application {application_id} has no valid contact email."}
                    comp_name = (
                        app.job.company.name
                        if (app.job and app.job.company)
                        else (app.job.company_raw if app.job else "")
                    )
                    job_title = app.job.title if app.job else ""
                    rec_name = app.contact.name or "Hiring Manager"
                    contact_email = app.contact.email
                    job_id = app.job_id
                    contact_id = app.contact_id
                    existing_app_id = app.id
                    res_id = resume_id or app.resume_id
                elif target_info:
                    comp_name = target_info.get("company_name", "")
                    job_title = target_info.get("job_title", "")
                    rec_name = target_info.get("recruiter_name", "Hiring Manager")
                    contact_email = target_info.get("recruiter_email", "")
                    if not contact_email or "@" not in contact_email:
                        return {"success": False, "error": "Recipient email is invalid."}
                    job_id = None
                    contact_id = None
                    existing_app_id = None
                    res_id = resume_id
                else:
                    return {"success": False, "error": "No valid target application or recipient details provided."}

                # Render template / custom template override
                repo_tpl = EmailTemplateRepository(s)
                tpl = repo_tpl.get_by_id(template_id)
                subj_source = custom_subject if custom_subject else (tpl.subject_template if tpl else "")
                body_source = custom_body if custom_body else (tpl.body_template if tpl else "")

                primary_user = UserRepository(s).get_primary_user() or s.get(User, 1)
                context = {
                    "candidate_name": primary_user.name if (primary_user and primary_user.name) else "Candidate",
                    "candidate_email": primary_user.email if (primary_user and primary_user.email) else "candidate@example.com",
                    "candidate_phone": primary_user.phone if (primary_user and primary_user.phone) else "",
                    "portfolio_url": "",
                    "skills": "Python, RPA, Automation",
                    "years_of_experience": "2",
                    "company_name": comp_name,
                    "job_title": job_title,
                    "recruiter_name": rec_name,
                    "platform": "JobPilot Direct Outreach",
                }
                subj, _ = TemplateRenderer.render(subj_source, context, strict=False)
                body, _ = TemplateRenderer.render(body_source, context, strict=False)

                dto = OutreachCreateDTO(
                    existing_application_id=existing_app_id,
                    job_id=job_id,
                    manual_company_name=comp_name,
                    manual_job_title=job_title,
                    contact_id=contact_id,
                    contact_name=rec_name,
                    contact_email=contact_email,
                    resume_id=res_id,
                    template_id=template_id,
                    subject=subj,
                    body_text=body,
                    override_duplicate=override_duplicate,
                )

            creds = SecretsService().get_email_credentials(dto.account_id)
            auth_email = creds.get("user") if (creds and creds.get("user") and "@" in str(creds.get("user"))) else None
            primary_user = UserRepository(s).get_primary_user() or s.get(User, 1) if 's' in locals() else None
            resolved_name = (primary_user.name if primary_user else None) or "Candidate"
            resolved_email = auth_email or (primary_user.email if primary_user else None) or "candidate@example.com"

            res, staged_app, comm, dup = self._dispatcher.dispatch_outreach(
                dto=dto,
                sender_name=resolved_name,
                sender_email=resolved_email,
                provider=self._email_provider,
            )
            resolved_app_id = application_id or (staged_app.id if staged_app else None)
            return {
                "success": res.success,
                "application_id": resolved_app_id,
                "error": res.error_message if not res.success else None,
                "provider_message_id": res.provider_message_id,
            }
        except Exception as e:
            logger.error("Error in dispatch_bulk_outreach_step for target %s: %s", application_id or target_info, e)
            return {
                "success": False,
                "application_id": application_id,
                "error": str(e),
                "provider_message_id": None,
            }

    def get_conversation_detail_vm(self, application_id: int) -> Optional[ConversationDetailViewModel]:
        """Returns a fully populated ConversationDetailViewModel for the recruitment workspace."""
        with get_db_session(self._session_factory) as s:
            app = s.get(Application, application_id)
            if not app:
                return None

            # Company / Job
            company_name = ""
            job_title = ""
            if app.job:
                job_title = app.job.title or ""
                if app.job.company:
                    company_name = app.job.company.name or ""
                elif app.job.company_raw:
                    company_name = app.job.company_raw

            # Contact
            contact_vm = None
            if app.contact:
                contact_vm = ContactViewModel(
                    id=app.contact.id,
                    name=app.contact.name or "",
                    email=app.contact.email or "",
                    designation=app.contact.designation,
                )

            # Resume snapshot
            resume_vm = None
            r_obj = None
            if app.resume_id:
                r_obj = s.get(Resume, app.resume_id)
            if not r_obj:
                r_obj = s.execute(select(Resume).where(Resume.is_default == True)).scalar_one_or_none()
                if not r_obj:
                    r_obj = s.execute(select(Resume).order_by(Resume.id.asc())).scalars().first()

            if r_obj:
                v_raw = getattr(r_obj, "version", "1.0") or "1.0"
                v_tag = f"v{v_raw}" if not str(v_raw).startswith("v") else str(v_raw)
                if not app.resume_id:
                    v_tag += " (Profile Default)"
                file_exists = bool(r_obj.file_path and os.path.isfile(r_obj.file_path))
                resume_vm = ResumeSnapshotViewModel(
                    id=r_obj.id,
                    name=r_obj.name or "Primary Candidate Resume",
                    role_target=r_obj.role_target or "General Profile",
                    version_tag=v_tag,
                    file_path=r_obj.file_path,
                    file_exists=file_exists,
                )

            # Communications
            comms = s.execute(
                select(Communication)
                .where(Communication.application_id == application_id)
                .order_by(Communication.occurred_at.asc())
            ).scalars().all()

            messages = []
            draft_body = None
            draft_subject = None
            has_inbound = False
            latest_inbound_class = None

            for c in comms:
                if c.status == MessageStatus.DRAFT.value and c.direction == "OUTBOUND":
                    draft_body = c.summary or c.body_snippet or ""
                    draft_subject = c.subject
                    continue  # Don't show DRAFT in thread messages

                if c.direction == "INBOUND":
                    has_inbound = True
                    latest_inbound_class = getattr(c, "ai_classification", None)

                resume_tag_msg = None
                if c.direction == "OUTBOUND" and resume_vm:
                    resume_tag_msg = resume_vm.version_tag

                messages.append(TimelineMessageViewModel(
                    id=c.id,
                    direction=c.direction or "",
                    status=c.status or "",
                    occurred_at=c.occurred_at,
                    subject=c.subject,
                    snippet=c.body_snippet or (c.summary[:160] if c.summary else ""),
                    body_text=c.summary or c.body_snippet or "",
                    sender_email=c.sender_email,
                    recipient_email=c.recipient_email,
                    attachment_path=c.attachment_snapshot_path,
                    attachment_name=os.path.basename(c.attachment_snapshot_path) if c.attachment_snapshot_path else None,
                    resume_version_tag=resume_tag_msg,
                    error_message=c.error_message,
                ))

            # Follow-ups
            follow_ups_raw = s.execute(
                select(FollowUp)
                .where(FollowUp.application_id == application_id)
                .order_by(FollowUp.step_number.asc())
            ).scalars().all()

            follow_ups_vm = [
                FollowUpStepViewModel(
                    id=f.id,
                    step_number=f.step_number,
                    due_at=f.due_at,
                    status=f.status or "",
                    paused_reason=f.paused_reason,
                    notes=f.notes,
                )
                for f in follow_ups_raw
            ]

            next_fu_due = None
            for fu in follow_ups_raw:
                if fu.status in (FollowUpStatus.PENDING.value, FollowUpStatus.DUE.value) and fu.due_at:
                    next_fu_due = fu.due_at
                    break

            # Compute state
            p_state = self._resolve_presentation_state(
                app_status=app.status or "",
                has_inbound=has_inbound,
                latest_inbound_classification=latest_inbound_class,
                follow_ups=follow_ups_raw,
                has_draft=draft_body is not None,
            )

            next_action = self._compute_next_action(
                app_status=app.status or "",
                conv_state=p_state,
                has_inbound=has_inbound,
                latest_inbound_classification=latest_inbound_class,
                next_followup_due=next_fu_due,
            )

            return ConversationDetailViewModel(
                application_id=app.id,
                company_name=company_name,
                job_title=job_title,
                recruitment_status=app.status or "",
                applied_at=app.applied_at,
                state=p_state,
                next_action=next_action,
                contact=contact_vm,
                resume=resume_vm,
                messages=messages,
                follow_ups=follow_ups_vm,
                active_draft_body=draft_body,
                active_draft_subject=draft_subject,
            )

    def refine_pitch(
        self,
        current_body: str,
        instructions: Optional[str] = None,
        company_name: str = "",
        job_title: str = "",
    ) -> Dict[str, Any]:
        """Refines pitch body via OutreachAIService."""
        from app.services.outreach_ai_service import OutreachAIService
        ai_svc = OutreachAIService(session_factory=self._session_factory)
        return ai_svc.refine_pitch(
            current_body=current_body,
            instructions=instructions,
            company_name=company_name,
            job_title=job_title,
        )

    def generate_rag_reply(
        self,
        application_id: int,
        user_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generates a contextual RAG reply grounded in thread history and candidate facts."""
        from app.services.outreach_ai_service import OutreachAIService
        ai_svc = OutreachAIService(session_factory=self._session_factory)
        return ai_svc.generate_rag_reply(
            application_id=application_id,
            user_prompt=user_prompt,
        )

