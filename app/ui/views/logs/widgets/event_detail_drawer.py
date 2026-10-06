"""Slide-out / side inspection drawer detailing a selected AutomationEvent."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.automation_event import AutomationEvent
from app.ui.theme import ThemeManager


class EventDetailDrawer(QFrame):
    """Deep inspection drawer for a selected timeline event."""

    open_job_requested = Signal(int)         # job_id
    open_application_requested = Signal(int) # application_id
    view_in_raw_logs_requested = Signal(object) # LogFileReference
    closed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_event: Optional[AutomationEvent] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedWidth(360)
        self.setStyleSheet(f"""
            EventDetailDrawer {{
                background-color: {c.get("surface", "#161B22")};
                border-left: 1px solid {c.get("border", "#262C36")};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header: Title + Close button
        hdr_layout = QHBoxLayout()
        hdr_lbl = QLabel("Event Inspector")
        hdr_lbl.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        hdr_layout.addWidget(hdr_lbl)
        hdr_layout.addStretch()

        btn_close = QPushButton("✕")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {c.get('text_muted', '#8B949E')};
                border: none;
                font-size: 13px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                color: {c.get('text', '#F0F6FC')};
            }}
        """)
        btn_close.clicked.connect(self.closed.emit)
        hdr_layout.addWidget(btn_close)
        layout.addLayout(hdr_layout)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        # 1. Event Type & Source Badge
        self.badges_layout = QHBoxLayout()
        self.type_badge = QLabel("")
        self.source_badge = QLabel("")
        self.badges_layout.addWidget(self.type_badge)
        self.badges_layout.addWidget(self.source_badge)
        self.badges_layout.addStretch()
        self.content_layout.addLayout(self.badges_layout)

        # 2. Headline: Action & Target
        self.title_lbl = QLabel("")
        self.title_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        self.title_lbl.setWordWrap(True)
        self.content_layout.addWidget(self.title_lbl)

        # 3. Message Box
        self.msg_lbl = QLabel("")
        self.msg_lbl.setStyleSheet(f"""
            background-color: {c.get('surface_alt', '#1C2128')};
            border: 1px solid {c.get('border', '#262C36')};
            border-radius: 6px;
            padding: 10px;
            font-size: 11px;
            color: {c.get('text', '#F0F6FC')};
        """)
        self.msg_lbl.setWordWrap(True)
        self.content_layout.addWidget(self.msg_lbl)

        # 4. Context Parameters Table
        self.info_table = QTableWidget(0, 2)
        self.info_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.verticalHeader().setVisible(False)
        self.info_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                gridline-color: {c.get('border_subtle', '#21262D')};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text_muted', '#8B949E')};
                border: none;
                padding: 4px;
                font-weight: 600;
            }}
        """)
        self.info_table.setFixedHeight(180)
        self.content_layout.addWidget(self.info_table)

        # 5. Deep Link Action Buttons
        self.btn_open_job = QPushButton("Open Job Listing")
        self.btn_open_job.setCursor(Qt.PointingHandCursor)
        self.btn_open_job.clicked.connect(self._on_open_job)
        self.content_layout.addWidget(self.btn_open_job)

        self.btn_open_app = QPushButton("Open Application Record")
        self.btn_open_app.setCursor(Qt.PointingHandCursor)
        self.btn_open_app.clicked.connect(self._on_open_app)
        self.content_layout.addWidget(self.btn_open_app)

        self.btn_view_raw = QPushButton("View in Raw Logs")
        self.btn_view_raw.setCursor(Qt.PointingHandCursor)
        self.btn_view_raw.clicked.connect(self._on_view_raw)
        self.content_layout.addWidget(self.btn_view_raw)

        self.content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

        self._style_buttons()

    def _style_buttons(self) -> None:
        c = ThemeManager.get_instance().colors
        btn_style = f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {c.get('primary', '#FF5F15')};
                color: {c.get('primary', '#FF5F15')};
                background-color: {c.get('surface_hover', '#262C36')};
            }}
        """
        self.btn_open_job.setStyleSheet(btn_style)
        self.btn_open_app.setStyleSheet(btn_style)
        self.btn_view_raw.setStyleSheet(btn_style)

    def inspect_event(self, event: AutomationEvent) -> None:
        """Populates the drawer with details from the selected event."""
        self._current_event = event
        c = ThemeManager.get_instance().colors

        # Badges
        t_val = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        self.type_badge.setText(t_val)
        self.type_badge.setStyleSheet(f"""
            background-color: {c.get('primary_subtle', '#FF5F1518')};
            color: {c.get('primary', '#FF5F15')};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 700;
        """)

        s_val = event.source.value if hasattr(event.source, "value") else str(event.source)
        self.source_badge.setText(s_val)
        self.source_badge.setStyleSheet(f"""
            background-color: {c.get('surface_alt', '#1C2128')};
            color: {c.get('text_muted', '#8B949E')};
            border-radius: 4px;
            padding: 2px 6px;
            font-size: 10px;
            font-weight: 600;
        """)

        # Title
        if event.job_title and event.company:
            self.title_lbl.setText(f"{event.job_title} @ {event.company}")
        elif event.action:
            self.title_lbl.setText(event.action)
        else:
            self.title_lbl.setText(t_val)

        # Message
        self.msg_lbl.setText(event.message or "No message content")

        # Table rows
        fields = [
            ("Event ID", event.event_id[:12] + "..."),
            ("Run ID", event.run_id[:12] + "..."),
            ("Sequence", f"#{event.sequence}"),
            ("Platform", event.platform.capitalize()),
            ("Stage", event.stage or "—"),
            ("Status", event.status or "—"),
            ("Job ID", str(event.job_id) if event.job_id else "—"),
            ("App ID", str(event.application_id) if event.application_id else "—"),
            ("Timestamp", event.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")),
        ]
        if event.duration_ms:
            fields.append(("Duration", f"{event.duration_ms} ms"))

        self.info_table.setRowCount(len(fields))
        for row, (k, v) in enumerate(fields):
            item_k = QTableWidgetItem(k)
            item_k.setFlags(Qt.ItemIsEnabled)
            item_v = QTableWidgetItem(v)
            item_v.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.info_table.setItem(row, 0, item_k)
            self.info_table.setItem(row, 1, item_v)

        # Button visibility
        self.btn_open_job.setVisible(bool(event.job_id))
        if event.job_id:
            self.btn_open_job.setText(f"Open Job #{event.job_id}")

        self.btn_open_app.setVisible(bool(event.application_id))
        if event.application_id:
            self.btn_open_app.setText(f"Open Application #{event.application_id}")

        self.btn_view_raw.setVisible(bool(event.raw_reference))

    def _on_open_job(self) -> None:
        if self._current_event and self._current_event.job_id:
            self.open_job_requested.emit(self._current_event.job_id)

    def _on_open_app(self) -> None:
        if self._current_event and self._current_event.application_id:
            self.open_application_requested.emit(self._current_event.application_id)

    def _on_view_raw(self) -> None:
        if self._current_event and self._current_event.raw_reference:
            self.view_in_raw_logs_requested.emit(self._current_event.raw_reference)
