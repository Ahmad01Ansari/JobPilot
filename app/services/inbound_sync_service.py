"""Inbound Recruiter Email Synchronization and Two-Way Gmail Label Engine."""

from datetime import datetime, timezone
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models import (
    Application,
    Communication,
    Company,
    Contact,
    EmailSyncCheckpoint,
    Job,
    Resume,
    User,
)
from app.db.models.job import generate_job_fingerprint
from app.db.session import SessionLocal, get_db_session
from app.repositories.user_repository import UserRepository
from app.services.dto.outreach_dto import (
    ExpandedInboundEmailDTO,
    SyncCheckpointDTO,
)
from app.services.dto.outreach_enums import (
    CANONICAL_APPLICATION_METHOD_EMAIL,
    CANONICAL_PLATFORM_EMAIL,
    ConversationState,
    FollowUpStatus,
    MessageStatus,
)
from app.services.email.factory import get_email_provider
from app.services.email.provider import EmailProvider
from app.services.outreach_service import OutreachService
from app.services.secrets_service import SecretsService

logger = logging.getLogger(__name__)

PREFIX_REGEX = re.compile(r"^(re|fwd|fw)\s*:\s*", re.IGNORECASE)

PUBLIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "hotmail.com",
    "outlook.com", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "proton.me", "protonmail.com", "aol.com", "zoho.com", "gmx.com", "mail.com",
}


def normalize_subject(subject: Optional[str]) -> str:
    """Strips reply and forward prefixes and collapses whitespace."""
    if not subject:
        return ""
    cleaned = subject.strip()
    while True:
        sub = PREFIX_REGEX.sub("", cleaned).strip()
        if sub == cleaned:
            break
        cleaned = sub
    return " ".join(cleaned.lower().split())


def parse_application_subject(subject: Optional[str]) -> Tuple[str, Optional[str]]:
    """Extracts (job_title, company_name) from application email subjects.
    
    Examples:
        'Application for Junior Workflow Automation Developer' -> ('Junior Workflow Automation Developer', None)
        'Resume for RPA Developer Position at Infosys - Ahmad Raza' -> ('RPA Developer', 'Infosys')
    """
    if not subject:
        return "RPA Developer", None

    s = subject.strip()

    # 0. Check for repeated duplicate clauses (e.g. "Application for RPA Developer PositionApplication for RPA Developer Position")
    app_positions = [m.start() for m in re.finditer(r"(?:application|resume|applying)\s+for", s, re.IGNORECASE)]
    if len(app_positions) > 1 and app_positions[1] > 5:
        s = s[:app_positions[1]].strip()

    # 1. Candidate suffix after delimiter
    if " - " in s:
        s = s.split(" - ", 1)[0].strip()
    elif " | " in s:
        s = s.split(" | ", 1)[0].strip()

    # 2. Company after "at <Company>" or "@ <Company>"
    company = None
    at_match = re.search(r"\b(?:at|@)\s+([A-Za-z0-9&.,\s]+?)(?:$|\s*[-–|])", s, re.IGNORECASE)
    if at_match:
        company = at_match.group(1).strip()
        s = s[:at_match.start()].strip()

    # 3. Strip leading application phrases
    s = re.sub(
        r"^(?:job\s+)?(?:application|applying|resume)\s+(?:for|to|regarding|:)\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()

    # 4. Handle repeated phrases
    half_len = len(s) // 2
    if half_len > 5 and s[:half_len].lower() == s[half_len:].lower():
        s = s[:half_len].strip()
    s = re.sub(r"(?:application|resume)\s+for\s+", "", s, flags=re.IGNORECASE).strip()

    # 5. Strip trailing "Position", "Role", "Opening", "Job", "Opportunity"
    s = re.sub(r"\b(?:position|role|opening|job|opportunity)\b", "", s, flags=re.IGNORECASE).strip()

    title = " ".join(s.split()) or "RPA Developer"
    if company:
        company = " ".join(company.split())

    return title, company


def extract_recruiter_name_from_body(body_text: Optional[str]) -> Optional[str]:
    """Extracts recruiter name from greetings in body text."""
    if not body_text:
        return None
    for line in body_text.splitlines()[:6]:
        line = line.strip()
        if not line:
            continue
        m = re.match(
            r"^(?:Dear|Hi|Hello|Hey|Respected)\s+([A-Z][a-zA-Z\.\s]{1,30}?)(?:,|\n|\r|\s*-\s*|\s+Sir|\s+Ma'am)",
            line,
            re.IGNORECASE,
        )
        if m:
            candidate = m.group(1).strip().strip(".,")
            if candidate.lower() in ("hiring manager", "team", "all", "recruiter", "sir", "madam", "ma'am", "there"):
                return None
            return candidate
    return None


def extract_company_from_recipient_email(email_addr: Optional[str]) -> Optional[str]:
    """Extracts company name from corporate recipient email domain."""
    if not email_addr or "@" not in email_addr:
        return None
    domain = email_addr.split("@")[-1].strip().lower()
    if domain in PUBLIC_EMAIL_DOMAINS:
        return None
    comp = domain.split(".")[0]
    return comp.capitalize() if comp else None


IGNORED_SENDER_PATTERNS = (
    "donotreply@",
    "do-not-reply@",
    "no-reply@",
    "noreply@",
    "jobalert@",
    "jobalerts@",
    "jobalert.indeed.com",
    "alert@indeed.com",
    "messages-noreply@linkedin.com",
    "invitations@linkedin.com",
    "jobalerts-noreply@linkedin.com",
    "mailer-daemon@",
    "postmaster@",
    "notifications@",
    "digest-noreply@",
    "newsletters@",
    "marketing@",
    "promotions@",
    "alert@naukri.com",
    "notifications@naukri.com",
)


class InboundSyncService:
    """Synchronizes Gmail application labels and INBOX, ingesting applications and recruiter replies."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        outreach_service: Optional[OutreachService] = None,
        provider: Optional[EmailProvider] = None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._outreach_service = outreach_service or OutreachService(session_factory=self._session_factory)
        self._provider = provider

    def match_inbound_to_application(
        self,
        session: Session,
        inbound: ExpandedInboundEmailDTO,
    ) -> Tuple[Optional[int], Optional[str]]:
        """Matches an inbound email to an existing application using a 3-tier precedence."""
        sender_email = (inbound.from_address or "").strip().lower()

        # Reject automated newsletters, bounce notifications, and job alert emails
        if any(pat in sender_email for pat in IGNORED_SENDER_PATTERNS):
            return None, None

        # Tier 1: Header Matching (In-Reply-To / References)
        header_refs = []
        if inbound.in_reply_to:
            header_refs.append(inbound.in_reply_to.strip("<> "))
        if inbound.references:
            for ref in inbound.references.split():
                header_refs.append(ref.strip("<> "))

        for ref_id in header_refs:
            if not ref_id:
                continue
            comm = session.execute(
                select(Communication).where(
                    (Communication.provider_message_id == ref_id)
                    | (Communication.provider_message_id == f"<{ref_id}>")
                    | (Communication.send_token == ref_id)
                )
            ).scalar_one_or_none()
            if comm and comm.application_id:
                return comm.application_id, "HEADER_THREAD"

        # Tier 2: Recruiter Sender Email & Active Application Window
        if sender_email:
            active_statuses = ("SUBMITTED", "UNDER_REVIEW", "RECRUITER_CONTACTED", "INTERVIEW")
            comm_match = session.execute(
                select(Communication)
                .join(Communication.application)
                .where(
                    Communication.recipient_email == sender_email,
                    Application.status.in_(active_statuses),
                )
                .order_by(desc(Communication.occurred_at))
            ).scalars().first()

            if comm_match and comm_match.application_id:
                return comm_match.application_id, "RECRUITER_EMAIL"

            # Check Contact email directly
            contact_match = session.execute(
                select(Contact).where(Contact.email == sender_email)
            ).scalars().first()
            if contact_match:
                app_match = session.execute(
                    select(Application).where(
                        Application.contact_id == contact_match.id,
                        Application.status.in_(active_statuses),
                    ).order_by(desc(Application.created_at))
                ).scalars().first()
                if app_match:
                    return app_match.id, "RECRUITER_EMAIL"

        # Tier 3: Normalized Subject Tokens (Requires Company Name Match)
        norm_subj = normalize_subject(inbound.subject)
        if norm_subj and len(norm_subj) > 4:
            recent_apps = session.execute(
                select(Application)
                .join(Application.job)
                .where(Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL)
                .order_by(desc(Application.created_at))
                .limit(50)
            ).scalars().all()

            for app in recent_apps:
                comp_name = (
                    app.job.company.name if (app.job and app.job.company) else (app.job.company_raw if app.job else "")
                ).lower()
                if comp_name and len(comp_name) >= 3 and comp_name in norm_subj:
                    return app.id, "SUBJECT_TOKENS"

        return None, None

    def ingest_sent_application(
        self,
        session: Session,
        msg: ExpandedInboundEmailDTO,
        account_id: str,
        sync_label: str,
        user_id: int,
    ) -> Optional[int]:
        """Ingests an application email sent directly by the user from Gmail under the sync label."""
        if not msg.to_addresses:
            return None

        recruiter_email = msg.to_addresses[0].strip().lower()
        if not recruiter_email or "@" not in recruiter_email:
            return None

        # Parse position title and company name
        title, comp_name = parse_application_subject(msg.subject)
        if not comp_name:
            comp_name = extract_company_from_recipient_email(recruiter_email)
        if not comp_name:
            # Check for body mentions
            if "at your organization" in (msg.body_text or "").lower():
                comp_name = "Direct Outreach"
            else:
                comp_name = "Direct Outreach"

        recruiter_name = extract_recruiter_name_from_body(msg.body_text)
        if not recruiter_name:
            recruiter_name = recruiter_email.split("@")[0].replace(".", " ").title()

        # 1. Resolve or create Company
        company_id = None
        norm_comp = comp_name.lower()
        existing_comp = session.execute(
            select(Company).where(Company.normalized_name == norm_comp)
        ).scalar_one_or_none()
        if existing_comp:
            company_id = existing_comp.id
        else:
            new_comp = Company(name=comp_name, normalized_name=norm_comp)
            session.add(new_comp)
            session.flush()
            company_id = new_comp.id

        # 2. Resolve or create Contact
        contact = session.execute(
            select(Contact).where(Contact.email == recruiter_email)
        ).scalar_one_or_none()
        if not contact:
            contact = Contact(
                name=recruiter_name,
                email=recruiter_email,
                designation="Recruiter / Hiring Manager",
                company_id=company_id,
            )
            session.add(contact)
            session.flush()

        # 3. Check for existing Application matching this contact and job title
        app = session.execute(
            select(Application)
            .join(Application.job)
            .where(
                Application.contact_id == contact.id,
                Application.application_type == CANONICAL_APPLICATION_METHOD_EMAIL,
            )
        ).scalars().first()

        if not app:
            # Create Job
            src_url = f"email://{recruiter_email}"
            fp = generate_job_fingerprint(
                platform=CANONICAL_PLATFORM_EMAIL,
                company=comp_name,
                title=title,
                source_url=src_url,
            )
            existing_job = session.execute(select(Job).where(Job.job_fingerprint == fp)).scalar_one_or_none()
            if existing_job:
                job = existing_job
            else:
                job = Job(
                    title=title,
                    company_raw=comp_name,
                    company_id=company_id,
                    platform=CANONICAL_PLATFORM_EMAIL,
                    source_url=src_url,
                    job_fingerprint=fp,
                )
                session.add(job)
                session.flush()

            # Attempt to associate matching resume from attachments or default
            resume_match = None
            if msg.attachments_metadata:
                att_names = [a.get("filename", "").lower() for a in msg.attachments_metadata]
                all_resumes = session.execute(select(Resume).where(Resume.user_id == user_id)).scalars().all()
                for r in all_resumes:
                    if any(r.name.lower() in an or "ahmad" in an for an in att_names):
                        resume_match = r
                        break
            if not resume_match:
                resume_match = session.execute(
                    select(Resume).where(Resume.user_id == user_id, Resume.is_default == True)
                ).scalar_one_or_none()

            app = Application(
                job_id=job.id,
                contact_id=contact.id,
                user_id=user_id,
                resume_id=resume_match.id if resume_match else None,
                status="SUBMITTED",
                application_type=CANONICAL_APPLICATION_METHOD_EMAIL,
                applied_at=msg.received_at or utc_now(),
                created_at=msg.received_at or utc_now(),
                notes=f"Synced from Gmail label '{sync_label}'",
            )
            session.add(app)
            session.flush()

        # 4. Create Outbound Communication
        outbound_comm = Communication(
            application_id=app.id,
            contact_id=contact.id,
            type="EMAIL",
            direction="OUTBOUND",
            status=MessageStatus.SENT.value,
            account_id=account_id,
            provider_message_id=msg.message_id,
            sender_email=msg.from_address,
            recipient_email=recruiter_email,
            occurred_at=msg.received_at or utc_now(),
            subject=msg.subject,
            body_snippet=(msg.body_text or "")[:250],
            summary=msg.body_text,
            source=f"gmail_label:{sync_label}",
        )
        session.add(outbound_comm)
        session.commit()
        return app.id

    def sync_messages_from_folder(
        self,
        session: Session,
        provider: EmailProvider,
        account_id: str,
        folder_name: str,
        user_email: str,
        user_id: int,
    ) -> Tuple[int, int, int]:
        """Fetches and synchronizes messages from a specific folder/label.
        
        Returns:
            Tuple of (ingested_applications, matched_replies, unmatched_count)
        """
        checkpoint_key = f"{account_id}:{folder_name}"
        checkpoint = session.execute(
            select(EmailSyncCheckpoint).where(EmailSyncCheckpoint.account_id == checkpoint_key)
        ).scalar_one_or_none()

        ckpt_dto = SyncCheckpointDTO(
            account_id=checkpoint_key,
            last_sync_at=checkpoint.last_sync_at if checkpoint else None,
            last_history_id=checkpoint.last_history_id if checkpoint else None,
            cursor_token=checkpoint.cursor_token if checkpoint else None,
        )

        try:
            msgs = provider.fetch_inbound(ckpt_dto, folder=folder_name)
        except Exception as e:
            logger.error("Error fetching messages from folder '%s': %s", folder_name, e)
            return 0, 0, 0

        ingested_apps = 0
        matched_replies = 0
        unmatched_count = 0
        latest_timestamp = None

        user_clean = user_email.strip().lower()

        for msg in msgs:
            if not latest_timestamp or (msg.received_at and msg.received_at > latest_timestamp):
                latest_timestamp = msg.received_at

            # Deduplication: check if message ID already recorded
            already_exists = session.execute(
                select(Communication).where(Communication.provider_message_id == msg.message_id)
            ).scalar_one_or_none()
            if already_exists:
                continue

            msg_sender = (msg.from_address or "").strip().lower()
            is_sent_by_user = (user_clean in msg_sender or msg_sender in user_clean)

            if is_sent_by_user:
                # Ingest as outbound job application
                app_id = self.ingest_sent_application(
                    session=session,
                    msg=msg,
                    account_id=account_id,
                    sync_label=folder_name,
                    user_id=user_id,
                )
                if app_id:
                    ingested_apps += 1
                else:
                    unmatched_count += 1
            else:
                # Recruiter response: match against existing applications
                app_id, tier = self.match_inbound_to_application(session, msg)
                if app_id:
                    app = session.get(Application, app_id)
                    inbound_comm = Communication(
                        application_id=app_id,
                        contact_id=app.contact_id if app else None,
                        type="EMAIL",
                        direction="INBOUND",
                        status=MessageStatus.SENT.value,
                        account_id=account_id,
                        provider_message_id=msg.message_id,
                        sender_email=msg.from_address,
                        recipient_email=msg.to_addresses[0] if msg.to_addresses else None,
                        occurred_at=msg.received_at or utc_now(),
                        subject=msg.subject,
                        body_snippet=(msg.body_text or "")[:250],
                        summary=msg.body_text,
                        source=f"sync:{folder_name}",
                    )
                    session.add(inbound_comm)

                    if app and app.status in ("SUBMITTED", "UNDER_REVIEW"):
                        app.status = "RECRUITER_CONTACTED"

                    session.commit()

                    # Critical Invariant: Automatically pause follow-ups upon recruiter reply
                    self._outreach_service.pause_followups(
                        application_id=app_id,
                        reason=f"Recruiter reply received: {msg.subject} (Tier: {tier})",
                    )
                    matched_replies += 1
                else:
                    unmatched_count += 1

        # Update checkpoint for this folder
        if latest_timestamp:
            if not checkpoint:
                checkpoint = EmailSyncCheckpoint(
                    account_id=checkpoint_key,
                    last_sync_at=latest_timestamp,
                )
                session.add(checkpoint)
            else:
                checkpoint.last_sync_at = latest_timestamp
            session.commit()

        return ingested_apps, matched_replies, unmatched_count

    def sync_mailbox(
        self,
        account_id: str = "default",
        custom_provider: Optional[EmailProvider] = None,
        sync_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Performs two-way synchronization across both the Gmail Application Label and INBOX."""
        provider = custom_provider or self._provider or get_email_provider(account_id)

        sec_svc = SecretsService(session_factory=self._session_factory)
        creds = sec_svc.get_email_credentials(account_id)
        target_label = sync_label or creds.get("sync_label") or "RPA-Developer-Application"
        sender_email = creds.get("user") or "candidate@jobpilot"

        with get_db_session(self._session_factory) as s:
            user_repo = UserRepository(s)
            u = user_repo.get_primary_user()
            user_id = u.id if u else 1
            if u and u.email:
                sender_email = u.email

            total_ingested = 0
            total_matched = 0
            total_unmatched = 0

            # 1. Sync custom Gmail Application Label
            if target_label:
                ingested, matched, unmatched = self.sync_messages_from_folder(
                    session=s,
                    provider=provider,
                    account_id=account_id,
                    folder_name=target_label,
                    user_email=sender_email,
                    user_id=user_id,
                )
                total_ingested += ingested
                total_matched += matched
                total_unmatched += unmatched

            # 2. Sync INBOX for incoming recruiter replies
            _, inbox_matched, inbox_unmatched = self.sync_messages_from_folder(
                session=s,
                provider=provider,
                account_id=account_id,
                folder_name="INBOX",
                user_email=sender_email,
                user_id=user_id,
            )
            total_matched += inbox_matched
            total_unmatched += inbox_unmatched

        return {
            "success": True,
            "ingested_applications": total_ingested,
            "matched_count": total_matched,
            "unmatched_count": total_unmatched,
            "synced_count": total_ingested + total_matched,
            "sync_label": target_label,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    def sync_inbound(self, *args, **kwargs) -> Dict[str, Any]:
        """Backward-compatible alias for sync_mailbox."""
        return self.sync_mailbox(*args, **kwargs)
