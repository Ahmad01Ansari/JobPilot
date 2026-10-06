"""Data contracts and navigation models for Universal Global Search and Exact Navigation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class NavigationAction(str, Enum):
    """Supported navigation action behaviors on destination views."""
    OPEN = "open"       # Open primary inspection dialog / detail modal / preview
    FOCUS = "focus"     # Scroll to, highlight, and select row/card in current list without filtering
    FILTER = "filter"   # Isolate the view to strictly this single record with an exact-filter chip


@dataclass(frozen=True)
class SearchResult:
    """Normalized search result item emitted across thread boundaries."""

    entity_type: str                   # 'job', 'application', 'company', 'contact', 'interview', 'followup', 'outreach', 'resume', 'qna', 'platform'
    entity_id: int                     # Database primary key (canonical identifier)
    category: str                      # Grouping label: 'Jobs', 'Applications', 'Companies', etc.
    title: str                         # Primary display line (e.g. "Staff RPA Engineer")
    subtitle: str                      # Secondary context (e.g. "Acme Corp • Bengaluru • Direct")
    route: str                         # NavItem route key ('jobs', 'applications', 'outreach', 'interviews', etc.)
    action: str = "open"               # Default action on click ('open', 'focus', 'filter')
    score: float = 0.0                 # Deterministic relevance rank (0.0 to 100.0)
    matched_fields: List[str] = field(default_factory=list)  # Fields that matched: ['title', 'company_raw', 'id']
    description: Optional[str] = None  # Snippet or detail preview (safe, non-sensitive)
    badge_text: Optional[str] = None   # Status or method tag (e.g. 'SUBMITTED', 'ACTIVE')
    badge_variant: str = "neutral"     # Theme token: 'success', 'warning', 'danger', 'info', 'primary', 'neutral'
    metadata: Dict[str, Any] = field(default_factory=dict)  # Non-critical supplemental data

    @property
    def target_route(self) -> str:
        """Alias for route."""
        return self.route

    @property
    def navigation_key(self) -> Tuple[str, int]:
        """Immutable canonical identity for routing and deduplication."""
        return (self.entity_type, self.entity_id)


@dataclass
class NavigationRequest:
    """Centralized navigation instruction dispatched by AppNavigator."""

    route: str                         # Destination page_id ('jobs', 'applications', etc.)
    entity_type: str                   # Canonical type ('job', 'application', etc.)
    entity_id: int                     # Primary key
    action: NavigationAction = NavigationAction.OPEN
    focus: bool = True                 # Ensure row/card is selected and scrolled into viewport
    preserve_history: bool = True      # Take a ViewStateSnapshot of destination before mutating
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ViewStateSnapshot:
    """Preserves user's contextual filters before applying exact record mode."""

    search_query: str = ""
    status_filter: Optional[str] = None
    platform_filter: Optional[str] = None
    current_page: int = 1
    selected_row_id: Optional[int] = None
    extra_filters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GlobalSearchBatch:
    """Consolidated results of a multi-entity search query."""

    query: str
    total_count: int
    items: List[SearchResult]
    categories: Dict[str, int] = field(default_factory=dict)
    request_id: int = 0
