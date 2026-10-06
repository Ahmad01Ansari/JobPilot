"""Bulk Recruiter Outreach Campaign Dialog for high-capacity, safe campaign dispatching.

Adheres strictly to WorkingFlow/OutreachV2.md:
- Pre-send recipient preview with individual removal and checkbox selection.
- Search and filtering across all target fields (company, role, recruiter, email).
- Ability to add fresh custom recruiter contacts on the fly.
- Editable subject and body personalization preview before dispatch.
- Anti-spam throttled delays (30s, 60s, 90s, 120s, 10s, 3s).
- Live progress feedback, pause, and cancellation controls.
- Obsidian Canvas theme styling (#0F1117, #161B22, #FF5F15).
"""

import logging
import time
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.session import SessionLocal, get_db_session
from app.repositories.email_template_repository import EmailTemplateRepository
from app.repositories.user_repository import UserRepository
from app.services.dto.outreach_enums import ConversationOpState, NextActionType
from app.services.dto.outreach_viewmodels import BulkTargetPreviewItemDTO
from app.services.outreach_service import OutreachService
from app.services.resume_service import ResumeService
from app.services.template_renderer import TemplateRenderer
from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.BulkOutreachDialog")


class AddCustomTargetDialog(QDialog):
    """Modal to quickly add a fresh recruiter contact into the campaign batch."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Add Fresh Recruiter Contact")
        self.resize(460, 340)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 600;
            }}
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        lbl_head = QLabel("➕ Add Fresh Recruiter Target")
        lbl_head.setStyleSheet("font-size: 15px; font-weight: 800; color: #F0F6FC;")
        layout.addWidget(lbl_head)

        lbl_sub = QLabel("Enter fresh recipient details to include directly in this campaign.")
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; margin-bottom: 6px;")
        layout.addWidget(lbl_sub)

        layout.addWidget(QLabel("Company Name *"))
        self.txt_company = QLineEdit()
        self.txt_company.setPlaceholderText("e.g. Acme Technologies")
        layout.addWidget(self.txt_company)

        layout.addWidget(QLabel("Position / Job Title *"))
        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("e.g. Senior RPA / Python Developer")
        layout.addWidget(self.txt_title)

        layout.addWidget(QLabel("Recruiter Name"))
        self.txt_recruiter = QLineEdit()
        self.txt_recruiter.setPlaceholderText("e.g. Sarah Jenkins (or Hiring Manager)")
        layout.addWidget(self.txt_recruiter)

        layout.addWidget(QLabel("Recruiter Email *"))
        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("e.g. careers@acme.com")
        layout.addWidget(self.txt_email)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.PointingHandCursor)
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Add to Campaign")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 18px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _validate_and_accept(self):
        comp = self.txt_company.text().strip()
        title = self.txt_title.text().strip()
        email = self.txt_email.text().strip()

        if not comp:
            QMessageBox.warning(self, "Missing Company", "Please enter a company name.")
            self.txt_company.setFocus()
            return
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a position / job title.")
            self.txt_title.setFocus()
            return
        if not email or "@" not in email or "." not in email:
            QMessageBox.warning(self, "Invalid Email", "Please enter a valid recruiter email address.")
            self.txt_email.setFocus()
            return

        self.accept()

    def get_target_dto(self) -> BulkTargetPreviewItemDTO:
        comp = self.txt_company.text().strip()
        title = self.txt_title.text().strip()
        rec = self.txt_recruiter.text().strip() or "Hiring Manager"
        email = self.txt_email.text().strip().lower()

        return BulkTargetPreviewItemDTO(
            application_id=None,
            company_name=comp,
            job_title=title,
            recruiter_name=rec,
            recruiter_email=email,
            resume_id=None,
            resume_name="",
            is_valid=True,
            validation_error=None,
            is_duplicate=False,
            duplicate_tier=None,
            current_state=ConversationOpState.NEEDS_ACTION,
            next_action_type=NextActionType.NONE,
            is_selected=True,
        )


class BulkOutreachWorker(QThread):
    """Executes safe, sequential outreach dispatch in a background thread."""

    progress = Signal(int, int, str)  # current_idx, total_count, company_name
    step_completed = Signal(int, dict)  # application_id, result_dict
    finished = Signal(dict)  # summary_dict
    error = Signal(str)

    def __init__(
        self,
        outreach_service: OutreachService,
        targets: List[BulkTargetPreviewItemDTO],
        template_id: int,
        resume_id: Optional[int],
        interval_seconds: float = 60.0,
        override_duplicate: bool = False,
        custom_subject: Optional[str] = None,
        custom_body: Optional[str] = None,
    ):
        super().__init__()
        self.outreach_service = outreach_service
        self.targets = targets
        self.template_id = template_id
        self.resume_id = resume_id
        self.interval_seconds = max(0.5, float(interval_seconds))
        self.override_duplicate = override_duplicate
        self.custom_subject = custom_subject
        self.custom_body = custom_body

        self._is_paused = False
        self._is_cancelled = False

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        total = len(self.targets)
        sent_count = 0
        failed_count = 0
        results = []

        logger.info("BulkOutreachWorker started for %d targets (delay=%.1fs)", total, self.interval_seconds)

        for idx, target in enumerate(self.targets):
            if self._is_cancelled:
                logger.info("BulkOutreachWorker cancelled by user at step %d/%d", idx, total)
                break

            while self._is_paused and not self._is_cancelled:
                time.sleep(0.2)

            if self._is_cancelled:
                break

            self.progress.emit(idx + 1, total, target.company_name)

            try:
                target_info = {
                    "company_name": target.company_name,
                    "job_title": target.job_title,
                    "recruiter_name": target.recruiter_name,
                    "recruiter_email": target.recruiter_email,
                }
                res = self.outreach_service.dispatch_bulk_outreach_step(
                    application_id=target.application_id,
                    template_id=self.template_id,
                    resume_id=self.resume_id,
                    override_duplicate=self.override_duplicate,
                    custom_subject=self.custom_subject,
                    custom_body=self.custom_body,
                    target_info=target_info,
                )
                if res.get("success"):
                    sent_count += 1
                else:
                    failed_count += 1
                results.append(res)
                self.step_completed.emit(target.application_id or 0, res)
            except Exception as e:
                logger.error("Error dispatching bulk step for target %s: %s", target.company_name, e)
                failed_count += 1
                err_dict = {"success": False, "error": str(e), "application_id": target.application_id}
                results.append(err_dict)
                self.step_completed.emit(target.application_id or 0, err_dict)

            # Polite throttle delay between dispatches (skip on final item)
            if idx < total - 1 and not self._is_cancelled:
                time.sleep(self.interval_seconds)

        summary = {
            "total": total,
            "processed": len(results),
            "sent": sent_count,
            "failed": failed_count,
            "cancelled": self._is_cancelled,
            "results": results,
        }
        self.finished.emit(summary)


class BulkOutreachDialog(QDialog):
    """High-capacity, safety-controlled bulk outreach dialog."""

    campaign_dispatched = Signal()

    def __init__(
        self,
        outreach_service: OutreachService,
        resume_service: ResumeService,
        initial_targets: Optional[List[BulkTargetPreviewItemDTO]] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.outreach_service = outreach_service
        self.resume_service = resume_service
        if initial_targets is not None:
            self._targets = list(initial_targets)
        else:
            try:
                val_result = self.outreach_service.validate_bulk_targets(None)
                self._targets = list(val_result.items)
            except Exception as e:
                logger.error("Failed loading initial bulk targets: %s", e)
                self._targets = []
        self._worker: Optional[BulkOutreachWorker] = None
        self._templates_cache: List[Any] = []
        self._block_item_signals = False

        self.setWindowTitle("Bulk Recruiter Outreach Campaign")
        self.resize(920, 800)
        self._apply_dialog_styles()
        self._setup_ui()
        self._load_templates_and_resumes()
        self._update_table_and_summary()

    def _apply_dialog_styles(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {COLORS['primary']};
            }}
            QTableWidget {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                gridline-color: {COLORS['border_light']};
                color: {COLORS['text']};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 700;
                font-size: 11px;
                padding: 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QProgressBar {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                text-align: center;
                color: white;
                font-weight: 700;
                font-size: 11px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 5px;
            }}
        """)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(10)

        # 1. Header
        hdr = QHBoxLayout()
        v_title = QVBoxLayout()
        v_title.setSpacing(2)
        lbl_title = QLabel("⚡ Bulk Recruiter Campaign")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 800; color: #F0F6FC;")
        lbl_sub = QLabel("Select recipients, customize personalization template, and execute safe throttled dispatch.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        v_title.addWidget(lbl_title)
        v_title.addWidget(lbl_sub)
        hdr.addLayout(v_title)
        hdr.addStretch()

        self.lbl_stats_badge = QLabel("0 Targets")
        self.lbl_stats_badge.setStyleSheet(f"""
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
            padding: 4px 12px;
            font-size: 12px;
            font-weight: 700;
            color: #F0F6FC;
        """)
        hdr.addWidget(self.lbl_stats_badge)
        root.addLayout(hdr)

        # 2. Recipients Table Header & Toolbar
        sec_rec = QLabel("CAMPAIGN RECIPIENTS PREVIEW")
        sec_rec.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        root.addWidget(sec_rec)

        tb = QHBoxLayout()
        tb.setSpacing(8)

        self.txt_search_targets = QLineEdit()
        self.txt_search_targets.setPlaceholderText("🔍 Filter targets by company, role, recruiter, email...")
        self.txt_search_targets.textChanged.connect(self._apply_table_filters)
        tb.addWidget(self.txt_search_targets, 1)

        self.btn_select_all = QPushButton("Select All")
        self.btn_select_all.setCursor(Qt.PointingHandCursor)
        self.btn_select_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        self.btn_select_all.clicked.connect(self._select_all_targets)
        tb.addWidget(self.btn_select_all)

        self.btn_deselect_all = QPushButton("Deselect All")
        self.btn_deselect_all.setCursor(Qt.PointingHandCursor)
        self.btn_deselect_all.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_deselect_all.clicked.connect(self._deselect_all_targets)
        tb.addWidget(self.btn_deselect_all)

        self.btn_add_target = QPushButton("➕ Add Fresh Recruiter")
        self.btn_add_target.setCursor(Qt.PointingHandCursor)
        self.btn_add_target.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 95, 21, 0.15);
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']};
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
            }}
        """)
        self.btn_add_target.clicked.connect(self._open_add_custom_target_dialog)
        tb.addWidget(self.btn_add_target)

        root.addLayout(tb)

        # 3. Recipients Table
        self.table_targets = QTableWidget()
        self.table_targets.setColumnCount(7)
        self.table_targets.setHorizontalHeaderLabels([
            "Send", "Company", "Position", "Recruiter", "Email", "Validation", "Action"
        ])
        header = self.table_targets.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table_targets.verticalHeader().setVisible(False)
        self.table_targets.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_targets.setMinimumHeight(160)
        self.table_targets.setMaximumHeight(220)
        self.table_targets.itemChanged.connect(self._on_table_item_changed)
        root.addWidget(self.table_targets)

        # 4. Campaign Configuration Options
        cfg_frame = QFrame()
        cfg_frame.setStyleSheet(f"background-color: {COLORS['surface_alt']}; border: 1px solid {COLORS['border_light']}; border-radius: 8px; padding: 10px;")
        cfg_layout = QGridLayout(cfg_frame)
        cfg_layout.setContentsMargins(10, 8, 10, 8)
        cfg_layout.setSpacing(10)

        cfg_layout.addWidget(QLabel("Email Template Preset *"), 0, 0)
        cfg_layout.addWidget(QLabel("Attached Resume *"), 0, 1)
        cfg_layout.addWidget(QLabel("Throttling Interval (Anti-Spam)"), 0, 2)

        self.cmb_template = QComboBox()
        self.cmb_template.currentIndexChanged.connect(self._on_template_changed)
        cfg_layout.addWidget(self.cmb_template, 1, 0)

        self.cmb_resume = QComboBox()
        cfg_layout.addWidget(self.cmb_resume, 1, 1)

        self.cmb_interval = QComboBox()
        self.cmb_interval.addItem("1.0 Minute delay (Recommended)", 60.0)
        self.cmb_interval.addItem("30 Seconds delay (Safe)", 30.0)
        self.cmb_interval.addItem("1.5 Minutes delay (Anti-Spam)", 90.0)
        self.cmb_interval.addItem("2.0 Minutes delay (Conservative)", 120.0)
        self.cmb_interval.addItem("10 Seconds delay (Standard)", 10.0)
        self.cmb_interval.addItem("3.0 Seconds delay (Dev / Testing)", 3.0)
        self.cmb_interval.addItem("1.0 Second delay (Dev / Fast)", 1.0)
        self.cmb_interval.setCurrentIndex(0)
        cfg_layout.addWidget(self.cmb_interval, 1, 2)

        root.addWidget(cfg_frame)

        # 5. Template Personalization Preview Box (Editable)
        sec_prev = QHBoxLayout()
        lbl_p_title = QLabel("PERSONALIZATION PREVIEW & IN-LINE EDITING")
        lbl_p_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        sec_prev.addWidget(lbl_p_title)
        sec_prev.addStretch()

        lbl_hint = QLabel("💡 Subject and body are editable. Placeholders like {{company_name}}, {{job_title}}, {{recruiter_name}} are personalized per recipient.")
        lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-style: italic;")
        sec_prev.addWidget(lbl_hint)
        root.addLayout(sec_prev)

        prev_box = QVBoxLayout()
        prev_box.setSpacing(6)

        self.txt_preview_subject = QLineEdit()
        self.txt_preview_subject.setReadOnly(False)
        self.txt_preview_subject.setPlaceholderText("Subject line (e.g. Application: {{job_title}} - {{candidate_name}})...")
        prev_box.addWidget(self.txt_preview_subject)

        self.txt_preview_body = QTextEdit()
        self.txt_preview_body.setReadOnly(False)
        self.txt_preview_body.setPlaceholderText("Template body text...")
        self.txt_preview_body.setFixedHeight(105)
        prev_box.addWidget(self.txt_preview_body)
        root.addLayout(prev_box)

        # 6. Progress Section
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        self.lbl_status = QLabel("Ready to launch bulk campaign.")
        self.lbl_status.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        root.addWidget(self.lbl_status)

        # 7. Action Footer
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.setVisible(False)
        self.btn_pause.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
            }}
        """)
        self.btn_pause.clicked.connect(self._toggle_pause)
        footer.addWidget(self.btn_pause)

        self.btn_cancel_worker = QPushButton("⏹ Cancel Campaign")
        self.btn_cancel_worker.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_worker.setVisible(False)
        self.btn_cancel_worker.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(248, 81, 73, 0.15);
                color: {COLORS['danger']};
                border: 1px solid {COLORS['danger']}80;
                border-radius: 6px;
                padding: 7px 14px;
                font-weight: 600;
            }}
        """)
        self.btn_cancel_worker.clicked.connect(self._cancel_worker)
        footer.addWidget(self.btn_cancel_worker)

        footer.addStretch()

        self.btn_close = QPushButton("Close")
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet(f"""
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
        self.btn_close.clicked.connect(self.close)
        footer.addWidget(self.btn_close)

        self.btn_dispatch = QPushButton("🚀 Dispatch Campaign Now")
        self.btn_dispatch.setCursor(Qt.PointingHandCursor)
        self.btn_dispatch.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 22px;
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
        self.btn_dispatch.clicked.connect(self._start_dispatch)
        footer.addWidget(self.btn_dispatch)

        root.addLayout(footer)

    def _load_templates_and_resumes(self):
        # 1. Resumes
        try:
            with get_db_session(SessionLocal) as s:
                u = UserRepository(s).get_primary_user()
                uid = u.id if u else 1
            resumes = self.resume_service.list_resumes(user_id=uid)
            def_idx = -1
            for r in resumes:
                title = f"{r.name} ({r.role_target or 'General'})"
                if r.is_default:
                    title += " [Default]"
                self.cmb_resume.addItem(title, r.id)
                if r.is_default:
                    def_idx = self.cmb_resume.count() - 1
            if def_idx >= 0:
                self.cmb_resume.setCurrentIndex(def_idx)
        except Exception as e:
            logger.warning("Failed loading resumes for bulk dialog: %s", e)

        # 2. Templates
        try:
            with get_db_session(SessionLocal) as s:
                repo = EmailTemplateRepository(s)
                repo.seed_defaults_if_empty()
                self._templates_cache = repo.list_all(include_inactive=False)
                for t in self._templates_cache:
                    self.cmb_template.addItem(t.name, t)
        except Exception as e:
            logger.warning("Failed loading templates for bulk dialog: %s", e)

    def _update_table_and_summary(self):
        self._block_item_signals = True
        self.table_targets.setRowCount(len(self._targets))

        for row, t in enumerate(self._targets):
            # Column 0: Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk_item.setCheckState(Qt.Checked if t.is_selected else Qt.Unchecked)
            self.table_targets.setItem(row, 0, chk_item)

            # Columns 1-4: Details
            self.table_targets.setItem(row, 1, QTableWidgetItem(t.company_name or "—"))
            self.table_targets.setItem(row, 2, QTableWidgetItem(t.job_title or "—"))
            self.table_targets.setItem(row, 3, QTableWidgetItem(t.recruiter_name or "Hiring Team"))
            self.table_targets.setItem(row, 4, QTableWidgetItem(t.recruiter_email or "No email"))

            # Column 5: Validation tag
            if t.is_valid:
                v_item = QTableWidgetItem("✓ Ready")
                v_item.setForeground(Qt.green)
            else:
                v_item = QTableWidgetItem(f"⛔ {t.validation_error or 'Blocked'}")
                v_item.setForeground(Qt.red)
            self.table_targets.setItem(row, 5, v_item)

            # Column 6: Remove button
            btn_remove = QPushButton("✕ Remove")
            btn_remove.setCursor(Qt.PointingHandCursor)
            btn_remove.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 2px 8px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    color: {COLORS['danger']};
                    border-color: {COLORS['danger']};
                }}
            """)
            btn_remove.clicked.connect(lambda _, idx=row: self._remove_target_at(idx))
            self.table_targets.setCellWidget(row, 6, btn_remove)

        self._block_item_signals = False
        self._apply_table_filters(self.txt_search_targets.text())
        self._update_dispatch_button_state()
        self._render_sample_preview()

    def _update_dispatch_button_state(self):
        valid_count = sum(1 for t in self._targets if t.is_valid)
        blocked_count = len(self._targets) - valid_count
        selected_valid = sum(1 for t in self._targets if t.is_valid and t.is_selected)

        self.lbl_stats_badge.setText(
            f"{len(self._targets)} Total • {selected_valid} Selected Valid • {blocked_count} Blocked"
        )
        self.btn_dispatch.setText(f"🚀 Dispatch Campaign ({selected_valid} Valid Targets)")
        self.btn_dispatch.setEnabled(selected_valid > 0)

    def _on_table_item_changed(self, item: QTableWidgetItem):
        if self._block_item_signals or item.column() != 0:
            return
        row = item.row()
        if 0 <= row < len(self._targets):
            self._targets[row].is_selected = (item.checkState() == Qt.Checked)
            self._update_dispatch_button_state()

    def _apply_table_filters(self, text: str):
        query = (text or "").strip().lower()
        for row in range(self.table_targets.rowCount()):
            if row >= len(self._targets):
                continue
            t = self._targets[row]
            match = True
            if query:
                match = (
                    query in (t.company_name or "").lower()
                    or query in (t.job_title or "").lower()
                    or query in (t.recruiter_name or "").lower()
                    or query in (t.recruiter_email or "").lower()
                )
            self.table_targets.setRowHidden(row, not match)

    def _select_all_targets(self):
        self._block_item_signals = True
        for row in range(self.table_targets.rowCount()):
            if not self.table_targets.isRowHidden(row) and row < len(self._targets):
                self._targets[row].is_selected = True
                item = self.table_targets.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked)
        self._block_item_signals = False
        self._update_dispatch_button_state()

    def _deselect_all_targets(self):
        self._block_item_signals = True
        for row in range(self.table_targets.rowCount()):
            if row < len(self._targets):
                self._targets[row].is_selected = False
                item = self.table_targets.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
        self._block_item_signals = False
        self._update_dispatch_button_state()

    def _open_add_custom_target_dialog(self):
        dlg = AddCustomTargetDialog(self)
        if dlg.exec() == QDialog.Accepted:
            new_target = dlg.get_target_dto()
            self._targets.insert(0, new_target)
            logger.info("Added fresh custom target: %s (%s)", new_target.company_name, new_target.recruiter_email)
            self._update_table_and_summary()

    def _remove_target_at(self, index: int):
        if 0 <= index < len(self._targets):
            removed = self._targets.pop(index)
            logger.info("Removed target from bulk preview: %s", removed.company_name)
            self._update_table_and_summary()

    def _on_template_changed(self, idx: int):
        self._render_sample_preview()

    def _render_sample_preview(self):
        tmpl = self.cmb_template.currentData()
        if not tmpl:
            self.txt_preview_subject.clear()
            self.txt_preview_body.clear()
            return

        sample = self._targets[0] if self._targets else None
        comp = sample.company_name if sample else "Acme Technologies"
        title = sample.job_title if sample else "Senior RPA Developer"
        rec = sample.recruiter_name if sample else "Sarah Jenkins"

        ctx = {
            "candidate_name": "Candidate",
            "candidate_email": "candidate@example.com",
            "candidate_phone": "+1 555-0199",
            "company_name": comp,
            "job_title": title,
            "recruiter_name": rec,
            "portfolio_url": "https://github.com/ahmadraza",
            "skills": "Python, RPA, Automation",
            "years_of_experience": "4",
            "platform": "JobPilot Direct Outreach",
        }
        subj, _ = TemplateRenderer.render(tmpl.subject_template, ctx, strict=False)
        body, _ = TemplateRenderer.render(tmpl.body_template, ctx, strict=False)

        self.txt_preview_subject.setText(subj)
        self.txt_preview_body.setPlainText(body)

    def _start_dispatch(self):
        selected_targets = [t for t in self._targets if t.is_valid and t.is_selected]
        if not selected_targets:
            QMessageBox.warning(
                self,
                "No Selected Targets",
                "Please select at least one valid recipient target to dispatch.",
            )
            return

        tmpl = self.cmb_template.currentData()
        if not tmpl:
            QMessageBox.warning(self, "Template Required", "Please select an email template.")
            return

        resume_id = self.cmb_resume.currentData()
        interval = float(self.cmb_interval.currentData() or 60.0)
        interval_desc = self.cmb_interval.currentText()

        # Custom subject and body overrides
        custom_subj = self.txt_preview_subject.text().strip() or None
        custom_body = self.txt_preview_body.toPlainText().strip() or None

        # Safety confirmation
        confirm = QMessageBox.question(
            self,
            "Confirm Bulk Outreach",
            f"Are you sure you want to dispatch outreach to {len(selected_targets)} selected recruiter(s)?\n\n"
            f"• Template: {tmpl.name}\n"
            f"• Throttling Interval: {interval_desc}\n"
            f"• Attached Resume ID: {resume_id or 'None'}\n\n"
            "This will send real emails via your configured SMTP account.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if confirm != QMessageBox.Yes:
            return

        # Lock UI
        self.btn_dispatch.setEnabled(False)
        self.btn_close.setEnabled(False)
        self.cmb_template.setEnabled(False)
        self.cmb_resume.setEnabled(False)
        self.cmb_interval.setEnabled(False)
        self.txt_preview_subject.setEnabled(False)
        self.txt_preview_body.setEnabled(False)
        self.txt_search_targets.setEnabled(False)
        self.btn_select_all.setEnabled(False)
        self.btn_deselect_all.setEnabled(False)
        self.btn_add_target.setEnabled(False)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_targets))
        self.progress_bar.setValue(0)

        self.btn_pause.setVisible(True)
        self.btn_cancel_worker.setVisible(True)
        self.lbl_status.setText(f"Initializing bulk dispatch for {len(selected_targets)} selected targets...")

        self._worker = BulkOutreachWorker(
            outreach_service=self.outreach_service,
            targets=selected_targets,
            template_id=tmpl.id,
            resume_id=resume_id,
            interval_seconds=interval,
            override_duplicate=False,
            custom_subject=custom_subj,
            custom_body=custom_body,
        )
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.step_completed.connect(self._on_step_completed)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_progress(self, current: int, total: int, company: str):
        self.progress_bar.setValue(current)
        self.lbl_status.setText(f"Sending {current} of {total}: {company}...")

    def _on_step_completed(self, app_id: int, res: dict):
        logger.info("Dispatched target app_id=%d: success=%s", app_id, res.get("success"))

    def _toggle_pause(self):
        if not self._worker:
            return
        if self._worker._is_paused:
            self._worker.resume()
            self.btn_pause.setText("⏸ Pause")
            self.lbl_status.setText("Campaign resumed.")
        else:
            self._worker.pause()
            self.btn_pause.setText("▶ Resume")
            self.lbl_status.setText("Campaign paused by user.")

    def _cancel_worker(self):
        if self._worker:
            self._worker.cancel()
            self.lbl_status.setText("Stopping campaign after current send finishes...")

    def _on_worker_finished(self, summary: dict):
        self.btn_pause.setVisible(False)
        self.btn_cancel_worker.setVisible(False)
        self.btn_close.setEnabled(True)
        self.progress_bar.setValue(summary.get("processed", 0))

        # Re-enable inputs
        self.cmb_template.setEnabled(True)
        self.cmb_resume.setEnabled(True)
        self.cmb_interval.setEnabled(True)
        self.txt_preview_subject.setEnabled(True)
        self.txt_preview_body.setEnabled(True)
        self.txt_search_targets.setEnabled(True)
        self.btn_select_all.setEnabled(True)
        self.btn_deselect_all.setEnabled(True)
        self.btn_add_target.setEnabled(True)

        sent = summary.get("sent", 0)
        failed = summary.get("failed", 0)
        total = summary.get("total", 0)
        was_cancelled = summary.get("cancelled", False)

        status_prefix = "⏹ Campaign Cancelled." if was_cancelled else "🎉 Campaign Complete."
        self.lbl_status.setText(f"{status_prefix} Sent: {sent} | Failed: {failed} | Total: {total}")

        msg = (
            f"{status_prefix}\n\n"
            f"• Successfully Dispatched: {sent}\n"
            f"• Failed: {failed}\n"
            f"• Processed: {summary.get('processed', 0)} of {total}\n"
        )
        QMessageBox.information(self, "Campaign Complete", msg)
        self.campaign_dispatched.emit()
