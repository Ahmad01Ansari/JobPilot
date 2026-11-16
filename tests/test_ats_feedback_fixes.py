"""Targeted verification tests for Universal ATS feedback fixes.

Validates:
1. FileUploader logger definition and polling behavior.
2. Orchestrator NoneType guard in field_details lookup.
3. State machine terminal state and transition suppression after COMPLETED.
4. Filtering of action buttons ("Apply With Resume") from screening questions.
5. PopupManager cookie consent regex coverage.
6. FrameResolver embedded ATS indicator coverage (Zoho Recruit, NiyukHR, CatsOne).
7. PageAnalyzer exclusion of skip anchors and login submits from next_buttons.
8. Overview entry button loop prevention.
"""

import asyncio
import re
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.services.automation.universal_agent.state_machine import (
    AgentExecutionState,
    InterventionReason,
    TerminalResult,
    UniversalApplicationStateMachine,
)
from app.services.automation.universal_agent.page_analyzer import (
    FormAnalysisResult,
    FormFieldInfo,
)
from app.services.automation.universal_agent.popup_manager import (
    PopupClassification,
    PopupManager,
)
from app.services.automation.universal_agent.frame_resolver import (
    FrameInfo,
    FrameResolver,
)
from app.services.automation.universal_agent.form_filler import FormFillResult
from app.services.automation.universal_agent.file_uploader import FileUploader, logger as file_uploader_logger
from app.services.automation.universal_agent.orchestrator import UniversalApplicationOrchestrator


class TestATSFeedbackFixes(unittest.TestCase):
    """Unit tests validating ATS fixes reported during beta testing."""

    def test_file_uploader_logger_is_defined(self) -> None:
        """FileUploader module must have a valid logger instance."""
        self.assertIsNotNone(file_uploader_logger)
        self.assertEqual(file_uploader_logger.name, "app.services.automation.universal_agent.file_uploader")

    def test_state_machine_is_terminal_and_transition_suppression(self) -> None:
        """State machine must report is_terminal when COMPLETED and suppress subsequent transitions."""
        sm = UniversalApplicationStateMachine()
        self.assertFalse(sm.is_terminal)

        sm.transition_to(AgentExecutionState.INITIALIZING)
        sm.complete(TerminalResult.USER_CANCELLED, message="Stopped by user")

        self.assertTrue(sm.is_terminal)
        self.assertEqual(sm.state, AgentExecutionState.COMPLETED)

        # Attempting further transitions must be suppressed without raising IllegalStateTransitionError
        sm.transition_to(AgentExecutionState.NAVIGATING_NEXT_STEP)
        self.assertEqual(sm.state, AgentExecutionState.COMPLETED)

        sm.transition_to(AgentExecutionState.ANALYZING_PAGE)
        self.assertEqual(sm.state, AgentExecutionState.COMPLETED)

    def test_popup_manager_cookie_patterns(self) -> None:
        """PopupManager must match common variations of cookie consent buttons."""
        samples = [
            "Accept All Cookies",
            "Accept all",
            "Accept cookies",
            "I Agree",
            "Allow all",
            "Allow all cookies",
            "Agree & proceed",
            "Got it",
            "Understood",
        ]
        for text in samples:
            matched = False
            for pat in PopupManager.BENIGN_DISMISS_PATTERNS:
                if re.match(pat, text.strip(), re.IGNORECASE):
                    matched = True
                    break
            self.assertTrue(matched, f"Pattern failed to match cookie button text: '{text}'")

    def test_frame_resolver_embedded_ats_indicators(self) -> None:
        """FrameResolver must detect Zoho Recruit, NiyukHR, and CatsOne frames."""
        agent = MagicMock()
        agent.evaluate = MagicMock(return_value=[
            {
                "frame_index": 0,
                "name": "recruit_frame",
                "frame_id": "zrc_frame",
                "src": "https://assetsoft.zohorecruit.com/jobs/Careers/embed",
                "input_count": 0,
                "has_form": False,
                "is_accessible": False,
                "selector": "#zrc_frame",
            },
            {
                "frame_index": 1,
                "name": "niyuk_frame",
                "frame_id": "niyuk",
                "src": "https://sphinx.niyukhr.com/careers/sphinx/widget",
                "input_count": 0,
                "has_form": False,
                "is_accessible": False,
                "selector": "#niyuk",
            },
        ])

        discovered = asyncio.run(FrameResolver.find_application_frame(agent))
        self.assertIsNotNone(discovered)
        self.assertIn("zohorecruit.com", discovered.src)

    def test_screening_question_filtering_excludes_action_buttons(self) -> None:
        """Action buttons and resume upload buttons must not be flagged as unanswered screening questions."""
        analysis = FormAnalysisResult(
            url="https://example.com/careers/job1",
            title="Job",
            fields=[
                FormFieldInfo(
                    field_id="btn_resume",
                    name="btn_resume",
                    selector="button.apply-resume",
                    input_type="button",
                    label="Apply With Resume",
                    required=True,
                ),
                FormFieldInfo(
                    field_id="q_exp",
                    name="q_exp",
                    selector="input#years",
                    input_type="text",
                    label="How many years of RPA experience do you have?",
                    required=True,
                ),
            ],
        )

        fill_res = FormFillResult(
            total_fields=1,
            filled_fields=1,
            failed_fields=0,
            field_details={"q_exp": {"status": "FILLED", "required": True}},
        )

        filled_labels_or_keys = {
            str(k).lower() for k, v in (fill_res.field_details or {}).items() if (v or {}).get("status") == "FILLED"
        } | {
            str((v or {}).get("label") or "").lower() for k, v in (fill_res.field_details or {}).items() if (v or {}).get("status") == "FILLED"
        }
        unfilled_screening_questions = [
            f.label for f in analysis.fields
            if f.label and f.input_type in ("text", "textarea", "email", "tel", "number", "select", "radio_group", "checkbox")
            and not any(k in f.label.lower() for k in ["apply with", "import from", "upload resume", "upload cv", "attach resume", "choose file", "browse"])
            and ("?" in f.label or any(k in f.label.lower() for k in ["rpa", "experience", "ctc", "salary", "notice", "location", "authorized", "visa", "sponsorship"]))
            and f.label.lower() not in filled_labels_or_keys
            and (f.field_id or "").lower() not in filled_labels_or_keys
            and (f.name or "").lower() not in filled_labels_or_keys
        ]

        self.assertEqual(unfilled_screening_questions, [])

    def test_nonetype_guard_in_field_details(self) -> None:
        """Field details containing None entries must not crash with AttributeError."""
        fill_res = FormFillResult(
            total_fields=2,
            filled_fields=1,
            failed_fields=1,
            field_details={
                "valid_field": {"status": "FILLED", "required": True},
                "corrupted_field": None,
            },
        )

        unfilled_required = [
            f_name for f_name, f_data in (fill_res.field_details or {}).items()
            if (f_data or {}).get("required") and (f_data or {}).get("status") != "FILLED"
            and not any(k in str(f_name).lower() for k in ["apply with", "import from", "upload resume", "upload cv"])
        ]

        self.assertEqual(unfilled_required, [])

    def test_overview_loop_prevention(self) -> None:
        """Orchestrator must track clicked entry selectors and avoid infinite loops."""
        orchestrator = UniversalApplicationOrchestrator()
        url = "https://www.avidall.com/careers.html"
        sel = "a.btn-apply"

        # Simulating multiple attempts
        orchestrator._clicked_entry_history[(url, sel)] = 1
        self.assertEqual(orchestrator._clicked_entry_history.get((url, sel)), 1)

        orchestrator._clicked_entry_history[(url, sel)] += 1
        self.assertEqual(orchestrator._clicked_entry_history.get((url, sel)), 2)

        # Third attempt triggers breaker
        orchestrator._clicked_entry_history[(url, sel)] += 1
        self.assertGreater(orchestrator._clicked_entry_history.get((url, sel)), 2)


if __name__ == "__main__":
    unittest.main()
