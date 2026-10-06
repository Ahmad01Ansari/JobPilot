"""Provider Setup and Guidance Modal Dialog for JobPilot AI Engine.

Displays step-by-step configuration guidance, verified first-party documentation
links, API key console links, and official pricing resources.
"""

from typing import Optional
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.ai.provider_registry import ProviderDefinition
from app.ui.theme import COLORS


class ProviderSetupDialog(QDialog):
    """Modal dialog displaying setup instructions, official developer links, and data privacy disclosures."""

    def __init__(
        self,
        provider: ProviderDefinition,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.provider = provider
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(f"Setup Guide — {self.provider.display_name}")
        self.setFixedWidth(520)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 10px;
            }}
            QLabel {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header with category badge
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        title_lbl = QLabel(self.provider.display_name)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        header_layout.addWidget(title_lbl)

        cat_badge = QLabel(self.provider.category.upper())
        badge_bg = COLORS.get('success', '#2EA043') if self.provider.is_local else COLORS.get('info', '#388BFD')
        cat_badge.setStyleSheet(f"""
            background-color: {badge_bg}22;
            color: {badge_bg};
            border: 1px solid {badge_bg};
            border-radius: 4px;
            font-size: 10px;
            font-weight: 700;
            padding: 2px 6px;
        """)
        header_layout.addWidget(cat_badge)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Step-by-step guidance card
        steps_card = QFrame()
        steps_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_alt', '#1C2128')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 8px;
            padding: 12px;
        """)
        steps_layout = QVBoxLayout(steps_card)
        steps_layout.setContentsMargins(12, 10, 12, 10)
        steps_layout.setSpacing(8)

        steps_title = QLabel("Setup Steps:")
        steps_title.setStyleSheet(f"font-weight: 700; font-size: 13px; color: {COLORS.get('text', '#F0F6FC')};")
        steps_layout.addWidget(steps_title)

        if self.provider.setup_steps:
            for idx, step in enumerate(self.provider.setup_steps, 1):
                step_lbl = QLabel(f"<b>{idx}.</b> {step}")
                step_lbl.setWordWrap(True)
                step_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text', '#F0F6FC')}; line-height: 1.4;")
                steps_layout.addWidget(step_lbl)
        else:
            no_steps = QLabel("Configure standard endpoint URL and model identifier.")
            no_steps.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
            steps_layout.addWidget(no_steps)

        layout.addWidget(steps_card)

        # Official Links Section
        links_layout = QHBoxLayout()
        links_layout.setSpacing(8)

        if self.provider.docs_url:
            btn_docs = QPushButton("📖 Documentation")
            btn_docs.setCursor(Qt.PointingHandCursor)
            btn_docs.setStyleSheet(self._link_btn_style())
            btn_docs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.provider.docs_url)))
            links_layout.addWidget(btn_docs)

        if self.provider.api_key_url:
            btn_key = QPushButton("🔑 Get API Key")
            btn_key.setCursor(Qt.PointingHandCursor)
            btn_key.setStyleSheet(self._link_btn_style())
            btn_key.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.provider.api_key_url)))
            links_layout.addWidget(btn_key)

        if self.provider.pricing_url:
            btn_pricing = QPushButton("💳 View Official Pricing")
            btn_pricing.setCursor(Qt.PointingHandCursor)
            btn_pricing.setStyleSheet(self._link_btn_style())
            btn_pricing.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.provider.pricing_url)))
            links_layout.addWidget(btn_pricing)

        links_layout.addStretch()
        layout.addLayout(links_layout)

        # Data Privacy Notice
        privacy_card = QFrame()
        privacy_card.setStyleSheet(f"""
            background-color: {COLORS.get('surface_active', '#FF5F1511')};
            border: 1px solid {COLORS.get('border', '#262C36')};
            border-radius: 6px;
            padding: 10px;
        """)
        p_layout = QVBoxLayout(privacy_card)
        p_layout.setContentsMargins(10, 8, 10, 8)
        p_layout.setSpacing(4)

        p_title = QLabel("🔒 Data Privacy & Transmission Notice" if self.provider.is_local else "🌐 Third-Party Data Transmission Notice")
        p_title.setStyleSheet(f"font-weight: 700; font-size: 11px; color: {COLORS.get('text', '#F0F6FC')};")
        p_layout.addWidget(p_title)

        if self.provider.is_local:
            p_desc = QLabel(
                "Local inference runs strictly on your machine. No resume, screening, or candidate data is transmitted outside your computer."
            )
        else:
            p_desc = QLabel(
                f"Prompts and Q&A texts will be transmitted via HTTPS to {self.provider.display_name}. "
                "Consult the provider's privacy policy for details on inference data retention."
            )
        p_desc.setWordWrap(True)
        p_desc.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        p_layout.addWidget(p_desc)
        layout.addWidget(privacy_card)

        # Footer close button
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 8px 16px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

    def _link_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('info', '#388BFD')};
                font-size: 12px;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border-color: {COLORS.get('info', '#388BFD')};
            }}
        """
