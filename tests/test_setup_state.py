"""
Unit tests for SetupState and SetupEvent persistence.
"""

import tempfile
import unittest
from pathlib import Path

from app.services.setup.setup_state import SetupState, SetupEvent, SETUP_SCHEMA_VERSION


class TestSetupState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "test_setup.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_state(self):
        state = SetupState()
        self.assertEqual(state.setup_schema_version, SETUP_SCHEMA_VERSION)
        self.assertFalse(state.is_completed)
        self.assertEqual(state.current_step, "welcome")
        self.assertEqual(state.completed_steps, [])

    def test_save_and_load(self):
        state = SetupState()
        state.mark_step_completed("resume")
        state.mark_step_skipped("ai_provider")
        state.active_resume_id = "42"
        success = state.save(self.state_file)
        self.assertTrue(success)
        self.assertTrue(self.state_file.exists())

        loaded = SetupState.load(self.state_file)
        self.assertEqual(loaded.completed_steps, ["resume"])
        self.assertEqual(loaded.skipped_steps, ["ai_provider"])
        self.assertEqual(loaded.active_resume_id, "42")

    def test_secret_redaction_invariant(self):
        state = SetupState()
        # Log an event containing a fake key or password
        state.log_event("TEST", "ai", "Saved api_key successfully")
        event = state.events[-1]
        self.assertNotIn("api_key", event.summary)
        self.assertIn("[REDACTED]", event.summary)


if __name__ == "__main__":
    unittest.main()
