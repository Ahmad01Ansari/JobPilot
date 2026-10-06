"""Browser engine and compatibility preferences section."""

from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS
from app.ui.views.settings.components.setting_row import SettingRow


class BrowserSection(QWidget):
    """Browser settings governing undetected Chrome profiles, headless execution, and system power."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
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
        lbl_head = QLabel("Browser Engine & Compatibility")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Configure Chrome automation parameters, session profile isolation, and system power wakelocks.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Primary Settings Card
        card = QFrame()
        card.setObjectName("BrowserCard")
        card.setStyleSheet(f"""
            QFrame#BrowserCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 8px 14px;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(0)

        # 1. Run in background (default False)
        self.chk_headless = QCheckBox()
        self.chk_headless.setChecked(False)
        self.chk_headless.setStyleSheet(self._chk_style())
        self.chk_headless.toggled.connect(lambda _: self.changed.emit())
        row_headless = SettingRow(
            title="Run in background (Headless)",
            description="Launches Chrome without a visible GUI window for background processing.",
            control_widget=self.chk_headless,
        )
        card_layout.addWidget(row_headless)

        # 2. Stealth Mode (default True)
        self.chk_stealth = QCheckBox()
        self.chk_stealth.setChecked(True)
        self.chk_stealth.setStyleSheet(self._chk_style())
        self.chk_stealth.toggled.connect(lambda _: self.changed.emit())
        row_stealth = SettingRow(
            title="Browser compatibility mode (Stealth)",
            description="Applies standard browser automation flags to maintain compatibility across platforms.",
            control_widget=self.chk_stealth,
        )
        card_layout.addWidget(row_stealth)

        # 3. Safe Mode (default True)
        self.chk_safe_mode = QCheckBox()
        self.chk_safe_mode.setChecked(True)
        self.chk_safe_mode.setStyleSheet(self._chk_style())
        self.chk_safe_mode.toggled.connect(lambda _: self.changed.emit())
        row_safe = SettingRow(
            title="Safe profile isolation",
            description="Isolates bot sessions into dedicated per-platform browser directories.",
            control_widget=self.chk_safe_mode,
        )
        card_layout.addWidget(row_safe)

        # 4. Keep Screen Awake (default True)
        self.chk_screen_awake = QCheckBox()
        self.chk_screen_awake.setChecked(True)
        self.chk_screen_awake.setStyleSheet(self._chk_style())
        self.chk_screen_awake.toggled.connect(lambda _: self.changed.emit())
        row_awake = SettingRow(
            title="Prevent system sleep during automation",
            description="Acquires a system display wakelock to prevent computer sleep while bot runs.",
            control_widget=self.chk_screen_awake,
        )
        card_layout.addWidget(row_awake)

        # 5. Disable Extensions (default False)
        self.chk_disable_extensions = QCheckBox()
        self.chk_disable_extensions.setChecked(False)
        self.chk_disable_extensions.setStyleSheet(self._chk_style())
        self.chk_disable_extensions.toggled.connect(lambda _: self.changed.emit())
        row_ext = SettingRow(
            title="Disable browser extensions",
            description="Disables third-party Chrome extensions during bot runs to reduce CPU/memory overhead.",
            control_widget=self.chk_disable_extensions,
            is_last=True,
        )
        card_layout.addWidget(row_ext)
        layout.addWidget(card)

        # Profiles Overview Box
        profiles_box = QFrame()
        profiles_box.setObjectName("BrowserProfilesBox")
        profiles_box.setStyleSheet(f"""
            QFrame#BrowserProfilesBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        p_layout = QVBoxLayout(profiles_box)
        p_layout.setContentsMargins(8, 8, 8, 8)
        p_layout.setSpacing(6)

        lbl_p_title = QLabel("Persistent Browser Profiles")
        lbl_p_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        p_layout.addWidget(lbl_p_title)

        # Check existing profiles on disk
        home = Path.home()
        li_dir = home / ".jobpilot-chrome-profile"
        if not li_dir.exists():
            li_dir = home / ".apply-and-pray-chrome-profile"
        li_exists = li_dir.exists()

        nk_dir = home / ".jobpilot-naukri-profile"
        if not nk_dir.exists():
            nk_dir = home / ".apply-and-pray-naukri-profile"
        nk_exists = nk_dir.exists()

        lbl_li = QLabel(f"• <b>LinkedIn Session Profile:</b> {'● Ready' if li_exists else '○ Initialized on first run'}")
        lbl_li.setStyleSheet(f"font-size: 12px; color: {COLORS.get('success', '#2EA043') if li_exists else COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(lbl_li)

        lbl_nk = QLabel(f"• <b>Naukri Session Profile:</b> {'● Ready' if nk_exists else '○ Initialized on first run'}")
        lbl_nk.setStyleSheet(f"font-size: 12px; color: {COLORS.get('success', '#2EA043') if nk_exists else COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(lbl_nk)

        # Profile directory button
        p_btn_row = QHBoxLayout()
        p_btn_row.setContentsMargins(0, 4, 0, 0)
        btn_open_profile = QPushButton("📁 Open Chrome Profile Folder")
        btn_open_profile.setCursor(Qt.PointingHandCursor)
        btn_open_profile.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 11px;
                padding: 4px 10px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """)
        target_dir = li_dir if li_dir.exists() else home
        btn_open_profile.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_dir))))
        p_btn_row.addWidget(btn_open_profile)
        p_btn_row.addStretch()
        p_layout.addLayout(p_btn_row)

        layout.addWidget(profiles_box)
        layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def get_values(self) -> Dict[str, Any]:
        return {
            "run_in_background": self.chk_headless.isChecked(),
            "stealth_mode": self.chk_stealth.isChecked(),
            "safe_mode": self.chk_safe_mode.isChecked(),
            "disable_extensions": self.chk_disable_extensions.isChecked(),
            "keep_screen_awake": self.chk_screen_awake.isChecked(),
        }

    def load_values(self, values: Dict[str, Any]) -> None:
        self.blockSignals(True)
        if "run_in_background" in values:
            self.chk_headless.setChecked(bool(values["run_in_background"]))
        if "stealth_mode" in values:
            self.chk_stealth.setChecked(bool(values["stealth_mode"]))
        if "safe_mode" in values:
            self.chk_safe_mode.setChecked(bool(values["safe_mode"]))
        if "disable_extensions" in values:
            self.chk_disable_extensions.setChecked(bool(values["disable_extensions"]))
        if "keep_screen_awake" in values:
            self.chk_screen_awake.setChecked(bool(values["keep_screen_awake"]))
        self.blockSignals(False)

    def reset_to_defaults(self) -> None:
        self.load_values({
            "run_in_background": False,
            "stealth_mode": True,
            "safe_mode": True,
            "disable_extensions": False,
            "keep_screen_awake": True,
        })
        self.changed.emit()

    def _chk_style(self) -> str:
        return f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLORS.get('border', '#262C36')};
                background: {COLORS.get('surface_alt', '#1C2128')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
        """
