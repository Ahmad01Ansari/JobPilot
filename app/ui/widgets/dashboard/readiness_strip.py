"""Readiness and platform health status strip widget."""

from typing import Optional

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from app.services.dto.dashboard_dto import ReadinessSummaryDTO
from app.ui.theme import COLORS
from app.ui.sidebar_icons import render_vector_icon


class ReadinessStrip(QFrame):
    """Compact horizontal component-level readiness and platform health indicator."""

    navigate_requested = Signal(str)  # Target view id ('profile', 'resumes', 'qna', 'platforms')

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            ReadinessStrip {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(8)

        # 1. Profile Pill
        self.btn_profile = self._create_pill_btn("Profile: —", "profile")
        layout.addWidget(self.btn_profile)

        # 2. Resume Pill
        self.btn_resume = self._create_pill_btn("Resume: —", "resumes")
        layout.addWidget(self.btn_resume)

        # 3. QnA Pill
        self.btn_qna = self._create_pill_btn("Q&A: —", "qna")
        layout.addWidget(self.btn_qna)

        # 4. Platforms Pill
        self.btn_platforms = self._create_pill_btn("Platforms: —", "platforms")
        layout.addWidget(self.btn_platforms)

        # Dummy plat_container for backward compatibility with existing tests
        self.plat_container = QHBoxLayout()

        # Compact Manage link
        btn_manage = QPushButton("Manage →")
        btn_manage.setCursor(Qt.PointingHandCursor)
        btn_manage.setStyleSheet(f"""
            QPushButton {{
                color: {COLORS['primary']};
                background: transparent;
                border: none;
                font-size: 11px;
                font-weight: 700;
                padding: 0 4px;
            }}
            QPushButton:hover {{
                text-decoration: underline;
                color: {COLORS['primary_hover']};
            }}
        """)
        btn_manage.clicked.connect(lambda: self.navigate_requested.emit("platforms"))
        layout.addWidget(btn_manage)

    def _create_pill_btn(self, text: str, target: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_subtle']};
                font-size: 11px;
                font-weight: 600;
                padding: 3px 8px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn.clicked.connect(lambda: self.navigate_requested.emit(target))
        return btn

    def set_readiness(self, readiness: ReadinessSummaryDTO) -> None:
        """Updates readiness pill texts, vector status icons, and consolidated platform health."""
        ok_color = COLORS["success"]
        warn_color = COLORS["warning"]

        self.btn_profile.setIconSize(QSize(12, 12))
        self.btn_profile.setIcon(render_vector_icon("check" if readiness.profile_complete else "alert", ok_color if readiness.profile_complete else warn_color, 12))
        self.btn_profile.setText("Profile")

        self.btn_resume.setIconSize(QSize(12, 12))
        self.btn_resume.setIcon(render_vector_icon("check" if readiness.resume_configured else "alert", ok_color if readiness.resume_configured else warn_color, 12))
        self.btn_resume.setText("Resume")

        qna_pct = int(readiness.qna_answered_ratio * 100)
        qna_ok = qna_pct >= 80
        self.btn_qna.setIconSize(QSize(12, 12))
        self.btn_qna.setIcon(render_vector_icon("check" if qna_ok else "alert", ok_color if qna_ok else warn_color, 12))
        self.btn_qna.setText("QA Ready" if qna_ok else f"QA {qna_pct}%")

        # Consolidated platforms
        platforms_dict = readiness.platforms or {}
        active_plats = [p for p in platforms_dict.keys() if p != "email"]
        ready_count = sum(1 for p, s in platforms_dict.items() if p != "email" and s in ("READY", "CONNECTED"))
        total_count = len(active_plats) or 4

        self.btn_platforms.setText(f"Platforms {ready_count}/{total_count}")
