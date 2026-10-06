"""Screening Q&A Knowledge Base view component.

Provides interactive viewing, searching, adding, editing, deleting,
and real-time question match testing for automated screening questions.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import QnAEntry
from app.services.qna_service import QnAService
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge


class QnAEntryDialog(QDialog):
    """Modal dialog for creating or editing a screening Q&A entry."""

    def __init__(
        self,
        entry: Optional[QnAEntry] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Q&A Entry" if entry else "Add Screening Q&A Entry")
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

        self.txt_question = QTextEdit()
        self.txt_question.setPlaceholderText("e.g. What is your notice period in days?")
        self.txt_question.setMaximumHeight(70)
        if entry:
            self.txt_question.setPlainText(entry.question_text)
        form.addRow("Question Prompt *", self.txt_question)

        self.txt_answer = QLineEdit()
        self.txt_answer.setPlaceholderText("e.g. 30")
        if entry:
            self.txt_answer.setText(entry.answer_text)
        form.addRow("Answer Value *", self.txt_answer)

        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["text", "numeric", "boolean", "choice"])
        if entry and entry.answer_type:
            idx = self.cmb_type.findText(entry.answer_type)
            if idx >= 0:
                self.cmb_type.setCurrentIndex(idx)
        form.addRow("Answer Type", self.cmb_type)

        self.cmb_category = QComboBox()
        self.cmb_category.setEditable(True)
        self.cmb_category.addItems([
            "notice_period",
            "salary",
            "experience",
            "work_auth",
            "background",
            "education",
            "location",
            "relocation",
            "skills",
            "custom",
            "general",
        ])
        if entry and entry.category:
            idx = self.cmb_category.findText(entry.category)
            if idx >= 0:
                self.cmb_category.setCurrentIndex(idx)
            else:
                self.cmb_category.setEditText(entry.category)
        form.addRow("Category", self.cmb_category)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["Universal", "LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"])
        if entry and entry.platform:
            idx = self.cmb_platform.findText(entry.platform.title())
            if idx >= 0:
                self.cmb_platform.setCurrentIndex(idx)
        form.addRow("Platform Target", self.cmb_platform)

        self.chk_active = QCheckBox("Active for automated answering")
        self.chk_active.setChecked(entry.is_active if entry else True)
        form.addRow("Status", self.chk_active)

        layout.addLayout(form)

        # Action buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.txt_question.toPlainText().strip():
            QMessageBox.warning(self, "Validation Error", "Question prompt is required.")
            return
        if not self.txt_answer.text().strip():
            QMessageBox.warning(self, "Validation Error", "Answer value is required.")
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        """Returns dialog form data."""
        plat = self.cmb_platform.currentText().strip().lower()
        return {
            "question": self.txt_question.toPlainText().strip(),
            "answer": self.txt_answer.text().strip(),
            "answer_type": self.cmb_type.currentText().strip().lower(),
            "category": self.cmb_category.currentText().strip().lower(),
            "platform": None if plat in ["universal", "all"] else plat,
            "is_active": self.chk_active.isChecked(),
        }


class QnATesterDialog(QDialog):
    """Modal dialog for testing real-time screening question resolution."""

    def __init__(self, service: QnAService, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service
        self.setWindowTitle("Screening Question Matcher Tester")
        self.setMinimumWidth(560)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLineEdit, QComboBox {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        desc = QLabel(
            "Test how JobPilot will answer an arbitrary screening question encountered during Easy Apply."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 12px;")
        layout.addWidget(desc)

        input_layout = QHBoxLayout()
        self.txt_test_question = QLineEdit()
        self.txt_test_question.setPlaceholderText("Type a question (e.g. 'How many years of experience in Python?')")
        self.txt_test_question.returnPressed.connect(self._run_test)

        self.cmb_platform = QComboBox()
        self.cmb_platform.addItems(["Universal", "LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"])

        btn_run = QPushButton("Test Match")
        btn_run.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_run.clicked.connect(self._run_test)

        input_layout.addWidget(self.txt_test_question, 1)
        input_layout.addWidget(self.cmb_platform)
        input_layout.addWidget(btn_run)
        layout.addLayout(input_layout)

        # Results Frame
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['background']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        res_layout = QVBoxLayout(self.result_frame)
        res_layout.setSpacing(8)

        self.lbl_match_badge = StatusBadge("Awaiting Query", variant="neutral")
        self.lbl_answer = QLabel("Answer will appear here...")
        self.lbl_answer.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_details = QLabel("Match details will appear here.")
        self.lbl_details.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        self.lbl_details.setWordWrap(True)

        res_layout.addWidget(self.lbl_match_badge, 0, Qt.AlignLeft)
        res_layout.addWidget(self.lbl_answer)
        res_layout.addWidget(self.lbl_details)
        layout.addWidget(self.result_frame)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignRight)

    def _run_test(self) -> None:
        q = self.txt_test_question.text().strip()
        if not q:
            return

        plat = self.cmb_platform.currentText().strip().lower()
        res = self.service.test_question_match(
            test_question=q,
            platform=None if plat == "universal" else plat,
        )

        if res.get("matched"):
            self.lbl_match_badge.update_style("success")
            self.lbl_match_badge.setText("Exact/Normalized Match Found")
            self.lbl_answer.setText(f"Answer: '{res['answer']}'")
            self.lbl_details.setText(
                f"Source: {res['source']}  |  Confidence: {res['confidence'] * 100:.0f}%  |  "
                f"Category: {res['category']}  |  Status: {res['validation_status']}  |  "
                f"Matched Prompt: '{res['question']}'"
            )
        else:
            self.lbl_match_badge.update_style("warning")
            self.lbl_match_badge.setText("No Knowledge Base Match")
            self.lbl_answer.setText("No direct match found.")
            self.lbl_details.setText(
                f"{res.get('message', '')}  (Normalized query: '{res.get('normalized_query', '')}')"
            )


class QnAView(QWidget):
    """Main screening Q&A knowledge base view."""

    def __init__(self, service: Optional[QnAService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service or QnAService()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header & Actions
        self.header = PageHeader(
            title="Screening Q&A Knowledge Base",
            subtitle="Manage screening questions, verified answers, and verify automated bot response rules.",
        )

        self.btn_test = QPushButton("Test Matcher")
        self.btn_test.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['accent']}60;
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_test.clicked.connect(self._on_test_clicked)

        self.btn_add = QPushButton("+ Add Q&A Entry")
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 600;
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
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 12px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)

        self.btn_sync_profile = QPushButton("Sync Profile")
        self.btn_sync_profile.setToolTip("Re-evaluates salary, notice period, and location answers based on latest profile details")
        self.btn_sync_profile.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['border']};
                padding: 7px 12px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
            }}
        """)
        self.btn_sync_profile.clicked.connect(self._on_sync_profile_clicked)

        self.btn_seed_canonical = QPushButton("Seed Bank")
        self.btn_seed_canonical.setToolTip("Hydrates Q&A bank with 100+ canonical screening questions from catalog")
        self.btn_seed_canonical.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 12px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_seed_canonical.clicked.connect(self._on_seed_canonical_clicked)

        self.header.add_action_widget(self.btn_test)
        self.header.add_action_widget(self.btn_sync_profile)
        self.header.add_action_widget(self.btn_seed_canonical)
        self.header.add_action_widget(self.btn_add)
        self.header.add_action_widget(self.btn_refresh)
        layout.addWidget(self.header)

        # 2. Notification Banner
        self.notification_bar = NotificationBar(self)
        layout.addWidget(self.notification_bar)

        # 3. Stats & Filter Toolbar
        filter_card = QFrame(self)
        filter_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(12)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filter questions or answers...")
        self.txt_search.textChanged.connect(self.refresh)
        filter_layout.addWidget(self.txt_search, 1)

        self.cmb_category_filter = QComboBox()
        self.cmb_category_filter.addItems([
            "All Categories",
            "notice_period",
            "salary",
            "experience",
            "work_auth",
            "background",
            "education",
            "skills",
            "custom",
            "general",
        ])
        self.cmb_category_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.cmb_category_filter)

        self.cmb_platform_filter = QComboBox()
        self.cmb_platform_filter.addItems(["All Platforms", "Universal", "LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"])
        self.cmb_platform_filter.currentIndexChanged.connect(self.refresh)
        filter_layout.addWidget(self.cmb_platform_filter)

        self.chk_active_only = QCheckBox("Active Only")
        self.chk_active_only.stateChanged.connect(self.refresh)
        filter_layout.addWidget(self.chk_active_only)

        self.lbl_stats = QLabel("0 entries")
        self.lbl_stats.setStyleSheet(f"color: {COLORS['text_muted']}; font-weight: 600;")
        filter_layout.addWidget(self.lbl_stats)

        layout.addWidget(filter_card)

        # 4. Table Widget
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Question Prompt",
            "Answer",
            "Type",
            "Category",
            "Platform",
            "Status",
            "Actions",
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 220)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 90)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 120)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 100)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Fixed)
        self.table.setColumnWidth(5, 145)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Fixed)
        self.table.setColumnWidth(6, 185)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)

        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                alternate-background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
                gridline-color: {COLORS['border']};
                color: {COLORS['text']};
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 10px 8px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
            }}
        """)
        layout.addWidget(self.table, 1)

    # ----------------------------------------------------------------------
    # Data Loading & Rendering
    # ----------------------------------------------------------------------

    def refresh(self) -> None:
        """Loads entries from service applying current search and category filters."""
        query = self.txt_search.text().strip()
        cat_filter = self.cmb_category_filter.currentText()
        category = None if cat_filter == "All Categories" else cat_filter

        plat_filter = self.cmb_platform_filter.currentText().lower()
        platform = None if plat_filter in ["all platforms", "universal"] else plat_filter

        active_only = self.chk_active_only.isChecked()

        entries = self.service.list_entries(
            category=category,
            search=query if query else None,
            platform=platform,
            only_active=active_only,
        )

        self.table.setRowCount(len(entries))
        self.lbl_stats.setText(f"{len(entries)} entries")

        for row, entry in enumerate(entries):
            # 0: Question Prompt
            q_item = QTableWidgetItem(entry.question_text)
            q_item.setToolTip(entry.question_text)
            q_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 0, q_item)

            # 1: Answer Value
            disp_ans = entry.answer_text if len(entry.answer_text) <= 55 else f"{entry.answer_text[:52]}..."
            a_item = QTableWidgetItem(disp_ans)
            a_item.setToolTip(entry.answer_text)
            a_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(row, 1, a_item)

            # 2: Type
            t_item = QTableWidgetItem((entry.answer_type or "text").upper())
            t_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, t_item)

            # 3: Category
            c_item = QTableWidgetItem((entry.category or "general").replace("_", " ").title())
            c_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, c_item)

            # 4: Platform
            p_item = QTableWidgetItem((entry.platform or "Universal").title())
            p_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 4, p_item)

            # 5: Status Badge
            status_widget = QWidget()
            status_widget.setStyleSheet("background: transparent; border: none;")
            status_layout = QHBoxLayout(status_widget)
            status_layout.setContentsMargins(0, 0, 0, 0)
            status_layout.setAlignment(Qt.AlignCenter)
            badge_variant = "success" if entry.validation_status == "VERIFIED" else "warning"
            badge = StatusBadge(entry.validation_status, variant=badge_variant, width=104, height=24)
            status_layout.addWidget(badge)
            self.table.setCellWidget(row, 5, status_widget)

            # 6: Action Buttons (Toggle Active, Edit, Delete)
            action_widget = QWidget()
            action_widget.setStyleSheet("background: transparent; border: none;")
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(6, 2, 6, 2)
            action_layout.setSpacing(6)
            action_layout.setAlignment(Qt.AlignCenter)

            # Active toggle button
            btn_toggle = QPushButton("Active" if entry.is_active else "Disabled")
            btn_toggle.setFixedWidth(64)
            btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: {'#064e3b' if entry.is_active else COLORS['surface_alt']};
                    color: {'#34d399' if entry.is_active else COLORS['text_muted']};
                    border: 1px solid {COLORS['border']};
                    font-size: 11px;
                    padding: 3px 6px;
                    border-radius: 4px;
                }}
            """)
            btn_toggle.clicked.connect(lambda _, eid=entry.id: self._on_toggle_clicked(eid))
            action_layout.addWidget(btn_toggle)

            # Edit button
            btn_edit = QPushButton("Edit")
            btn_edit.setFixedWidth(46)
            btn_edit.setStyleSheet(f"""
                QPushButton {{
                    background-color: {COLORS['surface']};
                    color: {COLORS['text']};
                    border: 1px solid {COLORS['border']};
                    font-size: 11px;
                    padding: 3px 6px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    border-color: {COLORS['accent']};
                }}
            """)
            btn_edit.clicked.connect(lambda _, e=entry: self._on_edit_clicked(e))
            action_layout.addWidget(btn_edit)

            # Delete button
            btn_del = QPushButton("✕")
            btn_del.setFixedSize(26, 24)
            btn_del.setToolTip("Delete Entry")
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['danger']};
                    border: none;
                    font-size: 13px;
                    font-weight: bold;
                    padding: 2px 4px;
                }}
                QPushButton:hover {{
                    background-color: #7f1d1d40;
                    border-radius: 4px;
                }}
            """)
            btn_del.clicked.connect(lambda _, eid=entry.id: self._on_delete_clicked(eid))
            action_layout.addWidget(btn_del)

            self.table.setCellWidget(row, 6, action_widget)

    def _on_add_clicked(self) -> None:
        dialog = QnAEntryDialog(parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            entry, err = self.service.add_entry(
                question=data["question"],
                answer=data["answer"],
                category=data["category"],
                answer_type=data["answer_type"],
                platform=data["platform"],
            )
            if entry:
                self.notification_bar.show_message("success", "Screening Q&A entry created successfully!")
                self.refresh()
            else:
                self.notification_bar.show_message("danger", f"Failed to add entry: {err}")

    def _on_edit_clicked(self, entry: QnAEntry) -> None:
        dialog = QnAEntryDialog(entry=entry, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            updated, err = self.service.update_entry(
                entry_id=entry.id,
                question=data["question"],
                answer=data["answer"],
                category=data["category"],
                answer_type=data["answer_type"],
                platform=data["platform"],
                is_active=data["is_active"],
            )
            if updated:
                self.notification_bar.show_message("success", "Screening Q&A entry updated!")
                self.refresh()
            else:
                self.notification_bar.show_message("danger", f"Failed to update: {err}")

    def _on_toggle_clicked(self, entry_id: int) -> None:
        new_state, err = self.service.toggle_active(entry_id)
        if err:
            self.notification_bar.show_message("danger", f"Failed to toggle: {err}")
        else:
            state_text = "enabled" if new_state else "disabled"
            self.notification_bar.show_message("info", f"Q&A entry {state_text}.")
            self.refresh()

    def _on_delete_clicked(self, entry_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            "Are you sure you want to delete this screening question and answer?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            success, err = self.service.delete_entry(entry_id)
            if success:
                self.notification_bar.show_message("info", "Screening Q&A entry deleted.")
                self.refresh()
            else:
                self.notification_bar.show_message("danger", f"Delete failed: {err}")

    def _on_test_clicked(self) -> None:
        dialog = QnATesterDialog(service=self.service, parent=self)
        dialog.exec()

    def _on_sync_profile_clicked(self) -> None:
        try:
            updated = self.service.resync_profile_answers(user_id=1)
            self.notification_bar.show_message("success", f"Successfully synced {updated} profile answers (CTC, notice period, location)!")
            self.refresh()
        except Exception as exc:
            self.notification_bar.show_message("danger", f"Profile sync failed: {exc}")

    def _on_seed_canonical_clicked(self) -> None:
        reply = QMessageBox.question(
            self,
            "Seed Canonical Question Catalog",
            "This will populate your Q&A knowledge base with 100+ standard screening questions personalized to your profile. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            try:
                created, updated = self.service.seed_canonical_bank(user_id=1, force=False)
                self.notification_bar.show_message("success", f"Canonical bank seeded! {created} entries created, {updated} updated.")
                self.refresh()
            except Exception as exc:
                self.notification_bar.show_message("danger", f"Failed to seed canonical bank: {exc}")
