"""Thread View — Clean email correspondence display (no chat bubbles).

Center of the recruitment workspace. Renders each message as a professional
email block with:
  - Direction indicator (📥 Inbound / 📤 Outbound)
  - Sender/recipient with formatted timestamp
  - Full message body with expandable long messages
  - Attachment chips and resume version badges
  - Sent resume lineage card

Design: Hairline left accent bars, clean typography, selectable text.
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
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
    ConversationDetailViewModel,
    TimelineMessageViewModel,
    PresentationConversationState,
)
from app.ui.theme import COLORS

logger = logging.getLogger("JobPilot.Outreach.ThreadView")

_MAX_COLLAPSED_CHARS = 200


class MessageBlock(QFrame):
    """A single email message in the thread (professional correspondence style)."""

    def __init__(self, msg: TimelineMessageViewModel, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._msg = msg
        self._expanded = len(msg.body_text) <= _MAX_COLLAPSED_CHARS

        is_inbound = msg.direction == "INBOUND"

        # Accent bar color
        accent = COLORS["info"] if is_inbound else COLORS["primary"]
        bg = "#1C2128" if is_inbound else "#161B22"

        self.setStyleSheet(f"""
            MessageBlock {{
                background: {bg};
                border-left: 3px solid {accent};
                border-top: none;
                border-right: none;
                border-bottom: none;
                border-radius: 4px;
                margin: 4px 0;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: direction icon + name + email + timestamp
        header = QHBoxLayout()
        header.setSpacing(6)

        icon = "📥" if is_inbound else "📤"
        sender_name = msg.sender_email or "You"
        if not is_inbound:
            sender_name = "You"

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 12px;")
        header.addWidget(icon_label)

        name_label = QLabel(sender_name)
        name_label.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {COLORS['text']};
        """)
        header.addWidget(name_label)

        header.addStretch(1)

        time_str = ""
        if msg.occurred_at:
            dt = msg.occurred_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            time_str = dt.strftime("%b %d, %Y, %I:%M %p")
        time_label = QLabel(time_str)
        time_label.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_dark']};
        """)
        header.addWidget(time_label)

        layout.addLayout(header)

        # Subject (show only if present and different from thread)
        if msg.subject:
            subject_label = QLabel(msg.subject)
            subject_label.setStyleSheet(f"""
                font-size: 12px;
                font-weight: 600;
                color: {COLORS['text_muted']};
                margin-bottom: 2px;
            """)
            layout.addWidget(subject_label)

        # Body text
        body_text = msg.body_text
        if not self._expanded:
            body_text = body_text[:_MAX_COLLAPSED_CHARS] + "…"

        self._body_label = QLabel(body_text)
        self._body_label.setWordWrap(True)
        self._body_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._body_label.setStyleSheet(f"""
            font-size: 13px;
            color: {COLORS['text']};
            line-height: 1.45;
        """)
        layout.addWidget(self._body_label)

        # Expand toggle
        if len(msg.body_text) > _MAX_COLLAPSED_CHARS:
            self._toggle_btn = QPushButton("Read full email ▼" if not self._expanded else "Collapse ▲")
            self._toggle_btn.setFlat(True)
            self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    color: {COLORS['info']};
                    font-size: 11px;
                    font-weight: 500;
                    border: none;
                    padding: 2px 0;
                    text-align: left;
                }}
                QPushButton:hover {{
                    color: {COLORS['primary']};
                }}
            """)
            self._toggle_btn.clicked.connect(self._toggle_expand)
            layout.addWidget(self._toggle_btn)

        # Attachment chip
        if msg.attachment_path:
            chip_layout = QHBoxLayout()
            chip_layout.setSpacing(6)

            file_name = msg.attachment_name or os.path.basename(msg.attachment_path)
            file_exists = os.path.isfile(msg.attachment_path) if msg.attachment_path else False
            status_badge = "✓ Verified" if file_exists else "⚠ Missing"

            chip = QLabel(f"📄 {file_name} · {status_badge}")
            chip.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['text_muted']};
                background: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 3px 8px;
            """)
            chip_layout.addWidget(chip)
            chip_layout.addStretch(1)
            layout.addLayout(chip_layout)

        # Resume version badge (outbound only)
        if not is_inbound and msg.resume_version_tag:
            resume_badge = QLabel(f"📎 Resume {msg.resume_version_tag}")
            resume_badge.setStyleSheet(f"""
                font-size: 10px;
                color: {COLORS['success']};
                background: {COLORS['success_subtle']};
                border-radius: 3px;
                padding: 2px 6px;
            """)
            layout.addWidget(resume_badge)

        # Error indicator
        if msg.error_message:
            error_label = QLabel(f"⚠ {msg.error_message}")
            error_label.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['danger']};
                background: {COLORS['danger_subtle']};
                border-radius: 3px;
                padding: 3px 6px;
            """)
            layout.addWidget(error_label)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        if self._expanded:
            self._body_label.setText(self._msg.body_text)
            self._toggle_btn.setText("Collapse ▲")
        else:
            self._body_label.setText(self._msg.body_text[:_MAX_COLLAPSED_CHARS] + "…")
            self._toggle_btn.setText("Read full email ▼")


class ThreadHeader(QFrame):
    """Thread header showing company, job title, and recruitment status pill."""

    def __init__(
        self,
        company_name: str,
        job_title: str,
        recruitment_status: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        company_label = QLabel(company_name)
        company_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        layout.addWidget(company_label)

        sep = QLabel("·")
        sep.setStyleSheet(f"color: {COLORS['text_dark']}; font-size: 14px;")
        layout.addWidget(sep)

        job_label = QLabel(job_title)
        job_label.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 500;
            color: {COLORS['text_muted']};
        """)
        layout.addWidget(job_label)

        layout.addStretch(1)

        # Status pill
        status_colors = {
            "APPLIED": COLORS["info"],
            "RECRUITER_CONTACTED": COLORS["info"],
            "UNDER_REVIEW": COLORS["warning"],
            "INTERVIEWING": COLORS["purple"],
            "OFFER": COLORS["success"],
            "REJECTED": COLORS["danger"],
            "WITHDRAWN": COLORS["text_muted"],
        }
        pill_color = status_colors.get(recruitment_status, COLORS["text_muted"])
        status_pill = QLabel(recruitment_status.replace("_", " ").title())
        status_pill.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {pill_color};
            background: {pill_color}18;
            border-radius: 4px;
            padding: 3px 10px;
        """)
        layout.addWidget(status_pill)

        self.setStyleSheet(f"""
            ThreadHeader {{
                background: {COLORS['surface']};
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)


class RecruiterIntentCard(QFrame):
    """AI-derived recruiter intent summary card (shown when inbound exists)."""

    def __init__(
        self,
        headline: str,
        rationale: str,
        confidence: str = "High",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(f"✨ Recruiter Intent: {headline}")
        title.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 600;
            color: {COLORS['accent']};
        """)
        header.addWidget(title)

        header.addStretch(1)

        conf_badge = QLabel(f"({confidence} Confidence)")
        conf_badge.setStyleSheet(f"""
            font-size: 10px;
            color: {COLORS['text_dark']};
        """)
        header.addWidget(conf_badge)
        layout.addLayout(header)

        why = QLabel(f'Why: "{rationale}"')
        why.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
            font-style: italic;
        """)
        why.setWordWrap(True)
        layout.addWidget(why)

        self.setStyleSheet(f"""
            RecruiterIntentCard {{
                background: {COLORS['surface']};
                border: 1px solid {COLORS['accent']}40;
                border-radius: 6px;
                margin: 4px 16px;
            }}
        """)


class ThreadView(QWidget):
    """Central thread panel showing email correspondence and intent card."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Placeholder when no conversation selected
        self._empty_state = QLabel("Select a conversation to view the thread")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setStyleSheet(f"""
            color: {COLORS['text_dark']};
            font-size: 14px;
            padding: 60px;
        """)
        self._main_layout.addWidget(self._empty_state)

        self.setStyleSheet(f"""
            ThreadView {{
                background: {COLORS['background']};
            }}
        """)

    def load_conversation(self, detail: ConversationDetailViewModel):
        """Replaces thread content with new conversation detail."""
        # Clear everything
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Thread header
        header = ThreadHeader(
            company_name=detail.company_name,
            job_title=detail.job_title,
            recruitment_status=detail.recruitment_status,
        )
        self._main_layout.addWidget(header)

        # Recruiter intent card (if action-requiring state)
        if detail.state in (
            PresentationConversationState.NEEDS_ACTION,
            PresentationConversationState.REPLIED,
        ):
            intent_card = RecruiterIntentCard(
                headline=detail.next_action.headline,
                rationale=detail.next_action.rationale,
            )
            self._main_layout.addWidget(intent_card)

        # Scroll area for messages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {COLORS['background']};
                border: none;
            }}
            QScrollBar:vertical {{
                width: 6px;
                background: transparent;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                border-radius: 3px;
                min-height: 30px;
            }}
        """)

        messages_container = QWidget()
        messages_layout = QVBoxLayout(messages_container)
        messages_layout.setContentsMargins(16, 8, 16, 8)
        messages_layout.setSpacing(8)

        for msg in detail.messages:
            block = MessageBlock(msg)
            messages_layout.addWidget(block)

        messages_layout.addStretch(1)
        scroll.setWidget(messages_container)
        self._scroll_area = scroll

        self._main_layout.addWidget(scroll, 1)

    def scroll_to_bottom(self):
        """Scrolls message thread down to the latest message."""
        if hasattr(self, "_scroll_area") and self._scroll_area:
            bar = self._scroll_area.verticalScrollBar()
            bar.setValue(bar.maximum())

    def clear(self):
        """Returns to empty state."""
        while self._main_layout.count():
            item = self._main_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._empty_state = QLabel("Select a conversation to view the thread")
        self._empty_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_state.setStyleSheet(f"""
            color: {COLORS['text_dark']};
            font-size: 14px;
            padding: 60px;
        """)
        self._main_layout.addWidget(self._empty_state)
