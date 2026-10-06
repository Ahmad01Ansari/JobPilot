"""Follow-ups and recruiter reminders view component.

Provides smart queues for outreach reminders, due date inspection, derived overdue indicators,
one-click completion, and reschedule/cancellation actions.
"""

from datetime import datetime
from typing import List, Optional

from PySide6.QtCore import QDateTime, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.base import utc_now
from app.db.models import Application, FollowUp
from app.services.application_service import ApplicationService
from app.services.recruitment_service import RecruitmentService
from app.services.search.search_result import NavigationAction, NavigationRequest
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge
from app.utils_time import format_local_datetime


class AddFollowUpDialog(QDialog):
    """Modern modal for scheduling a follow-up reminder."""

    def __init__(
        self,
        service: RecruitmentService,
        app_service: ApplicationService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service
        self.app_service = app_service
        self.setWindowTitle("Schedule Recruiter Follow-Up")
        self.setMinimumWidth(540)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-weight: 500;
            }}
            QLineEdit, QTextEdit, QComboBox, QDateTimeEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {{
                border-color: {COLORS['accent']};
            }}
            QComboBox::drop-down, QDateTimeEdit::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 26px;
                border-left: 1px solid {COLORS['border']};
            }}
            QComboBox QAbstractItemView {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 6px;
                padding: 4px;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                min-height: 60px;
            }}
            QCalendarWidget {{
                background-color: #161B22;
                color: #F0F6FC;
                border: 1px solid #262C36;
                border-radius: 8px;
            }}
            QCalendarWidget QWidget#qt_calendar_navigationbar {{
                background-color: #0F1117;
                border-bottom: 1px solid #262C36;
            }}
            QCalendarWidget QToolButton {{
                color: #F0F6FC;
                background-color: transparent;
                border: none;
                font-weight: bold;
                padding: 4px;
            }}
            QCalendarWidget QToolButton:hover {{
                background-color: #262C36;
                border-radius: 4px;
            }}
            QCalendarWidget QMenu {{
                background-color: #161B22;
                color: #F0F6FC;
            }}
            QCalendarWidget QSpinBox {{
                background-color: #0F1117;
                color: #F0F6FC;
            }}
            QCalendarWidget QTableView {{
                background-color: #161B22;
                selection-background-color: #FF5F15;
                selection-color: #FFFFFF;
                alternate-background-color: #1F242C;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(16)

        # 1. Header Card
        hdr_card = QFrame()
        hdr_card.setStyleSheet("""
            QFrame {{
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 8px;
                padding: 12px 14px;
            }}
        """)
        hdr_layout = QVBoxLayout(hdr_card)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(4)

        lbl_hdr_title = QLabel("🔔  Schedule Recruiter Follow-Up")
        lbl_hdr_title.setStyleSheet("color: #FF7A3D; font-size: 14px; font-weight: 700; background: transparent; border: none;")
        hdr_layout.addWidget(lbl_hdr_title)

        lbl_hdr_sub = QLabel("Set a targeted reminder date and log outreach notes to ensure no opportunity goes cold.")
        lbl_hdr_sub.setStyleSheet("color: #8B949E; font-size: 11px; background: transparent; border: none;")
        lbl_hdr_sub.setWordWrap(True)
        hdr_layout.addWidget(lbl_hdr_sub)

        layout.addWidget(hdr_card)

        # 2. Form Inputs Card
        form_card = QFrame()
        form_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        form_layout = QFormLayout(form_card)
        form_layout.setSpacing(14)
        form_layout.setLabelAlignment(Qt.AlignLeft)

        # Search filter + Application Combo
        app_box = QWidget()
        app_layout = QVBoxLayout(app_box)
        app_layout.setContentsMargins(0, 0, 0, 0)
        app_layout.setSpacing(6)

        self.txt_app_filter = QLineEdit()
        self.txt_app_filter.setPlaceholderText("🔍  Type to search company or role...")
        self.txt_app_filter.textChanged.connect(self._filter_applications)
        app_layout.addWidget(self.txt_app_filter)

        self.cmb_apps = QComboBox()
        self.applications = self.app_service.list_applications(limit=200)
        self._all_app_items = []
        for app in self.applications:
            job = app.job
            title = f"{job.company_raw if job else 'Unknown'} — {job.title if job else ''} (ID: #{app.id})"
            self._all_app_items.append((title, app.id))
            self.cmb_apps.addItem(title, app.id)
        app_layout.addWidget(self.cmb_apps)

        form_layout.addRow("Application *", app_box)

        # Due Date & Time
        self.dt_due = QDateTimeEdit(QDateTime.currentDateTime().addDays(3))
        self.dt_due.setCalendarPopup(True)
        self.dt_due.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        form_layout.addRow("Due Date && Time *", self.dt_due)

        # Recruiter contact
        self.txt_contact = QLineEdit()
        self.txt_contact.setPlaceholderText("Recruiter name, email, or LinkedIn URL...")
        form_layout.addRow("Recruiter Contact", self.txt_contact)

        # Notes & Goal
        self.txt_notes = QTextEdit()
        self.txt_notes.setPlaceholderText("e.g. Inquire about application status, follow up on take-home test, or ping on LinkedIn...")
        self.txt_notes.setMinimumHeight(85)
        self.txt_notes.setMaximumHeight(120)
        form_layout.addRow("Outreach Goal / Notes", self.txt_notes)

        layout.addWidget(form_card)

        lbl_hint = QLabel("💡 A reminder badge will highlight on your dashboard and Follow-ups tracker when due.")
        lbl_hint.setStyleSheet("color: #8B949E; font-size: 11px; font-weight: 500;")
        layout.addWidget(lbl_hint)

        # 3. Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['border_light']};
                color: {COLORS['text']};
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_save = QPushButton("Save Reminder")
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save.clicked.connect(self._validate_and_save)
        btn_layout.addWidget(btn_save)

        layout.addLayout(btn_layout)

    def _filter_applications(self, text: str) -> None:
        filter_text = text.strip().lower()
        current_data = self.cmb_apps.currentData()
        self.cmb_apps.clear()
        for title, app_id in self._all_app_items:
            if not filter_text or filter_text in title.lower():
                self.cmb_apps.addItem(title, app_id)
        idx = self.cmb_apps.findData(current_data)
        if idx >= 0:
            self.cmb_apps.setCurrentIndex(idx)

    def _validate_and_save(self) -> None:
        if self.cmb_apps.count() == 0:
            QMessageBox.warning(self, "No Applications", "Please select a target application.")
            return

        app_id = self.cmb_apps.currentData()
        dt = self.dt_due.dateTime().toPython()
        notes = self.txt_notes.toPlainText().strip() or None

        contact_id = None
        c_name = self.txt_contact.text().strip()
        if c_name:
            contact = self.service.get_or_create_contact(name=c_name)
            contact_id = contact.id

        fu, err = self.service.create_follow_up(
            due_at=dt,
            application_id=app_id,
            contact_id=contact_id,
            notes=notes,
        )

        if fu:
            self.accept()
        else:
            QMessageBox.warning(self, "Error Scheduling Follow-Up", f"Failed: {err}")


class FollowupsView(QWidget):
    """Recruiter follow-up reminders view."""

    data_updated = Signal(str)

    def __init__(
        self,
        service: Optional[RecruitmentService] = None,
        app_service: Optional[ApplicationService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or RecruitmentService()
        self.app_service = app_service or ApplicationService()
        self._current_follow_ups: List[FollowUp] = []
        self._pending_navigation_request: Optional[NavigationRequest] = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header
        self.header = PageHeader(
            title="Follow-ups & Reminders",
            subtitle="Schedule and track outreach cadences, recruiter check-ins, and post-interview messages.",
        )

        self.btn_add = QPushButton("+ Add Reminder")
        self.btn_add.setMinimumHeight(34)
        self.btn_add.setMinimumWidth(140)
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 700;
                font-size: 12px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_add.clicked.connect(self._on_add_clicked)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(34)
        self.btn_refresh.setMinimumWidth(80)
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
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
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)

        self.header.add_action_widget(self.btn_add)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # 2. Notification Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Metric Cards Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(14)

        self.lbl_pending = self._create_metric_widget("Pending Reminders", "0", "#38bdf8", target_tab=0)
        self.lbl_overdue = self._create_metric_widget("Overdue Follow-ups", "0", "#f87171", target_tab=0)
        self.lbl_interviews = self._create_metric_widget("Upcoming Interviews", "0", "#34d399", target_tab=3)

        metrics_layout.addWidget(self.lbl_pending)
        metrics_layout.addWidget(self.lbl_overdue)
        metrics_layout.addWidget(self.lbl_interviews)
        main_layout.addLayout(metrics_layout)

        # 4. Filter Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(QWidget(), "Pending Reminders")
        self.tabs.addTab(QWidget(), "Completed")
        self.tabs.addTab(QWidget(), "Cancelled")
        self.tabs.addTab(QWidget(), "All")
        self.tabs.currentChanged.connect(self.refresh)
        main_layout.addWidget(self.tabs)

        # 5. Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Company & Role",
            "Due Date",
            "Recruiter",
            "Notes / Goal",
            "Status",
            "Actions",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 195)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Fixed)
        self.table.setColumnWidth(1, 160)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 115)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 140)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 195)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setAutoScroll(False)
        self.table.setWordWrap(False)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                gridline-color: transparent;
                color: {COLORS['text']};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 4px 6px;
                border-bottom: 1px solid {COLORS['border']}40;
            }}
            QTableWidget::item:hover {{
                background-color: #262C36;
                color: #FFFFFF;
            }}
            QTableWidget::item:selected {{
                background-color: #262C36;
                color: #FFFFFF;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 8px 6px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        main_layout.addWidget(self.table, 1)

    def _create_metric_widget(
        self,
        title: str,
        value: str,
        color_hex: str,
        target_tab: Optional[int] = None,
    ) -> QWidget:
        box = QWidget()
        box.setCursor(Qt.PointingHandCursor)
        box.setToolTip(f"Click to filter by {title}")
        box.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-top: 3px solid {color_hex};
                border-radius: 8px;
            }}
            QWidget:hover {{
                border-color: {color_hex};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(14, 10, 14, 10)
        box_layout.setSpacing(4)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet(f"font-size: 22px; font-weight: 800; color: {color_hex}; border: none; background: transparent;")
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; border: none; background: transparent;")

        box_layout.addWidget(lbl_val)
        box_layout.addWidget(lbl_title)

        if target_tab is not None:
            box.mousePressEvent = lambda e, t=target_tab: self._on_metric_card_clicked(t)
        return box

    def _on_metric_card_clicked(self, target_tab: int) -> None:
        """Toggles active tab when a follow-up metric card is clicked."""
        if self.tabs.currentIndex() == target_tab:
            self.tabs.setCurrentIndex(3)  # Toggle back to 'All'
        else:
            self.tabs.setCurrentIndex(target_tab)

    def refresh(self) -> None:
        """Reloads follow-up reminders and metrics."""
        metrics = self.service.get_metrics()
        self._update_metric(self.lbl_pending, metrics.get("pending_follow_ups", 0))
        self._update_metric(self.lbl_overdue, metrics.get("overdue_follow_ups", 0))
        self._update_metric(self.lbl_interviews, metrics.get("upcoming_interviews", 0))

        # Determine filter from active tab
        tab_map = {0: "PENDING", 1: "COMPLETED", 2: "CANCELLED", 3: None}
        status_filter = tab_map.get(self.tabs.currentIndex())

        self._current_follow_ups = self.service.list_follow_ups(status=status_filter, limit=100)
        self.table.clearContents()
        self.table.setRowCount(len(self._current_follow_ups))

        now = utc_now()
        for row, fu in enumerate(self._current_follow_ups):
            app = fu.application
            job = app.job if app else None

            # 0. Target
            comp_role = f"{job.company_raw if job else 'Unknown'} — {job.title if job else ''}"
            c_item = QTableWidgetItem(comp_role)
            c_item.setToolTip(comp_role)
            self.table.setItem(row, 0, c_item)

            # 1. Due Date
            due_str = format_local_datetime(fu.due_at, "%Y-%m-%d %I:%M %p") if fu.due_at else "-"
            d_item = QTableWidgetItem(due_str)
            d_item.setTextAlignment(Qt.AlignCenter)
            d_item.setToolTip(due_str)
            self.table.setItem(row, 1, d_item)

            # 2. Contact
            contact_str = fu.contact.name if fu.contact else "-"
            self.table.setItem(row, 2, QTableWidgetItem(contact_str))

            # 3. Notes
            self.table.setItem(row, 3, QTableWidgetItem(fu.notes or "-"))

            # 4. Status (with dynamic OVERDUE detection)
            is_overdue = (fu.status == "PENDING" and fu.due_at and fu.due_at < now)
            display_status = "OVERDUE" if is_overdue else fu.status

            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent; border: none;")
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignCenter)
            status_layout.addWidget(StatusBadge(display_status))
            self.table.setCellWidget(row, 4, status_widget)

            # 5. Actions (Complete / Cancel)
            act_widget = QWidget()
            act_widget.setStyleSheet("background: transparent; border: none;")
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(2, 2, 2, 2)
            act_layout.setSpacing(8)
            act_layout.setAlignment(Qt.AlignCenter)

            if fu.status == "PENDING":
                btn_done = QPushButton("✓ Done")
                btn_done.setFixedSize(80, 26)
                btn_done.setCursor(Qt.PointingHandCursor)
                btn_done.setToolTip("Mark follow-up completed")
                btn_done.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #064E3B;
                        color: #34D399;
                        border: 1px solid #059669;
                        font-size: 11px;
                        font-weight: 700;
                        border-radius: 4px;
                        padding: 0 6px;
                    }}
                    QPushButton:hover {{
                        background-color: #047857;
                        color: white;
                    }}
                """)
                btn_done.clicked.connect(lambda _, fid=fu.id: self._on_complete_clicked(fid))
                act_layout.addWidget(btn_done)

                btn_cancel = QPushButton("Cancel")
                btn_cancel.setFixedSize(72, 26)
                btn_cancel.setCursor(Qt.PointingHandCursor)
                btn_cancel.setToolTip("Cancel this follow-up reminder")
                btn_cancel.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS['surface_alt']};
                        color: {COLORS['text_muted']};
                        border: 1px solid {COLORS['border']};
                        font-size: 11px;
                        font-weight: 600;
                        border-radius: 4px;
                        padding: 0 6px;
                    }}
                    QPushButton:hover {{
                        border-color: #EF4444;
                        color: #EF4444;
                    }}
                """)
                btn_cancel.clicked.connect(lambda _, fid=fu.id: self._on_cancel_clicked(fid))
                act_layout.addWidget(btn_cancel)
            else:
                lbl_done = QLabel(fu.status.title())
                lbl_done.setAlignment(Qt.AlignCenter)
                lbl_done.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 11px; font-weight: 600;")
                act_layout.addWidget(lbl_done)

            self.table.setCellWidget(row, 5, act_widget)

        self.table.horizontalScrollBar().setValue(0)

        if self._pending_navigation_request:
            req = self._pending_navigation_request
            self._pending_navigation_request = None
            self.handle_navigation_request(req)

    def arm_navigation_request(self, request: NavigationRequest) -> None:
        """Stores request to be applied safely during or after refresh."""
        self._pending_navigation_request = request

    def handle_navigation_request(self, request: NavigationRequest) -> None:
        """Applies navigation request without destroying table state."""
        if request.entity_type != "followup":
            return
        if request.action == NavigationAction.OPEN:
            self.open_record(request.entity_id)
        else:
            self.focus_record(request.entity_id)

    def focus_record(self, follow_up_id: int) -> bool:
        """Finds row for follow_up_id, selects and scrolls to it without breaking tab filters."""
        for row, fu in enumerate(self._current_follow_ups):
            if fu.id == follow_up_id:
                self.table.selectRow(row)
                item = self.table.item(row, 0)
                if item:
                    self.table.scrollToItem(item)
                return True
        # If not visible in current tab, switch to All (tab index 3)
        if self.tabs.currentIndex() != 3:
            self.tabs.setCurrentIndex(3)
            for row, fu in enumerate(self._current_follow_ups):
                if fu.id == follow_up_id:
                    self.table.selectRow(row)
                    item = self.table.item(row, 0)
                    if item:
                        self.table.scrollToItem(item)
                    return True
        return False

    def open_record(self, follow_up_id: int) -> bool:
        return self.focus_record(follow_up_id)

    def _update_metric(self, widget: QWidget, val: int) -> None:
        lbl = widget.findChild(QLabel)
        if lbl:
            lbl.setText(str(val))

    def _on_add_clicked(self) -> None:
        dialog = AddFollowUpDialog(service=self.service, app_service=self.app_service, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.notification_bar.show_message("success", "Follow-up reminder scheduled.")
            self.refresh()
            self.data_updated.emit("followups")

    def _on_complete_clicked(self, follow_up_id: int) -> None:
        fu, err = self.service.complete_follow_up(follow_up_id, status="COMPLETED")
        if fu:
            self.notification_bar.show_message("success", "Follow-up marked as completed.")
            self.refresh()
            self.data_updated.emit("followups")
        else:
            self.notification_bar.show_message("danger", f"Failed: {err}")

    def _on_cancel_clicked(self, follow_up_id: int) -> None:
        fu, err = self.service.complete_follow_up(follow_up_id, status="CANCELLED")
        if fu:
            self.notification_bar.show_message("info", "Follow-up reminder cancelled.")
            self.refresh()
            self.data_updated.emit("followups")
        else:
            self.notification_bar.show_message("danger", f"Failed: {err}")

    def highlight_follow_up(self, follow_up_id: int) -> None:
        """Switches to Pending tab, refreshes, and selects the row for follow_up_id."""
        self.tabs.setCurrentIndex(0)
        self.refresh()
        for row, fu in enumerate(getattr(self, "_current_follow_ups", [])):
            if fu.id == follow_up_id:
                self.table.selectRow(row)
                break
