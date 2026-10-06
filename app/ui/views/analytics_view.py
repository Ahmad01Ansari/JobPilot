"""Recruitment Analytics Workspace view component.

Provides conversion funnel performance metrics, time-series trends,
platform comparison tables, application method breakdown, active application aging,
and response time forensics.
"""

from datetime import datetime
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.analytics_service import AnalyticsFilter, AnalyticsService
from app.ui.theme import COLORS
from app.ui.widgets.analytics import (
    AnalyticsFilterBar,
    AnalyticsFunnelWidget,
    AnalyticsMethodAgingWidget,
    AnalyticsPlatformTable,
    AnalyticsRoleBreakdownWidget,
    AnalyticsSummaryTiles,
    AnalyticsTrendChart,
)
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader


class AnalyticsView(QWidget):
    """Modernized, enterprise-grade Recruitment Analytics Workspace."""

    def __init__(
        self,
        service: Optional[AnalyticsService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or AnalyticsService()
        self.current_filter = AnalyticsFilter(date_preset="30D")
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 16, 24, 16)
        main_layout.setSpacing(12)

        # 1. Header
        self.header = PageHeader(
            title="Application Analytics",
            subtitle="Understand application volume, conversion efficiency, funnel leakage, and response behavior over time.",
        )
        main_layout.addWidget(self.header)

        # 2. Notification Toast Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Global Filter Bar
        self.filter_bar = AnalyticsFilterBar(self)
        self.filter_bar.filter_changed.connect(self._on_filter_changed)
        self.filter_bar.refresh_requested.connect(self.refresh)
        self.filter_bar.export_requested.connect(self._on_export_csv)
        main_layout.addWidget(self.filter_bar)

        # 4. Scrollable Main Content Canvas
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        content_layout = QVBoxLayout(container)
        content_layout.setContentsMargins(0, 4, 0, 16)
        content_layout.setSpacing(14)

        # Section 1: KPI Summary Metric Tiles (6 Tiles)
        self.summary_tiles = AnalyticsSummaryTiles(self)
        self.summary_tiles.tile_clicked.connect(self._on_tile_clicked)
        content_layout.addWidget(self.summary_tiles)

        # Section 2: Trend Chart & Funnel Flow Row (2 Columns: 58% / 42%)
        trend_funnel_row = QHBoxLayout()
        trend_funnel_row.setSpacing(14)

        self.trend_chart = AnalyticsTrendChart(self)
        trend_funnel_row.addWidget(self.trend_chart, 58)

        self.funnel_widget = AnalyticsFunnelWidget(self)
        self.funnel_widget.stage_clicked.connect(self._on_funnel_stage_clicked)
        trend_funnel_row.addWidget(self.funnel_widget, 42)

        content_layout.addLayout(trend_funnel_row)

        # Section 3: Platform Performance Comparison Table
        self.platform_table = AnalyticsPlatformTable(self)
        self.platform_table.platform_selected.connect(self._on_platform_selected)
        content_layout.addWidget(self.platform_table)

        # Alias self.table for backwards compatibility with legacy tests
        self.table = self.platform_table.table

        # Section 4: Application Methods & Active Aging (Two Columns)
        self.method_aging = AnalyticsMethodAgingWidget(self)
        self.method_aging.method_clicked.connect(self._on_method_clicked)
        self.method_aging.aging_clicked.connect(self._on_aging_clicked)
        content_layout.addWidget(self.method_aging)

        # Section 5: Top Applied Roles & Companies (Two Columns)
        self.role_breakdown = AnalyticsRoleBreakdownWidget(self)
        self.role_breakdown.role_clicked.connect(self._on_role_clicked)
        self.role_breakdown.company_clicked.connect(self._on_company_clicked)
        content_layout.addWidget(self.role_breakdown)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def refresh(self) -> None:
        """Queries the analytics service with current filter and updates all components."""
        try:
            # 1. Summary Metrics
            summary = self.service.get_summary_metrics(self.current_filter)
            self.summary_tiles.update_metrics(summary)

            # 2. Time Series Trend
            trend_data = self.service.get_time_series_trend(self.current_filter)
            self.trend_chart.update_chart(trend_data)

            # 3. Funnel & Conversion
            funnel_data = self.service.get_funnel_flow(self.current_filter)
            self.funnel_widget.update_funnel(funnel_data)

            # 4. Platform Performance
            plat_data = self.service.get_platform_performance(self.current_filter)
            self.platform_table.update_data(plat_data)

            # 5. Method, Aging & Response Forensics
            methods = self.service.get_method_distribution(self.current_filter)
            aging = self.service.get_aging_distribution(self.current_filter)
            resp_stats = summary.get("response_stats") or self.service.get_response_time_stats(self.current_filter)
            self.method_aging.update_data(methods, aging, resp_stats)

            # 6. Role & Company Breakdown
            roles_data = self.service.get_role_company_breakdown(self.current_filter)
            self.role_breakdown.update_data(roles_data)

        except Exception as e:
            self.notification_bar.show_message(
                f"Error updating analytics: {e}",
                severity="danger",
                auto_dismiss_ms=6000,
            )

    def _on_filter_changed(self, f: AnalyticsFilter) -> None:
        self.current_filter = f
        self.refresh()

    def _on_platform_selected(self, platform_key: str) -> None:
        """Filters analytics to the clicked platform."""
        self.filter_bar.set_platform_filter(platform_key)

    def _on_funnel_stage_clicked(self, stage_id: str) -> None:
        """Handles funnel stage click drill-down."""
        status_map = {
            "submitted": "SUBMITTED",
            "responses": "UNDER_REVIEW",
            "interviews": "INTERVIEW",
            "offers": "OFFER",
        }
        if stage_id in status_map:
            self.filter_bar.set_status_filter(status_map[stage_id])
        elif stage_id in ["discovered", "qualified"]:
            self._navigate_to_view("jobs")

    def _on_tile_clicked(self, metric_key: str) -> None:
        """Handles metric card click drill-down."""
        if metric_key in ["submitted", "responses", "progression", "interviews", "offers"]:
            self._navigate_to_view("applications")
        elif metric_key == "velocity":
            self.filter_bar.set_platform_filter("all")

    def _on_method_clicked(self, method_key: str) -> None:
        idx = self.filter_bar.combo_method.findText(method_key.replace("_", " ").title())
        if idx >= 0:
            self.filter_bar.combo_method.setCurrentIndex(idx)

    def _on_aging_clicked(self, bucket_name: str) -> None:
        self._navigate_to_view("applications")

    def _on_role_clicked(self, role_title: str) -> None:
        self._navigate_to_view("applications", search=role_title)

    def _on_company_clicked(self, company_name: str) -> None:
        self._navigate_to_view("applications", search=company_name)

    def _navigate_to_view(self, view_name: str, search: Optional[str] = None) -> None:
        """Attempts navigation to another workspace view via parent window router if available."""
        window = self.window()
        if hasattr(window, "navigate_to"):
            window.navigate_to(view_name)
            # Apply search to target view if supported
            if search and hasattr(window, "views") and view_name in window.views:
                target_view = window.views[view_name]
                if hasattr(target_view, "apply_search"):
                    target_view.apply_search(search)
        else:
            self.notification_bar.show_message(
                f"Drill-down to {view_name.title()} ({search or 'all'})",
                severity="info",
                auto_dismiss_ms=3000,
            )

    def _on_export_csv(self) -> None:
        """Exports the active filtered analytics dataset to a CSV file."""
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"JobPilot_Analytics_Export_{now_str}.csv"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Analytics Dataset",
            default_filename,
            "CSV Files (*.csv);;All Files (*)",
        )
        if not path:
            return

        try:
            csv_content = self.service.export_to_csv(self.current_filter)
            with open(path, "w", encoding="utf-8") as f:
                f.write(csv_content)

            self.notification_bar.show_message(
                f"Successfully exported analytics data to {os.path.basename(path)}",
                severity="success",
                auto_dismiss_ms=4000,
            )
        except Exception as e:
            self.notification_bar.show_message(
                f"Failed to export CSV: {e}",
                severity="danger",
                auto_dismiss_ms=6000,
            )
