"""Resume Detail & Preview Workspace.

Embeds QPdfView strictly on the UI thread for instant PDF viewing,
alongside technical health diagnostics, boundary-detected skill tags,
and factual application usage history.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtPdf import QPdfDocument
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Resume
from app.ui.theme import COLORS


class ResumePreviewWorkspace(QWidget):
    """Integrated preview and diagnostics workspace for a selected resume."""

    back_requested = Signal()
    action_set_default = Signal(int)
    action_new_version = Signal(int)
    action_open_os = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.current_resume: Optional[Resume] = None
        self.pdf_doc = QPdfDocument(self)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(12)

        # 1. Top Navigation & Action Header
        self.header_frame = QFrame()
        self.header_frame.setObjectName("previewHeader")
        self.header_frame.setStyleSheet(f"""
            QFrame#previewHeader {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 16px;
            }}
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton#btnPrimary {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
            }}
            QPushButton#btnPrimary:hover {{
                background-color: {COLORS['primary_hover'] if 'primary_hover' in COLORS else COLORS['accent']};
            }}
        """)

        hdr_layout = QHBoxLayout(self.header_frame)
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(12)

        self.btn_back = QPushButton("← Back to Library")
        self.btn_back.setCursor(Qt.PointingHandCursor)
        self.btn_back.clicked.connect(self.back_requested.emit)
        hdr_layout.addWidget(self.btn_back)

        hdr_layout.addSpacing(8)

        # Title info
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)

        self.lbl_title = QLabel("Resume Preview")
        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text']};")
        name_row.addWidget(self.lbl_title)

        self.lbl_version = QLabel("v1.0")
        self.lbl_version.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['accent']};
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 1px 6px;
        """)
        name_row.addWidget(self.lbl_version)

        self.lbl_default_badge = QLabel("★ Default")
        self.lbl_default_badge.setStyleSheet("""
            font-size: 11px;
            font-weight: 700;
            color: #D97706;
            background-color: rgba(217, 119, 6, 0.15);
            border: 1px solid rgba(217, 119, 6, 0.35);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        self.lbl_default_badge.setVisible(False)
        name_row.addWidget(self.lbl_default_badge)

        name_row.addStretch()
        title_box.addLayout(name_row)

        self.lbl_subtitle = QLabel("Target: General")
        self.lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        title_box.addWidget(self.lbl_subtitle)

        hdr_layout.addLayout(title_box, 1)

        # Actions
        self.btn_set_default = QPushButton("★ Set as Default")
        self.btn_set_default.setCursor(Qt.PointingHandCursor)
        self.btn_set_default.clicked.connect(self._on_set_default_clicked)
        hdr_layout.addWidget(self.btn_set_default)

        self.btn_new_version = QPushButton("🧬 New Version")
        self.btn_new_version.setCursor(Qt.PointingHandCursor)
        self.btn_new_version.clicked.connect(self._on_new_version_clicked)
        hdr_layout.addWidget(self.btn_new_version)

        self.btn_os_view = QPushButton("↗ OS Viewer")
        self.btn_os_view.setCursor(Qt.PointingHandCursor)
        self.btn_os_view.clicked.connect(self._on_os_view_clicked)
        hdr_layout.addWidget(self.btn_os_view)

        root_layout.addWidget(self.header_frame)

        # 2. Main Content Splitter (Left: PDF Viewer, Right: Intelligence & Usage)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)

        # LEFT: PDF Viewer Widget
        self.viewer_container = QWidget()
        viewer_layout = QVBoxLayout(self.viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        viewer_layout.setSpacing(6)

        # PDF Toolbar (Pages & Zoom)
        self.pdf_toolbar = QFrame()
        self.pdf_toolbar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 8px;
            }}
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
            }}
            QLabel {{
                color: {COLORS['text']};
                font-size: 12px;
                font-weight: 500;
            }}
        """)
        tb_layout = QHBoxLayout(self.pdf_toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(8)

        self.btn_prev_page = QPushButton("◀")
        self.btn_prev_page.setFixedWidth(30)
        self.btn_prev_page.clicked.connect(self._prev_page)
        tb_layout.addWidget(self.btn_prev_page)

        self.lbl_page_info = QLabel("Page 1 of 1")
        tb_layout.addWidget(self.lbl_page_info)

        self.btn_next_page = QPushButton("▶")
        self.btn_next_page.setFixedWidth(30)
        self.btn_next_page.clicked.connect(self._next_page)
        tb_layout.addWidget(self.btn_next_page)

        tb_layout.addSpacing(16)

        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setFixedWidth(30)
        self.btn_zoom_out.clicked.connect(self._zoom_out)
        tb_layout.addWidget(self.btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        tb_layout.addWidget(self.lbl_zoom)

        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setFixedWidth(30)
        self.btn_zoom_in.clicked.connect(self._zoom_in)
        tb_layout.addWidget(self.btn_zoom_in)

        self.btn_fit_width = QPushButton("Fit Width")
        self.btn_fit_width.clicked.connect(self._fit_width)
        tb_layout.addWidget(self.btn_fit_width)

        tb_layout.addStretch()
        viewer_layout.addWidget(self.pdf_toolbar)

        # PDF Stack (Page View or Fallback Message)
        self.pdf_stack = QStackedWidget()

        # Page 0: QPdfView
        self.pdf_view = QPdfView(self)
        self.pdf_view.setDocument(self.pdf_doc)
        self.pdf_view.setPageMode(QPdfView.PageMode.SinglePage)
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setStyleSheet(f"""
            QPdfView {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        self.pdf_stack.addWidget(self.pdf_view)

        # Page 1: Fallback / Error Message
        self.fallback_frame = QFrame()
        self.fallback_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        fb_layout = QVBoxLayout(self.fallback_frame)
        fb_layout.setAlignment(Qt.AlignCenter)
        fb_layout.setSpacing(12)

        self.lbl_fb_icon = QLabel("📄")
        self.lbl_fb_icon.setStyleSheet("font-size: 40px;")
        self.lbl_fb_icon.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(self.lbl_fb_icon)

        self.lbl_fb_title = QLabel("Document Preview Unavailable")
        self.lbl_fb_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_fb_title.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(self.lbl_fb_title)

        self.lbl_fb_msg = QLabel("File is non-PDF or could not be loaded into the embedded viewer.")
        self.lbl_fb_msg.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']};")
        self.lbl_fb_msg.setAlignment(Qt.AlignCenter)
        fb_layout.addWidget(self.lbl_fb_msg)

        self.btn_fb_open = QPushButton("↗ Open with System Application")
        self.btn_fb_open.setCursor(Qt.PointingHandCursor)
        self.btn_fb_open.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
            }}
        """)
        self.btn_fb_open.clicked.connect(self._on_os_view_clicked)
        fb_layout.addWidget(self.btn_fb_open)

        self.pdf_stack.addWidget(self.fallback_frame)
        viewer_layout.addWidget(self.pdf_stack, 1)

        self.splitter.addWidget(self.viewer_container)

        # RIGHT: Diagnostics & Usage Panel
        self.details_scroll = QScrollArea()
        self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
        """)

        self.details_container = QWidget()
        details_layout = QVBoxLayout(self.details_container)
        details_layout.setContentsMargins(8, 0, 0, 0)
        details_layout.setSpacing(14)

        # Section 1: Technical Health Checklist
        self.health_card, self.health_card_layout = self._build_card_frame("Technical Health Checklist")
        details_layout.addWidget(self.health_card)

        # Section 2: Detected Skills
        self.skills_card, self.skills_card_layout = self._build_card_frame("Detected Skills (Catalog Matches)")
        details_layout.addWidget(self.skills_card)

        # Section 3: Application Footprint & History
        self.usage_card, self.usage_card_layout = self._build_card_frame("Application Usage & Footprint")
        details_layout.addWidget(self.usage_card)

        details_layout.addStretch()
        self.details_scroll.setWidget(self.details_container)
        self.splitter.addWidget(self.details_scroll)

        # Set 60/40 ratio
        self.splitter.setSizes([600, 400])
        root_layout.addWidget(self.splitter, 1)

    def _build_card_frame(self, title: str) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("diagCard")
        card.setStyleSheet(f"""
            QFrame#diagCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 14px;
            }}
        """)
        outer_layout = QVBoxLayout(card)
        outer_layout.setContentsMargins(14, 14, 14, 14)
        outer_layout.setSpacing(10)

        lbl = QLabel(title.upper())
        lbl.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLORS['text_muted']};
            letter-spacing: 0.5px;
            margin-bottom: 2px;
        """)
        outer_layout.addWidget(lbl)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)
        outer_layout.addLayout(content_layout)

        return card, content_layout

    def _clear_layout(self, layout):
        """Recursively detaches and deletes all child widgets and sub-layouts."""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                w = item.widget()
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
                item.layout().deleteLater()

    def load_resume(
        self,
        resume: Resume,
        health_info: Dict[str, Any],
        usage_info: Dict[str, Any],
    ):
        """Loads a resume, its technical health checklist, and application history into the workspace."""
        self.current_resume = resume

        # Header update
        self.lbl_title.setText(resume.name)
        v_str = f"v{resume.version}" if resume.version else "v1.0"
        self.lbl_version.setText(v_str)
        self.lbl_default_badge.setVisible(resume.is_default)
        self.btn_set_default.setVisible(not resume.is_default and not resume.is_archived)

        role_str = resume.role_target or "General"
        notes_str = f" • Notes: {resume.notes}" if resume.notes else ""
        self.lbl_subtitle.setText(f"Target: {role_str}{notes_str}")

        # Load PDF in UI thread
        path = Path(resume.file_path).resolve()
        if path.exists() and path.suffix.lower() == ".pdf":
            self.pdf_doc.load(str(path))
            total_pages = self.pdf_doc.pageCount()
            if total_pages > 0:
                self.pdf_stack.setCurrentIndex(0)
                self.pdf_toolbar.setVisible(True)
                self._update_page_label()
            else:
                self.pdf_stack.setCurrentIndex(1)
                self.pdf_toolbar.setVisible(False)
                self.lbl_fb_title.setText("PDF Loading Failed")
                self.lbl_fb_msg.setText("Unable to parse pages or file is encrypted.")
        else:
            self.pdf_stack.setCurrentIndex(1)
            self.pdf_toolbar.setVisible(False)
            if not path.exists():
                self.lbl_fb_title.setText("File Missing on Disk")
                self.lbl_fb_msg.setText(f"Missing path: {resume.file_path}")
            else:
                self.lbl_fb_title.setText("Non-PDF File Format")
                self.lbl_fb_msg.setText(f"Embedded preview supports PDF. Click below to open {path.suffix.upper()}.")

        # Populate Sections
        self._populate_health_section(health_info)
        self._populate_skills_section(health_info)
        self._populate_usage_section(usage_info)

    def _populate_health_section(self, health_info: Dict[str, Any]):
        # Clear layout completely
        self._clear_layout(self.health_card_layout)

        status = health_info.get("health_status", "VALID")
        flags = health_info.get("flags", {})

        # Status Banner
        if status == "VALID":
            banner_text = "✓ Health Status: VALID"
            banner_style = "color: #059669; background-color: rgba(5, 150, 105, 0.12); border: 1px solid rgba(5, 150, 105, 0.3);"
        elif status == "NEEDS_ATTENTION":
            banner_text = "⚠ Health Status: NEEDS ATTENTION"
            banner_style = "color: #D97706; background-color: rgba(217, 119, 6, 0.12); border: 1px solid rgba(217, 119, 6, 0.3);"
        else:
            banner_text = "✕ Health Status: INVALID"
            banner_style = "color: #DC2626; background-color: rgba(220, 38, 38, 0.12); border: 1px solid rgba(220, 38, 38, 0.3);"

        lbl_banner = QLabel(banner_text)
        lbl_banner.setStyleSheet(f"""
            font-size: 12px;
            font-weight: 700;
            border-radius: 6px;
            padding: 6px 10px;
            {banner_style}
        """)
        self.health_card_layout.addWidget(lbl_banner)

        # 6 Factual Checks
        checks = [
            ("Physical file exists on storage", flags.get("file_exists", False)),
            ("SHA-256 integrity hash matches record", flags.get("hash_valid", False)),
            ("PDF document structure readable", flags.get("pdf_readable", False)),
            ("Text content extractable (>50 characters)", flags.get("text_extractable", False)),
            ("Contact presence (Email / Phone)", flags.get("contacts_detected", False)),
            ("Target role explicitly assigned", flags.get("role_assigned", False)),
        ]

        for desc, passed in checks:
            row = QHBoxLayout()
            row.setSpacing(8)
            icon = QLabel("✓" if passed else "✕")
            icon.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {'#059669' if passed else '#DC2626'};")
            icon.setFixedWidth(16)
            row.addWidget(icon)

            text = QLabel(desc)
            text.setStyleSheet(f"font-size: 12px; color: {COLORS['text'] if passed else COLORS['text_muted']};")
            row.addWidget(text)
            row.addStretch()
            self.health_card_layout.addLayout(row)

    def _populate_skills_section(self, health_info: Dict[str, Any]):
        self._clear_layout(self.skills_card_layout)

        meta = health_info.get("metadata", {}) or {}
        skills = meta.get("detected_skills", [])

        if not skills:
            lbl_none = QLabel("No catalog skills detected in text. (Parser checks against boundary-aware keyword set).")
            lbl_none.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
            self.skills_card_layout.addWidget(lbl_none)
            return

        # Group by category
        by_cat: Dict[str, List[str]] = {}
        for s in skills:
            cat = s.get("category", "General")
            by_cat.setdefault(cat, []).append(s.get("canonical", ""))

        for cat, names in by_cat.items():
            cat_lbl = QLabel(cat)
            cat_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['accent']}; margin-top: 4px;")
            self.skills_card_layout.addWidget(cat_lbl)

            chips_layout = QHBoxLayout()
            chips_layout.setSpacing(6)
            for name in names:
                chip = QLabel(name)
                chip.setStyleSheet(f"""
                    font-size: 11px;
                    color: {COLORS['text']};
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 3px 8px;
                """)
                chips_layout.addWidget(chip)
            chips_layout.addStretch()
            self.skills_card_layout.addLayout(chips_layout)

    def _populate_usage_section(self, usage_info: Dict[str, Any]):
        self._clear_layout(self.usage_card_layout)

        total = usage_info.get("total_applications", 0)
        submitted = usage_info.get("submitted_count", 0)
        interviews = usage_info.get("interviews_count", 0)
        offers = usage_info.get("offers_count", 0)

        # KPI mini row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)

        for label, val in [("Total", total), ("Submitted", submitted), ("Interviews", interviews), ("Offers", offers)]:
            box = QFrame()
            box.setStyleSheet(f"background-color: {COLORS['surface_alt']}; border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 6px;")
            b_layout = QVBoxLayout(box)
            b_layout.setContentsMargins(4, 4, 4, 4)
            b_layout.setSpacing(2)
            l = QLabel(label.upper())
            l.setStyleSheet(f"font-size: 9px; font-weight: 700; color: {COLORS['text_muted']};")
            v = QLabel(str(val))
            v.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']};")
            b_layout.addWidget(l)
            b_layout.addWidget(v)
            stats_row.addWidget(box)

        self.usage_card_layout.addLayout(stats_row)

        # Recent applications table/list
        recent = usage_info.get("recent_applications", [])
        if recent:
            lbl_recent = QLabel("Recent Applications Submitted:")
            lbl_recent.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']}; margin-top: 6px;")
            self.usage_card_layout.addWidget(lbl_recent)

            for app in recent:
                app_card = QFrame()
                app_card.setStyleSheet(f"""
                    QFrame {{
                        background-color: {COLORS['surface_alt']};
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        padding: 6px 10px;
                    }}
                """)
                a_layout = QHBoxLayout(app_card)
                a_layout.setContentsMargins(0, 0, 0, 0)
                a_layout.setSpacing(8)

                col = QVBoxLayout()
                col.setSpacing(2)
                t = QLabel(f"{app.get('job_title', 'Job')} • {app.get('company_name', 'Company')}")
                t.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']};")
                sub = QLabel(f"{app.get('platform', '').title()} • {app.get('applied_at') or 'Unknown date'}")
                sub.setStyleSheet(f"font-size: 10px; color: {COLORS['text_muted']};")
                col.addWidget(t)
                col.addWidget(sub)
                a_layout.addLayout(col, 1)

                st_lbl = QLabel(app.get("status", ""))
                st_lbl.setStyleSheet(f"""
                    font-size: 10px;
                    font-weight: 600;
                    color: {COLORS['accent']};
                    background-color: {COLORS['surface']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 4px;
                    padding: 2px 6px;
                """)
                a_layout.addWidget(st_lbl)

                self.usage_card_layout.addWidget(app_card)
        else:
            lbl_empty = QLabel("No applications have been submitted with this resume yet.")
            lbl_empty.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']}; margin-top: 4px;")
            self.usage_card_layout.addWidget(lbl_empty)

    # PDF Controls
    def _update_page_label(self):
        nav = self.pdf_view.pageNavigator()
        curr = nav.currentPage() + 1
        total = self.pdf_doc.pageCount()
        self.lbl_page_info.setText(f"Page {curr} of {total}")
        self.btn_prev_page.setEnabled(curr > 1)
        self.btn_next_page.setEnabled(curr < total)

    def _prev_page(self):
        nav = self.pdf_view.pageNavigator()
        if nav.currentPage() > 0:
            nav.jump(nav.currentPage() - 1, nav.currentLocation())
            self._update_page_label()

    def _next_page(self):
        nav = self.pdf_view.pageNavigator()
        if nav.currentPage() < self.pdf_doc.pageCount() - 1:
            nav.jump(nav.currentPage() + 1, nav.currentLocation())
            self._update_page_label()

    def _zoom_in(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() * 1.2)
        self.lbl_zoom.setText(f"{int(self.pdf_view.zoomFactor() * 100)}%")

    def _zoom_out(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.Custom)
        self.pdf_view.setZoomFactor(self.pdf_view.zoomFactor() / 1.2)
        self.lbl_zoom.setText(f"{int(self.pdf_view.zoomFactor() * 100)}%")

    def _fit_width(self):
        self.pdf_view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        self.lbl_zoom.setText("Fit Width")

    def _on_set_default_clicked(self):
        if self.current_resume:
            self.action_set_default.emit(self.current_resume.id)

    def _on_new_version_clicked(self):
        if self.current_resume:
            self.action_new_version.emit(self.current_resume.id)

    def _on_os_view_clicked(self):
        if self.current_resume:
            self.action_open_os.emit(self.current_resume.id)
