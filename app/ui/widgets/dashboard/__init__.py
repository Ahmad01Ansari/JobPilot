"""Dashboard modern UI widgets."""

from app.ui.widgets.dashboard.daily_progress import DailyProgressWidget
from app.ui.widgets.dashboard.kpi_metrics_bar import DashboardKPICardsBar
from app.ui.widgets.dashboard.needs_attention import NeedsAttentionWidget
from app.ui.widgets.dashboard.next_best_action import NextBestActionWidget
from app.ui.widgets.dashboard.readiness_strip import ReadinessStrip
from app.ui.widgets.dashboard.search_performance import SearchPerformanceWidget
from app.ui.widgets.dashboard.todays_job_hunt import TodaysJobHuntWidget
from app.ui.widgets.dashboard.top_opportunities import TopOpportunitiesWidget

__all__ = [
    "DailyProgressWidget",
    "DashboardKPICardsBar",
    "NeedsAttentionWidget",
    "NextBestActionWidget",
    "ReadinessStrip",
    "SearchPerformanceWidget",
    "TodaysJobHuntWidget",
    "TopOpportunitiesWidget",
]
