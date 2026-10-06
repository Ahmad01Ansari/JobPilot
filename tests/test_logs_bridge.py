"""Unit tests for LogNormalizer and AutomationLogBridge."""

import unittest
from PySide6.QtCore import QCoreApplication

from app.services.automation_events import (
    ApplicationSubmittedEvent,
    AutomationInterventionEvent,
    InterventionType,
    JobDiscoveredEvent,
    JobEvaluatedEvent,
)
from app.services.logs.automation_event import AutomationEventType, EventSource
from app.services.logs.automation_log_bridge import AutomationLogBridge
from app.services.logs.event_correlator import EventCorrelator
from app.services.logs.log_normalizer import LogNormalizer


class TestLogNormalizer(unittest.TestCase):
    """Verifies regex pattern matching on engine log tags."""

    def test_parse_application_confirmed(self):
        line = "[APPLICATION_CONFIRMED] Job: 'RPA Lead' | Company: 'Global Tech' | URL: 'https://naukri.com/job/1' | Platform: 'naukri' | Time: '2026-10-05 21:08:19'"
        event = LogNormalizer.parse_line(line, run_id="run-1", line_number=100)

        self.assertEqual(event.event_type, AutomationEventType.APPLICATION_SUBMITTED)
        self.assertEqual(event.source, EventSource.PARSED_LOG)
        self.assertEqual(event.platform, "naukri")
        self.assertEqual(event.job_title, "RPA Lead")
        self.assertEqual(event.company, "Global Tech")
        self.assertEqual(event.status, "SUCCESS")
        self.assertEqual(event.raw_reference.line_number, 100)

    def test_parse_submitter_confirmed(self):
        line = "[NaukriSubmitter] Submission confirmed for job 'naukri_submit_999': Success banner detected"
        event = LogNormalizer.parse_line(line, run_id="run-1")

        self.assertEqual(event.event_type, AutomationEventType.APPLICATION_SUBMITTED)
        self.assertEqual(event.platform, "naukri")
        self.assertEqual(event.engine, "Naukri")
        self.assertEqual(event.status, "SUCCESS")

    def test_parse_submitter_failure(self):
        line = "[NaukriSubmitter] ERROR: Submit button not found for job 'naukri_submit_999'"
        event = LogNormalizer.parse_line(line, run_id="run-1")

        self.assertEqual(event.event_type, AutomationEventType.APPLICATION_FAILED)
        self.assertEqual(event.level, "ERROR")
        self.assertEqual(event.status, "FAILED")

    def test_parse_safety_gate(self):
        line = "[NaukriSafetyGate] PAUSED: Review application above before proceeding."
        event = LogNormalizer.parse_line(line, run_id="run-1")

        self.assertEqual(event.event_type, AutomationEventType.MANUAL_INTERVENTION)
        self.assertEqual(event.level, "WARNING")
        self.assertEqual(event.status, "INTERVENTION")

    def test_parse_search_discovery(self):
        line = "[NaukriSearch] Discovered 5 job cards for 'RPA Developer'."
        event = LogNormalizer.parse_line(line, run_id="run-1")

        self.assertEqual(event.event_type, AutomationEventType.JOB_DISCOVERED)
        self.assertEqual(event.metadata["count"], 5)
        self.assertEqual(event.metadata["keyword"], "RPA Developer")

    def test_parse_fallback_raw_log(self):
        line = "Just some standard worker diagnostic information line."
        event = LogNormalizer.parse_line(line, run_id="run-1")

        self.assertEqual(event.event_type, AutomationEventType.RAW_LOG)
        self.assertEqual(event.source, EventSource.RAW)
        self.assertEqual(event.level, "INFO")


class TestAutomationLogBridge(unittest.TestCase):
    """Verifies typed worker signal integration and deduplication in the bridge."""

    @classmethod
    def setUpClass(cls):
        # Ensure a QCoreApplication instance exists for Qt signals
        cls._app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.correlator = EventCorrelator(deduplication_window_seconds=3.0)
        self.bridge = AutomationLogBridge(correlator=self.correlator)
        self.emitted_events = []
        self.bridge.event_emitted.connect(self.emitted_events.append)

    def test_typed_signals_emit_normalized_events(self):
        # 1. Job Discovered
        disc_evt = JobDiscoveredEvent(
            run_id="run-42",
            platform="naukri",
            title="Senior Automation Engineer",
            company="Enterprise Corp",
            external_job_id="ext-99",
        )
        self.bridge.on_job_discovered(disc_evt)
        self.assertEqual(len(self.emitted_events), 1)
        e1 = self.emitted_events[0]
        self.assertEqual(e1.event_type, AutomationEventType.JOB_DISCOVERED)
        self.assertEqual(e1.job_title, "Senior Automation Engineer")
        self.assertEqual(e1.company, "Enterprise Corp")

        # 2. Job Evaluated
        eval_evt = JobEvaluatedEvent(
            run_id="run-42",
            platform="naukri",
            title="Senior Automation Engineer",
            company="Enterprise Corp",
            is_qualified=True,
            reason="Matched 3/3 target skills",
        )
        self.bridge.on_job_evaluated(eval_evt)
        self.assertEqual(len(self.emitted_events), 2)
        e2 = self.emitted_events[1]
        self.assertEqual(e2.event_type, AutomationEventType.JOB_QUALIFIED)
        self.assertEqual(e2.status, "SUCCESS")

        # 3. Intervention Required
        int_evt = AutomationInterventionEvent(
            run_id="run-42",
            platform="naukri",
            intervention_type=InterventionType.CAPTCHA_DETECTED,
            message="Please solve Arkose challenge in browser",
        )
        self.bridge.on_intervention_required(int_evt)
        self.assertEqual(len(self.emitted_events), 3)
        e3 = self.emitted_events[2]
        self.assertEqual(e3.event_type, AutomationEventType.CAPTCHA_DETECTED)
        self.assertEqual(e3.status, "INTERVENTION")

    def test_deduplication_between_signal_and_log_tag(self):
        # A. ApplicationSubmittedEvent signal fires
        sub_evt = ApplicationSubmittedEvent(
            run_id="run-42",
            platform="naukri",
            title="Senior Automation Engineer",
            company="Enterprise Corp",
            job_id=4821,
        )
        self.bridge.on_application_submitted(sub_evt)
        self.assertEqual(len(self.emitted_events), 1)

        # B. Directly following, engine prints confirmation to log.txt and on_log_line is invoked
        log_line = "[APPLICATION_CONFIRMED] Job: 'Senior Automation Engineer' | Company: 'Enterprise Corp' | URL: 'https://naukri.com' | Platform: 'naukri' | Time: '2026-10-05 21:08:19'"
        self.bridge.on_log_line(log_line, run_id="run-42", line_number=500)

        # EXACTLY 1 EVENT MUST BE EMITTED! The log tag is deduplicated.
        self.assertEqual(len(self.emitted_events), 1)


if __name__ == "__main__":
    unittest.main()
