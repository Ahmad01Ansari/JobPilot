from pathlib import Path
from typing import Any, Dict, Optional
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS
from app.ui.views.settings.components.setting_row import SettingRow
from app.version import RELEASE_CHANNEL, VERSION


class GeneralSection(QWidget):
    """General preferences governing interaction delays, search rotation, and continuous loops."""

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

        # Section Header
        lbl_head = QLabel("General Execution Preferences")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(f"JobPilot v{VERSION} ({RELEASE_CHANNEL}) — Configure operational interaction delays, pagination search filters, and diagnostics.")
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Content Card Frame
        card = QFrame()
        card.setObjectName("GeneralCard")
        card.setStyleSheet(f"""
            QFrame#GeneralCard {{
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

        # 1. Click Gap (1–10s, default 1)
        self.spn_click_gap = QSpinBox()
        self.spn_click_gap.setRange(1, 10)
        self.spn_click_gap.setValue(1)
        self.spn_click_gap.setSuffix(" sec")
        self.spn_click_gap.setFixedWidth(90)
        self.spn_click_gap.setStyleSheet(self._spin_style())
        self.spn_click_gap.valueChanged.connect(lambda _: self.changed.emit())
        row_gap = SettingRow(
            title="Interaction delay",
            description="Controls the delay between automated UI clicks and navigation transitions.",
            control_widget=self.spn_click_gap,
        )
        card_layout.addWidget(row_gap)

        # 2. Smooth Scrolling (default False)
        self.chk_smooth_scroll = QCheckBox()
        self.chk_smooth_scroll.setChecked(False)
        self.chk_smooth_scroll.setStyleSheet(self._chk_style())
        self.chk_smooth_scroll.toggled.connect(lambda _: self.changed.emit())
        row_scroll = SettingRow(
            title="Smooth page scrolling",
            description="Simulates humanized scroll gestures when scanning job search results.",
            control_widget=self.chk_smooth_scroll,
        )
        card_layout.addWidget(row_scroll)

        # 3. Alternate Sortby (default True)
        self.chk_alternate_sortby = QCheckBox()
        self.chk_alternate_sortby.setChecked(True)
        self.chk_alternate_sortby.setStyleSheet(self._chk_style())
        self.chk_alternate_sortby.toggled.connect(lambda _: self.changed.emit())
        row_sort = SettingRow(
            title="Alternate Recent and Relevant sort",
            description="Alternates sort filter between Recent and Relevant across successive searches.",
            control_widget=self.chk_alternate_sortby,
        )
        card_layout.addWidget(row_sort)

        # 4. Cycle Date Posted (default True)
        self.chk_cycle_date_posted = QCheckBox()
        self.chk_cycle_date_posted.setChecked(True)
        self.chk_cycle_date_posted.setStyleSheet(self._chk_style())
        self.chk_cycle_date_posted.toggled.connect(lambda _: self.changed.emit())
        row_date = SettingRow(
            title="Cycle posted-date filters",
            description="Rotates through 24-hour, past-week, and past-month filters for maximum role discovery.",
            control_widget=self.chk_cycle_date_posted,
        )
        card_layout.addWidget(row_date)

        # 5. Run Non-Stop (default False, Caution)
        self.chk_run_non_stop = QCheckBox()
        self.chk_run_non_stop.setChecked(False)
        self.chk_run_non_stop.setStyleSheet(self._chk_style())
        self.chk_run_non_stop.toggled.connect(lambda _: self.changed.emit())
        row_loop = SettingRow(
            title="Run continuously in non-stop loop",
            description="Automation does not terminate upon reaching single-run quota; it loops until stopped manually.",
            control_widget=self.chk_run_non_stop,
            is_caution=True,
            is_last=True,
        )
        card_layout.addWidget(row_loop)

        layout.addWidget(card)

        # Diagnostics / Logs Directory Box
        logs_card = QFrame()
        logs_card.setObjectName("LogsCard")
        logs_card.setStyleSheet(f"""
            QFrame#LogsCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 12px 14px;
            }}
            QLabel {{
                background: transparent;
                border: none;
                padding: 0;
            }}
        """)
        l_layout = QHBoxLayout(logs_card)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(14)

        l_text_layout = QVBoxLayout()
        lbl_l_title = QLabel("Execution & Diagnostic Logs")
        lbl_l_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        l_text_layout.addWidget(lbl_l_title)

        lbl_l_desc = QLabel("Operational logs are stored with automatic secret scrubbing and trace logs.")
        lbl_l_desc.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        l_text_layout.addWidget(lbl_l_desc)
        l_layout.addLayout(l_text_layout, 1)

        btn_open_logs = QPushButton("📁 Open Logs Folder")
        btn_open_logs.setCursor(Qt.PointingHandCursor)
        btn_open_logs.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """)
        from app.services.os.app_paths import AppPaths
        logs_dir = AppPaths.get_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        btn_open_logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(logs_dir))))
        l_layout.addWidget(btn_open_logs)

        btn_export_diag = QPushButton("📋 Export Diagnostics")
        btn_export_diag.setCursor(Qt.PointingHandCursor)
        btn_export_diag.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('primary', '#FF5F15')};
                color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        btn_export_diag.clicked.connect(self._on_export_diagnostics_clicked)
        l_layout.addWidget(btn_export_diag)

        layout.addWidget(logs_card)

        # Setup & Readiness Card
        setup_card = QFrame()
        setup_card.setObjectName("SetupCard")
        setup_card.setStyleSheet(f"""
            QFrame#SetupCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        s_layout = QVBoxLayout(setup_card)
        s_layout.setSpacing(10)

        lbl_s_head = QLabel("Workspace Setup & Product Tour")
        lbl_s_head.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        s_layout.addWidget(lbl_s_head)

        lbl_s_desc = QLabel("Re-run the first-run configuration wizard or launch the 9-stop interactive product tour.")
        lbl_s_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        s_layout.addWidget(lbl_s_desc)

        btn_row = QHBoxLayout()
        btn_run_wizard = QPushButton("⚡ Run Setup Wizard")
        btn_run_wizard.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border-radius: 6px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('primary_hover', '#E04F0B')};
            }}
        """)
        btn_run_wizard.clicked.connect(self._on_run_wizard_clicked)
        btn_row.addWidget(btn_run_wizard)

        btn_run_tour = QPushButton("🧭 Restart Product Tour")
        btn_run_tour.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border_light', '#333A46')};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('primary', '#FF5F15')};
                color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        btn_run_tour.clicked.connect(self._on_restart_tour_clicked)
        btn_row.addWidget(btn_run_tour)

        btn_check_readiness = QPushButton("✓ Check Readiness")
        btn_check_readiness.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border_light', '#333A46')};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('primary', '#FF5F15')};
                color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        btn_check_readiness.clicked.connect(self._on_check_readiness_clicked)
        btn_row.addWidget(btn_check_readiness)

        btn_row.addStretch()
        s_layout.addLayout(btn_row)
        layout.addWidget(setup_card)

        layout.addStretch()

        scroll.setWidget(container)
        outer_layout.addWidget(scroll)

    def get_values(self) -> Dict[str, Any]:
        return {
            "click_gap": self.spn_click_gap.value(),
            "smooth_scroll": self.chk_smooth_scroll.isChecked(),
            "run_non_stop": self.chk_run_non_stop.isChecked(),
            "alternate_sortby": self.chk_alternate_sortby.isChecked(),
            "cycle_date_posted": self.chk_cycle_date_posted.isChecked(),
        }

    def load_values(self, values: Dict[str, Any]) -> None:
        self.blockSignals(True)
        if "click_gap" in values:
            self.spn_click_gap.setValue(int(values["click_gap"]))
        if "smooth_scroll" in values:
            self.chk_smooth_scroll.setChecked(bool(values["smooth_scroll"]))
        if "run_non_stop" in values:
            self.chk_run_non_stop.setChecked(bool(values["run_non_stop"]))
        if "alternate_sortby" in values:
            self.chk_alternate_sortby.setChecked(bool(values["alternate_sortby"]))
        if "cycle_date_posted" in values:
            self.chk_cycle_date_posted.setChecked(bool(values["cycle_date_posted"]))
        self.blockSignals(False)

    def reset_to_defaults(self) -> None:
        self.load_values({
            "click_gap": 1,
            "smooth_scroll": False,
            "run_non_stop": False,
            "alternate_sortby": True,
            "cycle_date_posted": True,
        })
        self.changed.emit()

    def _spin_style(self) -> str:
        return f"""
            QSpinBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 4px 8px;
                font-weight: 600;
                font-size: 13px;
            }}
            QSpinBox:focus {{
                border: 1px solid {COLORS.get('accent', '#FF5F15')};
            }}
        """

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

    def _on_run_wizard_clicked(self) -> None:
        win = self.window()
        if win and hasattr(win, "launch_onboarding"):
            win.launch_onboarding()

    def _on_restart_tour_clicked(self) -> None:
        win = self.window()
        if win and hasattr(win, "launch_product_tour"):
            win.launch_product_tour()

    def _on_check_readiness_clicked(self) -> None:
        from app.services.setup.setup_readiness import SetupReadinessService
        from PySide6.QtWidgets import QMessageBox
        report = SetupReadinessService().evaluate()
        core_msg = "✓ Ready" if report.is_core_ready else "⚠ Incomplete"
        auto_msg = "✓ Ready" if report.is_automation_ready else "○ Optional"
        details = (
            f"Readiness Status:\n\n"
            f"• Core Workspace: {core_msg} ({report.core_summary})\n"
            f"• Autonomous Automation: {auto_msg} ({report.recommended_summary})\n\n"
        )
        if report.blockers:
            details += "Blockers:\n" + "\n".join(f"  - {b}" for b in report.blockers) + "\n\n"
        if report.warnings:
            details += "Recommendations:\n" + "\n".join(f"  - {w}" for w in report.warnings)

        QMessageBox.information(self, "Workspace Readiness Diagnostic", details)

    def _on_export_diagnostics_clicked(self) -> None:
        from datetime import datetime
        from app.services.diagnostic_service import DiagnosticService

        default_name = f"jobpilot_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sanitized Diagnostic Report",
            default_name,
            "Markdown Files (*.md);;All Files (*)",
        )
        if not file_path:
            return

        try:
            saved_path = DiagnosticService().export_to_file(file_path)
            QMessageBox.information(
                self,
                "Diagnostic Report Exported",
                f"Sanitized diagnostic report successfully saved to:\n\n{saved_path}\n\n"
                "This report is free of plain passwords, tokens, cookies, or secrets.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to generate diagnostic report:\n\n{str(e)}",
            )

