"""Timeline cards and bubbles for the JobPilot AI Pilot conversation stream.

Provides rich HTML/Markdown rendering (bold, italic, code, headers, bullets),
modern AI chat typography, and high-resolution milestone step stepper widgets.
"""

import html
import re
from typing import Callable, Dict, Optional
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.pilot.pilot_models import (
    InterventionKind,
    InterventionStatus,
    PilotActionType,
    PilotAuthor,
    PilotMessage,
    PilotRuleChange,
    PilotStep,
)
from app.ui.theme import COLORS


def format_pilot_markdown(raw_text: str) -> str:
    """Transforms raw markdown text into crisp, theme-styled HTML.

    Eliminates raw asterisks, double stars, and formatting glitches while
    preserving code blocks, headers, and bullet lists with ATS typography.
    """
    if not raw_text:
        return ""

    lines = raw_text.split("\n")
    html_lines = []

    # Detect and group table lines
    in_table = False
    table_lines = []

    def flush_table():
        nonlocal in_table, table_lines
        if not table_lines:
            return
        rows = []
        for tl in table_lines:
            cells = [c.strip() for c in tl.strip().strip("|").split("|")]
            rows.append(cells)
        if rows:
            header = rows[0]
            tbl_html = [
                f"<table style='width: 100%; border-collapse: collapse; margin: 8px 0; "
                f"font-size: 12px; background-color: {COLORS.get('surface', '#161B22')}; "
                f"border: 1px solid {COLORS.get('border', '#262C36')}; border-radius: 4px;'>"
            ]
            tbl_html.append(
                f"<thead><tr style='background-color: {COLORS.get('surface_elevated', '#22272E')}; "
                f"border-bottom: 2px solid {COLORS.get('border', '#262C36')};'>"
            )
            for h in header:
                h_esc = html.escape(h)
                h_esc = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", h_esc)
                tbl_html.append(
                    f"<th style='text-align: left; padding: 6px 10px; color: {COLORS.get('primary', '#FF5F15')}; "
                    f"font-weight: 600;'>{h_esc}</th>"
                )
            tbl_html.append("</tr></thead><tbody>")
            for row in rows[1:]:
                if all(re.match(r"^[-:\s]+$", c) for c in row if c):
                    continue
                tbl_html.append(f"<tr style='border-bottom: 1px solid {COLORS.get('border', '#262C36')};'>")
                for c in row:
                    c_esc = html.escape(c)
                    c_esc = re.sub(r"\*\*(.+?)\*\*", rf"<b style='color: {COLORS.get('text', '#F0F6FC')};'>\1</b>", c_esc)
                    c_esc = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", rf"<i style='color: {COLORS.get('text_muted', '#8B949E')};'>\1</i>", c_esc)
                    tbl_html.append(f"<td style='padding: 5px 10px; color: {COLORS.get('text', '#F0F6FC')};'>{c_esc}</td>")
                tbl_html.append("</tr>")
            tbl_html.append("</tbody></table>")
            html_lines.append("".join(tbl_html))
        table_lines = []
        in_table = False

    for line in lines:
        stripped = line.strip()

        # Handle markdown table rows
        if stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:-1]:
            in_table = True
            table_lines.append(stripped)
            continue
        elif in_table:
            flush_table()

        if not stripped:
            html_lines.append("<div style='height: 6px;'></div>")
            continue

        # Horizontal rule divider
        if stripped in ("---", "***", "___") or re.match(r"^-{3,}$", stripped):
            html_lines.append(
                f"<hr style='border: none; border-top: 1px solid {COLORS.get('border', '#262C36')}; margin: 8px 0;'>"
            )
            continue

        # Markdown Headers: #, ##, ###, ####, #####, ######
        header_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if header_match:
            level = len(header_match.group(1))
            header_text = html.escape(header_match.group(2).strip())
            header_text = re.sub(
                r"\*\*(.+?)\*\*",
                rf"<b style='color: inherit; font-weight: 700;'>\1</b>",
                header_text,
            )
            if level == 1:
                html_lines.append(
                    f"<div style='color: {COLORS.get('text', '#F0F6FC')}; "
                    f"font-size: 15px; font-weight: 700; margin-top: 10px; margin-bottom: 6px;'>"
                    f"{header_text}</div>"
                )
            elif level == 2:
                html_lines.append(
                    f"<div style='color: {COLORS.get('text', '#F0F6FC')}; "
                    f"font-size: 14px; font-weight: 700; margin-top: 8px; margin-bottom: 4px;'>"
                    f"{header_text}</div>"
                )
            elif level == 3:
                html_lines.append(
                    f"<div style='color: {COLORS.get('primary', '#FF5F15')}; "
                    f"font-size: 13px; font-weight: 700; margin-top: 8px; margin-bottom: 4px;'>"
                    f"{header_text}</div>"
                )
            else:
                html_lines.append(
                    f"<div style='color: {COLORS.get('primary', '#FF5F15')}; "
                    f"font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; "
                    f"margin-top: 6px; margin-bottom: 3px;'>"
                    f"{header_text}</div>"
                )
            continue

        # Bullets
        is_bullet = False
        prefix = ""
        if stripped.startswith("• ") or stripped.startswith("* ") or stripped.startswith("- "):
            is_bullet = True
            prefix = "&bull;&nbsp;&nbsp;"
            stripped = stripped[2:].strip()
        elif re.match(r"^\d+\.\s+", stripped):
            match = re.match(r"^(\d+\.)\s+", stripped)
            if match:
                is_bullet = True
                prefix = f"<span style='color: {COLORS.get('primary', '#FF5F15')}; font-weight: 600;'>{match.group(1)}</span>&nbsp;&nbsp;"
                stripped = stripped[match.end():].strip()

        # Escape baseline HTML
        content = html.escape(stripped)

        # Bold: **text** -> styled <b>
        content = re.sub(
            r"\*\*(.+?)\*\*",
            rf"<b style='color: {COLORS.get('text', '#F0F6FC')}; font-weight: 600;'>\1</b>",
            content,
        )

        # Italic: *text* -> styled <i>
        content = re.sub(
            r"(?<!\*)\*([^*]+?)\*(?!\*)",
            rf"<i style='color: {COLORS.get('text_muted', '#8B949E')};'>\1</i>",
            content,
        )

        # Inline Code: `text` -> styled <span>
        content = re.sub(
            r"`(.+?)`",
            rf"<span style='background-color: {COLORS.get('surface_elevated', '#22272E')}; "
            rf"color: {COLORS.get('accent', '#FF7A3D')}; border: 1px solid {COLORS.get('border', '#262C36')}; "
            rf"padding: 1px 5px; border-radius: 4px; font-family: monospace; font-size: 11px;'>\1</span>",
            content,
        )

        if is_bullet:
            html_lines.append(
                f"<div style='margin-left: 10px; margin-top: 3px; margin-bottom: 3px; "
                f"line-height: 1.45; color: {COLORS.get('text', '#F0F6FC')};'>"
                f"{prefix}{content}</div>"
            )
        else:
            html_lines.append(
                f"<div style='line-height: 1.5; color: {COLORS.get('text', '#F0F6FC')};'>"
                f"{content}</div>"
            )

    if in_table:
        flush_table()

    return "".join(html_lines)


class UserMessageCard(QFrame):
    """Clean bubble displaying candidate prompts."""

    def __init__(self, message: PilotMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setStyleSheet(f"""
            UserMessageCard {{
                background-color: {COLORS.get('surface_hover', '#262C36')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 12px;
                margin-left: 60px;
                margin-right: 8px;
                margin-top: 4px;
                margin-bottom: 4px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)

        header = QLabel("Candidate")
        header.setStyleSheet(
            f"color: {COLORS.get('primary', '#FF5F15')}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;"
        )
        layout.addWidget(header)

        body = QLabel()
        body.setTextFormat(Qt.RichText)
        body.setWordWrap(True)
        body.setText(format_pilot_markdown(message.body))
        body.setStyleSheet(f"font-size: 13px; line-height: 1.5;")
        layout.addWidget(body)


class PilotStepItemWidget(QWidget):
    """Renders a single high-resolution milestone step with compact status pills."""

    def __init__(self, step: PilotStep, parent=None):
        super().__init__(parent)
        self.step = step
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Pulse timer for live running animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(350)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_tick = 0

        # Status badge (compact, perfectly aligned pill)
        self.badge = QLabel()
        self.badge.setFixedWidth(56)
        self.badge.setFixedHeight(18)
        self.badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.badge)

        # Title text
        self.title = QLabel()
        self.title.setTextFormat(Qt.RichText)
        self.title.setWordWrap(True)
        self.title.setText(format_pilot_markdown(step.title))
        self.title.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px; line-height: 1.35;")
        layout.addWidget(self.title, 1)

        self.detail_lbl = QLabel(step.detail or "")
        self.detail_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px;")
        if not step.detail:
            self.detail_lbl.hide()
        layout.addWidget(self.detail_lbl)

        self._update_badge()

    def _on_pulse(self):
        if self.step.status == "running":
            self._pulse_tick = (self._pulse_tick + 1) % 4
            dots = "." * self._pulse_tick
            self.badge.setText(f"● RUN{dots:<2}")

    def set_status(self, status: str, detail: Optional[str] = None):
        self.step.status = status
        if detail:
            self.step.detail = detail
            self.detail_lbl.setText(detail)
            self.detail_lbl.show()
        self._update_badge()

    def _update_badge(self):
        if self.step.status == "done":
            if self._pulse_timer.isActive():
                self._pulse_timer.stop()
            self.badge.setText("✓ DONE")
            self.badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS.get('success_subtle', '#2EA04318')};
                    color: {COLORS.get('success', '#2EA043')};
                    border: 1px solid {COLORS.get('success', '#2EA043')};
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
            self.title.setStyleSheet("color: #C9D1D9; font-size: 11px; line-height: 1.35;")
        elif self.step.status == "failed":
            if self._pulse_timer.isActive():
                self._pulse_timer.stop()
            self.badge.setText("✕ SKIP")
            self.badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS.get('danger_subtle', '#F8514918')};
                    color: {COLORS.get('danger', '#F85149')};
                    border: 1px solid {COLORS.get('danger', '#F85149')};
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
            self.title.setStyleSheet("color: #8B949E; font-size: 11px; line-height: 1.35;")
        elif self.step.status == "wait":
            if self._pulse_timer.isActive():
                self._pulse_timer.stop()
            self.badge.setText("○ WAIT")
            self.badge.setStyleSheet("""
                QLabel {{
                    background-color: #161B22;
                    color: #8B949E;
                    border: 1px solid #30363D;
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
            self.title.setStyleSheet("color: #8B949E; font-size: 11px; line-height: 1.35;")
        else:  # running
            if not self._pulse_timer.isActive():
                self._pulse_timer.start()
            dots = "." * self._pulse_tick
            self.badge.setText(f"● RUN{dots:<2}")
            self.badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS.get('primary_subtle', '#FF5F1518')};
                    color: {COLORS.get('primary', '#FF5F15')};
                    border: 1px solid {COLORS.get('primary', '#FF5F15')};
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
            self.title.setStyleSheet("color: #FFFFFF; font-size: 11px; font-weight: 500; line-height: 1.35;")


class NeedsYouCard(QFrame):
    """Interactive human-in-the-loop decision card."""

    answered = Signal(str, str)  # intervention_id, answer

    def __init__(self, message: PilotMessage, parent=None):
        super().__init__(parent)
        self.message = message
        inv = message.intervention

        self.setStyleSheet(f"""
            NeedsYouCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 2px solid {COLORS.get('warning', '#D29922')};
                border-radius: 12px;
                padding: 12px;
                margin-top: 6px;
                margin-bottom: 6px;
                margin-right: 60px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        # Title strip
        title_strip = QHBoxLayout()
        icon = QLabel("⚠️ ACTION REQUIRED")
        icon.setStyleSheet(f"color: {COLORS.get('warning', '#D29922')}; font-weight: bold; font-size: 12px;")
        title_strip.addWidget(icon)
        title_strip.addStretch()
        layout.addLayout(title_strip)

        # Prompt text
        prompt = QLabel(inv.prompt if inv else "Action needed")
        prompt.setWordWrap(True)
        prompt.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 13px; font-weight: bold;")
        layout.addWidget(prompt)

        # Interactive controls based on status and kind
        if inv and inv.status == InterventionStatus.OPEN:
            if inv.options:
                options_box = QHBoxLayout()
                for opt in inv.options:
                    btn = QPushButton(opt)
                    btn.setCursor(Qt.PointingHandCursor)
                    btn.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {COLORS.get('surface', '#161B22')};
                            color: {COLORS.get('text', '#F0F6FC')};
                            border: 1px solid {COLORS.get('border', '#262C36')};
                            border-radius: 6px;
                            padding: 6px 12px;
                        }}
                        QPushButton:hover {{
                            border-color: {COLORS.get('primary', '#FF5F15')};
                        }}
                    """)
                    btn.clicked.connect(lambda _, val=opt: self._submit_answer(val))
                    options_box.addWidget(btn)
                layout.addLayout(options_box)
            else:
                input_row = QHBoxLayout()
                self.input_field = QLineEdit()
                placeholder = "Enter 2FA Code..." if inv.kind == InterventionKind.TWO_FACTOR else "Enter answer..."
                self.input_field.setPlaceholderText(placeholder)
                self.input_field.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {COLORS.get('surface', '#161B22')};
                        color: {COLORS.get('text', '#F0F6FC')};
                        border: 1px solid {COLORS.get('border', '#262C36')};
                        border-radius: 6px;
                        padding: 6px 10px;
                        font-size: 13px;
                    }}
                    QLineEdit:focus {{
                        border-color: {COLORS.get('primary', '#FF5F15')};
                    }}
                """)
                self.input_field.returnPressed.connect(self._on_input_submitted)
                input_row.addWidget(self.input_field, 1)

                submit_btn = QPushButton("Submit")
                submit_btn.setCursor(Qt.PointingHandCursor)
                submit_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {COLORS.get('primary', '#FF5F15')};
                        color: #FFFFFF;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 14px;
                        font-weight: bold;
                    }}
                    QPushButton:hover {{
                        background-color: {COLORS.get('primary_hover', '#E04F0B')};
                    }}
                """)
                submit_btn.clicked.connect(self._on_input_submitted)
                input_row.addWidget(submit_btn)
                layout.addLayout(input_row)
        else:
            resolved_label = QLabel(f"Resolved with: {inv.answer if inv else ''}")
            resolved_label.setStyleSheet(f"color: {COLORS.get('success', '#2EA043')}; font-size: 12px;")
            layout.addWidget(resolved_label)

    def _on_input_submitted(self):
        val = self.input_field.text().strip()
        if val:
            self._submit_answer(val)

    def _submit_answer(self, val: str):
        if self.message.intervention:
            self.answered.emit(self.message.intervention.id, val)


class RuleChangeCard(QFrame):
    """Displays an applied rule modification with an undo button."""

    undo_clicked = Signal(str)  # rule_change_id

    def __init__(self, message: PilotMessage, parent=None):
        super().__init__(parent)
        self.message = message
        change = message.rule_change

        self.setStyleSheet(f"""
            RuleChangeCard {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                border: 1px solid {COLORS.get('info', '#388BFD')};
                border-radius: 8px;
                padding: 8px 12px;
                margin-top: 4px;
                margin-bottom: 4px;
                margin-right: 60px;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)

        desc = QLabel(f"Rule Updated: {change.description if change else ''}")
        desc.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 12px;")
        layout.addWidget(desc, 1)

        if change and change.can_undo and not change.undone:
            undo_btn = QPushButton("Undo")
            undo_btn.setCursor(Qt.PointingHandCursor)
            undo_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {COLORS.get('info', '#388BFD')};
                    border: 1px solid {COLORS.get('info', '#388BFD')};
                    border-radius: 4px;
                    padding: 3px 8px;
                    font-size: 11px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {COLORS.get('info_subtle', '#388BFD18')};
                }}
            """)
            undo_btn.clicked.connect(lambda: self.undo_clicked.emit(change.id))
            layout.addWidget(undo_btn)
        elif change and change.undone:
            undone_lbl = QLabel("(Undone)")
            undone_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 11px;")
            layout.addWidget(undone_lbl)


class AutomationConsoleBox(QFrame):
    """Medium-sized fixed-height live execution console for automation runs.

    Displays real-time streaming logs and compact KPI metric cards (Discovered, Evaluated,
    Qualified, Applied, Skipped) in a bounded, scrollable dark terminal box without filling
    or stretching the conversation stream, keeping the UI fast and responsive.
    """

    def __init__(self, platform_name: str = "Automation", parent=None):
        super().__init__(parent)
        self.platform_name = platform_name
        self.setFixedHeight(248)
        self.setStyleSheet(f"""
            AutomationConsoleBox {{
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-radius: 8px;
                margin-top: 6px;
            }}
        """)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 8, 10, 8)
        root_layout.setSpacing(5)

        # Header Bar
        header = QHBoxLayout()
        header.setSpacing(8)

        self.status_badge = QLabel("● RUNNING")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('primary_subtle', '#FF5F1518')};
                color: {COLORS.get('primary', '#FF5F15')};
                border: 1px solid {COLORS.get('primary', '#FF5F15')};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        header.addWidget(self.status_badge)

        self.title_lbl = QLabel(f"{platform_name.capitalize()} Live Execution Console")
        self.title_lbl.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px; font-weight: bold;")
        header.addWidget(self.title_lbl)
        header.addStretch()

        self.counter_lbl = QLabel("Streaming Logs")
        self.counter_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px;")
        header.addWidget(self.counter_lbl)
        root_layout.addLayout(header)

        # Compact KPI Metrics Strip (Runner statistics from automation playground)
        self.kpi_banner = QFrame()
        self.kpi_banner.setStyleSheet("background: transparent; border: none;")
        kpi_layout = QHBoxLayout(self.kpi_banner)
        kpi_layout.setContentsMargins(0, 1, 0, 1)
        kpi_layout.setSpacing(6)

        self._kpi_vals = {
            "discovered": 0,
            "evaluated": 0,
            "qualified": 0,
            "applied": 0,
            "skipped": 0,
        }

        self.kpi_labels: Dict[str, QLabel] = {}
        metrics_specs = [
            ("DISCOVERED", "discovered", COLORS.get("primary", "#FF5F15")),
            ("EVALUATED", "evaluated", COLORS.get("text", "#F0F6FC")),
            ("QUALIFIED", "qualified", COLORS.get("accent", "#A371F7")),
            ("APPLIED", "applied", COLORS.get("success", "#2EA043")),
            ("SKIPPED", "skipped", COLORS.get("text_muted", "#8B949E")),
        ]

        for title, key, val_color in metrics_specs:
            chip = QFrame()
            chip.setStyleSheet("""
                QFrame {
                    background-color: #161B22;
                    border: 1px solid #262C36;
                    border-radius: 6px;
                }
            """)
            c_lay = QVBoxLayout(chip)
            c_lay.setContentsMargins(6, 3, 6, 3)
            c_lay.setSpacing(1)

            t_lbl = QLabel(title)
            t_lbl.setAlignment(Qt.AlignCenter)
            t_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS.get('text_muted', '#8B949E')};
                    font-size: 8.5px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                }}
            """)
            c_lay.addWidget(t_lbl)

            v_lbl = QLabel("0")
            v_lbl.setAlignment(Qt.AlignCenter)
            v_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {val_color};
                    font-size: 14px;
                    font-weight: 800;
                }}
            """)
            c_lay.addWidget(v_lbl)
            self.kpi_labels[key] = v_lbl
            kpi_layout.addWidget(chip)

        root_layout.addWidget(self.kpi_banner)

        # Active Step Strip (single line showing current action)
        self.active_step_lbl = QLabel("● Initializing session...")
        self.active_step_lbl.setStyleSheet(f"""
            QLabel {{
                color: {COLORS.get('primary', '#FF5F15')};
                font-size: 11px;
                font-weight: 600;
                background-color: #161B22;
                border: 1px solid #262C36;
                border-radius: 4px;
                padding: 3px 8px;
            }}
        """)
        root_layout.addWidget(self.active_step_lbl)

        # Terminal Log Stream (read-only, monospace, auto-scrolling)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(250)
        self.log_view.setStyleSheet("""
            QPlainTextEdit {
                background-color: #090D12;
                color: #C9D1D9;
                border: 1px solid #21262D;
                border-radius: 4px;
                font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
                font-size: 10.5px;
                line-height: 1.4;
                padding: 4px;
            }
        """)
        root_layout.addWidget(self.log_view, 1)

        # Live running pulse timer
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(450)
        self._pulse_timer.timeout.connect(self._on_pulse)
        self._pulse_tick = 0
        self._pulse_timer.start()

    def _on_pulse(self):
        if self.status_badge.text().startswith("●"):
            self._pulse_tick = (self._pulse_tick + 1) % 4
            dots = "." * self._pulse_tick
            self.status_badge.setText(f"● RUNNING{dots:<3}")

    def update_metrics(
        self,
        discovered: Optional[int] = None,
        evaluated: Optional[int] = None,
        qualified: Optional[int] = None,
        applied: Optional[int] = None,
        skipped: Optional[int] = None,
    ):
        if discovered is not None:
            self._kpi_vals["discovered"] = max(self._kpi_vals["discovered"], int(discovered))
            self.kpi_labels["discovered"].setText(str(self._kpi_vals["discovered"]))
        if evaluated is not None:
            self._kpi_vals["evaluated"] = max(self._kpi_vals["evaluated"], int(evaluated))
            self.kpi_labels["evaluated"].setText(str(self._kpi_vals["evaluated"]))
        if qualified is not None:
            self._kpi_vals["qualified"] = max(self._kpi_vals["qualified"], int(qualified))
            self.kpi_labels["qualified"].setText(str(self._kpi_vals["qualified"]))
        if applied is not None:
            self._kpi_vals["applied"] = max(self._kpi_vals["applied"], int(applied))
            self.kpi_labels["applied"].setText(str(self._kpi_vals["applied"]))
        if skipped is not None:
            self._kpi_vals["skipped"] = max(self._kpi_vals["skipped"], int(skipped))
            self.kpi_labels["skipped"].setText(str(self._kpi_vals["skipped"]))

    def update_from_dict(self, data: dict):
        if not data or not isinstance(data, dict):
            return
        disc = data.get("jobs_discovered") if "jobs_discovered" in data else data.get("discovered")
        evals = data.get("jobs_evaluated") if "jobs_evaluated" in data else data.get("evaluated")
        qual = data.get("jobs_qualified") if "jobs_qualified" in data else data.get("qualified")
        app = data.get("applications_submitted") if "applications_submitted" in data else data.get("applied")
        skip = data.get("jobs_skipped") if "jobs_skipped" in data else data.get("skipped")
        self.update_metrics(discovered=disc, evaluated=evals, qualified=qual, applied=app, skipped=skip)

    def set_active_step(self, text: str, status: str = "running"):
        clean = text.strip()
        if status == "done":
            self.active_step_lbl.setText(f"✓ {clean}")
            self.active_step_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS.get('success', '#2EA043')};
                    font-size: 11px;
                    font-weight: 600;
                    background-color: #161B22;
                    border: 1px solid #262C36;
                    border-radius: 4px;
                    padding: 3px 8px;
                }}
            """)
        else:
            self.active_step_lbl.setText(f"● {clean}")
            self.active_step_lbl.setStyleSheet(f"""
                QLabel {{
                    color: {COLORS.get('primary', '#FF5F15')};
                    font-size: 11px;
                    font-weight: 600;
                    background-color: #161B22;
                    border: 1px solid #262C36;
                    border-radius: 4px;
                    padding: 3px 8px;
                }}
            """)

    def append_log(self, text: str):
        self.log_view.appendPlainText(text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

        # Dynamic KPI parser from live log stream
        lower = text.lower()
        if "qualified" in lower:
            self._kpi_vals["qualified"] += 1
            self.kpi_labels["qualified"].setText(str(self._kpi_vals["qualified"]))
            self._kpi_vals["evaluated"] = max(self._kpi_vals["evaluated"], self._kpi_vals["qualified"] + self._kpi_vals["skipped"])
            self.kpi_labels["evaluated"].setText(str(self._kpi_vals["evaluated"]))
        elif "skipped" in lower or "skip" in lower:
            self._kpi_vals["skipped"] += 1
            self.kpi_labels["skipped"].setText(str(self._kpi_vals["skipped"]))
            self._kpi_vals["evaluated"] = max(self._kpi_vals["evaluated"], self._kpi_vals["qualified"] + self._kpi_vals["skipped"])
            self.kpi_labels["evaluated"].setText(str(self._kpi_vals["evaluated"]))
        elif "evaluated" in lower or "evaluating" in lower:
            self._kpi_vals["evaluated"] += 1
            self.kpi_labels["evaluated"].setText(str(self._kpi_vals["evaluated"]))
        elif "application submitted" in lower or "successfully applied" in lower:
            self._kpi_vals["applied"] += 1
            self.kpi_labels["applied"].setText(str(self._kpi_vals["applied"]))
        elif "discovered" in lower or "found job" in lower:
            self._kpi_vals["discovered"] += 1
            self.kpi_labels["discovered"].setText(str(self._kpi_vals["discovered"]))

    def mark_completed(self, summary: str = "Automation cycle completed"):
        if self._pulse_timer.isActive():
            self._pulse_timer.stop()
        self.status_badge.setText("✓ COMPLETED")
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('info_subtle', '#388BFD18')};
                color: {COLORS.get('info', '#388BFD')};
                border: 1px solid {COLORS.get('info', '#388BFD')};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: bold;
            }}
        """)
        self.set_active_step(summary, status="done")


class AgentSimulationBox(QFrame):
    """Interactive AI Agent Thinking & Action Simulation Box.

    Provides a clean, conversational thinking container where the AI Copilot
    displays its live reasoning stream, internal decision-making, and animated execution progress.
    """

    def __init__(self, title: str = "AI Copilot Reasoning & Simulation", is_live: bool = True, parent=None):
        super().__init__(parent)
        self.is_live = is_live
        self._step_widgets: List[PilotStepItemWidget] = []
        self._current_anim_index: int = 0
        self._pending_completed: bool = False
        self._pulse_tick: int = 0

        self.setStyleSheet(f"""
            AgentSimulationBox {{
                background-color: #0D1117;
                border: 1px solid #30363D;
                border-left: 3px solid {COLORS.get('primary', '#FF5F15')};
                border-radius: 8px;
                margin-top: 6px;
                margin-bottom: 4px;
            }}
        """)
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(12, 8, 12, 8)
        root_layout.setSpacing(6)

        # Header Bar - zero margin so it perfectly aligns with step rows below
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self.status_badge = QLabel("● RUN" if self.is_live else "✓ DONE")
        self.status_badge.setFixedWidth(56)
        self.status_badge.setFixedHeight(18)
        self.status_badge.setAlignment(Qt.AlignCenter)
        if self.is_live:
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS.get('primary_subtle', '#FF5F1518')};
                    color: {COLORS.get('primary', '#FF5F15')};
                    border: 1px solid {COLORS.get('primary', '#FF5F15')};
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
        else:
            self.status_badge.setStyleSheet(f"""
                QLabel {{
                    background-color: {COLORS.get('success_subtle', '#2EA04318')};
                    color: {COLORS.get('success', '#2EA043')};
                    border: 1px solid {COLORS.get('success', '#2EA043')};
                    border-radius: 3px;
                    padding: 1px 4px;
                    font-size: 9px;
                    font-weight: 600;
                }}
            """)
        header.addWidget(self.status_badge)

        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet(f"color: {COLORS.get('text', '#F0F6FC')}; font-size: 11px; font-weight: bold;")
        header.addWidget(self.title_lbl)
        header.addStretch()

        self.mode_lbl = QLabel("Interactive Thought Stream")
        self.mode_lbl.setStyleSheet(f"color: {COLORS.get('text_muted', '#8B949E')}; font-size: 10px;")
        header.addWidget(self.mode_lbl)
        root_layout.addLayout(header)

        # Steps container - zero left/right margin to match header badge column
        self.steps_container = QWidget()
        self.steps_container.setStyleSheet("background: transparent;")
        self.steps_layout = QVBoxLayout(self.steps_container)
        self.steps_layout.setContentsMargins(0, 0, 0, 0)
        self.steps_layout.setSpacing(4)
        root_layout.addWidget(self.steps_container)

        # Pulse timer for header badge
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(350)
        self._pulse_timer.timeout.connect(self._on_pulse)

        # Staggered animation timer for live sequential step progression
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(280)
        self._anim_timer.timeout.connect(self._advance_step_animation)

        if self.is_live:
            self._pulse_timer.start()
            self._anim_timer.start()

    def _on_pulse(self):
        if self.status_badge.text().startswith("●"):
            self._pulse_tick = (self._pulse_tick + 1) % 4
            dots = "." * self._pulse_tick
            self.status_badge.setText(f"● RUN{dots:<2}")

    def add_or_update_step(self, step: PilotStep):
        existing_w = None
        for w in self._step_widgets:
            if w.step.title == step.title:
                existing_w = w
                break

        if existing_w:
            existing_w.set_status(step.status, step.detail)
        else:
            w = PilotStepItemWidget(step)
            if self.is_live and self._anim_timer.isActive():
                if len(self._step_widgets) == 0:
                    w.set_status("running")
                else:
                    w.set_status("wait")
            elif not self.is_live:
                w.set_status(step.status if step.status != "running" else "done")
            self._step_widgets.append(w)
            self.steps_layout.addWidget(w)

        all_done = all(w.step.status in ("done", "failed") for w in self._step_widgets)
        if all_done and self._step_widgets:
            self.mark_completed(immediate=True)

    def _advance_step_animation(self):
        if not self._step_widgets:
            return

        if self._current_anim_index < len(self._step_widgets):
            curr = self._step_widgets[self._current_anim_index]
            curr.set_status("done")
            self._current_anim_index += 1

            if self._current_anim_index < len(self._step_widgets):
                next_w = self._step_widgets[self._current_anim_index]
                next_w.set_status("running")
            else:
                if self._pending_completed:
                    self.mark_completed(immediate=True)
        else:
            if self._pending_completed:
                self.mark_completed(immediate=True)

    def mark_completed(self, summary: str = "Execution completed", immediate: bool = False):
        if not immediate and self.is_live and self._anim_timer.isActive() and self._current_anim_index < len(self._step_widgets) - 1:
            self._pending_completed = True
            return

        self._pending_completed = True
        if self._anim_timer.isActive():
            self._anim_timer.stop()
        if self._pulse_timer.isActive():
            self._pulse_timer.stop()

        self.status_badge.setText("✓ DONE")
        self.status_badge.setFixedWidth(56)
        self.status_badge.setFixedHeight(18)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS.get('success_subtle', '#2EA04318')};
                color: {COLORS.get('success', '#2EA043')};
                border: 1px solid {COLORS.get('success', '#2EA043')};
                border-radius: 3px;
                padding: 1px 4px;
                font-size: 9px;
                font-weight: 600;
            }}
        """)
        for w in self._step_widgets:
            if w.step.status != "failed":
                w.set_status("done")


class PilotMessageCard(QFrame):
    """Clean bubble displaying AI Pilot responses and step lists."""

    def __init__(self, message: PilotMessage, is_live: bool = False, parent=None):
        super().__init__(parent)
        self.message = message
        self.is_live = is_live
        self.console_box: Optional[AutomationConsoleBox] = None
        self.simulation_box: Optional[AgentSimulationBox] = None

        self.setStyleSheet(f"""
            PilotMessageCard {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-left: 3px solid {COLORS.get('primary', '#FF5F15')};
                border-radius: 12px;
                padding: 12px 16px;
                margin-right: 60px;
                margin-left: 8px;
                margin-top: 4px;
                margin-bottom: 4px;
            }}
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(14, 10, 14, 10)
        self.main_layout.setSpacing(8)

        # Header with AI Pilot identity
        header_row = QHBoxLayout()
        header = QLabel("JobPilot Copilot")
        header.setStyleSheet(
            f"color: {COLORS.get('primary', '#FF5F15')}; font-size: 11px; font-weight: bold; letter-spacing: 0.5px;"
        )
        header_row.addWidget(header)
        header_row.addStretch()
        self.main_layout.addLayout(header_row)

        # Body with rich markdown rendering
        self.body = QLabel()
        self.body.setTextFormat(Qt.RichText)
        self.body.setWordWrap(True)
        self.body.setText(format_pilot_markdown(message.body))
        self.body.setStyleSheet("font-size: 13px; line-height: 1.5;")
        self.main_layout.addWidget(self.body)

        is_automation = (
            message.action_type in (PilotActionType.START_AUTOMATION, PilotActionType.APPLY_JOBS)
            or any("agent action:" in s.title.lower() or "session state:" in s.title.lower() or "portal navigation:" in s.title.lower() for s in message.steps)
        )
        if is_automation:
            p_name = "Automation"
            if message.payload and isinstance(message.payload, dict):
                p_name = message.payload.get("platform", "Automation")
            self.console_box = AutomationConsoleBox(platform_name=p_name)
            for s in message.steps:
                self.console_box.set_active_step(s.title, status=s.status)
                self.console_box.append_log(f"[{s.status.upper()}] {s.title}")
            self.main_layout.addWidget(self.console_box)
        elif message.steps:
            self._build_simulation_box()

    def _build_simulation_box(self):
        if self.simulation_box:
            return
        self.simulation_box = AgentSimulationBox(title="AI Copilot Reasoning & Simulation", is_live=self.is_live)
        for step in self.message.steps:
            self.simulation_box.add_or_update_step(step)
        self.main_layout.addWidget(self.simulation_box)

    def update_step(self, step: Optional[PilotStep] = None):
        """Updates live execution in-place with zero widget recreation!"""
        if step is None:
            if self.console_box:
                self.console_box.mark_completed()
            if self.simulation_box:
                self.simulation_box.mark_completed()
            return

        if self.console_box:
            self.console_box.set_active_step(step.title, status=step.status)
            self.console_box.append_log(f"[{step.status.upper()}] {step.title}")
            if step.status == "done" and any(k in step.title.lower() for k in ["finished", "completed"]):
                self.console_box.mark_completed(step.title)
        elif self.simulation_box:
            self.simulation_box.add_or_update_step(step)
        else:
            is_automation_step = any(step.title.startswith(pfx) for pfx in ("Agent Action:", "Session State:", "Portal Navigation:", "Candidate Evaluation:"))
            if is_automation_step:
                if self.simulation_box:
                    self.main_layout.removeWidget(self.simulation_box)
                    self.simulation_box.deleteLater()
                    self.simulation_box = None
                p_name = "Automation"
                if self.message.payload and isinstance(self.message.payload, dict):
                    p_name = self.message.payload.get("platform", "Automation")
                self.console_box = AutomationConsoleBox(platform_name=p_name)
                for s in self.message.steps:
                    self.console_box.append_log(f"[{s.status.upper()}] {s.title}")
                self.console_box.set_active_step(step.title, status=step.status)
                self.console_box.append_log(f"[{step.status.upper()}] {step.title}")
                self.main_layout.addWidget(self.console_box)
            else:
                self._build_simulation_box()
                self.simulation_box.add_or_update_step(step)

    def update_metrics(self, data: dict):
        """Updates live KPI banner metrics (Discovered, Evaluated, Qualified, Applied, Skipped)."""
        if self.console_box:
            self.console_box.update_from_dict(data)

    def update_message(self, message: PilotMessage):
        """Updates the card's body and transitions all simulation steps to completed."""
        self.message = message
        self.body.setText(format_pilot_markdown(message.body))
        if self.simulation_box:
            for s in message.steps:
                self.simulation_box.add_or_update_step(s)
            self.simulation_box.mark_completed()
        elif message.steps:
            self._build_simulation_box()
            self.simulation_box.mark_completed()
        if self.console_box:
            self.console_box.mark_completed()
