"""Platform selection segmented control component for Automation Control Center.

Provides a sleek, compact horizontal segmented switcher for selecting target platforms
(LinkedIn, Naukri.com, Indeed, Foundit, All Platforms) with single-source-of-truth state
and 100% backward compatibility with combo_platform.
"""

from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class PlatformSelector(QWidget):
    """Compact segmented platform switcher with bidirectional combo_platform sync."""

    platform_changed = Signal(str)  # platform key ("linkedin", "naukri", "indeed", "foundit", "all")

    PLATFORMS = [
        ("linkedin", "LinkedIn", "Easy Apply"),
        ("naukri", "Naukri.com", "Fast Forward"),
        ("indeed", "Indeed", "Smart Apply"),
        ("foundit", "Foundit", "Quick Apply"),
        ("glassdoor", "Glassdoor", "Easy Apply"),
        ("universal", "Universal ATS", "Stagehand AI"),
        ("all", "All Platforms", "Sequential"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.buttons: Dict[str, QPushButton] = {}
        self.cards: Dict[str, QWidget] = {}  # Backward-compatibility alias
        self.card_titles: Dict[str, QLabel] = {}
        self.selected_platform = "linkedin"
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header Row: Label on left, docked combo_platform on right (for test contract compatibility)
        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        self.lbl_section = QLabel("Target Platform")
        self.lbl_section.setStyleSheet(f"""
            QLabel {{
                color: {COLORS.get('text_muted', '#8B949E')};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        header_row.addWidget(self.lbl_section)
        header_row.addStretch()

        # Backward compatibility combo_platform
        self.combo_platform = QComboBox()
        self.combo_platform.addItem("LinkedIn (Easy Apply)", "linkedin")
        self.combo_platform.addItem("Naukri.com (Fast Forward)", "naukri")
        self.combo_platform.addItem("Indeed (Smart Apply)", "indeed")
        self.combo_platform.addItem("Foundit (Quick Apply)", "foundit")
        self.combo_platform.addItem("Glassdoor (Easy Apply)", "glassdoor")
        self.combo_platform.addItem("All Platforms (Sequential)", "all")
        self.combo_platform.setVisible(False)
        self.combo_platform.currentIndexChanged.connect(self._on_combo_index_changed)
        header_row.addWidget(self.combo_platform)

        main_layout.addLayout(header_row)

        # Segmented Control Container
        self.segment_container = QFrame()
        self.segment_container.setObjectName("segment_container")
        self.segment_container.setFixedHeight(36)

        seg_layout = QHBoxLayout(self.segment_container)
        seg_layout.setContentsMargins(2, 2, 2, 2)
        seg_layout.setSpacing(2)

        self.btn_group = QButtonGroup(self)
        self.btn_group.setExclusive(True)

        for key, name, subtitle in self.PLATFORMS:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(32)
            btn.setToolTip(f"{name} — {subtitle}")
            btn.clicked.connect(lambda checked=False, k=key: self.select_platform(k))

            self.buttons[key] = btn
            self.cards[key] = btn
            # Dummy label holder for backward compatibility if accessed
            dummy_lbl = QLabel(name)
            dummy_lbl.setVisible(False)
            self.card_titles[key] = dummy_lbl

            self.btn_group.addButton(btn)
            seg_layout.addWidget(btn)

        main_layout.addWidget(self.segment_container)
        self._refresh_styles()

        # Set default
        self.select_platform("linkedin", emit_signal=False)

    def select_platform(self, platform_key: str, emit_signal: bool = True) -> None:
        """Selects a platform, updates button checks, and syncs combo_platform."""
        key = (platform_key or "linkedin").strip().lower()
        if key not in self.buttons:
            key = "linkedin"

        self.selected_platform = key
        for p_key, btn in self.buttons.items():
            btn.setChecked(p_key == key)

        # Sync combo index without re-triggering loop
        idx = self.combo_platform.findData(key)
        if idx >= 0 and self.combo_platform.currentIndex() != idx:
            self.combo_platform.blockSignals(True)
            self.combo_platform.setCurrentIndex(idx)
            self.combo_platform.blockSignals(False)

        self._refresh_styles()

        if emit_signal:
            self.platform_changed.emit(key)

    def current_platform(self) -> str:
        """Returns the currently active platform key."""
        return self.selected_platform

    def _on_combo_index_changed(self, index: int) -> None:
        """Syncs internal state if external code alters combo_platform."""
        key = self.combo_platform.itemData(index)
        if key and key != self.selected_platform:
            self.select_platform(key, emit_signal=True)

    def _refresh_styles(self) -> None:
        tokens = COLORS
        self.lbl_section.setStyleSheet(f"""
            QLabel {{
                color: {tokens.get('text_muted', '#8B949E')};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
        """)
        self.segment_container.setStyleSheet(f"""
            QFrame#segment_container {{
                background-color: {tokens.get('surface', '#161B22')};
                border: 1px solid {tokens.get('border', '#262C36')};
                border-radius: 8px;
            }}
        """)

        for key, btn in self.buttons.items():
            is_active = (key == self.selected_platform)
            if is_active:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {tokens.get('primary', '#FF5F15')};
                        color: #FFFFFF;
                        font-size: 12px;
                        font-weight: 700;
                        border-radius: 6px;
                        border: none;
                        padding: 0 12px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: transparent;
                        color: {tokens.get('text_muted', '#8B949E')};
                        font-size: 12px;
                        font-weight: 600;
                        border-radius: 6px;
                        border: none;
                        padding: 0 12px;
                    }}
                    QPushButton:hover {{
                        background-color: {tokens.get('surface_hover', '#262C36')};
                        color: {tokens.get('text', '#F0F6FC')};
                    }}
                """)

    def apply_theme(self, tokens: Dict[str, str]) -> None:
        self._refresh_styles()
