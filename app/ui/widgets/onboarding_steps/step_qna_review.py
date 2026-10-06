"""
Step 6: Screening Q&A Knowledge Base & Canonical Candidate Facts.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Prevents duplicate questions and provides interactive conflict resolution.
"""

from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QComboBox, QFrame, QScrollArea,
    QPushButton, QDialog, QRadioButton, QButtonGroup
)
from app.ui.theme import COLORS


class ConflictResolutionDialog(QDialog):
    """Modal dialog presenting a conflict between resume data and existing Q&A."""
    def __init__(self, conflict: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.conflict = conflict
        self.chosen_value = conflict.get("new_value", "")
        self.setWindowTitle("Resolve Data Conflict")
        self.setFixedWidth(460)
        self.setStyleSheet(f"background-color: {COLORS['surface']}; color: {COLORS['text']};")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        lbl_title = QLabel(f"⚠ Conflicting Data: {self.conflict.get('title', 'Field')}")
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLORS['warning']};")
        layout.addWidget(lbl_title)

        lbl_desc = QLabel("Information extracted from your resume differs from existing records:")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_desc)

        box = QFrame()
        box.setStyleSheet(f"background-color: {COLORS['surface_alt']}; border-radius: 8px; padding: 12px;")
        b_layout = QVBoxLayout(box)

        self.btn_group = QButtonGroup(self)

        self.rad_existing = QRadioButton(f"Keep Existing: {self.conflict.get('existing_value')}")
        self.rad_new = QRadioButton(f"Update from Resume: {self.conflict.get('new_value')}")
        self.rad_new.setChecked(True)

        self.btn_group.addButton(self.rad_existing, 1)
        self.btn_group.addButton(self.rad_new, 2)

        b_layout.addWidget(self.rad_existing)
        b_layout.addWidget(self.rad_new)
        layout.addWidget(box)

        btn_row = QHBoxLayout()
        btn_confirm = QPushButton("Confirm Choice")
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                font-weight: 700;
                border-radius: 6px;
                padding: 6px 14px;
            }}
        """)
        btn_confirm.clicked.connect(self._on_confirm)
        btn_row.addStretch()
        btn_row.addWidget(btn_confirm)
        layout.addLayout(btn_row)

    def _on_confirm(self):
        if self.rad_existing.isChecked():
            self.chosen_value = self.conflict.get("existing_value", "")
        else:
            self.chosen_value = self.conflict.get("new_value", "")
        self.accept()


class StepQnAReviewWidget(QWidget):
    """Screening Q&A configuration widget with canonical candidate facts."""
    qna_confirmed = Signal(dict)

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(32, 20, 32, 24)
        layout.setSpacing(18)

        lbl_title = QLabel("Screening Q&A Knowledge Base")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Review your canonical screening answers. When automated bots apply to jobs, "
            "JobPilot matches recruiter screening questions to these verified facts with zero hallucination."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # Core Questions Card
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(14)

        lbl_sec = QLabel("Standard Screening Prompts")
        lbl_sec.setStyleSheet("font-size: 14px; font-weight: 700; color: #F0F6FC;")
        c_layout.addWidget(lbl_sec)

        # 1. Authorization
        c_layout.addWidget(QLabel("1. Are you legally authorized to work in your target country?"))
        self.cmb_work_auth = QComboBox()
        self.cmb_work_auth.addItems(["Yes", "No"])
        self.cmb_work_auth.setStyleSheet(self._combo_qss())
        c_layout.addWidget(self.cmb_work_auth)

        # 2. Sponsorship
        c_layout.addWidget(QLabel("2. Will you now or in the future require visa sponsorship?"))
        self.cmb_sponsor = QComboBox()
        self.cmb_sponsor.addItems(["No", "Yes"])
        self.cmb_sponsor.setStyleSheet(self._combo_qss())
        c_layout.addWidget(self.cmb_sponsor)

        # 3. Notice Period
        c_layout.addWidget(QLabel("3. What is your notice period (in days)?"))
        self.txt_notice = QLineEdit("0")
        self.txt_notice.setPlaceholderText("e.g. 0 (Immediate), 15, 30, 60")
        self.txt_notice.setStyleSheet(self._input_qss())
        c_layout.addWidget(self.txt_notice)

        # 4. Relocation
        c_layout.addWidget(QLabel("4. Are you willing to relocate for the role?"))
        self.cmb_relocate = QComboBox()
        self.cmb_relocate.addItems(["Yes", "No", "Negotiable"])
        self.cmb_relocate.setStyleSheet(self._combo_qss())
        c_layout.addWidget(self.cmb_relocate)

        # 5. Total Experience
        c_layout.addWidget(QLabel("5. Total years of professional experience:"))
        self.txt_exp = QLineEdit("3")
        self.txt_exp.setStyleSheet(self._input_qss())
        c_layout.addWidget(self.txt_exp)

        # 6. Education Level
        c_layout.addWidget(QLabel("6. Highest completed education level:"))
        self.cmb_edu = QComboBox()
        self.cmb_edu.addItems(["Bachelor's Degree", "Master's Degree", "Doctorate / Ph.D.", "Associate Degree", "High School"])
        self.cmb_edu.setStyleSheet(self._combo_qss())
        c_layout.addWidget(self.cmb_edu)

        layout.addWidget(card)
        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    def load_from_profile(self, profile: Dict[str, Any]):
        if "years_of_experience" in profile:
            self.txt_exp.setText(str(profile["years_of_experience"]))
        elif "experience_years" in profile:
            val = profile["experience_years"]
            if isinstance(val, dict): val = val.get("value")
            if val: self.txt_exp.setText(str(val))

        if "notice_period" in profile and profile["notice_period"]:
            self.txt_notice.setText(str(profile["notice_period"]))

        if profile.get("work_authorization") is False:
            self.cmb_work_auth.setCurrentText("No")
        else:
            self.cmb_work_auth.setCurrentText("Yes")

        if profile.get("visa_sponsorship") is True:
            self.cmb_sponsor.setCurrentText("Yes")
        else:
            self.cmb_sponsor.setCurrentText("No")

    def prompt_conflicts_if_any(self, new_profile: Dict[str, Any]) -> None:
        """Checks for conflicts and prompts the candidate to resolve them."""
        conflicts = self.setup_service.detect_conflicts(new_profile)
        for conflict in conflicts:
            dlg = ConflictResolutionDialog(conflict, self)
            if dlg.exec():
                chosen = dlg.chosen_value
                if conflict["field"] == "experience_years":
                    self.txt_exp.setText(str(chosen))

    def get_qna_payload(self) -> Dict[str, Any]:
        return {
            "work_authorization": (self.cmb_work_auth.currentText() == "Yes"),
            "visa_sponsorship": (self.cmb_sponsor.currentText() == "Yes"),
            "notice_period_days": int(self.txt_notice.text().strip() or "0"),
            "willing_to_relocate": self.cmb_relocate.currentText(),
            "years_of_experience": self.txt_exp.text().strip(),
            "highest_education": self.cmb_edu.currentText(),
        }

    # Stylesheet Helpers

    def _card_qss(self) -> str:
        return f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 16px;
            }}
        """

    def _input_qss(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
        """

    def _combo_qss(self) -> str:
        return f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 7px 12px;
                font-size: 13px;
            }}
        """
