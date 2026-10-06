"""Thin SearchProvider adapter for Outreach Conversations & Messages."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.application import Application
from app.db.models.communication import Communication
from app.db.models.job import Job
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class OutreachSearchProvider(SearchProvider):
    """Searches Outreach communications, routing directly to the target conversation thread."""

    @property
    def category_key(self) -> str:
        return "outreach"

    @property
    def display_name(self) -> str:
        return "Outreach"

    @property
    def default_route(self) -> str:
        return "outreach"

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
        elif clean_q.startswith("conv-") and clean_q[5:].isdigit():
            exact_id = int(clean_q[5:])

        stmt = (
            select(Communication)
            .join(Communication.application)
            .outerjoin(Application.job)
        )
        if exact_id is not None:
            # Match either application_id (conversation id) or communication id
            stmt = stmt.where(
                or_(
                    Communication.application_id == exact_id,
                    Communication.id == exact_id,
                )
            )
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Communication.subject.ilike(pattern),
                        Communication.body_snippet.ilike(pattern),
                        Communication.sender_email.ilike(pattern),
                        Communication.recipient_email.ilike(pattern),
                        Job.company_raw.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = (
            stmt.options(joinedload(Communication.application).joinedload(Application.job))
            .order_by(Communication.id.desc())
            .limit(limit * 3)
        )
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        seen_conversations = set()

        for comm in records:
            app_id = comm.application_id
            if not app_id or app_id in seen_conversations:
                continue

            app = comm.application
            job = app.job if app else None
            company = job.company_raw if job else "Recruiter Outreach"
            title = comm.subject or f"Thread: {company}"

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=app_id,
                primary_text=title,
                secondary_text=company,
                tertiary_text=comm.sender_email or comm.recipient_email or "",
                long_text=comm.body_snippet or "",
                prefix_tags=["CONV", "OUTREACH"],
            )

            if score > 0 or exact_id in (app_id, comm.id):
                seen_conversations.add(app_id)
                results.append(
                    SearchResult(
                        entity_type="outreach",
                        entity_id=app_id,  # Conversation identity is application_id
                        category=self.display_name,
                        title=title,
                        subtitle=f"{company} • {comm.type} • {comm.direction}",
                        route=self.default_route,
                        action="focus",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=comm.direction,
                        badge_variant="info" if comm.direction == "INBOUND" else "primary",
                        metadata={"application_id": app_id, "communication_id": comm.id},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
