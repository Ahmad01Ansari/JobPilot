"""ATS-style interactive data grid for Jobs management with bulk selection, sorting, density, and persistence."""

from typing import List, Optional, Set
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from app.db.models import Job
from app.ui.theme import COLORS
from app.ui.widgets.status_badge import STATUS_DISPLAY_LABELS, StatusBadge


class StatusDropdownButton(QPushButton):
    """Interactive status pill button with a dropdown chevron for 1-click status transitions."""

    status_changed = Signal(str)  # target status string

    STATUS_OPTIONS = [
        ("SUBMITTED", "📄 Submitted", "success"),
        ("UNDER_REVIEW", "⏳ Under Review", "warning"),
        ("INTERVIEW", "🎯 Interview / Shortlisted", "purple"),
        ("OFFER", "🎉 Offer", "success"),
        ("REJECTED", "❌ Rejected", "danger"),
        ("WITHDRAWN", "↩️ Withdrawn", "neutral"),
        ("FAILED", "⚠️ Failed", "danger"),
        ("MANUAL_REQUIRED", "🖐️ Manual Check", "warning"),
        ("NOT_APPLIED", "⚪ Not Applied", "neutral"),
    ]

    def __init__(self, current_status: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_status = (current_status or "NOT_APPLIED").strip().upper()
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(115, 24)
        self.update_display(self.current_status)
        self.clicked.connect(self._show_menu)

    def update_display(self, status: str) -> None:
        self.current_status = (status or "NOT_APPLIED").strip().upper()
        display_label = STATUS_DISPLAY_LABELS.get(self.current_status, self.current_status.replace("_", " ").title())
        self.setText(f"{display_label} ▾")
        self.setToolTip(f"Current Status: {display_label}\nClick to change status (e.g. Failed → Submitted)")

        color_map = {
            "success": ("#34D399", "#064E3B", "#059669"),
            "warning": ("#FBBF24", "#451A03", "#D97706"),
            "danger": ("#F87171", "#450A0A", "#DC2626"),
            "primary": ("#FB923C", "#431407", "#EA580C"),
            "purple": ("#C084FC", "#2E1065", "#7C3AED"),
            "neutral": ("#9CA3AF", "#1F2937", "#374151"),
        }
        st = "neutral"
        if self.current_status in ["SUBMITTED", "OFFER", "COMPLETED", "READY", "QUALIFIED"]:
            st = "success"
        elif self.current_status in ["UNDER_REVIEW", "WARNING", "MANUAL_REQUIRED", "PENDING"]:
            st = "warning"
        elif self.current_status in ["SHORTLISTED", "RECRUITER_CONTACTED", "ACTIVE"]:
            st = "primary"
        elif self.current_status in ["ASSESSMENT", "INTERVIEW", "SCHEDULED"]:
            st = "purple"
        elif self.current_status in ["REJECTED", "FAILED", "OVERDUE", "CANCELLED"]:
            st = "danger"

        fg, bg, border = color_map.get(st, color_map["neutral"])
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {fg};
                border: 1px solid {border};
                border-radius: 12px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
                text-align: center;
            }}
            QPushButton:hover {{
                border-color: {fg};
                background-color: {border}40;
            }}
        """)

    def _show_menu(self) -> None:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary_hover']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 6px;
            }}
        """)

        hdr = menu.addAction("Change Application Status:")
        hdr.setEnabled(False)
        menu.addSeparator()

        for code, label, _ in self.STATUS_OPTIONS:
            act = menu.addAction(label)
            if code == self.current_status:
                act.setText(f"✓ {label}")
                act.setEnabled(False)
            act.triggered.connect(lambda _, c=code: self.status_changed.emit(c))

        menu.exec_(self.mapToGlobal(QPoint(0, self.height() + 2)))


def create_match_badge(score: Optional[int], decision: Optional[str]) -> QWidget:
    """Creates a stylized pill badge for qualification score and decision."""
    w = QWidget()
    w.setStyleSheet("background: transparent; border: none;")
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setAlignment(Qt.AlignCenter)

    lbl = QLabel()
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setFixedHeight(22)

    if score is None or not decision:
        lbl.setText("—")
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 500;")
        lbl.setToolTip("Not evaluated yet. Right-click or use panel to qualify.")
    else:
        dec = str(decision).upper()
        if "STRONG" in dec:
            bg = "rgba(34, 197, 94, 0.15)"
            color = "#22C55E"
            border = "rgba(34, 197, 94, 0.3)"
            txt = f"{score}% Strong"
        elif "GOOD" in dec:
            bg = "rgba(59, 130, 246, 0.15)"
            color = "#3B82F6"
            border = "rgba(59, 130, 246, 0.3)"
            txt = f"{score}% Good"
        elif "POSSIBLE" in dec:
            bg = "rgba(234, 179, 8, 0.15)"
            color = "#EAB308"
            border = "rgba(234, 179, 8, 0.3)"
            txt = f"{score}% Match"
        elif "WEAK" in dec:
            bg = "rgba(249, 115, 22, 0.15)"
            color = "#F97316"
            border = "rgba(249, 115, 22, 0.3)"
            txt = f"{score}% Weak"
        elif "REVIEW" in dec:
            bg = "rgba(168, 85, 247, 0.15)"
            color = "#A855F7"
            border = "rgba(168, 85, 247, 0.3)"
            txt = f"{score}% Review"
        else:
            bg = "rgba(239, 68, 68, 0.15)"
            color = "#EF4444"
            border = "rgba(239, 68, 68, 0.3)"
            txt = f"{score}% Rejected"

        lbl.setText(txt)
        lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {bg};
                color: {color};
                border: 1px solid {border};
                border-radius: 11px;
                padding: 1px 8px;
                font-size: 11px;
                font-weight: 700;
            }}
        """)
        lbl.setToolTip(f"Qualification Score: {score}/100\nDecision: {decision.replace('_', ' ').title()}")

    layout.addWidget(lbl)
    return w


class JobsHeaderView(QHeaderView):
    """ATS-style horizontal header with an integrated, natively drawn checkbox on section 0."""

    check_all_toggled = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(Qt.Horizontal, parent)
        self._is_checked = False
        self._is_partially_checked = False
        self.setSectionsClickable(True)

    def is_checked(self) -> bool:
        return self._is_checked

    def set_checked(self, checked: bool, partially: bool = False) -> None:
        if self._is_checked != checked or self._is_partially_checked != partially:
            self._is_checked = checked
            self._is_partially_checked = partially
            self.viewport().update()

    def paintSection(self, painter: QPainter, rect: QRect, logicalIndex: int) -> None:
        super().paintSection(painter, rect, logicalIndex)
        if logicalIndex == 0:
            opt = QStyleOptionButton()
            opt.state = QStyle.State_Enabled
            if self._is_checked:
                opt.state |= QStyle.State_On
            elif self._is_partially_checked:
                opt.state |= QStyle.State_NoChange
            else:
                opt.state |= QStyle.State_Off

            indicator_size = self.style().pixelMetric(QStyle.PM_IndicatorWidth)
            x = rect.x() + (rect.width() - indicator_size) // 2
            y = rect.y() + (rect.height() - indicator_size) // 2
            opt.rect = QRect(x, y, indicator_size, indicator_size)
            self.style().drawPrimitive(QStyle.PE_IndicatorCheckBox, opt, painter)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        col = self.logicalIndexAt(pos)
        if col == 0 and event.button() == Qt.LeftButton:
            new_checked = not (self._is_checked or self._is_partially_checked)
            self.set_checked(new_checked, False)
            self.check_all_toggled.emit(new_checked)
            event.accept()
            return
        super().mousePressEvent(event)


class CenteredCheckBoxDelegate(QStyledItemDelegate):
    """Item delegate that paints a centered checkbox in column 0, matching the header."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        if index.column() == 0:
            self.initStyleOption(option, index)
            style = option.widget.style() if option.widget else QApplication.style()
            style.drawPrimitive(QStyle.PE_PanelItemViewItem, option, painter, option.widget)

            opt = QStyleOptionButton()
            opt.state = QStyle.State_Enabled
            chk_state = index.data(Qt.CheckStateRole)
            if chk_state == Qt.Checked or chk_state == 2:
                opt.state |= QStyle.State_On
            else:
                opt.state |= QStyle.State_Off

            indicator_size = style.pixelMetric(QStyle.PM_IndicatorWidth)
            x = option.rect.x() + (option.rect.width() - indicator_size) // 2
            y = option.rect.y() + (option.rect.height() - indicator_size) // 2
            opt.rect = QRect(x, y, indicator_size, indicator_size)
            style.drawPrimitive(QStyle.PE_IndicatorCheckBox, opt, painter, option.widget)
        else:
            super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if index.column() == 0 and event.type() == event.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
            current = index.data(Qt.CheckStateRole)
            new_state = Qt.Unchecked if (current == Qt.Checked or current == 2) else Qt.Checked
            model.setData(index, new_state, Qt.CheckStateRole)
            return True
        return super().editorEvent(event, model, option, index)


class JobsTable(QTableWidget):
    """ATS-style data grid with checkboxes, sorting, density modes, tooltips, and badges."""

    job_selected = Signal(object)             # Job or None
    job_activated = Signal(object)            # Job (on Enter or double-click)
    sort_changed = Signal(str, str)           # sort_by, sort_order ('asc' | 'desc')
    bulk_selection_changed = Signal(list)     # List[Job]
    mark_junk_requested = Signal(list)        # List[Job]
    restore_junk_requested = Signal(list)     # List[Job]
    open_external_requested = Signal(list)    # List[Job]
    qualify_requested = Signal(list)          # List[Job]
    status_change_requested = Signal(object, str)  # (Job or List[Job], new_status)

    COLUMNS = [
        ("", None, False, QHeaderView.Fixed, 38),
        ("Job Title", "title", True, QHeaderView.Stretch, 200),
        ("Company", "company", True, QHeaderView.Interactive, 125),
        ("Platform", "platform", True, QHeaderView.Interactive, 80),
        ("Location", "location", True, QHeaderView.Interactive, 100),
        ("Experience", None, False, QHeaderView.Interactive, 85),
        ("Method", None, False, QHeaderView.Interactive, 85),
        ("Match", "match", True, QHeaderView.Interactive, 95),
        ("Status", "status", True, QHeaderView.Interactive, 120),
        ("Discovered", "first_seen_at", True, QHeaderView.Interactive, 90),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._jobs: List[Job] = []
        self._checked_job_ids: Set[int] = set()
        self._last_selected_job_id: Optional[int] = None
        self._current_sort_col = 1
        self._current_sort_order = "desc"
        self._density = "comfortable"
        self._is_junk_view = False

        self._setup_table()

    def _setup_table(self) -> None:
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels([col[0] for col in self.COLUMNS])

        self._header_view = JobsHeaderView(self)
        self._header_view.setToolTip("Select / Deselect all jobs")
        self.setHorizontalHeader(self._header_view)
        self._header_view.setMinimumSectionSize(36)
        self._header_view.setSortIndicatorShown(False)
        self._header_view.sectionClicked.connect(self._on_header_clicked)
        self._header_view.check_all_toggled.connect(self._on_check_all_toggled)

        self.setItemDelegateForColumn(0, CenteredCheckBoxDelegate(self))

        for idx, (name, sort_key, sortable, resize_mode, default_width) in enumerate(self.COLUMNS):
            self._header_view.setSectionResizeMode(idx, resize_mode)
            if default_width:
                self.setColumnWidth(idx, default_width)

        # Discovered column is hidden by default to keep grid clean
        self.setColumnHidden(9, True)

        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(46)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.SingleSelection)
        self.setAlternatingRowColors(True)

        self.itemSelectionChanged.connect(self._on_selection_changed)
        self.itemDoubleClicked.connect(self._on_double_clicked)
        self.itemClicked.connect(self._on_item_clicked)

        self.apply_theme()
        self._update_header_labels()

    def apply_theme(self) -> None:
        """Applies stylesheet conforming to active design tokens."""
        self.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                gridline-color: transparent;
                color: {COLORS['text']};
                outline: none;
            }}
            QTableWidget::item {{
                padding: {'6px 10px' if self._density == 'comfortable' else '3px 8px'};
                border-bottom: 1px solid {COLORS['border']}30;
            }}
            QTableWidget::item:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
            QHeaderView::section:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)

    def _on_check_all_toggled(self, checked: bool) -> None:
        """Handles the header checkbox being toggled — checks/unchecks all rows."""
        if checked:
            for job in self._jobs:
                self._checked_job_ids.add(job.id)
            for r in range(self.rowCount()):
                item = self.item(r, 0)
                if item:
                    item.setCheckState(Qt.Checked)
            self.bulk_selection_changed.emit(self.get_checked_jobs())
        else:
            self._checked_job_ids.clear()
            for r in range(self.rowCount()):
                item = self.item(r, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
            self.bulk_selection_changed.emit([])
        self._sync_header_checkbox()

    def _on_header_checkbox_toggled(self, state: int) -> None:
        """Backward-compatible handler for integer check states."""
        is_checked = (state == Qt.Checked.value if hasattr(Qt.Checked, 'value') else state == 2)
        self._on_check_all_toggled(is_checked)

    def _sync_header_checkbox(self) -> None:
        """Syncs the header checkbox state based on current row selections."""
        total = len(self._jobs)
        checked_count = len(self._checked_job_ids)
        if total > 0 and checked_count == total:
            self._header_view.set_checked(True, partially=False)
        elif 0 < checked_count < total:
            self._header_view.set_checked(False, partially=True)
        else:
            self._header_view.set_checked(False, partially=False)

    def set_density(self, density: str) -> None:
        """Sets row height and spacing density ('comfortable' vs 'compact')."""
        self._density = density
        if density == "compact":
            self.verticalHeader().setDefaultSectionSize(34)
        else:
            self.verticalHeader().setDefaultSectionSize(46)
        self.apply_theme()

    def set_jobs(self, jobs: List[Job]) -> None:
        """Populates the table with job records, preserving previous row selection if possible."""
        self._jobs = jobs
        self.setRowCount(len(jobs))

        row_to_reselect = -1

        for row, job in enumerate(jobs):
            if self._last_selected_job_id and job.id == self._last_selected_job_id:
                row_to_reselect = row

            # 0: Checkbox
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            chk_state = Qt.Checked if job.id in self._checked_job_ids else Qt.Unchecked
            chk_item.setCheckState(chk_state)
            chk_item.setTextAlignment(Qt.AlignCenter)
            self.setItem(row, 0, chk_item)

            # 1: Job Title
            t_item = QTableWidgetItem(job.title)
            t_item.setToolTip(f"{job.title}\nDouble-click to view full details")
            self.setItem(row, 1, t_item)

            # 2: Company
            c_item = QTableWidgetItem(job.company_raw)
            c_item.setToolTip(job.company_raw)
            self.setItem(row, 2, c_item)

            # 3: Platform
            p_item = QTableWidgetItem(job.platform.title())
            p_item.setTextAlignment(Qt.AlignCenter)
            p_item.setToolTip(f"Platform: {job.platform.title()}")
            self.setItem(row, 3, p_item)

            # 4: Location
            loc_text = job.location or "Unspecified"
            loc_item = QTableWidgetItem(loc_text)
            loc_item.setToolTip(loc_text)
            self.setItem(row, 4, loc_item)

            # 5: Experience
            exp_text = job.experience_text or (
                f"{job.required_experience_min or 0} Yrs" if job.required_experience_min else "-"
            )
            exp_item = QTableWidgetItem(exp_text)
            exp_item.setTextAlignment(Qt.AlignCenter)
            exp_item.setToolTip(f"Required Experience: {exp_text}")
            self.setItem(row, 5, exp_item)

            # 6: Method
            method_str = getattr(job, "application_method", "EASY_APPLY") or "EASY_APPLY"
            method_display = method_str.replace("_", " ").title()
            m_item = QTableWidgetItem(method_display)
            m_item.setTextAlignment(Qt.AlignCenter)
            m_item.setToolTip(f"Application Mode: {method_display}")
            self.setItem(row, 6, m_item)

            # 7: Match (Score & Decision)
            ev = None
            if hasattr(job, "evaluations") and job.evaluations:
                ev = sorted(
                    job.evaluations,
                    key=lambda e: getattr(e, "evaluated_at", None) or getattr(e, "created_at", None),
                    reverse=True,
                )[0]
            sc = ev.score if ev else None
            dec = ev.decision if ev else None
            self.setCellWidget(row, 7, create_match_badge(sc, dec))

            # 8: Status (Interactive 1-click status dropdown button)
            app_status = "NOT_APPLIED"
            try:
                if hasattr(job, "applications") and job.applications:
                    app_status = job.applications[0].status
            except Exception:
                app_status = "NOT_APPLIED"

            btn_status = StatusDropdownButton(app_status)
            btn_status.status_changed.connect(
                lambda new_st, j=job: self.status_change_requested.emit(j, new_st)
            )

            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent; border: none;")
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignCenter)
            status_layout.addWidget(btn_status)
            self.setCellWidget(row, 8, status_widget)

            # 9: Discovered
            disc_text = "-"
            if job.first_seen_at:
                disc_text = job.first_seen_at.strftime("%b %d, %Y")
            d_item = QTableWidgetItem(disc_text)
            d_item.setTextAlignment(Qt.AlignCenter)
            d_item.setToolTip(f"Discovered: {disc_text}")
            self.setItem(row, 9, d_item)

        # Restore selection or select first row
        if row_to_reselect >= 0:
            self.selectRow(row_to_reselect)
        elif self.rowCount() > 0:
            self.selectRow(0)
        else:
            self.job_selected.emit(None)

    def get_selected_job(self) -> Optional[Job]:
        """Returns the currently highlighted Job object, if any."""
        selected = self.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self._jobs):
            return self._jobs[row]
        return None

    def get_checked_jobs(self) -> List[Job]:
        """Returns list of Job objects whose checkbox is currently checked."""
        return [job for job in self._jobs if job.id in self._checked_job_ids]

    def clear_checked_jobs(self) -> None:
        """Unchecks all rows and resets checked IDs."""
        self._checked_job_ids.clear()
        for r in range(self.rowCount()):
            item = self.item(r, 0)
            if item:
                item.setCheckState(Qt.Unchecked)
        self._sync_header_checkbox()
        self.bulk_selection_changed.emit([])

    def update_job_evaluation(self, job_id: int, score: int, decision: str) -> None:
        """Dynamically updates the match badge for a specific job row."""
        for row, job in enumerate(self._jobs):
            if job.id == job_id:
                self.setCellWidget(row, 7, create_match_badge(score, decision))
                break

    def select_first_row(self) -> None:
        """Selects the first row if table is not empty."""
        if self.rowCount() > 0:
            self.selectRow(0)

    def _on_selection_changed(self) -> None:
        job = self.get_selected_job()
        if job:
            self._last_selected_job_id = job.id
        self.job_selected.emit(job)

    def _on_item_clicked(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            row = item.row()
            if 0 <= row < len(self._jobs):
                job = self._jobs[row]
                if item.checkState() == Qt.Checked:
                    self._checked_job_ids.add(job.id)
                else:
                    self._checked_job_ids.discard(job.id)
                self._sync_header_checkbox()
                self.bulk_selection_changed.emit(self.get_checked_jobs())

    def _on_double_clicked(self, item: QTableWidgetItem) -> None:
        job = self.get_selected_job()
        if job:
            self.job_activated.emit(job)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            job = self.get_selected_job()
            if job:
                self.job_activated.emit(job)
                return
        elif event.key() == Qt.Key_Space:
            # Toggle checkbox for currently selected row
            job = self.get_selected_job()
            if job:
                row = self.currentRow()
                item = self.item(row, 0)
                if item:
                    new_state = Qt.Unchecked if item.checkState() == Qt.Checked else Qt.Checked
                    item.setCheckState(new_state)
                    if new_state == Qt.Checked:
                        self._checked_job_ids.add(job.id)
                    else:
                        self._checked_job_ids.discard(job.id)
                    self._sync_header_checkbox()
                    self.bulk_selection_changed.emit(self.get_checked_jobs())
                    return
        super().keyPressEvent(event)

    def _on_header_clicked(self, col_idx: int) -> None:
        if col_idx == 0:
            current_all_checked = (
                len(self._checked_job_ids) == len(self._jobs) and len(self._jobs) > 0
            )
            self._on_check_all_toggled(not current_all_checked)
            return

        _, sort_key, sortable, _, _ = self.COLUMNS[col_idx]
        if not sortable or not sort_key:
            return

        if self._current_sort_col == col_idx:
            self._current_sort_order = "asc" if self._current_sort_order == "desc" else "desc"
        else:
            self._current_sort_col = col_idx
            self._current_sort_order = "asc"

        self._update_header_labels()
        self.sort_changed.emit(sort_key, self._current_sort_order)

    def _update_header_labels(self) -> None:
        for idx, (name, sort_key, sortable, _, _) in enumerate(self.COLUMNS):
            if idx == self._current_sort_col and sortable:
                arrow = " ▲" if self._current_sort_order == "asc" else " ▼"
                self.horizontalHeaderItem(idx).setText(f"{name}{arrow}")
            else:
                self.horizontalHeaderItem(idx).setText(name)

    def set_junk_view(self, is_junk: bool) -> None:
        """Sets whether the table is currently presenting junk items."""
        self._is_junk_view = is_junk

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Interactive context menu providing quick status changes, junking, and link copying."""
        row = self.rowAt(event.pos().y())
        if row < 0 or row >= len(self._jobs):
            return

        target_job = self._jobs[row]
        checked_jobs = self.get_checked_jobs()
        if target_job in checked_jobs and len(checked_jobs) > 1:
            selected_jobs = checked_jobs
        else:
            selected_jobs = [target_job]

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['primary_hover']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 8px;
            }}
        """)

        num_txt = f" ({len(selected_jobs)})" if len(selected_jobs) > 1 else ""

        if self._is_junk_view:
            act_restore = menu.addAction(f"↩ Restore to Active{num_txt}")
            act_restore.triggered.connect(lambda: self.restore_junk_requested.emit(selected_jobs))
        else:
            act_junk = menu.addAction(f"🗑 Move to Junk{num_txt}")
            act_junk.triggered.connect(lambda: self.mark_junk_requested.emit(selected_jobs))

        menu.addSeparator()
        menu_status = menu.addMenu(f"🔄 Change Status{num_txt}")
        for code, label, _ in StatusDropdownButton.STATUS_OPTIONS:
            act_s = menu_status.addAction(label)
            act_s.triggered.connect(lambda _, c=code: self.status_change_requested.emit(selected_jobs, c))

        act_qualify = menu.addAction(f"⚡ Qualify Candidate Fit{num_txt}")
        act_qualify.triggered.connect(lambda: self.qualify_requested.emit(selected_jobs))

        menu.addSeparator()

        if len(selected_jobs) == 1:
            job = selected_jobs[0]
            if job.listing_url:
                act_open = menu.addAction("↗ Open in Browser")
                act_open.triggered.connect(lambda: self.open_external_requested.emit([job]))

                act_copy = menu.addAction("📋 Copy Job URL")

                def copy_url():
                    from PySide6.QtWidgets import QApplication
                    QApplication.clipboard().setText(job.listing_url)

                act_copy.triggered.connect(copy_url)
        else:
            act_open = menu.addAction(f"↗ Open All URLs in Browser{num_txt}")
            act_open.triggered.connect(lambda: self.open_external_requested.emit(selected_jobs))

        menu.exec_(event.globalPos())
