"""Unit tests for the JobPilot AI Pilot PySide6 UI components."""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Set headless environment for Qt tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

# Ensure QApplication singleton exists
app = QApplication.instance()
if not app:
    app = QApplication(sys.argv)

from app.services.pilot.pilot_models import (
    InterventionKind,
    InterventionStatus,
    PilotActionType,
    PilotAuthor,
    PilotIntervention,
    PilotMessage,
    PilotRuleChange,
    PilotStep,
)
from app.ui.views.pilot.composer import PilotComposer
from app.ui.views.pilot.pilot_view import PilotView
from app.ui.views.pilot.tag_bar import SmartTagBar
from app.ui.views.pilot.timeline_cards import (
    NeedsYouCard,
    PilotMessageCard,
    RuleChangeCard,
    UserMessageCard,
    format_pilot_markdown,
)


class TestPilotUIWidgets(unittest.TestCase):
    """Verifies UI widgets instantiate and emit signals correctly."""

    def test_format_pilot_markdown_renders_rich_html(self):
        text = "**Run automation**: 'run linkedin', 'run indeed'\n• **Check results**: 'today apply report'"
        formatted = format_pilot_markdown(text)
        self.assertIn("Run automation</b>", formatted)
        self.assertNotIn("**Run automation**", formatted)
        self.assertIn("&bull;", formatted)
        self.assertIn("Check results</b>", formatted)

    def test_format_pilot_markdown_eliminates_raw_hashtags(self):
        raw = "#### Languages\n• Python\n#### Executive Summary\nTop performer."
        formatted = format_pilot_markdown(raw)
        self.assertNotIn("####", formatted)
        self.assertNotIn("###", formatted)
        self.assertIn("Languages", formatted)
        self.assertIn("Executive Summary", formatted)

    def test_format_pilot_markdown_renders_tables(self):
        table_raw = "| Company | Role |\n|---|---|\n| Ncare MD | RPA Developer |"
        formatted = format_pilot_markdown(table_raw)
        self.assertIn("<table", formatted)
        self.assertIn("Ncare MD", formatted)
        self.assertIn("RPA Developer", formatted)

    def test_composer_emit(self):
        composer = PilotComposer()
        emitted_text = []
        composer.message_submitted.connect(lambda t: emitted_text.append(t))

        composer.set_text("Find 5 python jobs")
        composer._handle_submit()

        self.assertEqual(len(emitted_text), 1)
        self.assertEqual(emitted_text[0], "Find 5 python jobs")
        self.assertEqual(composer.editor.toPlainText(), "")

    def test_tag_bar_emit(self):
        tag_bar = SmartTagBar()
        selected = []
        tag_bar.tag_selected.connect(lambda p: selected.append(p))

        tag_bar.tag_selected.emit("Find remote Python developer jobs")
        self.assertEqual(len(selected), 1)
        self.assertIn("Python", selected[0])

    def test_user_message_card(self):
        msg = PilotMessage(author=PilotAuthor.USER, body="Hello Copilot")
        card = UserMessageCard(msg)
        self.assertIsNotNone(card)

    def test_pilot_message_card_with_steps(self):
        msg = PilotMessage(author=PilotAuthor.PILOT, body="Starting search...")
        msg.steps.append(PilotStep(title="Step 1: Inspecting index", status="done"))
        card = PilotMessageCard(msg)
        self.assertIsNotNone(card)

    def test_needs_you_card_2fa(self):
        inv = PilotIntervention(
            kind=InterventionKind.TWO_FACTOR,
            prompt="Enter LinkedIn 2FA",
            status=InterventionStatus.OPEN,
        )
        msg = PilotMessage(intervention=inv)
        card = NeedsYouCard(msg)

        answers = []
        card.answered.connect(lambda i_id, ans: answers.append((i_id, ans)))

        card.input_field.setText("123456")
        card._on_input_submitted()

        self.assertEqual(len(answers), 1)
        self.assertEqual(answers[0][1], "123456")

    def test_rule_change_card_undo(self):
        change = PilotRuleChange(
            rule_key="pilot.deal_breakers",
            description="Exclude clearance",
            can_undo=True,
        )
        msg = PilotMessage(rule_change=change)
        card = RuleChangeCard(msg)

        undos = []
        card.undo_clicked.connect(lambda c_id: undos.append(c_id))
        card.undo_clicked.emit(change.id)

        self.assertEqual(len(undos), 1)
        self.assertEqual(undos[0], change.id)

    def test_pilot_view_initialization(self):
        view = PilotView()
        self.assertIsNotNone(view)
        self.assertIsNotNone(view.composer)
        self.assertIsNotNone(view.tag_bar)
        self.assertIsNotNone(view.sidebar)

    def test_automation_console_box(self):
        from app.ui.views.pilot.timeline_cards import AutomationConsoleBox
        box = AutomationConsoleBox(platform_name="Naukri")
        self.assertEqual(box.height(), 248)
        self.assertIsNotNone(box.kpi_banner)
        self.assertIn("discovered", box.kpi_labels)
        self.assertIn("applied", box.kpi_labels)

        # Test metric updates
        box.update_metrics(discovered=15, evaluated=10, qualified=4, applied=2, skipped=6)
        self.assertEqual(box.kpi_labels["discovered"].text(), "15")
        self.assertEqual(box.kpi_labels["evaluated"].text(), "10")
        self.assertEqual(box.kpi_labels["qualified"].text(), "4")
        self.assertEqual(box.kpi_labels["applied"].text(), "2")
        self.assertEqual(box.kpi_labels["skipped"].text(), "6")

        box.set_active_step("Scanning jobs", status="running")
        self.assertIn("Scanning jobs", box.active_step_lbl.text())
        box.append_log("Log line 1")
        box.append_log("Candidate Evaluation: Qualified: RPA Developer")
        self.assertIn("Log line 1", box.log_view.toPlainText())
        self.assertIn("Qualified", box.log_view.toPlainText())
        box.mark_completed("Done all applies")
        self.assertIn("COMPLETED", box.status_badge.text())

    def test_pilot_view_stream_logs_without_recreation(self):
        view = PilotView()
        # Add an initial automation message
        auto_msg = PilotMessage(
            author=PilotAuthor.PILOT,
            body="Starting Naukri bot...",
            action_type=PilotActionType.START_AUTOMATION,
            payload={"platform": "naukri"},
        )
        view._handle_service_event_on_main_thread("message_added", auto_msg)
        initial_widget_count = view.timeline_layout.count()
        latest_card = view._latest_pilot_card
        self.assertIsNotNone(latest_card)
        self.assertIsNotNone(latest_card.console_box)

        # Stream 100 rapid steps/logs
        for i in range(100):
            step = PilotStep(title=f"Agent Action: Step {i}", status="running")
            view._handle_service_event_on_main_thread("step_emitted", step)

        # Widget count in layout must not change, and latest_card must be the exact same instance
        self.assertEqual(view.timeline_layout.count(), initial_widget_count)
        self.assertIs(view._latest_pilot_card, latest_card)
        self.assertIn("Step 99", latest_card.console_box.active_step_lbl.text())

        # Emit metrics_updated and verify KPI chips update in-place
        view._handle_service_event_on_main_thread("metrics_updated", {
            "jobs_discovered": 25,
            "jobs_evaluated": 18,
            "jobs_qualified": 7,
            "applications_submitted": 3,
            "jobs_skipped": 11,
        })
        self.assertEqual(latest_card.console_box.kpi_labels["discovered"].text(), "25")
        self.assertEqual(latest_card.console_box.kpi_labels["evaluated"].text(), "18")
        self.assertEqual(latest_card.console_box.kpi_labels["applied"].text(), "3")

    def test_agent_simulation_box(self):
        from app.ui.views.pilot.timeline_cards import AgentSimulationBox
        box = AgentSimulationBox(title="AI Copilot Reasoning")
        step1 = PilotStep(title="Analyzing requirements", status="running")
        box.add_or_update_step(step1)
        self.assertEqual(box.steps_layout.count(), 1)
        self.assertIn("RUN", box.status_badge.text())

        # Complete step
        step1.status = "done"
        box.add_or_update_step(step1)
        self.assertIn("DONE", box.status_badge.text())

    def test_pilot_message_card_update_message(self):
        msg = PilotMessage(
            author=PilotAuthor.PILOT,
            body="Inspecting database...",
            action_type=PilotActionType.GET_OFFERS,
            steps=[PilotStep(title="Step 1", status="running")]
        )
        card = PilotMessageCard(msg)
        self.assertIn("Inspecting database...", card.body.text())

        # Now simulate worker completion with full body
        msg.body = "Offer Analysis: RPA Developer at Ncare MD"
        msg.steps[0].status = "done"
        card.update_message(msg)
        self.assertIn("Ncare MD", card.body.text())
        self.assertIn("DONE", card.simulation_box.status_badge.text())

    def test_pilot_view_single_action_queueing(self):
        from unittest.mock import patch
        from app.ui.views.pilot.pilot_view import _PilotPromptWorker

        with patch.object(_PilotPromptWorker, "start", return_value=None):
            view = PilotView()
            self.assertFalse(view._is_busy)
            self.assertEqual(len(view._prompt_queue), 0)

            # Submit first prompt - sets busy
            view._on_prompt_submitted("first task")
            self.assertTrue(view._is_busy)

            # Submit second prompt while busy - enqueues
            view._on_prompt_submitted("second queued task")
            self.assertEqual(len(view._prompt_queue), 1)
            self.assertIn("second queued task", view._prompt_queue)

            # Simulate completion of first task
            reply1 = PilotMessage(author=PilotAuthor.PILOT, body="First task done")
            view._on_prompt_worker_done(reply1)

            # Second task should now be dequeued and running
            self.assertEqual(len(view._prompt_queue), 0)
            self.assertTrue(view._is_busy)

            # Complete second task
            reply2 = PilotMessage(author=PilotAuthor.PILOT, body="Second task done")
            view._on_prompt_worker_done(reply2)
            self.assertFalse(view._is_busy)
            self.assertTrue(view.composer.send_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()

