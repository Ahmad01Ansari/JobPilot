"""Top configuration health bar providing real, backend-verified status chips."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)
from app.ui.theme import COLORS
from app.ui.views.settings.components.status_chip import StatusChip


class ConfigurationHealthBar(QFrame):
    """Top status bar displaying factual configuration health chips linked to their respective sections."""

    section_navigated = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("ConfigurationHealthBar")
        self.setStyleSheet(f"""
            QFrame#ConfigurationHealthBar {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 6px 12px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        lbl_lead = QLabel("CONFIGURATION HEALTH:")
        lbl_lead.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLORS.get('text_muted', '#8B949E')};
            letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_lead)

        # 1. Automation Status
        self.chip_automation = StatusChip("automation", "Automation Safe", "success")
        self.chip_automation.clicked.connect(self.section_navigated.emit)
        layout.addWidget(self.chip_automation)

        # 2. AI Status
        self.chip_ai = StatusChip("ai", "AI Configured", "neutral")
        self.chip_ai.clicked.connect(self.section_navigated.emit)
        layout.addWidget(self.chip_ai)

        # 3. Email Status
        self.chip_email = StatusChip("credentials", "Email: Not tested", "neutral")
        self.chip_email.clicked.connect(self.section_navigated.emit)
        layout.addWidget(self.chip_email)

        # 4. Credentials Count
        self.chip_credentials = StatusChip("credentials", "Credentials 0/2", "neutral")
        self.chip_credentials.clicked.connect(self.section_navigated.emit)
        layout.addWidget(self.chip_credentials)

        # 5. Backup Status
        self.chip_backup = StatusChip("backup", "Backup: Checking", "neutral")
        self.chip_backup.clicked.connect(self.section_navigated.emit)
        layout.addWidget(self.chip_backup)

        layout.addStretch()

    def update_automation_status(self, safe_active: bool) -> None:
        if safe_active:
            self.chip_automation.update_status("success", "Automation Safe")
        else:
            self.chip_automation.update_status("warning", "Unattended Mode")

    def update_ai_status(self, is_enabled: bool, is_tested: bool = False, latency_ms: float = 0.0) -> None:
        if not is_enabled:
            self.chip_ai.update_status("neutral", "AI Disabled")
        elif is_tested:
            lat_str = f" ({round(latency_ms)}ms)" if latency_ms > 0 else ""
            self.chip_ai.update_status("success", f"AI Tested{lat_str}")
        else:
            self.chip_ai.update_status("info", "AI Configured")

    def update_email_status(self, is_configured: bool, is_verified: bool = False) -> None:
        if not is_configured:
            self.chip_email.update_status("neutral", "Email: Not configured")
        elif is_verified:
            self.chip_email.update_status("success", "Email Verified")
        else:
            self.chip_email.update_status("info", "Email Configured")

    def update_credentials_count(self, configured_count: int, total_count: int = 2) -> None:
        label = f"Credentials {configured_count}/{total_count}"
        if configured_count == total_count:
            self.chip_credentials.update_status("success", label)
        elif configured_count > 0:
            self.chip_credentials.update_status("warning", label)
        else:
            self.chip_credentials.update_status("neutral", label)

    def update_backup_status(self, has_backup: bool, is_verified: bool = False) -> None:
        if has_backup and is_verified:
            self.chip_backup.update_status("success", "Backup Verified")
        elif has_backup:
            self.chip_backup.update_status("info", "Backup Available")
        else:
            self.chip_backup.update_status("neutral", "No backup found")
