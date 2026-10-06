"""Truthful 'What is the Bot Doing Right Now?' Hero Card."""

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.logs.run_context import RunObservabilityContext
from app.ui.theme import ThemeManager
from app.ui.views.logs.pipeline_flow_map import PipelineFlowMap


class CurrentActionCard(QFrame):
    """Hero panel displaying active automation execution state with truthful fallback."""

    stop_requested = Signal()
    pause_requested = Signal()
    resolve_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        c = ThemeManager.get_instance().colors
        self.setFrameShape(QFrame.NoFrame)
        self.setStyleSheet(f"""
            CurrentActionCard {{
                background-color: {c.get("surface", "#161B22")};
                border: 1px solid {c.get("border", "#262C36")};
                border-left: 5px solid {c.get("border_light", "#333A46")};
                border-radius: 10px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(10)

        # 1. Top row: Star icon + Tag + Status Badge + Platform + Elapsed Time
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.star_tag = QLabel("★ ACTIVE AUTOMATION SESSION")
        self.star_tag.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {c.get('primary', '#FF5F15')}; letter-spacing: 0.8px; background: transparent; border: none;")
        top_row.addWidget(self.star_tag)

        self.status_badge = QLabel("IDLE")
        self.status_badge.setStyleSheet(f"""
            background-color: {c.get("surface_alt", "#1C2128")};
            color: {c.get("text_muted", "#8B949E")};
            border: 1px solid {c.get("border", "#262C36")};
            border-radius: 6px;
            padding: 2px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)
        top_row.addWidget(self.status_badge)

        self.platform_lbl = QLabel("No active platform")
        self.platform_lbl.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")
        top_row.addWidget(self.platform_lbl)

        self.duration_lbl = QLabel("0s")
        self.duration_lbl.setStyleSheet(f"font-size: 11px; color: {c.get('text_muted', '#8B949E')}; font-family: monospace; background: transparent; border: none;")
        top_row.addWidget(self.duration_lbl)

        top_row.addStretch()
        layout.addLayout(top_row)

        # 2. Main Horizontal Body: Left (Title & Step Description) | Right (Action Buttons)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)

        left_col = QVBoxLayout()
        left_col.setSpacing(3)

        self.target_lbl = QLabel("Automation is currently idle")
        self.target_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {c.get('text', '#F0F6FC')}; background: transparent; border: none;")
        left_col.addWidget(self.target_lbl)

        self.action_lbl = QLabel("Waiting for an automation session to be initiated from the sidebar or dashboard.")
        self.action_lbl.setStyleSheet(f"font-size: 12px; color: {c.get('text_muted', '#8B949E')}; background: transparent; border: none;")
        self.action_lbl.setWordWrap(True)
        left_col.addWidget(self.action_lbl)

        body_layout.addLayout(left_col, 1)

        # Right CTA Deck
        self.right_cta_box = QHBoxLayout()
        self.right_cta_box.setSpacing(8)
        self.right_cta_box.setAlignment(Qt.AlignVCenter)

        # Resolve challenge primary button
        self.btn_resolve = QPushButton("Resolve Challenge →")
        self.btn_resolve.setCursor(Qt.PointingHandCursor)
        self.btn_resolve.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('primary', '#FF5F15')};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.get('primary_hover', '#E04F0B')};
            }}
        """)
        self.btn_resolve.clicked.connect(self.resolve_requested.emit)
        self.btn_resolve.setVisible(False)
        self.right_cta_box.addWidget(self.btn_resolve)

        # Stop button
        self.btn_stop = QPushButton("Stop Run")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.setFixedHeight(30)
        self.btn_stop.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.get('surface_alt', '#1C2128')};
                color: {c.get('danger', '#F85149')};
                border: 1px solid {c.get('border', '#262C36')};
                border-radius: 6px;
                padding: 5px 14px;
                font-size: 11px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {c.get('danger', '#F85149')};
                color: #FFFFFF;
                border-color: {c.get('danger', '#F85149')};
            }}
        """)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        self.btn_stop.setVisible(False)
        self.right_cta_box.addWidget(self.btn_stop)

        body_layout.addLayout(self.right_cta_box)
        layout.addLayout(body_layout)

        # 3. Horizontal Subtle Divider & Embedded Stage Flow Stepper
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.HLine)
        self.divider.setFixedHeight(1)
        self.divider.setStyleSheet(f"background-color: {c.get('border', '#262C36')}; border: none; margin-top: 4px; margin-bottom: 2px;")
        layout.addWidget(self.divider)

        self.pipeline_flow_map = PipelineFlowMap(parent=self, embedded=True)
        layout.addWidget(self.pipeline_flow_map)

    def set_current_stage(self, stage_name: Optional[str]) -> None:
        """Forwards stage progress to embedded pipeline flow map."""
        self.pipeline_flow_map.set_current_stage(stage_name)

    def update_from_context(self, ctx: Optional[RunObservabilityContext]) -> None:
        """Truthfully updates the hero card from active worker context."""
        c = ThemeManager.get_instance().colors

        if not ctx or ctx.status in ("IDLE", "STOPPED", "COMPLETED"):
            self.setStyleSheet(f"""
                CurrentActionCard {{
                    background-color: {c.get("surface", "#161B22")};
                    border: 1px solid {c.get("border", "#262C36")};
                    border-left: 5px solid {c.get("border_light", "#333A46")};
                    border-radius: 10px;
                }}
            """)
            self.status_badge.setText("IDLE" if not ctx else ctx.status)
            self.status_badge.setStyleSheet(f"""
                background-color: {c.get("surface_alt", "#1C2128")};
                color: {c.get("text_muted", "#8B949E")};
                border: 1px solid {c.get("border", "#262C36")};
                border-radius: 6px;
                padding: 2px 10px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
            """)
            self.platform_lbl.setText("No active platform" if not ctx else ctx.platform.capitalize())
            self.duration_lbl.setText(ctx.duration_str() if ctx else "0s")
            self.target_lbl.setText("Automation is currently idle" if not ctx else f"Run {ctx.status.title()}")
            self.action_lbl.setText("Waiting for an automation session to be initiated." if not ctx else (ctx.current_action or "Run finished."))
            self.btn_stop.setVisible(False)
            self.btn_resolve.setVisible(False)
            if ctx and ctx.current_stage:
                self.pipeline_flow_map.set_current_stage(ctx.current_stage)
            else:
                self.pipeline_flow_map.set_current_stage(None)
            return

        # Active states (RUNNING, ACTION_REQUIRED, PAUSED)
        st = ctx.status.upper()
        if "ACTION" in st:
            left_color = c.get("primary", "#FF5F15")
            badge_bg = "rgba(255, 95, 21, 0.15)"
            badge_color = c.get("primary", "#FF5F15")
            badge_border = c.get("primary", "#FF5F15")
            badge_text = "ACTION REQUIRED"
        elif "PAUSED" in st:
            left_color = c.get("warning", "#D29922")
            badge_bg = "rgba(210, 153, 34, 0.15)"
            badge_color = c.get("warning", "#D29922")
            badge_border = c.get("warning", "#D29922")
            badge_text = "PAUSED"
        else:
            left_color = c.get("success", "#2EA043")
            badge_bg = "rgba(46, 160, 67, 0.15)"
            badge_color = c.get("success", "#2EA043")
            badge_border = c.get("success", "#2EA043")
            badge_text = "RUNNING"

        self.setStyleSheet(f"""
            CurrentActionCard {{
                background-color: {c.get("surface", "#161B22")};
                border: 1px solid {left_color}50;
                border-left: 5px solid {left_color};
                border-radius: 10px;
            }}
        """)
        self.status_badge.setText(badge_text)
        self.status_badge.setStyleSheet(f"""
            background-color: {badge_bg};
            color: {badge_color};
            border: 1px solid {badge_border};
            border-radius: 6px;
            padding: 2px 10px;
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 0.5px;
        """)

        self.platform_lbl.setText(ctx.platform.capitalize())
        self.duration_lbl.setText(f"Elapsed: {ctx.duration_str()}")
        self.btn_stop.setVisible(True)
        self.btn_resolve.setVisible("ACTION" in st)

        # Target job & company
        if ctx.current_job_title and ctx.current_company:
            self.target_lbl.setText(f"{ctx.current_job_title} · {ctx.current_company}")
        elif ctx.current_job_title:
            self.target_lbl.setText(ctx.current_job_title)
        elif ctx.current_keyword:
            self.target_lbl.setText(f"Searching: '{ctx.current_keyword}'")
        else:
            self.target_lbl.setText(f"{ctx.platform.capitalize()} Automation in progress")

        # Action / step detail
        if ctx.current_action:
            self.action_lbl.setText(ctx.current_action)
        elif ctx.current_stage:
            self.action_lbl.setText(f"Executing stage: {ctx.current_stage}")
        else:
            self.action_lbl.setText("Current action unavailable")
