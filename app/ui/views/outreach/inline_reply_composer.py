"""Inline Reply Composer — Restart-safe reply editor with autosave.

Sits at the bottom of the thread view. Features:
  - Debounced autosave (1000ms) via OutreachService.save_draft()
  - Draft restore on conversation load
  - Discard Draft button
  - Visual autosave status indicator
  - Attachment and AI Copilot action buttons
  - Threaded Send Reply via ReplySendWorker

Design: Compact editor with formatting actions and save state feedback.
"""

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.Outreach.InlineReplyComposer")


class InlineReplyComposer(QFrame):
    """Compact inline reply editor with autosave and threaded send."""

    send_requested = Signal(int, str, object, object)       # (app_id, body, attachment_path, resume_id)
    draft_save_requested = Signal(int, str)  # (application_id, body_text)
    draft_discard_requested = Signal(int)    # (application_id,)
    ai_copilot_requested = Signal(int)       # (application_id,)
    ai_copilot_prompt_requested = Signal(int, str)  # (application_id, user_prompt)
    template_requested = Signal(int)         # (application_id,)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._app_id: Optional[int] = None
        self._recipient_label_text = ""
        self._recipient_name = ""
        self._is_sending = False
        self._is_minimized = False
        self._available_templates: List[Dict[str, Any]] = []

        # Attachment state
        self._attached_file_path: Optional[str] = None
        self._attached_resume_id: Optional[int] = None
        self._attached_display_name: str = ""

        # Autosave timer (debounced 1000ms)
        self._autosave_timer = QTimer()
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(1000)
        self._autosave_timer.timeout.connect(self._do_autosave)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 12)
        layout.setSpacing(6)

        # Header: "Reply to [Name]" + minimize button + autosave status
        header = QHBoxLayout()
        header.setSpacing(8)

        self._recipient_label = QLabel("Reply")
        self._recipient_label.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        header.addWidget(self._recipient_label)

        # Minimize / Collapse Button
        self._btn_minimize = QPushButton("▾ Collapse Reply")
        self._btn_minimize.setFixedHeight(24)
        self._btn_minimize.setToolTip("Collapse reply editor to view full thread history")
        self._btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_minimize.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 2px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        self._btn_minimize.clicked.connect(self._toggle_minimize)
        header.addWidget(self._btn_minimize)

        header.addStretch(1)

        self._save_status = QLabel("")
        self._save_status.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_dark']};
            background: transparent;
            border: none;
        """)
        header.addWidget(self._save_status)

        layout.addLayout(header)

        # Compact expand bar (shown only when minimized)
        self._compact_bar = QFrame()
        self._compact_bar.setVisible(False)
        self._compact_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._compact_bar.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface_alt']};
                border: 1px dashed {COLORS['border']};
                border-radius: 6px;
            }}
            QFrame:hover {{
                border-color: {COLORS['primary']};
                background: {COLORS['surface_hover']};
            }}
        """)
        c_layout = QHBoxLayout(self._compact_bar)
        c_layout.setContentsMargins(12, 6, 12, 6)
        self._lbl_compact = QLabel("💬 Reply Editor Collapsed — Click here to write a reply or follow-up...")
        self._lbl_compact.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px; font-weight: 500; background: transparent; border: none;")
        c_layout.addWidget(self._lbl_compact, 1)

        btn_expand_pill = QPushButton("▴ Expand Reply")
        btn_expand_pill.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_expand_pill.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_hover']};
            }}
        """)
        btn_expand_pill.clicked.connect(self._toggle_minimize)
        c_layout.addWidget(btn_expand_pill)

        self._compact_bar.mousePressEvent = lambda e: self._toggle_minimize()
        layout.addWidget(self._compact_bar)

        # Collapsible AI Copilot RAG Prompt Bar
        self._ai_prompt_bar = QFrame()
        self._ai_prompt_bar.setVisible(False)
        self._ai_prompt_bar.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface_alt']};
                border: 1px solid {COLORS['accent']}50;
                border-radius: 6px;
            }}
        """)
        ai_layout = QHBoxLayout(self._ai_prompt_bar)
        ai_layout.setContentsMargins(8, 4, 8, 4)
        ai_layout.setSpacing(6)

        lbl_ai_icon = QLabel("✨ Copilot Prompt:")
        lbl_ai_icon.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['accent']}; border: none; background: transparent;")
        ai_layout.addWidget(lbl_ai_icon)

        self._txt_copilot_prompt = QLineEdit()
        self._txt_copilot_prompt.setPlaceholderText("e.g. Confirm 2+ years RPA experience, provide contact number, express enthusiasm...")
        self._txt_copilot_prompt.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
        """)
        self._txt_copilot_prompt.returnPressed.connect(self._on_generate_copilot_reply)
        ai_layout.addWidget(self._txt_copilot_prompt, 1)

        self._btn_generate_rag = QPushButton("Generate Reply ✨")
        self._btn_generate_rag.setFixedHeight(26)
        self._btn_generate_rag.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate_rag.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: #E05698;
            }}
            QPushButton:disabled {{
                background: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self._btn_generate_rag.clicked.connect(self._on_generate_copilot_reply)
        ai_layout.addWidget(self._btn_generate_rag)

        btn_ai_close = QPushButton("✕")
        btn_ai_close.setFixedSize(20, 20)
        btn_ai_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_ai_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_ai_close.clicked.connect(lambda: self._ai_prompt_bar.setVisible(False))
        ai_layout.addWidget(btn_ai_close)

        layout.addWidget(self._ai_prompt_bar)

        # Text editor
        self._editor = QTextEdit()
        self._editor.setPlaceholderText("Type your reply...")
        self._editor.setMinimumHeight(80)
        self._editor.setMaximumHeight(160)
        self._editor.setStyleSheet(f"""
            QTextEdit {{
                background: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                font-size: 13px;
                line-height: 1.45;
            }}
            QTextEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self._editor.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._editor)

        # Attachment Chip Bar (displays currently attached document/resume)
        self._attachment_bar = QFrame()
        self._attachment_bar.setVisible(False)
        self._attachment_bar.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface_alt']};
                border: 1px solid {COLORS['primary']}40;
                border-radius: 5px;
            }}
        """)
        att_layout = QHBoxLayout(self._attachment_bar)
        att_layout.setContentsMargins(8, 4, 8, 4)
        att_layout.setSpacing(6)

        self._lbl_attachment_icon = QLabel("📎")
        self._lbl_attachment_icon.setStyleSheet("border: none; background: transparent; font-size: 12px;")
        att_layout.addWidget(self._lbl_attachment_icon)

        self._lbl_attachment_info = QLabel("")
        self._lbl_attachment_info.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text']}; border: none; background: transparent;")
        att_layout.addWidget(self._lbl_attachment_info, 1)

        btn_rem_att = QPushButton("✕")
        btn_rem_att.setFixedSize(20, 20)
        btn_rem_att.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rem_att.setToolTip("Remove attached document")
        btn_rem_att.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 11px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                color: {COLORS['danger']};
            }}
        """)
        btn_rem_att.clicked.connect(self._clear_attachment)
        att_layout.addWidget(btn_rem_att)

        layout.addWidget(self._attachment_bar)

        # Action bar container (can be hidden when minimized)
        self._actions_container = QWidget()
        actions = QHBoxLayout(self._actions_container)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)

        # Discard draft
        self._discard_btn = QPushButton("🗑 Discard")
        self._discard_btn.setFixedHeight(28)
        self._discard_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._discard_btn.setVisible(False)
        self._discard_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                font-size: 11px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['danger']};
                border-color: {COLORS['danger']};
            }}
        """)
        self._discard_btn.clicked.connect(self._on_discard)
        actions.addWidget(self._discard_btn)

        # Quick collapse button in actions bar
        self._btn_action_collapse = QPushButton("▾ Collapse")
        self._btn_action_collapse.setFixedHeight(28)
        self._btn_action_collapse.setToolTip("Collapse reply editor to view thread history")
        self._btn_action_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_action_collapse.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_dark']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                font-size: 11px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['surface_hover']};
            }}
        """)
        self._btn_action_collapse.clicked.connect(self._toggle_minimize)
        actions.addWidget(self._btn_action_collapse)

        actions.addStretch(1)

        # AI Copilot
        self._ai_btn = QPushButton("✨ AI Copilot")
        self._ai_btn.setFixedHeight(28)
        self._ai_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ai_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}40;
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent']}15;
            }}
        """)
        self._ai_btn.clicked.connect(self._toggle_ai_copilot_prompt)
        actions.addWidget(self._ai_btn)

        # Attach Resume / Document button
        self._attach_btn = QPushButton("📎 Attach ▾")
        self._attach_btn.setFixedHeight(28)
        self._attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._attach_btn.setToolTip("Attach your verified resume or choose a local PDF document to include with this reply")
        self._attach_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)
        self._attach_btn.clicked.connect(self._show_attach_menu)
        actions.addWidget(self._attach_btn)

        # Template
        self._tmpl_btn = QPushButton("📝 Template ▾")
        self._tmpl_btn.setFixedHeight(28)
        self._tmpl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tmpl_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
            }}
        """)
        self._tmpl_btn.clicked.connect(self._show_template_menu)
        actions.addWidget(self._tmpl_btn)

        # Send
        self._send_btn = QPushButton("Send Reply  →")
        self._send_btn.setFixedHeight(28)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_hover']};
            }}
            QPushButton:disabled {{
                background: {COLORS['border']};
                color: {COLORS['text_dark']};
            }}
        """)
        self._send_btn.clicked.connect(self._on_send)
        actions.addWidget(self._send_btn)

        layout.addWidget(self._actions_container)

        self.setStyleSheet(f"""
            InlineReplyComposer {{
                background: {COLORS['surface']};
                border-top: 1px solid {COLORS['border']};
            }}
        """)

    def set_templates(self, templates: List[Dict[str, Any]]):
        """Sets custom or database email templates available in this composer."""
        self._available_templates = templates or []

    def _toggle_minimize(self):
        """Toggles between minimized compact bar and full editor."""
        self._is_minimized = not self._is_minimized
        self._editor.setVisible(not self._is_minimized)
        self._actions_container.setVisible(not self._is_minimized)
        if self._is_minimized:
            self._ai_prompt_bar.setVisible(False)
            self._attachment_bar.setVisible(False)
            self._compact_bar.setVisible(True)
            self._btn_minimize.setText("▴ Expand Reply")
            self._btn_minimize.setToolTip("Expand reply editor")
        else:
            self._compact_bar.setVisible(False)
            self._attachment_bar.setVisible(bool(self._attached_file_path or self._attached_resume_id))
            self._btn_minimize.setText("▾ Collapse Reply")
            self._btn_minimize.setToolTip("Collapse reply editor")
            self._editor.setFocus()

    def _show_attach_menu(self):
        """Displays menu with options to attach default/saved resumes or browse a document."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface_elevated']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 11px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 6px;
            }}
        """)

        from app.services.resume_service import ResumeService
        try:
            rs = ResumeService()
            resumes = rs.list_resumes()
        except Exception as e:
            logger.warning("Could not list resumes for attachment: %s", e)
            resumes = []

        if resumes:
            # Sort with default first
            sorted_res = sorted(resumes, key=lambda r: (not r.is_default, r.name or ""))
            for r in sorted_res:
                def_tag = " ★ Default" if r.is_default else ""
                ver_tag = f" (v{r.version})" if r.version else ""
                label = f"📄 {r.name or 'Resume'}{ver_tag}{def_tag}"
                act = menu.addAction(label)
                act.triggered.connect(
                    lambda checked=False, res_id=r.id, res_name=r.name, res_ver=r.version, res_path=r.file_path:
                    self._set_resume_attachment(res_id, res_name, res_ver, res_path)
                )
            menu.addSeparator()

        act_browse = menu.addAction("📎 Browse Local Document / PDF...")
        act_browse.triggered.connect(self._browse_attachment)

        if self._attached_file_path or self._attached_resume_id:
            menu.addSeparator()
            act_remove = menu.addAction("✕ Remove Attached Document")
            act_remove.triggered.connect(self._clear_attachment)

        menu.exec(self._attach_btn.mapToGlobal(self._attach_btn.rect().bottomLeft()))

    def _browse_attachment(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume or Document to Attach",
            "",
            "Documents (*.pdf *.docx *.doc);;PDF Files (*.pdf);;All Files (*)",
        )
        if path:
            self._set_file_attachment(path)

    def _set_resume_attachment(self, resume_id: int, name: str, version: Optional[str], file_path: str):
        self._attached_resume_id = resume_id
        self._attached_file_path = file_path
        ver_str = f" v{version}" if version else ""
        size_str = ""
        import os
        if file_path and os.path.exists(file_path):
            kb = round(os.path.getsize(file_path) / 1024)
            size_str = f" · {kb} KB"
        self._attached_display_name = f"{name or 'Resume'}{ver_str}{size_str}"
        self._lbl_attachment_info.setText(f"{self._attached_display_name}  (Resume Attached ✓)")
        self._attachment_bar.setVisible(not self._is_minimized)
        self._attach_btn.setText("📎 Resume Attached ✓")
        self._attach_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['surface_hover']};
                color: {COLORS['success']};
                border: 1px solid {COLORS['success']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
        """)

    def _set_file_attachment(self, file_path: str):
        import os
        self._attached_resume_id = None
        self._attached_file_path = file_path
        fname = os.path.basename(file_path)
        kb = round(os.path.getsize(file_path) / 1024) if os.path.exists(file_path) else 0
        self._attached_display_name = f"{fname} · {kb} KB"
        self._lbl_attachment_info.setText(f"{self._attached_display_name}  (Custom Document Attached ✓)")
        self._attachment_bar.setVisible(not self._is_minimized)
        self._attach_btn.setText("📎 File Attached ✓")
        self._attach_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['surface_hover']};
                color: {COLORS['success']};
                border: 1px solid {COLORS['success']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 10px;
            }}
        """)

    def _clear_attachment(self):
        self._attached_resume_id = None
        self._attached_file_path = None
        self._attached_display_name = ""
        self._attachment_bar.setVisible(False)
        self._attach_btn.setText("📎 Attach ▾")
        self._attach_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 5px;
                font-size: 11px;
                font-weight: 500;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background: {COLORS['surface_hover']};
                border-color: {COLORS['primary']};
            }}
        """)

    def _show_template_menu(self):
        """Displays a menu of quick reply and follow-up templates."""
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface_elevated']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 6px;
            }}
        """)

        presets = [
            ("Follow-Up #1: Polite Check-in (+3-4d)", (
                "Hi {{recruiter_name}},\n\n"
                "I hope you're having a productive week.\n\n"
                "I wanted to quickly follow up on my application and see if there are any updates regarding next steps.\n\n"
                "Please let me know if you need any additional information from my side.\n\n"
                "Best regards,\n{{candidate_name}}"
            )),
            ("Follow-Up #2: Value-Add & Updates (+7-10d)", (
                "Hi {{recruiter_name}},\n\n"
                "Following up on our previous conversation. I recently delivered an automation project that aligns closely with your tech stack.\n\n"
                "Would love to connect for 10 minutes to discuss how my background can help accelerate your roadmap.\n\n"
                "Best regards,\n{{candidate_name}}"
            )),
            ("Follow-Up #3: Final Graceful Closeout (+14-17d)", (
                "Hi {{recruiter_name}},\n\n"
                "I assume priorities may have shifted or you've decided to move forward with other candidates at this time.\n\n"
                "I'll step back for now, but please feel free to reach out if another relevant opportunity arises in the future.\n\n"
                "Wishing you and the team continued success!\n\n"
                "Best regards,\n{{candidate_name}}"
            )),
            ("Screening Reply: Confirm Experience & Phone", (
                "Hi {{recruiter_name}},\n\n"
                "Thank you for getting back to me! I'm glad to share the details you requested:\n\n"
                "• Years of Experience: 2+ years\n"
                "• Contact Number: +91 6388623967\n"
                "• Notice Period: 30 days\n\n"
                "Looking forward to the next steps.\n\n"
                "Best regards,\n{{candidate_name}}"
            )),
            ("Interview: Availability for Call", (
                "Hi {{recruiter_name}},\n\n"
                "Thank you for the update! I would be delighted to speak with you and the hiring team.\n\n"
                "I am generally available during weekday afternoons (2:00 PM – 6:00 PM IST), but happy to adjust to your schedule.\n\n"
                "Best regards,\n{{candidate_name}}"
            )),
        ]

        menu.addSection("Follow-Up & Response Presets")
        for title, body_tmpl in presets:
            action = menu.addAction(title)
            action.triggered.connect(lambda _, b=body_tmpl: self._apply_template_text(b))

        if self._available_templates:
            menu.addSeparator()
            menu.addSection("Saved Templates (Database)")
            for t in self._available_templates:
                name = t.get("name") or "Template"
                body = t.get("body_template") or ""
                act = menu.addAction(name)
                act.triggered.connect(lambda _, b=body: self._apply_template_text(b))

        menu.exec(self._tmpl_btn.mapToGlobal(self._tmpl_btn.rect().bottomLeft()))

    def _apply_template_text(self, raw_tmpl: str):
        """Interpolates variables and sets text into editor, expanding composer if minimized."""
        if self._is_minimized:
            self._toggle_minimize()

        recruiter = self._recipient_name or "there"
        text = raw_tmpl.replace("{{recruiter_name}}", recruiter)
        text = text.replace("{{candidate_name}}", "Mohd Ahmad Raza Ansari")
        self._editor.setPlainText(text)
        self._editor.setFocus()
        self._save_status.setText("Template applied")

    def load_for_conversation(self, app_id: int, recipient_name: str, draft_body: Optional[str] = None):
        """Prepares the composer for a conversation, restoring any existing draft."""
        self._app_id = app_id
        self._recipient_name = recipient_name
        self._recipient_label.setText(f"Reply to {recipient_name}")
        self._lbl_compact.setText(f"💬 Click to reply to {recipient_name} or select a follow-up template...")
        self._editor.blockSignals(True)
        self._editor.setPlainText(draft_body or "")
        self._editor.blockSignals(False)
        self._discard_btn.setVisible(bool(draft_body))
        self._save_status.setText("Draft restored" if draft_body else "")
        self._is_sending = False
        self._send_btn.setEnabled(True)
        self._send_btn.setText("Send Reply  →")

    def clear(self):
        self._app_id = None
        self._recipient_name = ""
        self._clear_attachment()
        self._lbl_compact.setText("💬 Click to write a reply or follow-up...")
        self._editor.blockSignals(True)
        self._editor.clear()
        self._editor.blockSignals(False)
        self._recipient_label.setText("Reply")
        self._save_status.setText("")
        self._discard_btn.setVisible(False)

    def set_text(self, text: str):
        """Programmatically sets editor text (e.g., from AI Copilot)."""
        self._editor.setPlainText(text)

    def set_reply_text(self, text: str):
        """Sets the generated reply into the editor and focuses it."""
        self._editor.setPlainText(text)
        self._editor.setFocus()
        self._save_status.setText("Reply drafted by AI")
        self._ai_prompt_bar.setVisible(False)
        self.set_ai_generating(False)

    def focus_editor(self):
        """Focuses the reply editor text area."""
        self._editor.setFocus()

    def set_ai_generating(self, is_generating: bool):
        """Toggles loading state during RAG reply generation."""
        self._btn_generate_rag.setEnabled(not is_generating)
        if is_generating:
            self._btn_generate_rag.setText("✨ Generating...")
            self._save_status.setText("AI Copilot drafting reply...")
        else:
            self._btn_generate_rag.setText("Generate Reply ✨")
            self._save_status.setText("")

    def _toggle_ai_copilot_prompt(self):
        """Shows/hides the prompt input bar for AI Copilot reply."""
        if not self._app_id:
            return
        is_vis = not self._ai_prompt_bar.isVisible()
        self._ai_prompt_bar.setVisible(is_vis)
        if is_vis:
            self._txt_copilot_prompt.setFocus()

    def _on_generate_copilot_reply(self):
        """Triggers RAG-based reply generation with prompt."""
        if not self._app_id:
            return
        prompt_text = self._txt_copilot_prompt.text().strip()
        self.set_ai_generating(True)
        self.ai_copilot_prompt_requested.emit(self._app_id, prompt_text)

    def _on_text_changed(self):
        text = self._editor.toPlainText().strip()
        self._discard_btn.setVisible(bool(text))
        if text and self._app_id:
            self._save_status.setText("Saving draft...")
            self._autosave_timer.start()

    def _do_autosave(self):
        if not self._app_id:
            return
        body = self._editor.toPlainText().strip()
        if body:
            self.draft_save_requested.emit(self._app_id, body)
            from datetime import datetime
            time_str = datetime.now().strftime("%I:%M %p")
            self._save_status.setText(f"Draft saved ({time_str})")
        else:
            self._save_status.setText("")

    def _on_send(self):
        if not self._app_id or self._is_sending:
            return
        body = self._editor.toPlainText().strip()
        if not body:
            return

        self._is_sending = True
        self._send_btn.setEnabled(False)
        self._send_btn.setText("Sending...")
        self.send_requested.emit(self._app_id, body, self._attached_file_path, self._attached_resume_id)

    def on_send_success(self):
        """Called after successful send to reset the composer."""
        self._is_sending = False
        self._editor.clear()
        self._clear_attachment()
        self._save_status.setText("✓ Sent")
        self._discard_btn.setVisible(False)
        self._send_btn.setEnabled(True)
        self._send_btn.setText("Send Reply  →")

    def on_send_error(self, error_msg: str):
        """Called on send failure to re-enable the composer."""
        self._is_sending = False
        self._send_btn.setEnabled(True)
        self._send_btn.setText("Send Reply  →")
        self._save_status.setText(f"⚠ {error_msg[:40]}")
        self._save_status.setStyleSheet(f"font-size: 10px; color: {COLORS['danger']};")

    def _on_discard(self):
        if self._app_id:
            self._editor.clear()
            self._clear_attachment()
            self._save_status.setText("")
            self._discard_btn.setVisible(False)
            self.draft_discard_requested.emit(self._app_id)
