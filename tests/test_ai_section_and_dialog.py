"""Tests for AISection, ProviderCard, ProviderSetupDialog, and ModelDiscoveryWorker."""

import os
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Ensure offscreen Qt platform
os.environ["QT_QPA_PLATFORM"] = "offscreen"

app = QApplication.instance()
if app is None:
    app = QApplication([])

from app.services.ai.gateway import AIGateway
from app.services.ai.models import ModelInfo
from app.services.ai.provider_registry import AIProviderRegistry
from app.services.ai_service import UniversalAIService
from app.ui.views.settings.dialogs.provider_setup_dialog import ProviderSetupDialog
from app.ui.views.settings.sections.ai_section import AISection, ProviderCard
from app.ui.views.settings.workers.model_discovery_worker import ModelDiscoveryWorker


class TestAISectionAndDialog(unittest.TestCase):
    """Verifies that the redesigned AI section, dialogs, and workers operate reliably."""

    def setUp(self):
        self.mock_gateway = MagicMock(spec=AIGateway)
        self.mock_secrets = MagicMock()
        self.mock_secrets.get_ai_secret.return_value = "test-secret-key"
        self.mock_ai_service = MagicMock(spec=UniversalAIService)
        self.mock_ai_service.gateway = self.mock_gateway
        self.mock_ai_service.get_config.return_value = {
            "enabled": True,
            "provider": "ollama",
            "model": "llama3.1:8b",
            "api_url": "http://localhost:11434/v1",
            "api_key": "",
        }
        self.mock_ai_service.test_connection.return_value = (True, "Connected", 45.0)

        def mock_get_provider_config(prov):
            preset = AIProviderRegistry.get_provider(prov)
            return {
                "provider": prov,
                "model": preset.default_model if preset else "llama3.1:8b",
                "api_url": preset.default_base_url if preset else "http://localhost:11434/v1",
                "api_key": "",
            }
        self.mock_ai_service.get_provider_config.side_effect = mock_get_provider_config

    def test_provider_card_selection(self):
        preset = AIProviderRegistry.get_provider("groq")
        self.assertIsNotNone(preset)
        card = ProviderCard(preset)
        self.assertFalse(card._is_selected)

        card.set_selected(True)
        self.assertTrue(card._is_selected)
        card.set_selected(False)
        self.assertFalse(card._is_selected)

    def test_provider_setup_dialog_local_and_cloud(self):
        # Local provider dialog
        ollama_preset = AIProviderRegistry.get_provider("ollama")
        dlg_local = ProviderSetupDialog(ollama_preset)
        self.assertIn("Setup Guide", dlg_local.windowTitle())
        self.assertIn("Ollama", dlg_local.windowTitle())

        # Cloud provider dialog
        groq_preset = AIProviderRegistry.get_provider("groq")
        dlg_cloud = ProviderSetupDialog(groq_preset)
        self.assertIn("Groq", dlg_cloud.windowTitle())
        self.assertTrue(len(dlg_cloud.provider.setup_steps) > 0)

    def test_ai_section_initialization_and_defaults(self):
        section = AISection(
            ai_service=self.mock_ai_service,
            secrets_service=self.mock_secrets,
        )
        vals = section.get_values()
        self.assertEqual(vals["provider"], "ollama")
        self.assertEqual(vals["model"], "llama3.1:8b")
        self.assertEqual(vals["api_url"], "http://localhost:11434/v1")

    def test_ai_section_switching_providers(self):
        section = AISection(
            ai_service=self.mock_ai_service,
            secrets_service=self.mock_secrets,
        )

        # Switch to Groq
        section._select_provider("groq")
        vals = section.get_values()
        self.assertEqual(vals["provider"], "groq")
        self.assertIn("api.groq.com", vals["api_url"])
        self.assertFalse(section.btn_pricing_link.isHidden())

        # Switch to Gemini (URL should be disabled)
        section._select_provider("gemini")
        vals = section.get_values()
        self.assertEqual(vals["provider"], "gemini")
        self.assertFalse(section.txt_ai_url.isEnabled())

        # Switch to Custom OpenAI
        section._select_provider("custom_openai")
        vals = section.get_values()
        self.assertEqual(vals["provider"], "custom_openai")
        self.assertTrue(section.txt_ai_url.isEnabled())

    def test_ai_section_category_filters(self):
        section = AISection(
            ai_service=self.mock_ai_service,
            secrets_service=self.mock_secrets,
        )

        # Local filter
        section._apply_category_filter("local")
        self.assertFalse(section._cards["ollama"].isHidden())
        self.assertTrue(section._cards["groq"].isHidden())

        # Cloud filter
        section._apply_category_filter("cloud")
        self.assertTrue(section._cards["ollama"].isHidden())
        self.assertFalse(section._cards["groq"].isHidden())
        self.assertFalse(section._cards["xai"].isHidden())

        # Custom filter
        section._apply_category_filter("custom")
        self.assertFalse(section._cards["custom_openai"].isHidden())
        self.assertTrue(section._cards["groq"].isHidden())

        # All filter
        section._apply_category_filter("all")
        self.assertFalse(section._cards["ollama"].isHidden())
        self.assertFalse(section._cards["groq"].isHidden())

    def test_ai_section_load_and_reset_values(self):
        section = AISection(
            ai_service=self.mock_ai_service,
            secrets_service=self.mock_secrets,
        )

        section.load_values({
            "provider": "xai",
            "model": "grok-2",
            "api_url": "https://api.x.ai/v1",
            "api_key": "some-secret",
        })
        vals = section.get_values()
        self.assertEqual(vals["provider"], "xai")
        self.assertEqual(vals["model"], "grok-2")
        self.assertEqual(vals["api_url"], "https://api.x.ai/v1")
        self.assertEqual(section.txt_ai_key.text(), "••••••••")

        section.reset_to_defaults()
        vals_after = section.get_values()
        self.assertEqual(vals_after["provider"], "ollama")
        self.assertEqual(vals_after["model"], "llama3.1:8b")

    def test_model_discovery_worker(self):
        mock_gateway = MagicMock(spec=AIGateway)
        mock_gateway.discover_models.return_value = (
            [
                ModelInfo(id="custom-m1", name="Custom M1", description="4.2 GB"),
                ModelInfo(id="custom-m2", name="Custom M2", description="8.0 GB"),
            ],
            None,
        )

        worker = ModelDiscoveryWorker(
            endpoint_url="http://localhost:11434/v1",
            provider_id="ollama",
            gateway=mock_gateway,
        )

        results = []
        errors = []
        worker.result.connect(lambda models, err: (results.extend(models), errors.append(err)))
        worker.run()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "custom-m1")
        self.assertEqual(results[0]["size"], "4.2 GB")
        self.assertEqual(errors, [""])

    def test_azure_openai_support(self):
        from app.services.ai.adapters.openai_adapter import OpenAICompatibleAdapter
        adapter = OpenAICompatibleAdapter()

        # 1. Full Azure completion URL with query param
        full_url = "https://rpa-pdfextract-poc-openai.openai.azure.com/openai/deployments/gpt-4.1-mini/chat/completions?api-version=2025-01-01-preview"
        resolved_full = adapter.resolve_chat_endpoint(full_url, model="gpt-4.1-mini")
        self.assertEqual(resolved_full, full_url)

        # 2. Resource base URL -> auto-derives deployments completions endpoint
        base_url = "https://rpa-pdfextract-poc-openai.openai.azure.com"
        resolved_base = adapter.resolve_chat_endpoint(base_url, model="gpt-4.1-mini")
        self.assertIn("/openai/deployments/gpt-4.1-mini/chat/completions", resolved_base)
        self.assertIn("api-version=", resolved_base)

        # 3. Azure headers must include api-key
        headers = adapter._build_headers(api_key="my-azure-key")
        self.assertEqual(headers["api-key"], "my-azure-key")
        self.assertEqual(headers["Authorization"], "Bearer my-azure-key")

        # 4. Connectivity test fast-paths reachability for Azure
        ok, msg, _ = adapter.test_connectivity(full_url, api_key="my-azure-key")
        self.assertTrue(ok)
        self.assertIn("Azure OpenAI", msg)

        # 5. Azure preset exists in AIProviderRegistry
        preset = AIProviderRegistry.get_provider("azure_openai")
        self.assertIsNotNone(preset)
        self.assertEqual(preset.category, "cloud")
        self.assertTrue(preset.requires_api_key)

    def test_ai_section_save_provider_and_validation(self):
        section = AISection(
            ai_service=self.mock_ai_service,
            secrets_service=self.mock_secrets,
        )

        # 1. Invalid URL validation
        section.txt_ai_url.setText("nvidia/nemotron-3-ultra-550b-a55b")
        section._test_connection()
        self.assertIn("Invalid Endpoint URL", section.lbl_diag_status.text())

        # 2. Reset provider URL restores valid default
        section._select_provider("nvidia")
        section._reset_provider_url()
        self.assertEqual(section.txt_ai_url.text(), "https://integrate.api.nvidia.com/v1")

        # 3. Clear key
        section.txt_ai_key.setText("test-secret-value")
        section._clear_api_key()
        self.assertEqual(section.txt_ai_key.text(), "")

        # 4. Save provider settings directly (isolated provider config)
        section.txt_ai_url.setText("https://api.groq.com/openai/v1")
        section.txt_ai_key.setText("gsk_test123456789")
        section._save_provider_settings()
        self.mock_ai_service.save_provider_config.assert_called()
        self.assertIn("saved successfully", section.lbl_diag_status.text())

        # 5. Set as Default Engine (persists system default pointer)
        section._set_as_default_engine()
        self.mock_ai_service.save_config.assert_called()
        self.assertEqual(section._default_provider, "nvidia")
        self.assertIn("now the system default", section.lbl_diag_status.text())


if __name__ == "__main__":
    unittest.main()


