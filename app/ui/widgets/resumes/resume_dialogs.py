"""Modern modal dialogs for resume management workflows.

Includes:
- UploadResumeDialog: File picker, drag-and-drop zone, role assignment, initial version, notes.
- ResumeVersionDialog: Creates a subsequent revision preserving lineage_id.
- ResumeMetadataDialog: Edits name, target role, version, notes, default status.
"""

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Resume
from app.ui.theme import COLORS


class FileDropFrame(QFrame):
    """Drag-and-drop target frame for selecting resume files."""

    file_dropped = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("dropFrame")
        self._apply_style(is_hover=False)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(6)

        self.lbl_icon = QLabel("📁")
        self.lbl_icon.setStyleSheet("font-size: 28px;")
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_icon)

        self.lbl_text = QLabel("Drag & drop resume PDF here, or click to browse")
        self.lbl_text.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {COLORS['text']};")
        self.lbl_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_text)

        self.lbl_sub = QLabel("Supports PDF (recommended) or DOCX up to 15MB")
        self.lbl_sub.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_sub)

    def _apply_style(self, is_hover: bool):
        border_color = COLORS['accent'] if is_hover else COLORS['border']
        border_style = "dashed"
        bg_color = COLORS['surface_hover'] if is_hover else COLORS['surface_alt']
        self.setStyleSheet(f"""
            QFrame#dropFrame {{
                background-color: {bg_color};
                border: 2px {border_style} {border_color};
                border-radius: 8px;
            }}
        """)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._apply_style(is_hover=True)

    def dragLeaveEvent(self, event):
        self._apply_style(is_hover=False)

    def dropEvent(self, event):
        self._apply_style(is_hover=False)
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path:
                self.file_dropped.emit(path)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Resume Document",
                "",
                "Documents (*.pdf *.docx *.doc);;All Files (*.*)",
            )
            if path:
                self.file_dropped.emit(path)
        super().mousePressEvent(event)


class UploadResumeDialog(QDialog):
    """Modal dialog for uploading a new resume document."""

    def __init__(self, available_roles: Optional[List[str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Upload New Resume")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 500;
            }}
            QLineEdit, QComboBox, QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#btnCancel {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton#btnCancel:hover {{
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton#btnSubmit {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#btnSubmit:hover {{
                background-color: {COLORS['primary_hover'] if 'primary_hover' in COLORS else COLORS['accent']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        lbl_head = QLabel("📄 Upload Resume Document")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(lbl_head)

        self.lbl_sub = QLabel("Upload a resume to automatically extract skills, run technical health checks, and use in automation.")
        self.lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        self.lbl_sub.setWordWrap(True)
        layout.addWidget(self.lbl_sub)

        # Drop Zone
        self.drop_zone = FileDropFrame()
        self.drop_zone.file_dropped.connect(self._on_file_selected)
        layout.addWidget(self.drop_zone)

        # Selected File Path Display
        file_row = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setPlaceholderText("No file selected yet...")
        self.txt_file.setReadOnly(True)
        file_row.addWidget(self.txt_file, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self.btn_browse)
        layout.addLayout(file_row)

        # Name & Version Row
        name_row = QHBoxLayout()
        name_box = QVBoxLayout()
        lbl_name = QLabel("DISPLAY NAME *")
        lbl_name.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("e.g. Senior Backend Engineer - Python")
        name_box.addWidget(lbl_name)
        name_box.addWidget(self.txt_name)
        name_row.addLayout(name_box, 3)

        ver_box = QVBoxLayout()
        lbl_ver = QLabel("VERSION")
        lbl_ver.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_version = QLineEdit("1.0")
        self.txt_version.setFixedWidth(80)
        ver_box.addWidget(lbl_ver)
        ver_box.addWidget(self.txt_version)
        name_row.addLayout(ver_box, 1)
        layout.addLayout(name_row)

        # Target Role
        role_box = QVBoxLayout()
        lbl_role = QLabel("TARGET ROLE")
        lbl_role.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.combo_role = QComboBox()
        self.combo_role.setEditable(True)
        self.combo_role.addItem("General")
        if available_roles:
            for r in available_roles:
                if r and r != "General":
                    self.combo_role.addItem(r)
        role_box.addWidget(lbl_role)
        role_box.addWidget(self.combo_role)
        layout.addLayout(role_box)

        # Notes
        notes_box = QVBoxLayout()
        lbl_notes = QLabel("NOTES (OPTIONAL)")
        lbl_notes.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("e.g. Tailored for enterprise fintech roles")
        notes_box.addWidget(lbl_notes)
        notes_box.addWidget(self.txt_notes)
        layout.addLayout(notes_box)

        # Default Checkbox
        self.chk_default = QCheckBox("Set as Default Resume for automation applications")
        self.chk_default.setStyleSheet(f"color: {COLORS['text']}; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.chk_default)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("Upload & Analyze")
        self.btn_submit.setObjectName("btnSubmit")
        self.btn_submit.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(self.btn_submit)

        layout.addLayout(btn_row)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume Document",
            "",
            "Documents (*.pdf *.docx *.doc);;All Files (*.*)",
        )
        if path:
            self._on_file_selected(path)

    def _on_file_selected(self, file_path: str):
        self.txt_file.setText(file_path)
        p = Path(file_path)
        if not self.txt_name.text().strip():
            self.txt_name.setText(p.stem)
        self.lbl_sub.setText("Resume document selected. Click 'Upload & Analyze' to proceed.")
        self.lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['success']};")

    def _validate_and_accept(self):
        file_path = self.txt_file.text().strip()
        if not file_path:
            self._browse_file()
            file_path = self.txt_file.text().strip()
            if not file_path:
                self.lbl_sub.setText("⚠️ Please select a valid resume document file (PDF or DOCX).")
                self.lbl_sub.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['danger']};")
                return

        name = self.txt_name.text().strip()
        if not name:
            self.txt_name.setFocus()
            self.lbl_sub.setText("⚠️ Please enter a display name for this resume.")
            self.lbl_sub.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['danger']};")
            return

        self.accept()

    def get_data(self):
        return {
            "file_path": self.txt_file.text().strip(),
            "name": self.txt_name.text().strip(),
            "version": self.txt_version.text().strip() or "1.0",
            "role_target": self.combo_role.currentText().strip() or "General",
            "notes": self.txt_notes.text().strip() or None,
            "is_default": self.chk_default.isChecked(),
        }


class ResumeVersionDialog(QDialog):
    """Modal dialog for creating a new revision belonging to an existing resume lineage."""

    def __init__(self, source_resume: Resume, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.source_resume = source_resume
        self.setWindowTitle(f"New Version — {source_resume.name}")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 500;
            }}
            QLineEdit, QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#btnCancel {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton#btnSubmit {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        lbl_head = QLabel("🧬 Create New Version")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(lbl_head)

        self.lbl_desc = QLabel(
            f"Upload an updated document for '{source_resume.name}' (current: v{source_resume.version}). "
            "The new version preserves the same lineage family and role targeting."
        )
        self.lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        self.lbl_desc.setWordWrap(True)
        layout.addWidget(self.lbl_desc)

        # Drop zone
        self.drop_zone = FileDropFrame()
        self.drop_zone.file_dropped.connect(self._on_file_selected)
        layout.addWidget(self.drop_zone)

        # File display
        file_row = QHBoxLayout()
        self.txt_file = QLineEdit()
        self.txt_file.setPlaceholderText("Select updated resume file...")
        self.txt_file.setReadOnly(True)
        file_row.addWidget(self.txt_file, 1)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_file)
        file_row.addWidget(self.btn_browse)
        layout.addLayout(file_row)

        # Version & Notes
        ver_row = QHBoxLayout()
        ver_box = QVBoxLayout()
        lbl_ver = QLabel("NEW VERSION STRING *")
        lbl_ver.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")

        # Auto-increment suggestion
        curr_v = source_resume.version or "1.0"
        try:
            parts = curr_v.split(".")
            suggested = f"{parts[0]}.{int(parts[1]) + 1}"
        except Exception:
            suggested = "2.0"

        self.txt_version = QLineEdit(suggested)
        self.txt_version.setFixedWidth(100)
        ver_box.addWidget(lbl_ver)
        ver_box.addWidget(self.txt_version)
        ver_row.addLayout(ver_box)

        notes_box = QVBoxLayout()
        lbl_notes = QLabel("CHANGE NOTES")
        lbl_notes.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_notes = QLineEdit()
        self.txt_notes.setPlaceholderText("e.g. Added Q3 projects and Kubernetes experience")
        notes_box.addWidget(lbl_notes)
        notes_box.addWidget(self.txt_notes)
        ver_row.addLayout(notes_box, 1)

        layout.addLayout(ver_row)

        # Default Checkbox
        self.chk_default = QCheckBox("Promote this new version to Default Resume immediately")
        self.chk_default.setChecked(source_resume.is_default)
        self.chk_default.setStyleSheet(f"color: {COLORS['text']}; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.chk_default)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("Save New Version")
        self.btn_submit.setObjectName("btnSubmit")
        self.btn_submit.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(self.btn_submit)

        layout.addLayout(btn_row)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Updated Resume",
            "",
            "Documents (*.pdf *.docx *.doc);;All Files (*.*)",
        )
        if path:
            self._on_file_selected(path)

    def _on_file_selected(self, file_path: str):
        self.txt_file.setText(file_path)
        self.lbl_desc.setText(f"File selected: {Path(file_path).name}. Ready to save revision.")
        self.lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS['success']};")

    def _validate_and_accept(self):
        file_path = self.txt_file.text().strip()
        if not file_path:
            self._browse_file()
            file_path = self.txt_file.text().strip()
            if not file_path:
                self.lbl_desc.setText("⚠️ Please select an updated resume file (PDF or DOCX).")
                self.lbl_desc.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['danger']};")
                return

        version = self.txt_version.text().strip()
        if not version:
            self.txt_version.setFocus()
            self.lbl_desc.setText("⚠️ Please enter a new version number (e.g. 1.1 or 2.0).")
            self.lbl_desc.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['danger']};")
            return

        self.accept()

    def get_data(self):
        return {
            "file_path": self.txt_file.text().strip(),
            "version": self.txt_version.text().strip(),
            "notes": self.txt_notes.text().strip() or None,
            "is_default": self.chk_default.isChecked(),
        }


class ResumeMetadataDialog(QDialog):
    """Modal dialog for updating resume display name, target role, version, and notes."""

    def __init__(self, resume: Resume, available_roles: Optional[List[str]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.resume = resume
        self.setWindowTitle(f"Edit Resume — {resume.name}")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 500;
            }}
            QLineEdit, QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QPushButton {{
                border-radius: 6px;
                padding: 7px 16px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton#btnCancel {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton#btnSubmit {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_head = QLabel("✎ Edit Resume Details")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        layout.addWidget(lbl_head)

        # Name
        box_name = QVBoxLayout()
        lbl_n = QLabel("DISPLAY NAME *")
        lbl_n.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_name = QLineEdit(resume.name)
        box_name.addWidget(lbl_n)
        box_name.addWidget(self.txt_name)
        layout.addLayout(box_name)

        # Target Role
        box_role = QVBoxLayout()
        lbl_r = QLabel("TARGET ROLE")
        lbl_r.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.combo_role = QComboBox()
        self.combo_role.setEditable(True)
        self.combo_role.addItem("General")
        if available_roles:
            for r in available_roles:
                if r and r != "General":
                    self.combo_role.addItem(r)
        self.combo_role.setCurrentText(resume.role_target or "General")
        box_role.addWidget(lbl_r)
        box_role.addWidget(self.combo_role)
        layout.addLayout(box_role)

        # Version & Default
        ver_row = QHBoxLayout()
        box_v = QVBoxLayout()
        lbl_v = QLabel("VERSION")
        lbl_v.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_version = QLineEdit(resume.version or "1.0")
        self.txt_version.setFixedWidth(100)
        box_v.addWidget(lbl_v)
        box_v.addWidget(self.txt_version)
        ver_row.addLayout(box_v)

        box_notes = QVBoxLayout()
        lbl_not = QLabel("NOTES")
        lbl_not.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']};")
        self.txt_notes = QLineEdit(resume.notes or "")
        box_notes.addWidget(lbl_not)
        box_notes.addWidget(self.txt_notes)
        ver_row.addLayout(box_notes, 1)

        layout.addLayout(ver_row)

        if not resume.is_archived:
            self.chk_default = QCheckBox("Designate as Default Resume")
            self.chk_default.setChecked(resume.is_default)
            self.chk_default.setStyleSheet(f"color: {COLORS['text']}; font-weight: 600; font-size: 12px;")
            layout.addWidget(self.chk_default)
        else:
            self.chk_default = None

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)

        self.btn_submit = QPushButton("Save Changes")
        self.btn_submit.setObjectName("btnSubmit")
        self.btn_submit.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(self.btn_submit)

        layout.addLayout(btn_row)

    def _validate_and_accept(self):
        if not self.txt_name.text().strip():
            self.txt_name.setFocus()
            return
        self.accept()

    def get_data(self):
        return {
            "name": self.txt_name.text().strip(),
            "role_target": self.combo_role.currentText().strip() or None,
            "version": self.txt_version.text().strip() or "1.0",
            "notes": self.txt_notes.text().strip() or None,
            "is_default": self.chk_default.isChecked() if self.chk_default else self.resume.is_default,
        }
