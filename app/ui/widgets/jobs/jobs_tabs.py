"""Modern segmented category tabs for Jobs page: All Jobs, Easy Apply, Company Portal, Junk."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget
from app.ui.theme import COLORS


class JobsCategoryTabs(QWidget):
    """Segmented navigation tabs displaying categories with real-time job counts and Junk box."""

    tab_changed = Signal(object)  # None, "EASY_APPLY", "COMPANY_PORTAL", or "JUNK"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_method: Optional[str] = None
        self._counts = {"all": 0, "easy": 0, "portal": 0, "junk": 0}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_all = QPushButton("All Jobs")
        self.btn_easy = QPushButton("Easy Apply")
        self.btn_portal = QPushButton("Company Portal")
        self.btn_junk = QPushButton("🗑 Junk")

        for btn in [self.btn_all, self.btn_easy, self.btn_portal, self.btn_junk]:
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)

        self.btn_all.setChecked(True)

        self.btn_all.clicked.connect(lambda: self._on_btn_clicked(None))
        self.btn_easy.clicked.connect(lambda: self._on_btn_clicked("EASY_APPLY"))
        self.btn_portal.clicked.connect(lambda: self._on_btn_clicked("COMPANY_PORTAL"))
        self.btn_junk.clicked.connect(lambda: self._on_btn_clicked("JUNK"))

        layout.addWidget(self.btn_all)
        layout.addWidget(self.btn_easy)
        layout.addWidget(self.btn_portal)
        layout.addStretch()
        layout.addWidget(self.btn_junk)

        self._apply_styles()

    def _on_btn_clicked(self, method: Optional[str]) -> None:
        self.set_active_method(method)
        self.tab_changed.emit(self._current_method)

    def set_active_method(self, method: Optional[str]) -> None:
        self._current_method = method
        self.btn_all.setChecked(method is None)
        self.btn_easy.setChecked(method == "EASY_APPLY")
        self.btn_portal.setChecked(method == "COMPANY_PORTAL")
        self.btn_junk.setChecked(method == "JUNK")

    def get_active_method(self) -> Optional[str]:
        return self._current_method

    def set_counts(
        self,
        all_count: int,
        easy_count: int,
        portal_count: int,
        junk_count: int = 0,
    ) -> None:
        """Updates the count pills in the tabs."""
        self._counts = {
            "all": all_count,
            "easy": easy_count,
            "portal": portal_count,
            "junk": junk_count,
        }
        self.btn_all.setText(f"All Jobs  ({all_count})")
        self.btn_easy.setText(f"Easy Apply  ({easy_count})")
        self.btn_portal.setText(f"Company Portal  ({portal_count})")
        self.btn_junk.setText(f"🗑 Junk  ({junk_count})")

    def _apply_styles(self) -> None:
        style = f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border-color: {COLORS['border_light']};
            }}
            QPushButton:checked {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: 1px solid {COLORS['primary']};
                font-weight: 700;
            }}
        """
        self.btn_all.setStyleSheet(style)
        self.btn_easy.setStyleSheet(style)
        self.btn_portal.setStyleSheet(style)

        junk_style = f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 14px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover:!checked {{
                background-color: {COLORS['surface_hover']};
                color: #EF4444;
                border-color: #EF4444;
            }}
            QPushButton:checked {{
                background-color: #450A0A;
                color: #F87171;
                border: 1px solid #DC2626;
                font-weight: 700;
            }}
        """
        self.btn_junk.setStyleSheet(junk_style)
