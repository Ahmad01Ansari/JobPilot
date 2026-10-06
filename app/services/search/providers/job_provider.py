"""Thin SearchProvider adapter for Job listings."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.job import Job
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class JobSearchProvider(SearchProvider):
    """Searches discovered and qualified Job records."""

    @property
    def category_key(self) -> str:
        return "jobs"

    @property
    def display_name(self) -> str:
        return "Jobs"

    @property
    def default_route(self) -> str:
        return "jobs"

    def search(
        self,
        session: Session,
        tokens: List[str],
        raw_query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        if not tokens and not raw_query:
            return []

        # Check numeric ID directly
        exact_id = None
        clean_q = raw_query.strip().casefold()
        if clean_q.isdigit():
            exact_id = int(clean_q)
        elif clean_q.startswith("job-") and clean_q[4:].isdigit():
            exact_id = int(clean_q[4:])

        stmt = select(Job)
        if exact_id is not None:
            stmt = stmt.where(Job.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Job.title.ilike(pattern),
                        Job.company_raw.ilike(pattern),
                        Job.location.ilike(pattern),
                        Job.experience_text.ilike(pattern),
                        Job.description.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        # Retrieve a bounded set of candidates for deterministic scoring
        stmt = stmt.order_by(Job.id.desc()).limit(limit * 3)
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for job in records:
            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=job.id,
                primary_text=job.title or "",
                secondary_text=job.company_raw or "",
                tertiary_text=job.location or "",
                long_text=job.description or "",
                prefix_tags=["JOB"],
            )

            if score > 0 or exact_id == job.id:
                loc = job.location or "Location Unspecified"
                plat = job.platform.capitalize() if job.platform else "Direct"
                results.append(
                    SearchResult(
                        entity_type="job",
                        entity_id=job.id,
                        category=self.display_name,
                        title=job.title or f"Job #{job.id}",
                        subtitle=f"{job.company_raw or 'Unknown Company'} • {loc} • {plat}",
                        route=self.default_route,
                        action="filter",  # JobsView isolates with 1-row exact filter
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=plat,
                        badge_variant="primary",
                        metadata={"platform": job.platform, "company": job.company_raw},
                    )
                )

        # Sort by deterministic hierarchy: score DESC, entity_id DESC
        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
