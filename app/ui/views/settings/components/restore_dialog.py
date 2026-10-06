"""Safe restore confirmation modal dialog with pre-restore safety snapshot warning."""

from pathlib import Path
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.ui.theme import COLORS


class RestoreDialog(QDialog):
    """Explicit confirmation modal for restoring system database and profile from a backup archive."""

    def __init__(
        self,
        archive_path: str,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.archive_path = Path(archive_path)
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Restore System Data Confirmation")
        self.setFixedWidth(500)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 8px;
            }}
            QLabel {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(16)

        # Danger Header
        lbl_title = QLabel("⚠️ Restore JobPilot System Data")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('warning', '#D29922')};")
        layout.addWidget(lbl_title)

        # Body Warning
        lbl_warning = QLabel(
            "Restoring will replace the active SQLite database, candidate profile configuration, "
            "and resume files with contents from the selected archive."
        )
        lbl_warning.setWordWrap(True)
        lbl_warning.setStyleSheet(f"font-size: 13px; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_warning)

        # Safety Notice Box
        safety_box = QWidget()
        safety_box.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-left: 3px solid {COLORS.get('info', '#388BFD')};
                border-radius: 6px;
                padding: 10px 12px;
            }}
        """)
        s_layout = QVBoxLayout(safety_box)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(4)

        lbl_s_title = QLabel("🛡️ Automatic Safety Snapshot")
        lbl_s_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #388BFD;")
        s_layout.addWidget(lbl_s_title)

        lbl_s_desc = QLabel("A pre-restore safety copy (.db.pre_restore.bak) will be created automatically before any files are modified.")
        lbl_s_desc.setWordWrap(True)
        lbl_s_desc.setStyleSheet(f"font-size: 11px; color: {COLORS.get('text_muted', '#8B949E')};")
        s_layout.addWidget(lbl_s_desc)
        layout.addWidget(safety_box)

        # Selected Archive Info
        lbl_file = QLabel(f"<b>Selected Archive:</b> {self.archive_path.name}")
        lbl_file.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_file)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("Confirm & Restore")
        btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('danger', '#F85149')};
                border: none;
                color: #FFFFFF;
                padding: 8px 18px;
                border-radius: 6px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #CF222E;
            }}
        """)
        btn_confirm.clicked.connect(self.accept)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)
