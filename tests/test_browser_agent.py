"""Unit tests for BrowserAgent, UniversalSessionManager, and StagehandBrowserAgent."""

import asyncio
import os
import tempfile
import unittest

from app.services.automation.universal_agent.browser_agent import (
    BrowserAgent,
    StagehandBrowserAgent,
    UniversalSessionManager,
)
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestUniversalSessionManager(unittest.TestCase):
    """Verifies profile directory management and launch configuration."""

    def test_session_manager_defaults(self) -> None:
        mgr = UniversalSessionManager()
        self.assertTrue(mgr.get_user_data_dir().endswith(".jobpilot-universal-profile"))
        self.assertTrue(os.path.exists(mgr.get_user_data_dir()))

        opts = mgr.get_launch_options(headless=True)
        self.assertTrue(opts["headless"])
        self.assertEqual(opts["viewport_width"], 1280)
        self.assertEqual(opts["viewport_height"], 800)
        self.assertTrue(opts["preserve_user_data_dir"])


class TestStagehandBrowserAgent(unittest.IsolatedAsyncioTestCase):
    """Verifies StagehandBrowserAgent against FakeATSServer."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        # Use an isolated temporary user data directory for testing
        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_agent_lifecycle_and_deterministic_actions(self) -> None:
        self.assertFalse(self.agent.is_initialized)

        # 1. Initialize
        await self.agent.initialize(headless=True)
        self.assertTrue(self.agent.is_initialized)

        # 2. Navigate
        nav_success = await self.agent.navigate(f"{self.base_url}/standard-job")
        self.assertTrue(nav_success)

        # 3. Check URL & Title
        url = await self.agent.get_url()
        self.assertIn("/standard-job", url)
        title = await self.agent.get_title()
        self.assertIn("Acme Corp", title)

        # 4. Fill form fields
        self.assertTrue(await self.agent.fill("#first_name", "Jane"))
        self.assertTrue(await self.agent.fill("#last_name", "Doe"))
        self.assertTrue(await self.agent.fill("#email", "jane.doe@example.com"))
        self.assertTrue(await self.agent.fill("#phone", "+1 555-0199"))

        # 5. Select dropdown option
        self.assertTrue(await self.agent.select_option("#years_experience", "3-5"))

        # 6. File upload
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 Mock Candidate Resume")
            temp_pdf = f.name

        try:
            upload_success = await self.agent.upload_file("#resume_upload", temp_pdf)
            self.assertTrue(upload_success)
        finally:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)

        # 7. Screenshot
        screenshot_bytes = await self.agent.screenshot()
        self.assertIsInstance(screenshot_bytes, bytes)
        self.assertTrue(len(screenshot_bytes) > 0)

        # 8. Close
        await self.agent.close()
        self.assertFalse(self.agent.is_initialized)


if __name__ == "__main__":
    unittest.main()
