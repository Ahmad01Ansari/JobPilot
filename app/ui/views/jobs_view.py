"""Jobs listing and discovery management view component.

Provides full searching, filtering, inspecting job details, direct URL launching,
status observation, manual job entry modal dialog, CSV export, bulk operations, and ATS-style workspace.
"""

import csv
from typing import Any, List, Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Job
from app.services.application_service import ApplicationService
from app.services.job_service import JobFilter, JobService
from app.ui.theme import COLORS, ThemeManager
from app.ui.widgets.jobs import (
    JobDetailsDialog,
    JobDescriptionDialog,
    JobsBulkBar,
    JobsCategoryTabs,
    JobsDetailPanel,
    JobsEmptyState,
    JobsErrorState,
    JobsLoadingState,
    JobsPagination,
    JobsTable,
    JobsToolbar,
)
from app.services.search.search_result import NavigationAction, NavigationRequest, ViewStateSnapshot
from app.ui.widgets.exact_filter_chip import ExactFilterChip
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader


class AddManualJobDialog(QDialog):
    """Modal dialog for creating a manual, referral, or email job listing."""

    def __init__(self, service: JobService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Add Manual / Referral Job")
        self.setMinimumWidth(500)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: 500;
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setSpacing(12)

        self.txt_title = QLineEdit()
        self.txt_title.setPlaceholderText("e.g. Senior Automation Engineer")
        form.addRow("Job Title *", self.txt_title)

        self.txt_company = QLineEdit()
        self.txt_company.setPlaceholderText("e.g. Acme Innovations")
        form.addRow("Company *", self.txt_company)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["manual", "referral", "email", "linkedin", "naukri", "indeed", "foundit", "glassdoor"])
        form.addRow("Source / Channel", self.cmb_platform)

        self.txt_location = QLineEdit()
        self.txt_location.setPlaceholderText("e.g. Bengaluru, India or Remote")
        form.addRow("Location", self.txt_location)

        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("e.g. https://company.com/careers/job-123")
        form.addRow("Job / Application URL", self.txt_url)

        self.txt_salary = QLineEdit()
        self.txt_salary.setPlaceholderText("e.g. 15-20 LPA")
        form.addRow("Salary / CTC", self.txt_salary)

        self.txt_experience = QLineEdit()
        self.txt_experience.setPlaceholderText("e.g. 3-5 Years")
        form.addRow("Experience Required", self.txt_experience)

        self.txt_desc = QTextEdit()
        self.txt_desc.setPlaceholderText("Paste job description or notes here...")
        self.txt_desc.setMaximumHeight(90)
        form.addRow("Description / Notes", self.txt_desc)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_save(self) -> None:
        title = self.txt_title.text().strip()
        company = self.txt_company.text().strip()

        if not title:
            QMessageBox.warning(self, "Validation Error", "Job title is required.")
            return
        if not company:
            QMessageBox.warning(self, "Validation Error", "Company name is required.")
            return

        job, err = self.service.create_manual_job(
            title=title,
            company=company,
            platform=self.cmb_platform.currentText(),
            location=self.txt_location.text().strip() or None,
            source_url=self.txt_url.text().strip() or None,
            salary_text=self.txt_salary.text().strip() or None,
            experience_text=self.txt_experience.text().strip() or None,
            description=self.txt_desc.toPlainText().strip() or None,
        )

        if job:
            self.accept()
        else:
            QMessageBox.warning(self, "Error Adding Job", f"Failed: {err}")


class JobsView(QWidget):
    """Discovered and qualified job postings ATS workspace view."""

    data_updated = Signal(str)
    apply_universal_requested = Signal(object)      # Job

    def __init__(
        self,
        job_service: Optional[JobService] = None,
        app_service: Optional[ApplicationService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.job_service = job_service or JobService()
        self.service = self.job_service  # Alias for backward compatibility
        self.app_service = app_service or ApplicationService()

        self._current_jobs: List[Job] = []
        self._current_method_filter: Optional[str] = None
        self._is_junk_tab: bool = False
        self._current_page = 1
        self._page_size = 50
        self._sort_by = "first_seen_at"
        self._sort_order = "desc"
        self._qualification_workers: List[Any] = []
        self._exact_job_id: Optional[int] = None
        self._pending_navigation_request: Optional[NavigationRequest] = None
        self._state_snapshot: Optional[ViewStateSnapshot] = None

        self._setup_ui()
        ThemeManager.add_listener(self._on_theme_changed)
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        # 1. Header with Title, Actions (Add Manual, Refresh, Export)
        self.header = PageHeader(
            title="Jobs Repository",
            subtitle="Browse, filter, and manage opportunities across all job sources.",
        )

        self.btn_export = QPushButton("Export CSV")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_export.clicked.connect(self._on_export_clicked)

        self.btn_add_manual = QPushButton("+ Add Manual Job")
        self.btn_add_manual.setCursor(Qt.PointingHandCursor)
        self.btn_add_manual.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 600;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_add_manual.clicked.connect(self._on_add_manual_clicked)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 12px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)

        self.header.add_action_widget(self.btn_export)
        self.header.add_action_widget(self.btn_add_manual)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # 2. Notification Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Category Navigation Tabs: [All Jobs] [Easy Apply] [Company Portal]
        self.category_tabs = JobsCategoryTabs(self)
        self.category_tabs.tab_changed.connect(self._on_category_tab_changed)
        main_layout.addWidget(self.category_tabs)

        # Backwards-compatible tab button references
        self.btn_tab_all = self.category_tabs.btn_all
        self.btn_tab_easy = self.category_tabs.btn_easy
        self.btn_tab_portal = self.category_tabs.btn_portal
        self.btn_tab_junk = self.category_tabs.btn_junk

        # 4. Multi-Attribute Filter Toolbar & Active Chips
        self.toolbar = JobsToolbar(self)
        self.toolbar.filters_changed.connect(self.refresh)
        self.toolbar.column_visibility_changed.connect(self._on_column_visibility_changed)
        self.toolbar.density_changed.connect(self._on_density_changed)
        self.toolbar.clear_all_requested.connect(self._on_toolbar_clear_all)
        self.toolbar.calculate_all_requested.connect(self._on_calculate_all_requested)
        main_layout.addWidget(self.toolbar)

        # Backwards-compatible aliases for legacy properties and unit tests
        self.txt_search = self.toolbar.txt_search
        self.cmb_platform = self.toolbar.cmb_platform
        self.lbl_stats = QLabel("0 jobs")  # Backwards compatibility for unit test assertions
        self.lbl_stats.setVisible(False)
        main_layout.addWidget(self.lbl_stats)

        # Synchronous search update for instant response and test suite compatibility
        self.txt_search.textChanged.connect(lambda: self.refresh())

        # Exact Record Filter Banner Chip
        self.exact_filter_chip = ExactFilterChip(parent=self)
        self.exact_filter_chip.clear_requested.connect(self.clear_exact_filter)
        main_layout.addWidget(self.exact_filter_chip)

        # 5. Master-Detail Workspace: Splitter (Data Grid vs Detail Panel)
        self.splitter = QSplitter(Qt.Horizontal)

        # Left Container: Bulk Action Bar + Stacked Widget (Table vs Empty vs Loading vs Error)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        # Bulk Actions Bar
        self.bulk_bar = JobsBulkBar(self)
        self.bulk_bar.add_pipeline_clicked.connect(self._on_bulk_add_pipeline)
        self.bulk_bar.mark_skipped_clicked.connect(self._on_bulk_mark_skipped)
        self.bulk_bar.mark_junk_clicked.connect(self._on_bulk_mark_junk)
        self.bulk_bar.restore_junk_clicked.connect(self._on_bulk_restore_junk)
        self.bulk_bar.open_urls_clicked.connect(self._on_bulk_open_urls)
        self.bulk_bar.qualify_selected_clicked.connect(self._on_bulk_qualify_clicked)
        self.bulk_bar.clear_selection_clicked.connect(self._on_bulk_clear)
        left_layout.addWidget(self.bulk_bar)

        self.left_stack = QStackedWidget()

        # Stack Index 0: Interactive Data Grid
        self.table = JobsTable(self)
        self.table.job_selected.connect(self._on_job_selected)
        self.table.job_activated.connect(self._open_job_details_dialog)
        self.table.sort_changed.connect(self._on_sort_changed)
        self.table.bulk_selection_changed.connect(self._on_bulk_selection_changed)
        self.table.mark_junk_requested.connect(self._on_mark_jobs_junk)
        self.table.restore_junk_requested.connect(self._on_restore_jobs_junk)
        self.table.open_external_requested.connect(self._on_open_jobs_external)
        self.table.qualify_requested.connect(self._on_qualify_jobs_requested)
        self.table.status_change_requested.connect(self._on_status_change_requested)
        self.left_stack.addWidget(self.table)

        # Stack Index 1: Empty State
        self.empty_state = JobsEmptyState(self)
        self.empty_state.clear_filters_clicked.connect(self._on_clear_all)
        self.left_stack.addWidget(self.empty_state)

        # Stack Index 2: Loading State
        self.loading_state = JobsLoadingState(self)
        self.left_stack.addWidget(self.loading_state)

        # Stack Index 3: Error State
        self.error_state = JobsErrorState(self)
        self.error_state.retry_clicked.connect(self.refresh)
        self.left_stack.addWidget(self.error_state)

        left_layout.addWidget(self.left_stack, 1)
        self.splitter.addWidget(left_container)

        # Right: Detail Inspection Panel
        self.detail_panel = JobsDetailPanel(self)
        self.detail_panel.view_jd_requested.connect(self._open_job_details_dialog)
        self.detail_panel.track_application_requested.connect(self._on_track_clicked)
        self.detail_panel.apply_universal_requested.connect(self.apply_universal_requested.emit)
        self.detail_panel.qualify_job_requested.connect(self._on_qualify_job_requested)
        self.detail_panel.mark_junk_requested.connect(lambda job: self._on_mark_jobs_junk([job]))
        self.detail_panel.restore_junk_requested.connect(lambda job: self._on_restore_jobs_junk([job]))
        self.detail_panel.status_change_requested.connect(self._on_status_change_requested)
        self.splitter.addWidget(self.detail_panel)

        self.detail_panel.setMinimumWidth(320)
        self.detail_panel.setMaximumWidth(450)
        self.splitter.setStretchFactor(0, 5)
        self.splitter.setStretchFactor(1, 2)
        self.splitter.setSizes([720, 360])
        main_layout.addWidget(self.splitter, 1)

        # 6. Pagination Footer Bar
        self.pagination = JobsPagination(self)
        self.pagination.page_changed.connect(self._on_page_changed)
        self.pagination.page_size_changed.connect(self._on_page_size_changed)
        main_layout.addWidget(self.pagination)

        # Keyboard shortcuts
        self._shortcut_search = QShortcut(QKeySequence("Ctrl+F"), self)
        self._shortcut_search.activated.connect(self.txt_search.setFocus)

        self._shortcut_esc = QShortcut(QKeySequence("Esc"), self)
        self._shortcut_esc.activated.connect(self._on_esc_pressed)

    def _on_theme_changed(self, mode: str) -> None:
        self.table.apply_theme()

    def _on_esc_pressed(self) -> None:
        if self.txt_search.hasFocus():
            self.txt_search.clear()
            self.table.setFocus()

    def apply_external_filter(self, method: str) -> None:
        """Public API for sidebar virtual nav items to pre-filter by application method or junk.

        Args:
            method: 'EASY_APPLY', 'COMPANY_PORTAL', 'JUNK', or '' to clear filter.
        """
        if method == "JUNK":
            self._is_junk_tab = True
            self._current_method_filter = None
            self.category_tabs.set_active_method("JUNK")
            self.toolbar.cmb_status.blockSignals(True)
            idx = self.toolbar.cmb_status.findText("Junk")
            if idx >= 0:
                self.toolbar.cmb_status.setCurrentIndex(idx)
            self.toolbar.cmb_status.blockSignals(False)
            self.toolbar.update_chips()
            self.table.set_junk_view(True)
            self.bulk_bar.set_mode(is_junk_mode=True)
        else:
            self._is_junk_tab = False
            val = method if method else None
            self._current_method_filter = val
            self.category_tabs.set_active_method(val)
            self.toolbar.set_method(val)
            if self.toolbar.cmb_status.currentText() == "Junk":
                self.toolbar.cmb_status.blockSignals(True)
                self.toolbar.cmb_status.setCurrentIndex(0)
                self.toolbar.cmb_status.blockSignals(False)
                self.toolbar.update_chips()
            self.table.set_junk_view(False)
            self.bulk_bar.set_mode(is_junk_mode=False)
        self._current_page = 1
        self.refresh()

    def _on_category_tab_changed(self, method: Optional[str]) -> None:
        if method == "JUNK":
            self._is_junk_tab = True
            self._current_method_filter = None
            self.toolbar.cmb_status.blockSignals(True)
            idx = self.toolbar.cmb_status.findText("Junk")
            if idx >= 0:
                self.toolbar.cmb_status.setCurrentIndex(idx)
            self.toolbar.cmb_status.blockSignals(False)
            self.toolbar.update_chips()
            self.table.set_junk_view(True)
            self.bulk_bar.set_mode(is_junk_mode=True)
        else:
            self._is_junk_tab = False
            self._current_method_filter = method
            self.toolbar.set_method(method)
            if self.toolbar.cmb_status.currentText() == "Junk":
                self.toolbar.cmb_status.blockSignals(True)
                self.toolbar.cmb_status.setCurrentIndex(0)
                self.toolbar.cmb_status.blockSignals(False)
                self.toolbar.update_chips()
            self.table.set_junk_view(False)
            self.bulk_bar.set_mode(is_junk_mode=False)
        self._current_page = 1
        self.refresh()

    def _on_column_visibility_changed(self, col_idx: int, visible: bool) -> None:
        self.table.setColumnHidden(col_idx, not visible)

    def _on_density_changed(self, density: str) -> None:
        self.table.set_density(density)

    def _on_sort_changed(self, sort_by: str, sort_order: str) -> None:
        self._sort_by = sort_by
        self._sort_order = sort_order
        self.refresh()

    def _on_page_changed(self, new_page: int) -> None:
        self._current_page = new_page
        self.refresh()

    def _on_page_size_changed(self, new_page_size: int) -> None:
        self._page_size = new_page_size
        self._current_page = 1
        self.refresh()

    def _on_toolbar_clear_all(self) -> None:
        self._current_method_filter = None
        self._is_junk_tab = False
        self.category_tabs.set_active_method(None)
        self.table.set_junk_view(False)
        self.bulk_bar.set_mode(is_junk_mode=False)
        self._current_page = 1

    def _on_clear_all(self) -> None:
        self._on_toolbar_clear_all()
        self.toolbar.clear_all_filters()

    def _on_bulk_selection_changed(self, checked_jobs: List[Job]) -> None:
        self.bulk_bar.set_selected_count(len(checked_jobs))

    def _on_bulk_clear(self) -> None:
        self.table.clear_checked_jobs()

    def _on_bulk_add_pipeline(self) -> None:
        jobs = self.table.get_checked_jobs()
        if not jobs:
            return

        added_count = 0
        for job in jobs:
            app, _ = self.app_service.create_application(
                job_id=job.id,
                status="SUBMITTED",
                application_type="MANUAL",
                notes="Bulk tracked from Jobs Repository",
            )
            if app:
                added_count += 1

        self.notification_bar.show_message(
            "success", f"Added {added_count} {'job' if added_count == 1 else 'jobs'} to application pipeline."
        )
        self.table.clear_checked_jobs()
        self.refresh()
        self.data_updated.emit("jobs")

    def _on_bulk_mark_skipped(self) -> None:
        jobs = self.table.get_checked_jobs()
        if not jobs:
            return

        skipped_count = 0
        for job in jobs:
            app, _ = self.app_service.create_application(
                job_id=job.id,
                status="SKIPPED",
                application_type="MANUAL",
                notes="Bulk marked SKIPPED from Jobs Repository",
            )
            if app:
                skipped_count += 1

        self.notification_bar.show_message(
            "info", f"Marked {skipped_count} {'job' if skipped_count == 1 else 'jobs'} as SKIPPED."
        )
        self.table.clear_checked_jobs()
        self.refresh()
        self.data_updated.emit("jobs")

    def _on_bulk_open_urls(self) -> None:
        jobs = self.table.get_checked_jobs()
        if not jobs:
            return

        urls = []
        for j in jobs:
            url = getattr(j, "application_url", None) or getattr(j, "source_url", None)
            if url and url not in urls:
                urls.append(url)

        if not urls:
            self.notification_bar.show_message("warning", "None of the selected jobs have URLs.")
            return

        # Limit to 5 at a time to prevent accidental browser overload
        urls_to_open = urls[:5]
        for u in urls_to_open:
            QDesktopServices.openUrl(QUrl(u))

        msg = f"Opened {len(urls_to_open)} job links in your browser."
        if len(urls) > 5:
            msg += f" (Capped at 5 of {len(urls)} to protect browser resources)"
        self.notification_bar.show_message("info", msg)

    def _on_mark_jobs_junk(self, jobs: List[Job]) -> None:
        if not jobs:
            return
        count = 0
        for job in jobs:
            app, err = self.app_service.mark_as_junk(job_id=job.id, notes="Marked as junk from Jobs view")
            if app:
                count += 1
        
        self.notification_bar.show_message(
            "info", f"Moved {count} {'job' if count == 1 else 'jobs'} to Junk repository."
        )
        self.table.clear_checked_jobs()
        self.refresh()
        self.data_updated.emit("jobs")

    def _on_restore_jobs_junk(self, jobs: List[Job]) -> None:
        if not jobs:
            return
        count = 0
        for job in jobs:
            app, err = self.app_service.restore_from_junk(job_id=job.id)
            if app:
                count += 1
        
        self.notification_bar.show_message(
            "success", f"Restored {count} {'job' if count == 1 else 'jobs'} to active repository."
        )
        self.table.clear_checked_jobs()
        self.refresh()
        self.data_updated.emit("jobs")

    def _on_bulk_mark_junk(self) -> None:
        jobs = self.table.get_checked_jobs()
        self._on_mark_jobs_junk(jobs)

    def _on_bulk_restore_junk(self) -> None:
        jobs = self.table.get_checked_jobs()
        self._on_restore_jobs_junk(jobs)

    def _on_open_jobs_external(self, jobs: List[Job]) -> None:
        for job in jobs[:5]:
            url = getattr(job, "application_url", None) or getattr(job, "source_url", None)
            if url:
                QDesktopServices.openUrl(QUrl(url))

    def _on_qualify_job_requested(self, job: Job) -> None:
        """Triggers background qualification for a single job."""
        if not job:
            return
        self._run_qualification([job.id])

    def _on_qualify_jobs_requested(self, jobs: List[Job]) -> None:
        """Triggers background qualification for a list of jobs."""
        if not jobs:
            return
        self._run_qualification([j.id for j in jobs])

    def _on_bulk_qualify_clicked(self) -> None:
        """Triggers qualification for all currently checked jobs."""
        checked = self.table.get_checked_jobs()
        if not checked:
            self.notification_bar.show_message("warning", "No jobs selected for qualification.")
            return
        self._run_qualification([j.id for j in checked])

    def _run_qualification(self, job_ids: List[int]) -> None:
        """Spawns JobQualificationWorker to process jobs asynchronously without blocking UI."""
        from app.ui.workers.job_qualification_worker import JobQualificationWorker

        worker = JobQualificationWorker(
            job_ids=job_ids,
            force_reevaluate=True,
            parent=self,
        )

        def on_job_qualified(dto):
            # Update table badge dynamically
            self.table.update_job_evaluation(dto.job_id, dto.score, dto.decision.value)
            # Update detail panel if this job is currently selected
            selected = self.table.get_selected_job()
            if selected and selected.id == dto.job_id:
                self.detail_panel.set_qualification(dto)

        def on_progress(cur, total):
            if total > 1:
                self.notification_bar.show_message("info", f"Qualifying jobs: {cur}/{total} evaluated...")

        def on_finished(summary):
            if summary.get("total", 0) == 1:
                self.notification_bar.show_message("success", "Job qualification complete.")
            else:
                self.notification_bar.show_message(
                    "success",
                    f"Bulk qualification complete: {summary['processed']} evaluated, {summary['qualified']} qualified."
                )

        worker.job_qualified.connect(on_job_qualified)
        worker.progress.connect(on_progress)
        worker.bulk_finished.connect(on_finished)
        worker.finished.connect(lambda: self._cleanup_worker(worker))

        self._qualification_workers.append(worker)
        worker.start()

    def _cleanup_worker(self, worker):
        if worker in self._qualification_workers:
            self._qualification_workers.remove(worker)

    def _on_calculate_all_requested(self) -> None:
        """Triggers qualification for ALL jobs matching active filters in the database."""
        tf = self.toolbar.get_filters()
        status_filter = "JUNK" if self._is_junk_tab else tf.get("status")
        method_filter = None if self._is_junk_tab else (self._current_method_filter or tf.get("method"))

        f = JobFilter(
            platform=tf.get("platform"),
            status=status_filter,
            search=tf.get("search"),
            location=tf.get("location"),
            application_method=method_filter,
            match_score_max=tf.get("match_score_max"),
            match_score_min=tf.get("match_score_min"),
            match_not_evaluated=tf.get("match_not_evaluated", False),
            include_junk=self._is_junk_tab,
        )

        job_ids = self.job_service.get_job_ids(filters=f)
        if not job_ids:
            self.notification_bar.show_message("warning", "No matching jobs found in database to qualify.")
            return

        self.notification_bar.show_message("info", f"Starting qualification for all {len(job_ids)} matching jobs in database...")
        self._run_qualification(job_ids)

    def refresh(self) -> None:
        """Reloads jobs from database according to active filters, sorting, and pagination."""
        # 0. Check for armed navigation request from AppNavigator
        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)
            return

        # 0b. Exact Record Isolation Mode
        if self._exact_job_id is not None:
            job = self.service.get_job_by_id(self._exact_job_id) if hasattr(self.service, "get_job_by_id") else None
            if job:
                self._current_jobs = [job]
                self.left_stack.setCurrentIndex(0)
                self.table.set_jobs([job])
                self.table.selectRow(0)
                self._on_job_selected(job)
                self.exact_filter_chip.set_record(job.title, job.id, "Job")
                self.lbl_stats.setText("1 job")
                self.pagination.set_pagination(1, 1, self._page_size)
                return
            else:
                self.notification_bar.show_message("danger", f"Job #{self._exact_job_id} no longer exists or was removed.")
                self._exact_job_id = None
                self.exact_filter_chip.clear()

        # 1. Update Category Tab Counts
        try:
            counts = self.job_service.get_category_counts()
            self.category_tabs.set_counts(
                all_count=counts.get("all", 0),
                easy_count=counts.get("easy", 0),
                portal_count=counts.get("portal", 0),
                junk_count=counts.get("junk", 0),
            )
        except Exception:
            pass

        # 2. Extract active filters
        tf = self.toolbar.get_filters()
        status_filter = "JUNK" if self._is_junk_tab else tf.get("status")
        method_filter = None if self._is_junk_tab else (self._current_method_filter or tf.get("method"))

        is_junk_view = status_filter == "JUNK"
        self.table.set_junk_view(is_junk_view)
        self.bulk_bar.set_mode(is_junk_mode=is_junk_view)

        f = JobFilter(
            platform=tf.get("platform"),
            status=status_filter,
            search=tf.get("search"),
            location=tf.get("location"),
            application_method=method_filter,
            match_score_max=tf.get("match_score_max"),
            match_score_min=tf.get("match_score_min"),
            match_not_evaluated=tf.get("match_not_evaluated", False),
            include_junk=is_junk_view,
        )

        # 3. Query total count and paged jobs with error guard directly from DB
        try:
            total_count = self.job_service.count_jobs(filters=f)
            offset = (self._current_page - 1) * self._page_size

            self._current_jobs = self.job_service.list_jobs(
                filters=f,
                limit=self._page_size,
                offset=offset,
                sort_by=self._sort_by,
                sort_order=self._sort_order,
            )
        except Exception as e:
            self.error_state.set_error(str(e))
            self.left_stack.setCurrentIndex(3)
            self.lbl_stats.setText("0 jobs")
            self.pagination.set_pagination(1, 0, self._page_size)
            self.detail_panel.set_job(None)
            return

        # 4. Update stats and pagination
        self.lbl_stats.setText(f"{total_count} jobs")
        self.pagination.set_pagination(self._current_page, total_count, self._page_size)

        # 5. Populate Table or Empty State
        if total_count == 0:
            self.left_stack.setCurrentIndex(1)
            self.table.set_jobs([])
            self.detail_panel.set_job(None)
        else:
            self.left_stack.setCurrentIndex(0)
            self.table.set_jobs(self._current_jobs)

    def _on_job_selected(self, job: Optional[Job]) -> None:
        if not job:
            self.detail_panel.set_job(None)
            return

        in_pipeline = False
        app_status = "NOT_APPLIED"
        try:
            if hasattr(job, "applications") and job.applications:
                app_status = job.applications[0].status
                in_pipeline = app_status not in ("NOT_APPLIED", "JUNK")
            else:
                app = self.app_service.get_by_job_id(job.id)
                if app:
                    app_status = app.status
                    in_pipeline = app_status not in ("NOT_APPLIED", "JUNK")
        except Exception:
            try:
                app = self.app_service.get_by_job_id(job.id)
                if app:
                    app_status = app.status
                    in_pipeline = app_status not in ("NOT_APPLIED", "JUNK")
            except Exception:
                in_pipeline = False
                app_status = "NOT_APPLIED"

        self.detail_panel.set_job(job, in_pipeline=in_pipeline, app_status=app_status)

    def _open_job_details_dialog(self, job: Optional[Job]) -> None:
        if not job:
            return
        dlg = JobDetailsDialog(job, self)
        dlg.open()

    # ── Universal Exact Navigation Lifecycle ──────────────────────────────────
    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores a pending navigation request to be executed on view activation."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Executes navigation action (OPEN, FOCUS, or FILTER) on this view."""
        self._pending_navigation_request = None
        job_id = request.entity_id

        if request.action == NavigationAction.FILTER:
            self.apply_exact_filter(job_id)
        elif request.action == NavigationAction.OPEN:
            self.open_record(job_id)
        else:
            self.focus_record(job_id)

    def apply_exact_filter(self, job_id: int) -> None:
        """Filters the jobs workspace to strictly this single record with an exact-filter chip."""
        if self._exact_job_id != job_id:
            self._capture_state()
            self._exact_job_id = job_id
        self.refresh()

    def open_record(self, job_id: int) -> None:
        """Opens the inspection detail dialog for job_id."""
        job = self.service.get_job_by_id(job_id) if hasattr(self.service, "get_job_by_id") else None
        if job:
            self._on_job_selected(job)
            self._open_job_details_dialog(job)
        else:
            self.notification_bar.show_message("danger", f"Job #{job_id} no longer exists or was removed.")

    def focus_record(self, job_id: int) -> None:
        """Scrolls to and selects job_id in the existing table without isolating the view."""
        for row, j in enumerate(getattr(self, "_current_jobs", [])):
            if j.id == job_id:
                self.table.selectRow(row)
                self._on_job_selected(j)
                return
        # If not present in currently paged list, display in detail panel if available
        job = self.service.get_job_by_id(job_id) if hasattr(self.service, "get_job_by_id") else None
        if job:
            self._on_job_selected(job)

    def clear_exact_filter(self) -> None:
        """Exits exact-filter isolation and restores previous view filters."""
        self._exact_job_id = None
        self.exact_filter_chip.clear()
        self._restore_state()
        self.refresh()

    def _capture_state(self) -> None:
        """Captures contextual filters before applying exact-filter isolation."""
        if self._state_snapshot is None:
            tf = self.toolbar.get_filters()
            self._state_snapshot = ViewStateSnapshot(
                search_query=self.txt_search.text(),
                status_filter=tf.get("status"),
                platform_filter=tf.get("platform"),
                current_page=self._current_page,
            )

    def _restore_state(self) -> None:
        """Restores previous filter and page state when clearing exact filter."""
        if self._state_snapshot:
            snap = self._state_snapshot
            self.txt_search.blockSignals(True)
            self.txt_search.setText(snap.search_query)
            self.txt_search.blockSignals(False)
            self._current_page = snap.current_page
            self._state_snapshot = None

    def inspect_job_by_id(self, job_id: int) -> None:
        """Finds job by ID, isolates it in the workspace with exact filter, and opens detail dialog."""
        self.apply_exact_filter(job_id)
        job = self.service.get_job_by_id(job_id) if hasattr(self.service, "get_job_by_id") else None
        if job:
            self._open_job_details_dialog(job)


    def _on_track_clicked(self, job: Optional[Job]) -> None:
        if not job:
            return

        app, err = self.app_service.create_application(
            job_id=job.id,
            status="SUBMITTED",
            application_type="MANUAL",
            notes="Manually tracked from Jobs Repository",
        )

        if app:
            self.notification_bar.show_message(
                "success", f"Created application tracker record for '{job.title}'."
            )
            self.refresh()
            self._on_job_selected(job)
            self.data_updated.emit("jobs")
        else:
            self.notification_bar.show_message("danger", f"Failed to track: {err}")

    def _on_status_change_requested(self, target: Any, new_status: str) -> None:
        """Handles single or bulk application status transitions requested from table or detail drawer."""
        if not target:
            return

        jobs = target if isinstance(target, list) else [target]
        success_count = 0
        fail_count = 0
        last_error = ""

        for job in jobs:
            try:
                # Find existing application
                app = None
                try:
                    if hasattr(job, "applications") and job.applications:
                        app = job.applications[0]
                except Exception:
                    app = None

                if not app:
                    app = self.app_service.get_by_job_id(job.id)

                if app:
                    updated, err = self.app_service.transition_status(
                        application_id=app.id,
                        new_status=new_status,
                        source="USER",
                        notes=f"Status manually updated to {new_status} via Jobs Repository",
                        allow_override=True,
                    )
                    if updated:
                        success_count += 1
                    else:
                        fail_count += 1
                        last_error = err or "Transition rejected"
                else:
                    # No application record exists yet for this job; create one with target status
                    app, err = self.app_service.create_application(
                        job_id=job.id,
                        status=new_status,
                        application_type="MANUAL",
                        notes=f"Tracked and set to {new_status} via Jobs Repository",
                    )
                    if app:
                        success_count += 1
                    else:
                        fail_count += 1
                        last_error = err or "Creation failed"
            except Exception as e:
                fail_count += 1
                last_error = str(e)

        clean_status = new_status.replace("_", " ").title()
        if success_count > 0 and fail_count == 0:
            if len(jobs) == 1:
                self.notification_bar.show_message("success", f"Job status changed to {clean_status}.")
            else:
                self.notification_bar.show_message("success", f"Updated {success_count} jobs to {clean_status}.")
        elif success_count > 0 and fail_count > 0:
            self.notification_bar.show_message("warning", f"Updated {success_count} jobs ({fail_count} failed: {last_error}).")
        else:
            self.notification_bar.show_message("danger", f"Failed to change status: {last_error}")

        self.refresh()
        selected_job = self.table.get_selected_job()
        if selected_job:
            self._on_job_selected(selected_job)
        self.data_updated.emit("jobs")

    def _on_add_manual_clicked(self) -> None:
        dialog = AddManualJobDialog(service=self.job_service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.notification_bar.show_message("success", "Manual job listing added successfully.")
            self.refresh()
            self.data_updated.emit("jobs")

    def _on_export_clicked(self) -> None:
        """Exports currently filtered jobs to a clean CSV file."""
        if not self._current_jobs:
            self.notification_bar.show_message("info", "No jobs available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Filtered Jobs",
            "jobs_export.csv",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        try:
            # Query all jobs matching current filter (up to 5000 for export)
            tf = self.toolbar.get_filters()
            status_filter = "JUNK" if self._is_junk_tab else tf.get("status")
            f = JobFilter(
                platform=tf.get("platform"),
                status=status_filter,
                search=tf.get("search"),
                location=tf.get("location"),
                application_method=self._current_method_filter or tf.get("method"),
                match_score_max=tf.get("match_score_max"),
                match_score_min=tf.get("match_score_min"),
                match_not_evaluated=tf.get("match_not_evaluated", False),
                include_junk=self._is_junk_tab,
            )
            all_matching_jobs = self.job_service.list_jobs(
                filters=f,
                limit=5000,
                sort_by=self._sort_by,
                sort_order=self._sort_order,
            )

            with open(file_path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([
                    "Job Title",
                    "Company",
                    "Platform",
                    "Location",
                    "Salary",
                    "Experience",
                    "Method",
                    "Status",
                    "Application URL",
                    "Listing URL",
                    "Discovered Date",
                ])
                for j in all_matching_jobs:
                    app_status = "NOT_APPLIED"
                    if hasattr(j, "applications") and j.applications:
                        app_status = j.applications[0].status
                    writer.writerow([
                        j.title,
                        j.company_raw,
                        j.platform,
                        j.location or "",
                        j.salary_text or "",
                        j.experience_text or "",
                        getattr(j, "application_method", "EASY_APPLY") or "EASY_APPLY",
                        app_status,
                        getattr(j, "application_url", "") or "",
                        j.source_url or "",
                        j.first_seen_at.strftime("%Y-%m-%d %H:%M:%S") if j.first_seen_at else "",
                    ])

            self.notification_bar.show_message(
                "success", f"Successfully exported {len(all_matching_jobs)} jobs to CSV."
            )
        except Exception as e:
            self.notification_bar.show_message("danger", f"Failed to export CSV: {e}")
