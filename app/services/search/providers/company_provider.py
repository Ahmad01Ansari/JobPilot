"""Thin SearchProvider adapter for Companies."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.company import Company
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class CompanySearchProvider(SearchProvider):
    """Searches target Company organizations."""

    @property
    def category_key(self) -> str:
        return "companies"

    @property
    def display_name(self) -> str:
        return "Companies"

    @property
    def default_route(self) -> str:
        return "jobs"  # Companies route to Jobs filtered by company name

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
        elif clean_q.startswith("comp-") and clean_q[5:].isdigit():
            exact_id = int(clean_q[5:])

        stmt = select(Company)
        if exact_id is not None:
            stmt = stmt.where(Company.id == exact_id)
        else:
            filters = []
            for token in tokens:
                pattern = f"%{token}%"
                filters.append(
                    or_(
                        Company.name.ilike(pattern),
                        Company.location.ilike(pattern),
                        Company.industry.ilike(pattern),
                        Company.notes.ilike(pattern),
                        Company.website.ilike(pattern),
                    )
                )
            if filters:
                stmt = stmt.where(*filters)

        stmt = stmt.order_by(Company.id.desc()).limit(limit * 3)
        records = session.execute(stmt).scalars().all()

        results: List[SearchResult] = []
        for comp in records:
            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=comp.id,
                primary_text=comp.name or "",
                secondary_text=comp.industry or "",
                tertiary_text=comp.location or "",
                long_text=comp.notes or "",
                prefix_tags=["COMP", "COMPANY"],
            )

            if score > 0 or exact_id == comp.id:
                ind = comp.industry or "Industry Unspecified"
                loc = comp.location or "Location Unspecified"
                results.append(
                    SearchResult(
                        entity_type="company",
                        entity_id=comp.id,
                        category=self.display_name,
                        title=comp.name or f"Company #{comp.id}",
                        subtitle=f"{ind} • {loc}",
                        route=self.default_route,
                        action="filter",  # filters jobs by this company
                        score=score,
                        matched_fields=matched_fields,
                        badge_text="Company",
                        badge_variant="info",
                        metadata={"name": comp.name, "website": comp.website},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
