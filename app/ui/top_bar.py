"""
Top bar navigation and status header component.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QSizePolicy
from PySide6.QtCore import Qt, QSize, Signal

from app.ui.theme import COLORS
from app.ui.navigation import get_nav_item_by_id
from app.ui.sidebar_icons import render_vector_icon


class TopBar(QWidget):
    """Application top bar showing current view title, quick search, and user profile pill."""

    search_requested = Signal()
    refresh_requested = Signal()
    profile_clicked = Signal()
    about_clicked = Signal()
    toggle_sidebar_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(12)

        # Current Page Title
        self.title_label = QLabel("Dashboard")
        self.title_label.setObjectName("TopBarTitle")
        layout.addWidget(self.title_label)

        # Quick Search Trigger Button (Ctrl+K)
        self.btn_search = QPushButton(" Search jobs, companies, contacts...   (Ctrl+K)")
        self.btn_search.setObjectName("TopBarSearch")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.btn_search.setIconSize(QSize(14, 14))
        self.btn_search.clicked.connect(self.search_requested.emit)
        layout.addWidget(self.btn_search)

        layout.addStretch(1)

        # Global Refresh Button
        self.btn_refresh = QPushButton(" Refresh")
        self.btn_refresh.setObjectName("TopBarRefreshBtn")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setToolTip("Refresh current page and synchronize all views (Ctrl+R)")
        self.btn_refresh.setIconSize(QSize(14, 14))
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        layout.addWidget(self.btn_refresh)

        # Profile Pill Button
        self.btn_profile = QPushButton(" Candidate Profile")
        self.btn_profile.setObjectName("TopBarProfileBtn")
        self.btn_profile.setCursor(Qt.PointingHandCursor)
        self.btn_profile.setToolTip("View candidate profile and readiness")
        self.btn_profile.setIconSize(QSize(14, 14))
        self.btn_profile.clicked.connect(self.profile_clicked.emit)
        layout.addWidget(self.btn_profile)

        # About / System Info Button
        self.btn_about = QPushButton(" About")
        self.btn_about.setObjectName("TopBarAboutBtn")
        self.btn_about.setCursor(Qt.PointingHandCursor)
        self.btn_about.setToolTip("About JobPilot & Platform Specs")
        self.btn_about.setIconSize(QSize(14, 14))
        self.btn_about.clicked.connect(self.about_clicked.emit)
        layout.addWidget(self.btn_about)

        self.update_theme()

    def update_theme(self, mode: str = "dark") -> None:
        """Synchronizes vector icons with active ThemeManager tokens."""
        muted = COLORS["text_muted"]
        text = COLORS["text"]
        self.btn_search.setIcon(render_vector_icon("search", muted, 14))
        self.btn_refresh.setIcon(render_vector_icon("refresh", muted, 14))
        self.btn_profile.setIcon(render_vector_icon("user", text, 14))
        self.btn_about.setIcon(render_vector_icon("info", muted, 14))

    def set_active_page(self, page_id: str) -> None:
        """Updates displayed page title from registered item."""
        item = get_nav_item_by_id(page_id)
        if item:
            self.title_label.setText(item.title)
        else:
            self.title_label.setText(page_id.capitalize())

    def set_candidate_name(self, name: str) -> None:
        """Updates displayed user profile name in the top bar pill."""
        disp_name = (name or "Candidate").strip()
        self.btn_profile.setText(f" {disp_name}")
