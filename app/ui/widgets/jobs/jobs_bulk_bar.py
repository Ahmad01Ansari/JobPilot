"""Floating / dockable bulk action bar for selected jobs."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from app.ui.theme import COLORS


class JobsBulkBar(QFrame):
    """ATS bulk actions bar shown when multiple jobs are selected via checkboxes."""

    add_pipeline_clicked = Signal()
    qualify_selected_clicked = Signal()
    mark_skipped_clicked = Signal()
    mark_junk_clicked = Signal()
    restore_junk_clicked = Signal()
    open_urls_clicked = Signal()
    clear_selection_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._count = 0
        self._is_junk_mode = False
        self._setup_ui()
        self.setVisible(False)

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_elevated']};
                border: 1px solid {COLORS['accent']};
                border-radius: 8px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        # Counter Label
        self.lbl_count = QLabel("0 selected")
        self.lbl_count.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        layout.addWidget(self.lbl_count)

        layout.addStretch()

        # Action: Add to Pipeline
        self.btn_pipeline = QPushButton("+ Add to Pipeline")
        self.btn_pipeline.setCursor(Qt.PointingHandCursor)
        self.btn_pipeline.setToolTip("Create application records for all selected jobs")
        self.btn_pipeline.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_pipeline.clicked.connect(self.add_pipeline_clicked.emit)
        layout.addWidget(self.btn_pipeline)

        # Action: Qualify Fit
        self.btn_qualify = QPushButton("⚡ Qualify Fit")
        self.btn_qualify.setCursor(Qt.PointingHandCursor)
        self.btn_qualify.setToolTip("Evaluate qualification match for all selected jobs against your candidate profile")
        self.btn_qualify.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_qualify.clicked.connect(self.qualify_selected_clicked.emit)
        layout.addWidget(self.btn_qualify)

        # Action: Mark Skipped
        self.btn_skip = QPushButton("Mark Skipped")
        self.btn_skip.setCursor(Qt.PointingHandCursor)
        self.btn_skip.setToolTip("Track selected jobs as SKIPPED in pipeline")
        self.btn_skip.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_skip.clicked.connect(self.mark_skipped_clicked.emit)
        layout.addWidget(self.btn_skip)

        # Action: Mark Junk
        self.btn_junk = QPushButton("🗑 Mark Junk")
        self.btn_junk.setCursor(Qt.PointingHandCursor)
        self.btn_junk.setToolTip("Move selected jobs to Junk repository")
        self.btn_junk.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: #EF4444;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #450A0A;
                color: #F87171;
            }}
        """)
        self.btn_junk.clicked.connect(self.mark_junk_clicked.emit)
        layout.addWidget(self.btn_junk)

        # Action: Restore from Junk
        self.btn_restore = QPushButton("↩ Restore to Active")
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.setToolTip("Restore selected jobs from Junk back to active jobs repository")
        self.btn_restore.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_restore.clicked.connect(self.restore_junk_clicked.emit)
        self.btn_restore.setVisible(False)
        layout.addWidget(self.btn_restore)

        # Action: Open URLs
        self.btn_urls = QPushButton("Open URLs ↗")
        self.btn_urls.setCursor(Qt.PointingHandCursor)
        self.btn_urls.setToolTip("Open listing URLs in external browser")
        self.btn_urls.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_urls.clicked.connect(self.open_urls_clicked.emit)
        layout.addWidget(self.btn_urls)

        # Clear Selection
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 11px;
                font-weight: 600;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                color: {COLORS['danger']};
            }}
        """)
        self.btn_clear.clicked.connect(self.clear_selection_clicked.emit)
        layout.addWidget(self.btn_clear)

    def set_mode(self, is_junk_mode: bool = False) -> None:
        """Configures buttons based on whether the view is displaying Junk items."""
        self._is_junk_mode = is_junk_mode
        self.btn_pipeline.setVisible(not is_junk_mode)
        self.btn_skip.setVisible(not is_junk_mode)
        self.btn_junk.setVisible(not is_junk_mode)
        self.btn_restore.setVisible(is_junk_mode)

    def set_selected_count(self, count: int) -> None:
        """Updates the visible count and visibility of the bar."""
        self._count = count
        if count <= 0:
            self.setVisible(False)
            return

        self.setVisible(True)
        self.lbl_count.setText(f"{count} {'job' if count == 1 else 'jobs'} selected")
