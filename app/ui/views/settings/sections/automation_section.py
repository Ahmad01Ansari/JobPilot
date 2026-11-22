"""Automation safeguards and human review gates section."""

from typing import Any, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QScrollArea,
    QSpinBox,
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

        self.lbl_sb_title = QLabel("Automation Safety: ● Protected")
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
        )
        card_layout.addWidget(row_tabs)

        # 6. Auto-close stale applications (default True)
        self.chk_auto_close = QCheckBox()
        self.chk_auto_close.setChecked(True)
        self.chk_auto_close.setStyleSheet(self._chk_style())
        self.chk_auto_close.toggled.connect(self._on_control_changed)
        row_auto_close = SettingRow(
            title="Auto-close stale applications after inactivity",
            description="Automatically moves ghost applications in Submitted/Under Review to Closed when no recruiter response occurs within the threshold.",
            control_widget=self.chk_auto_close,
        )
        card_layout.addWidget(row_auto_close)

        # 7. Stale threshold (default 60 days)
        self.cmb_stale_days = QComboBox()
        self.cmb_stale_days.addItem("30 Days (1 Month)", 30)
        self.cmb_stale_days.addItem("45 Days (1.5 Months)", 45)
        self.cmb_stale_days.addItem("60 Days (Standard — 2 Months)", 60)
        self.cmb_stale_days.addItem("90 Days (Quarterly — 3 Months)", 90)
        self.cmb_stale_days.setCurrentIndex(2)  # default 60 days
        self.cmb_stale_days.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                min-width: 200px;
            }}
            QComboBox:hover {{
                border-color: {COLORS.get('primary', '#38BDF8')};
            }}
        """)
        self.cmb_stale_days.currentIndexChanged.connect(self._on_control_changed)
        row_days = SettingRow(
            title="Inactivity threshold before closing",
            description="Duration of zero recruiter or portal activity required before an application is considered cold and auto-closed.",
            control_widget=self.cmb_stale_days,
            is_last=False,
        )
        card_layout.addWidget(row_days)

        # 8. Round-Robin Batch Slice per Platform (default 10)
        self.spn_batch_slice = QSpinBox()
        self.spn_batch_slice.setRange(1, 50)
        self.spn_batch_slice.setValue(10)
        self.spn_batch_slice.setSuffix(" apps")
        self.spn_batch_slice.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                min-width: 140px;
            }}
            QSpinBox:hover {{
                border-color: {COLORS.get('primary', '#38BDF8')};
            }}
        """)
        self.spn_batch_slice.valueChanged.connect(self._on_control_changed)
        row_slice = SettingRow(
            title="Round-robin batch slice per platform",
            description="Applications submitted per platform in each cycle before yielding to the next platform in the queue.",
            control_widget=self.spn_batch_slice,
            is_last=False,
        )
        card_layout.addWidget(row_slice)

        # 9. Batch Daily Goal per Platform (default 25)
        self.spn_daily_goal = QSpinBox()
        self.spn_daily_goal.setRange(1, 100)
        self.spn_daily_goal.setValue(25)
        self.spn_daily_goal.setSuffix(" apps")
        self.spn_daily_goal.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                min-width: 140px;
            }}
            QSpinBox:hover {{
                border-color: {COLORS.get('primary', '#38BDF8')};
            }}
        """)
        self.spn_daily_goal.valueChanged.connect(self._on_control_changed)
        row_goal = SettingRow(
            title="Batch daily goal per platform",
            description="Daily target applications for each platform in multi-platform mode. The runner repeats round-robin cycles until met.",
            control_widget=self.spn_daily_goal,
            is_last=True,
        )
        card_layout.addWidget(row_goal)

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
        self.lbl_sb_title.setText(f"Automation Safety: {status_text}")
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
            "auto_close_stale_applications": self.chk_auto_close.isChecked(),
            "auto_close_stale_days": self.cmb_stale_days.currentData() or 60,
            "batch_size_per_platform": self.spn_batch_slice.value(),
            "batch_daily_goal_per_platform": self.spn_daily_goal.value(),
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
        if "auto_close_stale_applications" in values:
            self.chk_auto_close.setChecked(bool(values["auto_close_stale_applications"]))
        if "auto_close_stale_days" in values:
            try:
                days = int(values["auto_close_stale_days"])
                idx = self.cmb_stale_days.findData(days)
                if idx >= 0:
                    self.cmb_stale_days.setCurrentIndex(idx)
            except Exception:
                pass
        if "batch_size_per_platform" in values:
            try:
                self.spn_batch_slice.setValue(int(values["batch_size_per_platform"]))
            except Exception:
                pass
        if "batch_daily_goal_per_platform" in values:
            try:
                self.spn_daily_goal.setValue(int(values["batch_daily_goal_per_platform"]))
            except Exception:
                pass
        self.blockSignals(False)
        self.update_safety_banner()

    def reset_to_defaults(self) -> None:
        self.load_values({
            "enable_universal_agent": True,
            "pause_before_submit": False,
            "pause_at_failed_question": True,
            "follow_companies": False,
            "close_tabs": False,
            "auto_close_stale_applications": True,
            "auto_close_stale_days": 60,
            "batch_size_per_platform": 10,
            "batch_daily_goal_per_platform": 25,
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
