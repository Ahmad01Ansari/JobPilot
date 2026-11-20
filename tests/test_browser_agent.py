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
        self.assertTrue(mgr.get_user_data_dir().endswith("universal") or mgr.get_user_data_dir().endswith(".jobpilot-universal-profile"))
        self.assertTrue(os.path.exists(mgr.get_user_data_dir()))

        opts = mgr.get_launch_options(headless=True)
        self.assertTrue(opts["headless"])
        self.assertEqual(opts["viewport_width"], 1280)
        self.assertEqual(opts["viewport_height"], 800)
        self.assertTrue(opts["preserve_user_data_dir"])

    def test_session_manager_headed_launch_options_start_maximized(self) -> None:
        """Verifies that non-headless launch options configure Chrome for maximized launch without default fixed size."""
        mgr = UniversalSessionManager()
        opts = mgr.get_launch_options(headless=False)
        self.assertFalse(opts["headless"])
        self.assertIsNone(opts["viewport_width"])
        self.assertIsNone(opts["viewport_height"])
        self.assertIn("--start-maximized", opts["args"])
        self.assertIn("--window-position=0,0", opts["args"])
        self.assertIn("--window-size=1280,800", opts.get("ignore_default_args", []))


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

    async def test_ensure_maximized_invokes_cdp_set_window_bounds(self) -> None:
        """Verifies that _ensure_maximized issues CDP Browser.setWindowBounds with maximized state."""
        await self.agent.initialize(headless=True)
        self.agent._headless = False

        commands_sent = []
        attachment = getattr(self.agent.browser, "_attachment", None)
        if attachment and hasattr(attachment, "cdp_client"):
            orig_send = attachment.cdp_client.send_command
            async def mock_send(cmd: str, params: dict = None):
                commands_sent.append((cmd, params))
                if cmd == "Browser.getWindowForTarget":
                    return {"windowId": 9999}
                if cmd == "Browser.setWindowBounds":
                    return {}
                return await orig_send(cmd, params)
            attachment.cdp_client.send_command = mock_send

        await self.agent._ensure_maximized(self.agent.page)

        cdp_methods = [c[0] for c in commands_sent]
        self.assertIn("Browser.getWindowForTarget", cdp_methods)
        self.assertIn("Browser.setWindowBounds", cdp_methods)
        set_bounds_call = next(c for c in commands_sent if c[0] == "Browser.setWindowBounds")
        self.assertEqual(set_bounds_call[1]["bounds"]["windowState"], "maximized")
        self.assertEqual(set_bounds_call[1]["windowId"], 9999)


if __name__ == "__main__":
    unittest.main()
