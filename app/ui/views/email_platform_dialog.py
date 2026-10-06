"""Email Outreach Configuration Dialog.

Provides comprehensive platform configuration for direct email outreach, including:
1. Account & Gmail Sync Label settings (with live SMTP/IMAP connection tester).
2. Template Library Management (full CRUD: create, edit, duplicate, delete with variable pills and live preview).
3. Follow-Up Schedule Engine (cadence intervals, auto-pause safeguards, daily rate limits).
4. Sender & Message Defaults (sender name, default resume attachment, professional signature).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QSize, QThread, Signal, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.session import SessionLocal, get_db_session
from app.repositories.email_template_repository import EmailTemplateRepository
from app.services.platform_service import PlatformService
from app.services.secrets_service import SecretsService
from app.services.template_renderer import TemplateRenderer
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import StatusBadge

logger = logging.getLogger(__name__)

# Resolve SVG icon paths for password visibility toggle
_ICONS_DIR = Path(__file__).resolve().parent.parent / "assets" / "icons"
_EYE_ICON_PATH = str(_ICONS_DIR / "eye.svg")
_EYE_OFF_ICON_PATH = str(_ICONS_DIR / "eye_off.svg")


class EmailTestWorker(QThread):
    """Background worker to test SMTP and IMAP connection without blocking the UI."""

    result_ready = Signal(bool, str)

    def __init__(
        self,
        user: str,
        password: str,
        smtp_host: str,
        smtp_port: int,
        smtp_use_tls: bool,
        smtp_use_ssl: bool,
        imap_host: str,
        imap_port: int,
        imap_use_ssl: bool,
    ):
        super().__init__()
        self.user = user
        self.password = password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_use_tls = smtp_use_tls
        self.smtp_use_ssl = smtp_use_ssl
        self.imap_host = imap_host
        self.imap_port = imap_port
        self.imap_use_ssl = imap_use_ssl

    def run(self) -> None:
        try:
            from app.services.secrets_service import SecretsService
            sec = SecretsService()
            success, message = sec.test_email_connection(
                user=self.user,
                password=self.password,
                smtp_host=self.smtp_host,
                smtp_port=self.smtp_port,
                smtp_use_tls=self.smtp_use_tls,
                smtp_use_ssl=self.smtp_use_ssl,
                imap_host=self.imap_host,
                imap_port=self.imap_port,
                imap_use_ssl=self.imap_use_ssl,
            )
            self.result_ready.emit(success, message)
        except Exception as e:
            self.result_ready.emit(False, str(e))


class TemplateEditDialog(QDialog):
    """Interactive modal dialog for creating and editing email templates with variable insertion."""

    AVAILABLE_VARIABLES = [
        ("Candidate Name", "{{candidate_name}}"),
        ("Recruiter Name", "{{recruiter_name}}"),
        ("Company Name", "{{company_name}}"),
        ("Job Title", "{{job_title}}"),
        ("Skills", "{{skills}}"),
        ("Portfolio URL", "{{portfolio_url}}"),
        ("Experience (Yrs)", "{{years_of_experience}}"),
        ("Candidate Email", "{{candidate_email}}"),
        ("Candidate Phone", "{{candidate_phone}}"),
    ]

    def __init__(
        self,
        template: Optional[Any] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.template = template
        self.last_focused_input: Optional[QWidget] = None

        self.setWindowTitle("Edit Template" if template else "Create Custom Template")
        self.setMinimumWidth(680)
        self.resize(720, 800)
        self._apply_dialog_styles()
        self._setup_ui()
        if self.template:
            self._load_template_data()
        self._update_preview()

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QLineEdit, QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 10px;
                font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
                font-size: 13px;
                line-height: 1.4;
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # Dialog Header
        lbl_head = QLabel("Edit Outreach Template" if self.template else "Create New Outreach Template")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        root_layout.addWidget(lbl_head)

        lbl_sub = QLabel("Craft your personalized message with dynamic variables. Changes update the live preview below.")
        lbl_sub.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; margin-bottom: 4px;")
        root_layout.addWidget(lbl_sub)

        # Metadata Row (Name + Category)
        meta_grid = QGridLayout()
        meta_grid.setSpacing(12)

        lbl_name = QLabel("Template Name *")
        lbl_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Senior RPA Direct Pitch")
        self.txt_name.installEventFilter(self)

        lbl_cat = QLabel("Category")
        lbl_cat.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        self.cmb_category = QComboBox()
        self.cmb_category.addItems(["JOB_APPLICATION", "FOLLOW_UP", "NETWORKING", "OTHER"])

        meta_grid.addWidget(lbl_name, 0, 0)
        meta_grid.addWidget(self.txt_name, 1, 0)
        meta_grid.addWidget(lbl_cat, 0, 1)
        meta_grid.addWidget(self.cmb_category, 1, 1)
        root_layout.addLayout(meta_grid)

        # Subject Line Input
        lbl_subj = QLabel("Subject Line Template *")
        lbl_subj.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        root_layout.addWidget(lbl_subj)

        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText("e.g. Application: {{job_title}} - {{candidate_name}}")
        self.txt_subject.textChanged.connect(self._update_preview)
        self.txt_subject.installEventFilter(self)
        root_layout.addWidget(self.txt_subject)

        # Variable Insert Toolbar (Pill Buttons)
        lbl_vars = QLabel("Insert Variable (Click to append at cursor):")
        lbl_vars.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        root_layout.addWidget(lbl_vars)

        vars_scroll = QScrollArea()
        vars_scroll.setFixedHeight(44)
        vars_scroll.setWidgetResizable(True)
        vars_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        vars_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        vars_container = QWidget()
        vars_container.setStyleSheet("background: transparent;")
        vars_layout = QHBoxLayout(vars_container)
        vars_layout.setContentsMargins(0, 2, 0, 2)
        vars_layout.setSpacing(6)

        for label, token in self.AVAILABLE_VARIABLES:
            btn_var = QPushButton(f"+ {label}")
            btn_var.setCursor(Qt.PointingHandCursor)
            btn_var.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['accent']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 12px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['accent']};
                    color: #FFFFFF;
                    border-color: {COLORS['accent']};
                }}
            """)
            btn_var.clicked.connect(lambda _, t=token: self._insert_variable(t))
            vars_layout.addWidget(btn_var)

        vars_layout.addStretch()
        vars_scroll.setWidget(vars_container)
        root_layout.addWidget(vars_scroll)

        # Body Text Editor
        lbl_body = QLabel("Email Body Template *")
        lbl_body.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        root_layout.addWidget(lbl_body)

        self.txt_body = QTextEdit()
        self.txt_body.setPlaceholderText(
            "Hi {{recruiter_name}},\n\n"
            "I noticed that {{company_name}} is hiring for a {{job_title}}...\n\n"
            "Best regards,\n{{candidate_name}}"
        )
        self.txt_body.textChanged.connect(self._update_preview)
        self.txt_body.installEventFilter(self)
        root_layout.addWidget(self.txt_body, 1)

        # Real-time Live Preview Card
        preview_box = QFrame()
        preview_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']}90;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setContentsMargins(12, 10, 12, 10)
        prev_layout.setSpacing(4)

        lbl_prev_title = QLabel("LIVE RENDER PREVIEW (Sample Candidate Context)")
        lbl_prev_title.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {COLORS['accent']}; letter-spacing: 0.5px;")
        prev_layout.addWidget(lbl_prev_title)

        self.lbl_preview_subject = QLabel("Subject: ")
        self.lbl_preview_subject.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_preview_subject.setWordWrap(True)
        prev_layout.addWidget(self.lbl_preview_subject)

        self.txt_preview_body = QLabel("")
        self.txt_preview_body.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-family: sans-serif;")
        self.txt_preview_body.setWordWrap(True)
        self.txt_preview_body.setMaximumHeight(90)
        prev_layout.addWidget(self.txt_preview_body)

        root_layout.addWidget(preview_box)

        # Dialog Buttons
        btn_box = QDialogButtonBox()
        self.btn_cancel = btn_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        self.btn_save = btn_box.addButton("Save Template", QDialogButtonBox.AcceptRole)

        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 20px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #E04F0E;
            }}
        """)

        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self._validate_and_save)
        root_layout.addWidget(btn_box)

        # Default focused input
        self.last_focused_input = self.txt_body

    def eventFilter(self, watched: Any, event: Any) -> bool:
        if event.type() == QEvent.FocusIn:
            if watched in (self.txt_subject, self.txt_body):
                self.last_focused_input = watched
        return super().eventFilter(watched, event)

    def _insert_variable(self, token: str) -> None:
        target = self.last_focused_input or self.txt_body
        if isinstance(target, QLineEdit):
            target.insert(token)
        elif isinstance(target, QTextEdit):
            target.insertPlainText(token)
        target.setFocus()
        self._update_preview()

    def _update_preview(self) -> None:
        sample_context = {
            "candidate_name": "Candidate",
            "candidate_email": "candidate@example.com",
            "candidate_phone": "+1 555-0199",
            "recruiter_name": "Sarah Jenkins",
            "company_name": "Acme Innovations",
            "job_title": "Senior RPA / Python Automation Engineer",
            "skills": "UiPath, Python, Selenium, Automation Anywhere",
            "portfolio_url": "",
            "years_of_experience": "5",
        }
        subj_raw = self.txt_subject.text().strip() or "(No subject)"
        body_raw = self.txt_body.toPlainText().strip() or "(No body content)"

        subj_res, _ = TemplateRenderer.render(subj_raw, sample_context, strict=False)
        body_res, _ = TemplateRenderer.render(body_raw, sample_context, strict=False)

        self.lbl_preview_subject.setText(f"Subject: {subj_res}")
        # Format multiline preview neatly
        snippet = body_res.replace("\n", "  ")
        if len(snippet) > 220:
            snippet = snippet[:220] + "..."
        self.txt_preview_body.setText(snippet)

    def _load_template_data(self) -> None:
        if not self.template:
            return
        self.txt_name.setText(self.template.name or "")
        idx = self.cmb_category.findText(self.template.category or "JOB_APPLICATION")
        if idx >= 0:
            self.cmb_category.setCurrentIndex(idx)
        self.txt_subject.setText(self.template.subject_template or "")
        self.txt_body.setPlainText(self.template.body_template or "")

    def _validate_and_save(self) -> None:
        name = self.txt_name.text().strip()
        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()
        category = self.cmb_category.currentText()

        if not name:
            QMessageBox.warning(self, "Validation Error", "Template Name is required.")
            self.txt_name.setFocus()
            return
        if not subject:
            QMessageBox.warning(self, "Validation Error", "Subject Line is required.")
            self.txt_subject.setFocus()
            return
        if not body:
            QMessageBox.warning(self, "Validation Error", "Email Body cannot be empty.")
            self.txt_body.setFocus()
            return

        with get_db_session() as session:
            repo = EmailTemplateRepository(session)
            if self.template:
                repo.update(
                    template_id=self.template.id,
                    name=name,
                    subject_template=subject,
                    body_template=body,
                    category=category,
                )
            else:
                import re
                slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.lower()).strip("_")
                key = f"custom_{slug}"
                # Ensure unique key
                existing = repo.get_by_key(key)
                if existing:
                    import uuid
                    key = f"{key}_{uuid.uuid4().hex[:6]}"
                repo.create(
                    key=key,
                    name=name,
                    subject_template=subject,
                    body_template=body,
                    category=category,
                )
            session.commit()

        self.accept()


class EmailOutreachConfigDialog(QDialog):
    """Primary configuration dialog for the Email Outreach service on the Platforms view."""

    def __init__(
        self,
        service: Optional[PlatformService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or PlatformService()
        self.secrets = SecretsService()
        self.test_worker: Optional[EmailTestWorker] = None

        self.setWindowTitle("Configure Email Outreach & Automation")
        self.setMinimumWidth(640)
        self.resize(680, 800)
        self._apply_dialog_styles()
        self._setup_ui()
        self._load_data()

    def _apply_dialog_styles(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
            }}
            QTabWidget::pane {{
                border: 1px solid {COLORS['border']};
                background-color: {COLORS['surface']};
                border-radius: 8px;
                padding: 14px;
            }}
            QTabBar::tab {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 16px;
                margin-right: 4px;
                font-weight: 600;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background-color: {COLORS['surface']};
                color: {COLORS['accent']};
                border-color: {COLORS['border']};
                border-bottom: 2px solid {COLORS['accent']};
            }}
            QTabBar::tab:hover:!selected {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['border_light']};
            }}
        """)

    def _setup_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 18, 20, 18)
        root_layout.setSpacing(14)

        # Header Title
        header_row = QHBoxLayout()
        icon = QLabel("✉️")
        icon.setStyleSheet(f"font-size: 26px; background: {COLORS['surface_alt']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 6px;")
        header_row.addWidget(icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        lbl_title = QLabel("Email Outreach & Gmail Synchronization")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        lbl_subtitle = QLabel("Configure 2-way Gmail sync labels, custom pitches, cadence schedules, and message safeguards.")
        lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        title_col.addWidget(lbl_title)
        title_col.addWidget(lbl_subtitle)
        header_row.addLayout(title_col, 1)

        root_layout.addLayout(header_row)

        # Tabs Layout
        self.tabs = QTabWidget()
        self.tab_sync = QWidget()
        self.tab_templates = QWidget()
        self.tab_schedule = QWidget()
        self.tab_sender = QWidget()

        self._setup_sync_tab()
        self._setup_templates_tab()
        self._setup_schedule_tab()
        self._setup_sender_tab()

        self.tabs.addTab(self.tab_sync, "📬 Account & Gmail Sync")
        self.tabs.addTab(self.tab_templates, "📝 Email Templates")
        self.tabs.addTab(self.tab_schedule, "⏱️ Follow-Up Schedule")
        self.tabs.addTab(self.tab_sender, "👤 Sender Defaults")
        root_layout.addWidget(self.tabs, 1)

        # Bottom Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("💾 Save Outreach Settings")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 22px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #E04F0E;
            }}
        """)
        self.btn_save.clicked.connect(self._save_settings)
        btn_box.addWidget(self.btn_save)

        root_layout.addLayout(btn_box)

    # -------------------------------------------------------------------------
    # TAB 1: Account & Gmail Sync
    # -------------------------------------------------------------------------
    def _setup_sync_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        # Sync Label Card
        label_group = self._create_section_card(
            "🏷️ Gmail Label Synchronization",
            "Emails created or labeled with this tag in your Gmail will automatically sync into JobPilot.",
        )
        l_form = QFormLayout()
        l_form.setSpacing(10)

        self.txt_sync_label = QLineEdit()
        self.txt_sync_label.setPlaceholderText("RPA-Developer-Application")
        l_form.addRow("Gmail Sync Label *:", self.txt_sync_label)

        self.txt_reply_folder = QLineEdit()
        self.txt_reply_folder.setPlaceholderText("INBOX")
        l_form.addRow("Inbound Folder:", self.txt_reply_folder)

        label_group.layout().addLayout(l_form)
        layout.addWidget(label_group)

        # Account Credentials Card
        creds_group = self._create_section_card(
            "🔑 Email Account Credentials",
            "Use your personal Gmail and a 16-character Google App Password (not your main Google account password).",
        )
        c_form = QFormLayout()
        c_form.setSpacing(10)

        self.txt_email_user = QLineEdit()
        self.txt_email_user.setPlaceholderText("e.g. user@gmail.com")
        c_form.addRow("Email Address *:", self.txt_email_user)

        # Password with show/hide toggle
        pwd_box = QHBoxLayout()
        pwd_box.setSpacing(6)
        self.txt_email_pwd = QLineEdit()
        self.txt_email_pwd.setEchoMode(QLineEdit.Password)
        self.txt_email_pwd.setPlaceholderText("••••••••••••••••")
        pwd_box.addWidget(self.txt_email_pwd, 1)

        self.btn_toggle_pwd = QPushButton()
        self.btn_toggle_pwd.setIcon(QIcon(_EYE_ICON_PATH))
        self.btn_toggle_pwd.setIconSize(QSize(16, 16))
        self.btn_toggle_pwd.setFixedSize(36, 36)
        self.btn_toggle_pwd.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_pwd.setToolTip("Toggle password visibility")
        self._apply_eye_btn_default_style()
        self.btn_toggle_pwd.clicked.connect(self._toggle_pwd_visibility)
        pwd_box.addWidget(self.btn_toggle_pwd)

        c_form.addRow("App Password *:", pwd_box)
        creds_group.layout().addLayout(c_form)
        layout.addWidget(creds_group)

        # Advanced Server Settings Card (Collapsible)
        adv_group = self._create_section_card(
            "⚙️ Mail Server Endpoints",
            "Standard protocol settings for sending (SMTP) and receiving (IMAP).",
        )
        adv_grid = QGridLayout()
        adv_grid.setSpacing(10)

        adv_grid.addWidget(QLabel("SMTP Host:"), 0, 0)
        self.txt_smtp_host = QLineEdit("smtp.gmail.com")
        adv_grid.addWidget(self.txt_smtp_host, 0, 1)

        adv_grid.addWidget(QLabel("SMTP Port:"), 0, 2)
        self.spn_smtp_port = QSpinBox()
        self.spn_smtp_port.setRange(1, 65535)
        self.spn_smtp_port.setValue(587)
        adv_grid.addWidget(self.spn_smtp_port, 0, 3)

        adv_grid.addWidget(QLabel("IMAP Host:"), 1, 0)
        self.txt_imap_host = QLineEdit("imap.gmail.com")
        adv_grid.addWidget(self.txt_imap_host, 1, 1)

        adv_grid.addWidget(QLabel("IMAP Port:"), 1, 2)
        self.spn_imap_port = QSpinBox()
        self.spn_imap_port.setRange(1, 65535)
        self.spn_imap_port.setValue(993)
        adv_grid.addWidget(self.spn_imap_port, 1, 3)

        self.chk_smtp_tls = QCheckBox("SMTP STARTTLS (Recommended)")
        self.chk_smtp_tls.setChecked(True)
        adv_grid.addWidget(self.chk_smtp_tls, 2, 0, 1, 2)

        self.chk_imap_ssl = QCheckBox("IMAP SSL (Port 993)")
        self.chk_imap_ssl.setChecked(True)
        adv_grid.addWidget(self.chk_imap_ssl, 2, 2, 1, 2)

        adv_group.layout().addLayout(adv_grid)
        layout.addWidget(adv_group)

        # Test Connection Action Row
        test_box = QHBoxLayout()
        test_box.setSpacing(10)

        self.btn_test_conn = QPushButton("⚡ Test Server Connection")
        self.btn_test_conn.setCursor(Qt.PointingHandCursor)
        self.btn_test_conn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
            }}
            QPushButton:disabled {{
                opacity: 0.5;
            }}
        """)
        self.btn_test_conn.clicked.connect(self._run_connection_test)
        test_box.addWidget(self.btn_test_conn)

        self.lbl_test_status = QLabel("")
        self.lbl_test_status.setStyleSheet("font-size: 12px; font-weight: 600;")
        test_box.addWidget(self.lbl_test_status, 1)

        layout.addLayout(test_box)
        layout.addStretch()

        scroll.setWidget(container)
        v = QVBoxLayout(self.tab_sync)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scroll)

    # -------------------------------------------------------------------------
    # TAB 2: Email Templates
    # -------------------------------------------------------------------------
    def _setup_templates_tab(self) -> None:
        layout = QVBoxLayout(self.tab_templates)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        # Header Row with Count & Add Button
        head_row = QHBoxLayout()
        self.lbl_tmpl_count = QLabel("Active Templates (4)")
        self.lbl_tmpl_count.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
        head_row.addWidget(self.lbl_tmpl_count)
        head_row.addStretch()

        btn_add = QPushButton("➕ Create Template")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #E04F0E;
            }}
        """)
        btn_add.clicked.connect(self._create_new_template)
        head_row.addWidget(btn_add)
        layout.addLayout(head_row)

        # Scrollable Templates List
        self.scroll_tmpls = QScrollArea()
        self.scroll_tmpls.setWidgetResizable(True)

        self.tmpls_container = QWidget()
        self.tmpls_layout = QVBoxLayout(self.tmpls_container)
        self.tmpls_layout.setContentsMargins(0, 4, 0, 4)
        self.tmpls_layout.setSpacing(8)
        self.tmpls_layout.setAlignment(Qt.AlignTop)

        self.scroll_tmpls.setWidget(self.tmpls_container)
        layout.addWidget(self.scroll_tmpls, 1)

    def _render_templates_list(self) -> None:
        # Clear existing rows
        while self.tmpls_layout.count():
            item = self.tmpls_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        with get_db_session() as session:
            repo = EmailTemplateRepository(session)
            repo.seed_defaults_if_empty()
            templates = repo.list_all(include_inactive=True)

        self.lbl_tmpl_count.setText(f"Templates ({len(templates)})")

        for t in templates:
            card = self._create_template_row(t)
            self.tmpls_layout.addWidget(card)

    def _create_template_row(self, t: Any) -> QWidget:
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QFrame:hover {{
                border-color: {COLORS['border_light']};
            }}
        """)
        r_layout = QHBoxLayout(row)
        r_layout.setContentsMargins(14, 10, 14, 10)
        r_layout.setSpacing(12)

        # Category badge color
        cat = t.category or "OTHER"
        cat_badge = StatusBadge(cat, variant="info" if "APP" in cat else "neutral", width=110, height=22)
        r_layout.addWidget(cat_badge)

        # Text Details
        col = QVBoxLayout()
        col.setSpacing(2)

        lbl_name = QLabel(t.name or "Untitled Template")
        lbl_name.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")

        subj = t.subject_template or ""
        lbl_subj = QLabel(f"Subject: {subj}")
        lbl_subj.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        lbl_subj.setWordWrap(False)

        col.addWidget(lbl_name)
        col.addWidget(lbl_subj)
        r_layout.addLayout(col, 1)

        # Action Buttons
        btn_edit = QPushButton("✏️ Edit")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.setStyleSheet(self._action_btn_style())
        btn_edit.clicked.connect(lambda _, tmpl=t: self._edit_template(tmpl))
        r_layout.addWidget(btn_edit)

        btn_dup = QPushButton("📋 Duplicate")
        btn_dup.setCursor(Qt.PointingHandCursor)
        btn_dup.setStyleSheet(self._action_btn_style())
        btn_dup.clicked.connect(lambda _, tmpl_id=t.id: self._duplicate_template(tmpl_id))
        r_layout.addWidget(btn_dup)

        btn_del = QPushButton("🗑️ Delete")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: #EF4444;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: #991B1B;
                color: #FFFFFF;
            }}
        """)
        btn_del.clicked.connect(lambda _, tmpl=t: self._delete_template(tmpl))
        r_layout.addWidget(btn_del)

        return row

    def _action_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """

    def _create_new_template(self) -> None:
        dlg = TemplateEditDialog(template=None, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._render_templates_list()

    def _edit_template(self, template: Any) -> None:
        dlg = TemplateEditDialog(template=template, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self._render_templates_list()

    def _duplicate_template(self, template_id: int) -> None:
        with get_db_session() as session:
            repo = EmailTemplateRepository(session)
            repo.duplicate(template_id)
            session.commit()
        self._render_templates_list()

    def _delete_template(self, template: Any) -> None:
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the template '{template.name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            with get_db_session() as session:
                repo = EmailTemplateRepository(session)
                repo.delete(template.id)
                session.commit()
            self._render_templates_list()

    # -------------------------------------------------------------------------
    # TAB 3: Follow-Up Schedule
    # -------------------------------------------------------------------------
    def _setup_schedule_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        # Cadence Configuration Card
        cadence_group = self._create_section_card(
            "⏱️ Follow-Up Cadence Sequence",
            "Automatically queue strategic follow-up emails after an initial application is sent.",
        )
        self.chk_auto_followup = QCheckBox("Enable Automated Follow-Up Sequences")
        self.chk_auto_followup.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['accent']};")
        cadence_group.layout().addWidget(self.chk_auto_followup)

        # Steps container
        self.cadence_steps_box = QVBoxLayout()
        self.cadence_steps_box.setSpacing(8)
        cadence_group.layout().addLayout(self.cadence_steps_box)

        # Add step button
        btn_add_step = QPushButton("➕ Add Follow-Up Step")
        btn_add_step.setCursor(Qt.PointingHandCursor)
        btn_add_step.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px dashed {COLORS['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """)
        btn_add_step.clicked.connect(self._add_cadence_step)
        cadence_group.layout().addWidget(btn_add_step)

        layout.addWidget(cadence_group)

        # Safeguards Card
        safe_group = self._create_section_card(
            "🛡️ Reply & Status Safeguards",
            "Smart safety rails to prevent unwanted follow-up emails.",
        )
        self.chk_pause_on_reply = QCheckBox("Auto-pause sequence immediately when recruiter replies (Inbound detected)")
        self.chk_pause_on_reply.setChecked(True)
        safe_group.layout().addWidget(self.chk_pause_on_reply)

        self.chk_cancel_on_status = QCheckBox("Auto-cancel follow-ups if application is marked REJECTED or INTERVIEWING")
        self.chk_cancel_on_status.setChecked(True)
        safe_group.layout().addWidget(self.chk_cancel_on_status)

        layout.addWidget(safe_group)

        # Throttling & Rate Limits
        throttle_group = self._create_section_card(
            "⚡ Outbound Rate Limiting & Throttling",
            "Maintain high sender domain reputation by staggering and capping outbound volume.",
        )
        t_form = QFormLayout()
        t_form.setSpacing(10)

        self.spn_daily_limit = QSpinBox()
        self.spn_daily_limit.setRange(1, 200)
        self.spn_daily_limit.setValue(30)
        t_form.addRow("Daily Email Send Limit:", self.spn_daily_limit)

        self.spn_delay_seconds = QSpinBox()
        self.spn_delay_seconds.setRange(5, 300)
        self.spn_delay_seconds.setValue(25)
        t_form.addRow("Min Delay Between Emails (Sec):", self.spn_delay_seconds)

        throttle_group.layout().addLayout(t_form)
        layout.addWidget(throttle_group)
        layout.addStretch()

        scroll.setWidget(container)
        v = QVBoxLayout(self.tab_schedule)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scroll)

    def _render_cadence_steps(self, cadence_days: List[int]) -> None:
        while self.cadence_steps_box.count():
            item = self.cadence_steps_box.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        for idx, days in enumerate(cadence_days, 1):
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 2, 0, 2)
            h.setSpacing(8)

            lbl = QLabel(f"Step {idx}: Send after")
            lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")
            h.addWidget(lbl)

            spn = QSpinBox()
            spn.setRange(1, 90)
            spn.setValue(days)
            spn.setSuffix(" days")
            spn.setObjectName(f"cadence_step_{idx}")
            h.addWidget(spn)

            lbl_post = QLabel("after previous communication")
            lbl_post.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            h.addWidget(lbl_post, 1)

            btn_del = QPushButton("✕")
            btn_del.setFixedSize(24, 24)
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    color: #EF4444;
                    border-color: #EF4444;
                }}
            """)
            btn_del.clicked.connect(lambda _, i=idx-1: self._remove_cadence_step(i))
            h.addWidget(btn_del)

            self.cadence_steps_box.addWidget(row)

    def _get_cadence_days_from_ui(self) -> List[int]:
        days = []
        for i in range(self.cadence_steps_box.count()):
            item = self.cadence_steps_box.itemAt(i)
            widget = item.widget() if item else None
            if widget:
                spn = widget.findChild(QSpinBox)
                if spn:
                    days.append(spn.value())
        return days or [3, 7, 14]

    def _add_cadence_step(self) -> None:
        curr = self._get_cadence_days_from_ui()
        next_val = curr[-1] + 7 if curr else 3
        curr.append(next_val)
        self._render_cadence_steps(curr)

    def _remove_cadence_step(self, index: int) -> None:
        curr = self._get_cadence_days_from_ui()
        if len(curr) <= 1:
            QMessageBox.information(self, "Cadence Notice", "You must keep at least one follow-up step.")
            return
        if 0 <= index < len(curr):
            curr.pop(index)
            self._render_cadence_steps(curr)

    # -------------------------------------------------------------------------
    # TAB 4: Sender & Message Defaults
    # -------------------------------------------------------------------------
    def _setup_sender_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        # Sender Details Card
        sender_group = self._create_section_card(
            "👤 Candidate Display Profile",
            "Sender details appended to outbound headers and outgoing messages.",
        )
        s_form = QFormLayout()
        s_form.setSpacing(10)

        self.txt_sender_name = QLineEdit()
        self.txt_sender_name.setPlaceholderText("e.g. Mohd Ahmad Raza Ansari")
        s_form.addRow("Sender Display Name *:", self.txt_sender_name)

        # Resume Attachment with File Picker
        res_box = QHBoxLayout()
        res_box.setSpacing(6)
        self.txt_resume_path = QLineEdit()
        self.txt_resume_path.setPlaceholderText("/path/to/Mohd_Ahmad_Raza_Resume.pdf")
        res_box.addWidget(self.txt_resume_path, 1)

        btn_browse = QPushButton("📁 Browse...")
        btn_browse.setCursor(Qt.PointingHandCursor)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
            }}
        """)
        btn_browse.clicked.connect(self._browse_resume_file)
        res_box.addWidget(btn_browse)
        s_form.addRow("Default Resume PDF:", res_box)

        self.txt_bcc = QLineEdit()
        self.txt_bcc.setPlaceholderText("optional_bcc_crm@notion.so")
        s_form.addRow("BCC Address (CRM/Backup):", self.txt_bcc)

        sender_group.layout().addLayout(s_form)
        layout.addWidget(sender_group)

        # Signature Card
        sig_group = self._create_section_card(
            "✍️ Email Signature",
            "Professional footer automatically appended to outbound pitches and custom emails.",
        )
        self.txt_signature = QTextEdit()
        self.txt_signature.setPlaceholderText(
            "--\n"
            "Best regards,\n"
            "Mohd Ahmad Raza Ansari\n"
            "Senior RPA & Python Automation Engineer\n"
            "LinkedIn: linkedin.com/in/mohd-ahmad-raza-ansari\n"
            "GitHub: github.com/ahmad10raza"
        )
        self.txt_signature.setFixedHeight(120)
        sig_group.layout().addWidget(self.txt_signature)
        layout.addWidget(sig_group)
        layout.addStretch()

        scroll.setWidget(container)
        v = QVBoxLayout(self.tab_sender)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(scroll)

    def _browse_resume_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Default Resume PDF",
            os.path.expanduser("~"),
            "PDF Files (*.pdf);;All Files (*)",
        )
        if file_path:
            self.txt_resume_path.setText(file_path)

    # -------------------------------------------------------------------------
    # Helper Card Factory
    # -------------------------------------------------------------------------
    def _create_section_card(self, title: str, subtitle: str) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']}80;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(14, 12, 14, 12)
        c_layout.setSpacing(8)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        c_layout.addWidget(lbl_t)

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        lbl_s.setWordWrap(True)
        c_layout.addWidget(lbl_s)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']}60; border: none;")
        c_layout.addWidget(divider)

        return card

    def _apply_eye_btn_default_style(self) -> None:
        """Apply DesignUI.md Tool/Icon Button default (hidden) state."""
        self.btn_toggle_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['border_light']};
            }}
        """)

    def _apply_eye_btn_active_style(self) -> None:
        """Apply DesignUI.md Tool/Icon Button active (visible) state with Safety Orange accent."""
        self.btn_toggle_pwd.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary_subtle']};
                border: 1px solid {COLORS['accent']};
                border-radius: 8px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['accent']}30;
                border-color: {COLORS['primary']};
            }}
        """)

    def _toggle_pwd_visibility(self) -> None:
        if self.txt_email_pwd.echoMode() == QLineEdit.Password:
            self.txt_email_pwd.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_pwd.setIcon(QIcon(_EYE_OFF_ICON_PATH))
            self.btn_toggle_pwd.setToolTip("Hide password")
            self._apply_eye_btn_active_style()
        else:
            self.txt_email_pwd.setEchoMode(QLineEdit.Password)
            self.btn_toggle_pwd.setIcon(QIcon(_EYE_ICON_PATH))
            self.btn_toggle_pwd.setToolTip("Show password")
            self._apply_eye_btn_default_style()

    # -------------------------------------------------------------------------
    # Data Loading & Saving
    # -------------------------------------------------------------------------
    def _load_data(self) -> None:
        # Load from SecretsService
        creds = self.secrets.get_email_credentials()
        self.txt_email_user.setText(creds.get("user", ""))
        self.txt_email_pwd.setText(creds.get("password", ""))
        self.txt_sync_label.setText(creds.get("sync_label", "RPA-Developer-Application"))
        self.txt_smtp_host.setText(creds.get("smtp_host", "smtp.gmail.com"))
        self.spn_smtp_port.setValue(creds.get("smtp_port", 587))
        self.chk_smtp_tls.setChecked(creds.get("smtp_use_tls", True))
        self.txt_imap_host.setText(creds.get("imap_host", "imap.gmail.com"))
        self.spn_imap_port.setValue(creds.get("imap_port", 993))
        self.chk_imap_ssl.setChecked(creds.get("imap_use_ssl", True))

        # Load platform extra settings
        pcfg = self.service.get_platform_config("email")
        extra = (pcfg.get("extra_settings") or {}) if pcfg else {}

        self.txt_reply_folder.setText(extra.get("reply_folder", "INBOX"))
        self.chk_auto_followup.setChecked(extra.get("auto_followup_enabled", True))
        cadence = extra.get("followup_cadence_days", [3, 7, 14])
        self._render_cadence_steps(cadence)

        self.chk_pause_on_reply.setChecked(extra.get("auto_pause_on_reply", True))
        self.chk_cancel_on_status.setChecked(extra.get("cancel_on_status_change", True))

        daily_limit = pcfg.get("daily_application_goal", 30) if pcfg else 30
        self.spn_daily_limit.setValue(daily_limit)
        self.spn_delay_seconds.setValue(extra.get("min_delay_seconds", 25))

        self.txt_sender_name.setText(extra.get("sender_name", "Mohd Ahmad Raza Ansari"))
        self.txt_resume_path.setText(extra.get("default_resume_path", ""))
        self.txt_signature.setPlainText(extra.get("signature", "--\nBest regards,\nMohd Ahmad Raza Ansari"))
        self.txt_bcc.setText(extra.get("bcc_address", ""))

        # Render templates list
        self._render_templates_list()

    def _run_connection_test(self) -> None:
        user = self.txt_email_user.text().strip()
        pwd = self.txt_email_pwd.text().strip()

        if not user or not pwd:
            QMessageBox.warning(self, "Missing Credentials", "Please enter your Email Address and App Password before testing.")
            return

        self.btn_test_conn.setEnabled(False)
        self.lbl_test_status.setText("⏳ Testing SMTP & IMAP authentication...")
        self.lbl_test_status.setStyleSheet("color: #FBBF24; font-weight: 600;")

        self.test_worker = EmailTestWorker(
            user=user,
            password=pwd,
            smtp_host=self.txt_smtp_host.text().strip(),
            smtp_port=self.spn_smtp_port.value(),
            smtp_use_tls=self.chk_smtp_tls.isChecked(),
            smtp_use_ssl=False,
            imap_host=self.txt_imap_host.text().strip(),
            imap_port=self.spn_imap_port.value(),
            imap_use_ssl=self.chk_imap_ssl.isChecked(),
        )
        self.test_worker.result_ready.connect(self._on_connection_test_result)
        self.test_worker.start()

    def _on_connection_test_result(self, success: bool, message: str) -> None:
        self.btn_test_conn.setEnabled(True)
        if success:
            self.lbl_test_status.setText("✅ Connection Successful! SMTP & IMAP verified.")
            self.lbl_test_status.setStyleSheet("color: #34D399; font-weight: 700;")
        else:
            self.lbl_test_status.setText(f"❌ Failed: {message}")
            self.lbl_test_status.setStyleSheet("color: #EF4444; font-weight: 600;")

    def _save_settings(self) -> None:
        user = self.txt_email_user.text().strip()
        pwd = self.txt_email_pwd.text().strip()
        sync_label = self.txt_sync_label.text().strip() or "RPA-Developer-Application"

        # 1. Save Secrets
        self.secrets.set_email_credentials(
            user=user,
            password=pwd if pwd != "" else None,
            smtp_host=self.txt_smtp_host.text().strip(),
            smtp_port=self.spn_smtp_port.value(),
            smtp_use_tls=self.chk_smtp_tls.isChecked(),
            smtp_use_ssl=False,
            imap_host=self.txt_imap_host.text().strip(),
            imap_port=self.spn_imap_port.value(),
            imap_use_ssl=self.chk_imap_ssl.isChecked(),
            sync_label=sync_label,
        )

        # 2. Save Platform Config and extra settings
        cadence_days = self._get_cadence_days_from_ui()
        extra = {
            "sync_label": sync_label,
            "reply_folder": self.txt_reply_folder.text().strip() or "INBOX",
            "followup_cadence_days": cadence_days,
            "auto_followup_enabled": self.chk_auto_followup.isChecked(),
            "auto_pause_on_reply": self.chk_pause_on_reply.isChecked(),
            "cancel_on_status_change": self.chk_cancel_on_status.isChecked(),
            "daily_send_limit": self.spn_daily_limit.value(),
            "min_delay_seconds": self.spn_delay_seconds.value(),
            "sender_name": self.txt_sender_name.text().strip(),
            "default_resume_path": self.txt_resume_path.text().strip(),
            "signature": self.txt_signature.toPlainText().strip(),
            "bcc_address": self.txt_bcc.text().strip(),
        }

        self.service.save_platform_config(
            platform_name="email",
            daily_application_goal=self.spn_daily_limit.value(),
            max_applications=self.spn_daily_limit.value(),
            extra_settings=extra,
        )

        logger.info("Saved email outreach configuration successfully.")
        self.accept()
