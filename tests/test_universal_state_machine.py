"""Unit tests for UniversalApplicationStateMachine, three-way enums, and AgentRunTimeline."""

import unittest

from app.services.automation.universal_agent import (
    AgentExecutionState,
    AgentRunTimeline,
    IllegalStateTransitionError,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)


class TestUniversalApplicationStateMachine(unittest.TestCase):
    """Verifies state transitions, V1 review gate enforcement, interventions, and timeline logging."""

    def setUp(self) -> None:
        self.timeline = AgentRunTimeline(run_id="test-run-001")
        self.sm = UniversalApplicationStateMachine(timeline=self.timeline)

    def test_initial_state(self) -> None:
        self.assertEqual(self.sm.state, AgentExecutionState.IDLE)
        self.assertEqual(self.sm.intervention_reason, InterventionReason.NONE)
        self.assertEqual(self.sm.terminal_result, TerminalResult.NONE)
        self.assertEqual(len(self.timeline.events), 0)

    def test_standard_happy_path(self) -> None:
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        self.sm.transition_to(AgentExecutionState.UPLOADING_RESUME)
        self.sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        self.sm.transition_to(AgentExecutionState.SUBMITTING)
        self.sm.transition_to(AgentExecutionState.VERIFYING_SUBMISSION)
        self.sm.complete(TerminalResult.SUCCESS_SUBMITTED, message="Applied successfully")

        self.assertEqual(self.sm.state, AgentExecutionState.COMPLETED)
        self.assertEqual(self.sm.terminal_result, TerminalResult.SUCCESS_SUBMITTED)
        self.assertEqual(len(self.timeline.events), 10)

        # Verify timeline serialization
        dict_list = self.timeline.to_dict_list()
        self.assertEqual(len(dict_list), 10)
        self.assertEqual(dict_list[-1]["state"], "COMPLETED")
        self.assertEqual(dict_list[-1]["metadata"]["terminal_result"], "SUCCESS_SUBMITTED")

    def test_v1_human_review_gate_enforcement(self) -> None:
        """In V1, automatic submission is prohibited: submitting must pass through PENDING_HUMAN_REVIEW."""
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)

        # Direct transition from FILLING_FORM to SUBMITTING is strictly illegal!
        with self.assertRaises(IllegalStateTransitionError):
            self.sm.transition_to(AgentExecutionState.SUBMITTING)

        # Direct transition from UPLOADING_RESUME to SUBMITTING is also illegal!
        self.sm.transition_to(AgentExecutionState.UPLOADING_RESUME)
        with self.assertRaises(IllegalStateTransitionError):
            self.sm.transition_to(AgentExecutionState.SUBMITTING)

        # Transition to PENDING_HUMAN_REVIEW first
        self.sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        # Now transition to SUBMITTING is permitted!
        self.sm.transition_to(AgentExecutionState.SUBMITTING)
        self.assertEqual(self.sm.state, AgentExecutionState.SUBMITTING)

    def test_multi_page_wizard_transitions(self) -> None:
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        # Step 1 -> Next Step
        self.sm.transition_to(AgentExecutionState.NAVIGATING_NEXT_STEP)
        # Step 2 -> Analyze & Fill
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)
        self.sm.transition_to(AgentExecutionState.FILLING_FORM)
        self.sm.transition_to(AgentExecutionState.PENDING_HUMAN_REVIEW)
        self.assertEqual(self.sm.state, AgentExecutionState.PENDING_HUMAN_REVIEW)

    def test_pause_for_captcha_and_resume(self) -> None:
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)

        # Detect CAPTCHA challenge
        self.sm.pause_for_intervention(
            reason=InterventionReason.CAPTCHA_CHALLENGE,
            message="Cloudflare Turnstile challenge detected",
        )
        self.assertEqual(self.sm.state, AgentExecutionState.PAUSED_FOR_INTERVENTION)
        self.assertEqual(self.sm.intervention_reason, InterventionReason.CAPTCHA_CHALLENGE)
        self.assertEqual(self.sm.previous_active_state, AgentExecutionState.NAVIGATING)

        # User solves challenge and resumes
        self.sm.resume_from_intervention(message="User completed captcha")
        self.assertEqual(self.sm.state, AgentExecutionState.NAVIGATING)
        self.assertEqual(self.sm.intervention_reason, InterventionReason.NONE)
        self.assertIsNone(self.sm.previous_active_state)

    def test_pause_for_unknown_field_and_manual_takeover(self) -> None:
        self.sm.transition_to(AgentExecutionState.INITIALIZING)
        self.sm.transition_to(AgentExecutionState.NAVIGATING)
        self.sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.sm.transition_to(AgentExecutionState.MAPPING_FIELDS)

        # Missing mandatory screening question
        self.sm.pause_for_intervention(
            reason=InterventionReason.UNKNOWN_REQUIRED_FIELD,
            message="Candidate has no answer for security clearance requirement",
        )
        self.assertEqual(self.sm.intervention_reason, InterventionReason.UNKNOWN_REQUIRED_FIELD)

        # User chooses to complete manually
        self.sm.complete(
            TerminalResult.MANUAL_REQUIRED,
            message="Candidate completed submission manually",
        )
        self.assertEqual(self.sm.state, AgentExecutionState.COMPLETED)
        self.assertEqual(self.sm.terminal_result, TerminalResult.MANUAL_REQUIRED)

    def test_transition_listener(self) -> None:
        events = []

        def listener(old_state, new_state, reason, msg):
            events.append((old_state, new_state, msg))

        self.sm.add_listener(listener)
        self.sm.transition_to(AgentExecutionState.INITIALIZING, message="Booting session")
        self.sm.transition_to(AgentExecutionState.NAVIGATING, message="Loading URL")

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0], (AgentExecutionState.IDLE, AgentExecutionState.INITIALIZING, "Booting session"))
        self.assertEqual(events[1], (AgentExecutionState.INITIALIZING, AgentExecutionState.NAVIGATING, "Loading URL"))

    def test_invalid_pause_reason_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.sm.pause_for_intervention(InterventionReason.NONE, "Invalid pause")


if __name__ == "__main__":
    unittest.main()
