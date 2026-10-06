"""
Step 7: Job Search Strategy & Preferences.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Pre-populates intelligently from AI extracted resume data and allows direct editing.
"""

from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QCheckBox, QFrame, QGridLayout
)
from app.ui.theme import COLORS


class StepPreferencesWidget(QWidget):
    """Step 7: Job search criteria and strategy configuration widget."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        lbl_badge = QLabel("STEP 7: TARGET JOB SEARCH STRATEGY")
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

        lbl_title = QLabel("Job Search Criteria & Strategy")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Configure target role titles, locations, and negative keywords. "
            "These are auto-suggested from your AI resume extraction and can be freely edited."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # 1. Target Roles Frame
        frame_roles = QFrame()
        frame_roles.setObjectName("frame_roles")
        frame_roles.setStyleSheet(f"""
            #frame_roles {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            #frame_roles QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        r_layout = QVBoxLayout(frame_roles)
        r_layout.setContentsMargins(16, 14, 16, 14)
        r_layout.setSpacing(10)

        lbl_r = QLabel("Target Role Titles (Comma-separated) *")
        lbl_r.setStyleSheet(self._section_title_qss())
        self.txt_titles = QLineEdit()
        self.txt_titles.setPlaceholderText("e.g. RPA Developer, AI Automation Engineer, Python Backend Engineer")
        self.txt_titles.setStyleSheet(self._input_qss())
        r_layout.addWidget(lbl_r)
        r_layout.addWidget(self.txt_titles)

        lbl_loc = QLabel("Preferred Locations (Comma-separated) *")
        lbl_loc.setStyleSheet(self._section_title_qss())
        self.txt_locations = QLineEdit()
        self.txt_locations.setPlaceholderText("e.g. Remote, Delhi, Noida, Bengaluru, San Francisco")
        self.txt_locations.setStyleSheet(self._input_qss())
        r_layout.addWidget(lbl_loc)
        r_layout.addWidget(self.txt_locations)

        layout.addWidget(frame_roles)

        # 2. Workplace Arrangement & Experience Level
        frame_filters = QFrame()
        frame_filters.setObjectName("frame_filters")
        frame_filters.setStyleSheet(f"""
            #frame_filters {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            #frame_filters QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        f_layout = QGridLayout(frame_filters)
        f_layout.setContentsMargins(16, 14, 16, 14)
        f_layout.setSpacing(12)

        lbl_work = QLabel("Workplace Type:")
        lbl_work.setStyleSheet(self._section_title_qss())
        f_layout.addWidget(lbl_work, 0, 0)

        self.chk_remote = QCheckBox("Remote")
        self.chk_remote.setChecked(True)
        self.chk_remote.setStyleSheet(self._check_qss())
        self.chk_hybrid = QCheckBox("Hybrid")
        self.chk_hybrid.setChecked(True)
        self.chk_hybrid.setStyleSheet(self._check_qss())
        self.chk_onsite = QCheckBox("On-site")
        self.chk_onsite.setStyleSheet(self._check_qss())

        work_box = QHBoxLayout()
        work_box.addWidget(self.chk_remote)
        work_box.addWidget(self.chk_hybrid)
        work_box.addWidget(self.chk_onsite)
        work_box.addStretch()
        f_layout.addLayout(work_box, 0, 1)

        lbl_exp = QLabel("Experience Level:")
        lbl_exp.setStyleSheet(self._section_title_qss())
        f_layout.addWidget(lbl_exp, 1, 0)

        self.chk_entry = QCheckBox("Entry-Level")
        self.chk_entry.setStyleSheet(self._check_qss())
        self.chk_mid = QCheckBox("Mid-Senior")
        self.chk_mid.setChecked(True)
        self.chk_mid.setStyleSheet(self._check_qss())
        self.chk_lead = QCheckBox("Lead / Architect")
        self.chk_lead.setStyleSheet(self._check_qss())

        exp_box = QHBoxLayout()
        exp_box.addWidget(self.chk_entry)
        exp_box.addWidget(self.chk_mid)
        exp_box.addWidget(self.chk_lead)
        exp_box.addStretch()
        f_layout.addLayout(exp_box, 1, 1)

        layout.addWidget(frame_filters)

        # 3. Exclusions / Negative Keywords
        frame_neg = QFrame()
        frame_neg.setObjectName("frame_neg")
        frame_neg.setStyleSheet(f"""
            #frame_neg {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            #frame_neg QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        n_layout = QVBoxLayout(frame_neg)
        n_layout.setContentsMargins(16, 14, 16, 14)
        n_layout.setSpacing(8)

        lbl_neg = QLabel("Negative Keywords / Exclusions (Optional)")
        lbl_neg.setStyleSheet(self._section_title_qss())
        self.txt_exclusions = QLineEdit()
        self.txt_exclusions.setPlaceholderText("e.g. Unpaid, Clearance Required, Java, C++, Contract")
        self.txt_exclusions.setStyleSheet(self._input_qss())
        n_layout.addWidget(lbl_neg)
        n_layout.addWidget(self.txt_exclusions)

        layout.addWidget(frame_neg)
        layout.addStretch()

    def load_preferences(self, prefs: Dict[str, Any], extracted_data: Optional[Dict[str, Any]] = None):
        """Loads saved preferences or intelligently suggests from AI extracted profile."""
        titles = prefs.get("titles") or prefs.get("target_roles") or []
        locations = prefs.get("locations") or []
        exclusions = prefs.get("negative_keywords") or prefs.get("excluded_keywords") or []

        # If empty, suggest from AI extraction
        if not titles and extracted_data:
            role = extracted_data.get("current_title") or extracted_data.get("headline")
            if isinstance(role, dict):
                role = role.get("value")
            if role:
                titles = [str(role).strip(), f"{str(role).strip()} Developer"]

        if not locations and extracted_data:
            city = extracted_data.get("current_city")
            if isinstance(city, dict):
                city = city.get("value")
            if city:
                locations = [str(city).strip(), "Remote"]

        if isinstance(titles, list):
            self.txt_titles.setText(", ".join(str(t) for t in titles if t))
        elif isinstance(titles, str):
            self.txt_titles.setText(titles)

        if isinstance(locations, list):
            self.txt_locations.setText(", ".join(str(l) for l in locations if l))
        elif isinstance(locations, str):
            self.txt_locations.setText(locations)

        if isinstance(exclusions, list):
            self.txt_exclusions.setText(", ".join(str(e) for e in exclusions if e))

    def get_preferences_payload(self) -> Dict[str, Any]:
        titles = [t.strip() for t in self.txt_titles.text().split(",") if t.strip()]
        locations = [l.strip() for l in self.txt_locations.text().split(",") if l.strip()]
        exclusions = [e.strip() for e in self.txt_exclusions.text().split(",") if e.strip()]

        workplace_types = []
        if self.chk_remote.isChecked(): workplace_types.append("Remote")
        if self.chk_hybrid.isChecked(): workplace_types.append("Hybrid")
        if self.chk_onsite.isChecked(): workplace_types.append("On-site")

        return {
            "titles": titles,
            "locations": locations,
            "workplace_types": workplace_types,
            "negative_keywords": exclusions,
        }

    # Stylesheet Helpers

    def _section_title_qss(self) -> str:
        return f"font-size: 13px; font-weight: 700; color: {COLORS['text']};"

    def _input_qss(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border: 1px solid {COLORS['primary']};
            }}
        """

    def _check_qss(self) -> str:
        return f"""
            QCheckBox {{
                font-size: 12px;
                color: {COLORS['text']};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
            }}
        """
