"""Thin SearchProvider adapter for Follow-up reminders."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.application import Application
from app.db.models.follow_up import FollowUp
from app.db.models.job import Job
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class FollowUpSearchProvider(SearchProvider):
    """Searches Follow-up reminders and scheduled tasks."""

    @property
    def category_key(self) -> str:
        return "followups"

    @property
    def display_name(self) -> str:
        return "Follow-ups"

    @property
    def default_route(self) -> str:
        return "followups"

    def search(
        self,
        session: Session,
        tokens: List[str],
        raw_query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        if not tokens and not raw_query:
            return []

        exact_id = None
        clean_q = raw_query.strip().casefold()
        if clean_q.isdigit():
            exact_id = int(clean_q)
        elif clean_q.startswith("fu-") and clean_q[3:].isdigit():
            exact_id = int(clean_q[3:])

        stmt = (
            select(FollowUp)
            .outerjoin(FollowUp.application)
            .outerjoin(Application.job)
        )
        if exact_id is not None:
            stmt = stmt.where(FollowUp.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        FollowUp.notes.ilike(pattern),
                        FollowUp.status.ilike(pattern),
                        Job.title.ilike(pattern),
                        Job.company_raw.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = (
            stmt.options(joinedload(FollowUp.application).joinedload(Application.job))
            .order_by(FollowUp.due_at.desc())
            .limit(limit * 3)
        )
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for fu in records:
            app = fu.application
            job = app.job if app else None
            company = job.company_raw if job else "General Follow-up"
            job_title = job.title if job else "Application Outreach"
            title = f"Follow-up: {job_title}"

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=fu.id,
                primary_text=title,
                secondary_text=company,
                tertiary_text=fu.status,
                long_text=fu.notes or "",
                prefix_tags=["FU", "FOLLOWUP"],
            )

            if score > 0 or exact_id == fu.id:
                due_str = fu.due_at.strftime("%b %d, %Y") if fu.due_at else "No Date"
                results.append(
                    SearchResult(
                        entity_type="followup",
                        entity_id=fu.id,
                        category=self.display_name,
                        title=title,
                        subtitle=f"{company} • Due: {due_str} • Status: {fu.status}",
                        route=self.default_route,
                        action="focus",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=fu.status,
                        badge_variant="warning" if fu.status in ("PENDING", "DUE") else "neutral",
                        metadata={"followup_id": fu.id, "application_id": fu.application_id},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
