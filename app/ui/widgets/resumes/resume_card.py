"""Rich visual card component for a resume record."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Resume
from app.ui.theme import COLORS


class ResumeCard(QFrame):
    """Card displaying resume identity, technical health, detected skills, usage stats, and actions."""

    card_clicked = Signal(int)
    action_preview = Signal(int)
    action_set_default = Signal(int)
    action_new_version = Signal(int)
    action_edit = Signal(int)
    action_archive = Signal(int)
    action_unarchive = Signal(int)
    action_delete = Signal(int)
    action_open_os = Signal(int)

    def __init__(
        self,
        resume: Resume,
        health_info: Optional[Dict[str, Any]] = None,
        usage_info: Optional[Dict[str, Any]] = None,
        is_selected: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.resume_id = resume.id
        self._is_selected = is_selected
        self.resume = resume
        self.health_info = health_info or {}
        self.usage_info = usage_info or {}

        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("resumeCard")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(180)
        self._apply_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header Row: Icon, Title & Version, Default/Archive Badge, Menu
        hdr_layout = QHBoxLayout()
        hdr_layout.setContentsMargins(0, 0, 0, 0)
        hdr_layout.setSpacing(10)

        # PDF Doc Icon
        lbl_icon = QLabel("📄")
        lbl_icon.setStyleSheet(f"""
            font-size: 20px;
            background-color: {COLORS['surface_alt']};
            border-radius: 6px;
            padding: 6px;
        """)
        hdr_layout.addWidget(lbl_icon)

        # Title & Version
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)

        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(6)

        self.lbl_title = QLabel(resume.name)
        self.lbl_title.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {COLORS['text']};
        """)
        name_row.addWidget(self.lbl_title)

        v_text = f"v{resume.version}" if resume.version else "v1.0"
        lbl_ver = QLabel(v_text)
        lbl_ver.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['accent']};
            background-color: {COLORS['surface_alt']};
            border: 1px solid {COLORS['border']};
            border-radius: 4px;
            padding: 1px 5px;
        """)
        name_row.addWidget(lbl_ver)
        name_row.addStretch()
        title_box.addLayout(name_row)

        role_text = resume.role_target or "General"
        lbl_role = QLabel(f"Target: {role_text}")
        lbl_role.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
        """)
        title_box.addWidget(lbl_role)
        hdr_layout.addLayout(title_box, 1)

        # Default Badge
        if resume.is_default:
            lbl_def = QLabel("★ Default")
            lbl_def.setStyleSheet("""
                font-size: 11px;
                font-weight: 700;
                color: #D97706;
                background-color: rgba(217, 119, 6, 0.15);
                border: 1px solid rgba(217, 119, 6, 0.35);
                border-radius: 4px;
                padding: 3px 7px;
            """)
            hdr_layout.addWidget(lbl_def)

        # Archived Badge
        if resume.is_archived:
            lbl_arc = QLabel("Archived")
            lbl_arc.setStyleSheet(f"""
                font-size: 11px;
                font-weight: 600;
                color: {COLORS['text_muted']};
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 3px 6px;
            """)
            hdr_layout.addWidget(lbl_arc)

        # 3-Dots Quick Actions Menu Button
        self.btn_menu = QPushButton("⋮")
        self.btn_menu.setFixedSize(28, 28)
        self.btn_menu.setCursor(Qt.PointingHandCursor)
        self.btn_menu.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-radius: 4px;
                font-size: 16px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)
        self.btn_menu.clicked.connect(self._show_action_menu)
        hdr_layout.addWidget(self.btn_menu)

        layout.addLayout(hdr_layout)

        # Health Row & Technical Flags
        health_row = QHBoxLayout()
        health_row.setContentsMargins(0, 0, 0, 0)
        health_row.setSpacing(8)

        health_status = self.health_info.get("health_status", "VALID")
        flags = self.health_info.get("flags", {})

        if health_status == "VALID":
            lbl_health = QLabel("✓ Health: Valid")
            lbl_health.setStyleSheet("""
                font-size: 11px;
                font-weight: 600;
                color: #059669;
                background-color: rgba(5, 150, 105, 0.12);
                border: 1px solid rgba(5, 150, 105, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            tooltip = "Document is valid, text extractable, contacts verified."
        elif health_status == "NEEDS_ATTENTION":
            lbl_health = QLabel("⚠ Needs Attention")
            lbl_health.setStyleSheet("""
                font-size: 11px;
                font-weight: 600;
                color: #D97706;
                background-color: rgba(217, 119, 6, 0.12);
                border: 1px solid rgba(217, 119, 6, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            missing = []
            if not flags.get("role_assigned"):
                missing.append("Missing target role")
            if not flags.get("contacts_detected"):
                missing.append("Missing contact info")
            if not flags.get("text_extractable"):
                missing.append("Limited extractable text")
            tooltip = f"Attention: {', '.join(missing)}"
        else:
            lbl_health = QLabel("✕ Invalid File")
            lbl_health.setStyleSheet("""
                font-size: 11px;
                font-weight: 600;
                color: #DC2626;
                background-color: rgba(220, 38, 38, 0.12);
                border: 1px solid rgba(220, 38, 38, 0.3);
                border-radius: 4px;
                padding: 2px 6px;
            """)
            tooltip = "File missing on disk or SHA-256 hash corrupted."

        lbl_health.setToolTip(tooltip)
        lbl_health.setFixedHeight(22)
        health_row.addWidget(lbl_health)

        # Page count if available
        meta = self.health_info.get("metadata", {}) or {}
        page_cnt = meta.get("page_count", 0)
        if page_cnt > 0:
            lbl_pages = QLabel(f"{page_cnt} {'page' if page_cnt == 1 else 'pages'}")
            lbl_pages.setStyleSheet(f"""
                font-size: 11px;
                color: {COLORS['text_muted']};
            """)
            lbl_pages.setFixedHeight(22)
            health_row.addWidget(lbl_pages)

        health_row.addStretch()
        layout.addLayout(health_row)

        # Detected Skills Tag Cloud
        skills = meta.get("detected_skills", [])
        if skills:
            skills_layout = QHBoxLayout()
            skills_layout.setContentsMargins(0, 0, 0, 0)
            skills_layout.setSpacing(5)

            for s in skills[:4]:
                skill_name = s.get("canonical", "")
                pill = QLabel(skill_name)
                pill.setFixedHeight(22)
                pill.setStyleSheet(f"""
                    font-size: 10px;
                    font-weight: 500;
                    color: {COLORS['text']};
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 3px;
                    padding: 2px 6px;
                """)
                skills_layout.addWidget(pill)

            if len(skills) > 4:
                more_pill = QLabel(f"+{len(skills) - 4}")
                more_pill.setFixedHeight(22)
                more_pill.setStyleSheet(f"""
                    font-size: 10px;
                    font-weight: 600;
                    color: {COLORS['text_muted']};
                    background-color: {COLORS['surface_alt']};
                    border: 1px solid {COLORS['border']};
                    border-radius: 3px;
                    padding: 2px 5px;
                """)
                skills_layout.addWidget(more_pill)

            skills_layout.addStretch()
            layout.addLayout(skills_layout)

        layout.addStretch(1)

        # Footer Row: Applications count & Last used date
        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(0, 2, 0, 0)
        footer_layout.setSpacing(8)

        total_apps = self.usage_info.get("total_applications", 0)
        lbl_apps = QLabel(f"🚀 {total_apps} {'application' if total_apps == 1 else 'applications'}")
        lbl_apps.setStyleSheet(f"""
            font-size: 11px;
            font-weight: 600;
            color: {COLORS['text_secondary'] if 'text_secondary' in COLORS else COLORS['text_muted']};
        """)
        footer_layout.addWidget(lbl_apps)

        last_used = self.usage_info.get("last_used_at", "Never")
        lbl_last = QLabel(f"Last used: {last_used}")
        lbl_last.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
        """)
        footer_layout.addWidget(lbl_last)

        footer_layout.addStretch()

        # Preview Button
        btn_prev = QPushButton("Preview")
        btn_prev.setCursor(Qt.PointingHandCursor)
        btn_prev.setFixedHeight(24)
        btn_prev.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 4px;
                padding: 3px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        btn_prev.clicked.connect(lambda: self.action_preview.emit(self.resume_id))
        footer_layout.addWidget(btn_prev)

        layout.addLayout(footer_layout)

    def _apply_style(self):
        border_color = COLORS['accent'] if self._is_selected else COLORS['border']
        border_width = "2px" if self._is_selected else "1px"
        bg_color = COLORS['surface_hover'] if self._is_selected else COLORS['surface']
        self.setStyleSheet(f"""
            QFrame#resumeCard {{
                background-color: {bg_color};
                border: {border_width} solid {border_color};
                border-radius: 10px;
            }}
            QFrame#resumeCard:hover {{
                border-color: {COLORS['accent']};
            }}
        """)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.card_clicked.emit(self.resume_id)
        super().mousePressEvent(event)

    def _show_action_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 4px 0;
            }}
            QMenu::item {{
                padding: 6px 18px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['surface_hover']};
                color: {COLORS['text']};
            }}
        """)

        act_preview = menu.addAction("👁  Preview In-App")
        act_preview.triggered.connect(lambda: self.action_preview.emit(self.resume_id))

        act_os = menu.addAction("↗  Open with System Viewer")
        act_os.triggered.connect(lambda: self.action_open_os.emit(self.resume_id))

        menu.addSeparator()

        if not self.resume.is_default and not self.resume.is_archived:
            act_def = menu.addAction("★  Set as Default")
            act_def.triggered.connect(lambda: self.action_set_default.emit(self.resume_id))

        act_ver = menu.addAction("🧬  New Version...")
        act_ver.triggered.connect(lambda: self.action_new_version.emit(self.resume_id))

        act_edit = menu.addAction("✎  Edit Metadata...")
        act_edit.triggered.connect(lambda: self.action_edit.emit(self.resume_id))

        menu.addSeparator()

        if self.resume.is_archived:
            act_unarc = menu.addAction("♻  Restore from Archive")
            act_unarc.triggered.connect(lambda: self.action_unarchive.emit(self.resume_id))
        else:
            act_arc = menu.addAction("📦  Archive Resume")
            act_arc.triggered.connect(lambda: self.action_archive.emit(self.resume_id))

        act_del = menu.addAction("🗑  Delete Resume")
        act_del.triggered.connect(lambda: self.action_delete.emit(self.resume_id))

        menu.exec_(self.btn_menu.mapToGlobal(self.btn_menu.rect().bottomLeft()))
