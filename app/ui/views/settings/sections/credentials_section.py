"""Credentials & Security Center managing platform accounts, recruiter outreach email, and encryption health."""

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from app.services.secrets_service import SecretsService
from app.ui.theme import COLORS
from app.ui.views.settings.components.credential_dialog import CredentialDialog
from app.ui.views.settings.components.platform_card import PlatformCard
from app.ui.views.settings.workers.email_test_worker import EmailTestWorker

# Resolve SVG icon paths for password visibility toggle
_ICONS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "assets" / "icons"
_EYE_ICON_PATH = str(_ICONS_DIR / "eye.svg")
_EYE_OFF_ICON_PATH = str(_ICONS_DIR / "eye_off.svg")


class CredentialsSection(QWidget):
    """Security center managing encrypted credentials, email outreach, and local encryption health."""

    credentials_updated = Signal(int)  # Emits count of configured credentials (0..2)
    email_test_completed = Signal(bool)
    email_changed = Signal()

    def __init__(
        self,
        secrets_service: SecretsService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.secrets_service = secrets_service
        self._email_worker: Optional[EmailTestWorker] = None
        self.txt_li_pwd = QLineEdit()
        self.txt_li_pwd.setEchoMode(QLineEdit.Password)
        self.txt_nk_pwd = QLineEdit()
        self.txt_nk_pwd.setEchoMode(QLineEdit.Password)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 24, 16)
        layout.setSpacing(16)

        # Header
        lbl_head = QLabel("Credentials & Security Center")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Manage machine-encrypted platform logins and automated recruiter outreach email credentials.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # 1. Encryption Health Banner
        health_card = QFrame()
        health_card.setObjectName("HealthCard")
        health_card.setStyleSheet(f"""
            QFrame#HealthCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-left: 3px solid {COLORS.get('success', '#2EA043')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        h_layout = QVBoxLayout(health_card)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(4)

        lbl_h_title = QLabel("🔐 Local Credential Encryption: ✓ Active")
        lbl_h_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('success', '#2EA043')};")
        h_layout.addWidget(lbl_h_title)

        lbl_h_desc = QLabel("Credentials are encrypted with machine-local Fernet keys and never logged in plaintext.")
        lbl_h_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        h_layout.addWidget(lbl_h_desc)

        # Collapsible technical details button
        self.btn_tech_details = QPushButton("View Technical Details ▾")
        self.btn_tech_details.setCursor(Qt.PointingHandCursor)
        self.btn_tech_details.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {COLORS.get('info', '#388BFD')};
                font-size: 11px;
                font-weight: 600;
                text-align: left;
                padding: 0;
            }}
        """)
        self.btn_tech_details.clicked.connect(self._toggle_tech_details)
        h_layout.addWidget(self.btn_tech_details)

        self.box_tech_details = QWidget()
        self.box_tech_details.setVisible(False)
        td_layout = QVBoxLayout(self.box_tech_details)
        td_layout.setContentsMargins(0, 4, 0, 0)
        td_layout.setSpacing(2)

        key_path = getattr(self.secrets_service, "_key_path", Path.home() / ".jobpilot" / ".key")
        lbl_path = QLabel(f"• Key location: <code>{key_path}</code> (POSIX 0600)")
        lbl_path.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        td_layout.addWidget(lbl_path)

        lbl_cipher = QLabel("• Cipher: Authenticated AES-128-CBC with HMAC-SHA256")
        lbl_cipher.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        td_layout.addWidget(lbl_cipher)
        h_layout.addWidget(self.box_tech_details)

        layout.addWidget(health_card)

        # 2. Platform Accounts Group
        lbl_platforms = QLabel("Platform Accounts")
        lbl_platforms.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_platforms)

        self.card_linkedin = PlatformCard("linkedin", "LinkedIn", "💼", self)
        self.card_linkedin.edit_clicked.connect(self._open_credential_dialog)
        layout.addWidget(self.card_linkedin)

        self.card_naukri = PlatformCard("naukri", "Naukri.com", "🎯", self)
        self.card_naukri.edit_clicked.connect(self._open_credential_dialog)
        layout.addWidget(self.card_naukri)

        # 3. Recruiter Outreach Email Section
        lbl_email = QLabel("Recruiter Outreach Email")
        lbl_email.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_email)

        email_card = QFrame()
        email_card.setObjectName("EmailCard")
        email_card.setStyleSheet(f"""
            QFrame#EmailCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 14px 16px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        e_layout = QVBoxLayout(email_card)
        e_layout.setContentsMargins(10, 10, 10, 10)
        e_layout.setSpacing(12)

        email_form = QFormLayout()
        email_form.setSpacing(12)

        self.combo_email_preset = QComboBox()
        self.combo_email_preset.addItem("Google Mail (Gmail)", "gmail")
        self.combo_email_preset.addItem("Custom SMTP / IMAP", "custom")
        self.combo_email_preset.addItem("Microsoft Outlook / Office 365", "outlook")
        self.combo_email_preset.setStyleSheet(self._input_style())
        self.combo_email_preset.currentIndexChanged.connect(self._on_email_preset_changed)
        email_form.addRow("<b>Provider Preset:</b>", self.combo_email_preset)

        self.txt_email_user = QLineEdit()
        self.txt_email_user.setPlaceholderText("e.g. recruiter@example.com")
        self.txt_email_user.setStyleSheet(self._input_style())
        self.txt_email_user.textChanged.connect(lambda _: self.email_changed.emit())
        email_form.addRow("<b>Sender Email:</b>", self.txt_email_user)

        # App Password
        pwd_container = QWidget()
        p_layout = QHBoxLayout(pwd_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(8)

        self.txt_email_pwd = QLineEdit()
        self.txt_email_pwd.setEchoMode(QLineEdit.Password)
        self.txt_email_pwd.setPlaceholderText("Google App Password (16 characters)")
        self.txt_email_pwd.setStyleSheet(self._input_style())
        self.txt_email_pwd.textChanged.connect(lambda _: self.email_changed.emit())
        p_layout.addWidget(self.txt_email_pwd, 1)

        self.btn_toggle_email_pwd = QPushButton()
        self.btn_toggle_email_pwd.setIcon(QIcon(_EYE_ICON_PATH))
        self.btn_toggle_email_pwd.setIconSize(QSize(16, 16))
        self.btn_toggle_email_pwd.setFixedSize(36, 36)
        self.btn_toggle_email_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_email_pwd.setToolTip("Show password")
        self._apply_eye_default_style()
        self.btn_toggle_email_pwd.clicked.connect(self._toggle_email_pwd_visibility)
        p_layout.addWidget(self.btn_toggle_email_pwd)
        email_form.addRow("<b>App Password:</b>", pwd_container)

        # SMTP Host & Port
        smtp_container = QWidget()
        smtp_layout = QHBoxLayout(smtp_container)
        smtp_layout.setContentsMargins(0, 0, 0, 0)
        smtp_layout.setSpacing(8)

        self.txt_smtp_host = QLineEdit("smtp.gmail.com")
        self.txt_smtp_host.setPlaceholderText("e.g. smtp.gmail.com")
        self.txt_smtp_host.setStyleSheet(self._input_style())
        self.txt_smtp_host.textChanged.connect(lambda _: self.email_changed.emit())
        smtp_layout.addWidget(self.txt_smtp_host, 1)

        lbl_smtp_port = QLabel("Port:")
        lbl_smtp_port.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 12px; font-weight: 600; padding: 0;")
        smtp_layout.addWidget(lbl_smtp_port)

        self.spin_smtp_port = QSpinBox()
        self.spin_smtp_port.setRange(1, 65535)
        self.spin_smtp_port.setValue(587)
        self.spin_smtp_port.setFixedWidth(85)
        self.spin_smtp_port.setStyleSheet(self._input_style())
        self.spin_smtp_port.valueChanged.connect(lambda _: self.email_changed.emit())
        smtp_layout.addWidget(self.spin_smtp_port)
        email_form.addRow("<b>SMTP Host & Port:</b>", smtp_container)

        # IMAP Host & Port
        imap_container = QWidget()
        imap_layout = QHBoxLayout(imap_container)
        imap_layout.setContentsMargins(0, 0, 0, 0)
        imap_layout.setSpacing(8)

        self.txt_imap_host = QLineEdit("imap.gmail.com")
        self.txt_imap_host.setPlaceholderText("e.g. imap.gmail.com")
        self.txt_imap_host.setStyleSheet(self._input_style())
        self.txt_imap_host.textChanged.connect(lambda _: self.email_changed.emit())
        imap_layout.addWidget(self.txt_imap_host, 1)

        lbl_imap_port = QLabel("Port:")
        lbl_imap_port.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 12px; font-weight: 600; padding: 0;")
        imap_layout.addWidget(lbl_imap_port)

        self.spin_imap_port = QSpinBox()
        self.spin_imap_port.setRange(1, 65535)
        self.spin_imap_port.setValue(993)
        self.spin_imap_port.setFixedWidth(85)
        self.spin_imap_port.setStyleSheet(self._input_style())
        self.spin_imap_port.valueChanged.connect(lambda _: self.email_changed.emit())
        imap_layout.addWidget(self.spin_imap_port)
        email_form.addRow("<b>IMAP Host & Port:</b>", imap_container)

        # Gmail Sync Label
        self.txt_sync_label = QLineEdit("RPA-Developer-Application")
        self.txt_sync_label.setPlaceholderText("e.g. RPA-Developer-Application")
        self.txt_sync_label.setStyleSheet(self._input_style())
        self.txt_sync_label.textChanged.connect(lambda _: self.email_changed.emit())
        email_form.addRow("<b>Gmail Sync Label:</b>", self.txt_sync_label)

        e_layout.addLayout(email_form)

        # Email Diagnostics Row
        test_row = QHBoxLayout()
        test_row.setSpacing(12)

        self.btn_test_email = QPushButton("⚡ Test Connection")
        self.btn_test_email.setCursor(Qt.PointingHandCursor)
        self.btn_test_email.setStyleSheet(self._secondary_btn_style())
        self.btn_test_email.clicked.connect(self._test_email)
        test_row.addWidget(self.btn_test_email)

        self.lbl_email_diag = QLabel("Status: Not tested")
        self.lbl_email_diag.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        test_row.addWidget(self.lbl_email_diag)

        test_row.addStretch()
        e_layout.addLayout(test_row)
        layout.addWidget(email_card)

        layout.addStretch()
        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

        self.refresh_display()

    def _toggle_tech_details(self) -> None:
        visible = not self.box_tech_details.isVisible()
        self.box_tech_details.setVisible(visible)
        self.btn_tech_details.setText("Hide Technical Details ▴" if visible else "View Technical Details ▾")

    def _apply_eye_default_style(self) -> None:
        """DesignUI.md Tool/Icon Button default (password hidden) state."""
        self.btn_toggle_email_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """)

    def _apply_eye_active_style(self) -> None:
        """DesignUI.md Tool/Icon Button active (password visible) state with Safety Orange."""
        self.btn_toggle_email_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('primary_subtle', '#FF5F1518')};
                border: 1px solid {COLORS.get('accent', '#FF7A3D')};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent', '#FF7A3D')}30;
                border-color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)

    def _toggle_email_pwd_visibility(self) -> None:
        if self.txt_email_pwd.echoMode() == QLineEdit.Password:
            self.txt_email_pwd.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_email_pwd.setIcon(QIcon(_EYE_OFF_ICON_PATH))
            self.btn_toggle_email_pwd.setToolTip("Hide password")
            self._apply_eye_active_style()
        else:
            self.txt_email_pwd.setEchoMode(QLineEdit.Password)
            self.btn_toggle_email_pwd.setIcon(QIcon(_EYE_ICON_PATH))
            self.btn_toggle_email_pwd.setToolTip("Show password")
            self._apply_eye_default_style()

    def _open_credential_dialog(self, platform_key: str) -> None:
        name = "LinkedIn" if platform_key == "linkedin" else "Naukri.com"
        username, _ = self.secrets_service.get_platform_credentials(platform_key)
        dialog = CredentialDialog(platform_key, name, self.secrets_service, username or "", self)
        dialog.credentials_saved.connect(lambda _k, _u: self.refresh_display())
        dialog.exec()

    def refresh_display(self) -> None:
        # LinkedIn
        li_user, li_pwd = self.secrets_service.get_platform_credentials("linkedin")
        self.card_linkedin.set_configured(li_user, bool(li_pwd))

        # Naukri
        nk_user, nk_pwd = self.secrets_service.get_platform_credentials("naukri")
        self.card_naukri.set_configured(nk_user, bool(nk_pwd))

        # Count configured
        count = sum([bool(li_user and li_pwd), bool(nk_user and nk_pwd)])
        self.credentials_updated.emit(count)

        # Email
        email_creds = self.secrets_service.get_email_credentials()
        if email_creds.get("user"):
            self.txt_email_user.setText(email_creds["user"])
        if email_creds.get("password"):
            self.txt_email_pwd.setText("••••••••")
        if email_creds.get("smtp_host"):
            self.txt_smtp_host.setText(email_creds["smtp_host"])
        if email_creds.get("smtp_port"):
            self.spin_smtp_port.setValue(int(email_creds["smtp_port"]))
        if email_creds.get("imap_host"):
            self.txt_imap_host.setText(email_creds["imap_host"])
        if email_creds.get("imap_port"):
            self.spin_imap_port.setValue(int(email_creds["imap_port"]))
        if email_creds.get("sync_label"):
            self.txt_sync_label.setText(email_creds["sync_label"])

    def _on_email_preset_changed(self, index: int) -> None:
        preset = self.combo_email_preset.currentData()
        if preset == "gmail":
            self.txt_smtp_host.setText("smtp.gmail.com")
            self.spin_smtp_port.setValue(587)
            self.txt_imap_host.setText("imap.gmail.com")
            self.spin_imap_port.setValue(993)
            self.txt_email_pwd.setPlaceholderText("Google App Password (16 characters)")
        elif preset == "outlook":
            self.txt_smtp_host.setText("smtp-mail.outlook.com")
            self.spin_smtp_port.setValue(587)
            self.txt_imap_host.setText("outlook.office365.com")
            self.spin_imap_port.setValue(993)
            self.txt_email_pwd.setPlaceholderText("Outlook Password / App Password")
        elif preset == "custom":
            self.txt_email_pwd.setPlaceholderText("Mail Server Password / App Password")
        self.email_changed.emit()

    def _test_email(self) -> None:
        user = self.txt_email_user.text().strip()
        pwd = self.txt_email_pwd.text().strip()
        if not user or not pwd:
            self.lbl_email_diag.setText("Please enter sender email and password.")
            self.lbl_email_diag.setStyleSheet(f"font-size: 12px; color: {COLORS.get('warning', '#D29922')};")
            return

        # If user entered placeholder "••••••••", load decrypted secret
        if pwd == "••••••••":
            creds = self.secrets_service.get_email_credentials()
            pwd = creds.get("password", "")

        self.btn_test_email.setEnabled(False)
        self.lbl_email_diag.setText("Connecting to SMTP & IMAP...")
        self.lbl_email_diag.setStyleSheet(f"font-size: 12px; color: {COLORS.get('info', '#388BFD')};")

        self._email_worker = EmailTestWorker(
            secrets_service=self.secrets_service,
            user=user,
            password=pwd,
            smtp_host=self.txt_smtp_host.text().strip(),
            smtp_port=self.spin_smtp_port.value(),
            imap_host=self.txt_imap_host.text().strip(),
            imap_port=self.spin_imap_port.value(),
            parent=self,
        )
        self._email_worker.progress.connect(lambda _step, msg: self.lbl_email_diag.setText(msg))
        self._email_worker.finished.connect(self._on_email_test_finished)
        self._email_worker.start()

    def _on_email_test_finished(self, success: bool, msg: str) -> None:
        self.btn_test_email.setEnabled(True)
        if success:
            self.lbl_email_diag.setText("✓ SMTP & IMAP Verified")
            self.lbl_email_diag.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
        else:
            self.lbl_email_diag.setText(f"✕ {msg}")
            self.lbl_email_diag.setStyleSheet(f"font-size: 12px; color: {COLORS.get('danger', '#F85149')};")
        self.email_test_completed.emit(success)

    def save_email_credentials(self) -> None:
        user = self.txt_email_user.text().strip()
        pwd = self.txt_email_pwd.text().strip()
        self.secrets_service.set_email_credentials(
            user=user,
            password=pwd if pwd != "••••••••" else None,
            smtp_host=self.txt_smtp_host.text().strip(),
            smtp_port=self.spin_smtp_port.value(),
            imap_host=self.txt_imap_host.text().strip(),
            imap_port=self.spin_imap_port.value(),
            provider=self.combo_email_preset.currentData() or "gmail",
            sync_label=self.txt_sync_label.text().strip() or "RPA-Developer-Application",
        )

    def _input_style(self) -> str:
        return f"""
            QLineEdit, QComboBox, QSpinBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
                border: 1px solid {COLORS.get('accent', '#FF5F15')};
            }}
        """

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """
