"""Current Job inspector card widget for Automation Control Center.

Displays real metadata for the job currently under evaluation or submission,
handling optional fields gracefully without fabricating missing attributes,
and provides a dynamic, platform-aware browser launch button.
"""

from typing import Dict, Optional
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS
from app.ui.widgets.automation.state import AutomationUIState


class CurrentJobCard(QFrame):
    """Card displaying active job under evaluation or application."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._job_url: Optional[str] = None
        self._current_state_ref: Optional[AutomationUIState] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("current_job_card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header row
        top_row = QHBoxLayout()
        self.lbl_hdr = QLabel("Current Job Workspace")
        top_row.addWidget(self.lbl_hdr)
        top_row.addStretch()

        self.lbl_platform_tag = QLabel("Idle")
        top_row.addWidget(self.lbl_platform_tag)
        layout.addLayout(top_row)

        # Content container
        self.content_widget = QWidget()
        c_layout = QVBoxLayout(self.content_widget)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(6)

        self.lbl_title = QLabel("No active job")
        self.lbl_title.setWordWrap(True)
        c_layout.addWidget(self.lbl_title)

        self.lbl_company = QLabel("Jobs under evaluation will appear here in real time.")
        self.lbl_company.setWordWrap(True)
        c_layout.addWidget(self.lbl_company)

        self.lbl_location = QLabel("")
        self.lbl_location.setVisible(False)
        c_layout.addWidget(self.lbl_location)

        layout.addWidget(self.content_widget)

        # Action row
        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch()

        self.btn_open_job = QPushButton("↗ View Job")
        self.btn_open_job.setFixedHeight(28)
        self.btn_open_job.setEnabled(False)
        self.btn_open_job.clicked.connect(self._on_open_job_clicked)
        action_row.addWidget(self.btn_open_job)

        layout.addLayout(action_row)
        self._refresh_styles()

    def update_from_state(self, state: AutomationUIState) -> None:
        """Updates current job display based on UI state snapshot."""
        self._current_state_ref = state
        self._job_url = state.current_job_url
        tokens = COLORS

        if state.current_job_title:
            self.lbl_title.setText(state.current_job_title)
            self.lbl_title.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 14px; font-weight: 700;")

            comp = state.current_job_company or "Company not specified"
            self.lbl_company.setText(comp)
            self.lbl_company.setStyleSheet(f"color: {tokens.get('primary', '#FF5F15')}; font-size: 12px; font-weight: 600;")

            if state.current_job_location:
                self.lbl_location.setText(f"Location: {state.current_job_location}")
                self.lbl_location.setVisible(True)
            else:
                self.lbl_location.setVisible(False)

            self.lbl_platform_tag.setText(state.platform.capitalize())
            self.lbl_platform_tag.setStyleSheet(f"""
                QLabel {{
                    background-color: {tokens.get('primary_subtle', '#FF5F1518')};
                    color: {tokens.get('primary', '#FF5F15')};
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 8px;
                    border-radius: 6px;
                    border: 1px solid {tokens.get('primary', '#FF5F15')}40;
                }}
            """)

            # Platform-aware button label
            p_key = (state.platform or "").lower()
            if "linkedin" in p_key:
                btn_label = "↗ Open on LinkedIn"
            elif "naukri" in p_key:
                btn_label = "↗ Open on Naukri"
            elif "indeed" in p_key:
                btn_label = "↗ Open on Indeed"
            elif "foundit" in p_key:
                btn_label = "↗ Open on Foundit"
            elif "glassdoor" in p_key:
                btn_label = "↗ Open on Glassdoor"
            else:
                btn_label = "↗ Open Job in Browser"
            self.btn_open_job.setText(btn_label)

        else:
            self.lbl_title.setText("No active job")
            self.lbl_title.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 13px; font-weight: 600;")
            self.lbl_company.setText("Jobs under evaluation will appear here in real time.")
            self.lbl_company.setStyleSheet(f"color: {tokens.get('text_dark', '#6E7681')}; font-size: 12px;")
            self.lbl_location.setVisible(False)
            self.lbl_platform_tag.setText("Idle")
            self.lbl_platform_tag.setStyleSheet(f"""
                QLabel {{
                    background-color: {tokens.get('surface_alt', '#1C2128')};
                    color: {tokens.get('text_muted', '#8B949E')};
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 8px;
                    border-radius: 6px;
                    border: 1px solid {tokens.get('border', '#262C36')};
                }}
            """)
            self.btn_open_job.setText("↗ View Job")

        has_url = bool(self._job_url)
        self.btn_open_job.setEnabled(has_url)
        self.btn_open_job.setToolTip(self._job_url if has_url else "No direct job URL available")

        self._refresh_styles()

    def _on_open_job_clicked(self) -> None:
        """Opens job URL in default external browser safely."""
        if self._job_url:
            QDesktopServices.openUrl(QUrl(self._job_url))

    def _refresh_styles(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QFrame#current_job_card {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 10px;
            }}
        """)
        self.lbl_hdr.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 13px; font-weight: 700;")
        self.btn_open_job.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 11px;
                font-weight: 600;
                padding: 0 12px;
                border-radius: 6px;
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                border-color: {tokens.get('primary', '#FF5F15')};
            }}
            QPushButton:disabled {{
                color: {tokens.get('text_dark', '#6E7681')};
                border-color: {tokens.get('border', '#262C36')};
            }}
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
        if self._current_state_ref:
            self.update_from_state(self._current_state_ref)
