"""Right-side detail inspection drawer for selected job posting."""

from typing import Optional
from PySide6.QtCore import Qt, QUrl, Signal, QPoint
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Job
from app.ui.theme import COLORS


def format_platform_name(platform: Optional[str]) -> str:
    p = (platform or "").lower().strip()
    if p == "linkedin":
        return "LinkedIn"
    if p == "naukri":
        return "Naukri"
    if p == "indeed":
        return "Indeed"
    if p == "foundit":
        return "Foundit"
    if p == "glassdoor":
        return "Glassdoor"
    return platform.title() if platform else "Listing"


class JobsDetailPanel(QFrame):
    """ATS-style job detail panel displaying rich metadata, description, and contextual actions."""

    view_jd_requested = Signal(object)              # Job
    track_application_requested = Signal(object)    # Job
    apply_universal_requested = Signal(object)      # Job
    mark_junk_requested = Signal(object)            # Job
    restore_junk_requested = Signal(object)         # Job
    qualify_job_requested = Signal(object)          # Job
    status_change_requested = Signal(object, str)   # (Job, new_status)

    STATUS_OPTIONS = [
        ("SUBMITTED", "📄 Submitted"),
        ("UNDER_REVIEW", "⏳ Under Review"),
        ("INTERVIEW", "🎯 Interview / Shortlisted"),
        ("OFFER", "🎉 Offer"),
        ("REJECTED", "❌ Rejected"),
        ("FAILED", "⚠️ Failed"),
        ("MANUAL_REQUIRED", "🖐️ Manual Check"),
        ("NOT_APPLIED", "⚪ Not Applied"),
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_job: Optional[Job] = None
        self._current_app_status: Optional[str] = None
        self._setup_ui()
        self.set_job(None)

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"""
            JobsDetailPanel {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
        """)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scrollable container ensuring panel contents never get vertically crushed
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 6px;
                background: transparent;
            }
            QScrollBar::handle:vertical {
                background: #334155;
                border-radius: 3px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Header Information
        self.lbl_title = QLabel("Select a job to inspect")
        self.lbl_title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        self.lbl_title.setWordWrap(True)
        self.lbl_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_title)

        self.lbl_company = QLabel("")
        self.lbl_company.setStyleSheet(f"font-size: 13px; color: {COLORS['accent']}; font-weight: 600;")
        self.lbl_company.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_company)

        # External Portal banner
        self.lbl_portal_banner = QLabel("")
        self.lbl_portal_banner.setWordWrap(True)
        self.lbl_portal_banner.setOpenExternalLinks(True)
        self.lbl_portal_banner.setVisible(False)
        layout.addWidget(self.lbl_portal_banner)

        # Metadata Row (Location, Experience, Salary, Method)
        self.lbl_meta = QLabel("")
        self.lbl_meta.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        self.lbl_meta.setWordWrap(True)
        layout.addWidget(self.lbl_meta)

        # Qualification Assessment Section
        self.qual_frame = QFrame()
        self.qual_frame.setObjectName("qual_frame")
        self.qual_frame.setStyleSheet(f"""
            QFrame#qual_frame {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        qual_layout = QVBoxLayout(self.qual_frame)
        qual_layout.setContentsMargins(10, 10, 10, 10)
        qual_layout.setSpacing(6)

        qual_header = QHBoxLayout()
        lbl_q_title = QLabel("QUALIFICATION FIT")
        lbl_q_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']};")
        qual_header.addWidget(lbl_q_title)
        qual_header.addStretch()

        self.lbl_qual_badge = QLabel("Not Evaluated")
        self.lbl_qual_badge.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
        qual_header.addWidget(self.lbl_qual_badge)

        self.btn_qualify = QPushButton("⚡ Qualify Fit")
        self.btn_qualify.setCursor(Qt.PointingHandCursor)
        self.btn_qualify.setMinimumHeight(28)
        self.btn_qualify.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 3px 8px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']};
            }}
        """)
        self.btn_qualify.clicked.connect(self._on_qualify_clicked)
        qual_header.addWidget(self.btn_qualify)
        qual_layout.addLayout(qual_header)

        self.lbl_qual_metrics = QLabel("Select a job to inspect qualification fit.")
        self.lbl_qual_metrics.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        self.lbl_qual_metrics.setWordWrap(True)
        qual_layout.addWidget(self.lbl_qual_metrics)

        self.lbl_qual_reasons = QLabel("")
        self.lbl_qual_reasons.setStyleSheet(f"font-size: 11px; color: {COLORS['text']};")
        self.lbl_qual_reasons.setWordWrap(True)
        self.lbl_qual_reasons.setVisible(False)
        qual_layout.addWidget(self.lbl_qual_reasons)

        layout.addWidget(self.qual_frame)

        # 2. Job Description Area
        lbl_desc_heading = QLabel("JOB DESCRIPTION")
        lbl_desc_heading.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 700;
            color: {COLORS['text_muted']};
        """)
        layout.addWidget(lbl_desc_heading)

        self.txt_desc = QTextEdit()
        self.txt_desc.setReadOnly(True)
        self.txt_desc.setMinimumHeight(120)
        self.txt_desc.setMaximumHeight(220)
        self.txt_desc.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['background']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px;
                font-size: 12px;
                line-height: 1.5;
            }}
        """)
        layout.addWidget(self.txt_desc)

        # 3. Action Buttons Area
        actions_box = QVBoxLayout()
        actions_box.setSpacing(8)

        # Primary Action Button (Prominent, full-width)
        self.btn_primary_visit = QPushButton("Visit Application Link ↗")
        self.btn_primary_visit.setEnabled(False)
        self.btn_primary_visit.setMinimumHeight(40)
        self.btn_primary_visit.setCursor(Qt.PointingHandCursor)
        self.btn_primary_visit.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
            }}
        """)
        self.btn_primary_visit.clicked.connect(self._on_primary_visit_clicked)
        actions_box.addWidget(self.btn_primary_visit)

        # Dedicated Universal AI Agent Button
        self.btn_apply_universal = QPushButton("🤖 Apply with Universal AI Agent")
        self.btn_apply_universal.setEnabled(False)
        self.btn_apply_universal.setVisible(False)
        self.btn_apply_universal.setMinimumHeight(40)
        self.btn_apply_universal.setCursor(Qt.PointingHandCursor)
        self.btn_apply_universal.setToolTip("Launch Universal AI Application Agent to automatically complete this application")
        self.btn_apply_universal.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('success', '#22C55E')};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #16A34A;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
            }}
        """)
        self.btn_apply_universal.clicked.connect(self._on_apply_universal_clicked)
        actions_box.addWidget(self.btn_apply_universal)

        # Secondary Actions Row
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(6)

        self.btn_view_jd = QPushButton("Full JD 🔍")
        self.btn_view_jd.setEnabled(False)
        self.btn_view_jd.setToolTip("Inspect full job description and requirements in a focused modal dialog")
        self.btn_view_jd.setStyleSheet(self._secondary_btn_style())
        self.btn_view_jd.clicked.connect(lambda: self.view_jd_requested.emit(self._current_job))
        secondary_row.addWidget(self.btn_view_jd)

        self.btn_source_url = QPushButton("Platform Listing ↗")
        self.btn_source_url.setEnabled(False)
        self.btn_source_url.setVisible(False)
        self.btn_source_url.setToolTip("Open original job listing on platform")
        self.btn_source_url.setStyleSheet(self._secondary_btn_style())
        self.btn_source_url.clicked.connect(self._on_source_url_clicked)
        secondary_row.addWidget(self.btn_source_url)

        self.btn_track_app = QPushButton("+ Track Application")
        self.btn_track_app.setEnabled(False)
        self.btn_track_app.setToolTip("Track this job in your active recruitment pipeline")
        self.btn_track_app.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['accent']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']};
                border-color: {COLORS['border']};
            }}
        """)
        self.btn_track_app.clicked.connect(self._on_track_btn_clicked)
        secondary_row.addWidget(self.btn_track_app)

        self.btn_junk = QPushButton("🗑 Junk")
        self.btn_junk.setEnabled(False)
        self.btn_junk.setToolTip("Mark this job as junk / hide from active search")
        self.btn_junk.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: #EF4444;
                border: 1px solid #7F1D1D;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: #450A0A;
                color: #F87171;
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']};
                border-color: {COLORS['border']};
            }}
        """)
        self.btn_junk.setMinimumHeight(34)
        self.btn_junk.clicked.connect(self._on_junk_toggle_clicked)
        secondary_row.addWidget(self.btn_junk)

        self.btn_view_jd.setMinimumHeight(34)
        self.btn_source_url.setMinimumHeight(34)
        self.btn_track_app.setMinimumHeight(34)

        actions_box.addLayout(secondary_row)
        layout.addLayout(actions_box)
        layout.addStretch()

        self.scroll_area.setWidget(content_widget)
        root_layout.addWidget(self.scroll_area)

    def _secondary_btn_style(self) -> str:
        return f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
            }}
            QPushButton:disabled {{
                color: {COLORS['text_muted']};
            }}
        """

    def _on_track_btn_clicked(self) -> None:
        if not self._current_job:
            return

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

        hdr = menu.addAction("Set Application Status:")
        hdr.setEnabled(False)
        menu.addSeparator()

        for code, label in self.STATUS_OPTIONS:
            act = menu.addAction(label)
            if self._current_app_status and code == self._current_app_status:
                act.setText(f"✓ {label}")
            act.triggered.connect(lambda _, c=code: self.status_change_requested.emit(self._current_job, c))

        menu.exec_(self.btn_track_app.mapToGlobal(QPoint(0, self.btn_track_app.height() + 2)))

    def set_job(self, job: Optional[Job], in_pipeline: bool = False, app_status: Optional[str] = None) -> None:
        """Updates the detail panel with the given job's details."""
        self._current_job = job
        self._current_app_status = app_status

        if not job:
            self.lbl_title.setText("Select a job to inspect")
            self.lbl_company.setText("")
            self.lbl_portal_banner.setVisible(False)
            self.lbl_meta.setText("Choose a job from the table to view its full details and actions.")
            self.txt_desc.setPlainText("")
            self.btn_primary_visit.setEnabled(False)
            self.btn_primary_visit.setText("Visit Application Link ↗")
            self.btn_apply_universal.setVisible(False)
            self.btn_apply_universal.setEnabled(False)
            self.btn_view_jd.setEnabled(False)
            self.btn_source_url.setVisible(False)
            self.btn_track_app.setEnabled(False)
            self.btn_track_app.setText("+ Track Application")
            self.btn_junk.setEnabled(False)
            self.btn_junk.setText("🗑 Junk")
            self._update_qualification_display(None, None)
            return

        plat_name = format_platform_name(job.platform)
        self.lbl_title.setText(job.title)
        self.lbl_company.setText(f"{job.company_raw} • {plat_name}")

        loc = job.location or "N/A"
        sal = job.salary_text or "N/A"
        exp = job.experience_text or "N/A"
        method_str = getattr(job, "application_method", "EASY_APPLY") or "EASY_APPLY"
        method_name = method_str.replace("_", " ").title()

        self.lbl_meta.setText(
            f"📍 {loc}   |   💰 {sal}   |   💼 {exp}   |   ⚡ {method_name}"
        )
        self.txt_desc.setPlainText(job.description or "No detailed description provided.")
        self.btn_view_jd.setEnabled(True)

        is_portal = method_str == "COMPANY_PORTAL"
        app_url = getattr(job, "application_url", None)
        src_url = getattr(job, "source_url", None)

        if is_portal:
            self.lbl_portal_banner.setVisible(True)
            if app_url:
                self.lbl_portal_banner.setText(
                    f"🌐 <b>Company Portal</b>: <a style='color:{COLORS['primary']}; font-weight:600;' href='{app_url}'>External Portal Link ↗</a>"
                )
                self.lbl_portal_banner.setStyleSheet(
                    f"background-color: {COLORS['surface_alt']}; color: {COLORS['text']}; padding: 6px 10px; border-radius: 6px; font-size: 11px; border: 1px solid {COLORS['border']};"
                )
                self.btn_primary_visit.setText("🌐 Visit Company Portal ↗")
                self.btn_primary_visit.setToolTip(f"Open external company portal:\n{app_url}")
                self.btn_primary_visit.setEnabled(True)

                self.btn_source_url.setVisible(bool(src_url))
                self.btn_source_url.setEnabled(bool(src_url))
                self.btn_source_url.setText(f"{plat_name} Listing ↗")
            else:
                self.lbl_portal_banner.setText("🌐 <b>Company Portal</b>: Direct portal link not yet captured")
                self.lbl_portal_banner.setStyleSheet(
                    f"background-color: {COLORS['surface_alt']}; color: {COLORS['text_muted']}; padding: 6px 10px; border-radius: 6px; font-size: 11px; border: 1px dashed {COLORS['border']};"
                )
                self.btn_primary_visit.setText(f"🌐 Visit on {plat_name} to Apply ↗")
                self.btn_primary_visit.setToolTip(f"Open job listing on {plat_name} where 'Apply on company website' is located")
                self.btn_primary_visit.setEnabled(bool(src_url))
                self.btn_source_url.setVisible(False)
        else:
            self.lbl_portal_banner.setVisible(False)
            self.btn_primary_visit.setText(f"Open on {plat_name} ↗")
            self.btn_primary_visit.setToolTip(f"Open Easy Apply listing on {plat_name}")
            self.btn_primary_visit.setEnabled(bool(src_url or app_url))
            self.btn_source_url.setVisible(False)

        if not self._current_app_status:
            try:
                if hasattr(job, "applications") and job.applications:
                    self._current_app_status = job.applications[0].status
            except Exception:
                self._current_app_status = None

        curr_st = self._current_app_status or ("SUBMITTED" if in_pipeline else "NOT_APPLIED")
        if in_pipeline or (self._current_app_status and self._current_app_status not in ("NOT_APPLIED", "JUNK")):
            st_clean = curr_st.replace("_", " ").title()
            self.btn_track_app.setText(f"Status: {st_clean} ▾")
            self.btn_track_app.setEnabled(True)
            self.btn_track_app.setToolTip(f"Current status: {st_clean}. Click to update.")
        else:
            self.btn_track_app.setText("+ Track Application ▾")
            self.btn_track_app.setEnabled(True)
            self.btn_track_app.setToolTip("Track this job in your pipeline and set its status")

        # Configure Junk button
        is_junk = False
        try:
            if hasattr(job, "applications") and job.applications:
                is_junk = job.applications[0].status == "JUNK"
        except Exception:
            is_junk = False

        self.btn_junk.setEnabled(True)
        if is_junk:
            self.btn_junk.setText("↩ Restore")
            self.btn_junk.setToolTip("Restore this job back to active repository")
        else:
            self.btn_junk.setText("🗑 Junk")
            self.btn_junk.setToolTip("Move this job to Junk repository")

        # Configure Universal AI Agent button
        has_actionable_url = bool(app_url or src_url)
        self.btn_apply_universal.setVisible(is_portal or bool(app_url))
        self.btn_apply_universal.setEnabled(has_actionable_url)

        # Configure Qualification Fit
        ev = None
        try:
            if hasattr(job, "evaluations") and job.evaluations:
                ev = sorted(
                    job.evaluations,
                    key=lambda e: getattr(e, "evaluated_at", None) or getattr(e, "created_at", None),
                    reverse=True,
                )[0]
        except Exception:
            ev = None

        if ev:
            self.set_qualification(ev)
        else:
            self._update_qualification_display(None, None)

    def _on_qualify_clicked(self) -> None:
        if self._current_job:
            self.btn_qualify.setEnabled(False)
            self.btn_qualify.setText("Evaluating...")
            self.qualify_job_requested.emit(self._current_job)

    def set_qualification(self, result) -> None:
        """Updates the qualification card with a fresh QualificationResultDTO or JobEvaluation."""
        if not result:
            self._update_qualification_display(None, None)
            return

        score = getattr(result, "score", None)
        decision = getattr(result, "decision", None)
        if hasattr(decision, "value"):
            decision = decision.value
        confidence = getattr(result, "confidence", None)
        component_scores = getattr(result, "component_scores", None) or {}
        positive_reasons = getattr(result, "positive_reasons", None) or []
        negative_reasons = getattr(result, "negative_reasons", None) or []
        recommendation = getattr(result, "recommendation", None)

        self._update_qualification_display(
            score=score,
            decision=decision,
            confidence=confidence,
            component_scores=component_scores,
            positive_reasons=positive_reasons,
            negative_reasons=negative_reasons,
            recommendation=recommendation,
        )

    def _update_qualification_display(
        self,
        score: Optional[int],
        decision: Optional[str],
        confidence: Optional[float] = None,
        component_scores: Optional[dict] = None,
        positive_reasons: Optional[list] = None,
        negative_reasons: Optional[list] = None,
        recommendation: Optional[str] = None,
    ) -> None:
        if score is None or not decision:
            self.lbl_qual_badge.setText("Not Evaluated")
            self.lbl_qual_badge.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
            self.lbl_qual_metrics.setText("Not yet evaluated against your candidate profile.")
            self.lbl_qual_reasons.setVisible(False)
            self.btn_qualify.setText("⚡ Qualify Fit")
            self.btn_qualify.setEnabled(self._current_job is not None)
            return

        dec = str(decision).upper()
        if "STRONG" in dec:
            color = "#22C55E"
            label = f"{score}% Strong Match"
        elif "GOOD" in dec:
            color = "#3B82F6"
            label = f"{score}% Good Match"
        elif "POSSIBLE" in dec:
            color = "#EAB308"
            label = f"{score}% Possible Match"
        elif "WEAK" in dec:
            color = "#F97316"
            label = f"{score}% Weak Match"
        elif "REVIEW" in dec:
            color = "#A855F7"
            label = f"{score}% Review Required"
        else:
            color = "#EF4444"
            label = f"{score}% Rejected"

        self.lbl_qual_badge.setText(label)
        self.lbl_qual_badge.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color};")

        # Component breakdown
        cs = component_scores or {}
        role = cs.get("role_match", "—")
        skill = cs.get("skill_match", "—")
        exp = cs.get("experience_match", "—")
        loc = cs.get("location_match", "—")
        conf_str = f" • Conf: {int(confidence * 100)}%" if confidence is not None else ""
        self.lbl_qual_metrics.setText(f"🎯 Role: {role}%  |  🛠 Skill: {skill}%  |  💼 Exp: {exp}%  |  📍 Loc: {loc}%{conf_str}")

        # Highlight reason
        reasons_list = []
        if positive_reasons:
            reasons_list.extend([f"✓ {r}" for r in positive_reasons[:2]])
        if negative_reasons:
            reasons_list.extend([f"⚠ {r}" for r in negative_reasons[:1]])
        elif recommendation:
            reasons_list.append(recommendation)

        if reasons_list:
            self.lbl_qual_reasons.setText("\n".join(reasons_list))
            self.lbl_qual_reasons.setVisible(True)
        else:
            self.lbl_qual_reasons.setVisible(False)

        self.btn_qualify.setText("🔄 Re-qualify")
        self.btn_qualify.setEnabled(True)

    def _on_junk_toggle_clicked(self) -> None:
        if not self._current_job:
            return
        is_junk = False
        if hasattr(self._current_job, "applications") and self._current_job.applications:
            is_junk = self._current_job.applications[0].status == "JUNK"
        if is_junk:
            self.restore_junk_requested.emit(self._current_job)
        else:
            self.mark_junk_requested.emit(self._current_job)

    def _on_primary_visit_clicked(self) -> None:
        if not self._current_job:
            return
        target_url = getattr(self._current_job, "application_url", None) or getattr(self._current_job, "source_url", None)
        if target_url:
            QDesktopServices.openUrl(QUrl(target_url))

    def _on_apply_universal_clicked(self) -> None:
        if self._current_job:
            self.apply_universal_requested.emit(self._current_job)

    def _on_source_url_clicked(self) -> None:
        if not self._current_job:
            return
        if self._current_job.source_url:
            QDesktopServices.openUrl(QUrl(self._current_job.source_url))
