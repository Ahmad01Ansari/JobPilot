"""Real-Time Agent Run Timeline Visualizer Widget for Desktop UI.

Renders horizontal step-by-step progress through the universal automation lifecycle:
[Init] -> [Navigate] -> [Analyze] -> [Map Fields] -> [Fill Form] -> [Review Gate] -> [Submit] -> [Verify] -> [Done]
"""

from typing import Dict, List, Optional, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class UniversalTimelineWidget(QFrame):
    """Horizontal step-by-step pipeline visualizer for Universal AI Application Agent."""

    STEPS: List[Tuple[str, str]] = [
        ("INITIALIZING", "Initialize"),
        ("NAVIGATING", "Navigate"),
        ("ANALYZING_PAGE", "Analyze Form"),
        ("MAPPING_FIELDS", "Map Facts"),
        ("FILLING_FORM", "Fill & Upload"),
        ("PENDING_HUMAN_REVIEW", "Review Gate"),
        ("SUBMITTING", "Submit"),
        ("VERIFYING_SUBMISSION", "Verify"),
        ("COMPLETED", "Done"),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.current_step = "IDLE"
        self.step_widgets: Dict[str, Dict[str, QLabel]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("universal_timeline_widget")
        self._refresh_frame_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header Title
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(6)

        lbl_tag = QLabel("⚡ UNIVERSAL AGENT EXECUTION TIMELINE")
        lbl_tag.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLORS.get('text_muted', '#8B949E')};
            letter-spacing: 0.5px;
            background: transparent;
        """)
        hdr_layout.addWidget(lbl_tag)

        hdr_layout.addStretch()

        self.lbl_status_msg = QLabel("Idle")
        self.lbl_status_msg.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS.get('primary', '#1F6FEB')};
            background: transparent;
        """)
        hdr_layout.addWidget(self.lbl_status_msg)

        layout.addLayout(hdr_layout)

        # Steps Row
        self.steps_container = QHBoxLayout()
        self.steps_container.setSpacing(0)
        self.steps_container.setContentsMargins(0, 0, 0, 0)

        step_keys = [k for k, _ in self.STEPS]
        for idx, (step_key, step_title) in enumerate(self.STEPS):
            step_box = QVBoxLayout()
            step_box.setAlignment(Qt.AlignCenter)
            step_box.setSpacing(3)

            # Node Badge
            badge = QLabel("○")
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(22, 22)

            # Step Title
            title_lbl = QLabel(step_title)
            title_lbl.setAlignment(Qt.AlignCenter)

            step_box.addWidget(badge, alignment=Qt.AlignCenter)
            step_box.addWidget(title_lbl, alignment=Qt.AlignCenter)

            self.step_widgets[step_key] = {
                "badge": badge,
                "title": title_lbl,
            }

            self.steps_container.addLayout(step_box)

            # Connector line between steps
            if idx < len(self.STEPS) - 1:
                line = QFrame()
                line.setFrameShape(QFrame.HLine)
                line.setFixedHeight(2)
                line.setStyleSheet(f"background-color: {COLORS.get('border', '#30363D')}; margin-bottom: 14px;")
                self.step_widgets[f"line_{idx}"] = {"line": line}
                self.steps_container.addWidget(line, 1)

        layout.addLayout(self.steps_container)
        self._refresh_step_styles()

    def update_state(self, state_str: str, message: str = "") -> None:
        """Updates active step indicator and status message."""
        self.current_step = (state_str or "IDLE").strip().upper()
        if message:
            self.lbl_status_msg.setText(message)
        else:
            self.lbl_status_msg.setText(self.current_step)

        self._refresh_step_styles()

    def reset(self) -> None:
        """Resets timeline to initial state."""
        self.current_step = "IDLE"
        self.lbl_status_msg.setText("Idle")
        self._refresh_step_styles()

    def _refresh_frame_style(self) -> None:
        tokens = COLORS
        self.setStyleSheet(f"""
            QFrame#universal_timeline_widget {{
                background-color: {tokens.get('surface_alt', '#0D1117')};
                border: 1px solid {tokens.get('border', '#30363D')};
                border-radius: 8px;
            }}
        """)

    def _refresh_step_styles(self) -> None:
        tokens = COLORS
        step_keys = [k for k, _ in self.STEPS]

        # Determine current index
        current_idx = -1
        if self.current_step in step_keys:
            current_idx = step_keys.index(self.current_step)
        elif self.current_step == "PAUSED_FOR_INTERVENTION":
            current_idx = step_keys.index("PENDING_HUMAN_REVIEW")

        for idx, (step_key, _) in enumerate(self.STEPS):
            w = self.step_widgets.get(step_key, {})
            badge = w.get("badge")
            title = w.get("title")
            if not badge or not title:
                continue

            if current_idx >= 0 and idx < current_idx:
                # Completed step
                badge.setText("✓")
                badge.setStyleSheet(f"""
                    background-color: {tokens.get('success_subtle', '#23863622')};
                    color: {tokens.get('success', '#2EA043')};
                    border: 1px solid {tokens.get('success', '#2EA043')};
                    border-radius: 11px;
                    font-size: 11px;
                    font-weight: 700;
                """)
                title.setStyleSheet(f"color: {tokens.get('text', '#F0F6FC')}; font-size: 10px; font-weight: 600; background: transparent;")
            elif idx == current_idx:
                # Active step
                is_paused = (self.current_step == "PAUSED_FOR_INTERVENTION" or step_key == "PENDING_HUMAN_REVIEW")
                color = tokens.get('warning', '#D29922') if is_paused else tokens.get('primary', '#1F6FEB')
                char = "⚠" if is_paused else "●"
                badge.setText(char)
                badge.setStyleSheet(f"""
                    background-color: {color}33;
                    color: {color};
                    border: 2px solid {color};
                    border-radius: 11px;
                    font-size: 11px;
                    font-weight: 700;
                """)
                title.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: 700; background: transparent;")
            else:
                # Future pending step
                badge.setText("○")
                badge.setStyleSheet(f"""
                    background-color: transparent;
                    color: {tokens.get('text_muted', '#8B949E')};
                    border: 1px solid {tokens.get('border', '#30363D')};
                    border-radius: 11px;
                    font-size: 10px;
                """)
                title.setStyleSheet(f"color: {tokens.get('text_muted', '#8B949E')}; font-size: 10px; font-weight: 500; background: transparent;")

            # Line styling
            line_w = self.step_widgets.get(f"line_{idx}", {})
            line = line_w.get("line")
            if line:
                if current_idx >= 0 and idx < current_idx:
                    line.setStyleSheet(f"background-color: {tokens.get('success', '#2EA043')}; margin-bottom: 14px;")
                else:
                    line.setStyleSheet(f"background-color: {tokens.get('border', '#30363D')}; margin-bottom: 14px;")

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_frame_style()
        self._refresh_step_styles()
