"""Visual Canonical Pipeline Flow Map displaying 8 execution stages."""

from typing import List, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeManager


CANONICAL_STAGES = [
    ("SEARCH", "Search"),
    ("DISCOVER", "Discover"),
    ("QUALIFY", "Qualify"),
    ("APPLICATION", "Apply"),
    ("REVIEW", "Review"),
    ("SUBMISSION", "Submit"),
    ("VERIFICATION", "Verify"),
    ("COMPLETED", "Done"),
]


class StageNode(QFrame):
    """Individual stage node in the canonical execution pipeline."""

    def __init__(self, stage_id: str, label: str, step_num: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.stage_id = stage_id
        self.label_text = label
        self.step_num = step_num
        self._state = "UPCOMING"  # COMPLETED, ACTIVE, UPCOMING, SKIPPED
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignCenter)

        self.icon_lbl = QLabel("○")
        self.icon_lbl.setStyleSheet("font-size: 10px; background: transparent; border: none;")
        layout.addWidget(self.icon_lbl)

        self.text_lbl = QLabel(f"{self.step_num}. {self.label_text}")
        self.text_lbl.setStyleSheet("font-size: 11px; font-weight: 600; background: transparent; border: none;")
        layout.addWidget(self.text_lbl)

        self._apply_style()

    def set_state(self, state: str) -> None:
        self._state = state
        self._apply_style()

    def _apply_style(self) -> None:
        c = ThemeManager.get_instance().colors

        if self._state == "ACTIVE":
            self.setStyleSheet(f"""
                StageNode {{
                    background-color: {c.get('primary', '#FF5F15')};
                    border: 1px solid {c.get('primary', '#FF5F15')};
                    border-radius: 6px;
                }}
            """)
            self.icon_lbl.setText("●")
            self.icon_lbl.setStyleSheet("font-size: 9px; color: #FFFFFF; background: transparent; border: none;")
            self.text_lbl.setStyleSheet("font-size: 11px; font-weight: 800; color: #FFFFFF; background: transparent; border: none;")
        elif self._state == "COMPLETED":
            self.setStyleSheet("""
                StageNode {
                    background-color: rgba(46, 160, 67, 0.15);
                    border: 1px solid rgba(46, 160, 67, 0.45);
                    border-radius: 6px;
                }
            """)
            self.icon_lbl.setText("✓")
            self.icon_lbl.setStyleSheet("font-size: 11px; font-weight: 800; color: #3FB950; background: transparent; border: none;")
            self.text_lbl.setStyleSheet("font-size: 11px; font-weight: 700; color: #3FB950; background: transparent; border: none;")
        else:  # UPCOMING
            self.setStyleSheet(f"""
                StageNode {{
                    background-color: {c.get('surface_alt', '#1C2128')};
                    border: 1px solid {c.get('border', '#262C36')};
                    border-radius: 6px;
                }}
            """)
            self.icon_lbl.setText("○")
            self.icon_lbl.setStyleSheet(f"font-size: 9px; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")
            self.text_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")


class PipelineFlowMap(QFrame):
    """Horizontal pipeline visualization tracking normalized automation execution stages."""

    def __init__(self, parent: Optional[QWidget] = None, embedded: bool = False):
        super().__init__(parent)
        self.nodes: List[StageNode] = []
        self._embedded = embedded
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        if self._embedded:
            self.setStyleSheet("PipelineFlowMap { background: transparent; border: none; }")
        else:
            self.setStyleSheet(f"""
                PipelineFlowMap {{
                    background-color: {c.get("surface", "#161B22")};
                    border: 1px solid {c.get("border", "#262C36")};
                    border-radius: 8px;
                }}
            """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        for idx, (s_id, s_lbl) in enumerate(CANONICAL_STAGES):
            node = StageNode(stage_id=s_id, label=s_lbl, step_num=idx + 1, parent=self)
            self.nodes.append(node)
            layout.addWidget(node, 1)

            # Connector arrow except for last node
            if idx < len(CANONICAL_STAGES) - 1:
                arrow = QLabel("›")
                arrow.setStyleSheet(f"color: {c.get('border_light', '#333A46')}; font-size: 14px; font-weight: 700; background: transparent; border: none;")
                layout.addWidget(arrow)

    def set_current_stage(self, stage_name: Optional[str]) -> None:
        """Updates pipeline nodes highlighting active and completed stages."""
        clean_stage = (stage_name or "").upper().strip()
        stage_order = [s_id for s_id, _ in CANONICAL_STAGES]

        active_idx = -1
        for idx, s_id in enumerate(stage_order):
            if s_id in clean_stage or clean_stage in s_id:
                active_idx = idx
                break

        for idx, node in enumerate(self.nodes):
            if active_idx == -1:
                node.set_state("UPCOMING")
            elif idx < active_idx:
                node.set_state("COMPLETED")
            elif idx == active_idx:
                node.set_state("ACTIVE")
            else:
                node.set_state("UPCOMING")
