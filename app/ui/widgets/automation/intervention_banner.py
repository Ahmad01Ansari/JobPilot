"""Manual Intervention alert banner widget for Automation Control Center.

Displays notifications when user attention is required (CAPTCHA, login, OTP)
without fabricating non-existent resumption APIs, and preserves legacy attributes.
"""

from typing import Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.services.automation_events import AutomationInterventionEvent
from app.ui.theme import COLORS


class InterventionBanner(QFrame):
    """Alert banner for human intervention checkpoints."""

    captcha_resolved = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("intervention_card")
        self.setStyleSheet(f"""
            QFrame#intervention_card {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#30363D')};
                border-left: 4px solid {COLORS.get('warning', '#D29922')};
                border-radius: 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Elegant Icon Pill
        self.icon_badge = QLabel("🛡️")
        self.icon_badge.setAlignment(Qt.AlignCenter)
        self.icon_badge.setFixedSize(28, 28)
        self.icon_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('warning_subtle', '#D2992218')};
                border: 1px solid {COLORS.get('border_light', '#333A46')};
                border-radius: 6px;
                font-size: 14px;
            }}
        """)
        layout.addWidget(self.icon_badge)

        # Legacy-compatible label attribute with refined high-contrast styling
        self.lbl_intervention = QLabel("Attention Required: Manual action needed.")
        self.lbl_intervention.setStyleSheet(f"""
            QLabel {{
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 13px;
                line-height: 1.4;
            }}
            b {{
                color: {COLORS.get('warning', '#D29922')};
                font-weight: 700;
            }}
        """)
        self.lbl_intervention.setWordWrap(True)
        layout.addWidget(self.lbl_intervention, 1)

        # Human-in-the-loop CAPTCHA resolved button
        self.btn_resolve_captcha = QPushButton("✓ I Have Resolved CAPTCHA")
        self.btn_resolve_captcha.setFixedHeight(30)
        self.btn_resolve_captcha.setCursor(Qt.PointingHandCursor)
        self.btn_resolve_captcha.setStyleSheet("""
            QPushButton {
                background-color: #238636;
                color: #FFFFFF;
                font-weight: 700;
                font-size: 12px;
                padding: 0 16px;
                border-radius: 6px;
                border: 1px solid #2ea043;
            }
            QPushButton:hover {
                background-color: #2ea043;
                border-color: #3fb950;
            }
            QPushButton:pressed {
                background-color: #1b6528;
            }
        """)
        self.btn_resolve_captcha.clicked.connect(self._on_captcha_resolved_clicked)
        self.btn_resolve_captcha.setVisible(False)
        layout.addWidget(self.btn_resolve_captcha)

        # Legacy-compatible dismiss button attribute with subtle outline styling
        self.btn_dismiss_intervention = QPushButton("Dismiss Notice")
        self.btn_dismiss_intervention.setFixedHeight(30)
        self.btn_dismiss_intervention.setCursor(Qt.PointingHandCursor)
        self.btn_dismiss_intervention.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS.get('text_muted', '#8B949E')};
                font-weight: 600;
                font-size: 12px;
                padding: 0 14px;
                border-radius: 6px;
                border: 1px solid {COLORS.get('border', '#30363D')};
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                border-color: {COLORS.get('border_light', '#333A46')};
            }}
        """)
        self.btn_dismiss_intervention.clicked.connect(self.dismiss)
        layout.addWidget(self.btn_dismiss_intervention)

        self.setVisible(False)

    def _on_captcha_resolved_clicked(self) -> None:
        """Handles user clicking resolved button on banner."""
        self.captcha_resolved.emit()
        self.dismiss()

    def show_intervention(self, event: AutomationInterventionEvent) -> None:
        """Displays intervention message and unhides banner."""
        type_str = event.intervention_type.value if hasattr(event.intervention_type, "value") else str(event.intervention_type)
        msg = f"<b>{type_str}</b>: {event.message}"
        self.lbl_intervention.setText(msg)
        is_captcha = "captcha" in type_str.lower() or "captcha" in event.message.lower()
        self.btn_resolve_captcha.setVisible(is_captcha)
        self.setVisible(True)

    def dismiss(self) -> None:
        """Hides notice banner."""
        self.setVisible(False)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        """Refreshes styling on theme change."""
        self.setStyleSheet(f"""
            QFrame#intervention_card {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#30363D')};
                border-left: 4px solid {tokens.get('warning', '#D29922')};
                border-radius: 8px;
            }}
        """)
        self.lbl_intervention.setStyleSheet(f"""
            QLabel {{
                color: {tokens.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 13px;
                line-height: 1.4;
            }}
            b {{
                color: {tokens.get('warning', '#D29922')};
                font-weight: 700;
            }}
        """)
        self.icon_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {tokens.get('warning_subtle', '#D2992218')};
                border: 1px solid {tokens.get('border_light', '#333A46')};
                border-radius: 6px;
                font-size: 14px;
            }}
        """)
        self.btn_dismiss_intervention.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {tokens.get('text_muted', '#8B949E')};
                font-weight: 600;
                font-size: 12px;
                padding: 0 14px;
                border-radius: 6px;
                border: 1px solid {tokens.get('border', '#30363D')};
            }}
            QPushButton:hover {{
                background-color: {tokens.get('surface_hover', '#262C36')};
                color: {tokens.get('text', '#F0F6FC')};
                border-color: {tokens.get('border_light', '#333A46')};
            }}
        """)
