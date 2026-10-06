'''
Naukri Safety Gate & Human Review Engine (Phase 11)
Intercepts job applications at the final screen before submission.
Presents a structured, human-readable review summary of:
- Candidate CTC (current & expected)
- Notice period
- Resume attachment
- Filled screening questions with provenance & confidence scores
Enforces the Phase 11 hard safety lock: pause_before_submit is strictly respected.
'''

import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict, Literal, Callable

from modules.models import Job
from modules.helpers import print_lg
from modules.config_loader import (
    get_salary_preferences,
    get_notice_period,
    get_resume,
    get_platform,
)

ReviewDecision = Literal["APPROVE", "DISCARD", "MANUAL_REQUIRED"]


@dataclass
class ApplicationReviewSummary:
    """Consolidated summary of application details presented for human review."""
    job_id: str
    job_title: str
    company: str
    location: str
    source_url: str
    current_ctc: str
    expected_ctc: str
    notice_period: str
    resume_path: str
    resume_exists: bool
    filled_fields: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def format_table(self) -> str:
        """Renders an ASCII/Markdown formatted review card."""
        sep = "=" * 70
        sub_sep = "-" * 70
        lines = [
            sep,
            "APPLICATION SAFETY GATE REVIEW (Phase 11)",
            sep,
            f"Job ID       : {self.job_id}",
            f"Job Title    : {self.job_title}",
            f"Company      : {self.company}",
            f"Location     : {self.location}",
            f"Source URL   : {self.source_url}",
            sub_sep,
            "CANDIDATE PARAMETERS FOR VERIFICATION:",
            f"  Current CTC   : {self.current_ctc}",
            f"  Expected CTC  : {self.expected_ctc}",
            f"  Notice Period : {self.notice_period}",
            f"  Resume File   : {self.resume_path} ({'Found' if self.resume_exists else 'NOT FOUND ON DISK!'})",
            sub_sep,
            f"FILLED QUESTIONS & ANSWERS ({len(self.filled_fields)} items):",
        ]

        if not self.filled_fields:
            lines.append("  (No questionnaire required / 1-click apply)")
        else:
            for i, f in enumerate(self.filled_fields, 1):
                lbl = f.get("field", "Unknown Question")
                val = f.get("value", "")
                src = f.get("source", "rule")
                conf = f.get("confidence", 1.0)
                success = f.get("success", True)
                status_mark = "[OK]" if success else "[FAILED]"
                lines.append(f"  {i}. {lbl}")
                lines.append(f"     Answer: '{val}'  |  Source: {src}  |  Confidence: {conf:.2f}  {status_mark}")

        if self.warnings:
            lines.append(sub_sep)
            lines.append("WARNINGS:")
            for w in self.warnings:
                lines.append(f"  ! {w}")

        lines.append(sep)
        return "\n".join(lines)


@dataclass
class SafetyGateResult:
    """Outcome of the safety review process."""
    decision: ReviewDecision
    summary: ApplicationReviewSummary
    approved: bool
    notes: Optional[str] = None


_review_dispatcher = None

def _get_review_dispatcher():
    global _review_dispatcher
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QObject, Signal, Slot, Qt

    app = QApplication.instance()
    if not app:
        return None
    if _review_dispatcher is None:
        class _QtReviewDispatcher(QObject):
            request_review = Signal(object)

            def __init__(self):
                super().__init__()
                self.result = None
                self.request_review.connect(self._handle_review, Qt.BlockingQueuedConnection)

            @Slot(object)
            def _handle_review(self, summary_obj):
                self.result = _create_and_exec_qt_dialog(summary_obj)

        _review_dispatcher = _QtReviewDispatcher()
        _review_dispatcher.moveToThread(app.thread())
    return _review_dispatcher


def _create_and_exec_qt_dialog(summary: ApplicationReviewSummary) -> Optional[ReviewDecision]:
    """Renders a modern PySide6 dark-themed review dialog matching JobPilot theme."""
    try:
        from PySide6.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QFrame, QTextEdit
        )
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeySequence, QShortcut

        dlg = QDialog()
        dlg.setWindowTitle("JobPilot — Review Application")
        dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint)
        dlg.setFixedSize(680, 560)
        dlg.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 12px;
            }
            QLabel {
                color: #f0f6fc;
                font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
            }
            QFrame#card {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
            }
            QTextEdit {
                background-color: #0d1117;
                color: #f0f6fc;
                border: 1px solid #30363d;
                border-radius: 6px;
                font-family: 'Consolas', 'DejaVu Sans Mono', monospace;
                font-size: 12px;
                padding: 8px;
            }
            QPushButton#btn_approve {
                background-color: #238636;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border-radius: 6px;
                padding: 9px 18px;
                border: 1px solid rgba(240, 246, 252, 0.1);
                font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
            }
            QPushButton#btn_approve:hover {
                background-color: #2ea043;
            }
            QPushButton#btn_manual {
                background-color: #1f6feb;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border-radius: 6px;
                padding: 9px 18px;
                border: 1px solid rgba(240, 246, 252, 0.1);
                font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
            }
            QPushButton#btn_manual:hover {
                background-color: #388bfd;
            }
            QPushButton#btn_discard {
                background-color: #da3633;
                color: #ffffff;
                font-size: 13px;
                font-weight: 700;
                border-radius: 6px;
                padding: 9px 18px;
                border: 1px solid rgba(240, 246, 252, 0.1);
                font-family: 'Segoe UI', Ubuntu, Cantarell, sans-serif;
            }
            QPushButton#btn_discard:hover {
                background-color: #f85149;
            }
        """)

        decision = [None]

        def on_approve():
            decision[0] = "APPROVE"
            dlg.accept()

        def on_manual():
            decision[0] = "MANUAL_REQUIRED"
            dlg.accept()

        def on_discard():
            decision[0] = "DISCARD"
            dlg.reject()

        main_layout = QVBoxLayout(dlg)
        main_layout.setContentsMargins(20, 18, 20, 18)
        main_layout.setSpacing(14)

        # 1. Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)

        pill = QLabel("NAUKRI")
        pill.setStyleSheet("""
            background-color: #ff5f15;
            color: #ffffff;
            font-weight: 800;
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
        """)
        title_row.addWidget(pill)

        title_lbl = QLabel(f"Review Application: {summary.job_title}")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #f0f6fc;")
        title_row.addWidget(title_lbl, 1)
        header_layout.addLayout(title_row)

        sub_lbl = QLabel(f"{summary.company}   •   {summary.location}   •   Job ID: {summary.job_id}")
        sub_lbl.setStyleSheet("font-size: 12px; color: #8b949e; margin-left: 2px;")
        header_layout.addWidget(sub_lbl)
        main_layout.addLayout(header_layout)

        # 2. Candidate Parameters Card
        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        card_title = QLabel("Candidate Verification Parameters")
        card_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #ff5f15;")
        card_layout.addWidget(card_title)

        resume_status = "Found" if summary.resume_exists else "NOT FOUND"
        details_lbl = QLabel(
            f"Current CTC: {summary.current_ctc}    •    "
            f"Expected CTC: {summary.expected_ctc}    •    "
            f"Notice Period: {summary.notice_period}\n"
            f"Resume: {summary.resume_path} ({resume_status})"
        )
        details_lbl.setStyleSheet("font-size: 12px; color: #c9d1d9; line-height: 1.4;")
        card_layout.addWidget(details_lbl)
        main_layout.addWidget(card)

        # 3. Filled Questions Card
        q_card = QFrame()
        q_card.setObjectName("card")
        q_layout = QVBoxLayout(q_card)
        q_layout.setContentsMargins(12, 10, 12, 10)
        q_layout.setSpacing(6)

        q_title = QLabel(f"Filled Questions ({len(summary.filled_fields)} items)")
        q_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #ff5f15;")
        q_layout.addWidget(q_title)

        txt = QTextEdit()
        txt.setReadOnly(True)
        if summary.filled_fields:
            q_lines = []
            for idx, f in enumerate(summary.filled_fields, 1):
                f_name = f.get("field", "Question")
                f_val = f.get("value", "")
                f_src = f.get("source", "rule")
                f_conf = f.get("confidence", 1.0)
                q_lines.append(f"{idx}. {f_name}\n   Answer: '{f_val}'  (Source: {f_src}, Conf: {f_conf:.2f})")
            txt.setPlainText("\n\n".join(q_lines))
        else:
            txt.setPlainText("No questionnaire required (1-click direct apply).")
        q_layout.addWidget(txt)
        main_layout.addWidget(q_card, 1)

        # 4. Action Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_approve = QPushButton("✓ Approve & Submit  [Enter]")
        btn_approve.setObjectName("btn_approve")
        btn_approve.clicked.connect(on_approve)
        btn_row.addWidget(btn_approve)

        btn_manual = QPushButton("⚡ Complete in Browser  [M]")
        btn_manual.setObjectName("btn_manual")
        btn_manual.clicked.connect(on_manual)
        btn_row.addWidget(btn_manual)

        btn_row.addStretch()

        btn_discard = QPushButton("✕ Discard  [Esc]")
        btn_discard.setObjectName("btn_discard")
        btn_discard.clicked.connect(on_discard)
        btn_row.addWidget(btn_discard)

        main_layout.addLayout(btn_row)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key_Return), dlg, on_approve)
        QShortcut(QKeySequence(Qt.Key_Enter), dlg, on_approve)
        QShortcut(QKeySequence("A"), dlg, on_approve)
        QShortcut(QKeySequence("a"), dlg, on_approve)
        QShortcut(QKeySequence("M"), dlg, on_manual)
        QShortcut(QKeySequence("m"), dlg, on_manual)
        QShortcut(QKeySequence(Qt.Key_Escape), dlg, on_discard)
        QShortcut(QKeySequence("D"), dlg, on_discard)
        QShortcut(QKeySequence("d"), dlg, on_discard)

        btn_approve.setFocus()
        dlg.exec()
        return decision[0]
    except Exception as e:
        print_lg(f"[NaukriSafetyGate] PySide6 GUI notice ({e}). Falling back to Tkinter dialog.")
        return None


def _show_qt_review_dialog(summary: ApplicationReviewSummary) -> Optional[ReviewDecision]:
    """Renders a modern PySide6 dark-themed review dialog safely on the main GUI thread."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QThread

        app = QApplication.instance()
        if not app:
            return None

        # If already on the Qt main thread, run directly
        if QThread.currentThread() == app.thread():
            return _create_and_exec_qt_dialog(summary)

        # If running on a worker thread, dispatch to Qt main thread
        dispatcher = _get_review_dispatcher()
        if dispatcher:
            dispatcher.request_review.emit(summary)
            return dispatcher.result
        return None
    except Exception as e:
        print_lg(f"[NaukriSafetyGate] Qt review dispatch notice: {e}")
        return None


def show_gui_review_dialog(summary: ApplicationReviewSummary) -> Optional[ReviewDecision]:
    """
    Renders an interactive desktop GUI window (PySide6 with Tkinter fallback)
    allowing the user to review the filled application before submission.
    Returns:
        "APPROVE", "DISCARD", "MANUAL_REQUIRED", or None if GUI is unavailable.
    """
    import sys
    import os

    # In automated unit test environments, avoid popping up blocking desktop windows
    if "unittest" in sys.modules or os.environ.get("TESTING") == "1":
        return None

    # Check if graphical display is available
    if sys.platform != "win32" and not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return None

    # 1. Try modern PySide6 Qt6 dialog first
    try:
        qt_decision = _show_qt_review_dialog(summary)
        if qt_decision is not None:
            return qt_decision
    except Exception:
        pass

    # 2. Resilient Tkinter fallback
    try:
        import tkinter as tk
    except ImportError:
        return None

    decision = [None]

    try:
        root = tk.Tk()
        root.title("JobPilot — Human Review Gate")
        root.geometry("680x560")
        root.minsize(580, 480)
        root.configure(bg="#0F1117")

        # Resolve clean system vector font
        try:
            from tkinter import font as tkfont
            sys_font = tkfont.nametofont("TkDefaultFont").cget("family") or "DejaVu Sans"
        except Exception:
            sys_font = "DejaVu Sans"

        # Always on top so it appears right over Chrome
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        # 1. Header Frame (Top)
        header = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        header.pack(fill="x", side="top")

        # Platform badge + Title row
        title_row = tk.Frame(header, bg="#161B22")
        title_row.pack(fill="x")

        plat_pill = tk.Label(
            title_row,
            text=" NAUKRI ",
            font=(sys_font, 9, "bold"),
            fg="#FFFFFF",
            bg="#FF5F15",
            padx=6,
            pady=2,
        )
        plat_pill.pack(side="left", padx=(0, 10))

        title_lbl = tk.Label(
            title_row,
            text=f"Review Application: {summary.job_title}",
            font=(sys_font, 12, "bold"),
            fg="#F0F6FC",
            bg="#161B22",
            wraplength=540,
            justify="left",
        )
        title_lbl.pack(side="left", fill="x", expand=True)

        sub_text = f"{summary.company}   |   {summary.location}   |   Job ID: {summary.job_id}"
        sub_lbl = tk.Label(
            header,
            text=sub_text,
            font=(sys_font, 9),
            fg="#8B949E",
            bg="#161B22",
        )
        sub_lbl.pack(anchor="w", pady=(4, 0))

        # 2. Action Buttons Frame (Bottom) — Packed FIRST before main_frame to prevent cutoff!
        btn_bar = tk.Frame(root, bg="#161B22", padx=20, pady=12, highlightbackground="#262C36", highlightthickness=1)
        btn_bar.pack(fill="x", side="bottom")

        def on_approve(event=None):
            decision[0] = "APPROVE"
            root.destroy()

        def on_discard(event=None):
            decision[0] = "DISCARD"
            root.destroy()

        def on_manual(event=None):
            decision[0] = "MANUAL_REQUIRED"
            root.destroy()

        # Keyboard bindings
        root.bind("<Return>", on_approve)
        root.bind("<a>", on_approve)
        root.bind("<A>", on_approve)
        root.bind("<d>", on_discard)
        root.bind("<D>", on_discard)
        root.bind("<Escape>", on_discard)
        root.bind("<m>", on_manual)
        root.bind("<M>", on_manual)

        approve_btn = tk.Button(
            btn_bar,
            text="✓ Approve & Submit  [Enter]",
            command=on_approve,
            bg="#2EA043",
            fg="#FFFFFF",
            activebackground="#3FB950",
            activeforeground="#FFFFFF",
            font=(sys_font, 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        approve_btn.pack(side="left", padx=(0, 10))

        manual_btn = tk.Button(
            btn_bar,
            text="⚡ Complete in Browser  [M]",
            command=on_manual,
            bg="#1F6FEB",
            fg="#FFFFFF",
            activebackground="#388BFD",
            activeforeground="#FFFFFF",
            font=(sys_font, 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        manual_btn.pack(side="left", padx=(0, 10))

        discard_btn = tk.Button(
            btn_bar,
            text="✕ Discard  [Esc]",
            command=on_discard,
            bg="#DA3633",
            fg="#FFFFFF",
            activebackground="#F85149",
            activeforeground="#FFFFFF",
            font=(sys_font, 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
            relief="flat",
            bd=0,
        )
        discard_btn.pack(side="right")

        # 3. Main Body (Middle) — Fills remaining vertical space
        main_frame = tk.Frame(root, bg="#0F1117", padx=20, pady=12)
        main_frame.pack(fill="both", expand=True)

        # Candidate Details Card
        card = tk.LabelFrame(
            main_frame,
            text=" Candidate Verification Parameters ",
            font=(sys_font, 9, "bold"),
            fg="#FF5F15",
            bg="#161B22",
            padx=12,
            pady=8,
            highlightbackground="#262C36",
            highlightthickness=1,
            relief="flat",
        )
        card.pack(fill="x", pady=(0, 10))

        param_text = (
            f"Current CTC: {summary.current_ctc}    |    "
            f"Expected CTC: {summary.expected_ctc}    |    "
            f"Notice Period: {summary.notice_period}\n"
            f"Resume: {summary.resume_path} ({'Found' if summary.resume_exists else 'NOT FOUND'})"
        )
        tk.Label(
            card,
            text=param_text,
            font=(sys_font, 9),
            fg="#F0F6FC",
            bg="#161B22",
            justify="left",
        ).pack(anchor="w")

        # Questions Card
        q_frame = tk.LabelFrame(
            main_frame,
            text=f" Filled Questions ({len(summary.filled_fields)} items) ",
            font=(sys_font, 9, "bold"),
            fg="#FF5F15",
            bg="#161B22",
            padx=12,
            pady=8,
            highlightbackground="#262C36",
            highlightthickness=1,
            relief="flat",
        )
        q_frame.pack(fill="both", expand=True)

        txt = tk.Text(
            q_frame,
            bg="#0D1117",
            fg="#F0F6FC",
            insertbackground="#F0F6FC",
            font=("monospace", 9),
            wrap="word",
            relief="flat",
            padx=8,
            pady=8,
            height=6,
            highlightbackground="#262C36",
            highlightthickness=1,
        )
        scroll = tk.Scrollbar(q_frame, command=txt.yview)
        txt.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        if summary.filled_fields:
            for idx, f in enumerate(summary.filled_fields, 1):
                f_name = f.get("field", "Question")
                f_val = f.get("value", "")
                f_src = f.get("source", "rule")
                f_conf = f.get("confidence", 1.0)
                txt.insert("end", f"{idx}. {f_name}\n   Answer: '{f_val}'  (Source: {f_src}, Conf: {f_conf:.2f})\n\n")
        else:
            txt.insert("end", "No questionnaire required (1-click direct apply).\n")

        txt.configure(state="disabled")

        # Center on screen cleanly
        root.update_idletasks()
        w = 680
        h = 560
        x = max(0, (root.winfo_screenwidth() // 2) - (w // 2))
        y = max(0, (root.winfo_screenheight() // 2) - (h // 2))
        root.geometry(f"{w}x{h}+{x}+{y}")

        approve_btn.focus_set()
        root.mainloop()

        return decision[0]
    except Exception as e:
        print_lg(f"[NaukriSafetyGate] GUI dialog notice ({e}). Falling back to terminal prompt.")
        return None


class NaukriSafetyGate:
    """
    Safety Gate manager for pausing before submission and gathering human review.
    """

    def __init__(
        self,
        browser: Any = None,
        pause_before_submit: Optional[bool] = None,
        review_handler: Optional[Callable[[ApplicationReviewSummary], ReviewDecision]] = None,
    ):
        self.browser = browser
        self._explicit_pause = (pause_before_submit is not None)
        # Load from config if not explicitly passed
        if pause_before_submit is None:
            naukri_cfg = get_platform("naukri")
            self.pause_before_submit = bool(naukri_cfg.get("pause_before_submit", False))
        else:
            self.pause_before_submit = bool(pause_before_submit)

        self.review_handler = review_handler

    @property
    def driver(self):
        return getattr(self.browser, "driver", self.browser)

    def build_summary(
        self,
        job: Job,
        filled_fields: Optional[List[Dict[str, Any]]] = None,
        resume_path: Optional[str] = None,
    ) -> ApplicationReviewSummary:
        """Constructs an ApplicationReviewSummary from job and filled fields."""
        fields_list = filled_fields or []
        sal = get_salary_preferences()
        curr_ctc_val = sal.get("current_ctc", 350000)
        exp_ctc_val = sal.get("desired_salary", 550000)
        notice_days = get_notice_period()

        # Check if CTC was overridden in filled fields
        for f in fields_list:
            lbl = f.get("field", "").lower()
            val = str(f.get("value", ""))
            if "ctc" in lbl or "salary" in lbl or "pay" in lbl:
                if any(w in lbl for w in ["current", "present"]):
                    curr_ctc_val = val
                else:
                    exp_ctc_val = val
            elif "notice" in lbl:
                notice_days = val

        curr_ctc_str = f"INR {curr_ctc_val}" if not str(curr_ctc_val).startswith("INR") else str(curr_ctc_val)
        exp_ctc_str = f"INR {exp_ctc_val}" if not str(exp_ctc_val).startswith("INR") else str(exp_ctc_val)
        notice_str = f"{notice_days} days" if str(notice_days).isdigit() else str(notice_days)

        res_path = resume_path or get_resume()
        res_exists = os.path.exists(res_path) if res_path else False

        warnings = []
        if not res_exists:
            warnings.append(f"Configured resume file was not found on disk at: '{res_path}'")

        for f in fields_list:
            if f.get("source") == "llm" and f.get("confidence", 1.0) < 0.75:
                warnings.append(f"Low confidence LLM answer for question: '{f.get('field')}'")
            if not f.get("success", True):
                warnings.append(f"Field filling failed for: '{f.get('field')}'")

        return ApplicationReviewSummary(
            job_id=job.job_id,
            job_title=job.title,
            company=job.company,
            location=job.location,
            source_url=job.source_url,
            current_ctc=curr_ctc_str,
            expected_ctc=exp_ctc_str,
            notice_period=notice_str,
            resume_path=res_path or "Not configured",
            resume_exists=res_exists,
            filled_fields=fields_list,
            warnings=warnings,
        )

    def review(
        self,
        job: Job,
        filled_fields: Optional[List[Dict[str, Any]]] = None,
        resume_path: Optional[str] = None,
    ) -> SafetyGateResult:
        """
        Executes the human review step:
        1. Compiles and prints review summary.
        2. Pauses if pause_before_submit is True.
        3. Attempts graphical GUI window review (if available and enabled).
        4. Falls back to interactive CLI prompt.
        5. Returns user decision (APPROVE, DISCARD, or MANUAL_REQUIRED).
        """
        summary = self.build_summary(job, filled_fields, resume_path=resume_path)

        # Output summary to console
        print_lg(summary.format_table())

        # Check pause setting: use explicit if passed, otherwise check dynamic config
        if self._explicit_pause:
            pause = self.pause_before_submit
        else:
            naukri_cfg = get_platform("naukri")
            pause = bool(naukri_cfg.get("pause_before_submit", self.pause_before_submit))

        if not pause:
            print_lg("[NaukriSafetyGate] pause_before_submit is False. Proceeding without human pause.")
            return SafetyGateResult(
                decision="APPROVE",
                summary=summary,
                approved=True,
                notes="Automatic approval: pause_before_submit is disabled.",
            )

        # If a custom review callback/handler is provided (e.g., in unit tests)
        if self.review_handler:
            decision = self.review_handler(summary)
            approved = (decision == "APPROVE")
            print_lg(f"[NaukriSafetyGate] Review handler returned decision: {decision}")
            return SafetyGateResult(
                decision=decision,
                summary=summary,
                approved=approved,
                notes=f"Decision from review handler: {decision}",
            )

        # Check if GUI review window is enabled and available
        naukri_cfg = get_platform("naukri")
        use_gui = naukri_cfg.get("gui_review_dialog", True)
        if use_gui:
            gui_decision = show_gui_review_dialog(summary)
            if gui_decision in ["APPROVE", "DISCARD", "MANUAL_REQUIRED"]:
                approved = (gui_decision == "APPROVE")
                print_lg(f"[NaukriSafetyGate] Human decision from GUI window: {gui_decision}")
                return SafetyGateResult(
                    decision=gui_decision,
                    summary=summary,
                    approved=approved,
                    notes=f"Decision from GUI dialog: {gui_decision}",
                )

        # Interactive CLI review prompt (fallback)
        print_lg("[NaukriSafetyGate] PAUSED: Review application above before proceeding.")
        print_lg("  [A] Approve & Proceed to submission (Phase 12)")
        print_lg("  [D] Discard this application and close modal")
        print_lg("  [M] Pause for Manual completion in browser window")

        try:
            choice = input("Enter decision [A/d/m]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Safe fallback for non-interactive environments
            print_lg("[NaukriSafetyGate] Non-interactive environment detected. Holding application in MANUAL_REQUIRED.")
            return SafetyGateResult(
                decision="MANUAL_REQUIRED",
                summary=summary,
                approved=False,
                notes="Non-interactive stdin: safely routed to MANUAL_REQUIRED.",
            )

        if choice in ["d", "discard"]:
            return SafetyGateResult(
                decision="DISCARD",
                summary=summary,
                approved=False,
                notes="Discarded by user during review.",
            )
        elif choice in ["m", "manual"]:
            return SafetyGateResult(
                decision="MANUAL_REQUIRED",
                summary=summary,
                approved=False,
                notes="User requested manual completion in browser.",
            )
        else:
            return SafetyGateResult(
                decision="APPROVE",
                summary=summary,
                approved=True,
                notes="Approved by user during review.",
            )
