"""
Step 9: Automation Safety Limits & Guardrails.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
"""

from typing import Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QSlider, QCheckBox, QFrame
)
from app.ui.theme import COLORS


class StepSafetyWidget(QWidget):
    """Step 9: Automation safety limits and pacing guardrails widget."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        lbl_badge = QLabel("STEP 9: AUTOMATION PACING & LIMITS")
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

        lbl_title = QLabel("Automation Safety & Rate Limits")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Protect your job portal accounts from anti-bot rate limits and algorithmic flagging. "
            "JobPilot enforces strict human-like pacing, randomized cooldowns, and automatic error halts."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # 1. Daily Limit Card
        card_limits = QFrame()
        card_limits.setStyleSheet(self._card_qss())
        cl_layout = QVBoxLayout(card_limits)
        cl_layout.setSpacing(10)

        lbl_limit_title = QLabel("Daily Application Cap")
        lbl_limit_title.setStyleSheet(self._section_title_qss())
        cl_layout.addWidget(lbl_limit_title)

        lim_row = QHBoxLayout()
        self.slider_limit = QSlider(Qt.Horizontal)
        self.slider_limit.setRange(5, 50)
        self.slider_limit.setValue(25)
        self.slider_limit.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {COLORS['surface_alt']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {COLORS['primary']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: #FFFFFF;
                width: 16px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
        """)

        self.spin_limit = QSpinBox()
        self.spin_limit.setRange(5, 50)
        self.spin_limit.setValue(25)
        self.spin_limit.setStyleSheet(self._spin_qss())

        self.slider_limit.valueChanged.connect(self.spin_limit.setValue)
        self.spin_limit.valueChanged.connect(self.slider_limit.setValue)

        lim_row.addWidget(self.slider_limit)
        lim_row.addWidget(self.spin_limit)
        cl_layout.addLayout(lim_row)

        lbl_hint = QLabel("Recommended: 20–30 applications per day to keep account standing healthy.")
        lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        cl_layout.addWidget(lbl_hint)

        layout.addWidget(card_limits)

        # 2. Safety Options Card
        card_guard = QFrame()
        card_guard.setStyleSheet(self._card_qss())
        cg_layout = QVBoxLayout(card_guard)
        cg_layout.setSpacing(10)

        lbl_guard_title = QLabel("Safety Guardrails")
        lbl_guard_title.setStyleSheet(self._section_title_qss())
        cg_layout.addWidget(lbl_guard_title)

        self.chk_stealth = QCheckBox("Stealth Browser Mode (Anti-bot detection evasion active)")
        self.chk_stealth.setChecked(True)
        self.chk_stealth.setStyleSheet(self._check_qss())
        cg_layout.addWidget(self.chk_stealth)

        self.chk_stop_on_error = QCheckBox("Emergency Stop on 3 Consecutive Application Failures")
        self.chk_stop_on_error.setChecked(True)
        self.chk_stop_on_error.setStyleSheet(self._check_qss())
        cg_layout.addWidget(self.chk_stop_on_error)

        self.chk_manual_review = QCheckBox("Manual Review Mode (Pause before clicking final 'Submit Application')")
        self.chk_manual_review.setChecked(False)
        self.chk_manual_review.setStyleSheet(self._check_qss())
        cg_layout.addWidget(self.chk_manual_review)

        layout.addWidget(card_guard)
        layout.addStretch()

    def get_safety_payload(self) -> Dict[str, Any]:
        return {
            "daily_limit": self.spin_limit.value(),
            "stealth_mode": self.chk_stealth.isChecked(),
            "stop_on_consecutive_errors": self.chk_stop_on_error.isChecked(),
            "manual_review_mode": self.chk_manual_review.isChecked(),
            "min_delay_seconds": 45,
            "max_delay_seconds": 90,
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
        return f"font-size: 12px; font-weight: 700; color: {COLORS['text']};"

    def _spin_qss(self) -> str:
        return f"""
            QSpinBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 4px 8px;
                font-weight: 700;
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
