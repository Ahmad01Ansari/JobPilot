"""Unified Global Search Service coordinating modular SearchProviders with deterministic ranking."""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import sessionmaker

from app.db.session import SessionLocal, get_db_session
from app.services.search.ranking import normalize_query
from app.services.search.search_provider import SearchProviderRegistry
from app.services.search.search_result import GlobalSearchBatch, SearchResult
from app.services.search.providers import (
    JobSearchProvider,
    ApplicationSearchProvider,
    CompanySearchProvider,
    ContactSearchProvider,
    InterviewSearchProvider,
    FollowUpSearchProvider,
    OutreachSearchProvider,
    ResumeSearchProvider,
    QnASearchProvider,
    PlatformSearchProvider,
)

logger = logging.getLogger(__name__)


def build_default_provider_registry() -> SearchProviderRegistry:
    """Builds and populates the default registry with all 10 entity search providers."""
    registry = SearchProviderRegistry()
    registry.register(JobSearchProvider())
    registry.register(ApplicationSearchProvider())
    registry.register(CompanySearchProvider())
    registry.register(ContactSearchProvider())
    registry.register(InterviewSearchProvider())
    registry.register(FollowUpSearchProvider())
    registry.register(OutreachSearchProvider())
    registry.register(ResumeSearchProvider())
    registry.register(QnASearchProvider())
    registry.register(PlatformSearchProvider())
    return registry


class GlobalSearchService:
    """Coordinates fast multi-entity search across the application database."""

    def __init__(
        self,
        session_factory: Optional[sessionmaker] = None,
        registry: Optional[SearchProviderRegistry] = None,
    ) -> None:
        self._session_factory = session_factory or SessionLocal
        self.registry = registry or build_default_provider_registry()

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit_per_category: int = 5,
        global_limit: int = 30,
        request_id: int = 0,
    ) -> GlobalSearchBatch:
        """Executes a unified cross-entity search with deterministic ranking.

        Args:
            query: Raw user query string.
            category: Optional category filter key (e.g. 'all', 'jobs', 'applications').
            limit_per_category: Maximum results retained per individual category.
            global_limit: Absolute cap on total returned results.
            request_id: Generation counter for tracking stale asynchronous responses.
        """
        raw_query = str(query or "").strip()
        lowered_q, tokens = normalize_query(raw_query)

        if not raw_query or not tokens:
            return GlobalSearchBatch(
                query=raw_query,
                total_count=0,
                items=[],
                categories={},
                request_id=request_id,
            )

        cat_clean = (category or "all").strip().lower()

        # Determine which providers to query
        providers = []
        if cat_clean in ("all", "", None):
            providers = self.registry.list_providers()
        else:
            single = self.registry.get_provider(cat_clean)
            if single:
                providers = [single]
            else:
                # Handle plurals or aliases
                aliases = {
                    "job": "jobs",
                    "application": "applications",
                    "app": "applications",
                    "apps": "applications",
                    "company": "companies",
                    "contact": "contacts",
                    "recruiter": "contacts",
                    "interview": "interviews",
                    "followup": "followups",
                    "follow_up": "followups",
                    "resume": "resumes",
                    "platform": "platforms",
                }
                alias_key = aliases.get(cat_clean)
                if alias_key:
                    alias_prov = self.registry.get_provider(alias_key)
                    if alias_prov:
                        providers = [alias_prov]

        all_results: List[SearchResult] = []
        counts: Dict[str, int] = {}

        # Safe isolated database session per execution
        with get_db_session(self._session_factory) as session:
            for provider in providers:
                try:
                    category_items = provider.search(
                        session=session,
                        tokens=tokens,
                        raw_query=raw_query,
                        limit=limit_per_category,
                    )
                    counts[provider.category_key] = len(category_items)
                    all_results.extend(category_items)
                except Exception as e:
                    logger.exception(
                        "Search provider '%s' failed for query '%s': %s",
                        provider.category_key,
                        raw_query,
                        e,
                    )
                    counts[provider.category_key] = 0

        # Sort combined results by deterministic hierarchy: score DESC, entity_id DESC
        all_results.sort(key=lambda r: (r.score, r.entity_id), reverse=True)

        capped_results = all_results[:global_limit]

        return GlobalSearchBatch(
            query=raw_query,
            total_count=len(capped_results),
            items=capped_results,
            categories=counts,
            request_id=request_id,
        )
