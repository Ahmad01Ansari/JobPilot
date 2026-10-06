"""Compact Platform Health & Status Strip component for Automation Control Center.

Displays real-time operational readiness and runtime execution states for
LinkedIn, Naukri, Indeed, and Foundit using standard design tokens.
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QWidget,
)

from app.ui.theme import COLORS


class PlatformChip(QFrame):
    """Compact clickable platform health chip displaying status dot, platform name, and state."""

    chip_clicked = Signal(str)  # platform_name

    def __init__(self, platform_key: str, display_name: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.platform_key = platform_key
        self.display_name = display_name
        self._state = "READY"
        self._safe_info: Dict[str, str] = {
            "Status": "Ready",
            "Configured": "Yes",
            "Mode": "Standard",
        }

        self.setObjectName("platform_chip")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(6)
        layout.setSizeConstraint(QLayout.SetFixedSize)

        # Status Dot
        self.dot = QLabel("●")
        self.dot.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.dot)

        # Platform Name
        self.lbl_name = QLabel(self.display_name)
        layout.addWidget(self.lbl_name)

        # Status Text
        self.lbl_status = QLabel("Ready")
        layout.addWidget(self.lbl_status)

        self._refresh_styles()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.chip_clicked.emit(self.platform_key)
        super().mousePressEvent(event)

    def set_state(self, state: str, safe_info: Optional[Dict[str, str]] = None) -> None:
        """Updates display state and metadata tooltip."""
        self._state = (state or "READY").upper()
        if safe_info:
            self._safe_info.update(safe_info)

        display_text = self._state.replace("_", " ").title()
        self.lbl_status.setText(display_text)

        # Format safe, secret-free tooltip
        tooltip_lines = [f"<b>{self.display_name}</b>", f"State: {display_text}"]
        for k, v in self._safe_info.items():
            if k not in ("password", "secret", "token", "cookie", "username"):
                tooltip_lines.append(f"{k}: {v}")
        self.setToolTip("<br>".join(tooltip_lines))

        self._refresh_styles()

    def _refresh_styles(self) -> None:
        tokens = COLORS
        state_colors = {
            "READY": tokens.get("success", "#2EA043"),
            "RUNNING": tokens.get("cyan", "#39C5CF"),
            "PAUSED": tokens.get("warning", "#D29922"),
            "LOGIN_REQUIRED": tokens.get("danger", "#F85149"),
            "MANUAL_REQUIRED": tokens.get("warning", "#D29922"),
            "ERROR": tokens.get("danger", "#F85149"),
            "DISABLED": tokens.get("text_dark", "#6E7681"),
            "NOT_CONFIGURED": tokens.get("text_dark", "#6E7681"),
        }
        color = state_colors.get(self._state, tokens.get("text_muted", "#8B949E"))

        self.setStyleSheet(f"""
            QFrame#platform_chip {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 14px;
            }}
            QFrame#platform_chip:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                border-color: {tokens.get('border_light', '#333A46')};
            }}
        """)
        self.dot.setStyleSheet(f"color: {color}; font-size: 9px; background: transparent; border: none;")
        self.lbl_name.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self.lbl_status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700; background: transparent; border: none;")

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()


class PlatformStrip(QFrame):
    """Horizontal status strip displaying health indicators for all platforms."""

    platform_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.chips: Dict[str, PlatformChip] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("platform_strip")
        self.setStyleSheet(f"""
            QFrame#platform_strip {{
                background-color: transparent;
                border: none;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Section Tag
        lbl_tag = QLabel("PLATFORMS")
        lbl_tag.setStyleSheet(f"""
            color: {COLORS.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: transparent;
        """)
        layout.addWidget(lbl_tag)

        # 5 Core Platforms
        platforms = [
            ("linkedin", "LinkedIn"),
            ("naukri", "Naukri"),
            ("indeed", "Indeed"),
            ("foundit", "Foundit"),
            ("glassdoor", "Glassdoor"),
            ("universal", "Universal ATS"),
        ]

        for key, name in platforms:
            chip = PlatformChip(key, name, self)
            chip.chip_clicked.connect(self.platform_selected.emit)
            self.chips[key] = chip
            layout.addWidget(chip)

        layout.addStretch()

    def update_platform(self, platform_key: str, state: str, safe_info: Optional[Dict[str, str]] = None) -> None:
        """Updates state for a specific platform chip."""
        key = (platform_key or "").strip().lower()
        if key in self.chips:
            self.chips[key].set_state(state, safe_info)

    def set_platform_readiness(
        self,
        linkedin_ready: bool,
        naukri_ready: bool,
        indeed_ready: bool = True,
        foundit_ready: bool = True,
        glassdoor_ready: bool = True,
    ) -> None:
        """Sets readiness boolean flags for all chips."""
        mapping = [
            ("linkedin", linkedin_ready),
            ("naukri", naukri_ready),
            ("indeed", indeed_ready),
            ("foundit", foundit_ready),
            ("glassdoor", glassdoor_ready),
        ]
        for key, is_ready in mapping:
            st = "READY" if is_ready else "DISABLED"
            self.update_platform(key, st, {"Configured": "Yes" if is_ready else "Disabled"})

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        """Propagates theme token updates to all chips."""
        for chip in self.chips.values():
            chip.apply_theme(tokens)
