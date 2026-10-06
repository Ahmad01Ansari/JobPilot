"""Sections package for settings category views."""

from app.ui.views.settings.sections.general_section import GeneralSection
from app.ui.views.settings.sections.browser_section import BrowserSection
from app.ui.views.settings.sections.automation_section import AutomationSection
from app.ui.views.settings.sections.ai_section import AISection
from app.ui.views.settings.sections.credentials_section import CredentialsSection
from app.ui.views.settings.sections.backup_section import BackupSection

__all__ = [
    "GeneralSection",
    "BrowserSection",
    "AutomationSection",
    "AISection",
    "CredentialsSection",
    "BackupSection",
]
