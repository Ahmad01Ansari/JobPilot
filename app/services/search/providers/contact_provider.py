"""Thin SearchProvider adapter for Professional Contacts & Recruiters."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.company import Company
from app.db.models.contact import Contact
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class ContactSearchProvider(SearchProvider):
    """Searches Recruiter and Professional Contacts."""

    @property
    def category_key(self) -> str:
        return "contacts"

    @property
    def display_name(self) -> str:
        return "Contacts"

    @property
    def default_route(self) -> str:
        return "outreach"  # Contacts route to Outreach workspace

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
        elif clean_q.startswith("cont-") and clean_q[5:].isdigit():
            exact_id = int(clean_q[5:])

        stmt = select(Contact).outerjoin(Contact.company)
        if exact_id is not None:
            stmt = stmt.where(Contact.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Contact.name.ilike(pattern),
                        Contact.email.ilike(pattern),
                        Contact.phone.ilike(pattern),
                        Contact.designation.ilike(pattern),
                        Contact.notes.ilike(pattern),
                        Company.name.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = (
            stmt.options(joinedload(Contact.company))
            .order_by(Contact.id.desc())
            .limit(limit * 3)
        )
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for contact in records:
            comp_name = contact.company.name if contact.company else "Independent"
            desig = contact.designation or "Recruiter"

            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=contact.id,
                primary_text=contact.name or "",
                secondary_text=comp_name,
                tertiary_text=contact.email or "",
                long_text=contact.notes or "",
                prefix_tags=["CONT", "CONTACT"],
            )

            if score > 0 or exact_id == contact.id:
                email_part = f" • {contact.email}" if contact.email else ""
                results.append(
                    SearchResult(
                        entity_type="contact",
                        entity_id=contact.id,
                        category=self.display_name,
                        title=contact.name or f"Contact #{contact.id}",
                        subtitle=f"{desig} @ {comp_name}{email_part}",
                        route=self.default_route,
                        action="focus",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text="Contact",
                        badge_variant="warning",
                        metadata={"email": contact.email, "company": comp_name},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
