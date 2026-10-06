"""Context Panel — Right drawer with recruitment context information.

Ordered by tactical urgency (per plan §7):
  1. NEXT ACTION (top, high-contrast)
  2. APPLICATION CONTEXT
  3. RECRUITER CONTACT
  4. FOLLOW-UP CADENCE TIMELINE
  5. RESUME SNAPSHOT
  6. QUICK LINKS

Collapsible via splitter. Uses theme tokens exclusively.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.dto.outreach_viewmodels import (
    ContactViewModel,
    ConversationDetailViewModel,
    FollowUpStepViewModel,
    NextActionRecommendation,
    PresentationConversationState,
    ResumeSnapshotViewModel,
)
from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.Outreach.ContextPanel")


class _SectionHeader(QLabel):
    """Styled section divider label."""

    def __init__(self, text: str, parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self.setStyleSheet(f"""
            font-size: 10px;
            font-weight: 700;
            color: {COLORS['text_dark']};
            letter-spacing: 1px;
            padding: 8px 0 4px 0;
        """)


class NextActionCard(QFrame):
    """High-contrast card showing the exact next step and a 1-click CTA."""

    cta_clicked = Signal(str)  # emits action_type

    def __init__(self, action: NextActionRecommendation, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._action = action

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Icon + headline
        headline = QLabel(f"⚡ {action.headline}")
        headline.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        headline.setWordWrap(True)
        layout.addWidget(headline)

        # Rationale
        rationale = QLabel(action.rationale)
        rationale.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
        """)
        rationale.setWordWrap(True)
        layout.addWidget(rationale)

        # Suggested status pill
        if action.suggested_status:
            status_pill = QLabel(f"→ {action.suggested_status}")
            status_pill.setStyleSheet(f"""
                font-size: 10px;
                font-weight: 600;
                color: {COLORS['purple']};
                background: {COLORS['purple_subtle']};
                border-radius: 3px;
                padding: 2px 6px;
            """)
            layout.addWidget(status_pill)

        # CTA button
        raw_label = (action.cta_label or "").strip()
        is_wait_or_thread = (
            action.action_type == "WAIT"
            or "Thread" in raw_label
            or "Scroll" in raw_label
            or "Latest" in raw_label
        )
        btn_bg = "#FA6400" if is_wait_or_thread else COLORS['primary']
        btn_hover = "#FF7A00" if is_wait_or_thread else COLORS['primary_hover']

        cta_label = raw_label or ("View Latest Message" if is_wait_or_thread else "Draft Reply")

        cta_btn = QPushButton(cta_label)
        cta_btn.setFixedHeight(32)
        cta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_wait_or_thread:
            cta_btn.setToolTip("Scroll down to the latest message in this thread and focus reply box")
        cta_btn.setStyleSheet(f"""
            QPushButton {{
                background: {btn_bg};
                color: #FFFFFF !important;
                border: none;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 700;
                padding: 0 14px;
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
        """)
        cta_btn.clicked.connect(lambda: self.cta_clicked.emit(action.action_type))
        layout.addWidget(cta_btn)

        self.setStyleSheet(f"""
            NextActionCard {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['primary']}30;
                border-radius: 6px;
            }}
        """)


class CadenceTimeline(QFrame):
    """Follow-up cadence visual timeline with pause/resume/stop/execute controls."""

    pause_requested = Signal(int)    # app_id
    resume_requested = Signal(int)
    stop_requested = Signal(int)
    execute_now = Signal(int)        # followup_id

    def __init__(
        self,
        follow_ups: list,
        app_id: int,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._app_id = app_id

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        if not follow_ups:
            empty = QLabel("No cadence configured")
            empty.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 11px;")
            layout.addWidget(empty)
            return

        for fu in follow_ups:
            step_layout = QHBoxLayout()
            step_layout.setSpacing(4)

            # Status icon
            icon_map = {
                "COMPLETED": "●",
                "PENDING": "○",
                "DUE": "◉",
                "PAUSED": "⏸",
                "SKIPPED": "⊘",
                "CANCELLED": "✕",
            }
            icon = icon_map.get(fu.status, "○")
            color_map = {
                "COMPLETED": COLORS["success"],
                "PENDING": COLORS["text_muted"],
                "DUE": COLORS["accent"],
                "PAUSED": COLORS["warning"],
                "SKIPPED": COLORS["text_dark"],
                "CANCELLED": COLORS["danger"],
            }
            color = color_map.get(fu.status, COLORS["text_muted"])

            icon_label = QLabel(icon)
            icon_label.setStyleSheet(f"color: {color}; font-size: 12px;")
            step_layout.addWidget(icon_label)

            # Step description
            due_str = ""
            if fu.due_at:
                dt = fu.due_at
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                due_str = dt.strftime("%b %d")

            desc_text = f"Step {fu.step_number}"
            if due_str:
                desc_text += f" — {due_str}"
            if fu.paused_reason:
                desc_text += f" ({fu.paused_reason})"
            if fu.status == "DUE":
                desc_text += " ⚡"

            desc = QLabel(desc_text)
            desc.setStyleSheet(f"""
                font-size: 11px;
                color: {color};
            """)
            step_layout.addWidget(desc)

            step_layout.addStretch(1)

            # Execute now for DUE steps
            if fu.status in ("DUE", "PENDING"):
                exec_btn = QPushButton("⚡")
                exec_btn.setFixedSize(22, 22)
                exec_btn.setToolTip("Execute Now")
                exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                exec_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        border: none;
                        font-size: 11px;
                    }}
                    QPushButton:hover {{
                        background: {COLORS['surface_hover']};
                        border-radius: 3px;
                    }}
                """)
                fu_id = fu.id
                exec_btn.clicked.connect(lambda *args, fid=fu_id: self.execute_now.emit(fid))
                step_layout.addWidget(exec_btn)

            layout.addLayout(step_layout)

        # Action buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        has_pending = any(f.status in ("PENDING", "DUE") for f in follow_ups)
        has_paused = any(f.status == "PAUSED" for f in follow_ups)

        if has_pending:
            pause_btn = QPushButton("⏸ Pause")
            pause_btn.setFixedHeight(24)
            pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pause_btn.setStyleSheet(self._action_btn_style())
            pause_btn.clicked.connect(lambda *_: self.pause_requested.emit(self._app_id))
            btn_row.addWidget(pause_btn)

        if has_paused:
            resume_btn = QPushButton("▶ Resume")
            resume_btn.setFixedHeight(24)
            resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            resume_btn.setStyleSheet(self._action_btn_style())
            resume_btn.clicked.connect(lambda *_: self.resume_requested.emit(self._app_id))
            btn_row.addWidget(resume_btn)

        stop_btn = QPushButton("🛑 Stop")
        stop_btn.setFixedHeight(24)
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.setStyleSheet(self._action_btn_style(danger=True))
        stop_btn.clicked.connect(lambda *_: self.stop_requested.emit(self._app_id))
        btn_row.addWidget(stop_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    @staticmethod
    def _action_btn_style(danger: bool = False) -> str:
        color = COLORS["danger"] if danger else COLORS["text_muted"]
        return f"""
            QPushButton {{
                background: transparent;
                color: {color};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                font-size: 10px;
                font-weight: 500;
                padding: 0 8px;
            }}
            QPushButton:hover {{
                background: {COLORS['surface_hover']};
                border-color: {COLORS['border_light']};
            }}
        """


class ContextPanel(QWidget):
    """Right collapsible panel with recruitment context, ordered by urgency."""

    cta_clicked = Signal(str)     # action_type from NextActionCard
    pause_cadence = Signal(int)   # app_id
    resume_cadence = Signal(int)
    stop_cadence = Signal(int)
    execute_followup = Signal(int)  # followup_id

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # Scroll area wrapping all sections
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {COLORS['background']};
                border: none;
            }}
            QScrollBar:vertical {{
                width: 5px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 2px;
            }}
        """)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 8, 12, 16)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch(1)

        scroll.setWidget(self._content)
        outer.addWidget(scroll)

        self.setStyleSheet(f"""
            ContextPanel {{
                background: {COLORS['background']};
                border-left: 1px solid {COLORS['border']};
            }}
        """)

    def load_detail(self, detail: ConversationDetailViewModel):
        """Populates all sections from a ConversationDetailViewModel."""
        # Clear previous content
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Clear sub-layouts
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget():
                        sub.widget().deleteLater()

        idx = 0

        # 1. NEXT ACTION
        self._content_layout.insertWidget(idx, _SectionHeader("NEXT ACTION"))
        idx += 1
        action_card = NextActionCard(detail.next_action)
        action_card.cta_clicked.connect(self.cta_clicked.emit)
        self._content_layout.insertWidget(idx, action_card)
        idx += 1

        # 2. APPLICATION CONTEXT
        self._content_layout.insertWidget(idx, _SectionHeader("APPLICATION"))
        idx += 1
        app_info = QFrame()
        app_layout = QVBoxLayout(app_info)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(2)

        for label, value in [
            ("Company", detail.company_name),
            ("Role", detail.job_title),
            ("Status", detail.recruitment_status.replace("_", " ").title()),
            ("Applied", detail.applied_at.strftime("%b %d, %Y") if detail.applied_at else "—"),
        ]:
            row = QHBoxLayout()
            key = QLabel(label)
            key.setStyleSheet(f"font-size: 11px; color: {COLORS['text_dark']};")
            row.addWidget(key)
            row.addStretch(1)
            val = QLabel(value)
            val.setStyleSheet(f"font-size: 11px; font-weight: 500; color: {COLORS['text']};")
            row.addWidget(val)
            app_layout.addLayout(row)

        self._content_layout.insertWidget(idx, app_info)
        idx += 1

        # 3. CONTACT
        if detail.contact:
            self._content_layout.insertWidget(idx, _SectionHeader("CONTACT"))
            idx += 1
            contact_frame = QFrame()
            cl = QVBoxLayout(contact_frame)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(2)

            name_lbl = QLabel(detail.contact.name)
            name_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
            cl.addWidget(name_lbl)

            if detail.contact.designation:
                desg = QLabel(detail.contact.designation)
                desg.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
                cl.addWidget(desg)

            email_lbl = QLabel(detail.contact.email)
            email_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['info']};")
            email_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            cl.addWidget(email_lbl)

            self._content_layout.insertWidget(idx, contact_frame)
            idx += 1

        # 4. CADENCE
        if detail.follow_ups:
            self._content_layout.insertWidget(idx, _SectionHeader("FOLLOW-UP CADENCE"))
            idx += 1
            cadence = CadenceTimeline(detail.follow_ups, detail.application_id)
            cadence.pause_requested.connect(self.pause_cadence.emit)
            cadence.resume_requested.connect(self.resume_cadence.emit)
            cadence.stop_requested.connect(self.stop_cadence.emit)
            cadence.execute_now.connect(self.execute_followup.emit)
            self._content_layout.insertWidget(idx, cadence)
            idx += 1

        # 5. RESUME SNAPSHOT
        self._content_layout.insertWidget(idx, _SectionHeader("RESUME SNAPSHOT"))
        idx += 1
        resume_frame = QFrame()
        resume_frame.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        rl = QVBoxLayout(resume_frame)
        rl.setContentsMargins(8, 8, 8, 8)
        rl.setSpacing(4)

        if detail.resume:
            r_name = QLabel(f"📎 {detail.resume.name}")
            r_name.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
            r_name.setWordWrap(True)
            rl.addWidget(r_name)

            r_meta = QLabel(f"{detail.resume.role_target} · {detail.resume.version_tag}")
            r_meta.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            rl.addWidget(r_meta)

            row_status = QHBoxLayout()
            integrity = "✓ Verified File" if detail.resume.file_exists else "⚠ Missing File"
            integrity_color = COLORS["success"] if detail.resume.file_exists else COLORS["danger"]
            r_integrity = QLabel(integrity)
            r_integrity.setStyleSheet(f"font-size: 10px; font-weight: 600; color: {integrity_color};")
            row_status.addWidget(r_integrity)
            row_status.addStretch(1)

            if detail.resume.file_exists and detail.resume.file_path:
                btn_open = QPushButton("📄 Open PDF")
                btn_open.setFixedHeight(22)
                btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
                btn_open.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['surface_hover']};
                        color: {COLORS['text']};
                        border: 1px solid {COLORS['border']};
                        border-radius: 4px;
                        font-size: 10px;
                        padding: 0 8px;
                    }}
                    QPushButton:hover {{
                        border-color: {COLORS['primary']};
                        color: {COLORS['primary']};
                    }}
                """)
                fp = detail.resume.file_path
                btn_open.clicked.connect(lambda *_, p=fp: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
                row_status.addWidget(btn_open)

            rl.addLayout(row_status)
        else:
            no_r = QLabel("No resume linked to this application.")
            no_r.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
            rl.addWidget(no_r)

        self._content_layout.insertWidget(idx, resume_frame)
        idx += 1

    def clear(self):
        """Clears all sections."""
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
