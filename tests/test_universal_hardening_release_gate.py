"""Release Gate & Hardening Tests for Phase 16: Universal AI Application Agent.

Validates:
1. Feature Flag Isolation: enable_universal_agent defaults to True and can be disabled.
2. Platform Isolation: Disabling feature flag safely inhibits Universal execution without crashing.
3. Zero-Regression Invariants: LinkedIn, Naukri, Indeed, and Foundit platform architectures are untouched.
4. Security & Compliance: Bot evasion / CAPTCHA bypass libraries are not imported in universal agent.
5. Mandatory Human Confirmation: Universal Agent cannot complete without human approval.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.services.settings_service import SettingsService, DEFAULT_SETTINGS
from platforms.router import UniversalPlatform, PlatformRouter
from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)


class TestUniversalHardeningAndReleaseGate(unittest.TestCase):
    """Certifies Phase 16 hardening, feature flag isolation, and platform invariants."""

    def test_feature_flag_registered_in_default_settings(self) -> None:
        """Verifies enable_universal_agent is declared in system defaults with category 'automation'."""
        self.assertIn("enable_universal_agent", DEFAULT_SETTINGS)
        setting = DEFAULT_SETTINGS["enable_universal_agent"]
        self.assertTrue(setting["value"], "Default value must be True")
        self.assertEqual(setting["category"], "automation")

    def test_settings_service_universal_agent_enabled_queries(self) -> None:
        """Verifies SettingsService.is_universal_agent_enabled honors boolean and string formats."""
        svc = SettingsService()

        with patch.object(svc, "get_setting", return_value=True):
            self.assertTrue(svc.is_universal_agent_enabled())

        with patch.object(svc, "get_setting", return_value=False):
            self.assertFalse(svc.is_universal_agent_enabled())

        with patch.object(svc, "get_setting", return_value="true"):
            self.assertTrue(svc.is_universal_agent_enabled())

        with patch.object(svc, "get_setting", return_value="false"):
            self.assertFalse(svc.is_universal_agent_enabled())

    def test_universal_platform_inhibited_when_flag_disabled(self) -> None:
        """Verifies UniversalPlatform aborts gracefully when enable_universal_agent is False."""
        platform = UniversalPlatform(target_url="https://jobs.example.com/apply")

        with patch.object(SettingsService, "is_universal_agent_enabled", return_value=False):
            result = platform.search_and_apply()
            self.assertEqual(result["status"], "disabled")
            self.assertEqual(result["jobs_applied"], 0)
            self.assertIn("disabled", result["error"])

    def test_platform_router_maintains_all_legacy_platforms(self) -> None:
        """Verifies PlatformRouter retains intact dispatch across all 5 platforms."""
        router = PlatformRouter()
        
        # Test routing definitions exist
        with patch.object(router, "run_linkedin", return_value=(5, 0)) as mock_li:
            router.route("linkedin")
            mock_li.assert_called_once()

        with patch.object(router, "run_naukri", return_value=(3, 0)) as mock_nk:
            router.route("naukri")
            mock_nk.assert_called_once()

        with patch.object(router, "run_indeed", return_value=(2, 0)) as mock_in:
            router.route("indeed")
            mock_in.assert_called_once()

        with patch.object(router, "run_foundit", return_value=(4, 0)) as mock_fi:
            router.route("foundit")
            mock_fi.assert_called_once()

        with patch.object(router, "run_universal", return_value=(1, 0)) as mock_un:
            router.route("universal")
            mock_un.assert_called_once()

    def test_security_invariants_no_captcha_evasion_imports(self) -> None:
        """Verifies that no CAPTCHA solving or evasion packages are imported in universal agent."""
        import app.services.automation.universal_agent as uagent_pkg
        import inspect

        source = inspect.getsource(uagent_pkg)
        forbidden_tokens = ["2captcha", "anticaptcha", "capmonster", "deathbycaptcha"]
        for token in forbidden_tokens:
            self.assertNotIn(token, source.lower(), f"Forbidden CAPTCHA bypass library detected: {token}")

    def test_state_machine_mandatory_human_review_invariant(self) -> None:
        """Verifies that the state machine enforces PENDING_HUMAN_REVIEW before SUBMITTING."""
        sm = UniversalApplicationStateMachine()
        sm.transition_to(AgentExecutionState.INITIALIZING)
        sm.transition_to(AgentExecutionState.NAVIGATING)
        sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        sm.transition_to(AgentExecutionState.FILLING_FORM)

        # Attempting to jump directly from FILLING_FORM to SUBMITTING must raise IllegalStateTransitionError
        from app.services.automation.universal_agent.state_machine import IllegalStateTransitionError
        with self.assertRaises(IllegalStateTransitionError):
            sm.transition_to(AgentExecutionState.SUBMITTING)

        # Valid transition: FILLING_FORM -> PENDING_HUMAN_REVIEW -> SUBMITTING
        sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        self.assertEqual(sm.state, AgentExecutionState.PENDING_HUMAN_REVIEW)
        sm.transition_to(AgentExecutionState.SUBMITTING)
        self.assertEqual(sm.state, AgentExecutionState.SUBMITTING)


if __name__ == "__main__":
    unittest.main()
