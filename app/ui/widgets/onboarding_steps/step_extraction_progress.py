"""
Step 4: Staged AI Resume Extraction Progress.
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Shows actual completed stages (Reading -> Personal -> Experience -> Skills -> Education) via background QThread.
"""

from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame, QPushButton
)
from app.ui.theme import COLORS


class ExtractionWorker(QThread):
    """Background worker executing staged extraction without blocking the Qt main thread."""
    stage_updated = Signal(str, int)  # message, stage_number
    finished = Signal(bool, str, dict)  # success, error, extracted_data

    def __init__(self, setup_service, file_path: str, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self.file_path = file_path

    def run(self):
        try:
            def cb(msg, pct):
                self.stage_updated.emit(msg, pct)

            ok, err, data = self.setup_service.extract_resume_staged(
                file_path=self.file_path,
                progress_callback=cb
            )
            self.finished.emit(ok, err or "", data)
        except Exception as exc:
            self.finished.emit(False, str(exc), {})


class StageItem(QFrame):
    """Individual stage progress row."""
    def __init__(self, stage_num: int, label_text: str, parent=None):
        super().__init__(parent)
        self.stage_num = stage_num
        self.label_text = label_text
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("QFrame { background: transparent; border: none; }")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(10)

        self.lbl_icon = QLabel("○")
        self.lbl_icon.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLORS['border_light']};")
        layout.addWidget(self.lbl_icon)

        self.lbl_text = QLabel(self.label_text)
        self.lbl_text.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.lbl_text)
        layout.addStretch()

    def set_pending(self):
        self.lbl_icon.setText("○")
        self.lbl_icon.setStyleSheet(f"font-size: 13px; color: {COLORS['border_light']};")
        self.lbl_text.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")

    def set_running(self):
        self.lbl_icon.setText("●")
        self.lbl_icon.setStyleSheet(f"font-size: 13px; color: {COLORS['primary']};")
        self.lbl_text.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")

    def set_complete(self):
        self.lbl_icon.setText("✓")
        self.lbl_icon.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {COLORS['success']};")
        self.lbl_text.setStyleSheet(f"font-size: 12px; color: {COLORS['text']};")


class StepExtractionProgressWidget(QWidget):
    """Step 4: Visual staged progress during AI document extraction."""
    extraction_completed = Signal(dict)

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self._worker: Optional[ExtractionWorker] = None
        self._extracted_data: Dict[str, Any] = {}
        self.stages: list[StageItem] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(16)

        # Header
        lbl_badge = QLabel("STEP 4: STRUCTURED CANDIDATE EXTRACTION")
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

        lbl_title = QLabel("Extracting Candidate Profile")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        self.lbl_sub = QLabel(
            "Analyzing document sections. The extracted values will be presented for your review and verification in the next step."
        )
        self.lbl_sub.setWordWrap(True)
        self.lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.lbl_sub)

        # Staged Progress Frame
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(10)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {COLORS['surface_alt']};
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['primary']};
                border-radius: 4px;
            }}
        """)
        c_layout.addWidget(self.progress_bar)

        # Actual Stages
        stage_labels = [
            "Reading resume document text",
            "Extracting personal identity & contact information",
            "Extracting professional roles & work experience",
            "Extracting technical skills & competencies",
            "Extracting education & summary background",
            "Finalizing structured profile schema",
        ]

        for idx, text in enumerate(stage_labels):
            item = StageItem(idx + 1, text, card)
            self.stages.append(item)
            c_layout.addWidget(item)

        layout.addWidget(card)

        # Completion Status
        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 12px; font-weight: 700;")
        layout.addWidget(self.lbl_status)

        layout.addStretch()

    def start_extraction(self, file_path: str):
        """Starts asynchronous background extraction."""
        self.progress_bar.setValue(10)
        self.stages[0].set_running()
        for s in self.stages[1:]:
            s.set_pending()

        self.lbl_status.setText("⏳ Ingesting document...")
        self.lbl_status.setStyleSheet(f"color: {COLORS['info']};")

        self._worker = ExtractionWorker(
            setup_service=self.setup_service,
            file_path=file_path,
            parent=self
        )
        self._worker.stage_updated.connect(self._on_stage_update)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_stage_update(self, message: str, pct: int):
        self.progress_bar.setValue(pct)
        if pct >= 15:
            self.stages[0].set_complete()
            self.stages[1].set_running()
        if pct >= 30:
            self.stages[1].set_complete()
            self.stages[2].set_running()
        if pct >= 50:
            self.stages[2].set_complete()
            self.stages[3].set_running()
        if pct >= 70:
            self.stages[3].set_complete()
            self.stages[4].set_running()
        if pct >= 85:
            self.stages[4].set_complete()
            self.stages[5].set_running()
        if pct >= 100:
            self.stages[5].set_complete()

    def _on_finished(self, success: bool, err_msg: str, data: dict):
        self.progress_bar.setValue(100)
        for s in self.stages:
            s.set_complete()

        self._extracted_data = data
        if success and data:
            self.lbl_status.setText(f"✓ Extraction complete! Extracted {len(data)} fields. Click Continue to review.")
            self.lbl_status.setStyleSheet(f"color: {COLORS['success']};")
        else:
            self.lbl_status.setText(f"⚠ Document parsed. You can review and fill your profile in the next step.")
            self.lbl_status.setStyleSheet(f"color: {COLORS['warning']};")

        self.extraction_completed.emit(data)

    def get_extracted_data(self) -> Dict[str, Any]:
        return self._extracted_data
