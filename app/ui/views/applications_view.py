"""Application history and recruitment pipeline view component.

Provides stage-categorized tracking, summary metric cards, multi-action status
transition and scheduling modal, full chronological audit history inspection,
and an inline row-wise filter toolbar.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from PySide6.QtCore import QDateTime, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Application, ApplicationStatusHistory
from app.services.application_service import ApplicationFilter, ApplicationService
from app.services.recruitment_service import RecruitmentService
from app.services.search.search_result import NavigationAction, NavigationRequest, ViewStateSnapshot
from app.ui.theme import COLORS, _CHEVRON_DOWN_PATH, _CHEVRON_DOWN_HOVER_PATH
from app.ui.widgets.exact_filter_chip import ExactFilterChip
from app.ui.widgets.jobs import JobsPagination
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge
from app.utils_time import format_local_datetime


STATUS_OPTIONS = [
    ("SUBMITTED", "📄 Submitted"),
    ("UNDER_REVIEW", "⏳ Under Review"),
    ("SHORTLISTED", "🌟 Shortlisted"),
    ("RECRUITER_CONTACTED", "📞 Recruiter Contacted (Received Call)"),
    ("ASSESSMENT", "📝 Technical Assessment"),
    ("INTERVIEW", "🗓️ Interview Scheduled"),
    ("OFFER", "🎉 Offer Received"),
    ("REJECTED", "❌ Rejected / Closed"),
    ("WITHDRAWN", "↩️ Withdrawn"),
    ("JUNK", "🗑️ Junk / Discarded"),
]


class StatusTransitionDialog(QDialog):
    """Modern ATS multi-action dialog for updating status, scheduling interviews, and logging follow-ups."""

    def __init__(
        self,
        application: Application,
        service: ApplicationService,
        recruitment_service: Optional[RecruitmentService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.application = application
        self.service = service
        self.recruitment_service = recruitment_service or RecruitmentService()

        company = application.job.company_raw if application.job else "Company"
        title = application.job.title if application.job else "Job"
        platform = (application.job.platform if application.job else "Platform").title()

        self.setWindowTitle(f"Update Application — {company}")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: 500;
            }}
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit, QSpinBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 13px;
                min-height: 24px;
            }}
            QLineEdit:hover, QTextEdit:hover, QComboBox:hover, QDateTimeEdit:hover, QSpinBox:hover {{
                border-color: {COLORS['border_light']};
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus, QSpinBox:focus {{
                border-color: {COLORS['primary']};
            }}
            QComboBox, QDateTimeEdit {{
                padding-right: 32px;
            }}
            QComboBox::drop-down, QDateTimeEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow, QDateTimeEdit::down-arrow {{
                image: url({_CHEVRON_DOWN_PATH});
                width: 10px;
                height: 6px;
            }}
            QComboBox::down-arrow:hover, QDateTimeEdit::down-arrow:hover {{
                image: url({_CHEVRON_DOWN_HOVER_PATH});
            }}
            QComboBox QAbstractItemView {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 4px;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                min-height: 60px;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: #262C36;
                color: #F0F6FC;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #FF5F15;
                color: #FFFFFF;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background-color: {COLORS['surface']};
                padding: 14px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 600;
                font-size: 11px;
                padding: 8px 18px;
                margin-right: 6px;
                border-radius: 6px;
                border: 1px solid {COLORS['border']};
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['primary']};
                color: white;
                border-color: {COLORS['primary']};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # 1. Header Card with Job & Company Info
        hdr_card = QFrame()
        hdr_card.setStyleSheet("""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        hdr_layout = QVBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(4)

        top_meta = QHBoxLayout()
        lbl_meta = QLabel(f"🏢  {company}   •   🌐  {platform}")
        lbl_meta.setStyleSheet("color: #FF7A3D; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        top_meta.addWidget(lbl_meta)
        top_meta.addStretch()

        badge_curr = StatusBadge(application.status)
        top_meta.addWidget(badge_curr)
        hdr_layout.addLayout(top_meta)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("color: #F0F6FC; font-size: 15px; font-weight: 800; background: transparent; border: none;")
        hdr_layout.addWidget(lbl_title)

        applied_str = format_local_datetime(application.applied_at, "%b %d, %Y") if application.applied_at else "Recently"
        lbl_sub = QLabel(f"Applied: {applied_str}   •   Application ID: #{application.id}")
        lbl_sub.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent; border: none;")
        hdr_layout.addWidget(lbl_sub)
        layout.addWidget(hdr_card)

        # 2. Multi-Action Tabs (Change Status, Schedule Interview, Log Follow-Up)
        self.tabs = QTabWidget()

        # Tab 0: Update Pipeline Status
        tab_status = QWidget()
        tab_status_layout = QVBoxLayout(tab_status)
        tab_status_layout.setContentsMargins(14, 16, 14, 16)
        tab_status_layout.setSpacing(14)

        form_status = QFormLayout()
        form_status.setContentsMargins(0, 0, 0, 0)
        form_status.setSpacing(14)
        form_status.setLabelAlignment(Qt.AlignLeft)

        self.cmb_next = QComboBox()
        cur_status = application.status.strip().upper()
        default_select_idx = 0
        for idx, (code, label) in enumerate(STATUS_OPTIONS):
            self.cmb_next.addItem(label, code)
            if code == cur_status:
                default_select_idx = idx

        # Default to current or next logical step
        next_idx = min(default_select_idx + 1, len(STATUS_OPTIONS) - 1)
        self.cmb_next.setCurrentIndex(next_idx)
        form_status.addRow("Target Pipeline Status *", self.cmb_next)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Optional notes (e.g. recruiter called, salary discussed, assignment given, reason for change)...")
        self.txt_notes.setMinimumHeight(110)
        self.txt_notes.setMaximumHeight(150)
        form_status.addRow("Activity / Recruiter Notes", self.txt_notes)

        tab_status_layout.addLayout(form_status)

        lbl_status_hint = QLabel("💡 Updating the status records an immediate audit trail in the application history.")
        lbl_status_hint.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500;")
        tab_status_layout.addWidget(lbl_status_hint)
        tab_status_layout.addStretch()

        self.tabs.addTab(tab_status, "📊 Change Status")

        # Tab 1: Schedule Interview
        tab_interview = QWidget()
        tab_interview_layout = QVBoxLayout(tab_interview)
        tab_interview_layout.setContentsMargins(14, 16, 14, 16)
        tab_interview_layout.setSpacing(12)

        form_interview = QFormLayout()
        form_interview.setContentsMargins(0, 0, 0, 0)
        form_interview.setSpacing(10)
        form_interview.setLabelAlignment(Qt.AlignLeft)

        self.cmb_round_name = QComboBox()
        self.cmb_round_name.addItems([
            "HR Screening Call",
            "Technical Round 1",
            "Technical Round 2",
            "Coding Challenge / Assessment",
            "System Design / Architecture",
            "Hiring Manager Round",
            "Client / Final Round",
        ])
        form_interview.addRow("Round Name *", self.cmb_round_name)

        self.spn_round_num = QSpinBox()
        self.spn_round_num.setRange(1, 10)
        self.spn_round_num.setValue(1)
        form_interview.addRow("Round Number", self.spn_round_num)

        self.dt_interview = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
        self.dt_interview.setCalendarPopup(True)
        self.dt_interview.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        form_interview.addRow("Scheduled Date && Time *", self.dt_interview)

        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["VIRTUAL", "PHONE", "IN_PERSON"])
        form_interview.addRow("Interview Mode", self.cmb_mode)

        self.txt_meeting_link = QLineEdit()
        self.txt_meeting_link.setPlaceholderText("Google Meet, Zoom, MS Teams URL, or location...")
        form_interview.addRow("Meeting Link / Location", self.txt_meeting_link)

        self.txt_interviewer = QLineEdit()
        self.txt_interviewer.setPlaceholderText("e.g. Jane Doe (Engineering Manager)")
        form_interview.addRow("Interviewer Name", self.txt_interviewer)

        self.txt_interview_notes = QTextEdit()
        self.txt_interview_notes.setPlaceholderText("Topics to review, questions to ask, preparation points...")
        self.txt_interview_notes.setMaximumHeight(65)
        form_interview.addRow("Prep Notes", self.txt_interview_notes)

        tab_interview_layout.addLayout(form_interview)

        lbl_iv_hint = QLabel("💡 Saving will automatically move application to INTERVIEW status and show up on the Interviews page.")
        lbl_iv_hint.setStyleSheet("color: #A78BFA; font-size: 11px; font-weight: 500; padding-top: 4px;")
        lbl_iv_hint.setWordWrap(True)
        tab_interview_layout.addWidget(lbl_iv_hint)
        tab_interview_layout.addStretch()

        self.tabs.addTab(tab_interview, "🗓️ Schedule Interview")

        # Tab 2: Log / Schedule Follow-Up
        tab_followup = QWidget()
        tab_followup_layout = QVBoxLayout(tab_followup)
        tab_followup_layout.setContentsMargins(14, 16, 14, 16)
        tab_followup_layout.setSpacing(12)

        form_followup = QFormLayout()
        form_followup.setContentsMargins(0, 0, 0, 0)
        form_followup.setSpacing(12)
        form_followup.setLabelAlignment(Qt.AlignLeft)

        self.dt_followup_due = QDateTimeEdit(QDateTime.currentDateTime().addDays(3))
        self.dt_followup_due.setCalendarPopup(True)
        self.dt_followup_due.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        form_followup.addRow("Follow-Up Due Date *", self.dt_followup_due)

        self.txt_followup_contact = QLineEdit()
        self.txt_followup_contact.setPlaceholderText("Recruiter name, email, or LinkedIn profile URL...")
        form_followup.addRow("Recruiter Contact", self.txt_followup_contact)

        self.cmb_followup_channel = QComboBox()
        self.cmb_followup_channel.addItems(["Email", "LinkedIn InMail", "Phone Call", "WhatsApp Message"])
        form_followup.addRow("Outreach Channel", self.cmb_followup_channel)

        self.txt_followup_notes = QTextEdit()
        self.txt_followup_notes.setPlaceholderText("Context, message script, or what to follow up regarding...")
        self.txt_followup_notes.setMaximumHeight(85)
        form_followup.addRow("Reminder Notes", self.txt_followup_notes)

        tab_followup_layout.addLayout(form_followup)

        lbl_fu_hint = QLabel("💡 Creates an active reminder on the Follow-ups page.")
        lbl_fu_hint.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 500; padding-top: 4px;")
        tab_followup_layout.addWidget(lbl_fu_hint)
        tab_followup_layout.addStretch()

        self.tabs.addTab(tab_followup, "🔔 Schedule Follow-Up")

        layout.addWidget(self.tabs)

        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save && Update")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                padding: 7px 20px;
                border-radius: 6px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save.clicked.connect(self._save_action)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _save_action(self) -> None:
        active_tab = self.tabs.currentIndex()

        try:
            if active_tab == 0:
                # Tab 0: Status Change
                target = self.cmb_next.currentData() or self.cmb_next.currentText().strip()
                notes = self.txt_notes.toPlainText().strip() or None

                updated, err = self.service.transition_status(
                    application_id=self.application.id,
                    new_status=target,
                    source="manual_ui",
                    notes=notes,
                    allow_override=True,
                )
                if not updated:
                    QMessageBox.warning(self, "Transition Warning", f"Failed: {err}")
                    return

            elif active_tab == 1:
                # Tab 1: Schedule Interview
                round_name = self.cmb_round_name.currentText().strip()
                round_num = self.spn_round_num.value()
                qdt = self.dt_interview.dateTime()
                scheduled_at = qdt.toPython()
                mode = self.cmb_mode.currentText().strip()
                link = self.txt_meeting_link.text().strip() or None
                interviewer = self.txt_interviewer.text().strip() or None
                notes = self.txt_interview_notes.toPlainText().strip() or None

                # 1. Create interview record
                iv, err = self.recruitment_service.schedule_interview(
                    application_id=self.application.id,
                    round_name=round_name,
                    scheduled_at=scheduled_at,
                    round_number=round_num,
                    mode=mode,
                    meeting_link=link,
                    interviewer_name=interviewer,
                    notes=notes,
                )
                if not iv:
                    QMessageBox.warning(self, "Scheduling Error", f"Failed: {err}")
                    return

                # 2. Transition status to INTERVIEW
                self.service.transition_status(
                    application_id=self.application.id,
                    new_status="INTERVIEW",
                    source="manual_ui",
                    notes=f"Scheduled {round_name} with {interviewer or 'interviewer'}",
                    allow_override=True,
                )

            elif active_tab == 2:
                # Tab 2: Schedule Follow-Up
                qdt = self.dt_followup_due.dateTime()
                due_at = qdt.toPython()
                contact = self.txt_followup_contact.text().strip()
                channel = self.cmb_followup_channel.currentText().strip()
                raw_notes = self.txt_followup_notes.toPlainText().strip()
                notes = f"[{channel}] Contact: {contact}. {raw_notes}".strip()

                fu, err = self.recruitment_service.create_follow_up(
                    due_at=due_at,
                    application_id=self.application.id,
                    notes=notes,
                )
                if not fu:
                    QMessageBox.warning(self, "Follow-Up Error", f"Failed: {err}")
                    return

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")


class AuditTimelineGraphWidget(QScrollArea):
    """Connected timeline graph visualizing application status transitions."""

    def __init__(
        self,
        history: List[ApplicationStatusHistory],
        application: Application,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(0)

        if not history:
            empty_box = QFrame()
            empty_box.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border: 1px dashed {COLORS['border']};
                    border-radius: 8px;
                    padding: 30px;
                }}
            """)
            e_layout = QVBoxLayout(empty_box)
            e_layout.setAlignment(Qt.AlignCenter)
            e_lbl = QLabel("No state transitions recorded yet.")
            e_lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; font-weight: 600;")
            e_layout.addWidget(e_lbl)
            layout.addWidget(empty_box)
        else:
            for idx, item in enumerate(history):
                is_last = (idx == len(history) - 1)
                node_widget = self._create_timeline_node(item, idx, is_last)
                layout.addWidget(node_widget)

        layout.addStretch()
        self.setWidget(container)

    def _create_timeline_node(self, item: ApplicationStatusHistory, index: int, is_last: bool) -> QWidget:
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(14)

        # 1. Left Spine Column (Milestone Node + Connecting Rail)
        spine_col = QWidget()
        spine_col.setFixedWidth(24)
        spine_layout = QVBoxLayout(spine_col)
        spine_layout.setContentsMargins(0, 6, 0, 0)
        spine_layout.setSpacing(0)
        spine_layout.setAlignment(Qt.AlignHCenter)

        st_clean = (item.new_status or "").upper()
        if st_clean in ("SUBMITTED", "OFFER"):
            dot_color = COLORS.get("success", "#2EA043")
        elif st_clean in ("UNDER_REVIEW", "PENDING"):
            dot_color = COLORS.get("warning", "#D29922")
        elif st_clean in ("INTERVIEW", "ASSESSMENT", "SHORTLISTED"):
            dot_color = COLORS.get("purple", "#A371F7")
        elif st_clean in ("REJECTED", "FAILED", "WITHDRAWN"):
            dot_color = COLORS.get("danger", "#F85149")
        elif st_clean in ("APPLYING", "RUNNING"):
            dot_color = COLORS.get("cyan", "#39C5CF")
        else:
            dot_color = COLORS.get("info", "#388BFD")

        dot = QLabel()
        dot.setFixedSize(14, 14)
        dot.setStyleSheet(f"""
            background-color: {dot_color};
            border: 2px solid {COLORS['surface']};
            border-radius: 7px;
        """)
        spine_layout.addWidget(dot, 0, Qt.AlignHCenter)

        if not is_last:
            rail = QFrame()
            rail.setFixedWidth(2)
            rail.setStyleSheet(f"background-color: {COLORS['border']};")
            spine_layout.addWidget(rail, 1, Qt.AlignHCenter)
        else:
            spine_layout.addStretch(1)

        row_layout.addWidget(spine_col)

        # 2. Right Content Card
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {COLORS['border_light']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(12, 10, 12, 10)
        c_layout.setSpacing(6)

        # Header Row: Transition flow + Timestamp
        top_h = QHBoxLayout()
        top_h.setSpacing(8)

        from_st = item.old_status or "None (Init)"
        b_from = StatusBadge(from_st, status_type="neutral" if from_st.startswith("None") else "default", width=95, height=22)
        top_h.addWidget(b_from)

        arr = QLabel("→")
        arr.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 14px; font-weight: bold; background: transparent; border: none;")
        top_h.addWidget(arr)

        b_to = StatusBadge(item.new_status, width=105, height=22)
        top_h.addWidget(b_to)

        top_h.addStretch()

        time_str = format_local_datetime(item.changed_at, "%Y-%m-%d  %H:%M") if item.changed_at else "—"
        lbl_time = QLabel(f"🕒 {time_str}")
        lbl_time.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-family: monospace; background: transparent; border: none;")
        top_h.addWidget(lbl_time)
        c_layout.addLayout(top_h)

        # Meta Row: Trigger source
        src_raw = (item.source or "system").replace("_", " ").title()
        lbl_src = QLabel(f"Trigger Source: {src_raw}")
        lbl_src.setStyleSheet(f"""
            color: {COLORS['text_muted']};
            font-size: 11px;
            font-weight: 600;
            background: transparent;
            border: none;
        """)
        c_layout.addWidget(lbl_src)

        # Commentary block
        if item.notes and item.notes.strip():
            notes_box = QFrame()
            notes_box.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['background']};
                    border-left: 3px solid {COLORS['primary']};
                    border-radius: 4px;
                    padding: 6px 10px;
                }}
            """)
            n_layout = QVBoxLayout(notes_box)
            n_layout.setContentsMargins(0, 0, 0, 0)
            n_layout.setSpacing(2)

            lbl_note = QLabel(item.notes.strip())
            lbl_note.setWordWrap(True)
            lbl_note.setStyleSheet(f"color: {COLORS['text']}; font-size: 12px; background: transparent; border: none;")
            n_layout.addWidget(lbl_note)
            c_layout.addWidget(notes_box)

        row_layout.addWidget(card, 1)

        container_row = QWidget()
        cr_layout = QVBoxLayout(container_row)
        cr_layout.setContentsMargins(0, 0, 0, 0)
        cr_layout.setSpacing(0)
        cr_layout.addWidget(row)
        if not is_last:
            cr_layout.addSpacing(6)

        return container_row


class ApplicationHistoryDialog(QDialog):
    """Modal displaying chronological audit trail history for an application with dual Graph and Table views."""

    def __init__(
        self,
        application: Application,
        service: ApplicationService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.application = application
        self.service = service

        company = application.job.company_raw if application.job else "Company"
        title = application.job.title if application.job else "Job"
        platform = (application.job.platform if application.job else "Platform").title()

        self.setWindowTitle(f"Audit Trail — {company}")
        self.setMinimumWidth(800)
        self.setMinimumHeight(520)
        self.resize(840, 540)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                background-color: {COLORS['surface']};
                padding: 10px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 600;
                font-size: 12px;
                padding: 7px 18px;
                margin-right: 6px;
                border-radius: 6px;
                border: 1px solid {COLORS['border']};
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['primary']};
                color: white;
                border-color: {COLORS['primary']};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        # Header Card
        hdr_card = QFrame()
        hdr_card.setStyleSheet("""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        hdr_layout = QHBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(12)

        icon_lbl = QLabel("📋")
        icon_lbl.setStyleSheet("font-size: 20px; background: transparent; border: none;")
        hdr_layout.addWidget(icon_lbl)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        lbl_t = QLabel(f"{company} — {title}")
        lbl_t.setStyleSheet("color: #F0F6FC; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        info_layout.addWidget(lbl_t)

        lbl_sub = QLabel(f"Platform: {platform}   •   Application ID: #{application.id}")
        lbl_sub.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent; border: none;")
        info_layout.addWidget(lbl_sub)
        hdr_layout.addLayout(info_layout, 1)

        cur_badge = StatusBadge(application.status)
        hdr_layout.addWidget(cur_badge)
        layout.addWidget(hdr_card)

        # Load history records
        history = self.service.get_status_history(application.id)

        # Dual-View Tab Container (Graph View default, Tabular View secondary)
        self.tabs_view = QTabWidget()

        # Tab 0: Graph / Timeline View
        self.graph_view = AuditTimelineGraphWidget(history, application)
        self.tabs_view.addTab(self.graph_view, "📈 Timeline Graph View")

        # Tab 1: Tabular Audit View
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "Timestamp",
            "From Status",
            "To Status",
            "Trigger Source",
            "Notes / Reason",
        ])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        table.setColumnWidth(0, 135)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        table.setColumnWidth(1, 140)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        table.setColumnWidth(2, 140)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        table.setColumnWidth(3, 135)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(38)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)

        table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['background']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text']};
            }}
            QTableWidget::item:selected {{
                background-color: #21262D;
                color: #F0F6FC;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase;
                padding: 8px 10px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)

        table.setRowCount(len(history))
        for row, item in enumerate(history):
            time_str = format_local_datetime(item.changed_at, "%Y-%m-%d %H:%M") if item.changed_at else "-"
            t_item = QTableWidgetItem(time_str)
            t_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 0, t_item)

            from_st = item.old_status or "None (Init)"
            w_from = QWidget()
            l_from = QHBoxLayout(w_from)
            l_from.setContentsMargins(0, 0, 0, 0)
            l_from.setAlignment(Qt.AlignCenter)
            l_from.addWidget(StatusBadge(from_st, status_type="neutral" if from_st.startswith("None") else "default"))
            table.setCellWidget(row, 1, w_from)

            w_to = QWidget()
            l_to = QHBoxLayout(w_to)
            l_to.setContentsMargins(0, 0, 0, 0)
            l_to.setAlignment(Qt.AlignCenter)
            l_to.addWidget(StatusBadge(item.new_status))
            table.setCellWidget(row, 2, w_to)

            src_clean = (item.source or "system").replace("_", " ").title()
            s_item = QTableWidgetItem(src_clean)
            s_item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 3, s_item)

            n_item = QTableWidgetItem(item.notes or "-")
            n_item.setToolTip(item.notes or "")
            table.setItem(row, 4, n_item)

        self.tabs_view.addTab(table, "📋 Tabular Audit View")
        layout.addWidget(self.tabs_view, 1)

        # Footer
        ftr_layout = QHBoxLayout()
        lbl_count = QLabel(f"Total state transitions recorded: {len(history)}")
        lbl_count.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500;")
        ftr_layout.addWidget(lbl_count)
        ftr_layout.addStretch()

        if application.job:
            app_url = getattr(application.job, "application_url", None)
            src_url = getattr(application.job, "source_url", None)
            if app_url:
                btn_portal = QPushButton("🌐 Visit Company Portal ↗")
                btn_portal.setCursor(Qt.PointingHandCursor)
                btn_portal.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['primary']};
                        color: #FFFFFF;
                        border: none;
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['primary_hover']};
                    }}
                """)
                btn_portal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(app_url)))
                ftr_layout.addWidget(btn_portal)
            elif src_url:
                btn_src = QPushButton(f"Open on {application.job.platform.title()} ↗")
                btn_src.setCursor(Qt.PointingHandCursor)
                btn_src.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['surface_alt']};
                        color: {COLORS['text']};
                        border: 1px solid {COLORS['border']};
                        padding: 6px 14px;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 12px;
                    }}
                    QPushButton:hover {{
                        border-color: {COLORS['accent']};
                    }}
                """)
                btn_src.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(src_url)))
                ftr_layout.addWidget(btn_src)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 6px 18px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['border_light']};
                color: #FFFFFF;
            }}
        """)
        btn_close.clicked.connect(self.accept)
        ftr_layout.addWidget(btn_close)
        layout.addLayout(ftr_layout)


class ApplicationsView(QWidget):
    """Job application history and pipeline tracking view."""

    data_updated = Signal(str)

    # UI Tab categories mapped to domain statuses
    UI_STATUS_CATEGORIES = {
        0: None,  # All
        1: ["APPLYING", "MANUAL_REQUIRED", "UNKNOWN"],  # Active/In-Flight
        2: ["SUBMITTED", "UNDER_REVIEW"],  # Submitted
        3: ["SHORTLISTED", "RECRUITER_CONTACTED", "ASSESSMENT", "INTERVIEW"],  # Interview Pipeline
        4: ["OFFER"],  # Offers
        5: ["REJECTED", "WITHDRAWN"],  # Closed
    }

    STATUS_TO_TAB = {
        "APPLYING": 1,
        "MANUAL_REQUIRED": 1,
        "UNKNOWN": 1,
        "SUBMITTED": 2,
        "UNDER_REVIEW": 2,
        "SHORTLISTED": 3,
        "RECRUITER_CONTACTED": 3,
        "ASSESSMENT": 3,
        "INTERVIEW": 3,
        "OFFER": 4,
        "REJECTED": 5,
        "WITHDRAWN": 5,
    }

    def __init__(
        self,
        service: Optional[ApplicationService] = None,
        recruitment_service: Optional[RecruitmentService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or ApplicationService()
        self.recruitment_service = recruitment_service or RecruitmentService()
        self._current_apps: List[Application] = []
        self._is_syncing_filters = False
        self._current_page = 1
        self._page_size = 50
        self._exact_app_id: Optional[int] = None
        self._pending_navigation_request: Optional[NavigationRequest] = None
        self._state_snapshot: Optional[ViewStateSnapshot] = None

        # Debounced search timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(200)
        self._search_timer.timeout.connect(self.refresh)

        self._setup_ui()
        self._setup_shortcuts()
        self.refresh()

    def _setup_shortcuts(self) -> None:
        self._shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self._shortcut_search.activated.connect(self._focus_search)

        self._shortcut_refresh = QShortcut(QKeySequence("F5"), self)
        self._shortcut_refresh.activated.connect(self.refresh)

    def _focus_search(self) -> None:
        self.txt_search.setFocus()
        self.txt_search.selectAll()

    def _setup_ui(self) -> None:
        self.setObjectName("applicationsView")
        self.setStyleSheet(f"""
            #applicationsView {{
                background-color: {COLORS['background']};
            }}
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header
        self.header = PageHeader(
            title="Applications Pipeline",
            subtitle="Track application statuses, state transitions, recruiter calls, interviews, and full audit trails.",
        )
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # 2. Notification Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Pipeline Metrics Cards Bar (Clickable)
        self.metrics_frame = QFrame()
        self.metrics_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
        metrics_layout = QHBoxLayout(self.metrics_frame)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(14)

        self.lbl_card_submitted = self._create_metric_widget("Submitted", "0", COLORS.get("info", "#38bdf8"), target_tab=2, target_status="SUBMITTED")
        self.lbl_card_review = self._create_metric_widget("Under Review", "0", COLORS.get("warning", "#fbbf24"), target_tab=2, target_status="UNDER_REVIEW")
        self.lbl_card_interview = self._create_metric_widget("Interviewing", "0", COLORS.get("purple", "#a78bfa"), target_tab=3)
        self.lbl_card_offers = self._create_metric_widget("Offers", "0", COLORS.get("success", "#34d399"), target_tab=4, target_status="OFFER")
        self.lbl_card_rejected = self._create_metric_widget("Rejected", "0", COLORS.get("danger", "#f87171"), target_tab=5)

        metrics_layout.addWidget(self.lbl_card_submitted)
        metrics_layout.addWidget(self.lbl_card_review)
        metrics_layout.addWidget(self.lbl_card_interview)
        metrics_layout.addWidget(self.lbl_card_offers)
        metrics_layout.addWidget(self.lbl_card_rejected)
        main_layout.addWidget(self.metrics_frame)

        # 4. Segmented Pipeline Stage Tabs
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 600;
                font-size: 12px;
                padding: 8px 16px;
                margin-right: 6px;
                border-radius: 8px;
                border: 1px solid {COLORS['border']};
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['primary']};
                color: white;
                border-color: {COLORS['primary']};
                font-weight: 700;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        self.tabs.addTab(QWidget(), "All Applications")
        self.tabs.addTab(QWidget(), "Active / Applying")
        self.tabs.addTab(QWidget(), "Submitted")
        self.tabs.addTab(QWidget(), "Shortlisted && Interview")
        self.tabs.addTab(QWidget(), "Offers")
        self.tabs.addTab(QWidget(), "Closed / Rejected")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        main_layout.addWidget(self.tabs)

        # 5. Row-Wise Filter & Search Toolbar
        filter_card = QFrame()
        filter_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 12px;
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        filter_row = QHBoxLayout(filter_card)
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(10)

        # Search box with debounce
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Filter by company, job title, keywords...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        self.txt_search.returnPressed.connect(self.refresh)
        self.txt_search.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        filter_row.addWidget(self.txt_search, 1)

        # Platform Filter
        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["All Platforms", "LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor", "Manual"])
        self.cmb_platform.currentIndexChanged.connect(self._on_platform_filter_changed)
        self._style_combo(self.cmb_platform)
        filter_row.addWidget(self.cmb_platform)

        # Specific Status Filter
        self.cmb_status_filter = QComboBox()
        self.cmb_status_filter.addItems([
            "All Statuses",
            "Submitted",
            "Under Review",
            "Shortlisted",
            "Recruiter Contacted",
            "Assessment",
            "Interview",
            "Offer",
            "Rejected",
            "Withdrawn",
            "Junk",
        ])
        self.cmb_status_filter.currentIndexChanged.connect(self._on_status_filter_changed)
        self._style_combo(self.cmb_status_filter)
        filter_row.addWidget(self.cmb_status_filter)

        # Date Range Filter
        self.cmb_date_filter = QComboBox()
        self.cmb_date_filter.addItems(["All Time", "Today", "Past 7 Days", "Past 30 Days"])
        self.cmb_date_filter.currentIndexChanged.connect(self._on_date_filter_changed)
        self._style_combo(self.cmb_date_filter)
        filter_row.addWidget(self.cmb_date_filter)

        # Results Count Pill
        self.lbl_count_pill = QLabel("0 records")
        self.lbl_count_pill.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        filter_row.addWidget(self.lbl_count_pill)

        # Clear Filters Button
        self.btn_clear_filters = QPushButton("Reset")
        self.btn_clear_filters.setCursor(Qt.PointingHandCursor)
        self.btn_clear_filters.setToolTip("Reset all filters")
        self.btn_clear_filters.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        self.btn_clear_filters.clicked.connect(self._clear_all_filters)
        filter_row.addWidget(self.btn_clear_filters)

        main_layout.addWidget(filter_card)

        # Exact Record Filter Banner Chip
        self.exact_filter_chip = ExactFilterChip(parent=self)
        self.exact_filter_chip.clear_requested.connect(self.clear_exact_filter)
        main_layout.addWidget(self.exact_filter_chip)

        # 6. Applications Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Company",
            "Job Title",
            "Platform",
            "Status",
            "Applied Date",
            "Last Activity",
            "Actions",
        ])
        # Balanced column sizing to fit 950-1000px screens without overflow
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 135)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 80)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 145)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 95)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 125)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 145)

        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        # Double-click to inspect and update
        self.table.cellDoubleClicked.connect(self._on_table_double_clicked)

        # Right-click context menu
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                gridline-color: transparent;
                color: {COLORS['text']};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
                border-bottom: 1px solid {COLORS['border']}40;
            }}
            QTableWidget::item:hover {{
                background-color: #262C36;
                color: #FFFFFF;
            }}
            QTableWidget::item:selected {{
                background-color: #262C36;
                color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        main_layout.addWidget(self.table, 1)

        # 6. Pagination Bar
        self.pagination = JobsPagination(self, item_name="applications")
        self.pagination.page_changed.connect(self._on_page_changed)
        self.pagination.page_size_changed.connect(self._on_page_size_changed)
        main_layout.addWidget(self.pagination)

    def _on_page_changed(self, new_page: int) -> None:
        self._current_page = new_page
        self.refresh()

    def _on_page_size_changed(self, new_page_size: int) -> None:
        self._page_size = new_page_size
        self._current_page = 1
        self.refresh()

    def _style_combo(self, combo: QComboBox) -> None:
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 28px 5px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QComboBox:hover {{
                border-color: {COLORS['border_light']};
            }}
            QComboBox:focus {{
                border-color: {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border: none;
                background: transparent;
            }}
            QComboBox::down-arrow {{
                image: url({_CHEVRON_DOWN_PATH});
                width: 9px;
                height: 5px;
            }}
            QComboBox::down-arrow:hover {{
                image: url({_CHEVRON_DOWN_HOVER_PATH});
            }}
            QComboBox QAbstractItemView {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 4px;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 26px;
                padding: 4px 8px;
                border-radius: 4px;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: #FF5F15;
                color: #FFFFFF;
            }}
        """)

    def _on_search_text_changed(self, text: str) -> None:
        """Debounces search input to prevent rapid database queries while typing."""
        self._current_page = 1
        if not text.strip():
            self._search_timer.stop()
            self.refresh()
        else:
            self._search_timer.start()

    def _on_platform_filter_changed(self, idx: int) -> None:
        if not self._is_syncing_filters:
            self._current_page = 1
            self.refresh()

    def _on_date_filter_changed(self, idx: int) -> None:
        if not self._is_syncing_filters:
            self._current_page = 1
            self.refresh()

    def _on_tab_changed(self, tab_idx: int) -> None:
        """Synchronizes tab change with status dropdown to avoid contradictory zero-result queries."""
        if self._is_syncing_filters:
            return

        self._current_page = 1

        spec_text = self.cmb_status_filter.currentText().strip().upper().replace(" ", "_")
        allowed = self.UI_STATUS_CATEGORIES.get(tab_idx)
        if allowed is not None and spec_text not in ["ALL_STATUSES", "ALL"]:
            if spec_text not in allowed:
                self.cmb_status_filter.blockSignals(True)
                self.cmb_status_filter.setCurrentIndex(0)
                self.cmb_status_filter.blockSignals(False)

        self.refresh()

    def _on_status_filter_changed(self, idx: int) -> None:
        """Synchronizes specific status selection with active category tab."""
        if self._is_syncing_filters:
            return

        spec_text = self.cmb_status_filter.currentText().strip().upper().replace(" ", "_")
        if spec_text not in ["ALL_STATUSES", "ALL"]:
            cur_tab = self.tabs.currentIndex()
            allowed = self.UI_STATUS_CATEGORIES.get(cur_tab)
            if allowed is not None and spec_text not in allowed:
                target_tab = self.STATUS_TO_TAB.get(spec_text)
                if target_tab is not None:
                    self.tabs.blockSignals(True)
                    self.tabs.setCurrentIndex(target_tab)
                    self.tabs.blockSignals(False)

        self._current_page = 1
        self.refresh()

    def _clear_all_filters(self) -> None:
        self._is_syncing_filters = True
        try:
            self.txt_search.blockSignals(True)
            self.cmb_platform.blockSignals(True)
            self.cmb_status_filter.blockSignals(True)
            self.cmb_date_filter.blockSignals(True)
            self.tabs.blockSignals(True)

            self.txt_search.clear()
            self.cmb_platform.setCurrentIndex(0)
            self.cmb_status_filter.setCurrentIndex(0)
            self.cmb_date_filter.setCurrentIndex(0)
            self.tabs.setCurrentIndex(0)

            self.txt_search.blockSignals(False)
            self.cmb_platform.blockSignals(False)
            self.cmb_status_filter.blockSignals(False)
            self.cmb_date_filter.blockSignals(False)
            self.tabs.blockSignals(False)
            self._current_page = 1
        finally:
            self._is_syncing_filters = False

        self.refresh()

    def _create_metric_widget(
        self,
        title: str,
        value: str,
        color_hex: str,
        target_tab: int = 0,
        target_status: Optional[str] = None,
    ) -> QWidget:
        box = QWidget()
        box.setCursor(Qt.PointingHandCursor)
        box.setToolTip(f"Click to filter by {title}")
        box.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {color_hex};
                border-radius: 8px;
            }}
            QWidget:hover {{
                border-color: {color_hex};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(14, 10, 14, 10)
        box_layout.setSpacing(4)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {color_hex}; border: none; background: transparent;")
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border: none; background: transparent;")

        box_layout.addWidget(lbl_val)
        box_layout.addWidget(lbl_title)

        box.mousePressEvent = lambda e, t=target_tab, s=target_status: self._on_metric_card_clicked(t, s)
        return box

    def _on_metric_card_clicked(self, target_tab: int, target_status: Optional[str] = None) -> None:
        """Toggles category tab and status filter when a top metric card is clicked."""
        self._current_page = 1
        self._is_syncing_filters = True
        try:
            current_status = self.cmb_status_filter.currentText().strip().upper().replace(" ", "_")
            # If already active, toggle back to All Applications
            if self.tabs.currentIndex() == target_tab and (not target_status or current_status == target_status):
                self.tabs.setCurrentIndex(0)
                self.cmb_status_filter.setCurrentIndex(0)
            else:
                self.tabs.setCurrentIndex(target_tab)
                if target_status:
                    matched = False
                    for i in range(self.cmb_status_filter.count()):
                        code = self.cmb_status_filter.itemText(i).strip().upper().replace(" ", "_")
                        if code == target_status:
                            self.cmb_status_filter.setCurrentIndex(i)
                            matched = True
                            break
                    if not matched:
                        self.cmb_status_filter.setCurrentIndex(0)
                else:
                    self.cmb_status_filter.setCurrentIndex(0)
        finally:
            self._is_syncing_filters = False

        self.refresh()

    def _on_table_double_clicked(self, row: int, column: int) -> None:
        """Opens status transition dialog upon double-clicking an application row."""
        if 0 <= row < len(self._current_apps):
            self._on_transition_clicked(self._current_apps[row])

    def _on_table_context_menu(self, pos) -> None:
        """Displays rich context menu on right-clicking an application row."""
        row = self.table.rowAt(pos.y())
        if not (0 <= row < len(self._current_apps)):
            return

        app = self._current_apps[row]
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 18px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        act_update = menu.addAction("📝 Update Status...")
        act_update.triggered.connect(lambda: self._on_transition_clicked(app))

        act_history = menu.addAction("📋 View Audit Trail...")
        act_history.triggered.connect(lambda: self._on_history_clicked(app))

        job = app.job
        if job:
            url = getattr(job, "application_url", None) or getattr(job, "source_url", None)
            if url:
                menu.addSeparator()
                act_url = menu.addAction(f"🌐 Open Listing on {job.platform.title()} ↗")
                act_url.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))

            menu.addSeparator()
            if job.company_raw:
                act_copy_co = menu.addAction("🏢 Copy Company Name")
                act_copy_co.triggered.connect(lambda: QApplication.clipboard().setText(job.company_raw))
            if job.title:
                act_copy_title = menu.addAction("💼 Copy Job Title")
                act_copy_title.triggered.connect(lambda: QApplication.clipboard().setText(job.title))

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def refresh(self) -> None:
        """Reloads application records, applies multi-criteria filters at DB level, and recalculates metrics."""
        # 0. Check for armed navigation request from AppNavigator
        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)
            return

        # 0b. Exact Record Isolation Mode
        if self._exact_app_id is not None:
            app = self.service.get_application(self._exact_app_id)
            if app:
                self._current_apps = [app]
                self.pagination.set_pagination(1, 1, self._page_size)
                self.lbl_count_pill.setText("1 application")
                self.table.setSortingEnabled(False)
                self.table.setRowCount(1)
                self._populate_table_row(0, app)
                self.table.selectRow(0)
                job_title = app.job.title if app.job else f"Application #{app.id}"
                self.exact_filter_chip.set_record(job_title, app.id, "Application")
                return
            else:
                self.notification_bar.show_message("danger", f"Application #{self._exact_app_id} no longer exists or was removed.")
                self._exact_app_id = None
                self.exact_filter_chip.clear()

        summary = self.service.get_pipeline_summary()

        # Update metric cards
        self._update_metric_val(self.lbl_card_submitted, summary.get("SUBMITTED", 0))
        self._update_metric_val(self.lbl_card_review, summary.get("UNDER_REVIEW", 0))
        interview_total = summary.get("INTERVIEW", 0) + summary.get("SHORTLISTED", 0) + summary.get("RECRUITER_CONTACTED", 0) + summary.get("ASSESSMENT", 0)
        self._update_metric_val(self.lbl_card_interview, interview_total)
        self._update_metric_val(self.lbl_card_offers, summary.get("OFFER", 0))
        self._update_metric_val(self.lbl_card_rejected, summary.get("REJECTED", 0))

        # Determine target status list
        tab_idx = self.tabs.currentIndex()
        specific_status = self.cmb_status_filter.currentText().strip().upper().replace(" ", "_")
        if specific_status and specific_status not in ["ALL_STATUSES", "ALL"]:
            status_alias_map = {
                "RECRUITER_CALL": "RECRUITER_CONTACTED",
                "RECRUITER_CONTACTED": "RECRUITER_CONTACTED",
                "INTERVIEW": "INTERVIEW",
                "UNDER_REVIEW": "UNDER_REVIEW",
                "SUBMITTED": "SUBMITTED",
                "SHORTLISTED": "SHORTLISTED",
                "ASSESSMENT": "ASSESSMENT",
                "OFFER": "OFFER",
                "REJECTED": "REJECTED",
                "WITHDRAWN": "WITHDRAWN",
            }
            target_key = status_alias_map.get(specific_status, specific_status)
            status_list = [target_key]
        else:
            status_list = self.UI_STATUS_CATEGORIES.get(tab_idx)

        search = self.txt_search.text().strip() or None
        plat = self.cmb_platform.currentText().strip().lower()
        platform = None if plat in ["all platforms", "all", ""] else plat

        # Calculate database-level date range filter
        date_choice = self.cmb_date_filter.currentText().strip()
        date_from = None
        now = datetime.utcnow()
        if date_choice == "Today":
            date_from = datetime(now.year, now.month, now.day)
        elif date_choice == "Past 7 Days":
            date_from = now - timedelta(days=7)
        elif date_choice == "Past 30 Days":
            date_from = now - timedelta(days=30)

        f = ApplicationFilter(
            status_list=status_list,
            platform=platform,
            search=search,
            date_from=date_from,
        )
        total_count = self.service.count_applications(filters=f)
        offset = (self._current_page - 1) * self._page_size
        apps = self.service.list_applications(filters=f, limit=self._page_size, offset=offset)

        self._current_apps = apps
        self.pagination.set_pagination(self._current_page, total_count, self._page_size)
        self.lbl_count_pill.setText(f"{total_count} applications")

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._current_apps))
        for row, app in enumerate(self._current_apps):
            self._populate_table_row(row, app)
        self.table.setSortingEnabled(True)

    def _populate_table_row(self, row: int, app: Application) -> None:
        """Renders single application row with ATS status badges and action triggers."""
        job = app.job

        # Company (135px)
        c_name = job.company_raw if job else "N/A"
        c_item = QTableWidgetItem(c_name)
        c_item.setToolTip(c_name)
        self.table.setItem(row, 0, c_item)

        # Job Title (Stretch)
        t_name = job.title if job else "Unknown"
        t_item = QTableWidgetItem(t_name)
        t_item.setToolTip(t_name)
        self.table.setItem(row, 1, t_item)

        # Platform (80px)
        plat_str = (job.platform if job else "").title()
        p_item = QTableWidgetItem(plat_str)
        p_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 2, p_item)

        # Status Badge (145px)
        st_item = QTableWidgetItem(app.status)
        st_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 3, st_item)

        status_widget = QWidget()
        status_widget.setStyleSheet("background: transparent; border: none;")
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(StatusBadge(app.status))
        self.table.setCellWidget(row, 3, status_widget)

        # Applied Date (95px)
        applied_str = format_local_datetime(app.applied_at, "%Y-%m-%d") if app.applied_at else "-"
        d_item = QTableWidgetItem(applied_str)
        d_item.setData(Qt.UserRole, app.applied_at.isoformat() if app.applied_at else "")
        d_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 4, d_item)

        # Last Activity (125px)
        updated_str = format_local_datetime(app.updated_at, "%Y-%m-%d %H:%M") if app.updated_at else "-"
        u_item = QTableWidgetItem(updated_str)
        u_item.setData(Qt.UserRole, app.updated_at.isoformat() if app.updated_at else "")
        u_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(row, 5, u_item)

        # Actions (Update, Audit)
        act_widget = QWidget()
        act_widget.setStyleSheet("background: transparent; border: none;")
        act_layout = QHBoxLayout(act_widget)
        act_layout.setContentsMargins(4, 2, 4, 2)
        act_layout.setSpacing(6)
        act_layout.setAlignment(Qt.AlignCenter)

        btn_trans = QPushButton("Update")
        btn_trans.setCursor(Qt.PointingHandCursor)
        btn_trans.setToolTip("Update Status, Schedule Interview, or Log Follow-Up")
        btn_trans.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """)
        btn_trans.clicked.connect(lambda _, a=app: self._on_transition_clicked(a))
        act_layout.addWidget(btn_trans)

        btn_hist = QPushButton("Audit")
        btn_hist.setCursor(Qt.PointingHandCursor)
        btn_hist.setToolTip("View State Audit Trail & History")
        btn_hist.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}50;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']}20;
                border-color: {COLORS['accent']};
            }}
        """)
        btn_hist.clicked.connect(lambda _, a=app: self._on_history_clicked(a))
        act_layout.addWidget(btn_hist)

        self.table.setCellWidget(row, 6, act_widget)

    def _update_metric_val(self, widget: QWidget, val: int) -> None:
        lbl = widget.findChild(QLabel)
        if lbl:
            lbl.setText(str(val))

    def _on_transition_clicked(self, app: Application) -> None:
        dialog = StatusTransitionDialog(
            application=app,
            service=self.service,
            recruitment_service=self.recruitment_service,
            parent=self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.notification_bar.show_message("success", "Application updated successfully.")
            self.refresh()
            self.data_updated.emit("applications")
            self.data_updated.emit("interviews")
            self.data_updated.emit("followups")

    def _on_history_clicked(self, app: Application) -> None:
        dialog = ApplicationHistoryDialog(application=app, service=self.service, parent=self)
        dialog.exec()

    # ── Universal Exact Navigation Lifecycle ──────────────────────────────────
    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores a pending navigation request to be executed on view activation."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Executes navigation action (OPEN, FOCUS, or FILTER) on this view."""
        self._pending_navigation_request = None
        app_id = request.entity_id

        if request.action == NavigationAction.FILTER:
            self.apply_exact_filter(app_id)
        elif request.action == NavigationAction.OPEN:
            self.open_record(app_id)
        else:
            self.focus_record(app_id)

    def apply_exact_filter(self, app_id: int) -> None:
        """Filters the applications workspace to strictly this single application."""
        if self._exact_app_id != app_id:
            self._capture_state()
            self._exact_app_id = app_id
        self.refresh()

    def open_record(self, app_id: int) -> None:
        """Opens the status transition & detail dialog for app_id."""
        app = self.service.get_application(app_id)
        if app:
            self._on_transition_clicked(app)
        else:
            self.notification_bar.show_message("danger", f"Application #{app_id} no longer exists or was removed.")

    def focus_record(self, app_id: int) -> bool:
        """Selects app_id in the table without isolating the view."""
        for row, app in enumerate(getattr(self, "_current_apps", [])):
            if app.id == app_id:
                self.table.selectRow(row)
                return True
        return False

    def clear_exact_filter(self) -> None:
        """Exits exact-filter isolation and restores previous view filters."""
        self._exact_app_id = None
        self.exact_filter_chip.clear()
        self._restore_state()
        self.refresh()

    def _capture_state(self) -> None:
        """Captures contextual filters before applying exact-filter isolation."""
        if self._state_snapshot is None:
            self._state_snapshot = ViewStateSnapshot(
                search_query=self.txt_search.text(),
                status_filter=self.cmb_status_filter.currentText(),
                platform_filter=self.cmb_platform.currentText(),
                current_page=self._current_page,
            )

    def _restore_state(self) -> None:
        """Restores previous filter and page state when clearing exact filter."""
        if self._state_snapshot:
            snap = self._state_snapshot
            self.txt_search.blockSignals(True)
            self.txt_search.setText(snap.search_query)
            self.txt_search.blockSignals(False)
            self._current_page = snap.current_page
            self._state_snapshot = None

    def inspect_application_by_id(self, application_id: int) -> None:
        """Backward-compatible helper that delegates to open_record."""
        self.open_record(application_id)
