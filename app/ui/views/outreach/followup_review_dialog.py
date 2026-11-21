"""Human-in-the-Loop review dialog for due follow-up cadences."""

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QFrame,
    QWidget,
)

from app.ui.views.outreach.modern_popup import ModernPopup


class FollowUpReviewDialog(QDialog):
    """Presents a structured overview of a due follow-up for user approval before sending."""

    approved_send = Signal(int, str, str)  # (followup_id, subject, body)
    snoozed = Signal(int, int)             # (followup_id, days)
    cancelled_cadence = Signal(int)        # followup_id

    def __init__(self, followup_data: Dict[str, Any], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.followup_data = followup_data
        self.fu_id = followup_data.get("followup_id") or followup_data.get("id", 0)

        self.setWindowTitle("Review Scheduled Follow-Up — JobPilot")
        self.setMinimumWidth(680)
        self.setMinimumHeight(560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #0F1117;
                color: #E6EDF3;
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            }
            QLabel {
                color: #E6EDF3;
                font-size: 13px;
            }
            QLineEdit, QTextEdit {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 6px;
                color: #F0F6FC;
                padding: 10px;
                font-size: 13px;
                selection-background-color: #FF5F15;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 1px solid #FF5F15;
            }
            QPushButton {
                font-weight: 600;
                font-size: 13px;
                border-radius: 6px;
                padding: 10px 18px;
                cursor: pointer;
            }
        """)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        lbl_title = QLabel("Scheduled Follow-Up Review")
        lbl_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #FFFFFF;")
        title_box.addWidget(lbl_title)

        lbl_sub = QLabel("Human confirmation is required before any outreach cadence email is sent.")
        lbl_sub.setStyleSheet("font-size: 13px; color: #8B949E;")
        title_box.addWidget(lbl_sub)
        layout.addLayout(title_box)

        # Overview Card
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #161B22;
                border: 1px solid #30363D;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(8)

        comp = self.followup_data.get("company_name", "Target Company")
        title = self.followup_data.get("job_title", "Position")
        recruiter = self.followup_data.get("contact_name", "Hiring Team")
        rec_email = self.followup_data.get("contact_email", "")
        last_sent = self.followup_data.get("last_email_sent_at", "Unknown")
        step_num = self.followup_data.get("step_number", 1)
        last_subj = self.followup_data.get("last_email_subject", "")

        row1 = QLabel(f"<b>Target:</b> <span style='color: #FF5F15;'>{comp}</span> — <b>{title}</b>")
        row1.setStyleSheet("font-size: 14px;")
        card_layout.addWidget(row1)

        row2 = QLabel(f"<b>Recipient:</b> {recruiter} &lt;{rec_email}&gt; &nbsp;|&nbsp; <b>Cadence:</b> Step {step_num} of 3")
        row2.setStyleSheet("color: #8B949E; font-size: 12px;")
        card_layout.addWidget(row2)

        row3 = QLabel(f"<b>Last Email Sent:</b> {last_sent} (<i>\"{last_subj}\"</i>)")
        row3.setStyleSheet("color: #8B949E; font-size: 12px;")
        card_layout.addWidget(row3)

        layout.addWidget(card)

        # Proposed Subject
        lbl_subj = QLabel("Proposed Subject:")
        lbl_subj.setStyleSheet("font-weight: 600; font-size: 13px; color: #C9D1D9;")
        layout.addWidget(lbl_subj)

        self.txt_subject = QLineEdit(self.followup_data.get("proposed_subject", ""))
        layout.addWidget(self.txt_subject)

        # Proposed Body
        lbl_body = QLabel("Proposed Message (Edit as needed):")
        lbl_body.setStyleSheet("font-weight: 600; font-size: 13px; color: #C9D1D9;")
        layout.addWidget(lbl_body)

        self.txt_body = QTextEdit()
        self.txt_body.setPlainText(self.followup_data.get("proposed_body", ""))
        self.txt_body.setMinimumHeight(140)
        layout.addWidget(self.txt_body)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        btn_cancel = QPushButton("Cancel Cadence")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #F85149;
                border: 1px solid rgba(248, 81, 73, 0.4);
            }
            QPushButton:hover {
                background-color: rgba(248, 81, 73, 0.15);
            }
        """)
        btn_cancel.clicked.connect(self._on_cancel_clicked)
        btn_layout.addWidget(btn_cancel)

        btn_snooze = QPushButton("Snooze 3 Days")
        btn_snooze.setStyleSheet("""
            QPushButton {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
            }
            QPushButton:hover {
                background-color: #30363D;
                color: #FFFFFF;
            }
        """)
        btn_snooze.clicked.connect(self._on_snooze_clicked)
        btn_layout.addWidget(btn_snooze)

        btn_layout.addStretch()

        btn_send = QPushButton("Send Follow-Up Now")
        btn_send.setStyleSheet("""
            QPushButton {
                background-color: #FF5F15;
                color: #FFFFFF;
                border: none;
            }
            QPushButton:hover {
                background-color: #E04E0B;
            }
        """)
        btn_send.clicked.connect(self._on_send_clicked)
        btn_layout.addWidget(btn_send)

        layout.addLayout(btn_layout)

    def _on_send_clicked(self):
        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()
        if not subject or not body:
            ModernPopup.warning(self, "Incomplete Message", "Subject and message body cannot be empty.")
            return
        self.approved_send.emit(self.fu_id, subject, body)
        try:
            from app.services.outreach_coordinator import OutreachCadenceCoordinator
            OutreachCadenceCoordinator.get_instance().execute_approved_followup(
                self.fu_id, custom_subject=subject, custom_body=body
            )
        except Exception:
            pass
        self.accept()

    def _on_snooze_clicked(self):
        self.snoozed.emit(self.fu_id, 3)
        try:
            from app.services.outreach_coordinator import OutreachCadenceCoordinator
            OutreachCadenceCoordinator.get_instance().snooze_followup(self.fu_id, 3)
        except Exception:
            pass
        self.reject()

    def _on_cancel_clicked(self):
        self.cancelled_cadence.emit(self.fu_id)
        try:
            from app.services.outreach_coordinator import OutreachCadenceCoordinator
            OutreachCadenceCoordinator.get_instance().cancel_followup(self.fu_id)
        except Exception:
            pass
        self.reject()
