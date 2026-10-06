"""Job Picker Modal — ATS-style modal for selecting or creating tracked jobs.

Features:
  - Searchable list of tracked jobs from JobService / JobRepository
  - 10 jobs per page with pagination controls (Previous / Next / Page Indicator)
  - Inline "Create New Job" form to save new opportunities directly to JobRepository
  - Emits job_selected with the chosen Job record
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Job
from app.repositories.dto import JobCreateDTO
from app.services.job_service import JobFilter, JobService
from app.ui.theme import COLORS
from app.ui.views.outreach.modern_popup import ModernPopup

logger = logging.getLogger("JobPilot.Outreach.JobPickerModal")

PAGE_SIZE = 10


class JobPickerModal(QDialog):
    """Modal dialog for picking a tracked job with pagination, search, and new job creation."""

    job_selected = Signal(object)  # Emits chosen Job instance or dict

    def __init__(self, job_service: Optional[JobService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.job_service = job_service or JobService()

        self._current_page = 1
        self._total_jobs = 0
        self._total_pages = 1
        self._jobs_page: List[Job] = []

        self.setWindowTitle("Select Tracked Job Opportunity")
        self.setFixedSize(820, 580)
        self.setModal(True)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._do_search)

        self._setup_ui()
        self._load_page()

    def _setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QLineEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
            QTableWidget {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                gridline-color: {COLORS['border']};
                selection-background-color: {COLORS['surface_hover']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: none;
                border-bottom: 1px solid {COLORS['border']};
                padding: 6px 8px;
                font-weight: 700;
                font-size: 11px;
                text-transform: uppercase;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header Title + Subtitle
        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        lbl_title = QLabel("Select Tracked Opportunity")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: 700; color: #F0F6FC;")
        lbl_sub = QLabel("Select a saved job from your repository (10 per page) or create a new tracked job.")
        lbl_sub.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")

        title_box.addWidget(lbl_title)
        title_box.addWidget(lbl_sub)
        header_row.addLayout(title_box)
        header_row.addStretch()

        self.btn_toggle_create = QPushButton("+ Create New Job")
        self.btn_toggle_create.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_create.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary']};
                border: 1px solid {COLORS['primary']}60;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary']};
                color: white;
            }}
        """)
        self.btn_toggle_create.clicked.connect(self._toggle_create_form)
        header_row.addWidget(self.btn_toggle_create)

        layout.addLayout(header_row)

        # Inline "Create New Job" form (hidden by default)
        self.create_box = QFrame()
        self.create_box.setVisible(False)
        self.create_box.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        create_layout = QVBoxLayout(self.create_box)
        create_layout.setContentsMargins(10, 8, 10, 8)
        create_layout.setSpacing(8)

        lbl_create_head = QLabel("Create & Save New Job to Repository:")
        lbl_create_head.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['primary']};")
        create_layout.addWidget(lbl_create_head)

        row_fields = QHBoxLayout()
        row_fields.setSpacing(8)

        self.txt_new_company = QLineEdit()
        self.txt_new_company.setPlaceholderText("Target Company * (e.g. Acme Corp)")
        row_fields.addWidget(self.txt_new_company, 1)

        self.txt_new_title = QLineEdit()
        self.txt_new_title.setPlaceholderText("Position Title * (e.g. RPA Developer)")
        row_fields.addWidget(self.txt_new_title, 1)

        self.txt_new_url = QLineEdit()
        self.txt_new_url.setPlaceholderText("Job URL (optional)")
        row_fields.addWidget(self.txt_new_url, 1)

        btn_save_job = QPushButton("Save & Link Job")
        btn_save_job.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save_job.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save_job.clicked.connect(self._on_save_new_job)
        row_fields.addWidget(btn_save_job)

        create_layout.addLayout(row_fields)
        layout.addWidget(self.create_box)

        # Search Bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search by position title, company name, or platform...")
        self.txt_search.textChanged.connect(self._on_search_text_changed)
        search_row.addWidget(self.txt_search, 1)

        btn_clear = QPushButton("Clear")
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_clear.clicked.connect(lambda: self.txt_search.clear())
        search_row.addWidget(btn_clear)

        layout.addLayout(search_row)

        # Jobs Table (Shows 10 jobs per page)
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Position Title", "Company", "Platform", "Location", "Action"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 95)

        layout.addWidget(self.table, 1)

        # Pagination & Footer Action Bar
        footer = QHBoxLayout()
        footer.setSpacing(12)

        self.btn_prev = QPushButton("◀ Previous")
        self.btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_prev.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 5px 12px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_dark']};
                border-color: {COLORS['border_subtle']};
            }}
        """)
        self.btn_prev.clicked.connect(self._on_prev_page)
        footer.addWidget(self.btn_prev)

        self.lbl_page_info = QLabel("Page 1 of 1 (0 jobs)")
        self.lbl_page_info.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; font-weight: 500;")
        footer.addWidget(self.lbl_page_info)

        self.btn_next = QPushButton("Next ▶")
        self.btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_next.setStyleSheet(self.btn_prev.styleSheet())
        self.btn_next.clicked.connect(self._on_next_page)
        footer.addWidget(self.btn_next)

        footer.addStretch(1)

        btn_close = QPushButton("Cancel")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        btn_close.clicked.connect(self.reject)
        footer.addWidget(btn_close)

        layout.addLayout(footer)

    def _toggle_create_form(self):
        new_vis = not self.create_box.isVisible()
        self.create_box.setVisible(new_vis)
        self.btn_toggle_create.setText("▲ Close Form" if new_vis else "+ Create New Job")
        if new_vis:
            self.txt_new_company.setFocus()

    def _on_save_new_job(self):
        comp = self.txt_new_company.text().strip()
        title = self.txt_new_title.text().strip()
        url = self.txt_new_url.text().strip()

        if not comp or not title:
            ModernPopup.warning(self, "Required Fields", "Please enter both Company Name and Position Title.")
            return

        dto = JobCreateDTO(
            platform="email",
            company_raw=comp,
            title=title,
            source_url=url or f"email://{comp.lower().replace(' ', '')}",
            application_method="EMAIL",
            apply_type="DIRECT",
        )
        try:
            job, _ = self.job_service.upsert_job(dto)
            self._select_job(job)
        except Exception as e:
            logger.exception("Failed to save new job")
            ModernPopup.error(self, "Save Error", f"Failed to save job to repository:\n\n{e}")

    def _on_search_text_changed(self):
        self._search_timer.start()

    def _do_search(self):
        self._current_page = 1
        self._load_page()

    def _on_prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_page()

    def _on_next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_page()

    def _load_page(self):
        search_query = self.txt_search.text().strip() or None
        f = JobFilter(search=search_query)

        try:
            self._total_jobs = self.job_service.count_jobs(filters=f)
            self._total_pages = max(1, (self._total_jobs + PAGE_SIZE - 1) // PAGE_SIZE)
            if self._current_page > self._total_pages:
                self._current_page = self._total_pages

            offset = (self._current_page - 1) * PAGE_SIZE
            self._jobs_page = self.job_service.list_jobs(
                filters=f,
                limit=PAGE_SIZE,
                offset=offset,
                sort_by="created_at",
                sort_order="desc",
            )
        except Exception as e:
            logger.exception("Failed to query jobs")
            self._total_jobs = 0
            self._total_pages = 1
            self._jobs_page = []

        self._render_table()

    def _render_table(self):
        self.table.setRowCount(len(self._jobs_page))
        for row, job in enumerate(self._jobs_page):
            # Title
            t_item = QTableWidgetItem(job.title or "Untitled")
            t_item.setFlags(t_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, t_item)

            # Company
            comp_name = job.company_raw
            if not comp_name:
                try:
                    comp_name = job.company.name if job.company else None
                except Exception:
                    comp_name = None
            comp_name = comp_name or "Unknown"
            c_item = QTableWidgetItem(comp_name)
            c_item.setFlags(c_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, c_item)

            # Platform
            plat = (job.platform or "direct").capitalize()
            p_item = QTableWidgetItem(plat)
            p_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            p_item.setFlags(p_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, p_item)

            # Location
            loc = job.location or "—"
            l_item = QTableWidgetItem(loc)
            l_item.setFlags(l_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, l_item)

            # Action button
            btn_select = QPushButton("Select ✓")
            btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_select.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface_hover']};
                    color: {COLORS['primary']};
                    border: 1px solid {COLORS['primary']}50;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS['primary']};
                    color: white;
                }}
            """)
            btn_select.clicked.connect(lambda _, j=job: self._select_job(j))
            self.table.setCellWidget(row, 4, btn_select)

        # Update pagination indicators
        self.btn_prev.setEnabled(self._current_page > 1)
        self.btn_next.setEnabled(self._current_page < self._total_pages)
        self.lbl_page_info.setText(
            f"Page {self._current_page} of {self._total_pages} ({self._total_jobs} total jobs)"
        )

    def _select_job(self, job: Job):
        comp_name = job.company_raw
        if not comp_name:
            try:
                comp_name = job.company.name if job.company else None
            except Exception:
                comp_name = None
        comp_name = comp_name or ""
        job_data = {
            "id": job.id,
            "title": job.title or "",
            "company_name": comp_name,
            "source_url": job.source_url or "",
        }
        self.job_selected.emit(job_data)
        self.accept()
