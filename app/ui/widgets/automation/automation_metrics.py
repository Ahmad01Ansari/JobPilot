"""Compact KPI metric row for Automation Control Center.

Displays real-time counts for Discovered, Evaluated, Qualified, Submitted,
Skipped, and Errors, while preserving legacy label references for test compatibility.
"""

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS
from app.ui.widgets.automation.state import AutomationUIState


class AutomationMetricRow(QWidget):
    """Row of compact KPI cards reflecting runner statistics."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.cards: list[QFrame] = []
        self.title_labels: list[QLabel] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Exact legacy attribute names required by integration test assertions
        self.val_discovered = QLabel("0")
        self.val_evaluated = QLabel("0")
        self.val_qualified = QLabel("0")
        self.val_applied = QLabel("0")
        self.val_skipped = QLabel("0")
        self.val_errors = QLabel("0")

        metrics_config = [
            ("Jobs Discovered", self.val_discovered, "primary"),
            ("Jobs Evaluated", self.val_evaluated, "text"),
            ("Qualified", self.val_qualified, "accent"),
            ("Submitted", self.val_applied, "success"),
            ("Skipped", self.val_skipped, "text_muted"),
            ("Errors", self.val_errors, "danger"),
        ]

        for idx, (title, val_lbl, color_key) in enumerate(metrics_config):
            card = QFrame()
            card.setObjectName(f"metric_card_{idx}")
            card.setStyleSheet(f"""
                QFrame#metric_card_{idx} {{
                    background-color: {COLORS['surface']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 8px;
                }}
            """)
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(10, 6, 10, 6)
            c_layout.setSpacing(2)

            lbl_title = QLabel(title)
            lbl_title.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS['text_muted']};
                    font-size: 11px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
            """)
            self.title_labels.append(lbl_title)
            c_layout.addWidget(lbl_title)

            color_val = COLORS.get(color_key, COLORS["text"])
            val_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {color_val};
                    font-size: 22px;
                    font-weight: 800;
                    letter-spacing: -0.5px;
                }}
            """)
            c_layout.addWidget(val_lbl)

            layout.addWidget(card, 0, idx)
            self.cards.append(card)

    def update_from_state(self, state: AutomationUIState) -> None:
        """Updates metric counts from current state snapshot."""
        self.val_discovered.setText(str(state.jobs_discovered))
        self.val_evaluated.setText(str(state.jobs_evaluated))
        self.val_qualified.setText(str(state.jobs_qualified))
        self.val_applied.setText(str(state.applications_submitted))
        self.val_skipped.setText(str(state.jobs_skipped))
        self.val_errors.setText(str(state.errors_count))

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        """Refreshes styling on theme change."""
        for idx, card in enumerate(self.cards):
            card.setStyleSheet(f"""
                QFrame#metric_card_{idx} {{
                    background-color: {tokens['surface']};
                    border: 1px solid {tokens['border']};
                    border-radius: 8px;
                }}
            """)
        for lbl in self.title_labels:
            lbl.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")

        self.val_discovered.setStyleSheet(f"color: {tokens['primary']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        self.val_evaluated.setStyleSheet(f"color: {tokens['text']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        self.val_qualified.setStyleSheet(f"color: {tokens['accent']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        self.val_applied.setStyleSheet(f"color: {tokens['success']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        self.val_skipped.setStyleSheet(f"color: {tokens['text_muted']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
        self.val_errors.setStyleSheet(f"color: {tokens['danger']}; font-size: 22px; font-weight: 800; letter-spacing: -0.5px;")
