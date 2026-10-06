"""Thin SearchProvider adapter for Automation Platforms."""

from typing import List
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models.platform import Platform
from app.services.search.ranking import calculate_relevance_score
from app.services.search.search_provider import SearchProvider
from app.services.search.search_result import SearchResult


class PlatformSearchProvider(SearchProvider):
    """Searches Platform configuration entries (LinkedIn, Naukri, Indeed, Glassdoor, Foundit)."""

    @property
    def category_key(self) -> str:
        return "platforms"

    @property
    def display_name(self) -> str:
        return "Platforms"

    @property
    def default_route(self) -> str:
        return "platforms"

    def search(
        self,
        session: Session,
        tokens: List[str],
        raw_query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        if not tokens and not raw_query:
            return []

        clean_q = raw_query.strip().casefold()
        stmt = select(Platform)
        filters = []
        for token in tokens:
            pattern = f"%{token}%"
            filters.append(
                or_(
                    Platform.name.ilike(pattern),
                    Platform.display_name.ilike(pattern),
                    Platform.description.ilike(pattern),
                )
            )
        if filters:
            stmt = stmt.where(*filters)

        records = session.execute(stmt).scalars().all()
        results: List[SearchResult] = []

        for plat in records:
            score, matched_fields = calculate_relevance_score(
                raw_query=raw_query,
                tokens=tokens,
                entity_id=plat.id,
                primary_text=plat.display_name or plat.name,
                secondary_text=plat.name,
                tertiary_text="Enabled" if plat.is_enabled else "Disabled",
                long_text=plat.description or "",
                prefix_tags=["PLATFORM"],
            )

            if score > 0 or clean_q in (plat.name.casefold(), plat.display_name.casefold()):
                status_str = "Enabled" if plat.is_enabled else "Disabled"
                results.append(
                    SearchResult(
                        entity_type="platform",
                        entity_id=plat.id,
                        category=self.display_name,
                        title=plat.display_name or plat.name.capitalize(),
                        subtitle=f"Platform Config • Status: {status_str}",
                        route=self.default_route,
                        action="focus",
                        score=score,
                        matched_fields=matched_fields,
                        badge_text=status_str,
                        badge_variant="success" if plat.is_enabled else "neutral",
                        metadata={"platform_key": plat.name, "enabled": plat.is_enabled},
                    )
                )

        results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)
        return results[:limit]
