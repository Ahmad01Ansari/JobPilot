"""
Platform Automation Trigger Deck component for Dashboard.

Provides a prominent command center station allowing users to directly launch
targeted platform automation runs (LinkedIn, Naukri, or All Platforms sequentially)
with live telemetry status, progress bars, and cooperative stop controls.
"""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.automation_events import AutomationProgressEvent, AutomationState
from app.ui.theme import COLORS


class PlatformCardTile(QFrame):
    """Individual platform launch tile with platform branding, info, and trigger CTA."""

    trigger_clicked = Signal(str)

    def __init__(
        self,
        platform_id: str,
        title: str,
        tag: str,
        icon: str,
        description: str,
        badge_text: str,
        button_text: str,
        accent_color: str = "#FF5F15",
        is_highlighted: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.platform_id = platform_id
        self.accent_color = accent_color
        self._setup_ui(
            title=title,
            tag=tag,
            icon=icon,
            description=description,
            badge_text=badge_text,
            button_text=button_text,
            is_highlighted=is_highlighted,
        )

    def _setup_ui(
        self,
        title: str,
        tag: str,
        icon: str,
        description: str,
        badge_text: str,
        button_text: str,
        is_highlighted: bool,
    ) -> None:
        border_color = f"{self.accent_color}55" if is_highlighted else "#262C36"
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1C2128;
                border: 1px solid {border_color};
                border-radius: 10px;
            }}
            QFrame:hover {{
                border-color: {self.accent_color}88;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Header: Icon + Title + Tag
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(30, 30)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            background-color: {self.accent_color}20;
            color: {self.accent_color};
            border: 1px solid {self.accent_color}40;
            border-radius: 15px;
            font-size: 14px;
        """)
        hdr.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: #F0F6FC; background: transparent; border: none;")
        hdr.addWidget(title_lbl)

        hdr.addStretch()

        tag_lbl = QLabel(tag)
        tag_lbl.setStyleSheet(f"""
            background-color: {self.accent_color}18;
            color: {self.accent_color};
            border: 1px solid {self.accent_color}30;
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)
        hdr.addWidget(tag_lbl)
        layout.addLayout(hdr)

        # Description
        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("color: #8B949E; font-size: 11px; line-height: 1.3; background: transparent; border: none;")
        layout.addWidget(desc_lbl, 1)

        # Bottom row: Hint Badge + Trigger Button
        btm = QHBoxLayout()
        btm.setSpacing(8)

        badge_lbl = QLabel(badge_text)
        badge_lbl.setStyleSheet("color: #6E7681; font-size: 10px; font-weight: 600; background: transparent; border: none;")
        btm.addWidget(badge_lbl, 1)

        self.btn_trigger = QPushButton(button_text)
        self.btn_trigger.setCursor(Qt.PointingHandCursor)
        self.btn_trigger.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.accent_color};
                color: #FFFFFF;
                border: none;
                border-radius: 7px;
                padding: 7px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {self.accent_color}dd;
            }}
            QPushButton:disabled {{
                background-color: #262C36;
                color: #6E7681;
            }}
        """)
        self.btn_trigger.clicked.connect(lambda: self.trigger_clicked.emit(self.platform_id))
        btm.addWidget(self.btn_trigger)

        layout.addLayout(btm)

    def set_running(self, running: bool) -> None:
        """Disables button if another run is active."""
        self.btn_trigger.setEnabled(not running)


class PlatformTriggerDeck(QFrame):
    """High-weight Automation Command Deck embedded into the ATS Dashboard."""

    trigger_requested = Signal(str)  # platform: 'linkedin', 'naukri', 'all'
    stop_requested = Signal()
    open_console_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_state: str = AutomationState.IDLE.value
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 14px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # 1. Deck Header
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(12)

        icon_badge = QLabel("⚡")
        icon_badge.setFixedSize(38, 38)
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setStyleSheet("""
            background-color: #FF5F1520;
            color: #FF5F15;
            border: 1px solid #FF5F1540;
            border-radius: 19px;
            font-size: 18px;
        """)
        hdr_layout.addWidget(icon_badge)

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)

        deck_title = QLabel("Platform Automation Launch Deck")
        deck_title.setStyleSheet("color: #F0F6FC; font-size: 15px; font-weight: 800; letter-spacing: -0.2px; background: transparent; border: none;")
        text_col.addWidget(deck_title)

        deck_sub = QLabel("Direct multi-platform execution • Anti-bot stealth profiles & automated QnA ready")
        deck_sub.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        text_col.addWidget(deck_sub)
        hdr_layout.addLayout(text_col, 1)

        # Status Pill
        self.lbl_status_pill = QLabel("●  Ready to Launch")
        self.lbl_status_pill.setStyleSheet("""
            QLabel {
                color: #2EA043;
                background-color: #2EA04318;
                border: 1px solid #2EA04330;
                border-radius: 14px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 700;
            }
        """)
        hdr_layout.addWidget(self.lbl_status_pill)

        self.btn_open_console = QPushButton("Console ↗")
        self.btn_open_console.setCursor(Qt.PointingHandCursor)
        self.btn_open_console.setToolTip("Open full live stream automation monitor")
        self.btn_open_console.setStyleSheet("""
            QPushButton {
                background-color: #1C2128;
                color: #8B949E;
                border: 1px solid #333A46;
                border-radius: 8px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #262C36;
                color: #F0F6FC;
                border-color: #FF5F15;
            }
        """)
        self.btn_open_console.clicked.connect(self.open_console_requested.emit)
        hdr_layout.addWidget(self.btn_open_console)

        main_layout.addLayout(hdr_layout)

        # 2. Platform Launch Grid (3 Tiles)
        tiles_layout = QHBoxLayout()
        tiles_layout.setSpacing(12)

        self.tile_linkedin = PlatformCardTile(
            platform_id="linkedin",
            title="LinkedIn",
            tag="Easy Apply",
            icon="🔗",
            description="Auto-applies to matched roles using candidate profile, screening Q&A rules, and resume PDF.",
            badge_text="⚡ Stealth Profile Active",
            button_text="▶ Run LinkedIn",
            accent_color="#0A66C2",
        )
        self.tile_linkedin.trigger_clicked.connect(self.trigger_requested.emit)
        tiles_layout.addWidget(self.tile_linkedin, 1)

        self.tile_naukri = PlatformCardTile(
            platform_id="naukri",
            title="Naukri.com",
            tag="FastForward",
            icon="💼",
            description="Executes search rotation, automated questionnaire answer matching, and safety review gate.",
            badge_text="🛡️ Safety Review Gate",
            button_text="▶ Run Naukri",
            accent_color="#0284C7",
        )
        self.tile_naukri.trigger_clicked.connect(self.trigger_requested.emit)
        tiles_layout.addWidget(self.tile_naukri, 1)

        self.tile_all = PlatformCardTile(
            platform_id="all",
            title="All Platforms",
            tag="Sequential",
            icon="⚡",
            description="Full automated sweep executing LinkedIn and Naukri application engines back-to-back.",
            badge_text="🚀 Multi-Platform Batch",
            button_text="🚀 Launch All",
            accent_color="#FF5F15",
            is_highlighted=True,
        )
        self.tile_all.trigger_clicked.connect(self.trigger_requested.emit)
        tiles_layout.addWidget(self.tile_all, 1)

        main_layout.addLayout(tiles_layout)

        # 3. Live Telemetry & Progress Tray (hidden when idle)
        self.live_tray = QFrame()
        self.live_tray.setStyleSheet("""
            QFrame {
                background-color: #1C2128;
                border: 1px solid #FF5F1540;
                border-radius: 10px;
                padding: 10px 14px;
            }
        """)
        tray_layout = QVBoxLayout(self.live_tray)
        tray_layout.setContentsMargins(12, 10, 12, 10)
        tray_layout.setSpacing(8)

        # Tray Top Line: Status & Keyword & Stats
        t_top = QHBoxLayout()
        t_top.setSpacing(10)

        self.lbl_tray_platform = QLabel("⚡ Automation Active")
        self.lbl_tray_platform.setStyleSheet("color: #FF5F15; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        t_top.addWidget(self.lbl_tray_platform)

        self.lbl_tray_keyword = QLabel("🔍 Scanning matching roles...")
        self.lbl_tray_keyword.setStyleSheet("color: #F0F6FC; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        t_top.addWidget(self.lbl_tray_keyword, 1)

        self.lbl_tray_stats = QLabel("Discovered: 0  •  Qualified: 0  •  Submitted: 0  •  Errors: 0")
        self.lbl_tray_stats.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500; background: transparent; border: none;")
        t_top.addWidget(self.lbl_tray_stats)

        self.btn_stop = QPushButton("⏹ Emergency Stop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #F85149;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 700;
            }
            QPushButton:hover {
                background-color: #DA3633;
            }
        """)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        t_top.addWidget(self.btn_stop)

        tray_layout.addLayout(t_top)

        # Tray Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 0)  # Indeterminate pulsing by default
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #262C36;
                border: none;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #FF5F15;
                border-radius: 3px;
            }
        """)
        tray_layout.addWidget(self.progress_bar)

        # Tray Bottom Line: Activity log
        self.lbl_tray_log = QLabel("Engine initialized. Browser session launching...")
        self.lbl_tray_log.setStyleSheet("color: #8B949E; font-size: 10px; font-family: monospace; background: transparent; border: none;")
        tray_layout.addWidget(self.lbl_tray_log)

        self.live_tray.setVisible(False)
        main_layout.addWidget(self.live_tray)

    def set_state(self, state_str: str, active_platform: Optional[str] = None) -> None:
        """Updates visual state of launch tiles and telemetry tray."""
        normalized = (state_str or "").strip().upper()
        self._current_state = normalized
        is_active = normalized in (
            AutomationState.STARTING.value,
            AutomationState.RUNNING.value,
            AutomationState.STOP_REQUESTED.value,
            AutomationState.STOPPING.value,
        )

        # Update tiles enabled state
        self.tile_linkedin.set_running(is_active)
        self.tile_naukri.set_running(is_active)
        self.tile_all.set_running(is_active)

        # Update status pill
        plat_name = (active_platform or "Engine").title()
        if normalized in (AutomationState.STARTING.value, AutomationState.RUNNING.value):
            self.lbl_status_pill.setText(f"⚡ Running: {plat_name}")
            self.lbl_status_pill.setStyleSheet("""
                QLabel {
                    color: #FF5F15;
                    background-color: #FF5F1518;
                    border: 1px solid #FF5F1530;
                    border-radius: 14px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.live_tray.setVisible(True)
            self.lbl_tray_platform.setText(f"⚡ {plat_name} Engine Active")
        elif normalized in (AutomationState.STOP_REQUESTED.value, AutomationState.STOPPING.value):
            self.lbl_status_pill.setText("⏳ Stopping...")
            self.lbl_status_pill.setStyleSheet("""
                QLabel {
                    color: #D29922;
                    background-color: #D2992218;
                    border: 1px solid #D2992230;
                    border-radius: 14px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.live_tray.setVisible(True)
        else:
            self.lbl_status_pill.setText("●  Ready to Launch")
            self.lbl_status_pill.setStyleSheet("""
                QLabel {
                    color: #2EA043;
                    background-color: #2EA04318;
                    border: 1px solid #2EA04330;
                    border-radius: 14px;
                    padding: 4px 12px;
                    font-size: 11px;
                    font-weight: 700;
                }
            """)
            self.live_tray.setVisible(False)

    def update_progress(self, progress: AutomationProgressEvent) -> None:
        """Updates live telemetry tray with real-time stats."""
        if progress.current_term:
            self.lbl_tray_keyword.setText(f"🔍 Term: \"{progress.current_term}\"")
        self.lbl_tray_stats.setText(
            f"Discovered: {progress.jobs_discovered}  •  "
            f"Qualified: {progress.jobs_qualified}  •  "
            f"Submitted: {progress.applications_submitted}  •  "
            f"Errors: {progress.errors_count}"
        )

    def update_activity_log(self, timestamp: str, message: str) -> None:
        """Updates live activity snippet in telemetry tray."""
        self.lbl_tray_log.setText(f"[{timestamp}] {message}")
