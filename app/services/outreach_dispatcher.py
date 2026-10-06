"""Outreach Dispatcher implementing the two-phase idempotent send workflow."""

from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import shutil
from typing import List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models import (
    Application,
    Company,
    Contact,
    Communication,
    FollowUp,
    Job,
    Resume,
    calculate_file_sha256,
)
from app.db.models.job import generate_job_fingerprint
from app.db.session import SessionLocal, get_db_session
from app.repositories.application_repository import ApplicationRepository
from app.services.dto.outreach_dto import (
    DuplicateMatchResultDTO,
    EmailMessageDTO,
    OutreachCreateDTO,
    SendResultDTO,
)
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    CANONICAL_PLATFORM_EMAIL,
    FollowUpStatus,
    MessageStatus,
)
from app.services.email.factory import get_email_provider
from app.services.email.provider import EmailProvider

logger = logging.getLogger(__name__)


class OutreachDispatcher:
    """Orchestrates 2-phase outbox writes, immutable attachment staging, and network dispatch."""

    DEFAULT_ATTACHMENT_DIR = Path.home() / ".jobpilot" / "outbox_attachments"

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        attachments_dir: Optional[Path] = None,
        default_provider: Optional[EmailProvider] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._attachments_dir = attachments_dir or self.DEFAULT_ATTACHMENT_DIR
        self._attachments_dir.mkdir(parents=True, exist_ok=True)
        self._default_provider = default_provider

    @property
    def attachments_dir(self) -> Path:
        return self._attachments_dir

    def stage_attachment(self, source_path: str, send_token: str) -> Optional[str]:
        """Copies an attachment to an immutable staged snapshot file keyed by send_token and hash."""
        if not source_path or not os.path.exists(source_path):
            return None

        file_hash = calculate_file_sha256(source_path)[:12]
        base_name = os.path.basename(source_path)
        dest_filename = f"{send_token}_{file_hash}_{base_name}"
        dest_path = self._attachments_dir / dest_filename

        try:
            shutil.copy2(source_path, dest_path)
            return str(dest_path)
        except Exception as e:
            logger.error("Failed to stage attachment from %s: %s", source_path, e)
            return None

    def prepare_outbox_transaction(
        self,
        session: Session,
        dto: OutreachCreateDTO,
        send_token: str,
        sender_email: str,
        snapshot_path: Optional[str],
    ) -> Tuple[Optional[Application], Optional[Communication], Optional[DuplicateMatchResultDTO]]:
        """Phase 1: Validates duplicate rules and commits Application + Communication in SENDING state."""
        app_repo = ApplicationRepository(session)

        # 1. Duplicate check across active pipeline states
        dup_result = DuplicateMatchResultDTO(is_duplicate=False)
        if not dto.existing_application_id:
            dup_result = app_repo.check_duplicate_outreach_application(
                job_id=dto.job_id,
                company_name=dto.manual_company_name,
                job_title=dto.manual_job_title,
                contact_email=dto.contact_email,
                source_url=dto.manual_job_url,
            )

            if dup_result.is_duplicate and not dto.override_duplicate:
                logger.info("Duplicate application detected in Tier %s. Aborting pre-commit.", dup_result.match_tier)
                return None, None, dup_result

        # 2. Resolve or create Company
        company_id = None
        comp_name = (dto.manual_company_name or "").strip()
        if comp_name:
            norm_name = comp_name.lower()
            existing_comp = session.execute(
                select(Company).where(Company.normalized_name == norm_name)
            ).scalar_one_or_none()
            if existing_comp:
                company_id = existing_comp.id
            else:
                new_comp = Company(name=comp_name, normalized_name=norm_name)
                session.add(new_comp)
                session.flush()
                company_id = new_comp.id

        # 3. Resolve or create Contact
        contact = None
        if dto.contact_id:
            contact = session.get(Contact, dto.contact_id)
        elif dto.contact_email:
            clean_email = dto.contact_email.strip().lower()
            contact = session.execute(
                select(Contact).where(Contact.email == clean_email)
            ).scalar_one_or_none()
            if not contact:
                contact = Contact(
                    name=dto.contact_name or clean_email.split("@")[0],
                    email=clean_email,
                    designation=dto.contact_designation or "Recruiter / Hiring Contact",
                    company_id=company_id,
                )
                session.add(contact)
                session.flush()

        # 4. Resolve or create Job
        job = None
        if dto.job_id:
            job = session.get(Job, dto.job_id)
        elif not dto.existing_application_id:
            job_title = dto.manual_job_title or "Direct Outreach Opportunity"
            c_raw = comp_name or "Direct Outreach"
            src_url = dto.manual_job_url or f"email://{dto.contact_email or 'recruiter'}"
            fp = generate_job_fingerprint(
                platform=CANONICAL_PLATFORM_EMAIL,
                company=c_raw,
                title=job_title,
                source_url=src_url,
            )
            existing_job = session.execute(select(Job).where(Job.job_fingerprint == fp)).scalar_one_or_none()
            if existing_job:
                job = existing_job
            else:
                job = Job(
                    company_id=company_id,
                    platform=CANONICAL_PLATFORM_EMAIL,
                    job_fingerprint=fp,
                    title=job_title,
                    company_raw=c_raw,
                    source_url=src_url,
                    application_method=CANONICAL_APPLICATION_METHOD_EMAIL,
                )
                session.add(job)
                session.flush()

        # 5. Create or reuse Application
        from app.repositories.user_repository import UserRepository
        primary_u = UserRepository(session).get_primary_user()
        active_user_id = primary_u.id if primary_u else 1

        if dto.existing_application_id:
            application = session.get(Application, dto.existing_application_id)
            if not application:
                logger.error("Existing application %s not found. Aborting pre-commit.", dto.existing_application_id)
                return None, None, None
            application.status = "SUBMITTED"
            application.applied_at = utc_now()
            if dto.resume_id:
                application.resume_id = dto.resume_id
            if contact and not application.contact_id:
                application.contact_id = contact.id
        else:
            application = Application(
                job_id=job.id,
                user_id=active_user_id,
                resume_id=dto.resume_id,
                contact_id=contact.id if contact else None,
                status="SUBMITTED",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                applied_at=utc_now(),
                external_job_link=dto.manual_job_url,
            )
            session.add(application)
            session.flush()

        # 6. Create Communication in SENDING status (guarantees outbox record before network I/O)
        initial_status = MessageStatus.SENDING.value
        if dto.schedule_time and dto.schedule_time > datetime.now(timezone.utc):
            initial_status = MessageStatus.SCHEDULED.value

        comm = Communication(
            application_id=application.id,
            contact_id=contact.id if contact else None,
            type="EMAIL",
            direction="OUTBOUND",
            status=initial_status,
            account_id=dto.account_id,
            send_token=send_token,
            sender_email=sender_email,
            recipient_email=dto.contact_email,
            template_id=dto.template_id,
            attachment_snapshot_path=snapshot_path,
            body_snippet=(dto.body_text or "")[:250],
            subject=dto.subject,
            summary=dto.body_text,
            source="outreach_composer",
        )
        session.add(comm)
        session.flush()

        return application, comm, None

    def complete_outbox_transaction(
        self,
        session: Session,
        send_token: str,
        send_result: SendResultDTO,
        cadence_days: Optional[List[int]] = None,
    ) -> bool:
        """Phase 2: Updates Communication status based on provider response and registers follow-ups if sent."""
        comm = session.execute(
            select(Communication).where(Communication.send_token == send_token)
        ).scalar_one_or_none()

        if not comm:
            logger.error("Cannot complete outbox transaction: communication with send_token=%s not found", send_token)
            return False

        if send_result.success:
            comm.status = MessageStatus.SENT.value
            comm.provider_message_id = send_result.provider_message_id
            comm.provider_thread_id = send_result.provider_thread_id
            comm.occurred_at = send_result.timestamp or utc_now()
            comm.error_message = None

            # Schedule follow-up cadences
            if cadence_days and comm.application_id:
                seq_id = f"seq_{uuid.uuid4().hex[:12]}"
                for step_idx, days in enumerate(cadence_days, 1):
                    due_date = comm.occurred_at + timedelta(days=days)
                    fu = FollowUp(
                        application_id=comm.application_id,
                        contact_id=comm.contact_id,
                        sequence_id=seq_id,
                        step_number=step_idx,
                        due_at=due_date,
                        status=FollowUpStatus.PENDING.value,
                        notes=f"Automated follow-up step {step_idx} ({days} days after outreach)",
                    )
                    session.add(fu)
        else:
            comm.status = MessageStatus.FAILED.value
            comm.error_message = send_result.error_message or "Unknown provider dispatch failure"

        return True

    def dispatch_outreach(
        self,
        dto: OutreachCreateDTO,
        sender_name: str,
        sender_email: str,
        provider: Optional[EmailProvider] = None,
    ) -> Tuple[SendResultDTO, Optional[Application], Optional[Communication], Optional[DuplicateMatchResultDTO]]:
        """Executes the full 2-phase send workflow with idempotency and transaction boundaries."""
        send_token = f"stk_{uuid.uuid4().hex}"
        email_provider = provider or self._default_provider or get_email_provider(dto.account_id)

        # 1. Resolve and stage attachment
        snapshot_path = None
        if dto.resume_id:
            with get_db_session(self._session_factory) as s:
                resume = s.get(Resume, dto.resume_id)
                if resume and resume.file_path:
                    snapshot_path = self.stage_attachment(resume.file_path, send_token)

        # 2. Phase 1: Database Pre-commit
        with get_db_session(self._session_factory) as s:
            app, comm, dup = self.prepare_outbox_transaction(
                session=s,
                dto=dto,
                send_token=send_token,
                sender_email=sender_email,
                snapshot_path=snapshot_path,
            )
            if dup and dup.is_duplicate:
                return (
                    SendResultDTO(
                        success=False,
                        send_token=send_token,
                        status=MessageStatus.FAILED,
                        error_message=f"Duplicate application detected under {dup.match_tier}",
                    ),
                    None,
                    None,
                    dup,
                )
            s.commit()
            app_id = app.id if app else None
            comm_id = comm.id if comm else None

        # 3. Check if Deferred/Scheduled Send
        if dto.schedule_time and dto.schedule_time > datetime.now(timezone.utc):
            send_result = SendResultDTO(
                success=True,
                send_token=send_token,
                status=MessageStatus.SCHEDULED,
                timestamp=dto.schedule_time,
            )
            with get_db_session(self._session_factory) as s:
                fresh_app = s.get(Application, app_id) if app_id else None
                fresh_comm = s.get(Communication, comm_id) if comm_id else None
                s.expunge_all()
            return send_result, fresh_app, fresh_comm, None

        # 4. Network Dispatch

        msg_payload = EmailMessageDTO(
            account_id=dto.account_id,
            send_token=send_token,
            from_address=sender_email,
            from_name=sender_name,
            to_address=dto.contact_email or "",
            subject=dto.subject,
            body_text=dto.body_text,
            body_html=dto.body_html,
            attachment_snapshot_path=snapshot_path,
        )

        try:
            send_result = email_provider.send_email(msg_payload)
        except Exception as e:
            logger.error("Exception during email provider send_email: %s", e)
            send_result = SendResultDTO(
                success=False,
                send_token=send_token,
                status=MessageStatus.FAILED,
                error_message=f"{type(e).__name__}: {str(e)}",
                timestamp=datetime.now(timezone.utc),
            )

        # 3B. Two-Way Sync: Append outbound email to Gmail label if configured
        if send_result.success:
            try:
                from app.services.secrets_service import SecretsService
                creds = SecretsService(session_factory=self._session_factory).get_email_credentials(dto.account_id)
                sync_label = creds.get("sync_label", "RPA-Developer-Application")
                if sync_label and hasattr(email_provider, "append_to_label"):
                    email_provider.append_to_label(msg_payload, sync_label)
                    logger.info("Dispatched outreach successfully appended to label '%s'", sync_label)
            except Exception as e:
                logger.warning("Could not append outbound message to label: %s", e)

        # 4. Phase 2: Database Post-commit
        with get_db_session(self._session_factory) as s:
            self.complete_outbox_transaction(
                session=s,
                send_token=send_token,
                send_result=send_result,
                cadence_days=dto.followup_cadence_days,
            )
            s.commit()

            # Reload fresh entities to return
            fresh_app = s.get(Application, app_id) if app_id else None
            fresh_comm = s.get(Communication, comm_id) if comm_id else None
            s.expunge_all()

        return send_result, fresh_app, fresh_comm, None

    def reconcile_in_flight_communications(
        self,
        provider: EmailProvider,
        max_age_seconds: int = 300,
    ) -> int:
        """Finds orphan SENDING communications older than max_age_seconds and reconciles their state."""
        threshold = datetime.now(timezone.utc) - timedelta(seconds=max_age_seconds)
        reconciled_count = 0

        with get_db_session(self._session_factory) as s:
            stuck_records = s.execute(
                select(Communication).where(
                    Communication.status == MessageStatus.SENDING.value,
                    Communication.created_at < threshold,
                )
            ).scalars().all()

            for comm in stuck_records:
                # Check if provider has dispatched this token
                cached_res = None
                if comm.send_token:
                    cached_res = provider.check_send_status(comm.send_token)
                
                if cached_res and cached_res.success:
                    self.complete_outbox_transaction(s, comm.send_token, cached_res, [4, 10, 17])
                else:
                    fail_res = SendResultDTO(
                        success=False,
                        send_token=comm.send_token or "",
                        status=MessageStatus.FAILED,
                        error_message="Message dispatch timed out in-flight and was not confirmed by provider",
                    )
                    self.complete_outbox_transaction(s, comm.send_token, fail_res)
                reconciled_count += 1

            s.commit()

        return reconciled_count
