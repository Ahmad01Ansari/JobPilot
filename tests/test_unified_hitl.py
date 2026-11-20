"""Comprehensive unit tests for the Unified Human-in-the-Loop (HITL) architecture.

Tests event classification, chat input routing (CAPTCHA, OTP, Login, Approval),
modal auto-dismissal, and bridge input queues.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.services.automation_bridge import AutomationBridge
from app.services.automation_events import AutomationInterventionEvent, InterventionType
from app.services.pilot.pilot_models import InterventionKind, InterventionStatus
from app.services.pilot.pilot_service import PilotService


class TestUnifiedHITL(unittest.TestCase):
    def setUp(self):
        self.bridge = AutomationBridge(session_factory=None)
        self.pilot = PilotService(session_factory=None)
        self.pilot._active_interventions.clear()
        self.mock_mgr = MagicMock()
        self.pilot._automation_service = self.mock_mgr

    def test_intervention_classification_captcha(self):
        """Verify CAPTCHA events are mapped to InterventionKind.CAPTCHA with appropriate prompt."""
        ev = AutomationInterventionEvent(
            run_id="run-1",
            platform="indeed",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Cloudflare CAPTCHA challenge detected",
        )
        self.pilot._on_bot_intervention(ev)

        open_invs = [i for i in self.pilot._active_interventions.values() if i.status == InterventionStatus.OPEN]
        self.assertEqual(len(open_invs), 1)
        inv = open_invs[0]
        self.assertEqual(inv.kind, InterventionKind.CAPTCHA)
        self.assertIn("Visual verification challenge", inv.prompt)
        self.assertIn("I have solved the CAPTCHA", inv.options)

    def test_intervention_classification_2fa_otp(self):
        """Verify OTP/2FA events are mapped to InterventionKind.TWO_FACTOR."""
        ev = AutomationInterventionEvent(
            run_id="run-2",
            platform="indeed",
            intervention_type=InterventionType.TWO_FACTOR_AUTH,
            message="Please enter the verification code sent to your email",
        )
        self.pilot._on_bot_intervention(ev)

        open_invs = [i for i in self.pilot._active_interventions.values() if i.status == InterventionStatus.OPEN]
        self.assertEqual(len(open_invs), 1)
        inv = open_invs[0]
        self.assertEqual(inv.kind, InterventionKind.TWO_FACTOR)
        self.assertIn("Two-factor authentication", inv.prompt)

    def test_intervention_classification_manual_login(self):
        """Verify login required events are mapped to InterventionKind.MANUAL_LOGIN."""
        ev = AutomationInterventionEvent(
            run_id="run-3",
            platform="naukri",
            intervention_type=InterventionType.LOGIN_REQUIRED,
            message="Session expired, please sign in",
        )
        self.pilot._on_bot_intervention(ev)

        open_invs = [i for i in self.pilot._active_interventions.values() if i.status == InterventionStatus.OPEN]
        self.assertEqual(len(open_invs), 1)
        inv = open_invs[0]
        self.assertEqual(inv.kind, InterventionKind.MANUAL_LOGIN)
        self.assertIn("Manual sign-in", inv.prompt)
        self.assertIn("I am logged in", inv.options)

    def test_intervention_classification_approval(self):
        """Verify review events are mapped to InterventionKind.APPROVAL."""
        ev = AutomationInterventionEvent(
            run_id="run-4",
            platform="indeed",
            intervention_type=InterventionType.PRE_SUBMISSION_REVIEW,
            message="Review required before final submission",
        )
        self.pilot._on_bot_intervention(ev)

        open_invs = [i for i in self.pilot._active_interventions.values() if i.status == InterventionStatus.OPEN]
        self.assertEqual(len(open_invs), 1)
        inv = open_invs[0]
        self.assertEqual(inv.kind, InterventionKind.APPROVAL)
        self.assertIn("Approve & Submit", inv.options)
        self.assertIn("Skip Job", inv.options)

    def test_chat_input_resolves_captcha(self):
        """Verify typing 'solved' in chat resolves active CAPTCHA and notifies bridge."""
        ev = AutomationInterventionEvent(
            run_id="run-5",
            platform="indeed",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Cloudflare Turnstile",
        )
        self.pilot._on_bot_intervention(ev)
        self.assertEqual(len(self.pilot._active_interventions), 1)

        # User types "I solved it" in chat
        self.pilot.process_user_prompt("I solved it")

        inv = list(self.pilot._active_interventions.values())[0]
        self.assertEqual(inv.status, InterventionStatus.ANSWERED)
        self.assertEqual(inv.answer, "solved")
        self.mock_mgr.provide_intervention_input.assert_called_with("solved", intervention_id=inv.id)

    def test_chat_input_resolves_otp(self):
        """Verify typing numeric OTP in chat extracts code and provides input to bridge."""
        ev = AutomationInterventionEvent(
            run_id="run-6",
            platform="indeed",
            intervention_type=InterventionType.TWO_FACTOR_AUTH,
            message="Enter OTP",
        )
        self.pilot._on_bot_intervention(ev)

        # User types natural language containing OTP
        self.pilot.process_user_prompt("my code is 849201")

        inv = list(self.pilot._active_interventions.values())[0]
        self.assertEqual(inv.status, InterventionStatus.ANSWERED)
        self.assertEqual(inv.answer, "849201")
        self.mock_mgr.provide_intervention_input.assert_called_with("849201", intervention_id=inv.id)

    def test_automation_bridge_input_queue(self):
        """Verify AutomationBridge receives input and marks captcha resolved if applicable."""
        dismiss_mock = MagicMock()
        self.bridge.on_dismiss_intervention = dismiss_mock

        self.bridge.provide_input("solved", intervention_id="inv-1")
        self.assertTrue(self.bridge._captcha_resolved)
        dismiss_mock.assert_called_with("inv-1")

        # Test OTP retrieval
        self.bridge.provide_input("582910", intervention_id="inv-2")
        val = self.bridge.get_pending_input(clear=True)
        self.assertEqual(val, "582910")
        # Cleared after retrieval
        self.assertIsNone(self.bridge.get_pending_input())


if __name__ == "__main__":
    unittest.main()
