"""Workday Registered Company Portals Management Dialog."""

from typing import List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
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
    QVBoxLayout,
    QWidget,
)

from app.services.workday_account_service import WorkdayAccountService
from app.ui.theme import COLORS


class WorkdayAccountsDialog(QDialog):
    """Modal dialog displaying and managing company accounts registered across Workday tenants."""

    accounts_changed = Signal()

    def __init__(
        self,
        account_service: Optional[WorkdayAccountService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.account_service = account_service or WorkdayAccountService()
        self.setWindowTitle("Workday Company Accounts & Portals")
        self.resize(720, 460)
        self.setMinimumSize(600, 380)
        self._setup_ui()
        self._load_accounts()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS.get('surface', '#161B22')};
                color: {COLORS.get('text', '#F0F6FC')};
            }}
            QLabel {{
                color: {COLORS.get('text', '#F0F6FC')};
            }}
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 10px;
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS.get('accent', '#FF5F15')};
            }}
            QTableWidget {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                gridline-color: {COLORS.get('border', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
                font-size: 12px;
            }}
            QTableWidget::item {{
                padding: 6px 10px;
            }}
            QTableWidget::item:selected {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                color: {COLORS.get('text', '#F0F6FC')};
            }}
            QHeaderView::section {{
                background-color: {COLORS.get('surface', '#161B22')};
                color: {COLORS.get('text_muted', '#8B949E')};
                border: none;
                border-bottom: 1px solid {COLORS.get('border', '#262C36')};
                padding: 8px 10px;
                font-weight: 600;
                font-size: 11px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        lbl_head = QLabel("🏢 Registered Workday Company Accounts")
        lbl_head.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS.get('text', '#F0F6FC')};")
        layout.addWidget(lbl_head)

        lbl_desc = QLabel(
            "Workday isolates candidate logins per employer. When JobPilot applies to a company, it records "
            "the registration here so future applications automatically Sign In directly instead of re-registering."
        )
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        layout.addWidget(lbl_desc)

        # Action bar (Search & Add Company)
        action_row = QHBoxLayout()
        action_row.setSpacing(10)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter companies or portal domains...")
        self.txt_filter.textChanged.connect(self._filter_accounts)
        action_row.addWidget(self.txt_filter, 1)

        self.btn_add = QPushButton("+ Add Company Portal")
        self.btn_add.setCursor(Qt.PointingHandCursor)
        self.btn_add.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('accent', '#FF5F15')};
                color: {COLORS.get('accent', '#FF5F15')};
            }}
        """)
        self.btn_add.clicked.connect(self._open_add_dialog)
        action_row.addWidget(self.btn_add)
        layout.addLayout(action_row)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Company", "Tenant Domain", "Email / User ID", "Last Used", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        # Bottom Bar
        bottom_row = QHBoxLayout()
        self.lbl_count = QLabel("0 company portals registered")
        self.lbl_count.setStyleSheet(f"font-size: 12px; color: {COLORS.get('text_muted', '#8B949E')};")
        bottom_row.addWidget(self.lbl_count)
        bottom_row.addStretch()

        btn_close = QPushButton("Done")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 20px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('accent_hover', '#FF7A38')};
            }}
        """)
        btn_close.clicked.connect(self.accept)
        bottom_row.addWidget(btn_close)
        layout.addLayout(bottom_row)

    def _load_accounts(self) -> None:
        accounts = self.account_service.list_accounts()
        self._all_accounts = accounts
        self._populate_table(accounts)

    def _populate_table(self, accounts: List[dict]) -> None:
        self.table.setRowCount(len(accounts))
        for row, acct in enumerate(accounts):
            company = acct.get("company_name") or acct.get("tenant") or "Workday Employer"
            tenant = acct.get("tenant") or ""
            email = acct.get("username") or ""
            last_used = (acct.get("last_used_at") or acct.get("created_at") or "")[:10]

            item_company = QTableWidgetItem(f"🏢 {company}")
            item_tenant = QTableWidgetItem(tenant)
            item_email = QTableWidgetItem(email)
            item_date = QTableWidgetItem(last_used)

            self.table.setItem(row, 0, item_company)
            self.table.setItem(row, 1, item_tenant)
            self.table.setItem(row, 2, item_email)
            self.table.setItem(row, 3, item_date)

            btn_del = QPushButton("Delete")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    border: 1px solid {COLORS.get('border', '#262C36')};
                    border-radius: 4px;
                    color: {COLORS.get('danger', '#F85149')};
                    font-size: 11px;
                    padding: 3px 8px;
                }}
                QPushButton:hover {{
                    background-color: {COLORS.get('danger', '#F85149')};
                    color: white;
                }}
            """)
            btn_del.clicked.connect(lambda _, t=tenant, c=company: self._confirm_delete(t, c))
            self.table.setCellWidget(row, 4, btn_del)

        self.lbl_count.setText(f"{len(accounts)} company portals registered")

    def _filter_accounts(self, query: str) -> None:
        q = (query or "").strip().lower()
        if not q:
            self._populate_table(self._all_accounts)
            return

        filtered = [
            a for a in self._all_accounts
            if q in (a.get("company_name") or "").lower() or q in (a.get("tenant") or "").lower()
        ]
        self._populate_table(filtered)

    def _confirm_delete(self, tenant: str, company: str) -> None:
        reply = QMessageBox.question(
            self,
            "Remove Company Account",
            f"Are you sure you want to remove the Workday account record for '{company}' ({tenant})?\n\n"
            f"JobPilot will attempt to Create Account the next time you apply to this company.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.account_service.delete_account(tenant)
            self.accounts_changed.emit()
            self._load_accounts()

    def _open_add_dialog(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Workday Company Portal")
        dlg.setFixedSize(420, 220)
        dlg.setStyleSheet(f"""
            QDialog {{ background-color: {COLORS.get('surface', '#161B22')}; }}
            QLabel {{ color: {COLORS.get('text', '#F0F6FC')}; font-size: 12px; }}
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                color: {COLORS.get('text', '#F0F6FC')};
                padding: 6px 10px;
                font-size: 12px;
            }}
        """)
        d_layout = QVBoxLayout(dlg)
        d_layout.setContentsMargins(16, 16, 16, 16)
        d_layout.setSpacing(12)

        form = QFormLayout()
        txt_company = QLineEdit()
        txt_company.setPlaceholderText("e.g. Trane Technologies")
        form.addRow("Company Name:", txt_company)

        txt_url = QLineEdit()
        txt_url.setPlaceholderText("e.g. https://tranetechnologies.wd12.myworkdayjobs.com/...")
        form.addRow("Workday Portal URL:", txt_url)

        txt_email = QLineEdit()
        txt_email.setPlaceholderText("Candidate registered email")
        form.addRow("Email / User ID:", txt_email)
        d_layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(dlg.reject)
        btn_box.addWidget(btn_cancel)

        btn_save = QPushButton("Save Company")
        btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('accent', '#FF5F15')};
                border: none;
                border-radius: 6px;
                color: white;
                font-weight: 600;
                padding: 6px 14px;
            }}
        """)

        def _do_save():
            comp = txt_company.text().strip()
            u = txt_url.text().strip()
            em = txt_email.text().strip()
            if not u:
                QMessageBox.warning(dlg, "Missing URL", "Please enter a valid Workday portal URL.")
                return
            self.account_service.record_account(url=u, company_name=comp, username=em)
            self.accounts_changed.emit()
            self._load_accounts()
            dlg.accept()

        btn_save.clicked.connect(_do_save)
        btn_box.addWidget(btn_save)
        d_layout.addLayout(btn_box)
        dlg.exec()
