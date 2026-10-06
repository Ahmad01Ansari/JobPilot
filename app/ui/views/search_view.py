"""Job search criteria and strategy configuration workspace component.

Provides a modern, refined ATS-grade interface to configure search rotation keywords,
geographic locations, experience constraints, posted date filters, instant-skip rules,
description blacklists, continuous cycle controls, and resume synchronization.
"""

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.keyword_extractor_service import KeywordExtractorService
from app.services.platform_service import PlatformService
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.widgets.page_header import PageHeader
from app.ui.widgets.search import (
    KeywordTagContainer,
    SearchAutomationCard,
    SearchKeywordInput,
    SearchLocationCard,
    SearchPlatformsCard,
    SearchPreferencesCard,
    SearchPreviewDialog,
    SearchScopeCard,
    SearchSkipRulesCard,
    SearchStickyBar,
    SearchSummaryCard,
)


class SearchView(QWidget):
    """Refined Job Search Strategy workspace view."""

    data_updated = Signal(str)

    def __init__(self, service: Optional[PlatformService] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.service = service or PlatformService()
        self._is_loading = False

        self._setup_ui()
        self.load_platform_search("linkedin")

    def refresh(self) -> None:
        """Reloads the active platform search criteria from the database."""
        plat = self.cmb_platform.currentText().strip().lower()
        self.load_platform_search(plat)

    def _setup_ui(self) -> None:
        self.setObjectName("searchView")
        self.setStyleSheet(f"#searchView {{ background-color: {COLORS['background']}; }}")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(28, 20, 28, 0)
        main_layout.setSpacing(10)

        # 1. Page Header with Title & Top-Right Actions
        self.header = PageHeader(
            title="Job Search Strategy",
            subtitle="Define what JobPilot should search, prioritize, and skip across your job sources.",
        )

        self.btn_sync_resume = QPushButton("⚡ Sync from Resume")
        self.btn_sync_resume.setCursor(Qt.PointingHandCursor)
        self.btn_sync_resume.setToolTip("Auto-populates search terms and domain exclusions from your active resume")
        self.btn_sync_resume.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface_alt']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {COLORS['accent']};
                color: {COLORS['accent']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_sync_resume.clicked.connect(self._on_sync_from_resume_clicked)

        self.btn_reset = QPushButton("Reset")
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['surface']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 12px;
            }}
            QPushButton:hover {{
                color: {COLORS['text']};
                background-color: {COLORS['surface_hover']};
            }}
        """)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        self.btn_save = QPushButton("Save Strategy")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['primary']};
                color: white;
                font-weight: 700;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['primary_hover']};
            }}
        """)
        self.btn_save.clicked.connect(self._on_save_clicked)

        self.header.add_action_widget(self.btn_sync_resume)
        self.header.add_action_widget(self.btn_reset)
        self.header.add_action_widget(self.btn_save)
        main_layout.addWidget(self.header)

        # 2. Toast Notification Bar
        self.notification_bar = NotificationBar(self)
        main_layout.addWidget(self.notification_bar)

        # 3. Compact Strategy Summary Header
        self.summary_card = SearchSummaryCard(self)
        self.summary_card.preview_clicked.connect(self._open_preview_dialog)
        main_layout.addWidget(self.summary_card)

        # 4. Scrollable Main Strategy Workspace
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        container = QWidget()
        container.setStyleSheet(f"background-color: {COLORS['background']};")
        form_layout = QVBoxLayout(container)
        form_layout.setContentsMargins(0, 8, 0, 16)
        form_layout.setSpacing(16)

        # SECTION 1: Target Roles (First-Class Feature)
        form_layout.addWidget(self._build_section_header(
            title="Target Roles",
            subtitle="Job titles and keywords JobPilot will rotate through. Type or paste comma-separated values.",
        ))

        self.tag_search_terms = SearchKeywordInput(
            placeholder="e.g. RPA Developer, Automation Anywhere Developer, Python Automation Engineer...",
            badge_prefix="target roles",
            parent=self,
        )
        self.tag_search_terms.tags_changed.connect(self._on_field_changed)
        form_layout.addWidget(self.tag_search_terms)

        # SECTION 2: Search Scope (Platform + Location + Experience unified)
        form_layout.addWidget(self._build_section_header(
            title="Search Scope",
            subtitle="Configure target platforms, geographic location, and candidate experience range.",
        ))

        self.scope_card = SearchScopeCard(self)
        self.scope_card.field_changed.connect(self._on_field_changed)
        self.scope_card.platform_changed.connect(self.load_platform_search)
        form_layout.addWidget(self.scope_card)

        # Aliases for backward compatibility and test contracts
        self.platforms_card = self.scope_card
        self.location_card = self.scope_card
        self.cmb_platform = self.scope_card.cmb_platform
        self.chk_apply_all_platforms = self.scope_card.chk_apply_all_platforms
        self.txt_location = self.scope_card.txt_location
        self.spn_experience = self.scope_card.spn_experience

        # SECTION 3: Search Preferences (Freshness, pagination, thresholds)
        form_layout.addWidget(self._build_section_header(
            title="Search Preferences",
            subtitle="Set discovery freshness horizon, result depth, and keyword switching limits.",
        ))

        self.preferences_card = SearchPreferencesCard(self)
        self.preferences_card.field_changed.connect(self._on_field_changed)
        form_layout.addWidget(self.preferences_card)

        # Aliases
        self.cmb_date_posted = self.preferences_card.cmb_date_posted
        self.chk_easy_apply = self.preferences_card.chk_easy_apply
        self.spn_max_pages = self.preferences_card.spn_max_pages
        self.spn_switch_number = self.preferences_card.spn_switch_number
        self.spn_skips_limit = self.preferences_card.spn_skips_limit

        # SECTION 4: Instant Skip Rules & Description Filters
        form_layout.addWidget(self._build_section_header(
            title="Exclusion & Skip Rules",
            subtitle="Disqualify jobs instantly based on negative titles or after extracting the description.",
        ))

        self.skip_rules_card = SearchSkipRulesCard(self)
        self.skip_rules_card.load_rpa_clicked.connect(self._load_rpa_exclusions)
        self.skip_rules_card.load_standard_bad_clicked.connect(self._load_standard_bad_words)
        self.skip_rules_card.rules_changed.connect(self._on_field_changed)
        form_layout.addWidget(self.skip_rules_card)

        # Aliases
        self.tag_negative_titles = self.skip_rules_card.tag_negative_titles
        self.tag_bad_words = self.skip_rules_card.tag_bad_words

        # SECTION 5: Advanced Automation (Collapsible Disclosure)
        adv_header_box = QHBoxLayout()
        adv_header_box.setSpacing(8)

        self.btn_toggle_advanced = QPushButton("▾ Advanced Automation && Cycle Controls")
        self.btn_toggle_advanced.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_advanced.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: none;
                font-size: 13px;
                font-weight: 700;
                text-align: left;
                padding: 4px 0;
            }}
            QPushButton:hover {{
                color: {COLORS['accent']};
            }}
        """)
        self.btn_toggle_advanced.clicked.connect(self._toggle_advanced_section)
        adv_header_box.addWidget(self.btn_toggle_advanced)
        adv_header_box.addStretch()
        form_layout.addLayout(adv_header_box)

        self.automation_card = SearchAutomationCard(self)
        self.automation_card.field_changed.connect(self._on_field_changed)
        form_layout.addWidget(self.automation_card)

        # Aliases
        self.chk_run_non_stop = self.automation_card.chk_run_non_stop
        self.chk_cycle_date = self.automation_card.chk_cycle_date
        self.chk_alternate_sort = self.automation_card.chk_alternate_sort
        self.chk_stop_date_24h = self.automation_card.chk_stop_date_24h
        self.spn_sleep_duration = self.automation_card.spn_sleep_duration

        form_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll, 1)

        # 5. Clean Sticky Save Bar
        self.sticky_bar = SearchStickyBar(self)
        self.sticky_bar.save_clicked.connect(self._on_save_clicked)
        self.sticky_bar.reset_clicked.connect(self._on_reset_clicked)
        main_layout.addWidget(self.sticky_bar)

    def _build_section_header(self, title: str, subtitle: str) -> QWidget:
        """Constructs an unboxed section header sitting naturally above its content."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(2)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"""
            font-size: 14px;
            font-weight: 700;
            color: {COLORS['text']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(lbl_t)

        lbl_s = QLabel(subtitle)
        lbl_s.setStyleSheet(f"""
            font-size: 11px;
            color: {COLORS['text_muted']};
            background: transparent;
            border: none;
        """)
        layout.addWidget(lbl_s)

        return w

    def _toggle_advanced_section(self) -> None:
        """Toggles visibility of the Advanced Automation card."""
        is_visible = self.automation_card.isVisible()
        self.automation_card.setVisible(not is_visible)
        arrow = "▾" if not is_visible else "▸"
        self.btn_toggle_advanced.setText(f"{arrow} Advanced Automation && Cycle Controls")

    def _on_field_changed(self, *args) -> None:
        if self._is_loading:
            return

        self._update_summary_card()
        self.sticky_bar.set_dirty(True)

    def _update_summary_card(self) -> None:
        keywords = self.tag_search_terms.get_tags()
        location = self.txt_location.text().strip()
        plat = self.cmb_platform.currentText()
        sync_all = self.chk_apply_all_platforms.isChecked()
        exp = self.spn_experience.value()
        date_posted = self.cmb_date_posted.currentText()
        easy_apply = self.chk_easy_apply.isChecked()
        continuous = self.chk_run_non_stop.isChecked()

        self.summary_card.update_summary(
            keywords=keywords,
            location=location,
            platform=plat,
            sync_all=sync_all,
            experience=exp,
            date_posted=date_posted,
            easy_apply=easy_apply,
            continuous=continuous,
        )

    def _open_preview_dialog(self) -> None:
        keywords = self.tag_search_terms.get_tags()
        location = self.txt_location.text().strip()
        sync_all = self.chk_apply_all_platforms.isChecked()
        platforms = ["LinkedIn", "Naukri", "Indeed", "Foundit", "Glassdoor"] if sync_all else [self.cmb_platform.currentText()]
        date_posted = self.cmb_date_posted.currentText()
        easy_apply = self.chk_easy_apply.isChecked()
        exp = self.spn_experience.value()

        dlg = SearchPreviewDialog(
            keywords=keywords,
            location=location,
            platforms=platforms,
            date_posted=date_posted,
            easy_apply=easy_apply,
            experience=exp,
            parent=self,
        )
        dlg.exec()

    def load_platform_search(self, platform_name: str) -> None:
        """Loads search configuration from database into the form."""
        self._is_loading = True
        try:
            data = self.service.get_search_config(platform_name)

            self.tag_search_terms.set_tags(data.get("search_terms", []))
            self.txt_location.setText(data.get("search_location", "India"))
            self.spn_experience.setValue(data.get("experience_years", 5))

            date_val = data.get("date_posted", "Past week")
            idx = self.cmb_date_posted.findText(date_val)
            if idx >= 0:
                self.cmb_date_posted.setCurrentIndex(idx)

            self.spn_max_pages.setValue(data.get("max_pages_per_search", 3))
            self.spn_switch_number.setValue(data.get("switch_number", 30))
            self.spn_skips_limit.setValue(data.get("consecutive_skips_limit", 10))
            self.chk_easy_apply.setChecked(data.get("easy_apply_only", True))

            self.tag_negative_titles.set_tags(data.get("negative_title_words", []))
            self.tag_bad_words.set_tags(data.get("bad_words", []))

            # Cycle Controls
            self.chk_run_non_stop.setChecked(data.get("run_non_stop", False))
            self.chk_cycle_date.setChecked(data.get("cycle_date_posted", True))
            self.chk_alternate_sort.setChecked(data.get("alternate_sortby", True))
            self.chk_stop_date_24h.setChecked(data.get("stop_date_cycle_at_24hr", True))
            self.spn_sleep_duration.setValue(data.get("sleep_duration_minutes", 10))

            self._update_summary_card()
            self.sticky_bar.set_dirty(False)
        finally:
            self._is_loading = False

    def _load_rpa_exclusions(self) -> None:
        """Appends domain exclusion negative keywords for software / RPA automation."""
        current = self.tag_negative_titles.get_tags()
        rpa_exclusions = KeywordExtractorService.get_rpa_domain_exclusions()
        combined = list(dict.fromkeys(current + rpa_exclusions))
        self.tag_negative_titles.set_tags(combined)
        self.notification_bar.show_message(
            "info", f"Appended {len(rpa_exclusions)} domain exclusion keywords (Android, Full Stack, Java, etc.)."
        )
        self._on_field_changed()

    def _load_standard_bad_words(self) -> None:
        """Appends standard blacklist red flags."""
        current = self.tag_bad_words.get_tags()
        common = KeywordExtractorService.get_common_blacklists()
        combined = list(dict.fromkeys(current + common))
        self.tag_bad_words.set_tags(combined)
        self.notification_bar.show_message("info", "Appended standard job description blacklist phrases.")
        self._on_field_changed()

    def _on_sync_from_resume_clicked(self) -> None:
        """Inspects candidate's profile/resume to extract target keywords and domain exclusions."""
        try:
            from app.services.profile_service import ProfileService
            ps = ProfileService(self.service._session_factory)
            user, profile, pro = ps.get_primary_user_profile()

            role_title = (pro.current_title if pro else None) or "RPA Developer / AI Automation Engineer"
            skills = (pro.skills if pro else None) or ["Automation Anywhere", "Python", "SQL"]

            rec = KeywordExtractorService.get_recommendations_for_role(role_title, skills)

            self.tag_search_terms.set_tags(rec["search_terms"])
            self.tag_negative_titles.set_tags(rec["negative_title_words"])
            self.tag_bad_words.set_tags(rec["bad_words"])

            self.notification_bar.show_message(
                "success",
                f"Extracted {len(rec['search_terms'])} search terms and {len(rec['negative_title_words'])} domain exclusions from profile '{role_title}'.",
                duration_ms=6000,
            )
            self._on_field_changed()
        except Exception as e:
            self.notification_bar.show_message("danger", f"Failed to sync from resume: {e}")

    def _on_save_clicked(self) -> None:
        plat = self.cmb_platform.currentText().strip().lower()
        sync_all = self.chk_apply_all_platforms.isChecked()

        success, err = self.service.save_search_config(
            platform_name=plat,
            search_terms=self.tag_search_terms.get_tags(),
            search_location=self.txt_location.text().strip(),
            experience_years=self.spn_experience.value(),
            date_posted=self.cmb_date_posted.currentText(),
            easy_apply_only=self.chk_easy_apply.isChecked(),
            max_pages_per_search=self.spn_max_pages.value(),
            switch_number=self.spn_switch_number.value(),
            consecutive_skips_limit=self.spn_skips_limit.value(),
            bad_words=self.tag_bad_words.get_tags(),
            negative_title_words=self.tag_negative_titles.get_tags(),
            run_non_stop=self.chk_run_non_stop.isChecked(),
            cycle_date_posted=self.chk_cycle_date.isChecked(),
            alternate_sortby=self.chk_alternate_sort.isChecked(),
            stop_date_cycle_at_24hr=self.chk_stop_date_24h.isChecked(),
            sleep_duration_minutes=self.spn_sleep_duration.value(),
            sync_to_all_platforms=sync_all,
        )

        if success:
            dest = "ALL platforms (LinkedIn, Naukri, Indeed, Foundit, Glassdoor)" if sync_all else plat.title()
            self.notification_bar.show_message(
                "success", f"Search strategy for {dest} updated successfully."
            )
            self.sticky_bar.set_dirty(False)
            self.data_updated.emit("search")
            self.data_updated.emit("platforms")
            self.load_platform_search(plat)
        else:
            self.notification_bar.show_message("danger", f"Failed to save: {err}")

    def _on_reset_clicked(self) -> None:
        plat = self.cmb_platform.currentText().strip().lower()
        self.load_platform_search(plat)
        self.notification_bar.show_message(
            "info", f"Reloaded latest saved search criteria for {plat.title()}."
        )
