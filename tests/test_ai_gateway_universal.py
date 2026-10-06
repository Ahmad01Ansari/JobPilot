"""Comprehensive automated test suite for the Universal AI Gateway & Adapters.

Tests:
1. FakeOpenAIServer deterministic interactions
2. OpenAICompatibleAdapter chat, structured JSON, 401 auth, 429 rate limit, 404 model discovery
3. AISchemaValidator bracket slicing, markdown cleanup, schema mismatch
4. Provider-scoped secrets and zero-cloud-key sync to profile.json
5. AIGateway end-to-end integration and UniversalAIService façade
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.services.ai.adapters.openai_adapter import OpenAICompatibleAdapter
from app.services.ai.errors import AuthenticationError, RateLimitError
from app.services.ai.gateway import AIGateway
from app.services.ai.models import AICapability, AIRequest
from app.services.ai.provider_registry import AIProviderRegistry
from app.services.ai.schema_validator import AISchemaValidator
from app.services.ai_service import UniversalAIService
from app.services.secrets_service import SecretsService
from tests.fixtures.fake_openai_server import FakeOpenAIServer


class TestAIGatewayUniversal(unittest.TestCase):
    """Test suite covering adapters, gateway, validation, and security invariants."""

    @classmethod
    def setUpClass(cls):
        # Spin up local mock server on ephemeral port
        cls.fake_server = FakeOpenAIServer()
        cls.fake_server.start()

    @classmethod
    def tearDownClass(cls):
        cls.fake_server.stop()

    def setUp(self):
        self.fake_server.set_scenario("normal")
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_ai.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", future=True)
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine, future=True)

        self.key_path = os.path.join(self.temp_dir, ".master_key")
        self.secrets_service = SecretsService(key_path=self.key_path, session_factory=self.Session)
        self.gateway = AIGateway(session_factory=self.Session)
        self.ai_service = UniversalAIService(session_factory=self.Session, gateway=self.gateway, secrets_service=self.secrets_service)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. ADAPTER & FAKE SERVER TESTS
    # =========================================================================
    def test_openai_adapter_chat_normal(self):
        adapter = OpenAICompatibleAdapter()
        req = AIRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="test-mock-model",
        )
        resp = adapter.chat(req, base_url=self.fake_server.base_url, api_key="valid_token")
        self.assertIn("Simulated AI completion", resp.content)
        self.assertGreaterEqual(resp.latency_ms, 0)
        self.assertEqual(resp.usage.total_tokens, 35)

    def test_openai_adapter_auth_failure(self):
        self.fake_server.set_scenario("auth_fail")
        adapter = OpenAICompatibleAdapter()
        req = AIRequest(messages=[{"role": "user", "content": "ping"}], model="m")
        with self.assertRaises(AuthenticationError):
            adapter.chat(req, base_url=self.fake_server.base_url, api_key="bad_token")

    def test_openai_adapter_rate_limit(self):
        self.fake_server.set_scenario("rate_limit", retry_after=2)
        adapter = OpenAICompatibleAdapter()
        req = AIRequest(messages=[{"role": "user", "content": "ping"}], model="m")
        with self.assertRaises(RateLimitError) as ctx:
            adapter.chat(req, base_url=self.fake_server.base_url, api_key="key")
        self.assertEqual(ctx.exception.retry_after_seconds, 2.0)

    def test_openai_adapter_model_discovery(self):
        adapter = OpenAICompatibleAdapter()
        models, err = adapter.list_models(base_url=self.fake_server.base_url, api_key="key")
        self.assertIsNone(err)
        self.assertGreaterEqual(len(models), 1)
        model_ids = [m.id for m in models]
        self.assertIn("test-mock-model", model_ids)

    def test_openai_adapter_model_discovery_unsupported_not_failing(self):
        self.fake_server.set_scenario("no_models")
        adapter = OpenAICompatibleAdapter()
        models, err = adapter.list_models(base_url=self.fake_server.base_url, api_key="key")
        self.assertEqual(len(models), 0)
        self.assertIn("manual", err.lower())

    # =========================================================================
    # 2. SCHEMA VALIDATION TESTS
    # =========================================================================
    def test_schema_validator_bracket_slicing(self):
        raw = "Here is the JSON you requested:\n```json\n{\n  \"score\": 90,\n  \"summary\": \"Good\"\n}\n```\nHope that helps!"
        res = AISchemaValidator.validate(raw, expected_schema={"score": 0, "summary": ""})
        self.assertTrue(res.success)
        self.assertEqual(res.data["score"], 90)
        self.assertEqual(res.data["summary"], "Good")

    def test_schema_validator_syntax_error(self):
        raw = "Some corrupt output { missing_quotes: yes }"
        res = AISchemaValidator.validate(raw)
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "invalid_json")

    def test_schema_validator_reasoning_and_think_tags(self):
        raw = "<think>\nLet's evaluate the score: {\"preliminary\": 10}\n</think>\n```json\n{\"score\": 95, \"summary\": \"Excellent candidate\"}\n```"
        res = AISchemaValidator.validate(raw, expected_schema={"score": 0, "summary": ""})
        self.assertTrue(res.success)
        self.assertEqual(res.data["score"], 95)
        self.assertEqual(res.data["summary"], "Excellent candidate")

    def test_schema_validator_trailing_commas_repair(self):
        raw = '{"score": 88, "tags": ["python", "automation", ], }'
        res = AISchemaValidator.validate(raw)
        self.assertTrue(res.success)
        self.assertEqual(res.data["score"], 88)
        self.assertEqual(res.data["tags"], ["python", "automation"])

    def test_schema_validator_python_literal_dict(self):
        raw = "{'score': 85, 'passed': True, 'notes': 'Single quoted'}"
        res = AISchemaValidator.validate(raw)
        self.assertTrue(res.success)
        self.assertEqual(res.data["score"], 85)
        self.assertEqual(res.data["passed"], True)

    def test_schema_validator_unescaped_newlines_in_strings(self):
        raw = '{"summary": "Line 1\nLine 2\nLine 3", "score": 90}'
        res = AISchemaValidator.validate(raw)
        self.assertTrue(res.success)
        self.assertEqual(res.data["score"], 90)
        self.assertIn("Line 2", res.data["summary"])

    def test_schema_validator_schema_mismatch(self):
        raw = '{"name": "Alice"}'
        res = AISchemaValidator.validate(raw, expected_schema={"score": 0, "reason": ""})
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, "schema_mismatch")
        self.assertTrue(any("Missing required key" in e for e in res.validation_errors))

    # =========================================================================
    # 3. SECURITY & ZERO-CLOUD-KEY SYNC INVARIANT TESTS
    # =========================================================================
    def test_provider_scoped_secrets_isolation(self):
        # Store distinct keys for groq, xai, and ollama
        self.secrets_service.set_ai_secret("groq", "gsk_groq_secret_123")
        self.secrets_service.set_ai_secret("xai", "xai_secret_456")

        self.assertEqual(self.secrets_service.get_ai_secret("groq"), "gsk_groq_secret_123")
        self.assertEqual(self.secrets_service.get_ai_secret("xai"), "xai_secret_456")

    def test_zero_cloud_key_sync_to_profile_json(self):
        # 1. save_config stores secret in SecretsService
        self.ai_service.save_config(
            enabled=True,
            provider="groq",
            model="llama-3.3-70b-versatile",
            api_url="https://api.groq.com/openai/v1",
            api_key="gsk_super_secret_token",
        )
        saved_secret = self.secrets_service.get_ai_secret("groq")
        self.assertEqual(saved_secret, "gsk_super_secret_token")

        # 2. Verify _sync_to_profile_json never writes cloud secrets
        config_dir = os.path.join(self.temp_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        prof_file = os.path.join(config_dir, "profile.json")
        with open(prof_file, "w", encoding="utf-8") as f:
            json.dump({"ai": {}}, f)

        with patch("pathlib.Path.resolve") as m_res:
            m_res.return_value.parent.parent.parent = Path(self.temp_dir)
            self.ai_service._sync_to_profile_json(
                enabled=True,
                provider="groq",
                model="llama-3.3-70b-versatile",
                api_url="https://api.groq.com/openai/v1",
            )

        with open(prof_file, "r", encoding="utf-8") as f:
            synced = json.load(f)

        self.assertNotEqual(synced["ai"].get("api_key"), "gsk_super_secret_token")
        self.assertEqual(synced["ai"].get("api_key"), "MANAGED_BY_JOBPILOT_SECRETS_SERVICE")

    # =========================================================================
    # 4. PROVIDER REGISTRY & DOCUMENTATION INTEGRITY
    # =========================================================================
    def test_provider_registry_official_docs(self):
        for prov in AIProviderRegistry.list_providers():
            self.assertTrue(prov.docs_url.startswith("https://") or prov.docs_url.startswith("http://"))
            if prov.requires_api_key:
                self.assertIsNotNone(prov.api_key_url)
                self.assertTrue(prov.api_key_url.startswith("https://"))

    # =========================================================================
    # 5. GATEWAY & FAÇADE EXECUTION
    # =========================================================================
    def test_universal_ai_service_facade_text_and_structured(self):
        # Configure gateway to point to fake server
        self.ai_service.save_config(
            enabled=True,
            provider="groq",
            model="test-mock-model",
            api_url=self.fake_server.base_url,
            api_key="test_token",
        )

        # 1. Text generation
        txt = self.ai_service.generate_text("Say hello")
        self.assertIn("Simulated AI completion", txt)

        # 2. Structured JSON
        data = self.ai_service.extract_structured_json(
            prompt="Analyze candidate",
            schema_description=json.dumps({"semantic_score": 0, "semantic_summary": ""}),
        )
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("semantic_score"), 85)


if __name__ == "__main__":
    unittest.main()
