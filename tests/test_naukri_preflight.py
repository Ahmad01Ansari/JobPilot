'''
Unit Tests for Naukri Production Preflight Checker (Phase 19)
Verifies diagnostic report generation, configuration checks, resume validation,
safety lock detection, and Chrome environment checks.
'''

import os
import unittest
from unittest.mock import patch, MagicMock

from platforms.naukri.preflight import (
    NaukriPreflightChecker,
    PreflightReport,
    PreflightCheckResult,
    run_preflight,
)


class TestNaukriPreflight(unittest.TestCase):
    def setUp(self):
        self.checker = NaukriPreflightChecker()

    def test_run_all_checks_healthy_system(self):
        with patch("platforms.naukri.preflight.get_resume", return_value="/tmp/test_resume.pdf"), \
             patch("platforms.naukri.preflight.os.path.exists", return_value=True), \
             patch("platforms.naukri.preflight.os.path.getsize", return_value=1024):
            report = self.checker.run_all_checks()
            self.assertIsInstance(report, PreflightReport)
            self.assertTrue(report.is_ready)
            self.assertGreaterEqual(len(report.checks), 6)

        # Check safety lock is detected as LOCKED by default
        safety_check = next((c for c in report.checks if "Safety Lock" in c.name), None)
        self.assertIsNotNone(safety_check)
        self.assertTrue(safety_check.passed)
        self.assertIn("LOCKED", safety_check.details)

    def test_missing_resume_triggers_critical_fail(self):
        with patch("platforms.naukri.preflight.get_resume", return_value="/nonexistent/path/to/resume.pdf"):
            report = self.checker.run_all_checks()
            resume_check = next(c for c in report.checks if "Resume" in c.name)
            self.assertFalse(resume_check.passed)
            self.assertTrue(resume_check.is_critical)
            self.assertFalse(report.is_ready)

    def test_unlocked_safety_lock_reported(self):
        mock_cfg = {"pause_before_submit": False}
        with patch("platforms.naukri.preflight.get_platform", return_value=mock_cfg):
            report = self.checker.run_all_checks()
            safety_check = next(c for c in report.checks if "Safety Lock" in c.name)
            self.assertTrue(safety_check.passed)
            self.assertIn("UNLOCKED", safety_check.details)

    def test_missing_chrome_triggers_critical_fail(self):
        with patch("platforms.naukri.preflight.get_installed_chrome_major_version", return_value=None):
            report = self.checker.run_all_checks()
            chrome_check = next(c for c in report.checks if "Chrome" in c.name)
            self.assertFalse(chrome_check.passed)
            self.assertFalse(report.is_ready)

    def test_report_summary_formatting(self):
        report = PreflightReport(checks=[
            PreflightCheckResult("Test Item 1", True, "All good", is_critical=True),
            PreflightCheckResult("Test Item 2", False, "Missing param", is_critical=False),
        ])
        summary = report.summary()
        self.assertIn("NAUKRI PRODUCTION PRE-FLIGHT READINESS REPORT", summary)
        self.assertIn("[PASS]", summary)
        self.assertIn("[WARN]", summary)
        self.assertIn("READY FOR PRODUCTION RUN", summary)


if __name__ == "__main__":
    unittest.main()
