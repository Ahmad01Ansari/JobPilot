"""Unit tests for RunObservabilityContext, RunRegistry, and RunPersistenceBridge."""

import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.logs.automation_event import AutomationEvent, AutomationEventType, EventSource
from app.services.logs.run_context import RunObservabilityContext, RunRegistry
from app.services.logs.run_persistence_bridge import RunPersistenceBridge


class TestRunObservability(unittest.TestCase):
    """Verifies multi-run telemetry, metric scoping, and database persistence."""

    def setUp(self):
        # In-memory SQLite for testing persistence
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        self.registry = RunRegistry()
        self.bridge = RunPersistenceBridge(
            registry=self.registry,
            session_factory=self.session_factory,
        )

    def tearDown(self):
        Base.metadata.drop_all(self.engine)

    def test_multi_run_isolation(self):
        # Run A: Naukri (running)
        e_a1 = AutomationEvent(
            run_id="run-naukri",
            platform="naukri",
            event_type=AutomationEventType.JOB_DISCOVERED,
            metadata={"count": 5},
        )
        e_a2 = AutomationEvent(
            run_id="run-naukri",
            platform="naukri",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
        )

        # Run B: Universal ATS (action required)
        e_b1 = AutomationEvent(
            run_id="run-universal",
            platform="universal",
            event_type=AutomationEventType.CAPTCHA_DETECTED,
            message="Solve Cloudflare challenge",
        )

        self.bridge.handle_event(e_a1)
        self.bridge.handle_event(e_a2)
        self.bridge.handle_event(e_b1)

        ctx_a = self.registry.get("run-naukri")
        ctx_b = self.registry.get("run-universal")

        self.assertIsNotNone(ctx_a)
        self.assertIsNotNone(ctx_b)

        # Scoped metrics are completely isolated!
        self.assertEqual(ctx_a.jobs_discovered, 5)
        self.assertEqual(ctx_a.applications_submitted, 1)
        self.assertEqual(len(ctx_a.active_interventions), 0)

        self.assertEqual(ctx_b.jobs_discovered, 0)
        self.assertEqual(ctx_b.applications_submitted, 0)
        self.assertEqual(ctx_b.status, "ACTION_REQUIRED")
        self.assertEqual(len(ctx_b.active_interventions), 1)

    def test_persistence_to_sqlite(self):
        evt = AutomationEvent(
            run_id="run-persist-1",
            platform="linkedin",
            event_type=AutomationEventType.APPLICATION_SUBMITTED,
        )
        self.bridge.handle_event(evt)

        # Finalize run
        stop_evt = AutomationEvent(
            run_id="run-persist-1",
            platform="linkedin",
            event_type=AutomationEventType.RUN_COMPLETED,
            action="All keywords processed",
        )
        self.bridge.handle_event(stop_evt)

        history = self.bridge.list_historical_runs()
        self.assertEqual(len(history), 1)
        record = history[0]
        self.assertEqual(record["run_id"], "run-persist-1")
        self.assertEqual(record["platform"], "linkedin")
        self.assertEqual(record["status"], "COMPLETED")
        self.assertEqual(record["applications_submitted"], 1)


if __name__ == "__main__":
    unittest.main()
