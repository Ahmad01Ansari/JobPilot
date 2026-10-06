"""
Headless PySide6 UI tests for OnboardingWizardDialog and ProductTourOverlay.
"""

import sys
import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

# Ensure offscreen Qt application exists
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv + ["-platform", "offscreen"])

from app.ui.widgets.onboarding_wizard import OnboardingWizardDialog, STEP_KEYS
from app.ui.widgets.tour_overlay import ProductTourOverlay, TOUR_STOPS
from app.services.setup.setup_service import SetupService
from app.services.setup.setup_readiness import SetupReadinessService


class TestSetupWizardUI(unittest.TestCase):
    def setUp(self):
        self.mock_profile_service = MagicMock()
        self.mock_resume_service = MagicMock()
        self.mock_settings_service = MagicMock()
        self.mock_secrets_service = MagicMock()
        self.mock_qna_service = MagicMock()
        self.mock_platform_service = MagicMock()

        self.mock_profile_service.get_primary_user_profile.return_value = {}
        self.mock_resume_service.list_resumes.return_value = []
        self.mock_settings_service.get.return_value = {}

        self.readiness = SetupReadinessService(
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            settings_service=self.mock_settings_service,
            secrets_service=self.mock_secrets_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
        )

        self.setup_service = SetupService(
            readiness_service=self.readiness,
            profile_service=self.mock_profile_service,
            resume_service=self.mock_resume_service,
            settings_service=self.mock_settings_service,
            secrets_service=self.mock_secrets_service,
            qna_service=self.mock_qna_service,
            platform_service=self.mock_platform_service,
        )

        self.dialog = OnboardingWizardDialog(setup_service=self.setup_service)

    def tearDown(self):
        self.dialog.close()

    def test_wizard_initialization(self):
        self.assertEqual(len(self.dialog.rail_items), 10)
        self.assertEqual(self.dialog.stack.count(), 10)
        self.assertEqual(self.dialog.current_step_idx, 0)
        self.assertFalse(self.dialog.btn_back.isEnabled())

    def test_navigation_flow(self):
        # Step 0 (Welcome) -> Next -> Step 1 (AI Provider)
        self.dialog._go_next()
        self.assertEqual(self.dialog.current_step_idx, 1)
        self.assertTrue(self.dialog.btn_back.isEnabled())

        # Step 1 (AI Provider) -> Next -> Step 2 (Resume Ingest)
        self.dialog._go_next()
        self.assertEqual(self.dialog.current_step_idx, 2)

        # Go back to Step 1
        self.dialog._go_back()
        self.assertEqual(self.dialog.current_step_idx, 1)

    def test_skipping_optional_step(self):
        # Navigate to Step 1 (AI Provider) which is optional
        self.dialog._navigate_to_step(1)
        self.assertEqual(self.dialog.current_step_idx, 1)
        self.assertFalse(self.dialog.btn_skip.isHidden())

        # Skip AI step -> advances to Step 2 (Resume Ingest)
        self.dialog._skip_current_step()
        self.assertEqual(self.dialog.current_step_idx, 2)
        self.assertIn("ai_provider", self.setup_service.state.skipped_steps)

    def test_tour_overlay_initialization(self):
        mock_main_window = MagicMock()
        tour = ProductTourOverlay(main_window=mock_main_window)
        self.assertEqual(tour.current_stop, 0)
        self.assertEqual(len(TOUR_STOPS), 11)

        # Advance to stop 1 (Automation, Ctrl+2)
        tour._go_next()
        self.assertEqual(tour.current_stop, 1)
        mock_main_window.navigate_to.assert_called_with("automation")

        tour._close_tour()


if __name__ == "__main__":
    unittest.main()
