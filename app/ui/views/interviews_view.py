"""Interviews management view component.

Provides multi-round interview tracking, status updates, direct meeting link launching,
and modal scheduling/rescheduling dialogs.
"""

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QDateTime, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Application, Interview
from app.services.application_service import ApplicationService
from app.services.recruitment_service import (
    VALID_INTERVIEW_MODES,
    VALID_INTERVIEW_ROUNDS,
    VALID_INTERVIEW_STATUSES,
    RecruitmentService,
)
from app.services.search.search_result import NavigationAction, NavigationRequest
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge
from app.utils_time import format_local_datetime


class ScheduleInterviewDialog(QDialog):
    """Modal dialog for scheduling a new interview round."""

    def __init__(
        self,
        service: RecruitmentService,
        app_service: ApplicationService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service
        self.app_service = app_service
        self.setWindowTitle("Schedule Interview Round")
        self.setMinimumWidth(500)
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
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                min-height: 22px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down, QDateTimeEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {COLORS['border']};
            }}
            QComboBox QAbstractItemView {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                min-height: 60px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        # 1. Target Application
        self.cmb_apps = QComboBox()
        self.applications = self.app_service.list_applications(limit=100)
        for app in self.applications:
            job = app.job
            title = f"{job.company_raw if job else 'Unknown'} — {job.title if job else ''} (ID: {app.id})"
            self.cmb_apps.addItem(title, app.id)
        form.addRow("Application *", self.cmb_apps)

        # 2. Round Name & Number
        self.spn_round_num = QSpinBox()
        self.spn_round_num.setRange(1, 10)
        self.spn_round_num.setValue(1)
        form.addRow("Round Number", self.spn_round_num)

        self.cmb_round_type = QComboBox()
        self.cmb_round_type.addItems(["TECHNICAL", "HR", "CODING", "MANAGERIAL", "FINAL", "CLIENT", "OTHER"])
        form.addRow("Round Type", self.cmb_round_type)

        self.txt_round_name = QLineEdit("Technical Interview")
        form.addRow("Round Name / Topic *", self.txt_round_name)

        # 3. Schedule Time
        self.dt_scheduled = QDateTimeEdit(QDateTime.currentDateTime().addDays(1))
        self.dt_scheduled.setCalendarPopup(True)
        self.dt_scheduled.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        form.addRow("Date && Time *", self.dt_scheduled)

        # 4. Mode & Link
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["VIRTUAL", "PHONE", "IN_PERSON"])
        self.cmb_mode.currentTextChanged.connect(self._on_mode_changed)
        form.addRow("Interview Mode", self.cmb_mode)

        self.txt_link = QLineEdit()
        self.txt_link.setPlaceholderText("https://meet.google.com/xyz or Zoom link")
        form.addRow("Meeting Link", self.txt_link)

        # 5. Interviewer Contact
        self.txt_interviewer = QLineEdit()
        self.txt_interviewer.setPlaceholderText("e.g. Sarah Connor (Hiring Manager)")
        form.addRow("Interviewer Name", self.txt_interviewer)

        self.txt_interviewer_email = QLineEdit()
        self.txt_interviewer_email.setPlaceholderText("e.g. sarah@company.com")
        form.addRow("Interviewer Email", self.txt_interviewer_email)

        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("Preparation notes or agenda...")
        self.txt_notes.setMaximumHeight(70)
        form.addRow("Notes", self.txt_notes)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_mode_changed(self, mode: str) -> None:
        self.txt_link.setEnabled(mode.upper() == "VIRTUAL")

    def _validate_and_save(self) -> None:
        if self.cmb_apps.count() == 0:
            QMessageBox.warning(self, "No Applications", "Please create or track an application first.")
            return

        app_id = self.cmb_apps.currentData()
        round_name = self.txt_round_name.text().strip()
        if not round_name:
            QMessageBox.warning(self, "Validation Error", "Round name is required.")
            return

        dt = self.dt_scheduled.dateTime().toPython()
        mode = self.cmb_mode.currentText()
        link = self.txt_link.text().strip() or None

        interview, err = self.service.schedule_interview(
            application_id=app_id,
            round_name=round_name,
            scheduled_at=dt,
            round_number=self.spn_round_num.value(),
            round_type=self.cmb_round_type.currentText(),
            interviewer_name=self.txt_interviewer.text().strip() or None,
            interviewer_email=self.txt_interviewer_email.text().strip() or None,
            mode=mode,
            meeting_link=link,
            notes=self.txt_notes.toPlainText().strip() or None,
        )

        if interview:
            self.accept()
        else:
            QMessageBox.warning(self, "Scheduling Error", f"Failed: {err}")


class InterviewFeedbackDialog(QDialog):
    """Modern modal for updating interview status and recording feedback."""

    def __init__(
        self,
        interview: Interview,
        service: RecruitmentService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.interview = interview
        self.service = service

        app = interview.application
        job = app.job if app else None
        company = job.company_raw if job else "Company"
        job_title = job.title if job else "Interview Round"

        self.setWindowTitle(f"Interview Feedback — {company}")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: 500;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 24px;
                border-left: 1px solid {COLORS['border']};
            }}
            QComboBox QAbstractItemView {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                min-height: 60px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        # 1. Header Card with Round & Company Info
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

        top_row = QHBoxLayout()
        lbl_meta = QLabel(f"🏢  {company}   •   🗓️  Round #{interview.round_number}")
        lbl_meta.setStyleSheet("color: #FF7A3D; font-size: 12px; font-weight: 700; background: transparent; border: none;")
        top_row.addWidget(lbl_meta)
        top_row.addStretch()

        badge = StatusBadge(interview.status)
        top_row.addWidget(badge)
        hdr_layout.addLayout(top_row)

        round_type_str = getattr(interview, "round_type", None) or (f"{interview.mode.title()} Round" if interview.mode else "Round")
        lbl_round_title = QLabel(f"{interview.round_name} ({round_type_str})")
        lbl_round_title.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        hdr_layout.addWidget(lbl_round_title)

        interviewer_info = f"Interviewer: {interview.interviewer}" if interview.interviewer else "Interviewer: Not specified"
        time_info = format_local_datetime(interview.scheduled_at, "%b %d, %Y %I:%M %p") if interview.scheduled_at else ""
        sub_text = f"{interviewer_info}   •   {time_info}" if time_info else interviewer_info
        lbl_sub = QLabel(sub_text)
        lbl_sub.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent; border: none;")
        hdr_layout.addWidget(lbl_sub)

        layout.addWidget(hdr_card)

        # 2. Form Inputs
        form_card = QFrame()
        form_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        form_layout = QFormLayout(form_card)
        form_layout.setSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        self.cmb_status = QComboBox()
        self.cmb_status.addItems(["COMPLETED", "SCHEDULED", "CANCELLED", "NO_SHOW"])
        idx = self.cmb_status.findText(interview.status)
        if idx >= 0:
            self.cmb_status.setCurrentIndex(idx)
        form_layout.addRow("Round Status *", self.cmb_status)

        self.txt_feedback = QTextEdit()
        self.txt_feedback.setPlaceholderText("Detailed round learnings, questions asked, technical topics covered, self-evaluation, next steps...")
        self.txt_feedback.setMinimumHeight(110)
        self.txt_feedback.setMaximumHeight(160)
        if interview.feedback:
            self.txt_feedback.setPlainText(interview.feedback)
        form_layout.addRow("Feedback / Notes", self.txt_feedback)

        layout.addWidget(form_card)

        lbl_hint = QLabel("💡 Recording feedback immediately keeps your recruitment log up to date and aids prep for subsequent rounds.")
        lbl_hint.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500;")
        lbl_hint.setWordWrap(True)
        layout.addWidget(lbl_hint)

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
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['border_light']};
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save Feedback")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save.clicked.connect(self._save_feedback)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _save_feedback(self) -> None:
        status = self.cmb_status.currentText()
        feedback = self.txt_feedback.toPlainText().strip() or None

        updated, err = self.service.update_interview_status(
            interview_id=self.interview.id,
            status=status,
            feedback=feedback,
        )

        if updated:
            self.accept()
        else:
            QMessageBox.warning(self, "Update Error", f"Failed: {err}")


class InterviewsView(QWidget):
    """Interview pipeline and scheduling view."""

    data_updated = Signal(str)

    def __init__(
        self,
        service: Optional[RecruitmentService] = None,
        app_service: Optional[ApplicationService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or RecruitmentService()
        self.app_service = app_service or ApplicationService()
        self._current_interviews: List[Interview] = []
        self._pending_navigation_request: Optional[NavigationRequest] = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header
        self.header = PageHeader(
            title="Interview Stages",
            subtitle="Track screening calls, technical evaluations, managerial rounds, meeting links, and candidate feedback.",
        )

        self.btn_schedule = QPushButton("+ Schedule Interview")
        self.btn_schedule.setMinimumHeight(34)
        self.btn_schedule.setMinimumWidth(160)
        self.btn_schedule.setCursor(Qt.PointingHandCursor)
        self.btn_schedule.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_schedule.clicked.connect(self._on_schedule_clicked)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.setMinimumWidth(80)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)

        self.header.add_action_widget(self.btn_schedule)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # 2. Notification Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Metric Cards Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)

        self.lbl_card_scheduled = self._create_metric_widget("Scheduled Rounds", "0", "#38bdf8", target_status="SCHEDULED")
        self.lbl_card_completed = self._create_metric_widget("Completed Rounds", "0", "#34d399", target_status="COMPLETED")
        self.lbl_card_cancelled = self._create_metric_widget("Cancelled / Rescheduled", "0", "#f87171", target_status="CANCELLED")

        metrics_layout.addWidget(self.lbl_card_scheduled)
        metrics_layout.addWidget(self.lbl_card_completed)
        metrics_layout.addWidget(self.lbl_card_cancelled)
        main_layout.addLayout(metrics_layout)

        # 4. Filter Bar
        filter_card = QFrame()
        filter_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(12, 8, 12, 8)
        filter_layout.setSpacing(12)

        filter_layout.addWidget(QLabel("Status Filter:"))
        self.cmb_filter_status = QComboBox()
        self.cmb_filter_status.addItems(["All Statuses", "SCHEDULED", "COMPLETED", "CANCELLED", "NO_SHOW"])
        self.cmb_filter_status.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.cmb_filter_status)

        self.lbl_stats = QLabel("0 rounds")
        self.lbl_stats.setStyleSheet(f"color: {COLORS['text_muted']}; font-weight: 600;")
        filter_layout.addWidget(self.lbl_stats)
        filter_layout.addStretch()

        main_layout.addWidget(filter_card)

        # 5. Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Company & Role",
            "Round",
            "Scheduled Time",
            "Interviewer",
            "Mode",
            "Status",
            "Actions",
        ])
        self.table.horizontalHeader().setMinimumSectionSize(40)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 150)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 155)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 110)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 75)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 135)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 175)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setAutoScroll(False)
        self.table.setWordWrap(False)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                gridline-color: transparent;
                color: {COLORS['text']};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
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
                padding: 8px 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        main_layout.addWidget(self.table, 1)

    def _create_metric_widget(
        self,
        title: str,
        value: str,
        color_hex: str,
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

        if target_status:
            box.mousePressEvent = lambda e, s=target_status: self._on_metric_card_clicked(s)
        return box

    def _on_metric_card_clicked(self, target_status: str) -> None:
        """Toggles status filter when an interview metric card is clicked."""
        curr = self.cmb_filter_status.currentText().strip().upper()
        if curr == target_status:
            self.cmb_filter_status.setCurrentIndex(0)  # Toggle back to All Statuses
        else:
            idx = self.cmb_filter_status.findText(target_status)
            if idx >= 0:
                self.cmb_filter_status.setCurrentIndex(idx)

    def _update_metric(self, widget: QWidget, val: int) -> None:
        lbl = widget.findChild(QLabel)
        if lbl:
            lbl.setText(str(val))

    def refresh(self) -> None:
        """Reloads interviews matching filter and updates metrics."""
        all_ivs = self.service.list_interviews(limit=200)
        c_sched = sum(1 for iv in all_ivs if iv.status == "SCHEDULED")
        c_comp = sum(1 for iv in all_ivs if iv.status == "COMPLETED")
        c_canc = sum(1 for iv in all_ivs if iv.status in ["CANCELLED", "NO_SHOW"])

        self._update_metric(self.lbl_card_scheduled, c_sched)
        self._update_metric(self.lbl_card_completed, c_comp)
        self._update_metric(self.lbl_card_cancelled, c_canc)

        st = self.cmb_filter_status.currentText().strip().upper()
        status = None if st in ["ALL STATUSES", "ALL", ""] else st

        self._current_interviews = self.service.list_interviews(status=status, limit=100)
        self.lbl_stats.setText(f"{len(self._current_interviews)} rounds")

        self.table.clearContents()
        self.table.setRowCount(len(self._current_interviews))
        for row, item in enumerate(self._current_interviews):
            app = item.application
            job = app.job if app else None

            # 0. Company & Role
            comp_role = f"{job.company_raw if job else 'Unknown'} — {job.title if job else 'Unknown'}"
            t_item = QTableWidgetItem(comp_role)
            t_item.setToolTip(comp_role)
            self.table.setItem(row, 0, t_item)

            # 1. Round
            r_item = QTableWidgetItem(f"#{item.round_number} {item.round_name}")
            r_item.setTextAlignment(Qt.AlignCenter)
            r_item.setToolTip(f"Round #{item.round_number}: {item.round_name}")
            self.table.setItem(row, 1, r_item)

            # 2. Time
            time_str = format_local_datetime(item.scheduled_at, "%Y-%m-%d %I:%M %p") if item.scheduled_at else "-"
            d_item = QTableWidgetItem(time_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            d_item.setToolTip(time_str)
            self.table.setItem(row, 2, d_item)

            # 3. Interviewer
            i_item = QTableWidgetItem(item.interviewer or "Not Specified")
            self.table.setItem(row, 3, i_item)

            # 4. Mode
            m_item = QTableWidgetItem(item.mode.title())
            m_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, m_item)

            # 5. Status Badge
            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent; border: none;")
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignCenter)
            status_layout.addWidget(StatusBadge(item.status))
            self.table.setCellWidget(row, 5, status_widget)

            # 6. Actions (Join Link + Feedback)
            act_widget = QWidget()
            act_widget.setStyleSheet("background: transparent; border: none;")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(8)
            act_layout.setAlignment(Qt.AlignCenter)

            if item.meeting_link:
                btn_link = QPushButton("Join Link")
                btn_link.setFixedSize(76, 26)
                btn_link.setCursor(Qt.PointingHandCursor)
                btn_link.setToolTip(f"Open meeting link: {item.meeting_link}")
                btn_link.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #1C2128;
                        color: {COLORS['accent']};
                        border: 1px solid {COLORS['accent']}70;
                        font-size: 11px;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 0px 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['accent']}20;
                        border-color: {COLORS['accent']};
                        color: #FFFFFF;
                    }}
                """)
                btn_link.clicked.connect(lambda _, url=item.meeting_link: QDesktopServices.openUrl(QUrl(url)))
                act_layout.addWidget(btn_link)

                btn_update = QPushButton("Feedback")
                btn_update.setFixedSize(76, 26)
                btn_update.setCursor(Qt.PointingHandCursor)
                btn_update.setToolTip("Update round status and interview feedback")
                btn_update.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['surface_alt']};
                        color: {COLORS['text']};
                        border: 1px solid {COLORS['border']};
                        font-size: 11px;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 0px 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['surface_hover']};
                        border-color: {COLORS['border_light']};
                        color: #FFFFFF;
                    }}
                """)
                btn_update.clicked.connect(lambda _, iv=item: self._on_update_clicked(iv))
                act_layout.addWidget(btn_update)
            else:
                btn_update = QPushButton("Update / Feedback")
                btn_update.setFixedSize(130, 26)
                btn_update.setCursor(Qt.PointingHandCursor)
                btn_update.setToolTip("Update round status and interview feedback")
                btn_update.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['surface_alt']};
                        color: {COLORS['text']};
                        border: 1px solid {COLORS['border']};
                        font-size: 11px;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 0px 8px;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS['surface_hover']};
                        border-color: {COLORS['border_light']};
                        color: #FFFFFF;
                    }}
                """)
                btn_update.clicked.connect(lambda _, iv=item: self._on_update_clicked(iv))
                act_layout.addWidget(btn_update)

            self.table.setCellWidget(row, 6, act_widget)

        self.table.horizontalScrollBar().setValue(0)

        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)

    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores request to be applied safely during or after refresh."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Applies navigation request without destroying table state."""
        if request.entity_type != "interview":
            return
        if request.action == NavigationAction.OPEN:
            self.open_record(request.entity_id)
        else:
            self.focus_record(request.entity_id)

    def focus_record(self, interview_id: int) -> bool:
        """Finds row for interview_id, selects and scrolls to it without filtering."""
        for row, iv in enumerate(self._current_interviews):
            if iv.id == interview_id:
                self.table.selectRow(row)
                item = self.table.item(row, 0)
                if item:
                    self.table.scrollToItem(item)
                return True
        return False

    def open_record(self, interview_id: int) -> bool:
        """Opens feedback/details dialog for interview_id."""
        self.focus_record(interview_id)
        for iv in self._current_interviews:
            if iv.id == interview_id:
                self._on_update_clicked(iv)
                return True
        try:
            all_ivs = self.service.list_interviews(limit=200)
            target = next((i for i in all_ivs if i.id == interview_id), None)
            if target:
                self._on_update_clicked(target)
                return True
        except Exception:
            pass
        return False

    def _on_schedule_clicked(self) -> None:
        dialog = ScheduleInterviewDialog(service=self.service, app_service=self.app_service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.notification_bar.show_message("success", "Interview round scheduled successfully.")
            self.refresh()
            self.data_updated.emit("interviews")

    def _on_update_clicked(self, interview: Interview) -> None:
        dialog = InterviewFeedbackDialog(interview=interview, service=self.service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.notification_bar.show_message("success", "Interview feedback and status updated.")
            self.refresh()
            self.data_updated.emit("interviews")

    def inspect_interview_by_id(self, interview_id: int) -> None:
        """Finds and opens feedback/details dialog for a specific interview by ID."""
        for iv in getattr(self, "_current_interviews", []):
            if iv.id == interview_id:
                self._on_update_clicked(iv)
                return
        try:
            all_ivs = self.service.list_interviews(limit=200)
            target = next((i for i in all_ivs if i.id == interview_id), None)
            if target:
                self._on_update_clicked(target)
        except Exception:
            pass
