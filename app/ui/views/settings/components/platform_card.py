"""Platform account summary card for LinkedIn and Naukri credentials."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS


class PlatformCard(QFrame):
    """High-density card summarizing platform credentials without exposing raw secrets."""

    edit_clicked = Signal(str)  # Emits platform key: "linkedin" or "naukri"

    def __init__(
        self,
        platform_key: str,
        platform_name: str,
        icon_symbol: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.platform_key = platform_key
        self.platform_name = platform_name
        self.icon_symbol = icon_symbol
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("PlatformCard")
        self.setStyleSheet(f"""
            QFrame#PlatformCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 14px 16px;
            }}
            QFrame#PlatformCard:hover {{
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # Icon box
        lbl_icon = QLabel(self.icon_symbol)
        lbl_icon.setStyleSheet(f"""
            font-size: 20px;
            background-color: {COLORS.get('surface', '#161B22')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 6px;
            padding: 8px 10px;
        """)
        layout.addWidget(lbl_icon, 0, Qt.AlignVCenter)

        # Middle Details
        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)

        header_row = QHBoxLayout()
        self.lbl_name = QLabel(self.platform_name)
        self.lbl_name.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        header_row.addWidget(self.lbl_name)

        self.lbl_status = QLabel("○ Not configured")
        self.lbl_status.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS.get('text_muted', '#8B949E')};")
        header_row.addWidget(self.lbl_status)
        header_row.addStretch()
        details_layout.addLayout(header_row)

        self.lbl_account = QLabel("Account: Not set")
        self.lbl_account.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        details_layout.addWidget(self.lbl_account)

        self.lbl_pwd_status = QLabel("Password: Not stored")
        self.lbl_pwd_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        details_layout.addWidget(self.lbl_pwd_status)

        layout.addLayout(details_layout, 1)

        # Right Action
        self.btn_edit = QPushButton("Edit Credentials")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('accent', '#FF5F15')};
                color: {COLORS.get('accent', '#FF5F15')};
            }}
        """)
        self.btn_edit.clicked.connect(lambda: self.edit_clicked.emit(self.platform_key))
        layout.addWidget(self.btn_edit, 0, Qt.AlignVCenter)

    def set_configured(self, username: Optional[str], has_password: bool) -> None:
        if username and has_password:
            # Mask username safely (e.g. user@example.com -> us***@example.com)
            masked_user = username
            if "@" in username:
                parts = username.split("@", 1)
                prefix = parts[0]
                masked_prefix = prefix[:2] + "***" if len(prefix) > 2 else prefix + "***"
                masked_user = f"{masked_prefix}@{parts[1]}"
            elif len(username) > 4:
                masked_user = username[:2] + "***" + username[-2:]

            self.lbl_status.setText("● Configured")
            self.lbl_status.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS.get('success', '#2EA043')};")
            self.lbl_account.setText(f"Account: {masked_user}")
            self.lbl_pwd_status.setText("Password: ✓ Stored securely")
            self.lbl_pwd_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('success', '#2EA043')};")
        else:
            self.lbl_status.setText("○ Not configured")
            self.lbl_status.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS.get('text_muted', '#8B949E')};")
            self.lbl_account.setText("Account: Not set")
            self.lbl_pwd_status.setText("Password: Not stored")
            self.lbl_pwd_status.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
