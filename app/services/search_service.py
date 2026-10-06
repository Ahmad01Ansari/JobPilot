"""Global multi-entity search service across Jobs, Applications, Companies, Contacts, and Interviews."""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload, sessionmaker

from app.db.models import Application, Company, Contact, Interview, Job
from app.db.session import SessionLocal, get_db_session

logger = logging.getLogger(__name__)


@dataclass
class SearchResultItem:
    """Individual item returned from a global search query."""

    entity_type: str  # "job", "application", "company", "contact", "interview"
    entity_id: int
    title: str
    subtitle: str
    badge_text: str
    badge_type: str = "primary"  # "primary", "success", "warning", "info", "neutral"
    target_page: str = "jobs"  # "jobs", "applications", "interviews", "followups"
    extra_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlobalSearchResult:
    """Consolidated results of a multi-entity search query."""

    query: str
    total_count: int
    items: List[SearchResultItem]
    categories: Dict[str, int] = field(default_factory=dict)


class SearchService:
    """Coordinates fast multi-entity search across the application database."""

    def __init__(self, session_factory: Optional[sessionmaker] = None):
        self._session_factory = session_factory or SessionLocal

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit_per_category: int = 10,
    ) -> GlobalSearchResult:
        """Performs a unified cross-entity search with optional category filter.

        Args:
            query: User search text.
            category: Optional category filter ('all', 'job', 'application', 'company', 'contact', 'interview').
            limit_per_category: Max results per individual category.
        """
        raw_query = str(query or "").strip()
        cat_clean = (category or "all").strip().lower()
        if not raw_query:
            return GlobalSearchResult(query="", total_count=0, items=[], categories={})

        tokens = [t.strip() for t in raw_query.split() if t.strip()]
        if not tokens:
            return GlobalSearchResult(query="", total_count=0, items=[], categories={})

        items: List[SearchResultItem] = []
        counts: Dict[str, int] = {
            "job": 0,
            "application": 0,
            "company": 0,
            "contact": 0,
            "interview": 0,
        }

        with get_db_session(self._session_factory) as session:
            # 1. Jobs
            if cat_clean in ("all", "job", "jobs"):
                job_items = self._search_jobs(session, tokens, limit_per_category)
                counts["job"] = len(job_items)
                items.extend(job_items)

            # 2. Applications
            if cat_clean in ("all", "application", "applications", "apps"):
                app_items = self._search_applications(session, tokens, limit_per_category)
                counts["application"] = len(app_items)
                items.extend(app_items)

            # 3. Companies
            if cat_clean in ("all", "company", "companies"):
                company_items = self._search_companies(session, tokens, limit_per_category)
                counts["company"] = len(company_items)
                items.extend(company_items)

            # 4. Contacts / Recruiters
            if cat_clean in ("all", "contact", "contacts", "recruiter", "recruiters"):
                contact_items = self._search_contacts(session, tokens, limit_per_category)
                counts["contact"] = len(contact_items)
                items.extend(contact_items)

            # 5. Interviews
            if cat_clean in ("all", "interview", "interviews"):
                interview_items = self._search_interviews(session, tokens, limit_per_category)
                counts["interview"] = len(interview_items)
                items.extend(interview_items)

        return GlobalSearchResult(
            query=raw_query,
            total_count=len(items),
            items=items,
            categories=counts,
        )

    def _search_jobs(self, session, tokens: List[str], limit: int) -> List[SearchResultItem]:
        """Searches Job records matching all tokens across title, company, location, or skills."""
        stmt = select(Job)
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(pattern),
                    Job.company_raw.ilike(pattern),
                    Job.location.ilike(pattern),
                    Job.experience_text.ilike(pattern),
                    Job.description.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Job.id.desc()).limit(limit)
        results = session.execute(stmt).scalars().all()

        items = []
        for job in results:
            loc = job.location or "Location Unspecified"
            plat = job.platform.capitalize() if job.platform else "Direct"
            items.append(
                SearchResultItem(
                    entity_type="job",
                    entity_id=job.id,
                    title=job.title,
                    subtitle=f"{job.company_raw} • {loc} • {plat}",
                    badge_text="Job",
                    badge_type="primary",
                    target_page="jobs",
                    extra_data={"job_id": job.id, "platform": job.platform},
                )
            )
        return items

    def _search_applications(self, session, tokens: List[str], limit: int) -> List[SearchResultItem]:
        """Searches Application records joined with Job."""
        stmt = select(Application).join(Application.job)
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    Job.title.ilike(pattern),
                    Job.company_raw.ilike(pattern),
                    Application.status.ilike(pattern),
                    Application.notes.ilike(pattern),
                    Application.failure_reason.ilike(pattern),
                )
            )
        stmt = (
            stmt.options(joinedload(Application.job))
            .order_by(Application.id.desc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()

        badge_type_map = {
            "SUBMITTED": "success",
            "APPLYING": "info",
            "FAILED": "warning",
            "MANUAL_REQUIRED": "warning",
            "INTERVIEW": "success",
            "OFFER": "success",
            "REJECTED": "neutral",
        }

        items = []
        for app in results:
            title = app.job.title if app.job else f"Application #{app.id}"
            company = app.job.company_raw if app.job else "Unknown Company"
            date_str = app.applied_at.strftime("%b %d, %Y") if app.applied_at else "Not submitted"
            items.append(
                SearchResultItem(
                    entity_type="application",
                    entity_id=app.id,
                    title=title,
                    subtitle=f"{company} • Applied: {date_str} • Status: {app.status}",
                    badge_text=app.status,
                    badge_type=badge_type_map.get(app.status, "primary"),
                    target_page="applications",
                    extra_data={"application_id": app.id, "status": app.status},
                )
            )
        return items

    def _search_companies(self, session, tokens: List[str], limit: int) -> List[SearchResultItem]:
        """Searches Company records."""
        stmt = select(Company)
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    Company.name.ilike(pattern),
                    Company.location.ilike(pattern),
                    Company.industry.ilike(pattern),
                    Company.notes.ilike(pattern),
                    Company.website.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Company.id.desc()).limit(limit)
        results = session.execute(stmt).scalars().all()

        items = []
        for company in results:
            industry = company.industry or "Industry Unspecified"
            loc = company.location or "Location Unspecified"
            items.append(
                SearchResultItem(
                    entity_type="company",
                    entity_id=company.id,
                    title=company.name,
                    subtitle=f"{industry} • {loc}",
                    badge_text="Company",
                    badge_type="info",
                    target_page="jobs",
                    extra_data={"company_id": company.id, "name": company.name},
                )
            )
        return items

    def _search_contacts(self, session, tokens: List[str], limit: int) -> List[SearchResultItem]:
        """Searches Contact records with joined Company."""
        stmt = select(Contact).outerjoin(Contact.company)
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(pattern),
                    Contact.email.ilike(pattern),
                    Contact.phone.ilike(pattern),
                    Contact.designation.ilike(pattern),
                    Contact.notes.ilike(pattern),
                    Company.name.ilike(pattern),
                )
            )
        stmt = (
            stmt.options(joinedload(Contact.company))
            .order_by(Contact.id.desc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()

        items = []
        for contact in results:
            comp_name = contact.company.name if contact.company else "Independent"
            desig = contact.designation or "Recruiter"
            email_info = f" • {contact.email}" if contact.email else ""
            items.append(
                SearchResultItem(
                    entity_type="contact",
                    entity_id=contact.id,
                    title=contact.name,
                    subtitle=f"{desig} @ {comp_name}{email_info}",
                    badge_text="Contact",
                    badge_type="warning",
                    target_page="interviews",
                    extra_data={"contact_id": contact.id, "email": contact.email},
                )
            )
        return items

    def _search_interviews(self, session, tokens: List[str], limit: int) -> List[SearchResultItem]:
        """Searches Interview records joined with Application and Job."""
        stmt = (
            select(Interview)
            .join(Interview.application)
            .outerjoin(Application.job)
        )
        for token in tokens:
            pattern = f"%{token}%"
            stmt = stmt.where(
                or_(
                    Interview.round_name.ilike(pattern),
                    Interview.interviewer.ilike(pattern),
                    Interview.notes.ilike(pattern),
                    Interview.meeting_link.ilike(pattern),
                    Job.title.ilike(pattern),
                    Job.company_raw.ilike(pattern),
                )
            )
        stmt = (
            stmt.options(
                joinedload(Interview.application).joinedload(Application.job)
            )
            .order_by(Interview.scheduled_at.desc())
            .limit(limit)
        )
        results = session.execute(stmt).scalars().all()

        badge_type_map = {
            "SCHEDULED": "info",
            "COMPLETED": "success",
            "CANCELLED": "neutral",
            "NO_SHOW": "warning",
        }

        items = []
        for interview in results:
            app = interview.application
            job = app.job if app else None
            company = job.company_raw if job else "Unknown Company"
            date_str = (
                interview.scheduled_at.strftime("%b %d, %Y @ %H:%M")
                if interview.scheduled_at
                else "Unscheduled"
            )
            items.append(
                SearchResultItem(
                    entity_type="interview",
                    entity_id=interview.id,
                    title=f"{interview.round_name} Round (Round {interview.round_number})",
                    subtitle=f"{company} • Scheduled: {date_str} • Mode: {interview.mode}",
                    badge_text=interview.status,
                    badge_type=badge_type_map.get(interview.status, "primary"),
                    target_page="interviews",
                    extra_data={"interview_id": interview.id, "status": interview.status},
                )
            )
        return items
