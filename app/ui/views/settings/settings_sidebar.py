"""Vertical category navigation sidebar with active indicator and live status subtitles."""

from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS


class SidebarItem(QFrame):
    """Clickable navigation item representing a settings category."""

    clicked = Signal(str)

    def __init__(
        self,
        category_id: str,
        icon: str,
        title: str,
        subtitle: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.category_id = category_id
        self._is_active = False
        self._setup_ui(icon, title, subtitle)

    def _setup_ui(self, icon: str, title: str, subtitle: str) -> None:
        self.setObjectName("SidebarItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(54)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        # Icon
        self.lbl_icon = QLabel(icon)
        self.lbl_icon.setStyleSheet("font-size: 16px; background: transparent;")
        layout.addWidget(self.lbl_icon)

        # Text Layout
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setStyleSheet(f"""
            font-size: 13px;
            font-weight: 600;
            color: {COLORS.get('text', '#F0F6FC')};
            background: transparent;
        """)
        text_layout.addWidget(self.lbl_title)

        self.lbl_subtitle = QLabel(subtitle)
        self.lbl_subtitle.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS.get('text_muted', '#8B949E')};
            background: transparent;
        """)
        text_layout.addWidget(self.lbl_subtitle)

        layout.addLayout(text_layout, 1)
        self.update_style()

    def set_subtitle(self, text: str) -> None:
        self.lbl_subtitle.setText(text)

    def set_active(self, active: bool) -> None:
        self._is_active = active
        self.update_style()

    def update_style(self) -> None:
        if self._is_active:
            self.setStyleSheet(f"""
                QFrame#SidebarItem {{
                    background-color: {COLORS.get('surface_active', '#FF5F1522')};
                    border-left: 3px solid {COLORS.get('accent', '#FF5F15')};
                    border-radius: 6px;
                }}
            """)
            self.lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS.get('accent', '#FF5F15')}; background: transparent;")
        else:
            self.setStyleSheet(f"""
                QFrame#SidebarItem {{
                    background-color: transparent;
                    border-left: 3px solid transparent;
                    border-radius: 6px;
                }}
                QFrame#SidebarItem:hover {{
                    background-color: {COLORS.get('surface_hover', '#262C36')};
                }}
            """)
            self.lbl_title.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS.get('text', '#F0F6FC')}; background: transparent;")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.category_id)
        super().mousePressEvent(event)


class SettingsSidebar(QFrame):
    """Vertical category navigation bar for the redesigned Settings control center."""

    section_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._items: Dict[str, SidebarItem] = {}
        self._current_category: str = "general"
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setObjectName("SettingsSidebar")
        self.setFixedWidth(240)
        self.setStyleSheet(f"""
            QFrame#SettingsSidebar {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
                padding: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 8)
        layout.setSpacing(4)

        categories = [
            ("general", "⚙️", "General", "Interaction timing & loops"),
            ("browser", "🌐", "Browser", "Profiles & compatibility"),
            ("automation", "🛡️", "Automation", "Human review safeguards"),
            ("ai", "✦", "AI & Screening", "Ollama / Cloud LLM"),
            ("credentials", "🔐", "Credentials", "Accounts & email"),
            ("backup", "💾", "Backup & Restore", "System archives & restore"),
        ]

        for cat_id, icon, title, subtitle in categories:
            item = SidebarItem(cat_id, icon, title, subtitle, self)
            item.clicked.connect(self._on_item_clicked)
            layout.addWidget(item)
            self._items[cat_id] = item

        layout.addStretch()

        # Set default active
        self.set_current_section("general")

    def _on_item_clicked(self, category_id: str) -> None:
        if category_id != self._current_category:
            self.section_selected.emit(category_id)

    def set_current_section(self, category_id: str) -> None:
        cat = category_id.strip().lower()
        if cat in self._items:
            self._current_category = cat
            for cid, item in self._items.items():
                item.set_active(cid == cat)

    def set_subtitle(self, category_id: str, subtitle: str) -> None:
        cat = category_id.strip().lower()
        if cat in self._items:
            self._items[cat].set_subtitle(subtitle)
