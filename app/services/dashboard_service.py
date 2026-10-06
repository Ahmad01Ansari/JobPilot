"""Dashboard metrics and recent activity feed service.

Aggregates overall application pipeline counts, platform breakdowns,
and provides a chronological timeline feed of system activity events.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now

logger = logging.getLogger(__name__)
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    Communication,
    FollowUp,
    Interview,
    Job,
    JobEvaluation,
    Offer,
)
from app.db.session import SessionLocal, get_db_session
from app.services.dto.dashboard_dto import (
    DailyProgressDTO,
    DashboardSnapshotDTO,
    NextBestActionDTO,
    PlatformMetricDTO,
    ReadinessSummaryDTO,
    SearchPerformanceDTO,
    TodaysHuntItemDTO,
    TopOpportunityDTO,
)
from app.utils_time import format_local_datetime, get_local_day_utc_range


@dataclass
class ActivityEvent:
    """Represents a unified chronological event in the dashboard activity stream."""

    event_type: str  # JOB_DISCOVERED, APPLICATION_SUBMITTED, STATUS_CHANGED, INTERVIEW_SCHEDULED, OFFER_RECEIVED
    timestamp: datetime
    platform: Optional[str]
    title: str
    description: str
    status: Optional[str] = None
    entity_id: Optional[int] = None


class DashboardService:
    """Service layer for mission-control dashboard data aggregation."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        job_service=None,
        recruitment_service=None,
        outreach_service=None,
        application_service=None,
        profile_service=None,
        resume_service=None,
        qna_service=None,
        platform_service=None,
        analytics_service=None,
    ):
        self._session_factory = session_factory or SessionLocal
        self._job_service = job_service
        self._recruitment_service = recruitment_service
        self._outreach_service = outreach_service
        self._application_service = application_service
        self._profile_service = profile_service
        self._resume_service = resume_service
        self._qna_service = qna_service
        self._platform_service = platform_service
        self._analytics_service = analytics_service

    @property
    def analytics_service(self):
        if self._analytics_service is None:
            from app.services.analytics_service import AnalyticsService
            self._analytics_service = AnalyticsService(session_factory=self._session_factory)
        return self._analytics_service

    @property
    def job_service(self):
        if self._job_service is None:
            from app.services.job_service import JobService
            self._job_service = JobService(session_factory=self._session_factory)
        return self._job_service

    @property
    def recruitment_service(self):
        if self._recruitment_service is None:
            from app.services.recruitment_service import RecruitmentService
            self._recruitment_service = RecruitmentService(session_factory=self._session_factory)
        return self._recruitment_service

    @property
    def outreach_service(self):
        if self._outreach_service is None:
            from app.services.outreach_service import OutreachService
            self._outreach_service = OutreachService(session_factory=self._session_factory)
        return self._outreach_service

    @property
    def application_service(self):
        if self._application_service is None:
            from app.services.application_service import ApplicationService
            self._application_service = ApplicationService(session_factory=self._session_factory)
        return self._application_service

    @property
    def profile_service(self):
        if self._profile_service is None:
            from app.services.profile_service import ProfileService
            self._profile_service = ProfileService(session_factory=self._session_factory)
        return self._profile_service

    @property
    def resume_service(self):
        if self._resume_service is None:
            from app.services.resume_service import ResumeService
            self._resume_service = ResumeService(session_factory=self._session_factory)
        return self._resume_service

    @property
    def qna_service(self):
        if self._qna_service is None:
            from app.services.qna_service import QnAService
            self._qna_service = QnAService(session_factory=self._session_factory)
        return self._qna_service

    @property
    def platform_service(self):
        if self._platform_service is None:
            from app.services.platform_service import PlatformService
            self._platform_service = PlatformService(session_factory=self._session_factory)
        return self._platform_service


    def get_summary_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Calculates current and historical summary metrics."""
        with get_db_session(self._session_factory) as session:
            # 1. Total Jobs Discovered
            q_jobs = select(func.count(Job.id))
            if start_date:
                q_jobs = q_jobs.where(Job.created_at >= start_date)
            if end_date:
                q_jobs = q_jobs.where(Job.created_at <= end_date)
            total_jobs = session.scalar(q_jobs) or 0

            # 2. Total Applications in SUBMITTED status
            q_submitted = select(func.count(Application.id)).where(
                Application.status == "SUBMITTED"
            )
            if start_date:
                q_submitted = q_submitted.where(Application.created_at >= start_date)
            if end_date:
                q_submitted = q_submitted.where(Application.created_at <= end_date)
            submitted_apps = session.scalar(q_submitted) or 0

            # 3. Under Review (status == 'UNDER_REVIEW')
            q_review = select(func.count(Application.id)).where(
                Application.status == "UNDER_REVIEW"
            )
            if start_date:
                q_review = q_review.where(Application.created_at >= start_date)
            if end_date:
                q_review = q_review.where(Application.created_at <= end_date)
            under_review_count = session.scalar(q_review) or 0

            # 4. Interviews / Shortlisted / Assessment
            interview_statuses = ["SHORTLISTED", "RECRUITER_CONTACTED", "ASSESSMENT", "INTERVIEW"]
            q_interviews = select(func.count(func.distinct(Application.id))).where(
                Application.status.in_(interview_statuses)
            )
            if start_date:
                q_interviews = q_interviews.where(Application.created_at >= start_date)
            if end_date:
                q_interviews = q_interviews.where(Application.created_at <= end_date)
            interviews_count = session.scalar(q_interviews) or 0

            q_iv_table = select(func.count(func.distinct(Interview.application_id)))
            iv_table_count = session.scalar(q_iv_table) or 0
            interviews_count = max(interviews_count, iv_table_count)

            # 5. Offers (status == 'OFFER' or in Offer table)
            q_offers = select(func.count(Application.id)).where(
                Application.status == "OFFER"
            )
            if start_date:
                q_offers = q_offers.where(Application.created_at >= start_date)
            if end_date:
                q_offers = q_offers.where(Application.created_at <= end_date)
            offers_count = session.scalar(q_offers) or 0
            q_off_table = select(func.count(func.distinct(Offer.application_id)))
            off_table_count = session.scalar(q_off_table) or 0
            offers_count = max(offers_count, off_table_count)

            # 6. Withdrawn (status == 'WITHDRAWN')
            q_withdrawn = select(func.count(Application.id)).where(
                Application.status == "WITHDRAWN"
            )
            if start_date:
                q_withdrawn = q_withdrawn.where(Application.created_at >= start_date)
            if end_date:
                q_withdrawn = q_withdrawn.where(Application.created_at <= end_date)
            withdrawn_count = session.scalar(q_withdrawn) or 0

            # 7. Rejected (status == 'REJECTED')
            q_rejected = select(func.count(Application.id)).where(
                Application.status == "REJECTED"
            )
            if start_date:
                q_rejected = q_rejected.where(Application.created_at >= start_date)
            if end_date:
                q_rejected = q_rejected.where(Application.created_at <= end_date)
            rejections_count = session.scalar(q_rejected) or 0

            # 8. In Active Pipeline (submitted + under review + interviewing)
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

    def get_pipeline_funnel(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Convenience accessor for overall pipeline funnel progression."""
        return self.get_summary_metrics(start_date=start_date, end_date=end_date)

    def get_platform_breakdown(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, int]]:
        """Calculates jobs and application metrics grouped by platform."""
        platforms = ["linkedin", "naukri", "indeed", "foundit", "glassdoor", "manual"]
        breakdown: Dict[str, Dict[str, int]] = {}

        APPLIED_STATUSES = [
            "SUBMITTED",
            "UNDER_REVIEW",
            "SHORTLISTED",
            "RECRUITER_CONTACTED",
            "ASSESSMENT",
            "INTERVIEW",
            "OFFER",
            "WITHDRAWN",
            "REJECTED",
        ]

        with get_db_session(self._session_factory) as session:
            for plat in platforms:
                # Jobs on this platform
                q_j = select(func.count(Job.id)).where(Job.platform == plat)
                if start_date:
                    q_j = q_j.where(Job.created_at >= start_date)
                if end_date:
                    q_j = q_j.where(Job.created_at <= end_date)
                jobs_count = session.scalar(q_j) or 0

                # Applications submitted for jobs on this platform
                q_a = (
                    select(func.count(func.distinct(Application.id)))
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat, Application.status.in_(APPLIED_STATUSES))
                )
                if start_date:
                    q_a = q_a.where(Application.created_at >= start_date)
                if end_date:
                    q_a = q_a.where(Application.created_at <= end_date)
                apps_count = session.scalar(q_a) or 0

                # Interviews for jobs on this platform
                q_i = (
                    select(func.count(func.distinct(Interview.application_id)))
                    .join(Application, Interview.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat)
                )
                if start_date:
                    q_i = q_i.where(Interview.created_at >= start_date)
                if end_date:
                    q_i = q_i.where(Interview.created_at <= end_date)
                interviews_count = session.scalar(q_i) or 0

                # Offers for jobs on this platform
                q_o = (
                    select(func.count(func.distinct(Offer.application_id)))
                    .join(Application, Offer.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat)
                )
                if start_date:
                    q_o = q_o.where(Offer.created_at >= start_date)
                if end_date:
                    q_o = q_o.where(Offer.created_at <= end_date)
                offers_count = session.scalar(q_o) or 0

                breakdown[plat] = {
                    "jobs": jobs_count,
                    "applications": apps_count,
                    "interviews": interviews_count,
                    "offers": offers_count,
                }

        return breakdown

    def get_recent_activity(
        self,
        limit: int = 15,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[ActivityEvent]:
        """Generates a unified chronological stream of activity events sorted timestamp DESC."""
        events: List[ActivityEvent] = []

        import re

        def _clean_str(s: Optional[str]) -> str:
            if not s:
                return ""
            cleaned = re.sub(r"[\s_-]+[0-9a-fA-F]{5,}\b", "", s).strip()
            cleaned = re.sub(r"_+", " ", cleaned).strip()
            return cleaned or s

        def _clean_platform(p: Optional[str]) -> str:
            if not p:
                return "Direct"
            p = p.replace("_", " ").strip()
            return p.title()

        with get_db_session(self._session_factory) as session:
            # 1. Job discoveries
            q_jobs = select(Job).order_by(Job.created_at.desc()).limit(limit)
            if start_date:
                q_jobs = q_jobs.where(Job.created_at >= start_date)
            if end_date:
                q_jobs = q_jobs.where(Job.created_at <= end_date)
            for j in session.execute(q_jobs).scalars().all():
                role = _clean_str(j.title) or "Role"
                company = _clean_str(j.company_raw) or "Company"
                plat = _clean_platform(j.platform)
                events.append(
                    ActivityEvent(
                        event_type="JOB_DISCOVERED",
                        timestamp=j.created_at,
                        platform=plat,
                        title=f"{role} — {company}",
                        description=f"Discovered on {plat} • {j.location or 'Location N/A'}",
                        entity_id=j.id,
                    )
                )

            # 2. Application Status Transitions
            q_hist = (
                select(ApplicationStatusHistory, Application, Job)
                .join(Application, ApplicationStatusHistory.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .order_by(ApplicationStatusHistory.changed_at.desc())
                .limit(limit)
            )
            if start_date:
                q_hist = q_hist.where(ApplicationStatusHistory.changed_at >= start_date)
            if end_date:
                q_hist = q_hist.where(ApplicationStatusHistory.changed_at <= end_date)

            for h, app, job in session.execute(q_hist).all():
                ev_type = (
                    "APPLICATION_SUBMITTED"
                    if h.new_status == "SUBMITTED"
                    else "STATUS_CHANGED"
                )
                role = _clean_str(job.title) or "Role"
                company = _clean_str(job.company_raw) or "Company"
                plat = _clean_platform(job.platform)
                st_text = h.new_status.replace("_", " ").title()
                events.append(
                    ActivityEvent(
                        event_type=ev_type,
                        timestamp=h.changed_at,
                        platform=plat,
                        title=f"{role} — {company}",
                        description=f"Application status: {st_text}",
                        status=h.new_status,
                        entity_id=app.id,
                    )
                )

            # 3. Scheduled Interviews
            q_iv = (
                select(Interview, Application, Job)
                .join(Application, Interview.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .order_by(Interview.created_at.desc())
                .limit(limit)
            )
            if start_date:
                q_iv = q_iv.where(Interview.created_at >= start_date)
            if end_date:
                q_iv = q_iv.where(Interview.created_at <= end_date)

            for iv, app, job in session.execute(q_iv).all():
                role = _clean_str(job.title) or "Role"
                company = _clean_str(job.company_raw) or "Company"
                plat = _clean_platform(job.platform)
                events.append(
                    ActivityEvent(
                        event_type="INTERVIEW_SCHEDULED",
                        timestamp=iv.created_at,
                        platform=plat,
                        title=f"{role} — {company}",
                        description=f"{iv.round_name or 'Interview round'} scheduled ({iv.mode or 'Virtual'})",
                        status=iv.status,
                        entity_id=iv.id,
                    )
                )

            # 4. Inbound Communications / Recruiter Responses
            try:
                q_comm = (
                    select(Communication, Application, Job)
                    .join(Application, Communication.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Communication.direction == "INBOUND")
                    .order_by(Communication.occurred_at.desc())
                    .limit(limit)
                )
                if start_date:
                    q_comm = q_comm.where(Communication.occurred_at >= start_date)
                if end_date:
                    q_comm = q_comm.where(Communication.occurred_at <= end_date)

                for comm, app, job in session.execute(q_comm).all():
                    role = _clean_str(job.title) or "Role"
                    company = _clean_str(job.company_raw) or "Company"
                    plat = _clean_platform(comm.type or job.platform)
                    events.append(
                        ActivityEvent(
                            event_type="RECRUITER_REPLIED",
                            timestamp=comm.occurred_at,
                            platform=plat,
                            title=f"{role} — {company}",
                            description=f"Recruiter replied via {plat}",
                            status="REPLIED",
                            entity_id=app.id,
                        )
                    )
            except Exception as e:
                logger.warning("Error fetching inbound communications for recent activity: %s", e)

        # Sort all unified events strictly by timestamp DESC
        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    def get_todays_progress(self, target_date: Optional[datetime] = None) -> DailyProgressDTO:
        """Calculates verified daily progress counters from authoritative repository methods."""
        from app.repositories.application_repository import ApplicationRepository
        from app.repositories.job_evaluation_repo import JobEvaluationRepository
        from app.repositories.job_repository import JobRepository
        from app.repositories.recruitment_repository import RecruitmentRepository

        start_of_day, end_of_day = get_local_day_utc_range(target_date)

        with get_db_session(self._session_factory) as session:
            job_repo = JobRepository(session)
            eval_repo = JobEvaluationRepository(session)
            app_repo = ApplicationRepository(session)
            rec_repo = RecruitmentRepository(session)

            disc_count = job_repo.count_discovered_between(start_of_day, end_of_day)
            qual_count = eval_repo.count_qualified_between(start_of_day, end_of_day)
            apps_count = app_repo.count_submitted_between(start_of_day, end_of_day)
            outreach_count = rec_repo.count_outbound_communications_between(start_of_day, end_of_day)
            fu_count = rec_repo.count_completed_followups_between(start_of_day, end_of_day)

            return DailyProgressDTO(
                discovered_today=disc_count,
                qualified_today=qual_count,
                applications_submitted_today=apps_count,
                outreach_sent_today=outreach_count,
                followups_completed_today=fu_count,
            )


    def get_readiness_summary(self) -> ReadinessSummaryDTO:
        """Determines component-level readiness without inventing fake overall percentages."""
        # 1. Profile completeness
        profile_complete = False
        try:
            user, profile, pro_profile = self.profile_service.get_primary_user_profile()
            profile_complete = bool(user and user.name and user.email and pro_profile and pro_profile.skills)
        except Exception:
            profile_complete = False


        # 2. Resume availability
        resume_ok = False
        try:
            resumes = self.resume_service.list_resumes()
            resume_ok = any(r.is_default for r in resumes) or len(resumes) > 0
        except Exception:
            resume_ok = False

        # 3. QnA readiness
        qna_ratio = 0.0
        qna_answered = 0
        qna_total = 0
        try:
            stats = self.qna_service.get_stats() if hasattr(self.qna_service, "get_stats") else {}
            qna_answered = stats.get("active_entries", stats.get("total_entries", stats.get("total_pairs", 0)))
            qna_total = max(25, qna_answered)
            qna_ratio = round(min(1.0, qna_answered / float(qna_total)), 2)
        except Exception:
            pass

        # 4. Platforms
        platforms: Dict[str, str] = {}
        try:
            for p in self.platform_service.list_platforms():
                if p.is_enabled:
                    cfg = self.platform_service.get_platform_config(p.name) or {}
                    st = cfg.get("status", "READY").upper()
                    platforms[p.name] = st
                else:
                    platforms[p.name] = "UNAVAILABLE"
        except Exception:
            pass

        return ReadinessSummaryDTO(
            profile_complete=profile_complete,
            resume_configured=resume_ok,
            qna_answered_ratio=qna_ratio,
            qna_answered_count=qna_answered,
            qna_total_count=qna_total,
            platforms=platforms,
        )

    @staticmethod
    def _extract_case_info(case, default_now: datetime) -> Tuple[Any, str, str, str, str, str, datetime]:
        """Safely extracts operational fields from OutreachCaseOperationViewModel or mocks."""
        app_id = getattr(case, "application_id", None) or getattr(case, "id", None)
        if hasattr(app_id, "_mock_name") or app_id is None:
            app_id = 0

        comp = getattr(case, "company_name", None)
        if hasattr(comp, "_mock_name") or not comp:
            comp = getattr(case, "application_company", None)
        if hasattr(comp, "_mock_name") or not comp:
            comp = "Recruiter"

        title = getattr(case, "job_title", None)
        if hasattr(title, "_mock_name") or not title:
            title = getattr(case, "application_job_title", None)
        if hasattr(title, "_mock_name") or not title:
            title = "Role"

        headline = getattr(case, "next_action_headline", None)
        if hasattr(headline, "_mock_name") or not headline:
            headline = getattr(case, "subject", None) or getattr(case, "last_snippet", None)
        if hasattr(headline, "_mock_name") or not headline:
            headline = "Inbound response"

        rationale = getattr(case, "next_action_rationale", None)
        if hasattr(rationale, "_mock_name") or not rationale:
            rationale = getattr(case, "primary_reason", None)
        if hasattr(rationale, "_mock_name") or not rationale:
            rationale = "Recruiter responded to your outreach. Fast follow-ups maximize conversation momentum."

        cta = getattr(case, "next_action_cta", None)
        if hasattr(cta, "_mock_name") or not cta:
            cta = "Reply to Recruiter"

        ts = getattr(case, "last_inbound_at", None)
        if hasattr(ts, "_mock_name") or not ts:
            ts = getattr(case, "last_message_at", None)
        if hasattr(ts, "_mock_name") or not ts:
            ts = default_now

        return app_id, str(comp), str(title), str(headline), str(rationale), str(cta), ts

    def _sanitize_failure_reason(self, raw: Optional[str]) -> str:
        """Sanitizes raw error/exception messages and strips Selenium stacktrace dumps."""
        if not raw:
            return "Application paused for manual verification"
        # Remove stacktrace and traceback blocks
        for token in ("Stacktrace:", "stack trace:", "Traceback (most recent"):
            if token in raw:
                raw = raw.split(token)[0]
        raw = raw.strip()
        if raw.startswith("Message:"):
            raw = raw[8:].strip()
        # Filter out lines with stack addresses or <unknown>
        lines = [
            l.strip()
            for l in raw.splitlines()
            if l.strip() and not l.strip().startswith(("#", "0x")) and "<unknown>" not in l
        ]
        cleaned = " ".join(lines).strip()
        if not cleaned or cleaned.startswith("0x") or len(cleaned) < 3:
            return "Browser automation paused for manual verification"
        if len(cleaned) > 110:
            return cleaned[:107] + "..."
        return cleaned

    def get_todays_job_hunt_items(self, limit: int = 10) -> List[TodaysHuntItemDTO]:
        """Assembles and prioritizes actionable work queue items with strict deduplication.
        Today's Job Hunt is strictly an operational work queue and NEVER falls back to unapplied jobs.
        """
        candidates: List[TodaysHuntItemDTO] = []
        now = utc_now()
        start_of_today, end_of_today = get_local_day_utc_range()
        end_of_week = end_of_today + timedelta(days=7)

        # 1. Interviews (Today & Upcoming)
        try:
            interviews = self.recruitment_service.list_interviews(status="SCHEDULED", limit=20)
            for iv in interviews:
                if not iv.scheduled_at:
                    continue
                app = iv.application
                job = app.job if app else None
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Role")
                round_name = iv.round_name or "Interview"
                time_str = format_local_datetime(iv.scheduled_at, "%I:%M %p")

                if start_of_today <= iv.scheduled_at <= end_of_today:
                    candidates.append(
                        TodaysHuntItemDTO(
                            id=f"INTERVIEW:{iv.id}",
                            item_type="INTERVIEW_TODAY",
                            priority=1,
                            urgency="URGENT",
                            title=f"Interview Today: {title}",
                            company=company,
                            subtitle=f"{round_name} • {time_str} ({iv.mode})",
                            reason=f"Scheduled {round_name} round with {company}",
                            source_entity_type="interview",
                            source_entity_id=iv.id,
                            recommended_action="PREPARE_INTERVIEW",
                            action_payload={
                                "interview_id": iv.id,
                                "application_id": iv.application_id,
                                "meeting_link": iv.meeting_link,
                            },
                            due_at=iv.scheduled_at,
                            sort_key=f"1_{iv.scheduled_at.isoformat()}",
                        )
                    )
                elif end_of_today < iv.scheduled_at <= end_of_week:
                    day_str = format_local_datetime(iv.scheduled_at, "%a, %b %d at %I:%M %p")
                    candidates.append(
                        TodaysHuntItemDTO(
                            id=f"UPCOMING_INTERVIEW:{iv.id}",
                            item_type="UPCOMING_INTERVIEW",
                            priority=7,
                            urgency="INFORMATIONAL",
                            title=f"Upcoming: {title}",
                            company=company,
                            subtitle=f"{round_name} on {day_str}",
                            reason=f"Interview scheduled on {day_str}",
                            source_entity_type="interview",
                            source_entity_id=iv.id,
                            recommended_action="PREPARE_INTERVIEW",
                            action_payload={
                                "interview_id": iv.id,
                                "application_id": iv.application_id,
                                "meeting_link": iv.meeting_link,
                            },
                            due_at=iv.scheduled_at,
                            sort_key=f"7_{iv.scheduled_at.isoformat()}",
                        )
                    )
        except Exception:
            pass

        # 2. Follow-ups (Overdue & Due Today)
        try:
            followups = self.recruitment_service.list_follow_ups(status="PENDING", limit=50)
            for fu in followups:
                app = fu.application
                job = app.job if app else None
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Application")

                if fu.due_at < start_of_today:
                    days_overdue = (start_of_today.date() - fu.due_at.date()).days
                    day_label = f"{days_overdue} day{'s' if days_overdue != 1 else ''} overdue"
                    candidates.append(
                        TodaysHuntItemDTO(
                            id=f"OVERDUE_FOLLOWUP:{fu.id}",
                            item_type="OVERDUE_FOLLOWUP",
                            priority=2,
                            urgency="URGENT",
                            title=f"Overdue Follow-up: {company}",
                            company=company,
                            subtitle=f"{title} • {day_label}",
                            reason=f"Follow-up reminder past due ({day_label})",
                            source_entity_type="followup",
                            source_entity_id=fu.id,
                            recommended_action="COMPOSE_FOLLOWUP",
                            action_payload={
                                "followup_id": fu.id,
                                "application_id": fu.application_id,
                                "contact_id": fu.contact_id,
                            },
                            due_at=fu.due_at,
                            sort_key=f"2_{fu.due_at.isoformat()}",
                        )
                    )
                elif start_of_today <= fu.due_at <= end_of_today:
                    candidates.append(
                        TodaysHuntItemDTO(
                            id=f"FOLLOWUP_DUE_TODAY:{fu.id}",
                            item_type="FOLLOWUP_DUE_TODAY",
                            priority=4,
                            urgency="HIGH",
                            title=f"Follow-up Due: {company}",
                            company=company,
                            subtitle=f"{title} • Due today",
                            reason="Follow-up cadence recommendation for today",
                            source_entity_type="followup",
                            source_entity_id=fu.id,
                            recommended_action="COMPOSE_FOLLOWUP",
                            action_payload={
                                "followup_id": fu.id,
                                "application_id": fu.application_id,
                                "contact_id": fu.contact_id,
                            },
                            due_at=fu.due_at,
                            sort_key=f"4_{fu.due_at.isoformat()}",
                        )
                    )
        except Exception:
            pass

        # 3. Recruiter Inbound Replies (from Outreach Operations WorkQueue)
        seen_recruiter_app_ids = set()
        try:
            from app.services.dto.outreach_enums import WorkQueueSection
            work_queue = self.outreach_service.get_work_queue()
            for group in work_queue:
                if group.section == WorkQueueSection.TODAY:
                    for case in group.cases:
                        c_appid, c_comp, c_title, c_headline, c_rationale, c_cta, c_ts = self._extract_case_info(case, now)
                        seen_recruiter_app_ids.add(c_appid)
                        candidates.append(
                            TodaysHuntItemDTO(
                                id=f"RECRUITER_REPLY:{c_appid}",
                                item_type="RECRUITER_REPLY",
                                priority=3,
                                urgency="HIGH",
                                title=f"Recruiter Attention: {c_comp}",
                                company=c_comp,
                                subtitle=f"{c_title} • {c_headline}",
                                reason=c_rationale,
                                source_entity_type="conversation",
                                source_entity_id=c_appid,
                                recommended_action="OPEN_CONVERSATION",
                                action_payload={
                                    "conversation_id": c_appid,
                                    "application_id": c_appid,
                                },
                                due_at=c_ts,
                                sort_key=f"3_{c_appid}",
                            )
                        )
        except Exception as e:
            logger.warning("Error fetching outreach work queue for hunt items: %s", e)

        # 3b. Direct Recruiter Contacted Applications (not already in outreach work queue)
        try:
            from app.services.application_service import ApplicationFilter
            rec_apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["RECRUITER_CONTACTED"]),
                limit=10,
            )
            for app in rec_apps:
                if app.id in seen_recruiter_app_ids:
                    continue
                seen_recruiter_app_ids.add(app.id)
                job = app.job
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Application")
                candidates.append(
                    TodaysHuntItemDTO(
                        id=f"RECRUITER_CONTACT:{app.id}",
                        item_type="RECRUITER_REPLY",
                        priority=3,
                        urgency="HIGH",
                        title=f"Recruiter Inquiry: {company}",
                        company=company,
                        subtitle=f"{title} • Inbound recruiter contact",
                        reason="Recruiter reached out regarding your candidacy. Review message thread.",
                        source_entity_type="application",
                        source_entity_id=app.id,
                        recommended_action="OPEN_CONVERSATION",
                        action_payload={
                            "conversation_id": app.id,
                            "application_id": app.id,
                        },
                        due_at=app.updated_at or app.created_at,
                        sort_key=f"3_{app.id}",
                    )
                )
        except Exception as e:
            logger.warning("Error fetching recruiter contacted apps: %s", e)

        # 4. Applications in Active INTERVIEW Stage
        try:
            from app.services.application_service import ApplicationFilter
            iv_apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["INTERVIEW"]),
                limit=10,
            )
            for app in iv_apps:
                job = app.job
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Application")
                candidates.append(
                    TodaysHuntItemDTO(
                        id=f"INTERVIEW_STAGE:{app.id}",
                        item_type="INTERVIEW_TODAY",
                        priority=4,
                        urgency="HIGH",
                        title=f"Interview Stage: {company}",
                        company=company,
                        subtitle=f"{title} • Active evaluation",
                        reason="Application is in active interview stage. Review job notes and interview prep.",
                        source_entity_type="application",
                        source_entity_id=app.id,
                        recommended_action="PREPARE_INTERVIEW",
                        action_payload={
                            "application_id": app.id,
                        },
                        due_at=app.updated_at or app.created_at,
                        sort_key=f"4_{app.id}",
                    )
                )
        except Exception as e:
            logger.warning("Error fetching interview stage apps: %s", e)

        # 5. Applications Requiring Manual Review
        try:
            from app.services.application_service import ApplicationFilter
            manual_apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["MANUAL_REQUIRED", "FAILED", "CHANGES_REQUESTED"]),
                limit=10,
            )
            for app in manual_apps:
                job = app.job
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Application")
                raw_reason = app.failure_reason or app.skip_reason
                cleaned_reason = self._sanitize_failure_reason(raw_reason)
                candidates.append(
                    TodaysHuntItemDTO(
                        id=f"MANUAL_REVIEW:{app.id}",
                        item_type="MANUAL_REVIEW",
                        priority=6,
                        urgency="NORMAL",
                        title=f"Manual Check: {company}",
                        company=company,
                        subtitle=f"{title} • Action required",
                        reason=cleaned_reason,
                        source_entity_type="application",
                        source_entity_id=app.id,
                        recommended_action="REVIEW_APPLICATION",
                        action_payload={
                            "application_id": app.id,
                            "job_id": app.job_id,
                        },
                        due_at=app.updated_at or app.created_at,
                        sort_key=f"6_{app.id}",
                    )
                )
        except Exception as e:
            logger.warning("Error fetching manual review apps: %s", e)

        # 6. Deduplication & Priority Selection
        # Group by unique opportunity key: application_id if present, else item.id
        grouped_by_opp: Dict[str, List[TodaysHuntItemDTO]] = {}
        for item in candidates:
            app_id = item.action_payload.get("application_id")
            if app_id:
                key = f"app:{app_id}"
            elif item.source_entity_type == "job":
                key = f"job:{item.source_entity_id}"
            else:
                key = item.id

            if key not in grouped_by_opp:
                grouped_by_opp[key] = []
            grouped_by_opp[key].append(item)

        deduplicated: List[TodaysHuntItemDTO] = []
        for key, items in grouped_by_opp.items():
            items.sort(key=lambda x: (x.priority, x.sort_key))
            winner = items[0]
            if len(items) > 1:
                secondary_count = len(items) - 1
                winner.subtitle = f"{winner.subtitle} (+{secondary_count} more action{'s' if secondary_count != 1 else ''})"
            deduplicated.append(winner)

        # Global sort: priority ASC, sort_key ASC
        deduplicated.sort(key=lambda x: (x.priority, x.sort_key))
        return deduplicated[:limit]

    def get_next_best_action(self) -> NextBestActionDTO:
        """Determines the single highest-priority operational action right now.
        Deterministic priority waterfall:
        1. Interview scheduled today (Urgent)
        2. Recruiter inbound reply awaiting response (Urgent)
        2b. Recruiter contacted application inquiry (Urgent)
        3. Overdue follow-up (Urgent)
        4. Follow-up due today (High)
        4b. Active interview stage preparation (High)
        5. Application manual review / blocked state (Action Required)
        6. Top qualified unapplied opportunity (High match - only if operational queue is clear)
        7. All caught up fallback (All clear)
        """
        now = utc_now()
        start_of_today, end_of_today = get_local_day_utc_range()

        # 1. Interview Today
        try:
            interviews = self.recruitment_service.list_interviews(status="SCHEDULED", limit=10)
            for iv in interviews:
                if iv.scheduled_at and start_of_today <= iv.scheduled_at <= end_of_today:
                    job = iv.application.job if iv.application else None
                    company = (job.company_raw if job else "Company")
                    title = (job.title if job else "Role")
                    round_name = iv.round_name or "Interview"
                    time_str = format_local_datetime(iv.scheduled_at, "%I:%M %p")
                    return NextBestActionDTO(
                        action_id=f"NBA_INTERVIEW:{iv.id}",
                        action_type="INTERVIEW_TODAY",
                        title=f"Interview Today: {title}",
                        company=company,
                        subtitle=f"{round_name} • {time_str} ({iv.mode or 'VIRTUAL'})",
                        reason=f"Scheduled {round_name} interview with {company}. Review candidate notes and meeting details.",
                        button_label="Prepare Interview",
                        action_name="PREPARE_INTERVIEW",
                        action_payload={
                            "interview_id": iv.id,
                            "application_id": iv.application_id,
                            "meeting_link": iv.meeting_link,
                        },
                        badge_text="INTERVIEW TODAY",
                        badge_variant="purple",
                        timestamp=iv.scheduled_at,
                    )
        except Exception as e:
            logger.warning("Error checking interviews for NBA: %s", e)

        # 2. Recruiter Inbound Reply / Outreach Attention
        try:
            from app.services.dto.outreach_enums import WorkQueueSection
            work_queue = self.outreach_service.get_work_queue()
            for group in work_queue:
                if group.section == WorkQueueSection.TODAY and group.cases:
                    case = group.cases[0]
                    c_appid, c_comp, c_title, c_headline, c_rationale, c_cta, c_ts = self._extract_case_info(case, now)
                    return NextBestActionDTO(
                        action_id=f"NBA_REPLY:{c_appid}",
                        action_type="RECRUITER_REPLY",
                        title=f"Recruiter replied — {c_comp}",
                        company=c_comp,
                        subtitle=c_title,
                        reason=c_rationale or "Recruiter responded — review the conversation and prepare a reply.",
                        button_label="Draft Reply",
                        action_name="OPEN_CONVERSATION",
                        action_payload={
                            "conversation_id": c_appid,
                            "application_id": c_appid,
                        },
                        badge_text="RECRUITER REPLY",
                        badge_variant="danger",
                        timestamp=c_ts,
                    )
        except Exception as e:
            logger.warning("Error checking outreach work queue for NBA: %s", e)

        # 2b. Recruiter Contacted Inquiries
        try:
            from app.services.application_service import ApplicationFilter
            rec_apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["RECRUITER_CONTACTED"]),
                limit=5,
            )
            if rec_apps:
                app = rec_apps[0]
                job = app.job
                comp = job.company_raw if job else "Company"
                titl = job.title if job else "Application"
                return NextBestActionDTO(
                    action_id=f"NBA_REC_CONTACT:{app.id}",
                    action_type="RECRUITER_REPLY",
                    title=f"Recruiter inquiry — {comp}",
                    company=comp,
                    subtitle=titl,
                    reason="Recruiter reached out regarding your candidacy — review and prepare a reply.",
                    button_label="Draft Reply",
                    action_name="OPEN_CONVERSATION",
                    action_payload={
                        "conversation_id": app.id,
                        "application_id": app.id,
                    },
                    badge_text="RECRUITER REPLY",
                    badge_variant="danger",
                    timestamp=app.updated_at or app.created_at,
                )
        except Exception as e:
            logger.warning("Error checking recruiter contacted apps for NBA: %s", e)

        # 3. Overdue Follow-up
        try:
            followups = self.recruitment_service.list_follow_ups(status="PENDING", limit=20)
            for fu in followups:
                if fu.due_at and fu.due_at < start_of_today:
                    app = fu.application
                    job = app.job if app else None
                    company = (job.company_raw if job else "Company")
                    title = (job.title if job else "Application")
                    days_overdue = (start_of_today.date() - fu.due_at.date()).days
                    day_label = f"{days_overdue} day{'s' if days_overdue != 1 else ''} overdue"
                    return NextBestActionDTO(
                        action_id=f"NBA_OVERDUE:{fu.id}",
                        action_type="OVERDUE_FOLLOWUP",
                        title=f"Follow-up overdue — {company}",
                        company=company,
                        subtitle=f"{title} • {day_label}",
                        reason=f"Follow-up is {day_label}. Send a check-in to keep this application warm.",
                        button_label="Send Follow-Up",
                        action_name="COMPOSE_FOLLOWUP",
                        action_payload={
                            "followup_id": fu.id,
                            "application_id": fu.application_id,
                            "contact_id": fu.contact_id,
                        },
                        badge_text="FOLLOW-UP DUE",
                        badge_variant="warning",
                        timestamp=fu.due_at,
                    )
        except Exception as e:
            logger.warning("Error checking overdue followups for NBA: %s", e)

        # 4. Follow-up Due Today
        try:
            followups = self.recruitment_service.list_follow_ups(status="PENDING", limit=20)
            for fu in followups:
                if fu.due_at and start_of_today <= fu.due_at <= end_of_today:
                    app = fu.application
                    job = app.job if app else None
                    company = (job.company_raw if job else "Company")
                    title = (job.title if job else "Application")
                    return NextBestActionDTO(
                        action_id=f"NBA_DUE_TODAY:{fu.id}",
                        action_type="FOLLOWUP_DUE_TODAY",
                        title=f"Follow-up due today — {company}",
                        company=company,
                        subtitle=title,
                        reason="Follow-up cadence recommendation for today. Maintain active recruiter engagement.",
                        button_label="Send Follow-Up",
                        action_name="COMPOSE_FOLLOWUP",
                        action_payload={
                            "followup_id": fu.id,
                            "application_id": fu.application_id,
                            "contact_id": fu.contact_id,
                        },
                        badge_text="DUE TODAY",
                        badge_variant="warning",
                        timestamp=fu.due_at,
                    )
        except Exception as e:
            logger.warning("Error checking due today followups for NBA: %s", e)

        # 4b. Active Interview Stage Preparation
        try:
            from app.services.application_service import ApplicationFilter
            iv_apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["INTERVIEW"]),
                limit=5,
            )
            if iv_apps:
                app = iv_apps[0]
                job = app.job
                comp = job.company_raw if job else "Company"
                titl = job.title if job else "Application"
                return NextBestActionDTO(
                    action_id=f"NBA_IV_STAGE:{app.id}",
                    action_type="INTERVIEW_TODAY",
                    title=f"Interview Stage: {comp}",
                    company=comp,
                    subtitle=f"{titl} • Active candidate evaluation",
                    reason="Your application has reached the interview stage. Review job notes and prepare questions.",
                    button_label="Prepare Interview",
                    action_name="PREPARE_INTERVIEW",
                    action_payload={
                        "application_id": app.id,
                    },
                    badge_text="INTERVIEW STAGE",
                    badge_variant="purple",
                    timestamp=app.updated_at or app.created_at,
                )
        except Exception as e:
            logger.warning("Error checking interview stage for NBA: %s", e)

        # 5. Application Manual Review / Action Needed
        try:
            from app.services.application_service import ApplicationFilter
            apps = self.application_service.list_applications(
                ApplicationFilter(status_list=["MANUAL_REQUIRED", "CHANGES_REQUESTED", "FAILED"]),
                limit=5,
            )
            if apps:
                app = apps[0]
                job = app.job if app else None
                company = (job.company_raw if job else "Company")
                title = (job.title if job else "Role")
                st = (app.status or "").replace("_", " ").title()
                return NextBestActionDTO(
                    action_id=f"NBA_APP_REVIEW:{app.id}",
                    action_type="MANUAL_REVIEW",
                    title=f"Application Requires Review: {title}",
                    company=company,
                    subtitle=f"{company} • Status: {st}",
                    reason="This application encountered a verification check or manual step requiring candidate confirmation.",
                    button_label="Review Application",
                    action_name="REVIEW_APPLICATION",
                    action_payload={
                        "application_id": app.id,
                        "job_id": app.job_id,
                    },
                    badge_text="ACTION REQUIRED",
                    badge_variant="primary",
                    timestamp=app.updated_at or app.created_at,
                )
        except Exception as e:
            logger.warning("Error checking manual review apps for NBA: %s", e)

        # 6. Top Qualified Opportunity (Only if operational queue is clear, score >= 85)
        try:
            top_opps = self.job_service.get_top_opportunities(limit=1)
            if top_opps and top_opps[0].score >= 85:
                top = top_opps[0]
                skills_preview = ", ".join(top.matched_skills[:3]) if top.matched_skills else "High match"
                return NextBestActionDTO(
                    action_id=f"NBA_TOP_OPP:{top.job_id}",
                    action_type="TOP_OPPORTUNITY_REVIEW",
                    title=f"Top Match: {top.title}",
                    company=top.company,
                    subtitle=f"{top.score}% Match ({top.decision.replace('_', ' ').title()}) • {top.platform.title()}",
                    reason=f"Strongest unapplied match: {skills_preview}. Review job details and start application.",
                    button_label="Review Opportunity",
                    action_name="REVIEW_JOB",
                    action_payload={"job_id": top.job_id},
                    badge_text=f"{top.score}% MATCH",
                    badge_variant="success",
                    timestamp=top.discovered_at,
                )
        except Exception as e:
            logger.warning("Error checking top opportunities for NBA: %s", e)

        # 7. All Caught Up
        return NextBestActionDTO(
            action_id="NBA_ALL_CLEAR",
            action_type="ALL_CAUGHT_UP",
            title="You're all caught up!",
            company="JobPilot Operational Queue",
            subtitle="No urgent tasks or overdue actions pending",
            reason="Your search pipeline is running smoothly. Discover new opportunities or run a keyword scan.",
            button_label="Discover Jobs",
            action_name="NAVIGATE_JOBS",
            action_payload={},
            badge_text="ALL CLEAR",
            badge_variant="success",
            timestamp=now,
        )

    def get_search_performance(self, preset: str = "30D") -> SearchPerformanceDTO:
        """Assembles unified Search Performance and ATS Funnel metrics using AnalyticsService."""
        from app.services.analytics_service import AnalyticsFilter
        from app.services.dto.dashboard_dto import PlatformMetricDTO, SearchPerformanceDTO

        f = AnalyticsFilter(date_preset=preset)
        funnel_data = self.analytics_service.get_funnel_flow(f)
        platform_data = self.analytics_service.get_platform_performance(f)

        stages = funnel_data.get("stages", [])
        stage_map = {s.get("stage_id"): s.get("count", 0) for s in stages}

        total_disc = stage_map.get("discovered", 0)
        total_qual = stage_map.get("qualified", 0)
        total_app = stage_map.get("submitted", 0)
        total_resp = stage_map.get("responses", 0)
        total_iv = stage_map.get("interviews", 0)
        total_off = stage_map.get("offers", 0)

        app_conv = round((total_app / total_qual * 100), 1) if total_qual > 0 else 0.0
        iv_conv = round((total_iv / total_app * 100), 1) if total_app > 0 else 0.0
        off_conv = round((total_off / total_app * 100), 1) if total_app > 0 else 0.0

        platform_metrics: List[PlatformMetricDTO] = []
        for p in platform_data:
            platform_metrics.append(
                PlatformMetricDTO(
                    platform_key=p.get("platform_key", ""),
                    platform_name=p.get("platform", "").title(),
                    discovered_count=p.get("jobs", 0),
                    applied_count=p.get("applications", 0),
                    interview_count=p.get("interviews", 0),
                    offer_count=p.get("offers", 0),
                    application_rate=p.get("application_rate", 0.0),
                    interview_rate=p.get("interview_rate", 0.0),
                    offer_rate=p.get("offer_rate", 0.0),
                )
            )

        return SearchPerformanceDTO(
            preset=preset,
            total_discovered=total_disc,
            total_qualified=total_qual,
            total_applied=total_app,
            total_responses=total_resp,
            total_interviews=total_iv,
            total_offers=total_off,
            application_conversion_pct=app_conv,
            interview_conversion_pct=iv_conv,
            offer_conversion_pct=off_conv,
            funnel_stages=stages,
            platform_metrics=platform_metrics,
        )

    def get_dashboard_snapshot(self) -> DashboardSnapshotDTO:

        """Assembles a unified snapshot across all domains."""
        next_best = self.get_next_best_action()
        hunt_items = self.get_todays_job_hunt_items(limit=10)
        top_opps = self.job_service.get_top_opportunities(limit=7)
        progress = self.get_todays_progress()
        search_perf = self.get_search_performance(preset="30D")
        readiness = self.get_readiness_summary()
        pipeline = self.get_summary_metrics()
        activities = self.get_recent_activity(limit=5)

        return DashboardSnapshotDTO(
            next_best_action=next_best,
            hunt_items=hunt_items,
            top_opportunities=top_opps,
            daily_progress=progress,
            search_performance=search_perf,
            readiness=readiness,
            pipeline_summary=pipeline,
            recent_activities=activities,
        )


