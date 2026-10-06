"""Analytics and recruitment conversion computation service.

Provides calculation of application rates, direct recruiter responses,
pipeline progression, interview conversion rates, offer conversion rates,
time-series trend buckets, application aging, response time forensics,
and cross-platform comparative metrics.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import statistics
from typing import Any, Dict, List, Optional, Tuple, Union

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import utc_now
from app.db.models import (
    Application,
    ApplicationStatusHistory,
    Communication,
    Interview,
    Job,
    JobEvaluation,
    Offer,
)
from app.db.session import SessionLocal, get_db_session
from app.utils_time import get_local_date_bounds, to_local_datetime


# ---------------------------------------------------------------------------
# Authoritative Status Sets
# ---------------------------------------------------------------------------

# Genuinely submitted applications (strictly excludes pre-submission/error states:
# APPLYING, FAILED, UNKNOWN, MANUAL_REQUIRED, EXTERNAL, SKIPPED)
SUBMITTED_STATUSES = {
    "SUBMITTED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "RECRUITER_CONTACTED",
    "ASSESSMENT",
    "INTERVIEW",
    "OFFER",
    "REJECTED",
    "WITHDRAWN",
}

# Advanced beyond initial submission into a recruitment progression stage
PROGRESSED_STATUSES = {
    "UNDER_REVIEW",
    "SHORTLISTED",
    "RECRUITER_CONTACTED",
    "ASSESSMENT",
    "INTERVIEW",
    "OFFER",
}

# Currently active recruitment applications for aging analysis (terminal states excluded)
ACTIVE_AGING_STATUSES = {
    "SUBMITTED",
    "UNDER_REVIEW",
    "SHORTLISTED",
    "RECRUITER_CONTACTED",
    "ASSESSMENT",
    "INTERVIEW",
}


# ---------------------------------------------------------------------------
# DTOs & Filter Models
# ---------------------------------------------------------------------------

@dataclass
class AnalyticsFilter:
    """Structured criteria for filtering recruitment analytics data."""

    date_preset: str = "30D"  # TODAY, 7D, 30D, 90D, 6M, 1Y, ALL, CUSTOM
    start_date: Optional[datetime] = None  # In UTC
    end_date: Optional[datetime] = None    # In UTC
    platform: Optional[str] = None         # "all" or specific: "linkedin", "naukri", etc.
    application_method: Optional[str] = None # "all" or specific: "EASY_APPLY", etc.
    status: Optional[str] = None           # "all" or specific status


@dataclass
class MetricWithComparison:
    """Metric value bundled with period-over-period comparison details."""

    value: Union[int, float]
    comparison_available: bool = False
    prev_value: Optional[Union[int, float]] = None
    pct_change: Optional[float] = None
    reason: Optional[str] = None


@dataclass
class ResponseTimeStats:
    """Forensic statistics for recruitment response latency."""

    has_sufficient_data: bool
    sample_count: int
    source_type: str  # "COMMUNICATION", "STATUS_TRANSITION_PROXY", or "INSUFFICIENT_DATA"
    avg_days: Optional[float] = None
    median_days: Optional[float] = None
    fastest_days: Optional[float] = None
    slowest_days: Optional[float] = None
    distribution: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Analytics Service Implementation
# ---------------------------------------------------------------------------

class AnalyticsService:
    """Service layer for recruitment conversion funnel metrics and platform comparisons."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def resolve_filter_dates(self, f: AnalyticsFilter) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Resolves filter date boundaries from preset or explicit start/end dates."""
        if f.start_date is not None or f.end_date is not None:
            return f.start_date, f.end_date
        return get_local_date_bounds(f.date_preset)

    def _apply_application_filters(
        self,
        stmt: Any,
        f: Optional[AnalyticsFilter],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        use_submission_date: bool = True,
    ) -> Any:
        """Applies date, platform, method, and status filters to Application queries."""
        # 1. Authoritative submission restriction
        stmt = stmt.where(Application.status.in_(SUBMITTED_STATUSES))

        # 2. Date filtering
        # Submission-centric: use applied_at, falling back to created_at if applied_at missing
        if use_submission_date:
            date_col = func.coalesce(Application.applied_at, Application.created_at)
        else:
            date_col = Application.created_at

        if start_date:
            stmt = stmt.where(date_col >= start_date)
        if end_date:
            stmt = stmt.where(date_col <= end_date)

        # 3. Platform filter via Job.platform join
        if f and f.platform and f.platform.strip().lower() not in ["all", ""]:
            stmt = stmt.where(Job.platform == f.platform.strip().lower())

        # 4. Application method filter
        if f and f.application_method and f.application_method.strip().upper() not in ["ALL", ""]:
            stmt = stmt.where(Application.application_type == f.application_method.strip().upper())

        # 5. Status filter
        if f and f.status and f.status.strip().upper() not in ["ALL", ""]:
            stmt = stmt.where(Application.status == f.status.strip().upper())

        return stmt

    def get_summary_metrics(self, f: Optional[AnalyticsFilter] = None) -> Dict[str, Any]:
        """Calculates top-level summary metrics with period-over-period comparisons."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        with get_db_session(self._session_factory) as session:
            # 1. Submitted Applications in current period
            q_apps = select(func.count(func.distinct(Application.id))).join(Job, Application.job_id == Job.id)
            q_apps = self._apply_application_filters(q_apps, f, start_date, end_date)
            submitted_apps = session.scalar(q_apps) or 0

            # 2. Direct Recruiter Responses (Inbound communication on submitted applications in cohort)
            q_resp = (
                select(func.count(func.distinct(Communication.application_id)))
                .join(Application, Communication.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .where(Communication.direction == "INBOUND")
            )
            q_resp = self._apply_application_filters(q_resp, f, start_date, end_date)
            direct_responses = session.scalar(q_resp) or 0

            # 3. Pipeline Progression (Advanced beyond SUBMITTED into PROGRESSED_STATUSES)
            q_prog = (
                select(func.count(func.distinct(Application.id)))
                .join(Job, Application.job_id == Job.id)
                .where(Application.status.in_(PROGRESSED_STATUSES))
            )
            q_prog = self._apply_application_filters(q_prog, f, start_date, end_date)
            progressed_apps = session.scalar(q_prog) or 0

            # 4. Distinct Applications with >= 1 Interview in cohort
            q_iv = (
                select(func.count(func.distinct(Interview.application_id)))
                .join(Application, Interview.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
            )
            q_iv = self._apply_application_filters(q_iv, f, start_date, end_date)
            interviewed_apps = session.scalar(q_iv) or 0

            # 5. Distinct Applications with an Offer in cohort
            q_off = (
                select(func.count(func.distinct(Offer.application_id)))
                .join(Application, Offer.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
            )
            q_off = self._apply_application_filters(q_off, f, start_date, end_date)
            offer_apps = session.scalar(q_off) or 0

            # 6. Conversion Rates
            resp_rate = round((direct_responses / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0
            prog_rate = round((progressed_apps / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0
            iv_rate = round((interviewed_apps / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0
            offer_rate = round((offer_apps / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0

            # 7. Period Comparison for Submitted Applications
            comp_apps = MetricWithComparison(value=submitted_apps)
            if start_date and end_date:
                duration = end_date - start_date
                prev_start = start_date - duration
                prev_end = start_date

                q_prev = select(func.count(func.distinct(Application.id))).join(Job, Application.job_id == Job.id)
                q_prev = self._apply_application_filters(q_prev, f, prev_start, prev_end)
                prev_apps = session.scalar(q_prev) or 0

                comp_apps.prev_value = prev_apps
                if prev_apps > 0:
                    comp_apps.comparison_available = True
                    comp_apps.pct_change = round(((submitted_apps - prev_apps) / prev_apps) * 100, 1)
                else:
                    comp_apps.comparison_available = False
                    comp_apps.reason = "No previous-period data"
            else:
                comp_apps.comparison_available = False
                comp_apps.reason = "Comparison requires bounded date range"

            # 8. Weekly Application Velocity
            velocity = self._calculate_velocity(session, f, start_date, end_date, submitted_apps)

            # 9. Response Time Stats
            response_stats = self.get_response_time_stats(f)

            return {
                "submitted_applications": comp_apps,
                "direct_responses": direct_responses,
                "response_rate": resp_rate,
                "progressed_applications": progressed_apps,
                "progression_rate": prog_rate,
                "interviewed_applications": interviewed_apps,
                "interview_rate": iv_rate,
                "offer_applications": offer_apps,
                "offer_rate": offer_rate,
                "velocity": velocity,
                "response_stats": response_stats,
            }

    def _calculate_velocity(
        self,
        session: Session,
        f: AnalyticsFilter,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        total_apps: int,
    ) -> MetricWithComparison:
        """Calculates weekly application velocity based on active date range."""
        if not start_date or not end_date:
            # All time velocity
            return MetricWithComparison(value=total_apps, comparison_available=False, reason="All time active")

        days_count = max(1, (end_date - start_date).days + 1)
        weeks = days_count / 7.0
        current_rate = round(total_apps / weeks, 1) if weeks > 0 else float(total_apps)

        # Previous period velocity
        duration = end_date - start_date
        prev_start = start_date - duration
        prev_end = start_date

        q_prev = select(func.count(func.distinct(Application.id))).join(Job, Application.job_id == Job.id)
        q_prev = self._apply_application_filters(q_prev, f, prev_start, prev_end)
        prev_apps = session.scalar(q_prev) or 0
        prev_rate = round(prev_apps / weeks, 1) if weeks > 0 else float(prev_apps)

        res = MetricWithComparison(value=current_rate)
        res.prev_value = prev_rate
        if prev_apps > 0:
            res.comparison_available = True
            res.pct_change = round(((current_rate - prev_rate) / prev_rate) * 100, 1)
        else:
            res.comparison_available = False
            res.reason = "No previous-period data"
        return res

    def get_funnel_flow(self, f: Optional[AnalyticsFilter] = None) -> Dict[str, Any]:
        """Calculates factual step-by-step conversion and drop-off across stages.

        Clearly delineates Discovery Cohort (Jobs created in period) from
        Application Cohort (Applications submitted in period).
        """
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        with get_db_session(self._session_factory) as session:
            # A. Discovery Cohort
            # 1. Total Jobs Discovered
            q_j = select(func.count(Job.id))
            if start_date:
                q_j = q_j.where(Job.created_at >= start_date)
            if end_date:
                q_j = q_j.where(Job.created_at <= end_date)
            if f.platform and f.platform.strip().lower() not in ["all", ""]:
                q_j = q_j.where(Job.platform == f.platform.strip().lower())
            discovered_jobs = session.scalar(q_j) or 0

            # 2. Total Jobs Qualified
            q_q = select(func.count(func.distinct(JobEvaluation.job_id))).join(Job, JobEvaluation.job_id == Job.id).where(
                JobEvaluation.status == "QUALIFIED"
            )
            if start_date:
                q_q = q_q.where(Job.created_at >= start_date)
            if end_date:
                q_q = q_q.where(Job.created_at <= end_date)
            if f.platform and f.platform.strip().lower() not in ["all", ""]:
                q_q = q_q.where(Job.platform == f.platform.strip().lower())
            qualified_jobs = session.scalar(q_q) or 0

            # B. Application Cohort (Applications submitted in period)
            # 3. Submitted Applications
            q_a = select(func.count(func.distinct(Application.id))).join(Job, Application.job_id == Job.id)
            q_a = self._apply_application_filters(q_a, f, start_date, end_date)
            submitted_apps = session.scalar(q_a) or 0

            # 4. Recruiter Responses (Inbound communication or Progression)
            q_r = (
                select(func.count(func.distinct(Application.id)))
                .join(Job, Application.job_id == Job.id)
                .outerjoin(Communication, Communication.application_id == Application.id)
                .where(
                    (Communication.direction == "INBOUND") | (Application.status.in_(PROGRESSED_STATUSES))
                )
            )
            q_r = self._apply_application_filters(q_r, f, start_date, end_date)
            responded_apps = session.scalar(q_r) or 0

            # 5. Distinct Interviews
            q_i = (
                select(func.count(func.distinct(Interview.application_id)))
                .join(Application, Interview.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
            )
            q_i = self._apply_application_filters(q_i, f, start_date, end_date)
            interviewed_apps = session.scalar(q_i) or 0

            # 6. Distinct Offers
            q_o = (
                select(func.count(func.distinct(Offer.application_id)))
                .join(Application, Offer.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
            )
            q_o = self._apply_application_filters(q_o, f, start_date, end_date)
            offer_apps = session.scalar(q_o) or 0

            # Calculate Stage Conversion & Drop-off percentages
            stages = [
                {
                    "stage_id": "discovered",
                    "label": "Jobs Discovered",
                    "cohort_type": "DISCOVERY",
                    "count": discovered_jobs,
                    "conversion_pct": 100.0,
                    "drop_off_pct": 0.0,
                },
                {
                    "stage_id": "qualified",
                    "label": "Jobs Qualified",
                    "cohort_type": "DISCOVERY",
                    "count": qualified_jobs,
                    "conversion_pct": round((qualified_jobs / discovered_jobs * 100), 1) if discovered_jobs > 0 else 0.0,
                    "drop_off_pct": round(((discovered_jobs - qualified_jobs) / discovered_jobs * 100), 1) if discovered_jobs > 0 else 0.0,
                },
                {
                    "stage_id": "submitted",
                    "label": "Applications Submitted",
                    "cohort_type": "APPLICATION",
                    "count": submitted_apps,
                    "conversion_pct": round((submitted_apps / qualified_jobs * 100), 1) if qualified_jobs > 0 else 0.0,
                    "drop_off_pct": round(((qualified_jobs - submitted_apps) / qualified_jobs * 100), 1) if qualified_jobs > 0 else 0.0,
                },
                {
                    "stage_id": "responses",
                    "label": "Responses & Review",
                    "cohort_type": "APPLICATION",
                    "count": responded_apps,
                    "conversion_pct": round((responded_apps / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0,
                    "drop_off_pct": round(((submitted_apps - responded_apps) / submitted_apps * 100), 1) if submitted_apps > 0 else 0.0,
                },
                {
                    "stage_id": "interviews",
                    "label": "Interviews Scheduled",
                    "cohort_type": "APPLICATION",
                    "count": interviewed_apps,
                    "conversion_pct": round((interviewed_apps / responded_apps * 100), 1) if responded_apps > 0 else 0.0,
                    "drop_off_pct": round(((responded_apps - interviewed_apps) / responded_apps * 100), 1) if responded_apps > 0 else 0.0,
                },
                {
                    "stage_id": "offers",
                    "label": "Offers Received",
                    "cohort_type": "APPLICATION",
                    "count": offer_apps,
                    "conversion_pct": round((offer_apps / interviewed_apps * 100), 1) if interviewed_apps > 0 else 0.0,
                    "drop_off_pct": round(((interviewed_apps - offer_apps) / interviewed_apps * 100), 1) if interviewed_apps > 0 else 0.0,
                },
            ]

            return {
                "discovery_cohort_count": discovered_jobs,
                "application_cohort_count": submitted_apps,
                "stages": stages,
            }

    def get_time_series_trend(self, f: Optional[AnalyticsFilter] = None) -> Dict[str, Any]:
        """Calculates time series trend for applications, responses, and interviews."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        # Default fallback to 30 days if unbounded
        if not start_date or not end_date:
            start_date, end_date = get_local_date_bounds("30D")

        # Determine bucketing: daily if <= 35 days, else weekly
        total_days = max(1, (end_date - start_date).days + 1)
        bucket_by_week = total_days > 35

        with get_db_session(self._session_factory) as session:
            # Query all matching applications with timestamps in range
            date_col = func.coalesce(Application.applied_at, Application.created_at)
            stmt = (
                select(
                    Application.id,
                    date_col.label("app_date"),
                    Application.status,
                )
                .join(Job, Application.job_id == Job.id)
            )
            stmt = self._apply_application_filters(stmt, f, start_date, end_date)
            rows = session.execute(stmt).all()

            # Query communications and interviews for these applications
            app_ids = [r[0] for r in rows]

            # Inbound responses mapping
            resp_apps = set()
            if app_ids:
                q_r = select(Communication.application_id).where(
                    Communication.application_id.in_(app_ids),
                    Communication.direction == "INBOUND",
                )
                resp_apps = set(session.scalars(q_r).all())

            # Interviews mapping
            iv_apps = set()
            if app_ids:
                q_i = select(Interview.application_id).where(Interview.application_id.in_(app_ids))
                iv_apps = set(session.scalars(q_i).all())

            # Generate buckets
            bucket_labels: List[str] = []
            apps_counts: List[int] = []
            resp_counts: List[int] = []
            iv_counts: List[int] = []

            if not bucket_by_week:
                # Daily buckets
                day_buckets: Dict[str, Dict[str, int]] = {}
                cur = start_date
                while cur <= end_date:
                    key = cur.strftime("%Y-%m-%d")
                    label = cur.strftime("%b %d")
                    day_buckets[key] = {"apps": 0, "resp": 0, "iv": 0, "label": label}
                    cur += timedelta(days=1)

                for app_id, dt_val, status in rows:
                    if dt_val:
                        key = dt_val.strftime("%Y-%m-%d")
                        if key in day_buckets:
                            day_buckets[key]["apps"] += 1
                            if app_id in resp_apps or status in PROGRESSED_STATUSES:
                                day_buckets[key]["resp"] += 1
                            if app_id in iv_apps:
                                day_buckets[key]["iv"] += 1

                for k, data in day_buckets.items():
                    bucket_labels.append(data["label"])
                    apps_counts.append(data["apps"])
                    resp_counts.append(data["resp"])
                    iv_counts.append(data["iv"])
            else:
                # Weekly buckets
                cur = start_date
                while cur <= end_date:
                    w_end = min(end_date, cur + timedelta(days=6))
                    label = f"{cur.strftime('%b %d')}-{w_end.strftime('%d')}"
                    bucket_labels.append(label)

                    w_apps = 0
                    w_resp = 0
                    w_iv = 0
                    for app_id, dt_val, status in rows:
                        if dt_val and cur <= dt_val <= w_end:
                            w_apps += 1
                            if app_id in resp_apps or status in PROGRESSED_STATUSES:
                                w_resp += 1
                            if app_id in iv_apps:
                                w_iv += 1

                    apps_counts.append(w_apps)
                    resp_counts.append(w_resp)
                    iv_counts.append(w_iv)
                    cur += timedelta(days=7)

            return {
                "x_labels": bucket_labels,
                "series": [
                    {"id": "submitted", "label": "Submitted", "color_hex": "#FF5F15", "values": apps_counts},
                    {"id": "responses", "label": "Responses / Progression", "color_hex": "#38BDF8", "values": resp_counts},
                    {"id": "interviews", "label": "Interviews", "color_hex": "#A78BFA", "values": iv_counts},
                ],
                "total_points": len(bucket_labels),
            }

    def get_platform_performance(self, f: Optional[AnalyticsFilter] = None) -> List[Dict[str, Any]]:
        """Calculates factual comparison metrics across platforms with safe division."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)
        platforms = ["linkedin", "naukri", "indeed", "foundit", "glassdoor", "manual"]
        comparison: List[Dict[str, Any]] = []

        with get_db_session(self._session_factory) as session:
            for plat in platforms:
                # 1. Jobs discovered on this platform
                q_j = select(func.count(Job.id)).where(Job.platform == plat)
                if start_date:
                    q_j = q_j.where(Job.created_at >= start_date)
                if end_date:
                    q_j = q_j.where(Job.created_at <= end_date)
                jobs_count = session.scalar(q_j) or 0

                # 2. Submitted applications for jobs on this platform
                q_a = (
                    select(func.count(func.distinct(Application.id)))
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat)
                )
                q_a = self._apply_application_filters(q_a, f, start_date, end_date)
                apps_count = session.scalar(q_a) or 0

                # 3. Direct Recruiter Responses
                q_dr = (
                    select(func.count(func.distinct(Communication.application_id)))
                    .join(Application, Communication.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat, Communication.direction == "INBOUND")
                )
                q_dr = self._apply_application_filters(q_dr, f, start_date, end_date)
                direct_resp_count = session.scalar(q_dr) or 0

                # 4. Pipeline progression
                q_pr = (
                    select(func.count(func.distinct(Application.id)))
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat, Application.status.in_(PROGRESSED_STATUSES))
                )
                q_pr = self._apply_application_filters(q_pr, f, start_date, end_date)
                prog_count = session.scalar(q_pr) or 0

                # 5. Distinct interviews
                q_i = (
                    select(func.count(func.distinct(Interview.application_id)))
                    .join(Application, Interview.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat)
                )
                q_i = self._apply_application_filters(q_i, f, start_date, end_date)
                iv_count = session.scalar(q_i) or 0

                # 6. Distinct offers
                q_o = (
                    select(func.count(func.distinct(Offer.application_id)))
                    .join(Application, Offer.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Job.platform == plat)
                )
                q_o = self._apply_application_filters(q_o, f, start_date, end_date)
                offers_count = session.scalar(q_o) or 0

                # Rates
                app_rate = round((apps_count / jobs_count * 100), 1) if jobs_count > 0 else 0.0
                resp_rate = round((direct_resp_count / apps_count * 100), 1) if apps_count > 0 else 0.0
                iv_rate = round((iv_count / apps_count * 100), 1) if apps_count > 0 else 0.0
                offer_rate = round((offers_count / apps_count * 100), 1) if apps_count > 0 else 0.0

                comparison.append({
                    "platform_key": plat,
                    "platform": plat.title(),
                    "jobs": jobs_count,
                    "applications": apps_count,
                    "responses": direct_resp_count,
                    "progression": prog_count,
                    "interviews": iv_count,
                    "offers": offers_count,
                    "application_rate": app_rate,
                    "response_rate": resp_rate,
                    "interview_rate": iv_rate,
                    "offer_rate": offer_rate,
                })

        return comparison

    def get_method_distribution(self, f: Optional[AnalyticsFilter] = None) -> List[Dict[str, Any]]:
        """Calculates volume and response performance by Application.application_type."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)
        methods = ["EASY_APPLY", "DIRECT", "QUESTIONNAIRE", "MANUAL"]
        results: List[Dict[str, Any]] = []

        with get_db_session(self._session_factory) as session:
            for meth in methods:
                # 1. Total applications for this method
                q_a = (
                    select(func.count(func.distinct(Application.id)))
                    .join(Job, Application.job_id == Job.id)
                    .where(Application.application_type == meth)
                )
                q_a = self._apply_application_filters(q_a, f, start_date, end_date)
                apps_cnt = session.scalar(q_a) or 0

                # 2. Inbound responses or progression
                q_r = (
                    select(func.count(func.distinct(Application.id)))
                    .join(Job, Application.job_id == Job.id)
                    .outerjoin(Communication, Communication.application_id == Application.id)
                    .where(
                        Application.application_type == meth,
                        (Communication.direction == "INBOUND") | (Application.status.in_(PROGRESSED_STATUSES)),
                    )
                )
                q_r = self._apply_application_filters(q_r, f, start_date, end_date)
                resp_cnt = session.scalar(q_r) or 0

                # 3. Interviews
                q_i = (
                    select(func.count(func.distinct(Interview.application_id)))
                    .join(Application, Interview.application_id == Application.id)
                    .join(Job, Application.job_id == Job.id)
                    .where(Application.application_type == meth)
                )
                q_i = self._apply_application_filters(q_i, f, start_date, end_date)
                iv_cnt = session.scalar(q_i) or 0

                rate = round((resp_cnt / apps_cnt * 100), 1) if apps_cnt > 0 else 0.0

                results.append({
                    "method_key": meth,
                    "method": meth.replace("_", " ").title(),
                    "applications": apps_cnt,
                    "responses": resp_cnt,
                    "interviews": iv_cnt,
                    "response_rate": rate,
                })

        return results

    def get_aging_distribution(self, f: Optional[AnalyticsFilter] = None) -> Dict[str, int]:
        """Calculates elapsed days since applied_at for currently active applications."""
        f = f or AnalyticsFilter()
        now = utc_now()
        buckets = {
            "< 3 days": 0,
            "3–7 days": 0,
            "8–14 days": 0,
            "15–30 days": 0,
            "30–60 days": 0,
            "60+ days": 0,
        }

        with get_db_session(self._session_factory) as session:
            stmt = (
                select(func.coalesce(Application.applied_at, Application.created_at))
                .join(Job, Application.job_id == Job.id)
                .where(Application.status.in_(ACTIVE_AGING_STATUSES))
            )
            if f.platform and f.platform.strip().lower() not in ["all", ""]:
                stmt = stmt.where(Job.platform == f.platform.strip().lower())

            dates = session.scalars(stmt).all()
            for dt in dates:
                if not dt:
                    continue
                # Ensure dt is timezone aware in UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                days = (now - dt).total_seconds() / 86400.0

                if days < 3:
                    buckets["< 3 days"] += 1
                elif days <= 7:
                    buckets["3–7 days"] += 1
                elif days <= 14:
                    buckets["8–14 days"] += 1
                elif days <= 30:
                    buckets["15–30 days"] += 1
                elif days <= 60:
                    buckets["30–60 days"] += 1
                else:
                    buckets["60+ days"] += 1

        return buckets

    def get_response_time_stats(self, f: Optional[AnalyticsFilter] = None) -> ResponseTimeStats:
        """Calculates response latency with transparent response_source disclosure."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        dist_template = {
            "< 1 day": 0,
            "1–3 days": 0,
            "4–7 days": 0,
            "8–14 days": 0,
            "15–30 days": 0,
            "30+ days": 0,
        }

        with get_db_session(self._session_factory) as session:
            # 1. Try actual inbound communications first
            q_comm = (
                select(
                    func.coalesce(Application.applied_at, Application.created_at).label("applied"),
                    func.min(Communication.occurred_at).label("responded"),
                )
                .join(Communication, Communication.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .where(Communication.direction == "INBOUND")
                .group_by(Application.id)
            )
            q_comm = self._apply_application_filters(q_comm, f, start_date, end_date)
            comm_rows = session.execute(q_comm).all()

            latencies: List[float] = []
            for app_dt, resp_dt in comm_rows:
                if app_dt and resp_dt:
                    sec = (resp_dt - app_dt).total_seconds()
                    days = max(0.0, round(sec / 86400.0, 1))
                    latencies.append(days)

            if len(latencies) >= 3:
                return self._compile_response_stats(latencies, "COMMUNICATION", dist_template)

            # 2. Try status transition proxy if communications insufficient
            q_hist = (
                select(
                    func.coalesce(Application.applied_at, Application.created_at).label("applied"),
                    func.min(ApplicationStatusHistory.changed_at).label("responded"),
                )
                .join(ApplicationStatusHistory, ApplicationStatusHistory.application_id == Application.id)
                .join(Job, Application.job_id == Job.id)
                .where(ApplicationStatusHistory.new_status.in_(PROGRESSED_STATUSES))
                .group_by(Application.id)
            )
            q_hist = self._apply_application_filters(q_hist, f, start_date, end_date)
            hist_rows = session.execute(q_hist).all()

            proxy_latencies: List[float] = []
            for app_dt, resp_dt in hist_rows:
                if app_dt and resp_dt:
                    sec = (resp_dt - app_dt).total_seconds()
                    days = max(0.0, round(sec / 86400.0, 1))
                    proxy_latencies.append(days)

            if len(proxy_latencies) >= 3:
                return self._compile_response_stats(proxy_latencies, "STATUS_TRANSITION_PROXY", dist_template)

            # 3. Insufficient data
            return ResponseTimeStats(
                has_sufficient_data=False,
                sample_count=len(latencies) or len(proxy_latencies),
                source_type="INSUFFICIENT_DATA",
                distribution=dist_template,
            )

    def _compile_response_stats(
        self,
        latencies: List[float],
        source_type: str,
        distribution: Dict[str, int],
    ) -> ResponseTimeStats:
        """Helper to compute mean, median, min, max, and bucketed distribution."""
        dist = dict(distribution)
        for d in latencies:
            if d < 1.0:
                dist["< 1 day"] += 1
            elif d <= 3.0:
                dist["1–3 days"] += 1
            elif d <= 7.0:
                dist["4–7 days"] += 1
            elif d <= 14.0:
                dist["8–14 days"] += 1
            elif d <= 30.0:
                dist["15–30 days"] += 1
            else:
                dist["30+ days"] += 1

        return ResponseTimeStats(
            has_sufficient_data=True,
            sample_count=len(latencies),
            source_type=source_type,
            avg_days=round(statistics.mean(latencies), 1),
            median_days=round(statistics.median(latencies), 1),
            fastest_days=round(min(latencies), 1),
            slowest_days=round(max(latencies), 1),
            distribution=dist,
        )

    def get_role_company_breakdown(
        self,
        f: Optional[AnalyticsFilter] = None,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Calculates application-centric distribution of job titles and companies."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        with get_db_session(self._session_factory) as session:
            # Top Applied Roles
            q_roles = (
                select(Job.title, func.count(Application.id).label("cnt"))
                .join(Job, Application.job_id == Job.id)
                .group_by(Job.title)
                .order_by(func.count(Application.id).desc())
            )
            q_roles = self._apply_application_filters(q_roles, f, start_date, end_date)
            role_rows = session.execute(q_roles.limit(limit)).all()

            # Top Applied Companies
            q_comp = (
                select(Job.company_raw, func.count(Application.id).label("cnt"))
                .join(Job, Application.job_id == Job.id)
                .group_by(Job.company_raw)
                .order_by(func.count(Application.id).desc())
            )
            q_comp = self._apply_application_filters(q_comp, f, start_date, end_date)
            comp_rows = session.execute(q_comp.limit(limit)).all()

            return {
                "roles": [{"title": r[0], "count": r[1]} for r in role_rows],
                "companies": [{"company": c[0], "count": c[1]} for c in comp_rows],
            }

    def export_to_csv(self, f: Optional[AnalyticsFilter] = None) -> str:
        """Exports the exact matching application dataset for the active filter to CSV."""
        f = f or AnalyticsFilter()
        start_date, end_date = self.resolve_filter_dates(f)

        lines = [
            "# JobPilot Recruitment Analytics Export",
            f"# Generated At: {utc_now().isoformat()}Z",
            f"# Date Filter: {f.date_preset} ({start_date.isoformat() if start_date else 'ALL'} to {end_date.isoformat() if end_date else 'ALL'})",
            f"# Platform Filter: {f.platform or 'ALL'}",
            f"# Method Filter: {f.application_method or 'ALL'}",
            f"# Status Filter: {f.status or 'ALL'}",
            "Application ID,Job Title,Company,Platform,Application Method,Status,Applied At,Has Inbound Response,Interviews Count,Has Offer",
        ]

        with get_db_session(self._session_factory) as session:
            stmt = select(Application).join(Job, Application.job_id == Job.id)
            stmt = self._apply_application_filters(stmt, f, start_date, end_date)
            apps = session.scalars(stmt).all()

            for a in apps:
                title = (a.job.title or "").replace('"', '""')
                comp = (a.job.company_raw or "").replace('"', '""')
                plat = a.job.platform or "unknown"
                meth = a.application_type or "EASY_APPLY"
                st = a.status or "SUBMITTED"
                app_date = a.applied_at.isoformat() if a.applied_at else (a.created_at.isoformat() if a.created_at else "")

                # Check inbound response
                has_inbound = any(c.direction == "INBOUND" for c in (a.communications or []))
                iv_cnt = len(a.interviews or [])
                has_offer = "YES" if a.offer else "NO"

                lines.append(
                    f'{a.id},"{title}","{comp}",{plat},{meth},{st},{app_date},{"YES" if has_inbound else "NO"},{iv_cnt},{has_offer}'
                )

        return "\n".join(lines)

    # -----------------------------------------------------------------------
    # Backwards Compatibility Methods (for existing callers and legacy tests)
    # -----------------------------------------------------------------------

    def get_funnel_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Calculates legacy funnel metrics dictionary for backward compatibility."""
        f = AnalyticsFilter(start_date=start_date, end_date=end_date)
        funnel = self.get_funnel_flow(f)
        summary = self.get_summary_metrics(f)

        return {
            "total_jobs": funnel["discovery_cohort_count"],
            "submitted_applications": summary["submitted_applications"].value,
            "responded_applications": summary["progressed_applications"],
            "interviewed_applications": summary["interviewed_applications"],
            "offer_applications": summary["offer_applications"],
            "application_rate": round(
                (summary["submitted_applications"].value / funnel["discovery_cohort_count"] * 100), 1
            ) if funnel["discovery_cohort_count"] > 0 else 0.0,
            "response_rate": summary["progression_rate"],
            "interview_rate": summary["interview_rate"],
            "offer_rate": summary["offer_rate"],
        }

    def get_platform_comparison(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Calculates legacy platform comparison list for backward compatibility."""
        f = AnalyticsFilter(start_date=start_date, end_date=end_date)
        return self.get_platform_performance(f)

    def get_stage_distribution(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, int]:
        """Calculates legacy stage distribution dictionary for backward compatibility."""
        with get_db_session(self._session_factory) as session:
            stmt = select(Application.status, func.count(Application.id)).group_by(Application.status)
            if start_date:
                stmt = stmt.where(Application.created_at >= start_date)
            if end_date:
                stmt = stmt.where(Application.created_at <= end_date)

            rows = session.execute(stmt).all()
            counts = {status: cnt for status, cnt in rows}

            return {
                "APPLYING": counts.get("APPLYING", 0),
                "SUBMITTED": counts.get("SUBMITTED", 0),
                "UNDER_REVIEW": counts.get("UNDER_REVIEW", 0),
                "SHORTLISTED": counts.get("SHORTLISTED", 0) + counts.get("RECRUITER_CONTACTED", 0),
                "INTERVIEW": counts.get("INTERVIEW", 0) + counts.get("ASSESSMENT", 0),
                "OFFER": counts.get("OFFER", 0),
                "CLOSED": counts.get("REJECTED", 0) + counts.get("WITHDRAWN", 0),
            }
