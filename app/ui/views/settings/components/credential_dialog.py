"""Focused modal dialog for editing platform credentials with temporary reveal and immediate encryption."""

from typing import Optional
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.services.secrets_service import SecretsService
from app.ui.theme import COLORS


class CredentialDialog(QDialog):
    """Isolated modal for entering sensitive credentials without exposing them on the main window."""

    credentials_saved = Signal(str, str)  # (platform_key, username)

    def __init__(
        self,
        platform_key: str,
        platform_name: str,
        secrets_service: SecretsService,
        current_username: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.platform_key = platform_key
        self.platform_name = platform_name
        self.secrets_service = secrets_service
        self.current_username = current_username
        self._mask_timer = QTimer(self)
        self._mask_timer.setSingleShot(True)
        self._mask_timer.timeout.connect(self._auto_mask_password)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(f"Configure {self.platform_name} Credentials")
        self.setFixedWidth(460)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
            }}
            QLabel {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS.get('accent', '#FF5F15')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header Title & Explanatory Subtitle
        lbl_title = QLabel(f"🔐 {self.platform_name} Credentials")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Credentials are encrypted immediately using your machine-local key and stored securely in SQLite.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Form Inputs
        form = QFormLayout()
        form.setSpacing(12)

        self.txt_username = QLineEdit(self.current_username)
        self.txt_username.setPlaceholderText("Email or username")
        form.addRow("<b>Username / Email:</b>", self.txt_username)

        # Password with temporary reveal
        pwd_container = QWidget()
        pwd_layout = QHBoxLayout(pwd_container)
        pwd_layout.setContentsMargins(0, 0, 0, 0)
        pwd_layout.setSpacing(8)

        self.txt_password = QLineEdit()
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.txt_password.setPlaceholderText("Enter password (leave empty to keep current)")
        pwd_layout.addWidget(self.txt_password, 1)

        self.btn_toggle_pwd = QPushButton("👁")
        self.btn_toggle_pwd.setToolTip("Show password temporarily (auto-masks after 10s)")
        self.btn_toggle_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
        """)
        self.btn_toggle_pwd.clicked.connect(self._toggle_password_visibility)
        pwd_layout.addWidget(self.btn_toggle_pwd)

        form.addRow("<b>Password:</b>", pwd_container)
        layout.addLayout(form)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save & Encrypt")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                color: #FFFFFF;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent_hover', '#E04F0B')};
            }}
        """)
        btn_save.clicked.connect(self._on_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _toggle_password_visibility(self) -> None:
        if self.txt_password.echoMode() == QLineEdit.Password:
            self.txt_password.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_pwd.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS.get('accent', '#FF5F15')}22;
                    border: 1px solid {COLORS.get('accent', '#FF5F15')};
                    color: {COLORS.get('accent', '#FF5F15')};
                    font-size: 14px;
                    padding: 6px 10px;
                    border-radius: 6px;
                }}
            """)
            self._mask_timer.start(10000)  # 10s auto-mask timeout
        else:
            self._auto_mask_password()

    def _auto_mask_password(self) -> None:
        self.txt_password.setEchoMode(QLineEdit.Password)
        self.btn_toggle_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-size: 14px;
                padding: 6px 10px;
                border-radius: 6px;
            }}
        """)
        self._mask_timer.stop()

    def _on_save(self) -> None:
        new_username = self.txt_username.text().strip()
        new_password = self.txt_password.text().strip()

        # Update credentials through SecretsService immediately
        existing_user, existing_pwd = self.secrets_service.get_platform_credentials(self.platform_key)
        final_pwd = new_password if new_password else (existing_pwd or "")

        if new_username:
            self.secrets_service.set_secret(f"{self.platform_key}_username", new_username)
        if final_pwd:
            self.secrets_service.set_secret(f"{self.platform_key}_password", final_pwd)

        self.credentials_saved.emit(self.platform_key, new_username)
        self.accept()
