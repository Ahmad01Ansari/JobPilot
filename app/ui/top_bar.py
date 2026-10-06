"""
Top bar navigation and status header component.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal

from app.ui.theme import COLORS
from app.ui.navigation import get_nav_item_by_id


class TopBar(QWidget):
    """Application top bar showing current view title, quick search, and user profile pill."""

    search_requested = Signal()
    profile_clicked = Signal()
    about_clicked = Signal()
    toggle_sidebar_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 20, 0)
        layout.setSpacing(14)

        # Current Page Title
        self.title_label = QLabel("Dashboard")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 700; color: #F0F6FC; background: transparent; border: none;")
        layout.addWidget(self.title_label)

        # Quick Search Trigger Button (Ctrl+K)
        self.btn_search = QPushButton("🔍   Search jobs, companies, contacts...       Ctrl+K")
        self.btn_search.setCursor(Qt.PointingHandCursor)
        self.btn_search.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #8B949E;
                border: 1px solid #333A46;
                border-radius: 18px;
                padding: 7px 16px;
                font-size: 12px;
                font-weight: 500;
                text-align: left;
                min-width: 320px;
            }
            QPushButton:hover {
                background-color: #262C36;
                color: #F0F6FC;
                border-color: #FF5F15;
            }
        """)
        self.btn_search.clicked.connect(self.search_requested.emit)
        layout.addWidget(self.btn_search)

        layout.addStretch()


        # Profile Pill Button
        self.btn_profile = QPushButton("  👤  Candidate Profile  ")
        self.btn_profile.setCursor(Qt.PointingHandCursor)
        self.btn_profile.setToolTip("View candidate profile and readiness")
        self.btn_profile.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #F0F6FC;
                border: 1px solid #333A46;
                border-radius: 16px;
                padding: 5px 14px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #262C36;
                border-color: #FF5F15;
            }
        """)
        self.btn_profile.clicked.connect(self.profile_clicked.emit)
        layout.addWidget(self.btn_profile)

        # About / System Info Button
        self.btn_about = QPushButton(" ℹ️  About ")
        self.btn_about.setCursor(Qt.PointingHandCursor)
        self.btn_about.setToolTip("About JobPilot & Platform Specs")
        self.btn_about.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #8B949E;
                border: 1px solid #333A46;
                border-radius: 16px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #262C36;
                color: #F0F6FC;
                border-color: #FF5F15;
            }
        """)
        self.btn_about.clicked.connect(self.about_clicked.emit)
        layout.addWidget(self.btn_about)

        self.setStyleSheet("""
            TopBar {
                background-color: #161B22;
                border-bottom: 1px solid #262C36;
            }
        """)

    def set_active_page(self, page_id: str):
        """Updates displayed page title from registered item."""
        item = get_nav_item_by_id(page_id)
        if item:
            self.title_label.setText(item.title)
        else:
            self.title_label.setText(page_id.capitalize())

    def set_candidate_name(self, name: str) -> None:
        """Updates displayed user profile name in the top bar pill."""
        disp_name = (name or "Candidate").strip()
        self.btn_profile.setText(f"  👤  {disp_name}  ")

