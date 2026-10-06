"""Search provider interface and provider registry for extensible multi-entity search."""

from abc import ABC, abstractmethod
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.services.search.search_result import SearchResult

logger = logging.getLogger(__name__)


class SearchProvider(ABC):
    """Abstract contract for an entity search provider."""

    @property
    @abstractmethod
    def category_key(self) -> str:
        """Unique machine-readable key (e.g. 'jobs', 'applications', 'companies')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable category header (e.g. 'Jobs', 'Applications')."""
        pass

    @property
    def default_route(self) -> str:
        """Destination navigation route (e.g. 'jobs', 'applications', 'outreach')."""
        return self.category_key

    @abstractmethod
    def search(
        self,
        session: Session,
        tokens: List[str],
        raw_query: str,
        limit: int = 5,
    ) -> List[SearchResult]:
        """Executes targeted query within session and returns scored SearchResult items."""
        pass


class SearchProviderRegistry:
    """Thread-safe registry of modular entity search providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, SearchProvider] = {}

    def register(self, provider: SearchProvider) -> None:
        """Registers a search provider instance."""
        key = provider.category_key.strip().lower()
        self._providers[key] = provider
        logger.debug("Registered SearchProvider: %s (%s)", key, provider.display_name)

    def unregister(self, category_key: str) -> None:
        """Removes a provider by key if registered."""
        self._providers.pop(category_key.strip().lower(), None)

    def get_provider(self, category_key: str) -> Optional[SearchProvider]:
        """Returns provider for category_key or None."""
        if not category_key:
            return None
        return self._providers.get(category_key.strip().lower())

    def list_providers(self) -> List[SearchProvider]:
        """Returns all registered providers in registration order."""
        return list(self._providers.values())
