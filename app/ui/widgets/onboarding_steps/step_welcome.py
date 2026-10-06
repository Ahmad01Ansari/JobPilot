"""
Step 1: Welcome & Overview.
Matches JobPilot ATS/SaaS design tokens (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Includes creative local-first guarantee and privacy manifesto.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QRadioButton, QButtonGroup
)
from app.ui.theme import COLORS


class StepWelcomeWidget(QWidget):
    """Initial onboarding step introducing JobPilot and setting expectations."""
    mode_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header Badge & Title
        lbl_badge = QLabel("JOBPILOT WORKSPACE SETUP")
        lbl_badge.setFixedHeight(22)
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 2px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("Welcome to JobPilot")
        lbl_title.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {COLORS['text']}; letter-spacing: -0.4px;")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "JobPilot automates your recruitment pipeline: importing your resume, configuring verified candidate "
            "facts for zero-hallucination screening, tracking job applications, and executing ATS submissions."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; line-height: 1.4;")
        layout.addWidget(lbl_sub)

        # Local-First Sovereign Privacy Card (Creative Message & Quote)
        privacy_card = QFrame()
        privacy_card.setObjectName("privacy_card")
        privacy_card.setStyleSheet(f"""
            #privacy_card {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border_light']};
                border-left: 3px solid {COLORS['success']};
                border-radius: 8px;
            }}
            #privacy_card QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        p_layout = QVBoxLayout(privacy_card)
        p_layout.setContentsMargins(16, 12, 16, 12)
        p_layout.setSpacing(6)

        lbl_quote = QLabel("“Your career data belongs to you — not the cloud.”")
        lbl_quote.setStyleSheet(f"font-size: 13px; font-weight: 700; font-style: italic; color: {COLORS['primary']};")
        p_layout.addWidget(lbl_quote)

        lbl_guarantee = QLabel(
            "🔒 100% Local & Sovereign Privacy: All your resumes, profile details, screening answers, "
            "and portal credentials stay encrypted exclusively on your local computer. "
            "No online intervention is required, no external tracking exists, and zero data is sent to third-party clouds. "
            "You maintain complete ownership of every job application submitted."
        )
        lbl_guarantee.setWordWrap(True)
        lbl_guarantee.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; line-height: 1.4;")
        p_layout.addWidget(lbl_guarantee)

        layout.addWidget(privacy_card)

        # Value Pillars (3 horizontal cards)
        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)

        pillars = [
            ("🔒 100% Private & Local", "Candidate data, resumes, and credentials stay securely encrypted on your local machine."),
            ("🧠 Verified AI Screening", "Uses local Ollama or high-speed cloud LLMs (Groq, NVIDIA, OpenAI) for precise ATS answers."),
            ("🎯 Autonomous Pipeline", "Orchestrates LinkedIn, Naukri, Indeed, and Universal ATS portals (Greenhouse, Lever, Workday)."),
        ]

        for title, desc in pillars:
            card = QFrame()
            card.setObjectName("pillar_card")
            card.setStyleSheet(f"""
                #pillar_card {{
                    background-color: {COLORS['surface']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 8px;
                }}
                #pillar_card QLabel {{
                    border: none;
                    background: transparent;
                }}
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(14, 12, 14, 12)
            c_layout.setSpacing(4)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
            d_lbl = QLabel(desc)
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")

            c_layout.addWidget(t_lbl)
            c_layout.addWidget(d_lbl)
            c_layout.addStretch()
            cards_row.addWidget(card)

        layout.addLayout(cards_row)

        # Setup Mode Selector
        mode_frame = QFrame()
        mode_frame.setObjectName("mode_frame")
        mode_frame.setStyleSheet(f"""
            #mode_frame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
            }}
            #mode_frame QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        m_layout = QVBoxLayout(mode_frame)
        m_layout.setContentsMargins(16, 12, 16, 12)
        m_layout.setSpacing(8)

        lbl_mode_head = QLabel("Select Setup Experience:")
        lbl_mode_head.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        m_layout.addWidget(lbl_mode_head)

        self.btn_group = QButtonGroup(self)

        self.rad_quick = QRadioButton("Quick Setup (Recommended · ~2–3 minutes)")
        self.rad_quick.setChecked(True)
        self.rad_quick.setStyleSheet(f"""
            QRadioButton {{
                font-size: 13px;
                font-weight: 600;
                color: {COLORS['text']};
                spacing: 8px;
            }}
        """)

        lbl_quick_hint = QLabel("    Configures AI, imports resume, and reviews candidate profile. Reaches 'Core Ready' fast.")
        lbl_quick_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")

        self.rad_adv = QRadioButton("Complete Setup (~5–8 minutes)")
        self.rad_adv.setStyleSheet(f"""
            QRadioButton {{
                font-size: 13px;
                font-weight: 600;
                color: {COLORS['text']};
                spacing: 8px;
            }}
        """)

        lbl_adv_hint = QLabel("    Walks through all 10 stages: AI, resume, profile, 398+ Q&A rules, job portals, and safety limits.")
        lbl_adv_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")

        self.btn_group.addButton(self.rad_quick, 1)
        self.btn_group.addButton(self.rad_adv, 2)

        m_layout.addWidget(self.rad_quick)
        m_layout.addWidget(lbl_quick_hint)
        m_layout.addWidget(self.rad_adv)
        m_layout.addWidget(lbl_adv_hint)

        layout.addWidget(mode_frame)
        layout.addStretch(1)

    def get_selected_mode(self) -> str:
        return "QUICK" if self.rad_quick.isChecked() else "ADVANCED"
