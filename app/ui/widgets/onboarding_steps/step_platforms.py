"""
Step 8: Supported Platforms Configuration.
Provides real platform cards with tailored inputs:
- Credentials for LinkedIn, Naukri, Foundit.
- Passwordless / Session Cookie configuration for Indeed and Glassdoor.
- Universal ATS engine (no credentials required).
- Transparent 2-3 line explanation of how it works, why it's required, and security notes.
"""

from typing import Dict, Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QFrame, QScrollArea
)
from app.ui.theme import COLORS


class RealPlatformCard(QFrame):
    """Card representing an active platform with tailored authentication controls."""

    def __init__(self, platform_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.p_data = platform_data
        self.txt_username = None
        self.txt_password = None
        self.txt_search_location = None
        self._init_ui()

    def _init_ui(self):
        self.setObjectName("platform_card")
        self.setStyleSheet(f"""
            #platform_card {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            #platform_card QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        # Header Row
        h_row = QHBoxLayout()
        lbl_name = QLabel(f"🌐 {self.p_data['name']}")
        lbl_name.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        h_row.addWidget(lbl_name)

        status_text = self.p_data.get("status_label", "Available")
        self.lbl_status = QLabel(status_text)
        is_ready = "✓" in status_text
        self.lbl_status.setStyleSheet(f"""
            color: {COLORS['success'] if is_ready else COLORS['text_muted']};
            background-color: {COLORS['success_subtle'] if is_ready else COLORS['surface_alt']};
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        h_row.addWidget(self.lbl_status)
        h_row.addStretch()
        layout.addLayout(h_row)

        p_id = self.p_data["id"].lower()

        # Explanatory & Workflow Details (How it works + Why required + Security note)
        if p_id in ["indeed", "glassdoor"]:
            how_text = (
                "• <b>How it works:</b> JobPilot connects to Indeed/Glassdoor using your local browser session cookies. "
                "No password is required or requested.<br>"
                "• <b>Why required:</b> Authenticated browser sessions allow searching matched listings and auto-filling Easy Apply questionnaires without CAPTCHAs.<br>"
                "• <b>🔒 Security Note:</b> Only optional search preferences or account emails are configured here. Session cookies remain in your local Chrome profile."
            )
        elif p_id in ["universal"]:
            how_text = (
                "• <b>How it works:</b> Automates public career pages on Greenhouse, Lever, Ashby, and Workday using Universal AI.<br>"
                "• <b>Why required:</b> Enables autonomous application submissions directly on employer websites.<br>"
                "• <b>🔒 Security Note:</b> Zero credentials or portal logins required. Fully standalone and operational out of the box."
            )
        else:
            how_text = (
                f"• <b>How it works:</b> Launches stealth automation to search {self.p_data['name']} jobs, match requirements against your profile, and execute Easy Apply.<br>"
                "• <b>Why required:</b> Login authentication allows JobPilot to apply directly on your behalf and access personalized job feeds.<br>"
                "• <b>🔒 Security Note:</b> Your password is encrypted and stored exclusively in your local OS Keyring. Zero credentials are ever transmitted to external servers."
            )

        lbl_how = QLabel(how_text)
        lbl_how.setWordWrap(True)
        lbl_how.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.4;")
        layout.addWidget(lbl_how)

        # Tailored Configurable Inputs
        if p_id in ["indeed", "glassdoor"]:
            # Passwordless / Session Cookie based platform: ask only configurable search parameters
            grid = QHBoxLayout()
            grid.setSpacing(8)

            self.txt_username = QLineEdit()
            self.txt_username.setPlaceholderText("Account Email (Optional, for session identification)")
            self.txt_username.setStyleSheet(self._input_qss())
            grid.addWidget(self.txt_username, 1)

            self.txt_search_location = QLineEdit()
            self.txt_search_location.setPlaceholderText("Preferred Search Location (e.g. Remote / India)")
            self.txt_search_location.setStyleSheet(self._input_qss())
            grid.addWidget(self.txt_search_location, 1)

            layout.addLayout(grid)
            self.txt_password = None

        elif p_id not in ["universal"]:
            # Standard credential-supporting platforms (LinkedIn, Naukri, Foundit)
            grid = QHBoxLayout()
            grid.setSpacing(8)

            self.txt_username = QLineEdit()
            self.txt_username.setPlaceholderText("Username / Email")
            self.txt_username.setStyleSheet(self._input_qss())
            grid.addWidget(self.txt_username, 1)

            self.txt_password = QLineEdit()
            self.txt_password.setEchoMode(QLineEdit.Password)
            self.txt_password.setPlaceholderText("Password (OS Keyring)")
            self.txt_password.setStyleSheet(self._input_qss())
            grid.addWidget(self.txt_password, 1)

            layout.addLayout(grid)
        else:
            self.txt_username = None
            self.txt_password = None

    def get_credentials(self) -> Dict[str, Any]:
        result = {}
        if self.txt_username:
            u = self.txt_username.text().strip()
            if u:
                result["username"] = u
        if self.txt_password:
            p = self.txt_password.text().strip()
            if p:
                result["password"] = p
        if self.txt_search_location:
            loc = self.txt_search_location.text().strip()
            if loc:
                result["location"] = loc
        return result

    def _input_qss(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
        """


class StepPlatformsWidget(QWidget):
    """Step 8: Dynamically loads and displays all real supported platforms."""
    skip_requested = Signal()

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self.cards: Dict[str, RealPlatformCard] = {}
        self._init_ui()
        self.load_platforms()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        lbl_badge = QLabel("STEP 8: JOB PLATFORM CONNECTORS")
        lbl_badge.setFixedHeight(22)
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 2px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("Connected Job Platforms & Portals")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Connect portals to unlock autonomous job searching and Easy Apply automation. "
            "You can configure credentials now or skip this step and sign in later via browser sessions."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # Cards Container
        self.cards_layout = QVBoxLayout()
        self.cards_layout.setSpacing(10)
        layout.addLayout(self.cards_layout)
        layout.addStretch(1)

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def load_platforms(self):
        # Clear existing cards
        while self.cards_layout.count() > 0:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

        platforms_list = []
        if hasattr(self.setup_service, "get_platform_statuses"):
            platforms_list = self.setup_service.get_platform_statuses()
        elif hasattr(self.setup_service, "get_supported_platforms"):
            platforms_list = self.setup_service.get_supported_platforms()

        for p_data in platforms_list:
            card = RealPlatformCard(p_data)
            self.cards[p_data["id"]] = card
            self.cards_layout.addWidget(card)

    def get_platforms_payload(self) -> Dict[str, Any]:
        payload = {}
        for p_id, card in self.cards.items():
            creds = card.get_credentials()
            if creds:
                payload[p_id] = creds
        return payload
