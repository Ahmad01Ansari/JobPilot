"""Mission Control top bar with multi-run selector and scoped action controls."""

from typing import Callable, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.run_context import RunObservabilityContext
from app.ui.theme import ThemeManager


class RunChip(QPushButton):
    """Segmented pill chip representing an active or recent automation run."""

    def __init__(
        self,
        context: RunObservabilityContext,
        is_selected: bool = False,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.context = context
        self.run_id = context.run_id
        self.setCheckable(True)
        self.setChecked(is_selected)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(30)
        self._update_appearance()

    def _update_appearance(self) -> None:
        tm = ThemeManager.get_instance()
        c = tm.colors

        # Status icon
        st = self.context.status.upper()
        if "RUNNING" in st:
            dot = "● "
            dot_color = c.get("success", "#2EA043")
        elif "ACTION" in st:
            dot = "⚠ "
            dot_color = c.get("warning", "#D29922")
        elif "PAUSED" in st:
            dot = "⏸ "
            dot_color = c.get("warning", "#D29922")
        elif "STOP" in st or "COMPLETED" in st:
            dot = "○ "
            dot_color = c.get("text_muted", "#8B949E")
        else:
            dot = "● "
            dot_color = c.get("info", "#388BFD")

        platform_name = self.context.platform.capitalize()
        status_text = self.context.status.replace("_", " ").title()
        self.setText(f"{dot}{platform_name} · {status_text}")

        # Stylesheet
        if self.isChecked():
            bg = c.get("surface", "#161B22")
            border = c.get("primary", "#FF5F15")
            text_color = c.get("primary", "#FF5F15")
            font_weight = "700"
        elif "ACTION" in st:
            bg = "rgba(255, 95, 21, 0.12)"
            border = c.get("primary", "#FF5F15")
            text_color = "#FF8F4D"
            font_weight = "600"
        else:
            bg = c.get("surface", "#161B22")
            border = c.get("border", "#262C36")
            text_color = c.get("text_muted", "#8B949E")
            font_weight = "500"

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {text_color};
                border: 1px solid {border};
                border-radius: 14px;
                padding: 4px 14px;
                font-size: 11px;
                font-weight: {font_weight};
            }}
            QPushButton:hover {{
                border-color: {c.get("primary", "#FF5F15")};
                color: {c.get("text", "#F0F6FC")};
                background-color: {c.get("surface_hover", "#262C36")};
            }}
        """)


class MissionHeader(QWidget):
    """Top bar for Automation Mission Control displaying active runs and control toggles."""

    run_selected = Signal(str)        # run_id
    pause_stream_toggled = Signal(bool) # is_paused
    clear_view_clicked = Signal()
    export_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_stream_paused = False
        self._selected_run_id: Optional[str] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(12)

        # Left: Title and subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("Mission Control")
        title_lbl.setStyleSheet(f"font-size: 18px; font-weight: 700; color: {c.get('text', '#F0F6FC')};")
        title_box.addWidget(title_lbl)

        sub_lbl = QLabel("Observability & Incident Command Cockpit")
        sub_lbl.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')};")
        title_box.addWidget(sub_lbl)

        layout.addLayout(title_box)

        # Center: Run Selector Chips (Scrollable)
        self.chips_container = QWidget()
        self.chips_layout = QHBoxLayout(self.chips_container)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.chips_layout.setSpacing(6)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setWidget(self.chips_container)
        scroll.setFixedHeight(34)
        layout.addWidget(scroll, 1)

        # Right: Quick Action Controls
        actions_box = QHBoxLayout()
        actions_box.setSpacing(8)

        # 1. Pause Stream Toggle
        self.btn_pause = QPushButton("⏸ Pause Stream")
        self.btn_pause.setCursor(Qt.PointingHandCursor)
        self.btn_pause.setFixedHeight(32)
        self.btn_pause.clicked.connect(self._toggle_pause_stream)
        actions_box.addWidget(self.btn_pause)

        # 2. Clear View (Safe non-destructive)
        self.btn_clear = QPushButton("Clear View")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.setFixedHeight(32)
        self.btn_clear.clicked.connect(self.clear_view_clicked.emit)
        actions_box.addWidget(self.btn_clear)

        # 3. Export Diagnostic Report
        self.btn_export = QPushButton("Export Report")
        self.btn_export.setCursor(Qt.PointingHandCursor)
        self.btn_export.setFixedHeight(32)
        self.btn_export.clicked.connect(self.export_clicked.emit)
        actions_box.addWidget(self.btn_export)

        layout.addLayout(actions_box)
        self._apply_button_styles()

    def _apply_button_styles(self) -> None:
        c = ThemeManager.get_instance().colors
        # Clean, crisp secondary button style matching Dashboard
        secondary_btn_style = f"""
            QPushButton {{
                background-color: {c.get("surface_alt", "#1C2128")};
                color: {c.get("text", "#F0F6FC")};
                border: 1px solid {c.get("border", "#262C36")};
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {c.get("surface_hover", "#262C36")};
                border-color: {c.get("primary", "#FF5F15")};
                color: {c.get("primary", "#FF5F15")};
            }}
            QPushButton:pressed {{
                background-color: {c.get("surface", "#161B22")};
            }}
        """
        self.btn_pause.setStyleSheet(secondary_btn_style)
        self.btn_clear.setStyleSheet(secondary_btn_style)

        # Crisp, vibrant solid Safety Orange accent for Export Report (matching Dashboard)
        export_btn_style = f"""
            QPushButton {{
                background-color: {c.get("primary", "#FF5F15")};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.get("primary_hover", "#E04F0B")};
            }}
            QPushButton:pressed {{
                background-color: {c.get("primary", "#FF5F15")};
            }}
        """
        self.btn_export.setStyleSheet(export_btn_style)

    def _toggle_pause_stream(self) -> None:
        self._is_stream_paused = not self._is_stream_paused
        c = ThemeManager.get_instance().colors
        if self._is_stream_paused:
            self.btn_pause.setText("▶ Resume Stream")
            self.btn_pause.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(210, 153, 34, 0.18);
                    color: #F0B72F;
                    border: 1px solid {c.get('warning', '#D29922')};
                    border-radius: 6px;
                    padding: 5px 14px;
                    font-size: 12px;
                    font-weight: 700;
                }}
                QPushButton:hover {{
                    background-color: rgba(210, 153, 34, 0.28);
                }}
            """)
        else:
            self.btn_pause.setText("⏸ Pause Stream")
            self._apply_button_styles()
        self.pause_stream_toggled.emit(self._is_stream_paused)

    def set_runs(self, runs: List[RunObservabilityContext], selected_run_id: Optional[str] = None) -> None:
        """Refreshes the run selector chips."""
        # Clear existing chips
        while self.chips_layout.count():
            item = self.chips_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        if not runs:
            idle_chip = QLabel("No active runs")
            c = ThemeManager.get_instance().colors
            idle_chip.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')};")
            self.chips_layout.addWidget(idle_chip)
            return

        self._selected_run_id = selected_run_id or runs[0].run_id

        for ctx in runs:
            is_sel = (ctx.run_id == self._selected_run_id)
            chip = RunChip(ctx, is_selected=is_sel, parent=self.chips_container)
            chip.clicked.connect(lambda checked=False, rid=ctx.run_id: self._on_chip_clicked(rid))
            self.chips_layout.addWidget(chip)

        self.chips_layout.addStretch()

    def _on_chip_clicked(self, run_id: str) -> None:
        self._selected_run_id = run_id
        for i in range(self.chips_layout.count()):
            w = self.chips_layout.itemAt(i).widget()
            if isinstance(w, RunChip):
                w.setChecked(w.run_id == run_id)
                w._update_appearance()
        self.run_selected.emit(run_id)
