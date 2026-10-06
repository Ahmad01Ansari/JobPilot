"""Compact horizontal execution pipeline widget for Automation Control Center.

Visualizes live candidate stage progression across:
DISCOVERED → EVALUATING → QUALIFIED → APPLYING → SUBMITTED
with real-time counts, clean stage arrows, and active state emphasis.
"""

from typing import Dict, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS
from app.ui.widgets.automation.state import AutomationUIState


class PipelineStageNode(QWidget):
    """Compact single stage node in the horizontal execution pipeline."""

    def __init__(self, stage_name: str, color_key: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.stage_name = stage_name
        self.color_key = color_key
        self._count = 0
        self._is_active = False
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_count = QLabel("0")
        self.lbl_count.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_count)

        self.lbl_title = QLabel(self.stage_name.upper())
        self.lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_title)

        self._refresh_styles()

    def set_count(self, count: int, is_active: bool = False) -> None:
        self._count = count
        self._is_active = is_active
        self.lbl_count.setText(str(count))
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        tokens = COLORS
        if self._is_active:
            val_col = tokens.get("cyan", "#39C5CF")
        elif self._count > 0:
            val_col = tokens.get(self.color_key, tokens.get("text", "#F0F6FC"))
        else:
            val_col = tokens.get("text_muted", "#8B949E")

        self.lbl_count.setStyleSheet(f"""
            color: {val_col};
            font-size: 18px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: transparent;
            border: none;
        """)
        self.lbl_title.setStyleSheet(f"""
            color: {tokens.get('text_muted', '#8B949E')};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
            background: transparent;
            border: none;
        """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()


class AutomationPipeline(QFrame):
    """Compact horizontal execution pipeline showing stage progression."""

    STAGES = [
        ("discovered", "Discovered", "primary"),
        ("evaluating", "Evaluating", "accent"),
        ("qualified", "Qualified", "info"),
        ("applying", "Applying", "cyan"),
        ("submitted", "Submitted", "success"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.nodes: Dict[str, PipelineStageNode] = {}
        self.arrows: list[QLabel] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("automation_pipeline")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 6, 14, 6)
        layout.setSpacing(6)

        # Header tag
        lbl_tag = QLabel("PIPELINE")
        lbl_tag.setStyleSheet(f"""
            color: {COLORS.get('text_muted', '#8B949E')};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        layout.addWidget(lbl_tag)
        layout.addSpacing(8)

        # Legacy backward-compatibility processing badge
        self.badge_processing = QLabel("Active: 0")
        self.badge_processing.setVisible(False)

        # Build horizontal nodes with arrows
        total_stages = len(self.STAGES)
        for idx, (key, label, color_key) in enumerate(self.STAGES):
            node = PipelineStageNode(label, color_key, self)
            self.nodes[key] = node
            layout.addWidget(node, 1)

            if idx < total_stages - 1:
                arrow = QLabel("→")
                arrow.setAlignment(Qt.AlignCenter)
                self.arrows.append(arrow)
                layout.addWidget(arrow)

        self._refresh_styles()

    def update_from_state(self, state: AutomationUIState) -> None:
        """Updates all node counts from state snapshot."""
        # Calculate active transient applying vs total submitted
        evaluating_count = max(0, state.jobs_evaluated - state.jobs_qualified - state.jobs_skipped)
        applying_count = state.active_processing_count if state.is_running() else 0

        self.nodes["discovered"].set_count(state.jobs_discovered)
        self.nodes["evaluating"].set_count(state.jobs_evaluated, is_active=(evaluating_count > 0 and state.is_running()))
        self.nodes["qualified"].set_count(state.jobs_qualified)
        self.nodes["applying"].set_count(applying_count, is_active=(applying_count > 0 and state.is_running()))
        self.nodes["submitted"].set_count(state.applications_submitted)

        self.badge_processing.setText(f"Active: {applying_count}")
        self._refresh_styles()

    def _refresh_styles(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QFrame#automation_pipeline {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
            }}
        """)
        for arrow in self.arrows:
            arrow.setStyleSheet(f"""
                color: {tokens.get('border_light', '#333A46')};
                font-size: 14px;
                font-weight: bold;
                background: transparent;
                border: none;
            """)
        for node in self.nodes.values():
            node.apply_theme(tokens)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
