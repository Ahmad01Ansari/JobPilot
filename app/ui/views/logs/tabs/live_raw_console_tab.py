"""Live Raw Console tab with bounded 10,000-line buffer, syntax highlighting, and deep-link jumps."""

from typing import List, Optional
from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor, QSyntaxHighlighter
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.automation_event import LogFileReference
from app.ui.theme import ThemeManager


class LogSyntaxHighlighter(QSyntaxHighlighter):
    """Real-time regex syntax highlighter for engine logs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []
        self._setup_rules()

    def _setup_rules(self) -> None:
        c = ThemeManager.get_instance().colors

        # Timestamps [YYYY-MM-DD HH:MM:SS]
        ts_format = QTextCharFormat()
        ts_format.setForeground(QColor(c.get("text_muted", "#8B949E")))
        self.rules.append((QRegularExpression(r"\b\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}\b"), ts_format))

        # Engine Tags [Tag]
        tag_format = QTextCharFormat()
        tag_format.setForeground(QColor(c.get("cyan", "#39C5CF")))
        tag_format.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"\[[A-Za-z0-9_]+\]"), tag_format))

        # INFO
        info_format = QTextCharFormat()
        info_format.setForeground(QColor(c.get("text", "#F0F6FC")))
        self.rules.append((QRegularExpression(r"\bINFO\b"), info_format))

        # WARNING
        warn_format = QTextCharFormat()
        warn_format.setForeground(QColor(c.get("warning", "#D29922")))
        warn_format.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"\b(WARNING|WARN)\b"), warn_format))

        # ERROR & CRITICAL
        err_format = QTextCharFormat()
        err_format.setForeground(QColor(c.get("danger", "#F85149")))
        err_format.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"\b(ERROR|CRITICAL|EXCEPTION|FAILED)\b"), err_format))

        # SUCCESS
        succ_format = QTextCharFormat()
        succ_format.setForeground(QColor(c.get("success", "#2EA043")))
        succ_format.setFontWeight(QFont.Bold)
        self.rules.append((QRegularExpression(r"\b(SUCCESS|CONFIRMED)\b"), succ_format))

    def highlightBlock(self, text: str) -> None:
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                match = it.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class LiveRawConsoleTab(QWidget):
    """Tab 4: Raw forensic log terminal with bounded buffer and deep linking."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # 1. Top Controls Bar
        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(8)

        # File Selector
        self.file_combo = QComboBox()
        self.file_combo.addItems(["logs/log.txt", "logs/bot.log"])
        self.file_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {c.get('surface', '#161B22')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }}
        """)
        ctrl_bar.addWidget(self.file_combo)

        # Search Bar
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Find in raw logs (regex supported)...")
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {c.get('surface', '#161B22')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus {{
                border-color: {c.get('primary', '#FF5F15')};
            }}
        """)
        self.search_input.returnPressed.connect(self._find_next)
        ctrl_bar.addWidget(self.search_input, 1)

        # Next / Prev search buttons
        btn_prev = QPushButton("◀")
        btn_prev.setFixedSize(26, 26)
        btn_prev.setCursor(Qt.PointingHandCursor)
        btn_prev.clicked.connect(self._find_prev)
        ctrl_bar.addWidget(btn_prev)

        btn_next = QPushButton("▶")
        btn_next.setFixedSize(26, 26)
        btn_next.setCursor(Qt.PointingHandCursor)
        btn_next.clicked.connect(self._find_next)
        ctrl_bar.addWidget(btn_next)

        # Match counter
        self.match_lbl = QLabel("")
        self.match_lbl.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')};")
        ctrl_bar.addWidget(self.match_lbl)

        # Word wrap toggle
        self.chk_wrap = QCheckBox("Wrap")
        self.chk_wrap.setChecked(False)
        self.chk_wrap.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')};")
        self.chk_wrap.toggled.connect(self._on_wrap_toggled)
        ctrl_bar.addWidget(self.chk_wrap)

        # Auto-scroll toggle
        self.chk_autoscroll = QCheckBox("Auto-scroll")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')};")
        ctrl_bar.addWidget(self.chk_autoscroll)

        # Clear View button
        btn_clear = QPushButton("Clear View")
        btn_clear.setCursor(Qt.PointingHandCursor)
        btn_clear.clicked.connect(self.clear_view)
        ctrl_bar.addWidget(btn_clear)

        layout.addLayout(ctrl_bar)
        self._style_buttons([btn_prev, btn_next, btn_clear])

        # 2. Main Raw Console PlainTextEdit
        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setMaximumBlockCount(10000)  # Bounded ring buffer
        self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)

        font = QFont("JetBrains Mono", 10)
        font.setStyleHint(QFont.Monospace)
        self.editor.setFont(font)

        self.editor.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {c.get('background', '#0F1117')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 8px;
            }}
        """)
        self.highlighter = LogSyntaxHighlighter(self.editor.document())
        layout.addWidget(self.editor, 1)

    def _style_buttons(self, buttons: List[QPushButton]) -> None:
        c = ThemeManager.get_instance().colors
        style = f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.get('surface_hover', '#262C36')};
                border-color: {c.get('primary', '#FF5F15')};
                color: {c.get('primary', '#FF5F15')};
            }}
        """
        for b in buttons:
            b.setStyleSheet(style)

    def append_log_line(self, line: str) -> None:
        """Appends a sanitized line to the console."""
        self.editor.appendPlainText(line.rstrip("\r\n"))
        if self.chk_autoscroll.isChecked():
            sb = self.editor.verticalScrollBar()
            sb.setValue(sb.maximum())

    def clear_view(self) -> None:
        """Clears console text without modifying file on disk."""
        self.editor.clear()

    def _on_wrap_toggled(self, checked: bool) -> None:
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth if checked else QPlainTextEdit.NoWrap)

    def jump_to_reference(self, ref: LogFileReference) -> None:
        """Deep links directly to a referenced line number and highlights it."""
        if not ref or ref.line_number <= 0:
            return

        doc = self.editor.document()
        target_block = doc.findBlockByLineNumber(ref.line_number - 1)
        if target_block.isValid():
            cursor = QTextCursor(target_block)
            cursor.select(QTextCursor.BlockUnderCursor)
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()

    def _find_next(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        found = self.editor.find(query)
        if not found:
            # Wrap around from top
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.Start)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(query)
        self.match_lbl.setText("Found" if found else "Not found")

    def _find_prev(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        found = self.editor.find(query, QTextCursor.FindBackward)
        if not found:
            cursor = self.editor.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.editor.setTextCursor(cursor)
            found = self.editor.find(query, QTextCursor.FindBackward)
        self.match_lbl.setText("Found" if found else "Not found")
