"""Repository for Recruitment Pipeline entities (Interviews, Communications, FollowUps, Offers)."""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import utc_now
from app.db.models import Communication, FollowUp, Interview, Offer
from app.repositories.base import BaseRepository


class RecruitmentRepository(BaseRepository):
    """Data access operations for interviews, communications, follow-ups, and offers."""

    # --- Interviews ---

    def schedule_interview(
        self,
        application_id: int,
        round_name: str,
        scheduled_at: datetime,
        round_number: int = 1,
        interviewer: Optional[str] = None,
        mode: str = "VIRTUAL",
        meeting_link: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Interview:
        """Schedules a new interview round for an application."""
        interview = Interview(
            application_id=application_id,
            round_name=round_name.strip(),
            round_number=round_number,
            scheduled_at=scheduled_at,
            interviewer=interviewer.strip() if interviewer else None,
            mode=mode.strip().upper(),
            meeting_link=meeting_link.strip() if meeting_link else None,
            status="SCHEDULED",
            notes=notes,
        )
        self.session.add(interview)
        self.session.flush()
        return interview

    def list_interviews_by_application(self, application_id: int) -> List[Interview]:
        """Lists all interviews scheduled for an application."""
        stmt = (
            select(Interview)
            .where(Interview.application_id == application_id)
            .order_by(Interview.round_number.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def update_interview_status(
        self,
        interview_id: int,
        status: str,
        feedback: Optional[str] = None,
    ) -> Optional[Interview]:
        """Updates the status and optional feedback for an interview round."""
        interview = self.session.execute(
            select(Interview).where(Interview.id == interview_id)
        ).scalar_one_or_none()
        if not interview:
            return None
        interview.status = status.strip().upper()
        if feedback:
            interview.feedback = feedback
        if status.strip().upper() == "COMPLETED" and not interview.completed_at:
            interview.completed_at = utc_now()
        self.session.flush()
        return interview

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
        source: str = "manual",
        occurred_at: Optional[datetime] = None,
    ) -> Communication:
        """Logs an inbound or outbound communication event."""
        comm = Communication(
            application_id=application_id,
            contact_id=contact_id,
            type=type_.strip().upper(),
            direction=direction.strip().upper(),
            occurred_at=occurred_at or utc_now(),
            subject=subject.strip() if subject else None,
            summary=summary,
            notes=notes,
            source=source,
        )
        self.session.add(comm)
        self.session.flush()
        return comm

    def list_communications_by_application(self, application_id: int) -> List[Communication]:
        """Lists all communication logs associated with an application."""
        stmt = (
            select(Communication)
            .where(Communication.application_id == application_id)
            .order_by(Communication.occurred_at.desc())
        )
        return list(self.session.execute(stmt).scalars().all())

    # --- Follow-Ups ---

    def create_follow_up(
        self,
        due_at: datetime,
        application_id: Optional[int] = None,
        contact_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> FollowUp:
        """Creates a new follow-up reminder."""
        follow_up = FollowUp(
            application_id=application_id,
            contact_id=contact_id,
            due_at=due_at,
            status="PENDING",
            notes=notes,
        )
        self.session.add(follow_up)
        self.session.flush()
        return follow_up

    def list_pending_follow_ups(self) -> List[FollowUp]:
        """Lists all pending follow-up reminders ordered by due date."""
        stmt = (
            select(FollowUp)
            .where(FollowUp.status == "PENDING")
            .order_by(FollowUp.due_at.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def complete_follow_up(
        self,
        follow_up_id: int,
        status: str = "COMPLETED",
    ) -> Optional[FollowUp]:
        """Marks a follow-up task as completed or cancelled."""
        fu = self.session.execute(
            select(FollowUp).where(FollowUp.id == follow_up_id)
        ).scalar_one_or_none()
        if not fu:
            return None
        fu.status = status.strip().upper()
        fu.completed_at = utc_now()
        self.session.flush()
        return fu

    # --- Offers ---

    def record_offer(
        self,
        application_id: int,
        offered_ctc: Optional[int] = None,
        currency: str = "INR",
        joining_date: Optional[datetime] = None,
        status: str = "RECEIVED",
        notes: Optional[str] = None,
    ) -> Offer:
        """Records a job offer received for an application."""
        existing = self.session.execute(
            select(Offer).where(Offer.application_id == application_id)
        ).scalar_one_or_none()

        if existing:
            existing.offered_ctc = offered_ctc
            existing.currency = currency
            existing.joining_date = joining_date
            existing.status = status.strip().upper()
            if notes:
                existing.notes = notes
            self.session.flush()
            return existing

        offer = Offer(
            application_id=application_id,
            offered_ctc=offered_ctc,
            currency=currency,
            joining_date=joining_date,
            offer_date=utc_now(),
            status=status.strip().upper(),
            notes=notes,
        )
        self.session.add(offer)
        self.session.flush()
        return offer

    def get_offer_by_application(self, application_id: int) -> Optional[Offer]:
        """Fetches the offer record associated with an application."""
        return self.session.execute(
            select(Offer).where(Offer.application_id == application_id)
        ).scalar_one_or_none()

    def count_outbound_communications_between(self, start_dt: datetime, end_dt: datetime) -> int:
        """Counts outbound communications within the specified UTC timestamp interval."""
        stmt = select(func.count(Communication.id)).where(
            Communication.direction == "OUTBOUND",
            Communication.occurred_at >= start_dt,
            Communication.occurred_at <= end_dt,
        )
        return self.session.scalar(stmt) or 0

    def count_completed_followups_between(self, start_dt: datetime, end_dt: datetime) -> int:
        """Counts completed follow-ups within the specified UTC timestamp interval."""
        stmt = select(func.count(FollowUp.id)).where(
            FollowUp.status == "COMPLETED",
            FollowUp.completed_at >= start_dt,
            FollowUp.completed_at <= end_dt,
        )
        return self.session.scalar(stmt) or 0
