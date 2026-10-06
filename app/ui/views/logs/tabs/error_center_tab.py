"""Error & Human Intervention Center with actionable resolution workflows and failure clustering."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.automation_event import AutomationEvent
from app.services.logs.event_correlator import EventCorrelator
from app.ui.theme import ThemeManager


class InterventionCard(QFrame):
    """Actionable human intervention card with explicit resolution buttons."""

    resolved = Signal(str)          # event_id
    skip_requested = Signal(str)    # event_id
    qna_requested = Signal(str)     # question
    browser_requested = Signal()

    def __init__(self, event: AutomationEvent, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.automation_event = event
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Header: Warning icon + Type + Target
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        warn_icon = QLabel("⚠")
        warn_icon.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {c.get('warning', '#D29922')};")
        hdr.addWidget(warn_icon)

        type_lbl = QLabel(self.automation_event.event_type.value.replace("_", " "))
        type_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        hdr.addWidget(type_lbl)

        hdr.addStretch()

        plat_lbl = QLabel(self.automation_event.platform.capitalize())
        plat_lbl.setStyleSheet(f"""
            background-color: {c.get('surface_alt', '#1C2128')};
            color: {c.get('text_muted', '#8B949E')};
            border-radius: 4px;
            padding: 2px 8px;
            font-size: 10px;
            font-weight: 600;
        """)
        hdr.addWidget(plat_lbl)
        layout.addLayout(hdr)

        # Message
        msg_lbl = QLabel(self.automation_event.message)
        msg_lbl.setStyleSheet(f"font-size: 12px; color: {c.get('text', '#F0F6FC')};")
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)

        # 4 Action Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(8)

        # 1. Solved
        btn_solved = QPushButton("I Have Solved The Challenge ✓")
        btn_solved.setCursor(Qt.PointingHandCursor)
        btn_solved.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('success', '#2EA043')};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: #3fb950;
            }}
        """)
        btn_solved.clicked.connect(lambda: self.resolved.emit(self.automation_event.event_id))
        btn_box.addWidget(btn_solved)

        # 2. Skip Job
        btn_skip = QPushButton("Skip This Job")
        btn_skip.setCursor(Qt.PointingHandCursor)
        btn_skip.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.get('surface_hover', '#262C36')};
                border-color: {c.get('danger', '#F85149')};
                color: {c.get('danger', '#F85149')};
            }}
        """)
        btn_skip.clicked.connect(lambda: self.skip_requested.emit(self.automation_event.event_id))
        btn_box.addWidget(btn_skip)

        # 3. Add to Q&A Bank
        btn_qna = QPushButton("Add Answer to Q&A Bank")
        btn_qna.setCursor(Qt.PointingHandCursor)
        btn_qna.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.get('surface_hover', '#262C36')};
                border-color: {c.get('primary', '#FF5F15')};
                color: {c.get('primary', '#FF5F15')};
            }}
        """)
        btn_qna.clicked.connect(lambda: self.qna_requested.emit(self.automation_event.message))
        btn_box.addWidget(btn_qna)

        # 4. Open Browser Session
        btn_browser = QPushButton("Bring Browser to Front")
        btn_browser.setCursor(Qt.PointingHandCursor)
        btn_browser.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text', '#F0F6FC')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.get('surface_hover', '#262C36')};
                border-color: {c.get('info', '#388BFD')};
                color: {c.get('info', '#388BFD')};
            }}
        """)
        btn_browser.clicked.connect(self.browser_requested.emit)
        btn_box.addWidget(btn_browser)

        btn_box.addStretch()
        layout.addLayout(btn_box)

        self.setStyleSheet(f"""
            InterventionCard {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-left: 4px solid {c.get('warning', '#D29922')};
                border-radius: 8px;
            }}
        """)


class ErrorCenterTab(QWidget):
    """Tab 3: Incident command center showing pending human interventions and failure clusters."""

    intervention_resolved = Signal(str)
    intervention_skip = Signal(str)
    add_qna_requested = Signal(str)
    browser_requested = Signal()

    def __init__(self, correlator: Optional[EventCorrelator] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.correlator = correlator or EventCorrelator()
        self._clusters: Dict[str, Dict[str, Any]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 1. Active Interventions Section
        int_hdr = QLabel("Pending Human Interventions")
        int_hdr.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        layout.addWidget(int_hdr)

        self.interventions_container = QWidget()
        self.interventions_layout = QVBoxLayout(self.interventions_container)
        self.interventions_layout.setContentsMargins(0, 0, 0, 0)
        self.interventions_layout.setSpacing(8)

        # Clean idle placeholder
        self.idle_card = QFrame()
        idle_layout = QHBoxLayout(self.idle_card)
        idle_layout.setContentsMargins(16, 12, 16, 12)
        idle_lbl = QLabel("✓ No pending interventions. Automation running smoothly.")
        idle_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {c.get('success', '#2EA043')};")
        idle_layout.addWidget(idle_lbl)
        self.idle_card.setStyleSheet(f"""
            QFrame {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
            }}
        """)
        self.interventions_layout.addWidget(self.idle_card)
        layout.addWidget(self.interventions_container)

        # 2. Failure Clusters Section
        cluster_hdr = QLabel("Automated Failure Clusters (Repeated Error Signatures)")
        cluster_hdr.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        layout.addWidget(cluster_hdr)

        self.cluster_table = QTableWidget(0, 5)
        self.cluster_table.setHorizontalHeaderLabels([
            "Occurrences", "Platform", "Stage", "Normalized Signature", "Sample Message"
        ])
        self.cluster_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.cluster_table.horizontalHeader().setStretchLastSection(True)
        self.cluster_table.verticalHeader().setVisible(False)
        self.cluster_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {c.get('surface', '#161B22')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                gridline-color: {c.get('border_subtle', '#21262D')};
                color: {c.get('text', '#F0F6FC')};
                font-size: 11px;
            }}
            QHeaderView::section {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('text_muted', '#8B949E')};
                border: none;
                padding: 6px 10px;
                font-weight: 600;
            }}
        """)
        layout.addWidget(self.cluster_table, 1)

    def set_active_interventions(self, events: List[AutomationEvent]) -> None:
        """Renders active intervention cards."""
        # Clear existing cards except idle placeholder
        while self.interventions_layout.count() > 1:
            item = self.interventions_layout.takeAt(1)
            w = item.widget()
            if w:
                w.deleteLater()

        if not events:
            self.idle_card.setVisible(True)
            return

        self.idle_card.setVisible(False)
        for evt in events:
            card = InterventionCard(evt, parent=self.interventions_container)
            card.resolved.connect(self.intervention_resolved.emit)
            card.skip_requested.connect(self.intervention_skip.emit)
            card.qna_requested.connect(self.add_qna_requested.emit)
            card.browser_requested.connect(self.browser_requested.emit)
            self.interventions_layout.addWidget(card)

    def record_error_event(self, event: AutomationEvent) -> None:
        """Records an error into failure clusters."""
        key = self.correlator.get_cluster_key(event)
        norm_msg = self.correlator.normalize_error_message(event.message)

        if key not in self._clusters:
            self._clusters[key] = {
                "count": 0,
                "platform": event.platform,
                "stage": event.stage or "APPLICATION",
                "normalized": norm_msg,
                "sample": event.message,
            }
        self._clusters[key]["count"] += 1
        self._refresh_cluster_table()

    def _refresh_cluster_table(self) -> None:
        sorted_clusters = sorted(self._clusters.values(), key=lambda c: c["count"], reverse=True)
        self.cluster_table.setRowCount(len(sorted_clusters))
        for row, cl in enumerate(sorted_clusters):
            items = [
                QTableWidgetItem(f"{cl['count']}x"),
                QTableWidgetItem(cl["platform"].capitalize()),
                QTableWidgetItem(str(cl["stage"])),
                QTableWidgetItem(cl["normalized"]),
                QTableWidgetItem(cl["sample"]),
            ]
            for col, item in enumerate(items):
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.cluster_table.setItem(row, col, item)
