"""Activity Record Detail and All Activity Dialogs for JobPilot.

Provides:
- ActivityDetailDialog: Clean popup displaying necessary data for a single activity record.
- AllActivityDialog: Full activity history popup with platform filtering and detail drill-down.
"""

from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QScrollArea,
    QWidget,
    QGridLayout,
    QComboBox,
)

from app.db.session import SessionLocal, get_db_session
from app.db.models.job import Job
from app.db.models.application import Application
from app.db.models.interview import Interview
from app.services.dashboard_service import ActivityEvent
from app.utils_time import format_local_datetime
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge


class ActivityDetailDialog(QDialog):
    """Modern modal popup displaying focused, essential details for a specific activity record."""

    def __init__(self, event: ActivityEvent, session_factory=None, parent=None):
        super().__init__(parent)
        self.activity_event = event
        self.session_factory = session_factory or SessionLocal

        self.setWindowTitle("Activity Record Details")
        self.setFixedSize(540, 430)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(18)

        # Header: Icon Pill, Event Name & Timestamp, Close Button
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        ev_icon = "📄" if "JOB" in event.event_type else ("🚀" if "SUBMIT" in event.event_type else ("📅" if "INTERVIEW" in event.event_type else "⚡"))
        lbl_icon_pill = QLabel(ev_icon)
        lbl_icon_pill.setAlignment(Qt.AlignCenter)
        lbl_icon_pill.setFixedSize(36, 36)
        lbl_icon_pill.setStyleSheet(f"""
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            font-size: 18px;
        """)
        hdr.addWidget(lbl_icon_pill)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        lbl_type = QLabel(event.event_type.replace("_", " ").title())
        lbl_type.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text']}; background: transparent;")
        
        time_str = format_local_datetime(event.timestamp, "%B %d, %Y • %H:%M") if hasattr(event.timestamp, "strftime") else str(event.timestamp)
        lbl_time = QLabel(time_str)
        lbl_time.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent;")
        title_box.addWidget(lbl_type)
        title_box.addWidget(lbl_time)
        hdr.addLayout(title_box, 1)

        plat_str = (event.platform or "System").title()
        plat_badge = QLabel(plat_str)
        plat_badge.setStyleSheet(f"""
            background-color: {COLORS['primary']}15;
            color: {COLORS['primary']};
            border: 1px solid {COLORS['primary']}40;
            border-radius: 4px;
            padding: 4px 10px;
            font-size: 11px;
            font-weight: 700;
        """)
        hdr.addWidget(plat_badge)

        layout.addLayout(hdr)

        # Subtle divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {COLORS['border']}; border: none;")
        layout.addWidget(div)

        # Clean Key-Value List (No nested border boxes!)
        extra = self._fetch_entity_details()

        rows_widget = QWidget()
        rows_layout = QVBoxLayout(rows_widget)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(0)

        job_title = extra.get("job_title") or event.title
        company = extra.get("company") or "N/A"
        location = extra.get("location") or "N/A"
        status_val = extra.get("status") or event.status or event.description

        rows_layout.addWidget(self._build_row("Job Title", job_title))
        rows_layout.addWidget(self._build_row("Company", company))
        rows_layout.addWidget(self._build_row("Location", location))
        rows_layout.addWidget(self._build_row("Status", status_val, is_badge=True))

        if extra.get("notes"):
            rows_layout.addWidget(self._build_row("Notes", extra["notes"]))

        if extra.get("job_url"):
            rows_layout.addWidget(self._build_row("Job Listing", extra["job_url"], is_link=True))

        layout.addWidget(rows_widget, 1)

        # Footer
        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 7px 24px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
                color: #FFFFFF;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)
        layout.addLayout(btn_box)

    def _build_row(self, label: str, value: str, is_badge: bool = False, is_link: bool = False) -> QWidget:
        """Builds a sleek key-value row with a subtle bottom divider."""
        row = QWidget()
        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(4, 9, 4, 9)
        r_layout.setSpacing(16)

        lbl_key = QLabel(label)
        lbl_key.setFixedWidth(110)
        lbl_key.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 500; background: transparent;")
        r_layout.addWidget(lbl_key)

        if is_link:
            lbl_val = QLabel(f'<a style="color: {COLORS["primary"]}; text-decoration: none; font-weight: 600;" href="{value}">Open Job Link ↗</a>')
            lbl_val.setOpenExternalLinks(True)
            lbl_val.setStyleSheet("font-size: 12px; background: transparent;")
            r_layout.addWidget(lbl_val, 1)
        elif is_badge:
            badge_container = QWidget()
            b_lay = QHBoxLayout(badge_container)
            b_lay.setContentsMargins(0, 0, 0, 0)
            b_lay.setSpacing(0)
            
            badge_lbl = QLabel(str(value))
            badge_lbl.setStyleSheet(f"""
                background-color: #23863622;
                color: #3fb950;
                border: 1px solid #23863666;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 11px;
                font-weight: 700;
            """)
            b_lay.addWidget(badge_lbl)
            b_lay.addStretch(1)
            r_layout.addWidget(badge_container, 1)
        else:
            lbl_val = QLabel(str(value))
            lbl_val.setWordWrap(True)
            lbl_val.setStyleSheet(f"color: {COLORS['text']}; font-size: 13px; font-weight: 600; background: transparent;")
            r_layout.addWidget(lbl_val, 1)

        wrapper = QWidget()
        w_lay = QVBoxLayout(wrapper)
        w_lay.setContentsMargins(0, 0, 0, 0)
        w_lay.setSpacing(0)
        w_lay.addWidget(row)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']}88; border: none;")
        w_lay.addWidget(divider)

        return wrapper

    def _fetch_entity_details(self) -> dict:
        """Fetches supplementary details from the SQLite database if entity_id is available."""
        details = {}
        if not self.activity_event.entity_id:
            # Parse from title and description
            if " — " in self.activity_event.title:
                parts = self.activity_event.title.split(" — ", 1)
                details["company"] = parts[0].strip()
                details["job_title"] = parts[1].strip()
            elif "Discovered: " in self.activity_event.title:
                details["job_title"] = self.activity_event.title.replace("Discovered: ", "").strip()
                if " • " in self.activity_event.description:
                    dparts = self.activity_event.description.split(" • ", 1)
                    details["company"] = dparts[0].strip()
                    details["location"] = dparts[1].strip()
            return details

        try:
            with get_db_session(self.session_factory) as session:
                if self.activity_event.event_type == "JOB_DISCOVERED":
                    job = session.query(Job).filter_by(id=self.activity_event.entity_id).first()
                    if job:
                        details["job_title"] = job.title
                        details["company"] = job.company_raw
                        details["location"] = job.location
                        details["job_url"] = job.job_url
                        details["notes"] = f"Experience: {job.experience_raw or 'N/A'} • Salary: {job.salary_raw or 'N/A'}"
                elif self.activity_event.event_type in ("APPLICATION_SUBMITTED", "STATUS_CHANGED"):
                    app = session.query(Application).filter_by(id=self.activity_event.entity_id).first()
                    if app and app.job:
                        details["job_title"] = app.job.title
                        details["company"] = app.job.company_raw
                        details["location"] = app.job.location
                        details["status"] = app.status
                        details["job_url"] = app.job.job_url
                        details["notes"] = f"Applied: {app.applied_at or 'N/A'} • Match Score: {app.match_score or 'N/A'}%"
                elif self.activity_event.event_type == "INTERVIEW_SCHEDULED":
                    iv = session.query(Interview).filter_by(id=self.activity_event.entity_id).first()
                    if iv and iv.application and iv.application.job:
                        details["job_title"] = iv.application.job.title
                        details["company"] = iv.application.job.company_raw
                        details["status"] = f"Round: {iv.round_name or 'Interview'}"
                        details["notes"] = f"Interviewer: {iv.interviewer_name or 'N/A'} • Meeting: {iv.meeting_link or 'N/A'}"
        except Exception:
            pass

        return details


class AllActivityDialog(QDialog):
    """Clean modern modal popup listing all system activities with platform filtering."""

    def __init__(self, events: List[ActivityEvent], session_factory=None, parent=None):
        super().__init__(parent)
        self.all_events = events
        self.session_factory = session_factory or SessionLocal

        self.setWindowTitle("System Activity Log")
        self.setFixedSize(680, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        hdr.setSpacing(10)

        lbl_icon = QLabel("⚡")
        lbl_icon.setStyleSheet("font-size: 18px; background: transparent;")
        hdr.addWidget(lbl_icon)

        lbl_title = QLabel("System Activity Log")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']}; background: transparent;")
        hdr.addWidget(lbl_title)

        hdr.addStretch(1)

        # Platform Filter Dropdown
        lbl_filter = QLabel("Platform:")
        lbl_filter.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 500; background: transparent;")
        hdr.addWidget(lbl_filter)

        self.combo_filter = QComboBox()
        self.combo_filter.addItem("All Platforms", "all")
        self.combo_filter.addItem("LinkedIn", "linkedin")
        self.combo_filter.addItem("Naukri", "naukri")
        self.combo_filter.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
                min-width: 110px;
            }}
        """)
        self.combo_filter.currentIndexChanged.connect(self._apply_filter)
        hdr.addWidget(self.combo_filter)

        layout.addLayout(hdr)

        # Divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background-color: {COLORS['border']}; border: none;")
        layout.addWidget(div)

        # Scroll Area for Activity List
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)

        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll, 1)

        # Footer
        footer = QHBoxLayout()
        self.lbl_count = QLabel(f"Showing {len(events)} events (click any row to view details)")
        self.lbl_count.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
        footer.addWidget(self.lbl_count)
        footer.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
                color: #FFFFFF;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

        self._render_events(self.all_events)

    def _apply_filter(self):
        plat = self.combo_filter.currentData()
        if plat == "all":
            filtered = self.all_events
        else:
            filtered = [e for e in self.all_events if (e.platform or "").lower() == plat]
        self._render_events(filtered)
        self.lbl_count.setText(f"Showing {len(filtered)} events (click any row to view details)")

    def _render_events(self, events: List[ActivityEvent]):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not events:
            lbl_none = QLabel("No events match the selected filter.")
            lbl_none.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; padding: 32px;")
            lbl_none.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(lbl_none)
            return

        for ev in events:
            row_container = QWidget()
            row_container.setCursor(Qt.PointingHandCursor)
            row_container.setStyleSheet(f"""
                QWidget#FeedRow {{
                    background-color: transparent;
                    border-radius: 6px;
                }}
                QWidget#FeedRow:hover {{
                    background-color: {COLORS['surface_alt']};
                }}
            """)
            row_container.setObjectName("FeedRow")

            r_lay = QHBoxLayout(row_container)
            r_lay.setContentsMargins(8, 8, 8, 8)
            r_lay.setSpacing(12)

            # Platform tag
            plat_str = (ev.platform or "System").title()
            lbl_p = QLabel(plat_str)
            lbl_p.setStyleSheet(f"""
                background-color: {COLORS['primary']}15;
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']}33;
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 10px;
                font-weight: 700;
            """)
            r_lay.addWidget(lbl_p)

            # Title and description
            t_box = QVBoxLayout()
            t_box.setContentsMargins(0, 0, 0, 0)
            t_box.setSpacing(2)
            lbl_title = QLabel(str(ev.title or ""))
            lbl_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; font-weight: 600; background: transparent;")
            lbl_desc = QLabel(str(ev.description or ""))
            lbl_desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; background: transparent;")
            t_box.addWidget(lbl_title)
            t_box.addWidget(lbl_desc)
            r_lay.addLayout(t_box, 1)

            # Timestamp
            time_str = format_local_datetime(ev.timestamp, "%b %d, %H:%M") if hasattr(ev.timestamp, "strftime") else str(ev.timestamp)
            lbl_t = QLabel(time_str)
            lbl_t.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 500; background: transparent;")
            r_lay.addWidget(lbl_t)

            # Subtle arrow
            lbl_arr = QLabel("→")
            lbl_arr.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: bold; background: transparent;")
            r_lay.addWidget(lbl_arr)

            # Clicking the row opens detail dialog
            row_container.mousePressEvent = lambda e, event=ev: self._open_detail(event)

            # Wrap in item with divider
            wrapper = QWidget()
            w_lay = QVBoxLayout(wrapper)
            w_lay.setContentsMargins(0, 0, 0, 0)
            w_lay.setSpacing(0)
            w_lay.addWidget(row_container)

            div = QFrame()
            div.setFixedHeight(1)
            div.setStyleSheet(f"background-color: {COLORS['border']}66; border: none;")
            w_lay.addWidget(div)

            self.list_layout.addWidget(wrapper)

        self.list_layout.addStretch(1)

    def _open_detail(self, event: ActivityEvent):
        dlg = ActivityDetailDialog(event, session_factory=self.session_factory, parent=self)
        dlg.exec()
