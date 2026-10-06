"""
Step 5: Candidate Profile Review with Complete Grouped Database Schema.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Exposes the real JobPilot candidate profile schema with field provenance badges and conflict resolution.
"""

from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QScrollArea, QFrame,
    QGridLayout, QComboBox, QPushButton, QDialog,
    QRadioButton, QButtonGroup
)
from app.ui.theme import COLORS


class ProvenancePill(QLabel):
    """Subtle badge displaying field source."""
    def __init__(self, source_text: str = "Existing profile", parent=None):
        super().__init__(parent)
        self.set_source(source_text)

    def set_source(self, text: str):
        if "AI" in text or "Resume" in text:
            color = COLORS["info"]
            bg = COLORS["info_subtle"]
        elif "User" in text or "Verified" in text:
            color = COLORS["success"]
            bg = COLORS["success_subtle"]
        elif "Not found" in text:
            color = COLORS["warning"]
            bg = COLORS["warning_subtle"]
        else:
            color = COLORS["text_muted"]
            bg = COLORS["surface_alt"]

        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: {bg};
                font-size: 10px;
                font-weight: 700;
                padding: 2px 8px;
                border-radius: 4px;
                border: 1px solid {color}33;
            }}
        """)


class ConflictBanner(QFrame):
    """Interactive conflict resolver card."""
    resolved = Signal(str, str)  # field, chosen_value

    def __init__(self, conflict: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.conflict = conflict
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['warning']};
                border-left: 4px solid {COLORS['warning']};
                border-radius: 6px;
                padding: 10px 14px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        title = self.conflict.get("title", "Field")
        old_val = self.conflict.get("existing_value", "")
        new_val = self.conflict.get("new_value", "")

        lbl_head = QLabel(f"⚠ Conflicting Data for '{title}':")
        lbl_head.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {COLORS['warning']};")
        layout.addWidget(lbl_head)

        row = QHBoxLayout()
        self.btn_keep_old = QPushButton(f"Keep Existing: {old_val}")
        self.btn_keep_old.setStyleSheet(self._btn_qss())
        self.btn_use_new = QPushButton(f"Use Resume: {new_val}")
        self.btn_use_new.setStyleSheet(self._btn_qss(primary=True))

        self.btn_keep_old.clicked.connect(lambda: self._on_choose(old_val))
        self.btn_use_new.clicked.connect(lambda: self._on_choose(new_val))

        row.addWidget(self.btn_keep_old)
        row.addWidget(self.btn_use_new)
        row.addStretch()
        layout.addLayout(row)

    def _on_choose(self, val: str):
        self.resolved.emit(self.conflict["field"], val)
        self.setVisible(False)

    def _btn_qss(self, primary: bool = False) -> str:
        if primary:
            return f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: #FFFFFF;
                    font-size: 11px;
                    font-weight: 700;
                    border-radius: 4px;
                    padding: 4px 10px;
                }}
            """
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                font-size: 11px;
                font-weight: 600;
                border-radius: 4px;
                padding: 4px 10px;
            }}
        """


class StepProfileWidget(QWidget):
    """Step 5: Full candidate profile review matching the complete database schema."""
    profile_saved = Signal(dict)

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self._conflicts_container: Optional[QVBoxLayout] = None
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
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Header
        lbl_badge = QLabel("STEP 5: CANDIDATE PROFILE REVIEW")
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 3px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("Candidate Profile Review")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Review your candidate identity sourced from your database records and uploaded resume. "
            "Every field shows its authoritative source. Missing fields are left blank for you to provide."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # Conflict Resolution Area (Dynamic)
        self.conflicts_box = QFrame()
        self.conflicts_box.setVisible(False)
        self.conflicts_box.setStyleSheet("QFrame { background: transparent; border: none; }")
        self._conflicts_layout = QVBoxLayout(self.conflicts_box)
        self._conflicts_layout.setContentsMargins(0, 0, 0, 0)
        self._conflicts_layout.setSpacing(8)
        layout.addWidget(self.conflicts_box)

        # 1. Personal & Contact
        layout.addWidget(self._build_personal_section())

        # 2. Location & Relocation
        layout.addWidget(self._build_location_section())

        # 3. Professional Roles & Experience
        layout.addWidget(self._build_professional_section())

        # 4. Compensation & Notice Period
        layout.addWidget(self._build_compensation_section())

        # 5. Technical Skills & Primary Competencies
        layout.addWidget(self._build_skills_section())

        # 6. Portfolio & Online Profiles
        layout.addWidget(self._build_links_section())

        # 7. Sensitive Demographics (Optional & User-Controlled Only)
        layout.addWidget(self._build_demographics_section())

        scroll.setWidget(container)
        root_layout.addWidget(scroll)

    # Section Builders

    def _build_personal_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("1. Personal Identity & Contact Information")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("First Name *"), 0, 0)
        self.txt_first_name = QLineEdit()
        self.txt_first_name.setStyleSheet(self._input_qss())
        self.pill_first_name = ProvenancePill()
        grid.addWidget(self.txt_first_name, 0, 1)
        grid.addWidget(self.pill_first_name, 0, 2)

        grid.addWidget(QLabel("Middle Name"), 1, 0)
        self.txt_middle_name = QLineEdit()
        self.txt_middle_name.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_middle_name, 1, 1)

        grid.addWidget(QLabel("Last Name *"), 2, 0)
        self.txt_last_name = QLineEdit()
        self.txt_last_name.setStyleSheet(self._input_qss())
        self.pill_last_name = ProvenancePill()
        grid.addWidget(self.txt_last_name, 2, 1)
        grid.addWidget(self.pill_last_name, 2, 2)

        grid.addWidget(QLabel("Email Address *"), 3, 0)
        self.txt_email = QLineEdit()
        self.txt_email.setStyleSheet(self._input_qss())
        self.pill_email = ProvenancePill()
        grid.addWidget(self.txt_email, 3, 1)
        grid.addWidget(self.pill_email, 3, 2)

        grid.addWidget(QLabel("Phone Number *"), 4, 0)
        self.txt_phone = QLineEdit()
        self.txt_phone.setStyleSheet(self._input_qss())
        self.pill_phone = ProvenancePill()
        grid.addWidget(self.txt_phone, 4, 1)
        grid.addWidget(self.pill_phone, 4, 2)

        layout.addLayout(grid)
        return card

    def _build_location_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("2. Location & Relocation")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Current City"), 0, 0)
        self.txt_city = QLineEdit()
        self.txt_city.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_city, 0, 1)

        grid.addWidget(QLabel("State / Province"), 0, 2)
        self.txt_state = QLineEdit()
        self.txt_state.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_state, 0, 3)

        grid.addWidget(QLabel("Country"), 1, 0)
        self.txt_country = QLineEdit()
        self.txt_country.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_country, 1, 1)

        grid.addWidget(QLabel("Postal / Zip Code"), 1, 2)
        self.txt_zip = QLineEdit()
        self.txt_zip.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_zip, 1, 3)

        grid.addWidget(QLabel("Open to Relocation"), 2, 0)
        self.cmb_relocate = QComboBox()
        self.cmb_relocate.addItems(["Yes", "No", "Remote Only"])
        self.cmb_relocate.setStyleSheet(self._combo_qss())
        grid.addWidget(self.cmb_relocate, 2, 1)

        layout.addLayout(grid)
        return card

    def _build_professional_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("3. Professional Experience & Role")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Headline / Title *"), 0, 0)
        self.txt_headline = QLineEdit()
        self.txt_headline.setStyleSheet(self._input_qss())
        self.pill_headline = ProvenancePill()
        grid.addWidget(self.txt_headline, 0, 1)
        grid.addWidget(self.pill_headline, 0, 2)

        grid.addWidget(QLabel("Current Employer"), 1, 0)
        self.txt_employer = QLineEdit()
        self.txt_employer.setStyleSheet(self._input_qss())
        self.pill_employer = ProvenancePill()
        grid.addWidget(self.txt_employer, 1, 1)
        grid.addWidget(self.pill_employer, 1, 2)

        grid.addWidget(QLabel("Total Experience (Years) *"), 2, 0)
        self.txt_experience = QLineEdit()
        self.txt_experience.setStyleSheet(self._input_qss())
        self.pill_exp = ProvenancePill()
        grid.addWidget(self.txt_experience, 2, 1)
        grid.addWidget(self.pill_exp, 2, 2)

        grid.addWidget(QLabel("Professional Summary"), 3, 0)
        self.txt_summary = QTextEdit()
        self.txt_summary.setMaximumHeight(85)
        self.txt_summary.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_summary, 3, 1)

        layout.addLayout(grid)
        return card

    def _build_compensation_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("4. Target Compensation & Notice Period")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Current CTC / Annual"), 0, 0)
        self.txt_current_ctc = QLineEdit()
        self.txt_current_ctc.setPlaceholderText("e.g. 350000")
        self.txt_current_ctc.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_current_ctc, 0, 1)

        grid.addWidget(QLabel("Expected CTC / Annual"), 0, 2)
        self.txt_expected_ctc = QLineEdit()
        self.txt_expected_ctc.setPlaceholderText("e.g. 550000")
        self.txt_expected_ctc.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_expected_ctc, 0, 3)

        grid.addWidget(QLabel("Notice Period (Days) *"), 1, 0)
        self.txt_notice = QLineEdit()
        self.txt_notice.setPlaceholderText("e.g. 0 (Immediate), 15, 30")
        self.txt_notice.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_notice, 1, 1)

        layout.addLayout(grid)
        return card

    def _build_skills_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("5. Technical Skills & Primary Competencies")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        lbl_hint = QLabel("Comma-separated technical skills. JobPilot uses these to compute ATS match scores.")
        lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_hint)

        self.txt_skills = QTextEdit()
        self.txt_skills.setMaximumHeight(70)
        self.txt_skills.setStyleSheet(self._input_qss())
        layout.addWidget(self.txt_skills)
        return card

    def _build_links_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(self._card_qss())
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        lbl = QLabel("6. Portfolio & Professional Profiles")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("LinkedIn URL"), 0, 0)
        self.txt_linkedin = QLineEdit()
        self.txt_linkedin.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_linkedin, 0, 1)

        grid.addWidget(QLabel("GitHub URL"), 1, 0)
        self.txt_github = QLineEdit()
        self.txt_github.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_github, 1, 1)

        grid.addWidget(QLabel("Portfolio / Website"), 2, 0)
        self.txt_portfolio = QLineEdit()
        self.txt_portfolio.setStyleSheet(self._input_qss())
        grid.addWidget(self.txt_portfolio, 2, 1)

        layout.addLayout(grid)
        return card

    def _build_demographics_section(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(8)

        lbl = QLabel("7. Sensitive Demographics (Optional & Strictly User-Controlled)")
        lbl.setStyleSheet(self._section_title_qss())
        layout.addWidget(lbl)

        lbl_notice = QLabel(
            "🔒 JobPilot privacy invariant: These compliance fields are NEVER inferred by AI models. "
            "They are strictly user-controlled for company ATS equal opportunity compliance."
        )
        lbl_notice.setWordWrap(True)
        lbl_notice.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_notice)

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Gender"), 0, 0)
        self.cmb_gender = QComboBox()
        self.cmb_gender.addItems(["Prefer not to say", "Male", "Female", "Non-binary", "Decline"])
        self.cmb_gender.setStyleSheet(self._combo_qss())
        grid.addWidget(self.cmb_gender, 0, 1)

        grid.addWidget(QLabel("Ethnicity / Race"), 0, 2)
        self.cmb_ethnicity = QComboBox()
        self.cmb_ethnicity.addItems(["Decline", "Asian", "White", "Black or African American", "Hispanic or Latino", "Two or More Races"])
        self.cmb_ethnicity.setStyleSheet(self._combo_qss())
        grid.addWidget(self.cmb_ethnicity, 0, 3)

        layout.addLayout(grid)
        return card

    # Loading & Pre-population

    def load_initial_data(self, extracted_data: Optional[Dict[str, Any]] = None):
        """Prepopulates all fields from real database profile and overlays extracted resume findings."""
        # 1. Load authoritative existing database records
        existing = self.setup_service.get_existing_profile()
        pers = existing.get("personal", {})
        prof = existing.get("professional", {})
        skills = existing.get("skills", [])

        self.txt_first_name.setText(pers.get("first_name", ""))
        self.txt_middle_name.setText(pers.get("middle_name", ""))
        self.txt_last_name.setText(pers.get("last_name", ""))
        self.txt_email.setText(pers.get("email", ""))
        self.txt_phone.setText(pers.get("phone_number", ""))
        self.txt_city.setText(pers.get("current_city", ""))
        self.txt_state.setText(pers.get("state", ""))
        self.txt_country.setText(pers.get("country", ""))
        self.txt_zip.setText(pers.get("zipcode", ""))

        if pers.get("willing_to_relocate") is False:
            self.cmb_relocate.setCurrentText("No")
        else:
            self.cmb_relocate.setCurrentText("Yes")

        self.txt_headline.setText(prof.get("headline", prof.get("current_title", "")))
        self.txt_employer.setText(prof.get("current_employer", ""))
        self.txt_experience.setText(str(prof.get("years_of_experience", 2.0)))
        self.txt_summary.setPlainText(prof.get("summary", ""))

        self.txt_current_ctc.setText(str(prof.get("current_ctc", "")))
        self.txt_expected_ctc.setText(str(prof.get("expected_ctc", "")))
        self.txt_notice.setText(str(prof.get("notice_period_days", 30)))

        if isinstance(skills, list):
            self.txt_skills.setPlainText(", ".join(str(s) for s in skills))

        self.txt_linkedin.setText(prof.get("linkedin_url", ""))
        self.txt_github.setText(prof.get("github_url", ""))
        self.txt_portfolio.setText(prof.get("portfolio_url", ""))

        # 2. Check for conflicts if resume extraction was performed
        if extracted_data:
            conflicts = self.setup_service.detect_conflicts(extracted_data)
            if conflicts:
                # Clear previous conflict banners
                while self._conflicts_layout.count():
                    child = self._conflicts_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()

                for c in conflicts:
                    banner = ConflictBanner(c, self)
                    banner.resolved.connect(self._on_conflict_resolved)
                    self._conflicts_layout.addWidget(banner)
                self.conflicts_box.setVisible(True)

            # Update provenance badges for extracted values
            def get_src(key):
                if key in extracted_data and extracted_data[key].get("value"):
                    return "Resume · AI extracted"
                return "Existing profile"

            self.pill_first_name.set_source(get_src("first_name"))
            self.pill_last_name.set_source(get_src("last_name"))
            self.pill_email.set_source(get_src("email"))
            self.pill_phone.set_source(get_src("phone_number"))
            self.pill_headline.set_source(get_src("current_title"))
            self.pill_employer.set_source(get_src("current_employer"))
            self.pill_exp.set_source(get_src("years_of_experience"))

    def _on_conflict_resolved(self, field: str, chosen_val: str):
        if field == "years_of_experience":
            # Extract digits if "X years"
            digits = "".join(c for c in chosen_val if c.isdigit() or c == ".")
            self.txt_experience.setText(digits or chosen_val)
        elif field == "current_title":
            self.txt_headline.setText(chosen_val)
        elif field == "current_employer":
            self.txt_employer.setText(chosen_val)

    def get_profile_payload(self) -> Dict[str, Any]:
        """Constructs clean dictionary payload for ProfileService."""
        skills_raw = self.txt_skills.toPlainText().strip()
        skills_list = [s.strip() for s in skills_raw.split(",") if s.strip()]

        return {
            "personal": {
                "first_name": self.txt_first_name.text().strip(),
                "middle_name": self.txt_middle_name.text().strip(),
                "last_name": self.txt_last_name.text().strip(),
                "email": self.txt_email.text().strip(),
                "phone": self.txt_phone.text().strip(),
                "current_city": self.txt_city.text().strip(),
                "state": self.txt_state.text().strip(),
                "country": self.txt_country.text().strip(),
                "zipcode": self.txt_zip.text().strip(),
                "linkedin_url": self.txt_linkedin.text().strip(),
                "github_url": self.txt_github.text().strip(),
                "portfolio_url": self.txt_portfolio.text().strip(),
            },
            "professional": {
                "current_title": self.txt_headline.text().strip(),
                "current_employer": self.txt_employer.text().strip(),
                "years_of_experience": float(self.txt_experience.text().strip() or 2.0),
                "current_ctc": int(self.txt_current_ctc.text().strip() or 0),
                "expected_ctc": int(self.txt_expected_ctc.text().strip() or 0),
                "notice_period_days": int(self.txt_notice.text().strip() or 30),
                "summary": self.txt_summary.toPlainText().strip(),
            },
            "skills": skills_list,
            "qna": {
                "open_to_relocation": self.cmb_relocate.currentText(),
            }
        }

    # Stylesheet Helpers

    def _card_qss(self) -> str:
        return f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            QLabel {{
                border: none;
                background: transparent;
            }}
        """

    def _section_title_qss(self) -> str:
        return f"font-size: 13px; font-weight: 700; color: {COLORS['text']};"

    def _input_qss(self) -> str:
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
                min-height: 20px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
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
                padding: 6px 10px;
                font-size: 12px;
            }}
        """
