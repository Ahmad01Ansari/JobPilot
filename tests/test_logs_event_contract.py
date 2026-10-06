"""Unit tests for AutomationEvent contracts, sanitization, and EventCorrelator."""

from datetime import datetime, timezone
import unittest

from app.services.logs.automation_event import (
    AutomationEvent,
    AutomationEventType,
    EventSource,
    LogFileReference,
)
from app.services.logs.event_correlator import EventCorrelator


class TestAutomationEventContract(unittest.TestCase):
    """Verifies event creation, sanitization, and serialization."""

    def test_event_initialization_and_fingerprint(self):
        event = AutomationEvent(
            run_id="run-100",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform="naukri",
            job_id=4821,
            application_id=1842,
            action="Submitted EasyApply",
            status="SUCCESS",
            message="Application submitted successfully for job 4821",
        )
        self.assertEqual(event.run_id, "run-100")
        self.assertEqual(event.event_type, AutomationEventType.APPLICATION_SUBMITTED)
        self.assertEqual(event.job_id, 4821)
        self.assertEqual(event.application_id, 1842)

        fp1 = event.get_fingerprint()
        self.assertTrue(len(fp1) == 64)  # SHA-256

        # Same attributes yield identical fingerprint
        event2 = AutomationEvent(
            run_id="run-100",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform="naukri",
            job_id=4821,
            application_id=1842,
            action="Submitted EasyApply",
            status="SUCCESS",
            message="Different human-readable text",  # Message text does NOT change fingerprint
        )
        self.assertEqual(event.get_fingerprint(), event2.get_fingerprint())

    def test_sanitization_preserves_identifiers_scrubs_secrets(self):
        secret_msg = "Submitted with password='SuperSecretPassword123' token=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 for job_id=4821"
        event = AutomationEvent(
            run_id="run-101",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform="linkedin",
            job_id=4821,
            application_id=1842,
            message=secret_msg,
            metadata={"api_key": "sk-123456789012345678901234", "candidate_id": 99},
        )

        # Message is scrubbed of password and bearer token
        self.assertNotIn("SuperSecretPassword123", event.message)
        self.assertIn("job_id=4821", event.message)
        self.assertEqual(event.job_id, 4821)

        # Metadata is scrubbed
        self.assertNotIn("sk-123456789012345678901234", str(event.metadata))
        self.assertEqual(event.metadata["candidate_id"], 99)

    def test_serialization_roundtrip(self):
        ref = LogFileReference(
            log_file="logs/log.txt",
            file_mtime=1700000000.0,
            line_number=420,
            byte_offset=84000,
            line_fingerprint="abc123def456",
        )
        event = AutomationEvent(
            event_id="evt-abc",
            run_id="run-200",
            sequence=7,
            source=EventSource.SIGNAL,
            level="ERROR",
            event_type=AutomationEventType.APPLICATION_FAILED,
            platform="indeed",
            job_id=500,
            application_id=12,
            company="Tech Corp",
            job_title="Software Engineer",
            action="Submit click timeout",
            status="FAILED",
            message="Failed to click submit button",
            metadata={"attempt": 3},
            raw_reference=ref,
        )

        d = event.to_dict()
        self.assertEqual(d["event_id"], "evt-abc")
        self.assertEqual(d["source"], "SIGNAL")
        self.assertEqual(d["raw_reference"]["line_number"], 420)

        restored = AutomationEvent.from_dict(d)
        self.assertEqual(restored.event_id, "evt-abc")
        self.assertEqual(restored.source, EventSource.SIGNAL)
        self.assertEqual(restored.event_type, AutomationEventType.APPLICATION_FAILED)
        self.assertEqual(restored.raw_reference.line_number, 420)
        self.assertEqual(restored.raw_reference.byte_offset, 84000)


class TestEventCorrelator(unittest.TestCase):
    """Verifies deduplication, monotonic sequencing, and error clustering."""

    def setUp(self):
        self.correlator = EventCorrelator(deduplication_window_seconds=2.0)

    def test_deduplication_and_raw_ref_merging(self):
        # 1. Primary SIGNAL event arrives
        sig_event = AutomationEvent(
            run_id="run-1",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform="naukri",
            job_id=4821,
            application_id=1842,
            action="Apply",
            status="SUCCESS",
            source=EventSource.SIGNAL,
            message="Application submitted via UI",
        )
        res1 = self.correlator.correlate(sig_event)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.sequence, 1)
        self.assertIsNone(res1.raw_reference)

        # 2. Fallback PARSED_LOG event arrives for the exact same occurrence
        ref = LogFileReference(
            log_file="logs/log.txt",
            file_mtime=1700000000.0,
            line_number=999,
            byte_offset=12345,
            line_fingerprint="fp123",
        )
        log_event = AutomationEvent(
            run_id="run-1",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
            platform="naukri",
            job_id=4821,
            application_id=1842,
            action="Apply",
            status="SUCCESS",
            source=EventSource.PARSED_LOG,
            message="[APPLICATION_CONFIRMED] Job: 4821",
            raw_reference=ref,
        )
        res2 = self.correlator.correlate(log_event)
        # MUST BE DROPPED AS DUPLICATE
        self.assertIsNone(res2)

        # But the raw reference MUST be merged into sig_event!
        self.assertIsNotNone(sig_event.raw_reference)
        self.assertEqual(sig_event.raw_reference.line_number, 999)

    def test_monotonic_sequences_per_run(self):
        e1 = AutomationEvent(run_id="run-A", event_type=AutomationEventType.SEARCH_STARTED, action="Search 1")
        e2 = AutomationEvent(run_id="run-B", event_type=AutomationEventType.SEARCH_STARTED, action="Search 1")
        e3 = AutomationEvent(run_id="run-A", event_type=AutomationEventType.JOB_DISCOVERED, job_id=101)

        r1 = self.correlator.correlate(e1)
        r2 = self.correlator.correlate(e2)
        r3 = self.correlator.correlate(e3)

        self.assertEqual(r1.sequence, 1)
        self.assertEqual(r2.sequence, 1)  # Separate run starts at 1
        self.assertEqual(r3.sequence, 2)  # run-A advances to 2

    def test_failure_clustering(self):
        # Two errors with dynamic job IDs and timestamps
        err1 = AutomationEvent(
            run_id="run-1",
            platform="naukri",
            stage="APPLICATION",
            event_type=AutomationEventType.APPLICATION_FAILED,
            message="Timeout locating submit button for job_12345 at 2026-10-05 21:00:00",
        )
        err2 = AutomationEvent(
            run_id="run-1",
            platform="naukri",
            stage="APPLICATION",
            event_type=AutomationEventType.APPLICATION_FAILED,
            message="Timeout locating submit button for job_99999 at 2026-10-05 21:05:12",
        )

        key1 = self.correlator.get_cluster_key(err1)
        key2 = self.correlator.get_cluster_key(err2)

        # Keys MUST match because dynamic job IDs and timestamps are normalized away!
        self.assertEqual(key1, key2)

        # Different error message gets a different cluster key
        err3 = AutomationEvent(
            run_id="run-1",
            platform="naukri",
            stage="APPLICATION",
            event_type=AutomationEventType.APPLICATION_FAILED,
            message="Screening question 'Are you willing to relocate?' was unanswered",
        )
        key3 = self.correlator.get_cluster_key(err3)
        self.assertNotEqual(key1, key3)


if __name__ == "__main__":
    unittest.main()
