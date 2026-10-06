"""Automation Control Center header widget.

Provides compact title block, engine status pill, Stop confirmation dialog,
and primary Start/Pause/Stop automation controls with strict visual hierarchy.
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.automation_events import AutomationState
from app.ui.theme import COLORS


class StopConfirmationDialog(QDialog):
    """Compact confirmation modal before stopping active automation."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Stop Automation?")
        self.setFixedSize(360, 160)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui()

    def _setup_ui(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 10px;
            }}
            QLabel {{
                color: {tokens.get('text', '#F0F6FC')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        lbl_title = QLabel("Stop Active Automation?")
        lbl_title.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("This will cooperatively terminate the active engine and stop processing further jobs.")
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {tokens.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Continue Run")
        btn_cancel.setFixedHeight(32)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 12px;
                font-weight: 600;
                padding: 0 14px;
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("Stop Automation")
        btn_confirm.setFixedHeight(32)
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('danger', '#F85149')};
                color: #FFFFFF;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
                border: none;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: #DC2626;
            }}
        """)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)


class AutomationHeader(QWidget):
    """Header bar with telemetry status indicators and execution command buttons."""

    start_clicked = Signal()
    stop_clicked = Signal()
    pause_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_state = AutomationState.IDLE.value
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Title block
        title_block = QVBoxLayout()
        title_block.setSpacing(3)

        self.lbl_title = QLabel("Automation")
        title_block.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel("Monitor and control live job application runs across all platforms.")
        title_block.addWidget(self.lbl_subtitle)
        layout.addLayout(title_block, 1)

        # Right side actions layout
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(10)
        actions_layout.setAlignment(Qt.AlignVCenter | Qt.AlignRight)

        # Engine State Badge
        self.badge_status = QLabel("IDLE")
        self.badge_status.setAlignment(Qt.AlignCenter)
        self.badge_status.setFixedHeight(28)
        actions_layout.addWidget(self.badge_status)

        # Pause / Resume Button
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setFixedHeight(34)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.clicked.connect(self.pause_clicked.emit)
        actions_layout.addWidget(self.btn_pause)

        # Stop Button
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setFixedHeight(34)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        actions_layout.addWidget(self.btn_stop)

        # Start Button (Safety Orange primary CTA)
        self.btn_start = QPushButton("▶ Start Automation")
        self.btn_start.setFixedHeight(34)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self.start_clicked.emit)
        actions_layout.addWidget(self.btn_start)

        layout.addLayout(actions_layout)

        # Platform readiness dummy pills (for backward-compatibility with tests/callers if any)
        self.pill_linkedin = QLabel("LinkedIn Ready")
        self.pill_naukri = QLabel("Naukri Ready")
        self.pill_indeed = QLabel("Indeed Ready")
        self.pill_foundit = QLabel("Foundit Ready")
        self.pill_glassdoor = QLabel("Glassdoor Ready")
        for p in (self.pill_linkedin, self.pill_naukri, self.pill_indeed, self.pill_foundit, self.pill_glassdoor):
            p.setVisible(False)

        self._refresh_styles()

    def _on_stop_clicked(self) -> None:
        """Opens stop confirmation dialog before emitting stop_clicked."""
        dialog = StopConfirmationDialog(self.window() or self)
        if dialog.exec() == QDialog.Accepted:
            self.stop_clicked.emit()

    def update_state(self, state_str: str) -> None:
        """Updates button enabled states and status badge according to state."""
        self._current_state = (state_str or AutomationState.IDLE.value).upper()
        self.badge_status.setText(self._current_state)

        is_running = self._current_state in (
            AutomationState.STARTING.value,
            AutomationState.RUNNING.value,
            AutomationState.PAUSED.value,
            AutomationState.STOP_REQUESTED.value,
            AutomationState.STOPPING.value,
        )
        is_paused = self._current_state == AutomationState.PAUSED.value

        self.btn_start.setEnabled(not is_running)
        self.btn_stop.setEnabled(is_running)
        self.btn_pause.setEnabled(is_running and self._current_state in (AutomationState.RUNNING.value, AutomationState.PAUSED.value))

        if is_paused:
            self.btn_pause.setText("▶ Resume")
        else:
            self.btn_pause.setText("⏸ Pause")

        self._refresh_styles()

    def set_platform_readiness(
        self,
        linkedin_ready: bool,
        naukri_ready: bool,
        indeed_ready: bool = True,
        foundit_ready: bool = True,
        glassdoor_ready: bool = True,
    ) -> None:
        """Backward-compatibility stub for callers updating header directly."""
        pass

    def _refresh_styles(self) -> None:
        tokens = COLORS

        self.lbl_title.setStyleSheet(f"""
            QLabel {{
                color: {tokens.get('text', '#F0F6FC')};
                font-size: 22px;
                font-weight: 700;
                letter-spacing: -0.3px;
                background: transparent;
            }}
        """)
        self.lbl_subtitle.setStyleSheet(f"""
            QLabel {{
                color: {tokens.get('text_muted', '#8B949E')};
                font-size: 12px;
                background: transparent;
            }}
        """)

        # Badge colors
        st_colors = {
            AutomationState.IDLE.value: tokens.get("text_muted", "#8B949E"),
            AutomationState.STARTING.value: tokens.get("cyan", "#39C5CF"),
            AutomationState.RUNNING.value: tokens.get("cyan", "#39C5CF"),
            AutomationState.PAUSED.value: tokens.get("warning", "#D29922"),
            AutomationState.STOP_REQUESTED.value: tokens.get("warning", "#D29922"),
            AutomationState.STOPPING.value: tokens.get("warning", "#D29922"),
            AutomationState.COMPLETED.value: tokens.get("success", "#2EA043"),
            AutomationState.FAILED.value: tokens.get("danger", "#F85149"),
        }
        badge_color = st_colors.get(self._current_state, tokens.get("text_muted", "#8B949E"))

        self.badge_status.setStyleSheet(f"""
            QLabel {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {badge_color};
                font-weight: 700;
                font-size: 11px;
                padding: 0 12px;
                border-radius: 14px;
                border: 1px solid {tokens.get('border_light', '#333A46')};
                letter-spacing: 0.5px;
            }}
        """)

        # Start button
        self.btn_start.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('primary', '#FF5F15')};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 0 18px;
                border-radius: 8px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {tokens.get('primary_hover', '#E04F0B')};
            }}
            QPushButton:disabled {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text_dark', '#6E7681')};
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
        """)

        # Pause button (secondary outline, orange/amber when resume)
        is_paused = self._current_state == AutomationState.PAUSED.value
        pause_border = tokens.get("primary", "#FF5F15") if is_paused else tokens.get("border_light", "#333A46")
        pause_fg = tokens.get("primary", "#FF5F15") if is_paused else tokens.get("text", "#F0F6FC")

        self.btn_pause.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {pause_fg};
                font-weight: 600;
                font-size: 12px;
                padding: 0 16px;
                border-radius: 8px;
                border: 1px solid {pause_border};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
            }}
            QPushButton:disabled {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text_dark', '#6E7681')};
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
        """)

        # Stop button
        self.btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('danger', '#F85149')};
                font-weight: 600;
                font-size: 12px;
                padding: 0 16px;
                border-radius: 8px;
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('danger', '#F85149')}22;
                border-color: {tokens.get('danger', '#F85149')};
            }}
            QPushButton:disabled {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                color: {tokens.get('text_dark', '#6E7681')};
                border: 1px solid {tokens.get('border', '#262C36')};
            }}
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
