"""Modal dialog for inspecting complete job description, requirements, and direct URLs."""

from typing import Optional
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Job
from app.ui.theme import COLORS


def format_platform_name(platform: Optional[str]) -> str:
    p = (platform or "").lower().strip()
    if p == "linkedin":
        return "LinkedIn"
    if p == "naukri":
        return "Naukri"
    if p == "indeed":
        return "Indeed"
    if p == "foundit":
        return "Foundit"
    if p == "glassdoor":
        return "Glassdoor"
    return platform.title() if platform else "Listing"


class JobDetailsDialog(QDialog):
    """ATS-style modal dialog for deep inspection of a job posting."""

    def __init__(self, job: Job, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Job Details: {job.title} — {job.company_raw}")
        self.resize(760, 620)
        self._setup_ui()

    def _setup_ui(self) -> None:
        plat_name = format_platform_name(self.job.platform)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # 1. Header Section
        header_box = QVBoxLayout()
        header_box.setSpacing(6)

        title_lbl = QLabel(self.job.title)
        title_lbl.setStyleSheet(f"font-size: 20px; font-weight: 700; color: {COLORS['text']};")
        title_lbl.setWordWrap(True)
        title_lbl.setTextInteractionFlags(title_lbl.textInteractionFlags() | title_lbl.textInteractionFlags().TextSelectableByMouse)
        header_box.addWidget(title_lbl)

        meta_sub = QLabel(f"{self.job.company_raw} • {plat_name} • {self.job.location or 'Location unstated'}")
        meta_sub.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS['accent']};")
        meta_sub.setTextInteractionFlags(meta_sub.textInteractionFlags() | meta_sub.textInteractionFlags().TextSelectableByMouse)
        header_box.addWidget(meta_sub)

        method_text = getattr(self.job, "application_method", "EASY_APPLY") or "EASY_APPLY"
        chips_text = (
            f"Method: {method_text.replace('_', ' ').title()}  •  "
            f"Experience: {self.job.experience_text or 'N/A'}  •  "
            f"Salary: {self.job.salary_text or 'N/A'}"
        )
        if self.job.first_seen_at:
            chips_text += f"  •  Discovered: {self.job.first_seen_at.strftime('%b %d, %Y')}"
        chips_lbl = QLabel(chips_text)
        chips_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        header_box.addWidget(chips_lbl)

        layout.addLayout(header_box)

        # 2. Description Section
        desc_heading = QLabel("COMPLETE JOB DESCRIPTION")
        desc_heading.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        layout.addWidget(desc_heading)

        desc_edit = QTextEdit()
        desc_edit.setReadOnly(True)
        desc_edit.setPlainText(self.job.description or "No detailed description provided.")
        desc_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 14px;
                font-size: 13px;
                line-height: 1.6;
            }}
        """)
        layout.addWidget(desc_edit, 1)

        # 3. Action Buttons Section
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        app_url = getattr(self.job, "application_url", None)
        if app_url:
            btn_app_url = QPushButton("🌐 Open Application Portal ↗")
            btn_app_url.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['primary']};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary_hover']};
                }}
            """)
            btn_app_url.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(app_url)))
            btn_box.addWidget(btn_app_url)

        if self.job.source_url:
            btn_src_url = QPushButton(f"Open on {plat_name} ↗")
            btn_src_url.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 12px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                }}
            """)
            btn_src_url.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.job.source_url)))
            btn_box.addWidget(btn_src_url)

        btn_box.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        btn_box.addWidget(btn_close)

        layout.addLayout(btn_box)


# Alias for backwards compatibility
JobDescriptionDialog = JobDetailsDialog
