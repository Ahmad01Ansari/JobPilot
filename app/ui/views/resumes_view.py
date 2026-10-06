"""Resume management workspace view.

Provides:
- 5 Domain KPI Summary Bar
- Search, target role filter, status filter, sort order, and grid/table toggle toolbar
- Grid View with rich ResumeCards (health badges, detected skills tags, usage metrics)
- Table View with compact sortable columns
- In-App Resume Preview Workspace with UI-thread QPdfView, diagnostics checklist, and usage history
- Background worker for file operations and hashing
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Resume, User
from app.db.session import SessionLocal, get_db_session
from app.repositories.user_repository import UserRepository
from app.services.resume_service import ResumeService
from app.services.search.search_result import NavigationAction, NavigationRequest
from app.ui.state import AppState
from app.ui.theme import COLORS
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.resumes.resume_card import ResumeCard
from app.ui.widgets.resumes.resume_dialogs import (
    ResumeMetadataDialog,
    ResumeVersionDialog,
    UploadResumeDialog,
)
from app.ui.widgets.resumes.resume_filter_toolbar import ResumeFilterToolbar
from app.ui.widgets.resumes.resume_preview_workspace import ResumePreviewWorkspace
from app.ui.widgets.resumes.resume_summary_bar import ResumeSummaryBar
from app.ui.widgets.resumes.resume_table_view import ResumeTableView


class ResumeOperationWorker(QObject):
    """Background worker for non-blocking file processing, copying, hashing, and parsing."""

    finished = Signal(bool, str, int)  # success, message, resume_id

    def __init__(
        self,
        service: ResumeService,
        user_id: int,
        action: str,  # "upload" or "version"
        file_path: str,
        display_name: Optional[str] = None,
        role_target: Optional[str] = None,
        version: str = "1.0",
        notes: Optional[str] = None,
        is_default: bool = False,
        source_resume_id: Optional[int] = None,
    ):
        super().__init__()
        self.service = service
        self.user_id = user_id
        self.action = action
        self.file_path = file_path
        self.display_name = display_name
        self.role_target = role_target
        self.version = version
        self.notes = notes
        self.is_default = is_default
        self.source_resume_id = source_resume_id

    def run(self):
        try:
            if self.action == "version":
                res, created, err = self.service.create_new_version(
                    source_resume_id=self.source_resume_id,
                    user_id=self.user_id,
                    new_source_path=self.file_path,
                    new_version=self.version,
                    notes=self.notes,
                    display_name=self.display_name,
                    role_target=self.role_target,
                    is_default=self.is_default,
                )
            else:
                res, created, err = self.service.add_resume(
                    user_id=self.user_id,
                    source_path=self.file_path,
                    display_name=self.display_name,
                    role_target=self.role_target,
                    version=self.version,
                    notes=self.notes,
                    is_default=self.is_default,
                )

            if created and res:
                self.finished.emit(True, f"Resume '{res.name}' saved successfully.", res.id)
            elif res and not created:
                self.finished.emit(False, err or "This exact resume file is already uploaded.", res.id)
            else:
                self.finished.emit(False, err or "Failed to store resume document.", 0)
        except Exception as e:
            self.finished.emit(False, f"Operation failed: {e}", 0)


class ResumesView(QWidget):
    """Primary workspace view for Resume Management & Intelligence."""

    def __init__(self, service: Optional[ResumeService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service or ResumeService()
        self.current_user_id = self._ensure_user()

        self._all_resumes: List[Resume] = []
        self._filtered_resumes: List[Resume] = []
        self._health_cache: Dict[int, Dict[str, Any]] = {}
        self._usage_cache: Dict[int, Dict[str, Any]] = {}

        # Filter states
        self._search_query: str = ""
        self._role_filter: str = "ALL"
        self._status_filter: str = "ACTIVE"
        self._sort_order: str = "RECENT"
        self._view_mode: str = "grid"

        self._selected_resume_id: Optional[int] = None
        self._pending_navigation_request: Optional[NavigationRequest] = None
        self._setup_ui()
        self.table = self.table_view
        self.refresh()

    @property
    def lbl_total(self):
        class _TotalHelper:
            def __init__(self, pill):
                self.pill = pill
            def text(self):
                return f"Total Resumes: {self.pill.lbl_value.text()}"
        return _TotalHelper(self.summary_bar.pill_active)

    @property
    def lbl_default(self):
        class _DefHelper:
            def __init__(self, pill):
                self.pill = pill
            def text(self):
                return f"Default: {self.pill.lbl_value.text()}"
        return _DefHelper(self.summary_bar.pill_default)

    def _ensure_user(self) -> int:
        with get_db_session(self.service._session_factory) as session:
            repo = UserRepository(session)
            user = repo.get_primary_user()
            if not user:
                user = User(name="Default Candidate", email="candidate@apply-and-pray.local")
                session.add(user)
                session.commit()
            return user.id

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        # Main Stack: Page 0 is Library Workspace, Page 1 is Detail & PDF Preview Workspace
        self.main_stack = QStackedWidget(self)

        # PAGE 0: Library Workspace
        self.library_page = QWidget()
        lib_layout = QVBoxLayout(self.library_page)
        lib_layout.setContentsMargins(0, 0, 0, 0)
        lib_layout.setSpacing(14)

        # 1. Header
        header = PageHeader(
            title="Resume Management & Intelligence",
            subtitle="Manage targeted resume variants, monitor technical health, and track application usage.",
        )
        lib_layout.addWidget(header)

        # 2. 5 Domain KPI Summary Bar
        self.summary_bar = ResumeSummaryBar(self)
        lib_layout.addWidget(self.summary_bar)

        # 3. Filter & Action Toolbar
        self.toolbar = ResumeFilterToolbar(self)
        self.toolbar.search_changed.connect(self._on_search_changed)
        self.toolbar.role_filter_changed.connect(self._on_role_filter_changed)
        self.toolbar.status_filter_changed.connect(self._on_status_filter_changed)
        self.toolbar.sort_changed.connect(self._on_sort_changed)
        self.toolbar.view_mode_changed.connect(self._on_view_mode_changed)
        self.toolbar.upload_requested.connect(self._on_upload_clicked)
        lib_layout.addWidget(self.toolbar)

        # 4. View Modes Stack (Grid, Table, Empty)
        self.views_stack = QStackedWidget(self)

        # View Mode 0: Grid Scroll Area
        self.grid_scroll = QScrollArea()
        self.grid_scroll.setWidgetResizable(True)
        self.grid_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(14)
        self.grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid_layout.setColumnStretch(0, 1)
        self.grid_layout.setColumnStretch(1, 1)
        self.grid_scroll.setWidget(self.grid_container)
        self.views_stack.addWidget(self.grid_scroll)

        # View Mode 1: Table View
        self.table_view = ResumeTableView(self)
        self.table_view.resume_selected.connect(self._on_resume_card_clicked)
        self.table_view.action_preview.connect(self._open_preview)
        self.table_view.action_set_default.connect(self._set_default)
        self.table_view.action_new_version.connect(self._open_new_version_dialog)
        self.table_view.action_edit.connect(self._open_edit_dialog)
        self.table_view.action_archive.connect(self._archive_resume)
        self.table_view.action_unarchive.connect(self._unarchive_resume)
        self.table_view.action_delete.connect(self._delete_resume)
        self.table_view.action_open_os.connect(self._open_os_viewer)
        self.views_stack.addWidget(self.table_view)

        # View Mode 2: Empty State
        self.empty_card = QFrame()
        self.empty_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px dashed {COLORS['border']};
                border-radius: 12px;
                padding: 40px 20px;
            }}
        """)
        empty_layout = QVBoxLayout(self.empty_card)
        empty_layout.setAlignment(Qt.AlignCenter)
        empty_layout.setSpacing(10)

        lbl_empty_icon = QLabel("📄")
        lbl_empty_icon.setStyleSheet("font-size: 36px;")
        lbl_empty_icon.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(lbl_empty_icon)

        self.lbl_empty_title = QLabel("No Resumes Found")
        self.lbl_empty_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_empty_title.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_title)

        self.lbl_empty_desc = QLabel("Upload a resume or adjust your filters above.")
        self.lbl_empty_desc.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']};")
        self.lbl_empty_desc.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(self.lbl_empty_desc)

        btn_empty_up = QPushButton("+ Upload Resume")
        btn_empty_up.setCursor(Qt.PointingHandCursor)
        btn_empty_up.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
        """)
        btn_empty_up.clicked.connect(self._on_upload_clicked)
        empty_layout.addWidget(btn_empty_up)

        self.views_stack.addWidget(self.empty_card)

        lib_layout.addWidget(self.views_stack, 1)
        self.main_stack.addWidget(self.library_page)

        # PAGE 1: Resume Preview & Detail Workspace
        self.preview_workspace = ResumePreviewWorkspace(self)
        self.preview_workspace.back_requested.connect(self._close_preview)
        self.preview_workspace.action_set_default.connect(self._set_default)
        self.preview_workspace.action_new_version.connect(self._open_new_version_dialog)
        self.preview_workspace.action_open_os.connect(self._open_os_viewer)
        self.main_stack.addWidget(self.preview_workspace)

        root_layout.addWidget(self.main_stack)

    def refresh(self):
        """Fetches fresh data from ResumeService and re-renders the library views and KPI summary."""
        # 1. Fetch library summary (optimized grouped query)
        summary = self.service.get_library_summary(self.current_user_id)
        self.summary_bar.set_summary(summary)

        # 2. Fetch all resumes for the user (active + archived for cache pre-population)
        self._all_resumes = self.service.list_resumes(self.current_user_id, include_archived=True)

        # 3. Populate dynamic roles in filter toolbar
        distinct_roles = set()
        for r in self._all_resumes:
            if r.role_target:
                distinct_roles.add(r.role_target)
        self.toolbar.populate_roles(list(distinct_roles))

        # 4. Pre-populate health and usage caches
        self._health_cache.clear()
        self._usage_cache.clear()
        for r in self._all_resumes:
            self._health_cache[r.id] = self.service.get_resume_health(r.id, self.current_user_id)
            self._usage_cache[r.id] = self.service.get_resume_usage(r.id, self.current_user_id)

        # 5. Apply filters and render
        self._apply_filters()

        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)

    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores request to be applied safely during or after refresh."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Navigates to resume matching request."""
        if request.entity_type != "resume":
            return
        if request.action == NavigationAction.OPEN:
            self.open_record(request.entity_id)
        else:
            self.focus_record(request.entity_id)

    def open_record(self, resume_id: int) -> bool:
        """Opens detail & preview workspace for resume_id."""
        self._open_preview(resume_id)
        return True

    def focus_record(self, resume_id: int) -> bool:
        """Selects resume card in library view without full preview."""
        self.main_stack.setCurrentIndex(0)
        self._on_resume_card_clicked(resume_id)
        return True

    def _apply_filters(self):
        """Filters and sorts _all_resumes according to active toolbar controls."""
        filtered = []

        q = self._search_query.strip().lower()
        rf = self._role_filter.strip().upper()
        sf = self._status_filter.strip().upper()

        for r in self._all_resumes:
            # Status filter
            if sf == "ACTIVE" and r.is_archived:
                continue
            if sf == "ARCHIVED" and not r.is_archived:
                continue

            # Role filter
            if rf != "ALL":
                r_role = (r.role_target or "General").upper()
                if rf == "GENERAL" and r_role != "GENERAL":
                    continue
                elif rf != "GENERAL" and rf != r_role:
                    continue

            # Search query
            if q:
                name_match = q in (r.name or "").lower()
                role_match = q in (r.role_target or "").lower()
                notes_match = q in (r.notes or "").lower()
                # Also check detected skills
                skills_match = False
                h = self._health_cache.get(r.id, {})
                for s in h.get("metadata", {}).get("detected_skills", []):
                    if q in s.get("canonical", "").lower():
                        skills_match = True
                        break
                if not (name_match or role_match or notes_match or skills_match):
                    continue

            filtered.append(r)

        # Sorting
        if self._sort_order == "MOST_APPS":
            filtered.sort(
                key=lambda r: (
                    r.is_default,
                    self._usage_cache.get(r.id, {}).get("total_applications", 0),
                ),
                reverse=True,
            )
        elif self._sort_order == "NAME":
            filtered.sort(key=lambda r: (r.name or "").lower())
        elif self._sort_order == "VERSION":
            filtered.sort(key=lambda r: r.version or "1.0", reverse=True)
        else:  # RECENT
            filtered.sort(key=lambda r: (r.is_default, r.updated_at or r.created_at), reverse=True)

        self._filtered_resumes = filtered
        self._render_views()

    def _render_views(self):
        """Renders either grid view, table view, or empty state."""
        self.table_view.set_resumes(
            self._filtered_resumes,
            health_map=self._health_cache,
            usage_map=self._usage_cache,
        )

        if not self._filtered_resumes:
            self.views_stack.setCurrentIndex(2)
            return

        if self._view_mode == "table":
            self.views_stack.setCurrentIndex(1)
        else:
            # Clear existing grid cards
            while self.grid_layout.count():
                item = self.grid_layout.takeAt(0)
                if item.widget():
                    w = item.widget()
                    w.setParent(None)
                    w.deleteLater()

            # Render 2-column or 3-column responsive grid
            columns = 2
            for idx, r in enumerate(self._filtered_resumes):
                row = idx // columns
                col = idx % columns

                card = ResumeCard(
                    resume=r,
                    health_info=self._health_cache.get(r.id),
                    usage_info=self._usage_cache.get(r.id),
                    is_selected=(r.id == self._selected_resume_id),
                )
                card.card_clicked.connect(self._on_resume_card_clicked)
                card.action_preview.connect(self._open_preview)
                card.action_set_default.connect(self._set_default)
                card.action_new_version.connect(self._open_new_version_dialog)
                card.action_edit.connect(self._open_edit_dialog)
                card.action_archive.connect(self._archive_resume)
                card.action_unarchive.connect(self._unarchive_resume)
                card.action_delete.connect(self._delete_resume)
                card.action_open_os.connect(self._open_os_viewer)

                self.grid_layout.addWidget(card, row, col)

            self.grid_layout.setColumnStretch(0, 1)
            self.grid_layout.setColumnStretch(1, 1)
            last_row = (len(self._filtered_resumes) + 1) // columns
            self.grid_layout.setRowStretch(last_row, 1)

            self.views_stack.setCurrentIndex(0)

    # Filter toolbar slot handlers
    def _on_search_changed(self, text: str):
        self._search_query = text
        self._apply_filters()

    def _on_role_filter_changed(self, role: str):
        self._role_filter = role
        self._apply_filters()

    def _on_status_filter_changed(self, status: str):
        self._status_filter = status
        self._apply_filters()

    def _on_sort_changed(self, sort_key: str):
        self._sort_order = sort_key
        self._apply_filters()

    def _on_view_mode_changed(self, mode: str):
        self._view_mode = mode
        self._render_views()

    def _on_resume_card_clicked(self, resume_id: int):
        self._selected_resume_id = resume_id
        # Re-apply selection style across cards without full reload
        for i in range(self.grid_layout.count()):
            w = self.grid_layout.itemAt(i).widget()
            if isinstance(w, ResumeCard):
                w.set_selected(w.resume_id == resume_id)

    # Navigation & Workspace Switching
    def _open_preview(self, resume_id: int):
        target = next((r for r in self._all_resumes if r.id == resume_id), None)
        if not target:
            return

        h_info = self._health_cache.get(resume_id) or self.service.get_resume_health(resume_id, self.current_user_id)
        u_info = self._usage_cache.get(resume_id) or self.service.get_resume_usage(resume_id, self.current_user_id)

        self.preview_workspace.load_resume(target, h_info, u_info)
        self.main_stack.setCurrentIndex(1)

    def _close_preview(self):
        self.main_stack.setCurrentIndex(0)

    # Actions: Default, Version, Edit, Archive, Delete, OS Viewer
    def _set_default(self, resume_id: int):
        target, err = self.service.set_default_resume(resume_id, self.current_user_id)
        if err:
            AppState().notify("danger", err)
        else:
            AppState().notify("success", f"'{target.name}' set as active default resume.")
            self.refresh()
            if self.main_stack.currentIndex() == 1:
                self._open_preview(resume_id)

    def _open_new_version_dialog(self, resume_id: int):
        target = next((r for r in self._all_resumes if r.id == resume_id), None)
        if not target:
            return

        dlg = ResumeVersionDialog(target, self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        AppState().notify("info", f"Processing new version v{data['version']} for '{target.name}'...")
        self._launch_worker(
            action="version",
            file_path=data["file_path"],
            version=data["version"],
            notes=data["notes"],
            is_default=data["is_default"],
            source_resume_id=resume_id,
        )

    def _open_edit_dialog(self, resume_id: int):
        target = next((r for r in self._all_resumes if r.id == resume_id), None)
        if not target:
            return

        # Available roles from active resumes
        roles = sorted(set(r.role_target for r in self._all_resumes if r.role_target))
        dlg = ResumeMetadataDialog(target, available_roles=roles, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        updated, err = self.service.update_resume(
            resume_id=resume_id,
            user_id=self.current_user_id,
            name=data["name"],
            role_target=data["role_target"],
            version=data["version"],
            is_default=data["is_default"],
        )
        if err:
            AppState().notify("danger", err)
        else:
            if data.get("notes") != target.notes:
                with get_db_session(self.service._session_factory) as s:
                    from app.repositories.resume_repository import ResumeRepository
                    r_db = ResumeRepository(s).get_by_id(resume_id)
                    if r_db:
                        r_db.notes = data["notes"]
                        s.commit()
            AppState().notify("success", f"Resume '{data['name']}' updated.")
            self.refresh()

    def _archive_resume(self, resume_id: int):
        target = next((r for r in self._all_resumes if r.id == resume_id), None)
        name = target.name if target else "this resume"

        confirm = QMessageBox.question(
            self,
            "Archive Resume",
            f"Archive '{name}'?\n\nIf this resume is currently default, the system will automatically promote the next active resume.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        ok, err = self.service.archive_resume(resume_id, self.current_user_id)
        if not ok:
            AppState().notify("danger", err or "Failed to archive resume.")
        else:
            AppState().notify("success", f"'{name}' archived.")
            self.refresh()
            if self.main_stack.currentIndex() == 1:
                self._close_preview()

    def _unarchive_resume(self, resume_id: int):
        ok, err = self.service.unarchive_resume(resume_id, self.current_user_id)
        if not ok:
            AppState().notify("danger", err or "Failed to restore resume.")
        else:
            AppState().notify("success", "Resume restored to active circulation.")
            self.refresh()

    def _delete_resume(self, resume_id: int):
        target = next((r for r in self._all_resumes if r.id == resume_id), None)
        name = target.name if target else "this resume"

        # Check references
        usage = self._usage_cache.get(resume_id, {})
        app_cnt = usage.get("total_applications", 0)
        if app_cnt > 0:
            QMessageBox.warning(
                self,
                "Cannot Delete Resume",
                f"'{name}' cannot be deleted because it is linked to {app_cnt} job application(s).\n\nYou can archive this resume instead.",
            )
            return

        confirm = QMessageBox.question(
            self,
            "Delete Resume",
            f"Are you sure you want to permanently delete '{name}' from the managed repository?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        ok, err = self.service.delete_resume(resume_id, self.current_user_id)
        if not ok:
            AppState().notify("danger", err or "Failed to delete resume.")
        else:
            AppState().notify("success", f"Resume '{name}' deleted.")
            self.refresh()
            if self.main_stack.currentIndex() == 1:
                self._close_preview()

    def _open_os_viewer(self, resume_id: int):
        ok, err = self.service.open_resume(resume_id, self.current_user_id)
        if not ok:
            AppState().notify("danger", err or "Failed to open system viewer.")
        else:
            AppState().notify("info", "Opening resume in system viewer...")

    def _on_upload_clicked(self):
        roles = sorted(set(r.role_target for r in self._all_resumes if r.role_target))
        dlg = UploadResumeDialog(available_roles=roles, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return

        data = dlg.get_data()
        AppState().notify("info", f"Analyzing and uploading resume '{data['name']}'...")
        self._launch_worker(
            action="upload",
            file_path=data["file_path"],
            display_name=data["name"],
            role_target=data["role_target"],
            version=data["version"],
            notes=data["notes"],
            is_default=data["is_default"],
        )

    def _launch_worker(
        self,
        action: str,
        file_path: str,
        display_name: Optional[str] = None,
        role_target: Optional[str] = None,
        version: str = "1.0",
        notes: Optional[str] = None,
        is_default: bool = False,
        source_resume_id: Optional[int] = None,
    ):
        """Runs the file upload/version extraction in a separate thread so UI does not stutter."""
        self.thread = QThread()
        self.worker = ResumeOperationWorker(
            service=self.service,
            user_id=self.current_user_id,
            action=action,
            file_path=file_path,
            display_name=display_name,
            role_target=role_target,
            version=version,
            notes=notes,
            is_default=is_default,
            source_resume_id=source_resume_id,
        )
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def _on_worker_finished(self, success: bool, message: str, resume_id: int = 0):
        level = "success" if success else "danger"
        AppState().notify(level, message)
        self.refresh()
        if success and resume_id > 0:
            if self.main_stack.currentIndex() == 1:
                # In preview mode: immediately display the new revision
                self._open_preview(resume_id)
            else:
                self._selected_resume_id = resume_id
