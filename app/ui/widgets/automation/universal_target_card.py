"""Universal ATS Portal Target Configuration Card for Automation View.

Provides an intuitive UI for entering an external application portal URL,
or selecting from discovered Company Portal jobs in the database.
"""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class UniversalTargetCard(QFrame):
    """Configuration panel displayed when Universal ATS platform is selected."""

    job_selected = Signal(object)  # Emits selected Job object if chosen from dropdown

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._jobs_cache: List[Any] = []
        self._setup_ui()
        self.refresh_portal_jobs()

    def _setup_ui(self) -> None:
        self.setObjectName("universal_target_card")
        self.setStyleSheet(f"""
            QFrame#universal_target_card {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('primary', '#FF5F15')}40;
                border-radius: 10px;
                padding: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # 1. Header with Mode Badge & Quick Dropdown
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        lbl_badge = QLabel("🌐 UNIVERSAL ATS TARGET")
        lbl_badge.setStyleSheet(f"""
            color: {COLORS.get('primary', '#FF5F15')};
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.5px;
            background: {COLORS.get('primary', '#FF5F15')}15;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        hdr.addWidget(lbl_badge)

        hdr.addStretch()

        lbl_quick = QLabel("Discovered Jobs:")
        lbl_quick.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px; font-weight: 600;")
        hdr.addWidget(lbl_quick)

        self.cmb_portal_jobs = QComboBox(self)
        self.cmb_portal_jobs.setMinimumWidth(260)
        self.cmb_portal_jobs.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                selection-background-color: {COLORS.get('primary', '#FF5F15')};
                selection-color: #FFFFFF;
                border: 1px solid {COLORS.get('border', '#262C36')};
            }}
        """)
        self.cmb_portal_jobs.currentIndexChanged.connect(self._on_job_combo_selected)
        hdr.addWidget(self.cmb_portal_jobs)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setToolTip("Refresh discovered portal jobs from database")
        btn_refresh.setFixedWidth(28)
        btn_refresh.setFixedHeight(26)
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text_muted', '#8B949E')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: #FFFFFF;
                border-color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        btn_refresh.clicked.connect(self.refresh_portal_jobs)
        hdr.addWidget(btn_refresh)

        layout.addLayout(hdr)

        # 2. Portal Application URL Row (Main input)
        url_layout = QVBoxLayout()
        url_layout.setSpacing(4)

        lbl_url = QLabel("Portal Application URL (Greenhouse, Lever, Workday, Ashby, or Career Site):")
        lbl_url.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px; font-weight: 600;")
        url_layout.addWidget(lbl_url)

        url_input_row = QHBoxLayout()
        url_input_row.setSpacing(6)

        self.txt_url = QLineEdit(self)
        self.txt_url.setPlaceholderText("https://boards.greenhouse.io/... or https://jobs.lever.co/...")
        self.txt_url.setClearButtonEnabled(True)
        self.txt_url.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: #58A6FF;
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 12px;
                font-family: monospace;
            }}
            QLineEdit:focus {{
                border-color: {COLORS.get('primary', '#FF5F15')};
            }}
        """)
        url_input_row.addWidget(self.txt_url, 1)

        btn_paste = QPushButton("📋 Paste")
        btn_paste.setCursor(Qt.PointingHandCursor)
        btn_paste.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
            }}
        """)
        btn_paste.clicked.connect(self._on_paste_clicked)
        url_input_row.addWidget(btn_paste)

        url_layout.addLayout(url_input_row)
        layout.addLayout(url_layout)

        # 3. Optional Metadata Row: Job Title and Company
        meta_row = QHBoxLayout()
        meta_row.setSpacing(10)

        # Job Title
        col_title = QVBoxLayout()
        col_title.setSpacing(4)
        lbl_title = QLabel("Position / Role Title:")
        lbl_title.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
        col_title.addWidget(lbl_title)
        self.txt_title = QLineEdit(self)
        self.txt_title.setPlaceholderText("e.g. Senior AI Systems Engineer")
        self.txt_title.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }}
        """)
        col_title.addWidget(self.txt_title)
        meta_row.addLayout(col_title, 1)

        # Company
        col_company = QVBoxLayout()
        col_company.setSpacing(4)
        lbl_company = QLabel("Company Name:")
        lbl_company.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
        col_company.addWidget(lbl_company)
        self.txt_company = QLineEdit(self)
        self.txt_company.setPlaceholderText("e.g. Stripe, OpenAI, etc.")
        self.txt_company.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }}
        """)
        col_company.addWidget(self.txt_company)
        meta_row.addLayout(col_company, 1)

        layout.addLayout(meta_row)

    def _on_paste_clicked(self) -> None:
        from PySide6.QtGui import QGuiApplication
        clip = QGuiApplication.clipboard()
        if clip:
            text = clip.text().strip()
            if text:
                self.txt_url.setText(text)

    def refresh_portal_jobs(self) -> None:
        """Fetches discovered jobs with company portal / external URLs from the database."""
        self.cmb_portal_jobs.blockSignals(True)
        self.cmb_portal_jobs.clear()
        self.cmb_portal_jobs.addItem("-- Select from Discovered Jobs --", None)
        self._jobs_cache = []

        try:
            from app.db.session import get_db_session
            from app.repositories.job_repository import JobRepository

            with get_db_session() as session:
                repo = JobRepository(session)
                # Query jobs with portal methods or application URLs
                jobs = repo.get_all(limit=100)
                portal_jobs = [
                    j for j in jobs
                    if (getattr(j, "application_method", "") == "COMPANY_PORTAL" or getattr(j, "application_url", None))
                ]

                self._jobs_cache = portal_jobs
                for idx, j in enumerate(portal_jobs):
                    title = getattr(j, "title", "Untitled") or "Untitled"
                    comp = getattr(j, "company_raw", None) or getattr(j, "company", "Unknown") or "Unknown"
                    label = f"{title} @ {comp}"
                    if len(label) > 40:
                        label = label[:37] + "..."
                    self.cmb_portal_jobs.addItem(f"💼 {label}", idx)

        except Exception:
            pass
        finally:
            self.cmb_portal_jobs.blockSignals(False)

    def _on_job_combo_selected(self, index: int) -> None:
        if index <= 0 or not self._jobs_cache:
            return
        data_idx = self.cmb_portal_jobs.currentData()
        if data_idx is not None and 0 <= data_idx < len(self._jobs_cache):
            job = self._jobs_cache[data_idx]
            self.set_target_job(job)
            self.job_selected.emit(job)

    def set_target_job(self, job: Any, job_title: str = "", company: str = "") -> None:
        """Populates fields from a Job database model, dict, or direct URL string."""
        if not job:
            return
        if isinstance(job, str):
            self.txt_url.setText(job)
            if job_title:
                self.txt_title.setText(job_title)
            if company:
                self.txt_company.setText(company)
            return

        url = getattr(job, "application_url", None) or getattr(job, "source_url", None) or ""
        self.txt_url.setText(url)
        title = getattr(job, "title", "") or job_title
        self.txt_title.setText(title or "")
        comp = getattr(job, "company_raw", None) or getattr(job, "company", None) or company
        self.txt_company.setText(comp or "")

    def get_target_url(self) -> str:
        return self.txt_url.text().strip()

    def get_job_title(self) -> str:
        return self.txt_title.text().strip() or "Target Position"

    def get_company(self) -> str:
        return self.txt_company.text().strip() or "Target Company"
