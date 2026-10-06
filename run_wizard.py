"""
Quick standalone launcher for testing the JobPilot Setup Wizard.
Runs the OnboardingWizardDialog directly with the full design system applied.
"""

import sys
from PySide6.QtWidgets import QApplication
from app.ui.theme import ThemeManager
from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog
from app.services.setup.setup_service import SetupService


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(ThemeManager.get_stylesheet())

    setup_service = SetupService()
    dialog = OnboardingWizardDialog(setup_service=setup_service)
    dialog.onboarding_completed.connect(lambda data: print(f"\n[Setup Wizard Finished] Result: {data}\n"))
    dialog.exec()


if __name__ == "__main__":
    main()
