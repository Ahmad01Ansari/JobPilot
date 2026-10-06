"""Resume workspace filter, search, sort, and action toolbar."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.ui.theme import COLORS


class ResumeFilterToolbar(QFrame):
    """Toolbar providing search, role/status filtering, sort order, grid/table view switch, and upload button."""

    search_changed = Signal(str)
    role_filter_changed = Signal(str)
    status_filter_changed = Signal(str)
    sort_changed = Signal(str)
    view_mode_changed = Signal(str)  # "grid" or "table"
    upload_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("filterToolbar")
        self.setStyleSheet(f"""
            QFrame#filterToolbar {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 6px 12px;
            }}
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
                min-width: 240px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 500;
                min-width: 120px;
            }}
            QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                selection-background-color: {COLORS['surface_hover']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px;
            }}
            QPushButton#viewToggle {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 6px 10px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton#viewToggle:checked {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
                border-color: {COLORS['accent']};
            }}
            QPushButton#btnUpload {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#btnUpload:hover {{
                background-color: {COLORS['primary_hover'] if 'primary_hover' in COLORS else COLORS['accent']};
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        # 1. Search Box
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍  Search resumes, skills, notes...")
        self.txt_search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.txt_search)

        # 2. Target Role Filter
        self.combo_role = QComboBox()
        self.combo_role.addItem("All Roles", "ALL")
        self.combo_role.addItem("General", "GENERAL")
        self.combo_role.currentIndexChanged.connect(self._on_role_changed)
        layout.addWidget(self.combo_role)

        # 3. Status Filter (Active / Archived)
        self.combo_status = QComboBox()
        self.combo_status.addItem("Active Resumes", "ACTIVE")
        self.combo_status.addItem("Archived Resumes", "ARCHIVED")
        self.combo_status.addItem("All Resumes", "ALL")
        self.combo_status.currentIndexChanged.connect(self._on_status_changed)
        layout.addWidget(self.combo_status)

        # 4. Sort Filter
        self.combo_sort = QComboBox()
        self.combo_sort.addItem("Default / Recent", "RECENT")
        self.combo_sort.addItem("Most Applications", "MOST_APPS")
        self.combo_sort.addItem("Name (A-Z)", "NAME")
        self.combo_sort.addItem("Highest Version", "VERSION")
        self.combo_sort.currentIndexChanged.connect(self._on_sort_changed)
        layout.addWidget(self.combo_sort)

        layout.addStretch()

        # 5. View Mode Switch (Grid vs Table)
        view_toggle_layout = QHBoxLayout()
        view_toggle_layout.setSpacing(0)
        self.btn_grid = QPushButton("▦ Grid")
        self.btn_grid.setObjectName("viewToggle")
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(True)
        self.btn_grid.setCursor(Qt.PointingHandCursor)
        self.btn_grid.setStyleSheet("border-top-left-radius: 6px; border-bottom-left-radius: 6px;")

        self.btn_table = QPushButton("☰ Table")
        self.btn_table.setObjectName("viewToggle")
        self.btn_table.setCheckable(True)
        self.btn_table.setCursor(Qt.PointingHandCursor)
        self.btn_table.setStyleSheet("border-top-right-radius: 6px; border-bottom-right-radius: 6px; border-left: none;")

        self.view_group = QButtonGroup(self)
        self.view_group.addButton(self.btn_grid)
        self.view_group.addButton(self.btn_table)
        self.view_group.setExclusive(True)

        self.btn_grid.clicked.connect(lambda: self.view_mode_changed.emit("grid"))
        self.btn_table.clicked.connect(lambda: self.view_mode_changed.emit("table"))

        view_toggle_layout.addWidget(self.btn_grid)
        view_toggle_layout.addWidget(self.btn_table)
        layout.addLayout(view_toggle_layout)

        # 6. Upload Action Button
        self.btn_upload = QPushButton("+ Upload Resume")
        self.btn_upload.setObjectName("btnUpload")
        self.btn_upload.setCursor(Qt.PointingHandCursor)
        self.btn_upload.clicked.connect(self.upload_requested.emit)
        layout.addWidget(self.btn_upload)

    def populate_roles(self, roles: List[str]):
        """Populates the role filter dropdown with dynamic role options while preserving selection."""
        current_data = self.combo_role.currentData()
        self.combo_role.blockSignals(True)
        self.combo_role.clear()
        self.combo_role.addItem("All Roles", "ALL")
        self.combo_role.addItem("General", "GENERAL")
        for r in sorted(set(r for r in roles if r and r.lower() != "general")):
            self.combo_role.addItem(r, r)

        # Restore selection if exists
        idx = self.combo_role.findData(current_data)
        if idx != -1:
            self.combo_role.setCurrentIndex(idx)
        else:
            self.combo_role.setCurrentIndex(0)
        self.combo_role.blockSignals(False)

    def _on_role_changed(self, idx: int):
        role_data = self.combo_role.currentData() or "ALL"
        self.role_filter_changed.emit(role_data)

    def _on_status_changed(self, idx: int):
        status_data = self.combo_status.currentData() or "ACTIVE"
        self.status_filter_changed.emit(status_data)

    def _on_sort_changed(self, idx: int):
        sort_data = self.combo_sort.currentData() or "RECENT"
        self.sort_changed.emit(sort_data)
