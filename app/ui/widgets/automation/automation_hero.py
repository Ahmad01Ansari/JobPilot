"""Active Run Hero centerpiece widget for Automation Control Center.

Displays high-clarity live execution telemetry, active platform identity,
monotonic elapsed runtime, truthful current action, honest progress indication,
and real-time counters without fabricated precision or fake percentages.
"""

from typing import Dict, Optional
from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.automation_events import AutomationState
from app.ui.theme import COLORS
from app.ui.widgets.automation.state import AutomationUIState


class AutomationHero(QFrame):
    """High-value centerpiece panel displaying live execution state and action telemetry."""

    stop_clicked = Signal()
    start_clicked = Signal()
    pause_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_url: Optional[str] = None
        self._current_state_ref: Optional[AutomationUIState] = None
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self) -> None:
        self.setObjectName("automation_hero")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 1. Top Row: Platform identity on left, State Pill + Elapsed time on right
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.lbl_platform_mode = QLabel("LinkedIn — Easy Apply")
        top_row.addWidget(self.lbl_platform_mode)

        top_row.addStretch()

        self.lbl_hero_badge = QLabel("IDLE")
        self.lbl_hero_badge.setFixedHeight(22)
        self.lbl_hero_badge.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.lbl_hero_badge)

        self.lbl_timer = QLabel("00:00")
        self.lbl_timer.setFixedHeight(22)
        self.lbl_timer.setAlignment(Qt.AlignCenter)
        top_row.addWidget(self.lbl_timer)

        layout.addLayout(top_row)

        # 2. Middle Row: Factual Action Indicator
        action_layout = QVBoxLayout()
        action_layout.setSpacing(4)

        self.lbl_search_term = QLabel("Automation is idle")
        action_layout.addWidget(self.lbl_search_term)

        self.lbl_active_job = QLabel("Select a platform and click Start Automation to begin job applications.")
        self.lbl_active_job.setWordWrap(True)
        action_layout.addWidget(self.lbl_active_job)

        layout.addLayout(action_layout)

        # 3. Honest Progress Bar (Indeterminate pulse when active, 0 when idle, 100 when completed)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # 4. Bottom Row: Current Step Label + Metrics Summary Line
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.lbl_operation_step = QLabel("Ready")
        bottom_row.addWidget(self.lbl_operation_step, 1)

        self.lbl_summary_counts = QLabel("0 Discovered  •  0 Qualified  •  0 Submitted")
        bottom_row.addWidget(self.lbl_summary_counts)

        # Backward compatibility action buttons (kept docked/hidden or accessible)
        self.btn_view_job = QPushButton("↗ View Job")
        self.btn_view_job.setVisible(False)
        self.btn_view_job.clicked.connect(self._on_view_job_clicked)
        bottom_row.addWidget(self.btn_view_job)

        self.btn_hero_stop = QPushButton("⏹ Stop")
        self.btn_hero_stop.setVisible(False)
        self.btn_hero_stop.clicked.connect(self.stop_clicked.emit)
        bottom_row.addWidget(self.btn_hero_stop)

        self.btn_hero_pause = QPushButton("⏸ Pause")
        self.btn_hero_pause.setVisible(False)
        self.btn_hero_pause.clicked.connect(self.pause_clicked.emit)
        bottom_row.addWidget(self.btn_hero_pause)

        layout.addLayout(bottom_row)

        self._refresh_styles()

    def _setup_timer(self) -> None:
        """Sets up 1-second monotonic UI update timer."""
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000)
        self.ui_timer.timeout.connect(self._on_timer_tick)

    def update_from_state(self, state: AutomationUIState) -> None:
        """Updates hero telemetry from state snapshot."""
        self._current_state_ref = state
        self._current_url = state.current_job_url

        # Format Platform Name
        plat_names = {
            "linkedin": "LinkedIn — Easy Apply & Keyword Rotation",
            "naukri": "Naukri.com — Quick Apply Automation",
            "indeed": "Indeed — Smart Apply Engine",
            "foundit": "Foundit — Quick Apply Automation",
            "glassdoor": "Glassdoor — Easy Apply Automation",
            "all": "Multi-Platform — Sequential Automation",
        }
        self.lbl_platform_mode.setText(plat_names.get(state.platform.lower(), state.platform.capitalize()))

        # Update Badge
        st_upper = state.state.upper()
        self.lbl_hero_badge.setText(st_upper)

        # Timer management
        if state.is_running():
            if not self.ui_timer.isActive():
                self.ui_timer.start()
            self.lbl_timer.setText(state.formatted_elapsed_time())
            # Indeterminate progress while running
            if self.progress_bar.maximum() != 0:
                self.progress_bar.setRange(0, 0)
        else:
            if self.ui_timer.isActive():
                self.ui_timer.stop()
            self.lbl_timer.setText(state.formatted_elapsed_time() if state.start_monotonic else "00:00")
            self.progress_bar.setRange(0, 100)
            if st_upper == AutomationState.COMPLETED.value:
                self.progress_bar.setValue(100)
            else:
                self.progress_bar.setValue(0)

        # Context action & step labels
        if state.is_running():
            if state.current_job_title and state.current_job_company:
                self.lbl_search_term.setText(f"{state.current_job_title}")
                loc = f" • {state.current_job_location}" if state.current_job_location else ""
                self.lbl_active_job.setText(f"{state.current_job_company}{loc}")
            elif state.current_keyword:
                self.lbl_search_term.setText(f"Searching: {state.current_keyword}")
                self.lbl_active_job.setText("Scanning job feed for matching vacancies...")
            else:
                self.lbl_search_term.setText("Automation active")
                self.lbl_active_job.setText("Engine running. Evaluating upcoming postings...")

            self.lbl_operation_step.setText(state.current_step_desc or "Processing...")
        elif st_upper == AutomationState.COMPLETED.value:
            self.lbl_search_term.setText("Automation run completed")
            self.lbl_active_job.setText(f"Finished session: {state.applications_submitted} applied, {state.jobs_discovered} discovered.")
            self.lbl_operation_step.setText("Session finished")
        elif st_upper == AutomationState.FAILED.value:
            self.lbl_search_term.setText("Automation stopped with error")
            self.lbl_active_job.setText(state.current_step_desc or "Run encountered an issue.")
            self.lbl_operation_step.setText("Error encountered")
        else:
            self.lbl_search_term.setText("Automation is idle")
            self.lbl_active_job.setText("Select a platform and click Start Automation to begin job applications.")
            self.lbl_operation_step.setText("Ready")

        # Summary line
        self.lbl_summary_counts.setText(
            f"{state.jobs_discovered} Discovered  •  {state.jobs_qualified} Qualified  •  {state.applications_submitted} Submitted"
        )

        self._refresh_styles()

    def _on_timer_tick(self) -> None:
        """Periodic clock update."""
        if self._current_state_ref:
            self.lbl_timer.setText(self._current_state_ref.formatted_elapsed_time())

    def _on_view_job_clicked(self) -> None:
        """Opens active job URL in system browser."""
        if self._current_url:
            QDesktopServices.openUrl(QUrl(self._current_url))

    def _refresh_styles(self) -> None:
        tokens = COLORS
        st = (self.lbl_hero_badge.text() or "IDLE").upper()

        st_colors = {
            "IDLE": tokens.get("text_muted", "#8B949E"),
            "STARTING": tokens.get("cyan", "#39C5CF"),
            "RUNNING": tokens.get("cyan", "#39C5CF"),
            "PAUSED": tokens.get("warning", "#D29922"),
            "STOP_REQUESTED": tokens.get("warning", "#D29922"),
            "STOPPING": tokens.get("warning", "#D29922"),
            "COMPLETED": tokens.get("success", "#2EA043"),
            "FAILED": tokens.get("danger", "#F85149"),
        }
        badge_color = st_colors.get(st, tokens.get("text_muted", "#8B949E"))

        self.setStyleSheet(f"""
            QFrame#automation_hero {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 10px;
            }}
        """)

        self.lbl_platform_mode.setStyleSheet(f"""
            color: {tokens.get('text', '#F0F6FC')};
            font-size: 13px;
            font-weight: 700;
            background: transparent;
            border: none;
        """)

        self.lbl_hero_badge.setStyleSheet(f"""
            background-color: {tokens.get('surface_alt', '#1C2128')};
            color: {badge_color};
            font-size: 10px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 11px;
            border: 1px solid {tokens.get('border_light', '#333A46')};
            letter-spacing: 0.5px;
        """)

        self.lbl_timer.setStyleSheet(f"""
            color: {tokens.get('text_muted', '#8B949E')};
            font-family: 'JetBrains Mono', 'Courier New', monospace;
            font-size: 11px;
            font-weight: 600;
            background-color: {tokens.get('surface_alt', '#1C2128')};
            padding: 2px 8px;
            border-radius: 6px;
            border: 1px solid {tokens.get('border', '#262C36')};
        """)

        self.lbl_search_term.setStyleSheet(f"""
            color: {tokens.get('text', '#F0F6FC')};
            font-size: 15px;
            font-weight: 700;
            background: transparent;
            border: none;
        """)

        self.lbl_active_job.setStyleSheet(f"""
            color: {tokens.get('text_muted', '#8B949E')};
            font-size: 12px;
            background: transparent;
            border: none;
        """)

        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {tokens.get('surface_alt', '#1C2128')};
                border: none;
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {tokens.get('primary', '#FF5F15')};
                border-radius: 3px;
            }}
        """)

        self.lbl_operation_step.setStyleSheet(f"""
            color: {tokens.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-style: italic;
            background: transparent;
            border: none;
        """)

        self.lbl_summary_counts.setStyleSheet(f"""
            color: {tokens.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
