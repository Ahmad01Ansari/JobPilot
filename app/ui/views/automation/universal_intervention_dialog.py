"""Human-in-the-Loop Universal Intervention Dialog for JobPilot Desktop UI.

Coordinates user assistance when security challenges (CAPTCHA, Login), unknown
required form fields, or site-specific interactions occur, without bot-bypass or evasion.
"""

from typing import Any, Callable, Dict, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.automation_events import InterventionType
from app.ui.theme import COLORS


class UniversalInterventionDialog(QDialog):
    """Modal dialog presenting actionable instructions during automation intervention."""

    resumed = Signal(dict)  # resolution data (e.g. {"answer": ...})
    takeover_requested = Signal(str)  # user notes
    cancelled = Signal(str)  # cancellation reason

    def __init__(
        self,
        intervention_type: InterventionType = InterventionType.MANUAL_ACTION_REQUIRED,
        message: str = "",
        action_url: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        on_resumed: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_takeover: Optional[Callable[[Optional[str]], None]] = None,
        on_cancelled: Optional[Callable[[str], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.intervention_type = intervention_type
        self.message_text = message or "User intervention is required to proceed."
        self.action_url = action_url or ""
        self.details = details or {}

        self.on_resumed_cb = on_resumed
        self.on_takeover_cb = on_takeover
        self.on_cancelled_cb = on_cancelled

        self.setWindowTitle("Action Required — Automation Paused")
        self.setFixedSize(580, 420)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        self._setup_ui()

    def _setup_ui(self) -> None:
        bg_color = COLORS.get("surface", "#161B22")
        border_color = COLORS.get("border", "#30363D")
        text_color = COLORS.get("text", "#F0F6FC")
        muted_color = COLORS.get("text_muted", "#8B949E")
        warning_color = COLORS.get("warning", "#D29922")
        primary_color = COLORS.get("primary", "#1F6FEB")
        danger_color = COLORS.get("danger", "#DA3633")

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 12px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Header with Dynamic Icon and Context
        hdr_layout = QHBoxLayout()
        hdr_layout.setSpacing(14)

        icon_char = "🛡️"
        type_str = getattr(self.intervention_type, "value", str(self.intervention_type))
        if "LOGIN" in type_str:
            icon_char = "🔑"
        elif "TWO_FACTOR" in type_str or "OTP" in type_str:
            icon_char = "🔢"
        elif "CAPTCHA" in type_str:
            icon_char = "🤖"
        elif "UNKNOWN" in type_str:
            icon_char = "❓"

        icon_lbl = QLabel(icon_char)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(46, 46)
        icon_lbl.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('warning_subtle', '#D2992218')};
                border: 1px solid {border_color};
                border-radius: 10px;
                font-size: 22px;
            }}
        """)
        hdr_layout.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)

        title_text = "Human Intervention Required"
        if type_str == "CAPTCHA_DETECTED":
            title_text = "Security Verification Detected"
        elif type_str == "LOGIN_REQUIRED":
            title_text = "Account Authentication Required"
        elif "TWO_FACTOR" in type_str or "OTP" in type_str:
            title_text = "Verification Code (OTP) Required"
        elif type_str == "UNKNOWN_REQUIRED_FIELD":
            title_text = "Unrecognized Required Question"

        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {text_color};")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel(f"STATE: PAUSED_FOR_INTERVENTION [{type_str}]")
        sub_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {warning_color}; letter-spacing: 0.5px;")
        title_box.addWidget(sub_lbl)
        hdr_layout.addLayout(title_box, 1)

        layout.addLayout(hdr_layout)

        # Separator line
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"background-color: {COLORS.get('border_light', '#21262D')}; max-height: 1px;")
        layout.addWidget(sep)

        # Message Container
        msg_frame = QFrame()
        msg_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS.get('surface_alt', '#0D1117')};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 12px;
            }}
        """)
        msg_layout = QVBoxLayout(msg_frame)
        msg_layout.setContentsMargins(12, 10, 12, 10)
        msg_layout.setSpacing(6)

        msg_body = QLabel(self.message_text)
        msg_body.setWordWrap(True)
        msg_body.setStyleSheet(f"color: {text_color}; font-size: 13px; line-height: 1.4; background: transparent; border: none;")
        msg_layout.addWidget(msg_body)

        if self.action_url:
            url_line = QLabel(f"<b>URL:</b> <a href='{self.action_url}' style='color: {primary_color};'>{self.action_url}</a>")
            url_line.setOpenExternalLinks(True)
            url_line.setStyleSheet("font-size: 11px; background: transparent; border: none;")
            msg_layout.addWidget(url_line)

        layout.addWidget(msg_frame)

        # Optional Field Input (for UNKNOWN_REQUIRED_FIELD or TWO_FACTOR_AUTH / OTP)
        self.field_input = None
        self.field_inputs: Dict[str, QLineEdit] = {}
        is_otp = "TWO_FACTOR" in type_str or "OTP" in type_str
        if type_str == "UNKNOWN_REQUIRED_FIELD":
            unresolved = self.details.get("unresolved_fields") or []
            if not unresolved:
                single_fn = self.details.get("field_name") or self.details.get("label")
                if single_fn:
                    unresolved = [single_fn]

            if unresolved:
                fields_container = QVBoxLayout()
                fields_container.setSpacing(10)

                for fn in unresolved:
                    fn_str = str(fn).strip()
                    if not fn_str:
                        continue
                    item_box = QVBoxLayout()
                    item_box.setSpacing(4)
                    lbl_prompt = QLabel(f"Question / Field: <b>{fn_str}</b>")
                    lbl_prompt.setStyleSheet(f"color: {text_color}; font-size: 13px;")
                    lbl_prompt.setWordWrap(True)
                    item_box.addWidget(lbl_prompt)

                    inp = QLineEdit()
                    inp.setPlaceholderText(f"Enter answer for '{fn_str}'...")
                    inp.setStyleSheet(f"""
                        QLineEdit {{
                            background-color: {COLORS.get('surface_alt', '#0D1117')};
                            border: 1px solid {border_color};
                            border-radius: 6px;
                            padding: 8px 10px;
                            color: {text_color};
                            font-size: 13px;
                        }}
                        QLineEdit:focus {{
                            border: 1px solid {primary_color};
                        }}
                    """)
                    inp.returnPressed.connect(self._on_resume_clicked)
                    item_box.addWidget(inp)
                    fields_container.addLayout(item_box)
                    self.field_inputs[fn_str] = inp

                if self.field_inputs:
                    self.field_input = list(self.field_inputs.values())[0]

                if len(self.field_inputs) > 2:
                    scroll_widget = QWidget()
                    scroll_widget.setLayout(fields_container)
                    scroll_area = QScrollArea()
                    scroll_area.setWidgetResizable(True)
                    scroll_area.setWidget(scroll_widget)
                    scroll_area.setMaximumHeight(220)
                    scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")
                    layout.addWidget(scroll_area)
                else:
                    layout.addLayout(fields_container)
            else:
                input_box = QVBoxLayout()
                input_box.setSpacing(4)
                lbl_prompt = QLabel("Provide answer for missing field:")
                lbl_prompt.setStyleSheet(f"color: {text_color}; font-size: 12px;")
                input_box.addWidget(lbl_prompt)

                self.field_input = QLineEdit()
                self.field_input.setPlaceholderText("Enter value to populate...")
                self.field_input.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {COLORS.get('surface_alt', '#0D1117')};
                        border: 1px solid {border_color};
                        border-radius: 6px;
                        padding: 8px 10px;
                        color: {text_color};
                        font-size: 13px;
                    }}
                """)
                self.field_input.returnPressed.connect(self._on_resume_clicked)
                input_box.addWidget(self.field_input)
                layout.addLayout(input_box)
        elif is_otp:
            input_box = QVBoxLayout()
            input_box.setSpacing(6)
            lbl_prompt = QLabel("Enter Verification Code (OTP):")
            lbl_prompt.setStyleSheet(f"color: {text_color}; font-size: 13px; font-weight: 600;")
            input_box.addWidget(lbl_prompt)

            self.field_input = QLineEdit()
            self.field_input.setPlaceholderText("e.g. 123456")
            self.field_input.setMaxLength(12)
            self.field_input.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {COLORS.get('surface_alt', '#0D1117')};
                    border: 1px solid {primary_color};
                    border-radius: 6px;
                    padding: 10px 14px;
                    color: {text_color};
                    font-size: 16px;
                    font-weight: 700;
                    letter-spacing: 3px;
                }}
                QLineEdit:focus {{
                    border: 1px solid #58A6FF;
                }}
            """)
            self.field_input.returnPressed.connect(self._on_resume_clicked)
            input_box.addWidget(self.field_input)

            inst_lbl = QLabel(
                "💡 A verification code was sent to your email or phone. "
                "Type the code above and click <b>'Verify & Continue'</b>, or enter it directly in the open Chrome browser."
            )
            inst_lbl.setWordWrap(True)
            inst_lbl.setStyleSheet(f"color: {muted_color}; font-size: 12px; line-height: 1.3;")
            input_box.addWidget(inst_lbl)
            layout.addLayout(input_box)
        else:
            inst_lbl = QLabel(
                "💡 <b>Instructions:</b> The active Chrome window has been kept open and focused. "
                "Complete the requested action in the browser, then click 'I've Solved It / Continue' below."
            )
            inst_lbl.setWordWrap(True)
            inst_lbl.setStyleSheet(f"color: {muted_color}; font-size: 12px; line-height: 1.3;")
            layout.addWidget(inst_lbl)

        layout.addStretch()

        # Action Buttons Footer
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel Run")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {danger_color};
                border-radius: 6px;
                color: {danger_color};
                padding: 8px 14px;
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
                padding: 8px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {border_color};
            }}
        """)
        self.btn_takeover.clicked.connect(self._on_takeover_clicked)
        footer_layout.addWidget(self.btn_takeover)

        btn_label = "Verify & Continue" if is_otp else "I've Solved It / Continue"
        self.btn_resume = QPushButton(btn_label)
        self.btn_resume.setCursor(Qt.PointingHandCursor)
        self.btn_resume.setStyleSheet(f"""
            QPushButton {{
                background-color: {primary_color};
                border: 1px solid {primary_color};
                border-radius: 6px;
                color: #FFFFFF;
                padding: 8px 18px;
                font-weight: 700;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #388BFD;
            }}
        """)
        self.btn_resume.clicked.connect(self._on_resume_clicked)
        footer_layout.addWidget(self.btn_resume)

        layout.addLayout(footer_layout)

    def _on_resume_clicked(self) -> None:
        data: Dict[str, Any] = {"action": "RESUME"}
        if self.field_inputs:
            has_unresolved_list = bool(self.details.get("unresolved_fields"))
            for field_name, inp in self.field_inputs.items():
                val = inp.text().strip()
                if has_unresolved_list or len(self.field_inputs) > 1:
                    data[field_name] = val
                if "value" not in data:
                    data["value"] = val
            if "value" not in data and self.field_inputs:
                data["value"] = list(self.field_inputs.values())[0].text().strip()
        elif self.field_input:
            val = self.field_input.text().strip()
            data["value"] = val
            type_str = getattr(self.intervention_type, "value", str(self.intervention_type))
            if "TWO_FACTOR" in type_str or "OTP" in type_str:
                data["code"] = val
        if self.on_resumed_cb:
            self.on_resumed_cb(data)
        self.resumed.emit(data)
        self.accept()

    def _on_takeover_clicked(self) -> None:
        if self.on_takeover_cb:
            self.on_takeover_cb(None)
        self.takeover_requested.emit("User selected manual mode")
        self.accept()

    def _on_cancel_clicked(self) -> None:
        reason = "User cancelled automation during intervention."
        if self.on_cancelled_cb:
            self.on_cancelled_cb(reason)
        self.cancelled.emit(reason)
        self.reject()
