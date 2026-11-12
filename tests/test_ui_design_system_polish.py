"""Unit tests for Desktop UI Design System polish and ThemeManager parity."""

import os
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from app.services.dto.dashboard_dto import ReadinessSummaryDTO
from app.ui.sidebar_icons import render_vector_icon, render_vector_pixmap
from app.ui.theme import COLORS, DARK_COLORS, LIGHT_COLORS, ThemeManager
from app.ui.top_bar import TopBar
from app.ui.widgets.dashboard.readiness_strip import ReadinessStrip
from app.ui.widgets.metric_card import ModernMetricCard
from app.ui.widgets.pipeline_funnel import PipelineFunnelCard
from app.ui.widgets.status_badge import StatusBadge, StatusDropdownButton


class TestUIDesignSystemPolish(unittest.TestCase):
    """Verifies ThemeManager contrast/focus rules, TopBar wiring, vector icons, and widget theme parity."""

    @classmethod
    def setUpClass(cls) -> None:
        app = QApplication.instance()
        cls.app = app if app is not None else QApplication(["jobpilot_ui_test", "-platform", "offscreen"])
        ThemeManager.apply_dark_theme(cls.app)

    def tearDown(self) -> None:
        ThemeManager.apply_dark_theme(self.app)

    def test_theme_stylesheet_focus_and_light_table_contrast(self) -> None:
        """QPushButton:focus must render a visible border and Light Mode table items must use dark text."""
        light_qss = ThemeManager.get_stylesheet(LIGHT_COLORS)
        self.assertIn("QPushButton:focus", light_qss)
        self.assertIn(f"border: 2px solid {LIGHT_COLORS['primary']}", light_qss)
        self.assertIn(f"selection-color: {LIGHT_COLORS['text']}", light_qss)
        self.assertNotIn("QTableWidget::item:hover, QTableView::item:hover {\n            background-color: #EAEFF5;\n            color: #FFFFFF;", light_qss)

    def test_theme_switching_updates_tooltip_palette(self) -> None:
        """Light and dark themes must synchronize native QPalette tooltip colors."""
        ThemeManager.apply_light_theme(self.app)
        pal_light = self.app.palette()
        self.assertEqual(pal_light.color(QPalette.ToolTipBase).name().upper(), LIGHT_COLORS["surface"].upper())
        self.assertEqual(pal_light.color(QPalette.ToolTipText).name().upper(), LIGHT_COLORS["text"].upper())

        ThemeManager.apply_dark_theme(self.app)
        pal_dark = self.app.palette()
        self.assertEqual(pal_dark.color(QPalette.ToolTipBase).name().upper(), DARK_COLORS["surface"].upper())
        self.assertEqual(pal_dark.color(QPalette.ToolTipText).name().upper(), DARK_COLORS["text"].upper())

    def test_vector_icon_helpers_render_non_null_assets(self) -> None:
        """Vector icon painters produce non-null pixmaps and icons for new topbar/dashboard glyphs."""
        for name in ("search", "refresh", "user", "info", "alert", "star", "check", "trash", "lightning"):
            pix = render_vector_pixmap(name, "#FF5F15", 16)
            self.assertFalse(pix.isNull(), f"Pixmap empty for {name}")
            icon = render_vector_icon(name, "#FF5F15", 16)
            self.assertFalse(icon.isNull(), f"Icon empty for {name}")

    def test_top_bar_uses_vector_icons_and_theme_object_names(self) -> None:
        """TopBar wires object names for ThemeManager and avoids hardcoded hex or emoji text."""
        top_bar = TopBar()
        self.assertEqual(top_bar.title_label.objectName(), "TopBarTitle")
        self.assertEqual(top_bar.btn_search.objectName(), "TopBarSearch")
        self.assertFalse(top_bar.btn_search.icon().isNull())
        self.assertFalse(top_bar.btn_refresh.icon().isNull())
        self.assertFalse(top_bar.btn_profile.icon().isNull())
        self.assertFalse(top_bar.btn_about.icon().isNull())
        self.assertNotIn("🔍", top_bar.btn_search.text())
        self.assertNotIn("👤", top_bar.btn_profile.text())
        self.assertNotIn("ℹ️", top_bar.btn_about.text())

        ThemeManager.apply_light_theme(self.app)
        top_bar.update_theme("light")
        self.assertFalse(top_bar.btn_search.icon().isNull())

    def test_metric_card_and_funnel_support_theme_and_conversion_pct(self) -> None:
        """ModernMetricCard renders vector pixmap and PipelineFunnelCard displays percentage conversion."""
        card = ModernMetricCard(title="Submitted", value="12", icon="chart")
        self.assertFalse(card.icon_badge.pixmap().isNull())
        ThemeManager.apply_light_theme(self.app)
        card.apply_theme()
        self.assertIn(LIGHT_COLORS["surface"], card.styleSheet())

        funnel = PipelineFunnelCard()
        funnel.update_stages(discovered=100, submitted=25, under_review=10, interview=5, offer=1)
        self.assertEqual(funnel.stage_rows["Submitted"].lbl_count.text(), "25 (25%)")
        self.assertEqual(funnel.stage_rows["Interview"].lbl_count.text(), "5 (20%)")
        self.assertEqual(funnel.lbl_total_apps.text(), "41 In Pipeline")

    def test_status_badge_and_readiness_strip_light_mode_and_icons(self) -> None:
        """StatusBadge adapts to Light Mode and ReadinessStrip displays vector status icons."""
        ThemeManager.apply_light_theme(self.app)
        badge = StatusBadge("SUBMITTED")
        self.assertIn("#DCFCE7", badge.styleSheet())

        dropdown = StatusDropdownButton("INTERVIEW")
        self.assertIn("#F3E8FF", dropdown.styleSheet())

        strip = ReadinessStrip()
        strip.set_readiness(ReadinessSummaryDTO(profile_complete=True, resume_configured=False, qna_answered_ratio=0.9))
        self.assertFalse(strip.btn_profile.icon().isNull())
        self.assertEqual(strip.btn_profile.text(), "Profile")
        self.assertEqual(strip.btn_qna.text(), "QA Ready")


if __name__ == "__main__":
    unittest.main()

