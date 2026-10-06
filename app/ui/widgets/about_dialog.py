"""About JobPilot modal dialog displaying official branding, version, and platform specs."""

import platform
import sys
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS, ThemeManager
from app.version import VERSION


class AboutDialog(QDialog):
    """Refined About modal featuring the JobPilot brand icon, platform version, and architecture specs."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("About JobPilot")
        self.setFixedSize(640, 490)
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('background', '#0F1117')};
                color: {COLORS.get('text', '#F0F6FC')};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
            QFrame#HeaderCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 10px;
            }}
            QFrame#SpecsCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 24)
        layout.setSpacing(18)

        # 1. Header Card: Brand Icon + Title + Version Badge
        header_card = QFrame()
        header_card.setObjectName("HeaderCard")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(16, 16, 16, 16)
        h_layout.setSpacing(18)

        # Brand Icon Pixmap (96x96)
        lbl_icon = QLabel()
        lbl_icon.setFixedSize(88, 88)
        lbl_icon.setAlignment(Qt.AlignCenter)
        pix = ThemeManager.get_brand_pixmap(88, variant="app")
        if not pix.isNull():
            lbl_icon.setPixmap(pix)
        h_layout.addWidget(lbl_icon)

        # Title column
        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(4)

        t_row = QHBoxLayout()
        t_row.setSpacing(10)
        lbl_title = QLabel("JobPilot")
        lbl_title.setStyleSheet(f"""
            font-size: 24px;
            font-weight: 800;
            color: {COLORS.get('text', '#F0F6FC')};
            letter-spacing: 0.5px;
        """)
        t_row.addWidget(lbl_title)

        lbl_badge = QLabel(f"v{VERSION}")
        lbl_badge.setStyleSheet(f"""
            background-color: {COLORS.get('primary', '#FF5F15')};
            color: #FFFFFF;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        """)
        t_row.addWidget(lbl_badge)
        t_row.addStretch()
        title_col.addLayout(t_row)

        lbl_tagline = QLabel("Autonomous Cross-Platform Job Application & Intelligence Platform")
        lbl_tagline.setWordWrap(True)
        lbl_tagline.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS.get('text_muted', '#8B949E')};
            font-weight: 500;
        """)
        title_col.addWidget(lbl_tagline)

        h_layout.addLayout(title_col, 1)
        layout.addWidget(header_card)

        # 2. Architecture & Capabilities Card
        specs_card = QFrame()
        specs_card.setObjectName("SpecsCard")
        s_layout = QVBoxLayout(specs_card)
        s_layout.setContentsMargins(16, 14, 16, 14)
        s_layout.setSpacing(10)

        capabilities = [
            ("⚡ Multi-Platform Automation", "LinkedIn, Naukri, Indeed, Glassdoor, Foundit"),
            ("🛡️ Identity & Deduplication", "ATS Requisition IDs, Safe URL Normalization, CAS Locking"),
            ("🧠 AI Multi-Tier Q&A", "Deterministic Rule Cache, Verified Profile Facts, Local Fallbacks"),
            ("🔒 Security & Isolation", "Isolated Profiles, Zero CAPTCHA Bypass, Sanitized Telemetry"),
        ]

        for title, desc in capabilities:
            row = QHBoxLayout()
            row.setSpacing(12)
            lbl_k = QLabel(title)
            lbl_k.setFixedWidth(200)
            lbl_k.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
            lbl_v = QLabel(desc)
            lbl_v.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
            row.addWidget(lbl_k)
            row.addWidget(lbl_v, 1)
            s_layout.addLayout(row)

        layout.addWidget(specs_card)

        # 3. Environment Telemetry
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"

        lbl_telemetry = QLabel(f"Python {py_ver} • PySide6 GUI • SQLite WAL • {os_info}")
        lbl_telemetry.setAlignment(Qt.AlignCenter)
        lbl_telemetry.setStyleSheet(f"font-size: 10px; color: {COLORS.get('text_dark', '#6E7681')};")
        layout.addWidget(lbl_telemetry)

        # 4. Bottom Button Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_export = QPushButton("📋 Export Diagnostic Report")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border_light', '#333A46')};
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('primary', '#FF5F15')};
                color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        btn_export.clicked.connect(self._on_export_diagnostics)
        btn_row.addWidget(btn_export)

        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('primary_hover', '#E04F0B')};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _on_export_diagnostics(self) -> None:
        """Prompts user for file location and exports sanitized markdown diagnostic report."""
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
