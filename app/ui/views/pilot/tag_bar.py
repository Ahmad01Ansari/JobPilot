"""Interactive Smart Action Tag Bar for the JobPilot AI Pilot.

Provides a left-and-right scrollable strip of categorized one-click
action chips with dedicated navigation chevrons and smooth animation,
giving candidates full control over automation and intelligence without typing.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QWidget,
)

from app.ui.theme import COLORS

# Comprehensive directory of all implemented capabilities (clean enterprise tags)
CATEGORIZED_ACTIONS = [
    # Automation Bots
    ("Run All Automation", "run all automation", "primary"),
    ("Run LinkedIn", "run the LinkedIn automation", "primary"),
    ("Run Indeed", "run indeed", "primary"),
    ("Run Naukri", "start naukri bot", "primary"),
    ("Run Foundit", "run foundit", "primary"),
    ("Run Glassdoor", "run glassdoor", "primary"),
    ("Run Universal ATS", "run universal ats", "primary"),

    # Bot Controls
    ("Pause Automation", "pause automation", "warning"),
    ("Resume Automation", "resume automation", "success"),
    ("Stop Automation", "stop automation", "danger"),

    # Factual Reports & Pipeline
    ("Today Apply Report", "today apply report", "info"),
    ("Top Opportunities", "show eligible jobs", "info"),
    ("Recent Applications", "show applications", "info"),
    ("Check Platform Logins", "check platforms", "info"),

    # Rule Configurations with Undo
    ("Skip Clearance Roles", "skip jobs requiring security clearance", "accent"),
    ("Skip Contract Roles", "skip contract roles", "accent"),
    ("Min Score 80%", "set minimum match score to 80%", "accent"),
    ("Min Score 90%", "set minimum match score to 90%", "accent"),

    # Resume & Fact Extraction
    ("Key Skills from Resume", "what are the key skills from my resume", "purple"),
    ("Design Role Resume", "design a resume for Tech Lead", "purple"),
    ("Extract Active Resume", "extract resume", "purple"),
    ("List Resumes", "list resumes", "purple"),

    # Candidate QnA Knowledge Bank
    ("List QnA Rules", "list qna", "cyan"),
    ("Test QnA Answer", "test question What is your expected salary?", "cyan"),

    # Discovery Searches
    ("Search Remote Python", "find remote Python developer jobs", "default"),
    ("Search React Frontend", "find React frontend engineer jobs", "default"),
    ("Search Full Stack", "find full stack engineer jobs", "default"),
]


class SmartTagBar(QFrame):
    """Horizontal scrollable strip with animated scroll arrows for one-click action chips."""

    tag_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self._scroll_anim: QPropertyAnimation = None

        self.setStyleSheet(f"""
            SmartTagBar {{
                background-color: {COLORS.get('surface', '#161B22')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 10px;
            }}
        """)

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(6, 4, 6, 4)
        root_layout.setSpacing(6)

        # 1. Left Scroll Arrow (Prominent, High-Contrast, Professional)
        self.left_btn = QPushButton("◀")
        self.left_btn.setFixedSize(30, 32)
        self.left_btn.setCursor(Qt.PointingHandCursor)
        self.left_btn.setToolTip("Scroll Options Left")
        self._set_arrow_style(self.left_btn)
        self.left_btn.clicked.connect(self._scroll_left)
        root_layout.addWidget(self.left_btn)

        # 2. Scrollable Strip
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self.chips_layout = QHBoxLayout(container)
        self.chips_layout.setContentsMargins(2, 2, 2, 2)
        self.chips_layout.setSpacing(6)

        for label, prompt, variant in CATEGORIZED_ACTIONS:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip(f"Click to run: '{prompt}'")
            btn.setStyleSheet(self._get_chip_style(variant))
            btn.clicked.connect(lambda _, p=prompt: self.tag_selected.emit(p))
            self.chips_layout.addWidget(btn)

        self.scroll.setWidget(container)
        root_layout.addWidget(self.scroll, 1)

        # 3. Right Scroll Arrow (Prominent, High-Contrast, Professional)
        self.right_btn = QPushButton("▶")
        self.right_btn.setFixedSize(30, 32)
        self.right_btn.setCursor(Qt.PointingHandCursor)
        self.right_btn.setToolTip("Scroll Options Right")
        self._set_arrow_style(self.right_btn)
        self.right_btn.clicked.connect(self._scroll_right)
        root_layout.addWidget(self.right_btn)

        # Connect scroll position updates
        hbar = self.scroll.horizontalScrollBar()
        hbar.valueChanged.connect(self._update_arrow_states)
        hbar.rangeChanged.connect(self._update_arrow_states)
        self._update_arrow_states()

    def _set_arrow_style(self, btn: QPushButton) -> None:
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: #21262D;
                color: #FFFFFF;
                border: 1.5px solid {COLORS.get('primary', '#FF5F15')};
                border-radius: 7px;
                font-size: 13px;
                font-weight: 900;
                padding: 0px;
            }}
            QPushButton:hover {{
                background-color: {COLORS.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border-color: #FFA066;
            }}
            QPushButton:pressed {{
                background-color: #CC4C10;
            }}
            QPushButton:disabled {{
                background-color: #161B22;
                color: #484F58;
                border: 1px solid #30363D;
            }}
        """)

    def _get_chip_style(self, variant: str) -> str:
        color_token = COLORS.get("primary", "#FF5F15")
        if variant == "warning":
            color_token = COLORS.get("warning", "#D29922")
        elif variant == "success":
            color_token = COLORS.get("success", "#2EA043")
        elif variant == "danger":
            color_token = COLORS.get("danger", "#F85149")
        elif variant == "info":
            color_token = COLORS.get("info", "#388BFD")
        elif variant == "purple":
            color_token = COLORS.get("purple", "#A371F7")
        elif variant == "cyan":
            color_token = COLORS.get("cyan", "#39C5CF")
        elif variant == "accent":
            color_token = COLORS.get("accent", "#FF5F15")

        return f"""
            QPushButton {{
                background-color: {COLORS.get('surface_alt', '#1C2128')};
                color: {COLORS.get('text', '#F0F6FC')};
                border: 1px solid {COLORS.get('border', '#262C36')};
                border-radius: 12px;
                padding: 5px 12px;
                font-size: 11px;
                font-weight: 500;
                white-space: nowrap;
            }}
            QPushButton:hover {{
                color: {color_token};
                border-color: {color_token};
                background-color: {COLORS.get('surface_hover', '#262C36')};
            }}
        """

    def _update_arrow_states(self, *_) -> None:
        hbar = self.scroll.horizontalScrollBar()
        self.left_btn.setEnabled(hbar.value() > 0)
        self.right_btn.setEnabled(hbar.value() < hbar.maximum())

    def _animate_scroll(self, delta: int) -> None:
        hbar = self.scroll.horizontalScrollBar()
        current = hbar.value()
        target = max(0, min(hbar.maximum(), current + delta))
        if current == target:
            return

        self._scroll_anim = QPropertyAnimation(hbar, b"value", self)
        self._scroll_anim.setDuration(280)
        self._scroll_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._scroll_anim.setStartValue(current)
        self._scroll_anim.setEndValue(target)
        self._scroll_anim.start()

    def _scroll_left(self) -> None:
        self._animate_scroll(-280)

    def _scroll_right(self) -> None:
        self._animate_scroll(280)
