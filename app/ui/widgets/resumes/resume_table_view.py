"""Compact, sortable table view for resumes."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Resume
from app.ui.theme import COLORS


class ResumeTableView(QTableWidget):
    """Table representation of resume library with sorting and action menus."""

    resume_selected = Signal(int)
    action_preview = Signal(int)
    action_set_default = Signal(int)
    action_new_version = Signal(int)
    action_edit = Signal(int)
    action_archive = Signal(int)
    action_unarchive = Signal(int)
    action_delete = Signal(int)
    action_open_os = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setColumnCount(7)
        self.setHorizontalHeaderLabels([
            "Name",
            "Target Role",
            "Version",
            "Health",
            "Applications",
            "Last Used",
            "Actions",
        ])

        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setShowGrid(False)

        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self.setColumnWidth(1, 170)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self.setColumnWidth(4, 110)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.setColumnWidth(5, 120)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self.setColumnWidth(6, 130)

        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                gridline-color: transparent;
            }}
            QTableWidget::item {{
                padding: 8px 10px;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: none;
                border-bottom: 1px solid {COLORS['border']};
                padding: 8px 10px;
                font-size: 11px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self._resumes_by_row: Dict[int, Resume] = {}

    def set_resumes(
        self,
        resumes: List[Resume],
        health_map: Dict[int, Dict[str, Any]],
        usage_map: Dict[int, Dict[str, Any]],
    ):
        """Populates the table rows with resume items."""
        self.setRowCount(len(resumes))
        self._resumes_by_row.clear()

        for row, r in enumerate(resumes):
            self._resumes_by_row[row] = r
            h_info = health_map.get(r.id, {})
            u_info = usage_map.get(r.id, {})

            # 0. Name
            name_item = QTableWidgetItem(r.name)
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 0, name_item)

            # 1. Target Role
            role_text = r.role_target or "General"
            role_item = QTableWidgetItem(role_text)
            role_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 1, role_item)

            # 2. Version
            ver_text = f"v{r.version or '1.0'}"
            ver_item = QTableWidgetItem(ver_text)
            ver_item.setTextAlignment(Qt.AlignCenter)
            ver_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 2, ver_item)

            # 3. Health
            st = h_info.get("health_status", "VALID")
            if st == "VALID":
                h_text = "✓ Valid"
            elif st == "NEEDS_ATTENTION":
                h_text = "⚠ Attention"
            else:
                h_text = "✕ Invalid"
            health_item = QTableWidgetItem(h_text)
            health_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 3, health_item)

            # 4. Applications
            app_cnt = u_info.get("total_applications", 0)
            app_item = QTableWidgetItem(str(app_cnt))
            app_item.setTextAlignment(Qt.AlignCenter)
            app_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 4, app_item)

            # 5. Last Used
            last_used = u_info.get("last_used_at", "Never")
            last_item = QTableWidgetItem(last_used)
            last_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.setItem(row, 5, last_item)

            # 6. Actions widget
            act_widget = QWidget()
            act_widget.setStyleSheet("background: transparent;")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(6, 4, 6, 4)
            act_layout.setSpacing(6)
            act_layout.setAlignment(Qt.AlignCenter)

            btn_prev = QPushButton("Preview")
            btn_prev.setCursor(Qt.PointingHandCursor)
            btn_prev.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_alt']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 3px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                    color: {COLORS['accent']};
                }}
            """)
            r_id = r.id
            btn_prev.clicked.connect(lambda _, rid=r_id: self.action_preview.emit(rid))
            act_layout.addWidget(btn_prev)

            btn_menu = QPushButton("⋮")
            btn_menu.setFixedSize(26, 26)
            btn_menu.setCursor(Qt.PointingHandCursor)
            btn_menu.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['surface_hover']};
                    color: {COLORS['text']};
                }}
            """)
            btn_menu.clicked.connect(lambda _, rid=r_id, b=btn_menu, res=r: self._show_row_menu(rid, b, res))
            act_layout.addWidget(btn_menu)

            self.setCellWidget(row, 6, act_widget)

    def _on_selection_changed(self):
        row = self.currentRow()
        if row in self._resumes_by_row:
            self.resume_selected.emit(self._resumes_by_row[row].id)

    def _show_row_menu(self, resume_id: int, button: QPushButton, resume: Resume):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 18px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        act_preview = menu.addAction("👁  Preview In-App")
        act_preview.triggered.connect(lambda: self.action_preview.emit(resume_id))

        act_os = menu.addAction("↗  Open with System Viewer")
        act_os.triggered.connect(lambda: self.action_open_os.emit(resume_id))

        menu.addSeparator()

        if not resume.is_default and not resume.is_archived:
            act_def = menu.addAction("★  Set as Default")
            act_def.triggered.connect(lambda: self.action_set_default.emit(resume_id))

        act_ver = menu.addAction("🧬  New Version...")
        act_ver.triggered.connect(lambda: self.action_new_version.emit(resume_id))

        act_edit = menu.addAction("✎  Edit Metadata...")
        act_edit.triggered.connect(lambda: self.action_edit.emit(resume_id))

        menu.addSeparator()

        if resume.is_archived:
            act_unarc = menu.addAction("♻  Restore from Archive")
            act_unarc.triggered.connect(lambda: self.action_unarchive.emit(resume_id))
        else:
            act_arc = menu.addAction("📦  Archive Resume")
            act_arc.triggered.connect(lambda: self.action_archive.emit(resume_id))

        act_del = menu.addAction("🗑  Delete Resume")
        act_del.triggered.connect(lambda: self.action_delete.emit(resume_id))

        menu.exec_(button.mapToGlobal(button.rect().bottomLeft()))
