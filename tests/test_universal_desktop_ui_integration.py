"""Integration tests for Universal ATS UI workflows across Desktop UI components."""

import os
import unittest
from unittest.mock import MagicMock

# Force offscreen Qt platform for test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from app.db.models import Job
from app.services.automation_events import AutomationState
from app.ui.views.automation_view import AutomationView
from app.ui.widgets.automation.universal_target_card import UniversalTargetCard
from app.ui.widgets.jobs.jobs_detail_panel import JobsDetailPanel


def _create_mock_manager():
    mock_manager = MagicMock()
    mock_manager.get_recent_runs.return_value = []
    mock_state = MagicMock()
    mock_state.value = AutomationState.IDLE.value
    mock_manager.get_state.return_value = mock_state
    return mock_manager


class TestUniversalUIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_universal_target_card_getters_and_setters(self):
        card = UniversalTargetCard()
        card.txt_url.setText("https://boards.greenhouse.io/testcompany/jobs/998877")
        card.txt_title.setText("Senior Backend Engineer")
        card.txt_company.setText("Acme Corp")

        self.assertEqual(card.get_target_url(), "https://boards.greenhouse.io/testcompany/jobs/998877")
        self.assertEqual(card.get_job_title(), "Senior Backend Engineer")
        self.assertEqual(card.get_company(), "Acme Corp")

    def test_universal_target_card_set_target_job(self):
        card = UniversalTargetCard()
        job = Job(
            id=101,
            title="Full Stack Engineer",
            company_raw="Stripe",
            application_url="https://jobs.lever.co/stripe/abc-123",
            source_url="https://linkedin.com/jobs/view/123",
            application_method="COMPANY_PORTAL",
        )
        card.set_target_job(job)

        self.assertEqual(card.get_target_url(), "https://jobs.lever.co/stripe/abc-123")
        self.assertEqual(card.get_job_title(), "Full Stack Engineer")
        self.assertEqual(card.get_company(), "Stripe")

    def test_universal_target_card_set_target_job_from_url_string(self):
        card = UniversalTargetCard()
        card.set_target_job("https://jobs.lever.co/openai/123", job_title="Research Engineer", company="OpenAI")

        self.assertEqual(card.get_target_url(), "https://jobs.lever.co/openai/123")
        self.assertEqual(card.get_job_title(), "Research Engineer")
        self.assertEqual(card.get_company(), "OpenAI")

    def test_automation_view_universal_target_card_visibility(self):
        mock_manager = _create_mock_manager()
        view = AutomationView(automation_manager=mock_manager)

        # Initially, platform is linkedin -> card is hidden
        self.assertTrue(view.universal_target_card.isHidden())

        # Select universal platform -> card becomes visible (not hidden)
        view.platform_selector.select_platform("universal")
        self.assertFalse(view.universal_target_card.isHidden())
        self.assertFalse(view.universal_timeline.isHidden())

        # Switch back to naukri -> card is hidden
        view.platform_selector.select_platform("naukri")
        self.assertTrue(view.universal_target_card.isHidden())
        self.assertTrue(view.universal_timeline.isHidden())

    def test_automation_view_validation_without_target_url(self):
        mock_manager = _create_mock_manager()
        view = AutomationView(automation_manager=mock_manager)
        view.platform_selector.select_platform("universal")
        view.universal_target_card.txt_url.clear()

        # Click start without url
        view._on_start_clicked()

        # Manager start_automation should NOT have been called
        mock_manager.start_automation.assert_not_called()
        self.assertIn("Please enter or select a Company Portal application URL", view.notification_bar.message_label.text())

    def test_automation_view_start_with_target_url(self):
        mock_manager = _create_mock_manager()
        mock_manager.start_automation.return_value = (True, None)

        view = AutomationView(automation_manager=mock_manager)
        view.prepare_universal_run(
            "https://jobs.lever.co/acme/backend",
            job_title="Backend Engineer",
            company="Acme Corp"
        )

        self.assertEqual(view.platform_selector.current_platform(), "universal")
        self.assertFalse(view.universal_target_card.isHidden())

        view._on_start_clicked()

        mock_manager.start_automation.assert_called_once_with(
            platform="universal",
            target_url="https://jobs.lever.co/acme/backend",
            job_title="Backend Engineer",
            company="Acme Corp"
        )

    def test_jobs_detail_panel_universal_button_and_signal(self):
        panel = JobsDetailPanel()
        portal_job = Job(
            id=202,
            title="ML Engineer",
            company_raw="Anthropic",
            application_url="https://boards.greenhouse.io/anthropic/jobs/456",
            application_method="COMPANY_PORTAL",
        )

        signal_received = []
        panel.apply_universal_requested.connect(lambda job: signal_received.append(job))

        panel.set_job(portal_job)

        self.assertFalse(panel.btn_apply_universal.isHidden())
        self.assertTrue(panel.btn_apply_universal.isEnabled())

        # Simulate user clicking "Apply with Universal AI Agent"
        panel.btn_apply_universal.click()

        self.assertEqual(len(signal_received), 1)
        self.assertEqual(signal_received[0].title, "ML Engineer")


if __name__ == "__main__":
    unittest.main()
