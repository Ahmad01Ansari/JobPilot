"""
Contextual Product Tour Overlay for JobPilot Desktop.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Guides the candidate across the 9 primary application views.
"""

from typing import List, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame
)
from app.ui.theme import COLORS

TOUR_STOPS: List[Tuple[str, str, str, str]] = [
    (
        "dashboard",
        "1. Workspace Dashboard (Ctrl+1)",
        "Your mission control center. Displays live pipeline conversion funnels, "
        "active bot status, and overall workspace readiness scorecards.",
        "dashboard"
    ),
    (
        "automation",
        "2. Autonomous Job Bot (Ctrl+2)",
        "Orchestrates multi-platform automation runs (LinkedIn, Naukri, Indeed, Universal ATS). "
        "Trigger autonomous applications, monitor real-time worker threads, and inspect active executions.",
        "automation"
    ),
    (
        "jobs",
        "3. Aggregated Jobs Board (Ctrl+3)",
        "Inspect discovered roles across all portals with match scores, salary benchmarks, "
        "and quick application triggers.",
        "jobs"
    ),
    (
        "search",
        "4. Automated Job Search (Ctrl+4)",
        "Configure target search titles, preferred locations, and negative keyword exclusion rules "
        "for portal crawlers.",
        "search"
    ),
    (
        "applications",
        "5. Application Pipeline (Ctrl+5)",
        "Track submitted applications through stages (Submitted, Review, Interview, Offer) "
        "with complete audit logs and status updates.",
        "applications"
    ),
    (
        "outreach",
        "6. Recruiter Outreach Center (Ctrl+6)",
        "Manage cold outreach emails, LinkedIn networking messages, and follow-up templates "
        "tailored to hiring managers.",
        "outreach"
    ),
    (
        "interviews",
        "7. Interview Schedule (Ctrl+7)",
        "Log upcoming HR screenings, technical assessments, and interview prep notes.",
        "interviews"
    ),
    (
        "followups",
        "8. Follow-ups & Reminders (Ctrl+8)",
        "Automated alerts for pending recruiter communications and status follow-ups.",
        "followups"
    ),
    (
        "analytics",
        "9. Intelligence & Analytics (Ctrl+9)",
        "Deep performance metrics: daily application throughput, platform success rates, and ATS funnel conversion.",
        "analytics"
    ),
    (
        "profile",
        "10. Candidate Profile & Facts (Ctrl+0)",
        "Manage verified personal details, skills, and 398+ screening Q&A facts used for zero-hallucination answers.",
        "profile"
    ),
    (
        "settings",
        "11. Settings & Readiness Center (Ctrl+,)",
        "Configure AI providers, automation safety limits, database backups, "
        "and re-run the Setup Wizard whenever needed.",
        "settings"
    ),
]


class ProductTourOverlay(QWidget):
    """Floating tour overlay guiding the user through the primary application views."""
    tour_finished = Signal()

    def __init__(self, main_window, parent=None):
        widget_parent = parent if isinstance(parent, QWidget) else (main_window if isinstance(main_window, QWidget) else None)
        super().__init__(widget_parent)
        self.main_window = main_window
        self.current_stop = 0

        # Semi-transparent overlay canvas
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet("background-color: rgba(15, 17, 23, 0.75);")
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setAlignment(Qt.AlignCenter)

        # Centered Tour Card
        self.card = QFrame()
        self.card.setObjectName("tour_card")
        self.card.setFixedSize(520, 240)
        self.card.setStyleSheet(f"""
            #tour_card {{
                background-color: {COLORS['surface']};
                border: 2px solid {COLORS['primary']};
                border-radius: 12px;
            }}
            #tour_card QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QVBoxLayout(self.card)
        c_layout.setContentsMargins(20, 20, 20, 20)
        c_layout.setSpacing(12)

        # Header Row
        h_row = QHBoxLayout()
        self.lbl_counter = QLabel("Stop 1 of 9")
        self.lbl_counter.setStyleSheet(f"""
            color: {COLORS['primary']};
            background-color: {COLORS['primary_subtle']};
            font-size: 11px;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        h_row.addWidget(self.lbl_counter)
        h_row.addStretch()

        self.btn_close = QPushButton("✕")
        self.btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                font-size: 14px;
                border: none;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_close.clicked.connect(self._close_tour)
        h_row.addWidget(self.btn_close)
        c_layout.addLayout(h_row)

        # Stop Title
        self.lbl_title = QLabel("1. Workspace Dashboard")
        self.lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLORS['text']};")
        c_layout.addWidget(self.lbl_title)

        # Stop Description
        self.lbl_desc = QLabel("Tour description text...")
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; line-height: 1.4;")
        c_layout.addWidget(self.lbl_desc)
        c_layout.addStretch()

        # Action Buttons
        btn_row = QHBoxLayout()
        self.btn_skip = QPushButton("Skip Tour")
        self.btn_skip.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                font-size: 12px;
                border: none;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_skip.clicked.connect(self._close_tour)
        btn_row.addWidget(self.btn_skip)
        btn_row.addStretch()

        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
            }}
        """)
        self.btn_prev.clicked.connect(self._go_prev)
        btn_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next Stop ►")
        self.btn_next.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_next.clicked.connect(self._go_next)
        btn_row.addWidget(self.btn_next)

        c_layout.addLayout(btn_row)
        root_layout.addWidget(self.card)

    def start(self):
        """Displays the tour overlay and jumps to the first stop."""
        target_parent = self.parent() or self.main_window
        if target_parent and hasattr(target_parent, "rect"):
            self.setGeometry(target_parent.rect())
        self.show()
        self.raise_()
        self._show_stop(0)

    def _show_stop(self, stop_idx: int):
        if 0 <= stop_idx < len(TOUR_STOPS):
            self.current_stop = stop_idx
            view_id, title, desc, _ = TOUR_STOPS[stop_idx]

            # Shift main window view underneath overlay
            if hasattr(self.main_window, "navigate_to"):
                self.main_window.navigate_to(view_id)

            self.lbl_counter.setText(f"Stop {stop_idx + 1} of {len(TOUR_STOPS)}")
            self.lbl_title.setText(title)
            self.lbl_desc.setText(desc)

            self.btn_prev.setEnabled(stop_idx > 0)
            if stop_idx == len(TOUR_STOPS) - 1:
                self.btn_next.setText("Finish Tour ✓")
            else:
                self.btn_next.setText("Next Stop ►")

    def _go_prev(self):
        if self.current_stop > 0:
            self._show_stop(self.current_stop - 1)

    def _go_next(self):
        if self.current_stop < len(TOUR_STOPS) - 1:
            self._show_stop(self.current_stop + 1)
        else:
            self._close_tour()

    def _close_tour(self):
        self.hide()
        self.tour_finished.emit()
        self.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._close_tour()
        elif event.key() == Qt.Key_Right:
            self._go_next()
        elif event.key() == Qt.Key_Left:
            self._go_prev()
        else:
            super().keyPressEvent(event)
