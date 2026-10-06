"""
Step 3: Resume Ingestion & Storage.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Ingests resume file, displays real file metadata, and prepares for staged extraction.
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QFileDialog
)
from app.ui.theme import COLORS


class StepResumeWidget(QWidget):
    """Step 3: Resume Ingestion widget displaying filename, size, and readiness status."""
    resume_selected = Signal(str)  # file_path

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self._selected_path: Optional[str] = None
        self.setAcceptDrops(True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Header
        lbl_badge = QLabel("STEP 3: CANDIDATE RESUME SOURCE")
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 3px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("Import Your Primary Resume")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        lbl_sub = QLabel(
            "Your resume is the foundational source for your candidate profile. "
            "JobPilot parses experience, contact details, and technical skills for verified screening answers."
        )
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(lbl_sub)

        # Drag & Drop Zone
        self.drop_frame = QFrame()
        self.drop_frame.setMinimumHeight(160)
        self.drop_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 2px dashed {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)
        d_layout = QVBoxLayout(self.drop_frame)
        d_layout.setAlignment(Qt.AlignCenter)
        d_layout.setSpacing(8)

        self.lbl_icon = QLabel("📄")
        self.lbl_icon.setStyleSheet("font-size: 32px;")
        d_layout.addWidget(self.lbl_icon, alignment=Qt.AlignCenter)

        self.lbl_prompt = QLabel("Drag & drop your resume here, or click Browse")
        self.lbl_prompt.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
        d_layout.addWidget(self.lbl_prompt, alignment=Qt.AlignCenter)

        self.btn_browse = QPushButton("Choose Resume (PDF / DOCX)")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 7px 16px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
        """)
        self.btn_browse.clicked.connect(self._on_browse_file)
        d_layout.addWidget(self.btn_browse, alignment=Qt.AlignCenter)

        self.lbl_formats = QLabel("Supported formats: PDF, DOCX, DOC (Up to 15 MB)")
        self.lbl_formats.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        d_layout.addWidget(self.lbl_formats, alignment=Qt.AlignCenter)

        layout.addWidget(self.drop_frame)

        # Selected Resume Details Card (Initially hidden)
        self.details_card = QFrame()
        self.details_card.setVisible(False)
        self.details_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['primary']};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        c_layout = QHBoxLayout(self.details_card)
        c_layout.setSpacing(12)

        icon_lbl = QLabel("📄")
        icon_lbl.setStyleSheet("font-size: 24px;")
        c_layout.addWidget(icon_lbl)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.lbl_file_name = QLabel("Resume.pdf")
        self.lbl_file_name.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_file_meta = QLabel("245 KB · Ready for AI extraction")
        self.lbl_file_meta.setStyleSheet(f"font-size: 11px; color: {COLORS['success']};")
        info_layout.addWidget(self.lbl_file_name)
        info_layout.addWidget(self.lbl_file_meta)
        c_layout.addLayout(info_layout)
        c_layout.addStretch()

        self.btn_replace = QPushButton("Replace")
        self.btn_replace.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                font-size: 11px;
                border: 1px solid {COLORS['border_light']};
                border-radius: 4px;
                padding: 4px 10px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_replace.clicked.connect(self._on_browse_file)
        c_layout.addWidget(self.btn_replace)

        layout.addWidget(self.details_card)

        # Status text
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 11px; font-weight: 600;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    # Drag & Drop Handlers

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.drop_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {COLORS['surface_alt']};
                    border: 2px dashed {COLORS['primary']};
                    border-radius: 10px;
                }}
            """)

    def dragLeaveEvent(self, event):
        self.drop_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 2px dashed {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)

    def dropEvent(self, event):
        self.drop_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 2px dashed {COLORS['border_light']};
                border-radius: 10px;
            }}
        """)
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            self._handle_file(file_path)

    def _on_browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Resume Document",
            "",
            "Resume Files (*.pdf *.docx *.doc);;All Files (*)"
        )
        if file_path:
            self._handle_file(file_path)

    def _handle_file(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return
        if path.suffix.lower() not in {".pdf", ".docx", ".doc"}:
            self.lbl_status.setText(f"❌ Unsupported format: {path.suffix}. Please upload PDF or Word DOCX.")
            self.lbl_status.setStyleSheet(f"color: {COLORS['danger']};")
            return

        # Register in ResumeService
        ok, err, record = self.setup_service.save_resume_upload(file_path)
        if not ok:
            self.lbl_status.setText(f"❌ Upload failed: {err}")
            self.lbl_status.setStyleSheet(f"color: {COLORS['danger']};")
            return

        self._selected_path = file_path
        size_kb = round(path.stat().st_size / 1024, 1)

        self.lbl_file_name.setText(path.name)
        self.lbl_file_meta.setText(f"{size_kb} KB · Ingested & Ready for AI Extraction ✓")
        self.details_card.setVisible(True)
        self.drop_frame.setVisible(False)
        self.lbl_status.setText("✓ Resume saved to managed library. Click Continue to start extraction.")
        self.lbl_status.setStyleSheet(f"color: {COLORS['success']};")

        self.resume_selected.emit(file_path)

    def get_selected_resume_path(self) -> Optional[str]:
        return self._selected_path
