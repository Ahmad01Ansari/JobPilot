"""Candidate Profile view component.

Provides a modern, high-precision candidate profile overview and management
interface designed after modern CRM / Donor spec-sheet layouts. Features
symmetrical 2-column data cards, consistent field heights, uppercase muted labels,
subtle row dividers, a top candidate banner with key statistics, and seamless
dual View / Edit modes.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.profile_service import ProfileService
from app.ui.theme import COLORS
from app.ui.views.qna_view import QnAView
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge


class DataSheetRow(QWidget):
    """A single aligned row in a data-sheet card.

    Renders a fixed-width uppercase label on the left, and a QStackedWidget
    holding the View widget (index 0) and Edit widget (index 1) on the right,
    underlaid with a subtle 1px divider in view mode.
    """

    def __init__(
        self,
        label: str,
        view_widget: QWidget,
        edit_widget: QWidget,
        min_height: int = 38,
        max_height: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.base_min_height = min_height
        self.base_max_height = max_height
        self.setMinimumHeight(min_height)
        if max_height:
            self.setMaximumHeight(max_height)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(12)

        # Label on left: uppercase, muted, fixed width for perfect vertical alignment
        self.lbl_title = QLabel(label.upper())
        self.lbl_title.setFixedWidth(125)
        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.5px;
                background: transparent;
                border: none;
            }}
        """)
        lbl_align = (Qt.AlignTop | Qt.AlignLeft) if min_height > 50 else Qt.AlignVCenter
        layout.addWidget(self.lbl_title, 0, lbl_align)

        # Value / Input on right
        self.stack = QStackedWidget(self)
        self.view_widget = view_widget
        self.edit_widget = edit_widget

        self.stack.addWidget(self.view_widget)
        self.stack.addWidget(self.edit_widget)
        self.stack.setCurrentIndex(0)  # Default: View mode
        layout.addWidget(self.stack, 1)

        # Subtle bottom divider line (view mode)
        self.setStyleSheet(f"""
            DataSheetRow {{
                border-bottom: 1px solid {COLORS['border']}60;
                background: transparent;
            }}
        """)

    def set_edit_mode(self, is_edit: bool) -> None:
        self.stack.setCurrentIndex(1 if is_edit else 0)
        if is_edit:
            self.setStyleSheet("""
                DataSheetRow {
                    border-bottom: none;
                    background: transparent;
                }
            """)
        else:
            self.setStyleSheet(f"""
                DataSheetRow {{
                    border-bottom: 1px solid {COLORS['border']}60;
                    background: transparent;
                }}
            """)


class DataSheetCard(QFrame):
    """A card container displaying rows in a symmetrical 2-column grid."""

    def __init__(self, title: str, icon: str = "", on_edit_toggle=None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.title_text = title
        self.icon_text = icon
        self.is_editing = False
        self.on_edit_toggle = on_edit_toggle
        self.rows: List[DataSheetRow] = []

        self.setObjectName("DataSheetCard")
        self.setStyleSheet(f"""
            QFrame#DataSheetCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)

        self.card_layout = QVBoxLayout(self)
        self.card_layout.setContentsMargins(20, 16, 20, 16)
        self.card_layout.setSpacing(12)

        # Card Header: Icon + Title on left, Action Button on right
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 4)

        icon_str = f"{icon} " if icon else ""
        self.header_lbl = QLabel(f"{icon_str}{title}")
        self.header_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 14px;
                font-weight: 700;
                color: {COLORS['text']};
                background: transparent;
                border: none;
            }}
        """)
        header_row.addWidget(self.header_lbl)
        header_row.addStretch()

        self.btn_card_edit = QPushButton("Edit ✏️")
        self.btn_card_edit.setCursor(Qt.PointingHandCursor)
        self.btn_card_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 4px 12px;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_card_edit.clicked.connect(self._toggle_card_edit)
        header_row.addWidget(self.btn_card_edit)
        self.card_layout.addLayout(header_row)

        # 2-Column Grid Layout for Left & Right Halves
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(32)  # Generous gutter between columns
        self.grid.setVerticalSpacing(0)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        self.card_layout.addLayout(self.grid)

    def add_row(self, row_idx: int, col_idx: int, data_row: DataSheetRow, row_span: int = 1, col_span: int = 1) -> None:
        self.rows.append(data_row)
        self.grid.addWidget(data_row, row_idx, col_idx, row_span, col_span)

    def _toggle_card_edit(self) -> None:
        was_editing = self.is_editing
        self.set_edit_mode(not self.is_editing)
        if self.on_edit_toggle:
            self.on_edit_toggle(self.is_editing, was_editing)

    def set_edit_mode(self, is_edit: bool) -> None:
        self.is_editing = is_edit
        self.btn_card_edit.setText("Done ✓" if is_edit else "Edit ✏️")
        # In edit mode, add generous vertical spacing between input rows so borders never touch or overlap
        self.grid.setVerticalSpacing(8 if is_edit else 0)
        if is_edit:
            self.btn_card_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['accent']}20;
                    color: {COLORS['accent']};
                    border: 1px solid {COLORS['accent']};
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)
        else:
            self.btn_card_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']};
                    padding: 4px 12px;
                    border-radius: 6px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    color: {COLORS['text']};
                    border-color: {COLORS['accent']};
                }}
            """)

        for r in self.rows:
            r.set_edit_mode(is_edit)


class ProfileView(QWidget):
    """Interactive Candidate Profile management and readiness diagnostic view."""

    def __init__(self, service: Optional[ProfileService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service or ProfileService()
        self.current_user_id: Optional[int] = None
        self.is_global_edit_mode: bool = False
        self.cards: List[DataSheetCard] = []

        self._setup_ui()
        self.load_profile()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header with Title & Action Buttons
        self.header = PageHeader(
            title="Candidate Profile & Background",
            subtitle="Manage personal details, compensation, notice period, and application readiness.",
        )

        self.btn_toggle_edit = QPushButton("Edit Profile ✏️")
        self.btn_toggle_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_toggle_edit.clicked.connect(self._toggle_global_edit_mode)

        self.btn_validate = QPushButton("Check Readiness")
        self.btn_validate.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}60;
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_validate.clicked.connect(self._on_validate_clicked)

        self.btn_reset = QPushButton("Reset Changes")
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        self.btn_save = QPushButton("Save Profile")
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 600;
                padding: 7px 18px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)

        self.header.add_action_widget(self.btn_toggle_edit)
        self.header.add_action_widget(self.btn_validate)
        self.header.add_action_widget(self.btn_reset)
        self.header.add_action_widget(self.btn_save)
        main_layout.addWidget(self.header)

        # 2. Notification Banner
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Top Candidate Banner & Summary Cards
        self.profile_banner = self._build_candidate_banner()

        # 4. Readiness Summary Bar
        self.readiness_card = self._build_readiness_bar()

        # 5. Scrollable Form Section with 2-Column Data Sheets
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background: transparent;
                border: none;
            }}
        """)

        form_container = QWidget()
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 8, 16)
        form_layout.setSpacing(16)

        # Candidate Banner & Readiness at top of scroll
        form_layout.addWidget(self.profile_banner)
        form_layout.addWidget(self.readiness_card)

        # Card A: Personal & Contact Details
        self.card_personal = self._build_personal_card()
        self.cards.append(self.card_personal)
        form_layout.addWidget(self.card_personal)

        # Card B: Professional Career & Compensation
        self.card_professional = self._build_professional_card()
        self.cards.append(self.card_professional)
        form_layout.addWidget(self.card_professional)

        # Card C: Technical Skills & Summary
        self.card_skills = self._build_skills_card()
        self.cards.append(self.card_skills)
        form_layout.addWidget(self.card_skills)

        # Card D: Online Profiles & Links
        self.card_links = self._build_links_card()
        self.cards.append(self.card_links)
        form_layout.addWidget(self.card_links)

        form_layout.addStretch()
        scroll_area.setWidget(form_container)

        # 6. Segmented Tabs: Profile Editor & Screening Q&A Knowledge Base
        self.tabs = QTabWidget(self)
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                background-color: transparent;
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                padding: 8px 18px;
                font-weight: 600;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border-bottom: 2px solid {COLORS['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        profile_tab = QWidget()
        tab1_layout = QVBoxLayout(profile_tab)
        tab1_layout.setContentsMargins(8, 8, 8, 8)
        tab1_layout.setSpacing(10)
        tab1_layout.addWidget(scroll_area, 1)

        self.qna_view = QnAView(parent=self)

        self.tabs.addTab(profile_tab, "Candidate Profile & Career")
        self.tabs.addTab(self.qna_view, "Screening Q&A Knowledge Base")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        main_layout.addWidget(self.tabs, 1)

    def _on_tab_changed(self, index: int) -> None:
        """Shows or hides profile action buttons depending on active tab."""
        is_profile = (index == 0)
        self.btn_toggle_edit.setVisible(is_profile)
        self.btn_validate.setVisible(is_profile)
        self.btn_reset.setVisible(is_profile)
        self.btn_save.setVisible(is_profile)
        if not is_profile:
            self.qna_view.refresh()

    def select_tab(self, tab_name_or_index: Any) -> None:
        """Selects tab by index or name ('profile', 'qna')."""
        if isinstance(tab_name_or_index, int):
            self.tabs.setCurrentIndex(tab_name_or_index)
        elif str(tab_name_or_index).lower() in ("qna", "screening"):
            self.tabs.setCurrentIndex(1)
        else:
            self.tabs.setCurrentIndex(0)

    def _toggle_global_edit_mode(self) -> None:
        """Toggles edit mode across all profile cards simultaneously."""
        self.is_global_edit_mode = not self.is_global_edit_mode
        self.btn_toggle_edit.setText("View Mode 👁️" if self.is_global_edit_mode else "Edit Profile ✏️")
        for card in self.cards:
            card.set_edit_mode(self.is_global_edit_mode)

    def _on_card_edit_toggle(self, is_editing: bool, was_editing: bool) -> None:
        """Auto-saves when user finishes editing an individual card."""
        if was_editing and not is_editing:
            # User clicked 'Done ✓' on card: persist changes immediately!
            self._on_save_clicked()

    # ----------------------------------------------------------------------
    # Banner & Summary Header
    # ----------------------------------------------------------------------

    def _build_candidate_banner(self) -> QFrame:
        """Constructs the modern top candidate summary banner matching the reference layout."""
        banner = QFrame()
        banner.setObjectName("CandidateBanner")
        banner.setStyleSheet(f"""
            QFrame#CandidateBanner {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Left: Avatar Badge
        self.avatar_badge = QLabel("AR")
        self.avatar_badge.setFixedSize(54, 54)
        self.avatar_badge.setAlignment(Qt.AlignCenter)
        self.avatar_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #1F1B18;
                color: {COLORS['accent']};
                font-size: 20px;
                font-weight: 800;
                border: 2px solid {COLORS['accent']}50;
                border-radius: 10px;
            }}
        """)
        layout.addWidget(self.avatar_badge)

        # Middle: Candidate Name, Title Badge, and Subtitle Info
        mid_box = QVBoxLayout()
        mid_box.setSpacing(4)

        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        self.lbl_banner_name = QLabel("Mohd Ahmad Raza Ansari")
        self.lbl_banner_name.setStyleSheet(f"""
            QLabel {{
                font-size: 18px;
                font-weight: 700;
                color: {COLORS['text']};
                background: transparent;
                border: none;
            }}
        """)
        name_row.addWidget(self.lbl_banner_name)

        self.lbl_banner_badge = QLabel("RPA & AI AUTOMATION")
        self.lbl_banner_badge.setStyleSheet(f"""
            QLabel {{
                background-color: #162B4D;
                color: #58A6FF;
                font-size: 10px;
                font-weight: 700;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #1F4273;
            }}
        """)
        name_row.addWidget(self.lbl_banner_badge)
        name_row.addStretch()
        mid_box.addLayout(name_row)

        self.lbl_banner_contact = QLabel("candidate@example.com  •  Phone  •  Location")
        self.lbl_banner_contact.setStyleSheet(f"""
            QLabel {{
                font-size: 12px;
                color: {COLORS['text_muted']};
                background: transparent;
                border: none;
            }}
        """)
        mid_box.addWidget(self.lbl_banner_contact)
        layout.addLayout(mid_box, 1)

        # Right: Quick Metrics (Current CTC, Target CTC, Experience, Notice)
        stats_box = QHBoxLayout()
        stats_box.setSpacing(18)

        # Metric 1: Current CTC
        col_cur = QVBoxLayout()
        col_cur.setSpacing(2)
        self.lbl_banner_cur_ctc = QLabel("₹3.50 LPA")
        self.lbl_banner_cur_ctc.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {COLORS['text']}; border: none;")
        lbl_cur_title = QLabel("CURRENT CTC")
        lbl_cur_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; border: none;")
        col_cur.addWidget(self.lbl_banner_cur_ctc)
        col_cur.addWidget(lbl_cur_title)
        stats_box.addLayout(col_cur)

        # Metric 2: Target CTC
        col_exp = QVBoxLayout()
        col_exp.setSpacing(2)
        self.lbl_banner_exp_ctc = QLabel("₹5.50 LPA")
        self.lbl_banner_exp_ctc.setStyleSheet(f"font-size: 17px; font-weight: 700; color: #3FB950; border: none;")
        lbl_exp_title = QLabel("TARGET CTC")
        lbl_exp_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; border: none;")
        col_exp.addWidget(self.lbl_banner_exp_ctc)
        col_exp.addWidget(lbl_exp_title)
        stats_box.addLayout(col_exp)

        # Metric 3: Experience
        col_yr = QVBoxLayout()
        col_yr.setSpacing(2)
        self.lbl_banner_exp = QLabel("2.0 Yrs")
        self.lbl_banner_exp.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {COLORS['text']}; border: none;")
        lbl_yr_title = QLabel("EXPERIENCE")
        lbl_yr_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; border: none;")
        col_yr.addWidget(self.lbl_banner_exp)
        col_yr.addWidget(lbl_yr_title)
        stats_box.addLayout(col_yr)

        # Metric 4: Notice Period
        col_np = QVBoxLayout()
        col_np.setSpacing(2)
        self.lbl_banner_notice = QLabel("30 Days")
        self.lbl_banner_notice.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {COLORS['text']}; border: none;")
        lbl_np_title = QLabel("NOTICE")
        lbl_np_title.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {COLORS['text_muted']}; border: none;")
        col_np.addWidget(self.lbl_banner_notice)
        col_np.addWidget(lbl_np_title)
        stats_box.addLayout(col_np)

        layout.addLayout(stats_box)
        return banner

    def _build_readiness_bar(self) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        readiness_layout = QHBoxLayout(card)
        readiness_layout.setContentsMargins(16, 10, 16, 10)
        readiness_layout.setSpacing(16)

        self.lbl_score = QLabel("Readiness Score: Calculating...")
        self.lbl_score.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']}; border: none;")

        self.badge_status = StatusBadge("Evaluating", variant="neutral")

        self.lbl_readiness_hint = QLabel("Evaluating completeness...")
        self.lbl_readiness_hint.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; border: none;")

        readiness_layout.addWidget(self.lbl_score)
        readiness_layout.addWidget(self.badge_status)
        readiness_layout.addWidget(self.lbl_readiness_hint, 1)
        return card

    # ----------------------------------------------------------------------
    # Helper for View & Edit widgets
    # ----------------------------------------------------------------------

    def _view_label(self, default_text: str = "-") -> QLabel:
        lbl = QLabel(default_text)
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['text']};
                font-size: 13px;
                font-weight: 500;
                background: transparent;
                border: none;
            }}
        """)
        return lbl

    def _line_edit(self, placeholder: str = "") -> QLineEdit:
        edt = QLineEdit()
        edt.setPlaceholderText(placeholder)
        edt.setMinimumHeight(34)
        edt.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        return edt

    # ----------------------------------------------------------------------
    # Card 1: Personal & Contact Details
    # ----------------------------------------------------------------------

    def _build_personal_card(self) -> DataSheetCard:
        card = DataSheetCard(title="Personal & Contact Details", icon="👤", on_edit_toggle=self._on_card_edit_toggle)

        # Left Column: Names & Location
        # 1. First Name
        self.val_first_name = self._view_label("Mohd Ahmad")
        self.txt_first_name = self._line_edit("First name")
        card.add_row(0, 0, DataSheetRow("First Name *", self.val_first_name, self.txt_first_name))

        # 2. Middle Name
        self.val_middle_name = self._view_label("Raza")
        self.txt_middle_name = self._line_edit("Middle name (optional)")
        card.add_row(1, 0, DataSheetRow("Middle Name", self.val_middle_name, self.txt_middle_name))

        # 3. Last Name
        self.val_last_name = self._view_label("Ansari")
        self.txt_last_name = self._line_edit("Last name")
        card.add_row(2, 0, DataSheetRow("Last Name *", self.val_last_name, self.txt_last_name))

        # 4. Street Address
        self.val_address = self._view_label("Delhi")
        self.txt_address = self._line_edit("Street or residential address")
        card.add_row(3, 0, DataSheetRow("Address", self.val_address, self.txt_address))

        # 5. City
        self.val_city = self._view_label("Delhi")
        self.txt_city = self._line_edit("Current city")
        card.add_row(4, 0, DataSheetRow("City *", self.val_city, self.txt_city))

        # 6. State & Zipcode
        self.val_state_zip = self._view_label("Delhi, 110001")
        sz_container = QWidget()
        sz_container.setStyleSheet("background: transparent; border: none;")
        sz_layout = QHBoxLayout(sz_container)
        sz_layout.setContentsMargins(0, 0, 0, 0)
        sz_layout.setSpacing(8)
        self.txt_state = self._line_edit("State")
        self.txt_zipcode = self._line_edit("Zipcode")
        sz_layout.addWidget(self.txt_state, 2)
        sz_layout.addWidget(self.txt_zipcode, 1)
        card.add_row(5, 0, DataSheetRow("State & Zip", self.val_state_zip, sz_container))

        # 7. Country
        self.val_country = self._view_label("India")
        self.txt_country = self._line_edit("Country")
        card.add_row(6, 0, DataSheetRow("Country *", self.val_country, self.txt_country))

        # Right Column: Contacts, Relocation & Demographics
        # 1. Email Address
        self.val_email = self._view_label("candidate@example.com")
        self.txt_email = self._line_edit("candidate@example.com")
        card.add_row(0, 1, DataSheetRow("Email Address *", self.val_email, self.txt_email))

        # 2. Mobile Number
        self.val_phone = self._view_label("+1 555-0199")
        self.txt_phone = self._line_edit("+1 555-0199")
        card.add_row(1, 1, DataSheetRow("Mobile", self.val_phone, self.txt_phone))

        # 3. Relocation
        self.val_relocate = self._view_label("Willing to Relocate (India & Remote)")
        self.chk_relocate = QCheckBox("Open and willing to relocate for opportunities")
        self.chk_relocate.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 500;")
        card.add_row(2, 1, DataSheetRow("Relocation", self.val_relocate, self.chk_relocate))

        # 4. Ethnicity
        self.val_ethnicity = self._view_label("Asian")
        self.txt_ethnicity = self._line_edit("e.g. Asian")
        card.add_row(3, 1, DataSheetRow("Ethnicity", self.val_ethnicity, self.txt_ethnicity))

        # 5. Gender
        self.val_gender = self._view_label("Male")
        self.txt_gender = self._line_edit("e.g. Male")
        card.add_row(4, 1, DataSheetRow("Gender", self.val_gender, self.txt_gender))

        # 6. Disability Status
        self.val_disability = self._view_label("No")
        self.txt_disability = self._line_edit("No / Yes / Decline")
        card.add_row(5, 1, DataSheetRow("Disability", self.val_disability, self.txt_disability))

        # 7. Veteran Status
        self.val_veteran = self._view_label("No")
        self.txt_veteran = self._line_edit("No / Yes / Decline")
        card.add_row(6, 1, DataSheetRow("Veteran", self.val_veteran, self.txt_veteran))

        return card

    # ----------------------------------------------------------------------
    # Card 2: Professional Career & Compensation
    # ----------------------------------------------------------------------

    def _build_professional_card(self) -> DataSheetCard:
        card = DataSheetCard(title="Professional Career & Compensation", icon="💼", on_edit_toggle=self._on_card_edit_toggle)

        # Left Column: Role, Employer, Experience, Notice
        # 1. Current Job Title
        self.val_title = self._view_label("RPA Developer / AI Automation Engineer")
        self.txt_title = self._line_edit("e.g. Senior RPA Developer")
        card.add_row(0, 0, DataSheetRow("Current Role *", self.val_title, self.txt_title))

        # 2. Current Employer
        self.val_employer = self._view_label("AventIQ AI")
        self.txt_employer = self._line_edit("e.g. AventIQ AI")
        card.add_row(1, 0, DataSheetRow("Employer", self.val_employer, self.txt_employer))

        # 3. Total Experience
        self.val_experience = self._view_label("2.0 Years")
        self.spn_experience = QDoubleSpinBox()
        self.spn_experience.setMinimumHeight(34)
        self.spn_experience.setRange(0.0, 50.0)
        self.spn_experience.setSingleStep(0.5)
        self.spn_experience.setDecimals(1)
        self.spn_experience.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }}
        """)
        card.add_row(2, 0, DataSheetRow("Experience *", self.val_experience, self.spn_experience))

        # 4. Notice Period
        self.val_notice = self._view_label("30 Days")
        self.spn_notice = QSpinBox()
        self.spn_notice.setMinimumHeight(34)
        self.spn_notice.setRange(0, 365)
        self.spn_notice.setSingleStep(15)
        self.spn_notice.setValue(30)
        self.spn_notice.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 13px;
            }}
        """)
        card.add_row(3, 0, DataSheetRow("Notice Period *", self.val_notice, self.spn_notice))

        # Right Column: Compensation & Headline
        # 1. Current CTC
        self.val_current_ctc = self._view_label("₹3,50,000 (3.50 LPA)")
        cur_container = QWidget()
        cur_container.setStyleSheet("background: transparent; border: none;")
        cur_layout = QHBoxLayout(cur_container)
        cur_layout.setContentsMargins(0, 0, 0, 0)
        cur_layout.setSpacing(8)
        self.txt_current_ctc = self._line_edit("350000")
        self.lbl_cur_ctc_helper = QLabel("3.50 LPA")
        self.lbl_cur_ctc_helper.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self.txt_current_ctc.textChanged.connect(self._update_ctc_helpers)
        cur_layout.addWidget(self.txt_current_ctc, 1)
        cur_layout.addWidget(self.lbl_cur_ctc_helper)
        card.add_row(0, 1, DataSheetRow("Current CTC *", self.val_current_ctc, cur_container))

        # 2. Expected CTC
        self.val_expected_ctc = self._view_label("₹5,50,000 (5.50 LPA)")
        exp_container = QWidget()
        exp_container.setStyleSheet("background: transparent; border: none;")
        exp_layout = QHBoxLayout(exp_container)
        exp_layout.setContentsMargins(0, 0, 0, 0)
        exp_layout.setSpacing(8)
        self.txt_expected_ctc = self._line_edit("550000")
        self.lbl_exp_ctc_helper = QLabel("5.50 LPA")
        self.lbl_exp_ctc_helper.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px;")
        self.txt_expected_ctc.textChanged.connect(self._update_ctc_helpers)
        exp_layout.addWidget(self.txt_expected_ctc, 1)
        exp_layout.addWidget(self.lbl_exp_ctc_helper)
        card.add_row(1, 1, DataSheetRow("Expected CTC *", self.val_expected_ctc, exp_container))

        # 3. Target Salary Hike
        self.val_target_hike = self._view_label("+57.1% (₹2.00 LPA)")
        lbl_hike_mode = QLabel("Automatic Hike Calculation")
        lbl_hike_mode.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        card.add_row(2, 1, DataSheetRow("Target Hike", self.val_target_hike, lbl_hike_mode))

        # 4. Professional Headline
        self.val_headline = self._view_label("RPA Developer | AI Automation Engineer | Python")
        self.txt_headline = self._line_edit("e.g. RPA Developer | AI Automation Engineer")
        card.add_row(3, 1, DataSheetRow("Headline", self.val_headline, self.txt_headline))

        return card

    # ----------------------------------------------------------------------
    # Card 3: Technical Skills & Summary
    # ----------------------------------------------------------------------

    def _build_skills_card(self) -> DataSheetCard:
        card = DataSheetCard(title="Technical Skills & Professional Bio", icon="🛠️", on_edit_toggle=self._on_card_edit_toggle)

        # 1. Skills Pills Container
        self.skills_pill_container = QWidget()
        self.skills_pill_layout = QHBoxLayout(self.skills_pill_container)
        self.skills_pill_layout.setContentsMargins(0, 4, 0, 4)
        self.skills_pill_layout.setSpacing(6)

        self.txt_skills = self._line_edit("e.g. Automation Anywhere, Python, SQL, REST API, SAP GUI, IDP, OCR")
        card.add_row(0, 0, DataSheetRow("Core Skills", self.skills_pill_container, self.txt_skills))

        # Proficiency label on right
        card.add_row(0, 1, DataSheetRow("Proficiency", self._view_label("Senior / Advanced"), self._view_label("Senior / Advanced")))

        # 2. Professional Summary (SPACIOUS Multi-line Box)
        self.val_summary = QTextEdit()
        self.val_summary.setReadOnly(True)
        self.val_summary.setMinimumHeight(110)
        self.val_summary.setMaximumHeight(160)
        self.val_summary.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)

        self.txt_summary = QTextEdit()
        self.txt_summary.setPlaceholderText("Concise career overview, key competencies, and domains...")
        self.txt_summary.setMinimumHeight(110)
        self.txt_summary.setMaximumHeight(160)
        self.txt_summary.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }}
            QTextEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        card.add_row(1, 0, DataSheetRow("Summary / Bio", self.val_summary, self.txt_summary, min_height=100, max_height=140), col_span=2)

        # 3. Default Cover Letter Pitch (EXPANSIVE Full-Width Box: 240px min height!)
        self.val_cover_letter = QTextEdit()
        self.val_cover_letter.setReadOnly(True)
        self.val_cover_letter.setMinimumHeight(240)
        self.val_cover_letter.setMaximumHeight(340)
        self.val_cover_letter.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }}
        """)

        self.txt_cover_letter = QTextEdit()
        self.txt_cover_letter.setPlaceholderText("Default cover letter template or pitch for job applications...")
        self.txt_cover_letter.setMinimumHeight(240)
        self.txt_cover_letter.setMaximumHeight(340)
        self.txt_cover_letter.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 12px;
                font-size: 13px;
                line-height: 1.5;
            }}
            QTextEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        card.add_row(2, 0, DataSheetRow("Cover Letter", self.val_cover_letter, self.txt_cover_letter, min_height=250, max_height=350), col_span=2)

        return card

    # ----------------------------------------------------------------------
    # Card 4: Online Profiles & Portfolios
    # ----------------------------------------------------------------------

    def _build_links_card(self) -> DataSheetCard:
        card = DataSheetCard(title="Online Profiles & Portfolios", icon="🌐", on_edit_toggle=self._on_card_edit_toggle)

        # 1. LinkedIn
        self.widget_val_linkedin, self.lbl_val_linkedin, self.btn_open_linkedin = self._create_link_widget("")
        self.txt_linkedin = self._line_edit("https://www.linkedin.com/in/username/")
        card.add_row(0, 0, DataSheetRow("LinkedIn", self.widget_val_linkedin, self.txt_linkedin))

        # 2. GitHub
        self.widget_val_github, self.lbl_val_github, self.btn_open_github = self._create_link_widget("")
        self.txt_github = self._line_edit("https://github.com/username")
        card.add_row(0, 1, DataSheetRow("GitHub", self.widget_val_github, self.txt_github))

        # 3. Portfolio
        self.widget_val_portfolio, self.lbl_val_portfolio, self.btn_open_portfolio = self._create_link_widget("")
        self.txt_portfolio = self._line_edit("https://myportfolio.dev")
        card.add_row(1, 0, DataSheetRow("Portfolio", self.widget_val_portfolio, self.txt_portfolio))

        # 4. Status
        val_status = QLabel("All accounts synced with bot engine")
        val_status.setStyleSheet(f"color: #3FB950; font-size: 12px; font-weight: 500; border: none;")
        card.add_row(1, 1, DataSheetRow("Sync Status", val_status, val_status))

        return card

    def _create_link_widget(self, url: str) -> Tuple[QWidget, QLabel, QPushButton]:
        container = QWidget()
        container.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        lbl = QLabel(url if url else "Not set")
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['accent'] if url else COLORS['text_muted']};
                font-size: 13px;
                font-weight: 500;
                border: none;
            }}
        """)
        layout.addWidget(lbl)

        btn_open = QPushButton("Open ↗")
        btn_open.setCursor(Qt.PointingHandCursor)
        btn_open.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['accent']};
                border: none;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        btn_open.setVisible(bool(url))
        layout.addWidget(btn_open)
        layout.addStretch()
        return container, lbl, btn_open

    def _update_link_widget(self, lbl: QLabel, btn: QPushButton, url: str) -> None:
        url = (url or "").strip()
        lbl.setText(url if url else "Not set")
        lbl.setStyleSheet(f"""
            QLabel {{
                color: {COLORS['accent'] if url else COLORS['text_muted']};
                font-size: 13px;
                font-weight: 500;
                border: none;
            }}
        """)
        btn.setVisible(bool(url))
        try:
            btn.disconnect()
        except Exception:
            pass
        if url:
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))

    # ----------------------------------------------------------------------
    # Helper & Event Handlers
    # ----------------------------------------------------------------------

    def _render_skill_pills(self, skills_list: List[str]) -> None:
        """Renders skills as attractive badges/pills in View mode."""
        while self.skills_pill_layout.count():
            item = self.skills_pill_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for skill in skills_list[:7]:  # Show top 7 skills
            pill = QLabel(skill)
            pill.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text']};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                    border-radius: 4px;
                    border: 1px solid {COLORS['border']};
                }}
            """)
            self.skills_pill_layout.addWidget(pill)

        if len(skills_list) > 7:
            more_pill = QLabel(f"+{len(skills_list) - 7} more")
            more_pill.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text_muted']};
                    font-size: 10px;
                    font-weight: 600;
                    padding: 3px 6px;
                    border-radius: 4px;
                    border: 1px solid {COLORS['border']};
                }}
            """)
            self.skills_pill_layout.addWidget(more_pill)

        self.skills_pill_layout.addStretch()

    def _update_ctc_helpers(self) -> None:
        """Calculates and displays LPA helpers, target hike, and banner stats."""
        cur_lpa = 0.0
        c_text = self.txt_current_ctc.text().strip()
        if c_text.isdigit():
            cur_val = int(c_text)
            cur_lpa = cur_val / 100000
            self.lbl_cur_ctc_helper.setText(f"{cur_lpa:.2f} LPA")
            self.val_current_ctc.setText(f"₹{cur_val:,} ({cur_lpa:.2f} LPA)")
            self.lbl_banner_cur_ctc.setText(f"₹{cur_lpa:.2f} LPA")
        else:
            self.lbl_cur_ctc_helper.setText("0.0 LPA")
            self.val_current_ctc.setText("-")
            self.lbl_banner_cur_ctc.setText("₹0.00 LPA")

        exp_lpa = 0.0
        e_text = self.txt_expected_ctc.text().strip()
        if e_text.isdigit():
            exp_val = int(e_text)
            exp_lpa = exp_val / 100000
            self.lbl_exp_ctc_helper.setText(f"{exp_lpa:.2f} LPA")
            self.val_expected_ctc.setText(f"₹{exp_val:,} ({exp_lpa:.2f} LPA)")
            self.lbl_banner_exp_ctc.setText(f"₹{exp_lpa:.2f} LPA")
        else:
            self.lbl_exp_ctc_helper.setText("0.0 LPA")
            self.val_expected_ctc.setText("-")
            self.lbl_banner_exp_ctc.setText("₹0.00 LPA")

        # Calculate Target Hike %
        if cur_lpa > 0 and exp_lpa > 0:
            diff = exp_lpa - cur_lpa
            pct = (diff / cur_lpa) * 100
            sign = "+" if pct >= 0 else ""
            self.val_target_hike.setText(f"{sign}{pct:.1f}% (₹{diff:.2f} LPA)")
        else:
            self.val_target_hike.setText("-")

    def load_profile(self) -> None:
        """Loads candidate personal and professional information from database."""
        user, profile, pro = self.service.get_primary_user_profile()
        if not user:
            return

        self.current_user_id = user.id

        # 1. Personal details
        fname = ""
        mname = ""
        lname = ""
        city = ""
        state = ""
        country = "India"
        zipcode = ""
        address = ""
        willing = True

        if profile:
            fname = profile.first_name or ""
            mname = profile.middle_name or ""
            lname = profile.last_name or ""
            city = profile.current_city or ""
            state = profile.state or ""
            country = profile.country or "India"
            zipcode = profile.zipcode or ""
            address = profile.address or ""
            willing = bool(profile.willing_to_relocate)
        else:
            parts = (user.name or "").split()
            fname = parts[0] if parts else ""
            lname = " ".join(parts[1:]) if len(parts) > 1 else ""

        email = user.email or ""
        phone = user.phone or ""

        # Update Edit Inputs
        self.txt_first_name.setText(fname)
        self.txt_middle_name.setText(mname)
        self.txt_last_name.setText(lname)
        self.txt_email.setText(email)
        self.txt_phone.setText(phone)
        self.txt_city.setText(city)
        self.txt_state.setText(state)
        self.txt_zipcode.setText(zipcode)
        self.txt_country.setText(country)
        self.txt_address.setText(address)
        self.chk_relocate.setChecked(willing)

        # Update View Labels
        self.val_first_name.setText(fname or "-")
        self.val_middle_name.setText(mname or "-")
        self.val_last_name.setText(lname or "-")
        self.val_email.setText(email or "-")
        self.val_phone.setText(phone or "-")
        self.val_city.setText(city or "-")
        self.val_state_zip.setText(f"{state}, {zipcode}".strip(", ") or "-")
        self.val_country.setText(country or "-")
        self.val_address.setText(address or "-")
        self.val_relocate.setText("Willing to Relocate (India & Remote)" if willing else "Prefers Current Location")

        # Update Banner Profile Info
        full_name = f"{fname} {lname}".strip() or user.name or "Candidate"
        self.lbl_banner_name.setText(full_name)
        initials = "".join([part[0].upper() for part in full_name.split()[:2]]) if full_name else "CP"
        self.avatar_badge.setText(initials)
        self.lbl_banner_contact.setText(f"{email}  •  {phone}  •  {city}, {country}")

        # 2. Professional details
        title = ""
        employer = ""
        exp = 0.0
        notice = 30
        cur_ctc = 350000
        exp_ctc = 550000
        skills_list = []
        headline = ""
        summary = ""
        cover_letter = ""
        linkedin = ""
        github = ""
        portfolio = ""

        if pro:
            title = pro.current_title or ""
            employer = pro.current_employer or ""
            exp = float(pro.years_of_experience or 0.0)
            cur_ctc = pro.current_ctc if pro.current_ctc is not None else 350000
            exp_ctc = pro.expected_ctc if pro.expected_ctc is not None else 550000
            notice = int(pro.notice_period_days or 30)
            skills_list = pro.skills or []
            headline = pro.headline or ""
            summary = pro.summary or ""
            cover_letter = pro.cover_letter or ""
            linkedin = pro.linkedin_url or ""
            github = pro.github_url or ""
            portfolio = pro.portfolio_url or ""

        # Update Edit Inputs
        self.txt_title.setText(title)
        self.txt_employer.setText(employer)
        self.spn_experience.setValue(exp)
        self.spn_notice.setValue(notice)
        self.txt_current_ctc.setText(str(cur_ctc))
        self.txt_expected_ctc.setText(str(exp_ctc))
        self.txt_skills.setText(", ".join(skills_list))
        self.txt_headline.setText(headline)
        self.txt_summary.setText(summary)
        self.txt_cover_letter.setText(cover_letter)
        self.txt_linkedin.setText(linkedin)
        self.txt_github.setText(github)
        self.txt_portfolio.setText(portfolio)

        # Update View Labels
        self.val_title.setText(title or "-")
        self.val_employer.setText(employer or "-")
        self.val_experience.setText(f"{exp:.1f} Years")
        self.val_notice.setText(f"{notice} Days")
        self.val_headline.setText(headline or "-")
        self.val_summary.setPlainText(summary or "No summary configured yet.")
        self.val_cover_letter.setPlainText(cover_letter or "No cover letter pitch configured yet.")
        self.lbl_banner_exp.setText(f"{exp:.1f} Yrs")
        self.lbl_banner_notice.setText(f"{notice} Days")
        if title:
            self.lbl_banner_badge.setText("RPA & AI AUTOMATION" if "rpa" in title.lower() else title.upper()[:24])

        self._render_skill_pills(skills_list)
        self._update_link_widget(self.lbl_val_linkedin, self.btn_open_linkedin, linkedin)
        self._update_link_widget(self.lbl_val_github, self.btn_open_github, github)
        self._update_link_widget(self.lbl_val_portfolio, self.btn_open_portfolio, portfolio)
        self._update_ctc_helpers()
        self._refresh_readiness_indicator()

    def _refresh_readiness_indicator(self) -> None:
        """Updates readiness score and badge based on current saved database state."""
        if not self.current_user_id:
            return

        res = self.service.validate_completeness(self.current_user_id)
        score = res.get("score", 0)
        is_ready = res.get("is_ready", False)

        self.lbl_score.setText(f"Readiness Score: {score}%")
        if is_ready:
            self.badge_status.update_style("success")
            self.badge_status.setText("Application Ready")
            self.lbl_readiness_hint.setText("All essential candidate parameters are verified.")
        else:
            self.badge_status.update_style("warning")
            self.badge_status.setText("Incomplete")
            missing = res.get("missing_critical", [])
            self.lbl_readiness_hint.setText(f"Missing essential field(s): {', '.join(missing[:3])}")

    def _on_save_clicked(self) -> None:
        """Saves current form inputs into database and refreshes view in real time."""
        if not self.current_user_id:
            return

        personal_data = {
            "first_name": self.txt_first_name.text().strip(),
            "middle_name": self.txt_middle_name.text().strip() or None,
            "last_name": self.txt_last_name.text().strip(),
            "email": self.txt_email.text().strip(),
            "phone_number": self.txt_phone.text().strip() or None,
            "current_city": self.txt_city.text().strip(),
            "state": self.txt_state.text().strip() or None,
            "country": self.txt_country.text().strip() or "India",
            "zipcode": self.txt_zipcode.text().strip() or None,
            "address": self.txt_address.text().strip() or None,
            "willing_to_relocate": self.chk_relocate.isChecked(),
        }

        professional_data = {
            "title": self.txt_title.text().strip(),
            "current_employer": self.txt_employer.text().strip() or None,
            "years_of_experience": self.spn_experience.value(),
            "current_ctc": self.txt_current_ctc.text().strip() or None,
            "expected_ctc": self.txt_expected_ctc.text().strip() or None,
            "notice_period_days": self.spn_notice.value(),
            "skills": self.txt_skills.text().strip(),
            "headline": self.txt_headline.text().strip() or None,
            "summary": self.txt_summary.toPlainText().strip() or None,
            "cover_letter": self.txt_cover_letter.toPlainText().strip() or None,
            "linkedin_url": self.txt_linkedin.text().strip() or None,
            "github_url": self.txt_github.text().strip() or None,
            "portfolio_url": self.txt_portfolio.text().strip() or None,
        }

        success, err = self.service.save_profile(
            user_id=self.current_user_id,
            personal_data=personal_data,
            professional_data=professional_data,
        )

        if success:
            self.load_profile()
            self.is_global_edit_mode = False
            self.btn_toggle_edit.setText("Edit Profile ✏️")
            for card in self.cards:
                card.set_edit_mode(False)
            self.notification_bar.show_message("success", "Profile successfully saved to database and synced!", duration_ms=5000)
        else:
            self.notification_bar.show_message("danger", f"Failed to save profile: {err}", duration_ms=6000)

    def _on_reset_clicked(self) -> None:
        """Discards uncommitted form edits and reloads last saved values."""
        self.load_profile()
        self.is_global_edit_mode = False
        self.btn_toggle_edit.setText("Edit Profile ✏️")
        for card in self.cards:
            card.set_edit_mode(False)
        self.notification_bar.show_message("info", "Profile reset to latest saved database state.")

    def _on_validate_clicked(self) -> None:
        """Performs on-demand validation and reports readiness status."""
        if not self.current_user_id:
            return

        res = self.service.validate_completeness(self.current_user_id)
        if res.get("is_ready"):
            self.notification_bar.show_message(
                "success",
                f"Profile Readiness: {res['score']}% — Ready for LinkedIn & Naukri automated submissions!",
                duration_ms=5000,
            )
        else:
            missing = res.get("missing_critical", [])
            self.notification_bar.show_message(
                "warning",
                f"Readiness: {res['score']}% — Missing required fields: {', '.join(missing)}",
                duration_ms=6000,
            )
        self._refresh_readiness_indicator()
