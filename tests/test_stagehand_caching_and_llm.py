"""Unit and integration tests for StagehandLLMAdapter and Stagehand v4 native caching."""

import asyncio
import json
import os
import tempfile
import unittest

from stagehand import (
    LLMMessageGenerateParams,
    LLMStructuredGenerateParams,
    LLMTextContent,
)
from stagehand._generated.models import (
    LLMJsonSchemaResponseFormat,
    LLMMessage,
)

from app.services.automation.universal_agent.browser_agent import (
    StagehandBrowserAgent,
    StagehandLLMAdapter,
    UniversalSessionManager,
)
from tests.fixtures.harness.fake_ats_server import FakeATSServer


class TestStagehandLLMAdapter(unittest.IsolatedAsyncioTestCase):
    """Verifies LLM adapter conversion, mock generation, and callback protocol."""

    async def test_adapter_with_mock_structured_generator(self) -> None:
        def mock_gen(params):
            return {"recommended_action": "click", "target_selector": "#submit-btn"}

        adapter = StagehandLLMAdapter(mock_generator=mock_gen)
        callback = adapter.get_callback()
        self.assertTrue(callable(callback))

        # Build mock structured params
        msg = LLMMessage(
            role="user",
            content=[LLMTextContent(type="text", text="Find the submit button")],
        )
        fmt = LLMJsonSchemaResponseFormat(
            type="json_schema",
            name="action_schema",
            schema_={"type": "object", "properties": {"recommended_action": {"type": "string"}}},
        )
        params = LLMStructuredGenerateParams(
            messages=[msg],
            response_format=fmt,
            system_prompt="You are a browser assistant",
        )

        result = await callback(params)
        self.assertEqual(adapter.total_invocations, 1)
        self.assertEqual(result.output_format, "json_schema")
        self.assertIsNotNone(result.structured_content)
        # Verify content was serialized
        self.assertIn("recommended_action", json.loads(result.content[0].root.text))

    async def test_adapter_with_mock_text_generator(self) -> None:
        def mock_gen(params):
            return "Application form has 12 detected input fields."

        adapter = StagehandLLMAdapter(mock_generator=mock_gen)
        callback = adapter.get_callback()

        msg = LLMMessage(
            role="user",
            content=[LLMTextContent(type="text", text="Summarize this form")],
        )
        params = LLMMessageGenerateParams(
            messages=[msg],
            system_prompt="You are an analyst",
        )

        result = await callback(params)
        self.assertEqual(adapter.total_invocations, 1)
        self.assertEqual(result.output_format, "text")
        self.assertEqual(result.content[0].root.text, "Application form has 12 detected input fields.")


class TestStagehandCachingAndBrowserIntegration(unittest.IsolatedAsyncioTestCase):
    """Verifies Stagehand browser initialization with custom LLM adapter and native metrics."""

    async def asyncSetUp(self) -> None:
        self.server = FakeATSServer()
        self.base_url = self.server.start()

        self.temp_dir = tempfile.TemporaryDirectory()
        self.session_manager = UniversalSessionManager(profile_dir=self.temp_dir.name)
        self.agent = StagehandBrowserAgent(session_manager=self.session_manager)

    async def asyncTearDown(self) -> None:
        if self.agent.is_initialized:
            await self.agent.close()
        self.server.stop()
        self.temp_dir.cleanup()

    async def test_agent_initialization_with_llm_adapter_and_caching(self) -> None:
        def mock_ai_action(params):
            return {"action": "click", "selector": "#submit-application"}

        adapter = StagehandLLMAdapter(mock_generator=mock_ai_action)

        # 1. Initialize agent with LLM callback
        await self.agent.initialize(headless=True, model=adapter.get_callback())
        self.assertTrue(self.agent.is_initialized)

        # 2. Navigate to local fake ATS standard job page
        nav_success = await self.agent.navigate(f"{self.base_url}/standard-job")
        self.assertTrue(nav_success)

        # 3. Verify metrics API access
        self.assertIsNotNone(self.agent.stagehand)
        metrics = await self.agent.stagehand.metrics()
        self.assertIsNotNone(metrics)
        self.assertTrue(hasattr(metrics, "total_cached_input_tokens"))
        self.assertTrue(hasattr(metrics, "total_prompt_tokens"))

        # 4. Fill standard fields deterministically
        await self.agent.fill("#first_name", "Jane")
        await self.agent.fill("#last_name", "Doe")
        await self.agent.fill("#email", "jane.doe@example.com")
        await self.agent.fill("#phone", "+1 555-0199")

        # 5. Clean close
        await self.agent.close()
        self.assertFalse(self.agent.is_initialized)


if __name__ == "__main__":
    unittest.main()
