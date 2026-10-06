"""Interactive Human-in-the-Loop Pre-Submission Review Dialog.

Enforces the V1 Human Review Gate: applications can NEVER be submitted automatically
without explicit human confirmation. Displays all populated form fields, provenance sources,
and candidate values for manual review before triggering final submission.
"""

import os
import re
from typing import Any, Callable, Dict, Optional, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import COLORS


class UniversalReviewDialog(QDialog):
    """Modal dialog displaying mapped form values and requiring human approval before submission."""

    confirmed = Signal(str)  # user notes
    takeover_requested = Signal(str)  # user notes
    rejected = Signal(str)  # cancellation reason

    def __init__(
        self,
        job_title: Optional[str] = None,
        company: Optional[str] = None,
        target_url: Optional[str] = None,
        resume_name: Optional[str] = None,
        field_details: Optional[Dict[str, Any]] = None,
        on_confirmed: Optional[Callable[[Optional[str]], None]] = None,
        on_takeover: Optional[Callable[[Optional[str]], None]] = None,
        on_rejected: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.job_title = job_title or "Target Position"
        self.company = company or "Target Company"
        self.target_url = target_url or ""
        self.resume_name = resume_name or "Managed Resume (Default)"
        self.field_details = field_details or {}

        self.on_confirmed_cb = on_confirmed
        self.on_takeover_cb = on_takeover
        self.on_rejected_cb = on_rejected

        self.setWindowTitle(f"Review Application — {self.job_title} @ {self.company}")
        self.resize(760, 580)
        self.setMinimumSize(640, 480)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        bg_color = COLORS.get("surface", "#161B22")
        border_color = COLORS.get("border", "#30363D")
        text_color = COLORS.get("text", "#F0F6FC")
        muted_color = COLORS.get("text_muted", "#8B949E")
        accent_color = COLORS.get("primary", "#1F6FEB")
        success_color = COLORS.get("success", "#238636")
        danger_color = COLORS.get("danger", "#DA3633")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header with Badge & Warning
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(12)

        icon_lbl = QLabel("📋")
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(40, 40)
        icon_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('primary_subtle', '#1F6FEB1A')};
                border: 1px solid {border_color};
                border-radius: 8px;
                font-size: 20px;
            }}
        """)
        hdr_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("Pre-Submission Human Review")
        title_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 16px;
                font-weight: 700;
                color: {text_color};
            }}
        """)
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("MANDATORY CONFIRMATION GATE — NO APPLICATION SUBMITS AUTOMATICALLY")
        sub_lbl.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                font-weight: 700;
                color: {COLORS.get('warning', '#D29922')};
                letter-spacing: 0.5px;
            }}
        """)
        title_box.addWidget(sub_lbl)
        hdr_layout.addLayout(title_box, 1)

        layout.addLayout(hdr_layout)

        # 2. Metadata Context Card
        meta_card = QFrame()
        meta_card.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS.get('surface_alt', '#0D1117')};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        meta_layout = QVBoxLayout(meta_card)
        meta_layout.setContentsMargins(12, 10, 12, 10)
        meta_layout.setSpacing(6)

        job_line = QLabel(f"<b>Job:</b> {self.job_title} &nbsp;|&nbsp; <b>Company:</b> {self.company}")
        job_line.setStyleSheet(f"color: {text_color}; font-size: 13px; background: transparent; border: none;")
        meta_layout.addWidget(job_line)

        url_line = QLabel(f"<b>Portal:</b> <span style='color: {muted_color};'>{self.target_url or 'N/A'}</span>")
        url_line.setStyleSheet(f"font-size: 11px; background: transparent; border: none;")
        url_line.setTextInteractionFlags(Qt.TextSelectableByMouse)
        meta_layout.addWidget(url_line)

        resume_line = QLabel(f"<b>Resume Attached:</b> 📄 {self.resume_name}")
        resume_line.setStyleSheet(f"color: {text_color}; font-size: 11px; background: transparent; border: none;")
        meta_layout.addWidget(resume_line)

        layout.addWidget(meta_card)

        # 3. Form Field Mapping Review Table
        table_lbl = QLabel(f"Mapped Form Responses ({len(self.field_details)} fields)")
        table_lbl.setStyleSheet(f"color: {muted_color}; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        layout.addWidget(table_lbl)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Question / Field", "Proposed Value", "Source Provenance"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 240)
        self.table.setColumnWidth(2, 190)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(36)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {COLORS.get('surface_alt', '#0D1117')};
                alternate-background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                gridline-color: {border_color};
                color: {text_color};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background-color: {bg_color};
                color: {muted_color};
                font-weight: 700;
                font-size: 11px;
                padding: 6px;
                border: 1px solid {border_color};
            }}
        """)
        self._populate_table()
        layout.addWidget(self.table, 1)

        # 4. Optional Submission Notes
        notes_box = QHBoxLayout()
        notes_box.setSpacing(8)
        notes_lbl = QLabel("Notes (optional):")
        notes_lbl.setStyleSheet(f"color: {muted_color}; font-size: 12px;")
        notes_box.addWidget(notes_lbl)

        self.notes_input = QLineEdit()
        self.notes_input.setPlaceholderText("Add optional notes for application audit history...")
        self.notes_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS.get('surface_alt', '#0D1117')};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px 10px;
                color: {text_color};
                font-size: 12px;
            }}
            QLineEdit:focus {{
                border-color: {accent_color};
            }}
        """)
        notes_box.addWidget(self.notes_input, 1)
        layout.addLayout(notes_box)

        # 5. Action Buttons Footer
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel Application")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {danger_color};
                border-radius: 6px;
                color: {danger_color};
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {danger_color}1A;
            }}
        """)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)
        footer_layout.addWidget(self.btn_cancel)

        footer_layout.addStretch()

        self.btn_takeover = QPushButton("Switch to Manual Mode")
        self.btn_takeover.setCursor(Qt.PointingHandCursor)
        self.btn_takeover.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#21262D')};
                border: 1px solid {border_color};
                border-radius: 6px;
                color: {text_color};
                padding: 8px 16px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {border_color};
            }}
        """)
        self.btn_takeover.clicked.connect(self._on_takeover_clicked)
        footer_layout.addWidget(self.btn_takeover)

        self.btn_confirm = QPushButton("Confirm & Submit")
        self.btn_confirm.setCursor(Qt.PointingHandCursor)
        self.btn_confirm.setStyleSheet(f"""
            QPushButton {{
                background-color: {success_color};
                border: 1px solid {success_color};
                border-radius: 6px;
                color: #FFFFFF;
                padding: 8px 22px;
                font-weight: 700;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #2EA043;
            }}
        """)
        self.btn_confirm.clicked.connect(self._on_confirm_clicked)
        footer_layout.addWidget(self.btn_confirm)

        layout.addLayout(footer_layout)

    def _clean_provenance(self, prov: Any) -> Tuple[str, str]:
        """Formats provenance to clean badge text and detailed tooltip."""
        if hasattr(prov, "source_domain"):
            domain = str(prov.source_domain).upper()
            key = getattr(prov, "source_key", "")
            conf = getattr(prov, "confidence", 1.0)
            short_key = key.split(".")[-1] if key else ""
            display = f"{domain} ({short_key})" if short_key else f"{domain}_FACT"
            tooltip = f"Source: {prov.source_domain} | Key: {key} | Confidence: {conf:.1f}"
            return display, tooltip
        prov_str = str(prov or "")
        if "FieldProvenance" in prov_str:
            import re
            m_dom = re.search(r"source_domain=[\'\"]([^\'\"]+)[\'\"]", prov_str)
            m_key = re.search(r"source_key=[\'\"]([^\'\"]+)[\'\"]", prov_str)
            dom = m_dom.group(1).upper() if m_dom else "FACT"
            key = m_key.group(1) if m_key else ""
            short_key = key.split(".")[-1] if key else ""
            display = f"{dom} ({short_key})" if short_key else f"{dom}_FACT"
            return display, prov_str
        return prov_str or "PROFILE_FACT", prov_str

    def _populate_table(self) -> None:
        """Populates the review table from field_details dict."""
        import os, re
        self.table.setRowCount(len(self.field_details))

        hash_aliases = {
            "street": "Address",
            "city": "City",
            "state": "State",
            "postalcode": "Zip Code",
            "zip": "Zip Code",
            "phone-secondary": "Phone",
            "resume": "Upload Resume",
            "firstname": "First Name",
            "lastname": "Last Name",
            "email": "Email",
        }

        for row, (field_name, field_info) in enumerate(self.field_details.items()):
            if isinstance(field_info, dict):
                label_txt = field_info.get("label") or field_name
                raw_val = field_info.get("value")
                val = "" if raw_val is None else str(raw_val).strip()
                prov_raw = field_info.get("provenance", "PROFILE_FACT")
                is_req = field_info.get("required", field_info.get("is_required", False))
                field_id = field_info.get("name") or field_info.get("field_id", "")
                mapping_hint = field_info.get("mapping", "")
            else:
                label_txt = str(field_name)
                val = str(field_info).strip()
                prov_raw = "PROFILE_FACT"
                is_req = False
                field_id = ""
                mapping_hint = ""

            # If label looks like a technical random hash, check known aliases
            if re.match(r"^[a-z0-9_-]{7,}$", label_txt, re.I):
                for alias_k, alias_v in hash_aliases.items():
                    if alias_k in (field_id or "").lower() or alias_k in mapping_hint.lower():
                        label_txt = alias_v
                        break

            req_marker = " *" if is_req else ""
            label_item = QTableWidgetItem(f"{label_txt}{req_marker}")
            if field_id and field_id != label_txt:
                label_item.setToolTip(f"DOM Identifier: {field_id}")
            label_item.setFlags(label_item.flags() ^ Qt.ItemIsEditable)

            # Format value nicely
            if not val:
                val_display = "[Optional — Not provided]"
                val_item = QTableWidgetItem(val_display)
                val_item.setForeground(QColor(COLORS.get("muted", "#8B949E")))
                font = val_item.font()
                font.setItalic(True)
                val_item.setFont(font)
            elif "/" in val and (val.endswith(".pdf") or val.endswith(".docx") or val.endswith(".doc")):
                fname = os.path.basename(val)
                clean_fname = re.sub(r"^res_[a-zA-Z0-9]+_[a-zA-Z0-9]+_", "", fname)
                clean_fname = re.sub(r"^res_[a-zA-Z0-9]+_", "", clean_fname)
                val_item = QTableWidgetItem(f"📄 {clean_fname}")
                val_item.setToolTip(f"File Path: {val}")
            else:
                val_item = QTableWidgetItem(val)
            val_item.setFlags(val_item.flags() ^ Qt.ItemIsEditable)

            prov_display, prov_tooltip = self._clean_provenance(prov_raw)
            prov_item = QTableWidgetItem(prov_display)
            prov_item.setTextAlignment(Qt.AlignCenter)
            if prov_tooltip:
                prov_item.setToolTip(prov_tooltip)
            prov_item.setFlags(prov_item.flags() ^ Qt.ItemIsEditable)

            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, val_item)
            self.table.setItem(row, 2, prov_item)

    def _on_confirm_clicked(self) -> None:
        notes = self.notes_input.text().strip() or None
        if self.on_confirmed_cb:
            self.on_confirmed_cb(notes)
        self.confirmed.emit(notes or "")
        self.accept()

    def _on_takeover_clicked(self) -> None:
        notes = self.notes_input.text().strip() or None
        if self.on_takeover_cb:
            self.on_takeover_cb(notes)
        self.takeover_requested.emit(notes or "")
        self.accept()

    def _on_cancel_clicked(self) -> None:
        reason = self.notes_input.text().strip() or "User rejected pre-submission review."
        if self.on_rejected_cb:
            self.on_rejected_cb(reason)
        self.rejected.emit(reason)
        self.reject()
