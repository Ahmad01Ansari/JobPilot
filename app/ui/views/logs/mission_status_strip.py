"""Scoped KPI metric strip displaying unambiguous run and daily telemetry counters."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.run_context import RunObservabilityContext
from app.ui.theme import ThemeManager


class MetricCard(QFrame):
    """Clean ATS-styled metric card with explicit scope indicator and click-filter."""

    clicked = Signal(str)  # metric_name

    def __init__(
        self,
        title: str,
        scope: str = "CURRENT RUN",
        initial_value: int = 0,
        highlight_color: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.metric_key = title.lower()
        self.scope = scope
        self.title_text = title
        self.highlight_color = highlight_color
        self._value = initial_value
        self.setCursor(Qt.PointingHandCursor)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        self.setFixedHeight(72)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        # Large Vibrant Value
        val_color = self.highlight_color or c.get("primary", "#FF5F15")
        self.val_lbl = QLabel(str(self._value))
        self.val_lbl.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {val_color}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; background: transparent; border: none;")
        layout.addWidget(self.val_lbl)

        # Title
        title_lbl = QLabel(self.title_text)
        title_lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {c.get('text_muted', '#8B949E')}; text-transform: uppercase; letter-spacing: 0.5px; background: transparent; border: none;")
        layout.addWidget(title_lbl)

        self._update_style()

    def _update_style(self) -> None:
        c = ThemeManager.get_instance().colors
        accent = self.highlight_color or c.get("primary", "#FF5F15")
        self.setStyleSheet(f"""
            MetricCard {{
                background-color: {c.get("surface", "#161B22")};
                border: 1px solid {c.get("border", "#262C36")};
                border-top: 3px solid {accent};
                border-radius: 8px;
            }}
            MetricCard:hover {{
                border-color: {accent};
                background-color: {c.get("surface_hover", "#262C36")};
            }}
        """)

    def set_value(self, val: int) -> None:
        c = ThemeManager.get_instance().colors
        self._value = val
        val_color = self.highlight_color or c.get("primary", "#FF5F15")
        self.val_lbl.setText(f"{val:,}")
        self.val_lbl.setStyleSheet(f"font-size: 24px; font-weight: 800; color: {val_color}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif; background: transparent; border: none;")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.metric_key)
        super().mousePressEvent(event)


class MissionStatusStrip(QWidget):
    """Horizontal grid of metric cards displaying Discovered, Qualified, Applied, Skipped, Errors, and Interventions."""

    filter_requested = Signal(str)  # metric_key

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(10)

        # 1. Discovered (Sky Blue)
        self.card_discovered = MetricCard("Discovered", initial_value=0, highlight_color=c.get("info", "#388BFD"))
        self.card_discovered.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_discovered)

        # 2. Qualified (Cyan)
        self.card_qualified = MetricCard("Qualified", initial_value=0, highlight_color=c.get("cyan", "#39C5CF"))
        self.card_qualified.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_qualified)

        # 3. Applied (Primary Safety Orange)
        self.card_applied = MetricCard("Applied", initial_value=0, highlight_color=c.get("primary", "#FF5F15"))
        self.card_applied.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_applied)

        # 4. Skipped (Purple)
        self.card_skipped = MetricCard("Skipped", initial_value=0, highlight_color=c.get("purple", "#A371F7"))
        self.card_skipped.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_skipped)

        # 5. Failed (Coral Red)
        self.card_failed = MetricCard("Failed", initial_value=0, highlight_color=c.get("danger", "#F85149"))
        self.card_failed.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_failed)

        # 6. Interventions (Golden Amber)
        self.card_interventions = MetricCard("Action Req", initial_value=0, highlight_color=c.get("warning", "#D29922"))
        self.card_interventions.clicked.connect(self.filter_requested.emit)
        layout.addWidget(self.card_interventions)

    def update_metrics(self, ctx: RunObservabilityContext) -> None:
        """Updates all cards from an active RunObservabilityContext."""
        self.card_discovered.set_value(ctx.jobs_discovered)
        self.card_qualified.set_value(ctx.jobs_qualified)
        self.card_applied.set_value(ctx.applications_submitted)
        self.card_skipped.set_value(ctx.jobs_skipped)
        self.card_failed.set_value(ctx.errors_count)
        self.card_interventions.set_value(ctx.interventions_count)
