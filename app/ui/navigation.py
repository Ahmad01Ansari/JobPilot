"""
Navigation registry and data definitions for JobPilot Desktop.
Single source of truth for sidebar items and view routing.
"""

from dataclasses import dataclass, field
from typing import List, Type, Optional
from PySide6.QtWidgets import QWidget

from app.ui.views.dashboard_view import DashboardView
from app.ui.views.profile_view import ProfileView
from app.ui.views.resumes_view import ResumesView
from app.ui.views.platforms_view import PlatformsView
from app.ui.views.search_view import SearchView
from app.ui.views.jobs_view import JobsView
from app.ui.views.applications_view import ApplicationsView
from app.ui.views.outreach.workspace import OutreachWorkspace
from app.ui.views.interviews_view import InterviewsView
from app.ui.views.followups_view import FollowupsView
from app.ui.views.analytics_view import AnalyticsView
from app.ui.views.automation_view import AutomationView
from app.ui.views.logs_view import LogsView
from app.ui.views.settings_view import SettingsView


@dataclass(frozen=True)
class NavItem:
    """Represents a registered navigation item in the application."""
    id: str
    title: str
    icon_type: str
    view_class: Type[QWidget]
    category: str
    shortcut: Optional[str] = None


@dataclass(frozen=True)
class SidebarNavEntry:
    """Presentation-layer sidebar item. Maps to a real NavItem route or applies a filter."""
    id: str                         # sidebar-unique ID (e.g. "easy_apply")
    label: str                      # display label
    icon: str                       # icon key consumed by SidebarIconPainter
    route: str                      # actual page_id to navigate to
    tooltip: str = ""               # tooltip text shown when collapsed
    filter_key: Optional[str] = None  # if set, applies a pre-filter on the target view


@dataclass(frozen=True)
class SidebarSection:
    """Defines a visual group in the sidebar."""
    title: str
    items: List[SidebarNavEntry] = field(default_factory=list)


# Central Navigation Registry: Exactly 13 items covering the master roadmap.
# ORDER MATTERS — this order determines stacked-widget indices in MainWindow.
NAV_ITEMS: List[NavItem] = [
    NavItem(
        id="dashboard",
        title="Dashboard",
        icon_type="chart",
        view_class=DashboardView,
        category="OVERVIEW",
        shortcut="Ctrl+1",
    ),
    NavItem(
        id="automation",
        title="Automation",
        icon_type="play",
        view_class=AutomationView,
        category="INTELLIGENCE",
        shortcut="Ctrl+2",
    ),
    NavItem(
        id="jobs",
        title="Jobs",
        icon_type="briefcase",
        view_class=JobsView,
        category="OPERATIONS",
        shortcut="Ctrl+3",
    ),
    NavItem(
        id="search",
        title="Job Search",
        icon_type="search",
        view_class=SearchView,
        category="OPERATIONS",
        shortcut="Ctrl+4",
    ),
    NavItem(
        id="applications",
        title="Applications",
        icon_type="list",
        view_class=ApplicationsView,
        category="PIPELINE",
        shortcut="Ctrl+5",
    ),
    NavItem(
        id="outreach",
        title="Outreach",
        icon_type="mail",
        view_class=OutreachWorkspace,
        category="PIPELINE",
        shortcut="Ctrl+6",
    ),
    NavItem(
        id="interviews",
        title="Interviews",
        icon_type="calendar",
        view_class=InterviewsView,
        category="PIPELINE",
        shortcut="Ctrl+7",
    ),
    NavItem(
        id="followups",
        title="Follow-ups",
        icon_type="bell",
        view_class=FollowupsView,
        category="PIPELINE",
        shortcut="Ctrl+8",
    ),
    NavItem(
        id="analytics",
        title="Analytics",
        icon_type="trending",
        view_class=AnalyticsView,
        category="INTELLIGENCE",
        shortcut="Ctrl+9",
    ),
    NavItem(
        id="profile",
        title="Profile",
        icon_type="user",
        view_class=ProfileView,
        category="CANDIDATE",
        shortcut="Ctrl+0",
    ),
    NavItem(
        id="resumes",
        title="Resumes",
        icon_type="document",
        view_class=ResumesView,
        category="CANDIDATE",
    ),
    NavItem(
        id="platforms",
        title="Platforms",
        icon_type="globe",
        view_class=PlatformsView,
        category="OPERATIONS",
    ),
    NavItem(
        id="logs",
        title="Logs",
        icon_type="terminal",
        view_class=LogsView,
        category="SYSTEM",
    ),
    NavItem(
        id="settings",
        title="Settings",
        icon_type="gear",
        view_class=SettingsView,
        category="SYSTEM",
        shortcut="Ctrl+,",
    ),
]


# ── Sidebar Presentation Layer ──────────────────────────────────────────
# Defines the VISUAL order and grouping of navigation items in the sidebar.
# This matches NAV_ITEMS order and keyboard shortcuts Ctrl+1..9, Ctrl+0.
# "easy_apply" and "company_portal" are virtual items that route to "jobs" with a filter.

SIDEBAR_SECTIONS: List[SidebarSection] = [
    SidebarSection("WORKSPACE", [
        SidebarNavEntry("dashboard",      "Dashboard",      "dashboard",   "dashboard",  "Dashboard (Ctrl+1)"),
        SidebarNavEntry("automation",     "Automation",     "automation",  "automation", "Automation (Ctrl+2)"),
    ]),
    SidebarSection("JOBS", [
        SidebarNavEntry("jobs",           "All Jobs",       "briefcase",   "jobs",       "All Jobs (Ctrl+3)"),
        SidebarNavEntry("easy_apply",     "Easy Apply",     "lightning",   "jobs",       "Easy Apply Jobs",     filter_key="EASY_APPLY"),
        SidebarNavEntry("company_portal", "Company Portal", "building",    "jobs",       "Company Portal Jobs", filter_key="COMPANY_PORTAL"),
        SidebarNavEntry("junk_jobs",      "Junk",           "trash",       "jobs",       "Junk Jobs",           filter_key="JUNK"),
        SidebarNavEntry("search",         "Job Search",     "search",      "search",     "Job Search (Ctrl+4)"),
    ]),
    SidebarSection("PIPELINE", [
        SidebarNavEntry("applications",   "Applications",   "file_check",  "applications", "Applications (Ctrl+5)"),
        SidebarNavEntry("outreach",       "Outreach",       "mail",        "outreach",     "Outreach Center (Ctrl+6)"),
        SidebarNavEntry("interviews",     "Interviews",     "calendar",    "interviews",   "Interviews (Ctrl+7)"),
        SidebarNavEntry("followups",      "Follow-ups",     "clock",       "followups",    "Follow-ups (Ctrl+8)"),
    ]),
    SidebarSection("INSIGHTS", [
        SidebarNavEntry("analytics",      "Analytics",      "chart",       "analytics",  "Analytics (Ctrl+9)"),
    ]),
    SidebarSection("CANDIDATE", [
        SidebarNavEntry("profile",        "Profile",        "user",        "profile",    "Profile (Ctrl+0)"),
        SidebarNavEntry("resumes",        "Resumes",        "file_text",   "resumes",    "Resumes"),
    ]),
    SidebarSection("SYSTEM", [
        SidebarNavEntry("platforms",      "Platforms",      "globe",       "platforms",  "Platforms"),
        SidebarNavEntry("logs",           "Logs",           "terminal",    "logs",       "Logs"),
        SidebarNavEntry("settings",       "Settings",       "gear",        "settings",   "Settings (Ctrl+,)"),
    ]),
]


def get_nav_item_by_id(item_id: str) -> Optional[NavItem]:
    """Retrieves a NavItem from the registry by its unique identifier."""
    for item in NAV_ITEMS:
        if item.id == item_id:
            return item
    return None
