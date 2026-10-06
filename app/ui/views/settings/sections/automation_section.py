"""Automation safeguards and human review gates section."""

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS
from app.ui.views.settings.components.setting_row import SettingRow


class AutomationSection(QWidget):
    """Automation safety section controlling review gates, failure pauses, and tab cleanups."""

    changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 24, 16)
        layout.setSpacing(16)

        # Header
        lbl_head = QLabel("Automation Safety & Human Review")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel("Configure human-in-the-loop review checkpoints and submission safeguards before applications are submitted.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Safety Profile Summary Banner
        self.safety_banner = QFrame()
        self.safety_banner.setObjectName("SafetyBanner")
        self.safety_banner.setStyleSheet(f"""
            QFrame#SafetyBanner {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-left: 3px solid {COLORS.get('success', '#2EA043')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        sb_layout = QVBoxLayout(self.safety_banner)
        sb_layout.setContentsMargins(8, 8, 8, 8)
        sb_layout.setSpacing(6)

        self.lbl_sb_title = QLabel("🛡️ Automation Safety: ● Protected")
        self.lbl_sb_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('success', '#2EA043')};")
        sb_layout.addWidget(self.lbl_sb_title)

        self.lbl_sb_summary = QLabel(
            "• Universal ATS automation agent active\n"
            "• Manual review enabled for uncertain screening questions\n"
            "• Company feed spam prevented\n"
            "• Immediate submission review configurable below"
        )
        self.lbl_sb_summary.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        sb_layout.addWidget(self.lbl_sb_summary)
        layout.addWidget(self.safety_banner)

        # Content Card Frame
        card = QFrame()
        card.setObjectName("AutomationCard")
        card.setStyleSheet(f"""
            QFrame#AutomationCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 8px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(0)

        # 1. Universal Agent (default True)
        self.chk_universal_agent = QCheckBox()
        self.chk_universal_agent.setChecked(True)
        self.chk_universal_agent.setStyleSheet(self._chk_style())
        self.chk_universal_agent.toggled.connect(self._on_control_changed)
        row_universal = SettingRow(
            title="Enable Universal AI Agent (External ATS)",
            description="Enables automated Stagehand navigation and form filling for external ATS portals (Workday, Greenhouse, Lever, etc.).",
            control_widget=self.chk_universal_agent,
        )
        card_layout.addWidget(row_universal)

        # 2. Pause before submit (default False)
        self.chk_pause_submit = QCheckBox()
        self.chk_pause_submit.setChecked(False)
        self.chk_pause_submit.setStyleSheet(self._chk_style())
        self.chk_pause_submit.toggled.connect(self._on_control_changed)
        row_submit = SettingRow(
            title="Pause before final submission",
            description="Halts the bot before clicking 'Submit Application' to allow manual review.",
            control_widget=self.chk_pause_submit,
        )
        card_layout.addWidget(row_submit)

        # 3. Pause at failed question (default True)
        self.chk_pause_failed = QCheckBox()
        self.chk_pause_failed.setChecked(True)
        self.chk_pause_failed.setStyleSheet(self._chk_style())
        self.chk_pause_failed.toggled.connect(self._on_control_changed)
        row_failed = SettingRow(
            title="Pause when screening answer is unresolved",
            description="Pauses execution and alerts you when a form question cannot be answered by AI or rules.",
            control_widget=self.chk_pause_failed,
        )
        card_layout.addWidget(row_failed)

        # 4. Follow companies (default False)
        self.chk_follow_companies = QCheckBox()
        self.chk_follow_companies.setChecked(False)
        self.chk_follow_companies.setStyleSheet(self._chk_style())
        self.chk_follow_companies.toggled.connect(self._on_control_changed)
        row_follow = SettingRow(
            title="Follow companies automatically on apply",
            description="Automatically checks the 'Follow company' box during LinkedIn Easy Apply.",
            control_widget=self.chk_follow_companies,
        )
        card_layout.addWidget(row_follow)

        # 5. Close tabs (default False)
        self.chk_close_tabs = QCheckBox()
        self.chk_close_tabs.setChecked(False)
        self.chk_close_tabs.setStyleSheet(self._chk_style())
        self.chk_close_tabs.toggled.connect(self._on_control_changed)
        row_tabs = SettingRow(
            title="Close external job tabs after capture",
            description="Automatically closes external redirect tabs in Chrome after capturing job details.",
            control_widget=self.chk_close_tabs,
            is_last=True,
        )
        card_layout.addWidget(row_tabs)

        layout.addWidget(card)
        layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def _on_control_changed(self) -> None:
        self.update_safety_banner()
        self.changed.emit()

    def update_safety_banner(self) -> None:
        is_safe = self.chk_pause_failed.isChecked() or self.chk_pause_submit.isChecked()
        color = COLORS.get('success', '#2EA043') if is_safe else COLORS.get('warning', '#D29922')
        status_text = "● Protected" if is_safe else "○ Unattended"
        self.lbl_sb_title.setText(f"🛡️ Automation Safety: {status_text}")
        self.lbl_sb_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {color};")
        self.safety_banner.setStyleSheet(f"""
            QFrame#SafetyBanner {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-left: 3px solid {color};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)

    def is_safety_active(self) -> bool:
        return self.chk_pause_failed.isChecked() or self.chk_pause_submit.isChecked()

    def get_values(self) -> Dict[str, Any]:
        return {
            "enable_universal_agent": self.chk_universal_agent.isChecked(),
            "pause_before_submit": self.chk_pause_submit.isChecked(),
            "pause_at_failed_question": self.chk_pause_failed.isChecked(),
            "follow_companies": self.chk_follow_companies.isChecked(),
            "close_tabs": self.chk_close_tabs.isChecked(),
        }

    def load_values(self, values: Dict[str, Any]) -> None:
        self.blockSignals(True)
        if "enable_universal_agent" in values:
            self.chk_universal_agent.setChecked(bool(values["enable_universal_agent"]))
        if "pause_before_submit" in values:
            self.chk_pause_submit.setChecked(bool(values["pause_before_submit"]))
        if "pause_at_failed_question" in values:
            self.chk_pause_failed.setChecked(bool(values["pause_at_failed_question"]))
        if "follow_companies" in values:
            self.chk_follow_companies.setChecked(bool(values["follow_companies"]))
        if "close_tabs" in values:
            self.chk_close_tabs.setChecked(bool(values["close_tabs"]))
        self.blockSignals(False)
        self.update_safety_banner()

    def reset_to_defaults(self) -> None:
        self.load_values({
            "enable_universal_agent": True,
            "pause_before_submit": False,
            "pause_at_failed_question": True,
            "follow_companies": False,
            "close_tabs": False,
        })
        self.changed.emit()

    def _chk_style(self) -> str:
        return f"""
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid {COLORS.get('border', '#262C36')};
                background: {COLORS.get('surface_alt', '#1C2128')};
            }}
            QCheckBox::indicator:hover {{
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
            QCheckBox::indicator:checked {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
        """
