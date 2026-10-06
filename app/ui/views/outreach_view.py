"""Outreach Center view component for Desktop UI (PySide6 / Qt6).

Adheres strictly to DesignUI.md:
- Obsidian Canvas (#0F1117), Elevated Surfaces (#161B22, #1C2128), Border (#262C36).
- Safety Orange Accent (#FF5F15).
- KPI Metric Cards (ModernMetricCard).
- Split-View Recruiter Workspace (QSplitter with list pane and detail pane).
- Embedded Recruiter Email Composer Dialog with AI Pitch generation.
- Real-time cadence tracking and AI recruiter intent categorization.
"""

from datetime import datetime, timezone
import json
import logging
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDateTime, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.base import utc_now
from app.db.models import Application, Communication, FollowUp, User
from app.db.session import SessionLocal, get_db_session
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.dto.outreach_enums import (
    CadenceState,
    ConversationOpState,
    FollowUpStatus,
    InboundClassification,
    MessageStatus,
    NextActionOwner,
    NextActionType,
    PriorityLevel,
    WorkQueueSection,
)
from app.services.dto.outreach_viewmodels import (
    BulkTargetPreviewItemDTO,
    ConversationDetailViewModel,
    FollowUpStepViewModel,
    NextActionRecommendation,
    OutreachCaseOperationViewModel,
    TimelineMessageViewModel,
    WorkQueueGroupViewModel,
)
from app.services.followup_scheduler import FollowUpScheduler
from app.services.inbound_sync_service import InboundSyncService
from app.services.outreach_ai_service import OutreachAIService
from app.services.outreach_service import OutreachService
from app.services.resume_service import ResumeService
from app.ui.theme import COLORS
from app.ui.views.bulk_outreach_dialog import BulkOutreachDialog
from app.ui.widgets.metric_card import ModernMetricCard
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge

logger = logging.getLogger("JobPilot.OutreachView")


# -----------------------------------------------------------------------------
# Background Worker for AI Pitch Generation
# -----------------------------------------------------------------------------
class AIPitchWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        company_name: str,
        job_title: str,
        recruiter_name: Optional[str] = None,
        resume_id: Optional[int] = None,
    ):
        super().__init__()
        self.company_name = company_name
        self.job_title = job_title
        self.recruiter_name = recruiter_name
        self.resume_id = resume_id

    def run(self):
        try:
            ai_svc = OutreachAIService()
            res = ai_svc.generate_pitch(
                company_name=self.company_name,
                job_title=self.job_title,
                recruiter_name=self.recruiter_name,
                resume_id=self.resume_id,
            )
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class OutreachSendWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, outreach_service: OutreachService, dto: OutreachCreateDTO):
        super().__init__()
        self.outreach_service = outreach_service
        self.dto = dto

    def run(self):
        try:
            res = self.outreach_service.send_outreach(self.dto)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class MailboxSyncWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, inbound_service: InboundSyncService):
        super().__init__()
        self.inbound_service = inbound_service

    def run(self):
        try:
            res = self.inbound_service.sync_mailbox()
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


class ReplySendWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, outreach_service: OutreachService, app_id: int, body_text: str, subject: Optional[str] = None):
        super().__init__()
        self.outreach_service = outreach_service
        self.app_id = app_id
        self.body_text = body_text
        self.subject = subject

    def run(self):
        try:
            res = self.outreach_service.send_reply(self.app_id, self.body_text, self.subject)
            self.finished.emit(res)
        except Exception as e:
            self.error.emit(str(e))


# -----------------------------------------------------------------------------
# Modal Dialog: Direct Outreach Composer
# -----------------------------------------------------------------------------
class OutreachComposerDialog(QDialog):
    """Modern modal for drafting and dispatching direct recruiter applications."""

    outreach_sent = Signal()

    def __init__(
        self,
        outreach_service: OutreachService,
        resume_service: ResumeService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.outreach_service = outreach_service
        self.resume_service = resume_service
        self._ai_worker: Optional[AIPitchWorker] = None
        self._send_worker: Optional[OutreachSendWorker] = None

        self.setWindowTitle("Direct Recruiter Outreach")
        self.setFixedSize(760, 800)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: 600;
                font-size: 12px;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {COLORS['accent']};
            }}
            QCheckBox {{
                color: {COLORS['text']};
                font-size: 12px;
                spacing: 6px;
            }}
        """)

        self._setup_ui()
        self._load_templates_and_resumes()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 18, 24, 18)
        root_layout.setSpacing(10)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        lbl_title = QLabel("Direct Recruiter Outreach")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #F0F6FC;")
        lbl_sub = QLabel("Craft a targeted application email with automated follow-up cadences.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; font-weight: 400;")
        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        root_layout.addLayout(title_box)

        # Grid 1: Company & Job Title
        grid1 = QGridLayout()
        grid1.setSpacing(10)
        grid1.addWidget(QLabel("Target Company *"), 0, 0)
        grid1.addWidget(QLabel("Position Title *"), 0, 1)

        self.txt_company = QLineEdit()
        self.txt_company.setPlaceholderText("e.g. Acme Technologies")
        grid1.addWidget(self.txt_company, 1, 0)

        self.txt_job_title = QLineEdit()
        self.txt_job_title.setPlaceholderText("e.g. Senior RPA Developer")
        grid1.addWidget(self.txt_job_title, 1, 1)
        root_layout.addLayout(grid1)

        # Grid 2: Recruiter Name & Email
        grid2 = QGridLayout()
        grid2.setSpacing(10)
        grid2.addWidget(QLabel("Recruiter / Contact Name"), 0, 0)
        grid2.addWidget(QLabel("Recruiter Email *"), 0, 1)

        self.txt_recruiter_name = QLineEdit()
        self.txt_recruiter_name.setPlaceholderText("e.g. Sarah Jenkins")
        grid2.addWidget(self.txt_recruiter_name, 1, 0)

        self.txt_recruiter_email = QLineEdit()
        self.txt_recruiter_email.setPlaceholderText("e.g. sjenkins@acme.com")
        grid2.addWidget(self.txt_recruiter_email, 1, 1)
        root_layout.addLayout(grid2)

        # Resumes & Templates
        grid3 = QGridLayout()
        grid3.setSpacing(10)
        grid3.addWidget(QLabel("Attached Resume"), 0, 0)
        grid3.addWidget(QLabel("Template Preset"), 0, 1)

        self.cmb_resume = QComboBox()
        self.cmb_resume.addItem("No Resume Attached", None)
        grid3.addWidget(self.cmb_resume, 1, 0)

        self.cmb_template = QComboBox()
        self.cmb_template.addItem("Custom Pitch (No Template)", None)
        self.cmb_template.currentIndexChanged.connect(self._on_template_selected)
        grid3.addWidget(self.cmb_template, 1, 1)
        root_layout.addLayout(grid3)

        # AI Pitch Trigger Button
        ai_box = QHBoxLayout()
        ai_box.addStretch()
        self.btn_ai_pitch = QPushButton("✨ Generate Tailored Pitch (AI)")
        self.btn_ai_pitch.setCursor(Qt.PointingHandCursor)
        self.btn_ai_pitch.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']}60;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
            }}
        """)
        self.btn_ai_pitch.clicked.connect(self._on_generate_ai_pitch)
        ai_box.addWidget(self.btn_ai_pitch)
        root_layout.addLayout(ai_box)

        # Subject Line
        root_layout.addWidget(QLabel("Subject Line *"))
        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText("e.g. Application: Senior RPA Developer - Candidate")
        root_layout.addWidget(self.txt_subject)

        # Body Text
        root_layout.addWidget(QLabel("Email Body *"))
        self.txt_body = QTextEdit()
        self.txt_body.setPlaceholderText("Compose your personalized message to the hiring manager...")
        self.txt_body.setFixedHeight(125)
        root_layout.addWidget(self.txt_body)

        # Automated Follow-up Cadence Selection
        cadence_frame = QFrame()
        cadence_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 10px;
            }}
        """)
        cadence_layout = QVBoxLayout(cadence_frame)
        cadence_layout.setContentsMargins(10, 8, 10, 8)
        cadence_layout.setSpacing(6)

        lbl_cadence = QLabel("AUTOMATED FOLLOW-UP CADENCE:")
        lbl_cadence.setStyleSheet("font-size: 11px; text-transform: uppercase; color: #8B949E; font-weight: 700;")
        cadence_layout.addWidget(lbl_cadence)

        cadence_grid = QGridLayout()
        cadence_grid.setSpacing(8)
        self.chk_step1 = QCheckBox("Step 1: Polite Check-in (+4 days)")
        self.chk_step1.setChecked(True)
        self.chk_step2 = QCheckBox("Step 2: Value-Add (+10 days)")
        self.chk_step2.setChecked(True)
        self.chk_step3 = QCheckBox("Step 3: Closeout (+17 days)")
        self.chk_step3.setChecked(True)

        cadence_grid.addWidget(self.chk_step1, 0, 0)
        cadence_grid.addWidget(self.chk_step2, 0, 1)
        cadence_grid.addWidget(self.chk_step3, 1, 0, 1, 2)
        cadence_layout.addLayout(cadence_grid)
        root_layout.addWidget(cadence_frame)

        # Action Buttons Footer
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)
        footer_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        self.btn_send = QPushButton("🚀 Send Outreach Now")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.btn_send.clicked.connect(self._on_submit_outreach)
        footer_layout.addWidget(self.btn_send)

        root_layout.addLayout(footer_layout)

    def _load_templates_and_resumes(self):
        # Load candidate resumes
        try:
            with get_db_session(SessionLocal) as s:
                from app.repositories.user_repository import UserRepository
                u = UserRepository(s).get_primary_user()
                uid = u.id if u else 1
            resumes = self.resume_service.list_resumes(user_id=uid)
            default_idx = -1
            for r in resumes:
                title = f"{r.name} ({r.role_target or 'General'})"
                if r.is_default:
                    title += " [Default]"
                self.cmb_resume.addItem(title, r.id)
                if r.is_default:
                    default_idx = self.cmb_resume.count() - 1
            if default_idx >= 0:
                self.cmb_resume.setCurrentIndex(default_idx)
        except Exception as e:
            logger.warning("Could not load resumes: %s", e)

        # Load templates
        try:
            with get_db_session(SessionLocal) as s:
                repo = EmailTemplateRepository(s)
                repo.seed_defaults_if_empty()
                templates = repo.list_all(include_inactive=False)
                for t in templates:
                    self.cmb_template.addItem(t.name, t)
        except Exception as e:
            logger.warning("Could not load email templates: %s", e)

    def _on_template_selected(self, index: int):
        tmpl = self.cmb_template.currentData()
        if not tmpl:
            return

        company = self.txt_company.text().strip() or "Acme Corp"
        job_title = self.txt_job_title.text().strip() or "Position"
        recruiter = self.txt_recruiter_name.text().strip() or "Hiring Team"

        with get_db_session(SessionLocal) as s:
            from app.repositories.user_repository import UserRepository
            repo = UserRepository(s)
            u = repo.get_primary_user()
            cand_name = u.name if u else "Candidate"
            cand_email = u.email if u else "candidate@example.com"
            pro = repo.get_professional_profile(u.id) if u else None
            skills_val = pro.skills if pro and pro.skills else ["RPA Development", "Python", "AI Automation", "Process Automation"]
            if isinstance(skills_val, list):
                cand_skills = ", ".join(skills_val[:5])
            else:
                cand_skills = str(skills_val)
            yoe = f"{pro.years_of_experience:.0f}" if pro and pro.years_of_experience else "2"

        ctx = {
            "candidate_name": cand_name,
            "candidate_email": cand_email,
            "recruiter_name": recruiter,
            "company_name": company,
            "job_title": job_title,
            "skills": cand_skills,
            "years_of_experience": yoe,
            "platform": "JobPilot Outreach",
        }

        from app.services.template_renderer import TemplateRenderer
        subj, _ = TemplateRenderer.render(tmpl.subject_template, ctx, strict=False)
        body, _ = TemplateRenderer.render(tmpl.body_template, ctx, strict=False)

        self.txt_subject.setText(subj)
        self.txt_body.setPlainText(body)

    def _on_generate_ai_pitch(self):
        comp = self.txt_company.text().strip()
        title = self.txt_job_title.text().strip()
        if not comp or not title:
            QMessageBox.warning(self, "Missing Details", "Please enter Target Company and Position Title first.")
            return

        self.btn_ai_pitch.setEnabled(False)
        self.btn_ai_pitch.setText("⏳ Generating Tailored Pitch...")

        recruiter = self.txt_recruiter_name.text().strip() or None
        resume_id = self.cmb_resume.currentData()

        self._ai_worker = AIPitchWorker(comp, title, recruiter, resume_id)
        self._ai_worker.finished.connect(self._on_ai_pitch_ready)
        self._ai_worker.error.connect(self._on_ai_pitch_failed)
        self._ai_worker.start()

    def _on_ai_pitch_ready(self, res: dict):
        self.btn_ai_pitch.setEnabled(True)
        self.btn_ai_pitch.setText("✨ Generate Tailored Pitch (AI)")
        if res.get("subject"):
            self.txt_subject.setText(res["subject"])
        if res.get("body_text"):
            self.txt_body.setPlainText(res["body_text"])

    def _on_ai_pitch_failed(self, err_msg: str):
        self.btn_ai_pitch.setEnabled(True)
        self.btn_ai_pitch.setText("✨ Generate Tailored Pitch (AI)")
        QMessageBox.warning(self, "AI Generation Notice", f"AI pitch generation fallback triggered: {err_msg}")

    def _on_submit_outreach(self):
        comp = self.txt_company.text().strip()
        title = self.txt_job_title.text().strip()
        recruiter_email = self.txt_recruiter_email.text().strip()
        subj = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()

        # Validation 1: Required fields
        if not comp or not title or not recruiter_email or not subj or not body:
            QMessageBox.warning(self, "Required Fields Missing", "Please fill in Company, Job Title, Recruiter Email, Subject, and Body before sending.")
            return

        # Validation 2: Email format
        if "@" not in recruiter_email or "." not in recruiter_email or len(recruiter_email) < 5:
            QMessageBox.warning(self, "Invalid Email Address", f"'{recruiter_email}' does not appear to be a valid email address.\nPlease enter a valid recipient email (e.g. recruiter@company.com).")
            return

        # Validation 3: Pre-flight check for configured email credentials
        from app.services.secrets_service import SecretsService
        creds = SecretsService().get_email_credentials()
        if not creds.get("is_configured") or not creds.get("password"):
            reply = QMessageBox.warning(
                self,
                "Email Account Not Configured",
                "Your outgoing email credentials are not fully configured yet.\n\n"
                "To send real emails, you must configure your Sender Email and App Password in:\n"
                "⚙️ Settings → Credentials & Security\n\n"
                "Would you like to attempt dispatching anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        cadence_days = []
        if self.chk_step1.isChecked():
            cadence_days.append(4)
        if self.chk_step2.isChecked():
            cadence_days.append(10)
        if self.chk_step3.isChecked():
            cadence_days.append(17)

        dto = OutreachCreateDTO(
            manual_company_name=comp,
            manual_job_title=title,
            contact_name=self.txt_recruiter_name.text().strip() or None,
            contact_email=recruiter_email,
            resume_id=self.cmb_resume.currentData(),
            subject=subj,
            body_text=body,
            followup_cadence_days=cadence_days,
            override_duplicate=True,
        )

        self.btn_send.setEnabled(False)
        self.btn_send.setText("⏳ Sending Outreach...")

        self._send_worker = OutreachSendWorker(self.outreach_service, dto)
        self._send_worker.finished.connect(lambda res: self._on_send_outreach_finished(res, recruiter_email))
        self._send_worker.error.connect(self._on_send_outreach_failed)
        self._send_worker.start()

    def _format_dispatch_error(self, err_str: str) -> str:
        err_lower = err_str.lower()
        if "530" in err_str or "authentication required" in err_lower or "smtpsenderrefused" in err_lower:
            return (
                "⚠️ SMTP Authentication Required (530)\n\n"
                "The mail server rejected the sender credentials or envelope address.\n\n"
                "How to resolve:\n"
                "1. Open Settings → Credentials & Security\n"
                "2. Verify 'Sender Email' matches your actual Gmail / Outlook account\n"
                "3. Verify you entered a 16-character App Password (not your personal login password)\n"
                "4. Click '⚡ Test Email Connection' to confirm authentication passes before trying again."
            )
        if "535" in err_str or "5.7.3" in err_str or "authentication unsuccessful" in err_lower:
            return (
                "⚠️ Authentication Failed (535)\n\n"
                "Your mail provider rejected the username or App Password.\n\n"
                "How to resolve:\n"
                "• For Gmail: Generate an App Password at https://myaccount.google.com/apppasswords\n"
                "• For Outlook: Enable 2-Step Verification and generate an App Password in Microsoft Security\n"
                "• Paste the 16-character App Password in Settings → Credentials & Security."
            )
        if "timeout" in err_lower or "timed out" in err_lower:
            return (
                "⚠️ Connection Timed Out\n\n"
                "Could not establish a connection to the mail server in time.\n\n"
                "Please verify your internet connection and check the SMTP Host and Port in Settings."
            )
        if "connection refused" in err_lower:
            return (
                "⚠️ Connection Refused\n\n"
                "The mail server actively refused the connection on the configured port. "
                "Please verify your SMTP host and port in Settings."
            )
        return f"Unable to dispatch email:\n\n{err_str}"

    def _on_send_outreach_finished(self, res: dict, recruiter_email: str):
        if res.get("success"):
            QMessageBox.information(self, "Outreach Dispatched", f"🎉 Email successfully sent to {recruiter_email}!")
            self.outreach_sent.emit()
            self.accept()
        else:
            raw_err = res.get("error", "Unknown error")
            formatted = self._format_dispatch_error(raw_err)
            QMessageBox.critical(self, "Dispatch Error", formatted)
            self.btn_send.setEnabled(True)
            self.btn_send.setText("🚀 Send Outreach Now")

    def _on_send_outreach_failed(self, err_msg: str):
        formatted = self._format_dispatch_error(err_msg)
        QMessageBox.critical(self, "Dispatch Error", formatted)
        self.btn_send.setEnabled(True)
        self.btn_send.setText("🚀 Send Outreach Now")


# -----------------------------------------------------------------------------
# Work Queue Operational Case Card Widget
# -----------------------------------------------------------------------------
class WorkQueueCaseCardWidget(QFrame):
    """High-density, actionable case card representing an outreach operation in the Work Queue."""

    clicked = Signal(int)
    selection_toggled = Signal(int, bool)
    priority_toggled = Signal(int)
    cta_triggered = Signal(int, str)

    def __init__(
        self,
        case: Any,
        is_selected: bool = False,
        is_checked: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.case = case
        self.is_selected = is_selected
        self.is_checked = is_checked

        # Adapt model vs legacy dictionary
        if isinstance(case, OutreachCaseOperationViewModel):
            self.app_id = case.application_id
            self.company_name = case.company_name or "Unknown Company"
            self.job_title = case.job_title or "Position"
            self.contact_name = case.contact_name or "Hiring Team"
            self.contact_email = case.contact_email or ""
            self.conv_state = case.conversation_state.value
            self.is_prio = bool(case.is_priority)
            self.is_unread = bool(case.unread_attention)
            self.headline = case.next_action_headline
            self.rationale = case.next_action_rationale
            self.cta_label = case.next_action_cta
            self.cta_type = case.next_action_type.value
            self.cadence_state = case.cadence_state.value
            self.cadence_step = case.cadence_active_step
            self.cadence_total = case.cadence_total_steps
            self.work_section = case.work_queue_section
        else:
            self.app_id = case.get("application_id", 0)
            self.company_name = case.get("company_name", "Unknown Company")
            self.job_title = case.get("job_title", "Position")
            self.contact_name = case.get("contact_name") or case.get("contact_email") or "Hiring Team"
            self.contact_email = case.get("contact_email", "")
            self.conv_state = case.get("conversation_state", "WAITING")
            self.is_prio = bool(case.get("is_priority", False))
            self.is_unread = bool(case.get("is_unread", False))
            self.headline = case.get("next_action_headline", "Review Conversation")
            self.rationale = case.get("next_action_rationale", "")
            self.cta_label = case.get("next_action_cta", "View")
            self.cta_type = "VIEW"
            self.cadence_state = "IDLE"
            self.cadence_step = 0
            self.cadence_total = 3
            self.work_section = WorkQueueSection.WAITING

        self.setCursor(Qt.PointingHandCursor)

        border_col = COLORS["primary"] if is_selected else (COLORS["accent"] if self.is_prio else COLORS["border"])
        bg_col = COLORS["surface_hover"] if is_selected else COLORS["surface"]

        self.setStyleSheet(f"""
            WorkQueueCaseCardWidget {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 8px;
            }}
            WorkQueueCaseCardWidget:hover {{
                border-color: {COLORS['primary']};
                background-color: {COLORS['surface_hover']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(5)

        # 1. Top Row: Checkbox, Priority Star, Unread indicator, Company, State Badge
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self.chk_select = QCheckBox()
        self.chk_select.setChecked(self.is_checked)
        self.chk_select.toggled.connect(lambda checked: self.selection_toggled.emit(self.app_id, checked))
        top_row.addWidget(self.chk_select)

        self.btn_star = QPushButton("⭐" if self.is_prio else "☆")
        self.btn_star.setCursor(Qt.PointingHandCursor)
        self.btn_star.setFixedSize(22, 22)
        star_color = "#FFD700" if self.is_prio else COLORS["text_dark"]
        self.btn_star.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 13px;
                color: {star_color};
                padding: 0px;
            }}
            QPushButton:hover {{
                color: #FFE066;
            }}
        """)
        self.btn_star.clicked.connect(lambda: self.priority_toggled.emit(self.app_id))
        top_row.addWidget(self.btn_star)

        if self.is_unread:
            lbl_unread = QLabel("●")
            lbl_unread.setStyleSheet("color: #388BFD; font-size: 11px;")
            top_row.addWidget(lbl_unread)

        lbl_comp = QLabel(self.company_name)
        lbl_comp.setStyleSheet("font-size: 13px; font-weight: 700; color: #F0F6FC;")
        top_row.addWidget(lbl_comp)
        top_row.addStretch()

        badge = StatusBadge(self.conv_state)
        top_row.addWidget(badge)
        layout.addLayout(top_row)

        # 2. Subtitle Row: Job Title • Recruiter • Cadence Status
        sub_row = QHBoxLayout()
        sub_row.setSpacing(6)
        lbl_title = QLabel(self.job_title)
        lbl_title.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; font-weight: 600;")
        sub_row.addWidget(lbl_title)

        lbl_dot = QLabel("•")
        lbl_dot.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 10px;")
        sub_row.addWidget(lbl_dot)

        rec_text = self.contact_name if not self.contact_email else f"{self.contact_name} ({self.contact_email})"
        lbl_recruiter = QLabel(rec_text)
        lbl_recruiter.setStyleSheet(f"font-size: 11px; color: {COLORS['text_dark']};")
        sub_row.addWidget(lbl_recruiter)
        sub_row.addStretch()

        # Cadence Step pill
        if self.cadence_state in ("ACTIVE", "PAUSED", "COMPLETED"):
            cad_label = f"Step {self.cadence_step}/{self.cadence_total}" if self.cadence_state != "PAUSED" else "Paused"
            cad_pill = QLabel(cad_label)
            cad_pill_color = "#388BFD" if self.cadence_state == "ACTIVE" else ("#D29922" if self.cadence_state == "PAUSED" else "#2EA043")
            cad_pill.setStyleSheet(f"""
                background-color: {COLORS['surface_alt']};
                color: {cad_pill_color};
                border: 1px solid {cad_pill_color}60;
                border-radius: 4px;
                padding: 1px 6px;
                font-size: 10px;
                font-weight: 700;
            """)
            sub_row.addWidget(cad_pill)

        layout.addLayout(sub_row)

        # 3. Next Action Banner (High Emphasis on actionable items)
        if self.headline:
            act_banner = QFrame()
            is_today = (self.work_section == WorkQueueSection.TODAY)
            border_banner = f"1px solid {COLORS['accent']}80" if is_today else f"1px solid {COLORS['border_light']}"
            bg_banner = f"rgba(255, 95, 21, 0.08)" if is_today else COLORS["surface_alt"]
            act_banner.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_banner};
                    border: {border_banner};
                    border-radius: 6px;
                    padding: 4px 8px;
                }}
            """)
            b_layout = QHBoxLayout(act_banner)
            b_layout.setContentsMargins(6, 4, 6, 4)
            b_layout.setSpacing(6)

            lbl_act = QLabel(f"👉 <b>{self.headline}</b>")
            lbl_act.setStyleSheet("font-size: 11px; color: #F0F6FC;")
            b_layout.addWidget(lbl_act)
            b_layout.addStretch()

            btn_cta = QPushButton(self.cta_label)
            btn_cta.setCursor(Qt.PointingHandCursor)
            cta_bg = COLORS['primary'] if is_today else COLORS['surface_hover']
            cta_col = "white" if is_today else COLORS['text']
            btn_cta.setStyleSheet(f"""
                QPushButton {{
                    background-color: {cta_bg};
                    color: {cta_col};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 10px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                    color: white;
                }}
            """)
            btn_cta.clicked.connect(lambda: self.cta_triggered.emit(self.app_id, self.cta_type))
            b_layout.addWidget(btn_cta)

            layout.addWidget(act_banner)

    def mousePressEvent(self, event):
        # Prevent card click if checkbox or star was clicked
        self.clicked.emit(self.app_id)
        super().mousePressEvent(event)


# Backward compatibility alias
ConversationCardWidget = WorkQueueCaseCardWidget


# -----------------------------------------------------------------------------
# Main Desktop Outreach Center View
# -----------------------------------------------------------------------------
class OutreachView(QWidget):
    """ATS Recruiter Outreach Center Command Center."""

    data_updated = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.outreach_service = OutreachService(session_factory=SessionLocal)
        self.resume_service = ResumeService()
        self.scheduler = FollowUpScheduler(session_factory=SessionLocal)
        self.inbound_service = InboundSyncService(session_factory=SessionLocal, outreach_service=self.outreach_service)

        self._work_queue: Dict[str, Any] = {}
        self._conversations: List[dict] = []
        self._selected_app_id: Optional[int] = None
        self._checked_app_ids: set[int] = set()
        self._active_filter: str = "ALL"

        self._setup_ui()
        self.refresh_data()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(14)

        # 1. Page Header with Action Buttons
        self.header = PageHeader(
            title="Outreach Center",
            subtitle="Direct recruiter email campaigns, automated cadence tracking, and work-oriented action queue.",
        )

        btn_outreach = QPushButton("+ Direct Outreach")
        btn_outreach.setCursor(Qt.PointingHandCursor)
        btn_outreach.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_outreach.clicked.connect(self._open_composer)
        self.header.add_action_widget(btn_outreach)

        btn_bulk = QPushButton("⚡ Bulk Outreach")
        btn_bulk.setCursor(Qt.PointingHandCursor)
        btn_bulk.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}80;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
            }}
        """)
        btn_bulk.clicked.connect(self._open_bulk_outreach_dialog)
        self.header.add_action_widget(btn_bulk)

        self.btn_sync = QPushButton("🔄 Sync Inbound")
        self.btn_sync.setCursor(Qt.PointingHandCursor)
        self.btn_sync.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_sync.clicked.connect(self._sync_inbound_mail)
        self.header.add_action_widget(self.btn_sync)
        root_layout.addWidget(self.header)

        # 2. KPI Metrics Strip (5 Metric Cards)
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(10)

        self.kpi_total = ModernMetricCard(title="Total Outreached", value="0", icon="✉️", accent_color="#388BFD")
        self.kpi_today = ModernMetricCard(title="Action Today", value="0", icon="🚨", accent_color="#FF5F15")
        self.kpi_awaiting = ModernMetricCard(title="Awaiting Reply", value="0", icon="⏳", accent_color="#D29922")
        self.kpi_replied = ModernMetricCard(title="Recruiter Replied", value="0", icon="💬", accent_color="#2EA043")
        self.kpi_followups = ModernMetricCard(title="Follow-ups Due", value="0", icon="🔔", accent_color="#F85149")

        kpi_row.addWidget(self.kpi_total)
        kpi_row.addWidget(self.kpi_today)
        kpi_row.addWidget(self.kpi_awaiting)
        kpi_row.addWidget(self.kpi_replied)
        kpi_row.addWidget(self.kpi_followups)
        root_layout.addLayout(kpi_row)

        # 3. Main Split-View Workspace
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet(f"""
            QSplitter::handle {{
                background-color: {COLORS['border']};
                width: 2px;
            }}
        """)

        # 3A. Left Work Queue Pane
        left_pane = QFrame()
        left_pane.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(10)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search company, job, recruiter, email...")
        self.txt_search.textChanged.connect(self._render_conversation_list)
        left_layout.addWidget(self.txt_search)

        # Filter Pills: All, Today, Waiting, Upcoming, Closed
        filter_box = QHBoxLayout()
        filter_box.setSpacing(6)
        self.btn_filter_all = self._create_filter_btn("All", "ALL")
        self.btn_filter_today = self._create_filter_btn("Today", "TODAY")
        self.btn_filter_waiting = self._create_filter_btn("Waiting", "WAITING")
        self.btn_filter_upcoming = self._create_filter_btn("Upcoming", "UPCOMING")
        self.btn_filter_closed = self._create_filter_btn("Closed", "CLOSED")

        filter_box.addWidget(self.btn_filter_all)
        filter_box.addWidget(self.btn_filter_today)
        filter_box.addWidget(self.btn_filter_waiting)
        filter_box.addWidget(self.btn_filter_upcoming)
        filter_box.addWidget(self.btn_filter_closed)
        left_layout.addLayout(filter_box)

        # Selection Action Bar (Appears when >= 1 card is checked)
        self.selection_bar = QFrame()
        self.selection_bar.setVisible(False)
        self.selection_bar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['primary']}80;
                border-radius: 6px;
                padding: 4px 8px;
            }}
        """)
        sel_layout = QHBoxLayout(self.selection_bar)
        sel_layout.setContentsMargins(8, 4, 8, 4)
        sel_layout.setSpacing(8)

        self.lbl_sel_count = QLabel("0 Selected")
        self.lbl_sel_count.setStyleSheet("font-size: 11px; font-weight: 700; color: #F0F6FC;")
        sel_layout.addWidget(self.lbl_sel_count)

        btn_sel_bulk = QPushButton("⚡ Bulk Email")
        btn_sel_bulk.setCursor(Qt.PointingHandCursor)
        btn_sel_bulk.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        btn_sel_bulk.clicked.connect(self._open_bulk_composer_for_selected)
        sel_layout.addWidget(btn_sel_bulk)

        btn_sel_pause = QPushButton("⏸ Pause")
        btn_sel_pause.setCursor(Qt.PointingHandCursor)
        btn_sel_pause.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)
        btn_sel_pause.clicked.connect(self._pause_selected_cadences)
        sel_layout.addWidget(btn_sel_pause)

        btn_sel_resume = QPushButton("▶ Resume")
        btn_sel_resume.setCursor(Qt.PointingHandCursor)
        btn_sel_resume.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)
        btn_sel_resume.clicked.connect(self._resume_selected_cadences)
        sel_layout.addWidget(btn_sel_resume)

        btn_sel_read = QPushButton("✉️ Read")
        btn_sel_read.setCursor(Qt.PointingHandCursor)
        btn_sel_read.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 11px;
            }}
        """)
        btn_sel_read.clicked.connect(self._mark_selected_read)
        sel_layout.addWidget(btn_sel_read)

        sel_layout.addStretch()

        btn_sel_clear = QPushButton("✕")
        btn_sel_clear.setCursor(Qt.PointingHandCursor)
        btn_sel_clear.setToolTip("Clear Selection")
        btn_sel_clear.setStyleSheet("background: transparent; color: #8B949E; border: none; font-size: 12px;")
        btn_sel_clear.clicked.connect(self._clear_selection)
        sel_layout.addWidget(btn_sel_clear)

        left_layout.addWidget(self.selection_bar)

        # Scrollable conversation cards list
        self.conv_scroll = QScrollArea()
        self.conv_scroll.setWidgetResizable(True)
        self.conv_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.conv_container = QWidget()
        self.conv_list_layout = QVBoxLayout(self.conv_container)
        self.conv_list_layout.setContentsMargins(0, 0, 0, 0)
        self.conv_list_layout.setSpacing(8)
        self.conv_list_layout.addStretch()
        self.conv_scroll.setWidget(self.conv_container)
        left_layout.addWidget(self.conv_scroll, 1)

        self.splitter.addWidget(left_pane)

        # 3B. Right Detail Pane
        self.right_pane = QFrame()
        self.right_pane.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        self.right_layout = QVBoxLayout(self.right_pane)
        self.right_layout.setContentsMargins(18, 18, 18, 18)
        self.right_layout.setSpacing(14)

        # Initial Empty State
        self.empty_state_label = QLabel("Select an outreach case from the Work Queue to inspect message history, next actions, and cadence status.")
        self.empty_state_label.setAlignment(Qt.AlignCenter)
        self.empty_state_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px; font-weight: 500;")
        self.right_layout.addWidget(self.empty_state_label)

        self.splitter.addWidget(self.right_pane)
        self.splitter.setSizes([380, 620])
        root_layout.addWidget(self.splitter, 1)

    def _create_filter_btn(self, label: str, filter_val: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        is_active = (self._active_filter == filter_val)
        bg = COLORS['primary'] if is_active else COLORS['surface_hover']
        color = "white" if is_active else COLORS['text_muted']

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        btn.clicked.connect(lambda: self._set_active_filter(filter_val))
        return btn

    def _set_active_filter(self, filter_val: str):
        self._active_filter = filter_val
        self._render_conversation_list()
        # Update filter pill styles
        for btn, val in [
            (self.btn_filter_all, "ALL"),
            (self.btn_filter_today, "TODAY"),
            (self.btn_filter_waiting, "WAITING"),
            (self.btn_filter_upcoming, "UPCOMING"),
            (self.btn_filter_closed, "CLOSED"),
        ]:
            is_active = (self._active_filter == val)
            bg = COLORS['primary'] if is_active else COLORS['surface_hover']
            color = "white" if is_active else COLORS['text_muted']
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg};
                    color: {color};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 700;
                }}
            """)

    def refresh_data(self):
        """Reloads stats and operational work queue from database."""
        try:
            stats = self.outreach_service.get_outreach_stats()
            groups = self.outreach_service.get_work_queue()

            today_cases = next((g.cases for g in groups if g.section == WorkQueueSection.TODAY), [])
            waiting_cases = next((g.cases for g in groups if g.section == WorkQueueSection.WAITING), [])
            upcoming_cases = next((g.cases for g in groups if g.section == WorkQueueSection.UPCOMING), [])
            closed_cases = next((g.cases for g in groups if g.section == WorkQueueSection.CLOSED), [])

            self._work_queue = {
                "today": today_cases,
                "waiting": waiting_cases,
                "upcoming": upcoming_cases,
                "closed": closed_cases,
            }

            self.kpi_total.set_value(str(stats.get("total_outreached", 0)))
            self.kpi_today.set_value(str(len(today_cases)))
            self.kpi_awaiting.set_value(str(stats.get("awaiting_reply", 0)))
            self.kpi_replied.set_value(str(stats.get("recruiter_replied", 0)))
            self.kpi_followups.set_value(str(stats.get("followups_due", 0)))

            self._render_conversation_list()

            if self._selected_app_id:
                self._load_conversation_detail(self._selected_app_id)
        except Exception as e:
            logger.error("Failed to refresh outreach work queue: %s", e)

    def _render_conversation_list(self):
        # Clear existing cards and headers
        while self.conv_list_layout.count() > 1:
            child = self.conv_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        query = self.txt_search.text().strip().lower()

        today_cases = self._work_queue.get("today", [])
        waiting_cases = self._work_queue.get("waiting", [])
        upcoming_cases = self._work_queue.get("upcoming", [])
        closed_cases = self._work_queue.get("closed", [])

        def matches_query(case: OutreachCaseOperationViewModel) -> bool:
            if not query:
                return True
            q = query
            return (
                q in (case.company_name or "").lower()
                or q in (case.job_title or "").lower()
                or q in (case.contact_name or "").lower()
                or q in (case.contact_email or "").lower()
                or q in (case.next_action_headline or "").lower()
            )

        sections = []
        if self._active_filter in ("ALL", "TODAY"):
            filtered_today = [c for c in today_cases if matches_query(c)]
            if filtered_today:
                sections.append(("🚨 ACTION REQUIRED TODAY", filtered_today, "#FF5F15"))

        if self._active_filter in ("ALL", "WAITING"):
            filtered_waiting = [c for c in waiting_cases if matches_query(c)]
            if filtered_waiting:
                sections.append(("⏳ WAITING ON RECRUITERS", filtered_waiting, "#D29922"))

        if self._active_filter in ("ALL", "UPCOMING"):
            filtered_upcoming = [c for c in upcoming_cases if matches_query(c)]
            if filtered_upcoming:
                sections.append(("📅 UPCOMING FOLLOW-UPS", filtered_upcoming, "#388BFD"))

        if self._active_filter in ("ALL", "CLOSED"):
            filtered_closed = [c for c in closed_cases if matches_query(c)]
            if filtered_closed:
                sections.append(("📁 CLOSED & COMPLETED", filtered_closed, "#8B949E"))

        if not sections:
            lbl_empty = QLabel("No outreach cases match your criteria.")
            lbl_empty.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; padding: 20px;")
            lbl_empty.setAlignment(Qt.AlignCenter)
            self.conv_list_layout.insertWidget(0, lbl_empty)
            return

        insert_pos = 0
        for section_title, cases, accent_col in sections:
            # Section Header Frame
            hdr_frame = QFrame()
            hdr_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border-left: 3px solid {accent_col};
                    border-radius: 4px;
                    padding: 3px 6px;
                }}
            """)
            h_layout = QHBoxLayout(hdr_frame)
            h_layout.setContentsMargins(6, 3, 6, 3)
            lbl_sec = QLabel(f"<b>{section_title}</b> ({len(cases)})")
            lbl_sec.setStyleSheet(f"color: #F0F6FC; font-size: 11px; letter-spacing: 0.5px;")
            h_layout.addWidget(lbl_sec)
            self.conv_list_layout.insertWidget(insert_pos, hdr_frame)
            insert_pos += 1

            for case in cases:
                is_sel = (case.application_id == self._selected_app_id)
                is_chk = (case.application_id in self._checked_app_ids)
                card = WorkQueueCaseCardWidget(case, is_selected=is_sel, is_checked=is_chk)
                card.clicked.connect(self._on_conversation_selected)
                card.selection_toggled.connect(self._on_selection_toggled)
                card.priority_toggled.connect(self._on_priority_toggled)
                card.cta_triggered.connect(self._on_cta_triggered)
                self.conv_list_layout.insertWidget(insert_pos, card)
                insert_pos += 1

    def _on_selection_toggled(self, app_id: int, checked: bool):
        if checked:
            self._checked_app_ids.add(app_id)
        else:
            self._checked_app_ids.discard(app_id)
        self._update_selection_bar()

    def _update_selection_bar(self):
        cnt = len(self._checked_app_ids)
        if cnt > 0:
            self.lbl_sel_count.setText(f"{cnt} Selected")
            self.selection_bar.setVisible(True)
        else:
            self.selection_bar.setVisible(False)

    def _clear_selection(self):
        self._checked_app_ids.clear()
        self._update_selection_bar()
        self._render_conversation_list()

    def _on_priority_toggled(self, app_id: int):
        self.outreach_service.toggle_conversation_priority(app_id)
        self.refresh_data()

    def _on_cta_triggered(self, app_id: int, cta_type: str):
        self._on_conversation_selected(app_id)
        if cta_type == NextActionType.SEND_FOLLOW_UP.value:
            # Check if there is an active due follow-up
            timeline = self.outreach_service.get_conversation_timeline(app_id)
            due_fu = next((f for f in timeline.get("follow_ups", []) if f.get("status") == "DUE"), None)
            if due_fu:
                self._execute_followup(due_fu.get("id"))

    def _open_bulk_outreach_dialog(self):
        """Opens BulkOutreachDialog for eligible applications."""
        val_result = self.outreach_service.validate_bulk_targets(
            list(self._checked_app_ids) if self._checked_app_ids else None
        )
        dlg = BulkOutreachDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            initial_targets=val_result.items,
            parent=self,
        )
        dlg.campaign_dispatched.connect(self.refresh_data)
        dlg.exec()

    def _open_bulk_composer_for_selected(self):
        if not self._checked_app_ids:
            return
        val_result = self.outreach_service.validate_bulk_targets(list(self._checked_app_ids))
        dlg = BulkOutreachDialog(
            outreach_service=self.outreach_service,
            resume_service=self.resume_service,
            initial_targets=val_result.items,
            parent=self,
        )
        dlg.campaign_dispatched.connect(self.refresh_data)
        dlg.exec()

    def _pause_selected_cadences(self):
        if not self._checked_app_ids:
            return
        for app_id in self._checked_app_ids:
            self.outreach_service.pause_followups(app_id, reason="Bulk pause from Work Queue")
        self._clear_selection()
        self.refresh_data()
        QMessageBox.information(self, "Cadence Paused", "Follow-up cadences paused for selected applications.")

    def _resume_selected_cadences(self):
        if not self._checked_app_ids:
            return
        for app_id in self._checked_app_ids:
            self.outreach_service.resume_followups(app_id)
        self._clear_selection()
        self.refresh_data()
        QMessageBox.information(self, "Cadence Resumed", "Follow-up cadences resumed for selected applications.")

    def _mark_selected_read(self):
        if not self._checked_app_ids:
            return
        for app_id in self._checked_app_ids:
            self.outreach_service.mark_conversation_read(app_id)
        self._clear_selection()
        self.refresh_data()

    def _on_conversation_selected(self, app_id: int):
        self._selected_app_id = app_id
        # Automatically mark conversation read
        self.outreach_service.mark_conversation_read(app_id)
        self._render_conversation_list()
        self._load_conversation_detail(app_id)

    def _load_conversation_detail(self, app_id: int):
        # Clear right layout
        while self.right_layout.count() > 0:
            child = self.right_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        timeline = self.outreach_service.get_conversation_timeline(app_id)
        detail_vm = self.outreach_service.get_conversation_detail_vm(app_id)

        if "error" in timeline and not detail_vm:
            lbl_err = QLabel(f"Error loading thread: {timeline.get('error', 'Unknown error')}")
            lbl_err.setStyleSheet(f"color: {COLORS['danger']};")
            self.right_layout.addWidget(lbl_err)
            return

        comp_name = detail_vm.company_name if detail_vm else timeline.get("company_name", "Target Company")
        job_title = detail_vm.job_title if detail_vm else timeline.get("job_title", "Position")
        rec_name = detail_vm.contact.name if (detail_vm and detail_vm.contact) else timeline.get("contact_name", "Hiring Team")
        rec_email = detail_vm.contact.email if (detail_vm and detail_vm.contact) else timeline.get("contact_email", "No email")
        conv_state = detail_vm.state.value if detail_vm else timeline.get("conversation_state", "WAITING")

        # 1. Header Box
        header_frame = QFrame()
        header_frame.setStyleSheet(f"background-color: {COLORS['surface_alt']}; border-radius: 8px; padding: 12px;")
        hdr_layout = QVBoxLayout(header_frame)
        hdr_layout.setContentsMargins(12, 10, 12, 10)
        hdr_layout.setSpacing(6)

        top_h = QHBoxLayout()
        lbl_comp = QLabel(comp_name)
        lbl_comp.setStyleSheet("font-size: 16px; font-weight: 800; color: #F0F6FC;")
        top_h.addWidget(lbl_comp)
        top_h.addStretch()

        badge = StatusBadge(conv_state)
        top_h.addWidget(badge)
        hdr_layout.addLayout(top_h)

        sub_h = QHBoxLayout()
        title_str = f"{job_title} • Recruiter: {rec_name} ({rec_email})"
        lbl_sub = QLabel(title_str)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        sub_h.addWidget(lbl_sub)
        sub_h.addStretch()

        # Cadence pause/resume toggle button
        has_paused = any(f.get("status") == "PAUSED" for f in timeline.get("follow_ups", []))
        btn_toggle = QPushButton("▶ Resume Follow-ups" if has_paused else "⏸ Pause Follow-ups")
        btn_toggle.setCursor(Qt.PointingHandCursor)
        btn_toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
            }}
        """)
        btn_toggle.clicked.connect(lambda: self._toggle_cadence(app_id, not has_paused))
        sub_h.addWidget(btn_toggle)
        hdr_layout.addLayout(sub_h)

        self.right_layout.addWidget(header_frame)

        # 2. Next Action Banner Box (V2 Core Invariant: "What do I need to do right now?")
        next_action = detail_vm.next_action if detail_vm else None
        if next_action and next_action.headline:
            act_card = QFrame()
            act_card.setStyleSheet(f"""
                QFrame {{
                    background-color: rgba(255, 95, 21, 0.12);
                    border: 1px solid {COLORS['accent']};
                    border-radius: 8px;
                    padding: 10px 14px;
                }}
            """)
            act_card_layout = QHBoxLayout(act_card)
            act_card_layout.setContentsMargins(10, 8, 10, 8)
            act_card_layout.setSpacing(10)

            v_act = QVBoxLayout()
            v_act.setSpacing(2)
            lbl_act_head = QLabel(f"👉 <b>Recommended Next Action:</b> {next_action.headline}")
            lbl_act_head.setStyleSheet("font-size: 13px; font-weight: 700; color: #F0F6FC;")
            lbl_act_rat = QLabel(next_action.rationale)
            lbl_act_rat.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            v_act.addWidget(lbl_act_head)
            v_act.addWidget(lbl_act_rat)
            act_card_layout.addLayout(v_act, 1)

            btn_do_cta = QPushButton(f"⚡ {next_action.cta_label}")
            btn_do_cta.setCursor(Qt.PointingHandCursor)
            btn_do_cta.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 16px;
                    font-weight: 700;
                    font-size: 12px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                }}
            """)
            act_card_layout.addWidget(btn_do_cta)
            self.right_layout.addWidget(act_card)

        # AI Intent Recommendation Banner (if recruiter response matches a specific intent)
        inbound_comm = next((c for c in timeline.get("communications", []) if c.get("direction") == "INBOUND"), None)
        if inbound_comm:
            ai_svc = OutreachAIService()
            classification = ai_svc.classify_response(email_body=inbound_comm.get("body_snippet", ""))
            action = classification.get("suggested_action")
            if action and action not in ("NONE", "REPLY"):
                banner = QFrame()
                banner.setStyleSheet(f"""
                    QFrame {{
                        background-color: rgba(56, 139, 253, 0.15);
                        border: 1px solid #388BFD;
                        border-radius: 6px;
                        padding: 10px;
                    }}
                """)
                b_layout = QHBoxLayout(banner)
                b_layout.setContentsMargins(10, 8, 10, 8)
                lbl_rec = QLabel(f"✨ <b>AI Recruiter Intent</b>: {classification.get('category')} — <i>{classification.get('rationale_snippet')}</i>")
                lbl_rec.setStyleSheet("color: #F0F6FC; font-size: 12px;")
                b_layout.addWidget(lbl_rec)
                b_layout.addStretch()

                btn_apply = QPushButton(f"✓ Apply Status: {action}")
                btn_apply.setCursor(Qt.PointingHandCursor)
                btn_apply.setStyleSheet("""
                    QPushButton {
                        background-color: #2EA043;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 5px 12px;
                        font-weight: 700;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        background-color: #268035;
                    }
                """)
                btn_apply.clicked.connect(lambda: self._apply_suggested_status(app_id, action))
                b_layout.addWidget(btn_apply)
                self.right_layout.addWidget(banner)



        # Communication Thread Timeline Stream
        lbl_stream = QLabel("COMMUNICATION TIMELINE")
        lbl_stream.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E; letter-spacing: 0.5px;")
        self.right_layout.addWidget(lbl_stream)

        stream_scroll = QScrollArea()
        stream_scroll.setWidgetResizable(True)
        stream_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        stream_container = QWidget()
        stream_layout = QVBoxLayout(stream_container)
        stream_layout.setContentsMargins(0, 0, 0, 0)
        stream_layout.setSpacing(10)

        for comm in timeline.get("communications", []):
            bubble = QFrame()
            is_outbound = (comm.get("direction") == "OUTBOUND")
            bg = "#161B22" if is_outbound else "#1C2128"
            border_accent = COLORS['primary'] if is_outbound else "#388BFD"

            bubble.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border-left: 3px solid {border_accent};
                    border-radius: 8px;
                    padding: 8px 12px;
                }}
            """)
            b_box = QVBoxLayout(bubble)
            b_box.setContentsMargins(8, 6, 8, 6)
            b_box.setSpacing(6)

            # 1. Header Row (Sender + Date)
            hdr = QHBoxLayout()
            sender_icon = "📤" if is_outbound else "📥"
            sender_text = "Candidate (You)" if is_outbound else f"Recruiter ({comm.get('sender_email') or 'Recruiter'})"
            lbl_snd = QLabel(f"{sender_icon} <b>{sender_text}</b>")
            lbl_snd.setStyleSheet("font-size: 12px; color: #F0F6FC;")
            hdr.addWidget(lbl_snd)
            hdr.addStretch()

            date_str = comm.get("occurred_at", "")
            if date_str and len(date_str) >= 16:
                date_str = date_str[:16].replace("T", " ")
            lbl_t = QLabel(date_str)
            lbl_t.setStyleSheet(f"font-size: 11px; color: {COLORS['text_dark']}; font-weight: 500;")
            hdr.addWidget(lbl_t)
            b_box.addLayout(hdr)

            # 2. Subject Line
            if comm.get("subject"):
                lbl_sub = QLabel(f"Subject: {comm.get('subject')}")
                lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; font-weight: 600;")
                b_box.addWidget(lbl_sub)

            # 3. Attached Resume Badge (Outbound Candidate)
            res_info = comm.get("resume_info") or timeline.get("resume_info")
            att_path = comm.get("attachment_path")
            if is_outbound and (res_info or att_path):
                r_name = res_info.get("name", "Candidate Resume") if res_info else "Candidate Resume (PDF)"
                r_target = f" ({res_info.get('role_target')})" if res_info and res_info.get("role_target") else ""
                r_version = f" [{res_info.get('version')}]" if res_info and res_info.get("version") else ""
                res_display_title = f"{r_name}{r_target}{r_version}"
                target_file = (res_info and res_info.get("file_path")) or att_path

                res_pill = QFrame()
                res_pill.setStyleSheet(f"""
                    QFrame {{
                        background-color: {COLORS['surface_alt']};
                        border: 1px solid {COLORS['border_light']};
                        border-radius: 6px;
                        padding: 4px 8px;
                    }}
                """)
                rp_layout = QHBoxLayout(res_pill)
                rp_layout.setContentsMargins(6, 4, 6, 4)
                rp_layout.setSpacing(8)

                lbl_res_icon = QLabel("📄")
                lbl_res_desc = QLabel(f"<b>Sent Resume:</b> {res_display_title}")
                lbl_res_desc.setStyleSheet("font-size: 11px; color: #E5E7EB;")
                rp_layout.addWidget(lbl_res_icon)
                rp_layout.addWidget(lbl_res_desc, 1)

                if target_file and os.path.exists(target_file):
                    btn_view_res = QPushButton("👁 View Sent Resume")
                    btn_view_res.setCursor(Qt.PointingHandCursor)
                    btn_view_res.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLORS['surface_hover']};
                            color: {COLORS['primary']};
                            border: 1px solid {COLORS['primary']}60;
                            border-radius: 4px;
                            padding: 3px 10px;
                            font-size: 11px;
                            font-weight: 700;
                        }}
                        QPushButton:hover {{
                            background-color: {COLORS['primary']};
                            color: white;
                        }}
                    """)
                    btn_view_res.clicked.connect(lambda _, p=target_file: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                    rp_layout.addWidget(btn_view_res)

                b_box.addWidget(res_pill)

            # 4. HR Attachment Badge (Inbound Recruiter)
            if not is_outbound and att_path:
                att_filename = comm.get("attachment_name") or os.path.basename(att_path)
                hr_pill = QFrame()
                hr_pill.setStyleSheet("""
                    QFrame {
                        background-color: rgba(56, 139, 253, 0.12);
                        border: 1px solid #388BFD;
                        border-radius: 6px;
                        padding: 4px 8px;
                    }
                """)
                hp_layout = QHBoxLayout(hr_pill)
                hp_layout.setContentsMargins(6, 4, 6, 4)
                hp_layout.setSpacing(8)

                lbl_hr_icon = QLabel("📎")
                lbl_hr_desc = QLabel(f"<b>Recruiter Attachment:</b> {att_filename}")
                lbl_hr_desc.setStyleSheet("font-size: 11px; color: #58A6FF;")
                hp_layout.addWidget(lbl_hr_icon)
                hp_layout.addWidget(lbl_hr_desc, 1)

                if os.path.exists(att_path):
                    btn_open_hr = QPushButton("📂 Open Attachment")
                    btn_open_hr.setCursor(Qt.PointingHandCursor)
                    btn_open_hr.setStyleSheet("""
                        QPushButton {
                            background-color: #388BFD;
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 3px 10px;
                            font-size: 11px;
                            font-weight: 700;
                        }
                        QPushButton:hover {
                            background-color: #1F6FEB;
                        }
                    """)
                    btn_open_hr.clicked.connect(lambda _, p=att_path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                    hp_layout.addWidget(btn_open_hr)

                b_box.addWidget(hr_pill)

            # 5. Message Content with Expand / Collapse
            full_body = (comm.get("body_text") or comm.get("snippet") or "").strip()
            if not full_body:
                full_body = "Message dispatched successfully."

            is_long = (len(full_body) > 160 or full_body.count("\n") >= 2)

            if is_long:
                snippet_text = full_body[:150].rstrip() + "..."
                lbl_snip = QLabel(snippet_text)
                lbl_snip.setWordWrap(True)
                lbl_snip.setStyleSheet("font-size: 12px; color: #D1D5DB; line-height: 1.4;")
                lbl_snip.setTextInteractionFlags(Qt.TextSelectableByMouse)
                b_box.addWidget(lbl_snip)

                txt_full = QTextEdit()
                txt_full.setPlainText(full_body)
                txt_full.setReadOnly(True)
                txt_full.setMaximumHeight(160)
                txt_full.setStyleSheet(f"""
                    QTextEdit {{
                        background-color: {COLORS['background']};
                        color: #E5E7EB;
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        font-size: 12px;
                        padding: 8px;
                    }}
                """)
                txt_full.setVisible(False)
                b_box.addWidget(txt_full)

                btn_expand = QPushButton("📖 Read Full Message ▼")
                btn_expand.setCursor(Qt.PointingHandCursor)
                btn_expand.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {COLORS['accent']};
                        border: none;
                        font-size: 11px;
                        font-weight: 700;
                        text-align: left;
                        padding: 2px 0px;
                    }}
                    QPushButton:hover {{
                        color: {COLORS['primary']};
                    }}
                """)

                def _toggle_msg(*args):
                    if txt_full.isVisible():
                        txt_full.setVisible(False)
                        lbl_snip.setVisible(True)
                        btn_expand.setText("📖 Read Full Message ▼")
                    else:
                        txt_full.setVisible(True)
                        lbl_snip.setVisible(False)
                        btn_expand.setText("▲ Show Less")

                btn_expand.clicked.connect(_toggle_msg)
                b_box.addWidget(btn_expand)
            else:
                lbl_body = QLabel(full_body)
                lbl_body.setWordWrap(True)
                lbl_body.setStyleSheet("font-size: 12px; color: #D1D5DB; margin-top: 2px;")
                lbl_body.setTextInteractionFlags(Qt.TextSelectableByMouse)
                b_box.addWidget(lbl_body)

            stream_layout.addWidget(bubble)

        stream_layout.addStretch()
        stream_scroll.setWidget(stream_container)
        self.right_layout.addWidget(stream_scroll, 1)

        # Quick Reply to Recruiter Card
        reply_card = QFrame()
        reply_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
            }}
        """)
        reply_layout = QVBoxLayout(reply_card)
        reply_layout.setContentsMargins(12, 10, 12, 10)
        reply_layout.setSpacing(8)

        reply_hdr = QHBoxLayout()
        lbl_reply_title = QLabel("💬 Reply to Recruiter (Threaded)")
        lbl_reply_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #F0F6FC;")
        reply_hdr.addWidget(lbl_reply_title)
        reply_hdr.addStretch()

        contact_info = timeline.get("contact")
        recruiter_target = (contact_info.get("email") if contact_info else None) or timeline.get("contact_email") or "Recruiter"
        lbl_target_info = QLabel(f"To: {recruiter_target}")
        lbl_target_info.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 500;")
        reply_hdr.addWidget(lbl_target_info)
        reply_layout.addLayout(reply_hdr)

        txt_reply_input = QTextEdit()
        txt_reply_input.setPlaceholderText("Write your reply message here... (e.g. confirming interview time, answering screening questions, or sharing availability)")
        txt_reply_input.setMinimumHeight(65)
        txt_reply_input.setMaximumHeight(100)
        txt_reply_input.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: #F0F6FC;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
            }}
            QTextEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        reply_layout.addWidget(txt_reply_input)

        reply_act_row = QHBoxLayout()
        reply_status_lbl = QLabel("")
        reply_status_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        reply_act_row.addWidget(reply_status_lbl)
        reply_act_row.addStretch()

        btn_send_reply = QPushButton("✉️ Send Reply (Threaded)")
        btn_send_reply.setCursor(Qt.PointingHandCursor)
        btn_send_reply.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text_dark']};
            }}
        """)

        def _do_send_reply(*args):
            reply_text = txt_reply_input.toPlainText().strip()
            if not reply_text:
                QMessageBox.warning(self, "Empty Message", "Please type a reply message before sending.")
                return

            btn_send_reply.setEnabled(False)
            btn_send_reply.setText("⏳ Sending Reply...")
            reply_status_lbl.setText("Connecting to mail server...")

            worker = ReplySendWorker(self.outreach_service, app_id, reply_text)
            self._active_reply_worker = worker

            def _on_success(res):
                btn_send_reply.setEnabled(True)
                btn_send_reply.setText("✉️ Send Reply (Threaded)")
                reply_status_lbl.setText("")
                if res.get("success"):
                    QMessageBox.information(self, "Reply Sent", "Your reply has been dispatched and recorded in the conversation thread!")
                    txt_reply_input.clear()
                    self.refresh_data()
                else:
                    QMessageBox.warning(self, "Reply Failed", f"Could not send reply:\n\n{res.get('error')}")

            def _on_err(err_str):
                btn_send_reply.setEnabled(True)
                btn_send_reply.setText("✉️ Send Reply (Threaded)")
                reply_status_lbl.setText("")
                QMessageBox.critical(self, "Send Error", f"Failed to dispatch reply:\n\n{err_str}")

            worker.finished.connect(_on_success)
            worker.error.connect(_on_err)
            worker.start()

        btn_send_reply.clicked.connect(_do_send_reply)
        reply_act_row.addWidget(btn_send_reply)
        reply_layout.addLayout(reply_act_row)

        self.right_layout.addWidget(reply_card)

        # Follow-up Cadence Schedule Box
        fu_frame = QFrame()
        fu_frame.setStyleSheet(f"background-color: {COLORS['background']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 10px;")
        fu_layout = QVBoxLayout(fu_frame)
        fu_layout.setContentsMargins(10, 8, 10, 8)
        fu_layout.setSpacing(6)

        lbl_cad_title = QLabel("AUTOMATED FOLLOW-UP CADENCE")
        lbl_cad_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #8B949E; letter-spacing: 0.5px;")
        fu_layout.addWidget(lbl_cad_title)

        follow_ups = timeline.get("follow_ups", [])
        if not follow_ups:
            lbl_none = QLabel("No active follow-up cadence scheduled.")
            lbl_none.setStyleSheet(f"font-size: 12px; color: {COLORS['text_dark']};")
            fu_layout.addWidget(lbl_none)
        else:
            for fu in follow_ups:
                row = QHBoxLayout()
                row.setSpacing(10)
                step_lbl = QLabel(f"Step {fu.get('step_number')}:")
                step_lbl.setStyleSheet("font-weight: 700; font-size: 12px; color: #F0F6FC;")
                row.addWidget(step_lbl)

                due_at = fu.get("due_at", "")
                if due_at and len(due_at) >= 10:
                    due_at = due_at[:10]
                lbl_due = QLabel(f"Due: {due_at}")
                lbl_due.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
                row.addWidget(lbl_due)
                row.addStretch()

                st = fu.get("status", "PENDING")
                badge_fu = StatusBadge(st)
                row.addWidget(badge_fu)

                if st == "DUE":
                    btn_exec = QPushButton("⚡ Execute Now")
                    btn_exec.setCursor(Qt.PointingHandCursor)
                    btn_exec.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLORS['primary']};
                            color: white;
                            border: none;
                            border-radius: 4px;
                            padding: 3px 8px;
                            font-size: 11px;
                            font-weight: 700;
                        }}
                    """)
                    btn_exec.clicked.connect(lambda _, fu_id=fu.get("id"): self._execute_followup(fu_id))
                    row.addWidget(btn_exec)

                fu_layout.addLayout(row)

        self.right_layout.addWidget(fu_frame)

    def _open_composer(self):
        dlg = OutreachComposerDialog(self.outreach_service, self.resume_service, self)
        dlg.outreach_sent.connect(self.refresh_data)
        dlg.exec()

    def _sync_inbound_mail(self):
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("🔄 Syncing...")

        self._sync_worker = MailboxSyncWorker(self.inbound_service)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.error.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_sync_finished(self, res: dict):
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("🔄 Sync Inbound")
        if res.get("success"):
            matched = res.get("matched_count", 0)
            ingested = res.get("ingested_applications", 0)
            label = res.get("sync_label", "Gmail")
            msg = (
                f"🎉 Sync completed for {label} & INBOX!\n\n"
                f"• {ingested} application(s) synced from Gmail\n"
                f"• {matched} recruiter reply/replies matched & updated\n"
            )
            QMessageBox.information(self, "Mailbox Synced", msg)
            self.refresh_data()
        else:
            QMessageBox.warning(self, "Sync Issue", f"Mailbox sync issue: {res.get('error')}")

    def _on_sync_failed(self, err_msg: str):
        self.btn_sync.setEnabled(True)
        self.btn_sync.setText("🔄 Sync Inbound")
        QMessageBox.critical(self, "Sync Error", f"Failed to sync inbox: {err_msg}")

    def _toggle_cadence(self, app_id: int, should_pause: bool):
        try:
            if should_pause:
                self.outreach_service.pause_followups(app_id, reason="Manual toggle from desktop")
            else:
                self.outreach_service.resume_followups(app_id)
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to toggle cadence: {e}")

    def _apply_suggested_status(self, app_id: int, status: str):
        try:
            with get_db_session(SessionLocal) as s:
                app = s.get(Application, app_id)
                if app:
                    app.status = status
                    app.notes = f"{app.notes or ''}\n[Status Updated via AI Intent]: {status}".strip()
                    s.commit()
            QMessageBox.information(self, "Status Updated", f"Application marked as {status}!")
            self.refresh_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not update status: {e}")

    def _execute_followup(self, fu_id: int):
        try:
            res = self.scheduler.execute_followup(fu_id)
            if res.get("success"):
                QMessageBox.information(self, "Follow-up Sent", "Follow-up email dispatched successfully!")
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Dispatch Failed", f"Could not execute follow-up: {res.get('error')}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Follow-up error: {e}")
