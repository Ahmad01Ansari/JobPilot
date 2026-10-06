"""Recruitment analytics widgets package."""

from app.ui.widgets.analytics.analytics_filter_bar import AnalyticsFilterBar
from app.ui.widgets.analytics.analytics_summary_tiles import AnalyticsSummaryTiles
from app.ui.widgets.analytics.analytics_trend_chart import AnalyticsTrendChart
from app.ui.widgets.analytics.analytics_funnel_widget import AnalyticsFunnelWidget
from app.ui.widgets.analytics.analytics_platform_table import AnalyticsPlatformTable
from app.ui.widgets.analytics.analytics_method_aging import AnalyticsMethodAgingWidget
from app.ui.widgets.analytics.analytics_role_breakdown import AnalyticsRoleBreakdownWidget

__all__ = [
    "AnalyticsFilterBar",
    "AnalyticsSummaryTiles",
    "AnalyticsTrendChart",
    "AnalyticsFunnelWidget",
    "AnalyticsPlatformTable",
    "AnalyticsMethodAgingWidget",
    "AnalyticsRoleBreakdownWidget",
]
