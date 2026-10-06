"""Redesigned System Settings & Security command center for JobPilot."""

from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from app.services.ai_service import UniversalAIService
from app.services.backup_service import BackupService
from app.services.secrets_service import SecretsService
from app.services.settings_service import SettingsService
from app.ui.theme import COLORS
from app.ui.widgets.notification_bar import NotificationBar
from app.ui.views.settings.configuration_health_bar import ConfigurationHealthBar
from app.ui.views.settings.presentation_model import SettingsPresentationModel
from app.ui.views.settings.sections.ai_section import AISection
from app.ui.views.settings.sections.automation_section import AutomationSection
from app.ui.views.settings.sections.backup_section import BackupSection
from app.ui.views.settings.sections.browser_section import BrowserSection
from app.ui.views.settings.sections.credentials_section import CredentialsSection
from app.ui.views.settings.sections.general_section import GeneralSection
from app.ui.views.settings.settings_header import SettingsHeader
from app.ui.views.settings.settings_registry import search_settings
from app.ui.views.settings.settings_sidebar import SettingsSidebar


class TabsShim(QObject):
    """Shim providing backward-compatible tabs interface for existing test suites."""

    def __init__(self, stacked_widget: QStackedWidget, titles: List[str]):
        super().__init__()
        self._stacked = stacked_widget
        self._titles = titles

    def count(self) -> int:
        return len(self._titles)

    def tabText(self, index: int) -> str:
        if 0 <= index < len(self._titles):
            return self._titles[index]
        return ""

    def currentIndex(self) -> int:
        return self._stacked.currentIndex()

    def setCurrentIndex(self, index: int) -> None:
        self._stacked.setCurrentIndex(index)


class SettingsView(QWidget):
    """Modern Desktop Control Center for JobPilot System Settings & Security."""

    SECTION_MAP = {
        "general": 0,
        "browser": 1,
        "automation": 2,
        "ai": 3,
        "credentials": 4,
        "backup": 5,
    }

    INDEX_TO_SECTION = {v: k for k, v in SECTION_MAP.items()}

    def __init__(
        self,
        service: Optional[SettingsService] = None,
        secrets_service: Optional[SecretsService] = None,
        backup_service: Optional[BackupService] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.service = service or SettingsService()
        self.secrets_service = secrets_service or SecretsService()
        self.backup_service = backup_service or BackupService(session_factory=self.service._session_factory)
        self.ai_service = UniversalAIService(session_factory=self.service._session_factory)

        self.presentation_model = SettingsPresentationModel(self)
        self._setup_ui()
        self.load_settings()
        self.load_credentials_display()

    def _setup_ui(self) -> None:
        self.setObjectName("SettingsView")
        self.setStyleSheet(f"""
            QWidget#SettingsView {{
                background-color: {COLORS.get('background', '#0F1117')};
            }}
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(20, 16, 20, 16)
        root_layout.setSpacing(12)

        # 1. Header (Title, Search, Unsaved indicator, CTAs)
        self.header = SettingsHeader(self)
        self.header.save_requested.connect(self._save_active_section)
        self.header.reset_requested.connect(self._reset_active_section)
        self.header.search_changed.connect(self._on_search_query)
        root_layout.addWidget(self.header)

        # 2. Notification Alert Bar
        self.notification_bar = NotificationBar(self)
        root_layout.addWidget(self.notification_bar)

        # 3. Top Configuration Health Bar
        self.health_bar = ConfigurationHealthBar(self)
        self.health_bar.section_navigated.connect(self._switch_section_safe)
        root_layout.addWidget(self.health_bar)

        # 4. Body Splitter (Sidebar + Active Section Content)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(14)

        # Left Sidebar (240px)
        self.sidebar = SettingsSidebar(self)
        self.sidebar.section_selected.connect(self._switch_section_safe)
        body_layout.addWidget(self.sidebar)

        # Right Stacked Sections Container (Controlled width)
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.stacked_widget = QStackedWidget(content_container)
        self.stacked_widget.setStyleSheet("background: transparent;")

        # Instantiate Sections
        self.general_section = GeneralSection(self)
        self.browser_section = BrowserSection(self)
        self.automation_section = AutomationSection(self)
        self.ai_section = AISection(self.ai_service, self.secrets_service, self)
        self.credentials_section = CredentialsSection(self.secrets_service, self)
        self.backup_section = BackupSection(self.backup_service, self)

        # Add to stack
        self.stacked_widget.addWidget(self.general_section)      # 0
        self.stacked_widget.addWidget(self.browser_section)      # 1
        self.stacked_widget.addWidget(self.automation_section)   # 2
        self.stacked_widget.addWidget(self.ai_section)           # 3
        self.stacked_widget.addWidget(self.credentials_section)  # 4
        self.stacked_widget.addWidget(self.backup_section)       # 5

        content_layout.addWidget(self.stacked_widget)
        body_layout.addWidget(content_container, 1)
        root_layout.addLayout(body_layout, 1)

        # Wire Dirty State Signals
        self.general_section.changed.connect(lambda: self._on_section_modified("general"))
        self.browser_section.changed.connect(lambda: self._on_section_modified("browser"))
        self.automation_section.changed.connect(lambda: self._on_section_modified("automation"))
        self.ai_section.changed.connect(lambda: self._on_section_modified("ai"))
        self.ai_section.saved.connect(self._on_ai_saved)
        self.credentials_section.email_changed.connect(lambda: self._on_section_modified("email"))

        # Wire Health Bar Signals
        self.credentials_section.credentials_updated.connect(self.health_bar.update_credentials_count)
        self.credentials_section.email_test_completed.connect(lambda ok: self.health_bar.update_email_status(True, is_verified=ok))
        self.ai_section.test_completed.connect(lambda ok, lat: self.health_bar.update_ai_status(True, is_tested=ok, latency_ms=lat))
        self.backup_section.backup_completed.connect(lambda has_b: self.health_bar.update_backup_status(has_b, is_verified=has_b))

        # Wire Setup Wizard
        self.ai_section.wizard_requested.connect(self._launch_setup_wizard)

        # Compatibility Tab Shim
        self.tabs = TabsShim(
            self.stacked_widget,
            [
                "General",
                "Browser",
                "Automation",
                "AI & Screening",
                "Credentials & Security",
                "Backup & Restore",
            ],
        )

    # =========================================================================
    # Compatibility Properties & Accessors for Tests
    # =========================================================================
    @property
    def spn_click_gap(self):
        return self.general_section.spn_click_gap

    @property
    def spin_click_gap(self):
        return self.general_section.spn_click_gap

    @property
    def btn_save(self):
        return self.header.btn_save

    @property
    def btn_reset(self):
        return self.header.btn_reset

    @property
    def txt_li_pwd(self):
        return self.credentials_section.txt_li_pwd

    @property
    def txt_nk_pwd(self):
        return self.credentials_section.txt_nk_pwd

    @property
    def txt_ai_key(self):
        return self.ai_section.txt_ai_key

    # =========================================================================
    # Data Loading & Initialization
    # =========================================================================
    def load_settings(self) -> None:
        """Loads non-sensitive configuration into sections and initializes presentation baseline."""
        gen_vals = self.service.get_category_settings("general")
        self.general_section.load_values(gen_vals)
        self.presentation_model.set_initial_category("general", gen_vals)

        browser_vals = self.service.get_category_settings("browser")
        self.browser_section.load_values(browser_vals)
        self.presentation_model.set_initial_category("browser", browser_vals)

        auto_vals = self.service.get_category_settings("automation")
        self.automation_section.load_values(auto_vals)
        self.presentation_model.set_initial_category("automation", auto_vals)

        # AI Configuration
        ai_cfg = self.ai_service.get_config()
        self.ai_section.load_values(ai_cfg)

        self._ai_dirty = False
        self._email_dirty = False
        # Update Health Bar
        self.health_bar.update_automation_status(self.automation_section.is_safety_active())
        self.health_bar.update_ai_status(ai_cfg.get("enabled", True), is_tested=False)

        # Reset header dirty state
        self.header.set_dirty_state(False)

    def load_credentials_display(self) -> None:
        """Refreshes platform and email credentials overview."""
        self.credentials_section.refresh_display()
        self.backup_section.refresh_backup_status()

    # =========================================================================
    # Dirty State & Section Navigation
    # =========================================================================
    def _on_section_modified(self, section: str) -> None:
        if section == "general":
            for k, v in self.general_section.get_values().items():
                self.presentation_model.update_current_value("general", k, v)
        elif section == "browser":
            for k, v in self.browser_section.get_values().items():
                self.presentation_model.update_current_value("browser", k, v)
        elif section == "automation":
            for k, v in self.automation_section.get_values().items():
                self.presentation_model.update_current_value("automation", k, v)
            self.health_bar.update_automation_status(self.automation_section.is_safety_active())
        elif section == "ai":
            self._ai_dirty = True
        elif section == "email":
            self._email_dirty = True

        self.header.set_dirty_state(self.presentation_model.is_any_dirty() or self._ai_dirty or self._email_dirty)

    def _switch_section_safe(self, target_section: str) -> None:
        """Guards against accidental loss of unsaved changes when navigating sections."""
        current_idx = self.stacked_widget.currentIndex()
        current_section = self.INDEX_TO_SECTION.get(current_idx, "general")

        if current_section == target_section:
            return

        # Check if current section is dirty
        is_dirty = (
            self.presentation_model.is_category_dirty(current_section)
            or (current_section == "ai" and self._ai_dirty)
            or (current_section == "credentials" and self._email_dirty)
        )
        if is_dirty:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                f"You have unsaved changes in {current_section.capitalize()}. Save changes before leaving?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if reply == QMessageBox.Save:
                self._save_active_section()
            elif reply == QMessageBox.Cancel:
                # Keep active section in sidebar
                self.sidebar.set_current_section(current_section)
                return
            else:
                # Discard: Revert current section to initial baseline
                self._revert_section_ui(current_section)

        # Switch to target section
        target_idx = self.SECTION_MAP.get(target_section, 0)
        self.stacked_widget.setCurrentIndex(target_idx)
        self.sidebar.set_current_section(target_section)

    def _revert_section_ui(self, section: str) -> None:
        if section == "general":
            self.general_section.load_values(self.service.get_category_settings("general"))
            self.presentation_model.mark_category_clean("general")
        elif section == "browser":
            self.browser_section.load_values(self.service.get_category_settings("browser"))
            self.presentation_model.mark_category_clean("browser")
        elif section == "automation":
            self.automation_section.load_values(self.service.get_category_settings("automation"))
            self.presentation_model.mark_category_clean("automation")
        elif section == "ai":
            self.ai_section.load_values(self.ai_service.get_config())
            self._ai_dirty = False
        elif section == "credentials":
            self.credentials_section.refresh_display()
            self._email_dirty = False
        self.header.set_dirty_state(self.presentation_model.is_any_dirty() or self._ai_dirty or self._email_dirty)

    def _on_ai_saved(self) -> None:
        self._ai_dirty = False
        self.header.set_dirty_state(self.presentation_model.is_any_dirty() or self._ai_dirty or self._email_dirty)
        self.notification_bar.show_message("AI provider configuration saved successfully.", "success")

    # =========================================================================
    # Section-Scoped Persistence & Reset
    # =========================================================================
    def _save_active_section(self) -> None:
        """Persists only the actively viewed section's configuration to avoid cross-category overwrites."""
        current_idx = self.stacked_widget.currentIndex()
        current_section = self.INDEX_TO_SECTION.get(current_idx, "general")
        self.header.set_saving(True)

        try:
            if current_section == "general":
                delta = self.general_section.get_values()
                ok, err = self.service.update_section("general", delta)
                if ok:
                    self.presentation_model.mark_category_clean("general")
                    self.notification_bar.show_message("General settings saved successfully.", "success")
                else:
                    self.notification_bar.show_message(err or "Failed to save general settings.", "danger")

            elif current_section == "browser":
                delta = self.browser_section.get_values()
                ok, err = self.service.update_section("browser", delta)
                if ok:
                    self.presentation_model.mark_category_clean("browser")
                    self.notification_bar.show_message("Browser settings saved successfully.", "success")
                else:
                    self.notification_bar.show_message(err or "Failed to save browser settings.", "danger")

            elif current_section == "automation":
                delta = self.automation_section.get_values()
                ok, err = self.service.update_section("automation", delta)
                if ok:
                    self.presentation_model.mark_category_clean("automation")
                    self.notification_bar.show_message("Automation safeguards saved successfully.", "success")
                else:
                    self.notification_bar.show_message(err or "Failed to save automation safeguards.", "danger")

            elif current_section == "ai":
                self.ai_section._save_provider_settings()
                self._ai_dirty = False
                self.header.set_dirty_state(self.presentation_model.is_any_dirty() or self._ai_dirty or self._email_dirty)
                self.notification_bar.show_message("AI configuration saved successfully.", "success")

            elif current_section == "credentials":
                self.credentials_section.save_email_credentials()
                self._email_dirty = False
                self.notification_bar.show_message("Email outreach settings saved successfully.", "success")

            elif current_section == "backup":
                self.notification_bar.show_message("Backup settings updated.", "info")

        finally:
            self.header.set_dirty_state(self.presentation_model.is_any_dirty() or self._ai_dirty or self._email_dirty)

    def _reset_active_section(self) -> None:
        """Prompts confirmation and resets only the actively displayed category to its production defaults."""
        current_idx = self.stacked_widget.currentIndex()
        current_section = self.INDEX_TO_SECTION.get(current_idx, "general")

        if current_section in ("general", "browser", "automation"):
            self.service.reset_section(current_section)
            if current_section == "general":
                self.general_section.reset_to_defaults()
                self.presentation_model.mark_category_clean("general")
            elif current_section == "browser":
                self.browser_section.reset_to_defaults()
                self.presentation_model.mark_category_clean("browser")
            elif current_section == "automation":
                self.automation_section.reset_to_defaults()
                self.presentation_model.mark_category_clean("automation")
            self.notification_bar.show_message(f"Reset {current_section.capitalize()} settings to defaults.", "info")

        elif current_section == "ai":
            self.ai_section.reset_to_defaults()
            self.notification_bar.show_message("Reset AI configuration to defaults.", "info")

        self.header.set_dirty_state(self.presentation_model.is_any_dirty())

    # =========================================================================
    # Compatibility Callbacks for Existing Callers
    # =========================================================================
    def _save_active_tab(self) -> None:
        self._save_active_section()

    def _reset_active_tab(self) -> None:
        self._reset_active_section()

    # =========================================================================
    # Search Navigation
    # =========================================================================
    def _on_search_query(self, query: str) -> None:
        results = search_settings(query)
        if results:
            best_match = results[0]
            target_section = best_match["section"]
            self._switch_section_safe(target_section)

    def _launch_setup_wizard(self) -> None:
        try:
            from app.ui.views.onboarding_wizard import OnboardingWizard
            wizard = OnboardingWizard(self.service._session_factory, self)
            wizard.exec()
            self.load_settings()
            self.load_credentials_display()
        except Exception as e:
            self.notification_bar.show_message(f"Could not open setup wizard: {e}", "warning")
