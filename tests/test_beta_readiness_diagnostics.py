"""Unit tests for beta readiness, versioning consistency, and sanitized diagnostics."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import app
from app.services.diagnostic_service import DiagnosticService
from app.services.sanitizer_service import LogSanitizer
from app.version import RELEASE_CHANNEL, VERSION


class TestBetaReadinessVersioning(unittest.TestCase):
    """Verifies single authoritative version invariants across package namespaces."""

    def test_authoritative_version_string(self):
        self.assertEqual(VERSION, "0.1.0-beta.1")
        self.assertEqual(RELEASE_CHANNEL, "private-beta")
        self.assertEqual(app.__version__, "0.1.0-beta.1")
        self.assertEqual(app.VERSION, "0.1.0-beta.1")


class TestDiagnosticService(unittest.TestCase):
    """Verifies that the diagnostic service compiles comprehensive sanitized telemetry."""

    def setUp(self):
        self.service = DiagnosticService()

    def test_generate_report_structure(self):
        report = self.service.generate_report()
        self.assertIsInstance(report, dict)
        self.assertIn("metadata", report)
        self.assertIn("system", report)
        self.assertIn("storage_paths", report)
        self.assertIn("database", report)
        self.assertIn("ai_configuration", report)
        self.assertIn("platforms", report)
        self.assertIn("workspace_readiness", report)
        self.assertIn("recent_diagnostic_logs", report)

        self.assertEqual(report["metadata"]["version"], "0.1.0-beta.1")
        self.assertEqual(report["metadata"]["release_channel"], "private-beta")
        self.assertEqual(report["metadata"]["application"], "JobPilot")

    def test_generate_markdown_content(self):
        md = self.service.generate_markdown()
        self.assertIsInstance(md, str)
        self.assertIn("# JobPilot Diagnostic Report", md)
        self.assertIn("0.1.0-beta.1", md)
        self.assertIn("System & Runtime Environment", md)
        self.assertIn("Storage & Filesystem", md)
        self.assertIn("Database & Schema Status", md)
        self.assertIn("Recent Diagnostic Logs (Sanitized)", md)

    def test_export_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "diag_test.md"
            exported = self.service.export_to_file(target_path)
            self.assertTrue(exported.exists())
            content = exported.read_text(encoding="utf-8")
            self.assertIn("JobPilot Diagnostic Report", content)
            self.assertIn("0.1.0-beta.1", content)

    def test_diagnostics_sanitizes_secrets(self):
        """Verifies that sensitive API keys and passwords never survive in diagnostic outputs."""
        secret_key = "sk-live1234567890abcdef1234567890abcdef"
        secret_pwd = "password=SuperSecretP@ssw0rd123!"

        with patch.object(self.service, "_collect_recent_logs", return_value=[
            f"Failed calling OpenAI with key {secret_key}",
            f"Database auth failure with {secret_pwd}",
        ]):
            report = self.service.generate_report()
            logs = report["recent_diagnostic_logs"]
            combined = "\n".join(logs)

            self.assertNotIn(secret_key, combined)
            self.assertNotIn("SuperSecretP@ssw0rd123!", combined)
            self.assertIn("[REDACTED_API_KEY]", combined)
            self.assertIn("password=[REDACTED]", combined)


if __name__ == "__main__":
    unittest.main()
