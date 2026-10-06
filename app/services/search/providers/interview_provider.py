"""Thin SearchProvider adapter for Job Interviews."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.application import Application
from app.db.models.interview import Interview
from app.db.models.job import Job
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class InterviewSearchProvider(SearchProvider):
    """Searches scheduled and completed Interview rounds."""

    @property
    def category_key(self) -> str:
        return "interviews"

    @property
    def display_name(self) -> str:
        return "Interviews"

    @property
    def default_route(self) -> str:
        return "interviews"

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
        elif clean_q.startswith("iv-") and clean_q[3:].isdigit():
            exact_id = int(clean_q[3:])
        elif clean_q.startswith("interview-") and clean_q[10:].isdigit():
            exact_id = int(clean_q[10:])

        stmt = (
            select(Interview)
            .join(Interview.application)
            .outerjoin(Application.job)
        )
        if exact_id is not None:
            stmt = stmt.where(Interview.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Interview.round_name.ilike(pattern),
                        Interview.interviewer.ilike(pattern),
                        Interview.notes.ilike(pattern),
                        Interview.meeting_link.ilike(pattern),
                        Job.title.ilike(pattern),
                        Job.company_raw.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = (
            stmt.options(joinedload(Interview.application).joinedload(Application.job))
            .order_by(Interview.scheduled_at.desc())
            .limit(limit * 3)
        )
        records = session.execute(stmt).scalars().all()

        badge_type_map = {
            "SCHEDULED": "info",
            "COMPLETED": "success",
            "CANCELLED": "neutral",
            "NO_SHOW": "warning",
        }

        results: List[SearchResult] = []
        for iv in records:
            app = iv.application
            job = app.job if app else None
            company = job.company_raw if job else "Unknown Company"
            round_title = f"{iv.round_name or 'Interview'} (Round {iv.round_number})"

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=iv.id,
                primary_text=round_title,
                secondary_text=company,
                tertiary_text=iv.interviewer or "",
                long_text=iv.notes or "",
                prefix_tags=["IV", "INTERVIEW"],
            )

            if score > 0 or exact_id == iv.id:
                date_str = (
                    iv.scheduled_at.strftime("%b %d, %Y @ %H:%M")
                    if iv.scheduled_at
                    else "Date Unscheduled"
                )
                results.append(
                    SearchResult(
                        entity_type="interview",
                        entity_id=iv.id,
                        category=self.display_name,
                        title=round_title,
                        subtitle=f"{company} • {date_str} • Mode: {iv.mode or 'Online'}",
                        route=self.default_route,
                        action="open",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=iv.status or "SCHEDULED",
                        badge_variant=badge_type_map.get(iv.status, "primary"),
                        metadata={"application_id": iv.application_id, "status": iv.status},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
