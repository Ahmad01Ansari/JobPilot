"""Thin SearchProvider adapter for Job Applications."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.application import Application
from app.db.models.job import Job
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class ApplicationSearchProvider(SearchProvider):
    """Searches Application records joined with Job details."""

    @property
    def category_key(self) -> str:
        return "applications"

    @property
    def display_name(self) -> str:
        return "Applications"

    @property
    def default_route(self) -> str:
        return "applications"

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
        elif clean_q.startswith("app-") and clean_q[4:].isdigit():
            exact_id = int(clean_q[4:])

        stmt = select(Application).join(Application.job)
        if exact_id is not None:
            stmt = stmt.where(Application.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Job.title.ilike(pattern),
                        Job.company_raw.ilike(pattern),
                        Application.status.ilike(pattern),
                        Application.notes.ilike(pattern),
                        Application.failure_reason.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = (
            stmt.options(joinedload(Application.job))
            .order_by(Application.id.desc())
            .limit(limit * 3)
        )
        records = session.execute(stmt).scalars().all()

        badge_type_map = {
            "SUBMITTED": "success",
            "APPLYING": "info",
            "FAILED": "danger",
            "MANUAL_REQUIRED": "warning",
            "INTERVIEW": "success",
            "OFFER": "success",
            "REJECTED": "neutral",
            "WITHDRAWN": "neutral",
        }

        results: List[SearchResult] = []
        for app in records:
            job_title = app.job.title if app.job else f"Application #{app.id}"
            company = app.job.company_raw if app.job else "Unknown Company"

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=app.id,
                primary_text=job_title,
                secondary_text=company,
                tertiary_text=app.status or "",
                long_text=app.notes or "",
                prefix_tags=["APP", "APPLICATION"],
            )

            if score > 0 or exact_id == app.id:
                date_str = app.applied_at.strftime("%b %d, %Y") if app.applied_at else "Draft / Unsubmitted"
                results.append(
                    SearchResult(
                        entity_type="application",
                        entity_id=app.id,
                        category=self.display_name,
                        title=job_title,
                        subtitle=f"{company} • {date_str} • Status: {app.status}",
                        route=self.default_route,
                        action="filter",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=app.status,
                        badge_variant=badge_type_map.get(app.status, "neutral"),
                        metadata={"job_id": app.job_id, "status": app.status},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
