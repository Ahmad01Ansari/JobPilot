"""Recruitment pipeline service for interviews, communications, follow-ups, and offers.

Encapsulates candidate recruitment interactions, multi-round scheduling,
deterministic contact management, audit history, and derived pipeline metrics.
"""

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, sessionmaker

from app.db.base import utc_now
from app.db.models import Application, Communication, Contact, FollowUp, Interview, Job, Offer
from app.db.session import SessionLocal, get_db_session
from app.repositories.contact_repository import ContactRepository
from app.repositories.recruitment_repository import RecruitmentRepository
from app.repositories.validators import normalize_company_name


VALID_INTERVIEW_ROUNDS = {"HR", "TECHNICAL", "CODING", "MANAGERIAL", "CLIENT", "FINAL", "OTHER"}
VALID_INTERVIEW_STATUSES = {"SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"}
VALID_INTERVIEW_MODES = {"VIRTUAL", "PHONE", "IN_PERSON"}

VALID_COMMUNICATION_TYPES = {"EMAIL", "PHONE", "LINKEDIN", "MESSAGE", "OTHER"}
VALID_COMMUNICATION_DIRECTIONS = {"INBOUND", "OUTBOUND"}

VALID_FOLLOWUP_STATUSES = {"PENDING", "COMPLETED", "CANCELLED"}
VALID_OFFER_STATUSES = {"RECEIVED", "ACCEPTED", "DECLINED", "EXPIRED", "WITHDRAWN"}


class RecruitmentService:
    """Service layer for recruitment pipeline operations."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    # --- Contacts ---

    def get_or_create_contact(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        company_id: Optional[int] = None,
        designation: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Contact:
        """Finds existing contact by email or (normalized name + company) or creates new."""
        c_name = str(name or "").strip()
        c_email = str(email or "").strip().lower() if email else None

        with get_db_session(self._session_factory) as session:
            # 1. Look up by email
            if c_email:
                stmt = select(Contact).where(Contact.email == c_email)
                existing = session.execute(stmt).scalar_one_or_none()
                if existing:
                    return existing

            # 2. Look up by name and company
            stmt = select(Contact).where(func.lower(Contact.name) == c_name.lower())
            if company_id:
                stmt = stmt.where(Contact.company_id == company_id)
            existing = session.execute(stmt).scalar_one_or_none()
            if existing:
                return existing

            # 3. Create new contact
            repo = ContactRepository(session)
            contact = repo.create_contact(
                name=c_name,
                company_id=company_id,
                designation=designation,
                email=c_email,
                phone=phone,
                notes=notes,
            )
            session.commit()
            return contact

    # --- Interviews ---

    def schedule_interview(
        self,
        application_id: int,
        round_name: str,
        scheduled_at: datetime,
        round_number: int = 1,
        round_type: str = "TECHNICAL",
        interviewer_name: Optional[str] = None,
        interviewer_email: Optional[str] = None,
        mode: str = "VIRTUAL",
        meeting_link: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Tuple[Optional[Interview], Optional[str]]:
        """Schedules a new interview round for an application."""
        mode_clean = mode.strip().upper()
        if mode_clean not in VALID_INTERVIEW_MODES:
            return None, f"Invalid interview mode '{mode}'. Allowed: {sorted(list(VALID_INTERVIEW_MODES))}"

        # URL validation for virtual interviews
        m_link = meeting_link.strip() if meeting_link else None
        if mode_clean == "VIRTUAL" and m_link:
            if not re.match(r"^https?://", m_link, re.IGNORECASE):
                return None, "Virtual meeting link must be a valid http:// or https:// URL."

        try:
            with get_db_session(self._session_factory) as session:
                app = session.execute(
                    select(Application).where(Application.id == application_id)
                ).scalar_one_or_none()
                if not app:
                    return None, f"Application with ID {application_id} not found."

                # Associate interviewer contact if details provided
                if interviewer_name:
                    job = session.execute(
                        select(Job).where(Job.id == app.job_id)
                    ).scalar_one_or_none()
                    company_id = job.company_id if job else None
                    self.get_or_create_contact(
                        name=interviewer_name,
                        email=interviewer_email,
                        company_id=company_id,
                    )

                repo = RecruitmentRepository(session)
                interview = repo.schedule_interview(
                    application_id=application_id,
                    round_name=round_name.strip(),
                    round_number=round_number,
                    scheduled_at=scheduled_at,
                    interviewer=interviewer_name.strip() if interviewer_name else None,
                    mode=mode_clean,
                    meeting_link=m_link,
                    notes=notes,
                )
                session.commit()
                return interview, None
        except Exception as e:
            return None, f"Error scheduling interview: {e}"

    def reschedule_interview(
        self,
        interview_id: int,
        new_scheduled_at: datetime,
        reason: Optional[str] = None,
    ) -> Tuple[Optional[Interview], Optional[str]]:
        """Reschedules an interview, retaining SCHEDULED status while recording reschedule notes."""
        try:
            with get_db_session(self._session_factory) as session:
                interview = session.execute(
                    select(Interview).where(Interview.id == interview_id)
                ).scalar_one_or_none()
                if not interview:
                    return None, f"Interview {interview_id} not found."

                prev_time_str = interview.scheduled_at.strftime("%Y-%m-%d %H:%M") if interview.scheduled_at else "None"
                interview.scheduled_at = new_scheduled_at
                interview.status = "SCHEDULED"

                note_addition = f"[Rescheduled from {prev_time_str}. Reason: {reason or 'Candidate/Recruiter request'}]"
                interview.notes = f"{interview.notes}\n{note_addition}" if interview.notes else note_addition

                session.commit()
                return interview, None
        except Exception as e:
            return None, f"Error rescheduling interview: {e}"

    def update_interview_status(
        self,
        interview_id: int,
        status: str,
        feedback: Optional[str] = None,
    ) -> Tuple[Optional[Interview], Optional[str]]:
        """Updates interview status and records optional evaluation feedback."""
        st_clean = status.strip().upper()
        if st_clean not in VALID_INTERVIEW_STATUSES:
            return None, f"Invalid interview status '{status}'. Allowed: {sorted(list(VALID_INTERVIEW_STATUSES))}"

        try:
            with get_db_session(self._session_factory) as session:
                repo = RecruitmentRepository(session)
                interview = repo.update_interview_status(
                    interview_id=interview_id,
                    status=st_clean,
                    feedback=feedback,
                )
                if not interview:
                    return None, f"Interview {interview_id} not found."
                session.commit()
                return interview, None
        except Exception as e:
            return None, f"Error updating interview status: {e}"

    def list_interviews(
        self,
        application_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Interview]:
        """Lists interviews with eager loaded application and job records."""
        with get_db_session(self._session_factory) as session:
            stmt = (
                select(Interview)
                .options(
                    joinedload(Interview.application).joinedload(Application.job)
                )
            )
            if application_id:
                stmt = stmt.where(Interview.application_id == application_id)
            if status and status.strip().upper() not in ["ALL", ""]:
                stmt = stmt.where(Interview.status == status.strip().upper())

            stmt = stmt.order_by(Interview.scheduled_at.desc()).limit(limit).offset(offset)
            return list(session.execute(stmt).scalars().all())

    # --- Communications ---

    def log_communication(
        self,
        type_: str,
        direction: str,
        application_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        subject: Optional[str] = None,
        summary: Optional[str] = None,
        notes: Optional[str] = None,
        occurred_at: Optional[datetime] = None,
    ) -> Tuple[Optional[Communication], Optional[str]]:
        """Logs an inbound or outbound communication event."""
        t_clean = type_.strip().upper()
        d_clean = direction.strip().upper()

        if t_clean not in VALID_COMMUNICATION_TYPES:
            return None, f"Invalid communication type '{type_}'. Allowed: {sorted(list(VALID_COMMUNICATION_TYPES))}"
        if d_clean not in VALID_COMMUNICATION_DIRECTIONS:
            return None, f"Invalid communication direction '{direction}'. Allowed: {sorted(list(VALID_COMMUNICATION_DIRECTIONS))}"

        try:
            with get_db_session(self._session_factory) as session:
                repo = RecruitmentRepository(session)
                comm = repo.log_communication(
                    type_=t_clean,
                    direction=d_clean,
                    application_id=application_id,
                    contact_id=contact_id,
                    subject=subject,
                    summary=summary,
                    notes=notes,
                    occurred_at=occurred_at,
                )
                session.commit()
                return comm, None
        except Exception as e:
            return None, f"Error logging communication: {e}"

    def list_communications(
        self,
        application_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[Communication]:
        """Lists logged communications."""
        with get_db_session(self._session_factory) as session:
            stmt = select(Communication)
            if application_id:
                stmt = stmt.where(Communication.application_id == application_id)
            stmt = stmt.order_by(Communication.occurred_at.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())

    # --- Follow-Ups ---

    def create_follow_up(
        self,
        due_at: datetime,
        application_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> Tuple[Optional[FollowUp], Optional[str]]:
        """Creates a follow-up reminder."""
        try:
            with get_db_session(self._session_factory) as session:
                repo = RecruitmentRepository(session)
                fu = repo.create_follow_up(
                    due_at=due_at,
                    application_id=application_id,
                    contact_id=contact_id,
                    notes=notes,
                )
                session.commit()
                return fu, None
        except Exception as e:
            return None, f"Error creating follow-up: {e}"

    def complete_follow_up(
        self,
        follow_up_id: int,
        status: str = "COMPLETED",
    ) -> Tuple[Optional[FollowUp], Optional[str]]:
        """Marks a follow-up as COMPLETED or CANCELLED, preserving the record."""
        st_clean = status.strip().upper()
        if st_clean not in {"COMPLETED", "CANCELLED"}:
            return None, "Follow-up terminal status must be COMPLETED or CANCELLED."

        try:
            with get_db_session(self._session_factory) as session:
                repo = RecruitmentRepository(session)
                fu = repo.complete_follow_up(follow_up_id, status=st_clean)
                if not fu:
                    return None, f"Follow-up {follow_up_id} not found."
                session.commit()
                return fu, None
        except Exception as e:
            return None, f"Error completing follow-up: {e}"

    def reschedule_follow_up(
        self,
        follow_up_id: int,
        new_due_at: datetime,
        notes: Optional[str] = None,
    ) -> Tuple[Optional[FollowUp], Optional[str]]:
        """Reschedules a pending follow-up reminder."""
        try:
            with get_db_session(self._session_factory) as session:
                fu = session.execute(
                    select(FollowUp).where(FollowUp.id == follow_up_id)
                ).scalar_one_or_none()
                if not fu:
                    return None, f"Follow-up {follow_up_id} not found."
                fu.due_at = new_due_at
                fu.status = "PENDING"
                if notes:
                    fu.notes = f"{fu.notes}\n[Rescheduled: {notes}]" if fu.notes else notes
                session.commit()
                return fu, None
        except Exception as e:
            return None, f"Error rescheduling follow-up: {e}"

    def list_follow_ups(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[FollowUp]:
        """Lists follow-up reminders with eager-loaded application, job, and contact."""
        with get_db_session(self._session_factory) as session:
            stmt = (
                select(FollowUp)
                .options(
                    joinedload(FollowUp.application).joinedload(Application.job),
                    joinedload(FollowUp.contact),
                )
            )
            if status and status.strip().upper() not in ["ALL", ""]:
                stmt = stmt.where(FollowUp.status == status.strip().upper())

            stmt = stmt.order_by(FollowUp.due_at.asc()).limit(limit).offset(offset)
            return list(session.execute(stmt).scalars().all())

    # --- Offers ---

    def record_offer(
        self,
        application_id: int,
        offered_ctc: Optional[int] = None,
        currency: str = "INR",
        joining_date: Optional[datetime] = None,
        status: str = "RECEIVED",
        notes: Optional[str] = None,
    ) -> Tuple[Optional[Offer], Optional[str]]:
        """Records an offer received for an application."""
        st_clean = status.strip().upper()
        if st_clean not in VALID_OFFER_STATUSES:
            return None, f"Invalid offer status '{status}'. Allowed: {sorted(list(VALID_OFFER_STATUSES))}"

        try:
            with get_db_session(self._session_factory) as session:
                repo = RecruitmentRepository(session)
                offer = repo.record_offer(
                    application_id=application_id,
                    offered_ctc=offered_ctc,
                    currency=currency,
                    joining_date=joining_date,
                    status=st_clean,
                    notes=notes,
                )
                session.commit()
                return offer, None
        except Exception as e:
            return None, f"Error recording offer: {e}"

    # --- Metrics ---

    def get_metrics(self) -> Dict[str, Any]:
        """Computes derived recruitment metrics across interviews, follow-ups, and offers."""
        now = utc_now()
        with get_db_session(self._session_factory) as session:
            # Upcoming interviews: SCHEDULED and scheduled_at >= now
            upcoming = session.scalar(
                select(func.count(Interview.id)).where(
                    Interview.status == "SCHEDULED",
                    Interview.scheduled_at >= now,
                )
            ) or 0

            # Pending follow-ups
            pending_fu = session.scalar(
                select(func.count(FollowUp.id)).where(FollowUp.status == "PENDING")
            ) or 0

            # Overdue follow-ups (derived: PENDING and due_at < now)
            overdue_fu = session.scalar(
                select(func.count(FollowUp.id)).where(
                    FollowUp.status == "PENDING",
                    FollowUp.due_at < now,
                )
            ) or 0

            # Offers received
            offers = session.scalar(
                select(func.count(Offer.id)).where(Offer.status == "RECEIVED")
            ) or 0

            return {
                "upcoming_interviews": upcoming,
                "pending_follow_ups": pending_fu,
                "overdue_follow_ups": overdue_fu,
                "offers_received": offers,
            }
