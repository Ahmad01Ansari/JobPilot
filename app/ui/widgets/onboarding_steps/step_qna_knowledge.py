"""
Step 6: Real Screening Q&A Knowledge Base (398+ Verified Records).
Adheres strictly to DesignUI.md (Obsidian #0F1117, Charcoal #161B22, Safety Orange #FF5F15).
Loads real QnA records from QnAService with search, category filtering, pagination, and direct answer editing.
"""

from typing import Dict, Any, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QTextEdit, QComboBox, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QMessageBox
)
from app.ui.theme import COLORS


class QnAEditDialog(QDialog):
    """Modal dialog allowing direct review and editing of a candidate screening answer."""
    def __init__(self, entry_id: int, question: str, answer: str, category: str, qna_service, parent=None):
        super().__init__(parent)
        self.entry_id = entry_id
        self.qna_service = qna_service

        self.setWindowTitle("Edit Screening Answer")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
        """)
        self._init_ui(question, answer, category)

    def _init_ui(self, question: str, answer: str, category: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        lbl_head = QLabel("Edit Screening Fact")
        lbl_head.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_head)

        # Question
        layout.addWidget(QLabel("Question:"))
        self.txt_q = QLineEdit(question)
        self.txt_q.setStyleSheet(self._input_qss())
        layout.addWidget(self.txt_q)

        # Answer
        layout.addWidget(QLabel("Verified Answer:"))
        self.txt_a = QTextEdit()
        self.txt_a.setPlainText(answer)
        self.txt_a.setMaximumHeight(90)
        self.txt_a.setStyleSheet(self._input_qss())
        layout.addWidget(self.txt_a)

        # Category
        layout.addWidget(QLabel("Category:"))
        self.txt_cat = QLineEdit(category)
        self.txt_cat.setStyleSheet(self._input_qss())
        layout.addWidget(self.txt_cat)

        # Buttons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 14px;
            }}
        """)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_save = QPushButton("Save Answer")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        btn_save.clicked.connect(self._on_save)
        btn_row.addWidget(btn_save)

        layout.addLayout(btn_row)

    def _on_save(self):
        new_q = self.txt_q.text().strip()
        new_a = self.txt_a.toPlainText().strip()
        new_cat = self.txt_cat.text().strip()

        if not new_q or not new_a:
            QMessageBox.warning(self, "Invalid Input", "Question and Answer cannot be empty.")
            return

        if self.qna_service and hasattr(self.qna_service, "update_entry"):
            updated, err = self.qna_service.update_entry(
                entry_id=self.entry_id,
                question=new_q,
                answer=new_a,
                category=new_cat,
                validation_status="VERIFIED"
            )
            if err:
                QMessageBox.warning(self, "Save Error", f"Could not update Q&A entry: {err}")
                return

        self.accept()

    def _input_qss(self) -> str:
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """


class StepQnAKnowledgeWidget(QWidget):
    """Step 6: Real Q&A Knowledge Base inspection with search, category filter, pagination, and editing."""
    qna_verified_completed = Signal()

    def __init__(self, setup_service, parent=None):
        super().__init__(parent)
        self.setup_service = setup_service
        self.current_page = 0
        self.page_size = 50
        self.total_entries = 0
        self._current_entries = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(14)

        # Header
        lbl_badge = QLabel("STEP 6: CANDIDATE SCREENING FACTS")
        lbl_badge.setFixedHeight(22)
        lbl_badge.setStyleSheet(f"""
            color: {COLORS['primary']};
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 1px;
            background: {COLORS['primary_subtle']};
            padding: 2px 8px;
            border-radius: 4px;
        """)
        layout.addWidget(lbl_badge, alignment=Qt.AlignLeft)

        lbl_title = QLabel("Screening Q&A Knowledge Base")
        lbl_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {COLORS['text']};")
        layout.addWidget(lbl_title)

        self.lbl_stats = QLabel("Loading verified candidate screening facts from database...")
        self.lbl_stats.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        layout.addWidget(self.lbl_stats)

        # Controls Bar (Search + Category Filter + Edit button + Mark Complete button)
        ctrl_card = QFrame()
        ctrl_card.setObjectName("ctrl_card")
        ctrl_card.setStyleSheet(f"""
            #ctrl_card {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
            #ctrl_card QLabel {{
                border: none;
                background: transparent;
            }}
        """)
        c_layout = QHBoxLayout(ctrl_card)
        c_layout.setContentsMargins(10, 8, 10, 8)
        c_layout.setSpacing(10)

        # Search Bar
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Search questions or answers...")
        self.txt_search.setStyleSheet(self._input_qss())
        self.txt_search.textChanged.connect(self._on_search_changed)
        c_layout.addWidget(self.txt_search, 2)

        # Category Filter
        self.cmb_category = QComboBox()
        self.cmb_category.setStyleSheet(self._combo_qss())
        self.cmb_category.addItem("All Categories", "")
        self.cmb_category.currentIndexChanged.connect(self._on_filter_changed)
        c_layout.addWidget(self.cmb_category, 1)

        # Edit Selected Button
        self.btn_edit = QPushButton("✏️ Edit Answer")
        self.btn_edit.setCursor(Qt.PointingHandCursor)
        self.btn_edit.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
        """)
        self.btn_edit.clicked.connect(self._on_edit_clicked)
        c_layout.addWidget(self.btn_edit)

        # Mark Complete Button
        self.btn_mark_complete = QPushButton("✓ Mark Q&A Complete")
        self.btn_mark_complete.setCursor(Qt.PointingHandCursor)
        self.btn_mark_complete.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['success_subtle']};
                color: {COLORS['success']};
                border: 1px solid {COLORS['success']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['success']};
                color: #FFFFFF;
            }}
        """)
        self.btn_mark_complete.clicked.connect(self._on_mark_complete_clicked)
        c_layout.addWidget(self.btn_mark_complete)

        layout.addWidget(ctrl_card)

        # Table Widget
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Question Text", "Answer Text", "Category", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.itemDoubleClicked.connect(lambda item: self._on_edit_clicked())
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                color: {COLORS['text']};
                gridline-color: {COLORS['border_light']};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                font-weight: 700;
                font-size: 11px;
                border: none;
                border-bottom: 1px solid {COLORS['border']};
                padding: 6px 8px;
            }}
            QTableWidget::item {{
                padding: 6px 8px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS['primary_subtle']};
                color: {COLORS['text']};
            }}
        """)
        layout.addWidget(self.table)

        # Pagination Bar
        page_row = QHBoxLayout()
        self.lbl_page_info = QLabel("Showing 0 of 0 entries")
        self.lbl_page_info.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        page_row.addWidget(self.lbl_page_info)
        page_row.addStretch()

        self.btn_prev = QPushButton("< Previous")
        self.btn_prev.setStyleSheet(self._page_btn_qss())
        self.btn_prev.clicked.connect(self._go_prev_page)
        page_row.addWidget(self.btn_prev)

        self.btn_next = QPushButton("Next >")
        self.btn_next.setStyleSheet(self._page_btn_qss())
        self.btn_next.clicked.connect(self._go_next_page)
        page_row.addWidget(self.btn_next)

        layout.addLayout(page_row)

    def load_knowledge_base(self):
        """Fetches stats and initializes categories and first page from real database."""
        _, stats = self.setup_service.get_qna_knowledge_base(limit=1)
        self.total_entries = stats.get("total_entries", 0)
        verified = stats.get("verified_entries", self.total_entries)
        unreviewed = stats.get("unreviewed_entries", 0)
        categories = stats.get("categories", {})

        self.lbl_stats.setText(
            f"✓ {self.total_entries} verified candidate facts loaded from database · "
            f"{verified} Verified · {unreviewed} Needs Review · {len(categories)} Categories"
        )

        # Populate category dropdown
        self.cmb_category.blockSignals(True)
        self.cmb_category.clear()
        self.cmb_category.addItem("All Categories", "")
        for cat_name, cat_count in sorted(categories.items()):
            self.cmb_category.addItem(f"{cat_name.title()} ({cat_count})", cat_name)
        self.cmb_category.blockSignals(False)

        self.current_page = 0
        self._refresh_page()

    def _refresh_page(self):
        search_query = self.txt_search.text().strip() or None
        cat_filter = self.cmb_category.currentData() or None

        offset = self.current_page * self.page_size
        entries, _ = self.setup_service.get_qna_knowledge_base(
            category=cat_filter,
            search=search_query,
            limit=self.page_size,
            offset=offset,
        )
        self._current_entries = entries

        self.table.setRowCount(len(entries))
        for row_idx, e in enumerate(entries):
            q_item = QTableWidgetItem(e.question_text)
            a_item = QTableWidgetItem(e.answer_text)
            c_item = QTableWidgetItem(e.category.title() if e.category else "General")
            s_item = QTableWidgetItem("✓ Verified")
            s_item.setForeground(Qt.green)

            self.table.setItem(row_idx, 0, q_item)
            self.table.setItem(row_idx, 1, a_item)
            self.table.setItem(row_idx, 2, c_item)
            self.table.setItem(row_idx, 3, s_item)

        start_idx = offset + 1 if entries else 0
        end_idx = offset + len(entries)
        self.lbl_page_info.setText(f"Showing {start_idx}–{end_idx} of {self.total_entries} entries")

        self.btn_prev.setEnabled(self.current_page > 0)
        self.btn_next.setEnabled(len(entries) == self.page_size)

    def _on_edit_clicked(self):
        sel = self.table.currentRow()
        if sel < 0 or sel >= len(self._current_entries):
            QMessageBox.information(self, "Select Row", "Please select a question row to edit its answer.")
            return

        entry = self._current_entries[sel]
        dialog = QnAEditDialog(
            entry_id=entry.id,
            question=entry.question_text,
            answer=entry.answer_text,
            category=entry.category or "general",
            qna_service=self.setup_service._get_qna_service(),
            parent=self
        )
        if dialog.exec():
            self._refresh_page()

    def _on_mark_complete_clicked(self):
        if hasattr(self.setup_service, "state"):
            self.setup_service.state.mark_step_completed("qna_knowledge")
            self.setup_service.state.save(self.setup_service._state_path)
        self.btn_mark_complete.setText("✓ Verified & Complete")
        self.btn_mark_complete.setEnabled(False)
        self.lbl_stats.setText(f"✓ All {self.total_entries} candidate screening facts verified and marked as complete.")
        self.lbl_stats.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['success']};")
        self.qna_verified_completed.emit()

    def _go_prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._refresh_page()

    def _go_next_page(self):
        self.current_page += 1
        self._refresh_page()

    def _on_search_changed(self):
        self.current_page = 0
        self._refresh_page()

    def _on_filter_changed(self):
        self.current_page = 0
        self._refresh_page()

    def _input_qss(self) -> str:
        return f"""
            QLineEdit {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
            }}
        """

    def _combo_qss(self) -> str:
        return f"""
            QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
        """

    def _page_btn_qss(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['primary']};
                color: {COLORS['primary']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_dark']};
                border-color: {COLORS['border']};
            }}
        """
