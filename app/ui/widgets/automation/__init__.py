"""Automation Control Center UI widgets package."""

from app.ui.widgets.automation.activity_stream import LiveActivityStream
from app.ui.widgets.automation.automation_header import AutomationHeader
from app.ui.widgets.automation.automation_hero import AutomationHero
from app.ui.widgets.automation.automation_metrics import AutomationMetricRow
from app.ui.widgets.automation.automation_pipeline import AutomationPipeline
from app.ui.widgets.automation.all_run_history_dialog import AllRunHistoryDialog
from app.ui.widgets.automation.captcha_dialog import CaptchaInterventionDialog
from app.ui.widgets.automation.current_job_card import CurrentJobCard
from app.ui.widgets.automation.intervention_banner import InterventionBanner
from app.ui.widgets.automation.platform_selector import PlatformSelector
from app.ui.widgets.automation.platform_strip import PlatformStrip
from app.ui.widgets.automation.run_details_drawer import RunDetailsDrawer
from app.ui.widgets.automation.run_summary_card import RunSummaryCard
from app.ui.widgets.automation.state import AutomationUIState
from app.ui.widgets.automation.universal_timeline_widget import UniversalTimelineWidget
from app.ui.widgets.automation.universal_target_card import UniversalTargetCard


def __getattr__(name: str):
    if name == "UniversalReviewDialog":
        from app.ui.views.automation.universal_review_dialog import UniversalReviewDialog
        return UniversalReviewDialog
    if name == "UniversalInterventionDialog":
        from app.ui.views.automation.universal_intervention_dialog import UniversalInterventionDialog
        return UniversalInterventionDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AutomationHeader",
    "PlatformStrip",
    "PlatformSelector",
    "UniversalTargetCard",
    "AutomationHero",
    "AutomationPipeline",
    "AutomationMetricRow",
    "CurrentJobCard",
    "LiveActivityStream",
    "RunSummaryCard",
    "RunDetailsDrawer",
    "InterventionBanner",
    "CaptchaInterventionDialog",
    "AllRunHistoryDialog",
    "AutomationUIState",
    "UniversalTimelineWidget",
    "UniversalReviewDialog",
    "UniversalInterventionDialog",
]
