"""New Outreach Composer Dialog — Modern ATS & Recruitment Conversation Composer.

Replaces the legacy rigid Direct Recruiter Outreach form with a modern email composer
tailored specifically for recruitment workflows. Supports:
  - Job Context (Search/select existing JobPilot jobs or manual job)
  - Recruiter Contact details (with duplicate avoidance)
  - Managed Resume selection (role-tailored, verified, clean display)
  - Template Library insertion (interpolating candidate & role variables)
  - AI Pitch Generation with template fallback
  - Automated Follow-up Cadence configuration (4d/10d/17d)
  - Draft saving and direct dispatch via OutreachService
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Job, Resume
from app.services.dto.outreach_dto import OutreachCreateDTO
from app.services.job_service import JobService
from app.services.outreach_ai_service import OutreachAIService
from app.services.outreach_service import OutreachService
from app.services.resume_service import ResumeService
from app.ui.theme import COLORS
from app.ui.views.outreach.modern_popup import ModernPopup

logger = logging.getLogger("JobPilot.Outreach.ComposerDialog")


# -----------------------------------------------------------------------------
# Background Workers
# -----------------------------------------------------------------------------

class _AIPitchWorker(QThread):
    """Generates an AI pitch in the background without freezing the UI."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        company_name: str,
        job_title: str,
        recruiter_name: Optional[str] = None,
        resume_id: Optional[int] = None,
        custom_instructions: Optional[str] = None,
    ):
        super().__init__()
        self.company_name = company_name
        self.job_title = job_title
        self.recruiter_name = recruiter_name
        self.resume_id = resume_id
        self.custom_instructions = custom_instructions

    def run(self):
        try:
            ai_svc = OutreachAIService()
            res = ai_svc.generate_pitch(
                company_name=self.company_name,
                job_title=self.job_title,
                recruiter_name=self.recruiter_name,
                resume_id=self.resume_id,
                custom_instructions=self.custom_instructions,
            )
            self.finished.emit(res)
        except Exception as e:
            logger.exception("AI Pitch generation failed")
            self.error.emit(str(e))


class _AIRefineWorker(QThread):
    """Refines existing email body with AI in the background."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        outreach_service: OutreachService,
        current_body: str,
        instructions: Optional[str] = None,
        company_name: str = "",
        job_title: str = "",
    ):
        super().__init__()
        self.outreach_svc = outreach_service
        self.current_body = current_body
        self.instructions = instructions
        self.company_name = company_name
        self.job_title = job_title

    def run(self):
        try:
            res = self.outreach_svc.refine_pitch(
                current_body=self.current_body,
                instructions=self.instructions,
                company_name=self.company_name,
                job_title=self.job_title,
            )
            self.finished.emit(res)
        except Exception as e:
            logger.exception("AI Refine failed")
            self.error.emit(str(e))


class _OutreachSendWorker(QThread):
    """Dispatches the outreach message via OutreachService on a background thread."""
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
            logger.exception("Outreach dispatch failed")
            self.error.emit(str(e))


class JobPickerComboBox(QComboBox):
    """QComboBox that redirects popup display to the paginated JobPickerModal."""
    picker_requested = Signal()

    def showPopup(self):
        self.picker_requested.emit()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.picker_requested.emit()
        else:
            super().mousePressEvent(e)


# -----------------------------------------------------------------------------
# Modern Outreach Composer Dialog
# -----------------------------------------------------------------------------

class OutreachComposerDialog(QDialog):
    """Modern ATS-style modal for drafting and dispatching direct recruiter applications."""

    outreach_sent = Signal()

    def __init__(
        self,
        outreach_service: Optional[OutreachService] = None,
        resume_service: Optional[ResumeService] = None,
        job_service: Optional[JobService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.outreach_service = outreach_service or OutreachService()
        self.resume_service = resume_service or ResumeService()
        self.job_service = job_service or JobService()

        self._ai_worker: Optional[_AIPitchWorker] = None
        self._send_worker: Optional[_OutreachSendWorker] = None
        self._templates_cache: List[Dict[str, Any]] = []
        self._jobs_cache: List[Job] = []

        self.setWindowTitle("New Outreach — Recruiter Conversation")
        self.setFixedWidth(780)
        self.setMinimumHeight(720)

        self._apply_dialog_styles()
        self._setup_ui()
        self._load_data()

    def _apply_dialog_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 13px;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
                selection-background-color: {COLORS['primary']};
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border: 1px solid {COLORS['primary']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 24px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface_elevated']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                selection-background-color: {COLORS['surface_hover']};
            }}
            QCheckBox, QRadioButton {{
                color: {COLORS['text']};
                font-size: 12px;
                spacing: 8px;
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 16px;
                height: 16px;
            }}
            QFrame#sectionFrame {{
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 12px;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(12)

        # Header Title Bar
        header_box = QHBoxLayout()
        header_text_box = QVBoxLayout()
        header_text_box.setSpacing(2)

        lbl_title = QLabel("New Recruiter Outreach")
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 700; color: #F0F6FC;")
        lbl_sub = QLabel("Initiate a tracked recruitment conversation with smart follow-ups and AI assistance.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")

        header_text_box.addWidget(lbl_title)
        header_text_box.addWidget(lbl_sub)
        header_box.addLayout(header_text_box)
        header_box.addStretch()

        root_layout.addLayout(header_box)

        # Scrollable Form Body
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.viewport().installEventFilter(self)

        self.scroll_content = QWidget()
        self.scroll_content.setMaximumWidth(740)
        scroll_layout = QVBoxLayout(self.scroll_content)
        scroll_layout.setContentsMargins(0, 0, 4, 0)
        scroll_layout.setSpacing(12)

        # -------------------------------------------------------------
        # Section 1: Job Context
        # -------------------------------------------------------------
        sec_job = QFrame()
        sec_job.setObjectName("sectionFrame")
        layout_job = QVBoxLayout(sec_job)
        layout_job.setContentsMargins(12, 10, 12, 10)
        layout_job.setSpacing(8)

        lbl_job_sec = QLabel("1. TARGET OPPORTUNITY")
        lbl_job_sec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; letter-spacing: 0.5px;")
        layout_job.addWidget(lbl_job_sec)

        # Job selection combo + browse modal button
        job_picker_row = QHBoxLayout()
        job_picker_row.setSpacing(8)

        lbl_picker = QLabel("Select Tracked Job:")
        lbl_picker.setFixedWidth(130)
        job_picker_row.addWidget(lbl_picker)

        self.cmb_jobs = JobPickerComboBox()
        self.cmb_jobs.addItem("— Choose from saved jobs (Click to browse 10/page) —", None)
        self.cmb_jobs.currentIndexChanged.connect(self._on_job_selected)
        self.cmb_jobs.picker_requested.connect(self._on_open_job_picker)
        self.cmb_jobs.setCursor(Qt.CursorShape.PointingHandCursor)
        job_picker_row.addWidget(self.cmb_jobs, 1)

        self.btn_browse_jobs = QPushButton("🔍 Browse (10/page)")
        self.btn_browse_jobs.setToolTip("Open paginated job picker modal with search")
        self.btn_browse_jobs.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse_jobs.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']}60;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
            }}
        """)
        self.btn_browse_jobs.clicked.connect(self._on_open_job_picker)
        job_picker_row.addWidget(self.btn_browse_jobs)

        self.btn_create_job = QPushButton("+ Create New")
        self.btn_create_job.setToolTip("Create a new job in repository")
        self.btn_create_job.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_create_job.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_create_job.clicked.connect(self._on_create_new_job_clicked)
        job_picker_row.addWidget(self.btn_create_job)

        layout_job.addLayout(job_picker_row)

        # Inputs for Company & Position Title
        grid_job = QGridLayout()
        grid_job.setSpacing(8)

        grid_job.addWidget(QLabel("Target Company *"), 0, 0)
        grid_job.addWidget(QLabel("Position Title *"), 0, 1)

        self.txt_company = QLineEdit()
        self.txt_company.setPlaceholderText("e.g. Acme Corp")
        self.txt_company.textChanged.connect(self._update_default_subject)
        grid_job.addWidget(self.txt_company, 1, 0)

        self.txt_job_title = QLineEdit()
        self.txt_job_title.setPlaceholderText("e.g. Senior Backend Engineer")
        self.txt_job_title.textChanged.connect(self._update_default_subject)
        grid_job.addWidget(self.txt_job_title, 1, 1)

        layout_job.addLayout(grid_job)

        # Optional Job URL
        url_row = QHBoxLayout()
        lbl_url = QLabel("Job Posting URL:")
        lbl_url.setFixedWidth(130)
        self.txt_job_url = QLineEdit()
        self.txt_job_url.setPlaceholderText("https://linkedin.com/jobs/view/...")
        url_row.addWidget(lbl_url)
        url_row.addWidget(self.txt_job_url, 1)
        layout_job.addLayout(url_row)

        scroll_layout.addWidget(sec_job)

        # -------------------------------------------------------------
        # Section 2: Recruiter Contact
        # -------------------------------------------------------------
        sec_contact = QFrame()
        sec_contact.setObjectName("sectionFrame")
        layout_contact = QVBoxLayout(sec_contact)
        layout_contact.setContentsMargins(12, 10, 12, 10)
        layout_contact.setSpacing(8)

        lbl_contact_sec = QLabel("2. RECRUITER CONTACT")
        lbl_contact_sec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; letter-spacing: 0.5px;")
        layout_contact.addWidget(lbl_contact_sec)

        grid_contact = QGridLayout()
        grid_contact.setSpacing(8)

        grid_contact.addWidget(QLabel("Recruiter / Hiring Manager Name"), 0, 0)
        grid_contact.addWidget(QLabel("Recruiter Email *"), 0, 1)

        self.txt_contact_name = QLineEdit()
        self.txt_contact_name.setPlaceholderText("e.g. Sarah Jenkins")
        grid_contact.addWidget(self.txt_contact_name, 1, 0)

        self.txt_contact_email = QLineEdit()
        self.txt_contact_email.setPlaceholderText("e.g. sjenkins@acme.com")
        grid_contact.addWidget(self.txt_contact_email, 1, 1)

        layout_contact.addLayout(grid_contact)

        scroll_layout.addWidget(sec_contact)

        # -------------------------------------------------------------
        # Section 3: Resume & Template Tools
        # -------------------------------------------------------------
        sec_tools = QFrame()
        sec_tools.setObjectName("sectionFrame")
        layout_tools = QVBoxLayout(sec_tools)
        layout_tools.setContentsMargins(12, 10, 12, 10)
        layout_tools.setSpacing(8)

        lbl_tools_sec = QLabel("3. ASSETS & PRESETS")
        lbl_tools_sec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; letter-spacing: 0.5px;")
        layout_tools.addWidget(lbl_tools_sec)

        grid_tools = QGridLayout()
        grid_tools.setSpacing(8)

        grid_tools.addWidget(QLabel("Attach Resume"), 0, 0)
        grid_tools.addWidget(QLabel("Template Preset"), 0, 1)

        self.cmb_resume = QComboBox()
        self.cmb_resume.addItem("No Resume Attached", None)
        grid_tools.addWidget(self.cmb_resume, 1, 0)

        self.cmb_template = QComboBox()
        self.cmb_template.addItem("Custom Pitch (No Template)", None)
        self.cmb_template.currentIndexChanged.connect(self._on_template_selected)
        grid_tools.addWidget(self.cmb_template, 1, 1)

        layout_tools.addLayout(grid_tools)

        # AI Instructions and Prompt
        prompt_box = QVBoxLayout()
        prompt_box.setSpacing(4)
        lbl_ai_inst = QLabel("AI Pitch Prompt / Instructions (Optional):")
        lbl_ai_inst.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 500;")
        prompt_box.addWidget(lbl_ai_inst)

        prompt_row = QHBoxLayout()
        prompt_row.setSpacing(8)
        self.txt_ai_instructions = QLineEdit()
        self.txt_ai_instructions.setPlaceholderText("e.g. Emphasize 2+ yrs Python/RPA experience, mention immediate availability, keep under 100 words...")
        prompt_row.addWidget(self.txt_ai_instructions, 1)

        self.btn_ai_pitch = QPushButton("✨ Generate AI Pitch")
        self.btn_ai_pitch.setCursor(Qt.PointingHandCursor)
        self.btn_ai_pitch.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']}60;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border-color: {COLORS['border']};
            }}
        """)
        self.btn_ai_pitch.clicked.connect(self._on_generate_ai_pitch)
        prompt_row.addWidget(self.btn_ai_pitch)
        prompt_box.addLayout(prompt_row)
        layout_tools.addLayout(prompt_box)

        scroll_layout.addWidget(sec_tools)

        # -------------------------------------------------------------
        # Section 4: Email Message
        # -------------------------------------------------------------
        sec_msg = QFrame()
        sec_msg.setObjectName("sectionFrame")
        layout_msg = QVBoxLayout(sec_msg)
        layout_msg.setContentsMargins(12, 10, 12, 10)
        layout_msg.setSpacing(8)

        lbl_msg_sec = QLabel("4. MESSAGE COMPOSITION")
        lbl_msg_sec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; letter-spacing: 0.5px;")
        layout_msg.addWidget(lbl_msg_sec)

        layout_msg.addWidget(QLabel("Subject Line *"))
        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText("e.g. Application: Senior Backend Engineer — Candidate")
        layout_msg.addWidget(self.txt_subject)

        body_header_row = QHBoxLayout()
        lbl_body_title = QLabel("Email Body *")
        body_header_row.addWidget(lbl_body_title)
        body_header_row.addStretch()

        self.btn_refine_body = QPushButton("✨ Refine with AI")
        self.btn_refine_body.setToolTip("Refine or polish your manual edits using AI")
        self.btn_refine_body.setCursor(Qt.PointingHandCursor)
        self.btn_refine_body.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: #58A6FF;
                border: 1px solid #58A6FF50;
                border-radius: 5px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #58A6FF;
                color: #0D1117;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border-color: {COLORS['border']};
            }}
        """)
        self.btn_refine_body.clicked.connect(self._on_refine_body)
        body_header_row.addWidget(self.btn_refine_body)
        layout_msg.addLayout(body_header_row)

        self.txt_body = QTextEdit()
        self.txt_body.setPlaceholderText("Compose your personalized message to the recruiter or hiring manager...")
        self.txt_body.setMinimumHeight(150)
        layout_msg.addWidget(self.txt_body)

        scroll_layout.addWidget(sec_msg)

        # -------------------------------------------------------------
        # Section 5: Automated Follow-Up Cadence
        # -------------------------------------------------------------
        sec_cadence = QFrame()
        sec_cadence.setObjectName("sectionFrame")
        layout_cadence = QVBoxLayout(sec_cadence)
        layout_cadence.setContentsMargins(12, 10, 12, 10)
        layout_cadence.setSpacing(8)

        lbl_cadence_sec = QLabel("5. AUTOMATED FOLLOW-UP CADENCE")
        lbl_cadence_sec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['primary']}; letter-spacing: 0.5px;")
        layout_cadence.addWidget(lbl_cadence_sec)

        self.cadence_group = QButtonGroup(self)
        self.rb_cadence_std = QRadioButton("Standard Cadence (+4d check-in, +10d value-add, +17d closeout)")
        self.rb_cadence_std.setChecked(True)
        self.rb_cadence_fast = QRadioButton("Short Cadence (+3d check-in, +7d closeout)")
        self.rb_cadence_none = QRadioButton("Single Outreach Only (No automated follow-ups)")

        self.cadence_group.addButton(self.rb_cadence_std, 1)
        self.cadence_group.addButton(self.rb_cadence_fast, 2)
        self.cadence_group.addButton(self.rb_cadence_none, 3)

        layout_cadence.addWidget(self.rb_cadence_std)
        layout_cadence.addWidget(self.rb_cadence_fast)
        layout_cadence.addWidget(self.rb_cadence_none)

        scroll_layout.addWidget(sec_cadence)

        self.scroll_area.setWidget(self.scroll_content)
        root_layout.addWidget(self.scroll_area, 1)

        # -------------------------------------------------------------
        # Footer Action Bar
        # -------------------------------------------------------------
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 4, 0, 0)
        footer_layout.setSpacing(10)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        footer_layout.addWidget(self.lbl_status, 1)

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
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        footer_layout.addWidget(btn_cancel)

        self.btn_send = QPushButton("Send Outreach Now")
        self.btn_send.setCursor(Qt.PointingHandCursor)
        self.btn_send.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
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
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.btn_send.clicked.connect(self._on_send_outreach)
        footer_layout.addWidget(self.btn_send)

        root_layout.addLayout(footer_layout)

    # -------------------------------------------------------------------------
    # Data Loading
    # -------------------------------------------------------------------------

    def _load_data(self):
        """Loads jobs, templates, and resumes into their respective controls."""
        # 1. Load Resumes
        try:
            resumes = self.resume_service.list_resumes()
            for r in resumes:
                title = getattr(r, "custom_title", None) or getattr(r, "name", None) or getattr(r, "role_target", None) or getattr(r, "target_role", "Resume")
                ver = f"v{r.version}" if getattr(r, "version", None) else ""
                verified_tag = " [✓ Verified]" if getattr(r, "is_verified", False) else ""
                default_tag = " (Default)" if getattr(r, "is_default", False) else ""
                label = f"{title} {ver}{default_tag}{verified_tag}".strip()
                self.cmb_resume.addItem(label, r.id)

                if r.is_default:
                    # Select default resume
                    self.cmb_resume.setCurrentIndex(self.cmb_resume.count() - 1)
        except Exception as e:
            logger.warning("Could not load resumes: %s", e)

        # 2. Load Templates
        try:
            self._templates_cache = self.outreach_service.list_templates()
            for t in self._templates_cache:
                cat = f"[{t.get('category', 'General')}]"
                name = t.get("name", "Template")
                self.cmb_template.addItem(f"{cat} {name}", t.get("id"))
        except Exception as e:
            logger.warning("Could not load templates: %s", e)

        # 3. Load Jobs
        try:
            self._jobs_cache = self.job_service.list_jobs(limit=100)
            for j in self._jobs_cache:
                comp_name = getattr(j, "company_raw", None) or getattr(j, "company_name", None)
                if not comp_name and hasattr(j, "company") and j.company:
                    comp_name = getattr(j.company, "name", "Unknown")
                comp_name = comp_name or "Unknown"
                plat = f"({j.platform.title()})" if j.platform else ""
                label = f"{comp_name} — {j.title} {plat}".strip()
                self.cmb_jobs.addItem(label, j.id)
        except Exception as e:
            logger.warning("Could not load jobs: %s", e)

    # -------------------------------------------------------------------------
    # UI Interactions & Event Filtering
    # -------------------------------------------------------------------------

    def eventFilter(self, watched, event):
        """Prevents horizontal wheel scrolling on the form scroll viewport."""
        if event.type() == QEvent.Type.Wheel:
            if abs(event.angleDelta().x()) > abs(event.angleDelta().y()):
                return True
        return super().eventFilter(watched, event)

    def _on_open_job_picker(self, open_create: bool = False):
        """Opens paginated modal to browse all saved jobs (10 per page) with search."""
        from app.ui.views.outreach.job_picker_modal import JobPickerModal
        modal = JobPickerModal(job_service=self.job_service, parent=self)
        if open_create:
            modal._toggle_create_form()
        modal.job_selected.connect(self._on_job_picked_from_modal)
        modal.exec()

    def _on_job_picked_from_modal(self, job_data: dict):
        """Auto-fills job details selected from the JobPickerModal."""
        comp = job_data.get("company_name", "")
        title = job_data.get("title", "")
        url = job_data.get("source_url", "")
        jid = job_data.get("id")

        if comp:
            self.txt_company.setText(comp)
        if title:
            self.txt_job_title.setText(title)
        if url:
            self.txt_job_url.setText(url)

        # Update combo box selection
        idx = self.cmb_jobs.findData(jid)
        if idx >= 0:
            self.cmb_jobs.setCurrentIndex(idx)
        else:
            self.cmb_jobs.addItem(f"{comp} — {title}", jid)
            self.cmb_jobs.setCurrentIndex(self.cmb_jobs.count() - 1)

    def _on_create_new_job_clicked(self):
        """Opens job picker directly in create new job mode."""
        self._on_open_job_picker(open_create=True)

    def _on_job_selected(self, index: int):
        """Auto-fills company name and job title when a saved job is selected."""
        job_id = self.cmb_jobs.currentData()
        if not job_id:
            return

        for j in self._jobs_cache:
            if j.id == job_id:
                comp_name = getattr(j, "company_raw", None) or getattr(j, "company_name", "")
                if not comp_name and hasattr(j, "company") and j.company:
                    comp_name = getattr(j.company, "name", "")
                self.txt_company.setText(comp_name)
                self.txt_job_title.setText(j.title or "")
                job_url = getattr(j, "source_url", None) or getattr(j, "application_url", None) or getattr(j, "job_url", None)
                if job_url:
                    self.txt_job_url.setText(job_url)
                break

    def _update_default_subject(self):
        """Keeps subject line sensible if not explicitly edited by the user."""
        current_subj = self.txt_subject.text().strip()
        comp = self.txt_company.text().strip()
        pos = self.txt_job_title.text().strip()

        # If subject is empty or follows the standard application pattern, update it automatically
        if not current_subj or current_subj.startswith("Application"):
            if pos and comp:
                self.txt_subject.setText(f"Application — {pos} at {comp}")
            elif pos:
                self.txt_subject.setText(f"Application — {pos}")
            elif comp:
                self.txt_subject.setText(f"Application to {comp}")

    def _on_template_selected(self, index: int):
        """Applies chosen template variables to subject and body."""
        template_id = self.cmb_template.currentData()
        if not template_id:
            return

        tmpl = next((t for t in self._templates_cache if t.get("id") == template_id), None)
        if not tmpl:
            return

        recruiter = self.txt_contact_name.text().strip() or "Hiring Team"
        company = self.txt_company.text().strip() or "Your Company"
        position = self.txt_job_title.text().strip() or "the open position"

        # Interpolate standard tokens
        replacements = {
            "{{recruiter_name}}": recruiter,
            "{{company_name}}": company,
            "{{job_title}}": position,
            "{{candidate_name}}": "Candidate",
        }

        subject = tmpl.get("subject_template", "")
        body = tmpl.get("body_template", "")

        for token, val in replacements.items():
            subject = subject.replace(token, val)
            body = body.replace(token, val)

        if subject:
            self.txt_subject.setText(subject)
        if body:
            self.txt_body.setPlainText(body)

    def _on_generate_ai_pitch(self):
        """Generates AI pitch using background worker."""
        comp = self.txt_company.text().strip()
        pos = self.txt_job_title.text().strip()
        recruiter = self.txt_contact_name.text().strip() or None
        resume_id = self.cmb_resume.currentData()
        instructions = self.txt_ai_instructions.text().strip() or None

        if not comp or not pos:
            self.lbl_status.setText("Enter Company and Position first.")
            ModernPopup.information(
                self,
                "Context Required",
                "Please enter both a Target Company and Position Title to generate an AI pitch.",
            )
            return

        self.btn_ai_pitch.setEnabled(False)
        self.btn_ai_pitch.setText("✨ Generating Pitch...")
        self.lbl_status.setText("Generating tailored pitch with AI...")

        self._ai_worker = _AIPitchWorker(
            company_name=comp,
            job_title=pos,
            recruiter_name=recruiter,
            resume_id=resume_id,
            custom_instructions=instructions,
        )
        self._ai_worker.finished.connect(self._on_ai_pitch_finished)
        self._ai_worker.error.connect(self._on_ai_pitch_error)
        self._ai_worker.start()

    def _on_ai_pitch_finished(self, result: dict):
        self.btn_ai_pitch.setEnabled(True)
        self.btn_ai_pitch.setText("✨ Generate AI Pitch")
        self.lbl_status.setText("AI pitch generated.")

        subj = result.get("subject")
        body = result.get("body_text")

        if subj:
            self.txt_subject.setText(subj)
        if body:
            self.txt_body.setPlainText(body)

    def _on_ai_pitch_error(self, err: str):
        self.btn_ai_pitch.setEnabled(True)
        self.btn_ai_pitch.setText("✨ Generate AI Pitch")
        self.lbl_status.setText(f"AI Pitch error: {err}")
        ModernPopup.warning(self, "AI Generation Issue", f"Pitch generation failed:\n\n{err}")

    def _on_refine_body(self):
        """Refines existing email body with AI."""
        current_text = self.txt_body.toPlainText().strip()
        if not current_text:
            self.lbl_status.setText("Enter or generate an email draft before refining.")
            return

        instructions = self.txt_ai_instructions.text().strip() or None
        comp = self.txt_company.text().strip()
        pos = self.txt_job_title.text().strip()

        self.btn_refine_body.setEnabled(False)
        self.btn_refine_body.setText("✨ Refining...")
        self.lbl_status.setText("Refining email draft with AI...")

        self._refine_worker = _AIRefineWorker(
            outreach_service=self.outreach_service,
            current_body=current_text,
            instructions=instructions,
            company_name=comp,
            job_title=pos,
        )
        self._refine_worker.finished.connect(self._on_refine_finished)
        self._refine_worker.error.connect(self._on_refine_error)
        self._refine_worker.start()

    def _on_refine_finished(self, result: dict):
        self.btn_refine_body.setEnabled(True)
        self.btn_refine_body.setText("✨ Refine with AI")
        self.lbl_status.setText("Email refined successfully.")
        refined = result.get("body_text")
        if refined:
            self.txt_body.setPlainText(refined)

    def _on_refine_error(self, err: str):
        self.btn_refine_body.setEnabled(True)
        self.btn_refine_body.setText("✨ Refine with AI")
        self.lbl_status.setText(f"Refinement error: {err}")
        ModernPopup.warning(self, "AI Refinement Issue", f"Refinement failed:\n\n{err}")

    # -------------------------------------------------------------------------
    # Dispatch & Validation
    # -------------------------------------------------------------------------

    def _validate_inputs(self, show_dialog: bool = True) -> bool:
        """Validates all mandatory fields prior to sending."""
        comp = self.txt_company.text().strip()
        pos = self.txt_job_title.text().strip()
        email = self.txt_contact_email.text().strip()
        subj = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()
        is_interactive = show_dialog and os.environ.get("QT_QPA_PLATFORM") != "offscreen"

        if not comp:
            self.lbl_status.setText("Target Company is required.")
            if is_interactive:
                ModernPopup.warning(self, "Required Field", "Target Company name is required to personalize your outreach.")
            self.txt_company.setFocus()
            return False

        if not pos:
            self.lbl_status.setText("Position Title is required.")
            if is_interactive:
                ModernPopup.warning(self, "Required Field", "Position Title is required.")
            self.txt_job_title.setFocus()
            return False

        if not email or "@" not in email:
            self.lbl_status.setText("A valid Recruiter Email address is required.")
            if is_interactive:
                ModernPopup.warning(self, "Invalid Recruiter Email", "Please enter a valid recipient email address (e.g. recruiter@company.com).")
            self.txt_contact_email.setFocus()
            return False

        if not subj:
            self.lbl_status.setText("Subject Line is required.")
            if is_interactive:
                ModernPopup.warning(self, "Subject Line Missing", "Subject Line is required for outreach emails.")
            self.txt_subject.setFocus()
            return False

        if not body:
            self.lbl_status.setText("Email Body cannot be empty.")
            if is_interactive:
                ModernPopup.warning(self, "Empty Message", "Email Body cannot be empty. Please write or generate a pitch first.")
            self.txt_body.setFocus()
            return False

        return True

    def _on_send_outreach(self):
        """Constructs OutreachCreateDTO and starts background dispatch."""
        if not self._validate_inputs():
            return

        # Determine cadence days
        if self.rb_cadence_std.isChecked():
            cadence_days = [4, 10, 17]
        elif self.rb_cadence_fast.isChecked():
            cadence_days = [3, 7]
        else:
            cadence_days = []

        job_id = self.cmb_jobs.currentData()
        company_name = self.txt_company.text().strip()
        job_title = self.txt_job_title.text().strip()
        job_url = self.txt_job_url.text().strip()
        contact_email = self.txt_contact_email.text().strip()

        # If new application without existing tracked job_id, auto-create in JobRepository
        if not job_id and company_name and job_title:
            try:
                from app.repositories.dto import JobCreateDTO
                dto_job = JobCreateDTO(
                    platform="email",
                    company_raw=company_name,
                    title=job_title,
                    source_url=job_url or f"email://{contact_email or 'outreach'}",
                    application_method="EMAIL",
                    apply_type="DIRECT",
                )
                new_job, _ = self.job_service.upsert_job(dto_job)
                job_id = new_job.id
            except Exception as e:
                logger.warning("Could not auto-create job in repository: %s", e)

        resume_id = self.cmb_resume.currentData()
        template_id = self.cmb_template.currentData()

        dto = OutreachCreateDTO(
            job_id=job_id,
            manual_company_name=company_name,
            manual_job_title=job_title,
            manual_job_url=job_url or None,
            contact_name=self.txt_contact_name.text().strip() or None,
            contact_email=self.txt_contact_email.text().strip(),
            resume_id=resume_id,
            template_id=template_id,
            subject=self.txt_subject.text().strip(),
            body_text=self.txt_body.toPlainText().strip(),
            followup_cadence_days=cadence_days,
            override_duplicate=False,
        )

        self.btn_send.setEnabled(False)
        self.btn_send.setText("Sending...")
        self.lbl_status.setText("Dispatching outreach via email provider...")

        self._send_worker = _OutreachSendWorker(self.outreach_service, dto)
        self._send_worker.finished.connect(self._on_send_finished)
        self._send_worker.error.connect(self._on_send_error)
        self._send_worker.start()

    def _on_send_finished(self, result: dict):
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Send Outreach Now")

        if result.get("success"):
            self.lbl_status.setText("Outreach sent successfully.")
            ModernPopup.success(
                self,
                "Outreach Dispatched",
                f"Application email dispatched to {self.txt_contact_email.text().strip()}.\n\n"
                f"Automated follow-up cadence has been scheduled.",
                button_text="Done",
            )
            self.outreach_sent.emit()
            self.accept()
        else:
            err = result.get("error", "Unknown dispatch failure")
            self.lbl_status.setText(f"Send failed: {err}")
            ModernPopup.error(self, "Dispatch Failed", f"Could not send outreach:\n\n{err}")

    def _on_send_error(self, err: str):
        self.btn_send.setEnabled(True)
        self.btn_send.setText("Send Outreach Now")
        self.lbl_status.setText(f"Error: {err}")
        ModernPopup.error(self, "Dispatch Error", f"Failed to dispatch outreach:\n\n{err}")
