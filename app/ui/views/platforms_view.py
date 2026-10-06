"""Platforms management view component.

Displays platform connection status cards (LinkedIn, Naukri, Indeed, Glassdoor),
quick stats, enable/disable toggling, and per-platform execution configuration modals.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.db.models import Platform
from app.services.platform_service import PlatformService
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.status_badge import StatusBadge


class PlatformConfigDialog(QDialog):
    """Modal dialog for modifying platform runtime parameters."""

    def __init__(
        self,
        platform_name: str,
        service: PlatformService,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.platform_name = platform_name
        self.service = service
        self.setWindowTitle(f"Configure {platform_name.title()}")
        self.setMinimumWidth(560)
        self.resize(580, 760)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['surface']};
                color: {COLORS['text']};
            }}
            QLabel {{
                color: {COLORS['text']};
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 7px 10px;
                font-size: 13px;
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border-color: {COLORS['accent']};
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px 2px 4px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {COLORS['border']};
                min-height: 24px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {COLORS['border_light']};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                background: none;
            }}
        """)

        # Main root layout
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(16)

        cfg = self.service.get_platform_config(self.platform_name)

        # Header
        hdr_box = QHBoxLayout()
        hdr_box.setSpacing(12)
        icon_char = PlatformCard.PLATFORM_ICONS.get(self.platform_name.lower(), "🌐")
        lbl_icon = QLabel(icon_char)
        lbl_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                font-size: 24px;
            }}
        """)
        lbl_icon.setAlignment(Qt.AlignCenter)
        lbl_icon.setFixedSize(50, 50)
        hdr_box.addWidget(lbl_icon)

        hdr_texts = QVBoxLayout()
        hdr_texts.setSpacing(2)
        title_lbl = QLabel(f"Configure {cfg.get('display_name', self.platform_name.title())}")
        title_lbl.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {COLORS['text']};")
        sub_lbl = QLabel(cfg.get("description", "Platform runtime, search rotation triggers, and bot automation settings."))
        sub_lbl.setStyleSheet(f"font-size: 12px; color: {COLORS['text_muted']};")
        sub_lbl.setWordWrap(True)
        hdr_texts.addWidget(title_lbl)
        hdr_texts.addWidget(sub_lbl)
        hdr_box.addLayout(hdr_texts, 1)
        layout.addLayout(hdr_box)

        # Section 1: General & Location
        sec_gen = QFrame()
        sec_gen.setStyleSheet(f"QFrame {{ background-color: {COLORS['surface_alt']}50; border: 1px solid {COLORS['border']}; border-radius: 8px; }}")
        gen_layout = QVBoxLayout(sec_gen)
        gen_layout.setContentsMargins(16, 14, 16, 14)
        gen_layout.setSpacing(12)

        self.chk_enabled = QCheckBox("Enable automation for this platform")
        self.chk_enabled.setChecked(cfg.get("is_enabled", True))
        self.chk_enabled.setStyleSheet(f"font-weight: 600; font-size: 13px; color: {COLORS['text']};")
        gen_layout.addWidget(self.chk_enabled)

        gen_form = QGridLayout()
        gen_form.setSpacing(10)

        lbl_dn = QLabel("DISPLAY NAME")
        lbl_dn.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
        self.txt_display_name = QLineEdit(cfg.get("display_name", ""))
        gen_form.addWidget(lbl_dn, 0, 0)
        gen_form.addWidget(self.txt_display_name, 0, 1)

        lbl_loc = QLabel("DEFAULT LOCATION")
        lbl_loc.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
        self.txt_location = QLineEdit(cfg.get("default_location", "India"))
        gen_form.addWidget(lbl_loc, 1, 0)
        gen_form.addWidget(self.txt_location, 1, 1)

        lbl_exp = QLabel("EXPERIENCE TARGET")
        lbl_exp.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
        self.spn_experience = QSpinBox()
        self.spn_experience.setRange(-1, 40)
        self.spn_experience.setValue(cfg.get("experience_years", 5))
        self.spn_experience.setSpecialValueText("Ignore (-1)")
        self.spn_experience.setSuffix(" Yrs")
        gen_form.addWidget(lbl_exp, 2, 0)
        gen_form.addWidget(self.spn_experience, 2, 1)

        is_naukri = (self.platform_name.lower() == "naukri")
        extra_settings = cfg.get("extra_settings", {}) or {}

        if is_naukri:
            # Naukri has no Easy Apply switch. It evaluates all jobs (Direct Apply in-app + External to Ledger).
            lbl_fresh = QLabel("SEARCH FRESHNESS")
            lbl_fresh.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
            self.cmb_freshness = QComboBox()
            self.cmb_freshness.addItem("Past 1 Day (jobAge=1)", 1)
            self.cmb_freshness.addItem("Past 3 Days (jobAge=3)", 3)
            self.cmb_freshness.addItem("Past 7 Days (jobAge=7) — Default", 7)
            self.cmb_freshness.addItem("Past 15 Days (jobAge=15)", 15)
            self.cmb_freshness.addItem("Past 30 Days (jobAge=30)", 30)
            curr_fresh = extra_settings.get("freshness_days", 7)
            for i in range(self.cmb_freshness.count()):
                if self.cmb_freshness.itemData(i) == curr_fresh:
                    self.cmb_freshness.setCurrentIndex(i)
                    break
            gen_form.addWidget(lbl_fresh, 3, 0)
            gen_form.addWidget(self.cmb_freshness, 3, 1)
        else:
            # Platforms supporting application mode (Easy Apply vs Hybrid)
            lbl_mode = QLabel("APPLICATION MODE")
            lbl_mode.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
            self.cmb_apply_mode = QComboBox()

            plat_lower = self.platform_name.lower()
            if plat_lower == "foundit":
                self.cmb_apply_mode.addItem("EASY_APPLY_ONLY — Quick Apply Only (In-App)", "EASY_APPLY_ONLY")
                self.cmb_apply_mode.addItem("ALL — Hybrid (Quick Apply + External)", "ALL")
            elif plat_lower == "indeed":
                self.cmb_apply_mode.addItem("EASY_APPLY_ONLY — Easily Apply Only (In-App)", "EASY_APPLY_ONLY")
                self.cmb_apply_mode.addItem("ALL — Hybrid (Easily Apply + Company Portal)", "ALL")
            elif plat_lower == "glassdoor":
                self.cmb_apply_mode.addItem("EASY_APPLY_ONLY — Easy Apply Only (In-App)", "EASY_APPLY_ONLY")
                self.cmb_apply_mode.addItem("ALL — Hybrid (Easy Apply + Collect External)", "ALL")
            else:  # linkedin
                self.cmb_apply_mode.addItem("EASY_APPLY_ONLY — Easy Apply Only (f_AL=true)", "EASY_APPLY_ONLY")
                self.cmb_apply_mode.addItem("ALL — Hybrid (Easy Apply + Collect External)", "ALL")

            curr_mode = cfg.get("apply_mode", "EASY_APPLY_ONLY")
            for i in range(self.cmb_apply_mode.count()):
                if self.cmb_apply_mode.itemData(i) == curr_mode or self.cmb_apply_mode.itemText(i) == curr_mode:
                    self.cmb_apply_mode.setCurrentIndex(i)
                    break
            gen_form.addWidget(lbl_mode, 3, 0)
            gen_form.addWidget(self.cmb_apply_mode, 3, 1)

            # Search Freshness for other platforms
            lbl_fresh = QLabel("SEARCH FRESHNESS")
            lbl_fresh.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};")
            self.cmb_freshness = QComboBox()
            self.cmb_freshness.addItem("Past 24 Hours", "Past 24 hours")
            self.cmb_freshness.addItem("Past Week (Default)", "Past week")
            self.cmb_freshness.addItem("Past Month", "Past month")
            self.cmb_freshness.addItem("Any Time", "Any time")
            curr_date = extra_settings.get("date_posted", "Past week")
            for i in range(self.cmb_freshness.count()):
                if self.cmb_freshness.itemData(i) == curr_date or self.cmb_freshness.itemText(i) == curr_date:
                    self.cmb_freshness.setCurrentIndex(i)
                    break
            gen_form.addWidget(lbl_fresh, 4, 0)
            gen_form.addWidget(self.cmb_freshness, 4, 1)

            self.lbl_apply_mode_hint = QLabel()
            self.lbl_apply_mode_hint.setWordWrap(True)

            def _update_mode_hint(idx: int):
                mode_key = self.cmb_apply_mode.itemData(idx) or "EASY_APPLY_ONLY"
                if plat_lower == "foundit":
                    if mode_key == "ALL":
                        self.lbl_apply_mode_hint.setText(
                            "🌐 Hybrid Mode Active: 'Quick Apply' filter toggle is turned OFF to discover and process both direct and external company jobs."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet("font-size: 11px; color: #38BDF8; line-height: 1.35; padding-top: 4px;")
                    else:
                        self.lbl_apply_mode_hint.setText(
                            "⚡ Quick Apply Filter ON: Flips ON the Quick Apply switch on Foundit search results to target 1-click in-app applications only."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.35; padding-top: 4px;")
                elif plat_lower == "indeed":
                    if mode_key == "ALL":
                        self.lbl_apply_mode_hint.setText(
                            "🌐 Hybrid Mode Active: Evaluates both 'Easily apply' direct jobs and external company portal job opportunities."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet("font-size: 11px; color: #38BDF8; line-height: 1.35; padding-top: 4px;")
                    else:
                        self.lbl_apply_mode_hint.setText(
                            "⚡ Easily Apply ON: Strictly targets jobs with 'Easily apply' tag for direct in-app submission."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.35; padding-top: 4px;")
                elif plat_lower == "glassdoor":
                    if mode_key == "ALL":
                        self.lbl_apply_mode_hint.setText(
                            "🌐 Hybrid Mode Active: 'Easy Apply' switch is OFF to allow both Easy Apply and external company portal jobs."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet("font-size: 11px; color: #38BDF8; line-height: 1.35; padding-top: 4px;")
                    else:
                        self.lbl_apply_mode_hint.setText(
                            "⚡ Easy Apply Filter ON: Flips the Easy Apply switch ON in Glassdoor search results for in-app applications only."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.35; padding-top: 4px;")
                else:  # linkedin
                    if mode_key == "ALL":
                        self.lbl_apply_mode_hint.setText(
                            "🌐 Hybrid Mode Active: 'Easy Apply' filter (f_AL=true) is turned OFF. The bot submits Easy Apply jobs autonomously, and extracts external company website jobs directly into your Company Portal ledger."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet("font-size: 11px; color: #38BDF8; line-height: 1.35; padding-top: 4px;")
                    else:
                        self.lbl_apply_mode_hint.setText(
                            "⚡ Easy Apply Filter ON: Strictly searches and applies to 1-click in-app applications (f_AL=true). External company website jobs are filtered out."
                        )
                        self.lbl_apply_mode_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.35; padding-top: 4px;")

            self.cmb_apply_mode.currentIndexChanged.connect(_update_mode_hint)
            _update_mode_hint(self.cmb_apply_mode.currentIndex())

        gen_layout.addLayout(gen_form)

        if is_naukri:
            naukri_notice = QFrame()
            naukri_notice.setStyleSheet(f"QFrame {{ background-color: {COLORS['surface_alt']}; border: 1px solid {COLORS['border']}; border-radius: 8px; }}")
            n_layout = QVBoxLayout(naukri_notice)
            n_layout.setContentsMargins(14, 12, 14, 12)
            n_layout.setSpacing(4)
            n_title = QLabel("💼 Naukri Application Model: Direct & External Search")
            n_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #38BDF8; background: transparent; border: none;")
            n_desc = QLabel(
                "Naukri does not feature an 'Easy Apply' search filter switch. The bot automatically evaluates all search results, "
                "submits standard in-app applications directly, and securely records external company portal listings to your ledger."
            )
            n_desc.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.35; background: transparent; border: none;")
            n_desc.setWordWrap(True)
            n_layout.addWidget(n_title)
            n_layout.addWidget(n_desc)
            gen_layout.addWidget(naukri_notice)
        else:
            gen_layout.addWidget(self.lbl_apply_mode_hint)
        layout.addWidget(sec_gen)

        # Section 2: ROTATION TRIGGERS & PACING (4 Conditions)
        sec_triggers = QFrame()
        sec_triggers.setStyleSheet(f"QFrame {{ background-color: {COLORS['surface_alt']}50; border: 1px solid {COLORS['border']}; border-radius: 8px; }}")
        trig_layout = QVBoxLayout(sec_triggers)
        trig_layout.setContentsMargins(16, 14, 16, 14)
        trig_layout.setSpacing(14)

        trig_header = QVBoxLayout()
        trig_header.setSpacing(4)
        trig_title = QLabel("🎯 ROTATION TRIGGERS & PACING (5 CONDITIONS)")
        trig_title.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {COLORS['primary']}; letter-spacing: 0.6px;")
        trig_desc = QLabel("Configure when the bot rotates to the next search keyword or pauses to prevent rate limits and maximize valid applications.")
        trig_desc.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']};")
        trig_desc.setWordWrap(True)
        trig_header.addWidget(trig_title)
        trig_header.addWidget(trig_desc)
        trig_layout.addLayout(trig_header)

        # Trigger 1: Relevance Decay Limit
        t1_box = QVBoxLayout()
        t1_box.setSpacing(4)
        t1_top = QHBoxLayout()
        t1_lbl = QLabel("1. Relevance Decay Threshold")
        t1_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.spn_skips_limit = QSpinBox()
        self.spn_skips_limit.setRange(1, 100)
        self.spn_skips_limit.setValue(cfg.get("consecutive_skips_limit", 20))
        self.spn_skips_limit.setSuffix(" skips")
        self.spn_skips_limit.setFixedWidth(130)
        t1_top.addWidget(t1_lbl, 1)
        t1_top.addWidget(self.spn_skips_limit)
        t1_hint = QLabel("Switches to next keyword when this many consecutive jobs fail qualification (wrong title/skills). Previously applied jobs do NOT trigger this penalty.")
        t1_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")
        t1_hint.setWordWrap(True)
        t1_box.addLayout(t1_top)
        t1_box.addWidget(t1_hint)
        trig_layout.addLayout(t1_box)

        # Trigger 2: Max Jobs Evaluated Per Keyword
        t2_box = QVBoxLayout()
        t2_box.setSpacing(4)
        t2_top = QHBoxLayout()
        t2_lbl = QLabel("2. Max Jobs Evaluated / Keyword")
        t2_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.spn_max_apps = QSpinBox()
        self.spn_max_apps.setRange(5, 300)
        self.spn_max_apps.setSingleStep(5)
        self.spn_max_apps.setValue(cfg.get("max_applications", 75))
        self.spn_max_apps.setSuffix(" jobs")
        self.spn_max_apps.setFixedWidth(130)
        t2_top.addWidget(t2_lbl, 1)
        t2_top.addWidget(self.spn_max_apps)
        t2_hint = QLabel("Maximum job cards inspected for the current keyword before rotating to the next keyword in your rotation list.")
        t2_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")
        t2_hint.setWordWrap(True)
        t2_box.addLayout(t2_top)
        t2_box.addWidget(t2_hint)
        trig_layout.addLayout(t2_box)

        # Trigger 3: Max Pages Per Keyword
        t3_box = QVBoxLayout()
        t3_box.setSpacing(4)
        t3_top = QHBoxLayout()
        t3_lbl = QLabel("3. Max Search Pages / Keyword")
        t3_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.spn_max_pages = QSpinBox()
        self.spn_max_pages.setRange(1, 25)
        self.spn_max_pages.setValue(cfg.get("max_pages_per_search", 5))
        self.spn_max_pages.setSuffix(" pages")
        self.spn_max_pages.setFixedWidth(130)
        t3_top.addWidget(t3_lbl, 1)
        t3_top.addWidget(self.spn_max_pages)
        t3_hint = QLabel("Maximum search result pages to scan per keyword (e.g. 5 pages scans ~100 jobs on Naukri or ~125 on LinkedIn).")
        t3_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")
        t3_hint.setWordWrap(True)
        t3_box.addLayout(t3_top)
        t3_box.addWidget(t3_hint)
        trig_layout.addLayout(t3_box)

        # Trigger 4: Daily Application Goal
        t4_box = QVBoxLayout()
        t4_box.setSpacing(4)
        t4_top = QHBoxLayout()
        t4_lbl = QLabel("4. Daily Application Goal")
        t4_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.spn_daily_goal = QSpinBox()
        self.spn_daily_goal.setRange(1, 500)
        self.spn_daily_goal.setSingleStep(5)
        self.spn_daily_goal.setValue(cfg.get("daily_application_goal", 50))
        self.spn_daily_goal.setSuffix(" apps / day")
        self.spn_daily_goal.setFixedWidth(130)
        t4_top.addWidget(t4_lbl, 1)
        t4_top.addWidget(self.spn_daily_goal)
        t4_hint = QLabel("Daily application target cap. When reached, automation halts cleanly or prompts for continuation to safeguard accounts.")
        t4_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")
        t4_hint.setWordWrap(True)
        t4_box.addLayout(t4_top)
        t4_box.addWidget(t4_hint)
        trig_layout.addLayout(t4_box)

        # Trigger 5: Cycle Sleep Duration (Sleeping Mode)
        t5_box = QVBoxLayout()
        t5_box.setSpacing(4)
        t5_top = QHBoxLayout()
        t5_lbl = QLabel("5. Cycle Sleep Duration (Sleeping Mode)")
        t5_lbl.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {COLORS['text']};")
        self.spn_sleep_duration = QSpinBox()
        self.spn_sleep_duration.setRange(0, 180)
        self.spn_sleep_duration.setSingleStep(5)
        self.spn_sleep_duration.setValue(cfg.get("sleep_duration_minutes", 10))
        self.spn_sleep_duration.setSuffix(" mins")
        self.spn_sleep_duration.setSpecialValueText("0 (Disabled)")
        self.spn_sleep_duration.setFixedWidth(130)
        t5_top.addWidget(t5_lbl, 1)
        t5_top.addWidget(self.spn_sleep_duration)
        t5_hint = QLabel("Duration the bot enters sleeping mode between search rotation cycles to mimic human rest intervals and prevent account rate limits. Set to 0 to disable sleep.")
        t5_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; line-height: 1.3;")
        t5_hint.setWordWrap(True)
        t5_box.addLayout(t5_top)
        t5_box.addWidget(t5_hint)
        trig_layout.addLayout(t5_box)

        layout.addWidget(sec_triggers)

        # Section 3: Safety & Anti-Bot Protection
        sec_safe = QFrame()
        sec_safe.setStyleSheet(f"QFrame {{ background-color: {COLORS['surface_alt']}50; border: 1px solid {COLORS['border']}; border-radius: 8px; }}")
        safe_layout = QVBoxLayout(sec_safe)
        safe_layout.setContentsMargins(16, 14, 16, 14)
        safe_layout.setSpacing(10)

        safe_title = QLabel("SAFETY GATES & ANTI-BOT CONTROLS")
        safe_title.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['text_muted']}; letter-spacing: 0.5px;")
        safe_layout.addWidget(safe_title)

        self.chk_pause = QCheckBox("Pause before final submit for review (Safety Gate)")
        self.chk_pause.setChecked(cfg.get("pause_before_submit", False))
        safe_layout.addWidget(self.chk_pause)

        self.chk_stealth = QCheckBox("Undetected stealth mode (bypasses bot detection)")
        self.chk_stealth.setChecked(cfg.get("stealth_mode", True))
        safe_layout.addWidget(self.chk_stealth)

        self.chk_safe = QCheckBox("Safe browser profile isolation (independent Chrome session)")
        self.chk_safe.setChecked(cfg.get("safe_mode", True))
        safe_layout.addWidget(self.chk_safe)

        lbl_advisory = QLabel("⚠️ Account Safety Advisory: Applying >50 jobs/day on LinkedIn or Naukri may risk account restriction. The bot will pause and request confirmation before continuing.")
        lbl_advisory.setStyleSheet("font-size: 11px; color: #F59E0B; line-height: 1.3; padding-top: 4px;")
        lbl_advisory.setWordWrap(True)
        safe_layout.addWidget(lbl_advisory)

        layout.addWidget(sec_safe)

        # Embed scroll area
        scroll.setWidget(content_widget)
        root_layout.addWidget(scroll, 1)

        # Fixed Footer Action Bar
        footer = QFrame()
        footer.setStyleSheet(f"QFrame {{ background-color: {COLORS['surface']}; border-top: 1px solid {COLORS['border']}; }}")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 14, 24, 14)
        footer_layout.setSpacing(12)
        footer_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_save = QPushButton("Save Configuration")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_save.clicked.connect(self._save_and_accept)

        footer_layout.addWidget(self.btn_cancel)
        footer_layout.addWidget(self.btn_save)
        root_layout.addWidget(footer)

    def _save_and_accept(self) -> None:
        extra_settings: Dict[str, Any] = {}
        if self.platform_name.lower() == "naukri":
            apply_mode_val = "direct_only"
            if hasattr(self, "cmb_freshness"):
                days = int(self.cmb_freshness.currentData())
                extra_settings["freshness_days"] = days
                extra_settings["date_posted"] = f"Past {days} days"
        else:
            apply_mode_val = self.cmb_apply_mode.currentData() or self.cmb_apply_mode.currentText() if hasattr(self, "cmb_apply_mode") else "EASY_APPLY_ONLY"
            if hasattr(self, "cmb_freshness"):
                date_val = self.cmb_freshness.currentData() or self.cmb_freshness.currentText()
                extra_settings["date_posted"] = str(date_val)
                freshness_map = {
                    "Past 24 hours": 1,
                    "Past 3 days": 3,
                    "Past week": 7,
                    "Past month": 30,
                    "Any time": None,
                }
                extra_settings["freshness_days"] = freshness_map.get(str(date_val))

        success, err = self.service.save_platform_config(
            platform_name=self.platform_name,
            is_enabled=self.chk_enabled.isChecked(),
            display_name=self.txt_display_name.text().strip(),
            default_location=self.txt_location.text().strip(),
            experience_years=self.spn_experience.value(),
            max_applications=self.spn_max_apps.value(),
            daily_application_goal=self.spn_daily_goal.value(),
            apply_mode=apply_mode_val,
            pause_before_submit=self.chk_pause.isChecked(),
            stealth_mode=self.chk_stealth.isChecked(),
            safe_mode=self.chk_safe.isChecked(),
            max_pages_per_search=self.spn_max_pages.value(),
            consecutive_skips_limit=self.spn_skips_limit.value(),
            sleep_duration_minutes=self.spn_sleep_duration.value(),
            extra_settings=extra_settings if extra_settings else None,
        )
        if success:
            self.accept()
        else:
            QMessageBox.warning(self, "Error Saving Config", f"Failed: {err}")


class PlatformCard(QFrame):
    """Visual card widget representing a single platform's status and actions."""

    PLATFORM_ICONS = {
        "linkedin": "🔗",
        "naukri": "💼",
        "indeed": "🔍",
        "foundit": "🎯",
        "glassdoor": "🏢",
        "email": "✉️",
    }

    def __init__(
        self,
        platform_name: str,
        service: PlatformService,
        on_changed_callback,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.platform_name = platform_name
        self.service = service
        self.on_changed = on_changed_callback
        self.chip_val_labels: Dict[str, QLabel] = {}
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setObjectName("PlatformCard")
        self.setStyleSheet(f"""
            QFrame#PlatformCard {{
                background-color: {COLORS['surface']};
                border: 1px solid {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame#PlatformCard:hover {{
                border-color: {COLORS['border_light']};
            }}
        """)
        card_layout = QVBoxLayout(self)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(14)

        # Header Row: Icon Badge + Title/Desc + Status & Toggle
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        icon_char = self.PLATFORM_ICONS.get(self.platform_name.lower(), "🌐")
        self.lbl_icon = QLabel(icon_char)
        self.lbl_icon.setStyleSheet(f"""
            QLabel {{
                background-color: {COLORS['surface_alt']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                font-size: 22px;
            }}
        """)
        self.lbl_icon.setFixedSize(44, 44)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        header_row.addWidget(self.lbl_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.lbl_title = QLabel(self.platform_name.title())
        self.lbl_title.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        self.lbl_desc = QLabel("")
        self.lbl_desc.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        self.lbl_desc.setWordWrap(True)
        title_col.addWidget(self.lbl_title)
        title_col.addWidget(self.lbl_desc)
        header_row.addLayout(title_col, 1)

        # Right status & toggle (Side by side with matching pill shape and dimensions)
        status_box = QHBoxLayout()
        status_box.setSpacing(8)
        status_box.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.btn_toggle = QPushButton("Enabled")
        self.btn_toggle.setCursor(Qt.PointingHandCursor)
        self.btn_toggle.setFixedSize(86, 26)
        self.btn_toggle.clicked.connect(self._toggle_enabled)
        status_box.addWidget(self.btn_toggle)

        self.badge_status = StatusBadge("READY", variant="success", width=86, height=26)
        status_box.addWidget(self.badge_status)

        header_row.addLayout(status_box)
        card_layout.addLayout(header_row)

        # Subtle Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background-color: {COLORS['border']}60; border: none;")
        card_layout.addWidget(divider)

        # Parameters Matrix (2x2 Clean Chips)
        chips_grid = QGridLayout()
        chips_grid.setSpacing(10)
        chips_grid.setContentsMargins(0, 4, 0, 4)

        if self.platform_name == "email":
            chip_label, self.chip_val_labels["sync_label"] = self._create_chip("SYNC LABEL", "RPA-Developer-Application", "🏷️")
            chip_acc, self.chip_val_labels["account"] = self._create_chip("ACCOUNT", "Not Configured", "📬")
            chip_tmpls, self.chip_val_labels["templates"] = self._create_chip("TEMPLATES", "4 Active", "📝")
            chip_cad, self.chip_val_labels["cadence"] = self._create_chip("CADENCE", "3, 7, 14 Days", "⏱️")
            chips_grid.addWidget(chip_label, 0, 0)
            chips_grid.addWidget(chip_acc, 0, 1)
            chips_grid.addWidget(chip_tmpls, 1, 0)
            chips_grid.addWidget(chip_cad, 1, 1)
        elif self.platform_name.lower() == "naukri":
            chip_loc, self.chip_val_labels["location"] = self._create_chip("LOCATION", "India", "📍")
            chip_exp, self.chip_val_labels["experience"] = self._create_chip("TARGET EXP", "5 Yrs", "🎯")
            chip_fresh, self.chip_val_labels["freshness"] = self._create_chip("FRESHNESS", "Past 7 Days", "⏱️")
            chip_goal, self.chip_val_labels["daily_goal"] = self._create_chip("DAILY GOAL", "50 Apps / Day", "🎯")
            chips_grid.addWidget(chip_loc, 0, 0)
            chips_grid.addWidget(chip_exp, 0, 1)
            chips_grid.addWidget(chip_fresh, 1, 0)
            chips_grid.addWidget(chip_goal, 1, 1)
        else:
            chip_loc, self.chip_val_labels["location"] = self._create_chip("LOCATION", "India", "📍")
            chip_exp, self.chip_val_labels["experience"] = self._create_chip("TARGET EXP", "5 Yrs", "🎯")
            chip_mode, self.chip_val_labels["mode"] = self._create_chip("APPLY MODE", "EASY_APPLY_ONLY", "⚡")
            chip_goal, self.chip_val_labels["daily_goal"] = self._create_chip("DAILY GOAL", "50 Apps / Day", "🎯")
            chips_grid.addWidget(chip_loc, 0, 0)
            chips_grid.addWidget(chip_exp, 0, 1)
            chips_grid.addWidget(chip_mode, 1, 0)
            chips_grid.addWidget(chip_goal, 1, 1)

        card_layout.addLayout(chips_grid)

        # Footer Row with Configure Action
        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 4, 0, 0)

        self.lbl_hint = QLabel("Ready for automation")
        self.lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        footer_row.addWidget(self.lbl_hint)
        footer_row.addStretch()

        self.btn_config = QPushButton("⚙ Configure")
        self.btn_config.setCursor(Qt.PointingHandCursor)
        self.btn_config.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['surface_hover']};
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
            }}
        """)
        self.btn_config.clicked.connect(self._open_config)
        footer_row.addWidget(self.btn_config)
        card_layout.addLayout(footer_row)

    def _create_chip(self, label: str, val: str, icon: str) -> tuple[QWidget, QLabel]:
        container = QWidget()
        container.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['surface_alt']}80;
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
            }}
        """)
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(12, 8, 12, 8)
        c_layout.setSpacing(2)

        lbl_t = QLabel(f"{icon} {label}")
        lbl_t.setStyleSheet(f"font-size: 10px; font-weight: 700; color: {COLORS['text_muted']}; background: transparent; border: none; letter-spacing: 0.5px;")
        lbl_v = QLabel(val)
        lbl_v.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {COLORS['text']}; background: transparent; border: none;")

        c_layout.addWidget(lbl_t)
        c_layout.addWidget(lbl_v)
        return container, lbl_v

    def refresh(self) -> None:
        cfg = self.service.get_platform_config(self.platform_name)
        if not cfg:
            return

        self.lbl_title.setText(cfg.get("display_name", self.platform_name.title()))
        self.lbl_desc.setText(cfg.get("description", ""))
        is_enabled = cfg.get("is_enabled", True)

        if self.platform_name == "email":
            from app.services.secrets_service import SecretsService
            from app.repositories.email_template_repository import EmailTemplateRepository
            from app.db.session import get_db_session

            extra = cfg.get("extra_settings") or {}
            creds = SecretsService().get_email_credentials()
            is_configured = creds.get("is_configured", False)

            sync_label = extra.get("sync_label") or creds.get("sync_label", "RPA-Developer-Application")
            user_acc = creds.get("user") or "Not configured"
            if len(user_acc) > 22:
                user_acc = user_acc[:20] + "..."

            cadence = extra.get("followup_cadence_days", [3, 7, 14])
            cadence_str = ", ".join(str(d) for d in cadence) + " Days"

            try:
                with get_db_session() as session:
                    tmpl_repo = EmailTemplateRepository(session)
                    tmpl_count = len(tmpl_repo.list_all())
            except Exception:
                tmpl_count = 4

            if "sync_label" in self.chip_val_labels:
                self.chip_val_labels["sync_label"].setText(sync_label)
            if "account" in self.chip_val_labels:
                self.chip_val_labels["account"].setText(user_acc)
            if "templates" in self.chip_val_labels:
                self.chip_val_labels["templates"].setText(f"{tmpl_count} Active")
            if "cadence" in self.chip_val_labels:
                self.chip_val_labels["cadence"].setText(cadence_str)

            if is_enabled:
                self.btn_toggle.setText("Enabled")
                self.btn_toggle.setToolTip("Click to disable email outreach")
                self.btn_toggle.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #064E3B;
                        color: #34D399;
                        border: 1px solid #059669;
                        font-weight: 700;
                        font-size: 11px;
                        border-radius: 13px;
                        padding: 0px 4px;
                    }}
                    QPushButton:hover {{
                        background-color: #047857;
                        color: #FFFFFF;
                    }}
                """)
                if is_configured:
                    self.badge_status.update_style("success")
                    self.badge_status.setText("READY")
                    self.lbl_hint.setText("2-Way Gmail sync active")
                    self.lbl_hint.setStyleSheet("font-size: 11px; color: #34D399; background: transparent; border: none;")
                else:
                    self.badge_status.update_style("warning")
                    self.badge_status.setText("SETUP")
                    self.lbl_hint.setText("App Password required to sync")
                    self.lbl_hint.setStyleSheet("font-size: 11px; color: #FBBF24; background: transparent; border: none;")
            else:
                self.btn_toggle.setText("Disabled")
                self.btn_toggle.setToolTip("Click to enable email outreach")
                self.btn_toggle.setStyleSheet(f"""
                    QPushButton {{
                        background-color: #1F2937;
                        color: #9CA3AF;
                        border: 1px solid #374151;
                        font-weight: 700;
                        font-size: 11px;
                        border-radius: 13px;
                        padding: 0px 4px;
                    }}
                    QPushButton:hover {{
                        background-color: #374151;
                        color: #F3F4F6;
                    }}
                """)
                self.badge_status.update_style("neutral")
                self.badge_status.setText("STANDBY")
                self.lbl_hint.setText("Email outreach disabled")
                self.lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
            return

        if is_enabled:
            self.btn_toggle.setText("Enabled")
            self.btn_toggle.setToolTip("Click to disable automation for this platform")
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: #064E3B;
                    color: #34D399;
                    border: 1px solid #059669;
                    font-weight: 700;
                    font-size: 11px;
                    border-radius: 13px;
                    padding: 0px 4px;
                }}
                QPushButton:hover {{
                    background-color: #047857;
                    color: #FFFFFF;
                }}
            """)
            self.badge_status.update_style("success")
            self.badge_status.setText(cfg.get("status", "READY"))
            self.lbl_hint.setText("Active and ready for automation runs")
            self.lbl_hint.setStyleSheet("font-size: 11px; color: #34D399; background: transparent; border: none;")
        else:
            self.btn_toggle.setText("Disabled")
            self.btn_toggle.setToolTip("Click to enable automation for this platform")
            self.btn_toggle.setStyleSheet(f"""
                QPushButton {{
                    background-color: #1F2937;
                    color: #9CA3AF;
                    border: 1px solid #374151;
                    font-weight: 700;
                    font-size: 11px;
                    border-radius: 13px;
                    padding: 0px 4px;
                }}
                QPushButton:hover {{
                    background-color: #374151;
                    color: #F3F4F6;
                }}
            """)
            self.badge_status.update_style("neutral")
            self.badge_status.setText("STANDBY")
            self.lbl_hint.setText("Platform standby / disabled")
            self.lbl_hint.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")

        # Update chip values
        loc = cfg.get("default_location", "India")
        exp = cfg.get("experience_years", 5)
        mode = cfg.get("apply_mode", "EASY_APPLY_ONLY")
        daily_goal = cfg.get("daily_application_goal", 50)
        extra = cfg.get("extra_settings", {}) or {}

        if "location" in self.chip_val_labels:
            self.chip_val_labels["location"].setText(loc)
        if "experience" in self.chip_val_labels:
            self.chip_val_labels["experience"].setText(f"{exp} Years" if exp >= 0 else "Any Exp")
        if "freshness" in self.chip_val_labels:
            f_days = extra.get("freshness_days", 7)
            d_posted = extra.get("date_posted")
            fresh_text = f"Past {f_days} Days" if f_days else (d_posted or "Past 7 Days")
            self.chip_val_labels["freshness"].setText(str(fresh_text))
        if "mode" in self.chip_val_labels:
            plat_lower = self.platform_name.lower()
            if plat_lower == "foundit":
                display_mode = "Hybrid (All)" if mode == "ALL" else "Quick Apply"
            elif plat_lower == "indeed":
                display_mode = "Hybrid (All)" if mode == "ALL" else "Easily Apply"
            else:
                display_mode = "Hybrid (All)" if mode == "ALL" else "Easy Apply Only"
            self.chip_val_labels["mode"].setText(display_mode)
        if "daily_goal" in self.chip_val_labels:
            self.chip_val_labels["daily_goal"].setText(f"{daily_goal} Apps / Day")

    def _toggle_enabled(self) -> None:
        self.service.toggle_platform(self.platform_name)
        self.refresh()
        if self.on_changed:
            self.on_changed()

    def _open_config(self) -> None:
        if self.platform_name == "email":
            from app.ui.views.email_platform_dialog import EmailOutreachConfigDialog
            dialog = EmailOutreachConfigDialog(
                service=self.service,
                parent=self,
            )
        else:
            dialog = PlatformConfigDialog(
                platform_name=self.platform_name,
                service=self.service,
                parent=self,
            )
        if dialog.exec() == QDialog.Accepted:
            self.refresh()
            if self.on_changed:
                self.on_changed()


class ComingSoonPlatformCard(QFrame):
    """Placeholder card showing future planned platform integrations."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: transparent;
                border: 2px dashed {COLORS['border']};
                border-radius: 12px;
            }}
            QFrame:hover {{
                border-color: {COLORS['accent']}80;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignCenter)

        icon = QLabel("➕")
        icon.setStyleSheet(f"font-size: 28px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        icon.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon)

        title = QLabel("More Platforms Coming Soon")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['text']}; background: transparent; border: none;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        desc = QLabel("Monster, ZipRecruiter, and custom corporate ATS connectors are currently under active development.")
        desc.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; background: transparent; border: none;")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        layout.addWidget(desc)


class PlatformsView(QWidget):
    """Main platforms management dashboard view."""

    def __init__(self, service: Optional[PlatformService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service or PlatformService()
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header
        self.header = PageHeader(
            title="Platform Connections",
            subtitle="Monitor authentication, execution profiles, and runtime configuration across job platforms.",
        )
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setCursor(Qt.PointingHandCursor)
        self.btn_refresh.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 7px 14px;
                border-radius: 6px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
            }}
        """)
        self.btn_refresh.clicked.connect(self.refresh)
        self.header.add_action_widget(self.btn_refresh)
        main_layout.addWidget(self.header)

        # Notification Banner
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # Scrollable Platform Grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setSpacing(16)
        self.grid.setContentsMargins(0, 8, 0, 8)
        self.grid.setAlignment(Qt.AlignTop)

        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

    def refresh(self) -> None:
        """Reloads all platform cards from database and appends future platform placeholder."""
        platforms = self.service.list_platforms()

        # Clear existing cards
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

        # Build 2-column responsive grid
        for i, plat in enumerate(platforms):
            row = i // 2
            col = i % 2
            card = PlatformCard(
                platform_name=plat.name,
                service=self.service,
                on_changed_callback=lambda: self.notification_bar.show_message(
                    "success", "Platform settings updated successfully."
                ),
                parent=self,
            )
            self.grid.addWidget(card, row, col)

        # Add coming soon card spanning last position
        next_idx = len(platforms)
        cs_row = next_idx // 2
        cs_col = next_idx % 2
        coming_soon = ComingSoonPlatformCard(self)
        # If odd number, let it take the second column; if even, span both
        if cs_col == 0:
            self.grid.addWidget(coming_soon, cs_row, 0, 1, 2)
        else:
            self.grid.addWidget(coming_soon, cs_row, cs_col)
